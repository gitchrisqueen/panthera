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
| Editable files | `config/lab/<sport>.yaml` (search space, guards, starting point) by pull request only. `data/lab/<sport>/` (features, champion, iterations) and `reports/LAB_REPORT.md` by the weekly bot only, except the two hand procedures below (undo a promotion, start a new loop). |
| Evaluator | `lab_eval_v1`: `lab/climb.py` (`simulate`, `walk`) with `lab/ncaaf_rules.py`, over `data/lab/<sport>/features.csv` and the sport's games (NCAAF: `data/ncaaf/games/games.csv`). Fixed for the whole loop. |
| Data | Raw per-game features logged at decision time, one row per game on the slate, no thresholds applied (`lab/features.py`, `FEATURE_COLUMNS`). Final scores come from the games file. |
| Metric, direction | Mean profit per straight bet in units ($100 flat = 1 unit): win `decimal - 1`, loss `-1`, push 0, void and pending excluded. Higher is better. Reported raw; it is not shrunk (a shrinkage target would have to be the no-skill return at the bet prices, about -4.5% at -110, not zero). |
| Candidate | The champion with exactly one parameter moved: a toggle, one `step` up or down inside `[min, max]`, or another listed choice. Parameters of a switched-off signal are not offered. |
| Budget per run | Zero API credits, no network. The only limit is the workflow's 10-minute timeout. |
| Stop policy | Weekly, in season only (`season_months`). A run with too little data records `insufficient_data` and changes nothing. A second real run in the same ISO week is refused (`--force` repeats it on purpose). Stop and start a new loop when the evaluator, the feature columns, the guards or the search space change (see below). |

### Promotion guards (all must hold; at most one promotion per run)

1. The challenger has at least `guards.min_bets` graded bets in the training window.
2. It differs from the champion on at least `guards.min_diff_bets` games. The z below rests
   only on those games, however many bets the two rule sets share (a rare signal that adds
   7 winning bets to 100 shared ones is not 107 bets of evidence).
3. Its paired profit difference to the champion has `z >= max(guards.z_min, sqrt(2 ln T))`.
   The difference is taken per game, over the games where either rule set bets (0 when
   one of them does not). `T` is the number of challengers ever evaluated, this run's
   included, so the bar rises as more are tried. That penalty is in the spirit of Harvey,
   Liu and Zhu (2016) and is a heuristic, not a proof.
4. The z still reaches that same required bar after the single best game is dropped.
5. The newest `guards.holdout_weeks` weeks, which did not pick the challenger, contain at
   least one game where the two rule sets differ and score the challenger strictly above the
   champion (mean profit per game where either bets). The window slides weekly, so last
   week's holdout is this week's training: it is a confirmation, not an untouched test set.
6. At most one promotion per run, one parameter per challenger.

A new champion takes effect the next ET day (`effective_from`). The walk itself replays the
champion over all logged history; `effective_from` only scopes the "forward" figures in the
report.

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
of NCAAF yields on the order of 100 to 200 straight bets (an estimate from v1's first two
weeks: about 14 S6 and 2 S5 qualifying legs a week, an upper bound for placed bets), so the
loop can only act on a large effect or a large rule change, and many weeks will end in
`insufficient_data`.

### What the evals measure (`tests/test_lab_eval.py`)

All on synthetic slates with known truth, seeded and pinned to the counts below. They are
measurements of this procedure on that generator, not guarantees about real data.

