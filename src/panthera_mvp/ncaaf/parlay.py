"""cfb_spread_total_parlay engine — one game day in, at most one ticket out.

Pure functions over plain inputs (games, odds lines, SP+ ratings, kickoff
wind) so the live pipeline and any later CFBD backtest share one code path.
Parameters come from config/ncaaf_strategies/cfb_spread_total_parlay.yaml;
there are no magic numbers here.

Signal ids follow the author's follow-up answers (issue #55):

  S1 spread moved >= N points open -> decision      side the line moved toward
  S2 total moved >= N points open -> decision       over if up, under if down
  S3 letdown: beat a ranked team last game and      the opponent's spread
     favored by 10+ now
  S4 look-ahead: ranked opponent next game and      the opponent's spread
     favored by 10+ now
  S5 outdoor and kickoff wind >= N mph              under
  S6 SP+ expected margin vs spread differs by >= N  the side SP+ favors
  S7 starting QB out -> skip game                   (no data; disabled)

A game becomes a leg when at least `legs.min_signals` angles fire and none
points the opposite way in the same market (a conflict skips the game).
Lines are signed from the ESPN home team throughout: spread < 0 = home
favored. Every qualifying leg is returned (graded later as evidence per
signal), and the top `ticket.legs_per_ticket` form the day's ticket.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from ..timeutil import parse_utc
from .matching import normalize_name
from .sources import school_key

SPREAD, TOTAL = "spread", "total"


@dataclass
class GameView:
    """One game as the engine sees it at decision time."""

    event_id: str
    start_time_utc: str
    home_team: str  # ESPN display names: what legs name and grading resolves
    away_team: str
    home_school: str
    away_school: str
    neutral_site: bool
    indoor: bool | None
    odds_home: str  # the Odds API's names for the same two teams
    odds_away: str
    spread_open: float | None  # home spread, consensus
    spread_now: float | None
    total_open: float | None
    total_now: float | None
    book_rows: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)

    @property
    def matchup(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    def team_spread(self, side: str) -> float | None:
        if self.spread_now is None:
            return None
        return self.spread_now if side == "home" else -self.spread_now


@dataclass
class Signal:
    signal_id: str
    market: str  # spread | total
    side: str  # home | away | over | under
    detail: str


@dataclass
class Leg:
    event_id: str
    matchup: str
    start_time_utc: str
    market: str
    side: str
    selection: str  # team name (spread) or Over/Under (total)
    line: float
    consensus_line: float | None
    price_american: float
    price_decimal: float
    bookmaker: str
    signals: list[Signal]

    @property
    def signal_ids(self) -> str:
        return "+".join(s.signal_id for s in self.signals)

    @property
    def label(self) -> str:
        if self.market == SPREAD:
            return f"{self.selection} {self.line:+g}"
        return f"{self.selection} {self.line:g}"


@dataclass
class DayDecision:
    status: str  # ticket | no_ticket | skip
    reason: str
    qualifiers: list[Leg]
    ticket_legs: list[Leg]
    price_decimal: float | None = None
    price_american: float | None = None
    in_band: bool | None = None
    skipped_games: list[str] = field(default_factory=list)


# --- odds -> game views ------------------------------------------------------


def _key(name: str, aliases: dict[str, str]) -> str:
    n = normalize_name(name)
    return aliases.get(n, n)


def _median(values) -> float | None:
    vals = [float(v) for v in values if v is not None and not pd.isna(v)]
    if not vals:
        return None
    vals.sort()
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def _consensus(rows: pd.DataFrame, market: str, odds_home: str, odds_away: str) -> float | None:
    """Median line in the home team's terms (spread) or the Over point (total)."""
    if rows.empty:
        return None
    if market == "spreads":
        sp = rows[rows["market"] == "spreads"]
        home = _median(sp.loc[sp["outcome"] == odds_home, "point"])
        if home is not None:
            return home
        away = _median(sp.loc[sp["outcome"] == odds_away, "point"])
        return None if away is None else -away
    tot = rows[(rows["market"] == "totals") & (rows["outcome"] == "Over")]
    return _median(tot["point"])


def _first_snapshot(rows: pd.DataFrame, market: str) -> pd.DataFrame:
    """The earliest snapshot that priced this market for the event."""
    m = rows[rows["market"] == market]
    if m.empty:
        return m
    return m[m["snapshot_ts_utc"] == m["snapshot_ts_utc"].min()]


