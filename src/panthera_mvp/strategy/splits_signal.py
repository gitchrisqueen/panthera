"""Lumify splits engines: sharp_split (follow the money) and fade_public
(fade the tickets).

Splits are an INPUT here — the deliberate, documented exception to the
"observational only" rule, which continues to hold for the P/V rules engine.
Prices are never read from the splits table (it stores only bets_pct /
handle_pct percentages); the bet is priced at the latest lines.csv consensus
already carried by StrategyContext.prices.

Event selection: splits.csv can carry two Lumify events for one game
(duplicate event records, doubleheaders), so rows are selected by matching
the event's start time against the game's scheduled start, then by snapshot
label preference, then by latest captured_at. Engines degrade to a Pass —
never raise — on any missing or stale input.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..timeutil import now_utc, parse_utc, to_et
from .daytype import day_type, slot_type
from .rules import Pass, Pick, american_to_decimal

#: Snapshot labels in freshness order for pick generation. Fixed
#: pipeline-wide (not per-strategy) so every splits engine reads the same
#: snapshot for a given run.
LABELS_PREFERENCE = ["pregame", "morning", "manual"]

#: Max clock skew between a Lumify event's starts_at and the MLB scheduled
#: start for them to count as the same game.
START_MATCH_TOLERANCE_MIN = 45


@dataclass
class GameSplits:
    lumify_event_id: int
    snapshot_label: str
    captured_at: str | None
    ml_home_bets: float | None
    ml_home_handle: float | None
    ml_away_bets: float | None
    ml_away_handle: float | None


def extract_game_splits(
    splits_df: pd.DataFrame,
    game_pk: int,
    game_start_utc,
) -> GameSplits | None:
    """Select one event's moneyline splits for a game.

    Keyed on (game_pk, start-time match) — never date+teams alone: 28 of the
    first 190 (date, game_pk) pairs carried two contradictory events before
    the UTC-date fix, and doubleheaders share teams+date legitimately.
    """
    if splits_df is None or splits_df.empty:
        return None
    rows = splits_df[splits_df["game_pk"] == game_pk]
    if rows.empty:
        return None

    def _start_matches(raw) -> bool:
        try:
            delta = abs((parse_utc(str(raw)) - game_start_utc).total_seconds())
        except (ValueError, TypeError):
            return False
        return delta <= START_MATCH_TOLERANCE_MIN * 60

    rows = rows[rows["starts_at_utc"].map(_start_matches)]
    if rows.empty:
        return None

    for label in LABELS_PREFERENCE:
        labeled = rows[rows["snapshot_label"] == label]
        if labeled.empty:
            continue
        # Duplicate Lumify events for one game: keep the latest capture.
        latest_capture = labeled["captured_at"].astype(str).max()
        labeled = labeled[labeled["captured_at"].astype(str) == latest_capture]
        ev_id = labeled.iloc[0]["lumify_event_id"]
        labeled = labeled[labeled["lumify_event_id"] == ev_id]

        def _metric(name: str, frame: pd.DataFrame = labeled) -> float | None:
            sel = frame[frame["metric"] == name]
            return float(sel.iloc[0]["value"]) if not sel.empty else None

        return GameSplits(
            lumify_event_id=int(ev_id),
            snapshot_label=label,
            captured_at=(
                str(labeled.iloc[0]["captured_at"])
                if pd.notna(labeled.iloc[0]["captured_at"])
                else None
            ),
            ml_home_bets=_metric("moneyline.home.bets_pct"),
            ml_home_handle=_metric("moneyline.home.handle_pct"),
            ml_away_bets=_metric("moneyline.away.bets_pct"),
            ml_away_handle=_metric("moneyline.away.handle_pct"),
        )
    return None


def make_splits_lookup(date_et: str):
    """One splits.csv read per picks run; returns game -> GameSplits | None."""
    from ..clients.lumify import load_splits

    splits = load_splits()
    if not splits.empty:
        splits = splits[splits["game_date_et"] == date_et]

    def lookup(game) -> GameSplits | None:
        return extract_game_splits(splits, game.game_pk, game.start_utc)

    return lookup


def _base_eligibility(ctx, rule_id: str) -> Pass | None:
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    if g.game_type not in ctx.cfg["season"]["game_types"]:
        return Pass(g.game_pk, matchup, rule_id, f"game_type={g.game_type}")
    if g.status != "Preview":
        return Pass(g.game_pk, matchup, rule_id, f"status={g.status}")
    return None


def _splits_guards(ctx, scfg: dict, rule_id: str) -> Pass | None:
    """Common pass conditions: no splits, stale splits."""
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    if ctx.splits is None:
        return Pass(g.game_pk, matchup, rule_id, "no-splits: none captured for game")
    max_stale_h = float(scfg.get("max_staleness_hours", 12))
    if ctx.splits.captured_at:
        try:
            age_h = (now_utc() - parse_utc(ctx.splits.captured_at)).total_seconds() / 3600
        except (ValueError, TypeError):
            age_h = None
        if age_h is not None and age_h > max_stale_h:
            return Pass(
                g.game_pk, matchup, rule_id, f"stale: splits captured {age_h:.1f}h ago"
            )
    return None


def _priced_pick(ctx, scfg, rule_id: str, selection: str, rationale: str) -> Pick | Pass:
    """Price the selection at the latest lines.csv consensus ML."""
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    if ctx.prices is None:
        return Pass(g.game_pk, matchup, rule_id, "no-price: no matched odds event")
    price = (
        ctx.prices.home_ml_latest
        if selection == g.home_team
        else ctx.prices.away_ml_latest
    )
    if price is None:
        return Pass(g.game_pk, matchup, rule_id, "no-price: moneyline unavailable")
    if abs(price) > float(scfg.get("max_abs_price", 300)):
        return Pass(g.game_pk, matchup, rule_id, f"too-heavy: {price:+.0f}")
    start_et = to_et(g.start_utc)
    return Pick(
        game_pk=g.game_pk,
        odds_event_id=ctx.odds_event_id,
        game_date_et=g.game_date_et,
        matchup=matchup,
        start_time_et=start_et.strftime("%Y-%m-%d %H:%M"),
        day_type=day_type(start_et.date(), ctx.cfg),
        slot_type=slot_type(g.start_utc, ctx.cfg),
        rule_id=rule_id,
        market="ml",
        selection=selection,
        line=None,
        price_american=price,
        price_decimal=american_to_decimal(price),
        open_price=None,
        latest_price=price,
        movement_cents=0.0,
        rationale=rationale,
    )


def sharp_split_pick(ctx) -> Pick | Pass | None:
    """Back the ML side whose money share exceeds its ticket share by the
    configured margin — measured sharp money (rule_id SS_ml)."""
    scfg = ctx.cfg.get("splits_signal", {})
    ineligible = _base_eligibility(ctx, "SS_ml")
    if ineligible:
        return ineligible
    guard = _splits_guards(ctx, scfg, "SS_ml")
    if guard:
        return guard
    s = ctx.splits
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    min_gap = float(scfg.get("min_handle_minus_bets", 15))
    min_handle = float(scfg.get("min_handle_pct", 50))

    candidates = []
    if s.ml_home_bets is not None and s.ml_home_handle is not None:
        candidates.append((s.ml_home_handle - s.ml_home_bets, s.ml_home_handle, g.home_team))
    if s.ml_away_bets is not None and s.ml_away_handle is not None:
        candidates.append((s.ml_away_handle - s.ml_away_bets, s.ml_away_handle, g.away_team))
    if not candidates:
        return Pass(g.game_pk, matchup, "SS_ml", "no-splits: moneyline metrics missing")
    gap, handle, side = max(candidates)
    if gap < min_gap or handle < min_handle:
        return Pass(
            g.game_pk,
            matchup,
            "SS_ml",
            f"no-divergence: best gap {gap:+.0f} (need >={min_gap:.0f} and "
            f"handle >={min_handle:.0f})",
        )
    return _priced_pick(
        ctx,
        scfg,
        "SS_ml",
        side,
        f"sharp split: {side} handle {handle:.0f}% vs tickets "
        f"{handle - gap:.0f}% ({ctx.splits.snapshot_label} capture)",
    )


def fade_public_pick(ctx) -> Pick | Pass | None:
    """Bet against the ML side holding >= min_tickets_pct of tickets — the
    contrarian baseline hypothesis (rule_id FP_ml)."""
    scfg = ctx.cfg.get("splits_signal", {})
    ineligible = _base_eligibility(ctx, "FP_ml")
    if ineligible:
        return ineligible
    guard = _splits_guards(ctx, scfg, "FP_ml")
    if guard:
        return guard
    s = ctx.splits
    g = ctx.game
    matchup = f"{g.away_team} @ {g.home_team}"
    min_tickets = float(scfg.get("min_tickets_pct", 65))

    sides = []
    if s.ml_home_bets is not None:
        sides.append((s.ml_home_bets, g.home_team, g.away_team))
    if s.ml_away_bets is not None:
        sides.append((s.ml_away_bets, g.away_team, g.home_team))
    if not sides:
        return Pass(g.game_pk, matchup, "FP_ml", "no-splits: moneyline metrics missing")
    tickets, public_side, other_side = max(sides)
    if tickets < min_tickets:
        return Pass(
            g.game_pk,
            matchup,
            "FP_ml",
            f"no-divergence: max tickets {tickets:.0f}% < {min_tickets:.0f}%",
        )
    return _priced_pick(
        ctx,
        scfg,
        "FP_ml",
        other_side,
        f"fade public: {public_side} holds {tickets:.0f}% of tickets "
        f"({ctx.splits.snapshot_label} capture)",
    )
