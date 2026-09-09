# Panthera Running Ledger

Updated: 2026-09-09T22:48:26Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 79 | 32-47-0 | $-591.63 | -7.49% ±12.9 | -0.7c (n=13, 23% pos, 16% cov) | 48% | 3 | screen only |
| fav_ml | baseline | 206 | 118-88-0 | $-948.62 | -4.60% ±5.8 | +0.1c (n=32, 28% pos, 15% cov) | 30% | 8 | screen only |
| pv_orig | aligned | 11 | 4-7-0 | $+85.30 | +7.75% ±56.3 | — | 79% | 3 | collecting (11/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 120 | 65-55-0 | $+1,089.01 | +9.08% ±9.4 | +1.5c (n=16, 44% pos, 13% cov) | 52% | 6 | SUPPORTED* |
| sharp_split | forward_test | 46 | 27-19-0 | $+663.20 | +14.42% ±14.6 | +0.0c (n=4, 0% pos, 8% cov) | 86% | 5 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-1,149.39 | -2.07% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 32-47-0 (0 void)
- **P/L:** $-591.63 on $7,900 risked
- **ROI:** -7.49% (±12.9 pts SE, own SD)
- **Pending:** 3

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 32-47-0 | $-591.63 | -7.49% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-06 | St. Louis Cardinals @ Colorado Rockies | Colorado Rockies ML | +117 | FP_ml | loss | $-100.00 |
| 2026-09-07 | Cincinnati Reds @ Los Angeles Dodgers | Cincinnati Reds ML | +152 | FP_ml | loss | $-100.00 |
| 2026-09-07 | Toronto Blue Jays @ Athletics | Athletics ML | +177 | FP_ml | win | $+177.00 |
| 2026-09-08 | Pittsburgh Pirates @ Chicago White Sox | Pittsburgh Pirates ML | +122 | FP_ml | win | $+122.00 |
| 2026-09-08 | Chicago Cubs @ Milwaukee Brewers | Chicago Cubs ML | +170 | FP_ml | loss | $-100.00 |
| 2026-09-08 | Washington Nationals @ San Diego Padres | Washington Nationals ML | +160 | FP_ml | loss | $-100.00 |
| 2026-09-08 | Cincinnati Reds @ Los Angeles Dodgers | Cincinnati Reds ML | +260 | FP_ml | loss | $-100.00 |
| 2026-09-09 | Toronto Blue Jays @ Athletics | Athletics ML | +138 | FP_ml | pending |  |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | San Francisco Giants ML | +101 | FP_ml | pending |  |
| 2026-09-09 | Colorado Rockies @ New York Yankees | Colorado Rockies ML | +203 | FP_ml | pending |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100, 200]

- **Record:** 118-88-0 (0 void)
- **P/L:** $-948.62 on $20,600 risked
- **ROI:** -4.60% (±5.8 pts SE, own SD)
- **Pending:** 8

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 118-88-0 | $-948.62 | -4.60% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-08 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | -110 | B_FAV | loss | $-100.00 |
| 2026-09-08 | Cincinnati Reds @ Los Angeles Dodgers | Los Angeles Dodgers ML | -310 | B_FAV | win | $+32.26 |
| 2026-09-09 | Toronto Blue Jays @ Athletics | Toronto Blue Jays ML | -160 | B_FAV | pending |  |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | -117 | B_FAV | pending |  |
| 2026-09-09 | Colorado Rockies @ New York Yankees | New York Yankees ML | -245 | B_FAV | pending |  |
| 2026-09-09 | Tampa Bay Rays @ Atlanta Braves | Atlanta Braves ML | -124 | B_FAV | pending |  |
| 2026-09-09 | Arizona Diamondbacks @ Kansas City Royals | Arizona Diamondbacks ML | -117 | B_FAV | pending |  |
| 2026-09-09 | Pittsburgh Pirates @ Chicago White Sox | Chicago White Sox ML | -132 | B_FAV | pending |  |
| 2026-09-09 | Chicago Cubs @ Milwaukee Brewers | Milwaukee Brewers ML | -133 | B_FAV | pending |  |
| 2026-09-09 | Cincinnati Reds @ Los Angeles Dodgers | Los Angeles Dodgers ML | -280 | B_FAV | pending |  |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 11/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 4-7-0 (0 void)
- **P/L:** $+85.30 on $1,100 risked
- **ROI:** +7.75% (±56.3 pts SE, own SD)
- **Pending:** 3

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-3-0 | $-216.67 | -54.17% |
| O3_totals | 0-2-0 | $-200.00 | -100.00% |
| O4 | 2-2-0 | $+1.97 | +0.49% |
| O5 | 1-0-0 | $+500.00 | +500.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | O1_big_scam | loss | $-100.00 |
| 2026-08-29 | Seattle Mariners @ Toronto Blue Jays | Seattle Mariners ML | -103 | O1_big_scam | loss | $-100.00 |
| 2026-09-02 | Detroit Tigers @ Minnesota Twins | Detroit Tigers +1.5 | -20 | O5 | win | $+500.00 |
| 2026-09-03 | Miami Marlins @ Kansas City Royals | Kansas City Royals ML | -120 | O1_big_scam | win | $+83.33 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Cleveland Guardians ML | -145 | O4 | win | $+68.97 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | O4 | loss | $-100.00 |
| 2026-09-05 | Washington Nationals @ Los Angeles Dodgers | Washington Nationals ML | +174 | O1_big_scam | loss | $-100.00 |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | -117 | O4 | pending |  |
| 2026-09-09 | Colorado Rockies @ New York Yankees | Colorado Rockies ML | +203 | O1_big_scam | pending |  |
| 2026-09-09 | Arizona Diamondbacks @ Kansas City Royals | Arizona Diamondbacks ML | -117 | O4 | pending |  |

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

