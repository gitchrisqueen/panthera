# Panthera Running Ledger

Updated: 2026-10-07T14:47:17Z · Flat stakes (per strategy YAML) · All picks are paper trades.

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
| fade_public | forward_test | 177 | 73-104-0 | $-1,285.38 | -7.26% ±8.5 | -0.9c (n=22, 32% pos, 12% cov) | 39% | 0 | screen only |
| fav_ml | baseline | 419 | 250-169-0 | $-229.68 | -0.55% ±4.0 | +0.0c (n=60, 35% pos, 14% cov) | 35% | 1 | screen only |
| pv_orig | aligned | 34 | 15-19-0 | $-135.54 | -3.99% ±22.5 | — | 79% | 0 | collecting (34/100) |
| pv_v2 | incumbent | 93 | 38-55-0 | $-1,446.65 | -15.56% ±10.9 | +17.6c (n=23, 48% pos, 100% cov) | 0% | 0 | collecting (93/100) |
| pv_v3 | incumbent | 224 | 123-101-0 | $+1,923.93 | +8.59% ±6.8 | +10.1c (n=23, 52% pos, 10% cov) | 53% | 1 | SUPPORTED* |
| sharp_split | forward_test | 114 | 64-50-0 | $+859.34 | +7.54% ±9.2 | -0.2c (n=10, 10% pos, 9% cov) | 82% | 1 | screen only |
| _portfolio (informational — not an evaluation target)_ |  |  |  | $-313.98 | -0.30% |  |  |  |  |

## Strategy: fade_public

_Heavily ticketed sides are overpriced by recreational flow; the opposite side at the latest lines.csv consensus beats the vig. Forward-test only; NOT backtestable (no historical splits)._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `256514e8ad` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 73-104-0 (0 void)
- **P/L:** $-1,285.38 on $17,700 risked
- **ROI:** -7.26% (±8.5 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| FP_ml | 73-104-0 | $-1,285.38 | -7.26% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-27 | New York Mets @ Washington Nationals | Washington Nationals ML | -106 | FP_ml | win | $+94.34 |
| 2026-09-27 | Houston Astros @ Athletics | Athletics ML | +159 | FP_ml | loss | $-100.00 |
| 2026-09-27 | Los Angeles Dodgers @ San Francisco Giants | San Francisco Giants ML | +202 | FP_ml | loss | $-100.00 |
| 2026-09-27 | Tampa Bay Rays @ Philadelphia Phillies | Tampa Bay Rays ML | +145 | FP_ml | loss | $-100.00 |
| 2026-09-27 | Cincinnati Reds @ Toronto Blue Jays | Cincinnati Reds ML | +150 | FP_ml | loss | $-100.00 |
| 2026-09-27 | Cleveland Guardians @ Kansas City Royals | Kansas City Royals ML | -105 | FP_ml | win | $+95.24 |
| 2026-09-27 | Pittsburgh Pirates @ Detroit Tigers | Detroit Tigers ML | -102 | FP_ml | loss | $-100.00 |
| 2026-09-27 | Arizona Diamondbacks @ San Diego Padres | San Diego Padres ML | +125 | FP_ml | win | $+125.00 |
| 2026-09-27 | Los Angeles Angels @ Seattle Mariners | Los Angeles Angels ML | +140 | FP_ml | loss | $-100.00 |
| 2026-09-27 | Texas Rangers @ Minnesota Twins | Minnesota Twins ML | -102 | FP_ml | win | $+98.04 |

## Strategy: fav_ml

_Control, not a strategy: full-slate favorite ML measures the vig drag on this slate/feed. Uncapped by design — a named exception to the explicit- cap rule, because a capped anchor (earliest games only) is a biased subsample. Its stakes dominate the informational portfolio row._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `0146686dc7` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100, 200]

