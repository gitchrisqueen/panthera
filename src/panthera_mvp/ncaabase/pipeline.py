"""`panthera-mvp ncaabase ...` commands — NCAA D1 college baseball plumbing.

  games     ncaa-api scoreboard for an ET date -> data/ncaabase/games/games.csv
            (+ ESPN finals fallback for started games ncaa-api hasn't settled)
  snapshot  Odds API `baseball_ncaa` -> data/ncaabase/odds/lines.csv; live
            calls only when odds_api.enabled (off by default) or --force
  grade     refresh dates holding unsettled started games or pending picks;
            settle pending picks
  status    row counts + shared credit balance

Outside config `season` every network command prints a skip and returns
(`--force` overrides for backfills and capture runs); `grade` simply has nothing to do
once the lookback holds no unsettled games or pending picks.

Offline fixtures (mirroring ncaaf): PANTHERA_NCAABASE_NCAA_FIXTURE and
PANTHERA_NCAABASE_ESPN_FIXTURE replace the scoreboard calls;
`snapshot --dry-run` reads PANTHERA_NCAABASE_ODDS_FIXTURE. All commands are
idempotent.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta

import pandas as pd

from .. import paths
from ..clients import college_baseball as cb
from ..clients import odds
from ..timeutil import ET, now_utc, utc_iso
from . import grading, store
from .config import in_season, load_ncaabase_config
from .matching import match_espn, match_odds_events

UNSETTLED = ("Scheduled", "InProgress", "Suspended")


def _now() -> datetime:
    return now_utc()


def _today_et() -> str:
    return str(_now().astimezone(ET).date())


def _aliases(cfg: dict) -> dict[str, str]:
    return (cfg.get("matching") or {}).get("team_aliases") or {}


def _ncaa_games(date_et: str, cfg: dict) -> list[cb.BaseballGame]:
    fixture = os.environ.get("PANTHERA_NCAABASE_NCAA_FIXTURE")
    if fixture:
        with open(fixture) as fh:
            games = cb.parse_schedule(json.load(fh), date_et)
        return [g for g in games if g.game_date_et == date_et]
    return cb.get_schedule(date_et, base_url=cfg["ncaa_api"]["base_url"])


def _espn_games(date_et: str, cfg: dict) -> list[cb.EspnBaseballGame]:
    fixture = os.environ.get("PANTHERA_NCAABASE_ESPN_FIXTURE")
    if fixture:
        with open(fixture) as fh:
            return cb.parse_espn_scoreboard(json.load(fh))
    return cb.get_espn_scoreboard(date_et, group=cfg["espn"].get("group"))


def _espn_fallback(date_et: str, cfg: dict) -> int:
    """Settle this date's started, unsettled games from ESPN. Returns how
    many rows changed. ESPN only ever updates games ncaa-api listed — it
    never creates rows (no NCAA gameID to key them by)."""
    if not cfg["espn"].get("enabled", True):
        return 0
    games = store.load_games()
    games = games[
        (games["game_date_et"] == date_et)
        & games["status"].isin(UNSETTLED)
        & (pd.to_datetime(games["start_time_utc"], utc=True) <= _now())
    ]
    if games.empty:
        return 0
    try:
        espn = _espn_games(date_et, cfg)
    except Exception as exc:  # fallback of a fallback: log and move on
        print(f"[ncaabase] ESPN fallback failed for {date_et}: {exc}", file=sys.stderr)
        return 0
    mcfg = cfg["matching"]
    rows = games.to_dict("records")
    matched, unmatched = match_espn(
        rows, espn, _aliases(cfg), mcfg["window_hours"], mcfg["ambiguity_minutes"]
    )
    for msg in unmatched:
        print(f"[ncaabase] no ESPN match: {msg}", file=sys.stderr)
    updated = []
    for row in rows:
        hit = matched.get(str(row["game_id"]))
        if hit is None:
            continue
        e, swapped = hit
        if e.status == "Final" and e.home_score is not None and e.away_score is not None:
            hs, as_ = (e.away_score, e.home_score) if swapped else (e.home_score, e.away_score)
            row |= {"status": "Final", "home_score": hs, "away_score": as_,
                    "score_source": "espn", "espn_event_id": e.event_id}
        elif e.status in ("Postponed", "Canceled"):
            row |= {"status": e.status, "espn_event_id": e.event_id}
        else:
            continue
        updated.append(row)
    store.upsert_games(pd.DataFrame(updated))
    return len(updated)


def refresh_date(date_et: str, cfg: dict | None = None) -> list[cb.BaseballGame]:
    """ncaa-api scoreboard -> store, then the ESPN fallback. An ncaa-api
    failure is logged, not raised, so the fallback still runs on stored rows."""
    cfg = cfg or load_ncaabase_config()
    games: list[cb.BaseballGame] = []
    try:
        games = _ncaa_games(date_et, cfg)
        store.upsert_games(pd.DataFrame([asdict(g) for g in games]))
    except Exception as exc:
        print(f"[ncaabase] ncaa-api refresh failed for {date_et}: {exc}", file=sys.stderr)
    n = _espn_fallback(date_et, cfg)
    if n:
        print(f"[ncaabase] {date_et}: {n} game(s) settled from ESPN")
    return games


def cmd_games(date_et: str | None = None, force: bool = False) -> None:
    cfg = load_ncaabase_config()
    d = date_et or _today_et()
    if not force and not in_season(d, cfg):
        print(f"[ncaabase games] {d} is outside the season window; skipped (--force overrides)")
        return
    games = refresh_date(d, cfg)
    stored = store.load_games()
    stored = stored[stored["game_date_et"] == d]
    finals = int((stored["status"] == "Final").sum())
    print(f"[ncaabase games] {d}: {len(games)} D1 games from ncaa-api; "
          f"{finals}/{len(stored)} stored final")


def cmd_snapshot(label: str, dry_run: bool = False, force: bool = False) -> None:
    """`force` (manual capture runs only) ignores the season window and
    odds_api.enabled — how coverage gets measured before enabling."""
    cfg = load_ncaabase_config()
    ocfg = cfg["odds_api"]
    d = _today_et()
    if not force and not in_season(d, cfg):
        print(f"[ncaabase snapshot] {d} is outside the season window; skipped")
        return
    ts = utc_iso(_now())

    if dry_run:
        fixture = os.environ.get("PANTHERA_NCAABASE_ODDS_FIXTURE")
        if not fixture:
            raise SystemExit(
                "--dry-run requires PANTHERA_NCAABASE_ODDS_FIXTURE pointing to a "
                "recorded Odds API baseball_ncaa response JSON"
            )
        with open(fixture) as fh:
            events = json.load(fh)
        print(f"[ncaabase snapshot] dry-run: {len(events)} events from fixture")
    else:
        if not force and not ocfg.get("enabled"):
            print("[ncaabase snapshot] odds_api.enabled is false in config/ncaabase.yaml; "
                  "skipped (0 credits)")
            return
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
            print(f"[ncaabase snapshot] SKIPPED: {exc}")
            return
        odds.record_credits(f"ncaabase_{label}", info)
        raw = paths.ncaabase_raw_odds_dir(d)
        raw.mkdir(parents=True, exist_ok=True)
        with open(raw / f"{label}.json", "w") as fh:
            json.dump(events, fh, indent=1)
        print(f"[ncaabase snapshot] {len(events)} events; credits used={info.used} "
              f"remaining={info.remaining}")

    df = odds.normalize(events, ts, label)
    if df.empty:
        # Off-days and thin coverage are normal for this feed — not an error.
        print("[ncaabase snapshot] no priced events")
        return

    df["game_date_et"] = (
        pd.to_datetime(df["commence_time_utc"], utc=True).dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    )
    for gd in sorted(df["game_date_et"].unique()):
        refresh_date(gd, cfg)
    stored = store.load_games()
    stored = stored[stored["game_date_et"].isin(df["game_date_et"].unique())]
    mcfg = cfg["matching"]
    priced = [ev for ev in events if ev["id"] in set(df["odds_event_id"])]
    matched, unmatched = match_odds_events(
        priced, stored.to_dict("records"), _aliases(cfg),
        mcfg["window_hours"], mcfg["ambiguity_minutes"],
    )
    for msg in unmatched:
        print(f"[ncaabase snapshot] unmatched odds event: {msg}", file=sys.stderr)
    df = df.drop(columns=["game_pk"]).assign(game_id=df["odds_event_id"].map(matched))
    added = store.append_lines(df)
    print(f"[ncaabase snapshot] appended {added} line rows ({label}); "
          f"{len(matched)} matched, {len(unmatched)} unmatched")


def _dates_to_grade(cfg: dict) -> list[str]:
    today = date.fromisoformat(_today_et())
    oldest = str(today - timedelta(days=int(cfg["grade"]["lookback_days"])))
    games = store.load_games()
    started = games[
        games["status"].isin(UNSETTLED)
        & (pd.to_datetime(games["start_time_utc"], utc=True) <= _now())
        & (games["game_date_et"] >= oldest)
    ]
    picks = store.load_picks()
    pending = picks.loc[picks["status"] == "pending", "game_date_et"]
    return sorted(set(started["game_date_et"]) | {d for d in pending if d <= str(today)})


def cmd_grade(date_et: str | None = None) -> None:
    cfg = load_ncaabase_config()
    dates = [date_et] if date_et else _dates_to_grade(cfg)
    if not dates:
        print("[ncaabase grade] nothing to refresh (no unsettled games or pending picks)")
        return
    for d in dates:
        refresh_date(d, cfg)
    settled = grading.grade_pending(_aliases(cfg))
    print(f"[ncaabase grade] refreshed {len(dates)} date(s); settled {len(settled)} pick(s)")


def cmd_status() -> None:
    cfg = load_ncaabase_config()
    games, lines, picks = store.load_games(), store.load_lines(), store.load_picks()
    d = _today_et()
    season = "in season" if in_season(d, cfg) else "out of season"
    print(f"[ncaabase] {d}: {season}; odds snapshots "
          f"{'enabled' if cfg['odds_api'].get('enabled') else 'disabled'}")
    print(f"[ncaabase] games: {len(games)}  line rows: {len(lines)}  picks: {len(picks)}")
    if not games.empty:
        print(games["status"].value_counts().to_string())
    if not picks.empty:
        print(picks["status"].value_counts().to_string())
    print(f"[ncaabase] odds credits remaining (shared pool): {odds.last_known_remaining()}")

