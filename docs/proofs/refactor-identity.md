# Migration proof (a): refactor identity for pv_v2

> **Frozen historical record — do NOT regenerate.** Re-running
> `scripts/proof_refactor_identity.py` today reports FAIL, and that is not a
> regression in the code it was about. Its premise was that
> `config/strategies/pv_v2.yaml`'s inlined parameters replicate
> base + calibrated exactly; `config/strategy.yaml` has moved since (the day
> map alignment, then the 2026-10-15 season-scope fix), so the two arms now
> load genuinely different configs — the old arm's hash has drifted from
> `edddc8abdb` to `fc0832e4b6` and the arms disagree on `day_type`. The
> figures below describe the migration at the time it was made, which is
> what a migration proof is for. pv_v2 is retired, so nothing live depends
> on re-deriving it.

Old path: `generate_pick` + pipeline config (base+calibrated). New path: registry `_pv_rules` + `config/strategies/pv_v2.yaml` + `pick_row`. Identical inputs (lines.csv + games.csv replay; shared games.csv-derived season context). Compared fields: `game_pk`, `market`, `selection`, `line`, `price_american`, `rule_id`, `day_type`, `slot_type`, `open_price`, `latest_price`, `movement_cents`, `rationale` — `pick_id`/`config_hash`/`strategy_id` excluded (they legitimately change).

Old config hash: `edddc8abdb` · new: `edddc8abdb` — identical here because pv_v2.yaml's inlined parameters replicate base+calibrated exactly under the new hash function. Both differ from the legacy live hash `6f0d0924d4` (computed by the old hash function over the whole dict incl. `meta`), which is why the ledger segments at the framework boundary. Neither path applies a bet cap in this replay — cap-semantics differences are proven separately in cap-delta.md.

## 2026-08-03

- old path picks: 3 · new path picks: 3
- field-identical: **YES**

- 823431 Washington Nationals ml +130 [R3]
- 823757 Pittsburgh Pirates ml +129 [R3]
- 824324 Colorado Rockies ml +154 [R3]

## 2026-08-16

- old path picks: 7 · new path picks: 7
- field-identical: **YES**

- 822774 New York Yankees rl -220 [R4]
- 822940 Tampa Bay Rays ml -174 [R3]
- 823590 New York Mets ml -164 [R3_series]
- 823670 Minnesota Twins rl -168 [R4]
- 824236 Chicago White Sox rl +160 [R4]
- 824397 Cleveland Guardians rl -175 [R4]
- 824880 Arizona Diamondbacks ml +113 [R3_series]

