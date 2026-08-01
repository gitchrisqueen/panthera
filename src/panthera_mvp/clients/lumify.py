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
from ..timeutil import now_utc, utc_iso


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


def fetch_splits_for_date(
    api_key: str,
    date_et: str,
    league: str = "MLB",
    min_credits_reserve: int = 50,
) -> tuple[list[dict], SplitsCreditInfo]:
    """Fetch splits for every league event on an ET date.

    Returns ([{event: EventSummary, splits: SplitsResponse}, ...], credits).
    """
    remaining = last_known_remaining()
    if remaining is not None and remaining <= min_credits_reserve:
        raise LumifyCreditGuardError(
            f"Lumify credits low ({remaining} remaining <= reserve "
            f"{min_credits_reserve}); skipping splits fetch."
        )

    from lumify import Lumify

    client = Lumify(api_key=api_key)
    listing = client.events.list(league=league, date=date_et, limit=100)
    events = listing.get("events", []) if isinstance(listing, dict) else []

    results: list[dict] = []
    last_used = last_rem = None
    for ev in events:
        ev_id = ev.get("id")
        if ev_id is None:
            continue
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


def _walk_percentages(node: Any, path: tuple = ()) -> list[tuple[tuple, float]]:
    """Recursively collect numeric leaves that look like percentages.

    The consensus payload is schemaless (Dict[str, Any]); raw JSON is always
    stored, and this flattener extracts whatever numeric split values exist,
    keyed by their JSON path (e.g. moneyline.home.tickets_pct)."""
    found: list[tuple[tuple, float]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_walk_percentages(value, (*path, str(key).lower())))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        if 0 <= float(node) <= 100:
            found.append((path, float(node)))
    return found


def normalize(results: list[dict], date_et: str, label: str = "manual") -> pd.DataFrame:
    """Flatten splits to a long table: one row per (event, metric path)."""
    rows = []
    ts = utc_iso(now_utc())
    for item in results:
        ev, splits = item["event"], item["splits"]
        consensus = splits.get("consensus") or {}
        for path, value in _walk_percentages(consensus):
            rows.append(
                {
                    "fetched_ts_utc": ts,
                    "game_date_et": date_et,
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
