"""reports/NCAAF_REPORT.md — the NCAAF strategies' ledger, regenerated from
data/ncaaf/tickets/ on every `ncaaf report` (the CSVs are the source of
truth). Kept out of BETTING_REPORT.md, which is the MLB ledger.

Per strategy: the registration (hypothesis, lineage, pre-registered screen),
tickets pooled by hash_lineage (other hashes render as separate SCREEN
segments, as in the MLB report), every qualifying leg as a flat-stake
single bet, every qualifying leg graded per signal against the -110
breakeven, and the decision log.
"""

from __future__ import annotations

import pandas as pd

from .. import paths
from ..timeutil import now_utc, utc_iso
from . import store
from .config import load_ncaaf_strategies

LEG_BREAKEVEN = 100 / 210  # win rate that breaks even at -110


def _record(statuses: pd.Series) -> tuple[int, int, int]:
    return int((statuses == "win").sum()), int((statuses == "loss").sum()), int(
        (statuses == "push").sum()
    )


def _leg_decimal(row: dict) -> float:
    """A leg's decimal price: the stored one, else from American, else -110."""
    for key in ("price_decimal", "price_american"):
        v = pd.to_numeric(row.get(key), errors="coerce")
        if pd.notna(v):
            if key == "price_decimal":
                return float(v)
            return 1 + (v / 100 if v > 0 else 100 / -v)
    return 1 + 100 / 110


def single_profit(row: dict, stake: float) -> float | None:
    """Profit of one qualifying leg as a straight bet; None until settled."""
    status = row.get("status")
    if status == "win":
        return round(stake * (_leg_decimal(row) - 1), 2)
    if status == "loss":
        return -float(stake)
    if status == "push":
        return 0.0
    return None


def single_bet_stats(quals: pd.DataFrame, stake: float) -> dict:
    """Every qualifying leg as a flat-stake straight bet (descriptive: the
    strategy's own bet is the ticket). A push returns the stake; a void leg
    (game not played) leaves the sample, as on the MLB ledger."""
    rows = [r for r in quals.to_dict("records") if r.get("status") != "void"]
    profits = [single_profit(r, stake) for r in rows]
    settled = [(r, pr) for r, pr in zip(rows, profits, strict=True) if pr is not None]
    statuses = pd.Series([r["status"] for r, _ in settled], dtype=object)
    w, lo, p = _record(statuses)
    staked = float(stake) * len(settled)
    profit = round(sum(pr for _, pr in settled), 2)
    return {
        "n": len(rows),
        "record": {"wins": w, "losses": lo, "pushes": p},
        "pending": len(rows) - len(settled),
        "staked": staked,
        "profit": profit,
        "roi": round(100 * profit / staked, 2) if staked else None,
    }


def leg_label(selection, market, line) -> str:
    """'BYU Cougars -6.5' for a spread, 'Under 47.5' for a total."""
    v = pd.to_numeric(line, errors="coerce")
    if pd.isna(v):
        return str(selection)
    return f"{selection} {float(v):+g}" if market == "spread" else f"{selection} {float(v):g}"


def _ticket_block(t: pd.DataFrame) -> list[str]:
    settled = t[t["status"].isin(["win", "loss", "push"])]
    w, lo, p = _record(settled["status"])
    staked = settled["stake"].astype(float).sum()
    profit = settled["profit"].astype(float).sum()
    roi = f"{100 * profit / staked:+.1f}%" if staked else "n/a"
    pending = int((t["status"] == "pending").sum())
    return [
        f"- Tickets: {len(t)} ({w}-{lo}-{p} W-L-P, {pending} pending)",
        f"- Staked ${staked:,.0f}, profit ${profit:+,.2f}, ROI {roi}",
    ]


