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


def historical_raw_dir() -> Path:
    return data_dir() / "historical" / "raw"


def historical_normalized_csv() -> Path:
    return data_dir() / "historical" / "normalized" / "mlb_odds_all.csv"


def calibration_dir() -> Path:
    return data_dir() / "calibration"
