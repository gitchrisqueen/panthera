"""Assertions against the REAL shipped config, not a fixture.

The 2026-09-27 outage was a wrong value in `config/strategy.yaml` — a
regular-season whitelist that excluded the whole postseason. Every engine
behaved exactly as written and the whole fixture-based suite stayed green for
14 slate days while the live pipeline produced 145 passes and zero picks.

A fixture suite cannot see a bad production value. This file reads the shipped
config, so the coupling to production config is the point. Keep that coupling
NARROW — scope and lineage invariants only, never thresholds or day maps,
which are expected to move under calibration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from panthera_mvp import paths
from panthera_mvp.config import (
    StrategyConfigError,
    config_hash,
    load_config,
    load_strategy_configs,
)
from panthera_mvp.strategy.registry import engines
from panthera_mvp.strategy.season import excluded_game_types, in_scope

#: MLB gameType codes for games that count. R regular season, then the
#: postseason ladder: F wild card, D division series, L LCS, W World Series.
COUNTING_GAME_TYPES = ("R", "F", "D", "L", "W")

#: Exhibitions. The source material (docs/sports_betting_process.md §6) asks
#: to exclude spring training; the others are the same kind of thing.
EXHIBITION_GAME_TYPES = ("S", "E", "A")


@pytest.fixture
def base_cfg() -> dict:
    # Base only — the calibrated overlay is written by `calibrate
    # --write-config` and is explicitly safe to delete, so scope must not
    # depend on it.
    return load_config(overrides=Path("/nonexistent"))


@pytest.mark.parametrize("game_type", COUNTING_GAME_TYPES)
def test_live_config_admits_every_counting_game_type(game_type, base_cfg):
    assert in_scope(game_type, base_cfg), (
        f"gameType {game_type} is excluded by the shipped config. If this is "
        "a postseason code, this is the 2026-09-27 outage happening again: "
        "every engine will Pass on every game and nothing will raise."
    )


@pytest.mark.parametrize("game_type", EXHIBITION_GAME_TYPES)
def test_live_config_excludes_exhibitions(game_type, base_cfg):
    assert not in_scope(game_type, base_cfg)


def test_unknown_game_type_defaults_to_in_scope(base_cfg):
    """The blacklist's whole point: a code nobody has heard of is playable, so
    a new MLB type code cannot silently empty the slate."""
    assert in_scope("ZZ_NEW_CODE", base_cfg)


def test_retired_whitelist_key_is_rejected():
    with pytest.raises(StrategyConfigError, match="retired"):
        excluded_game_types({"season": {"game_types": ["R"]}})


def test_missing_scope_key_is_rejected():
    with pytest.raises(StrategyConfigError, match="missing required key"):
        excluded_game_types({"season": {}})


@pytest.mark.parametrize(
    "path", sorted((paths.config_dir() / "strategies").glob("*.yaml")), ids=lambda p: p.stem
)
def test_no_strategy_reintroduces_the_whitelist(path):
    """A strategy YAML deep-merges over the base, so it could put the retired
    key back for itself alone — a per-strategy blackout nobody would spot."""
    raw = yaml.safe_load(path.read_text()) or {}
    assert "game_types" not in (raw.get("season") or {}), (
        f"{path.name} re-introduces the retired `season.game_types` whitelist"
    )


def test_strategies_agree_with_the_base_on_scope():
    """Scope is a pipeline-wide property: the SeasonContext is built once from
    the pipeline config and shared by every strategy (pipeline.cmd_picks), so
    a strategy that narrowed its own scope would be picking games its dossier
    was not built for."""
    base = excluded_game_types(load_config(overrides=Path("/nonexistent")))
    for sid, scfg in load_strategy_configs(known_engines=set(engines())).items():
        assert excluded_game_types(scfg) == base, f"{sid} diverges from base scope"


def test_every_live_strategy_hash_is_in_its_lineage():
    """A strategy whose current config_hash is absent from its own non-empty
    `hash_lineage` has its picks rendered as a separate report segment and its
    verdict countdown frozen. That is the half-finished state of a config
    change where the hash moved but the lineage was not amended.

    An EMPTY lineage is not that state — report.py reads `[]` as "pool every
    hash" — so it is skipped here rather than treated as drift.
    """
    stale = []
    for sid, scfg in load_strategy_configs(known_engines=set(engines())).items():
        meta = scfg["strategy"]
        if not (meta.get("enabled") and "live" in meta["scope"]):
            continue
        lineage = [str(h) for h in meta.get("hash_lineage") or []]
        if not lineage:
            continue
        current = config_hash(scfg)
        if current not in lineage:
            stale.append(f"{sid}: {current} not in {lineage}")
    assert not stale, (
        "config_hash moved without a hash_lineage amendment:\n  "
        + "\n  ".join(stale)
        + "\nRun `panthera-mvp hashes`. Extending a lineage requires "
        "tests/test_scope_fix_regression.py-style proof that the change is "
        "domain-extending; otherwise register a new strategy id."
    )