def build_views(
    games: pd.DataFrame,
    lines: pd.DataFrame,
    decision_ts: str,
    aliases: dict[str, str] | None = None,
) -> list[GameView]:
    """GameViews for every matched game priced in the decision snapshot.

    Open = the first snapshot at or before the decision that priced the
    market (lines.csv's dedupe keeps the first-seen open row per label).
    Odds home/away are re-oriented to ESPN's: neutral-site games can list
    the teams the other way round."""
    alias = {normalize_name(k): normalize_name(v) for k, v in (aliases or {}).items()}
    if lines.empty:
        return []
    lines = lines[lines["event_id"].notna()].copy()
    lines["event_id"] = lines["event_id"].astype(str)
    lines = lines[lines["snapshot_ts_utc"] <= decision_ts]
    now_rows = lines[lines["snapshot_ts_utc"] == decision_ts]
    by_id = {str(r["event_id"]): r for r in games.to_dict("records")}
    views: list[GameView] = []
    for eid, rows_now in now_rows.groupby("event_id"):
        g = by_id.get(eid)
        if g is None:
            continue
        o_home, o_away = rows_now.iloc[0]["home_team"], rows_now.iloc[0]["away_team"]
        gh, ga = _key(g["home_team"], alias), _key(g["away_team"], alias)
        if (_key(o_home, alias), _key(o_away, alias)) == (gh, ga):
            odds_home, odds_away = o_home, o_away
        elif (_key(o_home, alias), _key(o_away, alias)) == (ga, gh):
            odds_home, odds_away = o_away, o_home
        else:
            continue
        hist = lines[lines["event_id"] == eid]

        def cons(rows: pd.DataFrame, market: str, oh=odds_home, oa=odds_away) -> float | None:
            return _consensus(rows, market, oh, oa)

        views.append(
            GameView(
                event_id=eid,
                start_time_utc=str(g["start_time_utc"]),
                home_team=g["home_team"],
                away_team=g["away_team"],
                home_school=_s(g.get("home_school")),
                away_school=_s(g.get("away_school")),
                neutral_site=_b(g.get("neutral_site")),
                indoor=None if _isnull(g.get("indoor")) else _b(g.get("indoor")),
                odds_home=odds_home,
                odds_away=odds_away,
                spread_open=cons(_first_snapshot(hist, "spreads"), "spreads"),
                spread_now=cons(rows_now, "spreads"),
                total_open=cons(_first_snapshot(hist, "totals"), "totals"),
                total_now=cons(rows_now, "totals"),
                book_rows=rows_now,
            )
        )
    return views


