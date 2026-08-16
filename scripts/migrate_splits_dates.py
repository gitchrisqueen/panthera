"""One-time migration: fix game_date_et and game_pk in data/splits/splits.csv.

Why (2026-08-16): Lumify's events listing is UTC-keyed and `normalize()` used
to stamp the *fetch* date as `game_date_et`. Every >= 20:00 ET start therefore
carried the next day's date (56 of the first 218 events), and because
`match_splits_to_games` matches on (date, home_team_id, away_team_id), a
mis-dated previous-night game in a multi-day series attached to the *next*
day's game_pk — 28 of 190 (date, game_pk) pairs carried two contradictory
events. This script:

  1. re-derives `game_date_et` from `starts_at_utc` converted to ET;
  2. drops metric rows that are not ticket/money percentages (`*.price` was
     American odds mangled by a [0,100] filter; `*.line` was a spread/total
     point, not a percentage);
  3. re-matches `game_pk` from scratch against data/games/games.csv using the
     corrected dates.

Run once from the repo root: python scripts/migrate_splits_dates.py
Idempotent: re-running is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panthera_mvp import store  # noqa: E402
from panthera_mvp.clients.lumify import METRIC_WHITELIST_LEAVES, splits_csv  # noqa: E402
from panthera_mvp.pipeline import match_splits_to_games  # noqa: E402
from panthera_mvp.timeutil import ET, parse_utc  # noqa: E402


def main() -> None:
    path = splits_csv()
    if not path.exists():
        print("no splits.csv; nothing to migrate")
        return
    df = pd.read_csv(path)
    before = len(df)

    def derive_date(row):
        raw = row["starts_at_utc"]
        if pd.isna(raw):
            return row["game_date_et"]
        try:
            return str(parse_utc(str(raw)).astimezone(ET).date())
        except (ValueError, TypeError):
            return row["game_date_et"]

    new_dates = df.apply(derive_date, axis=1)
    n_redated = int((new_dates != df["game_date_et"]).sum())
    df["game_date_et"] = new_dates

    leaf = df["metric"].astype(str).str.rsplit(".", n=1).str[-1]
    keep = leaf.isin(METRIC_WHITELIST_LEAVES)
    n_dropped = int((~keep).sum())
    df = df[keep].copy()

    games = store.load_games()
    df["game_pk"] = None
    df = match_splits_to_games(df, games)
    n_matched = int(df["game_pk"].notna().sum())

    df.to_csv(path, index=False)
    print(
        f"migrated splits.csv: {before} rows in, {len(df)} out "
        f"({n_redated} re-dated, {n_dropped} non-percentage rows dropped, "
        f"{n_matched} matched to games)"
    )


if __name__ == "__main__":
    main()
