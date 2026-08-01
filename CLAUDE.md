# Project Panthera — MVP

## What this repo is right now

The MVP's single goal is to **prove or falsify the MLB betting strategy** in
`docs/sports_betting_process.md` — not to build the SaaS described in the
older docs. A fully automated pipeline takes odds snapshots, generates picks
from the strategy rules, grades them the next morning, and maintains a
running paper-trade ledger. GitHub Actions is the scheduler; git is the
database.

- **Active code:** `src/panthera_mvp/` (Python 3.11+, pandas). See
  `src/panthera_mvp/CLAUDE.md`.
- **Frozen legacy:** `backend/`, `frontend/`, `db/`, `mockup/`,
  `docker-compose.yml` are the abandoned SaaS scaffold. Do **not** fix,
  import from, or extend them; they are quarantined from CI and tooling.
- **Strategy source of truth:** `docs/sports_betting_process.md`; formalized
  in `docs/mvp-design.md`; parameterized in `config/strategy.yaml`.
- **The verdict lives in** `reports/BETTING_REPORT.md`.

## Commands

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -q          # offline; runs on fixtures
.venv/bin/ruff check src tests
panthera-mvp snapshot --label open --dry-run   # fixture odds, no credits
panthera-mvp picks --window-end-et 23:59
panthera-mvp grade
panthera-mvp report
panthera-mvp status
panthera-mvp backtest --seasons 2014-2023
panthera-mvp calibrate --train 2014-2019 --validate 2021-2023 --write-config
```

## Secrets & credits

- `ODDS_API_KEY` (repo Actions secret) — The Odds API free tier =
  **500 credits/month; every live snapshot costs 3**. Never commit keys.
  Always use `--dry-run` (fixture odds) during development; the credit guard
  in `clients/odds.py` refuses live calls below the configured reserve.
- MLB Stats API and ESPN endpoints are keyless. `GITHUB_TOKEN` is built-in.

## Gotchas

- Some sandboxed dev environments block `statsapi.mlb.com`,
  `site.api.espn.com`, and the odds/archive hosts (proxy 403). Develop
  against `tests/fixtures/`; verify live behavior by dispatching the MVP
  workflows on a GitHub runner.
- `data/` and `reports/` are **bot-owned**: workflows commit to them several
  times a day. Don't hand-edit; see `data/CLAUDE.md` and `reports/CLAUDE.md`.
- All times are stored UTC; all game-day/slot logic is US/Eastern via
  `timeutil.py`. Never use naive datetimes.
- Wednesday is a HYBRID day; historical backtests skip it (no start times in
  the archives) — only forward paper-trading tests hybrid slots.
