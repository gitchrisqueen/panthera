"""Skeleton Foundation Dossier (doc §3 step 2).

Feature bundle per game used by the rules engine: ERA comparison, previous
game result, recent form (last-10 moneyline record), and season-series
outcomes. Every field is optional so the rules degrade gracefully when a
source is missing (e.g. no ERA in historical backtests).

SeasonContext accumulates finals chronologically and answers the dossier's
"recent outcomes / trends" questions for any team key (MLB team id live,
team abbreviation in backtests). Callers must only add games that finished
*before* the game being evaluated — the backtest engine feeds results
incrementally to guarantee no lookahead.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass


class SeasonContext:
    def __init__(self) -> None:
        # team -> chronological list of (won, run_diff)
        self._results: dict[Hashable, list[tuple[bool, int]]] = defaultdict(list)
        # frozenset({a, b}) -> {team: wins}
        self._h2h: dict[frozenset, dict[Hashable, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def add_final(
        self, team_a: Hashable, team_b: Hashable, a_score: int, b_score: int
    ) -> None:
        if a_score == b_score:
            return  # cannot happen in MLB; defensive
        a_won = a_score > b_score
        self._results[team_a].append((a_won, a_score - b_score))
        self._results[team_b].append((not a_won, b_score - a_score))
        pair = frozenset((team_a, team_b))
        self._h2h[pair][team_a if a_won else team_b] += 1

    def prev_run_diff(self, team: Hashable) -> int | None:
        results = self._results.get(team)
        return results[-1][1] if results else None

    def last_n_wins(self, team: Hashable, n: int = 10) -> tuple[int, int] | None:
        """(wins, games) over the team's most recent n finals."""
        results = self._results.get(team)
        if not results:
            return None
        window = results[-n:]
        return sum(1 for won, _ in window if won), len(window)

    def series_wins(self, team_a: Hashable, team_b: Hashable) -> tuple[int, int]:
        record = self._h2h.get(frozenset((team_a, team_b)), {})
        return record.get(team_a, 0), record.get(team_b, 0)


@dataclass
class Dossier:
    era_home: float | None = None
    era_away: float | None = None
    first_meeting: bool = False
    # Previous game (most recent final) for each side: run differential from
    # that team's perspective, e.g. -6 = lost by 6.
    prev_run_diff_home: int | None = None
    prev_run_diff_away: int | None = None
    # Last-10 moneyline record (wins, games played in window).
    last10_wins_home: int | None = None
    last10_games_home: int | None = None
    last10_wins_away: int | None = None
    last10_games_away: int | None = None
    # Season head-to-head outcomes.
    series_wins_home: int | None = None
    series_wins_away: int | None = None

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

    def form_edge_side(self, min_win_gap: int) -> str | None:
        """Side with a clearly better last-10 record (doc §3: 'check the last
        10 games')."""
        if self.last10_wins_home is None or self.last10_wins_away is None:
            return None
        gap = self.last10_wins_home - self.last10_wins_away
        if abs(gap) < min_win_gap:
            return None
        return "home" if gap > 0 else "away"

    def series_edge_side(self, min_lead: int) -> str | None:
        """Side leading the season series (doc §3: 'head-to-head and season
        series analysis')."""
        if self.series_wins_home is None or self.series_wins_away is None:
            return None
        lead = self.series_wins_home - self.series_wins_away
        if abs(lead) < min_lead:
            return None
        return "home" if lead > 0 else "away"

    @classmethod
    def from_context(
        cls,
        ctx: SeasonContext,
        home_key: Hashable,
        away_key: Hashable,
        era_home: float | None = None,
        era_away: float | None = None,
        last10_n: int = 10,
    ) -> Dossier:
        home_form = ctx.last_n_wins(home_key, last10_n)
        away_form = ctx.last_n_wins(away_key, last10_n)
        series_home, series_away = ctx.series_wins(home_key, away_key)
        return cls(
            era_home=era_home,
            era_away=era_away,
            first_meeting=(series_home + series_away) == 0,
            prev_run_diff_home=ctx.prev_run_diff(home_key),
            prev_run_diff_away=ctx.prev_run_diff(away_key),
            last10_wins_home=home_form[0] if home_form else None,
            last10_games_home=home_form[1] if home_form else None,
            last10_wins_away=away_form[0] if away_form else None,
            last10_games_away=away_form[1] if away_form else None,
            series_wins_home=series_home,
            series_wins_away=series_away,
        )
