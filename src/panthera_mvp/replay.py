"""Retroactive replay — zero-API-cost evaluation over the pipeline's own
captured odds/games history (`panthera-mvp replay`, and the engine behind
`panthera-mvp catchup`).

Every live snapshot since launch (data/odds/lines.csv) and every game result
recorded since (data/games/games.csv) already exist on disk; this replays
strategy engines over them WITHOUT taking new snapshots or spending API
credits. Output goes to data/picks/shadow_picks.csv — a SEPARATE file from
the real ledger (data/picks/picks.csv), never pooled into any strategy's
pre-registered verdict (report.py renders it as a clearly marked RETROACTIVE
section). This keeps the append-once, pre-registered-criteria protocol
intact: replay picks were not placed in real time and cannot stand in for a
forward test, however useful they are as an early read.

**Fidelity.** The loop is `strategy/slate.py::evaluate_slate`, the same one
`cmd_picks` runs, and each day is replayed as the live scheduler would: a
morning pass against the `open` snapshot with a 16:00 window, then a pregame
pass against the `pregame` snapshot with a 23:59 window, the first pass's
picks counting against the second's daily budget. `bet_limits` caps and
`one_pick_per_game` therefore apply exactly as they do live. Before this, the
replay evaluated whole slates at once with no cap and no start-time window,
so shadow picks were systematically more numerous than the live picks they
stood in for.

**Warm-up.** The season context is accumulated from the FIRST captured date,
not from the start of the requested window, and it advances on every date in
between whether or not that date generates picks. A window starting
2026-09-29 otherwise evaluated its first day with no record, no form and no
previous-head-to-head price — and that price is `pv_orig`'s primary signal,
so a cold start is not a slightly different engine, it is a different one.
`ReplayResult.warmup_*` reports what the warm-up actually built; if it is
zero, the operator needs to see that.

Caveats stated in the report, not hidden:
  - ERA is only populated in games.csv from 2026-08-16 forward (the
    probablePitcher hydrate fix) — ERA-dependent gates are partly dormant
    for earlier dates.
  - The season context is built ONLY from what this pipeline has itself
    captured — short and sparse near the start of the window, unlike a live
    run, which reads the whole season from the MLB API.
  - Splits are not replayed. `sharp_split` and `fade_public` consult
    `data/splits/splits.csv` through a lookup the live pipeline builds per
    run; a replay passes none, so those engines pass every game on
    "no-splits". Replaying them would need the splits history keyed the way
    the live run keyed it, which is a separate piece of work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

import pandas as pd

from . import store
from .clients.mlb import GameInfo, PitcherInfo
from .grading import _result_for_pick
from .strategy.dossier import SeasonContext
from .strategy.movement import extract_game_prices
from .strategy.registry import engines
from .strategy.season import in_scope
from .strategy.slate import evaluate_slate, pick_row
from .timeutil import ET, now_utc, parse_utc, utc_iso

#: The two scheduled pick runs, as the replay reproduces them: (run label,
#: snapshot label, window end, the ET clock the run saw). Mirrors
#: .github/workflows/mvp-morning.yml (10:35 ET, --window-end-et 16:00) and
#: mvp-pregame.yml (16:50 ET, 23:59).
PASSES = (
    ("morning", "open", (16, 0), time(10, 35)),
    ("pregame", "pregame", (23, 59), time(16, 50)),
)


@dataclass
class ReplayResult:
    strategy_ids: list[str] = field(default_factory=list)
    generated_dates: list[str] = field(default_factory=list)
    warmup_dates: int = 0
    warmup_finals: int = 0
    warmup_h2h: int = 0
    added: int = 0
    graded: int = 0
    #: Dates in range that had no captured odds at all, so nothing could be
    #: replayed for them. A silent skip here used to look like "no picks".
    no_lines_dates: list[str] = field(default_factory=list)


def _game_info(row) -> GameInfo:
    """Rebuild the GameInfo a live run would have had.

    The pitcher objects matter: `slate.build_dossier` reads ERA off
    `g.home_pitcher.era`, so leaving them None would silently drop every
    ERA-dependent gate (R3_era, R4's evenness check, half of the R8 veto).
    games.csv stores the ERAs as columns, so they are put back here.
    """
    return GameInfo(
        game_pk=int(row.game_pk),
        game_date_et=str(row.game_date_et),
        game_type=str(row.game_type),
        status="Preview",  # replay always decides as of before the game
        detailed_state="Scheduled",
        start_utc=parse_utc(str(row.start_time_utc)),
        doubleheader=str(row.doubleheader) if pd.notna(row.doubleheader) else "N",
        game_number=int(row.game_number) if pd.notna(row.game_number) else 1,
        home_team_id=int(row.home_team_id),
        home_team=str(row.home_team),
        away_team_id=int(row.away_team_id),
        away_team=str(row.away_team),
        home_pitcher=PitcherInfo(
            era=float(row.home_pitcher_era) if pd.notna(row.home_pitcher_era) else None
        ),
        away_pitcher=PitcherInfo(
            era=float(row.away_pitcher_era) if pd.notna(row.away_pitcher_era) else None
        ),
    )


def _as_of(date_et: str, clock: time) -> datetime:
    return datetime.combine(pd.Timestamp(date_et).date(), clock, tzinfo=ET)


def _advance_context(ctx: SeasonContext, day_games, lines_today, scfg) -> tuple[int, int]:
    """Fold one day's finals into the context. Called AFTER that day's picks
    (no lookahead) and on EVERY date in range, generating or not — a window
    with gaps in the middle would otherwise develop a hole in its context.

    Returns (finals added, h2h prices added).
    """
    finals = h2h = 0
    for row in day_games[day_games["status"] == "Final"].itertuples(index=False):
        if pd.isna(row.home_score) or pd.isna(row.away_score):
            continue
        if not in_scope(str(row.game_type), scfg):
            continue
        ctx.add_final(
            row.home_team_id, row.away_team_id,
            int(row.home_score), int(row.away_score),
        )
        finals += 1
        if lines_today is None or lines_today.empty:
            continue
        ev_rows = lines_today[lines_today["game_pk"] == row.game_pk]
        if ev_rows.empty:
            continue
        # Same snapshot label the pregame pass priced its picks at. This used
        # to fall through to "most recent non-close", so the dossier's prices
        # were measured at a different endpoint than the picks' were.
        p = extract_game_prices(
            lines_today, ev_rows.iloc[0]["odds_event_id"],
            row.home_team, row.away_team, latest_label="pregame",
        )
        if p is not None:
            ctx.add_h2h_price(
                row.home_team_id, row.away_team_id,
                p.home_ml_latest, p.away_ml_latest,
                p.home_rl_price, p.away_rl_price,
            )
            h2h += 1
    return finals, h2h


def _live_strategy_ids(strategies: dict) -> list[str]:
    return sorted(
        sid
        for sid, cfg in strategies.items()
        if cfg["strategy"].get("enabled") and "live" in cfg["strategy"]["scope"]
    )


def replay_window(
    strategy_ids: list[str] | None = None,
    from_et: str | None = None,
    to_et: str | None = None,
    *,
    only_dates: set[str] | None = None,
    grade: bool = True,
    run_label: str = "replay",
    quiet: bool = False,
) -> ReplayResult:
    """Replay the given strategies over the captured history.

    `from_et`/`to_et` bound which dates GENERATE picks; the context always
    warms up from the first captured date. `only_dates` narrows generation
    further (catch-up passes its detected gap dates) without touching the
    warm-up or the advance.
    """
    from .config import config_hash, load_strategy_configs

    strategies = load_strategy_configs(known_engines=set(engines()))
    sids = strategy_ids or _live_strategy_ids(strategies)
    unknown = [s for s in sids if s not in strategies]
    if unknown:
        raise SystemExit(f"[replay] unknown strategy id(s): {', '.join(unknown)}")

    result = ReplayResult(strategy_ids=list(sids))
    games, lines = store.load_games(), store.load_lines()
    if games.empty or lines.empty:
        if not quiet:
            print("[replay] no captured games/lines to replay")
        return result
    lines = lines.dropna(subset=["game_pk"]).astype({"game_pk": int})

    all_dates = sorted(games["game_date_et"].unique())
    if to_et:
        all_dates = [d for d in all_dates if d <= to_et]

    def generating(d: str) -> bool:
        if from_et and d < from_et:
            return False
        return only_dates is None or d in only_dates

    if not any(generating(d) for d in all_dates):
        if not quiet:
            print("[replay] no dates in range")
        return result

    existing = store.load_shadow_picks()
    # One context per strategy: it advances under that strategy's own scope
    # rule, and `in_scope` is cheap enough that sharing is not worth the
    # coupling. Prep that does NOT vary by strategy — the day's games, lines
    # and event map — is built once per day below.
    ctxs = {sid: SeasonContext() for sid in sids}
    rows: list[dict] = []
    per_strategy_dates: dict[str, set[str]] = {sid: set() for sid in sids}

    for d in all_dates:
        day_games = games[games["game_date_et"] == d]
        lines_today = lines[lines["game_date_et"] == d]
        game_infos = [_game_info(r) for r in day_games.itertuples(index=False)]
        gen = generating(d)

        if gen and lines_today.empty:
            result.no_lines_dates.append(d)

        if gen and not lines_today.empty:
            events_by_pk = (
                lines_today.drop_duplicates("game_pk")
                .set_index("game_pk")["odds_event_id"]
                .to_dict()
            )
            for sid in sids:
                scfg = strategies[sid]
                engine = engines()[scfg["strategy"]["engine"]]
                chash = config_hash(scfg)
                mine = (
                    existing[
                        (existing["game_date_et"] == d)
                        & (existing["strategy_id"] == sid)
                    ]
                    if not existing.empty
                    else existing
                )
                max_per_day = scfg["bet_limits"]["max_picks_per_day"]
                budget = (
                    None
                    if max_per_day is None
                    else max(0, int(max_per_day) - len(mine))
                )
                picked_pks = set(mine["game_pk"]) if not mine.empty else set()

                day_rows: list[dict] = []
                for _label, snap_label, window, clock in PASSES:
                    out = evaluate_slate(
                        engine=engine,
                        scfg=scfg,
                        games=game_infos,
                        events_by_pk=events_by_pk,
                        lines_today=lines_today,
                        season_ctx=ctxs[sid],
                        snap_label=snap_label,
                        window=window,
                        date_et=d,
                        as_of_et=_as_of(d, clock),
                        already_picked_pks=picked_pks,
                        budget=budget,
                        splits_lookup=None,
                    )
                    for p in out.picks:
                        day_rows.append(pick_row(p, sid, scfg, chash))
                        picked_pks.add(p.game_pk)
                    if budget is not None:
                        budget = max(0, budget - len(out.picks))
                if day_rows:
                    rows.extend(day_rows)
                    per_strategy_dates[sid].add(d)

        for sid in sids:
            finals, h2h = _advance_context(
                ctxs[sid], day_games, lines_today, strategies[sid]
            )
            if sid == sids[0]:  # count the warm-up once, not once per strategy
                if not gen:
                    result.warmup_dates += 1
                    result.warmup_finals += finals
                    result.warmup_h2h += h2h

    result.generated_dates = sorted({d for s in per_strategy_dates.values() for d in s})
    if rows:
        result.added = store.append_shadow_picks(pd.DataFrame(rows))
    if not quiet:
        print(
            f"[replay] warm-up over {result.warmup_dates} date(s) "
            f"({result.warmup_finals} finals, {result.warmup_h2h} H2H prices)"
        )
        print(
            f"[replay] {result.added} shadow pick(s) added for "
            f"{', '.join(sids)} over {len(result.generated_dates)} date(s)"
        )
        if result.no_lines_dates:
            print(
                f"[replay] {len(result.no_lines_dates)} date(s) in range had no "
                f"captured odds and were skipped: "
                f"{', '.join(result.no_lines_dates[:5])}"
                + (" …" if len(result.no_lines_dates) > 5 else "")
            )

    for d in result.generated_dates:
        store.append_run_note(
            d, run_label, "replay_shadow",
            f"replayed {', '.join(sids)} into the shadow ledger",
        )

    if grade:
        result.graded = grade_shadow(games)
        if not quiet:
            print(f"[replay] {result.graded} shadow pick(s) graded")
    return result


def grade_shadow(games: pd.DataFrame | None = None) -> int:
    """Settle whatever the shadow ledger has pending, against games.csv."""
    games = store.load_games() if games is None else games
    shadow = store.load_shadow_picks()
    if shadow.empty or games.empty:
        return 0
    pending = shadow[shadow["status"] == "pending"]
    if pending.empty:
        return 0
    games_by_pk = games.set_index("game_pk")
    settlements = []
    for _, pick in pending.iterrows():
        pk = pick["game_pk"]
        if pk not in games_by_pk.index:
            continue
        outcome = _result_for_pick(pick, games_by_pk.loc[pk])
        if outcome is None:
            continue
        status, final_score = outcome
        stake = float(pick["stake"])
        profit = (
            round(stake * (float(pick["price_decimal"]) - 1), 2)
            if status == "win"
            else (-stake if status == "loss" else 0.0)
        )
        settlements.append(
            {
                "pick_id": pick["pick_id"],
                "status": status,
                "settled_ts_utc": utc_iso(now_utc()),
                "final_score": final_score,
                "profit": profit,
            }
        )
    return store.settle_shadow_picks(pd.DataFrame(settlements))


def cmd_replay(
    strategy: list[str] | str | None = None,
    from_et: str | None = None,
    to_et: str | None = None,
) -> None:
    """Thin CLI adapter over `replay_window`."""
    if isinstance(strategy, str):
        strategy = [strategy]
    replay_window(strategy_ids=strategy, from_et=from_et, to_et=to_et)
