"""Load config/ncaabase.yaml (college-baseball plumbing knobs; not hashed into
MLB picks) and answer "is this ET date in season?"."""

from __future__ import annotations

from typing import Any

import yaml

from .. import paths


def load_ncaabase_config() -> dict[str, Any]:
    path = paths.config_dir() / "ncaabase.yaml"
    if not path.exists():
        raise SystemExit(f"missing college baseball config: {path}")
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def in_season(date_et: str, cfg: dict[str, Any]) -> bool:
    """True when the ET date's MM-DD falls inside season.start..season.end
    (inclusive; a window that wraps the new year is not supported)."""
    season = cfg.get("season") or {}
    return str(season.get("start", "01-01")) <= date_et[5:10] <= str(season.get("end", "12-31"))
