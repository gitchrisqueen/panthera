"""Combine the NCAAF feeds: week ingest and the finals fallback chain.

Week ingest (`merge_week`) — CFBD /games is the schedule of record when
CFBD_API_KEY is set; ESPN's week scoreboard (keyless) supplies display
names, AP ranks, the indoor flag and live status, and is the whole schedule
when CFBD is unavailable. The two join on the game id: CFBD's game `id` IS
ESPN's event id (see clients/cfbd.py). The join is still checked — the
schools on both sides must agree, else the ESPN row is kept and the
disagreement logged. CFBD-only games (ESPN missed or failed) are stored
under their CFBD id with "School Mascot" names from /teams/fbs, so Odds API
matching and leg grading see the same name form as ESPN rows.

Finals chain (`ncaaf grade`, per ET date with pending legs):
  1. ESPN scoreboard by date                      (pipeline.refresh_games)
  2. CFBD /games for the game's week, id join      (`finals_from_cfbd`)
  3. ncaa-api scoreboard for the week, ET date +
     both schools                                  (`finals_from_ncaa`)
2 and 3 run only when ESPN errors for that date, and only fill games still
not Final/Postponed/Canceled. A game they cannot place is logged, never
guessed.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from ..clients.espn_cfb import CfbGame
from ..clients.ncaa_api import NcaaGame
from ..timeutil import game_date_et, parse_utc, utc_iso
from .matching import normalize_name

SETTLED = ("Final", "Postponed", "Canceled", "Cancelled")


def school_key(name: str, aliases: dict[str, str] | None = None) -> str:
    """Normalized school name. NCAA.com abbreviates State as "St."
    ("Ohio St.") where ESPN/CFBD spell it out, so a trailing " st" is
    expanded. Aliases (keys and values compared normalized) cover the rest."""
    alias = {_base_key(k): _base_key(v) for k, v in (aliases or {}).items()}
    k = _base_key(name)
    return alias.get(k, k)


def _base_key(name: str) -> str:
    k = normalize_name(name)
    return k[:-3] + " state" if k.endswith(" st") else k


def _isnull(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v))


# --- week ingest ------------------------------------------------------------


def cfbd_to_games(games_df: pd.DataFrame, display: dict[str, str]) -> list[CfbGame]:
    """CFBD /games rows -> CfbGame. `display` maps school -> "School Mascot"
    (cfbd.parse_teams); a school missing from it keeps its bare name."""
    out: list[CfbGame] = []
    for r in games_df.to_dict("records"):
        if _isnull(r.get("cfbd_game_id")) or not r.get("start_time_utc"):
            continue
        start = parse_utc(str(r["start_time_utc"]))
        final = bool(r.get("completed")) and not (
            _isnull(r.get("home_points")) or _isnull(r.get("away_points"))
        )
        out.append(
            CfbGame(
                event_id=str(int(r["cfbd_game_id"])),
                start_time_utc=utc_iso(start),
                game_date_et=str(game_date_et(start)),
                home_team=display.get(r["home_team"], r["home_team"]),
                away_team=display.get(r["away_team"], r["away_team"]),
                home_rank=None,
                away_rank=None,
                neutral_site=bool(r.get("neutral_site")),
                conference_game=bool(r.get("conference_game")),
                venue=r.get("venue") or "",
                indoor=None,
                status="Final" if final else "Scheduled",
                home_score=int(r["home_points"]) if final else None,
                away_score=int(r["away_points"]) if final else None,
                season=None if _isnull(r.get("season")) else int(r["season"]),
                season_type=r.get("season_type"),
                week=None if _isnull(r.get("week")) else int(r["week"]),
                home_school=r["home_team"],
                away_school=r["away_team"],
                score_source="cfbd" if final else "",
            )
        )
    return out


def _orientation(home_school: str, away_school: str, other_home: str, other_away: str):
    """True = same home team, False = home/away swapped (neutral sites),
    None = the schools disagree (or a side carries no school to check)."""
    h, a = school_key(home_school), school_key(away_school)
    oh, oa = school_key(other_home), school_key(other_away)
    if not (h and a):
        return None
    if (h, a) == (oh, oa):
        return True
    if (h, a) == (oa, oh):
        return False
    return None


def merge_week(
    espn_games: list[CfbGame], cfbd_games: list[CfbGame]
) -> tuple[list[CfbGame], list[str]]:
    """Return (games, warnings). See the module docstring for precedence."""
    espn_by_id = {g.event_id: g for g in espn_games}
    out: list[CfbGame] = []
    warnings: list[str] = []
    for c in cfbd_games:
        e = espn_by_id.pop(c.event_id, None)
        if e is None:
            out.append(c)
            continue
        same = _orientation(e.home_school, e.away_school, c.home_school, c.away_school)
        if same is None:
            warnings.append(
                f"{c.event_id}: ESPN {e.away_team} @ {e.home_team} vs CFBD "
                f"{c.away_school} @ {c.home_school} — kept ESPN row"
            )
            out.append(e)
            continue
        merged = replace(
            e,
            season=e.season or c.season,
            season_type=e.season_type or c.season_type,
            week=e.week or c.week,
            conference_game=c.conference_game,
        )
        if e.status not in SETTLED and c.status == "Final":
            hs, as_ = (c.home_score, c.away_score) if same else (c.away_score, c.home_score)
            merged = replace(
                merged, status="Final", home_score=hs, away_score=as_, score_source="cfbd"
            )
        out.append(merged)
    out.extend(espn_by_id.values())  # ESPN-only games (CFBD lagging)
    return out, warnings


CFBD_LINES_COLUMNS = [
    "fetched_ts_utc", "event_id", "season", "season_type", "week", "home_team",
    "away_team", "provider", "spread", "spread_open", "total", "total_open",
    "home_moneyline", "away_moneyline",
]


def cfbd_week_lines(
    lines_df: pd.DataFrame,
    games: list[CfbGame],
    display: dict[str, str],
    season_type: str,
    fetched_ts_utc: str,
) -> pd.DataFrame:
    """CFBD /lines rows keyed by event id, team names in the stored games'
    spelling. home/away stay CFBD's, because `spread` is signed from CFBD's
    home team (negative = that team favored)."""
    by_id = {g.event_id: g for g in games}
    rows = []
    for r in lines_df.to_dict("records"):
        if _isnull(r.get("cfbd_game_id")):
            continue
        eid = str(int(r["cfbd_game_id"]))
        home = display.get(r["home_team"], r["home_team"])
        away = display.get(r["away_team"], r["away_team"])
        g = by_id.get(eid)
        if g is not None:
            names = {school_key(g.home_school): g.home_team, school_key(g.away_school): g.away_team}
            home = names.get(school_key(r["home_team"]), home)
            away = names.get(school_key(r["away_team"]), away)
        rows.append(
            r | {"event_id": eid, "home_team": home, "away_team": away,
                 "season_type": season_type, "fetched_ts_utc": fetched_ts_utc}
        )
    return pd.DataFrame(rows).reindex(columns=CFBD_LINES_COLUMNS)


# --- finals fallbacks ---------------------------------------------------------


def _final_row(row: dict, home_score, away_score, source: str) -> dict:
    return row | {
        "status": "Final",
        "home_score": int(home_score),
        "away_score": int(away_score),
        "score_source": source,
    }


def finals_from_cfbd(targets: list[dict], cfbd_games: list[CfbGame]) -> list[dict]:
    """Fill stored game rows (dicts) from CFBD finals by event id."""
    by_id = {g.event_id: g for g in cfbd_games if g.status == "Final"}
    out = []
    for row in targets:
        c = by_id.get(str(row["event_id"]))
        if c is None:
            continue
        same = _orientation(
            _str(row.get("home_school")), _str(row.get("away_school")),
            c.home_school, c.away_school,
        )
        if same is False:
            out.append(_final_row(row, c.away_score, c.home_score, "cfbd"))
        else:  # True, or no stored schools: the id join alone decides
            out.append(_final_row(row, c.home_score, c.away_score, "cfbd"))
    return out


def _str(v) -> str:
    return "" if _isnull(v) else str(v)


def finals_from_ncaa(
    targets: list[dict], ncaa_games: list[NcaaGame], aliases: dict[str, str] | None = None
) -> tuple[list[dict], list[str]]:
    """Fill stored game rows from NCAA.com finals. A row matches a final
    with the same ET date whose two schools (short or seo name) equal the
    row's schools in either orientation; exactly one candidate is required.
    Returns (filled rows, unmatched descriptions)."""
    finals = [
        g for g in ncaa_games
        if g.state == "final" and g.game_date_et
        and g.home_score is not None and g.away_score is not None
    ]

    def keys(short: str, seo: str) -> set[str]:
        return {school_key(short, aliases), school_key(seo.replace("-", " "), aliases)} - {""}

    out, unmatched = [], []
    for row in targets:
        hs, as_ = school_key(_str(row.get("home_school")), aliases), school_key(
            _str(row.get("away_school")), aliases
        )
        label = f"{row['event_id']} ({row.get('away_team')} @ {row.get('home_team')})"
        if not (hs and as_):
            unmatched.append(f"{label}: no school names stored")
            continue
        hits = []
        for g in finals:
            if g.game_date_et != row["game_date_et"]:
                continue
            gh, ga = keys(g.home_short, g.home_seo), keys(g.away_short, g.away_seo)
            if hs in gh and as_ in ga:
                hits.append((g, True))
            elif hs in ga and as_ in gh:
                hits.append((g, False))
        if len(hits) != 1:
            unmatched.append(f"{label}: {len(hits)} NCAA.com finals match")
            continue
        g, same = hits[0]
        if same:
            out.append(_final_row(row, g.home_score, g.away_score, "ncaa_api"))
        else:
            out.append(_final_row(row, g.away_score, g.home_score, "ncaa_api"))
    return out, unmatched
