"""Parameter sweep: derive the P/V day map and thresholds from history.

Grid: 2^6 = 64 day maps (Mon/Tue/Thu/Fri/Sat/Sun each P or V; Wednesday fixed
HYBRID per the strategy doc) x min_move {5,10,15,20} x evenly-matched ML
{120,130,140} x heavy-fav {200,250,300}. Train on older seasons, rank by
validation-split ROI with a minimum-bet floor, and report the top configs so
stability (not a lone argmax) drives the choice.

Output: data/calibration/sweep_results.csv, data/calibration/best_params.json,
reports/CALIBRATION.md, and (with --write-config)
config/strategy.calibrated.yaml.
"""

from __future__ import annotations

import itertools
import json

import pandas as pd
import yaml

from .. import paths
from ..config import load_config
from ..timeutil import now_utc, utc_iso
from .engine import _parse_seasons, _prepare_games, run
from .loader import load_dir

SWEEP_DAYS = ["monday", "tuesday", "thursday", "friday", "saturday", "sunday"]
MIN_MOVE_GRID = [5, 10, 15, 20]
EVEN_ML_GRID = [120, 130, 140]
HEAVY_FAV_GRID = [200, 250, 300]
MIN_BETS_FLOOR = 150


def _configs(base_cfg: dict):
    for combo in itertools.product("PV", repeat=len(SWEEP_DAYS)):
        for min_move, even_ml, heavy in itertools.product(
            MIN_MOVE_GRID, EVEN_ML_GRID, HEAVY_FAV_GRID
        ):
            cfg = json.loads(json.dumps(base_cfg))  # deep copy
            for day, t in zip(SWEEP_DAYS, combo, strict=True):
                cfg["day_map"][day] = t
            cfg["day_map"]["wednesday"] = "HYBRID"
            cfg["movement"]["min_move_cents"] = min_move
            cfg["thresholds"]["evenly_matched_max_abs_ml"] = even_ml
            cfg["thresholds"]["heavy_fav_abs_ml"] = heavy
            config_id = (
                "".join(combo) + f"-m{min_move}-e{even_ml}-h{heavy}"
            )
            yield config_id, cfg, {
                "day_map": "".join(combo),
                "min_move_cents": min_move,
                "evenly_matched_max_abs_ml": even_ml,
                "heavy_fav_abs_ml": heavy,
            }


def sweep(hist: pd.DataFrame, base_cfg: dict, train, validate) -> pd.DataFrame:
    train_df = hist[(hist["season"] >= train[0]) & (hist["season"] <= train[1])]
    valid_df = hist[(hist["season"] >= validate[0]) & (hist["season"] <= validate[1])]
    prepared_train = _prepare_games(train_df)
    prepared_valid = _prepare_games(valid_df)

    rows = []
    for config_id, cfg, params in _configs(base_cfg):
        for split, prepared in (("train", prepared_train), ("valid", prepared_valid)):
            result = run(prepared, cfg)
            rows.append(
                {
                    "config_id": config_id,
                    **params,
                    "split": split,
                    **{
                        k: result.summary.get(k)
                        for k in ("n_bets", "wins", "losses", "pushes", "profit", "roi")
                    },
                }
            )
    return pd.DataFrame(rows)


def rank(results: pd.DataFrame) -> pd.DataFrame:
    """Rank configs by validation ROI among those clearing the bet floor on
    both splits."""
    pivot = results.pivot_table(
        index=["config_id", "day_map", "min_move_cents", "evenly_matched_max_abs_ml",
               "heavy_fav_abs_ml"],
        columns="split",
        values=["n_bets", "roi", "profit"],
    )
    pivot.columns = [f"{a}_{b}" for a, b in pivot.columns]
    pivot = pivot.reset_index()
    eligible = pivot[
        (pivot["n_bets_train"] >= MIN_BETS_FLOOR)
        & (pivot["n_bets_valid"] >= MIN_BETS_FLOOR)
    ]
    return eligible.sort_values("roi_valid", ascending=False).reset_index(drop=True)


