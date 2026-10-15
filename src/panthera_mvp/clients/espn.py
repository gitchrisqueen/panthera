"""ESPN unofficial scoreboard client — backup finals source for grading.

Keyless. Used only when the MLB Stats API is missing/errored for a final.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..timeutil import parse_utc, utc_iso

BASE = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
TIMEOUT = 30


@dataclass
class EspnGame:
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    completed: bool
    #: Scheduled first pitch, UTC ISO-8601 ("" when the payload omits it).
    #:
    #: Carried so the grading fallback can tell the two games of a split
    #: doubleheader apart: (game_date_et, home_team, away_team) is not unique
    #: on such a date, and without a start time an ESPN event cannot be keyed
    #: onto one stored row. The field is last and defaults to "" so the
    #: positional construction in the existing tests keeps working.
    start_time_utc: str = ""


def parse_scoreboard(payload: dict) -> list[EspnGame]:
    games: list[EspnGame] = []
    for event in payload.get("events", []):
        for comp in event.get("competitions", []):
            home = away = None
            for c in comp.get("competitors", []):
                team_name = c.get("team", {}).get("displayName", "")
                score = c.get("score")
                entry = (team_name, int(score) if score not in (None, "") else None)
                if c.get("homeAway") == "home":
                    home = entry
                else:
                    away = entry
            # `competitions[].date` is the per-game start; `events[].date`
            # repeats it for a single-game event. A doubleheader has one event
            # per game, so either reads the right one — but prefer the inner
            # value, as college baseball's parser does.
            start = comp.get("date") or event.get("date")
            if home and away:
                games.append(
                    EspnGame(
                        home_team=home[0],
                        away_team=away[0],
                        home_score=home[1],
                        away_score=away[1],
                        completed=comp.get("status", {})
                        .get("type", {})
                        .get("completed", False),
                        # A date-less event is still returned, not dropped: on
                        # a date whose matchup is unique the fallback never
                        # needs the time, and dropping the event there would
                        # trade one unfillable hole for another.
                        start_time_utc=utc_iso(parse_utc(start)) if start else "",
                    )
                )
    return games


def get_scoreboard(date_et: str, session: requests.Session | None = None) -> list[EspnGame]:
    """date_et format: YYYY-MM-DD (converted to ESPN's YYYYMMDD)."""
    sess = session or requests.Session()
    resp = sess.get(
        BASE, params={"dates": date_et.replace("-", "")}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    return parse_scoreboard(resp.json())
