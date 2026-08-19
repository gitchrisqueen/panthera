import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def odds_events() -> list[dict]:
    with open(FIXTURES / "odds_snapshot.json") as fh:
        return json.load(fh)


@pytest.fixture
def mlb_schedule_payload() -> dict:
    with open(FIXTURES / "mlb_schedule.json") as fh:
        return json.load(fh)


@pytest.fixture
def espn_payload() -> dict:
    with open(FIXTURES / "espn_scoreboard.json") as fh:
        return json.load(fh)


MINIMAL_PV_V2 = """\
# Minimal pv_v2 for tests: no behavioral overrides, so the suite stays pinned
# to the base config (the real pv_v2.yaml inlines the calibrated parameters).
strategy:
  id: pv_v2
  engine: pv_rules
  enabled: true
  kind: incumbent
  scope: [live, backtest]
  registered_at: "2026-08-17"
  hash_lineage: [6f0d0924d4]
verdict: {min_graded: 100, supported_roi: 0.0, falsified_roi: -5.0}
screen: {checkpoints: [100, 200]}
bet_limits: {max_picks_per_day: 6, one_pick_per_game: true}
staking: {flat_stake: 100}
"""


@pytest.fixture
def tmp_root(tmp_path, monkeypatch) -> Path:
    """Point the datastore at an isolated tmp repo root with the real base
    config (never the calibrated overlay — tests are pinned to base) plus a
    minimal strategies dir so load_strategy_configs' missing-dir hard error
    doesn't fire in unrelated tests."""
    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / "config" / "strategy.yaml", tmp_path / "config" / "strategy.yaml")
    sdir = tmp_path / "config" / "strategies"
    sdir.mkdir()
    (sdir / "pv_v2.yaml").write_text(MINIMAL_PV_V2)
    return tmp_path


@pytest.fixture
def cfg(tmp_root):
    from panthera_mvp.config import load_config

    return load_config()


def make_pick(
    pick_id,
    status="pending",
    profit=None,
    rule_id="R3",
    settled="",
    strategy_id="pv_v2",
    game_pk=1,
    selection="New York Yankees",
    config_hash="6f0d0924d4",
    market="ml",
):
    """Shared picks.csv row builder — used by test_report.py and
    test_dashboard.py so both stay pinned to the same schema/shape."""
    from panthera_mvp import store

    return {c: None for c in store.PICKS_COLUMNS} | {
        "pick_id": pick_id,
        "strategy_id": strategy_id,
        "game_pk": game_pk,
        "game_date_et": "2026-08-01",
        "matchup": "NYY @ BOS",
        "start_time_et": "2026-08-01 19:05",
        "day_type": "P",
        "slot_type": "P",
        "rule_id": rule_id,
        "market": market,
        "selection": selection,
        "price_american": -150,
        "price_decimal": 1.6667,
        "stake": 100,
        "movement_cents": 20,
        "rationale": "test",
        "config_hash": config_hash,
        "status": status,
        "settled_ts_utc": settled,
        "profit": profit,
        "final_score": "NYY 5 - BOS 3" if status != "pending" else None,
    }
