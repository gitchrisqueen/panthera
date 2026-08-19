"""Markdown report generation.

reports/BETTING_REPORT.md is fully regenerated from data/picks/picks.csv on
every run — the CSV is the source of truth, the markdown is derived. Daily
reports live in reports/daily/YYYY-MM-DD.md.

Multi-strategy semantics:
- Evaluation criteria are per-strategy, pre-registered in each strategy's
  YAML (config/strategies/<id>.yaml) at registration. There is no global
  verdict, and portfolio totals are informational — never a verdict target.
- A strategy's verdict pools only picks whose config_hash is in its declared
  `hash_lineage`. Picks under any other hash form separate segments rendered
  as SCREEN blocks (descriptive only, no inferential weight) — a behavioral
  change can never silently extend a verdict's sample.
- SE is computed from each strategy's own realized profit distribution,
  never a global constant.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from . import paths, store
from .config import StrategyConfigError, load_strategy_configs
from .timeutil import now_utc, utc_iso

HOW_TO_READ = """\
**How to read this report.** Every strategy here is a paper-traded hypothesis
with its own pre-registered evaluation criteria (declared in its YAML at
registration). Flat $100 stakes on near-even MLB prices put the per-bet SD
near the stake, so ROI estimates are noisy: SE(ROI) ≈ 10.5 points at n=100
and ≈ 6.1 points at n=300 (at SD $105 — each strategy's own SD is used
below). Two nulls matter: under a **zero-edge** null, a 0% "supported"
threshold is a 50% coin flip at any n; under a **no-skill-pays-vig** null
(≈ −4.5%), a −5% "falsified" threshold is crossed ~48% of the time at n=100.
For the forward-test template (n=300, supported > +2%, falsified < −5%, SD
$105): P(false SUPPORTED | true 0) ≈ 37%, P(false SUPPORTED | true −4.5%)
≈ 14%, P(false FALSIFIED | true 0) ≈ 21%, P(false FALSIFIED | true −4.5%)
≈ 47%, and power against a true +2% edge is 50%. **At these sample sizes no
ROI bar controls both error rates — paper-ROI verdicts are screens by
nature.** Replication across segments/windows is the strongest evidence
here; CLV is a directional price-capture cross-check over a ~75-minute
window, not an independent test of edge. With several strategies running in
parallel on the same slate, at least one false-positive screen is the
expected outcome, results are correlated (shared games, often shared
sides — see the overlap column), and the comparison table is descriptive,
not a tournament."""

GRADED_STATUSES = ["win", "loss", "push", "void"]


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


def _roi_se(graded: pd.DataFrame) -> float | None:
    """SE of the ROI estimate in percentage points, from this sample's own
    realized per-bet profit distribution (never a global constant)."""
    wl = graded[graded["status"].isin(["win", "loss"])]
    n = len(wl)
    if n < 2:
        return None
    per_dollar = wl["profit"].astype(float) / wl["stake"].astype(float)
    sd = float(per_dollar.std(ddof=1))
    return round(100 * sd / math.sqrt(n), 1)


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


def _close_launch_ts() -> str | None:
    """First timestamp the `close` snapshot label ever appeared — picks
    created before it can never have CLV and are excluded from coverage
    denominators (not counted as misses)."""
    lines = store.load_lines()
    if lines.empty or "snapshot_label" not in lines.columns:
        return None
    close_rows = lines[lines["snapshot_label"] == "close"]
    if close_rows.empty:
        return None
    return str(close_rows["snapshot_ts_utc"].min())


def _clv_cell(picks: pd.DataFrame, launch_ts: str | None) -> str:
    """Avg CLV over covered picks ('close' = last pre-start snapshot — a
    directional price-capture cross-check, not an independent edge test)."""
    if "clv_cents" not in picks.columns:
        return "—"
    covered = picks[picks["clv_cents"].notna()]
    if covered.empty:
        return "—"
    eligible = (
        picks[picks["created_ts_utc"].astype(str) >= launch_ts]
        if launch_ts
        else covered
    )
    denom = max(len(eligible), len(covered))
    avg = float(covered["clv_cents"].mean())
    pos = 100 * float((covered["clv_cents"] > 0).mean())
    coverage = 100 * len(covered) / denom if denom else 0
    return f"{avg:+.1f}c (n={len(covered)}, {pos:.0f}% pos, {coverage:.0f}% cov)"


def _verdict_text(criteria: dict, stats: dict, n_graded: int) -> str:
    min_n = int(criteria["min_graded"])
    sup = float(criteria["supported_roi"])
    fal = float(criteria["falsified_roi"])
    if n_graded < min_n:
        return (
            f"**INCONCLUSIVE — collecting data.** {n_graded}/{min_n} graded picks. "
            f"Pre-registered: after {min_n} graded, ROI > {sup:.0f}% → SUPPORTED; "
            f"ROI < {fal:.0f}% → FALSIFIED; otherwise inconclusive."
        )
    if stats["roi"] > sup:
        return (
            f"**SUPPORTED** — ROI {stats['roi']:+.2f}% over {n_graded} graded picks. "
            "(Screen-grade evidence; see 'How to read this report'.)"
        )
    if stats["roi"] < fal:
        return f"**FALSIFIED** — ROI {stats['roi']:+.2f}% over {n_graded} graded picks."
    return (
        f"**INCONCLUSIVE** — ROI {stats['roi']:+.2f}% over {n_graded} graded picks "
        "(between falsification and support thresholds)."
    )


def _status_summary(scfg: dict, picks: pd.DataFrame) -> str:
    """Short status for the comparison table."""
    meta = scfg["strategy"]
    lineage = set(meta.get("hash_lineage") or [])
    graded = picks[picks["status"].isin(GRADED_STATUSES)]
    criteria = scfg.get("verdict")
    if criteria:
        pool = graded[graded["config_hash"].isin(lineage)] if lineage else graded
        n = len(pool[pool["status"].isin(["win", "loss", "push"])])
        if n == 0:
            return "collecting"
        stats = _ledger_stats(pool)
        min_n = int(criteria["min_graded"])
        if n < min_n:
            return f"collecting ({n}/{min_n})"
        if stats["roi"] > float(criteria["supported_roi"]):
            return "SUPPORTED*"
        if stats["roi"] < float(criteria["falsified_roi"]):
            return "FALSIFIED"
        return "INCONCLUSIVE"
    if not meta.get("enabled") and "live" not in meta.get("scope", []):
        return "not live"
    return "screen only"


def _overlap_pct(picks: pd.DataFrame, sid: str) -> str:
    """% of this strategy's picks where another strategy picked the same side
    of the same game/market that day — correlated results, not independent
    evidence."""
    mine = picks[picks["strategy_id"] == sid]
    if mine.empty or picks["strategy_id"].nunique() < 2:
        return "—"
    others = picks[picks["strategy_id"] != sid]
    other_keys = set(
        map(tuple, others[["game_date_et", "game_pk", "market", "selection"]].astype(str).values)
    )
    shared = sum(
        tuple(map(str, row)) in other_keys
        for row in mine[["game_date_et", "game_pk", "market", "selection"]].values
    )
    return f"{100 * shared / len(mine):.0f}%"


def _load_strategies_for_report() -> dict[str, dict]:
    try:
        return load_strategy_configs(known_engines=None)
    except StrategyConfigError:
        return {}


def _segment_blocks(sid: str, scfg: dict, picks: pd.DataFrame) -> list[str]:
    """Per-strategy section body: verdict on the lineage pool (if criteria
    exist), then SCREEN blocks for every out-of-lineage hash segment."""
    meta = scfg["strategy"]
    lineage = list(meta.get("hash_lineage") or [])
    criteria = scfg.get("verdict")
    checkpoints = (scfg.get("screen") or {}).get("checkpoints") or []
    body: list[str] = []

    def _stats_lines(pool: pd.DataFrame, se_note: bool = True) -> list[str]:
        graded = pool[pool["status"].isin(GRADED_STATUSES)]
        pending = pool[pool["status"] == "pending"]
        if graded.empty:
            return [f"_No graded picks yet ({len(pending)} pending)._", ""]
        s = _ledger_stats(graded)
        se = _roi_se(graded)
        se_txt = f" (±{se} pts SE, own SD)" if se is not None and se_note else ""
        out = [
            f"- **Record:** {s['wins']}-{s['losses']}-{s['pushes']} ({s['voids']} void)",
            f"- **P/L:** ${s['profit']:+,.2f} on ${s['risked']:,.0f} risked",
            f"- **ROI:** {s['roi']:+.2f}%{se_txt}",
            f"- **Pending:** {len(pending)}",
            "",
        ]
        return out

    if criteria:
        pool = (
            picks[picks["config_hash"].isin(lineage)] if lineage else picks
        )
        graded_pool = pool[pool["status"].isin(GRADED_STATUSES)]
        n = len(graded_pool[graded_pool["status"].isin(["win", "loss", "push"])])
        stats = _ledger_stats(graded_pool) if not graded_pool.empty else {"roi": 0.0}
        lineage_label = ", ".join(lineage) if lineage else "all hashes"
        body += [
            f"**Verdict segment** (config hashes: {lineage_label}):",
            "",
            _verdict_text(criteria, stats, n),
            "",
        ]
        body += _stats_lines(pool)
        seg_source = picks[~picks["config_hash"].isin(lineage)] if lineage else picks.iloc[0:0]
    else:
        body += [
            "_No verdict criteria — descriptive SCREEN readouts only "
            "(baseline or budget-limited forward test)._",
            "",
        ]
        seg_source = picks

    for chash, seg in seg_source.groupby("config_hash"):
        graded = seg[seg["status"].isin(GRADED_STATUSES)]
        n = len(graded[graded["status"].isin(["win", "loss", "push"])])
        reached = [c for c in checkpoints if n >= int(c)]
        cp_txt = (
            f" checkpoints reached: {reached}" if reached else ""
        )
        body += [
            f"**SCREEN segment** `{chash}` — descriptive only, no inferential "
            f"weight; no threshold is tested.{cp_txt}",
            "",
        ]
        body += _stats_lines(seg)
    return body


def write_ledger_report(cfg: dict) -> Path:
    picks = store.load_picks()
    strategies = _load_strategies_for_report()
    path = paths.reports_dir() / "BETTING_REPORT.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# Panthera Running Ledger",
        "",
        f"Updated: {utc_iso(now_utc())} · Flat stakes (per strategy YAML) · "
        "All picks are paper trades.",
        "",
        HOW_TO_READ,
        "",
    ]

    if picks.empty:
        body = ["_No picks recorded yet. The daily workflows will populate this ledger._"]
        path.write_text("\n".join(header + body) + "\n")
        return path

    # --- Strategy comparison ------------------------------------------------
    ledger_sids = [s for s in picks["strategy_id"].dropna().unique()]
    all_sids = list(dict.fromkeys(list(strategies.keys()) + ledger_sids))
    body = [
        "## Strategy comparison",
        "",
        "| Strategy | Kind | Graded | Record | P/L | ROI (±SE) | Avg CLV | Overlap "
        "| Pending | Status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    totals = {"profit": 0.0, "risked": 0.0}
    launch_ts = _close_launch_ts()
    for sid in all_sids:
        mine = picks[picks["strategy_id"] == sid]
        scfg = strategies.get(sid)
        kind = scfg["strategy"].get("kind", "?") if scfg else "retired?"
        graded = mine[mine["status"].isin(GRADED_STATUSES)]
        pending = mine[mine["status"] == "pending"]
        if scfg and not scfg["strategy"].get("enabled") and mine.empty:
            continue  # never-run disabled strategy: skip the empty row
        if graded.empty:
            body.append(
                f"| {sid} | {kind} | 0 | — | — | — | — | — | {len(pending)} "
                f"| {_status_summary(scfg, mine) if scfg else 'retired'} |"
            )
            continue
        s = _ledger_stats(graded)
        se = _roi_se(graded)
        se_txt = f" ±{se}" if se is not None else ""
        n = s["wins"] + s["losses"] + s["pushes"]
        totals["profit"] += s["profit"]
        totals["risked"] += s["risked"]
        body.append(
            f"| {sid} | {kind} | {n} | {s['wins']}-{s['losses']}-{s['pushes']} "
            f"| ${s['profit']:+,.2f} | {s['roi']:+.2f}%{se_txt} | {_clv_cell(mine, launch_ts)} "
            f"| {_overlap_pct(picks, sid)} | {len(pending)} "
            f"| {_status_summary(scfg, mine) if scfg else 'retired'} |"
        )
    if totals["risked"]:
        roi = 100 * totals["profit"] / totals["risked"]
        body.append(
            f"| _portfolio (informational — not an evaluation target)_ |  |  |  "
            f"| ${totals['profit']:+,.2f} | {roi:+.2f}% |  |  |  |  |"
        )
    body.append("")

    # --- Per-strategy sections ---------------------------------------------
    for sid in all_sids:
        mine = picks[picks["strategy_id"] == sid]
        scfg = strategies.get(sid)
        if mine.empty and (scfg is None or not scfg["strategy"].get("enabled")):
            continue
        body += [f"## Strategy: {sid}", ""]
        if scfg:
            hyp = str(scfg["strategy"].get("hypothesis", "")).strip()
            if hyp:
                body += [f"_{hyp}_", ""]
            body += _segment_blocks(sid, scfg, mine)
        else:
            body += [
                "_No YAML registered for this id (retired). Descriptive stats only._",
                "",
            ]
            graded = mine[mine["status"].isin(GRADED_STATUSES)]
            if not graded.empty:
                s = _ledger_stats(graded)
                body += [
                    f"- Record {s['wins']}-{s['losses']}-{s['pushes']}, "
                    f"P/L ${s['profit']:+,.2f}, ROI {s['roi']:+.2f}%",
                    "",
                ]
        graded = mine[mine["status"].isin(GRADED_STATUSES)]
        if not graded.empty:
            body += ["**By rule**", "", _breakdown(graded, "rule_id"), ""]
            if scfg and scfg["strategy"].get("engine") == "pv_rules":
                body += [
                    "**By day type**",
                    "",
                    _breakdown(graded, "day_type"),
                    "",
                    "**By slot**",
                    "",
                    _breakdown(graded, "slot_type"),
                    "",
                    "**By market**",
                    "",
                    _breakdown(graded, "market"),
                    "",
                ]
        recent = mine.tail(10)
        if not recent.empty:
            body += [
                "**Last 10 picks**",
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
            body.append("")

    body += _shadow_section()

    path.write_text("\n".join(header + body) + "\n")
    return path


def _shadow_section() -> list[str]:
    """Retroactive replay picks (`panthera-mvp replay`) — data/picks/
    shadow_picks.csv. Rendered as a clearly-separate, non-evaluable section:
    these picks were computed after the fact over already-known odds
    history, not placed in real time, and are NEVER pooled into any
    strategy's pre-registered verdict, portfolio total, or by-rule table
    above."""
    shadow = store.load_shadow_picks()
    if shadow.empty:
        return []
    lines = [
        "## Retroactive replay (NOT an evaluation — read before citing)",
        "",
        "_Picks below were computed by `panthera-mvp replay` over odds/game",
        "history this pipeline had already captured — they were never placed",
        "in real time and cost no API credits. They are useful as an early,",
        "qualitative read on an engine before its live sample accumulates,",
        "but they are look-ahead-free only with respect to the STRATEGY",
        "(no future prices/results feed a pick's own inputs) — the SAMPLE",
        "itself was picked after every outcome in it was already known, so",
        "it carries none of the evidentiary weight of a forward paper-trade",
        "or a train/validate backtest split. Never pooled into any",
        "strategy's verdict, portfolio total, or the tables above._",
        "",
    ]
    for sid in sorted(shadow["strategy_id"].dropna().unique()):
        mine = shadow[shadow["strategy_id"] == sid]
        graded = mine[mine["status"].isin(GRADED_STATUSES)]
        lines.append(f"### {sid} (retroactive)")
        lines.append("")
        if graded.empty:
            lines += [f"_{len(mine)} pick(s), none graded yet._", ""]
            continue
        s = _ledger_stats(graded)
        lines += [
            f"- Record {s['wins']}-{s['losses']}-{s['pushes']}, "
            f"P/L ${s['profit']:+,.2f}, ROI {s['roi']:+.2f}% "
            f"({len(graded)} graded, descriptive only)",
            "",
            "**By rule**",
            "",
            _breakdown(graded, "rule_id"),
            "",
        ]
    return lines


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
        (picks["status"].isin(GRADED_STATUSES))
        & (picks["settled_ts_utc"].astype(str).str.startswith(date_et))
    ]
    if not graded_today.empty:
        lines += [
            "## Graded today",
            "",
            "| Strategy | Matchup | Pick | Price | Result | Final | P/L |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, row in graded_today.iterrows():
            lines.append(
                f"| {row['strategy_id']} | {row['matchup']} | {_pick_label(row)} "
                f"| {_fmt_price(row['price_american'])} | {row['status']} "
                f"| {row['final_score']} | ${float(row['profit']):+,.2f} |"
            )
        lines.append("")

    todays = picks[picks["game_date_et"] == date_et]
    if not todays.empty:
        lines += [
            "## Today's picks",
            "",
            "| Strategy | Start (ET) | Slot | Matchup | Pick | Price | Move | Rule | Rationale |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, row in todays.sort_values(["strategy_id", "start_time_et"]).iterrows():
            move = "" if pd.isna(row["movement_cents"]) else f"{float(row['movement_cents']):+.0f}c"
            lines.append(
                f"| {row['strategy_id']} | {row['start_time_et']} | {row['slot_type']} "
                f"| {row['matchup']} | {_pick_label(row)} "
                f"| {_fmt_price(row['price_american'])} "
                f"| {move} | {row['rule_id']} | {row['rationale']} |"
            )
        lines.append("")
    elif new_picks is not None:
        lines += ["## Today's picks", "", "_No picks generated for this date._", ""]

    lines += _passes_section(date_et, todays)

    run_log = store.load_run_log()
    notes_today = (
        run_log[run_log["game_date_et"] == date_et] if not run_log.empty else run_log
    )
    if not notes_today.empty:
        lines += ["## Run notes", ""]
        for _, row in notes_today.iterrows():
            lines.append(f"- `{row['run_label']}` [{row['kind']}] {row['note']}")
        lines.append("")

    lines += _splits_section(date_et, picks)

    if credits_note:
        lines += ["## Odds API credits", "", credits_note, ""]

    path.write_text("\n".join(lines) + "\n")
    return path


def _passes_section(date_et: str, todays_picks: pd.DataFrame) -> list[str]:
    """Rendered from data/picks/passes.csv (durable — regeneration used to
    erase in-memory pass lists ~20 minutes after the picks run wrote them).
    Games that later produced a pick for the same strategy are subtracted:
    a morning structural pass followed by a pregame pick is not a pass."""
    passes = store.load_passes()
    if passes.empty:
        return []
    today = passes[passes["game_date_et"] == date_et]
    if today.empty:
        return []
    picked_keys = (
        set(map(tuple, todays_picks[["strategy_id", "game_pk"]].astype(str).values))
        if not todays_picks.empty
        else set()
    )
    kept = today[
        [
            tuple(map(str, row)) not in picked_keys
            for row in today[["strategy_id", "game_pk"]].values
        ]
    ]
    if kept.empty:
        return []
    lines = ["## Passed games (net of later picks)", ""]
    for (sid, run_label), grp in kept.groupby(["strategy_id", "run_label"]):
        lines.append(f"- **{sid}** ({run_label} run):")
        for _, row in grp.iterrows():
            lines.append(f"  - game {int(row['game_pk'])}: {row['reason']}")
    lines.append("")
    return lines


def _splits_section(date_et: str, picks: pd.DataFrame) -> list[str]:
    """Measured public-betting splits (Lumify) vs our picks.

    Splits are an input only for splits-based engines; for the P/V rules
    engine they remain observational. With multiple strategies a game can
    carry several picks — they are joined into one cell (the old
    single-pick `.loc` rendered a DataFrame repr and garbled the table)."""
    from .clients.lumify import load_splits

    splits = load_splits()
    if splits.empty:
        return []
    if "snapshot_label" not in splits.columns:
        splits["snapshot_label"] = "manual"
    todays = splits[splits["game_date_et"] == date_et]
    if todays.empty:
        return []

    picks_today = picks[picks["game_date_et"] == date_et] if not picks.empty else picks
    lines = [
        "## Public betting splits (Lumify)",
        "",
        "| Matchup | Snapshot | Split metrics (consensus) | Our pick(s) |",
        "|---|---|---|---|",
    ]
    for _event_id, grp in todays.groupby("lumify_event_id"):
        # Show the most recent snapshot for each event.
        latest_ts = grp["fetched_ts_utc"].max()
        grp = grp[grp["fetched_ts_utc"] == latest_ts]
        name = grp.iloc[0]["event_name"]
        label = grp.iloc[0]["snapshot_label"]
        metrics = "; ".join(
            f"{row.metric}={row.value:g}" for row in grp.head(8).itertuples()
        )
        pk = grp.iloc[0]["game_pk"]
        pick_label = ""
        if pd.notna(pk) and not picks_today.empty:
            prows = picks_today[picks_today["game_pk"] == int(pk)]
            pick_label = "; ".join(
                f"{r['selection']} ({r['strategy_id']}/{r['rule_id']})"
                for _, r in prows.iterrows()
            )
        lines.append(f"| {name} | {label} | {metrics} | {pick_label} |")
    lines.append("")
    return lines
