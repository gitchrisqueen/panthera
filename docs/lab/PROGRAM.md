# Lab program: the weekly hill-climb

This is the contract for the weekly champion/challenger loop in `src/panthera_mvp/lab/`.
It follows the keep-or-revert experiment-loop format: say what may change, what
scores it, which direction is better, how much a run may spend, and when to stop.
The loop is **exploratory**. A champion is selected on past data, so it is never
verdict-eligible and sits outside the registration budget in `docs/mvp-design.md`.
Pre-registered strategies keep their own verdict rules; this loop never edits them.

## What the loop is for

Each in-season week, for each sport and level, look at what the paper-trading logged,
try one change at a time to the current rule set (the **champion**), and keep a change
only when the evidence clears every guard. The aim is a higher paper P/L in units of a
flat stake. Most weeks, correctly, nothing changes: see "What the sample can and cannot
tell us".

## The contract

| Item | Value |
|---|---|
| Editable files | `config/lab/<sport>.yaml` (search space, guards, starting point) by pull request only. `data/lab/<sport>/` (features, champion, iterations) and `reports/LAB_REPORT.md` by the weekly bot only. |
| Evaluator | `lab_eval_v1`: `lab/climb.py` (`simulate`, `walk`) with `lab/ncaaf_rules.py`, over `data/lab/<sport>/features.csv` and the sport's games (NCAAF: `data/ncaaf/games/games.csv`). Fixed for the whole loop. |
| Data | Raw per-game features logged at decision time, one row per game on the slate, no thresholds applied (`lab/features.py`, `FEATURE_COLUMNS`). Final scores come from the games file. |
| Metric, direction | Mean profit per straight bet in units ($100 flat = 1 unit): win `decimal - 1`, loss `-1`, push 0, void and pending excluded. Higher is better. Reported raw and shrunk (`roi * n / (n + 625)`; the 625 pseudo-bets are an assumption, not a measurement). |
| Candidate | The champion with exactly one parameter moved: a toggle, one `step` up or down inside `[min, max]`, or another listed choice. Parameters of a switched-off signal are not offered. |
| Budget per run | Zero API credits, no network, under 60 seconds. |
| Stop policy | Weekly, in season only (`season_months`). A run with too little data records `insufficient_data` and changes nothing. Stop and re-baseline when the evaluator, the feature columns or the guards change (see below). |

### Promotion guards (all must hold; at most one promotion per run)

1. The challenger has at least `guards.min_bets` graded bets in the training window.
2. Its paired profit difference to the champion has `z >= max(guards.z_min, sqrt(2 ln T))`.
   The difference is taken per game, over the games where either rule set bets (0 when
   one of them does not). `T` is the number of challengers ever evaluated, this run's
   included, so the bar rises as more are tried. That penalty is in the spirit of Harvey,
   Liu and Zhu (2016) and is a heuristic, not a proof.
3. The z still reaches `guards.z_min` after the single best game is dropped.
4. The newest `guards.holdout_weeks` weeks, which did not pick the challenger, do not score
   it below the champion (mean profit per game in that window).
5. A new champion takes effect the next ET day, so a decision already logged is never
   re-scored under rules chosen after it.

Every run appends one row to `data/lab/<sport>/iterations.csv`, including the no-change
and insufficient-data runs, with the best challenger and the reason it failed.

## What the sample can and cannot tell us

Straight bets at -110 have a per-bet standard deviation near 0.95 units. Break-even is a
52.38% win rate.

| To detect | Straight bets needed (two-sided 5%, 80% power) |
|---|---|
| +2% ROI | about 17,800 |
| +5% ROI | about 2,800 |
| 49 bets (the NCAAF single-leg count on 2026-11-09) | the standard error of ROI is 13.6 points |

These are our calculations from that standard deviation, not a published table. A season
of NCAAF yields a few hundred straight bets at most, so the loop can only act on a large
effect or a large rule change. The null evals in `tests/test_lab_eval.py` measure exactly
how rarely it invents one: over 7,400 simulated weekly runs on fair coins it promoted
3 times (0.04%), and the largest in-sample edge it ever claimed was +3% per bet.

Volume matters as much as the guards. As an estimate, not a measurement: with
`ticket.max_bets_per_day: 6` and two angles switched on, a 15-week NCAAF season yields
about 12 bets a week once the daily cap binds, so roughly 180 a season. That is below the
default `guards.min_bets: 300`, so until the cap is raised or more signals are on, the
likely weekly answer is `insufficient_data`. Re-check the real volume after a few weeks
of logged features and set `min_bets` and the cap on that evidence.

## Changing the evaluator starts a new loop

Scores from different evaluators do not compare. If you change `simulate`, `walk`, the
settlement, a guard's meaning, or `FEATURE_COLUMNS`:

1. Bump `EVAL_VERSION` in `lab/__init__.py` and `eval_version` in the sport's config
   (`lab_eval_v2`).
2. Keep the old `iterations.csv` (rename it `iterations.lab_eval_v1.csv`) and start an empty one.
3. Write the starting champion again. `lab run` refuses to continue from a champion written
   under another version.

Changing a guard value (`min_bets`, `z_min`, `holdout_weeks`) or the search space is also a
new loop for the same reason: the multiple-testing count `T` and the history it was earned
under no longer describe the same experiment.

## How the pieces fit

```
ncaaf picks (decision time)  -> data/lab/ncaaf/features.csv     (append-once per day and game)
ncaaf grade                  -> data/ncaaf/games/games.csv      (final scores)
panthera-mvp lab run         -> data/lab/ncaaf/iterations.csv   (one row per run)
                             -> data/lab/ncaaf/champion.json    (only on a promotion)
                             -> reports/LAB_REPORT.md
panthera-mvp lab status      -> prints the champion and the last run (read-only)
```

`lab run --dry-run` prints the decision and writes nothing. `--force` runs outside the
season months (for backfills and tests). The feature logging hook and the weekly workflow
are separate changes.

## Adding a sport or level

The loop is sport-agnostic above the rules module. A new sport adds, under its own name:
a `config/lab/<sport>.yaml`, a features module (raw per-game values at decision time), a
rules module that turns a feature frame and a params dict into bets, and a games source
for `lab/report.py::games_for`. MLB and college baseball plug in this way and stay dormant
out of season (MLB runs April to October, college baseball February to June). Parity with
the sport's live engine must be proven by a test like `tests/test_lab_ncaaf_parity.py`
before its first run.

## What this does not do

- It does not change any registered strategy, config hash or verdict.
- It does not call any API and spends no Odds API credits.
- It does not search the day map, price bands or parlay structure: the lab evaluates
  straight bets only, because a three-leg parlay carries about three times the vig of the
  same legs as singles and no evidence supports an edge from the structure itself.
- It does not tell anyone to place a real bet. Everything is paper.
