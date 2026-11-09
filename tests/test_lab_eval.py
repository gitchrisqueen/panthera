"""Evals of the optimizer itself: does the weekly loop find a planted edge, and does it
refuse to invent one? Seeded and deterministic.

The null eval is the one that matters. About 100 bets a week cannot separate a real
+2% ROI from noise, so a loop that promotes on small wins would walk off a cliff of
its own luck. These tests hold the guards to that.
"""

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import pytest

from lab_synth import DEC, START, eval_config, run_weekly, small_space, synth
from panthera_mvp.lab import climb
from panthera_mvp.lab.config import get_path, initial_params

NULL_SPACE = [
    "signals.line_move_spread.enabled", "signals.line_move_total.enabled",
    "signals.letdown.enabled", "signals.weather_wind_under.min_wind_mph",
    "signals.sp_plus_edge.min_edge_points", "ticket.max_bets_per_day",
]


# --- (a) null: fair coins, nothing to find ------------------------------------------


NULL_FAST = [
    "signals.line_move_spread.enabled", "signals.weather_wind_under.min_wind_mph",
    "signals.sp_plus_edge.min_edge_points", "ticket.max_bets_per_day",
]


def _null_seed(seed: int) -> tuple[int, int, list[float]]:
    cfg = eval_config(min_bets=60, min_graded_games_for_run=40)
    feats, games = synth(seed, 40, 20)
    _params, results = run_weekly(feats, games, 40, cfg, small_space(cfg, NULL_FAST))
    claimed = [r.challenger_roi for r in results if r.decision == "promoted"]
    return len(results), len(claimed), claimed


def test_null_eval_rarely_promotes_and_never_claims_a_big_edge():
    # 200 seeds x 37 weekly runs. min_bets is lowered to 60 (the real default is 300) so a
    # promotion is as easy as it can be: this is the hard version of the test.
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        out = list(pool.map(_null_seed, range(200), chunksize=10))
    runs = sum(o[0] for o in out)
    promoted = sum(o[1] for o in out)
    claimed = [c for o in out for c in o[2]]
    assert runs == 200 * 37
    # 0.04% measured. Taking the z bar out raises it to 0.7% and the largest claimed
    # in-sample edge to +20% per bet, which these two lines catch.
    assert promoted / runs < 0.002
    assert all(c < 0.10 for c in claimed)


def test_a_naive_climber_chases_noise_where_the_guards_do_not():
    """Same data, no guards: promote the best neighbour whenever it beats the champion.
    It promotes constantly and its forward result is no better than coin-flipping at -110."""
    cfg = eval_config(min_bets=60, min_graded_games_for_run=40)
    space = small_space(cfg, NULL_SPACE)
    promotions = forward_units = forward_bets = 0
    guarded = 0
    for seed in range(12):
        feats, games = synth(seed, 24, 30)
        full = climb.prepare(feats, games)
        params = initial_params(cfg)
        for w in range(6, 20):
            k = int((full.day < full.day[0] + 7 * w + 3).sum())
            train = full.head(k)
            champ = climb.simulate_prepared(train, params)
            best = None
            for _p, _o, _n, cand in climb.neighbours(params, space):
                sim = climb.simulate_prepared(train, cand)
                if sim.placed.sum() >= 60 and (best is None or sim.profit.sum() > best[0]):
                    best = (sim.profit.sum(), cand)
            if best and best[0] > champ.profit.sum():
                params = best[1]
                promotions += 1
            # What the current naive champion does on the NEXT week, unseen.
            nxt = full.head(int((full.day < full.day[0] + 7 * (w + 1) + 3).sum()))
            res = climb.simulate_prepared(nxt, params)
            week = (nxt.day >= full.day[0] + 7 * w + 3)
            forward_units += res.profit[week].sum()
            forward_bets += res.placed[week].sum()
        _p, results = run_weekly(feats, games, 24, cfg, space, start_week=6)
        guarded += sum(r.decision == "promoted" for r in results)
    assert promotions > 20 * guarded + 20          # the naive loop keeps "improving"
    assert forward_units / forward_bets < 0.03     # ...with nothing real behind it


# --- (b) a planted edge is found ------------------------------------------------------


def test_planted_edge_is_found_and_nothing_else_is_promoted():
    # SP+ edges of 3.5-4 points (just under the champion's 4-point bar) really cover 65%.
    def p_home(edge):
        return 0.5 + 0.15 * np.sign(edge) if 3.5 <= abs(edge) < 4.0 else 0.5

    cfg = eval_config(min_bets=150, min_graded_games_for_run=100)
    # No daily cap here: a cap of 6 would only ever keep the strongest edges, and the
    # planted 3.5-4 point band would never make a day's list.
    cfg["structure"]["max_bets_per_day"] = 1000
    feats, games = synth(5, 22, 400, p_home_cover=p_home)
    space = small_space(cfg, [p for p in NULL_SPACE if p != "ticket.max_bets_per_day"])
    params, results = run_weekly(feats, games, 22, cfg, space)
    promos = [r for r in results if r.decision == "promoted"]
    assert [(r.param, r.new) for r in promos] == [("signals.sp_plus_edge.min_edge_points", 3.5)]
    start = initial_params(cfg)
    start["ticket"]["max_bets_per_day"] = 1000
    changed = [p for p in NULL_SPACE if p != "ticket.max_bets_per_day"
               and get_path(params, p) != get_path(start, p)]
    assert changed == ["signals.sp_plus_edge.min_edge_points"]
    # The claimed gain is real: the planted bets pay about +24% per bet.
    assert promos[0].challenger_roi > promos[0].champion_roi


