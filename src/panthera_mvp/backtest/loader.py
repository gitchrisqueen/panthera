"""Load and normalize sportsbookreviewsonline-style historical MLB odds files.

Expected raw format (one row per team, visitor then home, per game):
  Date (mmdd int) | Rot | VH (V/H/N) | Team (abbrev) | Pitcher |
  1st..9th | Final | Open (ML) | Close (ML) | RunLine | <RL odds> |
  OpenOU | <over/under juice> | CloseOU | <over/under juice>

Column names drift across seasons ("Open OU" vs "OpenOU", "Run Line" vs
"RunLine"), so headers are normalized by stripping non-alphanumerics and
lowercasing. The three price columns are *unnamed* in every published file
and are resolved positionally — see ADJACENT_PRICE_COLUMNS.

Files must be named to contain a 4-digit season year, e.g. "mlb odds
2021.xlsx". Output: one row per GAME with visitor/home fields.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from .. import paths


def _norm_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# normalized header -> canonical field
HEADER_MAP = {
    "date": "date",
    "rot": "rot",
    "vh": "vh",
    "team": "team",
    "pitcher": "pitcher",
    "final": "final",
    "open": "open_ml",
    "close": "close_ml",
    "runline": "rl_line",
    "runlineodds": "rl_odds",
    "openou": "open_ou",
    "openouodds": "open_ou_odds",
    "closeou": "close_ou",
    "closeouodds": "close_ou_odds",
}

#: Anchor column -> the canonical field held by the *unnamed* column directly
#: to its right. Every sbro season file lays the price out this way
#: ("Run Line | Unnamed: 18", "Open OU | Unnamed: 20", "Close OU |
#: Unnamed: 22") — no season has ever carried a literal "Run Line Odds"
#: header, so without this fallback those three price columns are dropped and
#: every run-line/total bet silently degrades to a moneyline. Regression
#: guard: tests/test_backtest.py::test_loader_captures_prices.
ADJACENT_PRICE_COLUMNS = {
    "runline": "rl_odds",
    "openou": "open_ou_odds",
    "closeou": "close_ou_odds",
}


def _resolve_headers(columns: list) -> dict:
    """Map raw column labels -> canonical fields, including the positional
    fallback for the unnamed price columns (see ADJACENT_PRICE_COLUMNS)."""
    renamed = {}
    norms = [_norm_header(c) for c in columns]
    for col, norm in zip(columns, norms, strict=True):
        if norm in HEADER_MAP:
            renamed[col] = HEADER_MAP[norm]
    taken = set(renamed.values())
    for idx, norm in enumerate(norms):
        field = ADJACENT_PRICE_COLUMNS.get(norm)
        if field is None or field in taken or idx + 1 >= len(columns):
            continue
        # Only claim the neighbour when it is not itself a named data column.
        if norms[idx + 1] in HEADER_MAP or norms[idx + 1] in ADJACENT_PRICE_COLUMNS:
            continue
        renamed[columns[idx + 1]] = field
        taken.add(field)
    return renamed


def _season_from_name(path: Path) -> int | None:
    m = re.search(r"(19|20)\d{2}", path.name)
    return int(m.group(0)) if m else None


def _to_num(val):
    if pd.isna(val):
        return None
    s = str(val).strip().lower()
    if s in ("", "nl", "pk", "even"):
        return 100.0 if s == "even" else None
    try:
        return float(s)
    except ValueError:
        return None


def load_season_file(path: Path) -> pd.DataFrame:
    season = _season_from_name(path)
    if season is None:
        raise ValueError(f"cannot infer season year from filename: {path.name}")

    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path)
    else:
        raw = pd.read_csv(path)

    raw = raw.rename(columns=_resolve_headers(list(raw.columns)))

    required = {"date", "vh", "team", "final", "open_ml", "close_ml"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns after normalization: {missing}")

    games = []
    rows = raw.to_dict("records")
    i = 0
    while i + 1 < len(rows):
        vis, home = rows[i], rows[i + 1]
        # Rows come in visitor/home pairs; resync if the pairing is off.
        if str(vis.get("vh")).strip().upper() not in ("V", "N") or str(
            home.get("vh")
        ).strip().upper() not in ("H", "N"):
            i += 1
            continue
        try:
            mmdd = int(vis["date"])
            game_date = date(season, mmdd // 100, mmdd % 100)
        except (ValueError, TypeError):
            i += 2
            continue
        games.append(
            {
                "season": season,
                "game_date": str(game_date),
                "day_of_week": game_date.strftime("%A").lower(),
                "vis_team": str(vis["team"]).strip(),
                "home_team": str(home["team"]).strip(),
                "vis_pitcher": str(vis.get("pitcher", "")).strip(),
                "home_pitcher": str(home.get("pitcher", "")).strip(),
                "vis_final": _to_num(vis["final"]),
                "home_final": _to_num(home["final"]),
                "vis_ml_open": _to_num(vis["open_ml"]),
                "vis_ml_close": _to_num(vis["close_ml"]),
                "home_ml_open": _to_num(home["open_ml"]),
                "home_ml_close": _to_num(home["close_ml"]),
                "vis_rl_line": _to_num(vis.get("rl_line")),
                "vis_rl_odds": _to_num(vis.get("rl_odds")),
                "home_rl_line": _to_num(home.get("rl_line")),
                "home_rl_odds": _to_num(home.get("rl_odds")),
                # sbro convention: the visitor row carries the OVER price and
                # the home row the UNDER price; the total itself is repeated.
                "total_open": _to_num(vis.get("open_ou")),
                "total_open_over_odds": _to_num(vis.get("open_ou_odds")),
                "total_open_under_odds": _to_num(home.get("open_ou_odds")),
                "total_close": _to_num(vis.get("close_ou")),
                "total_close_over_odds": _to_num(vis.get("close_ou_odds")),
                "total_close_under_odds": _to_num(home.get("close_ou_odds")),
                # Retained under its historical name: existing callers and the
                # committed normalized CSV both reference `close_ou`.
                "close_ou": _to_num(vis.get("close_ou")),
            }
        )
        i += 2

    df = pd.DataFrame(games)
    # Drop rows without scores or complete moneylines — they can't be graded.
    df = df.dropna(
        subset=["vis_final", "home_final", "vis_ml_close", "home_ml_close"]
    ).reset_index(drop=True)
    return df


def load_dir(raw_dir: Path | None = None) -> pd.DataFrame:
    raw_dir = raw_dir or paths.historical_raw_dir()
    files = sorted(
        p
        for p in raw_dir.glob("*")
        if p.suffix.lower() in (".xlsx", ".xls", ".csv") and _season_from_name(p)
    )
    if not files:
        raise FileNotFoundError(f"no historical season files in {raw_dir}")
    frames = [load_season_file(p) for p in files]
    df = pd.concat(frames, ignore_index=True)
    out = paths.historical_normalized_csv()
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df
