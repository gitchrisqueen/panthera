"""Lumify client — public betting splits (lumify.ai, via the official SDK).

Why this exists: the strategy's core premise is Public vs. Vegas money.
Line movement only *infers* which side the public is on; Lumify's splits
endpoint *measures* it (ticket/money percentages per side). Splits are
collected alongside picks so the ledger can test whether the movement
inference (rule R2) agrees with measured public betting.

Splits are observational for now — they do not change pick generation.

Credits: free tier = 1,000 non-expiring credits; every response reports
X-Credits-Used / X-Credits-Remaining (surfaced by the SDK as response meta).
Fetching one slate (1 list + ~15 splits calls) daily costs roughly
16+ credits/day, so the default schedule is the pregame run only, with a
reserve guard mirroring clients/odds.py.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .. import paths
from ..timeutil import ET, now_utc, parse_utc, utc_iso


class LumifyCreditGuardError(RuntimeError):
    """Raised when a live splits fetch would breach the credit reserve."""


@dataclass
class SplitsCreditInfo:
    used: int | None
    remaining: int | None


def splits_csv():
    return paths.data_dir() / "splits" / "splits.csv"


def credit_log():
    return paths.data_dir() / "splits" / "credit_log.csv"


def raw_dir(date_et: str):
    return paths.data_dir() / "splits" / "raw" / date_et


def last_known_remaining() -> int | None:
    path = credit_log()
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    val = df.iloc[-1]["credits_remaining"]
    return int(val) if pd.notna(val) else None


def record_credits(info: SplitsCreditInfo) -> None:
    path = credit_log()
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with open(path, "a", newline="") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(["ts_utc", "credits_used", "credits_remaining"])
        writer.writerow(
            [
                utc_iso(now_utc()),
                info.used if info.used is not None else "",
                info.remaining if info.remaining is not None else "",
            ]
        )


def _meta_credits(payload: Any) -> tuple[int | None, int | None]:
    """Pull credit counters off an SDK response, tolerating absence."""
    try:
        from lumify import get_meta

        meta = get_meta(payload)
        if meta is None:
            return None, None
        used = getattr(meta, "credits_used", None)
        remaining = getattr(meta, "credits_remaining", None)
        return (
            int(used) if used is not None else None,
            int(remaining) if remaining is not None else None,
        )
    except Exception:
        return None, None


def _event_start_et(ev: dict):
    """Parse an event's starts_at into an ET datetime (None if unparseable)."""
    raw = ev.get("starts_at")
    if not raw:
        return None
    try:
        return parse_utc(str(raw)).astimezone(ET)
    except (ValueError, TypeError):
        return None


def fetch_splits_for_date(
    api_key: str,
    date_et: str,
    league: str = "MLB",
    min_credits_reserve: int = 50,
    window: str = "all",
) -> tuple[list[dict], SplitsCreditInfo]:
    """Fetch splits for the ET date's not-yet-started events.

    Lumify's `date=` parameter is **UTC-keyed**: games starting >= 20:00 ET
    fall on the next UTC date and were previously fetched a day late, after
    they had finished (56 of the first 218 collected events). So the evening
    fetch queries both overlapping UTC dates and filters events to those whose
    *ET start date* equals `date_et`.

    Already-started events are skipped before spending a splits credit —
    ~54% of early pregame-run credits were burned on games underway.

    `window`: "morning" keeps only games starting before 16:00 ET (the
    morning picks window; the pregame fetch covers the evening with fresher
    data); "pregame" / "all" keep the whole remaining ET day.

    Returns ([{event: EventSummary, splits: SplitsResponse}, ...], credits).
    """
    remaining = last_known_remaining()
    if remaining is not None and remaining <= min_credits_reserve:
        raise LumifyCreditGuardError(
            f"Lumify credits low ({remaining} remaining <= reserve "
            f"{min_credits_reserve}); skipping splits fetch."
        )

    from datetime import date as _date
    from datetime import timedelta as _timedelta

    from lumify import Lumify

    client = Lumify(api_key=api_key)

    # Evening ET games (>= 20:00 ET) live on UTC date D+1; the morning window
    # (< 16:00 ET) never does, so one list call suffices there.
    utc_dates = [date_et]
    if window != "morning":
        utc_dates.append(str(_date.fromisoformat(date_et) + _timedelta(days=1)))

    events: list[dict] = []
    seen_ids: set = set()
    for utc_d in utc_dates:
        listing = client.events.list(league=league, date=utc_d, limit=100)
        for ev in listing.get("events", []) if isinstance(listing, dict) else []:
            ev_id = ev.get("id")
            if ev_id is None or ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)
            events.append(ev)

    now_et = now_utc().astimezone(ET)
    results: list[dict] = []
    last_used = last_rem = None
    for ev in events:
        start_et = _event_start_et(ev)
        if start_et is None or str(start_et.date()) != date_et:
            continue  # wrong ET day (UTC-shifted listing)
        if start_et <= now_et:
            continue  # already started — a splits credit here is wasted
        if window == "morning" and start_et.hour >= 16:
            continue  # evening game; the pregame fetch covers it fresher
        ev_id = ev.get("id")
        try:
            splits = client.events.splits(ev_id)
        except Exception as exc:  # one bad event must not sink the slate
            print(f"[splits] event {ev_id} failed: {exc}")
            continue
        used, rem = _meta_credits(splits)
        last_used, last_rem = (
            used if used is not None else last_used,
            rem if rem is not None else last_rem,
        )
        if splits.get("available"):
            results.append({"event": ev, "splits": splits})
    return results, SplitsCreditInfo(used=last_used, remaining=last_rem)


