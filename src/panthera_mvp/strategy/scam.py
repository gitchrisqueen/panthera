"""Natural-vs-scam classification (doc §1/§4/§5).

The live rules engine (rules.py R3) maps line-movement DIRECTION straight to
a side: shortened -> back the favorite (public) or fade to the dog (Vegas).
The source strategy does not use direction alone -- it asks whether the
move is *justified* by the team's recent merit, and reads that justification
oppositely depending on the slot:

  - NATURAL: price shortened and merit rose (won last game, beat a stronger
    opponent, better record/ERA) -- P1 43:44: "that's a natural line
    movement. That's what we want to see." Or: price lengthened and merit
    fell -- the mirror case, equally natural.
  - SCAM: price moved the OPPOSITE way from what merit would predict --
    P1 57:47: "why would Vegas all of a sudden now want to pay out 28 points
    more expensive... that makes absolutely no sense."

Then (doc §5, restated P2 19:48): a PUBLIC slot rides natural movement (bets
the side the market and the merit agree on); a VEGAS slot fades a scam (bets
the side the market is suspiciously NOT rewarding).

Merit is a signed score built from cheap, always-available dossier inputs:
season win gap, previous-opponent strength, last-10 form, ATS streak, and
ERA. It is intentionally coarse -- the source's own read is qualitative
("does it make sense?") -- and every weight lives in config so it can be
swept honestly rather than hand-tuned (see backtest/calibrate.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from .dossier import Dossier
from .movement import american_cost

DEFAULT_MERIT_WEIGHTS = {
    "season_win_gap": 1.0,  # per game of season-record gap
    "prev_opponent_rank_gap": 0.15,  # per rank of "beat a tougher opponent"
    "last10_win_gap": 1.5,  # per game of last-10 form gap
    "ats_streak_gap": 1.0,  # per game of ATS-cover-streak gap
    "era_edge": 2.0,  # flat, applied toward the lower-ERA side
}


@dataclass
class ScamSignal:
    classification: str  # "natural" | "scam" | "neutral"
    price_moved_toward: str | None  # "home" | "away" | None (no move)
    merit_favors: str | None  # "home" | "away" | None (no clear edge)
    price_delta_cents: float  # signed cents of movement toward `home`


def merit_score(dossier: Dossier, weights: dict[str, float] | None = None) -> float:
    """Positive = home has the edge, negative = away, magnitude = strength.
    Every term is independently optional -- missing inputs just contribute 0."""
    w = weights or DEFAULT_MERIT_WEIGHTS
    score = 0.0

    gap = dossier.season_win_gap()
    if gap is not None:
        score += w["season_win_gap"] * gap

    if dossier.prev_opponent_rank_home is not None and dossier.prev_opponent_rank_away is not None:
        # Lower rank number = tougher opponent beaten (or lost to) most
        # recently; a team whose last opponent ranked better (numerically
        # lower) gets credit (doc P1 38:34: "Red Sox performance actually
        # outplayed the Blue Jays performance" because they'd faced the #1
        # team, not the #4 team).
        rank_gap = dossier.prev_opponent_rank_away - dossier.prev_opponent_rank_home
        score += w["prev_opponent_rank_gap"] * rank_gap

    if dossier.last10_wins_home is not None and dossier.last10_wins_away is not None:
        score += w["last10_win_gap"] * (dossier.last10_wins_home - dossier.last10_wins_away)

    if dossier.ats_streak_home is not None and dossier.ats_streak_away is not None:
        score += w["ats_streak_gap"] * (dossier.ats_streak_home - dossier.ats_streak_away)

    edge = dossier.era_edge_side()
    if edge is not None:
        score += w["era_edge"] if edge == "home" else -w["era_edge"]

    return score


def _price_delta_toward_home(
    prev_home: float | None, prev_away: float | None,
    cur_home: float | None, cur_away: float | None,
) -> float | None:
    """Signed cents the market moved toward `home` between the previous
    head-to-head meeting's closing price and today's price (doc §1's primary
    comparison -- P1 33:20, 46:59, 50:34; P2 05:33). Positive = home got
    more expensive (shortened) relative to away."""
    if None in (prev_home, prev_away, cur_home, cur_away):
        return None
    home_delta = american_cost(cur_home) - american_cost(prev_home)
    away_delta = american_cost(cur_away) - american_cost(prev_away)
    return home_delta - away_delta


def classify(
    dossier: Dossier,
    cur_home_ml: float | None,
    cur_away_ml: float | None,
    cfg: dict,
) -> ScamSignal:
    """The primary signal: today's price vs the previous H2H meeting's price
    (doc §1), read against merit. Callers needing the secondary/intraday
    confirmation compare it separately (see strategy/orig_rules.py)."""
    scfg = cfg.get("scam", {})
    weights = scfg.get("merit_weights", DEFAULT_MERIT_WEIGHTS)
    min_merit = float(scfg.get("min_merit_score", 1.0))
    min_price_cents = float(scfg.get("min_price_delta_cents", 5.0))

    delta = _price_delta_toward_home(
        dossier.prev_h2h_ml_home, dossier.prev_h2h_ml_away, cur_home_ml, cur_away_ml
    )
    score = merit_score(dossier, weights)

    if delta is None or abs(delta) < min_price_cents or abs(score) < min_merit:
        moved = None if delta is None else ("home" if delta > 0 else "away")
        favored = None if abs(score) < min_merit else ("home" if score > 0 else "away")
        return ScamSignal("neutral", moved, favored, delta or 0.0)

    moved_toward = "home" if delta > 0 else "away"
    merit_favors = "home" if score > 0 else "away"
    # Natural: the side the price moved toward is also the side merit favors
    # (shortened AND deserved, or lengthened AND undeserved -- both are the
    # "makes sense" case). Scam: they disagree.
    classification = "natural" if moved_toward == merit_favors else "scam"
    return ScamSignal(classification, moved_toward, merit_favors, delta)
