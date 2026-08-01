"""Load and normalize sportsbookreviewsonline-style historical MLB odds files.

Expected raw format (one row per team, visitor then home, per game):
  Date (mmdd int) | Rot | VH (V/H/N) | Team (abbrev) | Pitcher |
  1st..9th | Final | Open (ML) | Close (ML) | RunLine | RunLineOdds |
  OpenOU | OpenOUOdds | CloseOU | CloseOUOdds

Column names drift across seasons ("Open OU" vs "OpenOU", "Run Line" vs
"RunLine"), so headers are normalized by stripping non-alphanumerics and
lowercasing. Files must be named to contain a 4-digit season year, e.g.
"mlb odds 2021.xlsx". Output: one row per GAME with visitor/home fields.
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
    # Some seasons put the run line and its odds in adjacent unnamed columns;
    # handled below via positional fallback.
    "openou": "open_ou",
    "openouodds": "open_ou_odds",
    "closeou": "close_ou",
    "closeouodds": "close_ou_odds",
}


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

    renamed = {}
    for col in raw.columns:
        norm = _norm_header(col)
        if norm in HEADER_MAP:
            renamed[col] = HEADER_MAP[norm]
    raw = raw.rename(columns=renamed)

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