- **Record:** 250-169-0 (0 void)
- **P/L:** $-229.68 on $41,900 risked
- **ROI:** -0.55% (±4.0 pts SE, own SD)
- **Pending:** 1

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| B_FAV | 250-169-0 | $-229.68 | -0.55% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-27 | Tampa Bay Rays @ Philadelphia Phillies | Philadelphia Phillies ML | -174 | B_FAV | win | $+57.47 |
| 2026-09-27 | Cincinnati Reds @ Toronto Blue Jays | Toronto Blue Jays ML | -177 | B_FAV | win | $+56.50 |
| 2026-09-27 | Cleveland Guardians @ Kansas City Royals | Cleveland Guardians ML | -112 | B_FAV | loss | $-100.00 |
| 2026-09-27 | Pittsburgh Pirates @ Detroit Tigers | Pittsburgh Pirates ML | -116 | B_FAV | win | $+86.21 |
| 2026-09-27 | Arizona Diamondbacks @ San Diego Padres | Arizona Diamondbacks ML | -144 | B_FAV | loss | $-100.00 |
| 2026-09-27 | Los Angeles Angels @ Seattle Mariners | Seattle Mariners ML | -165 | B_FAV | win | $+60.61 |
| 2026-09-27 | Texas Rangers @ Minnesota Twins | Texas Rangers ML | -113 | B_FAV | loss | $-100.00 |
| 2026-09-27 | Colorado Rockies @ Chicago White Sox | Chicago White Sox ML | -170 | B_FAV | win | $+58.82 |
| 2026-09-27 | Atlanta Braves @ Miami Marlins | Miami Marlins ML | -118 | B_FAV | win | $+84.75 |
| 2026-09-27 | St. Louis Cardinals @ Milwaukee Brewers | Milwaukee Brewers ML | -200 | B_FAV | win | $+50.00 |

## Strategy: pv_orig

_The source strategy as the recordings actually describe it, not the doc's lossy bullet-point summary: the documented Mon-Sun day map (not the sweep-derived inverse), the shape-of-schedule slot algorithm (strategy/slots.py), a day-over-day-vs-previous-head-to-head primary signal with a natural-vs-scam classifier (strategy/scam.py) instead of raw movement-direction mapping, the per-day play policy (Tue/Sun totals primary, Thu/Sat off unless a big scam, Wed public-first-half-only, Vegas-days-Vegas-slots-only discipline), the -160-or-cheaper public price filter, heavy favorites (<=-200) passed rather than converted to a run line, and a totals engine. pv_v2/pv_v3's -15.6%/-29.9% live ROI falsifies THEIR engine; this strategy tests the one the source material actually documents. Fresh evaluation clock, no pre-registration picks._

**Verdict segment** (config hashes: 3fff5be8ec):

**INCONCLUSIVE — collecting data.** 34/100 graded picks. Pre-registered: after 100 graded, ROI > 0% → SUPPORTED; ROI < -5% → FALSIFIED; otherwise inconclusive.

- **Record:** 15-19-0 (0 void)
- **P/L:** $-135.54 on $3,400 risked
- **ROI:** -3.99% (±22.5 pts SE, own SD)
- **Pending:** 0

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| O1_big_scam | 1-7-0 | $-616.67 | -77.08% |
| O3_totals | 2-4-0 | $-212.67 | -35.45% |
| O4 | 10-8-0 | $+38.80 | +2.16% |
| O5 | 2-0-0 | $+655.00 | +327.50% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-19 | Atlanta Braves @ Houston Astros | Houston Astros ML | -134 | O1_big_scam | loss | $-100.00 |
| 2026-09-22 | Tampa Bay Rays @ New York Yankees | under 6.0 | -113 | O3_totals | loss | $-100.00 |
| 2026-09-22 | Cleveland Guardians @ Boston Red Sox | under 6.0 | -112 | O3_totals | win | $+89.29 |
| 2026-09-23 | Toronto Blue Jays @ Baltimore Orioles | Baltimore Orioles ML | -126 | O4 | win | $+79.37 |
| 2026-09-23 | Minnesota Twins @ San Francisco Giants | Minnesota Twins ML | -155 | O4 | win | $+64.52 |
| 2026-09-23 | Milwaukee Brewers @ Philadelphia Phillies | Milwaukee Brewers ML | -126 | O4 | win | $+79.37 |
| 2026-09-24 | Milwaukee Brewers @ Philadelphia Phillies | Philadelphia Phillies ML | -134 | O1_big_scam | loss | $-100.00 |
| 2026-09-25 | Pittsburgh Pirates @ Detroit Tigers | Detroit Tigers ML | -116 | O4 | win | $+86.21 |
| 2026-09-25 | New York Mets @ Washington Nationals | New York Mets +1.5 | +155 | O5 | win | $+155.00 |
| 2026-09-27 | Cincinnati Reds @ Toronto Blue Jays | Toronto Blue Jays ML | -177 | O4 | win | $+56.50 |

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

