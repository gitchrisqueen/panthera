# panthera_mvp package

## Module map

- `cli.py` — argparse entry point (`panthera-mvp`); subcommands dispatch to
  `pipeline.py` and `backtest/`.
- `pipeline.py` — daily orchestration: `snapshot` / `picks` / `grade` /
  `report` / `status`. All commands are idempotent (safe to re-run).
- `config.py` — loads `config/strategy.yaml`, deep-merges
  `strategy.calibrated.yaml`, provides `config_hash()` (stamped on every pick).
- `timeutil.py` — UTC storage, ET game logic. The only place timezone
  conversion is allowed.
- `paths.py` — all file locations; honors `PANTHERA_ROOT` (tests point it at
  a tmp dir).
- `clients/` — `mlb.py` (schedule/ERA/finals, keyless), `odds.py` (The Odds
  API + credit guard; `sport_key` selects MLB or NCAAF, one shared credit
  pool), `espn.py` (backup finals), `espn_cfb.py` (NCAAF FBS schedule +
  finals by ET date or by CFB week, keyless; always `groups=80`),
  `cfbd.py` (CollegeFootballData.com: games, open/close lines, SP+, venues,
  FBS teams, rankings, season team stats; `CFBD_API_KEY`; CFBD game id ==
  ESPN event id), `ncaa_api.py` (ncaa-api.henrygd.me NCAA.com scoreboard
  by week, keyless — last NCAAF finals fallback), `weather.py` (Open-Meteo
  kickoff-hour wind/temp, keyless; forecast + archive).
