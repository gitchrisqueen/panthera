"""MLB Stats API client (statsapi.mlb.com — free, keyless).

Primary source for schedules, probable pitchers + ERA, finals, head-to-head
and recent form. NOTE: unreachable from some sandboxed dev environments;
tests run on recorded fixtures and live calls happen on GitHub runners.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import requests

from ..timeutil import parse_utc

BASE = "https://statsapi.mlb.com/api/v1"
TIMEOUT = 30


@dataclass
class PitcherInfo:
    pitcher_id: int | None = None
    name: str | None = None
    era: float | None = None


@dataclass
class GameInfo:
    game_pk: int
    game_date_et: str
    game_type: str
    status: str  # abstractGameState: Preview | Live | Final
    detailed_state: str
    start_utc: datetime
    doubleheader: str  # N, Y (traditional), S (split)
    game_number: int
    home_team_id: int
    home_team: str
    away_team_id: int
    away_team: str
    home_score: int | None = None
    away_score: int | None = None
    home_pitcher: PitcherInfo | None = None
    away_pitcher: PitcherInfo | None = None


def _pitcher_from_probable(side: dict) -> PitcherInfo | None:
    prob = side.get("probablePitcher")
    if not prob:
        return None
    era = None
    # The person(stats(type=season)) hydrate attaches season splits to the
    # probablePitcher object itself.
    for grp in prob.get("stats", []):
        for split in grp.get("splits", []):
            stat = split.get("stat", {})
            if "era" in stat:
                try:
                    era = float(stat["era"])
                except (TypeError, ValueError):
                    era = None
    return PitcherInfo(pitcher_id=prob.get("id"), name=prob.get("fullName"), era=era)


def parse_schedule(payload: dict) -> list[GameInfo]:
    games: list[GameInfo] = []
    for day in payload.get("dates", []):
        for g in day.get("games", []):
            home = g["teams"]["home"]
            away = g["teams"]["away"]
            start_utc = parse_utc(g["gameDate"])
            games.append(
                GameInfo(
                    game_pk=g["gamePk"],
                    game_date_et=day["date"],
                    game_type=g.get("gameType", ""),
                    status=g.get("status", {}).get("abstractGameState", ""),
                    detailed_state=g.get("status", {}).get("detailedState", ""),
                    start_utc=start_utc,
                    doubleheader=g.get("doubleHeader", "N"),
                    game_number=g.get("gameNumber", 1),
                    home_team_id=home["team"]["id"],
                    home_team=home["team"]["name"],
                    away_team_id=away["team"]["id"],
                    away_team=away["team"]["name"],
                    home_score=home.get("score"),
                    away_score=away.get("score"),
                    home_pitcher=_pitcher_from_probable(home),
                    away_pitcher=_pitcher_from_probable(away),
                )
            )
    return games


def get_schedule(date_et: str | date, session: requests.Session | None = None) -> list[GameInfo]:
    sess = session or requests.Session()
    resp = sess.get(
        f"{BASE}/schedule",
        params={
            "sportId": 1,
            "date": str(date_et),
            # probablePitcher(stats(...)) is silently ignored by the live API
            # (probe evidence: actions run 31966193151 — only fullName/id/link
            # come back). The person(...) form returns the full person object
            # with season pitching splits attached to probablePitcher.
            "hydrate": "probablePitcher,person(stats(type=season)),linescore,team",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_schedule(resp.json())


def get_schedule_range(
    start_et: str, end_et: str, session: requests.Session | None = None
) -> list[GameInfo]:
    sess = session or requests.Session()
    resp = sess.get(
        f"{BASE}/schedule",
        params={"sportId": 1, "startDate": start_et, "endDate": end_et},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_schedule(resp.json())


def season_meetings(
    team_a_id: int, team_b_id: int, season: int, before: date, session=None
) -> int:
    """Number of regular-season meetings between two teams before `before`.

    Used for the first-meeting rule (R6)."""
    sess = session or requests.Session()
    resp = sess.get(
        f"{BASE}/schedule",
        params={
            "sportId": 1,
            "teamId": team_a_id,
            "startDate": f"{season}-01-01",
            "endDate": str(before),
            "gameType": "R",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    count = 0
    for game in parse_schedule(resp.json()):
        opponents = {game.home_team_id, game.away_team_id}
        if opponents == {team_a_id, team_b_id} and game.status == "Final":
            count += 1
    return count
