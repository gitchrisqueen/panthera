import json

import pandas as pd

from conftest import make_pick as _pick
from panthera_mvp import paths, store
from panthera_mvp.dashboard import build_site_data, write_site
from panthera_mvp.report import _verdict_text, write_ledger_report


def test_empty_site_data(tmp_root, cfg):
    """No picks yet: the fixture's one registered (enabled) strategy still
    shows up with zero graded picks, same as write_ledger_report's '0 | —'
    row — but nothing pooled anywhere and no portfolio/replay data."""
    data = build_site_data()
    assert all(s["graded_n"] == 0 for s in data["strategies"])
    assert data["picks_history"] == []
    assert data["portfolio_totals"] is None
    assert data["retroactive_replay"]["strategies"] == []
    assert "banner" in data["retroactive_replay"]


def test_site_data_matches_markdown_ledger_numbers(tmp_root, cfg):
    """The JSON payload must report the exact same record/P&L/ROI as the
    markdown ledger for the same picks — same source, two renderings."""
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick(
                    "b", "loss", -100.0, rule_id="R4",
                    settled="2026-08-02T14:00:00Z", game_pk=2, market="rl",
                ),
                _pick("c", game_pk=3),
            ]
        )
    )
    md = write_ledger_report(cfg).read_text()
    data = build_site_data()
    pv_v2 = next(s for s in data["strategies"] if s["id"] == "pv_v2")
    assert pv_v2["record"] == {"wins": 1, "losses": 1, "pushes": 0, "voids": 0}
    assert "1-1-0" in md  # cross-check against the markdown's own rendering
    assert pv_v2["verdict_segment"]["verdict_text"] == _verdict_text(
        {"min_graded": 100, "supported_roi": 0.0, "falsified_roi": -5.0},
        {"roi": pv_v2["roi"]},
        pv_v2["graded_n"],
    )
    assert "collecting (2/100)" in md
    assert pv_v2["verdict_segment"]["n_graded"] == 2


def test_verdict_segments_never_include_zero_graded_only_when_absent(tmp_root, cfg):
    """A strategy with zero graded picks still gets a verdict_segment object
    (e.g. pv_orig's '0/100 collecting') — dashboard.py must not early-return
    before computing it, mirroring report.py's _segment_blocks."""
    (tmp_root / "config" / "strategies" / "pv_orig.yaml").write_text(
        "strategy: {id: pv_orig, engine: orig_rules, enabled: true, kind: aligned,\n"
        "  scope: [live], registered_at: '2026-08-19', hash_lineage: [deadbeef01]}\n"
        "verdict: {min_graded: 100, supported_roi: 0.0, falsified_roi: -5.0}\n"
        "screen: {checkpoints: [100]}\n"
        "bet_limits: {max_picks_per_day: null, one_pick_per_game: true}\n"
        "staking: {flat_stake: 100}\n"
    )
    data = build_site_data()
    pv_orig = next(s for s in data["strategies"] if s["id"] == "pv_orig")
    assert pv_orig["verdict_segment"] is not None
    assert pv_orig["verdict_segment"]["n_graded"] == 0
    assert "0/100" in pv_orig["verdict_segment"]["verdict_text"]


def test_out_of_lineage_hash_is_screen_not_verdict(tmp_root, cfg):
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick(
                    "b", "loss", -100.0, settled="2026-08-02T14:00:00Z",
                    game_pk=2, config_hash="newhash9999",
                ),
            ]
        )
    )
    data = build_site_data()
    pv_v2 = next(s for s in data["strategies"] if s["id"] == "pv_v2")
    assert pv_v2["verdict_segment"]["n_graded"] == 1  # lineage-only pool
    assert len(pv_v2["screen_segments"]) == 1
    assert pv_v2["screen_segments"][0]["config_hash"] == "newhash9999"

    ledger_rows = {r["pick_id"]: r for r in data["picks_history"]}
    assert ledger_rows["a"]["segment_kind"] == "verdict"
    assert ledger_rows["b"]["segment_kind"] == "screen"


