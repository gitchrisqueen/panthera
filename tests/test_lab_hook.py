"""The feature-logging hook in `ncaaf picks`: it logs one row per game on the slate at
decision time, is idempotent, and can never sink a live decision."""

import json
import shutil
from datetime import UTC, datetime

import pytest

from panthera_mvp.lab import store as lab_store
from panthera_mvp.ncaaf import picks, pipeline
from panthera_mvp.ncaaf import store as nstore

V1 = "config/ncaaf_strategies/cfb_spread_total_parlay.yaml"


@pytest.fixture
def root(tmp_path, monkeypatch, fixtures_dir):
    from conftest import REPO

    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config" / "ncaaf_strategies").mkdir(parents=True)
    (tmp_path / "config" / "lab").mkdir(parents=True)
    shutil.copy(REPO / "config/ncaaf.yaml", tmp_path / "config/ncaaf.yaml")
    shutil.copy(REPO / V1, tmp_path / V1)
    shutil.copy(REPO / "config/lab/ncaaf.yaml", tmp_path / "config/lab/ncaaf.yaml")
    cfb = fixtures_dir / "ncaaf"
    monkeypatch.setenv("PANTHERA_NCAAF_ESPN_FIXTURE", str(cfb / "espn_cfb_scoreboard.json"))
    monkeypatch.setenv("PANTHERA_NCAAF_ODDS_FIXTURE", str(cfb / "odds_ncaaf_snapshot.json"))
    monkeypatch.delenv("CFBD_API_KEY", raising=False)
    monkeypatch.setattr(pipeline, "_today_et", lambda: "2026-10-03")
    monkeypatch.setattr(picks, "_now", lambda: datetime(2026, 10, 3, 18, 0, tzinfo=UTC))
    return tmp_path


def test_decision_logs_one_feature_row_per_game_and_is_idempotent(root):
    picks.cmd_prep(odds_mode="dry_run")
    picks.cmd_picks(dry_run=True)
    feats = lab_store.load_features("ncaaf")
    assert len(feats) >= 3 and set(feats["decision_date_et"]) == {"2026-10-03"}
    assert not feats.duplicated(["decision_date_et", "event_id"]).any()
    n = len(feats)
    picks.cmd_picks(dry_run=True)  # already decided: no second decision, no duplicate rows
    assert len(lab_store.load_features("ncaaf")) == n


def test_a_lab_failure_never_sinks_the_decision(root, monkeypatch, capsys):
    from panthera_mvp.lab import features

    def boom(*a, **k):
        raise RuntimeError("bad\n::set-output name=x::y")

    monkeypatch.setattr(features, "build_feature_rows", boom)
    picks.cmd_prep(odds_mode="dry_run")
    picks.cmd_picks(dry_run=True)
    assert list(nstore.load_decisions()["strategy_id"]) == ["cfb_spread_total_parlay"]
    err = capsys.readouterr().err
    assert "::warning::ncaaf picks: lab feature logging failed: RuntimeError" in err
    assert not any(ln.startswith("::set-output") for ln in err.splitlines())
    assert lab_store.load_features("ncaaf").empty


def test_logged_features_replay_to_the_engines_decision(root):
    """End to end: the hook's rows, run through the lab rules with v1's own thresholds,
    qualify the same events the engine put in its ledger."""
    # The same synthetic SP+ the engine tests use, so S6 fires.
    from panthera_mvp.clients import cfbd
    from panthera_mvp.lab import ncaaf_rules
    from panthera_mvp.ncaaf.config import load_ncaaf_strategies

    picks.cmd_prep(odds_mode="dry_run")
    season = int(nstore.load_games()["season"].dropna().iloc[0])
    sp = [{"year": season, "team": t, "rating": r} for t, r in
          (("BYU", 20.0), ("TCU", 0.0), ("Miami", 30.0), ("Clemson", 5.0),
           ("Texas Tech", 25.0), ("Colorado", 2.0))]
    path = cfbd.cache_path("ratings/sp", {"year": season})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sp))
    picks.cmd_picks(dry_run=True)

    engine = set(nstore.load_qualifiers()["event_id"].astype(str))
    cfg = load_ncaaf_strategies()["cfb_spread_total_parlay"]
    feats = lab_store.load_features("ncaaf")
    lab = set()
    for row in feats.to_dict("records"):
        lab |= {str(b["event_id"]) for b in ncaaf_rules.qualify_row(row, cfg)}
    assert engine and lab == engine