| Eval | Configuration | Result |
|---|---|---|
| Null, shipped regime | Fair coins. Shipped guards (`min_bets` 100, `min_diff_bets` 30) and the shipped 18-path space. 17 weeks of 18 games, 300 seeds. | 4,200 runs, **1 promotion** (95% upper bound on the per-run rate under 0.2%); 2,609 of the runs recorded `insufficient_data`. |
| Null, long horizon | Same guards and space, 40 weeks of 20 games, 100 seeds. | 3,700 runs, **1 promotion**; 747 `insufficient_data`. |
| Null, reduced stress | 4 of the 18 paths, `min_bets` 60, 200 seeds x 37 runs. | Rate under 0.2% (measured about 0.04% when written), no claimed in-sample edge of +10% per bet or more. |
| Planted edge | A real +24% per bet edge in a 3.5-4 point SP+ band, **400 games a week** (ten times the real volume), 22 weeks, no daily cap, `min_bets` 150, 20 seeds. | Promoted in **18 of 20**; a **wrong parameter was promoted twice** (seeds 3 and 19, in seasons that also found the planted one). |
| Rare signal | 100 shared bets plus 7 winning bets from a rare signal. | Rejected by `min_diff_bets`; promoted if that guard is set to 1. |
| Empty holdout | Challenger identical to the champion in the newest 3 weeks. | Rejected: the holdout confirms nothing. |
| One winner | A coin-flip challenger plus one +1000 winner, z bar lowered to 0.4 so the pool sits just over the line. | Rejected by the best-game guard. A price that long cannot lift z to the shipped bar of 2.0 by itself, so that guard is only live near the threshold. |

What this means:

- The planted-edge case checks **plumbing at ten times the real volume**. It is not a power
  estimate: at the real volume the loop is blind to an effect this size is not.
- The guards do **not** make a false promotion impossible. At high volume, where the loop has
  many eligible runs, a wrong change was promoted in 2 of 20 seasons. At the real volume the
  null measured about 1 promotion in 300 simulated seasons.
- Late in a season the bar is high: with a few hundred challengers evaluated, `sqrt(2 ln T)`
  is about 3.4, so late promotions are rare by construction.
- The z uses per-game differences and treats games as independent. Games on the same day
  share weather and luck, so the real standard error is larger and the bar is somewhat
  easier to clear than it looks. A day-level or permutation test would be more defensible and
  is not built.
- The bar `sqrt(2 ln T)` is the expected size of the largest of `T` independent normal
  draws. It is a multiple-testing penalty that grows with `T`, not a calibrated 5% test.

## Operating the lab

**Stop, resume.** `gh workflow disable lab.yml` stops the weekly run; `gh workflow enable
lab.yml` resumes it. `ncaaf picks` keeps logging features either way and existing data is
untouched, so the loop resumes with everything logged in the gap. To stop everything that
writes to the `data` branch, use the kill switch in `.github/workflows/CLAUDE.md` (it lists
`lab`).

**Is it healthy?** `panthera-mvp lab status` reads the LOCAL `data/lab/`, which on a normal
checkout is the stale copy frozen on `main`. Pull first:

```bash
bash scripts/ci/data_branch.sh pull
.venv/bin/panthera-mvp lab status
```

A healthy last row has a `run_ts` from this week and a `decision` of `no_change` or
`insufficient_data` with a stated reason (or `promoted`). Each in-season week has one row; a
missing `week_label` means the run failed or was dropped: open the Actions run list for
`lab.yml`. A red run is the only alert (GitHub emails the last cron editor); nothing else
notifies anyone.

**Undo a wrong promotion.** `champion.json` keeps the current parameters and `parent_hash`,
not the parent's parameters; those are in the `data` branch history.

1. Stop the weekly run (above) so nothing lands on top of you.
2. `bash scripts/ci/data_branch.sh pull`, then find the parent's parameters:
   `git log -p origin/data -- data/lab/ncaaf/champion.json` (the previous version of the file
   is the parent champion).
3. Put that `params` block into `data/lab/ncaaf/champion.json` and recompute its hash:

   ```bash
   .venv/bin/python - <<'PY'
   import json
   from panthera_mvp.config import config_hash
   p = "data/lab/ncaaf/champion.json"
   c = json.load(open(p))
   c["hash"] = config_hash(c["params"])
   c["change"] = "revert of <the bad champion's hash>"
   c["effective_from"] = "<tomorrow, YYYY-MM-DD>"
   json.dump(c, open(p, "w"), indent=2)
   PY
   ```

4. Leave `iterations.csv` untouched: its `trials_total` is the multiple-testing count and
   must not be reset. Push with `bash scripts/ci/data_branch.sh push "data: lab revert"`
   (or the worktree recipe in `.github/workflows/CLAUDE.md` § Undoing or restoring bot data),
   re-enable the workflow, and check `lab status` shows the restored hash.

