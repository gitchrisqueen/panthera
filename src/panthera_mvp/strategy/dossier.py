"""Skeleton Foundation Dossier (doc §3 step 2).

Feature bundle per game used by the rules engines: ERA comparison, previous
game result, recent form, season-series outcomes, and (2026-08-19 alignment)
the additional "merit" inputs the original strategy's natural-vs-scam read
actually runs on -- full season record, previous-opponent strength, ATS/cover
streaks, combined-runs trends, and the previous head-to-head meeting's own
prices. Every field is optional so the rules degrade gracefully when a source
is missing (e.g. no ERA/RL prices in parts of the historical backtest).

SeasonContext accumulates finals (and, where available, closing prices)
chronologically and answers the dossier's "recent outcomes / trends"
questions for any team key (MLB team id live, sbro team abbreviation in
backtests). Callers must only add games that finished *before* the game
being evaluated -- the backtest engine feeds results incrementally to
guarantee no lookahead.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass


@dataclass
class _GameRecord:
    opponent: Hashable
    won: bool
    run_diff: int
    team_runs: int
    opp_runs: int
    covered_rl: bool | None  # None = run-line price unknown for this game


@dataclass
class _PriceRecord:
    """One side's ML/RL price at the close of one head-to-head meeting."""

    ml: float | None
    rl: float | None


