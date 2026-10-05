"""Match outside feeds (ESPN finals, Odds API events) to NCAA games.

~300 D1 programs and no shared id, so names do the work. NCAA gives a bare
school name (`names.short` "Florida St.", `names.seo` "florida-st"); ESPN
and the Odds API usually append the mascot ("Florida State Seminoles"). A
team *fits* when its normalized outside name equals one of the NCAA keys or
extends one by whole words ("lsu tigers" fits "lsu"), after a config alias
map for the true collisions ("Miami" -> "Miami (FL)"). Normalization is
ncaaf's `normalize_name` plus "st" -> "state", applied to both sides.

A candidate must fit both teams (either orientation — neutral sites may
list home/away differently; scores and sides are then mapped by team) and
start within `window_hours`. Doubleheaders are the norm in college
baseball: the nearest start wins, and when the runner-up is within
`ambiguity_minutes` of it (e.g. a "game 2, time TBA" listing) the match is
skipped and logged — never guessed.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..ncaaf.matching import normalize_name
from ..timeutil import parse_utc


def canon(name: str) -> str:
    return " ".join("state" if t == "st" else t for t in normalize_name(name).split())


def alias_map(aliases: dict[str, str] | None) -> dict[str, str]:
    return {canon(k): canon(v) for k, v in (aliases or {}).items()}


def team_keys(short: str, seo: str = "") -> set[str]:
    """NCAA-side keys for one team."""
    seo = seo if isinstance(seo, str) else ""  # NaN from a CSV round trip
    return {k for k in (canon(short), canon(seo.replace("-", " "))) if k}


def fits(outside_names: Iterable[str], keys: set[str], alias: dict[str, str]) -> bool:
    for name in outside_names:
        o = canon(name)
        o = alias.get(o, o)
        if any(o == k or o.startswith(k + " ") for k in keys):
            return True
    return False


def orientation(
    home_names: Iterable[str], away_names: Iterable[str], game: dict, alias: dict[str, str]
) -> bool | None:
    """None = not this game; False = same home/away; True = swapped."""
    home_names, away_names = list(home_names), list(away_names)
    gh = team_keys(game["home_team"], game.get("home_seo", ""))
    ga = team_keys(game["away_team"], game.get("away_seo", ""))
    if fits(home_names, gh, alias) and fits(away_names, ga, alias):
        return False
    if fits(home_names, ga, alias) and fits(away_names, gh, alias):
        return True
    return None


def _nearest(
    cands: list[tuple[float, str, bool]], window_hours: float, ambiguity_minutes: float
) -> tuple[str, bool] | str:
    """cands = [(gap_seconds, id, swapped)]. Returns (id, swapped) or a reason."""
    cands = sorted(c for c in cands if c[0] <= window_hours * 3600)
    if not cands:
        return "no game within the start-time window"
    if len(cands) > 1 and cands[1][0] - cands[0][0] < ambiguity_minutes * 60:
        return f"ambiguous between {cands[0][1]} and {cands[1][1]} (doubleheader?)"
    return cands[0][1], cands[0][2]


def match_odds_events(
    events: list[dict],
    games: list[dict],
    aliases: dict[str, str] | None = None,
    window_hours: float = 4,
    ambiguity_minutes: float = 60,
) -> tuple[dict[str, str], list[str]]:
    """Return ({odds_event_id: ncaa game_id}, [unmatched descriptions])."""
    alias = alias_map(aliases)
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    used: set[str] = set()
    for ev in events:
        desc = f"{ev.get('id')}: {ev.get('away_team')} @ {ev.get('home_team')}"
        if not (ev.get("commence_time") and ev.get("home_team") and ev.get("away_team")):
            unmatched.append(f"{desc}: missing teams/time")
            continue
        commence = parse_utc(ev["commence_time"])
        cands = []
        for g in games:
            if str(g["game_id"]) in used:
                continue
            swapped = orientation([ev["home_team"]], [ev["away_team"]], g, alias)
            if swapped is not None:
                gap = abs((parse_utc(g["start_time_utc"]) - commence).total_seconds())
                cands.append((gap, str(g["game_id"]), swapped))
        pick = _nearest(cands, window_hours, ambiguity_minutes)
        if isinstance(pick, str):
            unmatched.append(f"{desc} at {ev['commence_time']}: {pick}")
            continue
        matched[ev["id"]] = pick[0]
        used.add(pick[0])
    return matched, unmatched


def match_espn(
    games: list[dict],
    espn_games: list,
    aliases: dict[str, str] | None = None,
    window_hours: float = 4,
    ambiguity_minutes: float = 60,
) -> tuple[dict[str, tuple[object, bool]], list[str]]:
    """Return ({ncaa game_id: (EspnBaseballGame, swapped)}, [unmatched])."""
    alias = alias_map(aliases)
    matched: dict[str, tuple[object, bool]] = {}
    unmatched: list[str] = []
    used: set[str] = set()
    by_id = {e.event_id: e for e in espn_games}
    for g in games:
        start = parse_utc(g["start_time_utc"])
        cands = []
        for e in espn_games:
            if e.event_id in used:
                continue
            swapped = orientation(e.home_names, e.away_names, g, alias)
            if swapped is not None:
                gap = abs((parse_utc(e.start_time_utc) - start).total_seconds())
                cands.append((gap, e.event_id, swapped))
        pick = _nearest(cands, window_hours, ambiguity_minutes)
        if isinstance(pick, str):
            unmatched.append(f"{g['game_id']}: {g['away_team']} @ {g['home_team']}: {pick}")
            continue
        matched[str(g["game_id"])] = (by_id[pick[0]], pick[1])
        used.add(pick[0])
    return matched, unmatched


def side(selection: str, game: dict, aliases: dict[str, str] | None = None) -> str:
    """Resolve a pick's team selection to "home" or "away": an exact key
    match first, else the side whose key is the longest word prefix."""
    alias = alias_map(aliases)
    keys = {
        "home": team_keys(game["home_team"], game.get("home_seo", "")),
        "away": team_keys(game["away_team"], game.get("away_seo", "")),
    }
    s = canon(selection)
    s = alias.get(s, s)
    exact = [k for k, v in keys.items() if s in v]
    if len(exact) == 1:
        return exact[0]
    # Word-prefix fits, scored by the longest key matched ("Texas A&M Aggies"
    # fits both "texas" and "texas a and m"; the longer key names the team).
    best = {
        k: max((len(key) for key in v if s.startswith(key + " ")), default=0)
        for k, v in keys.items()
    }
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][1] and ranked[0][1] > ranked[1][1]:
        return ranked[0][0]
    raise ValueError(
        f"selection {selection!r} does not name exactly one of "
        f"{game['away_team']!r} / {game['home_team']!r}"
    )
