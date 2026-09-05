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
  in `docs/mvp-design.md`; parameterized in `config/strategy.yaml` plus one
  YAML per registered strategy in `config/strategies/` (multi-strategy
  framework: several strategies paper-trade the same slate in parallel, each
  with its own pre-registered evaluation — see `docs/mvp-design.md`).
- **The per-strategy verdicts live in** `reports/BETTING_REPORT.md`.

## Commands

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -q          # offline; runs on fixtures
.venv/bin/ruff check src tests
panthera-mvp snapshot --label open --dry-run   # fixture odds, no credits
panthera-mvp picks --window-end-et 23:59 --label pregame
panthera-mvp grade                              # also fills CLV
panthera-mvp report
panthera-mvp status
panthera-mvp backtest --seasons 2014-2023 [--strategy pv_v2]
panthera-mvp calibrate --train 2014-2019 --validate 2021-2023 --write-config
```

## Secrets & credits

- `ODDS_API_KEY` (repo Actions secret) — The Odds API free tier =
  **500 credits/month; every live snapshot costs 3**. Never commit keys.
  Always use `--dry-run` (fixture odds) during development; the credit guard
  in `clients/odds.py` refuses live calls below the configured reserve.
- `LUMIFY_API_KEY` (repo Actions secret, optional) — Lumify betting splits,
  **1,000 non-expiring credits total**; one slate ≈ 16 calls, collected in
  the morning and pregame runs. Splits never change the P/V strategies'
  picks; `fade_public` and `sharp_split` are built on them. Missing key =
  silent skip.
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

## Cross-project context
Global rules for every session live in `~/.claude/CLAUDE.md` (sourced from the CQC Boss Vault, `00-Home/CLAUDE.global.md`). The vault is at `$CQC_VAULT` (fallback: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/CQC Boss Vault`); read it as plain files.
- This project's vault note: `60-Projects/Panthera.md` (create it per `00-Home/Vault-Conventions.md` if missing).
- Handoff packets: `80-Handoffs/HO-<date>-<n>-<slug>.md` per `80-Handoffs/Handoff-Protocol.md`.
- Tracker: none recorded.
- Other projects: look them up in `00-Home/Source-Map.md`; write anything another project needs to the vault, not to auto-memory.
- Decisions for Christopher: options with a recommendation, in chat (see `00-Home/Working-With-Christopher.md`).
