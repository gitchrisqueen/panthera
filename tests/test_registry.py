"""Strategy config loading + registry validation."""

import pytest

from panthera_mvp.config import (
    StrategyConfigError,
    config_hash,
    load_config,
    load_strategy_configs,
)
from panthera_mvp.strategy.registry import engines

VALID = """\
strategy:
  id: {sid}
  engine: {engine}
  enabled: true
  kind: baseline
  scope: [live]
  registered_at: "2026-08-17"
  hash_lineage: []
verdict: null
screen: {{checkpoints: []}}
bet_limits: {{max_picks_per_day: 3, one_pick_per_game: true}}
staking: {{flat_stake: 100}}
"""


def test_engines_registered():
    known = engines()
    assert {"pv_rules", "fav_ml", "dog_ml"} <= set(known)


def test_load_and_merge_order(tmp_root):
    """Base < strategy file; the calibrated overlay is never merged for
    registry strategies."""
    (tmp_root / "config" / "strategy.calibrated.yaml").write_text(
        "movement: {min_move_cents: 99}\n"
    )
    sdir = tmp_root / "config" / "strategies"
    (sdir / "pv_v2.yaml").write_text(
        (sdir / "pv_v2.yaml").read_text() + "movement: {min_move_cents: 7}\n"
    )
    cfgs = load_strategy_configs()
    # Strategy file wins over base; calibrated (99) is ignored entirely.
    assert cfgs["pv_v2"]["movement"]["min_move_cents"] == 7
    # The pipeline config still honors the calibrated overlay.
    assert load_config()["movement"]["min_move_cents"] == 99


def test_missing_dir_hard_errors(tmp_root):
    import shutil

    shutil.rmtree(tmp_root / "config" / "strategies")
    with pytest.raises(StrategyConfigError, match="no strategy configs"):
        load_strategy_configs()


def test_id_must_match_filename(tmp_root):
    sdir = tmp_root / "config" / "strategies"
    (sdir / "wrong.yaml").write_text(VALID.format(sid="other", engine="fav_ml"))
    with pytest.raises(StrategyConfigError, match="filename stem"):
        load_strategy_configs()


def test_unknown_engine_rejected(tmp_root):
    sdir = tmp_root / "config" / "strategies"
    (sdir / "mystery.yaml").write_text(VALID.format(sid="mystery", engine="nope"))
    with pytest.raises(StrategyConfigError, match="unknown engine"):
        load_strategy_configs(known_engines=set(engines()))


def test_bet_limits_must_be_explicit(tmp_root):
    sdir = tmp_root / "config" / "strategies"
    text = VALID.format(sid="nocap", engine="fav_ml").replace(
        "bet_limits: {max_picks_per_day: 3, one_pick_per_game: true}",
        "bet_limits: {one_pick_per_game: true}",
    )
    (sdir / "nocap.yaml").write_text(text)
    with pytest.raises(StrategyConfigError, match="max_picks_per_day"):
        load_strategy_configs()


def test_verdict_string_none_rejected(tmp_root):
    """YAML plain `none` parses to the string 'none', not null — a truthy
    value that would silently pass for criteria."""
    sdir = tmp_root / "config" / "strategies"
    text = VALID.format(sid="strnone", engine="fav_ml").replace(
        "verdict: null", "verdict: none"
    )
    (sdir / "strnone.yaml").write_text(text)
    with pytest.raises(StrategyConfigError, match="verdict"):
        load_strategy_configs()


def test_scope_validated(tmp_root):
    sdir = tmp_root / "config" / "strategies"
    text = VALID.format(sid="badscope", engine="fav_ml").replace(
        "scope: [live]", "scope: [production]"
    )
    (sdir / "badscope.yaml").write_text(text)
    with pytest.raises(StrategyConfigError, match="scope"):
        load_strategy_configs()


def test_hash_excludes_metadata_and_criteria(tmp_root):
    cfgs = load_strategy_configs()
    pv = cfgs["pv_v2"]
    h = config_hash(pv)
    import copy

    changed = copy.deepcopy(pv)
    changed["strategy"]["hypothesis"] = "totally different words"
    changed["strategy"]["registered_at"] = "2027-01-01"
    changed["screen"] = {"checkpoints": [50]}
    changed["meta"] = {"calibrated_at": "2099-01-01T00:00:00Z"}
    assert config_hash(changed) == h

    behavioral = copy.deepcopy(pv)
    behavioral["movement"]["min_move_cents"] = 42
    assert config_hash(behavioral) != h
