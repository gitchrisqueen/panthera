"""Parameter sweep: derive genuine-unknown thresholds from history.

The day map is no longer swept (2026-08-19): it is stated directly in the
source recordings (P1 02:10) and is now a documented constant in
config/strategy.yaml, not an unknown. The 64-day-map x 2,304-config sweep
that used to run here is exactly what produced the inverted VVHPPPP map —
see docs/mvp-design.md's alignment section for the full account.

Two sweeps remain, both over the FIXED documented day map:

1. `sweep` — the incumbent pv_rules-family thresholds (min_move_cents,
   evenly_matched_max_abs_ml, heavy_fav_abs_ml). Diagnostic/comparative now
   that pv_v2/pv_v3 pin their own values; useful for any future pv_rules-
   family registration.
2. `sweep_orig` — pv_orig's genuine unknowns (strategy/scam.py's merit
   thresholds, the day-policy "big scam" magnitude). Per repo protocol,
   registry strategies never merge strategy.calibrated.yaml and this command
   never writes to config/strategies/*.yaml directly — a stray calibrate run
   must not silently change a registered strategy's behavior mid-evaluation.
   Results are reported in CALIBRATION.md as a recommendation; applying them
   to pv_orig.yaml is a deliberate, owner-approved, manual step (same
   protocol as the original day-map decision).

Output: data/calibration/sweep_results.csv, data/calibration/best_params.json,
reports/CALIBRATION.md, and (with --write-config) config/strategy.calibrated.yaml
(pv_rules-family thresholds only — never pv_orig's).
"""

from __future__ import annotations

import itertools
import json

import pandas as pd
import yaml

from .. import paths
from ..config import load_config, load_strategy_configs
from ..timeutil import now_utc, utc_iso
from .engine import _parse_seasons, _prepare_games, run
from .loader import load_dir

MIN_MOVE_GRID = [5, 10, 15, 20]
EVEN_ML_GRID = [110, 120, 130, 140]
HEAVY_FAV_GRID = [200, 250, 300]
MIN_BETS_FLOOR = 150

# pv_orig's genuine unknowns (strategy/scam.py, strategy/orig_rules.py) —
# merit_weights themselves are held fixed (a 5-dimensional weight sweep is a
# separate, larger project; this targets the thresholds built on top of them).
ORIG_MIN_MERIT_GRID = [0.5, 1.0, 1.5, 2.0]
ORIG_MIN_PRICE_DELTA_GRID = [5.0, 10.0]
ORIG_BIG_SCAM_GRID = [40, 60, 80, 100]
ORIG_EVEN_ML_GRID = [110, 120, 130, 140]
ORIG_MIN_BETS_FLOOR = 40  # pv_orig's day/slot discipline cuts volume hard


