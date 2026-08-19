"""Historical MLB schedules — start times for the backtest (keyless).

The sportsbookreviewsonline archives carry no game start times, which is why
the backtest fabricated a 19:05 ET start for every game and skipped hybrid
Wednesdays entirely. The strategy's slot algorithm (strategy/slots.py) is
driven *entirely* by the shape of a day's start times, so without them the
historical replay cannot test the rule that decides most picks.

The MLB Stats API serves a whole season in one keyless call, so the whole
2014-2021 archive costs seven requests. Results are cached to
data/historical/schedules/<season>.csv and committed — the fetch is meant to
run once, not on every backtest.

NOTE: unreachable from some sandboxed dev environments (see CLAUDE.md); the
cache is what tests and offline runs read.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests

from .. import paths
from ..timeutil import parse_utc, to_et

BASE = "https://statsapi.mlb.com/api/v1"
TIMEOUT = 120

#: Season bounds are deliberately generous — the API clips to the real
#: schedule, and 2020's shortened season starts far later than the others.
SEASON_START_MMDD = "03-01"
SEASON_END_MMDD = "11-15"

#: sportsbookreviewsonline team abbreviations -> MLB Stats API team ids.
#: Several drift across seasons (LOS/LAD, KAN/KC), so both spellings are here.
SBRO_TEAM_IDS: dict[str, int] = {
    "ARI": 109,
    "ATL": 144,
    "BAL": 110,
    "BOS": 111,
    "CUB": 112,
    "CHC": 112,
    "CWS": 145,
    "CHW": 145,
    "CIN": 113,
    "CLE": 114,
    "COL": 115,
    "DET": 116,
    "HOU": 117,
    "KAN": 118,
    "KC": 118,
    "LAA": 108,
    "ANA": 108,
    "LAD": 119,
    "LOS": 119,
    "MIA": 146,
    "FLA": 146,
    "MIL": 158,
    "MIN": 142,
    "NYM": 121,
    "NYY": 147,
    "OAK": 133,
    "PHI": 143,
    "PIT": 134,
    "SDG": 135,
    "SD": 135,
    "SEA": 136,
    "SFO": 137,
    "SF": 137,
    "STL": 138,
    "TAM": 139,
    "TB": 139,
    "TEX": 140,
    "TOR": 141,
    "WAS": 120,
}

SCHEDULE_COLUMNS = [
    "season",
    "game_date_et",
    "game_pk",
    "start_utc",
    "game_type",
    "doubleheader",
    "game_number",
    "home_team_id",
    "away_team_id",
    "home_team",
    "away_team",
]


def sbro_team_id(abbrev: str) -> int | None:
    return SBRO_TEAM_IDS.get(str(abbrev).strip().upper())


def schedule_csv(season: int):
    return paths.historical_schedules_dir() / f"{season}.csv"


def fetch_season_schedule(season: int, game_types: tuple[str, ...] = ("R",)):
    """One request per season. Returns the SCHEDULE_COLUMNS frame."""
    resp = requests.get(
        f"{BASE}/schedule",
        params={
            "sportId": 1,
            "gameType": ",".join(game_types),
            "startDate": f"{season}-{SEASON_START_MMDD}",
            "endDate": f"{season}-{SEASON_END_MMDD}",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    rows = []
    for day in resp.json().get("dates", []):
        for g in day.get("games", []):
            start: datetime = parse_utc(g["gameDate"])
            teams = g.get("teams", {})
            home, away = teams.get("home", {}), teams.get("away", {})
            rows.append(
                {
                    "season": season,
                    # officialDate is the scheduling date MLB itself keys on;
                    # it survives suspensions and post-midnight finishes that
                    # a naive UTC->ET conversion would move to the wrong day.
                    "game_date_et": g.get("officialDate")
                    or str(to_et(start).date()),
                    "game_pk": g["gamePk"],
                    "start_utc": start,
                    "game_type": g.get("gameType"),
                    "doubleheader": g.get("doubleHeader", "N"),
                    "game_number": g.get("gameNumber", 1),
                    "home_team_id": home.get("team", {}).get("id"),
                    "away_team_id": away.get("team", {}).get("id"),
                    "home_team": home.get("team", {}).get("name"),
                    "away_team": away.get("team", {}).get("name"),
                }
            )
    return pd.DataFrame(rows, columns=SCHEDULE_COLUMNS)


def load_season_schedule(season: int, refresh: bool = False):
    """Cached read. Fetches (and writes the cache) only when missing."""
    path = schedule_csv(season)
    if path.exists() and not refresh:
        df = pd.read_csv(path)
        df["start_utc"] = pd.to_datetime(df["start_utc"], utc=True)
        return df
    df = fetch_season_schedule(season)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def load_schedules(seasons, refresh: bool = False):
    frames = [load_season_schedule(int(s), refresh=refresh) for s in seasons]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=SCHEDULE_COLUMNS
    )


def attach_start_times(hist: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    """Add `start_utc` / `game_pk` to normalized archive rows.

    Join key is (date, home id, away id). Doubleheaders produce two archive
    rows and two schedule rows for one key; they are paired in order, which is
    correct because the archives are ordered by rotation number and MLB
    numbers doubleheader games in playing order. Rows with no schedule match
    keep a null start_utc and are reported by the caller, never guessed.
    """
    hist = hist.copy()
    hist["home_team_id"] = hist["home_team"].map(sbro_team_id)
    hist["away_team_id"] = hist["vis_team"].map(sbro_team_id)
    hist["_key"] = list(
        zip(hist["game_date"], hist["home_team_id"], hist["away_team_id"], strict=True)
    )
    hist["_seq"] = hist.groupby("_key").cumcount()

    sched = schedules.copy()
    sched = sched.sort_values(["game_date_et", "game_number", "start_utc"])
    sched["_key"] = list(
        zip(
            sched["game_date_et"],
            sched["home_team_id"],
            sched["away_team_id"],
            strict=True,
        )
    )
    sched["_seq"] = sched.groupby("_key").cumcount()

    merged = hist.merge(
        sched[["_key", "_seq", "game_pk", "start_utc", "doubleheader", "game_number"]],
        on=["_key", "_seq"],
        how="left",
    )
    return merged.drop(columns=["_key", "_seq"])
