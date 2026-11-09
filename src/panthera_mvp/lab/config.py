"""Load and validate config/lab/<sport>.yaml, and read or write params by path."""

from __future__ import annotations

import copy
from typing import Any

import yaml

from .. import paths

REQUIRED = ("sport", "feature", "initial_champion", "structure", "space", "guards")
GUARD_KEYS = ("min_bets", "z_min", "holdout_weeks", "shrink_pseudo_bets",
              "min_graded_games_for_run")


class LabConfigError(RuntimeError):
    """A lab config is missing or inconsistent: a hard error, never a silent no-op."""


def get_path(params: dict, path: str) -> Any:
    cur: Any = params
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
    return cur


def set_path(params: dict, path: str, value: Any) -> dict:
    """A deep copy of params with `path` set (the original is never touched)."""
    out = copy.deepcopy(params)
    cur = out
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value
    return out


def initial_params(cfg: dict) -> dict:
    """The starting champion: the signal block plus the straight-bet structure."""
    params = copy.deepcopy(cfg["initial_champion"])
    s = cfg["structure"]
    params["ticket"] = {
        "max_bets_per_day": s["max_bets_per_day"],
        "max_price_american": s["max_price_american"],
        "rank_by": s["rank_by"],
    }
    params["bet_limits"] = {"skip_day_after_loss": bool(s.get("skip_day_after_loss", False))}
    return params


def validate(cfg: dict) -> None:
    for key in REQUIRED:
        if key not in cfg:
            raise LabConfigError(f"lab config: missing `{key}`")
    for key in GUARD_KEYS:
        if key not in cfg["guards"]:
            raise LabConfigError(f"lab config: guards.{key} missing")
    params = initial_params(cfg)
    for item in cfg["space"]:
        path = item.get("path")
        try:
            cur = get_path(params, path)
        except KeyError:
            raise LabConfigError(f"lab config: space path {path!r} is not in the champion") from None
        kinds = [k for k in ("toggle", "step", "choices") if k in item]
        if len(kinds) != 1:
            raise LabConfigError(f"lab config: {path}: exactly one of toggle/step/choices")
        if "toggle" in item and not isinstance(cur, bool):
            raise LabConfigError(f"lab config: {path}: toggle needs a boolean")
        if "step" in item:
            if isinstance(cur, bool) or not isinstance(cur, (int, float)):
                raise LabConfigError(f"lab config: {path}: step needs a number")
            if item["step"] <= 0 or "min" not in item or "max" not in item:
                raise LabConfigError(f"lab config: {path}: positive step with min and max")
        if "choices" in item and cur not in item["choices"]:
            raise LabConfigError(f"lab config: {path}: {cur!r} not in choices")
    for sig in ("letdown", "look_ahead"):
        if params["signals"][sig]["min_fav_points"] <= 0:
            raise LabConfigError(f"lab config: {sig}.min_fav_points must be positive")


def load_lab_config(sport: str) -> dict[str, Any]:
    path = paths.config_dir() / "lab" / f"{sport}.yaml"
    if not path.exists():
        raise LabConfigError(f"missing lab config: {path}")
    with open(path) as fh:
        cfg = yaml.safe_load(fh) or {}
    validate(cfg)
    return cfg


def lab_sports() -> list[str]:
    d = paths.config_dir() / "lab"
    return sorted(p.stem for p in d.glob("*.yaml")) if d.is_dir() else []
