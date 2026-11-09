"""NCAAF signals S1-S6 over logged feature rows, with a parameter dict.

The same decision function as ncaaf/parlay.py (`game_signals` + `qualify`), but
vectorised over many rows and driven by a params dict, so one pass can score a
challenger over a whole season of logged features. tests/test_lab_ncaaf_parity.py
holds the two to the same qualifying legs on the engine's fixtures; if they
ever disagree, this module is the one that is wrong.

Params (same keys as the strategy YAML where one exists):
  min_lead_minutes
  signals.line_move_spread {enabled, min_points}     S1  bet with the move
  signals.line_move_total  {enabled, min_points}     S2  over if up, under if down
  signals.letdown          {enabled, min_fav_points, max_rank}   S3  fade the favourite
  signals.look_ahead       {enabled, min_fav_points, max_rank}   S4  fade the favourite
  signals.weather_wind_under {enabled, min_wind_mph}  S5  under
  signals.sp_plus_edge     {enabled, min_edge_points}  S6  the side SP+ favours
  legs.min_signals
  ticket.max_bets_per_day, ticket.max_price_american, ticket.rank_by
  bet_limits.skip_day_after_loss

The home-field constant for SP+ lives in the lab config's `feature` block (it
shapes the logged `sp_margin_home`), not in params.

One bet per game: the market with more signals, a tie going to the spread.
Opposite sides inside one market skip the game. A bet whose best price is worse
than ticket.max_price_american is dropped BEFORE ranking and capping, so a
dropped bet never uses up a daily slot.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SPREAD_IDS = ("S1", "S3", "S4", "S6")
TOTAL_IDS = ("S2", "S5")
SIGNAL_ORDER = ("S1", "S2", "S3", "S4", "S5", "S6")

BET_COLUMNS = [
    "pos", "event_id", "decision_date_et", "start_time_utc", "market", "side",
    "line", "price_decimal", "signal_ids", "n_signals", "strength",
]


class Arrays:
    """The numeric columns of a feature frame, parsed once."""

    def __init__(self, df: pd.DataFrame):
        n = len(df)
        self.n = n

        def f(col: str) -> np.ndarray:
            if col not in df.columns:
                return np.full(n, np.nan)
            return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)

        self.so, self.sn = f("spread_open"), f("spread_now")
        self.to, self.tn = f("total_open"), f("total_now")
        self.wind, self.sp = f("wind_mph"), f("sp_margin_home")
        self.hpb, self.apb = f("home_prev_beat_rank"), f("away_prev_beat_rank")
        self.hno, self.ano = f("home_next_opp_rank"), f("away_next_opp_rank")
        self.lead = f("lead_minutes")
        self.price = {k: (f(f"{k}_point"), f(f"{k}_dec"))
                      for k in ("spread_home", "spread_away", "over", "under")}
        ind = df["indoor"] if "indoor" in df.columns else [None] * n
        self.outdoor = np.array([str(v).strip().lower() == "false" for v in ind], dtype=bool)


def _signals(a: Arrays, p: dict) -> list[tuple[str, str, np.ndarray, np.ndarray, np.ndarray]]:
    """(id, market, fire, code, ratio) per enabled signal. code +1 = home / over,
    -1 = away / under. ratio = how far past its threshold the signal fired."""
    s = p["signals"]
    out = []
    with np.errstate(invalid="ignore", divide="ignore"):
        c = s["line_move_spread"]
        if c["enabled"]:
            move = a.sn - a.so  # negative = toward home
            out.append(("S1", "spread", np.abs(move) >= c["min_points"],
                        np.where(move < 0, 1, -1), np.abs(move) / c["min_points"]))
        c = s["line_move_total"]
        if c["enabled"]:
            move = a.tn - a.to
            out.append(("S2", "total", np.abs(move) >= c["min_points"],
                        np.where(move > 0, 1, -1), np.abs(move) / c["min_points"]))
        for sid, key, home_rank, away_rank in (
            ("S3", "letdown", a.hpb, a.apb), ("S4", "look_ahead", a.hno, a.ano),
        ):
            c = s[key]
            if not c["enabled"]:
                continue
            fav_home = a.sn <= -c["min_fav_points"]
            fav_away = a.sn >= c["min_fav_points"]
            fire_h = fav_home & (home_rank <= c["max_rank"])  # fade home -> bet away
            fire_a = fav_away & (away_rank <= c["max_rank"])  # fade away -> bet home
            out.append((sid, "spread", fire_h | fire_a, np.where(fire_h, -1, 1),
                        np.abs(a.sn) / c["min_fav_points"]))
        c = s["weather_wind_under"]
        if c["enabled"]:
            out.append(("S5", "total", a.outdoor & (a.wind >= c["min_wind_mph"]),
                        np.full(a.n, -1), a.wind / c["min_wind_mph"]))
        c = s["sp_plus_edge"]
        if c["enabled"]:
            edge = a.sp + a.sn  # SP+ expected home margin vs the market's -spread
            out.append(("S6", "spread", np.abs(edge) >= c["min_edge_points"],
                        np.where(edge > 0, 1, -1), np.abs(edge) / c["min_edge_points"]))
    return out


def _min_decimal(max_price_american) -> float:
    if max_price_american is None:
        return 0.0
    m = float(max_price_american)
    return 1 + (100 / abs(m) if m < 0 else m / 100) - 5e-4


def qualify_frame(
    df: pd.DataFrame, params: dict, arrays: Arrays | None = None
) -> pd.DataFrame:
    """Every bet the params would place on these rows, before ranking and capping."""
    if df.empty:
        return pd.DataFrame(columns=BET_COLUMNS)
    a = arrays or Arrays(df)
    sigs = _signals(a, params)
    n = a.n
    zero_i, zero_f = np.zeros(n, dtype=int), np.zeros(n)

    def market(ids: tuple[str, ...]):
        pos, neg, best = zero_i.copy(), zero_i.copy(), zero_f.copy()
        for sid, _m, fire, code, ratio in sigs:
            if sid in ids:
                pos += (fire & (code > 0)).astype(int)
                neg += (fire & (code < 0)).astype(int)
                best = np.maximum(best, np.where(fire, ratio, 0.0))
        return pos, neg, best

    ps, ns, bs = market(SPREAD_IDS)
    pt, nt, bt = market(TOTAL_IDS)
    n_s, n_t = ps + ns, pt + nt
    conflict = ((ps > 0) & (ns > 0)) | ((pt > 0) & (nt > 0))
    need = max(int(params["legs"]["min_signals"]), 1)
    ready_s, ready_t = n_s >= need, n_t >= need
    pick_spread = ready_s & (~ready_t | (n_s >= n_t))
    pick_total = ready_t & ~pick_spread
    valid = (pick_spread | pick_total) & ~conflict
    lead = float(params.get("min_lead_minutes", 0))
    valid &= ~(a.lead < lead)  # NaN lead passes, like an engine with no clock

    home_side = np.where(pick_spread, ps > 0, pt > 0)  # home or over
    line = np.full(n, np.nan)
    dec = np.full(n, np.nan)
    for key, mask in (
        ("spread_home", pick_spread & home_side), ("spread_away", pick_spread & ~home_side),
        ("over", pick_total & home_side), ("under", pick_total & ~home_side),
    ):
        pts, decs = a.price[key]
        line = np.where(mask, pts, line)
        dec = np.where(mask, decs, dec)
    keep = valid & ~np.isnan(line) & ~np.isnan(dec)
    keep &= dec >= _min_decimal(params["ticket"].get("max_price_american"))
    idx = np.flatnonzero(keep)
    if idx.size == 0:
        return pd.DataFrame(columns=BET_COLUMNS)

    fire_by = {sid: fire for sid, _m, fire, _c, _r in sigs}
    rows = []
    for i in idx:
        ids = SPREAD_IDS if pick_spread[i] else TOTAL_IDS
        fired = [s for s in SIGNAL_ORDER if s in ids and s in fire_by and fire_by[s][i]]
        rows.append({
            "pos": int(i),
            "event_id": str(df["event_id"].iloc[i]),
            "decision_date_et": str(df["decision_date_et"].iloc[i]),
            "start_time_utc": str(df["start_time_utc"].iloc[i]),
            "market": "spread" if pick_spread[i] else "total",
            "side": (("home" if home_side[i] else "away") if pick_spread[i]
                     else ("over" if home_side[i] else "under")),
            "line": float(line[i]),
            "price_decimal": float(dec[i]),
            "signal_ids": "+".join(fired),
            "n_signals": len(fired),
            "strength": float((bs if pick_spread[i] else bt)[i]),
        })
    return pd.DataFrame(rows, columns=BET_COLUMNS)


def qualify_row(row: dict, params: dict) -> list[dict]:
    """The bet (zero or one) the params place on a single feature row."""
    bets = qualify_frame(pd.DataFrame([row]), params)
    return [{k: v for k, v in r.items() if k != "pos"} for r in bets.to_dict("records")]


def select_bets(bets: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rank each ET day's bets and keep the top ticket.max_bets_per_day.
    Ties break on kickoff, then event id, so the choice is deterministic."""
    if bets.empty:
        return bets
    rank_by = params["ticket"]["rank_by"]
    if rank_by == "n_signals":
        cols, asc = (["decision_date_et", "n_signals", "start_time_utc", "event_id"],
                     [True, False, True, True])
    elif rank_by == "strength":
        cols, asc = (["decision_date_et", "strength", "n_signals", "start_time_utc", "event_id"],
                     [True, False, False, True, True])
    else:
        raise ValueError(f"unknown ticket.rank_by {rank_by!r}")
    out = bets.sort_values(cols, ascending=asc, kind="mergesort")
    cap = params["ticket"].get("max_bets_per_day")
    if cap:
        out = out[out.groupby("decision_date_et").cumcount() < int(cap)]
    return out


def settle_bets(bets: pd.DataFrame, hs: np.ndarray, as_: np.ndarray, final: np.ndarray) -> np.ndarray:
    """Profit per bet in units of a flat stake: win dec-1, loss -1, push 0, and NaN
    while the game has no final score (pending or void: excluded from ROI)."""
    pos = bets["pos"].to_numpy(dtype=int)
    h, aw, ok = hs[pos], as_[pos], final[pos]
    side = bets["side"].to_numpy()
    line = bets["line"].to_numpy(dtype=float)
    dec = bets["price_decimal"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        margin = np.where(side == "home", h - aw, aw - h)
        total = h + aw
        r_total = np.where(side == "over", total - line, line - total)
        r = np.where(bets["market"].to_numpy() == "spread", margin + line, r_total)
        profit = np.where(r > 0, dec - 1.0, np.where(r < 0, -1.0, 0.0))
    return np.where(ok, profit, np.nan)
