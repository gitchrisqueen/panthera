import shutil

import pytest

from panthera_mvp import paths
from panthera_mvp.backtest.engine import _prepare_games, run
from panthera_mvp.backtest.loader import load_dir


@pytest.fixture
def hist(tmp_root, fixtures_dir):
    raw = paths.historical_raw_dir()
    raw.mkdir(parents=True)
    shutil.copy(fixtures_dir / "sbro_2021.csv", raw / "mlb odds 2021.csv")
    return load_dir()


def test_loader_pairs_rows_into_games(hist):
    assert len(hist) == 5
    row = hist.iloc[0]
    assert row["vis_team"] == "NYY"
    assert row["home_team"] == "BOS"
    assert row["game_date"] == "2021-04-01"
    assert row["day_of_week"] == "thursday"
    assert row["vis_ml_open"] == -165
    assert row["vis_ml_close"] == -180
    assert row["home_final"] == 3


def test_loader_writes_normalized_csv(hist):
    assert paths.historical_normalized_csv().exists()


def test_engine_produces_graded_picks(hist, cfg):
    prepared = _prepare_games(hist)
    result = run(prepared, cfg)
    assert result.summary["n_bets"] >= 1
    # Every pick must be fully graded with a profit number.
    assert set(result.picks["status"]) <= {"win", "loss", "push"}
    assert result.picks["profit"].notna().all()


def test_engine_skips_hybrid_days(hist, cfg):
    # Force every day to HYBRID: with no start times, nothing can be slotted.
    for day in cfg["day_map"]:
        cfg["day_map"][day] = "HYBRID"
    prepared = _prepare_games(hist)
    result = run(prepared, cfg)
    assert result.summary["n_bets"] == 0
    assert result.summary.get("skipped_hybrid", 0) == 0 or result.summary["n_bets"] == 0


def test_hand_checked_pnl(hist, cfg):
    """2021-04-06 HOU @ TEX: fav HOU -220 -> -240 (shortened >= 10 = public),
    Tuesday = V day in default map -> back the dog (TEX ML +205). TEX lost
    1-6 -> loss of $100."""
    prepared = _prepare_games(hist)
    result = run(prepared, cfg)
    tex = result.picks[result.picks["matchup"] == "HOU @ TEX"]
    assert len(tex) == 1
    assert tex.iloc[0]["selection"] == "TEX"
    assert tex.iloc[0]["status"] == "loss"
    assert tex.iloc[0]["profit"] == -100.0
