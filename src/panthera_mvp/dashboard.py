"""Static GitHub Pages dashboard generation.

`site/` (gitignored, rebuilt fresh on every `panthera-mvp pages` run — see
paths.site_dir()) is generated entirely from the same data/picks/picks.csv
source of truth as reports/BETTING_REPORT.md. This module deliberately
reuses report.py's private stat/verdict helpers (`_ledger_stats`, `_roi_se`,
`_verdict_text`, `_status_summary`, `_clv_cell`, `_overlap_pct`,
`_load_strategies_for_report`) rather than reimplementing any ROI/verdict
math — that is the mechanism that guarantees the dashboard can never drift
from or contradict the markdown ledger. See reports/CLAUDE.md: this is a
second consumer of those helpers, not a fork of them.

Emits one JSON data file (`site/site_data.json`) plus a `calibration_data
.json`; the HTML/CSS/JS is static, tracked source under
`dashboard_static/`, copied verbatim into `site/` — no Jinja2, no
server-side chart rendering. All interactivity (sort/filter/charts) reads
`site_data.json` client-side. The single hard rule the JSON encodes
structurally, not just by convention: retroactive-replay picks
(data/picks/shadow_picks.csv) live ONLY under the top-level
`retroactive_replay` key and are never merged into `picks_history`,
`strategies[].verdict_segment`, or `portfolio_totals` — nothing iterates
`retroactive_replay` by default, so a forgotten filter can't accidentally
pool it into a verdict.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from . import paths, store
from .report import (
    GRADED_STATUSES,
    HOW_TO_READ,
    _close_launch_ts,
    _clv_cell,
    _ledger_stats,
    _load_strategies_for_report,
    _overlap_pct,
    _roi_se,
    _status_summary,
    _verdict_text,
)
from .timeutil import now_utc, utc_iso

STATIC_SRC = Path(__file__).parent / "dashboard_static"


def _n(x):
    """None-safe float coercion for JSON (pandas NaN is not valid JSON)."""
    if x is None or (isinstance(x, float) and pd.isna(x)) or pd.isna(x):
        return None
    return x


def _segment_kind(scfg: dict | None, config_hash: str) -> str:
    """Mirrors report.py::_segment_blocks' pooling logic exactly: a pick
    pools into the verdict segment only if the strategy has verdict criteria
    AND (its hash_lineage is empty [pools everything] OR this hash is in
    it); everything else is a SCREEN segment."""
    if not scfg:
        return "screen"
    criteria = scfg.get("verdict")
    if not criteria:
        return "screen"
    lineage = set(scfg["strategy"].get("hash_lineage") or [])
    if not lineage:
        return "verdict"
    return "verdict" if config_hash in lineage else "screen"


def _record(stats: dict) -> dict:
    return {
        "wins": stats["wins"],
        "losses": stats["losses"],
        "pushes": stats["pushes"],
        "voids": stats["voids"],
    }


def _breakdown_rows(graded: pd.DataFrame, column: str) -> list[dict]:
    rows = []
    for value, grp in graded.groupby(column, dropna=False):
        s = _ledger_stats(grp)
        rows.append(
            {
                "key": str(value),
                "record": _record(s),
                "profit": s["profit"],
                "roi": s["roi"],
            }
        )
    return rows


def _verdict_segment_payload(scfg: dict, mine: pd.DataFrame) -> dict:
    meta = scfg["strategy"]
    lineage = list(meta.get("hash_lineage") or [])
    criteria = scfg["verdict"]
    pool = mine[mine["config_hash"].isin(lineage)] if lineage else mine
    graded_pool = pool[pool["status"].isin(GRADED_STATUSES)]
    n = len(graded_pool[graded_pool["status"].isin(["win", "loss", "push"])])
    stats = _ledger_stats(graded_pool) if not graded_pool.empty else {"roi": 0.0}
    payload = {
        "config_hashes": lineage,
        "n_graded": n,
        "min_graded": int(criteria["min_graded"]),
        "supported_roi": float(criteria["supported_roi"]),
        "falsified_roi": float(criteria["falsified_roi"]),
        "verdict_text": _verdict_text(criteria, stats, n),
    }
    if not graded_pool.empty:
        full = _ledger_stats(graded_pool)
        payload["record"] = _record(full)
        payload["profit"] = full["profit"]
        payload["risked"] = full["risked"]
        payload["roi"] = full["roi"]
        payload["roi_se"] = _roi_se(graded_pool)
    return payload


def _screen_segments_payload(
    scfg: dict | None, mine: pd.DataFrame, seg_source: pd.DataFrame
) -> list[dict]:
    checkpoints = (scfg.get("screen") or {}).get("checkpoints") or [] if scfg else []
    out = []
    for chash, seg in seg_source.groupby("config_hash"):
        graded = seg[seg["status"].isin(GRADED_STATUSES)]
        n = len(graded[graded["status"].isin(["win", "loss", "push"])])
        entry = {
            "config_hash": str(chash),
            "n_graded": n,
            "checkpoints_reached": [int(c) for c in checkpoints if n >= int(c)],
        }
        if not graded.empty:
            s = _ledger_stats(graded)
            entry["record"] = _record(s)
            entry["profit"] = s["profit"]
            entry["roi"] = s["roi"]
        out.append(entry)
    return out


def _strategy_payload(
    sid: str, scfg: dict | None, picks: pd.DataFrame, launch_ts: str | None
) -> dict:
    mine = picks[picks["strategy_id"] == sid]
    meta = scfg["strategy"] if scfg else {}
    graded = mine[mine["status"].isin(GRADED_STATUSES)]
    pending = mine[mine["status"] == "pending"]

    payload: dict = {
        "id": sid,
        "kind": meta.get("kind", "?") if scfg else "retired?",
        "enabled": bool(meta.get("enabled")) if scfg else False,
        "registered_at": meta.get("registered_at") if scfg else None,
        "hypothesis": str(meta.get("hypothesis", "")).strip() if scfg else "",
        "hash_lineage": list(meta.get("hash_lineage") or []) if scfg else [],
        "status_short": _status_summary(scfg, mine) if scfg else "retired",
        "clv": _clv_cell(mine, launch_ts),
        "overlap_pct": _overlap_pct(picks, sid),
        "pending": int(len(pending)),
        "graded_n": 0,
        "verdict_segment": None,
        "screen_segments": [],
        "breakdowns": {},
    }
    if not graded.empty:
        s = _ledger_stats(graded)
        payload["record"] = _record(s)
        payload["profit"] = s["profit"]
        payload["risked"] = s["risked"]
        payload["roi"] = s["roi"]
        payload["roi_se"] = _roi_se(graded)
        payload["graded_n"] = s["wins"] + s["losses"] + s["pushes"]

        payload["breakdowns"]["by_rule"] = _breakdown_rows(graded, "rule_id")
        if scfg and meta.get("engine") == "pv_rules":
            payload["breakdowns"]["by_day_type"] = _breakdown_rows(graded, "day_type")
            payload["breakdowns"]["by_slot"] = _breakdown_rows(graded, "slot_type")
            payload["breakdowns"]["by_market"] = _breakdown_rows(graded, "market")

    # Verdict/screen segments are computed regardless of whether anything is
    # graded yet — a strategy with 0 graded picks still has a meaningful
    # "collecting data 0/N" verdict line (matches report.py::_segment_blocks,
    # which never early-returns on an empty graded pool).
    if scfg:
        criteria = scfg.get("verdict")
        lineage = list(meta.get("hash_lineage") or [])
        if criteria:
            payload["verdict_segment"] = _verdict_segment_payload(scfg, mine)
            seg_source = (
                mine[~mine["config_hash"].isin(lineage)] if lineage else mine.iloc[0:0]
            )
        else:
            seg_source = mine
        payload["screen_segments"] = _screen_segments_payload(scfg, mine, seg_source)

    return payload


def _picks_history_rows(picks: pd.DataFrame, strategies: dict[str, dict]) -> list[dict]:
    rows = []
    for _, row in picks.iterrows():
        scfg = strategies.get(row["strategy_id"])
        rows.append(
            {
                "pick_id": row["pick_id"],
                "strategy_id": row["strategy_id"],
                "game_date_et": row["game_date_et"],
                "start_time_et": row["start_time_et"],
                "matchup": row["matchup"],
                "day_type": row["day_type"],
                "slot_type": row["slot_type"],
                "rule_id": row["rule_id"],
                "market": row["market"],
                "selection": row["selection"],
                "line": _n(row["line"]),
                "price_american": _n(row["price_american"]),
                "status": row["status"],
                "profit": _n(row["profit"]),
                "settled_ts_utc": _n(row["settled_ts_utc"]),
                "clv_cents": _n(row["clv_cents"]),
                "config_hash": row["config_hash"],
                "segment_kind": _segment_kind(scfg, row["config_hash"]),
                "rationale": row["rationale"],
            }
        )
    return rows


def _portfolio_totals(picks: pd.DataFrame, all_sids: list[str], strategies: dict) -> dict:
    """Mirrors write_ledger_report's totals loop exactly (sum over every
    strategy's own graded pool, not lineage-filtered) — byte-parity with the
    markdown ledger's portfolio row, not a "fixed" recalculation."""
    profit = 0.0
    risked = 0.0
    for sid in all_sids:
        scfg = strategies.get(sid)
        mine = picks[picks["strategy_id"] == sid]
        if scfg and not scfg["strategy"].get("enabled") and mine.empty:
            continue
        graded = mine[mine["status"].isin(GRADED_STATUSES)]
        if graded.empty:
            continue
        s = _ledger_stats(graded)
        profit += s["profit"]
        risked += s["risked"]
    roi = round(100 * profit / risked, 2) if risked else 0.0
    return {
        "profit": round(profit, 2),
        "risked": risked,
        "roi": roi,
        "note": "Informational — not an evaluation target. Descriptive, not "
        "a tournament: strategies share games/sides, so results are "
        "correlated (see each strategy's overlap figure).",
    }


