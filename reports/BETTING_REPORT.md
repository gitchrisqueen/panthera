# Panthera Running Ledger

Updated: 2026-08-18T16:39:19Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
not a tournament.

## Strategy comparison

| Strategy | Kind | Graded | Record | P/L | ROI (±SE) | Avg CLV | Overlap | Pending | Status |
|---|---|---|---|---|---|---|---|---|---|
| fav_ml | baseline | 12 | 8-4-0 | $+109.91 | +9.16% ±23.7 | +1.8c (n=4, 75% pos, 36% cov) | 8% | 0 | screen only |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 7 | 0-7-0 | $-700.00 | -100.00% ±0.0 | +0.7c (n=3, 33% pos, 50% cov) | 14% | 0 | collecting (7/100) |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-2,036.74 | -18.19% |  |  |  |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 8-4-0 (0 void)
- **P/L:** $+109.91 on $1,200 risked
- **ROI:** +9.16% (±23.7 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 8-4-0 | $+109.91 | +9.16% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-17 | St. Louis Cardinals @ Cincinnati Reds | St. Louis Cardinals ML | -118 | B_FAV | loss | $-100.00 |
| 2026-08-17 | Baltimore Orioles @ Tampa Bay Rays | Tampa Bay Rays ML | -160 | B_FAV | win | $+62.50 |
| 2026-08-17 | Miami Marlins @ Philadelphia Phillies | Philadelphia Phillies ML | -245 | B_FAV | win | $+40.82 |
| 2026-08-17 | Detroit Tigers @ Pittsburgh Pirates | Pittsburgh Pirates ML | -105 | B_FAV | loss | $-100.00 |
| 2026-08-17 | Arizona Diamondbacks @ Boston Red Sox | Boston Red Sox ML | -132 | B_FAV | win | $+75.76 |
| 2026-08-17 | San Diego Padres @ New York Mets | New York Mets ML | -120 | B_FAV | win | $+83.33 |
| 2026-08-17 | Athletics @ Kansas City Royals | Kansas City Royals ML | -180 | B_FAV | win | $+55.56 |
| 2026-08-17 | Atlanta Braves @ Minnesota Twins | Atlanta Braves ML | -127 | B_FAV | loss | $-100.00 |
| 2026-08-17 | Chicago White Sox @ Chicago Cubs | Chicago Cubs ML | -158 | B_FAV | win | $+63.29 |
| 2026-08-17 | Los Angeles Dodgers @ Colorado Rockies | Los Angeles Dodgers ML | -265 | B_FAV | win | $+37.74 |

## Strategy: pv_v2

_Calibrated P/V config VVPPPP-m5-e120-h200 — the best of 768 distinct sweep hypotheses (2,304 configs, heavy_fav parameter inert): validation +1.40%, train -1.83%, zero configs positive on both splits, and the archives priced no run lines, so R4/R5/R7 were swept as ML bets rather than the RL bets placed live. Live segment 1 verdict recorded at 100 graded picks; the strategy continues afterwards as the labeled control — a deliberate, documented choice._

**Verdict segment** (config hashes: 6f0d0924d4):

**INCONCLUSIVE — collecting data.** 93/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 38-55-0 (0 void)
- **P/L:** $-1,446.65 on $9,300 risked
- **ROI:** -15.56% (±10.9 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 11-17-0 | $-492.70 | -17.60% |
| R3_form | 8-13-0 | $-520.05 | -24.76% |
| R3_series | 4-10-0 | $-513.51 | -36.68% |
| R4 | 6-8-0 | $-367.70 | -26.26% |
| R5 | 7-5-0 | $+496.04 | +41.34% |
| R7 | 2-2-0 | $-48.73 | -12.18% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 8-8-0 | $+148.75 | +9.30% |
| P | 20-34-0 | $-1,613.44 | -29.88% |
| V | 10-13-0 | $+18.04 | +0.78% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 23-35-0 | $-1,523.69 | -26.27% |
| V | 15-20-0 | $+77.04 | +2.20% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 23-40-0 | $-1,526.26 | -24.23% |
| rl | 15-15-0 | $+79.61 | +2.65% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-15 | San Diego Padres @ Cleveland Guardians | San Diego Padres +1.5 | -198 | R4 | loss | $-100.00 |
| 2026-08-15 | Seattle Mariners @ Houston Astros | Seattle Mariners +1.5 | -190 | R4 | win | $+52.63 |
| 2026-08-15 | Boston Red Sox @ Pittsburgh Pirates | Pittsburgh Pirates +1.5 | -175 | R4 | loss | $-100.00 |
| 2026-08-15 | Kansas City Royals @ Los Angeles Angels | Kansas City Royals ML | +135 | R3_series | loss | $-100.00 |
| 2026-08-15 | Texas Rangers @ Athletics | Texas Rangers ML | -160 | R3 | win | $+62.50 |
| 2026-08-16 | Baltimore Orioles @ Tampa Bay Rays | Tampa Bay Rays ML | -140 | R3_form | loss | $-100.00 |
| 2026-08-16 | Arizona Diamondbacks @ Atlanta Braves | Arizona Diamondbacks ML | +112 | R3_series | loss | $-100.00 |
| 2026-08-16 | San Diego Padres @ Cleveland Guardians | Cleveland Guardians +1.5 | -175 | R4 | loss | $-100.00 |
| 2026-08-16 | Chicago White Sox @ Detroit Tigers | Chicago White Sox +1.5 | +159 | R4 | win | $+159.00 |
| 2026-08-16 | Philadelphia Phillies @ Minnesota Twins | Minnesota Twins +1.5 | -170 | R4 | loss | $-100.00 |

## Strategy: pv_v3

_The documented P/V strategy with its full dossier finally active: day/slot classification, line movement, and the ERA inputs (R3_era, R4 evenness, R8 veto) that were silently dormant in pv_v2 because the live schedule hydrate never returned pitcher stats. Same calibrated parameters as pv_v2 (VVPPPP-m5-e120-h200); the only change is ERA availability. Evaluation clock starts at registration — no pre-registration picks pool here._

**Verdict segment** (config hashes: e7a93ebed7):

**INCONCLUSIVE — collecting data.** 7/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 0-7-0 (0 void)
- **P/L:** $-700.00 on $700 risked
- **ROI:** -100.00% (±0.0 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 0-2-0 | $-200.00 | -100.00% |
| R3_era | 0-1-0 | $-100.00 | -100.00% |
| R5 | 0-4-0 | $-400.00 | -100.00% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| P | 0-1-0 | $-100.00 | -100.00% |
| V | 0-6-0 | $-600.00 | -100.00% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 0-1-0 | $-100.00 | -100.00% |
| V | 0-6-0 | $-600.00 | -100.00% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 0-3-0 | $-300.00 | -100.00% |
| rl | 0-4-0 | $-400.00 | -100.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-16 | Seattle Mariners @ Houston Astros | Houston Astros ML | -121 | R3_era | loss | $-100.00 |
| 2026-08-17 | St. Louis Cardinals @ Cincinnati Reds | St. Louis Cardinals -1.5 | +137 | R5 | loss | $-100.00 |
| 2026-08-17 | St. Louis Cardinals @ Cincinnati Reds | St. Louis Cardinals -1.5 | +131 | R5 | loss | $-100.00 |
| 2026-08-17 | Baltimore Orioles @ Tampa Bay Rays | Tampa Bay Rays -1.5 | +132 | R5 | loss | $-100.00 |
| 2026-08-17 | Miami Marlins @ Philadelphia Phillies | Miami Marlins ML | +212 | R3 | loss | $-100.00 |
| 2026-08-17 | Detroit Tigers @ Pittsburgh Pirates | Pittsburgh Pirates -1.5 | -175 | R5 | loss | $-100.00 |
| 2026-08-17 | Arizona Diamondbacks @ Boston Red Sox | Arizona Diamondbacks ML | +119 | R3 | loss | $-100.00 |

