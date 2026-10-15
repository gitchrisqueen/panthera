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


# `detailedState` heads that mean this game will never produce a score, mapped
# to the spelling `grading._result_for_pick` voids on. MLB writes both
# "Cancelled" and "Canceled", and appends a reason ("Suspended: Rain"), so
# match on the head and normalise.
_CALLED_OFF = {
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
    "postponed": "Postponed",
    "suspended": "Suspended",
}
# The stored-status vocabulary beyond abstractGameState, defined once here and
# read by `pipeline._needs_final` and `grading._result_for_pick` so the writer
# and the settler cannot drift (the repo's "exactly one reader" convention).
#
# CALLED_OFF_STATUSES: a normal refresh will not produce a score for these, so
# a finals fallback must not try to reopen them.
# VOID_STATUSES: of those, the ones that mean NO score will EVER exist, so a
# pick on them refunds the stake.
#
# "Suspended" is deliberately in the first and NOT the second: MLB resumes a
# suspended game under the same gamePk, so the pick must stay pending until the
# real final arrives. Voiding it would be irreversible — `store.settle_picks`
# only rewrites rows still `pending`, so the true win/loss could never land and
# the strategy's realised P/L would be silently wrong. College baseball already
# makes this call the same way (tests/test_ncaabase.py: `pick("Suspended") is
# None  # resumed later, not voided`).
CALLED_OFF_STATUSES = ("Cancelled", "Postponed", "Suspended")
VOID_STATUSES = ("Cancelled", "Postponed")


def stored_status(game: GameInfo) -> str:
    """The status to persist for a game — `detailedState` when the game was
    called off, otherwise `abstractGameState`.

    `abstractGameState` is only ever Preview | Live | Final, so a rain-out
    comes back as "Final" with no linescore behind it. Stored that way a pick
    on it can neither settle (grading settles from the score, and there is
    none) nor void (grading's void branch tests for
    Postponed/Suspended/Cancelled, which this pipeline never wrote), and the
    derived winner/run_diff/total_runs columns get filled from `score or 0`
    with a fabricated 0-0 result. Game 823490, cancelled for rain on
    2026-09-27, left three picks pending for 18 days exactly this way.
    `detailedState` is the only field that says a game was called off.

    "Completed Early: Rain" and "Delayed Start: Rain" are deliberately NOT in
    the map: the first is an official shortened game that HAS a score, the
    second is still live.
    """
    head = game.detailed_state.split(":", 1)[0].strip().lower()
    return _CALLED_OFF.get(head, game.status)


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
