"""Orchestration for the daily CLI commands.

Each command is idempotent: re-running a snapshot/picks/grade for the same day
never duplicates rows (store-level dedupe keys) and never rewrites settled
picks.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

import pandas as pd

from . import paths, store
from .clients import espn, lumify, mlb, odds
from .config import config_hash, load_config
from .grading import grade_pending
from .matching import match_events
from .report import write_daily_report, write_ledger_report
from .strategy.dossier import Dossier
from .strategy.movement import extract_game_prices
from .strategy.rules import Pass, Pick, generate_pick
from .timeutil import ET, now_utc, utc_iso


def today_et() -> date:
    return now_utc().astimezone(ET).date()


def _load_fixture_events() -> list[dict]:
    fixture = os.environ.get("PANTHERA_ODDS_FIXTURE")
    if not fixture:
        raise SystemExit(
            "--dry-run requires PANTHERA_ODDS_FIXTURE pointing to a recorded "
            "Odds API response JSON"
        )
    with open(fixture) as fh:
        return json.load(fh)


def cmd_snapshot(label: str, dry_run: bool = False) -> None:
    cfg = load_config()
    d = str(today_et())
    ts = utc_iso(now_utc())

    if dry_run:
        events = _load_fixture_events()
        info = odds.CreditInfo(used=None, remaining=None)
        print(f"[snapshot] dry-run: {len(events)} events from fixture")
    else:
        api_key = os.environ.get("ODDS_API_KEY")
        if not api_key:
            raise SystemExit("ODDS_API_KEY is not set")
        try:
            events, info = odds.fetch_snapshot(
                api_key,
                regions=cfg["odds_api"]["regions"],
                markets=",".join(cfg["odds_api"]["markets"]),
                min_credits_reserve=cfg["odds_api"]["min_credits_reserve"],
            )
        except odds.CreditGuardError as exc:
            print(f"[snapshot] SKIPPED: {exc}")
            return
        odds.record_credits(label, info)
        odds.save_raw(events, d, label)
        print(
            f"[snapshot] {len(events)} events; credits used={info.used} "
            f"remaining={info.remaining}"
        )

    df = odds.normalize(events, ts, label)
    if df.empty:
        print("[snapshot] no priced events (empty slate?)")
        return

    # Match to MLB games and stamp game_pk / game_date_et.
    games = _refresh_games(d)
    matched, unmatched = match_events(events, games)
    for msg in unmatched:
        print(f"[snapshot] unmatched odds event: {msg}", file=sys.stderr)
    df["game_pk"] = df["odds_event_id"].map(matched)
    df["game_date_et"] = d
    added = store.append_lines(df)
    print(f"[snapshot] appended {added} line rows ({label})")


def _refresh_games(date_et: str) -> list[mlb.GameInfo]:
    """Fetch today's MLB schedule and upsert into games.csv."""
    games = mlb.get_schedule(date_et)
    rows = []
    for g in games:
        rows.append(
            {
                "game_pk": g.game_pk,
                "game_date_et": g.game_date_et,
                "day_of_week_et": g.start_utc.astimezone(ET).strftime("%A").lower(),
                "game_type": g.game_type,
                "doubleheader": g.doubleheader,
                "game_number": g.game_number,
                "start_time_utc": utc_iso(g.start_utc),
                "home_team_id": g.home_team_id,
                "home_team": g.home_team,
                "away_team_id": g.away_team_id,
                "away_team": g.away_team,
                "status": g.status if g.status != "Final" else "Final",
                "home_score": g.home_score,
                "away_score": g.away_score,
                "winner": (
                    g.home_team
                    if (g.home_score or 0) > (g.away_score or 0)
                    else g.away_team
                )
                if g.status == "Final"
                else None,
                "run_diff": (
                    abs((g.home_score or 0) - (g.away_score or 0))
                    if g.status == "Final"
                    else None
                ),
                "total_runs": (
                    (g.home_score or 0) + (g.away_score or 0)
                    if g.status == "Final"
                    else None
                ),
                "home_pitcher_era": g.home_pitcher.era if g.home_pitcher else None,
                "away_pitcher_era": g.away_pitcher.era if g.away_pitcher else None,
                "score_source": "mlb",
            }
        )
    store.upsert_games(pd.DataFrame(rows))
    return games


