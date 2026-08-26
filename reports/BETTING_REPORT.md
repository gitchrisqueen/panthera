# Panthera Running Ledger

Updated: 2026-08-26T16:03:56Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 24 | 9-15-0 | $-383.00 | -15.96% ±22.7 | +2.0c (n=1, 100% pos, 4% cov) | 40% | 1 | screen only |
| fav_ml | baseline | 114 | 72-42-0 | $+656.09 | +5.76% ±7.7 | +0.7c (n=12, 50% pos, 10% cov) | 22% | 3 | screen only |
| pv_orig | aligned | 4 | 1-3-0 | $-167.00 | -41.75% ±58.2 | — | 60% | 1 | collecting (4/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 55 | 29-26-0 | $+221.68 | +4.03% ±13.7 | +2.6c (n=7, 71% pos, 12% cov) | 41% | 3 | collecting (55/100) |
| sharp_split | forward_test | 14 | 9-5-0 | $+489.75 | +34.98% ±28.4 | — | 75% | 2 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-629.13 | -2.07% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 9-15-0 (0 void)
- **P/L:** $-383.00 on $2,400 risked
- **ROI:** -15.96% (±22.7 pts SE, own SD)
- **Pending:** 1

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 9-15-0 | $-383.00 | -15.96% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-25 | Boston Red Sox @ Miami Marlins | Miami Marlins ML | +131 | FP_ml | loss | $-100.00 |
| 2026-08-25 | Colorado Rockies @ Washington Nationals | Colorado Rockies ML | +133 | FP_ml | win | $+133.00 |
| 2026-08-25 | Houston Astros @ New York Yankees | Houston Astros ML | +127 | FP_ml | win | $+127.00 |
| 2026-08-25 | Milwaukee Brewers @ New York Mets | New York Mets ML | +141 | FP_ml | win | $+141.00 |
| 2026-08-25 | Los Angeles Dodgers @ Atlanta Braves | Atlanta Braves ML | +136 | FP_ml | win | $+136.00 |
| 2026-08-25 | Baltimore Orioles @ St. Louis Cardinals | Baltimore Orioles ML | +115 | FP_ml | win | $+115.00 |
| 2026-08-25 | Cleveland Guardians @ Los Angeles Angels | Los Angeles Angels ML | +128 | FP_ml | loss | $-100.00 |
| 2026-08-25 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -109 | FP_ml | loss | $-100.00 |
| 2026-08-25 | Minnesota Twins @ Athletics | Athletics ML | +135 | FP_ml | win | $+135.00 |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Arizona Diamondbacks ML | -105 | FP_ml | pending |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 72-42-0 (0 void)
- **P/L:** $+656.09 on $11,400 risked
- **ROI:** +5.76% (±7.7 pts SE, own SD)
- **Pending:** 3

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 72-42-0 | $+656.09 | +5.76% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-25 | Baltimore Orioles @ St. Louis Cardinals | St. Louis Cardinals ML | -128 | B_FAV | loss | $-100.00 |
| 2026-08-25 | Cleveland Guardians @ Los Angeles Angels | Cleveland Guardians ML | -142 | B_FAV | win | $+70.42 |
| 2026-08-25 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -109 | B_FAV | loss | $-100.00 |
| 2026-08-25 | Pittsburgh Pirates @ San Diego Padres | San Diego Padres ML | -122 | B_FAV | loss | $-100.00 |
| 2026-08-25 | Minnesota Twins @ Athletics | Minnesota Twins ML | -150 | B_FAV | loss | $-100.00 |
| 2026-08-25 | Philadelphia Phillies @ Seattle Mariners | Seattle Mariners ML | -106 | B_FAV | win | $+94.34 |
| 2026-08-25 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | -107 | B_FAV | win | $+93.46 |
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | B_FAV | pending |  |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -107 | B_FAV | pending |  |
| 2026-08-26 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | -109 | B_FAV | pending |  |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 4/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 1-3-0 (0 void)
- **P/L:** $-167.00 on $400 risked
- **ROI:** -41.75% (±58.2 pts SE, own SD)
- **Pending:** 1

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O3_totals | 0-2-0 | $-200.00 | -100.00% |
| O4 | 1-1-0 | $+33.00 | +16.50% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Washington Nationals @ Miami Marlins | Washington Nationals ML | +140 | O4 | loss | $-100.00 |
| 2026-08-25 | Colorado Rockies @ Washington Nationals | Colorado Rockies ML | +133 | O4 | win | $+133.00 |
| 2026-08-25 | Texas Rangers @ Chicago White Sox | under 7.0 | -103 | O3_totals | loss | $-100.00 |
| 2026-08-25 | Cleveland Guardians @ Los Angeles Angels | under 7.0 | -110 | O3_totals | loss | $-100.00 |
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | O1_big_scam | pending |  |

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

**INCONCLUSIVE — collecting data.** 55/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 29-26-0 (0 void)
- **P/L:** $+221.68 on $5,500 risked
- **ROI:** +4.03% (±13.7 pts SE, own SD)
- **Pending:** 3

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 5-6-0 | $-95.52 | -8.68% |
| R3_era | 12-9-0 | $+100.29 | +4.78% |
| R4 | 2-1-0 | $+18.87 | +6.29% |
| R5 | 8-8-0 | $+195.00 | +12.19% |
| R7 | 2-2-0 | $+3.04 | +0.76% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 2-4-0 | $-275.29 | -45.88% |
| P | 15-10-0 | $+225.97 | +9.04% |
| V | 12-12-0 | $+271.00 | +11.29% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 17-12-0 | $+150.68 | +5.20% |
| V | 12-14-0 | $+71.00 | +2.73% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 17-15-0 | $+4.77 | +0.15% |
| rl | 12-11-0 | $+216.91 | +9.43% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-24 | Pittsburgh Pirates @ San Diego Padres | Pittsburgh Pirates ML | +100 | R3 | win | $+100.00 |
| 2026-08-25 | Tampa Bay Rays @ Detroit Tigers | Tampa Bay Rays -1.5 | +135 | R5 | loss | $-100.00 |
| 2026-08-25 | Boston Red Sox @ Miami Marlins | Boston Red Sox -1.5 | +118 | R5 | win | $+118.00 |
| 2026-08-25 | Colorado Rockies @ Washington Nationals | Washington Nationals -1.5 | +135 | R5 | loss | $-100.00 |
| 2026-08-25 | Houston Astros @ New York Yankees | New York Yankees -1.5 | +143 | R5 | loss | $-100.00 |
| 2026-08-25 | Kansas City Royals @ Toronto Blue Jays | Kansas City Royals ML | +117 | R3 | win | $+117.00 |
| 2026-08-25 | Milwaukee Brewers @ New York Mets | New York Mets ML | +141 | R3 | win | $+141.00 |
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | R3_era | pending |  |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Arizona Diamondbacks ML | -105 | R3_era | pending |  |
| 2026-08-26 | Cincinnati Reds @ San Francisco Giants | Cincinnati Reds +1.5 | +140 | R4 | pending |  |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 9-5-0 (0 void)
- **P/L:** $+489.75 on $1,400 risked
- **ROI:** +34.98% (±28.4 pts SE, own SD)
- **Pending:** 2

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 9-5-0 | $+489.75 | +34.98% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-24 | Texas Rangers @ Chicago White Sox | Texas Rangers ML | +116 | SS_ml | win | $+116.00 |
| 2026-08-24 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -139 | SS_ml | win | $+71.94 |
| 2026-08-24 | Pittsburgh Pirates @ San Diego Padres | Pittsburgh Pirates ML | +100 | SS_ml | win | $+100.00 |
| 2026-08-24 | Philadelphia Phillies @ Seattle Mariners | Seattle Mariners ML | -101 | SS_ml | win | $+99.01 |
| 2026-08-24 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | +142 | SS_ml | win | $+142.00 |
| 2026-08-25 | Kansas City Royals @ Toronto Blue Jays | Kansas City Royals ML | +117 | SS_ml | win | $+117.00 |
| 2026-08-25 | Minnesota Twins @ Athletics | Minnesota Twins ML | -150 | SS_ml | loss | $-100.00 |
| 2026-08-25 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | -107 | SS_ml | win | $+93.46 |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -107 | SS_ml | pending |  |
| 2026-08-26 | Cincinnati Reds @ San Francisco Giants | Cincinnati Reds ML | -104 | SS_ml | pending |  |

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

