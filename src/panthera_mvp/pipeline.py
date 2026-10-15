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
from .config import (
    StrategyConfigError,
    config_hash,
    load_config,
    load_strategy_configs,
)
from .grading import grade_pending
from .matching import match_events, nearest_start
from .report import write_daily_report, write_ledger_report
from .strategy.daytype import day_type
from .strategy.dossier import Dossier, SeasonContext
from .strategy.movement import extract_game_prices, extract_totals_prices
from .strategy.registry import StrategyContext, engines
from .strategy.rules import Pass, Pick
from .strategy.season import in_scope
from .strategy.slots import assign_slots
from .timeutil import ET, now_utc, parse_utc, utc_iso


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
    """Fetch today's MLB schedule and upsert into games.csv.

    PANTHERA_MLB_FIXTURE (tests/offline dry-runs) points at a recorded
    schedule payload instead of calling statsapi — unit tests never touch
    the network.

    That variable is a TEST-ONLY switch: it is read with a bare `open()` and
    no path confinement, so it must never be wired to a `workflow_dispatch`
    input, a matrix value or any other caller-supplied value. Today only
    workflow YAML and the test suite set it. The same holds for the
    PANTHERA_NCAAF_* and PANTHERA_NCAABASE_* fixture variables."""
    fixture = os.environ.get("PANTHERA_MLB_FIXTURE")
    if fixture:
        with open(fixture) as fh:
            games = [
                g for g in mlb.parse_schedule(json.load(fh)) if g.game_date_et == date_et
            ]
    else:
        games = mlb.get_schedule(date_et)
    rows = []
    for g in games:
        # NOT g.status: `abstractGameState` reports a called-off game as
        # "Final", which nothing downstream can settle or void. See
        # mlb.stored_status.
        status = mlb.stored_status(g)
        is_final = status == "Final"
        if is_final and (g.home_score is None or g.away_score is None):
            # The shape that stranded 823490. If this fires, `detailedState`
            # carries a head `mlb._CALLED_OFF` does not know, so the row is
            # about to be stored Final with no score — unsettleable, and
            # doctor's H05 will suggest backfilling a score that may not
            # exist. Say so loudly rather than repeating the dead end.
            msg = (
                f"game {g.game_pk} is Final with no linescore and detailedState "
                f"{g.detailed_state!r} is not a known called-off state. A pick "
                "on it cannot settle. If that state means the game was called "
                "off, add its head to clients/mlb.py::_CALLED_OFF."
            )
            print(f"[refresh] {g.game_date_et}: {msg}", file=sys.stderr)
            store.append_run_note(
                g.game_date_et, "refresh", "unmapped_final_no_score", msg
            )
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
                "status": status,
                "home_score": g.home_score,
                "away_score": g.away_score,
                # `score or 0` on a Final with no linescore used to fabricate a
                # 0-0 result (the live 823490 row carried winner=Baltimore
                # Orioles, run_diff=0, total_runs=0 for a game never played).
                # No score means no derived result.
                "winner": (
                    (g.home_team if g.home_score > g.away_score else g.away_team)
                    if is_final and g.home_score is not None and g.away_score is not None
                    else None
                ),
                "run_diff": (
                    abs(g.home_score - g.away_score)
                    if is_final and g.home_score is not None and g.away_score is not None
                    else None
                ),
                "total_runs": (
                    g.home_score + g.away_score
                    if is_final and g.home_score is not None and g.away_score is not None
                    else None
                ),
                "home_pitcher_era": g.home_pitcher.era if g.home_pitcher else None,
                "away_pitcher_era": g.away_pitcher.era if g.away_pitcher else None,
                "score_source": "mlb",
            }
        )
    store.upsert_games(pd.DataFrame(rows))
    return games


