"""The Odds API client (the-odds-api.com).

Free tier = 500 credits/month. One MLB snapshot with markets h2h,spreads,totals
in the `us` region costs 3 credits (1 per market-region). The credit guard
refuses live calls when the remaining balance is at or below
odds_api.min_credits_reserve, so a hot month degrades gracefully instead of
zeroing out.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass

import pandas as pd
import requests

from .. import paths
from ..timeutil import now_utc, utc_iso

SPORTS_URL = "https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
MLB_SPORT_KEY = "baseball_mlb"
NCAAF_SPORT_KEY = "americanfootball_ncaaf"
BASE = SPORTS_URL.format(sport_key=MLB_SPORT_KEY)
TIMEOUT = 30


class CreditGuardError(RuntimeError):
    """Raised when a live snapshot would breach the credit reserve."""


class OddsRequestError(RuntimeError):
    """An Odds API request failure with the credentialed query string removed.

    The Odds API accepts its key only as the `apiKey` query parameter (there is
    no header form), and `requests` puts the whole request URL -- query string
    included -- into the message of HTTPError, ConnectionError and Timeout
    alike. This repository is public and every scheduled run writes to a public
    Actions log, so a raw `requests` exception from a keyed call would print the
    live key there, with GitHub's best-effort secret masking as the only
    barrier. Those messages therefore never leave this module: the raiser is
    replaced by this one, carrying the status code and the key-free base URL
    and nothing else, and raised outside the handler so the original is not
    reachable through `__cause__` or `__context__` either.

    The response body is dropped deliberately, so the status code is the whole
    diagnosis; `docs/secret-rotation.md` maps each status to an action.
    """

    def __init__(
        self, url: str, status_code: int | None = None, cause: str = ""
    ) -> None:
        self.url = url  # base URL only -- never the query string
        self.status_code = status_code
        self.cause = cause
        detail = (
            f"HTTP {status_code}"
            if status_code is not None
            else cause or "request failed"
        )
        super().__init__(f"Odds API request to {url} failed: {detail}")


@dataclass
class CreditInfo:
    used: int | None
    remaining: int | None


def api_key_from_env() -> str:
    """Read ODDS_API_KEY and hand it straight to `fetch_snapshot`.

    Callers use `odds.fetch_snapshot(odds.api_key_from_env(), ...)` rather than
    binding the key to a local of their own: a caller's frame is in the
    traceback of a failed snapshot, and a local there would hold the key for any
    renderer that prints locals, undoing the `del` inside `fetch_snapshot`. This
    function has returned by the time the keyed call runs, so its own frame is
    not in that traceback.
    """
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise SystemExit("ODDS_API_KEY is not set")
    return key


def last_known_remaining() -> int | None:
    path = paths.credit_log_csv()
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    # Only trust balances observed in the current UTC month — the free tier
    # resets monthly.
    month = now_utc().strftime("%Y-%m")
    df = df[df["month"] == month]
    if df.empty:
        return None
    val = df.iloc[-1]["requests_remaining"]
    return int(val) if pd.notna(val) else None


def record_credits(label: str, info: CreditInfo) -> None:
    path = paths.credit_log_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with open(path, "a", newline="") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(
                ["ts_utc", "label", "requests_used_total", "requests_remaining", "month"]
            )
        writer.writerow(
            [
                utc_iso(now_utc()),
                label,
                info.used if info.used is not None else "",
                info.remaining if info.remaining is not None else "",
                now_utc().strftime("%Y-%m"),
            ]
        )


def fetch_snapshot(
    api_key: str,
    regions: str = "us",
    markets: str = "h2h,spreads,totals",
    min_credits_reserve: int = 30,
    session: requests.Session | None = None,
    sport_key: str = MLB_SPORT_KEY,
) -> tuple[list[dict], CreditInfo]:
    """Fetch one odds snapshot. Every sport draws on the same monthly credit
    pool, so the guard reads the one shared credit log regardless of sport."""
    remaining = last_known_remaining()
    if remaining is not None and remaining <= min_credits_reserve:
        raise CreditGuardError(
            f"Odds API credits low ({remaining} remaining <= reserve "
            f"{min_credits_reserve}); skipping live snapshot."
        )
    sess = session or requests.Session()
    url = SPORTS_URL.format(sport_key=sport_key)
    scrubbed: OddsRequestError | None = None
    try:
        resp = sess.get(
            url,
            params={
                "apiKey": api_key,
                "regions": regions,
                "markets": markets,
                "oddsFormat": "american",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        scrubbed = OddsRequestError(url, status_code=status)
    except requests.RequestException as exc:
        # Transport failures embed the query string too -- ConnectionError's
        # "Max retries exceeded with url: ...?apiKey=...".
        scrubbed = OddsRequestError(url, cause=type(exc).__name__)
    if scrubbed is not None:
        # `del` first: this frame appears in the raised traceback, and its
        # locals still bind the key. The default traceback renderer never
        # prints locals, but a renderer that does -- `pytest --showlocals`,
        # rich, an error reporter -- would expose the key past the scrubbed
        # message.
        del api_key
        # Raised OUTSIDE the handler on purpose. `raise ... from None` only
        # sets __suppress_context__, which stops the default traceback printer
        # from rendering the original -- the keyed exception object itself
        # stays reachable on __context__. Out here the active exception is
        # already cleared, so __context__ is None and nothing holding the key
        # survives the call.
        raise scrubbed

    def _hdr(name: str) -> int | None:
        val = resp.headers.get(name)
        try:
            return int(float(val)) if val is not None else None
        except ValueError:
            return None

    info = CreditInfo(
        used=_hdr("x-requests-used"), remaining=_hdr("x-requests-remaining")
    )
    return resp.json(), info


def save_raw(events: list[dict], date_et: str, label: str) -> None:
    raw_dir = paths.raw_odds_dir(date_et)
    raw_dir.mkdir(parents=True, exist_ok=True)
    with open(raw_dir / f"{label}.json", "w") as fh:
        json.dump(events, fh, indent=1)


def american_to_decimal(american: float) -> float:
    if american > 0:
        return round(1 + american / 100, 4)
    return round(1 + 100 / abs(american), 4)


def normalize(
    events: list[dict], snapshot_ts_utc: str, label: str
) -> pd.DataFrame:
    """Flatten an Odds API response to the long lines.csv schema.

    game_pk and game_date_et are filled by the caller after event matching.
    """
    rows = []
    for ev in events:
        for bm in ev.get("bookmakers", []):
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    if price is None:
                        continue
                    rows.append(
                        {
                            "snapshot_ts_utc": snapshot_ts_utc,
                            "snapshot_label": label,
                            "odds_event_id": ev["id"],
                            "game_pk": None,
                            "game_date_et": None,
                            "commence_time_utc": ev.get("commence_time"),
                            "home_team": ev.get("home_team"),
                            "away_team": ev.get("away_team"),
                            "bookmaker": bm.get("key"),
                            "market": market.get("key"),
                            "outcome": outcome.get("name"),
                            "point": outcome.get("point"),
                            "price_american": price,
                            "price_decimal": american_to_decimal(price),
                        }
                    )
    return pd.DataFrame(rows)
