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


def test_null_eval_reduced_space_long_horizon():
    """200 seeds x 37 weekly runs over a REDUCED space (4 of the 18 shipped paths: the
    fast version) with min_bets lowered to 60 (shipped: 100). It is a stress test of the
    z bar, not a measurement of the shipped loop: see the shipped-regime test below."""
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        out = list(pool.map(_null_seed, range(200), chunksize=10))
    runs = sum(o[0] for o in out)
    promoted = sum(o[1] for o in out)
    claimed = [c for o in out for c in o[2]]
    assert runs == 200 * 37
    seasons_hit = sum(o[1] > 0 for o in out)
    # Runs inside a season replay the same growing data, so they are not independent trials:
    # the honest unit is the simulated season.
    assert cp_upper(seasons_hit, 200) < 0.05
    assert promoted / runs < 0.002   # descriptive only, per run
    assert all(c < 0.10 for c in claimed)


def _shipped_seed(args: tuple[int, int, int]) -> tuple[int, int, int]:
    """(runs, promotions, insufficient_data runs) under the SHIPPED guards and space."""
    seed, weeks, per_week = args
    cfg = eval_config()
    feats, games = synth(seed, weeks, per_week)
    _p, results = run_weekly(feats, games, weeks, cfg, cfg["space"])
    return (len(results), sum(r.decision == "promoted" for r in results),
            sum(r.decision == "insufficient_data" for r in results))


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided Clopper-Pearson upper bound for k events in n trials (bisection)."""
    from math import comb

    def cdf(p):  # P(X <= k)
        return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))

    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > 1 - conf else (lo, mid)
    return hi


@pytest.mark.parametrize(
    "name,seeds,weeks,per_week,expect",
    [
        # A season-length run at the real volume (about 12-14 bets a week): 17 weeks, 18 games
        # a week. Measured 2026-11-09: 1 promotion in 4,200 runs, 2,609 of them insufficient.
        ("season", 300, 17, 18, (4200, 1, 2609)),
        # The long stress case: 40 weeks, 20 games a week. Measured: 1 in 3,700 runs.
        ("long", 100, 40, 20, (3700, 1, 747)),
    ],
)
def test_null_eval_with_the_shipped_guards_and_space(name, seeds, weeks, per_week, expect):
    """Fair coins, nothing to find, the SHIPPED guards (min_bets 100, min_diff_bets 30) and
    the SHIPPED 18-path space. Pinned to the measured counts: a change here means the guards,
    the rules or the generator changed, and PROGRAM.md's quoted rate must be updated."""
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        out = list(pool.map(_shipped_seed, [(s, weeks, per_week) for s in range(seeds)],
                            chunksize=5))
    runs, promoted, insufficient = (sum(o[i] for o in out) for i in range(3))
    assert (runs, promoted, insufficient) == expect, (name, runs, promoted, insufficient)
    # The unit is the simulated SEASON (the runs inside one replay the same growing data, so
    # they are not independent, and 62% of them could not promote at all). One promotion in
    # `seeds` seasons: 95% one-sided Clopper-Pearson upper bound about 1.6% (300) / 4.7% (100).
    seasons_hit = sum(o[1] > 0 for o in out)
    assert seasons_hit == 1
    upper = {300: 0.0157, 100: 0.0466}[seeds]
    assert cp_upper(seasons_hit, seeds) == pytest.approx(upper, abs=2e-3)


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


def _planted(seed: int):
    """400 games a week, 22 weeks, no daily cap, SP+ edges of 3.5-4 points (just under the
    champion's 4-point bar) really cover 65%: about +24% per planted bet. This checks the
    PLUMBING at more than twenty times the real volume (about 330 bets a week against about 14 in
    the season-length null eval, both measured on this generator). It is not a power
    estimate: at the real volume the loop cannot see an effect of this size, see
    PROGRAM.md."""
    def p_home(edge):
        return 0.5 + 0.15 * np.sign(edge) if 3.5 <= abs(edge) < 4.0 else 0.5

    cfg = eval_config(min_bets=150, min_graded_games_for_run=100)
    cfg["structure"]["max_bets_per_day"] = 1000
    feats, games = synth(seed, 22, 400, p_home_cover=p_home)
    paths_ = [p for p in NULL_SPACE if p != "ticket.max_bets_per_day"]
    params, results = run_weekly(feats, games, 22, cfg, small_space(cfg, paths_))
    start = initial_params(cfg)
    changed = [p for p in paths_ if get_path(params, p) != get_path(start, p)]
    return [(r.param, r.new) for r in results if r.decision == "promoted"], changed


def _planted_seed(seed: int) -> tuple[bool, int]:
    promos, _changed = _planted(seed)
    right = "signals.sp_plus_edge.min_edge_points"
    return any(p == right and new < 4.0 for p, new in promos), sum(p != right for p, _ in promos)


