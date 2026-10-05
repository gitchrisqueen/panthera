"""`panthera-mvp ncaaf ...` commands — NCAAF data plumbing.

  games     FBS games -> data/ncaaf/games/games.csv. `--date` = one ET day
            from ESPN; `--week N [--year]` = a whole CFB week: CFBD /games +
            /lines (when CFBD_API_KEY is set) merged with ESPN's week
            scoreboard (see sources.py); CFBD lines land in
            data/ncaaf/odds/cfbd_lines.csv
  snapshot  Odds API NCAAF spreads/totals/h2h -> data/ncaaf/odds/lines.csv.
            One call returns every upcoming FBS event (3 credits), so the
            cadence is weekly, not daily. `--week N` first ingests that week
            (as `games --week`) and matches against it
  grade     refresh finals for dates with pending legs (ESPN; on an ESPN
            error, CFBD then ncaa-api by week); settle tickets
  cfbd-pull cache CFBD games/lines/SP+/rankings/team stats/teams/venues for
            backtest seasons
  status    row counts + shared credit balance

Offline fixtures (mirroring the MLB commands): PANTHERA_NCAAF_ESPN_FIXTURE
replaces the ESPN call (date and week mode); `snapshot --dry-run` reads
PANTHERA_NCAAF_ODDS_FIXTURE. All commands are idempotent.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

import pandas as pd

from .. import paths
from ..clients import cfbd, espn_cfb, ncaa_api, odds
from ..timeutil import ET, now_utc, utc_iso
from . import grading, sources, store
from .config import load_ncaaf_config
from .matching import match_events


def _today_et() -> str:
    return str(now_utc().astimezone(ET).date())


def default_season() -> int:
    """CFB seasons are named by their starting year; January/February bowl
    and playoff games belong to the previous season."""
    today = now_utc().astimezone(ET).date()
    return today.year if today.month >= 3 else today.year - 1


def _fixture_games() -> list[espn_cfb.CfbGame] | None:
    fixture = os.environ.get("PANTHERA_NCAAF_ESPN_FIXTURE")
    if not fixture:
        return None
    with open(fixture) as fh:
        return espn_cfb.parse_scoreboard(json.load(fh))


def _scoreboard(date_et: str, cfg: dict) -> list[espn_cfb.CfbGame]:
    games = _fixture_games()
    if games is not None:
        return [g for g in games if g.game_date_et == date_et]
    return espn_cfb.get_scoreboard(date_et, group=str(cfg["espn"]["group"]))


def _week_scoreboard(
    season: int, week: int, season_type: str, cfg: dict
) -> list[espn_cfb.CfbGame]:
    games = _fixture_games()
    if games is not None:
        return [g for g in games if g.week in (None, week)]
    return espn_cfb.get_week_scoreboard(
        season, week, season_type, group=str(cfg["espn"]["group"])
    )


def _save_games(games: list[espn_cfb.CfbGame]) -> None:
    store.upsert_games(pd.DataFrame([asdict(g) for g in games]))


def refresh_games(date_et: str, cfg: dict | None = None) -> list[espn_cfb.CfbGame]:
    cfg = cfg or load_ncaaf_config()
    games = _scoreboard(date_et, cfg)
    _save_games(games)
    return games


def _cfbd_week_games(
    season: int, week: int, season_type: str, cfg: dict, api_key: str
) -> tuple[list[espn_cfb.CfbGame], dict[str, str]]:
    """CFBD /games for one week (re-fetched every time: the week is live)
    plus the school -> "School Mascot" map from /teams/fbs (cached per
    season)."""
    params = {"year": season, "week": week, "seasonType": season_type}
    payload = cfbd.get_cached(
        "games", params | {"classification": cfg["cfbd"]["classification"]}, api_key,
        refresh=True,
    )
    teams = cfbd.parse_teams(cfbd.get_cached("teams/fbs", {"year": season}, api_key))
    display = dict(zip(teams["school"], teams["display_name"], strict=True))
    return sources.cfbd_to_games(cfbd.parse_games(payload), display), display


def refresh_week(
    season: int, week: int, season_type: str = "regular", cfg: dict | None = None
) -> list[espn_cfb.CfbGame]:
    """Ingest one CFB week: games (CFBD + ESPN merged) and CFBD's lines.
    Either game source alone is enough; both failing is an error."""
    cfg = cfg or load_ncaaf_config()
    tag = f"{season} wk{week} {season_type}"
    espn_games: list[espn_cfb.CfbGame] = []
    espn_failed = False
    try:
        espn_games = _week_scoreboard(season, week, season_type, cfg)
    except Exception as exc:
        espn_failed = True
        print(f"[ncaaf week] ESPN week scoreboard failed ({tag}): {exc}", file=sys.stderr)

    api_key = os.environ.get("CFBD_API_KEY", "")
    cfbd_games: list[espn_cfb.CfbGame] | None = None
    display: dict[str, str] = {}
    if api_key:
        try:
            cfbd_games, display = _cfbd_week_games(season, week, season_type, cfg, api_key)
        except Exception as exc:
            print(f"[ncaaf week] CFBD games failed ({tag}): {exc}", file=sys.stderr)
    if cfbd_games is None:
        if espn_failed:
            raise SystemExit(f"[ncaaf week] no game source available for {tag}")
        games = espn_games
    else:
        games, warnings = sources.merge_week(espn_games, cfbd_games)
        for msg in warnings:
            print(f"[ncaaf week] id/school mismatch: {msg}", file=sys.stderr)
    _save_games(games)

    if cfbd_games is not None:
        try:
            payload = cfbd.get_cached(
                "lines", {"year": season, "week": week, "seasonType": season_type}, api_key,
                refresh=True,
            )
            lines = sources.cfbd_week_lines(
                cfbd.parse_lines(payload), games, display, season_type, utc_iso(now_utc())
            )
            n = store.upsert_cfbd_lines(lines)
            print(f"[ncaaf week] {tag}: {n} CFBD line rows")
        except Exception as exc:
            print(f"[ncaaf week] CFBD lines failed ({tag}): {exc}", file=sys.stderr)
    return games


def cmd_games(
    date_et: str | None = None,
    week: int | None = None,
    season: int | None = None,
    season_type: str = "regular",
) -> None:
    if week is not None:
        yr = season or default_season()
        games = refresh_week(yr, week, season_type)
        where = f"{yr} week {week} ({season_type})"
    else:
        where = date_et or _today_et()
        games = refresh_games(where)
    finals = sum(g.status == "Final" for g in games)
    print(f"[ncaaf games] {where}: {len(games)} FBS games ({finals} final)")


def cmd_snapshot(
    label: str,
    dry_run: bool = False,
    week: int | None = None,
    season: int | None = None,
    season_type: str = "regular",
) -> str | None:
    """Returns the snapshot timestamp, or None when nothing was stored."""
    cfg = load_ncaaf_config()
    ocfg = cfg["odds_api"]
    d = _today_et()
    ts = utc_iso(now_utc())

    if dry_run:
        fixture = os.environ.get("PANTHERA_NCAAF_ODDS_FIXTURE")
        if not fixture:
            raise SystemExit(
                "--dry-run requires PANTHERA_NCAAF_ODDS_FIXTURE pointing to a "
                "recorded Odds API NCAAF response JSON"
            )
        with open(fixture) as fh:
            events = json.load(fh)
        print(f"[ncaaf snapshot] dry-run: {len(events)} events from fixture")
    else:
        api_key = os.environ.get("ODDS_API_KEY")
        if not api_key:
            raise SystemExit("ODDS_API_KEY is not set")
        try:
            events, info = odds.fetch_snapshot(
                api_key,
                regions=ocfg["regions"],
                markets=",".join(ocfg["markets"]),
                min_credits_reserve=ocfg["min_credits_reserve"],
                sport_key=ocfg["sport_key"],
            )
        except odds.CreditGuardError as exc:
            print(f"[ncaaf snapshot] SKIPPED: {exc}")
            return None
        odds.record_credits(f"ncaaf_{label}", info)
        raw = paths.ncaaf_raw_odds_dir(d)
        raw.mkdir(parents=True, exist_ok=True)
        with open(raw / f"{label}.json", "w") as fh:
            json.dump(events, fh, indent=1)
        print(
            f"[ncaaf snapshot] {len(events)} events; credits used={info.used} "
            f"remaining={info.remaining}"
        )

    df = odds.normalize(events, ts, label)
    if df.empty:
        print("[ncaaf snapshot] no priced events")
        return None

    # The Odds API NCAAF feed spans the whole week. Week mode matches against
    # that week's ingest; otherwise each event's own ET kickoff date is
    # refreshed from ESPN.
    df["game_date_et"] = (
        pd.to_datetime(df["commence_time_utc"], utc=True).dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    )
    games: list[espn_cfb.CfbGame] = []
    if week is not None:
        games = refresh_week(season or default_season(), week, season_type, cfg)
    else:
        for gd in sorted(df["game_date_et"].unique()):
            games.extend(refresh_games(gd, cfg))
    mcfg = cfg["matching"]
    matched, unmatched = match_events(
        events, games, mcfg.get("team_aliases") or {}, mcfg["window_hours"]
    )
    for msg in unmatched:
        print(f"[ncaaf snapshot] unmatched odds event: {msg}", file=sys.stderr)
    df = df.drop(columns=["game_pk"]).assign(event_id=df["odds_event_id"].map(matched))
    added = store.append_lines(df)
    print(
        f"[ncaaf snapshot] appended {added} line rows ({label}); "
        f"{len(matched)} matched, {len(unmatched)} unmatched"
    )
    return ts


def cmd_grade(date_et: str | None = None) -> None:
    cfg = load_ncaaf_config()
    legs, quals = store.load_legs(), store.load_qualifiers()
    pending = pd.concat(
        [
            legs.loc[legs["status"] == "pending", ["event_id", "start_time_utc"]],
            quals.loc[quals["status"] == "pending", ["event_id", "start_time_utc"]],
        ],
        ignore_index=True,
    )
    if pending.empty:
        print("[ncaaf grade] no pending legs")
        return
    dates = (
        pd.to_datetime(pending["start_time_utc"], utc=True)
        .dt.tz_convert(ET)
        .dt.strftime("%Y-%m-%d")
        .unique()
    )
    failed: list[str] = []
    for d in sorted(dates):
        if date_et and d != date_et:
            continue
        try:
            refresh_games(d, cfg)
        except Exception as exc:  # one bad date must not block the rest
            print(f"[ncaaf grade] ESPN refresh failed for {d}: {exc}", file=sys.stderr)
            failed.append(d)
    if failed:
        fill_finals_fallback(failed, set(pending["event_id"].astype(str)), cfg)
    aliases = cfg["matching"].get("team_aliases") or {}
    settled = grading.grade_pending(aliases)
    n_q = grading.grade_qualifiers(aliases)
    print(f"[ncaaf grade] settled {len(settled)} ticket(s), {n_q} qualifying leg(s)")


def fill_finals_fallback(dates: list[str], event_ids: set[str], cfg: dict) -> int:
    """ESPN failed for these ET dates: fill the pending-leg games still not
    settled from CFBD (id join; needs CFBD_API_KEY), then ncaa-api (school
    join). Both are week-keyed, so a stored row without season/week cannot
    use them (logged). Returns how many games were filled."""
    games = store.load_games()
    todo = games[
        games["event_id"].astype(str).isin(event_ids)
        & games["game_date_et"].isin(dates)
        & ~games["status"].isin(sources.SETTLED)
    ]
    groups: dict[tuple[int, int, str], list[dict]] = {}
    for r in todo.to_dict("records"):
        if pd.isna(r.get("season")) or pd.isna(r.get("week")):
            print(
                f"[ncaaf grade] {r['event_id']}: no season/week stored; "
                "fallback finals need them",
                file=sys.stderr,
            )
            continue
        stype = r["season_type"] if isinstance(r.get("season_type"), str) else "regular"
        groups.setdefault((int(r["season"]), int(r["week"]), stype), []).append(r)

    api_key = os.environ.get("CFBD_API_KEY", "")
    aliases = (cfg.get("ncaa_api") or {}).get("school_aliases") or {}
    filled: list[dict] = []
    for (season, week, stype), targets in sorted(groups.items()):
        tag = f"{season} wk{week} {stype}"
        if api_key:
            try:
                cfbd_games, _ = _cfbd_week_games(season, week, stype, cfg, api_key)
                got = sources.finals_from_cfbd(targets, cfbd_games)
                filled += got
                done = {str(r["event_id"]) for r in got}
                targets = [r for r in targets if str(r["event_id"]) not in done]
            except Exception as exc:
                print(f"[ncaaf grade] CFBD finals failed ({tag}): {exc}", file=sys.stderr)
        if not targets:
            continue
        try:
            got, unmatched = sources.finals_from_ncaa(
                targets, ncaa_api.get_scoreboard(season, week, stype), aliases
            )
        except Exception as exc:
            print(f"[ncaaf grade] ncaa-api finals failed ({tag}): {exc}", file=sys.stderr)
            continue
        filled += got
        for msg in unmatched:
            print(f"[ncaaf grade] ncaa-api: not filled {msg}", file=sys.stderr)
    if filled:
        store.upsert_games(pd.DataFrame(filled))
    print(f"[ncaaf grade] fallback filled {len(filled)} final(s)")
    return len(filled)


def cmd_cfbd_pull(seasons: str, refresh: bool = False) -> None:
    """Cache CFBD history for the backtest. One call per (endpoint, season)
    — six per season — plus one for venues."""
    cfg = load_ncaaf_config()["cfbd"]
    api_key = os.environ.get("CFBD_API_KEY", "")
    start, _, end = seasons.partition("-")
    years = range(int(start), int(end or start) + 1)
    for year in years:
        base = {"year": year, "seasonType": cfg["season_type"]}
        g = cfbd.get_cached(
            "games", base | {"classification": cfg["classification"]}, api_key, refresh
        )
        ln = cfbd.get_cached("lines", base, api_key, refresh)
        sp = cfbd.get_cached("ratings/sp", {"year": year}, api_key, refresh)
        rk = cfbd.get_cached("rankings", base, api_key, refresh)
        st = cfbd.get_cached("stats/season", {"year": year}, api_key, refresh)
        tm = cfbd.get_cached("teams/fbs", {"year": year}, api_key, refresh)
        print(
            f"[ncaaf cfbd] {year}: {len(g)} games, {len(ln)} lined games, "
            f"{len(sp)} SP+ rows, {len(rk)} poll weeks, {len(st)} team-stat rows, "
            f"{len(tm)} FBS teams"
        )
    venues = cfbd.get_cached("venues", {}, api_key, refresh)
    print(f"[ncaaf cfbd] {len(venues)} venues")


def cmd_status() -> None:
    games, lines = store.load_games(), store.load_lines()
    cfbd_lines, tickets = store.load_cfbd_lines(), store.load_tickets()
    print(
        f"[ncaaf] games: {len(games)}  odds line rows: {len(lines)}  "
        f"CFBD line rows: {len(cfbd_lines)}  tickets: {len(tickets)}"
    )
    if not tickets.empty:
        print(tickets["status"].value_counts().to_string())
    decisions, quals = store.load_decisions(), store.load_qualifiers()
    print(f"[ncaaf] decisions: {len(decisions)}  qualifying legs: {len(quals)}")
    print(f"[ncaaf] odds credits remaining (shared with MLB): {odds.last_known_remaining()}")
