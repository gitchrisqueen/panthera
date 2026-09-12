# Panthera Running Ledger

Updated: 2026-09-12T20:55:13Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 88 | 35-53-0 | $-813.63 | -9.25% ±12.1 | -0.7c (n=13, 23% pos, 14% cov) | 47% | 4 | screen only |
| fav_ml | baseline | 224 | 129-95-0 | $-963.24 | -4.30% ±5.6 | +0.0c (n=33, 27% pos, 14% cov) | 34% | 10 | screen only |
| pv_orig | aligned | 16 | 6-10-0 | $-12.81 | -0.80% ±41.0 | — | 82% | 1 | collecting (16/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 133 | 73-60-0 | $+1,225.32 | +9.21% ±8.8 | +1.5c (n=16, 44% pos, 12% cov) | 55% | 6 | SUPPORTED* |
| sharp_split | forward_test | 55 | 34-21-0 | $+1,180.49 | +21.46% ±13.3 | -0.8c (n=5, 0% pos, 8% cov) | 82% | 5 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-830.52 | -1.36% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 35-53-0 (0 void)
- **P/L:** $-813.63 on $8,800 risked
- **ROI:** -9.25% (±12.1 pts SE, own SD)
- **Pending:** 4

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 35-53-0 | $-813.63 | -9.25% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-11 | Pittsburgh Pirates @ Chicago Cubs | Pittsburgh Pirates ML | +162 | FP_ml | loss | $-100.00 |
| 2026-09-11 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +162 | FP_ml | loss | $-100.00 |
| 2026-09-11 | Philadelphia Phillies @ Atlanta Braves | Philadelphia Phillies ML | +157 | FP_ml | loss | $-100.00 |
| 2026-09-11 | Cincinnati Reds @ Milwaukee Brewers | Cincinnati Reds ML | +169 | FP_ml | loss | $-100.00 |
| 2026-09-11 | Seattle Mariners @ Athletics | Athletics ML | +139 | FP_ml | win | $+139.00 |
| 2026-09-11 | San Diego Padres @ San Francisco Giants | San Francisco Giants ML | +135 | FP_ml | loss | $-100.00 |
| 2026-09-12 | Pittsburgh Pirates @ Chicago Cubs | Pittsburgh Pirates ML | +105 | FP_ml | pending |  |
| 2026-09-12 | Baltimore Orioles @ Toronto Blue Jays | Baltimore Orioles ML | +108 | FP_ml | pending |  |
| 2026-09-12 | Cincinnati Reds @ Milwaukee Brewers | Cincinnati Reds ML | +170 | FP_ml | pending |  |
| 2026-09-12 | Chicago White Sox @ St. Louis Cardinals | Chicago White Sox ML | -108 | FP_ml | pending |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100, 200]

- **Record:** 129-95-0 (0 void)
- **P/L:** $-963.24 on $22,400 risked
- **ROI:** -4.30% (±5.6 pts SE, own SD)
- **Pending:** 10

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 129-95-0 | $-963.24 | -4.30% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-12 | Colorado Rockies @ Detroit Tigers | Detroit Tigers ML | -168 | B_FAV | pending |  |
| 2026-09-12 | New York Mets @ New York Yankees | New York Yankees ML | -168 | B_FAV | pending |  |
| 2026-09-12 | Pittsburgh Pirates @ Chicago Cubs | Chicago Cubs ML | -122 | B_FAV | pending |  |
| 2026-09-12 | Baltimore Orioles @ Toronto Blue Jays | Toronto Blue Jays ML | -127 | B_FAV | pending |  |
| 2026-09-12 | Houston Astros @ Tampa Bay Rays | Tampa Bay Rays ML | -146 | B_FAV | pending |  |
| 2026-09-12 | Cincinnati Reds @ Milwaukee Brewers | Milwaukee Brewers ML | -201 | B_FAV | pending |  |
| 2026-09-12 | Philadelphia Phillies @ Atlanta Braves | Atlanta Braves ML | -142 | B_FAV | pending |  |
| 2026-09-12 | Chicago White Sox @ St. Louis Cardinals | Chicago White Sox ML | -108 | B_FAV | pending |  |
| 2026-09-12 | Texas Rangers @ Arizona Diamondbacks | Arizona Diamondbacks ML | -130 | B_FAV | pending |  |
| 2026-09-12 | Seattle Mariners @ Athletics | Seattle Mariners ML | -170 | B_FAV | pending |  |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 16/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 6-10-0 (0 void)
- **P/L:** $-12.81 on $1,600 risked
- **ROI:** -0.80% (±41.0 pts SE, own SD)
- **Pending:** 1

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-4-0 | $-316.67 | -63.33% |
| O3_totals | 0-2-0 | $-200.00 | -100.00% |
| O4 | 4-4-0 | $+3.86 | +0.48% |
| O5 | 1-0-0 | $+500.00 | +500.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-03 | Miami Marlins @ Kansas City Royals | Kansas City Royals ML | -120 | O1_big_scam | win | $+83.33 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Cleveland Guardians ML | -145 | O4 | win | $+68.97 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | O4 | loss | $-100.00 |
| 2026-09-05 | Washington Nationals @ Los Angeles Dodgers | Washington Nationals ML | +174 | O1_big_scam | loss | $-100.00 |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | -117 | O4 | loss | $-100.00 |
| 2026-09-09 | Colorado Rockies @ New York Yankees | Colorado Rockies ML | +203 | O1_big_scam | loss | $-100.00 |
| 2026-09-09 | Arizona Diamondbacks @ Kansas City Royals | Arizona Diamondbacks ML | -117 | O4 | loss | $-100.00 |
| 2026-09-11 | Seattle Mariners @ Athletics | Athletics ML | +139 | O4 | win | $+139.00 |
| 2026-09-11 | San Diego Padres @ San Francisco Giants | San Diego Padres ML | -159 | O4 | win | $+62.89 |
| 2026-09-12 | Pittsburgh Pirates @ Chicago Cubs | Pittsburgh Pirates ML | +105 | O1_big_scam | pending |  |

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

