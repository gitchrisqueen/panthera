"""CollegeFootballData.com (CFBD) API client — NCAAF history and metrics.

Free key (`CFBD_API_KEY`, sent as a Bearer token; free tier has a monthly
call cap, so responses are cached under data/ncaaf/cfbd/). It covers four of
the cfb_spread_total_parlay export's five inputs:

  /games        schedule + finals, neutral site, conference game (week index
                for the letdown/look-ahead angle)
  /lines        per-provider spread/total with opening values — line movement,
                and the historical lines the backtest replays
  /ratings/sp   SP+ team ratings (offense/defense) — "advanced metrics"
  /venues       coordinates + dome flag — the weather angle's lookup key

plus the weekly-ingest and context endpoints:

  /teams/fbs    school -> mascot, so CFBD's school-only names ("Miami")
                can be shown as ESPN-style display names ("Miami Hurricanes")
  /rankings     weekly polls (AP, Coaches, CFP) per (season, week)
  /stats/season season-to-date team stats, long format (statName/statValue)

Game ids: CFBD's game `id` is ESPN's event id for the same game (CFBD sources
its schedule from ESPN; cfbfastR joins the two feeds on it). The NCAAF store
therefore keys CFBD games by `event_id = str(id)` with no name matching; the
merge in `ncaaf/sources.py` still cross-checks school names on every shared
id and logs a disagreement instead of trusting it.

Injury reports are not in CFBD; that input stays unavailable. Every parser
here is a pure function over the JSON payload so fixtures cover it offline.
"""

from __future__ import annotations

import json

import pandas as pd
import requests

from .. import paths

BASE = "https://api.collegefootballdata.com"
TIMEOUT = 30


class CfbdError(RuntimeError):
    pass


