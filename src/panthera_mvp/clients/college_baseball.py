"""NCAA Division I college baseball — schedule and finals. Keyless.

Primary: henrygd/ncaa-api (a JSON wrapper over NCAA.com). One call per ET
date returns every D1 game with its NCAA `gameID` (our game key), teams,
start time and, once played, the final score:

    GET {base}/scoreboard/baseball/d1/{YYYY}/{MM}/{DD}/all-conf

The daily path is the one the ncaa-api project's own tests use for baseball
(`/scoreboard/baseball/d1/2025/06/22/all-conf`); its source passes the
`YYYY/MM/DD` segment through as NCAA's `contestDate`. The month-only form
(`.../2026/05/all-conf`) also answers, but what NCAA returns for a bare month
is not documented — we never use it. The public demo host is rate-limited to
5 requests/second/IP; `get_schedule_range` paces itself under that.
Since 2025 the API builds the scoreboard from NCAA's GraphQL feed, where
`names.full` and conference names are empty — `names.short` / `names.seo` /
`names.char6` are what we get ("Florida St.", "florida-st", "FSU").
`gameState` is only ever final | live | pre (unknown NCAA states map to pre),
so postponed/canceled/suspended are read from `currentPeriod`/`finalMessage`
text — unverified against a live postponement.

Fallback finals: ESPN's unofficial college-baseball scoreboard,

    GET https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard?dates=YYYYMMDD

used only to settle games ncaa-api has not marked final. Whether ESPN needs
a `groups=` filter to list every D1 game (as its college-football feed does)
is unverified; `groups` is a config knob, default unset.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import requests

from ..timeutil import ET, game_date_et, parse_utc, utc_iso

NCAA_API_BASE = "https://ncaa-api.henrygd.me"
ESPN_BASE = (
    "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard"
)
TIMEOUT = 30
MIN_INTERVAL_S = 0.25  # stay under the demo host's 5 req/s/IP


@dataclass
class BaseballGame:
    game_id: str  # NCAA gameID
    game_date_et: str
    start_time_utc: str
    start_time_tba: bool  # no epoch/time from NCAA: start is the ET date's midnight
    home_team: str  # NCAA names.short
    away_team: str
    home_seo: str
    away_seo: str
    home_char6: str
    away_char6: str
    home_rank: int | None
    away_rank: int | None
    home_conference: str  # conferenceSeo
    away_conference: str
    status: str  # Scheduled | InProgress | Final | Postponed | Canceled | Suspended
    current_period: str  # e.g. "FINAL", "FINAL/7" (run rule), "Top 5th"
    home_score: int | None
    away_score: int | None
    score_source: str  # "ncaa" | "espn" (fallback); "" until final


@dataclass
class EspnBaseballGame:
    event_id: str
    start_time_utc: str
    home_names: list[str]  # location, displayName, shortDisplayName — for matching
    away_names: list[str]
    status: str
    home_score: int | None
    away_score: int | None


# --- ncaa-api ---------------------------------------------------------------

# Checked in order against "currentPeriod finalMessage" (lowercased).
_TEXT_STATUS = [
    ("cancel", "Canceled"),
    ("postpone", "Postponed"),
    ("ppd", "Postponed"),
    ("suspend", "Suspended"),
]
_STATE = {"final": "Final", "live": "InProgress", "pre": "Scheduled"}


def _ncaa_status(game: dict) -> str:
    text = f"{game.get('currentPeriod', '')} {game.get('finalMessage', '')}".lower()
    for needle, status in _TEXT_STATUS:
        if needle in text:
            return status
    return _STATE.get(str(game.get("gameState", "")).lower(), "Scheduled")


def _int_or_none(val) -> int | None:
    if val in (None, ""):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _start(game: dict, fallback_date_et: str) -> tuple[datetime, str, bool]:
    """Return (start UTC, ET game date, tba). Prefers startTimeEpoch; then
    startDate + "6:00PM ET"; a TBA time keeps the date at ET midnight."""
    try:
        d = datetime.strptime(game.get("startDate", ""), "%m/%d/%Y").date()
    except ValueError:
        d = date.fromisoformat(fallback_date_et)
    epoch = _int_or_none(game.get("startTimeEpoch"))
    if epoch:
        start = datetime.fromtimestamp(epoch, UTC)
        return start, str(game_date_et(start)), False
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*([AP]M)", game.get("startTime", "") or "", re.I)
    if m:
        hour = int(m.group(1)) % 12 + (12 if m.group(3).upper() == "PM" else 0)
        local = datetime(d.year, d.month, d.day, hour, int(m.group(2)), tzinfo=ET)
        return local.astimezone(UTC), str(d), False
    return datetime(d.year, d.month, d.day, tzinfo=ET).astimezone(UTC), str(d), True


def parse_schedule(payload: dict, date_et: str) -> list[BaseballGame]:
    """Parse one ncaa-api scoreboard payload. `date_et` (YYYY-MM-DD) is the
    requested date, used only when a game carries no startDate."""
    games: list[BaseballGame] = []
    for wrapper in payload.get("games", []):
        g = wrapper.get("game") or {}
        home, away = g.get("home") or {}, g.get("away") or {}
        hn, an = home.get("names") or {}, away.get("names") or {}
        if not (g.get("gameID") and hn.get("short") and an.get("short")):
            continue
        start, gd, tba = _start(g, date_et)
        status = _ncaa_status(g)
        hs, as_ = _int_or_none(home.get("score")), _int_or_none(away.get("score"))
        final = status == "Final" and hs is not None and as_ is not None
        if status == "Final" and not final:  # "final" with no score: not settled
            status = "InProgress"
        games.append(
            BaseballGame(
                game_id=str(g["gameID"]),
                game_date_et=gd,
                start_time_utc=utc_iso(start),
                start_time_tba=tba,
                home_team=hn["short"],
                away_team=an["short"],
                home_seo=hn.get("seo", ""),
                away_seo=an.get("seo", ""),
                home_char6=hn.get("char6", ""),
                away_char6=an.get("char6", ""),
                home_rank=_int_or_none(home.get("rank")),
                away_rank=_int_or_none(away.get("rank")),
                home_conference=((home.get("conferences") or [{}])[0]).get("conferenceSeo", ""),
                away_conference=((away.get("conferences") or [{}])[0]).get("conferenceSeo", ""),
                status=status,
                current_period=str(g.get("currentPeriod", "")),
                home_score=hs if final else None,
                away_score=as_ if final else None,
                score_source="ncaa" if final else "",
            )
        )
    return games


def scoreboard_url(date_et: str, base_url: str = NCAA_API_BASE) -> str:
    y, m, d = date_et.split("-")
    return f"{base_url.rstrip('/')}/scoreboard/baseball/d1/{y}/{m}/{d}/all-conf"


def get_schedule(
    date_et: str, base_url: str = NCAA_API_BASE, session: requests.Session | None = None
) -> list[BaseballGame]:
    """All D1 games for one ET date (YYYY-MM-DD). A 404 raises like any other
    error: ncaa-api answers 404 both for "no such scoreboard" and when its
    upstream NCAA GraphQL call fails for a 2026+ date, so it can't be read as
    "no games"."""
    sess = session or requests.Session()
    resp = sess.get(scoreboard_url(date_et, base_url), timeout=TIMEOUT)
    resp.raise_for_status()
    return [g for g in parse_schedule(resp.json(), date_et) if g.game_date_et == date_et]


def get_schedule_range(
    start_et: str,
    end_et: str,
    base_url: str = NCAA_API_BASE,
    session: requests.Session | None = None,
    pause_s: float = MIN_INTERVAL_S,
) -> list[BaseballGame]:
    """Inclusive ET date range, one call per day, paced under the rate limit."""
    sess = session or requests.Session()
    d, end = date.fromisoformat(start_et), date.fromisoformat(end_et)
    games: list[BaseballGame] = []
    while d <= end:
        games.extend(get_schedule(str(d), base_url, sess))
        d += timedelta(days=1)
        if d <= end and pause_s:
            time.sleep(pause_s)
    return games


# --- ESPN fallback ------------------------------------------------------------

_ESPN_STATUS = {
    "STATUS_SCHEDULED": "Scheduled",
    "STATUS_IN_PROGRESS": "InProgress",
    "STATUS_END_PERIOD": "InProgress",
    "STATUS_DELAYED": "Scheduled",
    "STATUS_RAIN_DELAY": "InProgress",
    "STATUS_FINAL": "Final",
    "STATUS_POSTPONED": "Postponed",
    "STATUS_CANCELED": "Canceled",
    "STATUS_SUSPENDED": "Suspended",
}


def _espn_status(comp: dict) -> str:
    stype = (comp.get("status") or {}).get("type") or {}
    name = stype.get("name", "")
    if name in _ESPN_STATUS:
        return _ESPN_STATUS[name]
    if stype.get("completed"):
        return "Final"
    return "Scheduled"


def _espn_names(competitor: dict) -> list[str]:
    team = competitor.get("team") or {}
    names = [team.get(k) for k in ("location", "displayName", "shortDisplayName")]
    return [n for n in dict.fromkeys(names) if n]


def parse_espn_scoreboard(payload: dict) -> list[EspnBaseballGame]:
    games: list[EspnBaseballGame] = []
    for event in payload.get("events", []):
        for comp in event.get("competitions", []):
            home = away = None
            for c in comp.get("competitors", []):
                if c.get("homeAway") == "home":
                    home = c
                else:
                    away = c
            start = comp.get("date") or event.get("date")
            if not (home and away and start):
                continue
            status = _espn_status(comp)
            final = status == "Final"
            games.append(
                EspnBaseballGame(
                    event_id=str(event.get("id") or comp.get("id")),
                    start_time_utc=utc_iso(parse_utc(start)),
                    home_names=_espn_names(home),
                    away_names=_espn_names(away),
                    status=status,
                    home_score=_int_or_none(home.get("score")) if final else None,
                    away_score=_int_or_none(away.get("score")) if final else None,
                )
            )
    return games


def get_espn_scoreboard(
    date_et: str, group: str | None = None, session: requests.Session | None = None
) -> list[EspnBaseballGame]:
    """date_et format: YYYY-MM-DD. ESPN keys the feed by US/Eastern date."""
    sess = session or requests.Session()
    params = {"dates": date_et.replace("-", ""), "limit": 500}
    if group:
        params["groups"] = group
    resp = sess.get(ESPN_BASE, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return parse_espn_scoreboard(resp.json())