# --- crafted pools: one challenger, a known story ----------------------------------------


def craft(win_rate_by_week: dict[int, float], per_week: int = 40, seed: int = 3,
          spike_week: int | None = None):
    """Every game fires S1 (home, -3.5, -110); S5/S6 never fire, so the champion bets
    nothing and the challenger 'S1 on' is the whole story."""
    rng = np.random.default_rng(seed)
    rows, games = [], []
    for w, p in win_rate_by_week.items():
        for i in range(per_week):
            eid = f"{w}-{i}"
            date = str((START + pd.Timedelta(days=7 * w + i % 3)).date())
            dec = DEC
            win = rng.random() < p
            if spike_week is not None and (w, i) == (spike_week, 0):
                dec, win = 400.0, True
            rows.append({
                "decision_date_et": date, "decision_ts_utc": date, "event_id": eid,
                "start_time_utc": f"{date}T19:00:00Z", "neutral_site": False, "indoor": False,
                "spread_open": -1.5, "spread_now": -3.5, "total_open": 50.5, "total_now": 50.5,
                "wind_mph": np.nan, "sp_margin_home": np.nan,
                "spread_home_point": -3.5, "spread_home_dec": dec,
                "spread_away_point": 3.5, "spread_away_dec": DEC,
                "over_point": 50.5, "over_dec": DEC, "under_point": 50.5, "under_dec": DEC,
                "lead_minutes": 600.0,
            })
            games.append({"event_id": eid, "status": "Final", "away_score": 10,
                          "home_score": 10 + (4 if win else 3)})
    return pd.DataFrame(rows), pd.DataFrame(games)


S1_TOGGLE = ["signals.line_move_spread.enabled"]


def one_run(feats, games, **guards):
    cfg = eval_config(**guards)
    return climb.walk(feats, games, initial_params(cfg), small_space(cfg, S1_TOGGLE),
                      cfg["guards"], {"trials_total": 0})


def test_control_a_real_and_lasting_edge_is_promoted():
    wins = {w: 0.65 for w in range(13)}
    res = one_run(*craft(wins), min_bets=100, min_graded_games_for_run=50)
    assert res.decision == "promoted", res.reason
    assert (res.param, res.new) == ("signals.line_move_spread.enabled", True)
    assert res.paired_z >= res.z_required


# --- (c) outlier ---------------------------------------------------------------------------


def test_one_huge_winner_does_not_buy_a_promotion():
    wins = {w: 0.5 for w in range(13)}
    feats, games = craft(wins, spike_week=2)
    res = one_run(feats, games, min_bets=100, min_graded_games_for_run=50, z_min=0.8)
    assert res.paired_z >= res.z_required          # the spike alone clears the z bar
    assert res.decision == "no_change"
    assert "one game" in res.reason
    # Without the spike the same data is a null result for another reason.
    plain = one_run(*craft(wins), min_bets=100, min_graded_games_for_run=50, z_min=0.8)
    assert plain.decision == "no_change" and "one game" not in plain.reason


# --- (d) holdout ------------------------------------------------------------------------------


def test_good_in_training_bad_in_the_holdout_is_rejected():
    wins = {w: 0.65 for w in range(10)} | {w: 0.30 for w in (10, 11, 12)}
    res = one_run(*craft(wins), min_bets=100, min_graded_games_for_run=50)
    assert res.paired_z >= res.z_required          # training alone would promote it
    assert res.decision == "no_change"
    assert "holdout" in res.reason
    assert res.holdout_challenger_roi < res.holdout_champion_roi or np.isnan(
        res.holdout_champion_roi)


# --- the shape of a quiet week ---------------------------------------------------------------


def test_too_little_data_is_recorded_not_guessed():
    wins = {0: 0.5, 1: 0.5}
    res = one_run(*craft(wins, per_week=10), min_bets=100, min_graded_games_for_run=50)
    assert res.decision == "insufficient_data"
    assert res.trials_total == 0


def test_the_multiple_testing_bar_rises_with_every_challenger_tried():
    g = eval_config()["guards"]
    assert climb.z_required(g, 1) == g["z_min"]
    assert climb.z_required(g, 10_000) > climb.z_required(g, 100) > g["z_min"]
    assert climb.z_required(g, 100) == pytest.approx(np.sqrt(2 * np.log(100)))