def save_raw(results: list[dict], date_et: str, label: str = "manual") -> None:
    out = raw_dir(date_et)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"splits-{label}.json", "w") as fh:
        json.dump(results, fh, indent=1, default=str)


#: Only true split percentages are stored. The consensus payload also carries
#: `price` (American odds, e.g. -131 — meaningless under a [0,100] filter,
#: which used to keep +100 prices and drop everything else) and `line`
#: (spread/total points, which used to masquerade as percentages). Prices for
#: splits strategies come from lines.csv consensus, never from this table.
METRIC_WHITELIST_LEAVES = {"bets_pct", "handle_pct"}


def _walk_percentages(node: Any, path: tuple = ()) -> list[tuple[tuple, float]]:
    """Recursively collect whitelisted percentage leaves.

    The consensus payload is schemaless (Dict[str, Any]); raw JSON is always
    stored, and this flattener extracts the ticket/money share values,
    keyed by their JSON path (e.g. moneyline.home.bets_pct)."""
    found: list[tuple[tuple, float]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_walk_percentages(value, (*path, str(key).lower())))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        if path and path[-1] in METRIC_WHITELIST_LEAVES and 0 <= float(node) <= 100:
            found.append((path, float(node)))
    return found


def normalize(results: list[dict], date_et: str, label: str = "manual") -> pd.DataFrame:
    """Flatten splits to a long table: one row per (event, metric path).

    `game_date_et` is derived from the event's ET start date, not the fetch
    date — Lumify listings are UTC-keyed, and stamping the fetch date used to
    attach a late game's splits to the *next day's* game in a multi-day
    series (28 contradictory (date, game_pk) pairs in the first 16 days).
    The fetch date is only a fallback for unparseable start times.
    """
    rows = []
    ts = utc_iso(now_utc())
    for item in results:
        ev, splits = item["event"], item["splits"]
        start_et = _event_start_et(ev)
        game_date = str(start_et.date()) if start_et is not None else date_et
        consensus = splits.get("consensus") or {}
        for path, value in _walk_percentages(consensus):
            rows.append(
                {
                    "fetched_ts_utc": ts,
                    "game_date_et": game_date,
                    "snapshot_label": label,
                    "lumify_event_id": ev.get("id"),
                    "event_name": ev.get("name"),
                    "starts_at_utc": ev.get("starts_at"),
                    "captured_at": splits.get("captured_at"),
                    "game_pk": None,
                    "metric": ".".join(path),
                    "value": value,
                }
            )
    return pd.DataFrame(rows)


SPLITS_KEY = ["game_date_et", "snapshot_label", "lumify_event_id", "metric"]


def append_splits(df: pd.DataFrame) -> int:
    """Upsert by (date, label, event, metric): morning and pregame snapshots
    coexist; re-running the same label refreshes its values."""
    if df.empty:
        return 0
    path = splits_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        if "snapshot_label" not in existing.columns:
            # Rows written before labels existed came from manual runs.
            existing["snapshot_label"] = "manual"
        merged_keys = set(map(tuple, df[SPLITS_KEY].astype(str).values))
        keep = [
            tuple(map(str, row)) not in merged_keys
            for row in existing[SPLITS_KEY].values
        ]
        combined = pd.concat([existing[keep], df], ignore_index=True)
    else:
        combined = df
    combined.to_csv(path, index=False)
    return len(df)


def load_splits() -> pd.DataFrame:
    path = splits_csv()
    return pd.read_csv(path) if path.exists() else pd.DataFrame()
