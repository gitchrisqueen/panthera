"""Load config/ncaaf.yaml (NCAAF plumbing knobs; not hashed into MLB picks)
and the NCAAF strategy registry (config/ncaaf_strategies/<id>.yaml)."""

from __future__ import annotations

from typing import Any

import yaml

from .. import paths
from ..config import STRATEGY_ID_RE, StrategyConfigError

#: NCAAF engines by name. The MLB registry (strategy/registry.py) never sees
#: these: their YAMLs live outside config/strategies/.
NCAAF_ENGINES = {"cfb_parlay"}


def load_ncaaf_config() -> dict[str, Any]:
    path = paths.config_dir() / "ncaaf.yaml"
    if not path.exists():
        raise SystemExit(f"missing NCAAF config: {path}")
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def ncaaf_strategies_dir():
    return paths.config_dir() / "ncaaf_strategies"


def load_ncaaf_strategies() -> dict[str, dict[str, Any]]:
    """{strategy_id: cfg} for every NCAAF strategy YAML. Unlike MLB, there is
    no base file to merge: each YAML is complete. Invalid files hard-error."""
    out: dict[str, dict[str, Any]] = {}
    sdir = ncaaf_strategies_dir()
    for path in sorted(sdir.glob("*.yaml")) if sdir.is_dir() else []:
        with open(path) as fh:
            cfg = yaml.safe_load(fh) or {}
        meta = cfg.get("strategy")
        if not isinstance(meta, dict):
            raise StrategyConfigError(f"{path.name}: missing `strategy:` block")
        sid = meta.get("id")
        if sid != path.stem or not (isinstance(sid, str) and STRATEGY_ID_RE.match(sid)):
            raise StrategyConfigError(f"{path.name}: strategy.id must equal the filename stem")
        if meta.get("engine") not in NCAAF_ENGINES:
            raise StrategyConfigError(
                f"{path.name}: unknown NCAAF engine {meta.get('engine')!r} "
                f"(registered: {sorted(NCAAF_ENGINES)})"
            )
        out[sid] = cfg
    return out
