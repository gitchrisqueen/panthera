"""Flat-file datastore: CSVs committed to git, idempotent appends/upserts.

Dedupe keys:
  lines.csv  -> (snapshot_ts_utc is unique per run, but re-runs are deduped on
                 snapshot_label + odds_event_id + bookmaker + market + outcome
                 + game_date_et)
  games.csv  -> game_pk (upsert)
  picks.csv  -> pick_id (append once; settle in place)
"""

from __future__ import annotations

import pandas as pd

from . import paths

LINES_KEY = [
    "game_date_et",
    "snapshot_label",
    "odds_event_id",
    "bookmaker",
    "market",
    "outcome",
]

PICKS_COLUMNS = [
    "pick_id",
    "created_ts_utc",
    "game_date_et",
    "game_pk",
    "odds_event_id",
    "matchup",
    "start_time_et",
    "day_type",
    "slot_type",
    "rule_id",
    "market",
    "selection",
    "line",
    "price_american",
    "price_decimal",
    "stake",
    "open_price",
    "latest_price",
    "movement_cents",
    "rationale",
    "config_hash",
    "status",
    "settled_ts_utc",
    "final_score",
    "profit",
]

GAMES_COLUMNS = [
    "game_pk",
    "game_date_et",
    "day_of_week_et",
    "game_type",
    "doubleheader",
    "game_number",
    "start_time_utc",
    "home_team_id",
    "home_team",
    "away_team_id",
    "away_team",
    "status",
    "home_score",
    "away_score",
    "winner",
    "run_diff",
    "total_runs",
    "home_pitcher_era",
    "away_pitcher_era",
    "score_source",
]


RUN_LOG_COLUMNS = ["ts_utc", "game_date_et", "run_label", "kind", "note"]


def _load(path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns or [])


def append_run_note(game_date_et: str, run_label: str, kind: str, note: str) -> None:
    """Persist an operational note (late run, degraded snapshot, engine error)
    so daily-report regeneration doesn't erase it."""
    from .timeutil import now_utc, utc_iso

    path = paths.data_dir() / "picks" / "run_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame(
        [
            {
                "ts_utc": utc_iso(now_utc()),
                "game_date_et": game_date_et,
                "run_label": run_label,
                "kind": kind,
                "note": note,
            }
        ]
    )
    existing = _load(path, RUN_LOG_COLUMNS)
    pd.concat([existing, row], ignore_index=True).to_csv(path, index=False)


def load_run_log() -> pd.DataFrame:
    return _load(paths.data_dir() / "picks" / "run_log.csv", RUN_LOG_COLUMNS)


def load_lines() -> pd.DataFrame:
    return _load(paths.lines_csv())


def load_games() -> pd.DataFrame:
    return _load(paths.games_csv(), GAMES_COLUMNS)


def load_picks() -> pd.DataFrame:
    return _load(paths.picks_csv(), PICKS_COLUMNS)


def append_lines(df: pd.DataFrame) -> int:
    """Append new line rows; skip rows whose dedupe key already exists."""
    if df.empty:
        return 0
    path = paths.lines_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load(path)
    if not existing.empty:
        existing_keys = set(map(tuple, existing[LINES_KEY].astype(str).values))
        mask = [
            tuple(map(str, row)) not in existing_keys
            for row in df[LINES_KEY].values
        ]
        df = df[mask]
        if df.empty:
            return 0
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.to_csv(path, index=False)
    return len(df)


def upsert_games(df: pd.DataFrame) -> None:
    if df.empty:
        return
    path = paths.games_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load(path, GAMES_COLUMNS)
    if not existing.empty:
        existing = existing[~existing["game_pk"].isin(df["game_pk"])]
    combined = pd.concat([existing, df], ignore_index=True)
    combined = combined.sort_values(["game_date_et", "game_pk"])
    combined.to_csv(path, index=False)


def append_picks(df: pd.DataFrame) -> int:
    """Append picks whose pick_id is not already present (idempotent)."""
    if df.empty:
        return 0
    path = paths.picks_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load(path, PICKS_COLUMNS)
    if not existing.empty:
        df = df[~df["pick_id"].isin(existing["pick_id"])]
        if df.empty:
            return 0
    combined = pd.concat([existing, df], ignore_index=True)
    combined.to_csv(path, index=False)
    return len(df)


def settle_picks(settlements: pd.DataFrame) -> int:
    """settlements columns: pick_id, status, settled_ts_utc, final_score, profit."""
    if settlements.empty:
        return 0
    path = paths.picks_csv()
    picks = _load(path, PICKS_COLUMNS)
    if picks.empty:
        return 0
    count = 0
    picks = picks.set_index("pick_id")
    # All-NaN columns load as float64; coerce to object so strings assign.
    for col in ("status", "settled_ts_utc", "final_score"):
        picks[col] = picks[col].astype(object)
    for row in settlements.itertuples(index=False):
        if row.pick_id in picks.index and picks.at[row.pick_id, "status"] == "pending":
            picks.at[row.pick_id, "status"] = row.status
            picks.at[row.pick_id, "settled_ts_utc"] = row.settled_ts_utc
            picks.at[row.pick_id, "final_score"] = row.final_score
            picks.at[row.pick_id, "profit"] = row.profit
            count += 1
    picks.reset_index().to_csv(path, index=False)
    return count
