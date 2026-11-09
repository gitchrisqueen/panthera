"""`panthera-mvp lab run|status`: one weekly walk, and a read-only look.

`run` spends no API credits and makes no network call: it reads the logged
features and the stored games, walks once, appends one row to the iteration
ledger, promotes the champion when every guard holds, and rewrites the report.
"""

from __future__ import annotations

import math
import sys

from ..timeutil import ET, now_utc, utc_iso
from . import climb, store
from .config import LabConfigError, initial_params, lab_sports, load_lab_config
from .report import games_for, write_report


def loop_hash(cfg: dict) -> str:
    """Identity of the experiment: evaluator version, guards, search space and feature
    constants. A champion written under another hash belongs to another loop, because the
    multiple-testing count `trials_total` was earned under the old one."""
    from ..config import config_hash

    return config_hash({"eval": cfg["eval_version"], "guards": cfg["guards"],
                        "space": cfg["space"], "feature": cfg["feature"]})


def _champion_record(cfg: dict, params: dict, effective_from: str, change: str,
                     parent: str | None) -> dict:
    from ..config import config_hash

    return {
        "sport": cfg["sport"], "eval_version": cfg["eval_version"], "loop_hash": loop_hash(cfg),
        "params": params,
        "hash": config_hash(params), "effective_from": effective_from,
        "promoted_at": utc_iso(now_utc()), "parent_hash": parent, "change": change,
    }


def cmd_run(
    sport: str = "ncaaf", dry_run: bool = False, force: bool = False
) -> climb.RunResult | None:
    cfg = load_lab_config(sport)
    now = now_utc()
    today = now.astimezone(ET).date()
    if not force and today.month not in cfg["season_months"]:
        print(f"[lab {sport}] out of season (month {today.month}): nothing to do")
        return None
    champ = store.load_champion(sport)
    if champ is not None and champ.get("eval_version") != cfg["eval_version"]:
        raise LabConfigError(
            f"champion was written under {champ.get('eval_version')}, the config says "
            f"{cfg['eval_version']}: a new evaluator starts a new loop (docs/lab/PROGRAM.md)"
        )
    if champ is not None and champ.get("loop_hash") != loop_hash(cfg):
        raise LabConfigError(
            "the guards, search space or feature constants changed since this champion was "
            "written (loop hash differs): that starts a new loop. See 'Changing the evaluator "
            "starts a new loop' in docs/lab/PROGRAM.md"
        )
    iso = today.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    if not dry_run and not force:
        prior = store.load_iterations(sport)
        if not prior.empty and str(prior.iloc[-1]["week_label"]) == week:
            print(f"[lab {sport}] already ran in {week}; a second real run would count the "
                  f"same challengers twice (--force to repeat)")
            return None
    params = initial_params(cfg) if champ is None else champ["params"]
    res = climb.walk(
        store.load_features(sport), games_for(sport), params, cfg["space"], cfg["guards"],
        {"trials_total": store.trials_total(sport)},
    )
    print(f"[lab {sport}] {res.decision}: {res.reason}")
    if dry_run:
        return res

    if champ is None:
        champ = _champion_record(cfg, params, str(today), "initial", None)
        store.save_champion(sport, champ)
    store.append_iteration(sport, {
        "run_ts": utc_iso(now), "week_label": week,
        "eval_version": cfg["eval_version"], "n_games": res.n_games, "n_graded": res.n_graded,
        "champion_hash": champ["hash"], "best_challenger_param": res.param, "old": res.old,
        "new": res.new, "train_n": res.train_n, "champion_roi": res.champion_roi,
        "challenger_roi": res.challenger_roi, "paired_z": res.paired_z,
        "z_required": res.z_required, "n_neighbours": res.n_neighbours,
        "trials_total": res.trials_total, "holdout_champion_roi": res.holdout_champion_roi,
        "holdout_challenger_roi": res.holdout_challenger_roi, "decision": res.decision,
        "reason": res.reason,
    })
    if res.decision == "promoted":
        # Effective the next ET day: today's decisions may already be logged.
        nxt = str(today.fromordinal(today.toordinal() + 1))
        store.save_champion(sport, _champion_record(
            cfg, res.new_params, nxt, f"{res.param}: {res.old} -> {res.new}", champ["hash"]))
        print(f"[lab {sport}] new champion effective {nxt}")
    try:
        print(f"[lab {sport}] wrote {write_report()}")
    except Exception as exc:  # noqa: BLE001 - a report failure must not discard the run
        print(f"::warning::lab report failed (the run itself is recorded): "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
    return res


def cmd_status(sport: str | None = None) -> None:
    for s in [sport] if sport else lab_sports():
        cfg = load_lab_config(s)
        champ = store.load_champion(s)
        it = store.load_iterations(s)
        feats = store.load_features(s)
        print(f"[lab {s}] eval {cfg['eval_version']}; {len(feats)} feature rows; "
              f"{len(it)} runs; {store.trials_total(s)} challengers evaluated")
        if champ is None:
            print(f"[lab {s}] no champion yet (first run writes the starting point)")
            continue
        print(f"[lab {s}] champion {champ['hash']} effective {champ['effective_from']} "
              f"({champ.get('change')})")
        if not it.empty:
            last = it.iloc[-1]
            z = last["paired_z"]
            zs = "-" if z is None or (isinstance(z, float) and math.isnan(z)) else f"{z:.2f}"
            print(f"[lab {s}] last run {last['run_ts']}: {last['decision']} (z {zs})")
