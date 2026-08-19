import shutil

import pytest

from panthera_mvp import paths
from panthera_mvp.backtest.engine import _prepare_games, run
from panthera_mvp.backtest.loader import load_dir, load_season_file


@pytest.fixture
def hist(tmp_root, fixtures_dir):
    raw = paths.historical_raw_dir()
    raw.mkdir(parents=True)
    shutil.copy(fixtures_dir / "sbro_2021.csv", raw / "mlb odds 2021.csv")
    _stub_schedule_cache(fixtures_dir)
    return load_dir()


def _stub_schedule_cache(fixtures_dir) -> None:
    """Pre-populate the MLB schedule cache so _prepare_games' start-time join
    never touches the network in tests (CLAUDE.md: no network in unit
    tests) -- mirrors the real committed data/historical/schedules/*.csv."""
    sched_dir = paths.historical_schedules_dir()
    sched_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixtures_dir / "mlb_schedule_2021_sbro.csv", sched_dir / "2021.csv")


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


def test_engine_no_longer_skips_hybrid_days(hist, cfg):
    """Regression guard for the 2026-08-19 fix (docs/mvp-design.md finding
    #13): the backtest used to fabricate a 19:05 ET start for every game and
    unconditionally skip HYBRID days, since daytype.slot_type can't classify
    a slot without a real start time. Real start times are now joined in
    from the MLB schedule cache, so forcing every day to HYBRID must still
    produce bets, not zero."""
    for day in cfg["day_map"]:
        cfg["day_map"][day] = "HYBRID"
    prepared = _prepare_games(hist)
    result = run(prepared, cfg)
    assert result.summary["n_bets"] > 0
    assert set(result.picks["day_type"]) == {"HYBRID"}


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


def test_engine_accepts_registry_engines(hist, cfg):
    """run(generate=...) takes any registry engine; default (_pv_rules) is
    equivalent to the raw rules path."""
    from panthera_mvp.strategy.registry import _pv_rules, fav_ml_pick

    prepared = _prepare_games(hist)
    default = run(prepared, cfg)
    explicit = run(prepared, cfg, generate=_pv_rules)
    assert default.summary == explicit.summary

    fav = run(prepared, cfg, generate=fav_ml_pick)
    assert fav.summary["n_bets"] == len(hist)  # baseline bets every game
    assert set(fav.picks["rule_id"]) == {"B_FAV"}


def test_cmd_backtest_writes_per_strategy_outputs(hist, tmp_root, capsys):
    """Per-strategy output files, by-rule persistence, and the loud splits
    refusal."""
    import shutil

    from conftest import REPO
    from panthera_mvp.backtest.engine import cmd_backtest

    sdir = tmp_root / "config" / "strategies"
    for name in ("fav_ml", "dog_ml", "sharp_split"):
        shutil.copy(REPO / "config" / "strategies" / f"{name}.yaml", sdir / f"{name}.yaml")

    cmd_backtest("2021-2021")
    out = capsys.readouterr().out
    # sharp_split has scope [live], so the default run skips it entirely.
    assert "sharp_split" not in out
    for sid in ("pv_v2", "fav_ml", "dog_ml"):
        assert (paths.calibration_dir() / f"backtest_picks_{sid}.csv").exists()
        assert (paths.calibration_dir() / f"backtest_by_rule_{sid}.csv").exists()

    # Explicitly requesting a splits strategy gets the loud refusal.
    cmd_backtest("2021-2021", strategy="sharp_split")
    out = capsys.readouterr().out
    assert "REFUSED sharp_split" in out and "not backtestable" in out
    assert not (paths.calibration_dir() / "backtest_picks_sharp_split.csv").exists()


@pytest.fixture
def hist_unnamed(tmp_root, fixtures_dir):
    """The real sbro files leave the run-line and total price columns
    *unnamed*; the committed fixture above names them, which is why the
    positional-fallback bug went unnoticed for the whole calibration era."""
    raw = paths.historical_raw_dir()
    raw.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixtures_dir / "sbro_2021_unnamed.csv", raw / "mlb odds 2021.csv")
    return load_dir()


PRICE_COLUMNS = [
    "vis_rl_odds",
    "home_rl_odds",
    "total_open",
    "total_open_over_odds",
    "total_open_under_odds",
    "total_close",
    "total_close_over_odds",
    "total_close_under_odds",
]


@pytest.mark.parametrize("frame", ["hist", "hist_unnamed"])
def test_loader_captures_prices(frame, request):
    """Regression guard: run-line odds and both totals must survive parsing
    whether or not the source file names those columns. When they do not, every
    run-line pick silently degrades to a moneyline (rules.py falls back on a
    missing rl_price) and no totals bet can be priced at all."""
    hist = request.getfixturevalue(frame)
    for col in PRICE_COLUMNS:
        assert col in hist.columns, col
        assert hist[col].notna().all(), f"{col} has nulls in {frame}"


def test_loader_price_values_match_source(hist_unnamed):
    row = hist_unnamed.iloc[0]  # NYY @ BOS, 2021-04-01
    assert row["vis_rl_line"] == -1.5
    assert row["vis_rl_odds"] == 145
    assert row["home_rl_line"] == 1.5
    assert row["home_rl_odds"] == -165
    assert row["total_open"] == 8.5
    assert row["total_close"] == 8
    # Visitor row carries the over price, home row the under price.
    assert row["total_close_over_odds"] == -105
    assert row["total_close_under_odds"] == -115


def test_loader_named_and_unnamed_agree(fixtures_dir, tmp_path):
    """Both header styles must normalize to identical data."""
    import pandas as pd

    frames = []
    for src in ("sbro_2021.csv", "sbro_2021_unnamed.csv"):
        dest = tmp_path / src.replace(".csv", "") / "mlb odds 2021.csv"
        dest.parent.mkdir(parents=True)
        shutil.copy(fixtures_dir / src, dest)
        frames.append(load_season_file(dest))
    pd.testing.assert_frame_equal(*frames)
