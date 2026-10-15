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
    "strategy_id",
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
    "close_price",
    "clv_cents",
]

#: Append-once identity for a pick. `pick_id` alone can't be the dedupe key:
#: the 93 legacy rows keep their unprefixed ids (annotated, never re-termed),
#: which would collide with nothing and protect nothing once ids gained the
#: strategy prefix. `pick_id` remains the settlement key and must stay unique.
PICKS_DEDUPE_KEY = ["strategy_id", "game_pk", "market", "game_date_et"]

PASSES_COLUMNS = [
    "ts_utc",
    "run_label",
    "strategy_id",
    "game_pk",
    "game_date_et",
    "reason",
]

#: A game passed in the morning run and picked in the pregame run must not
#: double-count: passes are keyed per run, and reports subtract games that
#: later produced a pick.
PASSES_KEY = ["strategy_id", "game_pk", "game_date_et", "run_label"]

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
    """Persist an operational note so daily-report regeneration doesn't erase
    it. `kind` is one of `late_run`, `degraded_snapshot`, `engine_error`,
    `ambiguous_espn_match` or `unmapped_final_no_score`; the schema is
    documented in `data/CLAUDE.md`, and every kind written anywhere in `src/`
    belongs there.

    Identical notes are not repeated: the same (game_date_et, kind, note)
    collapses to one row. A game stuck in an unmapped terminal state is
    re-examined by every refresh — several times a day, indefinitely — and
    each note renders as a bullet in the daily report.
    """
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
    if not existing.empty:
        same = (
            (existing["game_date_et"].astype(str) == str(game_date_et))
            & (existing["kind"].astype(str) == str(kind))
            & (existing["note"].astype(str) == str(note))
        )
        if bool(same.any()):
            return
    pd.concat([existing, row], ignore_index=True).to_csv(path, index=False)


def load_run_log() -> pd.DataFrame:
    return _load(paths.data_dir() / "picks" / "run_log.csv", RUN_LOG_COLUMNS)


def load_lines() -> pd.DataFrame:
    return _load(paths.lines_csv())


def load_games() -> pd.DataFrame:
    return _load(paths.games_csv(), GAMES_COLUMNS)


def _load_picks() -> pd.DataFrame:
    """Load picks reindexed to the canonical schema (legacy files gain the
    new columns as nulls). Scoped to picks only — a blanket reindex in _load
    would drop unknown columns from lines/games. Every picks call site
    (load/append/settle) routes through here so an append after a schema
    extension can never silently write the legacy column set back."""
    df = _load(paths.picks_csv(), PICKS_COLUMNS)
    return df.reindex(columns=PICKS_COLUMNS)


def load_picks() -> pd.DataFrame:
    return _load_picks()


def load_shadow_picks() -> pd.DataFrame:
    """Retroactive replay ledger (data/picks/shadow_picks.csv) — same schema
    as picks.csv, kept in a separate file so it can never pool into a live
    strategy's pre-registered verdict."""
    df = _load(paths.shadow_picks_csv(), PICKS_COLUMNS)
    return df.reindex(columns=PICKS_COLUMNS)


def append_shadow_picks(df: pd.DataFrame) -> int:
    """Append-once into shadow_picks.csv, same dedupe key as append_picks."""
    if df.empty:
        return 0
    path = paths.shadow_picks_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_shadow_picks()
    if not existing.empty:
        existing_keys = set(map(tuple, existing[PICKS_DEDUPE_KEY].astype(str).values))
        mask = [
            tuple(map(str, row)) not in existing_keys
            for row in df[PICKS_DEDUPE_KEY].values
        ]
        df = df[mask]
        if df.empty:
            return 0
    combined = pd.concat([existing, df], ignore_index=True)
    combined = combined.reindex(columns=PICKS_COLUMNS)
    combined.to_csv(path, index=False)
    return len(df)


def settle_shadow_picks(settlements: pd.DataFrame) -> int:
    """Same shape/semantics as settle_picks, applied to shadow_picks.csv."""
    if settlements.empty:
        return 0
    path = paths.shadow_picks_csv()
    picks = load_shadow_picks()
    if picks.empty:
        return 0
    count = 0
    picks = picks.set_index("pick_id")
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


def _has_both_scores(df: pd.DataFrame) -> pd.Series:
    """True where both scores are present. A frame that lacks the score
    columns altogether carries no scores anywhere — callers may hand over a
    narrow frame, and a missing column is an absence, not an error."""
    if not {"home_score", "away_score"} <= set(df.columns):
        return pd.Series(False, index=df.index)
    return df["home_score"].notna() & df["away_score"].notna()


