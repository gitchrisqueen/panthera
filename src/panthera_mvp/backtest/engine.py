"""Replay the rules engine over normalized historical seasons.

Uses the exact same generate_pick code path as the live pipeline, with:
  - movement = open -> close moneyline (a coarse proxy for intraday movement);
  - no ERA/dossier data (sbro files carry pitcher names, not ERAs), so the
    neutral-movement ERA fallback and the R8 veto never fire historically;
  - hybrid (Wednesday) days skipped — the files carry no game start times, so
    slots cannot be assigned. Hybrid behavior is only testable in forward
    paper-trading. This is reported, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING

import pandas as pd

from .. import paths
from ..clients.mlb import GameInfo
from ..strategy.dossier import Dossier, SeasonContext
from ..strategy.rules import GamePrices, Pass, Pick
from ..timeutil import ET, UTC
from .loader import load_dir

if TYPE_CHECKING:
    from ..strategy.registry import GenerateFn


@dataclass
class BacktestResult:
    picks: pd.DataFrame
    summary: dict


def _prepare_games(hist: pd.DataFrame) -> list[tuple[GameInfo, GamePrices, Dossier, dict]]:
    """Precompute per-game inputs once; reused across every config in a sweep."""
    prepared = []
    # Chronological iteration + per-season contexts: each game's dossier sees
    # only strictly earlier finals (no lookahead). Team keys are the raw
    # abbreviations from the archive files.
    hist = hist.sort_values(["season", "game_date"]).reset_index(drop=True)
    contexts: dict[int, SeasonContext] = {}
    for idx, row in enumerate(hist.itertuples(index=False)):
        # Fabricate a 19:05 ET start; only the DATE matters because hybrid
        # days are skipped in backtests.
        start_utc = datetime.combine(
            pd.Timestamp(row.game_date).date(), time(19, 5), tzinfo=ET
        ).astimezone(UTC)
        game = GameInfo(
            game_pk=1_000_000 + idx,
            game_date_et=str(row.game_date),
            game_type="R",
            status="Preview",
            detailed_state="Scheduled",
            start_utc=start_utc,
            doubleheader="N",
            game_number=1,
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
        ctx = contexts.setdefault(int(row.season), SeasonContext())
        dossier = Dossier.from_context(
            ctx, home_key=str(row.home_team), away_key=str(row.vis_team)
        )
        ctx.add_final(
            str(row.home_team),
            str(row.vis_team),
            int(row.home_final),
            int(row.vis_final),
        )
        result = {
            "home_final": row.home_final,
            "vis_final": row.vis_final,
            "season": row.season,
            "day_of_week": row.day_of_week,
        }
        prepared.append((game, prices, dossier, result))
    return prepared


def _grade(pick: Pick, result: dict, stake: float) -> tuple[str, float]:
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


def run(
    prepared: list[tuple[GameInfo, GamePrices, Dossier, dict]],
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
    rows = []
    skipped_hybrid = 0
    for game, prices, dossier, result in prepared:
        # Hybrid days can't be slotted without start times.
        if cfg["day_map"].get(result["day_of_week"]) == "HYBRID":
            skipped_hybrid += 1
            continue
        outcome = engine(
            StrategyContext(
                game=game,
                odds_event_id=f"bt-{game.game_pk}",
                prices=prices,
                dossier=dossier,
                cfg=cfg,
            )
        )
        if not isinstance(outcome, Pick):
            if isinstance(outcome, Pass):
                continue
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
            "skipped_hybrid": skipped_hybrid,
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
