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
        "index.html", "football.html", "calibration.html", "glossary.html",
        "site_data.json", "ncaaf_data.json", "calibration_data.json", "glossary.json",
        ".nojekyll",
        "static/app.css", "static/app.js", "static/common.js", "static/football.js",
        "static/calibration.js", "static/glossary.js", "static/icons.svg",
    ):
        assert (out / name).exists(), f"missing {name}"
    data = json.loads((out / "site_data.json").read_text())
    assert data["generated_by_run"] == "morning"


def test_write_site_is_idempotent_and_gitignored_dir(tmp_root, cfg):
    write_site()
    write_site()  # must not error on a pre-existing site/ dir
    assert (paths.site_dir() / "site_data.json").exists()


# ------------------------------------------------------------------ NCAAF
def _seed_ncaaf(root):
    """One settled in-lineage ticket, one ticket under another hash, two
    decisions and three graded qualifying legs."""
    import shutil

    from conftest import REPO
    from panthera_mvp.ncaaf import store as nstore

    sdir = root / "config" / "ncaaf_strategies"
    sdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "config/ncaaf_strategies/cfb_spread_total_parlay.yaml", sdir)
    sid, lineage = "cfb_spread_total_parlay", "e96612a177"

    def leg(tid, n, sel, line, status):
        return {"ticket_id": tid, "leg_no": n, "event_id": str(n), "matchup": f"A{n} @ B{n}",
                "start_time_utc": "2026-10-03T19:00:00Z", "market": "spread",
                "selection": sel, "line": line, "price_american": -110,
                "price_decimal": 1.9091, "bookmaker": "dk", "status": status}

    nstore.append_ticket(
        {"ticket_id": "t1", "strategy_id": sid, "game_date_et": "2026-10-03", "n_legs": 2,
         "price_american": 264, "price_decimal": 3.6447, "stake": 100, "config_hash": lineage,
         "status": "win", "profit": 264.47},
        [leg("t1", 1, "BYU Cougars", -6.5, "win"), leg("t1", 2, "Miami Hurricanes", -15.5, "win")],
    )
    nstore.append_ticket(
        {"ticket_id": "t2", "strategy_id": sid, "game_date_et": "2026-10-04", "n_legs": 1,
         "price_american": -110, "price_decimal": 1.9091, "stake": 100,
         "config_hash": "0000000000", "status": "loss", "profit": -100.0},
        [leg("t2", 3, "Iowa Hawkeyes", 14.5, "loss")],
    )
    for day, status, quals in (
        ("2026-10-03", "ticket", [("S6", "win"), ("S1+S6", "win")]),
        ("2026-10-04", "no_ticket", [("S1", "loss")]),
    ):
        nstore.append_decision(
            {"strategy_id": sid, "game_date_et": day, "status": status,
             "reason": "test", "n_qualifiers": len(quals)},
            [{"strategy_id": sid, "game_date_et": day, "event_id": f"{day}-{i}",
              "matchup": "A @ B", "market": "spread", "selection": "A", "line": -3.0,
              "signal_ids": sigs, "on_ticket": True, "status": st}
             for i, (sigs, st) in enumerate(quals)],
        )


def test_ncaaf_payload_empty_without_strategies(tmp_root):
    from panthera_mvp.dashboard import build_ncaaf_data

    data = build_ncaaf_data()
    assert data["sport"] == "football" and data["level"] == "college"
    assert data["strategies"] == [] and data["tickets"] == []


def test_ncaaf_payload_matches_markdown_report(tmp_root):
    from panthera_mvp.dashboard import build_ncaaf_data
    from panthera_mvp.ncaaf.report import write_report

    _seed_ncaaf(tmp_root)
    data = build_ncaaf_data()
    md = open(write_report()).read()
    (s,) = data["strategies"]

    t = s["tickets"]  # in lineage only
    assert (t["n"], t["record"], t["pending"]) == (1, {"wins": 1, "losses": 0, "pushes": 0}, 0)
    assert "- Tickets: 1 (1-0-0 W-L-P, 0 pending)" in md
    assert f"profit ${t['profit']:+,.2f}, ROI {t['roi']:+.1f}%" in md
    (seg,) = s["screen_segments"]
    assert seg["config_hash"] == "0000000000" and seg["profit"] == -100.0
    assert "**SCREEN segment 0000000000**" in md

    rows = {r["signal"]: r for r in s["signals"]}
    assert set(rows) == {"S1", "S6"}
    for r in rows.values():
        rec = r["record"]
        line = (f"| {r['signal']} | {r['legs']} | {rec['wins']}-{rec['losses']}-{rec['pushes']} "
                f"| {r['win_pct']:.1f}% | {r['vs_breakeven']:+.1f} pts |")
        assert line in md, line
    assert s["decisions"]["counts"] == {"ticket": 1, "no_ticket": 1}
    assert [d["game_date_et"] for d in s["decisions"]["recent"]] == ["2026-10-04", "2026-10-03"]

    sg = s["singles"]  # 2 wins + 1 loss, $100 each at the -110 fallback price
    assert (sg["n"], sg["record"], sg["pending"]) == (3, {"wins": 2, "losses": 1, "pushes": 0}, 0)
    assert sg["profit"] == 81.82 and sg["staked"] == 300.0
    assert "- Singles: 3 (2-1-0 W-L-P, 0 pending)" in md
    assert f"profit ${sg['profit']:+,.2f}, ROI {sg['roi']:+.1f}%" in md
    dates = [x["game_date_et"] for x in data["singles"]]
    assert dates == ["2026-10-04", "2026-10-03", "2026-10-03"]
    assert data["singles"][0]["profit"] == -100.0 and data["singles"][0]["on_ticket"] is True

    ticket_ids = [x["ticket_id"] for x in data["tickets"]]
    assert ticket_ids == ["t2", "t1"]  # newest first
    assert [lg["selection"] for lg in data["tickets"][1]["legs"]] == [
        "BYU Cougars", "Miami Hurricanes"
    ]
    assert data["tickets"][0]["in_lineage"] is False


def test_audit_ncaaf_fixture_matches_payload_shape(tmp_root):
    """scripts/site_audit.py swaps tests/fixtures/ncaaf/site_ncaaf_data.json in
    when the live ledger is empty; it must keep the real payload's shape."""
    from conftest import FIXTURES
    from panthera_mvp.dashboard import build_ncaaf_data

    _seed_ncaaf(tmp_root)
    real = build_ncaaf_data()
    fixture = json.loads((FIXTURES / "ncaaf" / "site_ncaaf_data.json").read_text())
    assert set(fixture) == set(real)
    assert set(fixture["strategies"][0]) == set(real["strategies"][0])
    assert set(fixture["tickets"][0]) == set(real["tickets"][0])
    assert set(fixture["tickets"][0]["legs"][0]) == set(real["tickets"][0]["legs"][0])
    assert set(fixture["singles"][0]) == set(real["singles"][0])
    assert set(fixture["strategies"][0]["singles"]) == set(real["strategies"][0]["singles"])
    assert fixture["tickets"], "the audit fixture must carry tickets"