def _strategy_section(sid: str, cfg: dict) -> list[str]:
    meta, screen = cfg["strategy"], cfg.get("screen") or {}
    tickets = store.load_tickets()
    tickets = tickets[tickets["strategy_id"] == sid]
    legs = store.load_legs()
    quals = store.load_qualifiers()
    quals = quals[quals["strategy_id"] == sid]
    decisions = store.load_decisions()
    decisions = decisions[decisions["strategy_id"] == sid]
    lineage = [str(h) for h in meta.get("hash_lineage") or []]

    out = [
        f"## {sid}",
        "",
        f"**{meta['kind']}**, registered {meta['registered_at']}, "
        f"{'enabled' if meta.get('enabled') else 'disabled'}. "
        f"Hash lineage: {', '.join(lineage) or 'none'}.",
        "",
        f"> {' '.join(str(meta.get('hypothesis', '')).split())}",
        "",
        "**Pre-registered evaluation:** "
        + ("no verdict (SCREEN only). " if cfg.get("verdict") is None else "")
        + f"Ticket checkpoints {screen.get('checkpoints', [])}; "
        f"qualifying-leg checkpoints {screen.get('leg_checkpoints', [])}. "
        "A 3-leg ticket at -110 legs pays +596, so tickets break even at a "
        "14.4% hit rate; single legs at 52.4%.",
        "",
        "### Tickets",
        "",
    ]
    if tickets.empty:
        n_legs = (cfg.get("ticket") or {}).get("legs_per_ticket", 3)
        out += [f"No tickets yet: a ticket needs {n_legs} qualifying legs from "
                "different games. See Single bets and Decisions below.", ""]
    else:
        in_lineage = tickets["config_hash"].astype(str).isin(lineage)
        out += ["**In lineage:**", ""] + _ticket_block(tickets[in_lineage]) + [""]
        for h, seg in tickets[~in_lineage].groupby(tickets["config_hash"].astype(str)):
            out += [f"**SCREEN segment {h}** (outside the lineage; descriptive only):", ""]
            out += _ticket_block(seg) + [""]
        out += [
            "| Date | Legs | Price | Status | Profit |",
            "|---|---|---|---|---|",
        ]
        for t in tickets.sort_values("game_date_et", ascending=False).to_dict("records"):
            tl = legs[legs["ticket_id"].astype(str) == str(t["ticket_id"])].sort_values("leg_no")
            desc = "<br>".join(
                f"{r['selection']} {float(r['line']):+g} ({r['status']})"
                if r["market"] == "spread"
                else f"{r['selection']} {float(r['line']):g} ({r['status']})"
                for r in tl.to_dict("records")
            )
            profit = "" if pd.isna(t["profit"]) else f"${float(t['profit']):+,.2f}"
            out.append(
                f"| {t['game_date_et']} | {desc} | {float(t['price_american']):+g} "
                f"| {t['status']} | {profit} |"
            )
        out.append("")

    stake = float((cfg.get("staking") or {}).get("flat_stake", 100))
    out += ["### Single bets", ""]
    if quals.empty:
        out += ["No qualifying legs yet.", ""]
    else:
        st = single_bet_stats(quals, stake)
        rec = st["record"]
        roi = f"{st['roi']:+.1f}%" if st["roi"] is not None else "n/a"
        out += [
            f"Every qualifying leg as a ${stake:,.0f} straight bet at its "
            "best-available price (break-even 52.4% at -110). Descriptive: the "
            "strategy's bet is still the ticket.",
            "",
            f"- Singles: {st['n']} ({rec['wins']}-{rec['losses']}-{rec['pushes']} "
            f"W-L-P, {st['pending']} pending)",
            f"- Staked ${st['staked']:,.0f}, profit ${st['profit']:+,.2f}, ROI {roi}",
            "",
            "| Date | Pick | Matchup | Price | Signals | Result | P/L |",
            "|---|---|---|---|---|---|---|",
        ]
        recent = quals.sort_values(["game_date_et", "start_time_utc"], ascending=False)
        for r in recent.head(30).to_dict("records"):
            pa = pd.to_numeric(r.get("price_american"), errors="coerce")
            pr = single_profit(r, stake)
            out.append(
                f"| {r['game_date_et']} | {leg_label(r['selection'], r['market'], r['line'])} "
                f"| {r['matchup']} | {'' if pd.isna(pa) else f'{float(pa):+g}'} "
                f"| {r['signal_ids']} | {r['status']} "
                f"| {'' if pr is None else f'${pr:+,.2f}'} |"
            )
        out.append("")

    out += ["### Qualifying legs by signal", ""]
    if quals.empty:
        out += ["No qualifying legs yet.", ""]
    else:
        out += [
            "Every leg the engine found qualifying, on the ticket or not, graded "
            "at its best-available line. A leg fired by several signals counts "
            "under each.",
            "",
            "| Signal | Legs | W-L-P | Win % | vs 52.4% |",
            "|---|---|---|---|---|",
        ]
        exploded = quals.assign(signal=quals["signal_ids"].astype(str).str.split("+")).explode(
            "signal"
        )
        for sig, g in sorted(exploded.groupby("signal"), key=lambda kv: kv[0]):
            w, lo, p = _record(g["status"])
            n = w + lo
            rate = f"{100 * w / n:.1f}%" if n else "n/a"
            delta = f"{100 * (w / n - LEG_BREAKEVEN):+.1f} pts" if n else ""
            out.append(f"| {sig} | {len(g)} | {w}-{lo}-{p} | {rate} | {delta} |")
        out.append("")

    out += ["### Decisions", ""]
    if decisions.empty:
        out += ["No decisions yet.", ""]
    else:
        counts = decisions["status"].value_counts()
        out += [", ".join(f"{k}: {v}" for k, v in counts.items()), ""]
        out += ["| Date | Decision | Reason |", "|---|---|---|"]
        for d in decisions.sort_values("game_date_et", ascending=False).head(14).to_dict(
            "records"
        ):
            out.append(f"| {d['game_date_et']} | {d['status']} | {d['reason']} |")
        out.append("")
    return out


def write_report() -> str:
    lines = [
        "# NCAAF strategies",
        "",
        f"_Generated {utc_iso(now_utc())} by `panthera-mvp ncaaf report` from "
        "`data/ncaaf/tickets/`. Do not edit._",
        "",
        "Paper trades only: flat stakes, no real money. Intake record and the "
        "author's answers: `docs/strategy-intake/`.",
        "",
    ]
    for sid, cfg in load_ncaaf_strategies().items():
        lines += _strategy_section(sid, cfg)
    text = "\n".join(lines).rstrip() + "\n"
    path = paths.ncaaf_report_md()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path)
