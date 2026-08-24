# Panthera Running Ledger

Updated: 2026-08-24T21:15:19Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 7 | 1-6-0 | $-499.00 | -71.29% ±28.7 | — | 43% | 7 | screen only |
| fav_ml | baseline | 89 | 62-27-0 | $+1,414.34 | +15.89% ±8.3 | +0.9c (n=11, 55% pos, 11% cov) | 21% | 10 | screen only |
| pv_orig | aligned | 1 | 0-1-0 | $-100.00 | -100.00% | — | 100% | 0 | collecting (1/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 43 | 21-22-0 | $-338.32 | -7.87% ±14.9 | +2.6c (n=7, 71% pos, 15% cov) | 41% | 6 | collecting (43/100) |
| sharp_split | forward_test | 6 | 2-4-0 | $-149.66 | -24.94% ±48.1 | — | 73% | 5 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-1,119.29 | -4.68% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 1-6-0 (0 void)
- **P/L:** $-499.00 on $700 risked
- **ROI:** -71.29% (±28.7 pts SE, own SD)
- **Pending:** 7

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 1-6-0 | $-499.00 | -71.29% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Los Angeles Angels @ Texas Rangers | Los Angeles Angels ML | +140 | FP_ml | loss | $-100.00 |
| 2026-08-23 | San Francisco Giants @ Boston Red Sox | San Francisco Giants ML | +182 | FP_ml | loss | $-100.00 |
| 2026-08-23 | Atlanta Braves @ Milwaukee Brewers | Atlanta Braves ML | +101 | FP_ml | win | $+101.00 |
| 2026-08-24 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | +116 | FP_ml | pending |  |
| 2026-08-24 | Colorado Rockies @ Washington Nationals | Colorado Rockies ML | +174 | FP_ml | pending |  |
| 2026-08-24 | Texas Rangers @ Chicago White Sox | Texas Rangers ML | +116 | FP_ml | pending |  |
| 2026-08-24 | Cleveland Guardians @ Los Angeles Angels | Los Angeles Angels ML | +143 | FP_ml | pending |  |
| 2026-08-24 | Chicago Cubs @ Arizona Diamondbacks | Arizona Diamondbacks ML | +124 | FP_ml | pending |  |
| 2026-08-24 | Minnesota Twins @ Athletics | Athletics ML | +128 | FP_ml | pending |  |
| 2026-08-24 | Philadelphia Phillies @ Seattle Mariners | Philadelphia Phillies ML | -110 | FP_ml | pending |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 62-27-0 (0 void)
- **P/L:** $+1,414.34 on $8,900 risked
- **ROI:** +15.89% (±8.3 pts SE, own SD)
- **Pending:** 10

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 62-27-0 | $+1,414.34 | +15.89% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-24 | Tampa Bay Rays @ Detroit Tigers | Tampa Bay Rays ML | -128 | B_FAV | pending |  |
| 2026-08-24 | Boston Red Sox @ Miami Marlins | Boston Red Sox ML | -122 | B_FAV | pending |  |
| 2026-08-24 | Colorado Rockies @ Washington Nationals | Washington Nationals ML | -200 | B_FAV | pending |  |
| 2026-08-24 | Texas Rangers @ Chicago White Sox | Chicago White Sox ML | -128 | B_FAV | pending |  |
| 2026-08-24 | Cleveland Guardians @ Los Angeles Angels | Cleveland Guardians ML | -161 | B_FAV | pending |  |
| 2026-08-24 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -139 | B_FAV | pending |  |
| 2026-08-24 | Pittsburgh Pirates @ San Diego Padres | San Diego Padres ML | -112 | B_FAV | pending |  |
| 2026-08-24 | Minnesota Twins @ Athletics | Minnesota Twins ML | -142 | B_FAV | pending |  |
| 2026-08-24 | Philadelphia Phillies @ Seattle Mariners | Philadelphia Phillies ML | -110 | B_FAV | pending |  |
| 2026-08-24 | Cincinnati Reds @ San Francisco Giants | Cincinnati Reds ML | -161 | B_FAV | pending |  |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 1/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 0-1-0 (0 void)
- **P/L:** $-100.00 on $100 risked
- **ROI:** -100.00%
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O4 | 0-1-0 | $-100.00 | -100.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Washington Nationals @ Miami Marlins | Washington Nationals ML | +140 | O4 | loss | $-100.00 |

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

**INCONCLUSIVE — collecting data.** 43/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 21-22-0 (0 void)
- **P/L:** $-338.32 on $4,300 risked
- **ROI:** -7.87% (±14.9 pts SE, own SD)
- **Pending:** 6

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 2-6-0 | $-453.52 | -56.69% |
| R3_era | 12-9-0 | $+100.29 | +4.78% |
| R4 | 2-1-0 | $+18.87 | +6.29% |
| R5 | 3-4-0 | $-7.00 | -1.00% |
| R7 | 2-2-0 | $+3.04 | +0.76% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 2-4-0 | $-275.29 | -45.88% |
| P | 15-10-0 | $+225.97 | +9.04% |
| V | 4-8-0 | $-289.00 | -24.08% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 17-12-0 | $+150.68 | +5.20% |
| V | 4-10-0 | $-489.00 | -34.93% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 14-15-0 | $-353.23 | -12.18% |
| rl | 7-7-0 | $+14.91 | +1.06% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Toronto Blue Jays @ New York Yankees | Toronto Blue Jays ML | +116 | R3_era | loss | $-100.00 |
| 2026-08-23 | Washington Nationals @ Miami Marlins | Miami Marlins ML | -156 | R3_era | win | $+64.10 |
| 2026-08-23 | Detroit Tigers @ Kansas City Royals | Kansas City Royals +1.5 | -168 | R4 | win | $+59.52 |
| 2026-08-23 | Athletics @ Houston Astros | Athletics ML | +156 | R3_era | win | $+156.00 |
| 2026-08-24 | Tampa Bay Rays @ Detroit Tigers | Tampa Bay Rays -1.5 | +128 | R5 | pending |  |
| 2026-08-24 | Boston Red Sox @ Miami Marlins | Boston Red Sox -1.5 | +136 | R5 | pending |  |
| 2026-08-24 | Texas Rangers @ Chicago White Sox | Chicago White Sox -1.5 | +155 | R5 | pending |  |
| 2026-08-24 | Cleveland Guardians @ Los Angeles Angels | Cleveland Guardians -1.5 | +105 | R5 | pending |  |
| 2026-08-24 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs -1.5 | +115 | R5 | pending |  |
| 2026-08-24 | Pittsburgh Pirates @ San Diego Padres | Pittsburgh Pirates ML | +100 | R3 | pending |  |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 2-4-0 (0 void)
- **P/L:** $-149.66 on $600 risked
- **ROI:** -24.94% (±48.1 pts SE, own SD)
- **Pending:** 5

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 2-4-0 | $-149.66 | -24.94% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Detroit Tigers @ Kansas City Royals | Detroit Tigers ML | -112 | SS_ml | loss | $-100.00 |
| 2026-08-23 | Athletics @ Houston Astros | Athletics ML | +156 | SS_ml | win | $+156.00 |
| 2026-08-23 | New York Mets @ Chicago White Sox | New York Mets ML | -106 | SS_ml | loss | $-100.00 |
| 2026-08-23 | Cleveland Guardians @ Colorado Rockies | Colorado Rockies ML | +148 | SS_ml | loss | $-100.00 |
| 2026-08-23 | San Francisco Giants @ Boston Red Sox | San Francisco Giants ML | +182 | SS_ml | loss | $-100.00 |
| 2026-08-24 | Texas Rangers @ Chicago White Sox | Texas Rangers ML | +116 | SS_ml | pending |  |
| 2026-08-24 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -139 | SS_ml | pending |  |
| 2026-08-24 | Pittsburgh Pirates @ San Diego Padres | Pittsburgh Pirates ML | +100 | SS_ml | pending |  |
| 2026-08-24 | Philadelphia Phillies @ Seattle Mariners | Seattle Mariners ML | -101 | SS_ml | pending |  |
| 2026-08-24 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | +142 | SS_ml | pending |  |

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

