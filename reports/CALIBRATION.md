# Calibration Report — P/V Day Map & Thresholds

Generated: 2026-08-01T18:04:36Z

## Data coverage

- Seasons: 2014–2021 (17245 games)
- Train: 2014–2018 · Validate: 2019–2021

## Method

Grid: 64 day-maps (Wed fixed HYBRID) × min_move [5, 10, 15, 20] × evenly-matched ML [120, 130, 140] × heavy-fav [200, 250, 300] = 2,304 configs. Movement proxy = open→close moneyline. Ranked by validation ROI with a ≥150-bet floor per split.

## Caveats (read before trusting)

- **Open→close is a coarse proxy** for the strategy's intraday
  line-movement reads; only forward paper-trading tests the real thing.
- **Wednesday (hybrid) games are excluded** — historical files carry no
  start times, so hybrid slots cannot be assigned.
- **64 day-maps is a lot of hypotheses.** The validation split guards
  against overfitting, but treat the chosen map as a prior to be
  confirmed live, not a proven fact.
- No ERA/dossier data in historical files: the ERA fallback and R8 veto
  never fire in backtests.

## Top 10 configs by validation ROI

| Day map (M,T,Th,F,Sa,Su) | min_move | even_ml | heavy_fav | Train bets | Train ROI | Valid bets | Valid ROI |
|---|---|---|---|---|---|---|---|
| VVPPPP | 5 | 120 | 200 | 9542 | -1.83% | 3853 | +1.40% |
| VVPPPP | 5 | 120 | 300 | 9542 | -1.83% | 3853 | +1.40% |
| VVPPPP | 5 | 120 | 250 | 9542 | -1.83% | 3853 | +1.40% |
| VVPPPV | 5 | 120 | 250 | 9542 | -1.96% | 3853 | +0.89% |
| VVPPPV | 5 | 120 | 200 | 9542 | -1.96% | 3853 | +0.89% |
| VVPPPV | 5 | 120 | 300 | 9542 | -1.96% | 3853 | +0.89% |
| PVPPPP | 10 | 120 | 250 | 8653 | -1.93% | 3505 | +0.82% |
| PVPPPP | 10 | 120 | 300 | 8653 | -1.93% | 3505 | +0.82% |
| PVPPPP | 10 | 120 | 200 | 8653 | -1.93% | 3505 | +0.82% |
| PVPPPP | 5 | 120 | 200 | 9542 | -2.17% | 3853 | +0.80% |

## Chosen config

`VVPPPP-m5-e120-h200` — day map **VVPPPP** over (Mon, Tue, Thu, Fri, Sat, Sun), Wednesday HYBRID. Validation ROI +1.40% on 3853 bets (train -1.83% on 9542).

Written to `config/strategy.calibrated.yaml` when `--write-config` is used;
override any value by editing `config/strategy.yaml`.
