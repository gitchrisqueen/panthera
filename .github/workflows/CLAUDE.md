# Workflows

## Cron ↔ ET table (crons are UTC; ET is UTC-4 during EDT)

| Workflow | Cron (UTC) | ET (EDT) | Does |
|---|---|---|---|
| mvp-morning | 35 14 * * * | 10:35 | grade yesterday (fills CLV) → snapshot `open` (3 cr) → Lumify splits `morning` (scoped to pre-16:00 ET starts) → picks `--label morning` for pre-16:00 starts → report |
| mvp-pregame | 50 20 * * * | 16:50 | snapshot `pregame` (3 cr) → Lumify splits (not-yet-started events, both overlapping UTC dates) → picks `--label pregame` for evening slate → report |
| mvp-close | 20 22 * * * | 18:20 | snapshot `close` (3 cr) — **CLV endpoint only**, never a movement endpoint for pick generation; lands after the pregame picks priced and before ~96% of first pitches |
| mvp-calibrate | manual | — | download archives → calibration sweep → write calibrated config (registry strategies do NOT read it — their params are inlined) |
| mvp-debug-era | manual | — | probe live statsapi hydrate variants for the dormant probable-pitcher ERA (no commits) |
| pages | `workflow_run` after mvp-morning/mvp-pregame; `workflow_dispatch` from ncaaf after a push | — | `panthera-mvp pages` → deploy the public dashboard (gitchrisqueen.github.io/panthera). Plain default checkout — **do not** pin `ref:` to `github.event.workflow_run.head_sha` (see the fixed 2026-08-20 bug in `pages.yml`'s header comment: that field is the triggering run's pre-commit SHA, not what it just pushed) |
| ncaaf-capture | manual | — | NCAAF plumbing check: games by ET `date` (ESPN) or by `week`/`year` (CFBD /games + /lines when `CFBD_API_KEY` is set, merged with ESPN's week scoreboard) → optional NCAAF odds snapshot (`odds: none / dry_run / live`; live = 3 cr from the shared pool, reserve 60; one call covers the whole week) → optional CFBD season cache → uploads raw ESPN (and, in week mode, ncaa-api) payloads as the `ncaaf-capture` artifact (fixture material). Dry runs never commit. Manual plumbing check; the scheduled NCAAF runs are in `ncaaf` |
| ncaaf | `5 13-23,0-4 * * *` + `35 15-23,0-4 * * *` · `10 23 * * 0,3` · `15 13 * * *` | half-hourly 9:05–00:35 (no :35 before 11:35) · Sun+Wed 19:10 · 9:15 | **half-hourly** `ncaaf picks --auto`: a no-op (no network, credits or commit) unless the day's first kickoff is 15–90 min away (no lower bound past `min_lead`: GitHub starts crons 15–50 min late, so a late run still decides — once), then one `decision-<date>` snapshot (3 cr) and the day's `cfb_spread_total_parlay` decision. **Sun+Wed** `ncaaf prep`: ESPN games 8 days back / 14 ahead, `open` snapshot (3 cr; skipped with nothing upcoming), CFBD SP+ + venues. **Daily** `ncaaf grade`. Report only when `data/ncaaf` changed; after a real push it dispatches `pages` (`actions: write`) so football.html updates within minutes. ≈ 78 cr/month. `:05`/`:35` keep it clear of the MLB runs in the shared group (no `:35` at 14 UTC, the MLB morning slot) (a newer queued run cancels an older *pending* one). Dispatch: `task` picks/prep/grade, `dry_run` (default true) never commits |
| ncaabase-capture | manual | — | NCAA D1 baseball plumbing check: records raw ncaa-api (daily + month scoreboard, schedule), ESPN and Odds API `/sports` (0 cr) payloads → `ncaabase games --force` (ESPN finals fallback) → optional `baseball_ncaa` snapshot (`odds: none / dry_run / live`; live = 3 cr, `--force` bypasses `odds_api.enabled` to measure coverage) → uploads the `ncaabase-capture` artifact (fixture material). Dry runs never commit. No cron until a college baseball strategy exists |
| ci | push/PR | — | ruff + pytest on `tests/` only |
| site-audit | push/PR touching `dashboard_static/**`, `dashboard.py`, `glossary.py`, `config/glossary.yaml`, the script or its seeded football payload | — | `scripts/site_audit.py` — headless-Chromium geometry audit of the built site (Baseball, Football, Calibration, Glossary, plus `?level=` fallbacks) at 375–1440px in both themes. An empty NCAAF ledger is swapped for `tests/fixtures/ncaaf/site_ncaaf_data.json` so football.html never audits blank. Catches what pytest cannot: overlapping boxes, content clipped with no way to scroll to it, unlabeled columns, tables needing horizontal scroll above their stack point, markdown leaking into rendered text, undefined glossary terms. Own file, not a job in `ci.yml`, because `paths:` is only valid under `on:` |

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

## Bot-commit loop guards (keep all three)

1. Pushes made with the default `GITHUB_TOKEN` don't trigger new workflow runs.
2. Data commits carry `[skip ci]`.
3. `ci.yml` has `paths-ignore: data/**, reports/**, badges/**`.

## Race handling

All data-writing workflows share `concurrency: group: panthera-data`
(serialized, no cancel) and `git pull --rebase` before push. Keep both when
adding a workflow that commits.

## Testing a workflow

Use **workflow_dispatch with `dry_run: true`** — snapshots then read
`tests/fixtures/odds_snapshot.json` and cost 0 credits. The first real
(3-credit) call should be a deliberate dispatch with `dry_run: false` after
`ODDS_API_KEY` is set.

Scheduled crons only fire from the **default branch**; the daily automation
goes live when the MVP branch merges to `main`.
