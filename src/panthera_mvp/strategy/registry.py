"""Strategy registry — the multi-strategy layer over the rules engine.

An **engine** is a pure function `(StrategyContext) -> Pick | Pass | None`.
A **strategy** is an engine plus a per-strategy YAML in config/strategies/
(id, scope, evaluation criteria, bet limits, behavioral parameters). The
daily pipeline prepares shared inputs once per slate — N strategies cost no
extra Odds API credits — and runs every enabled live strategy's engine over
each game, with per-strategy bet limits, ledger rows, pass records, and
report sections.

The incumbent P/V rules engine is wrapped by a thin adapter (`_pv_rules`) so
`generate_pick` keeps its plain-argument signature and stays the single
shared code path between the live pipeline and the backtest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..clients.mlb import GameInfo
from ..timeutil import to_et
from .daytype import day_type, slot_type
from .dossier import Dossier
from .rules import GamePrices, Pass, Pick, american_to_decimal, generate_pick

if TYPE_CHECKING:
    from .splits_signal import GameSplits


@dataclass
class StrategyContext:
    """Everything an engine may consult for one game. Engines must treat this
    as read-only and degrade to a Pass (never raise) on missing inputs."""

    game: GameInfo
    odds_event_id: str | None
    prices: GamePrices | None
    dossier: Dossier
    cfg: dict[str, Any]
    splits: GameSplits | None = None


GenerateFn = Callable[[StrategyContext], Pick | Pass | None]


def _pv_rules(ctx: StrategyContext) -> Pick | Pass | None:
    """Adapter over the incumbent R0–R8 rules engine (strategy/rules.py)."""
    return generate_pick(ctx.game, ctx.odds_event_id, ctx.prices, ctx.dossier, ctx.cfg)


def fav_ml_pick(ctx: StrategyContext) -> Pick | Pass | None:
    """Baseline control: the lower-ML side at latest consensus, every game.

    Purpose: a full-slate vig anchor (expected ROI ≈ the book's hold on
    favorites — measured, not assumed) and a grading/price-capture bug
    detector. Uncapped by design: capped-earliest-games would be a biased
    subsample, not an anchor.
    """
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    if g.game_type not in ctx.cfg["season"]["game_types"]:
        return Pass(g.game_pk, matchup, "B_FAV", f"game_type={g.game_type}")
    if g.status != "Preview":
        return Pass(g.game_pk, matchup, "B_FAV", f"status={g.status}")
    if ctx.odds_event_id is None or ctx.prices is None:
        return Pass(g.game_pk, matchup, "B_FAV", "no matched odds event")
    home_ml, away_ml = ctx.prices.home_ml_latest, ctx.prices.away_ml_latest
    if home_ml is None or away_ml is None:
        return Pass(g.game_pk, matchup, "B_FAV", "incomplete moneyline")

    home_is_fav = home_ml <= away_ml
    selection, price = (
        (g.home_team, home_ml) if home_is_fav else (g.away_team, away_ml)
    )
    start_et = to_et(g.start_utc)
    dtype = day_type(start_et.date(), ctx.cfg)
    return Pick(
        game_pk=g.game_pk,
        odds_event_id=ctx.odds_event_id,
        game_date_et=g.game_date_et,
        matchup=matchup,
        start_time_et=start_et.strftime("%Y-%m-%d %H:%M"),
        day_type=dtype,
        slot_type=slot_type(g.start_utc, ctx.cfg),
        rule_id="B_FAV",
        market="ml",
        selection=selection,
        line=None,
        price_american=price,
        price_decimal=american_to_decimal(price),
        open_price=None,
        latest_price=price,
        movement_cents=0.0,
        rationale="baseline: favorite ML at latest consensus",
    )


def dog_ml_pick(ctx: StrategyContext) -> Pick | Pass | None:
    """Backtest-only baseline: the higher-ML side, every game. Together with
    fav_ml it brackets the vig band in CALIBRATION.md. Not run live."""
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    if g.game_type not in ctx.cfg["season"]["game_types"]:
        return Pass(g.game_pk, matchup, "B_DOG", f"game_type={g.game_type}")
    if g.status != "Preview":
        return Pass(g.game_pk, matchup, "B_DOG", f"status={g.status}")
    if ctx.odds_event_id is None or ctx.prices is None:
        return Pass(g.game_pk, matchup, "B_DOG", "no matched odds event")
    home_ml, away_ml = ctx.prices.home_ml_latest, ctx.prices.away_ml_latest
    if home_ml is None or away_ml is None:
        return Pass(g.game_pk, matchup, "B_DOG", "incomplete moneyline")

    home_is_fav = home_ml <= away_ml
    selection, price = (
        (g.away_team, away_ml) if home_is_fav else (g.home_team, home_ml)
    )
    start_et = to_et(g.start_utc)
    return Pick(
        game_pk=g.game_pk,
        odds_event_id=ctx.odds_event_id,
        game_date_et=g.game_date_et,
        matchup=matchup,
        start_time_et=start_et.strftime("%Y-%m-%d %H:%M"),
        day_type=day_type(start_et.date(), ctx.cfg),
        slot_type=slot_type(g.start_utc, ctx.cfg),
        rule_id="B_DOG",
        market="ml",
        selection=selection,
        line=None,
        price_american=price,
        price_decimal=american_to_decimal(price),
        open_price=None,
        latest_price=price,
        movement_cents=0.0,
        rationale="baseline: underdog ML at latest consensus",
    )


def engines() -> dict[str, GenerateFn]:
    """Engine name -> callable. Splits engines register here in the PR that
    ships strategy/splits_signal.py; a strategy YAML naming an unregistered
    engine is a hard config error."""
    registry: dict[str, GenerateFn] = {
        "pv_rules": _pv_rules,
        "fav_ml": fav_ml_pick,
        "dog_ml": dog_ml_pick,
    }
    try:
        from .splits_signal import fade_public_pick, sharp_split_pick

        registry["sharp_split"] = sharp_split_pick
        registry["fade_public"] = fade_public_pick
    except ImportError:
        pass
    return registry


#: Engines replayable over the historical archives. Splits engines are NOT
#: backtestable — no historical splits exist — and the backtest refuses them
#: loudly rather than silently emitting nothing.
BACKTESTABLE_ENGINES = {"pv_rules", "fav_ml", "dog_ml"}