**SUPPORTED** — ROI +9.21% over 133 graded picks. (Screen-grade evidence; see 'How to read this report'.)

- **Record:** 73-60-0 (0 void)
- **P/L:** $+1,225.32 on $13,300 risked
- **ROI:** +9.21% (±8.8 pts SE, own SD)
- **Pending:** 6

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 15-10-0 | $+435.83 | +17.43% |
| R3_era | 37-30-0 | $+445.05 | +6.64% |
| R3_series | 0-1-0 | $-100.00 | -100.00% |
| R4 | 5-3-0 | $+172.69 | +21.59% |
| R5 | 13-11-0 | $+463.71 | +19.32% |
| R7 | 3-5-0 | $-191.96 | -24.00% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 12-10-0 | $+238.83 | +10.86% |
| P | 40-29-0 | $+563.15 | +8.16% |
| V | 21-21-0 | $+423.34 | +10.08% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 45-36-0 | $+335.10 | +4.14% |
| V | 28-24-0 | $+890.22 | +17.12% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 52-41-0 | $+780.88 | +8.40% |
| rl | 21-19-0 | $+444.44 | +11.11% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-11 | Philadelphia Phillies @ Atlanta Braves | Atlanta Braves ML | -184 | R3_era | win | $+54.35 |
| 2026-09-11 | Cincinnati Reds @ Milwaukee Brewers | Cincinnati Reds ML | +169 | R3_era | loss | $-100.00 |
| 2026-09-11 | Cleveland Guardians @ Minnesota Twins | Cleveland Guardians ML | -116 | R3_era | win | $+86.21 |
| 2026-09-11 | Chicago White Sox @ St. Louis Cardinals | St. Louis Cardinals ML | -111 | R3 | win | $+90.09 |
| 2026-09-12 | Colorado Rockies @ Detroit Tigers | Detroit Tigers ML | -168 | R3_era | pending |  |
| 2026-09-12 | New York Mets @ New York Yankees | New York Yankees ML | -168 | R3_era | pending |  |
| 2026-09-12 | Pittsburgh Pirates @ Chicago Cubs | Chicago Cubs ML | -122 | R3_era | pending |  |
| 2026-09-12 | Baltimore Orioles @ Toronto Blue Jays | Toronto Blue Jays ML | -127 | R3_era | pending |  |
| 2026-09-12 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +125 | R3_era | pending |  |
| 2026-09-12 | Cincinnati Reds @ Milwaukee Brewers | Milwaukee Brewers -1.5 | +100 | R7 | pending |  |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 34-21-0 (0 void)
- **P/L:** $+1,180.49 on $5,500 risked
- **ROI:** +21.46% (±13.3 pts SE, own SD)
- **Pending:** 5

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 34-21-0 | $+1,180.49 | +21.46% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-09 | Chicago Cubs @ Milwaukee Brewers | Milwaukee Brewers ML | -133 | SS_ml | win | $+75.19 |
| 2026-09-11 | Chicago White Sox @ St. Louis Cardinals | Chicago White Sox ML | -105 | SS_ml | loss | $-100.00 |
| 2026-09-11 | Seattle Mariners @ Athletics | Athletics ML | +139 | SS_ml | win | $+139.00 |
| 2026-09-11 | Texas Rangers @ Arizona Diamondbacks | Arizona Diamondbacks ML | -116 | SS_ml | win | $+86.21 |
| 2026-09-11 | San Diego Padres @ San Francisco Giants | San Diego Padres ML | -159 | SS_ml | win | $+62.89 |
| 2026-09-12 | Colorado Rockies @ Detroit Tigers | Colorado Rockies ML | +142 | SS_ml | pending |  |
| 2026-09-12 | New York Mets @ New York Yankees | New York Mets ML | +141 | SS_ml | pending |  |
| 2026-09-12 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +125 | SS_ml | pending |  |
| 2026-09-12 | Philadelphia Phillies @ Atlanta Braves | Philadelphia Phillies ML | +120 | SS_ml | pending |  |
| 2026-09-12 | Seattle Mariners @ Athletics | Seattle Mariners ML | -170 | SS_ml | pending |  |

## Retroactive replay (NOT an evaluation — read before citing)

_Picks below were computed by `panthera-mvp replay` over odds/game
history this pipeline had already captured — they were never placed
in real time and cost no API credits. They are useful as an early,
qualitative read on an engine before its live sample accumulates,
but they are look-ahead-free only with respect to the STRATEGY
(no future prices/results feed a pick's own inputs) — the SAMPLE
itself was picked after every outcome in it was already known, so
it carries none of the evidentiary weight of a forward paper-trade
or a train/validate backtest split. Never pooled into any
strategy's verdict, portfolio total, or the tables above._

### pv_orig (retroactive)

- Record 7-7-0, P/L $-135.83, ROI -9.70% (14 graded, descriptive only)

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-1-0 | $-3.85 | -1.93% |
| O3_totals | 6-5-0 | $-31.98 | -2.91% |
| O4 | 0-1-0 | $-100.00 | -100.00% |