def _build_season_context(date_et: str, cfg: dict) -> SeasonContext | None:
    """One league-wide schedule call covering the season to date; feeds every
    dossier's recent-outcomes/trends fields (doc §3). Returns None when the
    MLB API is unreachable — dossier tiebreaks then simply don't fire.

    Scope comes from `in_scope` — the same helper the engine gates use. These
    two disagreed until 2026-10-15 (config there, a hardcoded `== "R"` here),
    which is how a whitelist bug survived a config read. Postseason finals DO
    belong here: in a series the previous head-to-head meeting is yesterday's
    game, and that price is orig_rules' primary signal; excluding it would
    reach months back for exactly the games the gate now admits.

    `cfg` is the pipeline config, not a per-strategy one: the context is built
    once and shared by every strategy (see cmd_picks). A strategy that one day
    needs a different context scope is the moment to build per-strategy
    contexts — not before.
    """
    fixture = os.environ.get("PANTHERA_MLB_FIXTURE")
    if fixture:
        # Offline: any finals present in the fixture feed the context; a
        # picks-day fixture usually has none, so tiebreaks simply don't fire.
        with open(fixture) as fh:
            payload = json.load(fh)
        ctx = SeasonContext()
        for g in mlb.parse_schedule(payload):
            if (
                in_scope(g.game_type, cfg)
                and g.status == "Final"
                and g.home_score is not None
            ):
                ctx.add_final(g.home_team_id, g.away_team_id, g.home_score, g.away_score)
        _backfill_h2h_prices(ctx)
        return ctx
    season = date_et[:4]
    yesterday = str(date.fromisoformat(date_et) - timedelta(days=1))
    try:
        finals = mlb.get_schedule_range(f"{season}-03-15", yesterday)
    except Exception as exc:
        print(f"[picks] season context unavailable: {exc}", file=sys.stderr)
        return None
    ctx = SeasonContext()
    for g in finals:
        if not in_scope(g.game_type, cfg) or g.status != "Final":
            continue
        if g.home_score is None or g.away_score is None:
            continue
        ctx.add_final(g.home_team_id, g.away_team_id, g.home_score, g.away_score)
    _backfill_h2h_prices(ctx)
    return ctx


def _backfill_h2h_prices(ctx: SeasonContext) -> None:
    """Overlay closing H2H prices (orig_rules' primary signal, doc §1) onto
    an already-scored SeasonContext, for whichever finals we ALSO captured
    our own odds for. `_build_season_context`'s finals come from the whole
    season via the MLB API; our own odds (data/odds/lines.csv) only exist
    from this pipeline's own launch date forward, so early-season pairs
    simply have no price on file -- Dossier.prev_h2h_ml_* stays None and
    orig_rules' ML/RL path degrades to neutral for them, same as the
    already-documented ERA/ATS gaps in mvp-design.md."""
    games = store.load_games()
    lines = store.load_lines()
    if games.empty or lines.empty:
        return
    finals = games[
        (games["status"] == "Final")
        & games["home_score"].notna()
        & games["away_score"].notna()
    ].sort_values("game_date_et")
    for row in finals.itertuples(index=False):
        ev_rows = lines[
            (lines["game_pk"] == row.game_pk) & (lines["snapshot_label"] != "close")
        ]
        if ev_rows.empty:
            continue
        odds_event_id = ev_rows.iloc[0]["odds_event_id"]
        prices = extract_game_prices(lines, odds_event_id, row.home_team, row.away_team)
        if prices is None:
            continue
        ctx.add_h2h_price(
            row.home_team_id,
            row.away_team_id,
            prices.home_ml_latest,
            prices.away_ml_latest,
            prices.home_rl_price,
            prices.away_rl_price,
        )


def _build_dossier(g: mlb.GameInfo, ctx: SeasonContext | None, cfg: dict) -> Dossier:
    era_home = g.home_pitcher.era if g.home_pitcher else None
    era_away = g.away_pitcher.era if g.away_pitcher else None
    if ctx is None:
        return Dossier(era_home=era_home, era_away=era_away)
    return Dossier.from_context(
        ctx,
        home_key=g.home_team_id,
        away_key=g.away_team_id,
        era_home=era_home,
        era_away=era_away,
        last10_n=int(cfg.get("dossier", {}).get("last10_n", 10)),
    )


# Snapshot-label canon, chronological. Two label vocabularies exist: snapshot
# labels (below) name odds captures; picks-run labels (morning/pregame/manual)
# name scheduled pipeline runs. Never conflate them — the mapping lives in
# _resolve_snapshot_label.
SNAPSHOT_LABEL_ORDER = ["open", "midday", "pregame", "close"]

