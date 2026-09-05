# Panthera Running Ledger

Updated: 2026-09-05T16:55:02Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 64 | 26-38-0 | $-511.22 | -7.99% ±14.2 | -1.0c (n=12, 17% pos, 19% cov) | 42% | 0 | screen only |
| fav_ml | baseline | 179 | 106-73-0 | $-176.46 | -0.99% ±6.2 | +0.7c (n=30, 30% pos, 17% cov) | 28% | 0 | screen only |
| pv_orig | aligned | 10 | 4-6-0 | $+185.30 | +18.53% ±61.1 | — | 70% | 0 | collecting (10/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 99 | 54-45-0 | $+970.57 | +9.80% ±10.4 | +1.2c (n=15, 40% pos, 15% cov) | 49% | 0 | collecting (99/100) |
| sharp_split | forward_test | 37 | 20-17-0 | $+245.53 | +6.64% ±16.6 | +0.0c (n=4, 0% pos, 11% cov) | 81% | 0 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-732.93 | -1.52% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 26-38-0 (0 void)
- **P/L:** $-511.22 on $6,400 risked
- **ROI:** -7.99% (±14.2 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 26-38-0 | $-511.22 | -7.99% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-03 | Athletics @ Seattle Mariners | Athletics ML | +180 | FP_ml | win | $+180.00 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Detroit Tigers ML | +122 | FP_ml | loss | $-100.00 |
| 2026-09-04 | Boston Red Sox @ Baltimore Orioles | Baltimore Orioles ML | -102 | FP_ml | loss | $-100.00 |
| 2026-09-04 | San Francisco Giants @ New York Mets | San Francisco Giants ML | +170 | FP_ml | loss | $-100.00 |
| 2026-09-04 | Chicago Cubs @ Miami Marlins | Miami Marlins ML | +146 | FP_ml | loss | $-100.00 |
| 2026-09-04 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | -117 | FP_ml | loss | $-100.00 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | FP_ml | loss | $-100.00 |
| 2026-09-04 | St. Louis Cardinals @ Colorado Rockies | Colorado Rockies ML | +109 | FP_ml | loss | $-100.00 |
| 2026-09-04 | New York Yankees @ San Diego Padres | San Diego Padres ML | +100 | FP_ml | win | $+100.00 |
| 2026-09-04 | Washington Nationals @ Los Angeles Dodgers | Washington Nationals ML | +225 | FP_ml | loss | $-100.00 |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 106-73-0 (0 void)
- **P/L:** $-176.46 on $17,900 risked
- **ROI:** -0.99% (±6.2 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 106-73-0 | $-176.46 | -0.99% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-04 | San Francisco Giants @ New York Mets | New York Mets ML | -200 | B_FAV | win | $+50.00 |
| 2026-09-04 | Chicago Cubs @ Miami Marlins | Chicago Cubs ML | -165 | B_FAV | win | $+60.61 |
| 2026-09-04 | Minnesota Twins @ Chicago White Sox | Chicago White Sox ML | -122 | B_FAV | win | $+81.97 |
| 2026-09-04 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | -117 | B_FAV | loss | $-100.00 |
| 2026-09-04 | Arizona Diamondbacks @ Houston Astros | Houston Astros ML | -130 | B_FAV | win | $+76.92 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | B_FAV | loss | $-100.00 |
| 2026-09-04 | St. Louis Cardinals @ Colorado Rockies | St. Louis Cardinals ML | -126 | B_FAV | win | $+79.37 |
| 2026-09-04 | New York Yankees @ San Diego Padres | New York Yankees ML | -117 | B_FAV | loss | $-100.00 |
| 2026-09-04 | Washington Nationals @ Los Angeles Dodgers | Los Angeles Dodgers ML | -270 | B_FAV | win | $+37.04 |
| 2026-09-04 | Athletics @ Seattle Mariners | Seattle Mariners ML | -225 | B_FAV | loss | $-100.00 |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 10/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 4-6-0 (0 void)
- **P/L:** $+185.30 on $1,000 risked
- **ROI:** +18.53% (±61.1 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-2-0 | $-116.67 | -38.89% |
| O3_totals | 0-2-0 | $-200.00 | -100.00% |
| O4 | 2-2-0 | $+1.97 | +0.49% |
| O5 | 1-0-0 | $+500.00 | +500.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Washington Nationals @ Miami Marlins | Washington Nationals ML | +140 | O4 | loss | $-100.00 |
| 2026-08-25 | Colorado Rockies @ Washington Nationals | Colorado Rockies ML | +133 | O4 | win | $+133.00 |
| 2026-08-25 | Texas Rangers @ Chicago White Sox | under 7.0 | -103 | O3_totals | loss | $-100.00 |
| 2026-08-25 | Cleveland Guardians @ Los Angeles Angels | under 7.0 | -110 | O3_totals | loss | $-100.00 |
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | O1_big_scam | loss | $-100.00 |
| 2026-08-29 | Seattle Mariners @ Toronto Blue Jays | Seattle Mariners ML | -103 | O1_big_scam | loss | $-100.00 |
| 2026-09-02 | Detroit Tigers @ Minnesota Twins | Detroit Tigers +1.5 | -20 | O5 | win | $+500.00 |
| 2026-09-03 | Miami Marlins @ Kansas City Royals | Kansas City Royals ML | -120 | O1_big_scam | win | $+83.33 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Cleveland Guardians ML | -145 | O4 | win | $+68.97 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | O4 | loss | $-100.00 |

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

**INCONCLUSIVE — collecting data.** 99/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 54-45-0 (0 void)
- **P/L:** $+970.57 on $9,900 risked
- **ROI:** +9.80% (±10.4 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 10-8-0 | $+111.12 | +6.17% |
| R3_era | 25-20-0 | $+386.72 | +8.59% |
| R3_series | 0-1-0 | $-100.00 | -100.00% |
| R4 | 5-2-0 | $+272.69 | +38.96% |
| R5 | 11-9-0 | $+492.00 | +24.60% |
| R7 | 3-5-0 | $-191.96 | -24.00% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 9-7-0 | $+237.08 | +14.82% |
| P | 28-22-0 | $+280.45 | +5.61% |
| V | 17-16-0 | $+453.04 | +13.73% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 33-27-0 | $+252.40 | +4.21% |
| V | 21-18-0 | $+718.17 | +18.41% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 35-29-0 | $+397.84 | +6.22% |
| rl | 19-16-0 | $+572.73 | +16.36% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-03 | Miami Marlins @ Kansas City Royals | Miami Marlins +1.5 | -195 | R4 | loss | $-100.00 |
| 2026-09-03 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | +107 | R3_era | win | $+107.00 |
| 2026-09-03 | Athletics @ Seattle Mariners | Seattle Mariners -1.5 | +105 | R7 | loss | $-100.00 |
| 2026-09-03 | St. Louis Cardinals @ Los Angeles Dodgers | Los Angeles Dodgers -1.5 | -130 | R7 | loss | $-100.00 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Detroit Tigers ML | +110 | R3_era | loss | $-100.00 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Cleveland Guardians ML | -145 | R3 | win | $+68.97 |
| 2026-09-04 | Los Angeles Angels @ Pittsburgh Pirates | Pittsburgh Pirates ML | -196 | R3 | win | $+51.02 |
| 2026-09-04 | Boston Red Sox @ Baltimore Orioles | Baltimore Orioles +1.5 | -170 | R4 | win | $+58.82 |
| 2026-09-04 | San Francisco Giants @ New York Mets | New York Mets -1.5 | +105 | R7 | win | $+105.00 |
| 2026-09-04 | Chicago Cubs @ Miami Marlins | Chicago Cubs ML | -165 | R3 | win | $+60.61 |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 20-17-0 (0 void)
- **P/L:** $+245.53 on $3,700 risked
- **ROI:** +6.64% (±16.6 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 20-17-0 | $+245.53 | +6.64% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-02 | Miami Marlins @ Kansas City Royals | Kansas City Royals ML | -112 | SS_ml | loss | $-100.00 |
| 2026-09-02 | Chicago White Sox @ Houston Astros | Houston Astros ML | -141 | SS_ml | win | $+70.92 |
| 2026-09-03 | Milwaukee Brewers @ Chicago Cubs | Milwaukee Brewers ML | -123 | SS_ml | loss | $-100.00 |
| 2026-09-03 | Tampa Bay Rays @ Texas Rangers | Tampa Bay Rays ML | -125 | SS_ml | loss | $-100.00 |
| 2026-09-04 | Los Angeles Angels @ Pittsburgh Pirates | Pittsburgh Pirates ML | -196 | SS_ml | win | $+51.02 |
| 2026-09-04 | Minnesota Twins @ Chicago White Sox | Chicago White Sox ML | -122 | SS_ml | win | $+81.97 |
| 2026-09-04 | Tampa Bay Rays @ Texas Rangers | Tampa Bay Rays ML | +100 | SS_ml | win | $+100.00 |
| 2026-09-04 | Arizona Diamondbacks @ Houston Astros | Houston Astros ML | -130 | SS_ml | win | $+76.92 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Toronto Blue Jays ML | +100 | SS_ml | win | $+100.00 |
| 2026-09-04 | New York Yankees @ San Diego Padres | San Diego Padres ML | +100 | SS_ml | win | $+100.00 |

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