**SUPPORTED** — ROI +8.59% over 224 graded picks. (Screen-grade evidence; see 'How to read this report'.)

- **Record:** 123-101-0 (0 void)
- **P/L:** $+1,923.93 on $22,400 risked
- **ROI:** +8.59% (±6.8 pts SE, own SD)
- **Pending:** 1

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| R3 | 24-13-0 | $+1,150.60 | +31.10% |
| R3_era | 64-58-0 | $-159.81 | -1.31% |
| R3_series | 0-2-0 | $-200.00 | -100.00% |
| R4 | 9-3-0 | $+670.23 | +55.85% |
| R5 | 19-18-0 | $+507.94 | +13.73% |
| R7 | 7-7-0 | $-45.03 | -3.22% |

**By day type**

| day_type | Record | P/L | ROI |
|---|---|---|---|
| HYBRID | 18-16-0 | $+362.70 | +10.67% |
| P | 73-55-0 | $+697.66 | +5.45% |
| V | 32-30-0 | $+863.57 | +13.93% |

**By slot**

| slot_type | Record | P/L | ROI |
|---|---|---|---|
| P | 82-65-0 | $+586.48 | +3.99% |
| V | 41-36-0 | $+1,337.45 | +17.37% |

**By market**

| market | Record | P/L | ROI |
|---|---|---|---|
| ml | 88-73-0 | $+790.79 | +4.91% |
| rl | 35-28-0 | $+1,133.14 | +17.99% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-26 | Cincinnati Reds @ Toronto Blue Jays | Toronto Blue Jays ML | -164 | R3_era | loss | $-100.00 |
| 2026-09-26 | Cleveland Guardians @ Kansas City Royals | Kansas City Royals ML | -104 | R3_era | loss | $-100.00 |
| 2026-09-26 | Colorado Rockies @ Chicago White Sox | Chicago White Sox -1.5 | -117 | R7 | loss | $-100.00 |
| 2026-09-26 | St. Louis Cardinals @ Milwaukee Brewers | St. Louis Cardinals ML | +135 | R3_era | loss | $-100.00 |
| 2026-09-27 | New York Mets @ Washington Nationals | New York Mets ML | -110 | R3_era | loss | $-100.00 |
| 2026-09-27 | Baltimore Orioles @ New York Yankees | Baltimore Orioles ML | +104 | R3_era | pending |  |
| 2026-09-27 | Chicago Cubs @ Boston Red Sox | Boston Red Sox ML | +104 | R3_series | loss | $-100.00 |
| 2026-09-27 | Houston Astros @ Athletics | Houston Astros ML | -190 | R3_era | win | $+52.63 |
| 2026-09-27 | Los Angeles Dodgers @ San Francisco Giants | Los Angeles Dodgers -1.5 | -140 | R7 | win | $+71.43 |
| 2026-09-27 | Tampa Bay Rays @ Philadelphia Phillies | Tampa Bay Rays ML | +145 | R3_era | loss | $-100.00 |

## Strategy: sharp_split

_A side taking a much larger share of money than of tickets is where informed ("sharp") bettors are. Backing that side at the latest lines.csv consensus beats the vig. Grounded in 16 days of measured divergences (e.g. 29% tickets / 86% handle); no historical splits exist, so this is forward-test only and is NOT backtestable._