class SeasonContext:
    def __init__(self) -> None:
        self._results: dict[Hashable, list[_GameRecord]] = defaultdict(list)
        # frozenset({a, b}) -> {team: wins}
        self._h2h: dict[frozenset, dict[Hashable, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        # frozenset({a, b}) -> chronological list of (team_a, team_b, a_runs, b_runs)
        self._h2h_games: dict[frozenset, list[tuple]] = defaultdict(list)
        # frozenset({a, b}) -> chronological list of {team: _PriceRecord}
        self._h2h_prices: dict[frozenset, list[dict[Hashable, _PriceRecord]]] = (
            defaultdict(list)
        )

    def add_final(
        self,
        team_a: Hashable,
        team_b: Hashable,
        a_score: int,
        b_score: int,
        a_covered_rl: bool | None = None,
        b_covered_rl: bool | None = None,
    ) -> None:
        """Record one final. `a_covered_rl`/`b_covered_rl` (doc §6 ATS streaks,
        P1 63:20) are optional -- pass them only when the game's standard
        +/-1.5 run-line price was actually available (backtests have it; the
        live season-context backfill from MLB finals alone does not)."""
        if a_score == b_score:
            return  # cannot happen in MLB; defensive
        a_won = a_score > b_score
        self._results[team_a].append(
            _GameRecord(team_b, a_won, a_score - b_score, a_score, b_score, a_covered_rl)
        )
        self._results[team_b].append(
            _GameRecord(team_a, not a_won, b_score - a_score, b_score, a_score, b_covered_rl)
        )
        pair = frozenset((team_a, team_b))
        self._h2h[pair][team_a if a_won else team_b] += 1
        self._h2h_games[pair].append((team_a, team_b, a_score, b_score))

    def add_h2h_price(
        self,
        team_a: Hashable,
        team_b: Hashable,
        a_ml: float | None,
        b_ml: float | None,
        a_rl: float | None = None,
        b_rl: float | None = None,
    ) -> None:
        """Record the closing price each side had in one head-to-head
        meeting -- the input for the primary day-over-day signal (doc §1;
        every worked example leads with "last head-to-head... today")."""
        pair = frozenset((team_a, team_b))
        self._h2h_prices[pair].append(
            {team_a: _PriceRecord(a_ml, a_rl), team_b: _PriceRecord(b_ml, b_rl)}
        )

    def prev_run_diff(self, team: Hashable) -> int | None:
        results = self._results.get(team)
        return results[-1].run_diff if results else None

    def prev_opponent(self, team: Hashable) -> Hashable | None:
        results = self._results.get(team)
        return results[-1].opponent if results else None

    def last_n_wins(self, team: Hashable, n: int = 10) -> tuple[int, int] | None:
        """(wins, games) over the team's most recent n finals."""
        results = self._results.get(team)
        if not results:
            return None
        window = results[-n:]
        return sum(1 for r in window if r.won), len(window)

    def season_record(self, team: Hashable) -> tuple[int, int] | None:
        """(wins, losses) over every final recorded this season."""
        results = self._results.get(team)
        if not results:
            return None
        wins = sum(1 for r in results if r.won)
        return wins, len(results) - wins

    def win_pct(self, team: Hashable) -> float | None:
        record = self.season_record(team)
        if record is None or sum(record) == 0:
            return None
        wins, losses = record
        return wins / (wins + losses)

    def rank(self, team: Hashable) -> int | None:
        """1-based MLB-wide rank by season win pct among every team seen so
        far this season (doc: "Yankees got the number one record in the
        league", P1 38:34). Approximate by design -- ties broken by win
        count, and the field is necessarily noisy early in a season."""
        if team not in self._results:
            return None
        standings = sorted(
            (t for t in self._results if self.win_pct(t) is not None),
            key=lambda t: (self.win_pct(t), self.season_record(t)[0]),
            reverse=True,
        )
        return standings.index(team) + 1 if team in standings else None

    def prev_opponent_rank(self, team: Hashable) -> int | None:
        """Rank of the opponent in `team`'s most recent prior game (doc:
        "the reason why I really like MLB.com's website... I can see, okay,
        cool, the Yankees got the number one record", P1 38:34-39:11).
        Uses each team's CURRENT rank as a stand-in for its rank as of that
        earlier game -- an approximation, since ranks are not snapshotted
        historically; documented, not hidden."""
        opp = self.prev_opponent(team)
        return None if opp is None else self.rank(opp)

    def last5_combined_runs(self, team: Hashable) -> int | None:
        """Sum of (team_runs + opp_runs) over the team's last 5 games (doc
        P1 77:18: "what have the teams been combining for their last five
        games")."""
        results = self._results.get(team)
        if not results:
            return None
        window = results[-5:]
        return sum(r.team_runs + r.opp_runs for r in window)

    def last4_h2h_combined_runs(
        self, team_a: Hashable, team_b: Hashable
    ) -> int | None:
        """Sum of combined runs over up to the last 4 head-to-head meetings
        (doc P2 15:21: "the last four head-to-heads... have not exceeded
        six runs")."""
        games = self._h2h_games.get(frozenset((team_a, team_b)))
        if not games:
            return None
        window = games[-4:]
        return sum(a + b for _, _, a, b in window)

    def ats_streak(self, team: Hashable) -> int | None:
        """Signed trailing run-line cover streak: +N = last N games covered,
        -N = last N failed to cover, None = no priced games recorded (doc
        P1 63:20: "three-game covering streak"). Games with an unknown
        `covered_rl` are skipped rather than breaking the streak."""
        results = [r for r in self._results.get(team, []) if r.covered_rl is not None]
        if not results:
            return None
        sign = results[-1].covered_rl
        streak = 0
        for r in reversed(results):
            if r.covered_rl != sign:
                break
            streak += 1
        return streak if sign else -streak

    def series_wins(self, team_a: Hashable, team_b: Hashable) -> tuple[int, int]:
        record = self._h2h.get(frozenset((team_a, team_b)), {})
        return record.get(team_a, 0), record.get(team_b, 0)

    def prev_h2h_price(
        self, team_a: Hashable, team_b: Hashable
    ) -> tuple[_PriceRecord | None, _PriceRecord | None]:
        """(team_a's, team_b's) price records from the most recent recorded
        head-to-head meeting, or (None, None) if none is on file."""
        prices = self._h2h_prices.get(frozenset((team_a, team_b)))
        if not prices:
            return None, None
        latest = prices[-1]
        return latest.get(team_a), latest.get(team_b)


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
    # --- merit inputs (2026-08-19 alignment) ---
    season_wins_home: int | None = None
    season_losses_home: int | None = None
    season_wins_away: int | None = None
    season_losses_away: int | None = None
    rank_home: int | None = None
    rank_away: int | None = None
    prev_opponent_rank_home: int | None = None
    prev_opponent_rank_away: int | None = None
    ats_streak_home: int | None = None
    ats_streak_away: int | None = None
    last5_combined_runs_home: int | None = None
    last5_combined_runs_away: int | None = None
    last4_h2h_combined_runs: int | None = None
    # Previous head-to-head meeting's closing prices -- the primary signal
    # (doc §1; see strategy/scam.py).
    prev_h2h_ml_home: float | None = None
    prev_h2h_ml_away: float | None = None
    prev_h2h_rl_home: float | None = None
    prev_h2h_rl_away: float | None = None

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

    def season_win_gap(self) -> int | None:
        """Home wins minus away wins over the full season record (doc: 'only
        two wins separating these two teams', P1 40:47)."""
        if self.season_wins_home is None or self.season_wins_away is None:
            return None
        return self.season_wins_home - self.season_wins_away

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
        season_home = ctx.season_record(home_key)
        season_away = ctx.season_record(away_key)
        prev_ml_home, prev_rl_home = ctx.prev_h2h_price(home_key, away_key)
        prev_ml_away, prev_rl_away = ctx.prev_h2h_price(away_key, home_key)
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
            season_wins_home=season_home[0] if season_home else None,
            season_losses_home=season_home[1] if season_home else None,
            season_wins_away=season_away[0] if season_away else None,
            season_losses_away=season_away[1] if season_away else None,
            rank_home=ctx.rank(home_key),
            rank_away=ctx.rank(away_key),
            prev_opponent_rank_home=ctx.prev_opponent_rank(home_key),
            prev_opponent_rank_away=ctx.prev_opponent_rank(away_key),
            ats_streak_home=ctx.ats_streak(home_key),
            ats_streak_away=ctx.ats_streak(away_key),
            last5_combined_runs_home=ctx.last5_combined_runs(home_key),
            last5_combined_runs_away=ctx.last5_combined_runs(away_key),
            last4_h2h_combined_runs=ctx.last4_h2h_combined_runs(home_key, away_key),
            prev_h2h_ml_home=prev_ml_home.ml if prev_ml_home else None,
            prev_h2h_ml_away=prev_ml_away.ml if prev_ml_away else None,
            prev_h2h_rl_home=prev_rl_home.rl if prev_rl_home else None,
            prev_h2h_rl_away=prev_rl_away.rl if prev_rl_away else None,
        )