def _build_dossier(g: mlb.GameInfo) -> Dossier:
    dossier = Dossier(
        era_home=g.home_pitcher.era if g.home_pitcher else None,
        era_away=g.away_pitcher.era if g.away_pitcher else None,
    )
    try:
        season = int(g.game_date_et[:4])
        meetings = mlb.season_meetings(
            g.home_team_id,
            g.away_team_id,
            season,
            date.fromisoformat(g.game_date_et) - timedelta(days=1),
        )
        dossier.first_meeting = meetings == 0
    except Exception as exc:  # network hiccup: degrade, don't die
        print(f"[picks] dossier enrichment failed for {g.game_pk}: {exc}", file=sys.stderr)
    return dossier


def cmd_picks(window_end_et: str, dry_run: bool = False) -> None:
    cfg = load_config()
    chash = config_hash(cfg)
    d = str(today_et())
    lines = store.load_lines()
    lines_today = lines[lines["game_date_et"] == d] if not lines.empty else lines
    if lines_today.empty:
        print("[picks] no odds lines for today; run snapshot first")
        return

    games = _refresh_games(d)
    events_by_pk = (
        lines_today.dropna(subset=["game_pk"])
        .drop_duplicates("game_pk")
        .set_index("game_pk")["odds_event_id"]
        .to_dict()
    )

    end_h, end_m = (int(x) for x in window_end_et.split(":"))
    picks: list[Pick] = []
    passes: list[Pass] = []
    existing = store.load_picks()
    existing_pks_today = (
        set(existing[existing["game_date_et"] == d]["game_pk"]) if not existing.empty else set()
    )

    for g in games:
        start_et = g.start_utc.astimezone(ET)
        if (start_et.hour, start_et.minute) > (end_h, end_m):
            continue
        if start_et <= now_utc().astimezone(ET) and not dry_run:
            continue  # game already started
        if cfg["bet_limits"]["one_pick_per_game"] and g.game_pk in existing_pks_today:
            continue
        event_id = events_by_pk.get(g.game_pk)
        prices = (
            extract_game_prices(lines_today, event_id, g.home_team, g.away_team)
            if event_id
            else None
        )
        result = generate_pick(g, event_id, prices, _build_dossier(g), cfg)
        if isinstance(result, Pick):
            picks.append(result)
        elif isinstance(result, Pass):
            passes.append(result)

    picks = picks[: cfg["bet_limits"]["max_picks_per_day"]]
    if picks:
        rows = []
        for p in picks:
            rows.append(
                {
                    "pick_id": p.pick_id,
                    "created_ts_utc": utc_iso(now_utc()),
                    "game_date_et": p.game_date_et,
                    "game_pk": p.game_pk,
                    "odds_event_id": p.odds_event_id,
                    "matchup": p.matchup,
                    "start_time_et": p.start_time_et,
                    "day_type": p.day_type,
                    "slot_type": p.slot_type,
                    "rule_id": p.rule_id,
                    "market": p.market,
                    "selection": p.selection,
                    "line": p.line,
                    "price_american": p.price_american,
                    "price_decimal": p.price_decimal,
                    "stake": cfg["staking"]["flat_stake"],
                    "open_price": p.open_price,
                    "latest_price": p.latest_price,
                    "movement_cents": p.movement_cents,
                    "rationale": p.rationale,
                    "config_hash": chash,
                    "status": "pending",
                    "settled_ts_utc": None,
                    "final_score": None,
                    "profit": None,
                }
            )
        added = store.append_picks(pd.DataFrame(rows))
        print(f"[picks] {added} new pick(s) recorded")
    else:
        print("[picks] no picks generated")
    for p in passes:
        print(f"[picks] pass {p.matchup}: [{p.rule_id}] {p.reason}")

    credits_note = _credits_note()
    write_daily_report(d, cfg, passes=passes, credits_note=credits_note)
    write_ledger_report(cfg)


def _credits_note() -> str:
    remaining = odds.last_known_remaining()
    if remaining is None:
        return "No live Odds API calls recorded this month."
    return f"Odds API credits remaining this month: **{remaining}** / 500 (free tier)."


def cmd_grade(grade_date: str | None = None) -> None:
    cfg = load_config()
    # Refresh finals for any date that still has pending picks.
    picks = store.load_picks()
    if picks.empty:
        print("[grade] no picks to grade")
        return
    pending_dates = sorted(set(picks[picks["status"] == "pending"]["game_date_et"]))
    if grade_date:
        pending_dates = [d for d in pending_dates if d == grade_date]
    for d in pending_dates:
        try:
            _refresh_games(d)
        except Exception as exc:
            print(f"[grade] MLB refresh failed for {d}: {exc}; trying ESPN", file=sys.stderr)
            _espn_fallback(d)
    settled = grade_pending()
    print(f"[grade] settled {len(settled)} pick(s)")
    write_ledger_report(cfg)
    for d in pending_dates:
        write_daily_report(d, cfg, credits_note=_credits_note())