def test_screen_only_strategy_never_gets_a_verdict_segment(tmp_root, cfg):
    """fav_ml has verdict: null — it must render as SCREEN-only, never a
    VERDICT segment, no matter how many picks it accumulates."""
    (tmp_root / "config" / "strategies" / "fav_ml.yaml").write_text(
        "strategy: {id: fav_ml, engine: fav_ml, enabled: true, kind: baseline,\n"
        "  scope: [live, backtest], registered_at: '2026-08-17', hash_lineage: []}\n"
        "verdict: null\n"
        "screen: {checkpoints: [100, 200]}\n"
        "bet_limits: {max_picks_per_day: null, one_pick_per_game: true}\n"
        "staking: {flat_stake: 100}\n"
    )
    store.append_picks(
        pd.DataFrame(
            [
                _pick(
                    "fav_ml-1", "win", 66.67, strategy_id="fav_ml",
                    rule_id="B_FAV", config_hash="abcdef1234",
                    settled="2026-08-02T14:00:00Z",
                )
            ]
        )
    )
    data = build_site_data()
    fav_ml = next(s for s in data["strategies"] if s["id"] == "fav_ml")
    assert fav_ml["verdict_segment"] is None
    assert len(fav_ml["screen_segments"]) == 1
    row = next(r for r in data["picks_history"] if r["strategy_id"] == "fav_ml")
    assert row["segment_kind"] == "screen"


def test_retroactive_replay_never_appears_outside_its_own_key(tmp_root, cfg):
    """The single most important isolation test: a shadow (replay) pick must
    never surface in picks_history, any strategy's verdict_segment/
    screen_segments, or portfolio_totals — only under retroactive_replay."""
    store.append_picks(
        pd.DataFrame([_pick("live-1", "win", 66.67, settled="2026-08-02T14:00:00Z")])
    )
    store.append_shadow_picks(
        pd.DataFrame(
            [
                _pick(
                    "shadow-1", "win", 200.0, settled="2026-08-01T00:00:00Z",
                    strategy_id="pv_orig", game_pk=999, config_hash="shadowhash",
                )
            ]
        )
    )
    data = build_site_data()

    shadow_ids = {"shadow-1"}
    picks_history_ids = {r["pick_id"] for r in data["picks_history"]}
    assert not (shadow_ids & picks_history_ids)

    for s in data["strategies"]:
        if s["verdict_segment"]:
            assert "shadow-1" not in json.dumps(s["verdict_segment"])
        assert "shadow-1" not in json.dumps(s["screen_segments"])

    assert data["portfolio_totals"]["profit"] == 66.67  # only the real pick

    replay = data["retroactive_replay"]
    assert any(s["id"] == "pv_orig" for s in replay["strategies"])
    pv_orig_replay = next(s for s in replay["strategies"] if s["id"] == "pv_orig")
    assert pv_orig_replay["profit"] == 200.0
    assert "Not an evaluation" in replay["banner"]


def test_portfolio_totals_match_markdown_totals_row(tmp_root, cfg):
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick(
                    "b", "loss", -100.0, settled="2026-08-02T14:00:00Z",
                    game_pk=2, market="rl",
                ),
            ]
        )
    )
    md = write_ledger_report(cfg).read_text()
    data = build_site_data()
    assert data["portfolio_totals"]["profit"] == -33.33
    assert "$-33.33" in md
    assert "portfolio (informational" in md
    assert "not an evaluation target" in data["portfolio_totals"]["note"]


def test_write_site_produces_expected_files(tmp_root, cfg):
    out = write_site(generated_by_run="morning")
    assert out == paths.site_dir()
    for name in (
        "index.html", "calibration.html", "site_data.json",
        "calibration_data.json", ".nojekyll",
        "static/app.css", "static/app.js", "static/icons.svg",
    ):
        assert (out / name).exists(), f"missing {name}"
    data = json.loads((out / "site_data.json").read_text())
    assert data["generated_by_run"] == "morning"


def test_write_site_is_idempotent_and_gitignored_dir(tmp_root, cfg):
    write_site()
    write_site()  # must not error on a pre-existing site/ dir
    assert (paths.site_dir() / "site_data.json").exists()