- `ncaaf/` — college-football plumbing for the `cfb_spread_total_parlay`
  intake: own config (`config/ncaaf.yaml`, deliberately outside
  `strategy.yaml` so MLB config hashes don't move), own data tree
  (`data/ncaaf/`), name-normalized odds↔ESPN matching, `sources.py` (week
  ingest = CFBD /games merged with ESPN's week scoreboard by game id; finals
  fallback chain ESPN → CFBD → ncaa-api, filling only unsettled games), and
  a parlay-ticket ledger (`grading.py`: spread/total/moneyline legs;
  push/void legs drop out and the ticket price is re-figured).
  `parlay.py` is the `cfb_spread_total_parlay` engine (pure: GameViews +
  schedule context + SP+ + kickoff wind -> one day's qualifying legs and
  ticket; signal ids S1-S7 in its docstring), `picks.py` runs it
  (`ncaaf prep` / `ncaaf picks [--auto]`), `report.py` writes
  `reports/NCAAF_REPORT.md`. NCAAF strategies are YAMLs in
  `config/ncaaf_strategies/` loaded by `ncaaf/config.py`, never by the MLB
  registry; same `config_hash` / `hash_lineage` protocol.
- `clients/college_baseball.py` + `ncaabase/` — NCAA D1 college baseball
  (issue #52): ncaa-api (henrygd wrapper over NCAA.com; daily scoreboard,
  NCAA `gameID` = game key) with ESPN's college-baseball scoreboard as the
  finals fallback, both keyless. Own config (`config/ncaabase.yaml`: season
  window, hosts, aliases; odds snapshot off by default), own data tree
  (`data/ncaabase/`). `matching.py` fits mascot-suffixed outside names onto
  NCAA short names and splits doubleheaders by start time (ambiguous =
  skipped, never guessed); `store.py` keeps finals sticky; `grading.py`
  settles single ml/rl/total picks. No strategy yet.
- `matching.py` — odds event ↔ MLB gamePk; alias table + commence-time
  proximity for doubleheaders; unmatched events are logged, never guessed.
- `store.py` — CSV datastore with dedupe keys (lines) / upsert (games) /
  append-once + settle-in-place (picks).
- `strategy/` — the IP: `daytype.py` (P/V/hybrid), `movement.py` (public vs
  Vegas line moves), `dossier.py` (ERA/first-meeting features), `rules.py`
  (R0–R8 rules engine; the rule-ID table is in its docstring),
  `registry.py` (multi-strategy layer: engines are pure functions
  `StrategyContext -> Pick | Pass | None`; strategies are engine + YAML in
  `config/strategies/`; baselines fav_ml/dog_ml live here),
  `splits_signal.py` (Lumify splits engines).
- `doctor.py` — `panthera-mvp doctor`: cross-sport health and staleness
  checks (H01-H09), thresholds in `config/health.yaml` (NOT
  `strategy.yaml`, which is hashed into every pick). Read-only and
  zero-API-cost by contract — every input is a committed CSV, enforced by
  `tests/test_doctor.py::test_doctor_makes_no_network_calls`. Each sport's
  store is imported lazily, so an unset sport is a finding, not a crash.
  H01 `slate_shutout` is the one that catches a silent pipeline: every
  evaluated strategy producing zero picks while passing every game for the
  same stated reason. Window checks downgrade to INFO when a sport is out
  of season; the correctness checks (H07-H09) deliberately do not.
  Findings carry a `fingerprint` of `<sport>/<check>` which
  `.github/workflows/health.yml` uses as an issue identity, so a check must
  emit at most ONE finding per sport per run.
- `hashes.py` — `panthera-mvp hashes`: each strategy's `config_hash` and
  whether it sits in its own declared `hash_lineage`. Shared with
  `doctor`'s H07 so the command and the alert cannot disagree.
- `grading.py` — settles picks (ML/RL/total, pushes, voids).
- `report.py` — regenerates all markdown from `picks.csv`.
- `dashboard.py` — builds the public site: `site_data.json` (Baseball ·
  Professional, from `picks.csv` via report.py's helpers),
  `ncaaf_data.json` (Football · College, from `data/ncaaf/tickets/`, same
  definitions as `ncaaf/report.py`, parity-tested) and the static pages in
  `dashboard_static/`. One page per sport (`index.html` = Baseball,
  `football.html`); `common.js` holds the sport tabs and the
  Professional/College/Other level chips (`SPORTS` constant: add a sport =
  add a page + an entry). New top-level pages go in `write_site`'s move list
  and `scripts/site_audit.py`'s `DEFAULT_PAGES`.
- `glossary.py` — loads `config/glossary.yaml` (the one source of truth for
  every acronym, column header, badge and rule id the public surfaces name)
  and renders it two ways: `site/glossary.json` for the dashboard's
  `glossary.html` and its `[data-term]` affordances, and the `## Glossary`
  section of `BETTING_REPORT.md`. A missing/invalid file is a hard error —
  a term-less build ships dead `#fragment` links. `tests/test_glossary.py`
  scans the engines for rule ids and the dashboard source for wired terms,
  so a new column or rule cannot ship undefined.
- `backtest/` — `loader.py` (sbro-format archives), `engine.py` (replays the
  same `generate_pick`), `calibrate.py` (parameter sweep).

## Conventions

- **Picks are immutable once created** — settle them, never rewrite terms.
  CLV enrichment (`close_price`/`clv_cents`) fills nulls once, never rewrites.
- **Every behavior knob lives in `config/strategy.yaml` or the strategy's
  own `config/strategies/<id>.yaml`** — no magic numbers in engine code.
  New thresholds get a documented YAML entry. (Amended 2026-08-17: registry
  strategies inline their behavioral params and do NOT merge
  `strategy.calibrated.yaml`.)
- `generate_pick` takes plain `GamePrices` values so live pipeline and
  backtest share one code path (the registry wraps it in the `_pv_rules`
  adapter). Don't fork the rules logic.
- **A behavioral change under a reused strategy id is a protocol violation**:
  it changes `config_hash`, and the report refuses to pool it with the
  declared `hash_lineage`. New behavior ⇒ new strategy id, fresh counters.
- **A `hash_lineage` may be extended only for a DOMAIN-EXTENDING change, and
  only with an automated proof** (added 2026-10-15). A change is
  domain-extending when, restricted to the inputs the old config admitted,
  the two configs are the same decision function — so no pick already in the
  ledger would have differed and pooling cannot contaminate the pre-fix
  sample. The proof is a test that replays both configs over captured history
  and asserts identical engine output; `tests/test_scope_fix_regression.py`
  is the worked example, written for the postseason scope fix. Without that
  test the rule above stands: register a new strategy id. A threshold, a
  weight or a day-map cell is never domain-extending.
  `tests/test_live_config.py` fails the build if a live strategy's current
  hash is absent from its own non-empty lineage; `panthera-mvp hashes` prints
  the current state. An EMPTY lineage means "pool every hash" (report.py),
  not "undeclared" — never "fix" one by writing a hash into it.
- **A finals fallback selects its targets by "no score", never by status
  alone** (added 2026-10-15). Every sport's fallback used to gate on status —
  MLB `status != "Final"`, NCAAF `~status.isin(SETTLED)`, college baseball
  `status.isin(UNSETTLED)` — which made a row recorded `Final` with a NULL
  score, the one state that most needs a fallback, permanently unreachable.
  Grading settles from the score, so a pick on such a game can never settle.
  The admitted extra shape is exactly "Final with a missing score": a
  Postponed/Cancelled row has no score either and must not be reopened, and a
  row already Final with BOTH scores is never rewritten. MLB's reader is
  `pipeline._needs_final`.
- **A game's stored status comes from `clients/mlb.py::stored_status`, not
  from `abstractGameState`** (added 2026-10-15). The abstract state is only
  Preview | Live | Final, so it reports a called-off game as `Final` with no
  linescore; stored that way a pick can neither settle (no score) nor void
  (`grading`'s void branch tests for Postponed/Suspended/Cancelled, which the
  pipeline never wrote). `detailedState` is the only field that says a game
  was called off. Game 823490, cancelled for rain on 2026-09-27, left three
  picks pending for 18 days this way.
- **Game-type scope has exactly one reader**: `strategy/season.py::in_scope`,
  over `season.exclude_game_types`. Engines and `pipeline`'s SeasonContext
  both call it. They did not before 2026-10-15 — config in one, a hardcoded
  `== "R"` in the other — and the disagreement is why a whitelist that
  excluded the entire postseason survived for 14 slate days. Do not add a
  second reader.
- Store timestamps with `timeutil.utc_iso()`; compare game days in ET only.
- Tests run offline on `tests/fixtures/` — network calls are never made in
  unit tests. If you add a client method, add a fixture and a parse test.
