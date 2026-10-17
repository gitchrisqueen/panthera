"""Direct tests for `strategy/slate.py::evaluate_slate`.

This module decides every live pick, and before this file nothing imported it
from `tests/` — it was covered only incidentally through the pipeline tests,
and `scripts/proof_slate_identity.py` is a one-shot artifact CI never runs.
Each skip branch and the budget truncation are exercised here instead.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.strategy.rules import Pass, Pick
from panthera_mvp.strategy.slate import evaluate_slate

ET_DATE = "2026-08-03"  # Monday


def _game(pk: int, hour_utc: int = 23) -> GameInfo:
    return GameInfo(
        game_pk=pk,
        game_date_et=ET_DATE,
        game_type="R",
        status="Preview",
        detailed_state="Scheduled",
        start_utc=datetime(2026, 8, 3, hour_utc, 5, tzinfo=UTC),
        doubleheader="N",
        game_number=1,
        home_team_id=111,
        home_team="Boston Red Sox",
        away_team_id=147,
        away_team="New York Yankees",
    )


def _always_picks(ctx):
    """Engine stub: one ml Pick per game, so the loop's own filtering is the
    only thing that can reduce the output."""
    g = ctx.game
    return Pick(
        game_pk=g.game_pk,
        odds_event_id="e",
        game_date_et=g.game_date_et,
        matchup=f"{g.away_team} @ {g.home_team}",
        start_time_et="2026-08-03 19:05",
        day_type="P",
        slot_type=None,
        rule_id="R3",
        market="ml",
        selection=g.home_team,
        line=None,
        price_american=-110,
        price_decimal=1.9091,
        open_price=-110,
        latest_price=-110,
        movement_cents=0.0,
        rationale="stub",
    )


@pytest.fixture
def scfg(cfg):
    """The base config plus the `strategy` block `evaluate_slate` reads to
    decide whether the orig_rules-only slot map and totals apply. A
    non-orig_rules engine is the common path."""
    out = dict(cfg)
    out["strategy"] = {"id": "stub", "engine": "pv_rules"}
    return out


def _run(strategy_cfg, games, **kw):
    defaults = dict(
        engine=_always_picks,
        scfg=strategy_cfg,
        games=games,
        # No matched event: price extraction is skipped entirely, so these
        # tests isolate the loop's own filtering from odds parsing.
        events_by_pk={},
        lines_today=pd.DataFrame(),
        season_ctx=None,
        snap_label="open",
        window=(23, 59),  # (hour, minute) of the latest ET start to consider
        date_et=ET_DATE,
        as_of_et=None,
        already_picked_pks=set(),
        budget=None,
        splits_lookup=None,
    )
    defaults.update(kw)
    return evaluate_slate(**defaults)


def test_uncapped_budget_takes_the_whole_slate(scfg):
    res = _run(scfg, [_game(1), _game(2), _game(3)])
    assert len(res.picks) == 3
    assert not any(res.skipped.values())


def test_budget_keeps_the_first_games_in_the_order_given(scfg):
    """The cap drops the LAST games, not random ones.

    `evaluate_slate` does not sort: its docstring says the earliest-start
    bias is preserved because "games arrive in schedule order", which makes
    the ordering the caller's contract. Pinned here in the documented shape.
    """
    games = [_game(1, hour_utc=17), _game(2, hour_utc=20), _game(3, hour_utc=23)]
    res = _run(scfg, games, budget=2)
    assert [p.game_pk for p in res.picks] == [1, 2]


def test_the_cap_follows_input_order_not_start_time(scfg):
    """The other half of that contract, and the reason it is worth stating:
    hand the loop an unsorted slate and the earliest-start bias is gone. A
    caller that stops passing schedule order silently changes which games a
    capped day bets, with nothing to catch it."""
    games = [_game(3, hour_utc=23), _game(1, hour_utc=17), _game(2, hour_utc=20)]
    res = _run(scfg, games, budget=2)
    assert [p.game_pk for p in res.picks] == [3, 1]


def test_budget_zero_picks_nothing(scfg):
    """The live second-run-of-a-capped-day shape: the ledger already holds the
    day's maximum, so the remaining budget is 0 rather than None."""
    res = _run(scfg, [_game(1), _game(2)], budget=0)
    assert res.picks == []


def test_already_picked_game_is_skipped(scfg):
    res = _run(scfg, [_game(1), _game(2)], already_picked_pks={1})
    assert [p.game_pk for p in res.picks] == [2]
    assert res.skipped["already_picked"] == 1


def test_started_game_is_skipped_when_as_of_is_set(scfg):
    """A real run must never pick a game already under way; a dry run passes
    as_of_et=None and evaluates the whole slate."""
    as_of = datetime(2026, 8, 3, 21, 0, tzinfo=UTC)
    started, upcoming = _game(1, hour_utc=17), _game(2, hour_utc=23)

    res = _run(scfg, [started, upcoming], as_of_et=as_of)
    assert [p.game_pk for p in res.picks] == [2]
    assert res.skipped["started"] == 1

    dry = _run(scfg, [started, upcoming], as_of_et=None)
    assert len(dry.picks) == 2
    assert dry.skipped["started"] == 0


def test_game_after_the_window_is_skipped(scfg):
    """The morning run stops at 16:00 ET; a 19:05 ET start belongs to pregame."""
    res = _run(scfg, [_game(1, hour_utc=23)], window=(16, 0))
    assert res.picks == []
    assert res.skipped["after_window"] == 1


def test_a_passing_engine_yields_passes_not_skips(scfg):
    """A Pass is the engine's judgement and must not be counted as a skip —
    doctor H01 reads the difference."""

    def _always_passes(ctx):
        return Pass(ctx.game.game_pk, "m", "R0", "nope")

    res = _run(scfg, [_game(1)], engine=_always_passes)
    assert res.picks == []
    assert len(res.passes) == 1
    assert not any(res.skipped.values())
