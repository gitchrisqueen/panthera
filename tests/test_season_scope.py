"""Every registered engine gates on game type the same way.

The 2026-09-27 outage was one whitelist read from config, but the reason it
was invisible is that the read was DUPLICATED: five engines consulted
`cfg["season"]["game_types"]` while pipeline.py hardcoded `== "R"`. Fixing
one and missing the other produces a subtler version of the same bug — picks
made on games whose own prior results the dossier cannot see.

So the gate is asserted here across every engine in the registry, by
iterating `engines()` rather than listing them. A new engine that ships a
private whitelist fails this file on arrival.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.strategy.dossier import Dossier
from panthera_mvp.strategy.registry import StrategyContext, engines
from panthera_mvp.strategy.rules import GamePrices, Pass
from panthera_mvp.strategy.season import in_scope

COUNTING = ("R", "F", "D", "L", "W")
EXCLUDED = ("S", "E", "A", "I")


def _game(**kw) -> GameInfo:
    defaults = dict(
        game_pk=776001,
        game_date_et="2026-08-03",  # Monday
        game_type="R",
        status="Preview",
        detailed_state="Scheduled",
        start_utc=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),
        doubleheader="N",
        game_number=1,
        home_team_id=111,
        home_team="Boston Red Sox",
        away_team_id=147,
        away_team="New York Yankees",
    )
    defaults.update(kw)
    return GameInfo(**defaults)


def _prices() -> GamePrices:
    return GamePrices(
        home_ml_open=140,
        away_ml_open=-160,
        home_ml_latest=155,
        away_ml_latest=-180,
        home_rl_price=-125,
        away_rl_price=105,
    )


def _ctx(cfg, **kw) -> StrategyContext:
    return StrategyContext(
        game=_game(**kw),
        odds_event_id="e",
        prices=_prices(),
        dossier=Dossier(),
        cfg=cfg,
        slot_type="P1",
    )


def _is_game_type_pass(outcome) -> bool:
    return isinstance(outcome, Pass) and outcome.reason.startswith("excluded_game_type=")


@pytest.mark.parametrize("engine_name", sorted(engines()))
@pytest.mark.parametrize("game_type", EXCLUDED)
def test_every_engine_excludes_non_counting_game_types(engine_name, game_type, cfg):
    outcome = engines()[engine_name](_ctx(cfg, game_type=game_type))
    assert _is_game_type_pass(outcome), (
        f"{engine_name} did not gate gameType {game_type}: {outcome!r}"
    )
    assert outcome.reason == f"excluded_game_type={game_type}"


@pytest.mark.parametrize("engine_name", sorted(engines()))
@pytest.mark.parametrize("game_type", COUNTING)
def test_no_engine_gates_a_counting_game_type(engine_name, game_type, cfg):
    """Postseason types must get past the gate. Engines may still Pass for
    their own reasons (no splits, wrong day, unpriced) — what must never
    happen again is a Pass whose stated reason is the game type itself."""
    outcome = engines()[engine_name](_ctx(cfg, game_type=game_type))
    assert not _is_game_type_pass(outcome), (
        f"{engine_name} gated gameType {game_type} — the 2026-09-27 outage"
    )


@pytest.mark.parametrize("game_type", COUNTING + EXCLUDED)
def test_engines_agree_with_the_shared_helper(game_type, cfg):
    """No engine may disagree with `in_scope` about any code, in either
    direction — that divergence is what hid the original bug."""
    expected = in_scope(game_type, cfg)
    for engine_name, engine in engines().items():
        gated = _is_game_type_pass(engine(_ctx(cfg, game_type=game_type)))
        assert gated != expected, f"{engine_name} disagrees on {game_type}"


def _final(game_pk: int, game_type: str, home_id: int, away_id: int) -> dict:
    return {
        "gamePk": game_pk,
        "gameType": game_type,
        "gameDate": "2026-10-10T23:05:00Z",
        "doubleHeader": "N",
        "gameNumber": 1,
        "status": {"abstractGameState": "Final", "detailedState": "Final"},
        "teams": {
            "away": {"team": {"id": away_id, "name": "Away"}, "score": 2},
            "home": {"team": {"id": home_id, "name": "Home"}, "score": 5},
        },
    }


def test_season_context_scope_matches_the_engine_gate(tmp_root, monkeypatch, tmp_path):
    """`_build_season_context` fed the dossier from a HARDCODED `== "R"` until
    2026-10-15, while the engines read config. Both now call `in_scope`, so a
    postseason final reaches the dossier and an exhibition still does not.

    This matters beyond tidiness: in a postseason series the previous
    head-to-head meeting is yesterday's game, and that price is orig_rules'
    primary signal.
    """
    import json

    from panthera_mvp.config import load_config
    from panthera_mvp.pipeline import _build_season_context

    payload = {
        "dates": [
            {
                "date": "2026-10-10",
                "games": [
                    _final(1, "L", home_id=111, away_id=147),  # postseason: counts
                    _final(2, "S", home_id=121, away_id=133),  # spring: excluded
                ]
            }
        ]
    }
    fixture = tmp_path / "finals.json"
    fixture.write_text(json.dumps(payload))
    monkeypatch.setenv("PANTHERA_MLB_FIXTURE", str(fixture))

    ctx = _build_season_context("2026-10-11", load_config())

    assert ctx is not None
    assert len(ctx._results[111]) == 1, "postseason final did not reach the dossier"
    assert len(ctx._results[147]) == 1
    assert not ctx._results[121], "spring-training final leaked into the dossier"
    assert not ctx._results[133]
