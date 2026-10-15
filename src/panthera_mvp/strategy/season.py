"""Which MLB game types the strategy layer is allowed to act on.

One definition, used by every engine gate AND by the dossier's season context,
so the two can never drift again.

They did drift. Before 2026-10-15 the engines read `season.game_types` from
config while `pipeline._build_season_context` hardcoded `== "R"`, and the
config value was a regular-season WHITELIST: `["R"]`. The source material
(docs/sports_betting_process.md §6) asks only to "exclude spring training",
but a whitelist of "R" also excludes every postseason type — F wild card,
D division series, L LCS, W World Series. From 2026-09-29 every live engine
returned a Pass on every game: 14 consecutive slate days, 145 passes, zero
picks, and nothing watched for it.

The replacement is a blacklist, so the default for an unrecognized type is
IN scope. A whitelist fails silent on anything it has not heard of; that is
precisely the failure being fixed here.
"""

from __future__ import annotations

from ..config import StrategyConfigError

#: Retired 2026-10-15. Present only to detect and reject stale configs.
LEGACY_KEY = "game_types"

KEY = "exclude_game_types"


def excluded_game_types(cfg: dict) -> frozenset[str]:
    """The MLB `gameType` codes the strategy layer must not act on.

    Hard-errors rather than defaulting: `StrategyConfigError`'s own docstring
    names "silently generating zero picks" as the failure mode it exists to
    prevent, and that is exactly what a permissive default would reinstate.
    """
    season = cfg.get("season") or {}
    if LEGACY_KEY in season:
        raise StrategyConfigError(
            "config key `season.game_types` was retired 2026-10-15 — it was a "
            "regular-season whitelist that silently excluded the whole "
            f"postseason. Use `season.{KEY}` (a blacklist) instead. Check "
            "config/strategy.yaml, config/strategy.calibrated.yaml and "
            "config/strategies/*.yaml."
        )
    if KEY not in season:
        raise StrategyConfigError(f"config is missing required key `season.{KEY}`")
    excluded = season[KEY]
    if not isinstance(excluded, list) or not all(isinstance(x, str) for x in excluded):
        raise StrategyConfigError(
            f"`season.{KEY}` must be a list of MLB gameType codes (got {excluded!r})"
        )
    return frozenset(excluded)


def in_scope(game_type: str, cfg: dict) -> bool:
    """True if the strategy layer may act on a game of this `gameType`."""
    return game_type not in excluded_game_types(cfg)
