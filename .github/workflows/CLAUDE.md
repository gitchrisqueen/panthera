# Workflows

## Cron ↔ ET table (crons are UTC; ET is UTC-4 during EDT)

| Workflow | Cron (UTC) | ET (EDT) | Does |
|---|---|---|---|
| mvp-morning | 35 14 * * * | 10:35 | grade yesterday → snapshot `open` (3 cr) → Lumify splits `morning` → picks for pre-16:00 starts → report |
| mvp-midday | 5 16 * * * | 12:05 | snapshot `midday` (3 cr) → report |
| mvp-pregame | 50 20 * * * | 16:50 | snapshot `pregame` (3 cr) → Lumify splits (~16 cr of its own 1,000 pool) → picks for evening slate → report |
| mvp-calibrate | manual | — | download archives → calibration sweep → write calibrated config |
| ci | push/PR | — | ruff + pytest on `tests/` only |

**DST note:** crons are DST-dumb. When the US shifts (Nov/Mar), runs drift
1 hour of wall-clock ET. All game logic is ET-internal so nothing breaks —
shift the cron hours by 1 if the drift matters (MLB season mostly avoids it).

**Credit budget:** 3 snapshots/day × 3 credits ≈ 279/month vs 500 free. The
credit guard (`min_credits_reserve` in `config/strategy.yaml`) skips
snapshots rather than exhausting the balance.

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
