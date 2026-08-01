"""Skeleton Foundation Dossier (doc §3 step 2).

Feature bundle per game used by the rules engine: ERA comparison, previous
game result, and first-meeting flag. Live enrichment (last-10, season series)
is fetched by the pipeline where network allows; every field is optional so
the rules degrade gracefully when a source is missing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Dossier:
    era_home: float | None = None
    era_away: float | None = None
    first_meeting: bool = False
    # Previous game (most recent final) for each side: run differential from
    # that team's perspective, e.g. -6 = lost by 6.
    prev_run_diff_home: int | None = None
    prev_run_diff_away: int | None = None

    @property
    def era_diff(self) -> float | None:
        if self.era_home is None or self.era_away is None:
            return None
        return round(abs(self.era_home - self.era_away), 2)

    def era_edge_side(self) -> str | None:
        """"home"/"away" for the side with the better (lower) probable ERA."""
        if self.era_home is None or self.era_away is None:
            return None
        if self.era_home == self.era_away:
            return None
        return "home" if self.era_home < self.era_away else "away"
