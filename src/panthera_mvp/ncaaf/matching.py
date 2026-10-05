"""Match Odds API NCAAF events to ESPN event ids.

There are ~130 FBS teams, so no hand-kept ID table like MLB's: both feeds
use "School Mascot" display names, compared after `normalize_name`, with a
config alias map for the stragglers. Neutral-site games may list home/away
differently between feeds, so a swapped pair also matches. That is safe
because lines and legs name their side by team, never by home/away; grading
resolves the team against the ESPN result by the same normalized name.
Unmatched events are returned and logged — never guessed.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import timedelta

from ..clients.espn_cfb import CfbGame
from ..timeutil import parse_utc


def normalize_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[.'’`]", "", s)
    s = re.sub(r"[^a-z0-9()]+", " ", s)
    return " ".join(s.split())


def match_events(
    odds_events: list[dict],
    games: list[CfbGame],
    aliases: dict[str, str] | None = None,
    window_hours: float = 4,
) -> tuple[dict[str, str], list[str]]:
    """Return ({odds_event_id: espn_event_id}, [unmatched descriptions])."""
    alias = {normalize_name(k): normalize_name(v) for k, v in (aliases or {}).items()}
    window = timedelta(hours=window_hours)

    def key(name: str) -> str:
        n = normalize_name(name)
        return alias.get(n, n)

    matched: dict[str, str] = {}
    unmatched: list[str] = []
    used: set[str] = set()
    for ev in odds_events:
        home, away = key(ev.get("home_team", "")), key(ev.get("away_team", ""))
        if not ev.get("commence_time") or not home or not away:
            unmatched.append(f"{ev.get('id')}: missing teams/time")
            continue
        commence = parse_utc(ev["commence_time"])
        best = None
        for g in games:
            if g.event_id in used:
                continue
            gh, ga = key(g.home_team), key(g.away_team)
            if {gh, ga} != {home, away}:
                continue
            gap = abs(parse_utc(g.start_time_utc) - commence)
            if gap <= window and (best is None or gap < best[0]):
                best = (gap, g)
        if best is None:
            unmatched.append(
                f"{ev.get('id')}: no ESPN FBS game for "
                f"{ev.get('away_team')} @ {ev.get('home_team')} at {ev['commence_time']}"
            )
            continue
        g = best[1]
        matched[ev["id"]] = g.event_id
        used.add(g.event_id)
    return matched, unmatched