def _retroactive_replay_payload() -> dict:
    shadow = store.load_shadow_picks()
    banner = (
        "Not an evaluation — read before citing. These picks were computed "
        "by `panthera-mvp replay` over odds/game history already captured — "
        "they were never placed in real time and cost no API credits. "
        "Look-ahead-free only with respect to the strategy itself; the "
        "sample was selected after every outcome in it was already known, "
        "so it carries none of the evidentiary weight of a forward "
        "paper-trade. Never pooled into any strategy's verdict, portfolio "
        "total, or the picks ledger above."
    )
    if shadow.empty:
        return {"banner": banner, "strategies": []}
    out = []
    for sid in sorted(shadow["strategy_id"].dropna().unique()):
        mine = shadow[shadow["strategy_id"] == sid]
        graded = mine[mine["status"].isin(GRADED_STATUSES)]
        entry: dict = {"id": sid, "n_picks": int(len(mine)), "graded_n": 0}
        if not graded.empty:
            s = _ledger_stats(graded)
            entry["graded_n"] = s["wins"] + s["losses"] + s["pushes"]
            entry["record"] = _record(s)
            entry["profit"] = s["profit"]
            entry["roi"] = s["roi"]
            entry["by_rule"] = _breakdown_rows(graded, "rule_id")
        out.append(entry)
    return {"banner": banner, "strategies": out}


