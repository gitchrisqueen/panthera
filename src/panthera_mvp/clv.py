"""Closing-line value: did the pick beat the last pre-start price?

Honest scope (see docs/mvp-design.md): the "close" here is the last snapshot
taken at or before first pitch — normally the 18:20 ET `close` label, a
~75-minute window after the pregame picks run, from the same consensus feed
that priced the bet. CLV is therefore a directional price-capture
cross-check, NOT an independent test of edge. A pick's CLV is null (never a
fabricated zero) when no snapshot exists strictly between its creation and
its start — e.g. every pick settled before the close label existed, and
early-afternoon starts.

`clv_cents = american_cost(close) - american_cost(price_american)`:
positive = the market moved against the pick's side after we bet it (we got
the cheaper price — beat the close).
"""

from __future__ import annotations

import pandas as pd

from . import store
from .strategy.movement import american_cost, consensus_price, consensus_rl_price
from .timeutil import parse_utc


def _start_utc_by_pk(games: pd.DataFrame) -> dict:
    if games.empty:
        return {}
    return games.set_index("game_pk")["start_time_utc"].to_dict()


def fill_clv() -> int:
    """Fill close_price/clv_cents for picks that lack them and have a
    qualifying snapshot. Fills nulls only — idempotent, never rewrites."""
    picks = store.load_picks()
    if picks.empty:
        return 0
    todo = picks[picks["close_price"].isna()]
    if todo.empty:
        return 0
    lines = store.load_lines()
    if lines.empty:
        return 0
    starts = _start_utc_by_pk(store.load_games())

    updates = []
    for _, p in todo.iterrows():
        start_raw = starts.get(p["game_pk"])
        if not start_raw or pd.isna(start_raw):
            continue
        try:
            start_ts = parse_utc(str(start_raw))
            created_ts = parse_utc(str(p["created_ts_utc"]))
        except (ValueError, TypeError):
            continue
        ev = lines[lines["odds_event_id"] == p["odds_event_id"]]
        if ev.empty:
            continue
        snaps = ev.drop_duplicates("snapshot_label")[["snapshot_label", "snapshot_ts_utc"]]
        eligible = []
        for _, s in snaps.iterrows():
            try:
                ts = parse_utc(str(s["snapshot_ts_utc"]))
            except (ValueError, TypeError):
                continue
            # Strictly after creation: the snapshot that priced the pick is
            # not a close (it would make CLV structurally zero).
            if created_ts < ts <= start_ts:
                eligible.append((ts, s["snapshot_label"]))
        if not eligible:
            continue
        _, close_label = max(eligible)
        if p["market"] == "rl":
            close = consensus_rl_price(
                lines, p["odds_event_id"], p["selection"], close_label, float(p["line"])
            )
        else:
            close = consensus_price(
                lines, p["odds_event_id"], "h2h", p["selection"], close_label
            )
        if close is None:
            continue
        clv = round(
            american_cost(float(close)) - american_cost(float(p["price_american"])), 1
        )
        updates.append(
            {"pick_id": p["pick_id"], "close_price": float(close), "clv_cents": clv}
        )
    if not updates:
        return 0
    return store.fill_clv(pd.DataFrame(updates))