_No verdict criteria — descriptive SCREEN readouts only (baseline or budget-limited forward test)._

**SCREEN segment** `afcd384952` — descriptive only, no inferential weight; no threshold is tested. checkpoints reached: [100]

- **Record:** 64-50-0 (0 void)
- **P/L:** $+859.34 on $11,400 risked
- **ROI:** +7.54% (±9.2 pts SE, own SD)
- **Pending:** 1

**By rule**

| rule_id | Record | P/L | ROI |
|---|---|---|---|
| SS_ml | 64-50-0 | $+859.34 | +7.54% |

**Last 10 picks**

| Date | Matchup | Pick | Price | Rule | Status | P/L |
|---|---|---|---|---|---|---|
| 2026-09-25 | St. Louis Cardinals @ Milwaukee Brewers | Milwaukee Brewers ML | -190 | SS_ml | win | $+52.63 |
| 2026-09-26 | Pittsburgh Pirates @ Detroit Tigers | Detroit Tigers ML | -116 | SS_ml | win | $+86.21 |
| 2026-09-26 | Colorado Rockies @ Chicago White Sox | Colorado Rockies ML | +205 | SS_ml | win | $+205.00 |
| 2026-09-26 | Tampa Bay Rays @ Philadelphia Phillies | Philadelphia Phillies ML | -123 | SS_ml | loss | $-100.00 |
| 2026-09-27 | New York Mets @ Washington Nationals | New York Mets ML | -110 | SS_ml | loss | $-100.00 |
| 2026-09-27 | Baltimore Orioles @ New York Yankees | New York Yankees ML | -120 | SS_ml | pending |  |
| 2026-09-27 | Chicago Cubs @ Boston Red Sox | Chicago Cubs ML | -121 | SS_ml | win | $+82.64 |
| 2026-09-27 | Los Angeles Dodgers @ San Francisco Giants | San Francisco Giants ML | +202 | SS_ml | loss | $-100.00 |
| 2026-09-27 | Tampa Bay Rays @ Philadelphia Phillies | Tampa Bay Rays ML | +145 | SS_ml | loss | $-100.00 |
| 2026-09-27 | Cincinnati Reds @ Toronto Blue Jays | Cincinnati Reds ML | +150 | SS_ml | loss | $-100.00 |

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
| Decision | What the strategy did that day: ticket, no_ticket (too few qualifying legs) or skip (a daily rule, such as the day after a loss). |
| Graded | How many of this strategy's picks have a final result yet. Pending picks are not counted. |
| Kind | What role a strategy plays: baseline (a control), incumbent, aligned, or forward_test. |
| Legs | The selections on the ticket, each with its line and its own result. |
| Market | Which bet type was taken: ml (moneyline), rl (run line), or total. |
| Matchup | The game, written away team @ home team. |
| N (valid) | How many bets this config placed over the validation seasons — the ones it was not tuned on. |
| Overlap | Share of this strategy's picks where another strategy backed the same side of the same game that day — correlated results, not independent evidence. |
| P/L | Profit or loss in dollars over the graded picks, at flat paper stakes. Positive is a gain. |
| P/L (valid) | Profit or loss in dollars over the validation seasons, at flat stakes. |
| Pending | Picks recorded but not yet graded — the game has not finished, or its result has not been collected yet. |
| Pick | The side and market backed — e.g. 'Detroit Tigers ML' for a moneyline, or 'Chicago Cubs +1.5' for a run line. |
| Price | The American odds the pick was recorded at. Negative is the favorite (risk that much to win $100); positive is the underdog (win that much on $100). |
| Qualifying legs | How many qualifying legs this signal picked, on a ticket or not. |
| Reason | Why the day's decision came out the way it did, as recorded at decision time. |
| Record | Wins–losses–pushes over the graded picks, in that order. |
| ROI (valid) | ROI over the validation seasons only. The training-season ROI is not shown here because a config was chosen partly by it. |
| ROI (±SE) | ROI with its standard error: the ± figure is how much this ROI estimate would typically wobble from sampling noise alone. |
| Rule | Which sub-rule of the strategy produced this pick. The by-rule breakdown is the falsification instrument — it shows which parts carry the strategy. |
| Signal | The rule (angle) that picked a leg, S1 to S6. Click one for its definition. |
| Slot | The P or V classification of the specific start-time slot this game sits in, which need not match the day's own type. |
| Start (ET) | Scheduled first pitch in US/Eastern. |
| Status | Where this strategy stands against its own pre-registered bar: collecting, SUPPORTED, FALSIFIED, INCONCLUSIVE, screen only, or not live. |
| Status | How a pick settled: pending, win, loss, push, or void. |
| Strategy | The named hypothesis that produced this pick. Each strategy is evaluated separately against its own pre-registered bar. |
| Ticket status | pending until every leg settles; loss as soon as any leg loses; win if the rest all win; push if every leg pushed. |
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
| vs 52.4% | Win % minus 52.4%, the hit rate a -110 bet needs to break even, in percentage points. Positive means beating the vig so far. |
| Win % | Wins divided by wins plus losses; pushes are left out. |