def _isnull(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _s(v) -> str:
    return "" if _isnull(v) else str(v)


def _b(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return bool(v) and not _isnull(v)


# --- schedule context (S3 letdown, S4 look-ahead) ------------------------------


@dataclass
class TeamGame:
    start: datetime
    status: str
    team_score: float | None
    opp_score: float | None
    opp_rank: float | None


def team_schedules(
    games: pd.DataFrame, aliases: dict[str, str] | None = None
) -> dict[str, list[TeamGame]]:
    """Normalized team name -> that team's games in kickoff order."""
    alias = {normalize_name(k): normalize_name(v) for k, v in (aliases or {}).items()}
    out: dict[str, list[TeamGame]] = {}
    for r in games.to_dict("records"):
        if not r.get("start_time_utc") or _isnull(r.get("start_time_utc")):
            continue
        start = parse_utc(str(r["start_time_utc"]))
        hs, as_ = r.get("home_score"), r.get("away_score")
        for team, opp_rank, mine, theirs in (
            (r["home_team"], r.get("away_rank"), hs, as_),
            (r["away_team"], r.get("home_rank"), as_, hs),
        ):
            out.setdefault(_key(team, alias), []).append(
                TeamGame(
                    start=start,
                    status=str(r.get("status")),
                    team_score=None if _isnull(mine) else float(mine),
                    opp_score=None if _isnull(theirs) else float(theirs),
                    opp_rank=None if _isnull(opp_rank) else float(opp_rank),
                )
            )
    for lst in out.values():
        lst.sort(key=lambda t: t.start)
    return out


def _prev_game(sched: list[TeamGame], start: datetime, max_gap: timedelta) -> TeamGame | None:
    before = [t for t in sched if t.start < start and start - t.start <= max_gap]
    return before[-1] if before else None


def _next_game(sched: list[TeamGame], start: datetime, max_gap: timedelta) -> TeamGame | None:
    after = [
        t for t in sched
        if t.start > start and t.start - start <= max_gap
        and t.status not in ("Canceled", "Cancelled", "Postponed")
    ]
    return after[0] if after else None


# --- signals -------------------------------------------------------------------


def game_signals(
    v: GameView,
    cfg: dict,
    schedules: dict[str, list[TeamGame]],
    sp_ratings: dict[str, float],
    wind_mph: dict[str, float],
    aliases: dict[str, str] | None = None,
) -> list[Signal]:
    alias = {normalize_name(k): normalize_name(val) for k, val in (aliases or {}).items()}
    s = cfg["signals"]
    out: list[Signal] = []

    c = s["line_move_spread"]
    if c["enabled"] and v.spread_open is not None and v.spread_now is not None:
        move = v.spread_now - v.spread_open  # negative = toward home
        if abs(move) >= c["min_points"]:
            side = "home" if move < 0 else "away"
            out.append(Signal("S1", SPREAD, side,
                              f"spread {v.spread_open:+g} -> {v.spread_now:+g} (home)"))

    c = s["line_move_total"]
    if c["enabled"] and v.total_open is not None and v.total_now is not None:
        move = v.total_now - v.total_open
        if abs(move) >= c["min_points"]:
            out.append(Signal("S2", TOTAL, "over" if move > 0 else "under",
                              f"total {v.total_open:g} -> {v.total_now:g}"))

    start = parse_utc(v.start_time_utc)
    for sid, key in (("S3", "letdown"), ("S4", "look_ahead")):
        c = s[key]
        if not c["enabled"]:
            continue
        gap = timedelta(days=c["max_gap_days"])
        for side, team, other in (("home", v.home_team, "away"), ("away", v.away_team, "home")):
            spread = v.team_spread(side)
            if spread is None or spread > -c["min_fav_points"]:
                continue
            sched = schedules.get(_key(team, alias), [])
            if sid == "S3":
                g = _prev_game(sched, start, gap)
                fired = (
                    g is not None and g.status == "Final"
                    and g.team_score is not None and g.opp_score is not None
                    and g.team_score > g.opp_score
                    and g.opp_rank is not None and g.opp_rank <= c["max_rank"]
                )
                why = "beat a ranked team last game"
            else:
                g = _next_game(sched, start, gap)
                fired = g is not None and g.opp_rank is not None and g.opp_rank <= c["max_rank"]
                why = "ranked opponent next game"
            if fired:
                out.append(Signal(sid, SPREAD, other,
                                  f"fade {team} ({spread:+g}): {why} (#{int(g.opp_rank)})"))

    c = s["weather_wind_under"]
    wind = wind_mph.get(v.event_id)
    if c["enabled"] and v.indoor is False and wind is not None and wind >= c["min_wind_mph"]:
        out.append(Signal("S5", TOTAL, "under", f"kickoff wind {wind:.0f} mph"))

    c = s["sp_plus_edge"]
    if c["enabled"] and v.spread_now is not None:
        rh = sp_ratings.get(school_key(v.home_school)) if v.home_school else None
        ra = sp_ratings.get(school_key(v.away_school)) if v.away_school else None
        if rh is not None and ra is not None:
            hfa = 0.0 if v.neutral_site else c["home_field_points"]
            sp_margin = rh - ra + hfa  # expected home margin
            edge = sp_margin + v.spread_now  # vs the market's -spread
            if abs(edge) >= c["min_edge_points"]:
                out.append(Signal("S6", SPREAD, "home" if edge > 0 else "away",
                                  f"SP+ home margin {sp_margin:+.1f} vs spread {v.spread_now:+g}"))
    return out


# --- legs and the ticket ---------------------------------------------------------


def best_price(v: GameView, market: str, side: str) -> dict | None:
    """Best available number for the bettor among the snapshot's books:
    spread — most points for the side, then best price; under — highest
    total; over — lowest total."""
    rows = v.book_rows
    if market == SPREAD:
        name = v.odds_home if side == "home" else v.odds_away
        cand = rows[(rows["market"] == "spreads") & (rows["outcome"] == name)]
        order = [("point", False), ("price_decimal", False)]
    else:
        cand = rows[(rows["market"] == "totals") & (rows["outcome"] == side.capitalize())]
        order = [("point", side == "over"), ("price_decimal", False)]
    cand = cand.dropna(subset=["point", "price_decimal"])
    if cand.empty:
        return None
    cand = cand.sort_values([k for k, _ in order], ascending=[a for _, a in order])
    return cand.iloc[0].to_dict()


def qualify(v: GameView, signals: list[Signal], cfg: dict) -> tuple[Leg | None, str]:
    """(leg, note). A conflict in either market skips the whole game."""
    lc = cfg["legs"]
    by_market: dict[str, list[Signal]] = {}
    for sig in signals:
        by_market.setdefault(sig.market, []).append(sig)
    for market, sigs in by_market.items():
        if len({sg.side for sg in sigs}) > 1:
            ids = ", ".join(f"{sg.signal_id}->{sg.side}" for sg in sigs)
            return None, f"{v.matchup}: conflicting {market} angles ({ids}) - game skipped"
    ready = {m: sg for m, sg in by_market.items() if len(sg) >= lc["min_signals"]}
    if not ready:
        return None, ""
    if lc["same_game_legs"]:
        raise NotImplementedError("same_game_legs: true is not implemented")
    market = max(ready, key=lambda m: (len(ready[m]), m == SPREAD))
    sigs = ready[market]
    side = sigs[0].side
    bp = best_price(v, market, side)
    if bp is None:
        return None, f"{v.matchup}: no {market} price for {side}"
    if market == SPREAD:
        selection = v.home_team if side == "home" else v.away_team
        consensus = v.team_spread(side)
    else:
        selection = side.capitalize()
        consensus = v.total_now
    return Leg(
        event_id=v.event_id,
        matchup=v.matchup,
        start_time_utc=v.start_time_utc,
        market=market,
        side=side,
        selection=selection,
        line=float(bp["point"]),
        consensus_line=consensus,
        price_american=float(bp["price_american"]),
        price_decimal=float(bp["price_decimal"]),
        bookmaker=str(bp["bookmaker"]),
        signals=sigs,
    ), ""


def decimal_to_american(dec: float) -> float:
    return round((dec - 1) * 100) if dec >= 2 else round(-100 / (dec - 1))


def prior_day_lost(tickets: pd.DataFrame, legs: pd.DataFrame, strategy_id: str, day: str) -> bool:
    """True when this strategy's ticket on the previous ET day is a loss —
    settled, or still pending with a leg already lost."""
    if tickets.empty:
        return False
    prev = str((pd.Timestamp(day) - pd.Timedelta(days=1)).date())
    t = tickets[(tickets["strategy_id"] == strategy_id) & (tickets["game_date_et"] == prev)]
    if t.empty:
        return False
    if (t["status"] == "loss").any():
        return True
    ids = set(t["ticket_id"].astype(str))
    return bool((legs["ticket_id"].astype(str).isin(ids) & (legs["status"] == "loss")).any())


def decide_day(
    views: list[GameView],
    cfg: dict,
    now_utc: datetime,
    schedules: dict[str, list[TeamGame]],
    sp_ratings: dict[str, float],
    wind_mph: dict[str, float],
    tickets_today: int = 0,
    lost_yesterday: bool = False,
    aliases: dict[str, str] | None = None,
) -> DayDecision:
    limits = cfg["bet_limits"]
    if tickets_today >= limits["max_tickets_per_day"]:
        return DayDecision("skip", "daily ticket limit reached", [], [])
    if limits["skip_day_after_loss"] and lost_yesterday:
        return DayDecision("skip", "previous day's ticket lost (skip-day rule)", [], [])

    lead = timedelta(minutes=cfg["decision"]["min_lead_minutes"])
    qualifiers: list[Leg] = []
    notes: list[str] = []
    for v in sorted(views, key=lambda x: (x.start_time_utc, x.event_id)):
        if parse_utc(v.start_time_utc) - now_utc < lead:
            continue
        sigs = game_signals(v, cfg, schedules, sp_ratings, wind_mph, aliases)
        leg, note = qualify(v, sigs, cfg)
        if note:
            notes.append(note)
        if leg is not None:
            qualifiers.append(leg)

    tc = cfg["ticket"]
    if tc["selection"] != ["n_signals_desc", "kickoff_asc"]:
        raise ValueError(f"unknown ticket.selection {tc['selection']!r}")
    ranked = sorted(qualifiers, key=lambda lg: (-len(lg.signals), lg.start_time_utc, lg.event_id))
    n = tc["legs_per_ticket"]
    if len(ranked) < n:
        return DayDecision(
            "no_ticket", f"{len(ranked)} qualifying leg(s); a ticket needs {n}",
            qualifiers, [], skipped_games=notes,
        )
    legs = ranked[:n]
    dec = round(math.prod(lg.price_decimal for lg in legs), 4)
    american = decimal_to_american(dec)
    lo, hi = tc["price_band_american"]
    in_band = lo <= american <= hi
    if tc["price_band_is_hard_rule"] and not in_band:
        return DayDecision(
            "no_ticket", f"ticket +{american:g} outside the {lo}-{hi} band",
            qualifiers, [], dec, american, in_band, notes,
        )
    return DayDecision(
        "ticket", f"{len(qualifiers)} qualifying leg(s); top {n} taken",
        qualifiers, legs, dec, american, in_band, notes,
    )