# picks-run label -> the snapshot label that run takes immediately beforehand.
RUN_TO_SNAPSHOT = {"morning": "open", "pregame": "pregame"}


def _resolve_snapshot_label(
    run_label: str, lines_today: pd.DataFrame
) -> tuple[str | None, bool]:
    """Map a picks-run label to the movement-endpoint snapshot label.

    Returns (label, degraded). Fallback when the mapped label has no rows
    today (e.g. the credit guard skipped the snapshot): the latest label
    present that sits at or before the mapped one in SNAPSHOT_LABEL_ORDER,
    else the earliest label present — never zero-out the slate. `close` is
    CLV-only and never selected. `manual` runs use the latest label present.
    """
    present = [
        lab
        for lab in SNAPSHOT_LABEL_ORDER[:-1]  # excludes `close`
        if lab in set(lines_today["snapshot_label"])
    ]
    if not present:
        return None, False
    mapped = RUN_TO_SNAPSHOT.get(run_label)
    if mapped is None:  # manual
        return present[-1], False
    if mapped in present:
        return mapped, False
    mapped_idx = SNAPSHOT_LABEL_ORDER.index(mapped)
    before = [lab for lab in present if SNAPSHOT_LABEL_ORDER.index(lab) < mapped_idx]
    return (before[-1] if before else present[0]), True


def _late_run_check(run_label: str, cfg: dict, d: str) -> None:
    """GitHub cron drift can fire a run hours late (observed 2026-08-06,
    ~4h). Note it durably so the daily report explains a reduced slate."""
    runs_cfg = cfg.get("runs", {})
    sched = runs_cfg.get(run_label, {}).get("scheduled_et")
    if not sched:
        return
    grace = int(runs_cfg.get("late_run_grace_minutes", 90))
    now_et = now_utc().astimezone(ET)
    sched_h, sched_m = (int(x) for x in sched.split(":"))
    minutes_late = (now_et.hour * 60 + now_et.minute) - (sched_h * 60 + sched_m)
    if minutes_late > grace:
        note = (
            f"late run: {run_label} started {minutes_late} min after its "
            f"{sched} ET schedule; started games were skipped, slate reduced"
        )
        print(f"[picks] {note}")
        store.append_run_note(d, run_label, "late_run", note)


def _pick_row(p: Pick, strategy_id: str, scfg: dict, chash: str) -> dict:
    """Build a ledger row from a Pick. The single authoritative pick_id
    stamping site: whatever id the engine set is overwritten with the
    strategy-prefixed format."""
    return {
        "pick_id": f"{strategy_id}-{p.game_pk}-{p.market}-{p.game_date_et.replace('-', '')}",
        "strategy_id": strategy_id,
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
        "stake": scfg["staking"]["flat_stake"],
        "open_price": p.open_price,
        "latest_price": p.latest_price,
        "movement_cents": p.movement_cents,
        "rationale": p.rationale,
        "config_hash": chash,
        "status": "pending",
        "settled_ts_utc": None,
        "final_score": None,
        "profit": None,
        "close_price": None,
        "clv_cents": None,
    }


