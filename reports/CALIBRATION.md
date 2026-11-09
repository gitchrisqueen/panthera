# Calibration Report — Threshold Sweeps

Generated: 2026-08-19T22:26:46Z

## Data coverage

- Seasons: 2014–2021 (17245 games)
- Train: 2014–2019 · Validate: 2021–2021

## What changed (2026-08-19)

The day map is **no longer swept**. It is stated directly in the
source recordings (P1 02:10: "Monday...public day...Tuesday...Vegas
day...Wednesday...hybrid day...Thursday...Vegas day...Friday...public
day...both Saturday and Sunday are both going to be Vegas days") and
is now a documented constant in `config/strategy.yaml`. The previous
64-day-map sweep picked an inverted map (VVHPPPP vs the documented
PVHVPVV) on +1.40% validation ROI against −1.83% train — a sweep
artifact, not a finding. It ran live as `pv_v2`/`pv_v3` for their
entire history; both are −15%/−30% ROI live. See
`docs/mvp-design.md`'s alignment section for the full account.

The historical archive loader also had a bug (fixed the same day):
run-line odds and totals prices sit in *unnamed* columns in every
published sbro file and were silently dropped, so every backtested
run-line pick fell back to a moneyline bet — R4/R5/R7 were never
actually tested pre-2026-08-19. The numbers below are the first run
under correctly-parsed run-line and totals pricing, and the first
with real game start times (joined from the MLB Stats API schedule
cache), so hybrid Wednesdays are no longer skipped.

## Method — incumbent (pv_rules-family) thresholds

Grid: min_move [5, 10, 15, 20] × evenly-matched ML [110, 120, 130, 140] × heavy-fav [200, 250, 300] = 48 configs, under the fixed documented day map. Ranked by validation ROI with a ≥150-bet floor per split. Diagnostic/
comparative now — pv_v2/pv_v3 already pin their own deployed values
and this sweep cannot change them (registry strategies never merge
`strategy.calibrated.yaml`); useful for any future pv_rules-family
registration.

## Caveats (read before trusting)

- **Open→close is a coarse proxy** for the strategy's intraday
  line-movement reads; only forward paper-trading tests the real thing.
- No probable-pitcher ERA in historical files (pitcher names only): the
  ERA fallback and R8 veto never fire in backtests.

## Top 10 configs by validation ROI

| min_move | even_ml | heavy_fav | Train bets | Train ROI | Valid bets | Valid ROI |
|---|---|---|---|---|---|---|
| 10 | 110 | 250 | 11725 | -1.96% | 1944 | +3.47% |
| 10 | 130 | 250 | 11725 | -1.64% | 1944 | +3.40% |
| 10 | 110 | 300 | 11983 | -1.83% | 2002 | +3.21% |
| 10 | 130 | 300 | 11983 | -1.52% | 2002 | +3.15% |
| 10 | 120 | 250 | 11725 | -1.89% | 1944 | +3.03% |
| 5 | 110 | 250 | 12926 | -1.92% | 2137 | +3.01% |
| 10 | 110 | 200 | 10969 | -2.33% | 1779 | +2.89% |
| 10 | 140 | 250 | 11725 | -2.03% | 1944 | +2.88% |
| 10 | 130 | 200 | 10969 | -1.98% | 1779 | +2.81% |
| 10 | 120 | 300 | 11983 | -1.77% | 2002 | +2.79% |

## Chosen config (incumbent thresholds)

`m10-e110-h250`. Validation ROI +3.47% on 1944 bets (train -1.96% on 11725).

Written to `config/strategy.calibrated.yaml` when `--write-config` is
used (day map is never written there anymore); override any value by
editing `config/strategy.yaml`.

## Method — pv_orig genuine unknowns

Grid: min_merit_score [0.5, 1.0, 1.5, 2.0] × min_price_delta_cents [5.0, 10.0] × big_scam_min_price_delta_cents [40, 60, 80, 100] × evenly_matched_max_abs_ml [110, 120, 130, 140] = 128 configs, over pv_orig's full day-policy/slot-discipline engine (merit_weights held fixed at their YAML starting values — a 5-dimensional weight sweep is future work, not done here). Ranked by validation ROI with a ≥40-bet floor per split (lower than the incumbent's: the day-off/slots-discipline policy cuts volume hard by design).

**Never auto-applied.** Registry strategies never merge `strategy.calibrated.yaml`, and this command never writes to `config/strategies/pv_orig.yaml` directly — a stray calibrate run must not silently change a registered, evaluating strategy's behavior. Applying a result below is a deliberate, owner-approved,
manual edit (the same protocol the original day-map decision used).

| min_merit | min_price_Δ | big_scam_Δ | even_ml | Train bets | Train ROI | Valid bets | Valid ROI |
|---|---|---|---|---|---|---|---|
| 2.0 | 10.0 | 100 | 120 | 1634 | +2.86% | 303 | +2.33% |
| 2.0 | 10.0 | 40 | 120 | 1812 | +2.02% | 341 | +2.06% |
| 2.0 | 10.0 | 80 | 120 | 1683 | +2.55% | 312 | +2.03% |
| 2.0 | 5.0 | 100 | 120 | 1664 | +2.86% | 304 | +1.99% |
| 2.0 | 5.0 | 40 | 120 | 1842 | +2.03% | 342 | +1.76% |
| 1.5 | 10.0 | 100 | 120 | 1682 | +2.72% | 309 | +1.71% |
| 2.0 | 5.0 | 80 | 120 | 1713 | +2.56% | 313 | +1.70% |
| 1.0 | 10.0 | 100 | 120 | 1726 | +2.99% | 322 | +1.51% |
| 2.0 | 10.0 | 100 | 110 | 1683 | +1.28% | 306 | +1.43% |
| 1.5 | 10.0 | 80 | 120 | 1731 | +2.43% | 318 | +1.42% |
