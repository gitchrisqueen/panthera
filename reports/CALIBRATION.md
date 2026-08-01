# Calibration Report — P/V Day Map & Thresholds

Generated: 2026-08-01T02:59:54Z

## Data coverage

- Seasons: 2014–2021 (17245 games)
- Train: 2014–2019 · Validate: 2021–2023

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
| VVPPPV | 10 | 130 | 200 | 7625 | -2.46% | 1259 | +5.25% |
| VVPPPV | 10 | 130 | 300 | 7625 | -2.46% | 1259 | +5.25% |
| VVPPPV | 10 | 130 | 250 | 7625 | -2.46% | 1259 | +5.25% |
| VPVPPV | 20 | 130 | 200 | 3925 | -7.16% | 663 | +5.18% |
| VPVPPV | 20 | 130 | 250 | 3925 | -7.16% | 663 | +5.18% |
| VPVPPV | 20 | 130 | 300 | 3925 | -7.16% | 663 | +5.18% |
| VPPPPV | 20 | 120 | 300 | 3925 | -5.47% | 663 | +4.99% |
| VPPPPV | 20 | 120 | 200 | 3925 | -5.47% | 663 | +4.99% |
| VPPPPV | 20 | 120 | 250 | 3925 | -5.47% | 663 | +4.99% |
| VPVPPV | 20 | 120 | 300 | 3925 | -8.64% | 663 | +4.89% |

## Chosen config

`VVPPPV-m10-e130-h200` — day map **VVPPPV** over (Mon, Tue, Thu, Fri, Sat, Sun), Wednesday HYBRID. Validation ROI +5.25% on 1259 bets (train -2.46% on 7625).

Written to `config/strategy.calibrated.yaml` when `--write-config` is used;
override any value by editing `config/strategy.yaml`.
