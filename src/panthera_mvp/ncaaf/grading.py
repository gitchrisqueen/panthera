"""Grade NCAAF legs and settle parlay tickets.

Leg settlement (selection is a team name for spread/moneyline, "Over"/"Under"
for totals; team names compare via matching.normalize_name + aliases):
  spread    — selection margin + line; exactly 0 = push.
  total     — combined points vs line; exact = push.
  moneyline — selection wins outright (no ties in college football — OT).
  void      — Postponed/Canceled game.

Ticket settlement (standard sportsbook parlay rules):
  any leg lost                  -> loss (settles immediately, even with
                                   other legs still pending)
  any leg still pending         -> stays pending
  otherwise, push/void legs drop out and the price is re-figured from the
  winning legs; no winning legs -> push (stake refunded).
Profit at stake S: win -> S * (settled_decimal - 1); loss -> -S; push -> 0.
"""

from __future__ import annotations

import math

import pandas as pd

from ..timeutil import now_utc, utc_iso
from . import store
from .matching import normalize_name


def grade_leg(
    market: str,
    selection: str,
    line: float | None,
    game: dict,
    aliases: dict[str, str] | None = None,
) -> tuple[str, str] | None:
    """Return (status, final_score) or None when the game has no result yet."""
    status = str(game.get("status"))
    if status in ("Postponed", "Canceled", "Cancelled"):
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

    alias = {normalize_name(k): normalize_name(v) for k, v in (aliases or {}).items()}

    def key(name: str) -> str:
        n = normalize_name(name)
        return alias.get(n, n)

    sel = key(selection)
    if sel == key(game["home_team"]):
        margin = hs - as_
    elif sel == key(game["away_team"]):
        margin = as_ - hs
    else:
        raise ValueError(f"leg selection {selection!r} is not in {final!r}")

    if market == "spread":
        adjusted = margin + float(line)
        if adjusted == 0:
            return "push", final
        return ("win" if adjusted > 0 else "loss"), final
    if market == "moneyline":
        return ("win" if margin > 0 else "loss"), final
    raise ValueError(f"unknown leg market {market!r}")


def settle_ticket(leg_statuses: list[str], leg_decimals: list[float]) -> tuple[str, float | None]:
    """Return (ticket_status, settled_decimal). settled_decimal is None while
    pending or on a loss."""
    if "loss" in leg_statuses:
        return "loss", None
    if "pending" in leg_statuses:
        return "pending", None
    winners = [d for s, d in zip(leg_statuses, leg_decimals, strict=True) if s == "win"]
    if not winners:
        return "push", 1.0
    return "win", round(math.prod(winners), 4)


def grade_pending(aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """Grade every pending leg with a result, then settle tickets. Returns the
    newly settled tickets."""
    tickets, legs, games = store.load_tickets(), store.load_legs(), store.load_games()
    if tickets.empty or legs.empty:
        return pd.DataFrame()
    legs = legs.astype({"status": object, "final_score": object})
    tickets = tickets.astype({"status": object, "settled_ts_utc": object})
    games_by_id = {str(r["event_id"]): r for r in games.to_dict("records")}

    for i, leg in legs[legs["status"] == "pending"].iterrows():
        game = games_by_id.get(str(leg["event_id"]))
        if game is None:
            continue
        out = grade_leg(leg["market"], leg["selection"], leg["line"], game, aliases)
        if out is not None:
            legs.at[i, "status"], legs.at[i, "final_score"] = out

    settled = []
    ts = utc_iso(now_utc())
    for i, t in tickets[tickets["status"] == "pending"].iterrows():
        tl = legs[legs["ticket_id"].astype(str) == str(t["ticket_id"])].sort_values("leg_no")
        status, dec = settle_ticket(
            tl["status"].tolist(), tl["price_decimal"].astype(float).tolist()
        )
        if status == "pending":
            continue
        stake = float(t["stake"])
        profit = -stake if status == "loss" else round(stake * (dec - 1), 2)
        tickets.at[i, "status"] = status
        tickets.at[i, "settled_ts_utc"] = ts
        tickets.at[i, "settled_price_decimal"] = dec
        tickets.at[i, "profit"] = profit
        settled.append(tickets.loc[i])

    store.save_legs(legs)
    store.save_tickets(tickets)
    return pd.DataFrame(settled)
