"""Repository-relative paths for the flat-file datastore.

The repo root is resolved from PANTHERA_ROOT if set (tests point it at a tmp
dir), otherwise from this file's location.
"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("PANTHERA_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    return repo_root() / "config"


def data_dir() -> Path:
    return repo_root() / "data"


def reports_dir() -> Path:
    return repo_root() / "reports"


def lines_csv() -> Path:
    return data_dir() / "odds" / "lines.csv"


def credit_log_csv() -> Path:
    return data_dir() / "odds" / "credit_log.csv"


def raw_odds_dir(date_et: str) -> Path:
    return data_dir() / "odds" / "raw" / date_et


def games_csv() -> Path:
    return data_dir() / "games" / "games.csv"


def picks_csv() -> Path:
    return data_dir() / "picks" / "picks.csv"


def shadow_picks_csv() -> Path:
    """Retroactive replay output (`panthera-mvp replay`) — same schema as
    picks.csv, but never pooled into any strategy's verdict. See
    pipeline.py's cmd_replay and report.py's write_shadow_report."""
    return data_dir() / "picks" / "shadow_picks.csv"


def historical_raw_dir() -> Path:
    return data_dir() / "historical" / "raw"


def historical_schedules_dir() -> Path:
    """Cached MLB Stats API season schedules — the backtest's start times."""
    return data_dir() / "historical" / "schedules"


def historical_normalized_csv() -> Path:
    return data_dir() / "historical" / "normalized" / "mlb_odds_all.csv"


def calibration_dir() -> Path:
    return data_dir() / "calibration"


def site_dir() -> Path:
    """Build output for the public GitHub Pages dashboard (`panthera-mvp
    pages`). Disposable and gitignored — regenerated fresh on every deploy
    from data/picks/picks.csv, never committed (unlike reports/, which is
    bot-owned committed markdown history)."""
    return repo_root() / "site"


# --- NCAAF (college football) -------------------------------------------
# A separate tree so the MLB ledger, reports and dashboard never see college
# rows. Same conventions: bot-owned, UTC timestamps, ET game dates.


def ncaaf_dir() -> Path:
    return data_dir() / "ncaaf"


def ncaaf_lines_csv() -> Path:
    return ncaaf_dir() / "odds" / "lines.csv"


def ncaaf_cfbd_lines_csv() -> Path:
    return ncaaf_dir() / "odds" / "cfbd_lines.csv"


def ncaaf_raw_odds_dir(date_et: str) -> Path:
    return ncaaf_dir() / "odds" / "raw" / date_et


def ncaaf_games_csv() -> Path:
    return ncaaf_dir() / "games" / "games.csv"


def ncaaf_tickets_csv() -> Path:
    return ncaaf_dir() / "tickets" / "tickets.csv"


def ncaaf_ticket_legs_csv() -> Path:
    return ncaaf_dir() / "tickets" / "ticket_legs.csv"


def ncaaf_cfbd_dir() -> Path:
    """Cached CollegeFootballData.com responses (games, lines, ratings,
    venues) — the historical backtest's inputs."""
    return ncaaf_dir() / "cfbd"
