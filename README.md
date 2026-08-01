# Project Panthera 🐆

[![CI Build](https://github.com/gitchrisqueen/panthera/actions/workflows/ci.yml/badge.svg)](https://github.com/gitchrisqueen/panthera/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue)

**Project Panthera** is an MLB sports-betting analysis project. Its long-term
vision is a SaaS platform; its **current phase is an automated MVP that
proves — or falsifies — the core betting strategy** before any product gets
built on top of it.

## 🎯 Current phase: Automated Strategy Validation

A fully automated, zero-cost paper-trading pipeline lives in
[`src/panthera_mvp`](src/panthera_mvp). GitHub Actions take odds snapshots
three times a day, generate picks from the documented strategy rules, grade
them the next morning, and commit a running ledger back to this repo — git is
the database, markdown is the dashboard.

- 📈 **Live results & verdict:** [`reports/BETTING_REPORT.md`](reports/BETTING_REPORT.md)
- 📅 **Daily pick reports:** [`reports/daily/`](reports/daily)
- 🔬 **Design & rule formalization:** [`docs/mvp-design.md`](docs/mvp-design.md)
- 📖 **The strategy itself:** [`docs/sports_betting_process.md`](docs/sports_betting_process.md)
- ⚙️ **Strategy parameters:** [`config/strategy.yaml`](config/strategy.yaml)
- 🗄️ **Historical calibration:** [`reports/CALIBRATION.md`](reports/CALIBRATION.md)

### How it works

| Workflow | When (ET) | What it does |
|---|---|---|
| [MVP Morning Run](.github/workflows/mvp-morning.yml) | 10:35 daily | Grades yesterday's picks, takes the opening odds snapshot, picks afternoon games |
| [MVP Midday Check](.github/workflows/mvp-midday.yml) | 12:05 daily | Midday odds snapshot (the strategy's "12 PM check") |
| [MVP Pregame Run](.github/workflows/mvp-pregame.yml) | 16:50 daily | Pregame snapshot, picks the evening slate on open→pregame line movement |
| [MVP Historical Calibration](.github/workflows/mvp-calibrate.yml) | manual | Downloads free historical odds archives and derives the P/V day map + thresholds |

Picks are paper trades at a flat $100 stake. The verdict criteria are
pre-registered in the ledger: after 100 graded picks, ROI > 0% supports the
strategy, ROI < −5% falsifies it.

### Data sources (all free)

- **[MLB Stats API](https://statsapi.mlb.com)** (keyless) — schedules, probable pitchers/ERA, finals
- **[The Odds API](https://the-odds-api.com)** (free tier, 500 credits/month) — moneyline, run line, totals
- **ESPN scoreboard API** (keyless) — backup finals source
- **[Sportsbook Reviews Online archives](https://www.sportsbookreviewsonline.com/scoresoddsarchives/)** — historical open/close odds for backtesting

### Setup

The pipeline needs exactly one secret: `ODDS_API_KEY` (repo → Settings →
Secrets and variables → Actions). Everything else is keyless; workflows
commit with the built-in `GITHUB_TOKEN`.

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For any questions, issues, or contributions, please reach out via
[GitHub Issues](https://github.com/gitchrisqueen/panthera/issues) or contact
the project lead directly at [Chris Queen](mailto:chris@christopherqueenconsulting.com).
