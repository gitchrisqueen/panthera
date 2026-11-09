"""`panthera-mvp ncaaf prep|picks` — run NCAAF strategies on live slates.

  prep   weekly context: ESPN games for prep_days_back..prep_days_ahead ET
         days (results and ranks for letdown/look-ahead, the week's kickoffs
         for the cron), an "open" odds snapshot (first-seen lines: line
         movement is measured from here), and CFBD SP+ + venues when
         CFBD_API_KEY is set (S6 and S5 need them)
  picks  one decision per (strategy, ET day): refresh today's games, take ONE
         "decision-<ET date>" snapshot shared by every enabled strategy (a second
         strategy costs no credits), build the day's GameViews, run each engine,
         write the ticket(s) (if any), every qualifying leg, and the decision.
         `--auto` (the half-hourly cron) does nothing — no network, no credits,
         no writes — unless the day's first unstarted kickoff is within the
         decision window around the strategy's minutes_before_first_kickoff

Idempotent: a day already decided is never re-decided.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta

import pandas as pd

from ..clients import cfbd, weather
from ..config import config_hash
from ..timeutil import ET, now_utc, parse_utc, utc_iso
from . import parlay, store
from .config import load_ncaaf_config, load_ncaaf_strategies
from .matching import normalize_name
from .pipeline import cmd_snapshot, default_season, refresh_games
from .sources import school_key


def _now() -> datetime:
    return now_utc()


def cmd_prep(odds_mode: str = "live") -> None:
    cfg = load_ncaaf_config()
    sched = cfg["schedule"]
    today = _now().astimezone(ET).date()
    n_games = 0
    for offset in range(-sched["prep_days_back"], sched["prep_days_ahead"] + 1):
        d = str(today + timedelta(days=offset))
        try:
            n_games += len(refresh_games(d, cfg))
        except Exception as exc:  # one bad date must not block the rest
            print(f"[ncaaf prep] ESPN refresh failed for {d}: {exc}", file=sys.stderr)
    print(f"[ncaaf prep] refreshed {n_games} FBS game rows")
    games = store.load_games()
    upcoming = games[
        (games["status"] == "Scheduled")
        & (games["game_date_et"] >= str(today))
        & (games["game_date_et"] <= str(today + timedelta(days=sched["prep_days_ahead"])))
    ]
    if odds_mode != "none" and upcoming.empty:
        print("[ncaaf prep] no upcoming FBS games: open snapshot skipped (0 credits)")
    elif odds_mode != "none":
        cmd_snapshot("open", dry_run=odds_mode == "dry_run")

    api_key = os.environ.get("CFBD_API_KEY", "")
    if not api_key:
        print("[ncaaf prep] CFBD_API_KEY not set: SP+ (S6) and venue coordinates "
              "for wind (S5) stay on whatever is cached", file=sys.stderr)
        return
    season = default_season()
    try:
        sp = cfbd.parse_sp_ratings(
            cfbd.get_cached("ratings/sp", {"year": season}, api_key, refresh=True)
        )
        venues = cfbd.parse_venues(cfbd.get_cached("venues", {}, api_key))
        print(f"[ncaaf prep] SP+ {season}: {len(sp)} teams; {len(venues)} venues")
    except Exception as exc:
        print(f"[ncaaf prep] CFBD refresh failed: {exc}", file=sys.stderr)


def _sp_ratings(season: int) -> dict[str, float]:
    """school_key -> SP+ rating from the cached CFBD pull (prep refreshes it)."""
    path = cfbd.cache_path("ratings/sp", {"year": season})
    if not path.exists():
        print(f"[ncaaf picks] no cached SP+ for {season}: S6 cannot fire", file=sys.stderr)
        return {}
    sp = cfbd.parse_sp_ratings(cfbd.get_cached("ratings/sp", {"year": season}, ""))
    return {school_key(r["team"]): float(r["rating"])
            for r in sp.to_dict("records") if r["rating"] is not None}


def _venues() -> dict[str, dict]:
    path = cfbd.cache_path("venues", {})
    if not path.exists():
        return {}
    v = cfbd.parse_venues(cfbd.get_cached("venues", {}, ""))
    return {normalize_name(r["name"]): r for r in v.to_dict("records") if r["name"]}


def _kickoff_winds(views: list[parlay.GameView], games_by_id: dict[str, dict]) -> dict[str, float]:
    """event_id -> kickoff wind (mph) for outdoor games at a venue with known
    coordinates. A venue CFBD lists as a dome counts as indoor, whatever ESPN
    says. Lookup failures are logged and the game simply gets no S5."""
    venues = _venues()
    if not venues:
        print("[ncaaf picks] no cached CFBD venues: S5 cannot fire", file=sys.stderr)
        return {}
    winds: dict[str, float] = {}
    for v in views:
        name = str(games_by_id.get(v.event_id, {}).get("venue") or "")
        venue = venues.get(normalize_name(name))
        if venue is None:
            print(f"[ncaaf picks] no venue coordinates for {name!r} ({v.matchup})",
                  file=sys.stderr)
            continue
        if venue["dome"]:
            v.indoor = True
            continue
        if v.indoor is not False or venue["latitude"] is None:
            continue
        try:
            kw = weather.get_kickoff_weather(
                float(venue["latitude"]), float(venue["longitude"]), v.start_time_utc
            )
        except Exception as exc:
            print(f"[ncaaf picks] weather failed for {v.matchup}: {exc}", file=sys.stderr)
            continue
        if kw is not None and kw.wind_mph is not None:
            winds[v.event_id] = float(kw.wind_mph)
    return winds


def in_decision_window(
    games: pd.DataFrame, day: str, now: datetime, scfg: dict, cfg: dict
) -> tuple[bool, str]:
    """(decide now?, why). The day's first kickoff that is still at least
    min_lead_minutes away must be less than target + halfwidth minutes away.
    There is no lower bound beyond min_lead: GitHub starts crons up to ~50
    min late, so a run that arrives after the target still decides (once —
    cmd_picks skips a day already decided) rather than dropping the day."""
    target = scfg["decision"]["minutes_before_first_kickoff"]
    half = cfg["schedule"]["decision_window_halfwidth_minutes"]
    lead = timedelta(minutes=scfg["decision"]["min_lead_minutes"])
    today = games[(games["game_date_et"] == day) & (games["status"] == "Scheduled")]
    starts = sorted(
        s for s in (parse_utc(str(x)) for x in today["start_time_utc"].dropna())
        if s - now >= lead
    )
    if not starts:
        return False, f"no upcoming FBS games stored for {day}"
    minutes = (starts[0] - now).total_seconds() / 60
    if minutes < target + half:
        return True, f"first kickoff in {minutes:.0f} min"
    return False, f"first kickoff in {minutes:.0f} min (decide under {target + half})"


def _write_decision(
    sid: str, scfg: dict, decision: parlay.DayDecision, day: str, now: datetime,
    snap_ts: str, base: dict, chash: str,
) -> None:
    singles = scfg["ticket"].get("structure", "parlay") == "singles"
    stake = float(scfg["staking"]["flat_stake"])
    ticket_ids: list[str] = []
    if decision.status == "ticket" and singles:
        # One straight bet per leg, each a one-leg ticket so grading, the
        # report and the dashboard need no second ledger.
        for lg in decision.ticket_legs:
            tid = f"{sid}-{day}-{lg.event_id}"
            ticket_ids.append(tid)
            store.append_ticket(
                {
                    "ticket_id": tid, "strategy_id": sid, "game_date_et": day,
                    "created_ts_utc": utc_iso(now), "n_legs": 1,
                    "price_american": lg.price_american, "price_decimal": lg.price_decimal,
                    "stake": stake, "rule_id": lg.signal_ids,
                    "rationale": f"straight bet: {lg.label} ({lg.signal_ids}, "
                                 f"strength {lg.strength:g})",
                    "config_hash": chash,
                },
                [{
                    "ticket_id": tid, "leg_no": 1, "event_id": lg.event_id,
                    "matchup": lg.matchup, "start_time_utc": lg.start_time_utc,
                    "market": lg.market, "selection": lg.selection, "line": lg.line,
                    "price_american": lg.price_american, "price_decimal": lg.price_decimal,
                    "bookmaker": lg.bookmaker,
                }],
            )
    elif decision.status == "ticket":
        tid = f"{sid}-{day}"
        ticket_ids.append(tid)
        lo, hi = scfg["ticket"]["price_band_american"]
        store.append_ticket(
            {
                "ticket_id": tid, "strategy_id": sid, "game_date_et": day,
                "created_ts_utc": utc_iso(now), "n_legs": len(decision.ticket_legs),
                "price_american": decision.price_american,
                "price_decimal": decision.price_decimal, "stake": stake,
                "rule_id": "|".join(lg.signal_ids for lg in decision.ticket_legs),
                "rationale": (
                    f"{'in' if decision.in_band else 'outside'} the +{lo}-+{hi} target band; "
                    + "; ".join(f"{lg.label} ({lg.signal_ids})" for lg in decision.ticket_legs)
                ),
                "config_hash": chash,
            },
            [
                {
                    "ticket_id": tid, "leg_no": n, "event_id": lg.event_id,
                    "matchup": lg.matchup, "start_time_utc": lg.start_time_utc,
                    "market": lg.market, "selection": lg.selection, "line": lg.line,
                    "price_american": lg.price_american, "price_decimal": lg.price_decimal,
                    "bookmaker": lg.bookmaker,
                }
                for n, lg in enumerate(decision.ticket_legs, 1)
            ],
        )
    on_ticket = {lg.event_id for lg in decision.ticket_legs}
    store.append_decision(
        base | {
            "snapshot_ts_utc": snap_ts, "status": decision.status, "reason": decision.reason,
            "n_qualifiers": len(decision.qualifiers), "ticket_id": "|".join(ticket_ids),
            "notes": " | ".join(decision.skipped_games),
        },
        [
            {
                "strategy_id": sid, "game_date_et": day, "event_id": lg.event_id,
                "matchup": lg.matchup, "start_time_utc": lg.start_time_utc,
                "market": lg.market, "selection": lg.selection, "line": lg.line,
                "consensus_line": lg.consensus_line, "price_american": lg.price_american,
                "price_decimal": lg.price_decimal, "bookmaker": lg.bookmaker,
                "signal_ids": lg.signal_ids,
                "signal_detail": "; ".join(s.detail for s in lg.signals),
                "on_ticket": lg.event_id in on_ticket, "config_hash": chash,
            }
            for lg in decision.qualifiers
        ],
    )
    print(f"[ncaaf picks] {sid} {day}: {decision.status} — {decision.reason}")
    for lg in decision.ticket_legs:
        print(f"  {lg.label} ({lg.price_american:+g} {lg.bookmaker}) "
              f"[{lg.signal_ids}] {lg.matchup}")
    if decision.price_american is not None and not singles and ticket_ids:
        print(f"  ticket {decision.price_american:+g} (decimal {decision.price_decimal})")


def _log_lab_features(views, schedules, sp_ratings, winds, day, snap_ts, now, aliases) -> None:
    """Log every game's raw features for the weekly lab (docs/lab/PROGRAM.md). The lab is
    exploratory and must never be able to break a live decision, so any failure here is
    reported and swallowed. Idempotent: one row per (day, event)."""
    try:
        from ..lab import features
        from ..lab import store as lab_store

        rows = features.build_feature_rows(
            views, schedules, sp_ratings, winds, day, snap_ts, now, aliases)
        added = lab_store.append_features("ncaaf", rows)
        print(f"[ncaaf picks] lab: logged {added} feature row(s) for {day}")
    except Exception as exc:  # noqa: BLE001 - never let the lab sink a decision
        msg = re.sub(r"[^\x20-\x7e]", "?", str(exc))[:300]
        print(f"::warning::ncaaf picks: lab feature logging failed: {type(exc).__name__}: {msg}",
              file=sys.stderr)


def cmd_picks(
    strategy_id: str | None = None, auto: bool = False, dry_run: bool = False
) -> None:
    """Decide today for one strategy, or (no id) for every enabled one. The
    day's games, odds snapshot, schedules, SP+ and winds are built once and
    shared, so a second strategy adds no credits and no network calls."""
    cfg = load_ncaaf_config()
    strategies = load_ncaaf_strategies()
    if strategy_id is not None:
        if strategy_id not in strategies:
            raise SystemExit(f"unknown NCAAF strategy {strategy_id!r}")
        if not strategies[strategy_id]["strategy"].get("enabled"):
            print(f"[ncaaf picks] {strategy_id} is disabled")
            return
        ids = [strategy_id]
    else:
        ids = [i for i, c in strategies.items() if c["strategy"].get("enabled")]
    now = _now()
    day = str(now.astimezone(ET).date())
    todo: list[str] = []
    for sid in ids:
        if store.decided(sid, day):
            print(f"[ncaaf picks] {sid} already decided {day}")
            continue
        if auto:
            ok, why = in_decision_window(store.load_games(), day, now, strategies[sid], cfg)
            if not ok:
                print(f"[ncaaf picks] {sid} not deciding: {why}")
                continue
            print(f"[ncaaf picks] {sid} deciding: {why}")
        todo.append(sid)
    if not todo:
        return

    try:
        refresh_games(day, cfg)
    except Exception as exc:
        print(f"[ncaaf picks] ESPN refresh failed ({exc}); using stored games",
              file=sys.stderr)
    # One label per day: lines.csv dedupes on (event date, label, ...), so a
    # shared "decision" label would drop Saturday's rows for any game an
    # earlier day's decision snapshot had already priced.
    snap_ts = cmd_snapshot(f"decision-{day}", dry_run=dry_run)
    bases = {
        sid: {"strategy_id": sid, "game_date_et": day, "decided_ts_utc": utc_iso(now),
              "config_hash": config_hash(strategies[sid])}
        for sid in todo
    }
    if snap_ts is None:
        for sid in todo:
            store.append_decision(bases[sid] | {"status": "skip", "reason": "no odds snapshot",
                                                "n_qualifiers": 0}, [])
            print(f"[ncaaf picks] {sid} {day}: skip (no odds snapshot)")
        return

    aliases = cfg["matching"].get("team_aliases") or {}
    games, lines = store.load_games(), store.load_lines()
    games_today = games[games["game_date_et"] == day]
    views = parlay.build_views(games_today, lines, snap_ts, aliases)
    games_by_id = {str(r["event_id"]): r for r in games_today.to_dict("records")}
    seasons = games_today["season"].dropna()
    season = int(seasons.iloc[0]) if not seasons.empty else default_season()
    schedules = parlay.team_schedules(games, aliases)
    sp_ratings = _sp_ratings(season)
    winds = _kickoff_winds(views, games_by_id)
    _log_lab_features(views, schedules, sp_ratings, winds, day, snap_ts, now, aliases)
    tickets, legs = store.load_tickets(), store.load_legs()
    for sid in todo:
        scfg = strategies[sid]
        sigs = scfg["signals"]
        # A quiet day and a dead data feed look the same in the ledger, so say which.
        data_notes = []
        if sigs["sp_plus_edge"]["enabled"] and not sp_ratings:
            data_notes.append("no SP+ ratings cached: S6 cannot fire")
        if sigs["weather_wind_under"]["enabled"] and not winds:
            data_notes.append("no kickoff winds available: S5 cannot fire")
        try:
            today_tickets = tickets[(tickets["strategy_id"] == sid)
                                    & (tickets["game_date_et"] == day)]
            decision = parlay.decide_day(
                views, scfg, now, schedules=schedules, sp_ratings=sp_ratings, wind_mph=winds,
                tickets_today=len(today_tickets),
                lost_yesterday=parlay.prior_day_lost(tickets, legs, sid, day),
                aliases=aliases,
            )
            decision.skipped_games.extend(data_notes)
            _write_decision(sid, scfg, decision, day, now, snap_ts, bases[sid],
                            bases[sid]["config_hash"])
        except Exception as exc:  # noqa: BLE001 - one strategy must not sink the others
            # The snapshot is already paid for. Record the day as decided (an error
            # row stops the half-hourly retry loop re-buying it) and carry on, so the
            # other strategies' decisions still reach the push.
            kind = type(exc).__name__
            # One line, printable ASCII: team names in the message come from outside feeds
            # and must not be able to start a second workflow command.
            msg = re.sub(r"[^\x20-\x7e]", "?", str(exc))[:300]
            print(f"::error::ncaaf picks: {sid} failed on {day}: {kind}: {msg}", file=sys.stderr)
            store.append_decision(
                bases[sid] | {"snapshot_ts_utc": snap_ts, "status": "skip",
                              "reason": f"error: {kind}", "n_qualifiers": 0}, [])