### Bet types

| Term | Definition |
|---|---|
| Moneyline (ML) | A bet on which team wins the game outright, with no handicap. Priced in American odds. |
| Parlay | One bet made of several legs. It wins only if every leg wins; a pushed leg drops out and the price is re-figured from the rest. |
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
| Leg | One selection inside a parlay ticket, such as a team's spread or a game's total. |
| Level | Professional, College or Other (minor, international and semi-pro leagues). A sport page shows one level at a time; grayed levels have no strategy yet. |
| Line movement | How a price changed between the first snapshot of the day and the latest one. The direction and size of that move is a signal input. |
| min_move_cents | How many cents a price must move before the engine treats it as a real line-movement signal rather than noise. |
| Natural vs scam movement | Whether a price move is justified by the team's recent merit (natural) or moves against what merit would predict (scam). |
| Paper trade | A recorded hypothetical bet. No money is wagered, nothing here is placed at a book, and nothing here is financial advice. |
| Portfolio totals | All strategies' results added together. Informational and descriptive only — never an evaluation target, because the strategies overlap. |
| Pre-registration | Each strategy declares its sample size and its pass/fail ROI bars before seeing any results, and those numbers are never changed afterwards. |
| Public day (P) | A day classified as driven by recreational money, where the strategy backs the public side. |
| Push | A tie against the number — the stake is returned. Pushes appear in the record but move neither profit nor loss. |
| Qualifying leg | A game the strategy's rules picked on a decision day, whether or not it made the ticket. Graded on its own as evidence for each signal. |
| S1 — spread move | The spread moved 1.5+ points between the first snapshot and decision time; bet the side it moved toward. |
| S2 — total move | The total moved 2+ points between the first snapshot and decision time; bet over if it rose, under if it fell. |
| S3 — letdown | A team that beat a ranked opponent in its last game and is now favored by 10+; bet the other side's spread. |
| S4 — look-ahead | A team favored by 10+ that plays a ranked opponent in its next game; bet the other side's spread. |
| S5 — wind under | An outdoor game with wind of 15+ mph forecast at kickoff; bet the under. |
| S6 — SP+ edge | SP+ ratings (plus 2.5 points home field) disagree with the spread by 4+ points; bet the side SP+ favors. |
| Segment | A group of a strategy's picks sharing one config hash. Segments are reported separately so results from different behaviour are never silently pooled. |
| Single bet | One qualifying leg bet on its own at a flat $100, at its best available price. Shown alongside the parlay ticket; descriptive only. |
| Slate | All of a single day's games. |
| Sport | Each sport has its own page (Baseball, Football). The tabs at the top switch between them. |
| Ticket | One paper parlay bet: a set of legs, one flat stake, one combined price. |
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