def build_site_data(generated_by_run: str = "manual") -> dict:
    picks = store.load_picks()
    strategies = _load_strategies_for_report()
    launch_ts = _close_launch_ts()

    ledger_sids = [s for s in picks["strategy_id"].dropna().unique()] if not picks.empty else []
    all_sids = list(dict.fromkeys(list(strategies.keys()) + ledger_sids))
    # Drop never-run disabled strategies, same as write_ledger_report.
    all_sids = [
        sid
        for sid in all_sids
        if not (
            strategies.get(sid)
            and not strategies[sid]["strategy"].get("enabled")
            and (picks.empty or picks[picks["strategy_id"] == sid].empty)
        )
    ]

    strategy_payloads = [
        _strategy_payload(sid, strategies.get(sid), picks, launch_ts) for sid in all_sids
    ]

    return {
        "generated_at_utc": utc_iso(now_utc()),
        "generated_by_run": generated_by_run,
        "how_to_read": HOW_TO_READ,
        "strategies": strategy_payloads,
        "portfolio_totals": (
            _portfolio_totals(picks, all_sids, strategies) if not picks.empty else None
        ),
        "picks_history": _picks_history_rows(picks, strategies) if not picks.empty else [],
        "retroactive_replay": _retroactive_replay_payload(),
    }


def build_calibration_data() -> dict:
    """Best-effort summary for calibration.html. Full sweep methodology
    prose stays canonical in reports/CALIBRATION.md (linked from the page);
    this is a compact top-10-by-validation-ROI table, not a duplicate of
    the markdown's narrative sections."""
    best_path = paths.calibration_dir() / "best_params.json"
    sweep_path = paths.calibration_dir() / "sweep_results.csv"
    data: dict = {"available": False, "best_params": None, "top_configs": []}
    if best_path.exists():
        data["available"] = True
        data["best_params"] = json.loads(best_path.read_text())
    if sweep_path.exists():
        sweep = pd.read_csv(sweep_path)
        valid = sweep[sweep["split"] == "valid"].sort_values("roi", ascending=False)
        data["available"] = True
        data["top_configs"] = [
            {
                "config_id": r["config_id"],
                "n_bets": int(r["n_bets"]),
                "roi_valid": float(r["roi"]),
                "profit_valid": float(r["profit"]),
            }
            for _, r in valid.head(10).iterrows()
        ]
    return data


def write_site(generated_by_run: str = "manual") -> Path:
    """Build the full static dashboard into paths.site_dir(). Called by
    `panthera-mvp pages` (pipeline.cmd_pages). Fully regenerated every run —
    nothing here is ever hand-edited, same rule as reports/ (see
    reports/CLAUDE.md), just not committed."""
    out = paths.site_dir()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    site_data = build_site_data(generated_by_run=generated_by_run)
    (out / "site_data.json").write_text(json.dumps(site_data, indent=None))
    (out / "calibration_data.json").write_text(json.dumps(build_calibration_data(), indent=None))

    static_out = out / "static"
    shutil.copytree(STATIC_SRC, static_out)
    for html_file in ("index.html", "calibration.html"):
        shutil.move(str(static_out / html_file), str(out / html_file))
    (out / ".nojekyll").write_text("")

    return out
