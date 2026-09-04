# Project Panthera 🐆

[![CI Build](https://github.com/gitchrisqueen/panthera/actions/workflows/ci.yml/badge.svg)](https://github.com/gitchrisqueen/panthera/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)
[![View Live Dashboard](https://img.shields.io/badge/dashboard-live_results-1a7f37?logo=github)](https://gitchrisqueen.github.io/panthera/)

### 📊 [**View the live picks & performance dashboard →**](https://gitchrisqueen.github.io/panthera/)

**Project Panthera** is an MLB sports-betting analysis project. Its long-term
vision is a SaaS platform; its **current phase is an automated MVP that
proves — or falsifies — the core betting strategy** before any product gets
built on top of it.

## 🎯 Current phase: Automated Strategy Validation

A fully automated, zero-cost paper-trading pipeline lives in
[`src/panthera_mvp`](src/panthera_mvp). GitHub Actions take odds snapshots
three times a day, generate picks from the registered strategy rules, grade
them the next morning, and commit a running ledger back to this repo — git is
the database, markdown is the dashboard. Every enabled live strategy in
[`config/strategies/`](config/strategies) paper-trades the same slate in
parallel, each with its evaluation criteria (verdict thresholds or screen
checkpoints) pre-registered in its YAML.

- 📊 **Live dashboard:** [gitchrisqueen.github.io/panthera](https://gitchrisqueen.github.io/panthera/) — auto-updated 2×/day
- 📈 **Live results & verdict (markdown source):** [`reports/BETTING_REPORT.md`](reports/BETTING_REPORT.md)
- 📅 **Daily pick reports:** [`reports/daily/`](reports/daily)
- 🔬 **Design & rule formalization:** [`docs/mvp-design.md`](docs/mvp-design.md)
- 📖 **The strategy itself:** [`docs/sports_betting_process.md`](docs/sports_betting_process.md)
- ⚙️ **Strategy parameters:** [`config/strategy.yaml`](config/strategy.yaml) plus one YAML per strategy in [`config/strategies/`](config/strategies)
- 🗄️ **Historical calibration:** [`reports/CALIBRATION.md`](reports/CALIBRATION.md)

### How it works

| Workflow | When (ET) | What it does |
|---|---|---|
| [MVP Morning Run](.github/workflows/mvp-morning.yml) | 10:35 daily | Grades yesterday's picks, takes the opening odds snapshot, collects morning betting splits, picks afternoon games, regenerates reports |
| [MVP Pregame Run](.github/workflows/mvp-pregame.yml) | 16:50 daily | Pregame snapshot, collects pregame betting splits, picks the evening slate on open→pregame line movement, regenerates reports |
| [MVP Close Snapshot](.github/workflows/mvp-close.yml) | 18:20 daily | Closing-line-value snapshot only — never a movement endpoint for picks |
| [MVP Historical Calibration](.github/workflows/mvp-calibrate.yml) | manual | Downloads free historical odds archives and derives strategy thresholds |
| [Deploy Pages](.github/workflows/pages.yml) | after each morning and pregame run | Rebuilds and publishes the GitHub Pages dashboard |
| [MVP Splits Collection](.github/workflows/mvp-splits.yml) | manual | On-demand betting-splits fetch (key check, catch-up runs) |

Picks are paper trades at a flat $100 stake (`staking.flat_stake` in every
strategy YAML). The two live Public-vs-Vegas strategies (`pv_orig`, `pv_v3`)
carry a pre-registered verdict: after 100 graded picks, ROI > 0% supports the
strategy, ROI < −5% falsifies it. `pv_v2` was retired on 2026-08-16
(`enabled: false` in its YAML); its verdict segment stays in the ledger frozen
at 93 graded picks and will not reach 100. The baseline (`fav_ml`) and
the two splits-based forward tests (`fade_public`, `sharp_split`) have no
verdict criteria — the ledger reports them as descriptive screens only. Note
that the ledger's own preamble explains why paper-ROI verdicts at these
sample sizes are screens rather than proof.

### Data sources (all free)

- **[MLB Stats API](https://statsapi.mlb.com)** (keyless) — schedules, probable pitchers/ERA, finals
- **[The Odds API](https://the-odds-api.com)** (free tier, 500 credits/month) — moneyline, run line, totals
- **ESPN scoreboard API** (keyless) — backup finals source
- **[Sportsbook Reviews Online archives](https://www.sportsbookreviewsonline.com/scoresoddsarchives/)** — historical open/close odds for backtesting

### Setup

Repo Actions secrets (Settings → Secrets and variables → Actions):

- `ODDS_API_KEY` — required. Free at [the-odds-api.com](https://the-odds-api.com) (500 credits/month).
- `LUMIFY_API_KEY` — optional. Free at [lumify.ai/api-keys](https://lumify.ai/api-keys) (1,000 non-expiring credits). Enables public **betting-splits** collection in the morning and pregame runs — a direct measurement of the Public-vs-Vegas premise. If unset, splits collection skips silently; the odds pipeline and the P/V strategies still run, but the two splits-based strategies (`fade_public`, `sharp_split`) pass every game.

Everything else is keyless; workflows commit with the built-in `GITHUB_TOKEN`.

### Local development

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -q      # offline test suite (fixtures, no network)
.venv/bin/ruff check src tests

# CLI (use --dry-run to avoid spending Odds API credits):
panthera-mvp snapshot --label open --dry-run
panthera-mvp picks --window-end-et 23:59
panthera-mvp grade
panthera-mvp report
panthera-mvp status
```

See [`CLAUDE.md`](CLAUDE.md) for conventions and gotchas.

## 📚 Documentation

- [MVP Design](docs/mvp-design.md): strategy formalization, rule table, and parameter glossary — **start here**.
- [Data Source Registry](docs/data-sources.md): APIs in use, vetted free-API candidates (betting splits, line-movement history), and the NFL/NBA expansion blueprint.
- [Sports Betting Process](docs/sports_betting_process.md): the original strategy outline the MVP encodes.
- [Code Requirements](docs/code-requirements.md), [Project Plan](docs/project-plan.md), [Project Summary](docs/project-summary.md): the original SaaS specs (future phase; time estimates assume human developers).

## 🗃️ Legacy scaffold (frozen)

`backend/` (Flask), `frontend/` (React), `db/` (MySQL), `mockup/`, and
`docker-compose.yml` are the early SaaS scaffold. They are **frozen** —
excluded from CI and not maintained — until the strategy is validated. Don't
build on them in this phase.

## 🛠️ Development Workflow

- **`main`** is the only long-lived branch; scheduled workflows run from it
  and commit data/reports to it.
- Create a feature branch per change and open a PR to `main`. CI (ruff +
  pytest over `src/` and `tests/`) must pass.
- `data/` and `reports/` are bot-owned — don't hand-edit them in PRs (see
  [`data/CLAUDE.md`](data/CLAUDE.md)).

## 👥 Stakeholders and Investors

This project is an exciting opportunity for stakeholders and investors
interested in the growing sports betting market. The MVP phase exists to
de-risk the product: the strategy's track record accrues transparently in
this repo before any SaaS investment.

For business inquiries, please contact [Chris Queen](mailto:chris@christopherqueenconsulting.com).

## 📝 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For any questions, issues, or contributions, please reach out via
[GitHub Issues](https://github.com/gitchrisqueen/panthera/issues) or contact
the project lead directly at [Chris Queen](mailto:chris@christopherqueenconsulting.com).