**Changing the evaluator, the feature columns, the guards or the search space starts a new
loop.** Scores from different evaluators do not compare, and the multiple-testing count `T`
was earned under the old experiment. `lab run` enforces it: a champion carries a `loop_hash`
of the evaluator version, guards, space and feature constants, and a mismatch is an error
(`LabConfigError`), not a silent continuation. Procedure:

1. Make the change by PR. If the evaluator or its meaning changed, bump `EVAL_VERSION` in
   `src/panthera_mvp/lab/__init__.py` and `eval_version` in `config/lab/<sport>.yaml`. (A guard
   or space change alone needs no version bump: the loop hash already catches it. A feature
   column change needs the bump, and the old `features.csv` rows are no longer comparable.)
2. After the merge, stop the weekly run, `bash scripts/ci/data_branch.sh pull`, and in
   `data/lab/<sport>/` rename `iterations.csv` to `iterations.<old version>.csv`, rename
   `features.csv` the same way if its columns changed, and delete `champion.json`.
3. Push with `bash scripts/ci/data_branch.sh push "data: lab new loop"` and re-enable the
   workflow. The next real run writes the starting champion from `initial_champion`, then
   walks (and can promote) in that same run.

These two procedures are the only sanctioned hand edits to `data/lab/`; everything else there
is the bot's.

### When it breaks

| Symptom | Cause | What to do |
|---|---|---|
| Red `lab` run, log says `LabConfigError ... new evaluator` or `... loop hash differs` | The config or evaluator changed since the champion was written. | "Changing the evaluator ... starts a new loop" above. |
| Red `lab` run before any push | An exception in the walk, or in `lab.yml` setup. The run (and any promotion) is discarded: nothing was pushed. | Reproduce: `bash scripts/ci/data_branch.sh pull`, then `panthera-mvp lab run --sport ncaaf --dry-run`. A failure in the report alone does not discard the run: it prints a `::warning::` and the iteration row is still written. |
| A `week_label` is missing | The run failed, or it was superseded in the `panthera-data` group (GitHub keeps only one pending run per group, so a queued lab run can be replaced by a newer one). | Dispatch the workflow with `dry_run` false. A second real run in the same week is refused unless `force` is set. |
| Push failed | A concurrent writer or a refused file. | Download the `data-delta` artifact and replay it: `.github/workflows/CLAUDE.md` § Undoing or restoring bot data. |
| `lab status` says "no champion yet" on a checkout | You read the stale local copy. | Pull first (above). |

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
season months and repeats a run already made this week (smoke tests). The feature logging
hook is in `ncaaf picks` (`_log_lab_features`) and the weekly run is
`.github/workflows/lab.yml`. The report write is not atomic with the other two writes; in CI
the push is all-or-nothing, so a crash can only leave a partial state on a local run.

## Adding a sport or level

The loop is sport-agnostic above the rules module. A new sport adds, under its own name:
a `config/lab/<sport>.yaml`, a features module (raw per-game values at decision time), a
rules module that turns a feature frame and a params dict into bets, and a games source
for `lab/report.py::games_for`. MLB and college baseball plug in this way and stay dormant
out of season (MLB runs April to October, college baseball February to June); they are
tracked as #88 (MLB) and #89 (college baseball), and neither is covered until it has run
in season. A history backfill for NCAAF, which must flag leaky signals, is #90. Parity with
the sport's live engine must be proven by a test like `tests/test_lab_ncaaf_parity.py`
before its first run.

## What this does not do

- It never changes a registered strategy (`cfb_spread_total_parlay`, `_v2`, or any MLB
  strategy). A change worth keeping graduates by a human registering a new strategy id.
- It spends no Odds API credits and makes no network call.
- It does not read closing lines: NCAAF has no closing-line value, which would be the faster
  read of an edge.
- It has no history backfill (#90), so it learns only from what `ncaaf picks` logs from the
  day the hook merges.