def _configs(base_cfg: dict):
    for min_move, even_ml, heavy in itertools.product(
        MIN_MOVE_GRID, EVEN_ML_GRID, HEAVY_FAV_GRID
    ):
        cfg = json.loads(json.dumps(base_cfg))  # deep copy
        cfg["movement"]["min_move_cents"] = min_move
        cfg["thresholds"]["evenly_matched_max_abs_ml"] = even_ml
        cfg["thresholds"]["heavy_fav_abs_ml"] = heavy
        config_id = f"m{min_move}-e{even_ml}-h{heavy}"
        yield config_id, cfg, {
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
        index=["config_id", "min_move_cents", "evenly_matched_max_abs_ml",
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


def _orig_configs(pv_orig_cfg: dict):
    for min_merit, min_price, big_scam, even_ml in itertools.product(
        ORIG_MIN_MERIT_GRID, ORIG_MIN_PRICE_DELTA_GRID, ORIG_BIG_SCAM_GRID, ORIG_EVEN_ML_GRID
    ):
        cfg = json.loads(json.dumps(pv_orig_cfg))
        cfg["scam"]["min_merit_score"] = min_merit
        cfg["scam"]["min_price_delta_cents"] = min_price
        cfg["day_policy"]["big_scam_min_price_delta_cents"] = big_scam
        cfg["thresholds"]["evenly_matched_max_abs_ml"] = even_ml
        config_id = f"mm{min_merit}-mp{min_price}-bs{big_scam}-e{even_ml}"
        yield config_id, cfg, {
            "min_merit_score": min_merit,
            "min_price_delta_cents": min_price,
            "big_scam_min_price_delta_cents": big_scam,
            "evenly_matched_max_abs_ml": even_ml,
        }


def sweep_orig(hist: pd.DataFrame, pv_orig_cfg: dict, train, validate) -> pd.DataFrame:
    from ..strategy.registry import _orig_rules

    train_df = hist[(hist["season"] >= train[0]) & (hist["season"] <= train[1])]
    valid_df = hist[(hist["season"] >= validate[0]) & (hist["season"] <= validate[1])]
    prepared_train = _prepare_games(train_df)
    prepared_valid = _prepare_games(valid_df)

    rows = []
    for config_id, cfg, params in _orig_configs(pv_orig_cfg):
        for split, prepared in (("train", prepared_train), ("valid", prepared_valid)):
            result = run(prepared, cfg, generate=_orig_rules)
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


def rank_orig(results: pd.DataFrame) -> pd.DataFrame:
    pivot = results.pivot_table(
        index=["config_id", "min_merit_score", "min_price_delta_cents",
               "big_scam_min_price_delta_cents", "evenly_matched_max_abs_ml"],
        columns="split",
        values=["n_bets", "roi", "profit"],
    )
    pivot.columns = [f"{a}_{b}" for a, b in pivot.columns]
    pivot = pivot.reset_index()
    eligible = pivot[
        (pivot["n_bets_train"] >= ORIG_MIN_BETS_FLOOR)
        & (pivot["n_bets_valid"] >= ORIG_MIN_BETS_FLOOR)
    ]
    return eligible.sort_values("roi_valid", ascending=False).reset_index(drop=True)


def write_report(
    ranked: pd.DataFrame, train, validate, coverage: dict, ranked_orig: pd.DataFrame | None = None
) -> None:
    path = paths.reports_dir() / "CALIBRATION.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Calibration Report — Threshold Sweeps",
        "",
        f"Generated: {utc_iso(now_utc())}",
        "",
        "## Data coverage",
        "",
        f"- Seasons: {coverage['seasons']} ({coverage['n_games']} games)",
        f"- Train: {train[0]}–{train[1]} · Validate: {validate[0]}–{validate[1]}",
        "",
        "## What changed (2026-08-19)",
        "",
        "The day map is **no longer swept**. It is stated directly in the",
        "source recordings (P1 02:10: \"Monday...public day...Tuesday...Vegas",
        "day...Wednesday...hybrid day...Thursday...Vegas day...Friday...public",
        "day...both Saturday and Sunday are both going to be Vegas days\") and",
        "is now a documented constant in `config/strategy.yaml`. The previous",
        "64-day-map sweep picked an inverted map (VVHPPPP vs the documented",
        "PVHVPVV) on +1.40% validation ROI against −1.83% train — a sweep",
        "artifact, not a finding. It ran live as `pv_v2`/`pv_v3` for their",
        "entire history; both are −15%/−30% ROI live. See",
        "`docs/mvp-design.md`'s alignment section for the full account.",
        "",
        "The historical archive loader also had a bug (fixed the same day):",
        "run-line odds and totals prices sit in *unnamed* columns in every",
        "published sbro file and were silently dropped, so every backtested",
        "run-line pick fell back to a moneyline bet — R4/R5/R7 were never",
        "actually tested pre-2026-08-19. The numbers below are the first run",
        "under correctly-parsed run-line and totals pricing, and the first",
        "with real game start times (joined from the MLB Stats API schedule",
        "cache), so hybrid Wednesdays are no longer skipped.",
        "",
        "## Method — incumbent (pv_rules-family) thresholds",
        "",
        f"Grid: min_move {MIN_MOVE_GRID} × evenly-matched ML {EVEN_ML_GRID} × "
        f"heavy-fav {HEAVY_FAV_GRID} = "
        f"{len(MIN_MOVE_GRID) * len(EVEN_ML_GRID) * len(HEAVY_FAV_GRID)} configs, "
        f"under the fixed documented day map. Ranked by validation ROI with a "
        f"≥{MIN_BETS_FLOOR}-bet floor per split. Diagnostic/",
        "comparative now — pv_v2/pv_v3 already pin their own deployed values",
        "and this sweep cannot change them (registry strategies never merge",
        "`strategy.calibrated.yaml`); useful for any future pv_rules-family",
        "registration.",
        "",
        "## Caveats (read before trusting)",
        "",
        "- **Open→close is a coarse proxy** for the strategy's intraday",
        "  line-movement reads; only forward paper-trading tests the real thing.",
        "- No probable-pitcher ERA in historical files (pitcher names only): the",
        "  ERA fallback and R8 veto never fire in backtests.",
        "",
        "## Top 10 configs by validation ROI",
        "",
    ]
    top = ranked.head(10)
    if top.empty:
        lines.append("_No config cleared the minimum-bet floor. Check data coverage._")
    else:
        lines += [
            "| min_move | even_ml | heavy_fav | Train bets | Train ROI "
            "| Valid bets | Valid ROI |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, r in top.iterrows():
            lines.append(
                f"| {r['min_move_cents']} | {r['evenly_matched_max_abs_ml']} "
                f"| {r['heavy_fav_abs_ml']} | {int(r['n_bets_train'])} "
                f"| {r['roi_train']:+.2f}% | {int(r['n_bets_valid'])} "
                f"| {r['roi_valid']:+.2f}% |"
            )
        best = top.iloc[0]
        lines += [
            "",
            "## Chosen config (incumbent thresholds)",
            "",
            f"`{best['config_id']}`. Validation ROI {best['roi_valid']:+.2f}% on "
            f"{int(best['n_bets_valid'])} bets (train {best['roi_train']:+.2f}% on "
            f"{int(best['n_bets_train'])}).",
            "",
            "Written to `config/strategy.calibrated.yaml` when `--write-config` is",
            "used (day map is never written there anymore); override any value by",
            "editing `config/strategy.yaml`.",
        ]

    lines += [
        "",
        "## Method — pv_orig genuine unknowns",
        "",
        "Grid: min_merit_score {} × min_price_delta_cents {} × "
        "big_scam_min_price_delta_cents {} × evenly_matched_max_abs_ml {} = "
        "{} configs, over pv_orig's full day-policy/slot-discipline engine "
        "(merit_weights held fixed at their YAML starting values — a "
        "5-dimensional weight sweep is future work, not done here). Ranked "
        "by validation ROI with a ≥{}-bet floor per split (lower than the "
        "incumbent's: the day-off/slots-discipline policy cuts volume hard "
        "by design).".format(
            ORIG_MIN_MERIT_GRID, ORIG_MIN_PRICE_DELTA_GRID, ORIG_BIG_SCAM_GRID,
            ORIG_EVEN_ML_GRID,
            len(ORIG_MIN_MERIT_GRID) * len(ORIG_MIN_PRICE_DELTA_GRID)
            * len(ORIG_BIG_SCAM_GRID) * len(ORIG_EVEN_ML_GRID),
            ORIG_MIN_BETS_FLOOR,
        ),
        "",
        "**Never auto-applied.** Registry strategies never merge "
        "`strategy.calibrated.yaml`, and this command never writes to "
        "`config/strategies/pv_orig.yaml` directly — a stray calibrate run "
        "must not silently change a registered, evaluating strategy's "
        "behavior. Applying a result below is a deliberate, owner-approved,",
        "manual edit (the same protocol the original day-map decision used).",
        "",
    ]
    if ranked_orig is None or ranked_orig.empty:
        lines.append("_No pv_orig config cleared the minimum-bet floor._")
    else:
        top_orig = ranked_orig.head(10)
        lines += [
            "| min_merit | min_price_Δ | big_scam_Δ | even_ml | Train bets "
            "| Train ROI | Valid bets | Valid ROI |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, r in top_orig.iterrows():
            lines.append(
                f"| {r['min_merit_score']} | {r['min_price_delta_cents']} "
                f"| {r['big_scam_min_price_delta_cents']} "
                f"| {r['evenly_matched_max_abs_ml']} | {int(r['n_bets_train'])} "
                f"| {r['roi_train']:+.2f}% | {int(r['n_bets_valid'])} "
                f"| {r['roi_valid']:+.2f}% |"
            )
    path.write_text("\n".join(lines) + "\n")


def write_calibrated_yaml(best_row: pd.Series) -> None:
    payload = {
        "meta": {"calibrated": True, "calibrated_at": utc_iso(now_utc()),
                 "config_id": best_row["config_id"]},
        "movement": {"min_move_cents": int(best_row["min_move_cents"])},
        "thresholds": {
            "evenly_matched_max_abs_ml": int(best_row["evenly_matched_max_abs_ml"]),
            "heavy_fav_abs_ml": int(best_row["heavy_fav_abs_ml"]),
        },
    }
    out = paths.config_dir() / "strategy.calibrated.yaml"
    header = (
        "# Written by `panthera-mvp calibrate --write-config`.\n"
        "# Merged on top of strategy.yaml for non-registry-strategy pipeline\n"
        "# config only (registry strategies never merge this file). The day\n"
        "# map is never written here — it is a documented constant, not a\n"
        "# calibrated unknown. See reports/CALIBRATION.md. Safe to edit/delete.\n"
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
    n_incumbent = len(MIN_MOVE_GRID) * len(EVEN_ML_GRID) * len(HEAVY_FAV_GRID)
    n_games = coverage["n_games"]
    print(f"[calibrate] sweeping {n_incumbent} incumbent configs over {n_games} games...")
    results = sweep(hist, base_cfg, train, validate)
    cal_dir = paths.calibration_dir()
    cal_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(cal_dir / "sweep_results.csv", index=False)
    ranked = rank(results)

    ranked_orig = None
    try:
        strategies = load_strategy_configs()
        pv_orig_cfg = strategies.get("pv_orig")
    except Exception as exc:  # noqa: BLE001 - calibrate must not hard-fail on this
        print(f"[calibrate] pv_orig sweep skipped: {exc}")
        pv_orig_cfg = None
    if pv_orig_cfg is not None:
        n_orig = (
            len(ORIG_MIN_MERIT_GRID) * len(ORIG_MIN_PRICE_DELTA_GRID)
            * len(ORIG_BIG_SCAM_GRID) * len(ORIG_EVEN_ML_GRID)
        )
        print(f"[calibrate] sweeping {n_orig} pv_orig configs...")
        results_orig = sweep_orig(hist, pv_orig_cfg, train, validate)
        results_orig.to_csv(cal_dir / "sweep_results_orig.csv", index=False)
        ranked_orig = rank_orig(results_orig)

    write_report(ranked, train, validate, coverage, ranked_orig)
    if ranked.empty:
        print("[calibrate] no incumbent config cleared the bet floor; see CALIBRATION.md")
    else:
        best = ranked.iloc[0]
        (cal_dir / "best_params.json").write_text(
            json.dumps(best.to_dict(), indent=1, default=str)
        )
        print(
            f"[calibrate] best incumbent: {best['config_id']} valid ROI "
            f"{best['roi_valid']:+.2f}% ({int(best['n_bets_valid'])} bets)"
        )
        if write_config:
            write_calibrated_yaml(best)
            print("[calibrate] wrote config/strategy.calibrated.yaml")

    if ranked_orig is not None and not ranked_orig.empty:
        best_orig = ranked_orig.iloc[0]
        print(
            f"[calibrate] best pv_orig (report-only, not auto-applied): "
            f"{best_orig['config_id']} valid ROI {best_orig['roi_valid']:+.2f}% "
            f"({int(best_orig['n_bets_valid'])} bets)"
        )
