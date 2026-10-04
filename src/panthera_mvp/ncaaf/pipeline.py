"""`panthera-mvp ncaaf ...` commands — NCAAF data plumbing.

  games     ESPN FBS scoreboard for an ET date -> data/ncaaf/games/games.csv
  snapshot  Odds API NCAAF spreads/totals/h2h -> data/ncaaf/odds/lines.csv
  grade     refresh finals for dates with pending legs; settle tickets
  cfbd-pull cache CFBD games/lines/SP+/venues for backtest seasons
  status    row counts + shared credit balance

Offline fixtures (mirroring the MLB commands): PANTHERA_NCAAF_ESPN_FIXTURE
replaces the ESPN call; `snapshot --dry-run` reads PANTHERA_NCAAF_ODDS_FIXTURE.
All commands are idempotent.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

import pandas as pd

from .. import paths
from ..clients import cfbd, espn_cfb, odds
from ..timeutil import ET, now_utc, utc_iso
from . import grading, store
from .config import load_ncaaf_config
from .matching import match_events


def _today_et() -> str:
    return str(now_utc().astimezone(ET).date())


def _scoreboard(date_et: str, cfg: dict) -> list[espn_cfb.CfbGame]:
    fixture = os.environ.get("PANTHERA_NCAAF_ESPN_FIXTURE")
    if fixture:
        with open(fixture) as fh:
            games = espn_cfb.parse_scoreboard(json.load(fh))
        return [g for g in games if g.game_date_et == date_et]
    return espn_cfb.get_scoreboard(date_et, group=str(cfg["espn"]["group"]))


def refresh_games(date_et: str, cfg: dict | None = None) -> list[espn_cfb.CfbGame]:
    cfg = cfg or load_ncaaf_config()
    games = _scoreboard(date_et, cfg)
    store.upsert_games(pd.DataFrame([asdict(g) for g in games]))
    return games


def cmd_games(date_et: str | None = None) -> None:
    d = date_et or _today_et()
    games = refresh_games(d)
    finals = sum(g.status == "Final" for g in games)
    print(f"[ncaaf games] {d}: {len(games)} FBS games ({finals} final)")


def cmd_snapshot(label: str, dry_run: bool = False) -> None:
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
            return
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
        return

    # The Odds API NCAAF feed spans the whole week; match each event against
    # ESPN on its own ET kickoff date.
    df["game_date_et"] = (
        pd.to_datetime(df["commence_time_utc"], utc=True).dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    )
    games: list[espn_cfb.CfbGame] = []
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


def cmd_grade(date_et: str | None = None) -> None:
    cfg = load_ncaaf_config()
    legs = store.load_legs()
    pending = legs[legs["status"] == "pending"]
    if pending.empty:
        print("[ncaaf grade] no pending legs")
        return
    dates = (
        pd.to_datetime(pending["start_time_utc"], utc=True)
        .dt.tz_convert(ET)
        .dt.strftime("%Y-%m-%d")
        .unique()
    )
    for d in sorted(dates):
        if date_et and d != date_et:
            continue
        try:
            refresh_games(d, cfg)
        except Exception as exc:  # one bad date must not block the rest
            print(f"[ncaaf grade] ESPN refresh failed for {d}: {exc}", file=sys.stderr)
    settled = grading.grade_pending(cfg["matching"].get("team_aliases") or {})
    print(f"[ncaaf grade] settled {len(settled)} ticket(s)")


def cmd_cfbd_pull(seasons: str, refresh: bool = False) -> None:
    """Cache CFBD history for the backtest. One call per (endpoint, season)."""
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
        print(f"[ncaaf cfbd] {year}: {len(g)} games, {len(ln)} lined games, {len(sp)} SP+ rows")
    venues = cfbd.get_cached("venues", {}, api_key, refresh)
    print(f"[ncaaf cfbd] {len(venues)} venues")


def cmd_status() -> None:
    games, lines = store.load_games(), store.load_lines()
    tickets = store.load_tickets()
    print(f"[ncaaf] games: {len(games)}  line rows: {len(lines)}  tickets: {len(tickets)}")
    if not tickets.empty:
        print(tickets["status"].value_counts().to_string())
    print(f"[ncaaf] odds credits remaining (shared with MLB): {odds.last_known_remaining()}")
