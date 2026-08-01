"""Timezone helpers.

Convention: everything is *stored* in UTC ISO-8601; all game-day and slot
logic runs in US/Eastern (America/New_York), because MLB slates and the
strategy's day/slot rules are defined in ET.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = UTC


def now_utc() -> datetime:
    return datetime.now(UTC)


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (Z or offset form) to an aware UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def to_et(dt: datetime) -> datetime:
    return dt.astimezone(ET)


def game_date_et(start_utc: datetime) -> date:
    """The ET calendar date a game belongs to (late West Coast games still
    belong to the ET date they started on)."""
    return start_utc.astimezone(ET).date()


def day_of_week(d: date) -> str:
    return d.strftime("%A").lower()
