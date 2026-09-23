# Panthera Running Ledger

Updated: 2026-09-23T20:55:27Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 149 | 62-87-0 | $-951.41 | -6.39% ±9.3 | -0.9c (n=22, 32% pos, 15% cov) | 40% | 0 | screen only |
| fav_ml | baseline | 352 | 210-142-0 | $-215.03 | -0.61% ±4.4 | +0.4c (n=49, 37% pos, 13% cov) | 35% | 16 | screen only |
| pv_orig | aligned | 27 | 9-18-0 | $-556.51 | -20.61% ±26.5 | — | 77% | 3 | collecting (27/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 195 | 110-85-0 | $+2,139.36 | +10.97% ±7.2 | +10.5c (n=22, 50% pos, 11% cov) | 54% | 6 | SUPPORTED* |
| sharp_split | forward_test | 97 | 53-44-0 | $+455.94 | +4.70% ±9.9 | -0.3c (n=8, 12% pos, 8% cov) | 80% | 0 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-574.30 | -0.63% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 62-87-0 (0 void)
- **P/L:** $-951.41 on $14,900 risked
- **ROI:** -6.39% (±9.3 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 62-87-0 | $-951.41 | -6.39% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-20 | Detroit Tigers @ Chicago White Sox | Chicago White Sox ML | -115 | FP_ml | win | $+86.96 |
| 2026-09-20 | Seattle Mariners @ Colorado Rockies | Colorado Rockies ML | +135 | FP_ml | loss | $-100.00 |
| 2026-09-20 | Milwaukee Brewers @ Baltimore Orioles | Baltimore Orioles ML | +176 | FP_ml | loss | $-100.00 |
| 2026-09-21 | Washington Nationals @ Detroit Tigers | Washington Nationals ML | +114 | FP_ml | loss | $-100.00 |
| 2026-09-22 | Tampa Bay Rays @ New York Yankees | Tampa Bay Rays ML | +111 | FP_ml | win | $+111.00 |
| 2026-09-22 | Washington Nationals @ Detroit Tigers | Washington Nationals ML | +130 | FP_ml | win | $+130.00 |
| 2026-09-22 | Milwaukee Brewers @ Philadelphia Phillies | Milwaukee Brewers ML | +120 | FP_ml | loss | $-100.00 |
| 2026-09-22 | Cincinnati Reds @ Atlanta Braves | Cincinnati Reds ML | +200 | FP_ml | win | $+200.00 |
| 2026-09-22 | Chicago White Sox @ Kansas City Royals | Kansas City Royals ML | +102 | FP_ml | loss | $-100.00 |
| 2026-09-22 | Miami Marlins @ Chicago Cubs | Miami Marlins ML | +171 | FP_ml | win | $+171.00 |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100, 200]

- **Record:** 210-142-0 (0 void)
- **P/L:** $-215.03 on $35,200 risked
- **ROI:** -0.61% (±4.4 pts SE, own SD)
- **Pending:** 16

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 210-142-0 | $-215.03 | -0.61% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-23 | Tampa Bay Rays @ New York Yankees | New York Yankees ML | -137 | B_FAV | pending |  |
| 2026-09-23 | Cleveland Guardians @ Boston Red Sox | Boston Red Sox ML | -135 | B_FAV | pending |  |
| 2026-09-23 | Cincinnati Reds @ Atlanta Braves | Atlanta Braves ML | -260 | B_FAV | pending |  |
| 2026-09-23 | Chicago White Sox @ Kansas City Royals | Chicago White Sox ML | -119 | B_FAV | pending |  |
| 2026-09-23 | Miami Marlins @ Chicago Cubs | Chicago Cubs ML | -180 | B_FAV | pending |  |
| 2026-09-23 | New York Mets @ Texas Rangers | Texas Rangers ML | -109 | B_FAV | pending |  |
| 2026-09-23 | Arizona Diamondbacks @ Colorado Rockies | Arizona Diamondbacks ML | -159 | B_FAV | pending |  |
| 2026-09-23 | Los Angeles Angels @ Athletics | Los Angeles Angels ML | -133 | B_FAV | pending |  |
| 2026-09-23 | San Diego Padres @ Los Angeles Dodgers | Los Angeles Dodgers ML | -220 | B_FAV | pending |  |
| 2026-09-23 | Houston Astros @ Seattle Mariners | Seattle Mariners ML | -123 | B_FAV | pending |  |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 27/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 9-18-0 (0 void)
- **P/L:** $-556.51 on $2,700 risked
- **ROI:** -20.61% (±26.5 pts SE, own SD)
- **Pending:** 3

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-6-0 | $-516.67 | -73.81% |
| O3_totals | 2-4-0 | $-212.67 | -35.45% |
| O4 | 5-8-0 | $-327.17 | -25.17% |
| O5 | 1-0-0 | $+500.00 | +500.00% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-15 | Baltimore Orioles @ New York Mets | New York Mets ML | -132 | O4 | loss | $-100.00 |
| 2026-09-15 | San Francisco Giants @ St. Louis Cardinals | under 8.0 | -110 | O3_totals | loss | $-100.00 |
| 2026-09-15 | Boston Red Sox @ Texas Rangers | under 7.5 | -102 | O3_totals | win | $+98.04 |
| 2026-09-16 | Detroit Tigers @ Toronto Blue Jays | Detroit Tigers ML | +115 | O4 | loss | $-100.00 |
| 2026-09-19 | Atlanta Braves @ Houston Astros | Houston Astros ML | -134 | O1_big_scam | loss | $-100.00 |
| 2026-09-22 | Tampa Bay Rays @ New York Yankees | under 6.0 | -113 | O3_totals | loss | $-100.00 |
| 2026-09-22 | Cleveland Guardians @ Boston Red Sox | under 6.0 | -112 | O3_totals | win | $+89.29 |
| 2026-09-23 | Toronto Blue Jays @ Baltimore Orioles | Baltimore Orioles ML | -126 | O4 | pending |  |
| 2026-09-23 | Minnesota Twins @ San Francisco Giants | Minnesota Twins ML | -155 | O4 | pending |  |
| 2026-09-23 | Milwaukee Brewers @ Philadelphia Phillies | Milwaukee Brewers ML | -126 | O4 | pending |  |

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

**SUPPORTED** — ROI +10.97% over 195 graded picks. (Screen-grade evidence; see 'How to read this report'.)

- **Record:** 110-85-0 (0 void)
- **P/L:** $+2,139.36 on $19,500 risked
- **ROI:** +10.97% (±7.2 pts SE, own SD)
- **Pending:** 6

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 23-13-0 | $+1,085.24 | +30.15% |
| R3_era | 57-45-0 | $+494.41 | +4.85% |
| R3_series | 0-1-0 | $-100.00 | -100.00% |
| R4 | 7-3-0 | $+375.23 | +37.52% |
| R5 | 17-17-0 | $+300.94 | +8.85% |
| R7 | 6-6-0 | $-16.46 | -1.37% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 14-14-0 | $+37.33 | +1.33% |
| P | 64-41-0 | $+1,238.46 | +11.79% |
| V | 32-30-0 | $+863.57 | +13.93% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 71-50-0 | $+1,008.91 | +8.34% |
| V | 39-35-0 | $+1,130.45 | +15.28% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 80-59-0 | $+1,479.65 | +10.64% |
| rl | 30-26-0 | $+659.71 | +11.78% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-22 | Washington Nationals @ Detroit Tigers | Detroit Tigers -1.5 | +135 | R5 | loss | $-100.00 |
| 2026-09-22 | St. Louis Cardinals @ Pittsburgh Pirates | St. Louis Cardinals ML | +144 | R3_era | loss | $-100.00 |
| 2026-09-22 | Milwaukee Brewers @ Philadelphia Phillies | Philadelphia Phillies -1.5 | +156 | R5 | win | $+156.00 |
| 2026-09-22 | Cleveland Guardians @ Boston Red Sox | Cleveland Guardians ML | +105 | R3 | win | $+105.00 |
| 2026-09-23 | Washington Nationals @ Detroit Tigers | Washington Nationals ML | +139 | R3_era | pending |  |
| 2026-09-23 | Toronto Blue Jays @ Baltimore Orioles | Baltimore Orioles ML | -126 | R3_era | pending |  |
| 2026-09-23 | Minnesota Twins @ San Francisco Giants | San Francisco Giants ML | +132 | R3_era | pending |  |
| 2026-09-23 | St. Louis Cardinals @ Pittsburgh Pirates | Pittsburgh Pirates -1.5 | +160 | R5 | pending |  |
| 2026-09-23 | Milwaukee Brewers @ Philadelphia Phillies | Milwaukee Brewers -1.5 | +138 | R5 | pending |  |
| 2026-09-23 | Tampa Bay Rays @ New York Yankees | New York Yankees -1.5 | +169 | R5 | pending |  |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested.

- **Record:** 53-44-0 (0 void)
- **P/L:** $+455.94 on $9,700 risked
- **ROI:** +4.70% (±9.9 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 53-44-0 | $+455.94 | +4.70% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-20 | Detroit Tigers @ Chicago White Sox | Detroit Tigers ML | +100 | SS_ml | loss | $-100.00 |
| 2026-09-20 | Washington Nationals @ St. Louis Cardinals | Washington Nationals ML | +111 | SS_ml | loss | $-100.00 |
| 2026-09-20 | Seattle Mariners @ Colorado Rockies | Seattle Mariners ML | -159 | SS_ml | win | $+62.89 |
| 2026-09-21 | Toronto Blue Jays @ Baltimore Orioles | Toronto Blue Jays ML | -108 | SS_ml | loss | $-100.00 |
| 2026-09-21 | Washington Nationals @ Detroit Tigers | Detroit Tigers ML | -132 | SS_ml | win | $+75.76 |
| 2026-09-21 | Minnesota Twins @ San Francisco Giants | Minnesota Twins ML | -122 | SS_ml | loss | $-100.00 |
| 2026-09-22 | Tampa Bay Rays @ New York Yankees | New York Yankees ML | -130 | SS_ml | loss | $-100.00 |
| 2026-09-22 | Washington Nationals @ Detroit Tigers | Detroit Tigers ML | -152 | SS_ml | loss | $-100.00 |
| 2026-09-22 | Milwaukee Brewers @ Philadelphia Phillies | Philadelphia Phillies ML | -139 | SS_ml | win | $+71.94 |
| 2026-09-22 | Chicago White Sox @ Kansas City Royals | Chicago White Sox ML | -118 | SS_ml | win | $+84.75 |

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


## Glossary

Plain-language definitions for every column, badge and rule id above. Also published at <https://gitchrisqueen.github.io/panthera/glossary.html>.

### Table columns

| Term | Definition |
|---|---|
| Avg CLV | Average closing line value in cents, with the number of covered picks, the share that were positive, and coverage. |
| CLV | This pick's closing line value in cents: how much better (or worse) its price was than the last price before the game started. |
| Config | A parameter combination from the calibration sweep, named after its own values — e.g. m10-e110-h250. |
| Date | The game's calendar date in US/Eastern. All game-day logic uses Eastern time regardless of where the game is played. |
| Day type | Whether the whole day is classified Public (P), Vegas (V), or HYBRID. Wednesday is the hybrid day. |
| Graded | How many of this strategy's picks have a final result yet. Pending picks are not counted. |
| Kind | What role a strategy plays: baseline (a control), incumbent, aligned, or forward_test. |
| Market | Which bet type was taken: ml (moneyline), rl (run line), or total. |
| Matchup | The game, written away team @ home team. |
| N (valid) | How many bets this config placed over the validation seasons — the ones it was not tuned on. |
| Overlap | Share of this strategy's picks where another strategy backed the same side of the same game that day — correlated results, not independent evidence. |
| P/L | Profit or loss in dollars over the graded picks, at flat paper stakes. Positive is a gain. |
| P/L (valid) | Profit or loss in dollars over the validation seasons, at flat stakes. |
| Pending | Picks recorded but not yet graded — the game has not finished, or its result has not been collected yet. |
| Pick | The side and market backed — e.g. 'Detroit Tigers ML' for a moneyline, or 'Chicago Cubs +1.5' for a run line. |
| Price | The American odds the pick was recorded at. Negative is the favorite (risk that much to win $100); positive is the underdog (win that much on $100). |
| Record | Wins–losses–pushes over the graded picks, in that order. |
| ROI (valid) | ROI over the validation seasons only. The training-season ROI is not shown here because a config was chosen partly by it. |
| ROI (±SE) | ROI with its standard error: the ± figure is how much this ROI estimate would typically wobble from sampling noise alone. |
| Rule | Which sub-rule of the strategy produced this pick. The by-rule breakdown is the falsification instrument — it shows which parts carry the strategy. |
| Slot | The P or V classification of the specific start-time slot this game sits in, which need not match the day's own type. |
| Start (ET) | Scheduled first pitch in US/Eastern. |
| Status | Where this strategy stands against its own pre-registered bar: collecting, SUPPORTED, FALSIFIED, INCONCLUSIVE, screen only, or not live. |
| Status | How a pick settled: pending, win, loss, push, or void. |
| Strategy | The named hypothesis that produced this pick. Each strategy is evaluated separately against its own pre-registered bar. |
| Tier | How much evidential weight a pick carries: VERDICT picks count toward a pre-registered test; SCREEN picks are descriptive only. |

### Verdict & trust badges

| Term | Definition |
|---|---|
| COLLECTING | Not enough graded picks yet to apply this strategy's pre-registered test. The counter shows progress toward the threshold. |
| COLLECTING — closed | A superseded strategy whose counter stopped short of its threshold. It will never reach a verdict, by design. |
| FALSIFIED | This strategy reached its pre-registered sample size and finished below its pre-registered failure line. |
| INCONCLUSIVE | Enough picks to test, but the result landed between the support and falsification lines — neither bar was crossed. |
| REPLAY | A retroactive replay: these picks were computed after every outcome in them was already known, so they carry no evidential weight. |
| SCREEN | Descriptive only — this pick carries no inferential weight, because no pre-registered threshold is being tested against it. |
| SUPPORTED | This strategy reached its pre-registered sample size and cleared its pre-registered ROI bar. Screen-grade evidence, not proof. |
| VERDICT | This pick counts toward its strategy's pre-registered test, because it ran under a configuration in that strategy's declared lineage. |

### Metrics

| Term | Definition |
|---|---|
| Coverage (cov) | The share of picks that have a closing price on file. Picks made before closing-price collection started are excluded, not counted as misses. |
| ROI | Return on investment: profit divided by the total amount risked, as a percent. |

### Bet types

| Term | Definition |
|---|---|
| Moneyline (ML) | A bet on which team wins the game outright, with no handicap. Priced in American odds. |
| Run line (RL) | Baseball's spread, almost always ±1.5 runs: the favorite must win by 2+, or the underdog must win or lose by exactly 1. |
| Total | A bet on the combined runs scored by both teams, over or under a posted number. |

### Concepts

| Term | Definition |
|---|---|
| Backtest | Replaying a strategy over completed historical seasons. Cheap and fast, but only possible where historical data for every input exists. |
| Betting splits | The share of tickets (bet count) versus handle (money) on each side. A large gap between them is the signal the splits strategies read. |
| Calibration | A parameter sweep that picks a strategy's thresholds on training seasons and reports them on separate validation seasons. |
| Checkpoint | A pick count at which a SCREEN segment's running numbers are noted. Checkpoints are reporting milestones, not tests to pass. |
| Closing line | The last price recorded before a game starts — the market's final word, and the benchmark CLV measures against. |
| Config hash | A fingerprint of the exact configuration a pick ran under. If the behaviour changes, the hash changes. |
| ERA | Earned run average — runs a pitcher allows per nine innings. Lower is better. Used as a tiebreaker input where prices alone do not decide. |
| Evenly matched | A game where both sides are priced close to even, inside a configured threshold — the setup some rules treat specially. |
| evenly_matched_max_abs_ml | The price threshold below which two teams count as evenly matched — e.g. 120 means both sides priced inside ±120. |
| Favorite | The side the market expects to win, shown at a negative American price. |
| First meeting | The first game of the season between two teams, where no head-to-head form exists yet. Some rules restrict what may be played. |
| Flat stake | Every pick risks the same fixed amount. No progressive staking, no bet sizing by confidence — so results reflect the picks, not a staking scheme. |
| Forward test | Testing a strategy on games that have not happened yet. The only honest test for rules whose inputs have no historical record. |
| Hash lineage | The list of config hashes a strategy declared at registration. Only picks under those hashes count toward its verdict. |
| Heavy favorite | A favorite priced at or beyond a configured threshold (typically −200), where the payout no longer justifies the moneyline. |
| heavy_fav_abs_ml | The price at or beyond which a favorite counts as 'heavy' and gets special handling — converted to a run line, or passed entirely. |
| Line movement | How a price changed between the first snapshot of the day and the latest one. The direction and size of that move is a signal input. |
| min_move_cents | How many cents a price must move before the engine treats it as a real line-movement signal rather than noise. |
| Natural vs scam movement | Whether a price move is justified by the team's recent merit (natural) or moves against what merit would predict (scam). |
| Paper trade | A recorded hypothetical bet. No money is wagered, nothing here is placed at a book, and nothing here is financial advice. |
| Portfolio totals | All strategies' results added together. Informational and descriptive only — never an evaluation target, because the strategies overlap. |
| Pre-registration | Each strategy declares its sample size and its pass/fail ROI bars before seeing any results, and those numbers are never changed afterwards. |
| Public day (P) | A day classified as driven by recreational money, where the strategy backs the public side. |
| Push | A tie against the number — the stake is returned. Pushes appear in the record but move neither profit nor loss. |
| Segment | A group of a strategy's picks sharing one config hash. Segments are reported separately so results from different behaviour are never silently pooled. |
| Slate | All of a single day's games. |
| Underdog | The side the market expects to lose, shown at a positive American price. |
| Vegas day (V) | A day classified as driven by the book, where the strategy backs the side the public is not on. |
| Vig (juice) | The book's built-in margin: the reason the two sides of a game add up to more than 100% and a coin-flip bettor loses money over time. |

### Rule ids

| Term | Definition |
|---|---|
| B_DOG | The underdog-moneyline control, backtest only. Together with B_FAV it brackets the vig band. |
| B_FAV | The favorite-moneyline control: backs the favorite in every game, all slate. Measures the book's hold rather than testing an idea. |
| FP_ml | Fade-the-public moneyline: backs the side opposite a heavily ticketed favorite, on the theory recreational flow overprices it. |
| O0 | Eligibility gate for the aligned engine: regular season, not yet started, priced, and a slot could be assigned. |
| O1_big_scam | The exception that reopens an off day: a price move large enough to qualify as an outlier against recent merit. |
| O1_off_day | Thursday and Saturday are off by default in the aligned engine — no play unless the day offers an outlier mispricing. |
| O1_wed_second_half | Wednesday's second half is playable only on an outlier mispricing, matching the off-day rule. |
| O2_outrageous_scam | The override to slot discipline: a mispricing extreme enough to be worth playing even in the wrong slot. |
| O2_slot_mismatch | Slot discipline: passes a game whose slot type does not match what the day permits — Vegas days play Vegas slots only. |
| O3_first_meeting | Never play a total on the first meeting of the season between two teams — there is no head-to-head form to read yet. |
| O3_totals | Tuesdays and Sundays play the total rather than a side, per the source strategy's day policy. |
| O4 | The aligned engine's base pick: classify the move as natural or scam, then ride it in a public slot or fade it in a Vegas slot. |
| O5 | Evenly-matched game in a public slot: back the underdog's run line at +1.5. |
| O6 | Public-slot price filter: only plays prices of −160 or cheaper, passing anything more expensive. |
| O7 | Heavy favorite at −200 or shorter: the aligned engine passes outright rather than converting to a run line. |
| R0 | Eligibility gate: skips spring training, non-regular-season games, games already under way, and games with no matched odds. |
| R1 | Day and slot classification — assigns the game a P, V, or hybrid-Wednesday type. Passes if a hybrid day has no start time. |
| R3 | The base pick: a P slot backs the public side, a V slot backs the Vegas side, decided by which way the favorite's moneyline moved. |
| R3_era | R3's first fallback when the line did not move decisively: pick the side with the starting-pitcher ERA edge. |
| R3_form | R3's second fallback: with no movement signal and no ERA edge, pick the side with better last-10 form. |
| R3_series | R3's last fallback: with no movement, ERA or form edge, pick the side leading the season series. Otherwise pass. |
| R4 | Evenly-matched public slot: take the underdog's run line at +1.5 instead of the moneyline. |
| R5 | Vegas-slot favorite: take the favorite's run line at −1.5 instead of the moneyline. |
| R7 | Heavy favorite (−200 or shorter): convert the pick to a run line, or pass, depending on the strategy's configuration. |
| R8_veto | Sanity veto: cancels a pick when the line movement is contradicted by a recent blowout loss plus an ERA gap. |
| SS_ml | Sharp-split moneyline: backs the side taking a much larger share of money than of tickets, on the theory that is where informed money sits. |
