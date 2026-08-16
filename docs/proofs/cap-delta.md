# Migration proof (b): per-day cap delta on the live ledger

Per-day cap of 6 replayed against pv_v2's committed picks, in run order (created_ts) within each day. The rows below exist in the ledger only because the old cap was per-invocation; under per-day semantics they would not have been placed.

| Date | Pick | Market | Price | Status | P/L |
|---|---|---|---|---|---|
| 2026-08-02 | Boston Red Sox | ml | +155 | win | $+155.00 |
| 2026-08-05 | Atlanta Braves | rl | +161 | win | $+161.00 |
| 2026-08-05 | Kansas City Royals | rl | +163 | loss | $-100.00 |
| 2026-08-08 | Los Angeles Dodgers | ml | -188 | win | $+53.19 |
| 2026-08-12 | Toronto Blue Jays | ml | +116 | win | $+116.00 |
| 2026-08-12 | New York Mets | ml | +158 | loss | $-100.00 |

- Picks dropped under per-day semantics: **6**
- Realized P/L carried by those picks: **$+285.19**
- Ledger as recorded: $-1,205.65 on $8,800 (-13.70% ROI)
- Counterfactual under per-day cap: $-1,490.84 on $8,200

Segment rule: the fix ships with `bet_limits.cap_semantics: per_day` (hashed) → post-fix picks carry a new config_hash outside pv_v2's `hash_lineage` → the report renders them as a separate SCREEN segment. Segment 1's pre-registered verdict is computed on pre-fix data only.
