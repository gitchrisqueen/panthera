"""One-time migration: extend data/picks/picks.csv to the multi-strategy schema.

2026-08-16: adds `strategy_id` (backfilled to "pv_v2" — every pre-framework
pick came from the calibrated P/V rules engine under config_hash 6f0d0924d4),
plus null `close_price`/`clv_cents` columns. Legacy pick_ids are KEPT
(annotation, not a re-term — picks are immutable); the append dedupe key is
(strategy_id, game_pk, market, game_date_et), so unprefixed ids stay
protected. The 88 already-settled rows can never receive CLV (no close
snapshot existed before this migration) and are excluded from CLV coverage
denominators by construction (their close_price stays null forever).

Run once from the repo root: python scripts/migrate_picks_schema.py
Idempotent: re-running is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panthera_mvp import paths  # noqa: E402
from panthera_mvp.store import PICKS_COLUMNS  # noqa: E402


def main() -> None:
    path = paths.picks_csv()
    if not path.exists():
        print("no picks.csv; nothing to migrate")
        return
    df = pd.read_csv(path)
    if "strategy_id" in df.columns and df["strategy_id"].notna().all():
        print("already migrated; no-op")
        return
    df = df.reindex(columns=PICKS_COLUMNS)
    n_backfilled = int(df["strategy_id"].isna().sum())
    df["strategy_id"] = df["strategy_id"].fillna("pv_v2")
    df.to_csv(path, index=False)
    print(
        f"migrated picks.csv: {len(df)} rows, {n_backfilled} backfilled to "
        f"strategy_id=pv_v2, columns now {len(PICKS_COLUMNS)}"
    )


if __name__ == "__main__":
    main()
