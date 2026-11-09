"""The weekly walk: one parameter changes, the data decides, and most weeks nothing does.

Evaluator `lab_eval_v1`. Straight bets, $100 flat = 1 unit, best-available price,
one bet per game. A challenger (the champion with ONE parameter moved) replaces
the champion only when every guard holds:

  1. n    it has at least guards.min_bets graded bets in the training window.
  2. z    its paired profit difference to the champion, over the games where either
          places a bet, has z >= max(guards.z_min, sqrt(2 ln trials_total)). The
          second term is a multiple-testing penalty in the spirit of Harvey, Liu and
          Zhu (2016); it is a heuristic, not a proof. trials_total counts every
          challenger ever evaluated, this run's included.
  3. one  the z still reaches guards.z_min after the single best game is dropped.
  4. hold the newest guards.holdout_weeks, which never picked the challenger, do not
          score it below the champion (mean profit per pool game).
  5. one  at most one promotion per run, one parameter per challenger.

The shrunk ROI (roi * n / (n + shrink_pseudo_bets)) is reported next to the raw one.
The 625 pseudo-bets are an assumption (a prior SD of 2 points on a true win rate),
not a measurement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import EVAL_VERSION
from .config import get_path, set_path
from .ncaaf_rules import Arrays, qualify_frame, select_bets, settle_bets

NAN = float("nan")


# --- data ----------------------------------------------------------------------


@dataclass
class Prepared:
    """Feature rows joined to final scores, parsed once and reused by every sim."""

    rows: pd.DataFrame
    arrays: Arrays
    hs: np.ndarray
    as_: np.ndarray
    final: np.ndarray
    dates: np.ndarray
    n: int = field(init=False)

    def __post_init__(self) -> None:
        self.n = len(self.rows)


def prepare(rows: pd.DataFrame, games: pd.DataFrame) -> Prepared:
    rows = rows.copy()
    rows["event_id"] = rows["event_id"].astype(str)
    rows = rows.sort_values(["decision_date_et", "start_time_utc", "event_id"], kind="mergesort")
    rows = rows.drop_duplicates("event_id", keep="first").reset_index(drop=True)
    g = games.copy()
    g["event_id"] = g["event_id"].astype(str)
    g = g.drop_duplicates("event_id", keep="last").set_index("event_id")
    hs = pd.to_numeric(rows["event_id"].map(g["home_score"]), errors="coerce").to_numpy(float)
    aw = pd.to_numeric(rows["event_id"].map(g["away_score"]), errors="coerce").to_numpy(float)
    status = rows["event_id"].map(g["status"]).astype(str).to_numpy()
    final = (status == "Final") & ~np.isnan(hs) & ~np.isnan(aw)
    return Prepared(rows, Arrays(rows), hs, aw, final, rows["decision_date_et"].astype(str).to_numpy())


@dataclass
class SimResult:
    bets: pd.DataFrame       # selected bets with a `profit` column (NaN = unresolved)
    profit: np.ndarray       # per-row profit in units; 0 where no resolved bet
    placed: np.ndarray       # per-row: a resolved bet was placed


def simulate_prepared(prep: Prepared, params: dict) -> SimResult:
    bets = select_bets(qualify_frame(prep.rows, params, prep.arrays), params)
    profit = np.zeros(prep.n)
    placed = np.zeros(prep.n, dtype=bool)
    if bets.empty:
        return SimResult(bets.assign(profit=[]), profit, placed)
    bets = bets.copy()
    bets["profit"] = settle_bets(bets, prep.hs, prep.as_, prep.final)
    if params.get("bet_limits", {}).get("skip_day_after_loss"):
        bets = _skip_days_after_loss(bets)
    ok = bets["profit"].notna().to_numpy()
    pos = bets["pos"].to_numpy(dtype=int)[ok]
    profit[pos] = bets["profit"].to_numpy()[ok]
    placed[pos] = True
    return SimResult(bets, profit, placed)


def _skip_days_after_loss(bets: pd.DataFrame) -> pd.DataFrame:
    """Drop a day's bets when the previous ET day's resolved bets lost money."""
    dates = bets["decision_date_et"].to_numpy()
    prof = bets["profit"].to_numpy(dtype=float)
    keep = np.ones(len(bets), dtype=bool)
    net: dict[str, float] = {}
    for d in sorted(set(dates)):
        prev = str((pd.Timestamp(d) - pd.Timedelta(days=1)).date())
        m = dates == d
        if net.get(prev, 0.0) < 0:
            keep[m] = False
            net[d] = 0.0
        else:
            net[d] = float(np.nansum(prof[m]))
    return bets[keep]


def simulate(rows: pd.DataFrame, games: pd.DataFrame, params: dict) -> SimResult:
    return simulate_prepared(prepare(rows, games), params)


# --- statistics ------------------------------------------------------------------


def paired_z(d: np.ndarray) -> float:
    """mean(d) / (sd(d) / sqrt(M)); 0 when it is undefined."""
    m = len(d)
    if m < 2:
        return 0.0
    sd = float(np.std(d, ddof=1))
    return 0.0 if sd == 0.0 else float(np.mean(d)) / (sd / math.sqrt(m))


def z_required(guards: dict, trials_total: int) -> float:
    return max(float(guards["z_min"]), math.sqrt(2 * math.log(max(trials_total, 1))))


def roi(res: SimResult, mask: np.ndarray) -> tuple[int, float]:
    sel = res.placed & mask
    n = int(sel.sum())
    return n, (float(res.profit[sel].sum()) / n if n else NAN)


def shrunk(value: float, n: int, pseudo: float) -> float:
    return value * n / (n + pseudo) if n and not math.isnan(value) else NAN


# --- neighbours ------------------------------------------------------------------


def _moved(old, step, direction):
    new = old + direction * step
    if isinstance(old, int) and isinstance(step, int):
        return int(new)
    return round(float(new), 6)


def neighbours(params: dict, space: list[dict]) -> list[tuple[str, object, object, dict]]:
    """(path, old, new, params) for every one-parameter change, in space order.
    A numeric parameter of a switched-off signal is skipped: moving it changes
    nothing, and a no-op trial would only inflate the multiple-testing count."""
    out = []
    for item in space:
        path = item["path"]
        parts = path.split(".")
        if parts[0] == "signals" and parts[-1] != "enabled":
            if not get_path(params, ".".join(parts[:2] + ["enabled"])):
                continue
        old = get_path(params, path)
        if "toggle" in item:
            news = [not old]
        elif "choices" in item:
            news = [c for c in item["choices"] if c != old]
        else:
            news = []
            for direction in (-1, 1):
                new = _moved(old, item["step"], direction)
                if item["min"] <= new <= item["max"]:
                    news.append(new)
        out.extend((path, old, new, set_path(params, path, new)) for new in news)
    return out


# --- the walk ----------------------------------------------------------------------


@dataclass
class RunResult:
    decision: str                      # promoted | no_change | insufficient_data
    reason: str
    n_games: int = 0                   # feature rows
    n_graded: int = 0                  # of those, with a final score
    param: str = ""
    old: object = ""
    new: object = ""
    train_n: int = 0
    champion_roi: float = NAN
    challenger_roi: float = NAN
    champion_roi_shrunk: float = NAN
    challenger_roi_shrunk: float = NAN
    paired_z: float = NAN
    z_required: float = NAN
    n_neighbours: int = 0
    trials_total: int = 0
    holdout_champion_roi: float = NAN
    holdout_challenger_roi: float = NAN
    new_params: dict | None = None


def _fmt(x: float) -> str:
    return "nan" if math.isnan(x) else f"{x:.3g}"


def walk(
    rows: pd.DataFrame,
    games: pd.DataFrame,
    champion: dict,
    space: list[dict],
    guards: dict,
    ledger_state: dict | None = None,
) -> RunResult:
    """One weekly run. `ledger_state["trials_total"]` is the count of challengers
    evaluated in earlier runs; the returned `trials_total` is the new running total."""
    before = int((ledger_state or {}).get("trials_total", 0))
    prep = prepare(rows, games) if len(rows) else None
    if prep is None or prep.n == 0:
        return RunResult("insufficient_data", "no feature rows logged yet", trials_total=before)
    res = RunResult("insufficient_data", "", n_games=prep.n, n_graded=int(prep.final.sum()),
                    trials_total=before)

    last = pd.Timestamp(prep.dates.max())
    hold_start = str((last - pd.Timedelta(days=7 * int(guards["holdout_weeks"]) - 1)).date())
    hold = prep.dates >= hold_start
    train_pool = prep.final & ~hold
    hold_pool = prep.final & hold
    if int(train_pool.sum()) < int(guards["min_graded_games_for_run"]):
        res.reason = (f"{int(train_pool.sum())} graded training games, need "
                      f"{guards['min_graded_games_for_run']} (holdout is the newest "
                      f"{guards['holdout_weeks']} weeks)")
        return res

    champ = simulate_prepared(prep, champion)
    cn, c_roi = roi(champ, train_pool)
    hn, hc_roi = roi(champ, hold_pool)
    cands = neighbours(champion, space)
    res.n_neighbours = len(cands)
    res.trials_total = before + len(cands)
    res.z_required = z_required(guards, res.trials_total)
    res.champion_roi = c_roi
    res.champion_roi_shrunk = shrunk(c_roi, cn, guards["shrink_pseudo_bets"])
    res.holdout_champion_roi = hc_roi

    best = None  # (z, order, path, old, new, params, sim, d, n)
    best_any = None
    for order, (path, old, new, params) in enumerate(cands):
        sim = simulate_prepared(prep, params)
        n_k, _ = roi(sim, train_pool)
        union = train_pool & (sim.placed | champ.placed)
        d = sim.profit[union] - champ.profit[union]
        z = paired_z(d)
        entry = (z, order, path, old, new, params, sim, d, n_k)
        if best_any is None or z > best_any[0]:
            best_any = entry
        if n_k >= int(guards["min_bets"]) and (best is None or z > best[0]):
            best = entry

    if best is None:
        res.reason = (f"no challenger reaches min_bets={guards['min_bets']} graded bets "
                      f"in training"
                      + (f" (best z {_fmt(best_any[0])} on {best_any[8]} bets, "
                         f"{best_any[2]} {best_any[3]} -> {best_any[4]})" if best_any else ""))
        if best_any:
            _fill(res, best_any, guards, champ, train_pool, hold_pool)
        return res

    _fill(res, best, guards, champ, train_pool, hold_pool)
    z, _o, path, old, new, params, sim, d, _n = best
    res.decision = "no_change"
    tag = f"{path} {old} -> {new}"
    if not (d.size and float(np.mean(d)) > 0 and z >= res.z_required):
        res.reason = (f"best challenger {tag}: z {_fmt(z)} below the required "
                      f"{_fmt(res.z_required)} (trials {res.trials_total})")
        return res
    drop = np.delete(d, int(np.argmax(d)))
    z_wo = paired_z(drop)
    if z_wo < float(guards["z_min"]):
        res.reason = (f"best challenger {tag}: driven by one game (z {_fmt(z)} falls to "
                      f"{_fmt(z_wo)} without it, floor {guards['z_min']})")
        return res
    if not hold_pool.any():
        res.reason = f"best challenger {tag}: no holdout games to confirm it"
        return res
    diff_hold = sim.profit[hold_pool] - champ.profit[hold_pool]
    if float(np.mean(diff_hold)) < 0:
        res.reason = (f"best challenger {tag}: holdout worse than the champion "
                      f"({_fmt(res.holdout_challenger_roi)} vs {_fmt(res.holdout_champion_roi)} "
                      f"per bet)")
        return res
    res.decision = "promoted"
    res.reason = (f"{tag}: z {_fmt(z)} >= {_fmt(res.z_required)}, {_fmt(z_wo)} without the "
                  f"best game, holdout not worse")
    res.new_params = params
    return res


def _fill(res, entry, guards, champ, train_pool, hold_pool) -> None:
    z, _o, path, old, new, _params, sim, _d, n_k = entry
    res.param, res.old, res.new = path, old, new
    res.paired_z = z
    res.train_n = n_k
    _n, res.challenger_roi = roi(sim, train_pool)
    res.challenger_roi_shrunk = shrunk(res.challenger_roi, n_k, guards["shrink_pseudo_bets"])
    _n, res.holdout_challenger_roi = roi(sim, hold_pool)


def forward_summary(prep: Prepared, params: dict, effective_from: str) -> dict:
    """The champion replayed over decision days on or after effective_from."""
    sim = simulate_prepared(prep, params)
    mask = prep.final & (prep.dates >= effective_from)
    n, mean = roi(sim, mask)
    return {"n_bets": n, "units": float(sim.profit[sim.placed & mask].sum()),
            "roi": mean, "eval_version": EVAL_VERSION}
