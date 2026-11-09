"""Lab pieces: neighbours, settlement, ranking, the store, the CLI run and the report."""

import json
import os
import shutil

import numpy as np
import pandas as pd
import pytest

from lab_synth import eval_config, synth
from panthera_mvp.lab import climb, ncaaf_rules, report, run, store
from panthera_mvp.lab.config import (
    LabConfigError,
    get_path,
    initial_params,
    load_lab_config,
    set_path,
    validate,
)

# --- config and neighbours ---------------------------------------------------------------


def test_the_shipped_config_validates_and_starts_from_the_research_core():
    cfg = load_lab_config("ncaaf")
    p = initial_params(cfg)
    assert [k for k, v in p["signals"].items() if v["enabled"]] == [
        "weather_wind_under", "sp_plus_edge"]
    assert p["ticket"] == {"max_bets_per_day": 6, "max_price_american": -115,
                           "rank_by": "strength"}


def test_a_space_path_that_does_not_exist_is_a_hard_error():
    cfg = eval_config()
    cfg["space"].append({"path": "signals.nope.enabled", "toggle": True})
    with pytest.raises(LabConfigError):
        validate(cfg)


def test_neighbours_change_one_parameter_inside_bounds_in_a_fixed_order():
    cfg = eval_config()
    p = initial_params(cfg)
    n1 = climb.neighbours(p, cfg["space"])
    assert [(a, b, c) for a, b, c, _ in n1] == [(a, b, c) for a, b, c, _ in
                                                  climb.neighbours(p, cfg["space"])]
    for path, old, new, cand in n1:
        assert get_path(cand, path) == new != old
        changed = [q for q, _ in __import__("panthera_mvp.lab.report", fromlist=["x"])._flat(cand)
                   if get_path(cand, q) != get_path(p, q)]
        assert changed == [path]
    paths = {x[0] for x in n1}
    # Parameters of switched-off signals would be no-op trials: not offered.
    assert "signals.line_move_spread.min_points" not in paths
    assert "signals.line_move_spread.enabled" in paths
    assert "signals.sp_plus_edge.min_edge_points" in paths
    # Integers stay integers, and the original is untouched.
    assert ("ticket.max_bets_per_day", 6, 5) in {(a, b, c) for a, b, c, _ in n1}
    assert p == initial_params(cfg)
    # Bounds: at the minimum only the upward move remains.
    lo = set_path(p, "signals.sp_plus_edge.min_edge_points", 1.0)
    moves = [(b, c) for a, b, c, _ in climb.neighbours(lo, cfg["space"])
             if a == "signals.sp_plus_edge.min_edge_points"]
    assert moves == [(1.0, 1.5)]


def test_paired_z_is_zero_when_undefined():
    assert climb.paired_z(np.array([1.0])) == 0.0
    assert climb.paired_z(np.array([0.5, 0.5, 0.5])) == 0.0
    assert climb.paired_z(np.array([1.0, 0.0, 2.0, 1.0])) > 0


# --- settlement, ranking, caps -----------------------------------------------------------------


def one_game_rows(**over):
    r = {"decision_date_et": "2026-10-03", "decision_ts_utc": "t", "event_id": "g1",
         "start_time_utc": "2026-10-03T19:00:00Z", "neutral_site": False, "indoor": False,
         "spread_open": -3.5, "spread_now": -3.5, "total_open": 50.5, "total_now": 50.5,
         "wind_mph": 20.0, "sp_margin_home": np.nan,
         "spread_home_point": -3.5, "spread_home_dec": 1.9091,
         "spread_away_point": 3.5, "spread_away_dec": 1.9091,
         "over_point": 50.5, "over_dec": 1.9091, "under_point": 50.5, "under_dec": 1.9091,
         "lead_minutes": 600.0}
    return r | over


def wind_only(cfg):
    p = initial_params(cfg)
    p["signals"]["sp_plus_edge"]["enabled"] = False
    return p


@pytest.mark.parametrize("hs,as_,status,want", [
    (30, 20, "Final", 1.9091 - 1),     # 50 total < 50.5: under wins
    (30, 21, "Final", -1.0),           # 51 total: under loses
    (30, np.nan, "Final", None),       # no score: pending
    (np.nan, np.nan, "Postponed", None),
    (None, None, "Scheduled", None),
])
def test_settlement_of_a_wind_under(hs, as_, status, want):
    cfg = eval_config()
    games = pd.DataFrame([{"event_id": "g1", "status": status, "home_score": hs,
                           "away_score": as_}])
    res = climb.simulate(pd.DataFrame([one_game_rows()]), games, wind_only(cfg))
    assert len(res.bets) == 1 and res.bets.iloc[0]["signal_ids"] == "S5"
    if want is None:
        assert not res.placed.any() and np.isnan(res.bets["profit"].iloc[0])
    else:
        assert res.profit[0] == pytest.approx(want)


def test_a_push_pays_nothing():
    cfg = eval_config()
    p = wind_only(cfg)
    rows = pd.DataFrame([one_game_rows(under_point=50.0, total_now=50.0, total_open=50.0)])
    games = pd.DataFrame([{"event_id": "g1", "status": "Final", "home_score": 30,
                           "away_score": 20}])
    res = climb.simulate(rows, games, p)
    assert res.placed[0] and res.profit[0] == 0.0


