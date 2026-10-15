# Secret rotation — who rotates what, where

Three API keys exist, all as GitHub Actions repository secrets on
`gitchrisqueen/panthera`. No key is committed or written to `data/`, and the
["Where a key could reach a log"](#where-a-key-could-reach-a-log) section below
accounts for every place one is put on the wire.

**Owner: the repository owner.** Creating and rotating secrets is theirs alone —
agents never hold, mint, or replace one. An agent that suspects a key is exposed
opens a task for the owner and stops.

| Secret | Provider | Console action | Overlap? | Required? | Blast radius if leaked |
|---|---|---|---|---|---|
| `ODDS_API_KEY` | [The Odds API](https://dash.the-odds-api.com/) | Dashboard → regenerate | **No — assume regeneration replaces the key in place** | Yes — MLB, NCAAF and college-baseball snapshots all draw on it | A stranger can drain the 500 credits/month free tier, which silently stops every odds snapshot. No data of ours is readable through it. |
| `LUMIFY_API_KEY` | [Lumify](https://lumify.ai) | Account/API settings | Unverified — treat as no overlap | Optional — missing key = splits are skipped silently | Drains the 1,000 non-expiring credits, permanently. Splits never change a P/V pick, so picks survive; `fade_public` and `sharp_split` stop getting input. |
| `CFBD_API_KEY` | [CollegeFootballData.com](https://collegefootballdata.com/key) | Request a new free key by email | **Yes** — the new key arrives while the old one still works | Optional — missing key = ESPN-only NCAAF | Burns the free monthly call cap. Cached responses under `data/ncaaf/cfbd/` keep the backtest working. |

The **Overlap?** column decides the procedure, so read it first. Neither
provider console documents whether a regenerated key coexists with the old one,
and nobody here has tested it, so the no-overlap path is the default: it is
correct either way, and the overlap path is not.

## How to rotate — no overlap (`ODDS_API_KEY`, `LUMIFY_API_KEY`)

Regeneration is assumed to kill the old value immediately, so there is no
window in which to verify before committing. **Expect a gap.** Any live
snapshot that fires between the regeneration and the secret update gets a 401,
`fetch_snapshot` raises `OddsRequestError`, and the workflow step exits
non-zero: the run goes **red and writes no picks**, which is the designed
failure and not something to work around. Odds snapshots run at 10:35, 16:50
and 18:20 ET, so rotating outside those minutes keeps the gap invisible.

1. Regenerate in the provider console.
2. **Immediately** set the new value: repo **Settings → Secrets and variables →
   Actions →** the secret → *Update*. Never paste a key into an issue, a PR, a
   commit, or a message to an agent.
3. Verify with a dispatch, using the positive evidence below — not a green run.
4. If verification fails, regenerate again and repeat from step 2. There is no
   old value to fall back to; the only recovery is a working new one.
5. Record the date and the reason wherever this project's rotation history is
   kept. The ["When to rotate"](#when-to-rotate) triggers are what read it.

## How to rotate — overlap available (`CFBD_API_KEY`)

1. Request the new key. **Do not** retire the old one yet.
2. Set the new value as in step 2 above.
3. Verify with a dispatch, using the positive evidence below.
4. Retire the old key only after that verification produced its evidence line.
5. Record the date and the reason, as above.

## Verifying a rotated key

**A green run does not prove a key works.** Every keyed step is built to
degrade rather than fail the slate, so each of these exits 0 with the key
untouched, or broken:

- `ncaaf prep` prints `[ncaaf prep] no upcoming FBS games: open snapshot
  skipped (0 credits)` and continues — true for most of January to August
  (`src/panthera_mvp/ncaaf/picks.py`).
- The credit guard prints `[ncaaf snapshot] SKIPPED: ...` and returns when the
  shared pool is at or below the NCAAF reserve of 60, which MLB's ~270/month
  can reach late in a month (`src/panthera_mvp/ncaaf/pipeline.py`).
- A dead `CFBD_API_KEY` is swallowed: `[ncaaf prep] CFBD refresh failed: ...`
  goes to stderr and the command still exits 0 (`ncaaf/picks.py`).
- A missing `LUMIFY_API_KEY` prints `[splits] LUMIFY_API_KEY not set; skipping
  splits collection` and returns 0 (`src/panthera_mvp/pipeline.py`).

So verify on the **evidence line**, and treat its absence as a failed
rotation even when the run is green:

| Key | Dispatch | Evidence that the key was used |
|---|---|---|
| `ODDS_API_KEY` | **NCAAF Strategy** (`ncaaf.yml`), `task: prep`, `dry_run: false` — 3 credits, in FBS season | `[ncaaf snapshot] <N> events; credits used=... remaining=...` **and** a new row in `data/odds/credit_log.csv` |
| `ODDS_API_KEY`, out of FBS season | **NCAAF Capture** (`ncaaf-capture.yml`) or **NCAA Baseball Capture** (`ncaabase-capture.yml`) with `odds: live` — these snapshot unconditionally, 3 credits — or **MVP Morning Run** (`mvp-morning.yml`) with `dry_run: false` during MLB season | the same `events; credits used=...` line and `credit_log.csv` row |
| `CFBD_API_KEY` | **NCAAF Strategy**, `task: prep`, `dry_run: false` — the same dispatch; its SP+ pull passes `refresh=True`, so it always hits the network and never answers from `data/ncaaf/cfbd/` | `[ncaaf prep] SP+ <year>: <N> teams; <M> venues` |
| `LUMIFY_API_KEY` | **MVP Splits Collection** (`mvp-splits.yml`), `dry_run: false` — manual-only and built for this check | `[splits] <N> events with splits (<label>); credits ...` |

A `dry_run: true` dispatch uses fixtures and proves nothing about any key.

## What an Odds API failure means

`OddsRequestError` deliberately drops the response body, so the status code is
the whole diagnosis:

| In the log | Means | Do |
|---|---|---|
| `HTTP 401` | the key is wrong, revoked or disabled | rotate (above) |
| `HTTP 422` | the request is malformed — a bad sport key or market, not a key problem | check the config that built it |
| `HTTP 429` | the monthly credit pool is exhausted or the rate limit was hit | check `data/odds/credit_log.csv`; the credit guard normally prevents this |
| `HTTP 5xx` | the vendor is down | nothing; the next scheduled run picks it up |
| `failed: ConnectionError` / `Timeout` | network or DNS, usually transient | nothing; the next run picks it up |

## When to rotate

- **Routinely:** no fixed schedule. These are read-only, low-value keys with a
  credit cap as their only real exposure; a calendar rotation would cost more
  attention than it buys.
- **Immediately,** on any of: a key appearing in a log, a traceback, a
  committed file or a screenshot; an unexplained drop in remaining credits
  (`data/odds/credit_log.csv`, `data/splits/credit_log.csv` — `doctor`'s H08
  `credit_floor` raises an issue once the balance crosses the floor, but
  nothing watches for a sudden day-over-day delta, so that one is read by a
  person); a 401 from a key that was working; or anyone outside the owner
  having had sight of the value.

## One-time action for the exposure this fix closes (2026-10-15)

Until the fix in `clients/odds.py` landed, any live snapshot that hit a 401,
429, 5xx or transport failure raised a raw `requests` exception whose message
carried the full request URL — `apiKey` included — into a **public** Actions
log. GitHub's masking of the registered secret was the only barrier, and
masking is best-effort.

No run was found that demonstrably printed it: the odds-calling workflows have
no failed run with a populated step list (the two that exist are queue
cancellations), and Actions log text older than the API's retention window
cannot be re-read to prove a negative. **So treat prior disclosure as
possible, not as ruled out**, and do the following once:

1. **Rotate `ODDS_API_KEY`** by the no-overlap procedure above, as part of
   shipping this change. Owner's action.
2. **Delete any failed run of an odds-calling workflow** (`MVP Morning Run`,
   `MVP Pregame Run`, `MVP Close Snapshot`, `NCAAF Strategy`, the two capture
   workflows) that predates the fix. Deleting the run is the only removal
   GitHub offers — individual log lines cannot be edited. Owner's action; an
   agent may list the candidate runs but deletes nothing.
3. Record both in the rotation history, so the next reader knows the key in
   use post-dates the fix.

`LUMIFY_API_KEY` and `CFBD_API_KEY` were never URL-borne by this repository
(see below) and are not part of this one-time action.

## Where a key could reach a log

Four places put a key on the wire. Each is accounted for:

- **`clients/odds.py`** — `ODDS_API_KEY` as the `apiKey` query parameter, which
  is the only form The Odds API accepts. Every `requests` failure is converted
  to `OddsRequestError`, carrying the status code and the key-free base URL and
  nothing else, raised outside the `except` handler so the original is not
  reachable through `__cause__` or `__context__`, with `api_key` deleted from
  the frame first so a locals-printing renderer cannot reach it either.
  `tests/test_odds_credentials.py` fails the build if the key can reach an
  exception message, its chain, a rendered traceback or a frame's locals.
- **`clients/cfbd.py`** — `CFBD_API_KEY` in an `Authorization: Bearer` header,
  so it is not part of any URL and cannot appear in a `requests` exception
  message. `ncaaf/picks.py` prints a CFBD exception to stderr; that is safe for
  the same reason.
- **`clients/lumify.py`** — `LUMIFY_API_KEY` goes to the `lumify` SDK's
  constructor. The installed SDK (`lumify-sdk` 0.2.0) sends it as
  `Authorization: Bearer ...` in `lumify/_transport.py`, so it is not
  URL-borne today. Two call sites would print an SDK exception verbatim into
  the public log if a future SDK version moved the key into the query string:
  the per-event `print(f"[splits] event {ev_id} failed: {exc}")`, and
  `client.events.list(...)`, which is not wrapped at all. `pyproject.toml`
  pins only `lumify-sdk>=0.2`, so **this is a property of the dependency, not
  of this repository** — re-check it on an SDK upgrade, or scrub those two
  sites the way `odds.py` does.
- **`.github/workflows/ncaabase-capture.yml`** — a zero-credit `/v4/sports`
  probe builds the keyed URL in a shell `curl`. It cannot print the value:
  `${ODDS_API_KEY}` is a shell variable, not a `${{ }}` expression, so Actions
  renders the command unexpanded in the log, and `curl -sS` diagnostics name
  the host, not the query string.

GitHub masks registered secret values in Actions logs, but masking is
best-effort — it breaks on encoded or line-split values — so it is treated as a
second line of defence, never the first.
