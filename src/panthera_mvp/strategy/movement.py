"""Line-movement signals (doc §1).

The doc defines movement on a side's American price:
  - shortening (paying less: -160 -> -180, or +120 -> +105) = PUBLIC money on
    that side;
  - drifting (paying more: -180 -> -160, or +105 -> +120) = VEGAS/sharp
    positioning against that side.

We measure movement on the *favorite's* moneyline consensus (median across
bookmakers) between the earliest and latest snapshots of the day.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class MovementSignal:
    direction: str  # "public" | "vegas" | "neutral"
    open_price: float | None
    latest_price: float | None
    delta_cents: float  # signed change in "cost", positive = shortened


def american_cost(price: float) -> float:
    """Monotone 'expensiveness' scale for American odds.

    Maps price to the cents-cost of the side so deltas compare across the
    +/- boundary: -180 is more expensive than -160, +105 more than +120.
    cost(-160)=160, cost(+120)=-120: higher = more expensive.
    """
    return -price if price > 0 else abs(price)


def consensus_price(
    lines: pd.DataFrame,
    odds_event_id: str,
    market: str,
    outcome: str,
    snapshot_label: str,
) -> float | None:
    sel = lines[
        (lines["odds_event_id"] == odds_event_id)
        & (lines["market"] == market)
        & (lines["outcome"] == outcome)
        & (lines["snapshot_label"] == snapshot_label)
    ]
    if sel.empty:
        return None
    return float(sel["price_american"].median())


def extract_game_prices(lines: pd.DataFrame, odds_event_id: str, home_team: str, away_team: str):
    """Build a GamePrices bundle from the lines table for one event.

    `open` = earliest snapshot label present today, `latest` = most recent.
    Run-line prices come from the spreads market at the standard +/-1.5.
    """
    from .rules import GamePrices  # local import to avoid a cycle

    sel = lines[lines["odds_event_id"] == odds_event_id]
    if sel.empty:
        return None
    ordered = sel.sort_values("snapshot_ts_utc")["snapshot_label"].unique()
    open_label, latest_label = ordered[0], ordered[-1]

    def _rl(team: str) -> float | None:
        rows = sel[
            (sel["market"] == "spreads")
            & (sel["outcome"] == team)
            & (sel["snapshot_label"] == latest_label)
            & (sel["point"].abs() == 1.5)
        ]
        return float(rows["price_american"].median()) if not rows.empty else None

    return GamePrices(
        home_ml_open=consensus_price(lines, odds_event_id, "h2h", home_team, open_label),
        away_ml_open=consensus_price(lines, odds_event_id, "h2h", away_team, open_label),
        home_ml_latest=consensus_price(lines, odds_event_id, "h2h", home_team, latest_label),
        away_ml_latest=consensus_price(lines, odds_event_id, "h2h", away_team, latest_label),
        home_rl_price=_rl(home_team),
        away_rl_price=_rl(away_team),
    )


def movement_signal(
    open_price: float | None, latest_price: float | None, cfg: dict
) -> MovementSignal:
    if open_price is None or latest_price is None or open_price == latest_price:
        return MovementSignal("neutral", open_price, latest_price, 0.0)
    delta = american_cost(latest_price) - american_cost(open_price)
    if abs(delta) < float(cfg["movement"]["min_move_cents"]):
        return MovementSignal("neutral", open_price, latest_price, delta)
    direction = "public" if delta > 0 else "vegas"
    return MovementSignal(direction, open_price, latest_price, delta)
