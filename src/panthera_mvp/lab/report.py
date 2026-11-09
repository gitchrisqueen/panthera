"""reports/LAB_REPORT.md: the champion, its replayed forward result, the last runs.

Generated from data/lab/<sport>/ and the sport's games; never edited by hand.
Everything here is labelled exploratory: the champion was selected on past data.
"""

from __future__ import annotations

import math

import pandas as pd

from .. import paths
from ..timeutil import now_utc, utc_iso
from . import climb, store
from .config import lab_sports, load_lab_config

BANNER = (
    "Exploratory lab: selected on past data, not verdict-eligible; ~17,800 straight bets "
    "are needed to confirm a +2% ROI, so most weeks correctly end in no change."
)


def games_for(sport: str) -> pd.DataFrame:
    if sport == "ncaaf":
        from ..ncaaf import store as ncaaf_store

        return ncaaf_store.load_games()
    raise SystemExit(f"lab: no games source for sport {sport!r}")


def _n(x, fmt: str = "{:+.3f}") -> str:
    try:
        return "-" if x is None or math.isnan(float(x)) else fmt.format(float(x))
    except (TypeError, ValueError):
        return "-"


def _flat(params: dict, prefix: str = "") -> list[tuple[str, object]]:
    out = []
    for k, v in params.items():
        if isinstance(v, dict):
            out += _flat(v, f"{prefix}{k}.")
        else:
            out.append((f"{prefix}{k}", v))
    return out


def sport_section(sport: str) -> list[str]:
    cfg = load_lab_config(sport)
    champ = store.load_champion(sport)
    lines = [f"## {sport} ({cfg.get('level', '')})", ""]
    if champ is None:
        return lines + ["No run yet: the first weekly run writes the starting champion.", ""]
    it = store.load_iterations(sport)
    trials = store.trials_total(sport)
    n_next = len(climb.neighbours(champ["params"], cfg["space"]))
    z_next = climb.z_required(cfg["guards"], trials + n_next)
    lines += [
        f"Evaluator `{champ.get('eval_version', cfg['eval_version'])}`. Champion "
        f"`{champ['hash']}`, effective from {champ['effective_from']} "
        f"({champ.get('change', 'initial')}).",
        "",
        f"Challengers evaluated so far: {trials}. The next run needs z >= {z_next:.2f} "
        f"(floor {cfg['guards']['z_min']}, raised by the multiple-testing penalty), at least "
        f"{cfg['guards']['min_bets']} graded training bets, and a holdout that is not worse.",
        "",
    ]
    feats = store.load_features(sport)
    if not feats.empty:
        prep = climb.prepare(feats, games_for(sport))
        fwd = climb.forward_summary(prep, champ["params"], champ["effective_from"])
        lines += [
            f"**Replayed since {champ['effective_from']}:** {fwd['n_bets']} graded bets, "
            f"{fwd['units']:+.2f} units, ROI {_n(fwd['roi'], '{:+.1%}')} per bet. "
            "Selected on past data; replayed from the logged features, not a live ticket.",
            "",
        ]
    lines += ["| Parameter | Value |", "|---|---|"]
    lines += [f"| `{k}` | {v} |" for k, v in _flat(champ["params"])]
    lines += ["", "### Last 12 runs", ""]
    if it.empty:
        return lines + ["No runs recorded.", ""]
    lines += ["| Run (UTC) | Week | Decision | Change tested | n | Challenger z (needed) | Why |",
              "|---|---|---|---|---|---|---|"]
    for r in it.tail(12).iloc[::-1].itertuples():
        change = f"`{r.best_challenger_param}` {r.old} -> {r.new}" \
            if isinstance(r.best_challenger_param, str) and r.best_challenger_param else "-"
        lines.append(
            f"| {r.run_ts} | {r.week_label} | {r.decision} | {change} | {_n(r.train_n, '{:.0f}')} "
            f"| {_n(r.paired_z, '{:.2f}')} ({_n(r.z_required, '{:.2f}')}) | {r.reason} |"
        )
    return lines + [""]


def write_report() -> str:
    out = ["# Lab: weekly hill-climb", "",
           f"_Generated {utc_iso(now_utc())} by `panthera-mvp lab run`. Do not edit._", "",
           f"> {BANNER}", "",
           "Straight bets, $100 flat = 1 unit, best-available price. Search space, guards "
           "and the evaluator contract: `docs/lab/PROGRAM.md`.", ""]
    for sport in lab_sports():
        out += sport_section(sport)
    path = paths.lab_report_md()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out).rstrip() + "\n")
    return str(path)
