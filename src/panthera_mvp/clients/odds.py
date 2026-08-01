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
from dataclasses import dataclass

import pandas as pd
import requests

from .. import paths
from ..timeutil import now_utc, utc_iso

BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
TIMEOUT = 30


class CreditGuardError(RuntimeError):
    """Raised when a live snapshot would breach the credit reserve."""


@dataclass
class CreditInfo:
    used: int | None
    remaining: int | None


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
) -> tuple[list[dict], CreditInfo]:
    remaining = last_known_remaining()
    if remaining is not None and remaining <= min_credits_reserve:
        raise CreditGuardError(
            f"Odds API credits low ({remaining} remaining <= reserve "
            f"{min_credits_reserve}); skipping live snapshot."
        )
    sess = session or requests.Session()
    resp = sess.get(
        BASE,
        params={
            "apiKey": api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "american",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()

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