def get(
    endpoint: str,
    params: dict,
    api_key: str,
    session: requests.Session | None = None,
) -> list[dict]:
    if not api_key:
        raise CfbdError("CFBD_API_KEY is not set")
    sess = session or requests.Session()
    resp = sess.get(
        f"{BASE}/{endpoint.lstrip('/')}",
        params=params,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def cache_path(endpoint: str, params: dict):
    slug = endpoint.strip("/").replace("/", "_")
    suffix = "_".join(f"{k}-{params[k]}" for k in sorted(params))
    return paths.ncaaf_cfbd_dir() / f"{slug}__{suffix}.json"


def get_cached(
    endpoint: str,
    params: dict,
    api_key: str,
    refresh: bool = False,
    session: requests.Session | None = None,
) -> list[dict]:
    """Return a cached response when present; otherwise fetch and cache it.
    Completed seasons never change, so the cache is the archive."""
    path = cache_path(endpoint, params)
    if path.exists() and not refresh:
        with open(path) as fh:
            return json.load(fh)
    payload = get(endpoint, params, api_key, session=session)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"))  # compact: committed to git
    return payload


def _pick(d: dict, *keys, default=None):
    """CFBD v2 is camelCase; v1 was snake_case. Accept either."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


GAMES_COLUMNS = [
    "cfbd_game_id", "season", "week", "season_type", "start_time_utc",
    "neutral_site", "conference_game", "venue_id", "home_team",
    "home_conference", "away_team", "away_conference", "home_points",
    "away_points", "completed", "venue",
]


def parse_games(payload: list[dict]) -> pd.DataFrame:
    rows = [
        {
            "cfbd_game_id": _pick(g, "id"),
            "season": _pick(g, "season"),
            "week": _pick(g, "week"),
            "season_type": _pick(g, "seasonType", "season_type"),
            "start_time_utc": _pick(g, "startDate", "start_date"),
            "neutral_site": bool(_pick(g, "neutralSite", "neutral_site", default=False)),
            "conference_game": bool(
                _pick(g, "conferenceGame", "conference_game", default=False)
            ),
            "venue_id": _pick(g, "venueId", "venue_id"),
            "home_team": _pick(g, "homeTeam", "home_team"),
            "home_conference": _pick(g, "homeConference", "home_conference"),
            "away_team": _pick(g, "awayTeam", "away_team"),
            "away_conference": _pick(g, "awayConference", "away_conference"),
            "home_points": _pick(g, "homePoints", "home_points"),
            "away_points": _pick(g, "awayPoints", "away_points"),
            "completed": bool(_pick(g, "completed", default=False)),
            "venue": _pick(g, "venue"),
        }
        for g in payload
    ]
    return pd.DataFrame(rows, columns=GAMES_COLUMNS)


LINES_COLUMNS = [
    "cfbd_game_id", "season", "week", "home_team", "away_team", "provider",
    "spread", "spread_open", "total", "total_open", "home_moneyline",
    "away_moneyline",
]


def parse_lines(payload: list[dict]) -> pd.DataFrame:
    """One row per (game, provider). `spread` is from the HOME team's side
    (negative = home favored), matching CFBD's convention; `*_open` is the
    provider's opening number when CFBD has it."""
    rows = []
    for g in payload:
        for ln in g.get("lines") or []:
            rows.append(
                {
                    "cfbd_game_id": _pick(g, "id"),
                    "season": _pick(g, "season"),
                    "week": _pick(g, "week"),
                    "home_team": _pick(g, "homeTeam", "home_team"),
                    "away_team": _pick(g, "awayTeam", "away_team"),
                    "provider": _pick(ln, "provider"),
                    "spread": _pick(ln, "spread"),
                    "spread_open": _pick(ln, "spreadOpen", "spread_open"),
                    "total": _pick(ln, "overUnder", "over_under"),
                    "total_open": _pick(ln, "overUnderOpen", "over_under_open"),
                    "home_moneyline": _pick(ln, "homeMoneyline", "home_moneyline"),
                    "away_moneyline": _pick(ln, "awayMoneyline", "away_moneyline"),
                }
            )
    df = pd.DataFrame(rows, columns=LINES_COLUMNS)
    for col in ("spread", "spread_open", "total", "total_open"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


SP_COLUMNS = ["season", "team", "conference", "rating", "ranking", "offense", "defense"]


def parse_sp_ratings(payload: list[dict]) -> pd.DataFrame:
    rows = []
    for r in payload:
        team = _pick(r, "team")
        if not team or team == "nationalAverages":
            continue
        rows.append(
            {
                "season": _pick(r, "year", "season"),
                "team": team,
                "conference": _pick(r, "conference"),
                "rating": _pick(r, "rating"),
                "ranking": _pick(r, "ranking"),
                "offense": (_pick(r, "offense", default={}) or {}).get("rating"),
                "defense": (_pick(r, "defense", default={}) or {}).get("rating"),
            }
        )
    return pd.DataFrame(rows, columns=SP_COLUMNS)


VENUE_COLUMNS = ["venue_id", "name", "city", "state", "latitude", "longitude", "dome"]


def parse_venues(payload: list[dict]) -> pd.DataFrame:
    rows = []
    for v in payload:
        loc = _pick(v, "location", default={}) or {}
        rows.append(
            {
                "venue_id": _pick(v, "id"),
                "name": _pick(v, "name"),
                "city": _pick(v, "city"),
                "state": _pick(v, "state"),
                # v2 flattens to latitude/longitude; v1 nested {x: lat, y: lon}.
                "latitude": _pick(v, "latitude", default=loc.get("x")),
                "longitude": _pick(v, "longitude", default=loc.get("y")),
                "dome": bool(_pick(v, "dome", default=False)),
            }
        )
    return pd.DataFrame(rows, columns=VENUE_COLUMNS)


TEAM_COLUMNS = ["team_id", "school", "mascot", "abbreviation", "conference", "display_name"]


def parse_teams(payload: list[dict]) -> pd.DataFrame:
    """/teams/fbs. `display_name` = "School Mascot", ESPN's displayName form
    (falls back to the bare school when CFBD has no mascot)."""
    rows = []
    for t in payload:
        school = _pick(t, "school")
        if not school:
            continue
        mascot = _pick(t, "mascot")
        rows.append(
            {
                "team_id": _pick(t, "id"),
                "school": school,
                "mascot": mascot,
                "abbreviation": _pick(t, "abbreviation"),
                "conference": _pick(t, "conference"),
                "display_name": f"{school} {mascot}" if mascot else school,
            }
        )
    return pd.DataFrame(rows, columns=TEAM_COLUMNS)


RANKING_COLUMNS = [
    "season", "season_type", "week", "poll", "rank", "school", "conference",
    "first_place_votes", "points",
]


def parse_rankings(payload: list[dict]) -> pd.DataFrame:
    """/rankings: one row per (season, week, poll, team)."""
    rows = []
    for wk in payload:
        for poll in _pick(wk, "polls", default=[]) or []:
            for r in _pick(poll, "ranks", default=[]) or []:
                rows.append(
                    {
                        "season": _pick(wk, "season"),
                        "season_type": _pick(wk, "seasonType", "season_type"),
                        "week": _pick(wk, "week"),
                        "poll": _pick(poll, "poll"),
                        "rank": _pick(r, "rank"),
                        "school": _pick(r, "school"),
                        "conference": _pick(r, "conference"),
                        "first_place_votes": _pick(r, "firstPlaceVotes", "first_place_votes"),
                        "points": _pick(r, "points"),
                    }
                )
    return pd.DataFrame(rows, columns=RANKING_COLUMNS)


STAT_COLUMNS = ["season", "team", "conference", "stat", "value"]


def parse_season_stats(payload: list[dict]) -> pd.DataFrame:
    """/stats/season: long format, one row per (team, stat). Values are
    numeric; pivot on `stat` for a wide team table."""
    rows = [
        {
            "season": _pick(r, "season"),
            "team": _pick(r, "team"),
            "conference": _pick(r, "conference"),
            "stat": _pick(r, "statName", "stat_name"),
            "value": _pick(r, "statValue", "stat_value"),
        }
        for r in payload
    ]
    df = pd.DataFrame(rows, columns=STAT_COLUMNS)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df
