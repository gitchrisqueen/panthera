"""Splits engines: event selection, pass reasons, thresholds, pricing."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.config import load_strategy_configs
from panthera_mvp.strategy.registry import StrategyContext
from panthera_mvp.strategy.rules import GamePrices, Pass, Pick
from panthera_mvp.strategy.splits_signal import (
    extract_game_splits,
    fade_public_pick,
    sharp_split_pick,
)

GAME_START = datetime(2026, 8, 1, 23, 5, tzinfo=UTC)


def _splits_rows(event_id, starts_at, label, captured, metrics):
    return [
        {
            "fetched_ts_utc": "2026-08-01T15:00:00Z",
            "game_date_et": "2026-08-01",
            "snapshot_label": label,
            "lumify_event_id": event_id,
            "event_name": "NYY @ BOS",
            "starts_at_utc": starts_at,
            "captured_at": captured,
            "game_pk": 776001,
            "metric": f"moneyline.{k}",
            "value": v,
        }
        for k, v in metrics.items()
    ]


BASE_METRICS = {
    "home.bets_pct": 29.0,
    "home.handle_pct": 86.0,
    "away.bets_pct": 71.0,
    "away.handle_pct": 14.0,
}


def _game(status="Preview"):
    return GameInfo(
        game_pk=776001,
        game_date_et="2026-08-01",
        game_type="R",
        status=status,
        detailed_state="Scheduled",
        start_utc=GAME_START,
        doubleheader="N",
        game_number=1,
        home_team_id=111,
        home_team="Boston Red Sox",
        away_team_id=147,
        away_team="New York Yankees",
    )


def _ctx(tmp_root, splits, prices="default", sid="sharp_split"):
    cfgs = load_strategy_configs()
    scfg = cfgs.get(sid)
    if prices == "default":
        prices = GamePrices(
            home_ml_open=-140, away_ml_open=120, home_ml_latest=-140, away_ml_latest=120
        )
    return StrategyContext(
        game=_game(),
        odds_event_id="evt-1",
        prices=prices,
        dossier=None,
        cfg=scfg,
        splits=splits,
    )


@pytest.fixture
def strategies(tmp_root):
    """Real sharp_split/fade_public YAMLs copied into the tmp config dir."""
    import shutil

    from conftest import REPO

    sdir = tmp_root / "config" / "strategies"
    for name in ("sharp_split", "fade_public"):
        shutil.copy(REPO / "config" / "strategies" / f"{name}.yaml", sdir / f"{name}.yaml")
    return tmp_root


def test_extract_selects_event_by_start_time(strategies):
    """Two events attached to one (date, game_pk) — the historical
    contradictory-duplicate case — must resolve by start-time match, and a
    >= 20:00 ET start (UTC next day) must still be found."""
    wrong = _splits_rows(
        10800, "2026-08-01T00:15:00Z", "pregame", "2026-07-31T23:00:00Z",
        {"home.bets_pct": 80.0, "home.handle_pct": 94.0},
    )
    right = _splits_rows(
        11622, "2026-08-01T23:05:00Z", "pregame", "2026-08-01T20:00:00Z", BASE_METRICS
    )
    df = pd.DataFrame(wrong + right)
    s = extract_game_splits(df, 776001, GAME_START)
    assert s.lumify_event_id == 11622
    assert s.ml_home_bets == 29.0

    late_start = datetime(2026, 8, 2, 0, 40, tzinfo=UTC)  # 20:40 ET Aug 1
    late = pd.DataFrame(
        _splits_rows(12000, "2026-08-02T00:40:00Z", "pregame", "2026-08-01T20:00:00Z",
                     BASE_METRICS)
    )
    s2 = extract_game_splits(late, 776001, late_start)
    assert s2 is not None and s2.lumify_event_id == 12000


def test_extract_prefers_fresher_label_and_capture(strategies):
    morning = _splits_rows(
        11622, "2026-08-01T23:05:00Z", "morning", "2026-08-01T14:00:00Z",
        {"home.bets_pct": 50.0, "home.handle_pct": 50.0},
    )
    pregame_old = _splits_rows(
        11622, "2026-08-01T23:05:00Z", "pregame", "2026-08-01T19:00:00Z",
        {"home.bets_pct": 40.0, "home.handle_pct": 60.0},
    )
    df = pd.DataFrame(morning + pregame_old)
    s = extract_game_splits(df, 776001, GAME_START)
    assert s.snapshot_label == "pregame"
    assert s.ml_home_bets == 40.0


def test_sharp_split_picks_the_money_side(strategies, monkeypatch):
    monkeypatch.setattr(
        "panthera_mvp.strategy.splits_signal.now_utc",
        lambda: datetime(2026, 8, 1, 21, 0, tzinfo=UTC),
    )
    df = pd.DataFrame(
        _splits_rows(11622, "2026-08-01T23:05:00Z", "pregame",
                     "2026-08-01T20:00:00Z", BASE_METRICS)
    )
    s = extract_game_splits(df, 776001, GAME_START)
    result = sharp_split_pick(_ctx(strategies, s))
    assert isinstance(result, Pick)
    assert result.selection == "Boston Red Sox"  # 86% handle on 29% tickets
    assert result.rule_id == "SS_ml"
    assert result.market == "ml"
    assert result.price_american == -140  # from lines consensus, never splits


def test_sharp_split_pass_reasons(strategies, monkeypatch):
    monkeypatch.setattr(
        "panthera_mvp.strategy.splits_signal.now_utc",
        lambda: datetime(2026, 8, 1, 21, 0, tzinfo=UTC),
    )
    # no-splits
    r = sharp_split_pick(_ctx(strategies, None))
    assert isinstance(r, Pass) and "no-splits" in r.reason

    # stale (captured 13h ago vs max 12)
    df = pd.DataFrame(
        _splits_rows(1, "2026-08-01T23:05:00Z", "pregame",
                     "2026-08-01T08:00:00Z", BASE_METRICS)
    )
    s = extract_game_splits(df, 776001, GAME_START)
    r = sharp_split_pick(_ctx(strategies, s))
    assert isinstance(r, Pass) and "stale" in r.reason

    # no-divergence
    flat = {**BASE_METRICS, "home.handle_pct": 33.0, "away.handle_pct": 67.0}
    df = pd.DataFrame(
        _splits_rows(1, "2026-08-01T23:05:00Z", "pregame",
                     "2026-08-01T20:00:00Z", flat)
    )
    s = extract_game_splits(df, 776001, GAME_START)
    r = sharp_split_pick(_ctx(strategies, s))
    assert isinstance(r, Pass) and "no-divergence" in r.reason

    # no-price
    df = pd.DataFrame(
        _splits_rows(1, "2026-08-01T23:05:00Z", "pregame",
                     "2026-08-01T20:00:00Z", BASE_METRICS)
    )
    s = extract_game_splits(df, 776001, GAME_START)
    r = sharp_split_pick(_ctx(strategies, s, prices=None))
    assert isinstance(r, Pass) and "no-price" in r.reason

    # too-heavy
    heavy = GamePrices(
        home_ml_open=-320, away_ml_open=260, home_ml_latest=-320, away_ml_latest=260
    )
    r = sharp_split_pick(_ctx(strategies, s, prices=heavy))
    assert isinstance(r, Pass) and "too-heavy" in r.reason


def test_fade_public_bets_opposite_side(strategies, monkeypatch):
    monkeypatch.setattr(
        "panthera_mvp.strategy.splits_signal.now_utc",
        lambda: datetime(2026, 8, 1, 21, 0, tzinfo=UTC),
    )
    metrics = {
        "home.bets_pct": 22.0,
        "home.handle_pct": 30.0,
        "away.bets_pct": 78.0,   # >= 70% tickets on NYY -> fade to BOS
        "away.handle_pct": 70.0,
    }
    df = pd.DataFrame(
        _splits_rows(1, "2026-08-01T23:05:00Z", "pregame",
                     "2026-08-01T20:00:00Z", metrics)
    )
    s = extract_game_splits(df, 776001, GAME_START)
    result = fade_public_pick(_ctx(strategies, s, sid="fade_public"))
    assert isinstance(result, Pick)
    assert result.selection == "Boston Red Sox"
    assert result.rule_id == "FP_ml"

    # Below threshold -> no-divergence pass.
    mild = {**metrics, "away.bets_pct": 60.0, "home.bets_pct": 40.0}
    df = pd.DataFrame(
        _splits_rows(1, "2026-08-01T23:05:00Z", "pregame",
                     "2026-08-01T20:00:00Z", mild)
    )
    s = extract_game_splits(df, 776001, GAME_START)
    r = fade_public_pick(_ctx(strategies, s, sid="fade_public"))
    assert isinstance(r, Pass) and "no-divergence" in r.reason