def _strategy_picks(
    sid: str,
    scfg: dict,
    games: list,
    events_by_pk: dict,
    lines_today: pd.DataFrame,
    season_ctx,
    snap_label: str | None,
    window: tuple[int, int],
    d: str,
    dry_run: bool,
    run_label: str,
    existing: pd.DataFrame,
    splits_lookup=None,
) -> tuple[list[dict], list[Pass]]:
    """Run one strategy's engine over the slate; returns (rows, passes).

    Per-day cap: the budget counts picks this strategy already recorded today
    (across runs) — the original per-invocation cap gave morning and pregame
    runs a fresh budget each, over-capping 4 of the first 15 live days.
    Earliest-start-first truncation bias: games arrive in schedule order, so
    when the cap binds it drops the latest games, not random ones.
    """
    engine = engines()[scfg["strategy"]["engine"]]
    chash = config_hash(scfg)
    # orig_rules' slot algorithm is a whole-day computation (strategy/
    # slots.py), not per-game — run it once here rather than per game below.
    # Other engines compute their own slot label internally and ignore this.
    slot_map: dict[int, str] = {}
    if scfg["strategy"]["engine"] == "orig_rules" and games:
        dtype = day_type(date.fromisoformat(d), scfg)
        slot_map = assign_slots(
            [(g.game_pk, g.start_utc) for g in games],
            dtype,
            int(scfg["hybrid_boundary_hour_et"]),
        )
    mine_today = (
        existing[
            (existing["game_date_et"] == d) & (existing["strategy_id"] == sid)
        ]
        if not existing.empty
        else existing
    )
    max_per_day = scfg["bet_limits"]["max_picks_per_day"]
    budget = None if max_per_day is None else max(0, int(max_per_day) - len(mine_today))
    my_pks_today = set(mine_today["game_pk"]) if not mine_today.empty else set()

    end_h, end_m = window
    picks: list[Pick] = []
    passes: list[Pass] = []
    for g in games:
        start_et = g.start_utc.astimezone(ET)
        if (start_et.hour, start_et.minute) > (end_h, end_m):
            continue
        if start_et <= now_utc().astimezone(ET) and not dry_run:
            continue  # game already started
        if scfg["bet_limits"]["one_pick_per_game"] and g.game_pk in my_pks_today:
            continue
        event_id = events_by_pk.get(g.game_pk)
        prices = (
            extract_game_prices(
                lines_today, event_id, g.home_team, g.away_team, latest_label=snap_label
            )
            if event_id
            else None
        )
        totals = (
            extract_totals_prices(lines_today, event_id, latest_label=snap_label)
            if event_id and scfg["strategy"]["engine"] == "orig_rules"
            else None
        )
        ctx = StrategyContext(
            game=g,
            odds_event_id=event_id,
            prices=prices,
            totals=totals,
            slot_type=slot_map.get(g.game_pk),
            dossier=_build_dossier(g, season_ctx, scfg),
            cfg=scfg,
            splits=splits_lookup(g) if splits_lookup else None,
        )
        result = engine(ctx)
        if isinstance(result, Pick):
            picks.append(result)
        elif isinstance(result, Pass):
            passes.append(result)

    if budget is not None:
        picks = picks[:budget]
    return [_pick_row(p, sid, scfg, chash) for p in picks], passes


