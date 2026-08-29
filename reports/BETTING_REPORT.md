# Panthera Running Ledger

Updated: 2026-08-29T02:56:09Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 26 | 11-15-0 | $-123.76 | -4.76% ±22.4 | +0.5c (n=8, 25% pos, 25% cov) | 38% | 6 | screen only |
| fav_ml | baseline | 119 | 72-47-0 | $+156.09 | +1.31% ±7.6 | +0.5c (n=24, 29% pos, 19% cov) | 23% | 11 | screen only |
| pv_orig | aligned | 5 | 1-4-0 | $-267.00 | -53.40% ±46.6 | — | 60% | 0 | collecting (5/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 60 | 33-27-0 | $+640.92 | +10.68% ±13.4 | +1.4c (n=13, 38% pos, 20% cov) | 43% | 5 | collecting (60/100) |
| sharp_split | forward_test | 16 | 10-6-0 | $+485.90 | +30.37% ±26.5 | +0.0c (n=4, 0% pos, 20% cov) | 80% | 4 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-554.50 | -1.74% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 11-15-0 (0 void)
- **P/L:** $-123.76 on $2,600 risked
- **ROI:** -4.76% (±22.4 pts SE, own SD)
- **Pending:** 6

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 11-15-0 | $-123.76 | -4.76% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-25 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -109 | FP_ml | loss | $-100.00 |
| 2026-08-25 | Minnesota Twins @ Athletics | Athletics ML | +135 | FP_ml | win | $+135.00 |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Arizona Diamondbacks ML | -105 | FP_ml | win | $+95.24 |
| 2026-08-28 | Cincinnati Reds @ Chicago Cubs | Cincinnati Reds ML | +164 | FP_ml | win | $+164.00 |
| 2026-08-28 | Los Angeles Dodgers @ Detroit Tigers | Detroit Tigers ML | +180 | FP_ml | pending |  |
| 2026-08-28 | Miami Marlins @ Washington Nationals | Washington Nationals ML | +130 | FP_ml | pending |  |
| 2026-08-28 | San Diego Padres @ Tampa Bay Rays | San Diego Padres ML | +112 | FP_ml | pending |  |
| 2026-08-28 | Colorado Rockies @ Atlanta Braves | Colorado Rockies ML | +193 | FP_ml | pending |  |
| 2026-08-28 | Boston Red Sox @ New York Yankees | Boston Red Sox ML | +140 | FP_ml | pending |  |
| 2026-08-28 | Texas Rangers @ Milwaukee Brewers | Texas Rangers ML | +152 | FP_ml | pending |  |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 72-47-0 (0 void)
- **P/L:** $+156.09 on $11,900 risked
- **ROI:** +1.31% (±7.6 pts SE, own SD)
- **Pending:** 11

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 72-47-0 | $+156.09 | +1.31% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-28 | Miami Marlins @ Washington Nationals | Miami Marlins ML | -154 | B_FAV | pending |  |
| 2026-08-28 | Kansas City Royals @ Cleveland Guardians | Cleveland Guardians ML | -138 | B_FAV | pending |  |
| 2026-08-28 | Houston Astros @ New York Mets | Houston Astros ML | -126 | B_FAV | pending |  |
| 2026-08-28 | San Diego Padres @ Tampa Bay Rays | Tampa Bay Rays ML | -132 | B_FAV | pending |  |
| 2026-08-28 | Colorado Rockies @ Atlanta Braves | Atlanta Braves ML | -225 | B_FAV | pending |  |
| 2026-08-28 | Boston Red Sox @ New York Yankees | New York Yankees ML | -165 | B_FAV | pending |  |
| 2026-08-28 | Texas Rangers @ Milwaukee Brewers | Milwaukee Brewers ML | -179 | B_FAV | pending |  |
| 2026-08-28 | Chicago White Sox @ Minnesota Twins | Minnesota Twins ML | -117 | B_FAV | pending |  |
| 2026-08-28 | Pittsburgh Pirates @ St. Louis Cardinals | Pittsburgh Pirates ML | -117 | B_FAV | pending |  |
| 2026-08-28 | Philadelphia Phillies @ Los Angeles Angels | Philadelphia Phillies ML | -137 | B_FAV | pending |  |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 5/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 1-4-0 (0 void)
- **P/L:** $-267.00 on $500 risked
- **ROI:** -53.40% (±46.6 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 0-1-0 | $-100.00 | -100.00% |
| O3_totals | 0-2-0 | $-200.00 | -100.00% |
| O4 | 1-1-0 | $+33.00 | +16.50% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-23 | Washington Nationals @ Miami Marlins | Washington Nationals ML | +140 | O4 | loss | $-100.00 |
| 2026-08-25 | Colorado Rockies @ Washington Nationals | Colorado Rockies ML | +133 | O4 | win | $+133.00 |
| 2026-08-25 | Texas Rangers @ Chicago White Sox | under 7.0 | -103 | O3_totals | loss | $-100.00 |
| 2026-08-25 | Cleveland Guardians @ Los Angeles Angels | under 7.0 | -110 | O3_totals | loss | $-100.00 |
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | O1_big_scam | loss | $-100.00 |

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

**INCONCLUSIVE — collecting data.** 60/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 33-27-0 (0 void)
- **P/L:** $+640.92 on $6,000 risked
- **ROI:** +10.68% (±13.4 pts SE, own SD)
- **Pending:** 5

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 5-6-0 | $-95.52 | -8.68% |
| R3_era | 15-10-0 | $+379.53 | +15.18% |
| R4 | 3-1-0 | $+158.87 | +39.72% |
| R5 | 8-8-0 | $+195.00 | +12.19% |
| R7 | 2-2-0 | $+3.04 | +0.76% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 5-5-0 | $-20.05 | -2.00% |
| P | 16-10-0 | $+389.97 | +15.00% |
| V | 12-12-0 | $+271.00 | +11.29% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 20-13-0 | $+449.92 | +13.63% |
| V | 13-14-0 | $+191.00 | +7.07% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 20-16-0 | $+284.01 | +7.89% |
| rl | 13-11-0 | $+356.91 | +14.87% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-26 | Tampa Bay Rays @ Detroit Tigers | Detroit Tigers ML | -117 | R3_era | loss | $-100.00 |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Arizona Diamondbacks ML | -105 | R3_era | win | $+95.24 |
| 2026-08-26 | Cincinnati Reds @ San Francisco Giants | Cincinnati Reds +1.5 | +140 | R4 | win | $+140.00 |
| 2026-08-26 | Minnesota Twins @ Athletics | Athletics ML | +120 | R3_era | win | $+120.00 |
| 2026-08-28 | Cincinnati Reds @ Chicago Cubs | Cincinnati Reds ML | +164 | R3_era | win | $+164.00 |
| 2026-08-28 | Los Angeles Dodgers @ Detroit Tigers | Los Angeles Dodgers -1.5 | -120 | R7 | pending |  |
| 2026-08-28 | Miami Marlins @ Washington Nationals | Miami Marlins ML | -154 | R3_era | pending |  |
| 2026-08-28 | Kansas City Royals @ Cleveland Guardians | Kansas City Royals ML | +119 | R3_era | pending |  |
| 2026-08-28 | Houston Astros @ New York Mets | Houston Astros ML | -126 | R3_era | pending |  |
| 2026-08-28 | San Diego Padres @ Tampa Bay Rays | Tampa Bay Rays ML | -132 | R3_era | pending |  |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 10-6-0 (0 void)
- **P/L:** $+485.90 on $1,600 risked
- **ROI:** +30.37% (±26.5 pts SE, own SD)
- **Pending:** 4

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 10-6-0 | $+485.90 | +30.37% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-08-24 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | +142 | SS_ml | win | $+142.00 |
| 2026-08-25 | Kansas City Royals @ Toronto Blue Jays | Kansas City Royals ML | +117 | SS_ml | win | $+117.00 |
| 2026-08-25 | Minnesota Twins @ Athletics | Minnesota Twins ML | -150 | SS_ml | loss | $-100.00 |
| 2026-08-25 | Cincinnati Reds @ San Francisco Giants | San Francisco Giants ML | -107 | SS_ml | win | $+93.46 |
| 2026-08-26 | Chicago Cubs @ Arizona Diamondbacks | Chicago Cubs ML | -107 | SS_ml | loss | $-100.00 |
| 2026-08-26 | Cincinnati Reds @ San Francisco Giants | Cincinnati Reds ML | -104 | SS_ml | win | $+96.15 |
| 2026-08-28 | Miami Marlins @ Washington Nationals | Miami Marlins ML | -154 | SS_ml | pending |  |
| 2026-08-28 | Kansas City Royals @ Cleveland Guardians | Cleveland Guardians ML | -138 | SS_ml | pending |  |
| 2026-08-28 | San Diego Padres @ Tampa Bay Rays | Tampa Bay Rays ML | -132 | SS_ml | pending |  |
| 2026-08-28 | Boston Red Sox @ New York Yankees | Boston Red Sox ML | +140 | SS_ml | pending |  |

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

