"""Markdown report generation.

reports/BETTING_REPORT.md is fully regenerated from data/picks/picks.csv on
every run — the CSV is the source of truth, the markdown is derived. Daily
reports live in reports/daily/YYYY-MM-DD.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paths, store
from .timeutil import now_utc, utc_iso

# Pre-registered success criteria — written into the ledger from day one so
# the experiment cannot be judgment-shifted later.
VERDICT_MIN_PICKS = 100
VERDICT_SUPPORTED_ROI = 0.0
VERDICT_FALSIFIED_ROI = -5.0


def _fmt_price(p) -> str:
    if pd.isna(p):
        return "—"
    p = float(p)
    return f"{p:+.0f}"


def _pick_label(row) -> str:
    market = row["market"]
    if market == "ml":
        return f"{row['selection']} ML"
    if market == "rl":
        return f"{row['selection']} {float(row['line']):+.1f}"
    return f"{row['selection']} {row['line']}"


def _ledger_stats(graded: pd.DataFrame) -> dict:
    wins = int((graded["status"] == "win").sum())
    losses = int((graded["status"] == "loss").sum())
    pushes = int((graded["status"] == "push").sum())
    voids = int((graded["status"] == "void").sum())
    profit = round(float(graded["profit"].sum()), 2)
    risked = float(graded.loc[graded["status"].isin(["win", "loss"]), "stake"].sum())
    roi = round(100 * profit / risked, 2) if risked else 0.0
    return {
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "voids": voids,
        "profit": profit,
        "risked": risked,
        "roi": roi,
    }


def _breakdown(graded: pd.DataFrame, column: str) -> str:
    lines = [
        f"| {column} | Record | P/L | ROI |",
        "|---|---|---|---|",
    ]
    for value, grp in graded.groupby(column, dropna=False):
        s = _ledger_stats(grp)
        lines.append(
            f"| {value} | {s['wins']}-{s['losses']}-{s['pushes']} "
            f"| ${s['profit']:+,.2f} | {s['roi']:+.2f}% |"
        )
    return "\n".join(lines)


def _verdict(stats: dict, n_graded: int) -> str:
    if n_graded < VERDICT_MIN_PICKS:
        return (
            f"**INCONCLUSIVE — collecting data.** {n_graded}/{VERDICT_MIN_PICKS} graded "
            f"picks recorded. Verdict criteria (pre-registered): after "
            f"{VERDICT_MIN_PICKS} graded picks, ROI > {VERDICT_SUPPORTED_ROI:.0f}% → "
            f"strategy SUPPORTED; ROI < {VERDICT_FALSIFIED_ROI:.0f}% → strategy "
            f"FALSIFIED; otherwise inconclusive, keep collecting."
        )
    if stats["roi"] > VERDICT_SUPPORTED_ROI:
        return f"**SUPPORTED** — ROI {stats['roi']:+.2f}% over {n_graded} graded picks."
    if stats["roi"] < VERDICT_FALSIFIED_ROI:
        return f"**FALSIFIED** — ROI {stats['roi']:+.2f}% over {n_graded} graded picks."
    return (
        f"**INCONCLUSIVE** — ROI {stats['roi']:+.2f}% over {n_graded} graded picks "
        f"(between falsification and support thresholds)."
    )


def write_ledger_report(cfg: dict) -> Path:
    picks = store.load_picks()
    path = paths.reports_dir() / "BETTING_REPORT.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# Panthera Running Ledger",
        "",
        f"Updated: {utc_iso(now_utc())} · Flat stake: ${cfg['staking']['flat_stake']} "
        "· All picks are paper trades.",
        "",
    ]

    if picks.empty:
        body = ["_No picks recorded yet. The daily workflows will populate this ledger._"]
        path.write_text("\n".join(header + body) + "\n")
        return path

    graded = picks[picks["status"].isin(["win", "loss", "push", "void"])]
    pending = picks[picks["status"] == "pending"]
    stats = _ledger_stats(graded) if not graded.empty else None

    body: list[str] = []
    if stats:
        n_graded = len(graded[graded["status"].isin(["win", "loss", "push"])])
        body += [
            "## Verdict",
            "",
            _verdict(stats, n_graded),
            "",
            "## Headline",
            "",
            f"- **Record:** {stats['wins']}-{stats['losses']}-{stats['pushes']} "
            f"({stats['voids']} void)",
            f"- **P/L:** ${stats['profit']:+,.2f} on ${stats['risked']:,.0f} risked",
            f"- **ROI:** {stats['roi']:+.2f}%",
            f"- **Pending picks:** {len(pending)}",
            "",
            "## Breakdown by rule",
            "",
            _breakdown(graded, "rule_id"),
            "",
            "## Breakdown by day type",
            "",
            _breakdown(graded, "day_type"),
            "",
            "## Breakdown by slot",
            "",
            _breakdown(graded, "slot_type"),
            "",
            "## Breakdown by market",
            "",
            _breakdown(graded, "market"),
            "",
        ]
    else:
        body += [
            "## Verdict",
            "",
            _verdict({"roi": 0}, 0),
            "",
            f"_{len(pending)} pending pick(s), none graded yet._",
            "",
        ]

    recent = picks.tail(15)
    body += [
        "## Last 15 picks",
        "",
        "| Date | Matchup | Pick | Price | Rule | Status | P/L |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in recent.iterrows():
        profit = "" if pd.isna(row["profit"]) else f"${float(row['profit']):+,.2f}"
        body.append(
            f"| {row['game_date_et']} | {row['matchup']} | {_pick_label(row)} "
            f"| {_fmt_price(row['price_american'])} | {row['rule_id']} "
            f"| {row['status']} | {profit} |"
        )
    path.write_text("\n".join(header + body) + "\n")
    return path


def write_daily_report(
    date_et: str,
    cfg: dict,
    new_picks: pd.DataFrame | None = None,
    passes: list | None = None,
    credits_note: str = "",
) -> Path:
    picks = store.load_picks()
    path = paths.reports_dir() / "daily" / f"{date_et}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"# Panthera Daily Report — {date_et}", ""]

    graded_today = picks[
        (picks["status"].isin(["win", "loss", "push", "void"]))
        & (picks["settled_ts_utc"].astype(str).str.startswith(date_et))
    ]
    if not graded_today.empty:
        lines += [
            "## Graded today",
            "",
            "| Matchup | Pick | Price | Result | Final | P/L |",
            "|---|---|---|---|---|---|",
        ]
        for _, row in graded_today.iterrows():
            lines.append(
                f"| {row['matchup']} | {_pick_label(row)} "
                f"| {_fmt_price(row['price_american'])} | {row['status']} "
                f"| {row['final_score']} | ${float(row['profit']):+,.2f} |"
            )
        lines.append("")

    todays = picks[picks["game_date_et"] == date_et]
    if not todays.empty:
        lines += [
            "## Today's picks",
            "",
            "| Start (ET) | Slot | Matchup | Pick | Price | Move | Rule | Rationale |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, row in todays.iterrows():
            move = "" if pd.isna(row["movement_cents"]) else f"{float(row['movement_cents']):+.0f}c"
            lines.append(
                f"| {row['start_time_et']} | {row['slot_type']} | {row['matchup']} "
                f"| {_pick_label(row)} | {_fmt_price(row['price_american'])} "
                f"| {move} | {row['rule_id']} | {row['rationale']} |"
            )
        lines.append("")
    elif new_picks is not None:
        lines += ["## Today's picks", "", "_No picks generated for this date._", ""]

    if passes:
        lines += ["## Passed games", ""]
        for p in passes:
            lines.append(f"- {p.matchup}: [{p.rule_id}] {p.reason}")
        lines.append("")

    lines += _splits_section(date_et, picks)

    if credits_note:
        lines += ["## Odds API credits", "", credits_note, ""]

    path.write_text("\n".join(lines) + "\n")
    return path


def _splits_section(date_et: str, picks: pd.DataFrame) -> list[str]:
    """Measured public-betting splits (Lumify) vs the movement-inferred pick.

    Observational: splits do not influence pick generation; this section
    exists so the ledger can eventually test whether rule R2's movement
    inference agrees with measured public money."""
    from .clients.lumify import load_splits

    splits = load_splits()
    if splits.empty:
        return []
    todays = splits[splits["game_date_et"] == date_et]
    if todays.empty:
        return []

    picks_by_pk = (
        picks[picks["game_date_et"] == date_et].set_index("game_pk")
        if not picks.empty
        else pd.DataFrame()
    )
    lines = [
        "## Public betting splits (Lumify — observational)",
        "",
        "| Matchup | Split metrics (consensus) | Our pick |",
        "|---|---|---|",
    ]
    for _event_id, grp in todays.groupby("lumify_event_id"):
        name = grp.iloc[0]["event_name"]
        interesting = grp[
            grp["metric"].str.contains("ticket|money|bet|handle", case=False)
        ]
        shown = interesting if not interesting.empty else grp.head(6)
        metrics = "; ".join(
            f"{row.metric}={row.value:g}" for row in shown.head(8).itertuples()
        )
        pk = grp.iloc[0]["game_pk"]
        pick_label = ""
        if pd.notna(pk) and len(picks_by_pk) and int(pk) in picks_by_pk.index:
            prow = picks_by_pk.loc[int(pk)]
            pick_label = f"{prow['selection']} ({prow['rule_id']})"
        lines.append(f"| {name} | {metrics} | {pick_label} |")
    lines.append("")
    return lines
