"""ESPN unofficial college-football scoreboard — NCAAF schedule and finals.

Keyless. The NCAAF analogue of `mlb.py`: one call returns every game's ESPN
event id (our NCAAF game key), kickoff, teams, AP rank, venue (indoor flag
for the weather angle), neutral-site flag and, once played, the final score.

Two ways to key the call:
  date mode  `dates=YYYYMMDD` — one US/Eastern day (grading, daily refresh).
  week mode  `dates=YYYY&seasontype=2|3&week=N` — a whole CFB week (college
             football is scheduled by week; `dates=YYYY` selects the season).
Both send `groups=80&limit=300`: `groups=80` limits the feed to FBS, and
without it ESPN returns only the featured games (a short list — the likely
reason a bare `?week=5` call returned just 16 events).
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..timeutil import game_date_et, parse_utc, utc_iso

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
TIMEOUT = 30
FBS_GROUP = "80"
UNRANKED = 99  # ESPN's curatedRank.current for unranked teams
# ESPN seasontype ids, keyed by CFBD's seasonType names.
SEASON_TYPES = {"regular": 2, "postseason": 3}


@dataclass
class CfbGame:
    event_id: str
    start_time_utc: str
    game_date_et: str
    home_team: str
    away_team: str
    home_rank: int | None
    away_rank: int | None
    neutral_site: bool
    conference_game: bool
    venue: str
    indoor: bool | None
    status: str  # Scheduled | InProgress | Final | Postponed | Canceled
    home_score: int | None
    away_score: int | None
    season: int | None = None
    season_type: str | None = None  # regular | postseason
    week: int | None = None
    # School without mascot (ESPN team.location == CFBD school): the join key
    # for CFBD rows and the ncaa-api finals fallback.
    home_school: str = ""
    away_school: str = ""
    score_source: str = ""  # espn | cfbd | ncaa_api, once Final


_STATUS = {
    "STATUS_SCHEDULED": "Scheduled",
    "STATUS_IN_PROGRESS": "InProgress",
    "STATUS_HALFTIME": "InProgress",
    "STATUS_END_PERIOD": "InProgress",
    "STATUS_FINAL": "Final",
    "STATUS_FINAL_OT": "Final",
    "STATUS_POSTPONED": "Postponed",
    "STATUS_CANCELED": "Canceled",
    "STATUS_DELAYED": "Scheduled",
}
_SEASON_TYPE_NAMES = {v: k for k, v in SEASON_TYPES.items()}


def _rank(competitor: dict) -> int | None:
    val = (competitor.get("curatedRank") or {}).get("current")
    if val is None or int(val) >= UNRANKED:
        return None
    return int(val)


def _score(competitor: dict) -> int | None:
    score = competitor.get("score")
    return int(score) if score not in (None, "") else None


def _status(comp: dict) -> str:
    stype = (comp.get("status") or {}).get("type") or {}
    name = stype.get("name", "")
    if name in _STATUS:
        return _STATUS[name]
    if stype.get("completed"):
        return "Final"
    return "Scheduled"


def _int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def parse_scoreboard(payload: dict) -> list[CfbGame]:
    # Season/week sit on each event and on the payload; the event's wins.
    top_season = payload.get("season") or {}
    top_week = (payload.get("week") or {}).get("number")
    games: list[CfbGame] = []
    for event in payload.get("events", []):
        season = event.get("season") or top_season
        week = (event.get("week") or {}).get("number", top_week)
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
            start_dt = parse_utc(start)
            status = _status(comp)
            final = status == "Final"
            venue = comp.get("venue") or {}
            home_t, away_t = home.get("team", {}), away.get("team", {})
            games.append(
                CfbGame(
                    event_id=str(event.get("id") or comp.get("id")),
                    start_time_utc=utc_iso(start_dt),
                    game_date_et=str(game_date_et(start_dt)),
                    home_team=home_t.get("displayName", ""),
                    away_team=away_t.get("displayName", ""),
                    home_rank=_rank(home),
                    away_rank=_rank(away),
                    neutral_site=bool(comp.get("neutralSite", False)),
                    conference_game=bool(comp.get("conferenceCompetition", False)),
                    venue=venue.get("fullName", ""),
                    indoor=venue.get("indoor"),
                    status=status,
                    home_score=_score(home) if final else None,
                    away_score=_score(away) if final else None,
                    season=_int(season.get("year")),
                    season_type=_SEASON_TYPE_NAMES.get(_int(season.get("type"))),
                    week=_int(week),
                    home_school=home_t.get("location", ""),
                    away_school=away_t.get("location", ""),
                    score_source="espn" if final else "",
                )
            )
    return games


def scoreboard_params(
    date_et: str | None = None,
    season: int | None = None,
    week: int | None = None,
    season_type: str = "regular",
    group: str = FBS_GROUP,
) -> dict:
    """Query params for date mode (date_et) or week mode (season + week)."""
    if date_et:
        return {"dates": date_et.replace("-", ""), "groups": group, "limit": 300}
    if season is None or week is None:
        raise ValueError("week mode needs season and week")
    if season_type not in SEASON_TYPES:
        raise ValueError(f"season_type must be one of {sorted(SEASON_TYPES)}")
    return {
        "dates": str(season),
        "seasontype": SEASON_TYPES[season_type],
        "week": int(week),
        "groups": group,
        "limit": 300,
    }


def _fetch(params: dict, session: requests.Session | None) -> list[CfbGame]:
    sess = session or requests.Session()
    resp = sess.get(BASE, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return parse_scoreboard(resp.json())


def get_scoreboard(
    date_et: str, group: str = FBS_GROUP, session: requests.Session | None = None
) -> list[CfbGame]:
    """date_et format: YYYY-MM-DD. ESPN keys the feed by US/Eastern date."""
    return _fetch(scoreboard_params(date_et=date_et, group=group), session)


def get_week_scoreboard(
    season: int,
    week: int,
    season_type: str = "regular",
    group: str = FBS_GROUP,
    session: requests.Session | None = None,
) -> list[CfbGame]:
    """Every FBS game of one CFB week (season_type: regular | postseason)."""
    params = scoreboard_params(season=season, week=week, season_type=season_type, group=group)
    return _fetch(params, session)