def test_planted_edge_detection_and_false_promotions_over_20_seeds():
    """Measured 2026-11-09 over seeds 0-19: the planted change is promoted in 18 of 20 and
    a WRONG parameter is promoted twice (seeds 3 and 19, each in a run that also found the
    planted one). So the guards do not make a false promotion impossible: at more than twenty
    times the real volume, which gives the loop many eligible runs, it happens about once in ten
    seasons. Pinned, so a change in either number is a visible change in the loop."""
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        out = list(pool.map(_planted_seed, range(20)))
    assert sum(o[0] for o in out) == 18
    assert [seed for seed, o in enumerate(out) if o[1]] == [3, 19]  # one wrong promotion each


# --- crafted pools: one challenger, a known story ----------------------------------------


def craft(win_rate_by_week: dict[int, float], per_week: int = 40, seed: int = 3,
          spike_week: int | None = None, s1_weeks=None):
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
                dec, win = 11.0, True  # +1000
            rows.append({
                "decision_date_et": date, "decision_ts_utc": date, "event_id": eid,
                "start_time_utc": f"{date}T19:00:00Z", "neutral_site": False, "indoor": False,
                "spread_open": -1.5 if (s1_weeks is None or w in s1_weeks) else -3.5,
                "spread_now": -3.5, "total_open": 50.5, "total_now": 50.5,
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
    """A coin-flip challenger plus ONE winner at a realistic long price (+1000). A price
    that long cannot lift z to the shipped bar of 2.0 by itself, so the bar is lowered to
    0.4 to put the pool just over the line: the guard is only live near the threshold, and
    that is where this checks it. Without the winner the same data fails on z alone."""
    wins = {w: 0.5 for w in range(13)}
    feats, games = craft(wins, spike_week=2)
    res = one_run(feats, games, min_bets=100, min_graded_games_for_run=50, z_min=0.4)
    assert res.paired_z >= res.z_required          # the winner alone clears the z bar
    assert res.decision == "no_change"
    assert "one game" in res.reason
    plain = one_run(*craft(wins), min_bets=100, min_graded_games_for_run=50, z_min=0.4)
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


# --- the two guards the first review found missing ----------------------------------------------


def rare_signal_pool():
    """The champion (S5/S6 on) bets 100 shared games, coin flips. A rare signal (S1, off)
    would add 7 more bets, all winners. The two rule sets differ on those 7 games only."""
    rng = np.random.default_rng(4)
    rows, games = [], []

    def add(eid, date, shared, win):
        rows.append({
            "decision_date_et": date, "decision_ts_utc": date, "event_id": eid,
            "start_time_utc": f"{date}T19:00:00Z", "neutral_site": False, "indoor": False,
            "spread_open": -3.5 if shared else -1.5, "spread_now": -3.5,
            "total_open": 50.5, "total_now": 50.5, "wind_mph": np.nan,
            "sp_margin_home": 20.0 if shared else np.nan,
            "spread_home_point": -3.5, "spread_home_dec": DEC,
            "spread_away_point": 3.5, "spread_away_dec": DEC,
            "over_point": 50.5, "over_dec": DEC, "under_point": 50.5, "under_dec": DEC,
            "lead_minutes": 600.0,
        })
        games.append({"event_id": eid, "status": "Final", "away_score": 10,
                      "home_score": 10 + (4 if win else 3)})

    for i in range(100):
        w = i % 13
        add(f"s{i}", str((START + pd.Timedelta(days=7 * w + (i // 13) % 3)).date()), True,
            rng.random() < 0.5)
    for k, w in enumerate((2, 3, 5, 6, 8, 11, 12)):
        add(f"r{k}", str((START + pd.Timedelta(days=7 * w)).date()), False, True)
    return pd.DataFrame(rows), pd.DataFrame(games)


def test_a_rare_signal_cannot_buy_a_promotion_on_the_bets_it_shares():
    feats, games = rare_signal_pool()
    shipped = one_run(feats, games, min_bets=60, min_graded_games_for_run=50)
    assert shipped.decision != "promoted"
    assert "min_diff_bets" in shipped.reason
    # The guard is the only thing standing: with it out of the way the same pool promotes.
    loose = one_run(feats, games, min_bets=60, min_graded_games_for_run=50, min_diff_bets=1)
    assert loose.decision == "promoted", loose.reason
    assert loose.paired_z >= loose.z_required


def test_a_challenger_identical_to_the_champion_in_the_holdout_is_rejected():
    # S1 fires only in weeks 0-9, so in the newest 3 weeks the challenger bets nothing,
    # exactly like the champion: the holdout confirms nothing, however good training looked.
    wins = {w: 0.65 for w in range(13)}
    res = one_run(*craft(wins, s1_weeks=set(range(10))), min_bets=100,
                  min_graded_games_for_run=50)
    assert res.paired_z >= res.z_required
    assert res.decision == "no_change"
    assert "holdout has no game where it differs" in res.reason
