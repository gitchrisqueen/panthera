"""Load and merge strategy configuration.

Two kinds of config exist:

- The **pipeline config**: config/strategy.yaml (documented defaults) with
  config/strategy.calibrated.yaml (written by `calibrate --write-config`)
  deep-merged on top. Used by snapshot/splits/grade and as the base layer for
  strategies.
- **Registry strategies**: one YAML per strategy under config/strategies/.
  Each merges base strategy.yaml < config/strategies/<id>.yaml — the
  calibrated overlay is deliberately NOT merged for registry strategies: its
  own header says "safe to edit or delete" and `calibrate --write-config`
  overwrites it, so a stray calibrate run must never silently change a
  registered strategy's behavior mid-evaluation. Behavioral parameters a
  strategy depends on are inlined in its own YAML.

config_hash() stamps every pick so results trace to their parameters. It
hashes only *behavioral* keys: the top-level `strategy`, `verdict`, `screen`
and `meta` blocks are dropped first — editing a hypothesis string, toggling
`enabled`, editing `hash_lineage` (which lives under `strategy`, avoiding
self-reference), or a calibrate timestamp must not fragment a ledger. A
behavioral change under a reused strategy id produces a new hash, which the
report refuses to pool with the declared `hash_lineage` — that is the
anti-silent-tuning mechanism.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from . import paths

#: Top-level keys excluded from config_hash — metadata and evaluation criteria,
#: never behavior. `strategy` holds id/engine/kind/enabled/scope/registered_at/
#: hash_lineage/hypothesis; `verdict`/`screen` are evaluation criteria; `meta`
#: carries calibrate timestamps.
HASH_EXCLUDED_KEYS = ("strategy", "verdict", "screen", "meta")

STRATEGY_ID_RE = re.compile(r"^[a-z0-9_]+$")

VALID_SCOPES = {"live", "backtest"}


class StrategyConfigError(RuntimeError):
    """A strategy YAML is missing, invalid, or inconsistent — hard error:
    silently generating zero picks is the failure mode this prevents."""


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


def strategies_dir() -> Path:
    return paths.config_dir() / "strategies"


def _validate_strategy(
    cfg: dict, raw: dict, stem: str, known_engines: set[str] | None
) -> None:
    meta = cfg.get("strategy")
    if not isinstance(meta, dict):
        raise StrategyConfigError(f"{stem}.yaml: missing `strategy:` block")
    sid = meta.get("id")
    if sid != stem or not (isinstance(sid, str) and STRATEGY_ID_RE.match(sid)):
        raise StrategyConfigError(
            f"{stem}.yaml: strategy.id must equal the filename stem and match "
            f"[a-z0-9_]+ (got {sid!r})"
        )
    engine = meta.get("engine")
    if known_engines is not None and engine not in known_engines:
        raise StrategyConfigError(
            f"{stem}.yaml: unknown engine {engine!r} (registered: {sorted(known_engines)})"
        )
    scope = meta.get("scope")
    if not isinstance(scope, list) or not set(scope) <= VALID_SCOPES or not scope:
        raise StrategyConfigError(
            f"{stem}.yaml: strategy.scope must be a non-empty subset of "
            f"{sorted(VALID_SCOPES)} (got {scope!r})"
        )
    # Checked against the raw file, not the merge — the base config would
    # otherwise silently supply a cap the strategy never declared.
    raw_limits = raw.get("bet_limits")
    if not isinstance(raw_limits, dict) or "max_picks_per_day" not in raw_limits:
        raise StrategyConfigError(
            f"{stem}.yaml: bet_limits.max_picks_per_day must be declared "
            "explicitly in the strategy file (null is the explicit uncapped form)"
        )
    verdict = cfg.get("verdict")
    if verdict is not None and not isinstance(verdict, dict):
        raise StrategyConfigError(
            f"{stem}.yaml: verdict must be a mapping or null (YAML `null`, "
            f"not the string 'none'); got {verdict!r}"
        )


def load_strategy_configs(
    known_engines: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load every strategy YAML, merged base < strategy file (no calibrated).

    Returns {strategy_id: merged_cfg}. Disabled strategies are included —
    callers filter on `strategy.enabled` / `strategy.scope` for their use.
    Hard-errors on a missing/empty directory or any invalid file.
    """
    sdir = strategies_dir()
    files = sorted(sdir.glob("*.yaml")) if sdir.is_dir() else []
    if not files:
        raise StrategyConfigError(
            f"no strategy configs found in {sdir} — the multi-strategy pipeline "
            "refuses to run with zero strategies"
        )
    base = load_config(overrides=paths.config_dir() / "_no_calibrated_overlay_")
    out: dict[str, dict[str, Any]] = {}
    for path in files:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}
        merged = _deep_merge(base, raw)
        _validate_strategy(merged, raw, path.stem, known_engines)
        out[path.stem] = merged
    return out


def config_hash(cfg: dict[str, Any]) -> str:
    hashable = {k: v for k, v in cfg.items() if k not in HASH_EXCLUDED_KEYS}
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:10]
