"""Synthetic slates for the lab's evals: features, final scores and the weekly loop.

Outcomes are generated from stated probabilities, so a test knows the truth the
optimizer is supposed to find (or not to invent).
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from panthera_mvp.lab import climb
from panthera_mvp.lab.config import initial_params, load_lab_config

DEC = 1.9091  # -110
START = pd.Timestamp("2026-09-05")


def synth(seed: int, weeks: int, per_week: int, p_home_cover=None, p_over=0.5,
          dec: float = DEC):
    """(features, games). p_home_cover(edge) -> probability the home side covers; edge is
    SP+ margin plus the spread (positive = SP+ likes the home side). Default: fair coin."""
    rng = np.random.default_rng(seed)
    n = weeks * per_week
    week = np.repeat(np.arange(weeks), per_week)
    day = week * 7 + rng.integers(0, 3, n)
    dates = (START + pd.to_timedelta(day, unit="D")).strftime("%Y-%m-%d")
    sn = rng.integers(-21, 21, n) + 0.5
    so = sn + rng.choice([0, 0, 0, 1, -1, 2, -2], n)
    tn = rng.integers(40, 70, n) + 0.5
    to = tn + rng.choice([0, 0, 0, 1, -1, 2.5, -2.5], n)
    edge = rng.uniform(-14, 14, n)
    rank = lambda: np.where(rng.random(n) < 0.15, rng.integers(1, 26, n).astype(float), np.nan)  # noqa: E731
    eid = np.array([f"{seed}-{i}" for i in range(n)])
    feats = pd.DataFrame({
        "decision_date_et": dates, "decision_ts_utc": dates, "event_id": eid,
        "start_time_utc": [f"{d}T19:00:00Z" for d in dates],
        "home_team": "H", "away_team": "A", "neutral_site": False, "indoor": False,
        "spread_open": so, "spread_now": sn, "total_open": to, "total_now": tn,
        "wind_mph": rng.choice([np.nan, 5.0, 10.0, 16.0, 20.0], n),
        "sp_margin_home": edge - sn,
        "home_prev_beat_rank": rank(), "away_prev_beat_rank": rank(),
        "home_next_opp_rank": rank(), "away_next_opp_rank": rank(),
        "spread_home_point": sn, "spread_home_dec": dec,
        "spread_away_point": -sn, "spread_away_dec": dec,
        "over_point": tn, "over_dec": dec, "under_point": tn, "under_dec": dec,
        "lead_minutes": 600.0,
    })
    p_home = np.full(n, 0.5) if p_home_cover is None else np.array([p_home_cover(e) for e in edge])
    cover = rng.random(n) < p_home
    k = rng.integers(0, 9, n)
    margin = np.where(cover, np.ceil(-sn) + k, np.floor(-sn) - k).astype(int)
    over = rng.random(n) < p_over
    j = rng.integers(0, 7, n)
    total = np.where(over, np.ceil(tn) + j, np.floor(tn) - j).astype(int)
    total = np.where((total - margin) % 2 != 0, np.where(over, total + 1, total - 1), total)
    games = pd.DataFrame({
        "event_id": eid, "status": "Final",
        "home_score": (total + margin) // 2, "away_score": (total - margin) // 2,
    })
    return feats, games


def small_space(cfg: dict, paths: list[str]) -> list[dict]:
    return [i for i in cfg["space"] if i["path"] in paths]


def run_weekly(feats, games, weeks: int, cfg: dict, space=None, guards=None, start_week: int = 4):
    """Replay the weekly loop: at the end of week w the run sees only the data up to w.
    Returns (final champion params, list of RunResult)."""
    space = space if space is not None else cfg["space"]
    guards = guards or cfg["guards"]
    params = initial_params(cfg)
    trials = 0
    results = []
    full = climb.prepare(feats, games)
    day0 = int(START.to_datetime64().astype("datetime64[D]").astype(int))
    for w in range(start_week, weeks + 1):
        k = int((full.day < day0 + 7 * w).sum())
        res = climb.walk_prepared(full.head(k), params, space, guards, {"trials_total": trials})
        trials = res.trials_total
        results.append(res)
        if res.decision == "promoted":
            params = res.new_params
    return params, results


def eval_config(**guard_overrides) -> dict:
    cfg = copy.deepcopy(load_lab_config("ncaaf"))
    cfg["guards"].update(guard_overrides)
    return cfg
