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


@pytest.fixture
def tmp_root(tmp_path, monkeypatch) -> Path:
    """Point the datastore at an isolated tmp repo root with the real config."""
    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / "config" / "strategy.yaml", tmp_path / "config" / "strategy.yaml")
    return tmp_path


@pytest.fixture
def cfg(tmp_root):
    from panthera_mvp.config import load_config

    return load_config()
