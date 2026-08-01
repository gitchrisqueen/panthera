# Data Source Registry

Vetted data sources for Panthera — what the pipeline uses today, plus
candidates reviewed from the
[public-apis Sports & Fitness list](https://github.com/public-apis/public-apis#sports--fitness)
for deeper strategy signals and for expanding to NFL/NBA. Free-tier details
below were verified 2026-08-01; re-check before integrating (tiers drift).

## Currently integrated (MLB MVP)

| Source | Auth | Used for | Notes |
|---|---|---|---|
| [MLB Stats API](https://statsapi.mlb.com) (`statsapi.mlb.com`) | none | Schedule, probable pitchers + ERA, finals, head-to-head | Official-grade, undocumented but stable. Client: `clients/mlb.py` |
| [The Odds API](https://the-odds-api.com) | `ODDS_API_KEY` | ML/run-line/totals snapshots 3×/day | Free 500 credits/mo; 3 credits/snapshot; guard in `clients/odds.py` |
| [ESPN scoreboard API](https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard) | none | Backup finals for grading | Unofficial; can change without notice. Client: `clients/espn.py` |
| [Sportsbook Reviews Online archives](https://www.sportsbookreviewsonline.com/scoresoddsarchives/) | none | Historical open/close odds (2014–2021) for calibration | Files committed to `data/historical/raw/`; publication stopped after ~2021 |

## The key fact for NFL/NBA expansion

**No new odds subscription is needed.** The Odds API serves NFL
(`americanfootball_nfl`) and NBA (`basketball_nba`) under the same key and
credit pool, and the ESPN scoreboard pattern works for every league
(`.../sports/football/nfl/scoreboard`, `.../sports/basketball/nba/scoreboard`).
The sbro archives also include NFL and NBA season files for backtesting.
Expansion is mostly a config/schema exercise: sport key, season calendar,
spread instead of run line, and per-sport stat sources below. Budget note:
running a second sport doubles snapshot credit burn (~558/mo > 500 free), so
either alternate sports, cut to 2 snapshots/day each, or upgrade the plan.

## Vetted candidates from public-apis (worth integrating)

### High value for the current strategy

| Source | Auth / free tier | What it adds |
|---|---|---|
| [Lumify](https://lumify.ai/docs) | `apiKey` — 1,000 credits free (never expire), all endpoints, 20 req/min | **Public betting splits** (`.splits(id)`) for MLB/NFL/NCAAF — the first source that *directly measures* the Public-vs-Vegas premise instead of inferring it from line movement. Could power a new rule input (`public_bet_pct`) and validate R2's movement inference. |
| [TheRundown](https://therundown.io/) | `apiKey` — free 20k datapoints/day, 3 sportsbooks | **Line-movement history archived since 2020** and intraday movement endpoints. Two uses: (1) richer live movement than our 3-snapshot budget, (2) a far better backtest corpus than open→close — could re-run calibration with real intraday movement. 30+ leagues incl. NFL/NBA. |
| [Odds-API.io](https://docs.odds-api.io) | `apiKey` — free 100 req/hr, 2 recreational bookmakers | Backup/secondary odds feed (different vendor than our the-odds-api.com). Useful as a failover and a consensus cross-check; WebSocket on paid tiers. |

### For NFL/NBA/other-sport expansion

| Source | Auth / free tier | What it adds |
|---|---|---|
| [balldontlie](https://www.balldontlie.io) | `apiKey` — free 5 req/min: teams/players/games for NBA, NFL, MLB, NHL | Simple JSON stats for the dossier analog in other sports (form, results). Standings/stats/odds need paid tiers ($9.99+/mo per sport). |
| [NBA Stats](https://stats.nba.com) ([docs](https://any-api.com/nba_com/nba_com/docs/API_Description)) | none | Official NBA stats (requires browser-like headers). Deep team/player splits for an NBA dossier. |
| [NHL API](https://gitlab.com/dword4/nhlapi) | none | Official-grade NHL schedule/stats — same role statsapi.mlb.com plays for MLB. |
| [CollegeFootballData](https://collegefootballdata.com) | `apiKey` (free) | Detailed college football stats/results — if the strategy extends to NCAAF (big public-money sport). |
| [TheSportsDB](https://www.thesportsdb.com/api.php) | `apiKey` (free tier) | Cross-sport schedules/results backup; low rate limits, crowd-sourced quality. |
| [Cloudbet](https://www.cloudbet.com/api/) | `apiKey` (free) | Real odds straight from a sportsbook — a true "book price" to compare against aggregator consensus. |
| [PropLine](https://prop-line.com) | `apiKey` | Player-prop odds with graded resolution across 13 books — only relevant if a props strategy is added. |
| [Oddsmagnet](https://data.oddsmagnet.com) | none | Free odds *history* from UK bookmakers — supplementary movement history (UK books, but covers US majors). |

### Reviewed and not applicable

Fitness/wearables (Fitbit, Strava, Tredict, Wger), venues/bikes (City Bikes,
JCDecaux, Decathlon, Padel Snipe, DiscGolf), motorsport (Ergast, OpenF1,
RacingHub), non-US-betting sports for now (cricket, chess, AFL/Squiggle,
CFL), soccer-only APIs (API-FOOTBALL, Football-Data, Sportmonks, scorebat,
OpenLigaDB, SportScore) — revisit the soccer group only if a soccer strategy
emerges. The "MLB Records and Stats" entry documents the older MLB lookup
service; `statsapi.mlb.com` supersedes it. SuredBits is HTTP-only — excluded.

## Suggested integration order

1. **Lumify betting splits (MLB)** — one client + one dossier field; lets the
   ledger compare "movement-inferred public side" vs "measured public side".
   1,000 free credits ≈ a month of daily slates if fetched once per day.
2. **TheRundown historical movement** — re-run calibration with real intraday
   movement instead of the open→close proxy; this addresses the weakest part
   of the current backtest.
3. **NFL season pilot (Sept 2026)** — same pipeline, sport key
   `americanfootball_nfl`, spread −/+ from config; ESPN NFL scoreboard for
   grading; balldontlie/nfl for form stats.
4. **NBA (Oct 2026)** — as above with `basketball_nba` + NBA Stats for the
   dossier.

## Conventions when adding a source

- One module per source in `src/panthera_mvp/clients/`, network-free tests
  with a recorded fixture in `tests/fixtures/`.
- Free-tier limits documented at the top of the client + any hard credit
  guard mirrored from `clients/odds.py`.
- New secrets must be added to the README setup section, root `CLAUDE.md`,
  and the PR description that introduces them.
