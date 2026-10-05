"""Grade single college-baseball picks against stored finals.

Settlement (selection is a team for ml/rl, "Over"/"Under" for totals; teams
resolve to a side via matching.side, so "LSU Tigers" grades against "LSU"):
  ml     — selection wins outright (no ties in college baseball).
  rl     — selection margin + line; exactly 0 = push (whole-number lines).
  total  — combined runs vs line; exact = push.
  void   — Postponed/Canceled game. Suspended games stay pending: college
           baseball resumes them, and the resumed result is the final.
Run-rule finals (e.g. "FINAL/7") are official results and grade as played;
sportsbooks' own shortened-game rules for totals are not modeled.

Profit at stake S: win -> S * (decimal - 1); loss -> -S; push/void -> 0.
"""

from __future__ import annotations

import pandas as pd

from ..timeutil import now_utc, utc_iso
from . import store
from .matching import side


def grade_pick(
    market: str,
    selection: str,
    line: float | None,
    game: dict,
    aliases: dict[str, str] | None = None,
) -> tuple[str, str] | None:
    """Return (status, final_score) or None when the game has no result yet."""
    status = str(game.get("status"))
    if status in ("Postponed", "Canceled"):
        return "void", ""
    hs, as_ = game.get("home_score"), game.get("away_score")
    if status != "Final" or hs is None or as_ is None or pd.isna(hs) or pd.isna(as_):
        return None
    hs, as_ = int(hs), int(as_)
    final = f"{game['away_team']} {as_} - {game['home_team']} {hs}"

    if market == "total":
        line = float(line)
        total = hs + as_
        if total == line:
            return "push", final
        over = str(selection).lower().startswith("over")
        return ("win" if (total > line) == over else "loss"), final

    margin = hs - as_ if side(selection, game, aliases) == "home" else as_ - hs
    if market == "ml":
        return ("win" if margin > 0 else "loss"), final
    if market == "rl":
        adjusted = margin + float(line)
        if adjusted == 0:
            return "push", final
        return ("win" if adjusted > 0 else "loss"), final
    raise ValueError(f"unknown market {market!r}")


def grade_pending(aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """Settle every pending pick whose game has a result. Returns the newly
    settled picks."""
    picks, games = store.load_picks(), store.load_games()
    if picks.empty:
        return pd.DataFrame()
    picks = picks.astype({"status": object, "final_score": object, "settled_ts_utc": object})
    games_by_id = {str(r["game_id"]): r for r in games.to_dict("records")}
    ts = utc_iso(now_utc())
    settled = []
    for i, p in picks[picks["status"] == "pending"].iterrows():
        game = games_by_id.get(str(p["game_id"]))
        if game is None:
            continue
        out = grade_pick(p["market"], p["selection"], p["line"], game, aliases)
        if out is None:
            continue
        status, final = out
        stake = float(p["stake"])
        profit = {"win": round(stake * (float(p["price_decimal"]) - 1), 2), "loss": -stake}
        picks.at[i, "status"] = status
        picks.at[i, "final_score"] = final
        picks.at[i, "settled_ts_utc"] = ts
        picks.at[i, "profit"] = profit.get(status, 0.0)
        settled.append(picks.loc[i])
    store.save_picks(picks)
    return pd.DataFrame(settled)
