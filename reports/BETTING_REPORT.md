# Panthera Running Ledger

Updated: 2026-09-08T18:01:28Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 75 | 31-44-0 | $-413.63 | -5.52% ±13.3 | -0.7c (n=13, 23% pos, 17% cov) | 45% | 0 | screen only |
| fav_ml | baseline | 198 | 114-84-0 | $-737.48 | -3.72% ±6.0 | +0.4c (n=31, 29% pos, 16% cov) | 30% | 0 | screen only |
| pv_orig | aligned | 11 | 4-7-0 | $+85.30 | +7.75% ±56.3 | — | 73% | 0 | collecting (11/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 114 | 62-52-0 | $+1,095.71 | +9.61% ±9.7 | +1.2c (n=15, 40% pos, 13% cov) | 52% | 0 | SUPPORTED* |
| sharp_split | forward_test | 44 | 25-19-0 | $+516.23 | +11.73% ±15.1 | +0.0c (n=4, 0% pos, 9% cov) | 84% | 0 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-900.52 | -1.68% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 31-44-0 (0 void)
- **P/L:** $-413.63 on $7,500 risked
- **ROI:** -5.52% (±13.3 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 31-44-0 | $-413.63 | -5.52% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-05 | Arizona Diamondbacks @ Houston Astros | Houston Astros ML | -108 | FP_ml | loss | $-100.00 |
| 2026-09-05 | New York Yankees @ San Diego Padres | San Diego Padres ML | -128 | FP_ml | loss | $-100.00 |
| 2026-09-05 | St. Louis Cardinals @ Colorado Rockies | Colorado Rockies ML | +107 | FP_ml | win | $+107.00 |
| 2026-09-05 | Washington Nationals @ Los Angeles Dodgers | Washington Nationals ML | +174 | FP_ml | loss | $-100.00 |
| 2026-09-05 | Athletics @ Seattle Mariners | Athletics ML | +200 | FP_ml | win | $+200.00 |
| 2026-09-06 | Chicago Cubs @ Miami Marlins | Miami Marlins ML | +121 | FP_ml | win | $+121.00 |
| 2026-09-06 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | -108 | FP_ml | win | $+92.59 |
| 2026-09-06 | St. Louis Cardinals @ Colorado Rockies | Colorado Rockies ML | +117 | FP_ml | loss | $-100.00 |
| 2026-09-07 | Cincinnati Reds @ Los Angeles Dodgers | Cincinnati Reds ML | +152 | FP_ml | loss | $-100.00 |
| 2026-09-07 | Toronto Blue Jays @ Athletics | Athletics ML | +177 | FP_ml | win | $+177.00 |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 114-84-0 (0 void)
- **P/L:** $-737.48 on $19,800 risked
- **ROI:** -3.72% (±6.0 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 114-84-0 | $-737.48 | -3.72% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-06 | San Francisco Giants @ New York Mets | New York Mets ML | -168 | B_FAV | win | $+59.52 |
| 2026-09-06 | Chicago Cubs @ Miami Marlins | Chicago Cubs ML | -143 | B_FAV | loss | $-100.00 |
| 2026-09-06 | Arizona Diamondbacks @ Houston Astros | Houston Astros ML | -112 | B_FAV | loss | $-100.00 |
| 2026-09-06 | Toronto Blue Jays @ Kansas City Royals | Toronto Blue Jays ML | -122 | B_FAV | loss | $-100.00 |
| 2026-09-06 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | -108 | B_FAV | win | $+92.59 |
| 2026-09-06 | St. Louis Cardinals @ Colorado Rockies | St. Louis Cardinals ML | -135 | B_FAV | win | $+74.07 |
| 2026-09-06 | Washington Nationals @ Los Angeles Dodgers | Los Angeles Dodgers ML | -200 | B_FAV | win | $+50.00 |
| 2026-09-07 | St. Louis Cardinals @ San Francisco Giants | San Francisco Giants ML | -129 | B_FAV | win | $+77.52 |
| 2026-09-07 | Cincinnati Reds @ Los Angeles Dodgers | Los Angeles Dodgers ML | -177 | B_FAV | win | $+56.50 |
| 2026-09-07 | Toronto Blue Jays @ Athletics | Toronto Blue Jays ML | -208 | B_FAV | loss | $-100.00 |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 11/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 4-7-0 (0 void)
- **P/L:** $+85.30 on $1,100 risked
- **ROI:** +7.75% (±56.3 pts SE, own SD)
- **Pending:** 0

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
| 2026-08-25 | Colorado Rockies @ Washington Nationals | Colorado Rockies ML | +133 | O4 | win | $+133.00 |
| 2026-08-25 | Texas Rangers @ Chicago White Sox | under 7.0 | -103 | O3_totals | loss | $-100.00 |
| 2026-08-25 | Cleveland Guardians @ Los Angeles Angels | under 7.0 | -110 | O3_totals | loss | $-100.00 |
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | O1_big_scam | loss | $-100.00 |
| 2026-08-29 | Seattle Mariners @ Toronto Blue Jays | Seattle Mariners ML | -103 | O1_big_scam | loss | $-100.00 |
| 2026-09-02 | Detroit Tigers @ Minnesota Twins | Detroit Tigers +1.5 | -20 | O5 | win | $+500.00 |
| 2026-09-03 | Miami Marlins @ Kansas City Royals | Kansas City Royals ML | -120 | O1_big_scam | win | $+83.33 |
| 2026-09-04 | Detroit Tigers @ Cleveland Guardians | Cleveland Guardians ML | -145 | O4 | win | $+68.97 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -117 | O4 | loss | $-100.00 |
| 2026-09-05 | Washington Nationals @ Los Angeles Dodgers | Washington Nationals ML | +174 | O1_big_scam | loss | $-100.00 |

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

**SUPPORTED** — ROI +9.61% over 114 graded picks. (Screen-grade evidence; see 'How to read this report'.)

- **Record:** 62-52-0 (0 void)
- **P/L:** $+1,095.71 on $11,400 risked
- **ROI:** +9.61% (±9.7 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 11-8-0 | $+288.12 | +15.16% |
| R3_era | 32-26-0 | $+434.86 | +7.50% |
| R3_series | 0-1-0 | $-100.00 | -100.00% |
| R4 | 5-3-0 | $+172.69 | +21.59% |
| R5 | 11-9-0 | $+492.00 | +24.60% |
| R7 | 3-5-0 | $-191.96 | -24.00% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 9-7-0 | $+237.08 | +14.82% |
| P | 35-27-0 | $+428.59 | +6.91% |
| V | 18-18-0 | $+430.04 | +11.95% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 40-32-0 | $+400.54 | +5.56% |
| V | 22-20-0 | $+695.17 | +16.55% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 43-35-0 | $+622.98 | +7.99% |
| rl | 19-17-0 | $+472.73 | +13.13% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-05 | New York Yankees @ San Diego Padres | San Diego Padres ML | -128 | R3_era | loss | $-100.00 |
| 2026-09-06 | San Francisco Giants @ New York Mets | San Francisco Giants ML | +143 | R3_era | loss | $-100.00 |
| 2026-09-06 | Chicago Cubs @ Miami Marlins | Chicago Cubs ML | -143 | R3_era | loss | $-100.00 |
| 2026-09-06 | Arizona Diamondbacks @ Houston Astros | Arizona Diamondbacks ML | -105 | R3_era | win | $+95.24 |
| 2026-09-06 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | +105 | R3_era | win | $+105.00 |
| 2026-09-06 | Tampa Bay Rays @ Texas Rangers | Tampa Bay Rays +1.5 | +150 | R4 | loss | $-100.00 |
| 2026-09-06 | St. Louis Cardinals @ Colorado Rockies | St. Louis Cardinals ML | -135 | R3_era | win | $+74.07 |
| 2026-09-07 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | +111 | R3_era | loss | $-100.00 |
| 2026-09-07 | Cincinnati Reds @ Los Angeles Dodgers | Cincinnati Reds ML | +152 | R3_era | loss | $-100.00 |
| 2026-09-07 | Toronto Blue Jays @ Athletics | Athletics ML | +177 | R3 | win | $+177.00 |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 25-19-0 (0 void)
- **P/L:** $+516.23 on $4,400 risked
- **ROI:** +11.73% (±15.1 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 25-19-0 | $+516.23 | +11.73% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-04 | Arizona Diamondbacks @ Houston Astros | Houston Astros ML | -130 | SS_ml | win | $+76.92 |
| 2026-09-04 | Toronto Blue Jays @ Kansas City Royals | Toronto Blue Jays ML | +100 | SS_ml | win | $+100.00 |
| 2026-09-04 | New York Yankees @ San Diego Padres | San Diego Padres ML | +100 | SS_ml | win | $+100.00 |
| 2026-09-05 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | -108 | SS_ml | loss | $-100.00 |
| 2026-09-05 | Arizona Diamondbacks @ Houston Astros | Arizona Diamondbacks ML | -108 | SS_ml | win | $+92.59 |
| 2026-09-06 | San Francisco Giants @ New York Mets | New York Mets ML | -168 | SS_ml | win | $+59.52 |
| 2026-09-06 | Chicago Cubs @ Miami Marlins | Miami Marlins ML | +121 | SS_ml | win | $+121.00 |
| 2026-09-06 | Toronto Blue Jays @ Kansas City Royals | Kansas City Royals ML | +105 | SS_ml | win | $+105.00 |
| 2026-09-06 | Tampa Bay Rays @ Texas Rangers | Texas Rangers ML | -108 | SS_ml | win | $+92.59 |
| 2026-09-07 | St. Louis Cardinals @ San Francisco Giants | St. Louis Cardinals ML | +111 | SS_ml | loss | $-100.00 |

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

