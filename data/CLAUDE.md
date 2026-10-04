# data/ — the flat-file datastore (bot-owned)

The GitHub Actions workflows commit here several times a day. **Never
hand-edit these files**; fix the code in `src/panthera_mvp/` instead.
All writes go through `store.py`, which enforces the dedupe keys below —
that's what makes workflow re-runs safe.

## Schemas

### odds/lines.csv (append-only)
`snapshot_ts_utc, snapshot_label, odds_event_id, game_pk, game_date_et,
commence_time_utc, home_team, away_team, bookmaker, market, outcome, point,
price_american, price_decimal`
Dedupe key: `(game_date_et, snapshot_label, odds_event_id, bookmaker,
market, outcome)`.

### odds/credit_log.csv (append-only)
`ts_utc, label, requests_used_total, requests_remaining, month` — one row per
live Odds API call; the credit guard reads the latest row of the current
month.

### odds/raw/YYYY-MM-DD/{label}.json
Raw API responses, kept as the audit trail.

### games/games.csv (upsert by game_pk)
`game_pk, game_date_et, day_of_week_et, game_type, doubleheader, game_number,
start_time_utc, home_team_id, home_team, away_team_id, away_team, status,
home_score, away_score, winner, run_diff, total_runs, home_pitcher_era,
away_pitcher_era, score_source`

### picks/picks.csv (the ledger — source of truth)
`pick_id, strategy_id, created_ts_utc, game_date_et, game_pk, odds_event_id,
matchup, start_time_et, day_type, slot_type, rule_id, market, selection, line,
price_american, price_decimal, stake, open_price, latest_price,
movement_cents, rationale, config_hash, status, settled_ts_utc, final_score,
profit, close_price, clv_cents`
`pick_id = <strategy_id>-<gamePk>-<market>-<yyyymmdd>` (rows from before
2026-08-17 keep their legacy unprefixed ids — annotated with
`strategy_id=pv_v2` by `scripts/migrate_picks_schema.py`, never re-termed).
Append-once on `(strategy_id, game_pk, market, game_date_et)`; `pick_id`
remains the unique settlement key. Settle-in-place; status: pending →
win|loss|push|void. `close_price`/`clv_cents` are filled once at grade time
from the `close` snapshot (null = uncovered, never zero). Picks are never
deleted or re-termed.

### picks/passes.csv (append-once per run)
`ts_utc, run_label, strategy_id, game_pk, game_date_et, reason` — key
`(strategy_id, game_pk, game_date_et, run_label)`. Durable pass records per
strategy (reports subtract games later picked). run_label ∈
morning|pregame|manual.

### picks/run_log.csv (append-only)
`ts_utc, game_date_et, run_label, kind, note` — operational notes (late_run,
degraded_snapshot, engine_error) rendered into the daily report so they
survive regeneration.

### splits/splits.csv (upsert by game_date_et + snapshot_label + lumify_event_id + metric)
`fetched_ts_utc, game_date_et, snapshot_label, lumify_event_id, event_name,
starts_at_utc, captured_at, game_pk, metric, value` (column order in the file:
label last — historical drift, tolerated by the loader).
Public betting splits from Lumify: `metric` = JSON path, whitelisted to
`bets_pct` (ticket share) and `handle_pct` (money share) per market/side.
`game_date_et` derives from the event's **ET start date** (Lumify listings
are UTC-keyed; rows before 2026-08-17 were re-dated by
`scripts/migrate_splits_dates.py`; a few same-game duplicate Lumify events
remain — readers select by start-time match + latest `captured_at`).
`snapshot_label` is morning|pregame|manual. Raw responses in
`splits/raw/YYYY-MM-DD/splits-{label}.json`; credit log in
`splits/credit_log.csv` (credits_used = real per-run delta since 2026-08-17).
**Splits are an input only for splits-based engines (sharp_split,
fade_public) — never for the P/V rules engine, where they stay
observational.**

### historical/ & calibration/
`historical/raw/` holds downloaded season archives (committed once by
mvp-calibrate); `historical/normalized/mlb_odds_all.csv` is loader output;
`calibration/sweep_results.csv` + `best_params.json` are calibrate output.

## Rule of thumb

Reports are derived from `picks.csv` — to change what a report says,
regenerate it (`panthera-mvp report`), don't edit markdown.

## ncaaf/ (college football — `panthera-mvp ncaaf ...`)

Separate tree so nothing NCAAF reaches the MLB ledger/report/dashboard.
- `ncaaf/games/games.csv` (upsert by `event_id` = ESPN event id):
  `event_id, game_date_et, start_time_utc, home_team, away_team, home_rank,
  away_rank, neutral_site, conference_game, venue, indoor, status,
  home_score, away_score`
- `ncaaf/odds/lines.csv`: MLB lines schema with `game_pk` replaced by
  `event_id` (null = unmatched, e.g. FCS); same dedupe key.
- `ncaaf/odds/raw/YYYY-MM-DD/{label}.json`: raw Odds API responses.
- `ncaaf/tickets/tickets.csv` + `ticket_legs.csv`: paper parlay tickets
  (append-once, settled in place by `ncaaf grade`); schemas in
  `src/panthera_mvp/ncaaf/store.py`.
- `ncaaf/cfbd/*.json`: cached CollegeFootballData.com responses (one file
  per endpoint+params); completed seasons never change.
- NCAAF live snapshots log to the shared `odds/credit_log.csv` with labels
  `ncaaf_<label>` — one credit pool for both sports.

## ncaabase/ (NCAA D1 college baseball — `panthera-mvp ncaabase ...`)

Separate tree, same reason as ncaaf/.
- `ncaabase/games/games.csv` (upsert by `game_id` = NCAA gameID):
  `game_id, game_date_et, start_time_utc, start_time_tba, home_team,
  away_team, home_seo, away_seo, home_char6, away_char6, home_rank,
  away_rank, home_conference, away_conference, status, current_period,
  home_score, away_score, score_source, espn_event_id`. Team names are
  NCAA `names.short` ("Florida St."). `status` ∈ Scheduled | InProgress |
  Final | Postponed | Canceled | Suspended. **Finals are sticky**: a
  non-final refresh never replaces a stored Final; an ncaa-api Final
  overwrites an ESPN one. `score_source` = `ncaa` | `espn` (fallback, with
  `espn_event_id`). `start_time_tba` rows carry ET midnight as their start.
- `ncaabase/odds/lines.csv`: MLB lines schema with `game_pk` replaced by
  `game_id` (null = unmatched); same dedupe key. Raw responses in
  `ncaabase/odds/raw/YYYY-MM-DD/{label}.json`; live snapshots log to the
  shared `odds/credit_log.csv` as `ncaabase_<label>`.
- `ncaabase/picks/picks.csv`: single-bet ledger (append-once by `pick_id`,
  settled in place by `ncaabase grade`; market ∈ ml | rl | total); schema in
  `src/panthera_mvp/ncaabase/store.py`. Empty until a strategy exists.
