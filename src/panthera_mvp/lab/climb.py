"""The weekly walk: one parameter changes, the data decides, and most weeks nothing does.

Evaluator `lab_eval_v1`. Straight bets, $100 flat = 1 unit, best-available price,
one bet per game. A challenger (the champion with ONE parameter moved) replaces
the champion only when every guard holds:

  1. n    it has at least guards.min_bets graded bets in the training window.
  2. diff it differs from the champion on at least guards.min_diff_bets games: the z
          below rests only on those, however many bets the two share.
  3. z    its paired profit difference to the champion, over the games where either
          places a bet, has z >= max(guards.z_min, sqrt(2 ln trials_total)). The
          second term is a multiple-testing penalty in the spirit of Harvey, Liu and
          Zhu (2016); it is a heuristic, not a proof. trials_total counts every
          challenger ever evaluated, this run's included.
  4. one  the z still reaches that same required bar after the single best game is
          dropped.
  5. hold the newest guards.holdout_weeks, which did not pick the challenger, contain
          at least one game where the two differ and score the challenger strictly
          above the champion (mean profit per game where either bets). The window
          slides weekly, so last week's holdout is this week's training: it is a
          confirmation, not an untouched test set.
  6. one  at most one promotion per run, one parameter per challenger.

ROI is reported raw (mean profit per bet). It is not shrunk: a shrinkage target would
have to be the no-skill return at the bet prices (about -4.5% at -110), not zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import EVAL_VERSION
from .config import get_path, set_path
from .ncaaf_rules import Arrays, qualify_core, qualify_frame, select_bets, select_core, settle_core

NAN = float("nan")


# --- data ----------------------------------------------------------------------


@dataclass
class Prepared:
    """Feature rows joined to final scores, parsed once and reused by every sim.
    Rows are sorted by decision date, kickoff, event id, so a row's position is
    the deterministic tie-break inside a day."""

    rows: pd.DataFrame
    arrays: Arrays
    hs: np.ndarray
    as_: np.ndarray
    final: np.ndarray
    dates: np.ndarray       # ET decision date strings
    day: np.ndarray         # the same as whole days (int), for ranking and the skip rule
    n: int = field(init=False)

    def __post_init__(self) -> None:
        self.n = len(self.rows)

    def head(self, k: int) -> Prepared:
        """The first k rows: with rows sorted by date, the data as of an earlier day."""
        return Prepared(self.rows.iloc[:k], self.arrays.head(k), self.hs[:k], self.as_[:k],
                        self.final[:k], self.dates[:k], self.day[:k])


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
    dates = rows["decision_date_et"].astype(str).to_numpy()
    day = pd.to_datetime(rows["decision_date_et"]).to_numpy().astype("datetime64[D]").astype(int)
    return Prepared(rows, Arrays(rows), hs, aw, final, dates, day)


@dataclass
class SimResult:
    profit: np.ndarray       # per feature row: units won or lost; 0 where no resolved bet
    placed: np.ndarray       # per feature row: a resolved bet was placed
    bets: pd.DataFrame | None = None   # selected bets with `profit` (simulate() only)


def simulate_prepared(prep: Prepared, params: dict) -> SimResult:
    """The hot path: pure numpy, no DataFrames."""
    core = qualify_core(prep.arrays, params)
    sel = select_core(core, prep.day, params)
    profit = np.zeros(prep.n)
    placed = np.zeros(prep.n, dtype=bool)
    if sel.size == 0:
        return SimResult(profit, placed)
    p = settle_core(core, sel, prep.hs, prep.as_, prep.final)
    pos = core.idx[sel]
    if params.get("bet_limits", {}).get("skip_day_after_loss"):
        keep = _days_to_keep(prep.day[pos], p)
        pos, p = pos[keep], p[keep]
    ok = ~np.isnan(p)
    profit[pos[ok]] = p[ok]
    placed[pos[ok]] = True
    return SimResult(profit, placed)


def _days_to_keep(day: np.ndarray, profit: np.ndarray) -> np.ndarray:
    """Drop a day's bets when the previous calendar day's resolved bets lost money."""
    keep = np.ones(len(day), dtype=bool)
    net: dict[int, float] = {}
    for d in np.unique(day):
        m = day == d
        if net.get(int(d) - 1, 0.0) < 0:
            keep[m] = False
            net[int(d)] = 0.0
        else:
            net[int(d)] = float(np.nansum(profit[m]))
    return keep


def simulate(rows: pd.DataFrame, games: pd.DataFrame, params: dict) -> SimResult:
    """Readable form of the same simulation: also returns the selected bets as a frame.
    Built from the DataFrame rules path, so tests can hold it to the hot path."""
    prep = prepare(rows, games)
    res = simulate_prepared(prep, params)
    bets = select_bets(qualify_frame(prep.rows, params, prep.arrays), params).copy()
    if not bets.empty:
        core = qualify_core(prep.arrays, params)
        sel = select_core(core, prep.day, params)
        bets["profit"] = settle_core(core, sel, prep.hs, prep.as_, prep.final)
    else:
        bets["profit"] = []
    res.bets = bets
    return res


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
    prep = prepare(rows, games) if len(rows) else None
    return walk_prepared(prep, champion, space, guards, ledger_state)


def walk_prepared(
    prep: Prepared | None,
    champion: dict,
    space: list[dict],
    guards: dict,
    ledger_state: dict | None = None,
) -> RunResult:
    before = int((ledger_state or {}).get("trials_total", 0))
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
    _cn, c_roi = roi(champ, train_pool)
    _hn, hc_roi = roi(champ, hold_pool)
    cands = neighbours(champion, space)
    res.n_neighbours = len(cands)
    res.trials_total = before + len(cands)
    res.z_required = z_required(guards, res.trials_total)
    res.champion_roi = c_roi
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
        n_diff = int(np.count_nonzero(d))
        if (n_k >= int(guards["min_bets"]) and n_diff >= int(guards["min_diff_bets"])
                and (best is None or z > best[0])):
            best = entry

    if best is None:
        res.reason = (f"no challenger has min_bets={guards['min_bets']} graded bets and "
                      f"min_diff_bets={guards['min_diff_bets']} games that differ from the "
                      f"champion in training"
                      + (f" (highest z {_fmt(best_any[0])} on {best_any[8]} bets, "
                         f"{int(np.count_nonzero(best_any[7]))} differing, "
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
    if z_wo < res.z_required:
        res.reason = (f"best challenger {tag}: driven by one game (z {_fmt(z)} falls to "
                      f"{_fmt(z_wo)} without it, required {_fmt(res.z_required)})")
        return res
    if not hold_pool.any():
        res.reason = f"best challenger {tag}: no holdout games to confirm it"
        return res
    hold_union = hold_pool & (sim.placed | champ.placed)
    diff_hold = sim.profit[hold_union] - champ.profit[hold_union]
    if int(np.count_nonzero(diff_hold)) == 0:
        res.reason = (f"best challenger {tag}: the holdout has no game where it differs from "
                      f"the champion, so it confirms nothing")
        return res
    if float(np.mean(diff_hold)) <= 0:
        res.reason = (f"best challenger {tag}: holdout not better than the champion "
                      f"(mean difference {_fmt(float(np.mean(diff_hold)))} per game where "
                      f"either bets, on {diff_hold.size} games)")
        return res
    res.decision = "promoted"
    res.reason = (f"{tag}: z {_fmt(z)} >= {_fmt(res.z_required)}, {_fmt(z_wo)} without the "
                  f"best game, holdout better ({_fmt(float(np.mean(diff_hold)))} per game)")
    res.new_params = params
    return res


def _fill(res, entry, guards, champ, train_pool, hold_pool) -> None:
    z, _o, path, old, new, _params, sim, _d, n_k = entry
    res.param, res.old, res.new = path, old, new
    res.paired_z = z
    res.train_n = n_k
    _n, res.challenger_roi = roi(sim, train_pool)
    _n, res.holdout_challenger_roi = roi(sim, hold_pool)


def forward_summary(prep: Prepared, params: dict, effective_from: str) -> dict:
    """The champion replayed over decision days on or after effective_from."""
    sim = simulate_prepared(prep, params)
    mask = prep.final & (prep.dates >= effective_from)
    n, mean = roi(sim, mask)
    return {"n_bets": n, "units": float(sim.profit[sim.placed & mask].sum()),
            "roi": mean, "eval_version": EVAL_VERSION}
