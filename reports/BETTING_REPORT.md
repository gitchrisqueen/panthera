# Panthera Running Ledger

Updated: 2026-09-14T14:44:08Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 99 | 39-60-0 | $-1,070.04 | -10.81% ±11.3 | -1.2c (n=14, 21% pos, 14% cov) | 45% | 0 | screen only |
| fav_ml | baseline | 247 | 144-103-0 | $-747.73 | -3.03% ±5.3 | +0.2c (n=34, 29% pos, 14% cov) | 34% | 0 | screen only |
| pv_orig | aligned | 18 | 6-12-0 | $-212.81 | -11.82% ±37.1 | — | 83% | 0 | collecting (18/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 145 | 81-64-0 | $+1,399.96 | +9.65% ±8.3 | +13.4c (n=17, 47% pos, 12% cov) | 57% | 0 | SUPPORTED* |
| sharp_split | forward_test | 66 | 39-27-0 | $+1,032.18 | +15.64% ±12.2 | -0.8c (n=5, 0% pos, 8% cov) | 82% | 0 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-1,045.09 | -1.56% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 39-60-0 (0 void)
- **P/L:** $-1,070.04 on $9,900 risked
- **ROI:** -10.81% (±11.3 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 39-60-0 | $-1,070.04 | -10.81% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-12 | Baltimore Orioles @ Toronto Blue Jays | Baltimore Orioles ML | +108 | FP_ml | loss | $-100.00 |
| 2026-09-12 | Cincinnati Reds @ Milwaukee Brewers | Cincinnati Reds ML | +170 | FP_ml | loss | $-100.00 |
| 2026-09-12 | Chicago White Sox @ St. Louis Cardinals | Chicago White Sox ML | -108 | FP_ml | win | $+92.59 |
| 2026-09-13 | Colorado Rockies @ Detroit Tigers | Colorado Rockies ML | +154 | FP_ml | loss | $-100.00 |
| 2026-09-13 | New York Mets @ New York Yankees | New York Mets ML | +151 | FP_ml | loss | $-100.00 |
| 2026-09-13 | Baltimore Orioles @ Toronto Blue Jays | Baltimore Orioles ML | +127 | FP_ml | loss | $-100.00 |
| 2026-09-13 | Cleveland Guardians @ Minnesota Twins | Cleveland Guardians ML | +108 | FP_ml | win | $+108.00 |
| 2026-09-13 | Chicago White Sox @ St. Louis Cardinals | St. Louis Cardinals ML | +110 | FP_ml | win | $+110.00 |
| 2026-09-13 | Pittsburgh Pirates @ Chicago Cubs | Pittsburgh Pirates ML | +133 | FP_ml | win | $+133.00 |
| 2026-09-13 | Kansas City Royals @ Boston Red Sox | Kansas City Royals ML | +154 | FP_ml | loss | $-100.00 |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100, 200]

- **Record:** 144-103-0 (0 void)
- **P/L:** $-747.73 on $24,700 risked
- **ROI:** -3.03% (±5.3 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 144-103-0 | $-747.73 | -3.03% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-13 | New York Mets @ New York Yankees | New York Yankees ML | -179 | B_FAV | win | $+55.87 |
| 2026-09-13 | Baltimore Orioles @ Toronto Blue Jays | Toronto Blue Jays ML | -150 | B_FAV | win | $+66.67 |
| 2026-09-13 | Houston Astros @ Tampa Bay Rays | Tampa Bay Rays ML | -134 | B_FAV | win | $+74.63 |
| 2026-09-13 | Los Angeles Dodgers @ Miami Marlins | Los Angeles Dodgers ML | -142 | B_FAV | loss | $-100.00 |
| 2026-09-13 | Cleveland Guardians @ Minnesota Twins | Minnesota Twins ML | -126 | B_FAV | loss | $-100.00 |
| 2026-09-13 | Cincinnati Reds @ Milwaukee Brewers | Milwaukee Brewers ML | -188 | B_FAV | loss | $-100.00 |
| 2026-09-13 | Chicago White Sox @ St. Louis Cardinals | Chicago White Sox ML | -126 | B_FAV | loss | $-100.00 |
| 2026-09-13 | Pittsburgh Pirates @ Chicago Cubs | Chicago Cubs ML | -154 | B_FAV | loss | $-100.00 |
| 2026-09-13 | Kansas City Royals @ Boston Red Sox | Boston Red Sox ML | -181 | B_FAV | win | $+55.25 |
| 2026-09-13 | San Diego Padres @ San Francisco Giants | San Diego Padres ML | -141 | B_FAV | win | $+70.92 |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 18/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 6-12-0 (0 void)
- **P/L:** $-212.81 on $1,800 risked
- **ROI:** -11.82% (±37.1 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-5-0 | $-416.67 | -69.44% |
| O3_totals | 0-2-0 | $-200.00 | -100.00% |
| O4 | 4-5-0 | $-96.14 | -10.68% |
| O5 | 1-0-0 | $+500.00 | +500.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Cleveland Guardians ML | -145 | O4 | win | $+68.97 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | O4 | loss | $-100.00 |
| 2026-09-05 | Washington Nationals @ Los Angeles Dodgers | Washington Nationals ML | +174 | O1_big_scam | loss | $-100.00 |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | -117 | O4 | loss | $-100.00 |
| 2026-09-09 | Colorado Rockies @ New York Yankees | Colorado Rockies ML | +203 | O1_big_scam | loss | $-100.00 |
| 2026-09-09 | Arizona Diamondbacks @ Kansas City Royals | Arizona Diamondbacks ML | -117 | O4 | loss | $-100.00 |
| 2026-09-11 | Seattle Mariners @ Athletics | Athletics ML | +139 | O4 | win | $+139.00 |
| 2026-09-11 | San Diego Padres @ San Francisco Giants | San Diego Padres ML | -159 | O4 | win | $+62.89 |
| 2026-09-12 | Pittsburgh Pirates @ Chicago Cubs | Pittsburgh Pirates ML | +105 | O1_big_scam | loss | $-100.00 |
| 2026-09-13 | Kansas City Royals @ Boston Red Sox | Kansas City Royals ML | +154 | O4 | loss | $-100.00 |

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

**SUPPORTED** — ROI +9.65% over 145 graded picks. (Screen-grade evidence; see 'How to read this report'.)

- **Record:** 81-64-0 (0 void)
- **P/L:** $+1,399.96 on $14,500 risked
- **ROI:** +9.65% (±8.3 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 15-10-0 | $+435.83 | +17.43% |
| R3_era | 44-34-0 | $+519.69 | +6.66% |
| R3_series | 0-1-0 | $-100.00 | -100.00% |
| R4 | 5-3-0 | $+172.69 | +21.59% |
| R5 | 13-11-0 | $+463.71 | +19.32% |
| R7 | 4-5-0 | $-91.96 | -10.22% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 12-10-0 | $+238.83 | +10.86% |
| P | 48-33-0 | $+737.79 | +9.11% |
| V | 21-21-0 | $+423.34 | +10.08% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 53-40-0 | $+509.74 | +5.48% |
| V | 28-24-0 | $+890.22 | +17.12% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 59-45-0 | $+855.52 | +8.23% |
| rl | 22-19-0 | $+544.44 | +13.28% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-12 | Pittsburgh Pirates @ Chicago Cubs | Chicago Cubs ML | -122 | R3_era | win | $+81.97 |
| 2026-09-12 | Baltimore Orioles @ Toronto Blue Jays | Toronto Blue Jays ML | -127 | R3_era | win | $+78.74 |
| 2026-09-12 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +125 | R3_era | loss | $-100.00 |
| 2026-09-12 | Cincinnati Reds @ Milwaukee Brewers | Milwaukee Brewers -1.5 | +100 | R7 | win | $+100.00 |
| 2026-09-13 | Colorado Rockies @ Detroit Tigers | Detroit Tigers ML | -184 | R3_era | win | $+54.35 |
| 2026-09-13 | Los Angeles Angels @ Washington Nationals | Washington Nationals ML | -129 | R3_era | win | $+77.52 |
| 2026-09-13 | Philadelphia Phillies @ Atlanta Braves | Atlanta Braves ML | -128 | R3_era | loss | $-100.00 |
| 2026-09-13 | New York Mets @ New York Yankees | New York Yankees ML | -179 | R3_era | win | $+55.87 |
| 2026-09-13 | Baltimore Orioles @ Toronto Blue Jays | Toronto Blue Jays ML | -150 | R3_era | win | $+66.67 |
| 2026-09-13 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +114 | R3_era | loss | $-100.00 |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 39-27-0 (0 void)
- **P/L:** $+1,032.18 on $6,600 risked
- **ROI:** +15.64% (±12.2 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 39-27-0 | $+1,032.18 | +15.64% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-12 | New York Mets @ New York Yankees | New York Mets ML | +141 | SS_ml | win | $+141.00 |
| 2026-09-12 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +125 | SS_ml | loss | $-100.00 |
| 2026-09-12 | Philadelphia Phillies @ Atlanta Braves | Philadelphia Phillies ML | +120 | SS_ml | loss | $-100.00 |
| 2026-09-12 | Seattle Mariners @ Athletics | Seattle Mariners ML | -170 | SS_ml | win | $+58.82 |
| 2026-09-13 | Colorado Rockies @ Detroit Tigers | Detroit Tigers ML | -184 | SS_ml | win | $+54.35 |
| 2026-09-13 | Los Angeles Angels @ Washington Nationals | Washington Nationals ML | -129 | SS_ml | win | $+77.52 |
| 2026-09-13 | Baltimore Orioles @ Toronto Blue Jays | Baltimore Orioles ML | +127 | SS_ml | loss | $-100.00 |
| 2026-09-13 | Houston Astros @ Tampa Bay Rays | Houston Astros ML | +114 | SS_ml | loss | $-100.00 |
| 2026-09-13 | Los Angeles Dodgers @ Miami Marlins | Miami Marlins ML | +120 | SS_ml | win | $+120.00 |
| 2026-09-13 | Cincinnati Reds @ Milwaukee Brewers | Milwaukee Brewers ML | -188 | SS_ml | loss | $-100.00 |

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

