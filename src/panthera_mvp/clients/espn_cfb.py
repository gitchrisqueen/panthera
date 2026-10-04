"""ESPN unofficial college-football scoreboard — NCAAF schedule and finals.

Keyless. The NCAAF analogue of `mlb.py`: one call per ET date returns every
game's ESPN event id (our NCAAF game key), kickoff, teams, AP rank, venue
(indoor flag for the weather angle), neutral-site flag and, once played, the
final score. `groups=80` limits the feed to FBS; without it ESPN returns only
the featured games.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..timeutil import game_date_et, parse_utc, utc_iso

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
TIMEOUT = 30
FBS_GROUP = "80"
UNRANKED = 99  # ESPN's curatedRank.current for unranked teams


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


def parse_scoreboard(payload: dict) -> list[CfbGame]:
    games: list[CfbGame] = []
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
            start_dt = parse_utc(start)
            status = _status(comp)
            final = status == "Final"
            venue = comp.get("venue") or {}
            games.append(
                CfbGame(
                    event_id=str(event.get("id") or comp.get("id")),
                    start_time_utc=utc_iso(start_dt),
                    game_date_et=str(game_date_et(start_dt)),
                    home_team=home.get("team", {}).get("displayName", ""),
                    away_team=away.get("team", {}).get("displayName", ""),
                    home_rank=_rank(home),
                    away_rank=_rank(away),
                    neutral_site=bool(comp.get("neutralSite", False)),
                    conference_game=bool(comp.get("conferenceCompetition", False)),
                    venue=venue.get("fullName", ""),
                    indoor=venue.get("indoor"),
                    status=status,
                    home_score=_score(home) if final else None,
                    away_score=_score(away) if final else None,
                )
            )
    return games


def get_scoreboard(
    date_et: str, group: str = FBS_GROUP, session: requests.Session | None = None
) -> list[CfbGame]:
    """date_et format: YYYY-MM-DD. ESPN keys the feed by US/Eastern date."""
    sess = session or requests.Session()
    resp = sess.get(
        BASE,
        params={"dates": date_et.replace("-", ""), "groups": group, "limit": 300},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_scoreboard(resp.json())
