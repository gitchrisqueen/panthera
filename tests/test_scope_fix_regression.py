"""Evidence that the 2026-10-15 postseason scope fix is domain-EXTENDING.

`src/panthera_mvp/CLAUDE.md` forbids extending a strategy's `hash_lineage`
across a behavioral change — new behavior means a new strategy id and fresh
counters. The scope fix moved every live strategy's `config_hash`, so pooling
the pre-fix and post-fix picks needs this file to be true:

    restricted to the games the OLD config admitted (game_type == "R"), the
    pre-fix and post-fix configs are the same decision function.

If that holds, no pick already in the ledger would have been different, the
pre-fix sample is not contaminated by pooling, and the lineage may be
extended. If it ever stops holding, the lineage appends in
config/strategies/*.yaml are no longer justified and those strategies must be
re-registered under new ids. This is the precondition, not a formality.

What the fix DOES change is the population: postseason games the day map was
never calibrated on. That is disclosed in BETTING_REPORT.md's regime caveat
and the per-strategy by-phase split, not hidden behind the hash.

The proof runs over the real captured regular-season history in `data/`, not
a fixture — the bug it guards against was a wrong value in a real config file.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil

import pandas as pd
import pytest

import panthera_mvp.strategy as strategy_pkg
from panthera_mvp import paths, store
from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.config import load_strategy_configs
from panthera_mvp.strategy import orig_rules, registry, rules, splits_signal
from panthera_mvp.strategy.daytype import day_type
from panthera_mvp.strategy.dossier import Dossier
from panthera_mvp.strategy.movement import extract_game_prices, extract_totals_prices
from panthera_mvp.strategy.registry import StrategyContext, engines
from panthera_mvp.strategy.slots import assign_slots
from panthera_mvp.timeutil import parse_utc

#: Every module that imported `in_scope` by name, so a monkeypatch reaches the
#: symbol the engine actually calls. A new gating module must be added here —
#: test_every_gating_module_is_covered enforces it.
GATING_MODULES = (rules, orig_rules, registry, splits_signal)

LIVE_STRATEGIES = ("pv_v3", "pv_orig", "sharp_split", "fade_public", "fav_ml")


def _legacy_in_scope(game_type: str, cfg: dict) -> bool:
    """The retired gate: `season.game_types: ["R"]`, a regular-season
    whitelist. Confined to this file on purpose — strategy/season.py raises on
    the legacy key so a stale config cannot reach production."""
    return game_type == "R"


def test_every_gating_module_is_covered():
    """A new engine that gates on game type must join GATING_MODULES, or the
    equivalence proof below would silently stop covering it."""
    gating = set()
    for info in pkgutil.iter_modules(strategy_pkg.__path__):
        module = importlib.import_module(f"panthera_mvp.strategy.{info.name}")
        if info.name != "season" and hasattr(module, "in_scope"):
            gating.add(module.__name__)
    assert gating == {m.__name__ for m in GATING_MODULES}


@pytest.fixture(scope="module")
def prepared_slate():
    """(game, event_id, prices, totals) for every captured REGULAR-SEASON game.

    Module-scoped because the odds extraction over the full lines history is
    the expensive part and is identical for every strategy. Postseason is
    excluded deliberately: it is precisely where the two configs are SUPPOSED
    to differ, so including it would test the opposite of the claim.
    """
    if not paths.games_csv().exists() or not paths.lines_csv().exists():
        pytest.skip("no captured history in this checkout")
    games, lines = store.load_games(), store.load_lines()
    games = games[games["game_type"] == "R"]
    if games.empty or lines.empty:
        pytest.skip("no captured regular-season history")

    lines = lines.dropna(subset=["game_pk"]).astype({"game_pk": int})
    by_day = dict(tuple(lines.groupby("game_date_et")))

    prepared: list[tuple[str, GameInfo, object, object, object]] = []
    for day in sorted(games["game_date_et"].unique()):
        lines_today = by_day.get(day)
        if lines_today is None or lines_today.empty:
            continue
        events = (
            lines_today.drop_duplicates("game_pk")
            .set_index("game_pk")["odds_event_id"]
            .to_dict()
        )
        for row in games[games["game_date_et"] == day].itertuples(index=False):
            game = GameInfo(
                game_pk=int(row.game_pk),
                game_date_et=str(row.game_date_et),
                game_type=str(row.game_type),
                status="Preview",
                detailed_state="Scheduled",
                start_utc=parse_utc(str(row.start_time_utc)),
                doubleheader=str(row.doubleheader) if pd.notna(row.doubleheader) else "N",
                game_number=int(row.game_number) if pd.notna(row.game_number) else 1,
                home_team_id=int(row.home_team_id),
                home_team=str(row.home_team),
                away_team_id=int(row.away_team_id),
                away_team=str(row.away_team),
            )
            event_id = events.get(game.game_pk)
            prices = (
                extract_game_prices(
                    lines_today, event_id, game.home_team, game.away_team
                )
                if event_id
                else None
            )
            totals = extract_totals_prices(lines_today, event_id) if event_id else None
            prepared.append((day, game, event_id, prices, totals))

    assert prepared, "the proof is vacuous if it prepared no games"
    return prepared


def _contexts(prepared, scfg):
    """One StrategyContext per prepared game. A fixed empty dossier and no
    splits: both gate variants then see byte-identical inputs, so any output
    difference is attributable to the gate alone — which is the only question
    this file asks."""
    boundary = int(scfg.get("hybrid_boundary_hour_et", 18))
    slot_maps: dict[str, dict[int, str | None]] = {}
    for day, game, *_ in prepared:
        slot_maps.setdefault(day, {})[game.game_pk] = game.start_utc
    for day, starts in list(slot_maps.items()):
        dtype = day_type(pd.Timestamp(day).date(), scfg)
        slot_maps[day] = assign_slots(list(starts.items()), dtype, boundary)

    return [
        StrategyContext(
            game=game,
            odds_event_id=event_id,
            prices=prices,
            totals=totals,
            dossier=Dossier(),
            splits=None,
            slot_type=slot_maps[day].get(game.game_pk),
            cfg=scfg,
        )
        for day, game, event_id, prices, totals in prepared
    ]


@pytest.mark.parametrize("strategy_id", LIVE_STRATEGIES)
def test_scope_fix_is_domain_extending_only(strategy_id, prepared_slate, monkeypatch):
    scfg = load_strategy_configs(known_engines=set(engines()))[strategy_id]
    engine = engines()[scfg["strategy"]["engine"]]
    contexts = _contexts(prepared_slate, scfg)

    current = [repr(engine(ctx)) for ctx in contexts]

    for module in GATING_MODULES:
        monkeypatch.setattr(module, "in_scope", _legacy_in_scope)
    legacy = [repr(engine(dataclasses.replace(ctx))) for ctx in contexts]

    assert legacy == current, (
        f"{strategy_id}: the scope fix changed a decision on a regular-season "
        "game. It is NOT domain-extending, so extending hash_lineage in "
        "config/strategies/ is no longer justified — register a new strategy id."
    )