def _espn_fallback(date_et: str) -> None:
    """Fill finals from ESPN when the MLB API is unavailable."""
    try:
        scoreboard = espn.get_scoreboard(date_et)
    except Exception as exc:
        print(f"[grade] ESPN fallback failed for {date_et}: {exc}", file=sys.stderr)
        return
    games = store.load_games()
    if games.empty:
        return
    for eg in scoreboard:
        if not eg.completed or eg.home_score is None:
            continue
        mask = (
            (games["game_date_et"] == date_et)
            & (games["home_team"] == eg.home_team)
            & (games["away_team"] == eg.away_team)
            & (games["status"] != "Final")
        )
        games.loc[mask, ["status", "home_score", "away_score", "score_source"]] = [
            "Final",
            eg.home_score,
            eg.away_score,
            "espn",
        ]
        games.loc[mask, "winner"] = (
            eg.home_team if eg.home_score > eg.away_score else eg.away_team
        )
        games.loc[mask, "run_diff"] = abs(eg.home_score - eg.away_score)
        games.loc[mask, "total_runs"] = eg.home_score + eg.away_score
    games.to_csv(paths.games_csv(), index=False)


def match_splits_to_games(df: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Fill game_pk by parsing the Lumify event name into away/home teams and
    matching against the day's schedule. Unparsed events keep game_pk empty —
    the raw event name still identifies them in reports."""
    from .matching import team_id

    if df.empty or games.empty:
        return df

    def _resolve(row):
        name = str(row["event_name"] or "")
        for sep in (" @ ", " at ", " vs. ", " vs "):
            if sep in name:
                away_name, home_name = name.split(sep, 1)
                away, home = team_id(away_name), team_id(home_name)
                if away is None or home is None:
                    return None
                match = games[
                    (games["game_date_et"] == row["game_date_et"])
                    & (games["home_team_id"] == home)
                    & (games["away_team_id"] == away)
                ]
                if not match.empty:
                    return int(match.iloc[0]["game_pk"])
        return None

    df = df.copy()
    df["game_pk"] = df.apply(_resolve, axis=1)
    return df


def cmd_splits(dry_run: bool = False) -> None:
    cfg = load_config()
    d = str(today_et())
    lcfg = cfg.get("lumify", {})

    if dry_run:
        fixture = os.environ.get("PANTHERA_SPLITS_FIXTURE")
        if not fixture:
            raise SystemExit(
                "--dry-run requires PANTHERA_SPLITS_FIXTURE pointing to a "
                "recorded Lumify splits JSON"
            )
        with open(fixture) as fh:
            results = json.load(fh)
        print(f"[splits] dry-run: {len(results)} events from fixture")
    else:
        api_key = os.environ.get("LUMIFY_API_KEY")
        if not api_key:
            print("[splits] LUMIFY_API_KEY not set; skipping splits collection")
            return
        try:
            results, info = lumify.fetch_splits_for_date(
                api_key,
                d,
                league=lcfg.get("league", "MLB"),
                min_credits_reserve=lcfg.get("min_credits_reserve", 50),
            )
        except lumify.LumifyCreditGuardError as exc:
            print(f"[splits] SKIPPED: {exc}")
            return
        lumify.record_credits(info)
        lumify.save_raw(results, d)
        print(
            f"[splits] {len(results)} events with splits; credits "
            f"remaining={info.remaining}"
        )

    df = lumify.normalize(results, d)
    if df.empty:
        print("[splits] no split percentages found")
        return
    games = store.load_games()
    df = match_splits_to_games(df, games)
    added = lumify.append_splits(df)
    matched = df["game_pk"].notna().sum()
    print(f"[splits] stored {added} rows ({matched} rows matched to games)")


def cmd_report() -> None:
    cfg = load_config()
    write_ledger_report(cfg)
    write_daily_report(str(today_et()), cfg, credits_note=_credits_note())
    print("[report] reports regenerated")


def cmd_status() -> None:
    picks = store.load_picks()
    pending = 0 if picks.empty else int((picks["status"] == "pending").sum())
    remaining = odds.last_known_remaining()
    lines = store.load_lines()
    last_snap = "never" if lines.empty else str(lines["snapshot_ts_utc"].max())
    print(f"pending picks: {pending}")
    print(f"odds credits remaining (this month): {remaining}")
    print(f"last snapshot: {last_snap}")
