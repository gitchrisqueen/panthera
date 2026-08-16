"""Migration proof (b): the declared per-day cap delta, from the ledger itself.

The pre-framework cap was applied per *invocation* (`picks[:6]` in each run),
so morning and pregame runs each got a fresh budget — 4 of the first 15 live
days recorded 7-8 picks against `max_picks_per_day: 6`. This script replays
the per-day budget against the committed ledger (grouping picks by their
created_ts run, in order) and reports exactly which picks the fix would have
dropped and the P&L delta. It is a declared behavior change: post-fix picks
carry a new config_hash (bet_limits.cap_semantics) outside pv_v2's
hash_lineage, so the report never pools across the change.

Run from the repo root: python scripts/proof_cap_delta.py
Writes docs/proofs/cap-delta.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panthera_mvp import store  # noqa: E402

CAP = 6


def main() -> None:
    picks = store.load_picks()
    picks = picks[picks["strategy_id"] == "pv_v2"].sort_values(
        ["game_date_et", "created_ts_utc", "start_time_et"]
    )
    dropped_rows = []
    for _date_et, day in picks.groupby("game_date_et"):
        kept = 0
        for _, row in day.iterrows():
            if kept < CAP:
                kept += 1
            else:
                dropped_rows.append(row)

    report = [
        "# Migration proof (b): per-day cap delta on the live ledger",
        "",
        f"Per-day cap of {CAP} replayed against pv_v2's committed picks, in "
        "run order (created_ts) within each day. The rows below exist in the "
        "ledger only because the old cap was per-invocation; under per-day "
        "semantics they would not have been placed.",
        "",
        "| Date | Pick | Market | Price | Status | P/L |",
        "|---|---|---|---|---|---|",
    ]
    delta = 0.0
    for row in dropped_rows:
        pl = 0.0 if str(row["profit"]) in ("nan", "None", "") else float(row["profit"])
        delta += pl
        report.append(
            f"| {row['game_date_et']} | {row['selection']} | {row['market']} "
            f"| {float(row['price_american']):+.0f} | {row['status']} | ${pl:+,.2f} |"
        )
    graded = picks[picks["status"].isin(["win", "loss", "push"])]
    profit = float(graded["profit"].sum())
    risked = float(graded.loc[graded["status"].isin(["win", "loss"]), "stake"].sum())
    report += [
        "",
        f"- Picks dropped under per-day semantics: **{len(dropped_rows)}**",
        f"- Realized P/L carried by those picks: **${delta:+,.2f}**",
        f"- Ledger as recorded: ${profit:+,.2f} on ${risked:,.0f} "
        f"({100 * profit / risked:+.2f}% ROI)",
        f"- Counterfactual under per-day cap: ${profit - delta:+,.2f} on "
        f"${risked - 100 * len([r for r in dropped_rows if r['status'] in ('win', 'loss')]):,.0f}",
        "",
        "Segment rule: the fix ships with `bet_limits.cap_semantics: per_day` "
        "(hashed) → post-fix picks carry a new config_hash outside pv_v2's "
        "`hash_lineage` → the report renders them as a separate SCREEN "
        "segment. Segment 1's pre-registered verdict is computed on pre-fix "
        "data only.",
    ]
    out = Path("docs/proofs/cap-delta.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n")
    print(f"wrote {out}: {len(dropped_rows)} dropped, delta ${delta:+,.2f}")


if __name__ == "__main__":
    main()
