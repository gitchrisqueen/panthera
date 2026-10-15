# Secret rotation — who rotates what, where

Three API keys exist, all as GitHub Actions repository secrets on
`gitchrisqueen/panthera`. No key is ever committed, written to `data/`, or
printed by a workflow.

**Owner: the repository owner (Christopher).** Creating and rotating secrets is
his alone — agents never hold, mint, or replace one. An agent that suspects a
key is exposed raises it as a `needs-chris` task and stops.

| Secret | Provider | Console | Required? | Blast radius if leaked |
|---|---|---|---|---|
| `ODDS_API_KEY` | [The Odds API](https://the-odds-api.com/account/) | Account page → regenerate | Yes — MLB, NCAAF and college-baseball snapshots all draw on it | A stranger can drain the 500 credits/month free tier, which silently stops every odds snapshot. No data of ours is readable through it. |
| `LUMIFY_API_KEY` | [Lumify](https://lumify.ai) | Account/API settings | Optional — missing key = splits are skipped silently | Drains the 1,000 non-expiring credits, permanently. Splits never change a P/V pick, so picks survive; `fade_public` and `sharp_split` stop getting input. |
| `CFBD_API_KEY` | [CollegeFootballData.com](https://collegefootballdata.com/key) | Request a new free key by email | Optional — missing key = ESPN-only NCAAF | Burns the free monthly call cap. Cached responses under `data/ncaaf/cfbd/` keep the backtest working. |

## How to rotate

1. Mint the replacement in the provider's console above. Do not revoke the old
   key yet.
2. Set the new value: repo **Settings → Secrets and variables → Actions →**
   the secret → *Update*. Never paste a key into an issue, a PR, a commit, or a
   chat message with an agent.
3. Dispatch one cheap workflow to prove the new key works, rather than waiting
   for the next cron. A `dry_run` run uses fixtures and proves nothing about
   the key, so each of these needs `dry_run: false`:
   - `ODDS_API_KEY` **and** `CFBD_API_KEY` — **NCAAF Strategy**
     (`ncaaf.yml`), `task: prep`, `dry_run: false`. One `open` snapshot
     (3 credits, the cheapest live odds proof, and it covers a whole week)
     plus the CFBD SP+ and venues pulls. CFBD answers cached endpoints from
     `data/ncaaf/cfbd/`, so pick a week that is not cached yet if the CFBD leg
     needs to hit the network.
   - `LUMIFY_API_KEY` — **MVP Splits Collection** (`mvp-splits.yml`),
     `dry_run: false`. Manual-only and built for exactly this check.
4. Revoke the old key in the provider's console only after that run is green.
5. Record the rotation date and the reason in the project's vault note.

## When to rotate

- **Routinely:** no fixed schedule. These are read-only, low-value keys with a
  credit cap as their only real exposure; a calendar rotation would cost more
  attention than it buys.
- **Immediately,** on any of: a key appearing in a log, a traceback, a
  committed file or a screenshot; an unexplained drop in remaining credits
  (`data/odds/credit_log.csv`, `data/splits/credit_log.csv`); a 401 from a key
  that was working; or anyone outside the owner having had sight of the value.

## Why a leak is unlikely to come from our own logs

The Odds API accepts its key only as the `apiKey` query parameter, and
`requests` puts the whole request URL into the message of every exception it
raises — so an unhandled HTTP or transport error would have printed the live
key into this public repository's Actions log. `clients/odds.py` therefore
converts every `requests` failure into `OddsRequestError`, which carries the
status code and the key-free base URL and nothing else;
`tests/test_odds_credentials.py` fails the build if the key can reach an
exception message, its chain or a rendered traceback.

`CFBD_API_KEY` is sent as an `Authorization: Bearer` header, so it is not part
of any URL and never appears in a `requests` exception message.
`LUMIFY_API_KEY` is handed to the `lumify` SDK's constructor, not placed in a
URL by this repository.

GitHub masks the registered secret values in Actions logs, but masking is
best-effort — it breaks on encoded or line-split values — so it is treated as a
second line of defence, never the first.
