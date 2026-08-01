"""P/V day and slot classification (doc §2).

Each ET day is Public, Vegas, or hybrid (Wednesday per the doc). On a hybrid
day, games starting before hybrid_boundary_hour_et are Public slots and later
games are Vegas slots. On a plain P/V day every slot inherits the day type.
"""

from __future__ import annotations

from datetime import date, datetime

from ..timeutil import day_of_week, to_et


def day_type(d: date, cfg: dict) -> str:
    """Return "P", "V", or "HYBRID" for the ET calendar date."""
    return cfg["day_map"][day_of_week(d)]


def slot_type(start_utc: datetime, cfg: dict) -> str:
    """Return "P" or "V" for a game's start time."""
    start_et = to_et(start_utc)
    dtype = day_type(start_et.date(), cfg)
    if dtype != "HYBRID":
        return dtype
    boundary = int(cfg["hybrid_boundary_hour_et"])
    return "P" if start_et.hour < boundary else "V"