def test_spread_settlement_uses_the_bettors_side_and_line():
    cfg = eval_config()
    p = initial_params(cfg)
    p["signals"]["weather_wind_under"]["enabled"] = False
    p["signals"]["line_move_spread"] = {"enabled": True, "min_points": 1.5}
    rows = pd.DataFrame([one_game_rows(spread_open=-1.5, spread_now=-3.5)])  # moves home
    for hs, as_, want in ((14, 10, 0.9091), (14, 9, 0.9091), (13, 10, -1.0)):
        games = pd.DataFrame([{"event_id": "g1", "status": "Final", "home_score": hs,
                               "away_score": as_}])
        res = climb.simulate(rows, games, p)
        assert res.bets.iloc[0]["side"] == "home"
        assert res.profit[0] == pytest.approx(want)  # home -3.5: needs a margin of 4


def test_price_filter_drops_a_bet_before_it_takes_a_daily_slot():
    cfg = eval_config()
    p = wind_only(cfg)
    p["ticket"]["max_bets_per_day"] = 1
    good = one_game_rows(event_id="a", wind_mph=16.0, start_time_utc="2026-10-03T20:00:00Z")
    stronger_but_priced_out = one_game_rows(event_id="b", wind_mph=30.0, under_dec=1.80)
    rows = pd.DataFrame([stronger_but_priced_out, good])
    bets = ncaaf_rules.select_bets(ncaaf_rules.qualify_frame(rows, p), p)
    assert list(bets["event_id"]) == ["a"]
    p["ticket"]["max_price_american"] = None
    bets = ncaaf_rules.select_bets(ncaaf_rules.qualify_frame(rows, p), p)
    assert list(bets["event_id"]) == ["b"]


def test_the_numpy_hot_path_and_the_dataframe_path_select_the_same_bets():
    cfg = eval_config()
    feats, games = synth(11, 6, 120)
    for rank_by in ("strength", "n_signals"):
        for cap in (3, 6, None):
            p = initial_params(cfg)
            for s in ("line_move_spread", "line_move_total", "letdown", "look_ahead"):
                p["signals"][s]["enabled"] = True
            p["ticket"].update(rank_by=rank_by, max_bets_per_day=cap, max_price_american=None)
            prep = climb.prepare(feats, games)
            hot = climb.simulate_prepared(prep, p)
            slow = climb.simulate(feats, games, p)
            frame = slow.bets
            assert np.allclose(hot.profit, slow.profit)
            assert hot.placed.sum() == frame["profit"].notna().sum()
            if cap:
                assert frame.groupby("decision_date_et").size().max() <= cap
            # Ranked best-first inside each day.
            col = "strength" if rank_by == "strength" else "n_signals"
            for _d, grp in frame.groupby("decision_date_et", sort=False):
                assert list(grp[col]) == sorted(grp[col], reverse=True)


def test_skip_day_after_loss_skips_the_day_after_a_net_losing_day():
    cfg = eval_config()
    p = wind_only(cfg)
    p["bet_limits"]["skip_day_after_loss"] = True
    rows, games = [], []
    for day, over_total in (("2026-10-01", True), ("2026-10-02", False), ("2026-10-03", False),
                            ("2026-10-05", True)):
        eid = f"g{day}"
        rows.append(one_game_rows(event_id=eid, decision_date_et=day,
                                  start_time_utc=f"{day}T19:00:00Z"))
        games.append({"event_id": eid, "status": "Final", "home_score": 40 if over_total else 20,
                      "away_score": 20 if over_total else 10})  # 60 over / 30 under
    res = climb.simulate_prepared(climb.prepare(pd.DataFrame(rows), pd.DataFrame(games)), p)
    # Oct 1 loses (over hits), Oct 2 is skipped, Oct 3 bets and wins, Oct 5 follows no bet day.
    placed = {r["event_id"] for r, pl in zip(rows, res.placed, strict=True) if pl}
    assert placed == {"g2026-10-01", "g2026-10-03", "g2026-10-05"}


# --- the store --------------------------------------------------------------------------------


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    return tmp_path


def test_append_features_is_idempotent_and_keyed_by_day_and_event(root):
    feats, _ = synth(1, 1, 5)
    rows = feats.to_dict("records")
    assert store.append_features("ncaaf", rows) == 5
    assert store.append_features("ncaaf", rows) == 0
    later = [dict(r, decision_date_et="2026-12-01") for r in rows[:2]]
    assert store.append_features("ncaaf", later + rows[:1]) == 2
    assert len(store.load_features("ncaaf")) == 7
    assert store.append_features("ncaaf", []) == 0


def test_a_killed_write_leaves_the_old_file_intact(root, monkeypatch):
    feats, _ = synth(1, 1, 4)
    store.append_features("ncaaf", feats.to_dict("records")[:2])
    before = store.features_csv("ncaaf").read_bytes()

    def boom(*a, **k):
        raise OSError("killed")

    with monkeypatch.context() as m:
        m.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            store.append_features("ncaaf", feats.to_dict("records")[2:])
    assert store.features_csv("ncaaf").read_bytes() == before
    assert len(store.load_features("ncaaf")) == 2


