"""ncaa-api (ncaa-api.henrygd.me) — keyless NCAA.com scoreboard proxy.

The last link of the NCAAF finals chain (ESPN -> CFBD -> this): used only
when ESPN errors, and only to fill games still not Final. One call returns a
whole FBS week:

  GET /scoreboard/football/fbs/{YYYY}/{WW}/all-conf   (WW zero-padded; "P"
                                                       = postseason)

Rate limit: 5 requests/second per IP — we make one call per week.

NCAA.com ids and names share nothing with ESPN: `gameID` is NCAA's own id,
and teams carry `names.short` ("Ohio St.", "Miami (FL)"), `names.seo`
("ohio-st", "miami-fl") and `names.char6`. The pipeline matches on the ET
date plus both schools (see `ncaaf/sources.py`); anything ambiguous or
unknown is logged, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

from ..timeutil import UTC, game_date_et, utc_iso

BASE = "https://ncaa-api.henrygd.me"
TIMEOUT = 30


@dataclass
class NcaaGame:
    game_id: str
    start_time_utc: str | None
    game_date_et: str | None
    state: str  # pre | live | final (NCAA's gameState, lower-cased)
    home_short: str
    away_short: str
    home_seo: str
    away_seo: str
    home_score: int | None
    away_score: int | None


def _score(side: dict) -> int | None:
    try:
        return int(side.get("score"))
    except (TypeError, ValueError):
        return None


def parse_scoreboard(payload: dict) -> list[NcaaGame]:
    games: list[NcaaGame] = []
    for item in payload.get("games", []):
        g = item.get("game") or {}
        home, away = g.get("home") or {}, g.get("away") or {}
        hn, an = home.get("names") or {}, away.get("names") or {}
        epoch = g.get("startTimeEpoch")
        start = (
            datetime.fromtimestamp(int(epoch), tz=UTC) if str(epoch or "").isdigit() else None
        )
        state = str(g.get("gameState", "")).lower()
        final = state == "final"
        games.append(
            NcaaGame(
                game_id=str(g.get("gameID", "")),
                start_time_utc=utc_iso(start) if start else None,
                game_date_et=str(game_date_et(start)) if start else None,
                state=state,
                home_short=hn.get("short", ""),
                away_short=an.get("short", ""),
                home_seo=hn.get("seo", ""),
                away_seo=an.get("seo", ""),
                home_score=_score(home) if final else None,
                away_score=_score(away) if final else None,
            )
        )
    return games


def scoreboard_path(season: int, week: int, season_type: str = "regular") -> str:
    wk = "P" if season_type == "postseason" else f"{int(week):02d}"
    return f"/scoreboard/football/fbs/{int(season)}/{wk}/all-conf"


def get_scoreboard(
    season: int,
    week: int,
    season_type: str = "regular",
    session: requests.Session | None = None,
) -> list[NcaaGame]:
    sess = session or requests.Session()
    resp = sess.get(BASE + scoreboard_path(season, week, season_type), timeout=TIMEOUT)
    resp.raise_for_status()
    return parse_scoreboard(resp.json())