def write_report(ranked: pd.DataFrame, train, validate, coverage: dict) -> None:
    path = paths.reports_dir() / "CALIBRATION.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Calibration Report — P/V Day Map & Thresholds",
        "",
        f"Generated: {utc_iso(now_utc())}",
        "",
        "## Data coverage",
        "",
        f"- Seasons: {coverage['seasons']} ({coverage['n_games']} games)",
        f"- Train: {train[0]}–{train[1]} · Validate: {validate[0]}–{validate[1]}",
        "",
        "## Method",
        "",
        f"Grid: 64 day-maps (Wed fixed HYBRID) × min_move {MIN_MOVE_GRID} × "
        f"evenly-matched ML {EVEN_ML_GRID} × heavy-fav {HEAVY_FAV_GRID} = "
        "2,304 configs. Movement proxy = open→close moneyline. Ranked by "
        f"validation ROI with a ≥{MIN_BETS_FLOOR}-bet floor per split.",
        "",
        "## Caveats (read before trusting)",
        "",
        "- **Open→close is a coarse proxy** for the strategy's intraday",
        "  line-movement reads; only forward paper-trading tests the real thing.",
        "- **Wednesday (hybrid) games are excluded** — historical files carry no",
        "  start times, so hybrid slots cannot be assigned.",
        "- **64 day-maps is a lot of hypotheses.** The validation split guards",
        "  against overfitting, but treat the chosen map as a prior to be",
        "  confirmed live, not a proven fact.",
        "- No ERA/dossier data in historical files: the ERA fallback and R8 veto",
        "  never fire in backtests.",
        "- **The archives price no run lines** (`*_rl_odds` are 100% null in all",
        "  17,245 games), so R4/R5/R7 picks silently reverted to their moneyline",
        "  form in every sweep config — the sweep never tested the RL bets the",
        "  live strategy actually places (30 of the first 93 live picks were RL).",
        "  The `evenly_matched` marginal in particular measures an ML strategy.",
        "- 2,304 grid configs collapse to **768 distinct hypotheses**: the",
        "  heavy-fav parameter is inert across its whole grid (identical results",
        "  at 200/250/300), because unpriced run lines make R7's conversion a",
        "  no-op on market.",
        "",
        "## Top 10 configs by validation ROI",
        "",
    ]
    top = ranked.head(10)
    if top.empty:
        lines.append("_No config cleared the minimum-bet floor. Check data coverage._")
    else:
        lines += [
            "| Day map (M,T,Th,F,Sa,Su) | min_move | even_ml | heavy_fav "
            "| Train bets | Train ROI | Valid bets | Valid ROI |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, r in top.iterrows():
            lines.append(
                f"| {r['day_map']} | {r['min_move_cents']} "
                f"| {r['evenly_matched_max_abs_ml']} | {r['heavy_fav_abs_ml']} "
                f"| {int(r['n_bets_train'])} | {r['roi_train']:+.2f}% "
                f"| {int(r['n_bets_valid'])} | {r['roi_valid']:+.2f}% |"
            )
        best = top.iloc[0]
        lines += [
            "",
            "## Chosen config",
            "",
            f"`{best['config_id']}` — day map **{best['day_map']}** over "
            "(Mon, Tue, Thu, Fri, Sat, Sun), Wednesday HYBRID. "
            f"Validation ROI {best['roi_valid']:+.2f}% on {int(best['n_bets_valid'])} bets "
            f"(train {best['roi_train']:+.2f}% on {int(best['n_bets_train'])}).",
            "",
            "Written to `config/strategy.calibrated.yaml` when `--write-config` is used;",
            "override any value by editing `config/strategy.yaml`.",
        ]
    path.write_text("\n".join(lines) + "\n")


def write_calibrated_yaml(best_row: pd.Series) -> None:
    day_map = {"wednesday": "HYBRID"}
    for day, t in zip(SWEEP_DAYS, str(best_row["day_map"]), strict=True):
        day_map[day] = t
    payload = {
        "meta": {"calibrated": True, "calibrated_at": utc_iso(now_utc()),
                 "config_id": best_row["config_id"]},
        "day_map": day_map,
        "movement": {"min_move_cents": int(best_row["min_move_cents"])},
        "thresholds": {
            "evenly_matched_max_abs_ml": int(best_row["evenly_matched_max_abs_ml"]),
            "heavy_fav_abs_ml": int(best_row["heavy_fav_abs_ml"]),
        },
    }
    out = paths.config_dir() / "strategy.calibrated.yaml"
    header = (
        "# Written by `panthera-mvp calibrate --write-config`.\n"
        "# Merged on top of strategy.yaml. See reports/CALIBRATION.md for how\n"
        "# these values were chosen. Safe to edit or delete.\n"
    )
    out.write_text(header + yaml.safe_dump(payload, sort_keys=False))


def cmd_calibrate(train_spec: str, validate_spec: str, write_config: bool) -> None:
    train = _parse_seasons(train_spec)
    validate = _parse_seasons(validate_spec)
    hist = load_dir()
    coverage = {
        "seasons": f"{int(hist['season'].min())}–{int(hist['season'].max())}",
        "n_games": len(hist),
    }
    base_cfg = load_config()
    print(f"[calibrate] sweeping 2,304 configs over {coverage['n_games']} games...")
    results = sweep(hist, base_cfg, train, validate)
    cal_dir = paths.calibration_dir()
    cal_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(cal_dir / "sweep_results.csv", index=False)
    ranked = rank(results)
    write_report(ranked, train, validate, coverage)
    if ranked.empty:
        print("[calibrate] no config cleared the bet floor; see CALIBRATION.md")
        return
    best = ranked.iloc[0]
    (cal_dir / "best_params.json").write_text(
        json.dumps(best.to_dict(), indent=1, default=str)
    )
    print(
        f"[calibrate] best: {best['config_id']} valid ROI {best['roi_valid']:+.2f}% "
        f"({int(best['n_bets_valid'])} bets)"
    )
    if write_config:
        write_calibrated_yaml(best)
        print("[calibrate] wrote config/strategy.calibrated.yaml")
