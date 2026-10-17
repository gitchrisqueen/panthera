"""One day's slate through one strategy's engine — the single evaluation loop.

`pipeline._strategy_picks` and `replay`'s inner loop were the same algorithm
written twice, and they had already drifted four ways: replay applied no
`bet_limits` cap, ignored the start-time window, measured dossier H2H prices
at a different snapshot label than the prices it priced picks at, and wrote a
hardcoded stake. Shadow picks were therefore systematically more numerous and
subtly differently priced than the live picks they were meant to stand in for.

So there is one loop, here. **`pipeline._strategy_picks` is its only caller
today** — `replay.py` still runs its own copy and still has all four of those
divergences; PR 3b converts it. Until then shadow picks remain more numerous
and differently priced than live ones, and this module's existence has not
yet fixed that. What stays with the
CALLER is everything environment-shaped: which day, which snapshot label, how
much budget is left, which games it has already picked, and what "now" is.
This module decides nothing about those — it is pure, which is what will let the
replay pass a simulated `as_of` and get the live algorithm exactly once it is
converted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from ..clients import mlb
from ..timeutil import ET, now_utc, utc_iso
from .daytype import day_type
from .dossier import Dossier, SeasonContext
from .movement import extract_game_prices, extract_totals_prices
from .registry import StrategyContext
from .rules import Pass, Pick
from .slots import assign_slots


@dataclass
class SlateResult:
    picks: list[Pick]
    passes: list[Pass]
    #: Games skipped before the engine saw them, by reason. Not findings —
    #: `started`/`after_window` are the normal shape of a morning run — but a
    #: replay that silently skipped a whole slate used to be invisible.
    skipped: dict[str, int]


def build_dossier(g: mlb.GameInfo, ctx: SeasonContext | None, cfg: dict) -> Dossier:
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


def pick_row(p: Pick, strategy_id: str, scfg: dict, chash: str) -> dict:
    """Build a ledger row from a Pick. The single authoritative pick_id
    stamping site: whatever id the engine set is overwritten with the
    strategy-prefixed format.

    Lives here, not in pipeline, because the replay writes the same 28 columns
    to the shadow ledger. It had its own copy, and a `PICKS_COLUMNS` extension
    would have reached one and missed the other.
    """
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


def slot_map_for(scfg: dict, games: list, date_et: str) -> dict[int, str]:
    """orig_rules' slot algorithm is a whole-day computation (strategy/
    slots.py), not per-game — run it once per slate. Other engines compute
    their own slot label internally and ignore this."""
    if scfg["strategy"]["engine"] != "orig_rules" or not games:
        return {}
    dtype = day_type(date.fromisoformat(date_et), scfg)
    return assign_slots(
        [(g.game_pk, g.start_utc) for g in games],
        dtype,
        int(scfg["hybrid_boundary_hour_et"]),
    )


def evaluate_slate(
    *,
    engine,
    scfg: dict,
    games: list,
    events_by_pk: dict,
    lines_today: pd.DataFrame,
    season_ctx: SeasonContext | None,
    snap_label: str | None,
    window: tuple[int, int],
    date_et: str,
    as_of_et: datetime | None,
    already_picked_pks: set[int],
    budget: int | None,
    splits_lookup=None,
) -> SlateResult:
    """Run one strategy's engine over one day's games.

    `as_of_et` is the run's own clock, injected rather than read: `None` means
    "evaluate the whole slate regardless of start time" (a dry run, or a
    replay pass that is deliberately not simulating a cutoff), and a datetime
    means games already under way are skipped as a live run would skip them.
    Passing it in is what lets the replay reproduce the morning and pregame
    runs instead of grading a whole day at once.

    `engine` is resolved by the CALLER, not looked up here: the registry is a
    global, and a function that reaches into it is neither pure nor testable
    by substitution — `tests/test_pipeline_multi.py::test_engine_error_is_isolated`
    swaps in a deliberately broken engine and must still reach this loop.

    `budget` and `already_picked_pks` come from the caller because the live
    pipeline counts them in `picks.csv` and the replay in `shadow_picks.csv`.
    `budget` of `None` is uncapped (the explicit form); 0 means no room left.

    Earliest-start-first truncation bias is preserved: games arrive in
    schedule order, so when the cap binds it drops the latest games, not
    random ones.
    """
    slot_map = slot_map_for(scfg, games, date_et)
    end_h, end_m = window
    one_per_game = scfg["bet_limits"]["one_pick_per_game"]

    picks: list[Pick] = []
    passes: list[Pass] = []
    skipped = {"after_window": 0, "started": 0, "already_picked": 0}

    for g in games:
        start_et = g.start_utc.astimezone(ET)
        if (start_et.hour, start_et.minute) > (end_h, end_m):
            skipped["after_window"] += 1
            continue
        if as_of_et is not None and start_et <= as_of_et:
            skipped["started"] += 1
            continue
        if one_per_game and g.game_pk in already_picked_pks:
            skipped["already_picked"] += 1
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
            dossier=build_dossier(g, season_ctx, scfg),
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
    return SlateResult(picks=picks, passes=passes, skipped=skipped)
