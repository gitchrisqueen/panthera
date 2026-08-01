# MVP Design — Strategy Formalization & Parameter Glossary

Goal: **prove or falsify** the betting process in
`sports_betting_process.md` with an automated, zero-cost pipeline. This doc
maps each statement in that outline to executable rules and named parameters.

## The testable hypothesis

1. Each day of week is a **Public (P)** or **Vegas (V)** day (Wednesday
   hybrid: before ~4 PM ET public, after Vegas).
2. Line movement direction reveals which camp's money arrived: a side's
   price **shortening** (−160 → −180, +120 → +105) = public money; a side's
   price **drifting** (−180 → −160) = Vegas/sharp positioning.
3. Betting the side matching the day/slot type (public side on P slots,
   Vegas side on V slots), with the documented sub-rules, beats the vig.

## Rule table (implemented in `src/panthera_mvp/strategy/rules.py`)

| ID | Doc § | Rule | Parameters (config/strategy.yaml) |
|---|---|---|---|
| R0 | §6 | Regular-season games only; must be upcoming and priced | `season.game_types` |
| R1 | §2 | Day type from map; hybrid slots split at boundary hour | `day_map`, `hybrid_boundary_hour_et` |
| R2 | §1 | Movement on favorite's consensus ML (median of books), open → latest snapshot; below threshold = neutral | `movement.min_move_cents` |
| R3 | §5 | P slot backs public side; V slot backs Vegas side; neutral falls back to probable-pitcher ERA edge, else pass | — |
| R4 | §6 | Evenly-matched P slot → underdog run line +1.5 | `thresholds.evenly_matched_max_abs_ml`, `evenly_matched_max_era_diff` |
| R5 | §6 | V slot with favorite selected → favorite run line −1.5 | — |
| R6 | §6 | First meeting of season → ML/RL only | derived from schedule |
| R7 | §6 | Heavy favorite → convert to fav −1.5 (or pass) | `thresholds.heavy_fav_abs_ml`, `heavy_fav_action` |
| R8 | §4 | Veto when movement contradicts a ≥5-run blowout loss + >1.5 ERA deficit | fixed, logged as `R8_veto` |

Every pick records its terminal `rule_id`, full rationale, and a
`config_hash`, so `reports/BETTING_REPORT.md` can break results down by rule
— that's how we learn **which** sub-rules carry (or sink) the strategy.

## The unknown the doc never states

The actual Mon–Sun P/V mapping is not written anywhere. Decision (owner
approved): **derive it from data**. `panthera-mvp calibrate` sweeps all 64
non-Wednesday day maps × movement/threshold grids over historical seasons
(train/validate split, minimum-bet floor, top-10 stability report) and
writes the winner to `config/strategy.calibrated.yaml`. The owner can
override any value in `config/strategy.yaml` at any time.

## Data sources (all free)

| Source | Auth | Used for |
|---|---|---|
| MLB Stats API (`statsapi.mlb.com`) | none | schedule, probable pitchers + ERA, finals, meetings |
| The Odds API | `ODDS_API_KEY` (500 credits/mo free) | ML/run line/totals snapshots, 3 credits each, 3×/day |
| ESPN scoreboard API | none | backup finals for grading |
| sportsbookreviewsonline archives | none | historical open/close odds for calibration |

## Movement measurement honesty

- **Live:** movement = open (10:35 ET) → midday (12:05) → pregame (16:50)
  snapshots from our own collection. This matches the doc's process
  (morning line, 12 PM check, final scan).
- **Backtest:** only open→close exists in free archives — a coarse proxy.
  Hybrid Wednesday is untestable historically (no start times). Both
  limitations are stated in `reports/CALIBRATION.md`; forward paper-trading
  is the real test.

## Verdict criteria (pre-registered)

After **100 graded picks**: ROI > 0% → supported; ROI < −5% → falsified;
otherwise keep collecting. Flat $100 stakes. Criteria live in
`report.py` and are printed in every ledger update — no moving goalposts.