def cmd_picks(window_end_et: str, dry_run: bool = False, run_label: str = "manual") -> None:
    cfg = load_config()  # pipeline config: shared prep + report plumbing only
    d = str(today_et())
    lines = store.load_lines()
    lines_today = lines[lines["game_date_et"] == d] if not lines.empty else lines
    if lines_today.empty:
        print("[picks] no odds lines for today; run snapshot first")
        return

    _late_run_check(run_label, cfg, d)
    snap_label, degraded = _resolve_snapshot_label(run_label, lines_today)
    if degraded:
        note = (
            f"degraded snapshot: {run_label} run expected the "
            f"'{RUN_TO_SNAPSHOT[run_label]}' snapshot but it has no rows today; "
            f"movement measured to '{snap_label}' instead"
        )
        print(f"[picks] {note}")
        store.append_run_note(d, run_label, "degraded_snapshot", note)

    strategies = load_strategy_configs(known_engines=set(engines()))
    live = {
        sid: scfg
        for sid, scfg in strategies.items()
        if scfg["strategy"].get("enabled") and "live" in scfg["strategy"]["scope"]
    }
    if not live:
        print("[picks] no enabled live strategies")
        return

    # Shared prep — one schedule refresh, one season context, one lines slice
    # for every strategy; N strategies cost zero extra API credits.
    games = _refresh_games(d)
    season_ctx = _build_season_context(d, cfg)
    events_by_pk = (
        lines_today.dropna(subset=["game_pk"])
        .drop_duplicates("game_pk")
        .set_index("game_pk")["odds_event_id"]
        .to_dict()
    )
    splits_lookup = _make_splits_lookup(d)
    window = tuple(int(x) for x in window_end_et.split(":"))
    existing = store.load_picks()

    total_added = 0
    for sid, scfg in live.items():
        try:
            rows, passes = _strategy_picks(
                sid,
                scfg,
                games,
                events_by_pk,
                lines_today,
                season_ctx,
                snap_label,
                window,
                d,
                dry_run,
                run_label,
                existing,
                splits_lookup=splits_lookup,
            )
        except StrategyConfigError:
            # NEVER isolated. A config fault hits every strategy identically,
            # so swallowing it per-strategy turns a broken deploy into a
            # silent zero-pick day that still exits 0 and commits. Let it
            # abort the run; `load_strategy_configs` above normally catches
            # this first, and this is the backstop.
            raise
        except Exception as exc:  # isolate: one bad engine must not lose the slate
            note = f"{sid}: engine error — {type(exc).__name__}: {exc}"
            print(f"[picks:{sid}] ERROR {note}", file=sys.stderr)
            store.append_run_note(d, run_label, "engine_error", note)
            continue
        if rows:
            added = store.append_picks(pd.DataFrame(rows))
            total_added += added
            print(f"[picks:{sid}] {added} new pick(s) recorded")
        else:
            print(f"[picks:{sid}] no picks generated")
        if passes:
            ts = utc_iso(now_utc())
            store.append_passes(
                pd.DataFrame(
                    [
                        {
                            "ts_utc": ts,
                            "run_label": run_label,
                            "strategy_id": sid,
                            "game_pk": p.game_pk,
                            "game_date_et": d,
                            "reason": f"[{p.rule_id}] {p.reason}",
                        }
                        for p in passes
                    ]
                )
            )
            for p in passes:
                print(f"[picks:{sid}] pass {p.matchup}: [{p.rule_id}] {p.reason}")

    credits_note = _credits_note()
    write_daily_report(d, cfg, new_picks=pd.DataFrame(), credits_note=credits_note)
    write_ledger_report(cfg)


def _make_splits_lookup(date_et: str):
    """Build a per-game splits accessor for splits-based engines, or None
    when the splits module/data is unavailable (engines then Pass)."""
    try:
        from .strategy.splits_signal import make_splits_lookup

        return make_splits_lookup(date_et)
    except ImportError:
        return None


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
        # Unconditional, not only on a refresh exception: the MLB API also
        # fails by SUCCEEDING with a hole — returning a game as Final with no
        # linescore — and `_refresh_games` stores that verbatim. Gating the
        # fallback on an exception left that hole unreachable. `_espn_fallback`
        # makes no network call when the date has nothing missing, so a
        # fully-settled date costs exactly what it did before.
        filled = _espn_fallback(d)
        if filled:
            print(f"[grade] {d}: filled {filled} game(s) from ESPN")
    settled = grade_pending()
    print(f"[grade] settled {len(settled)} pick(s)")
    from .clv import fill_clv

    filled = fill_clv()
    if filled:
        print(f"[grade] CLV filled for {filled} pick(s)")
    write_ledger_report(cfg)
    for d in pending_dates:
        write_daily_report(d, cfg, credits_note=_credits_note())


def _needs_final(games: pd.DataFrame) -> pd.Series:
    """Rows a finals fallback may fill: not Final yet, OR recorded Final with
    a missing score.

    The second arm is the whole point, not a belt-and-braces addition. This
    guard used to read `games["status"] != "Final"`, meaning "only fill games
    that are still unsettled" — but a row stored as Final with a NULL score is
    exactly the state that most needs a fallback, and `!= "Final"` made it
    permanently unreachable. `grading._result_for_pick` settles from the score,
    so a pick on such a game could never settle at all; three picks on
    2026-09-27 sat pending for 18 days because of it. Do not reinstate the
    `!= "Final"` form.

    A row already Final with BOTH scores present is excluded, so a fallback
    can only fill holes and never rewrites a complete final.
    """
    final_hole = (games["status"] == "Final") & (
        games["home_score"].isna() | games["away_score"].isna()
    )
    # A called-off game has no score because it was never played. ESPN must
    # not reopen one — it carries stale 0-0 rows for rain-outs, and MLB stays
    # the authority on a game that is later resumed.
    called_off = games["status"].isin(mlb.CALLED_OFF_STATUSES)
    return ~called_off & ((games["status"] != "Final") | final_hole)