**SUPPORTED** — ROI +9.08% over 120 graded picks. (Screen-grade evidence; see 'How to read this report'.)

- **Record:** 65-55-0 (0 void)
- **P/L:** $+1,089.01 on $12,000 risked
- **ROI:** +9.08% (±9.4 pts SE, own SD)
- **Pending:** 6

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 13-9-0 | $+394.46 | +17.93% |
| R3_era | 32-27-0 | $+334.86 | +5.68% |
| R3_series | 0-1-0 | $-100.00 | -100.00% |
| R4 | 5-3-0 | $+172.69 | +21.59% |
| R5 | 12-10-0 | $+478.96 | +21.77% |
| R7 | 3-5-0 | $-191.96 | -24.00% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 9-7-0 | $+237.08 | +14.82% |
| P | 35-27-0 | $+428.59 | +6.91% |
| V | 21-21-0 | $+423.34 | +10.08% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 40-32-0 | $+400.54 | +5.56% |
| V | 25-23-0 | $+688.47 | +14.34% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 45-37-0 | $+629.32 | +7.67% |
| rl | 20-18-0 | $+459.69 | +12.10% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-08 | Chicago Cubs @ Milwaukee Brewers | Chicago Cubs ML | +170 | R3 | loss | $-100.00 |
| 2026-09-08 | Washington Nationals @ San Diego Padres | Washington Nationals ML | +160 | R3_era | loss | $-100.00 |
| 2026-09-08 | Texas Rangers @ Seattle Mariners | Texas Rangers ML | +112 | R3 | win | $+112.00 |
| 2026-09-08 | Toronto Blue Jays @ Athletics | Toronto Blue Jays -1.5 | -115 | R5 | win | $+86.96 |
| 2026-09-09 | Toronto Blue Jays @ Athletics | Toronto Blue Jays ML | -160 | R3_era | pending |  |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | -117 | R3_era | pending |  |
| 2026-09-09 | Colorado Rockies @ New York Yankees | New York Yankees -1.5 | -118 | R5 | pending |  |
| 2026-09-09 | Tampa Bay Rays @ Atlanta Braves | Atlanta Braves -1.5 | +164 | R5 | pending |  |
| 2026-09-09 | Arizona Diamondbacks @ Kansas City Royals | Kansas City Royals ML | +102 | R3_era | pending |  |
| 2026-09-09 | Pittsburgh Pirates @ Chicago White Sox | Pittsburgh Pirates ML | +115 | R3_era | pending |  |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 27-19-0 (0 void)
- **P/L:** $+663.20 on $4,600 risked
- **ROI:** +14.42% (±14.6 pts SE, own SD)
- **Pending:** 5

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 27-19-0 | $+663.20 | +14.42% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-06 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | +105 | SS_ml | win | $+105.00 |
| 2026-09-06 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | -108 | SS_ml | win | $+92.59 |
| 2026-09-07 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | +111 | SS_ml | loss | $-100.00 |
| 2026-09-08 | Arizona Diamondbacks @ Kansas City Royals | Arizona Diamondbacks ML | -106 | SS_ml | win | $+94.34 |
| 2026-09-08 | Washington Nationals @ San Diego Padres | San Diego Padres ML | -190 | SS_ml | win | $+52.63 |
| 2026-09-09 | Toronto Blue Jays @ Athletics | Athletics ML | +138 | SS_ml | pending |  |
| 2026-09-09 | St. Louis Cardinals @ San Francisco Giants | San Francisco Giants ML | +101 | SS_ml | pending |  |
| 2026-09-09 | Tampa Bay Rays @ Atlanta Braves | Atlanta Braves ML | -124 | SS_ml | pending |  |
| 2026-09-09 | Pittsburgh Pirates @ Chicago White Sox | Pittsburgh Pirates ML | +115 | SS_ml | pending |  |
| 2026-09-09 | Chicago Cubs @ Milwaukee Brewers | Milwaukee Brewers ML | -133 | SS_ml | pending |  |

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

