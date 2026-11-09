# Workflows

## Cron ↔ ET table (crons are UTC; ET is UTC-4 during EDT)

| Workflow | Cron (UTC) | ET (EDT) | Does |
|---|---|---|---|
| mvp-morning | 35 14 * * * | 10:35 | grade yesterday (fills CLV) → snapshot `open` (3 cr) → Lumify splits `morning` (scoped to pre-16:00 ET starts) → picks `--label morning` for pre-16:00 starts → report |
| mvp-pregame | 50 20 * * * | 16:50 | snapshot `pregame` (3 cr) → Lumify splits (not-yet-started events, both overlapping UTC dates) → picks `--label pregame` for evening slate → report |
| mvp-close | 20 22 * * * | 18:20 | snapshot `close` (3 cr) — **CLV endpoint only**, never a movement endpoint for pick generation; lands after the pregame picks priced and before ~96% of first pitches |
| mvp-calibrate | manual | — | download archives → calibration sweep → write calibrated config (registry strategies do NOT read it — their params are inlined) |
| mvp-debug-era | manual | — | probe live statsapi hydrate variants for the dormant probable-pitcher ERA (no commits) |
| pages | `workflow_run` after mvp-morning/mvp-pregame/panthera-catchup; `workflow_dispatch` from ncaaf after a push | — | `panthera-mvp pages` → deploy the public dashboard (gitchrisqueen.github.io/panthera). Plain default checkout — **do not** pin `ref:` to `github.event.workflow_run.head_sha` (see the fixed 2026-08-20 bug in `pages.yml`'s header comment: that field is the triggering run's pre-commit SHA, not what it just pushed) |
| ncaaf-capture | manual | — | NCAAF plumbing check: games by ET `date` (ESPN) or by `week`/`year` (CFBD /games + /lines when `CFBD_API_KEY` is set, merged with ESPN's week scoreboard) → optional NCAAF odds snapshot (`odds: none / dry_run / live`; live = 3 cr from the shared pool, reserve 60; one call covers the whole week) → optional CFBD season cache → uploads raw ESPN (and, in week mode, ncaa-api) payloads as the `ncaaf-capture` artifact (fixture material). Dry runs never commit. Manual plumbing check; the scheduled NCAAF runs are in `ncaaf` |
| ncaaf | `5 13-23,0-4 * 8-12,1 *` + `35 15-23,0-4 * 8-12,1 *` · `10 23 * 8-12,1 0,3` · `15 13 * 8-12,1 *` (Aug-Dec + Jan only; UTC months) | half-hourly 9:05–00:35 (no :35 before 11:35) · Sun+Wed 19:10 · 9:15 | **half-hourly** `ncaaf picks --auto`: a no-op (no network, credits or commit) unless the day's first kickoff is 15–90 min away (no lower bound past `min_lead`: GitHub starts crons 15–50 min late, so a late run still decides — once), then one `decision-<date>` snapshot (3 cr) and the day's `cfb_spread_total_parlay` decision. **Sun+Wed** `ncaaf prep`: ESPN games 8 days back / 14 ahead, `open` snapshot (3 cr; skipped with nothing upcoming), CFBD SP+ + venues. **Daily** `ncaaf grade`. Report only when `data/ncaaf` changed; after a real push it dispatches `pages` (`actions: write`) so football.html updates within minutes, except after a SCHEDULED `grade` task (the next successful MVP Morning, MVP Pregame or Catch-up run deploys via pages.yml, about 80 minutes later for Morning; if that run fails, graded football results wait for the next successful one; a manual `grade` dispatch still deploys, or run `gh workflow run pages.yml --ref main`). The month filter keeps the offseason (Feb-Jul) silent; hours and weekdays are deliberately not narrowed (committed kickoff data covers Oct 1 - Nov 4 only, no bowl or CFP weeks). The `Which task` case patterns must equal the four cron strings exactly, and a scheduled run that matches none exits 1 rather than doing nothing. `timeout-minutes: 10` (the longest job in the last 30 successful runs took 0.6 min). A scheduled run that matches no case exits 1; the alert is GitHub's failed-run email to the last cron editor (`health` checks data freshness, not this job). ≈ 78 cr/month. `:05`/`:35` keep it clear of the MLB runs in the shared group (no `:35` at 14 UTC, the MLB morning slot) (a newer queued run cancels an older *pending* one). Dispatch: `task` picks/prep/grade, `dry_run` (default true) never commits |
| ncaabase-capture | manual | — | NCAA D1 baseball plumbing check: records raw ncaa-api (daily + month scoreboard, schedule), ESPN and Odds API `/sports` (0 cr) payloads → `ncaabase games --force` (ESPN finals fallback) → optional `baseball_ncaa` snapshot (`odds: none / dry_run / live`; live = 3 cr, `--force` bypasses `odds_api.enabled` to measure coverage) → uploads the `ncaabase-capture` artifact (fixture material). Dry runs never commit. No cron until a college baseball strategy exists |
| health | 5 16 * * * | 12:05 | `panthera-mvp doctor` across every sport — read-only, zero API credits, commits nothing. Reconciles one GitHub issue per finding fingerprint (`<sport>/<check>`) under the `panthera-health` label: creates on first sight, **edits the body in place** afterwards (edits do not notify), comments only on a level escalation or every 7 days, and closes itself when `doctor` stops reporting that fingerprint. The job exits 0 on FINDINGS — a daily red X is a red X nobody reads, so the issue is the alert. One case exits 3 and reddens the job by design (2026-10-16): `cmd_doctor`'s DoctorConfigError branch, i.e. a missing or invalid `config/health.yaml` or one with no `doctor:` block. That is "doctor could not run", not a finding; on that run no issue is opened, edited or closed and no `health.json` artifact is uploaded, so the red X is the only alert and means the detector is down. Scheduled an hour after mvp-morning so it reads a checkout with today's data, and deliberately **outside** the `panthera-data` concurrency group so it never delays a pick run (its own per-workflow group cancels only a superseded PR run). Runs `doctor --json` once; the run-log text is derived from `health.json`; artifact `retention-days: 14`. Added 2026-10-15 after the postseason gate bug ran for 14 slate days unnoticed |
| panthera-catchup | 15 11 * * 1 | Mon 07:15 | `panthera-mvp catchup --sport all` — the weekly repair to `health`'s daily detection. Finds slate days the pipeline missed (never ran, or ran under a config since corrected per `catchup.mlb.void_pass_reasons` in `config/health.yaml`) and replays them into `data/picks/shadow_picks.csv` + `data/picks/catchup_log.csv` + `data/picks/run_log.csv`, then regenerates reports and commits. **Never `data/picks/picks.csv`** — a backdated pick is not a forward paper trade — and the commit step greps the staged paths and fails if one ever appears. Spends **no Odds API credits** on the MLB path (it replays captured odds); the NCAAF arm only grades (`CFBD_API_KEY` for its finals fallback, ESPN and ncaa-api otherwise) and the college-baseball arm refreshes games and grades over keyless hosts. In the `panthera-data` concurrency group (`cancel-in-progress: false`) because it commits — and the hour is chosen to sit OUTSIDE every other cron in that group, because a run left pending there is cancelled by the next one to queue, which would be a weekly repair that silently never ran. A successful run triggers `pages.yml` (it gates on `conclusion == 'success'`), which rebuilds and deploys only if the code, config or data changed since the last deploy (its build-key check), so it is skipped only when nothing changed since the last deploy; otherwise (for example after `mvp-close` landed data) it republishes the current tip, which is harmless. Dispatch: `sport`/`from`/`to`, `dry_run` default true, which never commits. Rollback and ownership: `docs/mvp-design.md` § Rollback and ownership — catch-up |
| ci | push/PR (not for docs-only changes: `**/*.md`, `docs/**`, `LICENSE`, plus `data/**`, `reports/**`, `badges/**`) | — | ruff + pytest on `tests/` only. `permissions: contents: read`; concurrency cancels a superseded PR run (never on push); `timeout-minutes: 15` |
| site-audit | push/PR touching `dashboard_static/**`, `dashboard.py`, `glossary.py`, `config/glossary.yaml`, the script or its seeded football payload | — | `scripts/site_audit.py` — headless-Chromium geometry audit of the built site (Baseball, Football, Calibration, Glossary, plus `?level=` fallbacks) at 375–1440px in both themes. An empty NCAAF ledger is swapped for `tests/fixtures/ncaaf/site_ncaaf_data.json` so football.html never audits blank. Catches what pytest cannot: overlapping boxes, content clipped with no way to scroll to it, unlabeled columns, tables needing horizontal scroll above their stack point, markdown leaking into rendered text, undefined glossary terms. Own file, not a job in `ci.yml`, because `paths:` is only valid under `on:`. Report uploaded on failure only (`retention-days: 7`); concurrency cancels a superseded PR run; `actions/cache` is SHA-pinned |

**Retired 2026-08-19: mvp-midday** (`snapshot --label midday`, was 12:05 ET).
No scheduled picks run ever selected it as a movement endpoint
(`RUN_TO_SNAPSHOT` only maps morning→open, pregame→pregame); it existed for
the doc's "12 PM check" fidelity and as an intermediate degradation target
if `pregame` failed (see the credit-guard note below). GitHub Actions has no
native trigger for a real-world condition like "an hour before this game" —
only `schedule`/`workflow_dispatch`/`repository_dispatch` — so there's no
cheaper "event-based" version of this run to fall back to; it's a straight
cut. Cost: ~90 credits/month freed (360→270 of the 500 free-tier budget).
Tradeoff: if a live `pregame` snapshot is skipped by the credit guard, the
pregame run now degrades straight back to `open` instead of the closer
`midday` snapshot (`_resolve_snapshot_label` in pipeline.py) — still
correct, just a coarser fallback. The `snapshot --label midday` CLI command
and `SNAPSHOT_LABEL_ORDER` machinery are untouched, so a manual/dispatched
midday snapshot still works if ever needed; only the automatic daily cron
is gone.

**DST note:** crons are DST-dumb. When the US shifts (Nov/Mar), runs drift
1 hour of wall-clock ET. All game logic is ET-internal so nothing breaks —
shift the cron hours by 1 if the drift matters (MLB season mostly avoids it).
The `close` snapshot at 17:20 ET (EST) is still post-pregame/pre-slate, so
no November adjustment is required. GitHub cron drift (hours-late fires,
observed 2026-08-06) is mitigated by the picks late-run guard: >90 min late
writes a durable run note; started games are skipped as always.

**Credit budgets:**
- Odds API: 3 snapshots/day × 3 credits ≈ 270/month vs 500 free (was 4/day,
  ≈360/month, until the unused `midday` snapshot was retired 2026-08-19 —
  see above). The credit guard (`min_credits_reserve`) skips snapshots
  rather than exhausting the balance; a skipped snapshot degrades the picks
  run to the previous label present (durable "degraded snapshot" note),
  never to the `close` label.
- Lumify: finite non-expiring pool (observed opening balance 1,082; reserve
  floor 50). The fetch policy — future-start events only, morning window
  scoped to pre-16:00 ET, both overlapping UTC dates queried in the evening —
  cut the burn from ~28/day to an estimated ~13-15/day. `credit_log.csv`
  records real per-run deltas since 2026-08-17; **measure ~3 days of actual
  burn before enabling the splits strategies** (their stopping rule is
  budget-based).

## Gate, inputs, token permissions, Pages change detection (issues #79, #80)

- **ncaaf pre-check gate (#79).** `ncaaf.yml` has a `gate` job that runs before the `run` job. For the two
  half-hourly `auto` crons it reads `data/ncaaf/games/games.csv` and `tickets/decisions.csv` from the `data`
  branch and skips the whole job (no `pip install`) when the day is already decided, no game is stored for
  today, or the first eligible kickoff is not yet inside the decision window. `scripts/ci/ncaaf_gate.py` mirrors
  `in_decision_window`; its `AUTO_CRONS` must equal the two `auto` cron strings (a test checks it). It
  **fails open**: a dispatch, the prep and grade crons, an unknown cron, a failed checkout or fetch, a missing
  or garbled file (wrong columns) or any exception is "go", and `run` also starts when the gate job itself
  fails (`needs.gate.result != 'success'`). Manual test: dispatch with `gate_fixture` =
  `tests/fixtures/ncaaf/gate_go.json` or `gate_nogo.json` (JSON with `now_utc`, `games`, `decided_days`),
  `gh workflow run ncaaf.yml --ref <branch> -f gate_fixture=...`. A fixture always forces `dry_run` and writes
  nothing; a path outside `tests/fixtures/ncaaf/` (absolute, `..`, symlink, not `.json`, missing or invalid JSON) fails the
  gate and the job does not run. With a fixture, only `go=true` runs the job.
- **A day looks wrongly skipped?** Open the run, job `gate`, step `Gate`: the log and the run summary
  carry `go=false (reason)`. Override with a dispatch, which always goes: `gh workflow run ncaaf.yml
  -f task=picks -f dry_run=false` (decide today now) or `-f task=prep`. A broken gate (data branch
  unreachable, bad files) shows as a red `gate` job with `run` still executing: that is the "detector is
  down" signal, not a skipped run. Rollback: revert the PR that added the gate. After any revert or replay
  on `data`, run `gh workflow run pages.yml --ref main` so the dashboard follows.
- **Dispatch inputs (#80).** `ncaaf-capture`, `ncaabase-capture`, `mvp-calibrate`, `mvp-splits`,
  `mvp-debug-era` and `ncaaf` pass inputs to their jobs through `env:` (`IN_*`, `TASK_INPUT`) and shell
  scripts read `"$IN_DATE"` etc.; no `${{ inputs.* }}` is interpolated into a `run:` script in these six workflows (a test enforces it; the boolean `dry_run` in `mvp-morning`, `mvp-pregame` and `mvp-close` still is, which cannot inject).
  Free-text inputs are validated first (`scripts/ci/validate_inputs.sh`: date, week, year, season range;
  `mvp-debug-era` has no checkout, so it validates inline).
- **Token permissions (#80).** Every workflow declares top-level `permissions: contents: read`; the one job that
  commits data raises to `contents: write` (and `ncaaf` also `actions: write` to dispatch pages). The repo
  default (`default_workflow_permissions`) is a separate setting; see the repo's Actions settings.
- **Pages change detection (#80).** `pages.yml` hashes the git object ids of `src`, `config`, `pyproject.toml`
  (checked-out ref) and `data`, `reports` (data branch) into a key, and the last deploy publishes it as
  `build-key.txt`. A `workflow_run` whose key equals the live one skips the build and deploy. A manual dispatch
  always builds; any problem reading the live key builds too. Nothing security-related is behind this check.

## Data lives on the `data` branch (2026-11-09)

`main` is protected (PR + `GitGuardian Security Checks`), so a workflow cannot push
data to it: every data push from the evening of 2026-10-23 on was rejected with GH006 and the feeds
went stale (health issues #81/#82). Bot data therefore lives on the orphan `data`
branch (`data/`, `reports/` and a README.md). Bypassing the protection for the Actions app
is not possible on a personal-account repo (`POST /rulesets` returned 422 "Actor GitHub
Actions integration must be part of the ruleset source or owner organization"), so the
branch is the fix. Owner: Christopher Queen; the `data` branch is the only live copy of
the ledger, protected by a ruleset that blocks deletion and non-fast-forward pushes.

- Every workflow that reads or writes data runs `bash scripts/ci/data_branch.sh pull`
  right after checkout (code and config still come from the ref it was started on).
- Committing workflows end with `bash scripts/ci/data_branch.sh push "<message>"`;
  it commits only this run's delta onto the pull baseline, rebases onto a concurrent
  writer, makes up to 3 push attempts, and sets `pushed=true` in `$GITHUB_OUTPUT` when it lands.
  `--forbid <regex>` fails the push if a changed path matches (catch-up's picks.csv
  guard).
- `main`'s `CLAUDE.md` files in `data/` and `reports/` are never synced.
- Change detection against the baseline is `bash scripts/ci/data_branch.sh changed data/ncaaf`
  (exit 0 = changed), not `git status` (the overlay always differs from main's frozen copy).
- `mvp-calibrate` also writes `config/`, which is code on `main`: it uploads
  `calibrated-config.patch` as an artifact for a human PR instead of committing it.
- Rollback and incident steps: § Undoing or restoring bot data, below. Reverting this change
  is not a rollback: the workflows would push to protected `main` again and fail with GH006.

## Undoing or restoring bot data

Run from a normal clone (git 2.42+ for `--orphan` worktrees; older git: `git switch --orphan`).
`data` is an orphan branch with no history shared with `main`. **First stop the writers** (kill switch
below) so nothing lands on top of your commit. Then open or refresh the worktree; repeatable, including
after the directory was deleted or a revert or `git am` was left half done:

```bash
git fetch origin data
git worktree prune
for c in revert am rebase cherry-pick; do git -C ../panthera-data "$c" --abort 2>/dev/null; done
git worktree add --detach ../panthera-data origin/data || git -C ../panthera-data checkout --detach origin/data
cd ../panthera-data && git status --short   # must print nothing
```

(In a `--single-branch` clone fetch explicitly: `git fetch origin data:refs/remotes/origin/data`.)
If `git push origin HEAD:data` is rejected (a bot landed first), `git fetch origin data && git rebase FETCH_HEAD`
and push again.

- **Undo a bad bot commit** (it is on `data`, not `main`): in that worktree, `git revert <sha>` then
  `git push origin HEAD:data`. Appended CSVs often conflict when later bot commits touched the same
  file; follow the "Keep HEAD for every derived path" recipe in `docs/mvp-design.md` (catch-up section).
- **Replay data a failed push lost.** A writer whose push step fails after the commit uploads artifact
  `data-delta` (14 days). Prefer this over re-running the workflow, which spends 3 Odds API credits
  again. `gh run download <run-id> -n data-delta -D /tmp/delta`, then in the worktree
  `git am -3 /tmp/delta/data-delta.patch` and `git push origin HEAD:data`. A same-file append conflict is
  the usual reason a patch exists: for append-only CSVs keep both sides (`git am --continue` after
  editing); if that is not clean, run `panthera-mvp catchup` instead and tell Christopher Queen (repo
  owner). Refusals (forbidden path, secret-looking text) and failures before the commit leave no patch.
  A re-run attempt overwrites the `data-delta` artifact of the same run, so download it before re-running.
  `git am` needs a git identity on your machine (`git config user.name`/`user.email`).
- **Kill switch:** `for w in mvp-morning mvp-pregame mvp-close mvp-splits ncaaf ncaaf-capture ncaabase-capture panthera-catchup mvp-calibrate; do gh workflow disable $w.yml; done`
  Disabling does not stop runs already started or waiting in the `panthera-data` group, so cancel them
  and repeat until all four lists are empty: `for s in in_progress queued pending waiting; do gh run list --status $s; done`
  then `gh run cancel <id>` for each writer. Re-enable with `gh workflow enable`. Pages and health write nothing.
- **Branch deleted:** the ruleset blocks deletion, but if it happens, restore from the last good SHA
  (`git push origin <full-sha>:refs/heads/data`; find it in a run's "data branch: pushed `<sha>`" summary
  line, expand the 7-character SHA with `gh api repos/gitchrisqueen/panthera/commits/<sha> --jq .sha` and
  `git fetch origin <full-sha>`; or use the reflog of a clone), or re-seed from `main`'s frozen copy (2026-10-23; use `git switch --orphan`
  on git older than 2.42; delete a stale local `data` branch first; the branch README.md is optional). Re-seeding
  from `main` loses everything pushed to `data` since the cutover:
  `git worktree add --orphan -b data ../seed && git archive origin/main data reports | tar -x -C ../seed --exclude=data/CLAUDE.md --exclude=reports/CLAUDE.md`,
  commit, then `git push origin HEAD:refs/heads/data`. A corrupted but existing branch needs the ruleset
  disabled and a force push: see the next item.
- **Secret reached `data`.** The push script refuses staged key-looking text and the env values of
  `ODDS_API_KEY`, `LUMIFY_API_KEY`, `CFBD_API_KEY`, but it is a pattern check. If one got through, treat the
  key as burned:
  1. Kill switch (above). Rotate the key per `docs/secret-rotation.md`.
  2. Back up first: `git branch backup-data origin/data` and `git bundle create ~/data-backup.bundle origin/data`.
  3. Find the leaked commit `<leak>` (`git log -S'<string>' origin/data`) and rebuild the branch without it but
     with everything after it: `git rebase --onto <leak>^ <leak> origin/data` in a local branch (or cherry-pick
     the later commits onto `<leak>^`), then check `git log -S'<string>'` is empty and
     `git diff --stat origin/data HEAD` shows only the leak's removal.
     This drops that whole bot commit, picks and CLV included, and later commits that settle those rows
     may conflict: to remove only the string, use `git rebase -i <leak>^` and `edit` that commit instead.
  4. Settings → Rules → Rulesets: disable "data branch: no delete, no force-push" (id 26871856), then
     `git push --force-with-lease=data:<old-tip-sha> origin HEAD:data`, then re-enable the ruleset and the writers.
  5. The old commit stays fetchable by SHA (and in any fork) until GitHub Support removes it: file a
     sensitive-data removal request. Delete the affected Actions runs and `data-delta` artifacts.
- **A push was refused** (`::error::refusing to commit ...` or `staged data looks like ... API key`):
  that run's delta is not recoverable and no artifact exists (a refusal happens before the commit). The
  log lists the file names (never the matching text) and that is the only pointer. Find out what the
  producer wrote there by running it locally with the same inputs (for example `panthera-mvp snapshot
  --label open --dry-run`, or the NCAAF fixture commands in the writer's workflow), then fix the producer
  or, for a false positive, change `SECRET_RE` or `CRED_NAME_RE` in `scripts/ci/data_branch.sh` by PR.
  There is no bypass flag. The lost data is replaced only by a manual re-dispatch of that workflow (a
  snapshot spends Odds API credits again) or, for the MLB shadow ledger, `panthera-mvp catchup`.
- **Moving data back to `main`:** no automated path. Copy `data/` and `reports/` from a `data` worktree
  into a branch off `main` and open a PR (it needs GitGuardian and merges by hand).
- **Gap to know about:** from the evening of 2026-10-23 (first rejected push: MVP Pregame run 40022747688)
  until the cutover, bot commits were rejected and are gone: odds snapshots, picks, CLV. `panthera-mvp
  catchup` cannot rebuild them: it replays only dates whose games and odds are already on disk, and both
  stop at 2026-10-23. See `data/CLAUDE.md`.
- **Size:** `data` grows with raw odds JSON; revisit (squash or prune) if the repo nears GitHub's size
  guidance. There is no scheduled mirror and no scheduled secret scan of the branch: the ruleset, the push
  script's checks and Git history are the safeguards. `ncaaf-capture` and `ncaabase-capture` also upload
  raw `capture/` payloads as public artifacts that the push script does not scan.

## Bot-commit loop guards (keep all three)

1. Pushes made with the default `GITHUB_TOKEN` don't trigger new workflow runs.
2. Data commits carry `[skip ci]`.
3. `ci.yml` has `paths-ignore: data/**, reports/**, badges/**` (plus docs-only paths: `**/*.md`, `docs/**`, `LICENSE`).

## Race handling

All data-writing workflows share `concurrency: group: panthera-data`
(serialized, no cancel); the push script rebases onto `origin/data`. Keep both when
adding a workflow that commits. Never add `cancel-in-progress: true` to a
data-writing workflow. `pages.yml` has its own `pages-build` group (also no
cancel). Every job has a `timeout-minutes`: a hung call in the `panthera-data`
group would otherwise hold it for up to 6 hours and every later cron would queue
behind it, the older pending ones cancelled.

## Testing a workflow

Use **workflow_dispatch with `dry_run: true`** — snapshots then read
`tests/fixtures/odds_snapshot.json`, cost 0 credits, and the data push step is skipped
(nothing reaches the `data` branch). The first real
(3-credit) call should be a deliberate dispatch with `dry_run: false` after
`ODDS_API_KEY` is set.

Scheduled crons only fire from the **default branch**; the daily automation
goes live when the MVP branch merges to `main`.
