"""Match Odds API events to MLB Stats API games (gamePk).

Algorithm: normalize both sides' team names to MLB team IDs via the alias
table, candidate = same (home, away) pair with commence time within a window
of the MLB start time (which also disambiguates doubleheaders). Unmatched
events are returned separately and logged — never guessed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .clients.mlb import GameInfo
from .timeutil import parse_utc

# MLB Stats API team IDs keyed by every name variant we expect from either API.
TEAM_IDS: dict[str, int] = {
    "arizona diamondbacks": 109,
    "atlanta braves": 144,
    "baltimore orioles": 110,
    "boston red sox": 111,
    "chicago cubs": 112,
    "chicago white sox": 145,
    "cincinnati reds": 113,
    "cleveland guardians": 114,
    "cleveland indians": 114,
    "colorado rockies": 115,
    "detroit tigers": 116,
    "houston astros": 117,
    "kansas city royals": 118,
    "los angeles angels": 108,
    "la angels": 108,
    "los angeles dodgers": 119,
    "la dodgers": 119,
    "miami marlins": 146,
    "milwaukee brewers": 158,
    "minnesota twins": 142,
    "new york mets": 121,
    "new york yankees": 147,
    "athletics": 133,
    "oakland athletics": 133,
    "las vegas athletics": 133,
    "philadelphia phillies": 143,
    "pittsburgh pirates": 134,
    "san diego padres": 135,
    "san francisco giants": 137,
    "seattle mariners": 136,
    "st. louis cardinals": 138,
    "st louis cardinals": 138,
    "tampa bay rays": 139,
    "texas rangers": 140,
    "toronto blue jays": 141,
    "washington nationals": 120,
}

MATCH_WINDOW = timedelta(hours=3)


def team_id(name: str) -> int | None:
    return TEAM_IDS.get(name.strip().lower())


def nearest_start(
    cands: list[tuple[float, str, Any]],
    window_hours: float,
    ambiguity_minutes: float,
) -> tuple[str, Any] | str:
    """Pick the candidate whose start time is nearest, or say why none is.

    `cands` is `[(gap_seconds, key, payload)]`, where `key` names the
    candidate in a log line and `payload` is whatever the caller needs back.
    Returns `(key, payload)`, or a one-line reason suitable for a run note.

    Two rules, in this order:

    1. A candidate further than `window_hours` from the event is not that
       event at all, and is dropped before anything is compared.
    2. **Ambiguity is never resolved by picking one.** When the two nearest
       gaps differ by less than `ambiguity_minutes`, the event cannot be keyed
       onto a single candidate — the "game 2, time TBA" shape — and a coin
       flip there writes one game's result onto the other. The caller gets a
       reason and reports it; unmatched is always better than guessed.

    Shared by MLB's ESPN finals fallback (`pipeline._match_doubleheader`) and
    college baseball's odds/ESPN matchers (`ncaabase.matching`), which had the
    only implementation until MLB needed the same rule.
    """
    cands = sorted(
        (c for c in cands if c[0] <= window_hours * 3600), key=lambda c: (c[0], c[1])
    )
    if not cands:
        return "no game within the start-time window"
    if len(cands) > 1 and cands[1][0] - cands[0][0] < ambiguity_minutes * 60:
        return f"ambiguous between {cands[0][1]} and {cands[1][1]} (doubleheader?)"
    return cands[0][1], cands[0][2]


def match_events(
    odds_events: list[dict], mlb_games: list[GameInfo]
) -> tuple[dict[str, int], list[str]]:
    """Return ({odds_event_id: game_pk}, [unmatched_event_descriptions])."""
    matched: dict[str, int] = {}
    unmatched: list[str] = []
    used_pks: set[int] = set()

    for ev in odds_events:
        home_id = team_id(ev.get("home_team", ""))
        away_id = team_id(ev.get("away_team", ""))
        commence: datetime | None = None
        if ev.get("commence_time"):
            commence = parse_utc(ev["commence_time"])
        if home_id is None or away_id is None or commence is None:
            unmatched.append(
                f"{ev.get('id')}: unknown teams/time "
                f"({ev.get('away_team')} @ {ev.get('home_team')})"
            )
            continue

        candidates = [
            g
            for g in mlb_games
            if g.home_team_id == home_id
            and g.away_team_id == away_id
            and g.game_pk not in used_pks
            and abs(g.start_utc - commence) <= MATCH_WINDOW
        ]
        if not candidates:
            unmatched.append(
                f"{ev.get('id')}: no MLB game for "
                f"{ev.get('away_team')} @ {ev.get('home_team')} at {commence}"
            )
            continue
        # Doubleheaders: pick the game whose start time is nearest.
        best = min(candidates, key=lambda g: abs(g.start_utc - commence))
        matched[ev["id"]] = best.game_pk
        used_pks.add(best.game_pk)

    return matched, unmatched