def test_champion_and_iterations_round_trip_and_count_trials(root):
    assert store.load_champion("ncaaf") is None and store.trials_total("ncaaf") == 0
    store.save_champion("ncaaf", {"params": {"a": 1}, "hash": "h"})
    assert store.load_champion("ncaaf")["params"] == {"a": 1}
    for t in (12, 31):
        store.append_iteration("ncaaf", {"run_ts": "x", "trials_total": t, "decision": "no_change"})
    assert store.trials_total("ncaaf") == 31
    assert len(store.load_iterations("ncaaf")) == 2


# --- the run and the report -----------------------------------------------------------------------


def seed_root(root, weeks=8, per_week=60, min_bets=None):
    (root / "config" / "lab").mkdir(parents=True)
    shutil.copy("config/lab/ncaaf.yaml", root / "config" / "lab" / "ncaaf.yaml")
    if min_bets is not None:  # pin the sample floor so the case does not depend on the default
        import yaml

        path = root / "config" / "lab" / "ncaaf.yaml"
        cfg = yaml.safe_load(path.read_text())
        cfg["guards"]["min_bets"] = min_bets
        path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    feats, games = synth(2, weeks, per_week)
    store.append_features("ncaaf", feats.to_dict("records"))
    gp = root / "data" / "ncaaf" / "games" / "games.csv"
    gp.parent.mkdir(parents=True)
    games.to_csv(gp, index=False)


def test_run_writes_champion_iteration_and_report_and_dry_run_writes_nothing(root, capsys):
    seed_root(root, min_bets=100_000)
    dry = run.cmd_run("ncaaf", dry_run=True, force=True)
    assert dry.decision == "insufficient_data"            # the floor is out of reach
    assert store.load_champion("ncaaf") is None and store.load_iterations("ncaaf").empty
    assert not (root / "reports" / "LAB_REPORT.md").exists()

    res = run.cmd_run("ncaaf", force=True)
    assert res.decision == "insufficient_data"
    champ = store.load_champion("ncaaf")
    assert champ["change"] == "initial" and champ["eval_version"] == "lab_eval_v1"
    it = store.load_iterations("ncaaf")
    assert len(it) == 1 and it.iloc[0]["decision"] == "insufficient_data"
    md = (root / "reports" / "LAB_REPORT.md").read_text()
    assert report.BANNER in md and champ["hash"] in md and "Last 12 runs" in md
    assert "selected on past data" in md

    run.cmd_run("ncaaf", force=True)
    assert len(store.load_iterations("ncaaf")) == 2
    run.cmd_status("ncaaf")
    assert "champion" in capsys.readouterr().out


def test_run_promotes_and_the_new_champion_starts_tomorrow(root, monkeypatch):
    seed_root(root)
    cfg_path = root / "config" / "lab" / "ncaaf.yaml"
    text = cfg_path.read_text().replace("min_bets: 300", "min_bets: 1")
    text = text.replace("z_min: 2.0", "z_min: -100.0")
    cfg_path.write_text(text)
    monkeypatch.setattr(climb, "z_required", lambda g, t: -100.0)
    res = run.cmd_run("ncaaf", force=True)
    if res.decision == "promoted":
        champ = store.load_champion("ncaaf")
        assert champ["parent_hash"] and champ["change"].startswith(res.param)
        assert champ["effective_from"] > store.load_iterations("ncaaf")["run_ts"].iloc[0][:10]
        assert "-> " in champ["change"]
    else:  # no neighbour beat the champion on this seed: the ledger still records it
        assert store.load_iterations("ncaaf").iloc[0]["decision"] == "no_change"


def test_out_of_season_is_a_no_op_and_a_changed_evaluator_refuses(root, monkeypatch, capsys):
    seed_root(root)
    import panthera_mvp.lab.run as lab_run

    class July:
        month, year = 7, 2026

        def isocalendar(self):
            return (2026, 28, 3)

    class FakeNow:
        def astimezone(self, tz):
            return type("D", (), {"date": lambda s: July()})()

    with monkeypatch.context() as m:
        m.setattr(lab_run, "now_utc", lambda: FakeNow())
        assert run.cmd_run("ncaaf") is None
    assert "out of season" in capsys.readouterr().out
    assert store.load_champion("ncaaf") is None

    store.save_champion("ncaaf", {"params": initial_params(load_lab_config("ncaaf")),
                                  "hash": "h", "eval_version": "lab_eval_v0",
                                  "effective_from": "2026-09-01"})
    with pytest.raises(LabConfigError, match="new evaluator"):
        run.cmd_run("ncaaf", force=True)


def test_report_with_no_runs_says_so(root):
    (root / "config" / "lab").mkdir(parents=True)
    shutil.copy("config/lab/ncaaf.yaml", root / "config" / "lab" / "ncaaf.yaml")
    path = report.write_report()
    text = open(path).read()
    assert "No run yet" in text and report.BANNER in text
    assert json.dumps  # keep the import honest
