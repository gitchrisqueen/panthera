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
  API + credit guard), `espn.py` (backup finals).
- `matching.py` — odds event ↔ MLB gamePk; alias table + commence-time
  proximity for doubleheaders; unmatched events are logged, never guessed.
- `store.py` — CSV datastore with dedupe keys (lines) / upsert (games) /
  append-once + settle-in-place (picks).
- `strategy/` — the IP: `daytype.py` (P/V/hybrid), `movement.py` (public vs
  Vegas line moves), `dossier.py` (ERA/first-meeting features), `rules.py`
  (R0–R8 rules engine; the rule-ID table is in its docstring).
- `grading.py` — settles picks (ML/RL/total, pushes, voids).
- `report.py` — regenerates all markdown from `picks.csv`.
- `backtest/` — `loader.py` (sbro-format archives), `engine.py` (replays the
  same `generate_pick`), `calibrate.py` (parameter sweep).

## Conventions

- **Picks are immutable once created** — settle them, never rewrite terms.
- **Every behavior knob lives in `config/strategy.yaml`** — no magic numbers
  in `rules.py`. New thresholds get a documented YAML entry.
- `generate_pick` takes plain `GamePrices` values so live pipeline and
  backtest share one code path. Don't fork the rules logic.
- Store timestamps with `timeutil.utc_iso()`; compare game days in ET only.
- Tests run offline on `tests/fixtures/` — network calls are never made in
  unit tests. If you add a client method, add a fixture and a parse test.
