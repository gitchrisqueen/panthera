"""Load config/ncaaf.yaml (NCAAF plumbing knobs; not hashed into MLB picks)."""

from __future__ import annotations

from typing import Any

import yaml

from .. import paths


def load_ncaaf_config() -> dict[str, Any]:
    path = paths.config_dir() / "ncaaf.yaml"
    if not path.exists():
        raise SystemExit(f"missing NCAAF config: {path}")
    with open(path) as fh:
        return yaml.safe_load(fh) or {}
