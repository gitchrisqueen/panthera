# Lab: weekly hill-climb

_Generated 2026-11-09T22:55:30Z by `panthera-mvp lab run`. Do not edit._

> Exploratory lab: selected on past data, not verdict-eligible; ~17,800 straight bets are needed to confirm a +2% ROI, so most weeks correctly end in no change.

Straight bets, $100 flat = 1 unit, best-available price. Search space, guards and the evaluator contract: `docs/lab/PROGRAM.md`.

## ncaaf (college)

Evaluator `lab_eval_v1`. Champion `e050ea59da`, effective from 2026-11-09 (initial).

Challengers evaluated so far: 0. The next run needs z >= 2.35 (floor 2.0, raised by the multiple-testing penalty), at least 100 graded training bets, and a holdout that is not worse.

| Parameter | Value |
|---|---|
| `bet_limits.skip_day_after_loss` | False |
| `legs.min_signals` | 1 |
| `min_lead_minutes` | 15 |
| `signals.letdown.enabled` | False |
| `signals.letdown.max_rank` | 25 |
| `signals.letdown.min_fav_points` | 10.0 |
| `signals.line_move_spread.enabled` | False |
| `signals.line_move_spread.min_points` | 1.5 |
| `signals.line_move_total.enabled` | False |
| `signals.line_move_total.min_points` | 2.0 |
| `signals.look_ahead.enabled` | False |
| `signals.look_ahead.max_rank` | 25 |
| `signals.look_ahead.min_fav_points` | 10.0 |
| `signals.sp_plus_edge.enabled` | True |
| `signals.sp_plus_edge.min_edge_points` | 4.0 |
| `signals.weather_wind_under.enabled` | True |
| `signals.weather_wind_under.min_wind_mph` | 15.0 |
| `ticket.max_bets_per_day` | 6 |
| `ticket.max_price_american` | -115 |
| `ticket.rank_by` | strength |

### Last 12 runs

| Run (UTC) | Week | Decision | Change tested | n | Challenger z (needed) | Why |
|---|---|---|---|---|---|---|
| 2026-11-09T22:55:30Z | 2026-W46 | insufficient_data | - | 0 | - (-) | no feature rows logged yet |
