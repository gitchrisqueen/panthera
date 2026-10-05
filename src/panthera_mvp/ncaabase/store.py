"""College-baseball CSV datastore: games (upsert, finals sticky), lines
(append, dedupe), single-bet picks (append-once, settle in place).

Finals are sticky: an incoming non-final row never replaces a stored Final
(an ESPN-settled game stays settled when ncaa-api still says "pre" on the
next refresh). An incoming Final always wins — ncaa-api is the official
source, so it overwrites an ESPN fallback score.
"""

from __future__ import annotations

import pandas as pd

from .. import paths

GAMES_COLUMNS = [
    "game_id", "game_date_et", "start_time_utc", "start_time_tba", "home_team",
    "away_team", "home_seo", "away_seo", "home_char6", "away_char6", "home_rank",
    "away_rank", "home_conference", "away_conference", "status", "current_period",
    "home_score", "away_score", "score_source", "espn_event_id",
]

LINES_KEY = ["game_date_et", "snapshot_label", "odds_event_id", "bookmaker", "market", "outcome"]

PICKS_COLUMNS = [
    "pick_id", "strategy_id", "created_ts_utc", "game_date_et", "game_id", "matchup",
    "start_time_utc", "market", "selection", "line", "price_american", "price_decimal",
    "stake", "rule_id", "rationale", "config_hash", "status", "settled_ts_utc",
    "final_score", "profit",
]

_IDS = {"game_id": str, "espn_event_id": str, "pick_id": str}
_GAME_INTS = ["home_rank", "away_rank", "home_score", "away_score"]


def _load(path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype=_IDS).reindex(columns=columns)
    return pd.DataFrame(columns=columns)


def _write(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def load_games() -> pd.DataFrame:
    return _load(paths.ncaabase_games_csv(), GAMES_COLUMNS)


def upsert_games(df: pd.DataFrame) -> None:
    if df.empty:
        return
    df = df.reindex(columns=GAMES_COLUMNS).astype({"game_id": str})
    existing = load_games()
    if not existing.empty:
        final_ids = set(existing.loc[existing["status"] == "Final", "game_id"])
        df = df[(df["status"] == "Final") | ~df["game_id"].isin(final_ids)]
        if df.empty:
            return
        existing = existing[~existing["game_id"].isin(df["game_id"])]
        df = pd.concat([existing, df], ignore_index=True)
    for col in _GAME_INTS:  # nullable ints: "4", not "4.0", beside blanks
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    _write(df.sort_values(["game_date_et", "start_time_utc", "game_id"]),
           paths.ncaabase_games_csv())


def load_lines() -> pd.DataFrame:
    path = paths.ncaabase_lines_csv()
    return pd.read_csv(path, dtype={"game_id": str}) if path.exists() else pd.DataFrame()


def append_lines(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    existing = load_lines()
    if not existing.empty:
        seen = set(map(tuple, existing[LINES_KEY].astype(str).values))
        df = df[[tuple(map(str, r)) not in seen for r in df[LINES_KEY].values]]
        if df.empty:
            return 0
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    _write(combined, paths.ncaabase_lines_csv())
    return len(df)


def load_picks() -> pd.DataFrame:
    return _load(paths.ncaabase_picks_csv(), PICKS_COLUMNS)


def append_pick(pick: dict) -> bool:
    """Append one pick; a pick_id already present is a no-op (picks are
    immutable once created)."""
    picks = load_picks()
    if str(pick["pick_id"]) in set(picks["pick_id"].astype(str)):
        return False
    p = pd.DataFrame([pick]).reindex(columns=PICKS_COLUMNS)
    p["status"] = p["status"].fillna("pending")
    _write(p if picks.empty else pd.concat([picks, p], ignore_index=True),
           paths.ncaabase_picks_csv())
    return True


def save_picks(df: pd.DataFrame) -> None:
    _write(df.reindex(columns=PICKS_COLUMNS), paths.ncaabase_picks_csv())