def _is_settled_final(df: pd.DataFrame) -> pd.Series:
    """A row whose result is complete: Final with both scores.

    The protection below keys on THIS and not on "has a score": an
    in-progress row carries a score too (a Live game at 0-0 counts), and
    protecting those would discard the very correction that says the game was
    called off mid-play — the same unsettleable shape this module's guard
    exists to prevent.
    """
    if "status" not in df.columns:
        return pd.Series(False, index=df.index)
    return (df["status"] == "Final") & _has_both_scores(df)


def upsert_games(df: pd.DataFrame) -> None:
    """Replace rows by game_pk — except that an incoming row never BLANKS the
    score of a game the store already has a COMPLETE final for.

    `_refresh_games` rebuilds every row straight from the MLB API, and the API
    sometimes returns a completed game as Final with no linescore. Without
    this guard, a score the ESPN fallback had filled was wiped again on the
    next `snapshot` or `picks` run (both call `_refresh_games`, and neither has
    a fallback behind it), so the repair never lasted a full day. A null score
    is an absence, never a correction, so the stored row wins — wholesale, not
    field by field. The one production writer rebuilds every column from the
    same MLB API call, and a game already Final has nothing else left to learn
    (start time, pitcher ERAs and game type are fixed by then), so keeping the
    stored row costs nothing. A score that DIFFERS is still accepted: this
    rejects an absent score, not a corrected one.
    """
    if df.empty:
        return
    path = paths.games_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load(path, GAMES_COLUMNS)
    if not existing.empty:
        scored = set(existing.loc[_is_settled_final(existing), "game_pk"])
        df = df[~(df["game_pk"].isin(scored) & ~_has_both_scores(df))]
        if df.empty:
            return
        existing = existing[~existing["game_pk"].isin(df["game_pk"])]
    combined = pd.concat([existing, df], ignore_index=True)
    combined = combined.sort_values(["game_date_et", "game_pk"])
    combined.to_csv(path, index=False)


def append_picks(df: pd.DataFrame) -> int:
    """Append picks not already present (idempotent, append-once).

    Dedupe key is (strategy_id, game_pk, market, game_date_et) — see
    PICKS_DEDUPE_KEY. Intra-strategy re-runs append nothing (picks are
    immutable once created); a second strategy on the same game/market is a
    distinct row."""
    if df.empty:
        return 0
    path = paths.picks_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_picks()
    if not existing.empty:
        existing_keys = set(
            map(tuple, existing[PICKS_DEDUPE_KEY].astype(str).values)
        )
        mask = [
            tuple(map(str, row)) not in existing_keys
            for row in df[PICKS_DEDUPE_KEY].values
        ]
        df = df[mask]
        if df.empty:
            return 0
    combined = pd.concat([existing, df], ignore_index=True)
    combined = combined.reindex(columns=PICKS_COLUMNS)
    combined.to_csv(path, index=False)
    return len(df)


def append_passes(df: pd.DataFrame) -> int:
    """Append pass records keyed by PASSES_KEY (append-once per run)."""
    if df.empty:
        return 0
    path = paths.data_dir() / "picks" / "passes.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load(path, PASSES_COLUMNS)
    if not existing.empty:
        existing_keys = set(map(tuple, existing[PASSES_KEY].astype(str).values))
        mask = [
            tuple(map(str, row)) not in existing_keys
            for row in df[PASSES_KEY].values
        ]
        df = df[mask]
        if df.empty:
            return 0
    combined = pd.concat([existing, df], ignore_index=True)
    combined.to_csv(path, index=False)
    return len(df)


def load_passes() -> pd.DataFrame:
    return _load(paths.data_dir() / "picks" / "passes.csv", PASSES_COLUMNS)


def fill_clv(updates: pd.DataFrame) -> int:
    """updates columns: pick_id, close_price, clv_cents. Fills only rows
    whose close_price is currently null — CLV enrichment never rewrites
    (mirrors the picks-immutable convention)."""
    if updates.empty:
        return 0
    path = paths.picks_csv()
    picks = _load_picks()
    if picks.empty:
        return 0
    picks = picks.set_index("pick_id")
    count = 0
    for row in updates.itertuples(index=False):
        if row.pick_id in picks.index and pd.isna(picks.at[row.pick_id, "close_price"]):
            picks.at[row.pick_id, "close_price"] = row.close_price
            picks.at[row.pick_id, "clv_cents"] = row.clv_cents
            count += 1
    picks.reset_index().reindex(columns=PICKS_COLUMNS).to_csv(path, index=False)
    return count


def settle_picks(settlements: pd.DataFrame) -> int:
    """settlements columns: pick_id, status, settled_ts_utc, final_score, profit."""
    if settlements.empty:
        return 0
    path = paths.picks_csv()
    picks = _load_picks()
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
