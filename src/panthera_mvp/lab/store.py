"""CSV/JSON store for the lab under data/lab/<sport>/.

features.csv    append-once by (decision_date_et, event_id)
champion.json   the current champion: params, hash, effective_from, change
iterations.csv  one row per weekly run, including the no-change ones

Every write goes to a temp file and is renamed into place, so a killed run
never leaves a half-written ledger.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from .. import paths
from .features import FEATURE_COLUMNS, KEY

ITERATION_COLUMNS = [
    "run_ts", "week_label", "eval_version", "n_games", "n_graded", "champion_hash",
    "best_challenger_param", "old", "new", "train_n", "champion_roi", "challenger_roi",
    "paired_z", "z_required", "n_neighbours", "trials_total",
    "holdout_champion_roi", "holdout_challenger_roi", "decision", "reason",
]


def _atomic_write(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    _atomic_write(path, lambda tmp: df.to_csv(tmp, index=False))


def features_csv(sport: str) -> Path:
    return paths.lab_dir(sport) / "features.csv"


def champion_json(sport: str) -> Path:
    return paths.lab_dir(sport) / "champion.json"


def iterations_csv(sport: str) -> Path:
    return paths.lab_dir(sport) / "iterations.csv"


def load_features(sport: str) -> pd.DataFrame:
    p = features_csv(sport)
    if p.exists():
        return pd.read_csv(p, dtype={"event_id": str}).reindex(columns=FEATURE_COLUMNS)
    return pd.DataFrame(columns=FEATURE_COLUMNS)


def append_features(sport: str, rows: list[dict]) -> int:
    """Add rows whose (decision_date_et, event_id) is not stored yet. Returns the
    number added; a re-run of the same decision adds nothing."""
    if not rows:
        return 0
    new = pd.DataFrame(rows).reindex(columns=FEATURE_COLUMNS)
    new["event_id"] = new["event_id"].astype(str)
    new = new.drop_duplicates(KEY, keep="first")
    old = load_features(sport)
    if not old.empty:
        seen = set(zip(old["decision_date_et"], old["event_id"], strict=True))
        keep = [k not in seen for k in zip(new["decision_date_et"], new["event_id"], strict=True)]
        new = new[keep]
    if new.empty:
        return 0
    out = new if old.empty else pd.concat([old, new], ignore_index=True)
    _write_csv(out, features_csv(sport))
    return len(new)


def load_champion(sport: str) -> dict | None:
    p = champion_json(sport)
    if not p.exists():
        return None
    with open(p) as fh:
        return json.load(fh)


def save_champion(sport: str, champion: dict) -> None:
    def write(tmp: Path) -> None:
        with open(tmp, "w") as fh:
            json.dump(champion, fh, indent=2, sort_keys=True)
            fh.write("\n")

    _atomic_write(champion_json(sport), write)


def load_iterations(sport: str) -> pd.DataFrame:
    p = iterations_csv(sport)
    if p.exists():
        return pd.read_csv(p).reindex(columns=ITERATION_COLUMNS)
    return pd.DataFrame(columns=ITERATION_COLUMNS)


def append_iteration(sport: str, row: dict) -> None:
    old = load_iterations(sport)
    new = pd.DataFrame([row]).reindex(columns=ITERATION_COLUMNS)
    out = new if old.empty else pd.concat([old, new], ignore_index=True)
    _write_csv(out, iterations_csv(sport))


def trials_total(sport: str) -> int:
    """Challenger evaluations recorded so far (the multiple-testing count)."""
    it = load_iterations(sport)
    if it.empty:
        return 0
    return int(pd.to_numeric(it["trials_total"], errors="coerce").dropna().max() or 0)
