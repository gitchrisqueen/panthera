"""Raw per-game features, logged at decision time.

One row per game on the slate (not only the qualifiers), raw values only: no
threshold is applied here, so any rule set can be replayed later over the same
rows without look-ahead. Pure: `build_feature_rows` reads nothing from disk
except the lab config's two fixed feature constants when none are passed.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from ..ncaaf import parlay
from ..ncaaf.matching import normalize_name
from ..ncaaf.sources import school_key
from ..timeutil import parse_utc, utc_iso

FEATURE_COLUMNS = [
    "decision_date_et", "decision_ts_utc", "event_id", "start_time_utc",
    "home_team", "away_team", "neutral_site", "indoor",
    "spread_open", "spread_now", "total_open", "total_now", "wind_mph",
    "sp_margin_home",
    "home_prev_beat_rank", "away_prev_beat_rank",
    "home_next_opp_rank", "away_next_opp_rank",
    "spread_home_point", "spread_home_dec", "spread_away_point", "spread_away_dec",
    "over_point", "over_dec", "under_point", "under_dec",
    "lead_minutes",
]

KEY = ["decision_date_et", "event_id"]


def _blank(v):
    """None for NaN, otherwise the value."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def _price(v: parlay.GameView, market: str, side: str) -> tuple:
    bp = parlay.best_price(v, market, side)
    if bp is None:
        return None, None
    return float(bp["point"]), float(bp["price_decimal"])


def build_feature_rows(
    views: list[parlay.GameView],
    schedules: dict[str, list[parlay.TeamGame]],
    sp_ratings: dict[str, float],
    wind_mph: dict[str, float],
    decision_day: str,
    decision_ts: str | datetime,
    now_utc: datetime,
    aliases: dict[str, str] | None = None,
    feature_cfg: dict | None = None,
) -> list[dict]:
    if feature_cfg is None:
        from .config import load_lab_config

        feature_cfg = load_lab_config("ncaaf")["feature"]
    hfa_const = float(feature_cfg["home_field_points"])
    gap = timedelta(days=float(feature_cfg["max_gap_days"]))
    alias = {normalize_name(k): normalize_name(val) for k, val in (aliases or {}).items()}
    ts = decision_ts if isinstance(decision_ts, str) else utc_iso(decision_ts)

    rows = []
    for v in sorted(views, key=lambda x: (x.start_time_utc, x.event_id)):
        start = parse_utc(v.start_time_utc)

        def prev_beat(team: str) -> float | None:
            g = parlay._prev_game(schedules.get(parlay._key(team, alias), []), start, gap)
            if (g is not None and g.status == "Final" and g.team_score is not None
                    and g.opp_score is not None and g.team_score > g.opp_score
                    and g.opp_rank is not None):
                return float(g.opp_rank)
            return None

        def next_opp(team: str) -> float | None:
            g = parlay._next_game(schedules.get(parlay._key(team, alias), []), start, gap)
            return None if g is None or g.opp_rank is None else float(g.opp_rank)

        sp_margin = None
        rh = sp_ratings.get(school_key(v.home_school)) if v.home_school else None
        ra = sp_ratings.get(school_key(v.away_school)) if v.away_school else None
        if rh is not None and ra is not None:
            sp_margin = rh - ra + (0.0 if v.neutral_site else hfa_const)

        sh_pt, sh_dec = _price(v, parlay.SPREAD, "home")
        sa_pt, sa_dec = _price(v, parlay.SPREAD, "away")
        ov_pt, ov_dec = _price(v, parlay.TOTAL, "over")
        un_pt, un_dec = _price(v, parlay.TOTAL, "under")
        rows.append({
            "decision_date_et": decision_day,
            "decision_ts_utc": ts,
            "event_id": v.event_id,
            "start_time_utc": v.start_time_utc,
            "home_team": v.home_team,
            "away_team": v.away_team,
            "neutral_site": bool(v.neutral_site),
            "indoor": None if v.indoor is None else bool(v.indoor),
            "spread_open": v.spread_open,
            "spread_now": v.spread_now,
            "total_open": v.total_open,
            "total_now": v.total_now,
            "wind_mph": wind_mph.get(v.event_id),
            "sp_margin_home": sp_margin,
            "home_prev_beat_rank": prev_beat(v.home_team),
            "away_prev_beat_rank": prev_beat(v.away_team),
            "home_next_opp_rank": next_opp(v.home_team),
            "away_next_opp_rank": next_opp(v.away_team),
            "spread_home_point": sh_pt, "spread_home_dec": sh_dec,
            "spread_away_point": sa_pt, "spread_away_dec": sa_dec,
            "over_point": ov_pt, "over_dec": ov_dec,
            "under_point": un_pt, "under_dec": un_dec,
            "lead_minutes": round((start - now_utc).total_seconds() / 60, 2),
        })
    return rows
