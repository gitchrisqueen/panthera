# Panthera Running Ledger

Updated: 2026-08-19T16:38:49Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fav_ml | baseline | 27 | 20-7-0 | $+601.32 | +22.27% ±14.4 | +1.8c (n=4, 75% pos, 13% cov) | 13% | 4 | screen only |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 13 | 4-9-0 | $-389.00 | -29.92% ±30.4 | +0.7c (n=3, 33% pos, 19% cov) | 24% | 4 | collecting (13/100) |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-1,234.33 | -9.28% |  |  |  |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 20-7-0 (0 void)
- **P/L:** $+601.32 on $2,700 risked
- **ROI:** +22.27% (±14.4 pts SE, own SD)
- **Pending:** 4

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 20-7-0 | $+601.32 | +22.27% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-18 | Atlanta Braves @ Minnesota Twins | Atlanta Braves ML | -140 | B_FAV | loss | $-100.00 |
| 2026-08-18 | Seattle Mariners @ Milwaukee Brewers | Milwaukee Brewers ML | -172 | B_FAV | win | $+58.14 |
| 2026-08-18 | Washington Nationals @ Texas Rangers | Texas Rangers ML | -148 | B_FAV | win | $+67.57 |
| 2026-08-18 | Chicago White Sox @ Chicago Cubs | Chicago Cubs ML | -172 | B_FAV | win | $+58.14 |
| 2026-08-18 | Los Angeles Angels @ Houston Astros | Houston Astros ML | -161 | B_FAV | loss | $-100.00 |
| 2026-08-18 | Los Angeles Dodgers @ Colorado Rockies | Los Angeles Dodgers ML | -190 | B_FAV | win | $+52.63 |
| 2026-08-19 | Detroit Tigers @ Pittsburgh Pirates | Pittsburgh Pirates ML | -153 | B_FAV | pending |  |
| 2026-08-19 | San Diego Padres @ New York Mets | San Diego Padres ML | -135 | B_FAV | pending |  |
| 2026-08-19 | Atlanta Braves @ Minnesota Twins | Atlanta Braves ML | -110 | B_FAV | pending |  |
| 2026-08-19 | Chicago White Sox @ Chicago Cubs | Chicago Cubs ML | -141 | B_FAV | pending |  |

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

**INCONCLUSIVE — collecting data.** 13/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 4-9-0 (0 void)
- **P/L:** $-389.00 on $1,300 risked
- **ROI:** -29.92% (±30.4 pts SE, own SD)
- **Pending:** 4

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 0-4-0 | $-400.00 | -100.00% |
| R3_era | 1-1-0 | $+18.00 | +9.00% |
| R5 | 3-4-0 | $-7.00 | -1.00% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| P | 0-1-0 | $-100.00 | -100.00% |
| V | 4-8-0 | $-289.00 | -24.08% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 0-1-0 | $-100.00 | -100.00% |
| V | 4-8-0 | $-289.00 | -24.08% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 1-5-0 | $-382.00 | -63.67% |
| rl | 3-4-0 | $-7.00 | -1.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-18 | New York Yankees @ Baltimore Orioles | New York Yankees -1.5 | +145 | R5 | win | $+145.00 |
| 2026-08-18 | Detroit Tigers @ Pittsburgh Pirates | Detroit Tigers ML | +135 | R3 | loss | $-100.00 |
| 2026-08-18 | San Francisco Giants @ Cleveland Guardians | Cleveland Guardians -1.5 | +113 | R5 | win | $+113.00 |
| 2026-08-18 | St. Louis Cardinals @ Cincinnati Reds | St. Louis Cardinals -1.5 | +135 | R5 | win | $+135.00 |
| 2026-08-18 | Toronto Blue Jays @ Tampa Bay Rays | Toronto Blue Jays ML | +118 | R3_era | win | $+118.00 |
| 2026-08-18 | Miami Marlins @ Philadelphia Phillies | Miami Marlins ML | +190 | R3 | loss | $-100.00 |
| 2026-08-19 | Detroit Tigers @ Pittsburgh Pirates | Pittsburgh Pirates ML | -153 | R3_era | pending |  |
| 2026-08-19 | San Diego Padres @ New York Mets | San Diego Padres ML | -135 | R3_era | pending |  |
| 2026-08-19 | Atlanta Braves @ Minnesota Twins | Minnesota Twins +1.5 | -168 | R4 | pending |  |
| 2026-08-19 | Chicago White Sox @ Chicago Cubs | Chicago Cubs ML | -141 | R3_era | pending |  |

