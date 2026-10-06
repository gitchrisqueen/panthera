"""`panthera-mvp ncaaf prep|picks` — run NCAAF strategies on live slates.

  prep   weekly context: ESPN games for prep_days_back..prep_days_ahead ET
         days (results and ranks for letdown/look-ahead, the week's kickoffs
         for the cron), an "open" odds snapshot (first-seen lines: line
         movement is measured from here), and CFBD SP+ + venues when
         CFBD_API_KEY is set (S6 and S5 need them)
  picks  one decision per (strategy, ET day): refresh today's games, take a
         "decision-<ET date>" snapshot, build the day's GameViews, run the engine,
         write the ticket (if any), every qualifying leg, and the decision.
         `--auto` (the half-hourly cron) does nothing — no network, no credits,
         no writes — unless the day's first unstarted kickoff is within the
         decision window around the strategy's minutes_before_first_kickoff

Idempotent: a day already decided is never re-decided.
"""

from __future__ import annotations

import os
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

DEFAULT_STRATEGY = "cfb_spread_total_parlay"


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


def cmd_picks(
    strategy_id: str = DEFAULT_STRATEGY, auto: bool = False, dry_run: bool = False
) -> None:
    cfg = load_ncaaf_config()
    scfg = load_ncaaf_strategies().get(strategy_id)
    if scfg is None:
        raise SystemExit(f"unknown NCAAF strategy {strategy_id!r}")
    if not scfg["strategy"].get("enabled"):
        print(f"[ncaaf picks] {strategy_id} is disabled")
        return
    now = _now()
    day = str(now.astimezone(ET).date())
    if store.decided(strategy_id, day):
        print(f"[ncaaf picks] {strategy_id} already decided {day}")
        return
    if auto:
        ok, why = in_decision_window(store.load_games(), day, now, scfg, cfg)
        if not ok:
            print(f"[ncaaf picks] not deciding: {why}")
            return
        print(f"[ncaaf picks] deciding: {why}")

    try:
        refresh_games(day, cfg)
    except Exception as exc:
        print(f"[ncaaf picks] ESPN refresh failed ({exc}); using stored games",
              file=sys.stderr)
    chash = config_hash(scfg)
    # One label per day: lines.csv dedupes on (event date, label, ...), so a
    # shared "decision" label would drop Saturday's rows for any game an
    # earlier day's decision snapshot had already priced.
    snap_ts = cmd_snapshot(f"decision-{day}", dry_run=dry_run)
    base = {"strategy_id": strategy_id, "game_date_et": day,
            "decided_ts_utc": utc_iso(now), "config_hash": chash}
    if snap_ts is None:
        store.append_decision(base | {"status": "skip", "reason": "no odds snapshot",
                                      "n_qualifiers": 0}, [])
        print(f"[ncaaf picks] {day}: skip (no odds snapshot)")
        return

    aliases = cfg["matching"].get("team_aliases") or {}
    games, lines = store.load_games(), store.load_lines()
    games_today = games[games["game_date_et"] == day]
    views = parlay.build_views(games_today, lines, snap_ts, aliases)
    games_by_id = {str(r["event_id"]): r for r in games_today.to_dict("records")}
    seasons = games_today["season"].dropna()
    season = int(seasons.iloc[0]) if not seasons.empty else default_season()
    tickets, legs = store.load_tickets(), store.load_legs()
    today_tickets = tickets[(tickets["strategy_id"] == strategy_id)
                            & (tickets["game_date_et"] == day)]
    decision = parlay.decide_day(
        views, scfg, now,
        schedules=parlay.team_schedules(games, aliases),
        sp_ratings=_sp_ratings(season),
        wind_mph=_kickoff_winds(views, games_by_id),
        tickets_today=len(today_tickets),
        lost_yesterday=parlay.prior_day_lost(tickets, legs, strategy_id, day),
        aliases=aliases,
    )

    ticket_id = f"{strategy_id}-{day}" if decision.status == "ticket" else ""
    if ticket_id:
        stake = float(scfg["staking"]["flat_stake"])
        lo, hi = scfg["ticket"]["price_band_american"]
        store.append_ticket(
            {
                "ticket_id": ticket_id, "strategy_id": strategy_id, "game_date_et": day,
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
                    "ticket_id": ticket_id, "leg_no": n, "event_id": lg.event_id,
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
            "n_qualifiers": len(decision.qualifiers), "ticket_id": ticket_id,
            "notes": " | ".join(decision.skipped_games),
        },
        [
            {
                "strategy_id": strategy_id, "game_date_et": day, "event_id": lg.event_id,
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
    print(f"[ncaaf picks] {strategy_id} {day}: {decision.status} — {decision.reason}")
    for lg in decision.ticket_legs:
        print(f"  {lg.label} ({lg.price_american:+g} {lg.bookmaker}) "
              f"[{lg.signal_ids}] {lg.matchup}")
    if decision.price_american is not None and ticket_id:
        print(f"  ticket {decision.price_american:+g} (decimal {decision.price_decimal})")
