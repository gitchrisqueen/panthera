"""NCAAF CSV datastore: games (upsert), lines (append, dedupe), parlay
tickets + legs (append-once, settle in place).

A ticket is one paper bet: N legs, one stake, one combined price. Legs are
stored separately so each leg grades on its own game; the ticket settles
when every leg has a result (or as soon as any leg loses).
"""

from __future__ import annotations

import pandas as pd

from .. import paths

GAMES_COLUMNS = [
    "event_id", "game_date_et", "start_time_utc", "home_team", "away_team",
    "home_rank", "away_rank", "neutral_site", "conference_game", "venue",
    "indoor", "status", "home_score", "away_score",
]

LINES_KEY = ["game_date_et", "snapshot_label", "odds_event_id", "bookmaker", "market", "outcome"]

TICKETS_COLUMNS = [
    "ticket_id", "strategy_id", "game_date_et", "created_ts_utc", "n_legs",
    "price_american", "price_decimal", "stake", "rule_id", "rationale",
    "config_hash", "status", "settled_ts_utc", "settled_price_decimal", "profit",
]

LEGS_COLUMNS = [
    "ticket_id", "leg_no", "event_id", "matchup", "start_time_utc", "market",
    "selection", "line", "price_american", "price_decimal", "bookmaker",
    "status", "final_score",
]


def _load(path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype={"event_id": str, "ticket_id": str}).reindex(
            columns=columns
        )
    return pd.DataFrame(columns=columns)


def _write(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def load_games() -> pd.DataFrame:
    return _load(paths.ncaaf_games_csv(), GAMES_COLUMNS)


def upsert_games(df: pd.DataFrame) -> None:
    if df.empty:
        return
    df = df.reindex(columns=GAMES_COLUMNS).astype({"event_id": str})
    existing = load_games()
    if not existing.empty:
        existing = existing[~existing["event_id"].isin(df["event_id"])]
        df = pd.concat([existing, df], ignore_index=True)
    _write(df.sort_values(["game_date_et", "start_time_utc", "event_id"]), paths.ncaaf_games_csv())


def load_lines() -> pd.DataFrame:
    path = paths.ncaaf_lines_csv()
    return pd.read_csv(path, dtype={"event_id": str}) if path.exists() else pd.DataFrame()


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
    _write(combined, paths.ncaaf_lines_csv())
    return len(df)


def load_tickets() -> pd.DataFrame:
    return _load(paths.ncaaf_tickets_csv(), TICKETS_COLUMNS)


def load_legs() -> pd.DataFrame:
    return _load(paths.ncaaf_ticket_legs_csv(), LEGS_COLUMNS)


def append_ticket(ticket: dict, legs: list[dict]) -> bool:
    """Append one ticket and its legs; a ticket_id already present is a
    no-op (tickets are immutable once created)."""
    tickets = load_tickets()
    if str(ticket["ticket_id"]) in set(tickets["ticket_id"].astype(str)):
        return False
    t = pd.DataFrame([ticket]).reindex(columns=TICKETS_COLUMNS)
    t["status"] = t["status"].fillna("pending")
    ls = pd.DataFrame(legs).reindex(columns=LEGS_COLUMNS)
    ls["status"] = ls["status"].fillna("pending")
    _write(t if tickets.empty else pd.concat([tickets, t], ignore_index=True),
           paths.ncaaf_tickets_csv())
    old_legs = load_legs()
    _write(ls if old_legs.empty else pd.concat([old_legs, ls], ignore_index=True),
           paths.ncaaf_ticket_legs_csv())
    return True


def save_tickets(df: pd.DataFrame) -> None:
    _write(df.reindex(columns=TICKETS_COLUMNS), paths.ncaaf_tickets_csv())


def save_legs(df: pd.DataFrame) -> None:
    _write(df.reindex(columns=LEGS_COLUMNS), paths.ncaaf_ticket_legs_csv())
