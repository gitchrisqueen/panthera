"""Replay a strategy engine over normalized historical seasons.

Shares the same StrategyContext -> Pick|Pass|None engine shape as the live
pipeline (strategy/registry.py). As of the 2026-08-19 alignment work:

  - movement = open -> close moneyline for pv_rules-family engines (a coarse
    proxy for intraday movement); orig_rules additionally uses the previous
    head-to-head meeting's own close as its primary signal (real data, not a
    proxy -- the archives price every game).
  - no probable-pitcher ERA in the archives (they carry pitcher names, not
    ERAs), so ERA-dependent gates never fire historically. This is the one
    remaining documented gap (see docs/mvp-design.md).
  - real game start times are joined in from the MLB Stats API schedule
    cache (clients/mlb_history.py) -- hybrid Wednesdays are no longer
    skipped, and the shape-of-day slot algorithm (strategy/slots.py) can run.
    A small fraction of games (~1.5%, an sbro home/away labeling edge case)
    have no schedule match; those are dropped and counted, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from .. import paths
from ..clients.mlb import GameInfo
from ..clients.mlb_history import attach_start_times, load_schedules
from ..strategy.dossier import Dossier, SeasonContext
from ..strategy.movement import TotalsPrices
from ..strategy.rules import GamePrices, Pick
from ..strategy.slots import assign_slots
from .loader import load_dir

if TYPE_CHECKING:
    from ..strategy.registry import GenerateFn


@dataclass
class BacktestResult:
    picks: pd.DataFrame
    summary: dict


def _totals_from_row(row) -> TotalsPrices | None:
    if row.total_open is None or row.total_close is None:
        return None
    return TotalsPrices(
        open_point=row.total_open,
        latest_point=row.total_close,
        over_price=row.total_close_over_odds,
        under_price=row.total_close_under_odds,
    )


PreparedGame = tuple[GameInfo, GamePrices, "TotalsPrices | None", Dossier, dict]


def _prepare_games(hist: pd.DataFrame) -> list[PreparedGame]:
    """Precompute per-game inputs once; reused across every config in a sweep."""
    hist = hist.sort_values(["season", "game_date"]).reset_index(drop=True)
    schedules = load_schedules(sorted(hist["season"].unique()))
    hist = attach_start_times(hist, schedules)

    unmatched = int(hist["start_utc"].isna().sum())
    if unmatched:
        print(f"[backtest] {unmatched} game(s) had no schedule match; dropped, never guessed")
    hist = hist[hist["start_utc"].notna()].reset_index(drop=True)

    prepared = []
    contexts: dict[int, SeasonContext] = {}
    for idx, row in enumerate(hist.itertuples(index=False)):
        game = GameInfo(
            game_pk=int(row.game_pk) if pd.notna(row.game_pk) else 1_000_000 + idx,
            game_date_et=str(row.game_date),
            game_type="R",
            status="Preview",
            detailed_state="Scheduled",
            start_utc=row.start_utc.to_pydatetime(),
            doubleheader=str(row.doubleheader) if pd.notna(row.doubleheader) else "N",
            game_number=int(row.game_number) if pd.notna(row.game_number) else 1,
            home_team_id=0,
            home_team=str(row.home_team),
            away_team_id=0,
            away_team=str(row.vis_team),
        )
        # Run-line price only counts when the line is the standard 1.5.
        home_rl = (
            row.home_rl_odds
            if row.home_rl_line is not None and abs(row.home_rl_line) == 1.5
            else None
        )
        vis_rl = (
            row.vis_rl_odds
            if row.vis_rl_line is not None and abs(row.vis_rl_line) == 1.5
            else None
        )
        prices = GamePrices(
            home_ml_open=row.home_ml_open,
            away_ml_open=row.vis_ml_open,
            home_ml_latest=row.home_ml_close,
            away_ml_latest=row.vis_ml_close,
            home_rl_price=home_rl,
            away_rl_price=vis_rl,
        )
        totals = _totals_from_row(row)
        ctx = contexts.setdefault(int(row.season), SeasonContext())
        dossier = Dossier.from_context(
            ctx, home_key=str(row.home_team), away_key=str(row.vis_team)
        )
        home_covered = away_covered = None
        if home_rl is not None:
            margin = int(row.home_final) - int(row.vis_final)
            adjusted = margin + float(row.home_rl_line)
            if adjusted != 0:
                home_covered = adjusted > 0
                away_covered = not home_covered
        ctx.add_final(
            str(row.home_team),
            str(row.vis_team),
            int(row.home_final),
            int(row.vis_final),
            a_covered_rl=home_covered,
            b_covered_rl=away_covered,
        )
        ctx.add_h2h_price(
            str(row.home_team), str(row.vis_team),
            row.home_ml_close, row.vis_ml_close,
            home_rl, vis_rl,
        )
        result = {
            "home_final": row.home_final,
            "vis_final": row.vis_final,
            "season": row.season,
            "game_date": row.game_date,
            "day_of_week": row.day_of_week,
        }
        prepared.append((game, prices, totals, dossier, result))
    return prepared


def _grade(pick: Pick, result: dict, stake: float) -> tuple[str, float]:
    if pick.market == "total":
        total_runs = int(result["home_final"]) + int(result["vis_final"])
        adjusted = total_runs - float(pick.line)
        if adjusted == 0:
            return "push", 0.0
        over_won = adjusted > 0
        won = over_won if pick.selection == "over" else not over_won
        return ("win", round(stake * (pick.price_decimal - 1), 2)) if won else ("loss", -stake)

    home_win_margin = result["home_final"] - result["vis_final"]
    sel_is_home = pick.selection == pick.matchup.split(" @ ")[1]
    margin = home_win_margin if sel_is_home else -home_win_margin
    if pick.market == "rl":
        adjusted = margin + float(pick.line)
        if adjusted == 0:
            return "push", 0.0
        won = adjusted > 0
    else:
        won = margin > 0
    if won:
        return "win", round(stake * (pick.price_decimal - 1), 2)
    return "loss", -stake


def _slot_maps(
    prepared: list[PreparedGame],
    cfg: dict,
) -> dict[tuple[int, str], dict[int, str]]:
    """Group prepared games by (season, game_date) and run the shape-of-day
    slot algorithm (strategy/slots.py) once per day -- orig_rules' input.
    Recomputed per strategy config (cheap: no I/O) since a config's own
    day_map/hybrid_boundary_hour_et may in principle differ."""
    by_day: dict[tuple[int, str], list[tuple[int, object]]] = {}
    for game, _, _, _, result in prepared:
        key = (result["season"], result["game_date"])
        by_day.setdefault(key, []).append((game.game_pk, game.start_utc))

    boundary = int(cfg.get("hybrid_boundary_hour_et", 18))
    out: dict[tuple[int, str], dict[int, str]] = {}
    for (season, day), games in by_day.items():
        dow = pd.Timestamp(day).strftime("%A").lower()
        dtype = cfg["day_map"].get(dow)
        if dtype is None:
            continue
        out[(season, day)] = assign_slots(games, dtype, boundary)
    return out


def run(
    prepared: list[PreparedGame],
    cfg: dict,
    stake: float = 100.0,
    generate: GenerateFn | None = None,
) -> BacktestResult:
    """Replay one strategy engine over the prepared games.

    `generate` is a registry engine (StrategyContext -> Pick|Pass|None);
    the default is the `_pv_rules` adapter — raw `generate_pick` has a
    5-argument signature and is not a GenerateFn, so the adapter keeps one
    shared engine shape between live pipeline and backtest."""
    from ..strategy.registry import StrategyContext, _pv_rules

    engine = generate or _pv_rules
    needs_slots = getattr(engine, "__name__", "") == "_orig_rules"
    slot_maps = _slot_maps(prepared, cfg) if needs_slots else {}

    rows = []
    for game, prices, totals, dossier, result in prepared:
        slot_type = None
        if needs_slots:
            slot_type = slot_maps.get((result["season"], result["game_date"]), {}).get(
                game.game_pk
            )
        outcome = engine(
            StrategyContext(
                game=game,
                odds_event_id=f"bt-{game.game_pk}",
                prices=prices,
                totals=totals,
                slot_type=slot_type,
                dossier=dossier,
                cfg=cfg,
            )
        )
        if not isinstance(outcome, Pick):
            continue
        status, profit = _grade(outcome, result, stake)
        rows.append(
            {
                "season": result["season"],
                "game_date": outcome.game_date_et,
                "day_of_week": result["day_of_week"],
                "matchup": outcome.matchup,
                "day_type": outcome.day_type,
                "slot_type": outcome.slot_type,
                "rule_id": outcome.rule_id,
                "market": outcome.market,
                "selection": outcome.selection,
                "price_american": outcome.price_american,
                "movement_cents": outcome.movement_cents,
                "status": status,
                "profit": profit,
            }
        )
    picks = pd.DataFrame(rows)
    if picks.empty:
        summary = {"n_bets": 0, "wins": 0, "losses": 0, "pushes": 0, "roi": 0.0, "profit": 0.0}
    else:
        wins = int((picks["status"] == "win").sum())
        losses = int((picks["status"] == "loss").sum())
        pushes = int((picks["status"] == "push").sum())
        profit = round(float(picks["profit"].sum()), 2)
        risked = stake * (wins + losses)
        summary = {
            "n_bets": len(picks),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "profit": profit,
            "roi": round(100 * profit / risked, 2) if risked else 0.0,
        }
    return BacktestResult(picks=picks, summary=summary)


def _parse_seasons(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    lo, _, hi = spec.partition("-")
    return int(lo), int(hi or lo)


def cmd_backtest(seasons: str | None, strategy: str | None = None) -> None:
    from ..config import load_strategy_configs
    from ..strategy.registry import BACKTESTABLE_ENGINES, engines

    strategies = load_strategy_configs(known_engines=set(engines()))
    if strategy:
        if strategy not in strategies:
            raise SystemExit(f"[backtest] unknown strategy id: {strategy}")
        targets = {strategy: strategies[strategy]}
    else:
        targets = {
            sid: scfg
            for sid, scfg in strategies.items()
            if "backtest" in scfg["strategy"]["scope"]
        }
    if not targets:
        raise SystemExit("[backtest] no strategies with backtest scope")

    hist = load_dir()
    rng = _parse_seasons(seasons)
    if rng:
        hist = hist[(hist["season"] >= rng[0]) & (hist["season"] <= rng[1])]
    prepared = _prepare_games(hist)  # expensive part — shared across strategies

    for sid, scfg in targets.items():
        engine_name = scfg["strategy"]["engine"]
        if engine_name not in BACKTESTABLE_ENGINES:
            # Loud refusal, never silent emptiness: splits engines have no
            # historical inputs (no splits archives exist).
            print(
                f"[backtest] REFUSED {sid}: engine '{engine_name}' is not "
                "backtestable (no historical splits data). Forward paper-trade "
                "only."
            )
            continue
        result = run(prepared, scfg, generate=engines()[engine_name])
        print(f"[backtest:{sid}] seasons={seasons or 'all'} summary={result.summary}")
        out = paths.calibration_dir() / f"backtest_picks_{sid}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        result.picks.to_csv(out, index=False)
        print(f"[backtest:{sid}] picks written to {out}")
        if not result.picks.empty:
            graded = result.picks[result.picks["status"].isin(["win", "loss"])]
            by_rule = (
                result.picks.groupby("rule_id")
                .agg(
                    n=("profit", "size"),
                    wins=("status", lambda s: int((s == "win").sum())),
                    profit=("profit", "sum"),
                )
                .assign(
                    roi_pct=lambda df: (
                        100 * df["profit"] / (100.0 * df["n"])
                    ).round(2)
                )
            )
            by_rule_out = paths.calibration_dir() / f"backtest_by_rule_{sid}.csv"
            by_rule.to_csv(by_rule_out)
            print(by_rule.to_string())
            print(
                f"[backtest:{sid}] graded={len(graded)} by-rule breakdown "
                f"written to {by_rule_out}"
            )