def _espn_match_window() -> tuple[float, float]:
    """`(window_hours, ambiguity_minutes)` for splitting a doubleheader.

    From config/health.yaml's `grading.espn_fallback`, deliberately NOT
    config/strategy.yaml or a config/strategies/*.yaml: `config.py`'s
    HASH_EXCLUDED_KEYS drops only four top-level keys, so every other key in
    those files is part of each strategy's `config_hash`. A tolerance tweak
    there would move every MLB strategy's hash, split its ledger into a new
    report segment and reset its verdict countdown — for a knob no engine
    reads. health.yaml is the established home for exactly that (doctor's
    thresholds, `catchup`'s windows), and its own header forbids a strategy
    engine from reading it.

    Loaded lazily, and only on a date that actually has a doubleheader, so a
    broken health.yaml cannot stop an ordinary grade run. A missing key raises
    rather than defaulting: a silent fallback value is the magic number in
    engine code this file exists to avoid.
    """
    from .doctor import load_health_config

    cfg = (load_health_config().get("grading") or {}).get("espn_fallback") or {}
    return float(cfg["window_hours"]), float(cfg["ambiguity_minutes"])


def _match_doubleheader(
    rows: pd.DataFrame,
    eg: espn.EspnGame,
    used: set,
    window_hours: float,
    ambiguity_minutes: float,
):
    """Which of several stored rows sharing one matchup this ESPN event is.

    `rows` are all the stored games on the date with this (home_team,
    away_team) — complete finals included, which is the point: an ESPN event
    must be able to land on the game it actually belongs to and find it
    already settled, rather than being the only remaining candidate for the
    other game's open row.

    Returns that row's index label, or a one-line reason it could not be
    decided. A row with no stored start time is not a candidate: a gap cannot
    be computed for it, and the alternative is the guess this whole path
    exists to refuse.
    """
    if not eg.start_time_utc:
        return "the ESPN event carries no start time"
    start = parse_utc(eg.start_time_utc)
    cands = []
    for idx, row in rows.iterrows():
        stored = row["start_time_utc"]
        if idx in used or pd.isna(stored) or not str(stored):
            continue
        gap = abs((parse_utc(str(stored)) - start).total_seconds())
        cands.append((gap, f"game_pk {row['game_pk']}", idx))
    pick = nearest_start(cands, window_hours, ambiguity_minutes)
    return pick if isinstance(pick, str) else pick[1]


