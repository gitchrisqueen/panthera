"""Load and merge strategy configuration.

config/strategy.yaml holds the documented defaults; config/strategy.calibrated.yaml
(written by `panthera-mvp calibrate --write-config`) is deep-merged on top when
present. config_hash() stamps every pick so results trace to their parameters.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from . import paths


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(
    base: Path | None = None,
    overrides: Path | None = None,
) -> dict[str, Any]:
    base = base or paths.config_dir() / "strategy.yaml"
    overrides = overrides or paths.config_dir() / "strategy.calibrated.yaml"

    with open(base) as fh:
        cfg = yaml.safe_load(fh)
    if overrides.exists():
        with open(overrides) as fh:
            calibrated = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, calibrated)
    return cfg


def config_hash(cfg: dict[str, Any]) -> str:
    canonical = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:10]