def _espn_fallback(date_et: str) -> int:
    """Fill this date's missing finals from ESPN. Returns how many game rows
    changed.

    Returns 0 without touching the network when the date has no hole, so
    calling it on every graded date is free in the common case."""
    games = store.load_games()
    if games.empty:
        return 0
    open_rows = (games["game_date_et"] == date_et) & _needs_final(games)
    if not open_rows.any():
        return 0
    try:
        scoreboard = espn.get_scoreboard(date_et)
    except Exception as exc:
        print(f"[grade] ESPN fallback failed for {date_et}: {exc}", file=sys.stderr)
        return 0
    # A games.csv in which no row yet carries these loads them as all-NaN
    # float64, and pandas refuses a string assignment into a float column
    # ("Invalid value 'New York Yankees' for dtype 'float64'"). Coerce once,
    # so the first final this store ever records can come from ESPN.
    for col in ("status", "winner", "score_source"):
        games[col] = games[col].astype(object)
    filled = 0
    # Both events of a doubleheader can hit the same ambiguity, and the run log
    # is committed and rendered into the daily report, so report each matchup
    # once.
    reported: set[tuple[str, str]] = set()
    # Index labels already claimed by an earlier event of the same matchup, so
    # two ESPN events cannot both land on one stored row.
    used: set = set()
    window: tuple[float, float] | None = None
    for eg in scoreboard:
        if not eg.completed or eg.home_score is None or eg.away_score is None:
            continue
        same_matchup = (
            (games["game_date_et"] == date_et)
            & (games["home_team"] == eg.home_team)
            & (games["away_team"] == eg.away_team)
        )
        # Nothing open for this matchup: no hole to fill, and therefore nothing
        # to report either — a settled doubleheader must not log an ambiguity.
        if not (same_matchup & _needs_final(games)).any():
            continue
        # (date, home_team, away_team) is NOT unique: a split doubleheader puts
        # two games of the same matchup on one date. Writing to the matchup
        # would broadcast one game's score to both rows, and `grade_pending`
        # settles from whichever score landed — permanently, because
        # `store.settle_picks` only rewrites rows still `pending`. So the event
        # is keyed onto ONE row by start time, the way `matching.py` and
        # `ncaabase/matching.py` already key theirs, and an event that cannot
        # be keyed is logged and skipped: reported, never guessed.
        if int(same_matchup.sum()) > 1:
            if window is None:
                window = _espn_match_window()
            hit = _match_doubleheader(games[same_matchup], eg, used, *window)
            if isinstance(hit, str):
                if (eg.home_team, eg.away_team) in reported:
                    continue
                reported.add((eg.home_team, eg.away_team))
                msg = (
                    f"{eg.away_team} @ {eg.home_team} starting "
                    f"{eg.start_time_utc or 'at an unreported time'}: "
                    f"{int(same_matchup.sum())} stored games share that matchup "
                    f"(doubleheader) and {hit}, so the ESPN event cannot be "
                    "keyed onto one of them; not filled. Only an MLB API "
                    "refresh can settle these — data/ is bot-owned and must "
                    "not be hand-edited."
                )
                print(
                    f"[grade] ambiguous ESPN match for {date_et} {msg}", file=sys.stderr
                )
                # Durable too: stderr lives only as long as the Actions log, and
                # this is the sole trace of a hole that will not be filled.
                store.append_run_note(date_et, "grade", "ambiguous_espn_match", msg)
                continue
            # Claimed even when the row turns out to be a complete final: that
            # is this event's game, so a later event of the same matchup must
            # not be allowed to take it.
            used.add(hit)
            mask = pd.Series(False, index=games.index)
            mask.loc[hit] = True
            mask &= _needs_final(games)
        else:
            mask = same_matchup & _needs_final(games)
        if not mask.any():
            continue
        filled += int(mask.sum())
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
    if filled:
        games.to_csv(paths.games_csv(), index=False)
    return filled


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


def cmd_splits(label: str = "manual", dry_run: bool = False) -> None:
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
        prev_remaining = lumify.last_known_remaining()
        try:
            results, info = lumify.fetch_splits_for_date(
                api_key,
                d,
                league=lcfg.get("league", "MLB"),
                min_credits_reserve=lcfg.get("min_credits_reserve", 50),
                # Morning fetch covers only the morning pick window (<16:00 ET);
                # the pregame fetch re-reads the evening slate fresher.
                window="morning" if label == "morning" else "all",
            )
        except lumify.LumifyCreditGuardError as exc:
            print(f"[splits] SKIPPED: {exc}")
            return
        # The SDK meta reports per-call credits (always 1); log the real
        # per-run delta so budget policy can be computed from the log.
        if prev_remaining is not None and info.remaining is not None:
            info = lumify.SplitsCreditInfo(
                used=prev_remaining - info.remaining, remaining=info.remaining
            )
        lumify.record_credits(info)
        lumify.save_raw(results, d, label)
        print(
            f"[splits] {len(results)} events with splits ({label}); credits "
            f"remaining={info.remaining}"
        )

    df = lumify.normalize(results, d, label)
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


def cmd_pages(run_label: str = "manual") -> None:
    from .dashboard import write_site

    out = write_site(generated_by_run=run_label)
    print(f"[pages] site regenerated at {out}")


def cmd_status() -> None:
    picks = store.load_picks()
    pending = 0 if picks.empty else int((picks["status"] == "pending").sum())
    remaining = odds.last_known_remaining()
    lines = store.load_lines()
    last_snap = "never" if lines.empty else str(lines["snapshot_ts_utc"].max())
    print(f"pending picks: {pending}")
    print(f"odds credits remaining (this month): {remaining}")
    print(f"last snapshot: {last_snap}")
