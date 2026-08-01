"""The rules engine — encodes docs/sports_betting_process.md as code.

Each game yields at most one Pick. Rule IDs are recorded on every pick (and
every pass) so the ledger's by-rule breakdown shows which sub-rules carry the
strategy — that is the falsification instrument.

generate_pick operates on plain GamePrices values (not raw odds tables) so the
live pipeline and the historical backtest share this exact code path.

Rule map (doc section -> id):
  R0  §6 exclude spring training / non-regular games
  R1  §2 day/slot classification (P, V, hybrid Wednesday)
  R2  §1 line-movement signal on the favorite's ML consensus
  R3  §5 base pick: P slot backs the public side, V slot backs the Vegas side
      (neutral movement falls back through the dossier: ERA edge -> last-10
      form -> season-series lead -> pass; rule ids R3_era/R3_form/R3_series)
  R4  §6 evenly-matched public slot -> underdog run line +1.5
  R5  §6 Vegas slot favorite -> favorite run line -1.5
  R6  §6 first meeting -> ML/RL only
  R7  §6 heavy favorite (-200+) -> convert to run line (or pass)
  R8  §4 sanity veto: movement contradicted by blowout loss + ERA gap
"""

from __future__ import annotations

from dataclasses import dataclass

from ..clients.mlb import GameInfo
from ..timeutil import to_et
from .daytype import day_type, slot_type
from .dossier import Dossier
from .movement import MovementSignal, movement_signal


@dataclass
class GamePrices:
    """Consensus prices for one game. `open` = earliest snapshot of the day,
    `latest` = most recent (for the backtest: the closing line)."""

    home_ml_open: float | None
    away_ml_open: float | None
    home_ml_latest: float | None
    away_ml_latest: float | None
    home_rl_price: float | None = None  # price of home at -/+1.5
    away_rl_price: float | None = None


@dataclass
class Pick:
    pick_id: str
    game_pk: int
    odds_event_id: str
    game_date_et: str
    matchup: str
    start_time_et: str
    day_type: str
    slot_type: str
    rule_id: str
    market: str  # "ml" | "rl"
    selection: str  # team name
    line: float | None
    price_american: float
    price_decimal: float
    open_price: float | None
    latest_price: float | None
    movement_cents: float
    rationale: str


@dataclass
class Pass:
    game_pk: int
    matchup: str
    rule_id: str
    reason: str


def american_to_decimal(price: float) -> float:
    return round(1 + price / 100, 4) if price > 0 else round(1 + 100 / abs(price), 4)


def generate_pick(
    game: GameInfo,
    odds_event_id: str | None,
    prices: GamePrices | None,
    dossier: Dossier,
    cfg: dict,
) -> Pick | Pass | None:
    matchup = f"{game.away_team} @ {game.home_team}"

    # R0 — regular season, still upcoming, and priced.
    if game.game_type not in cfg["season"]["game_types"]:
        return Pass(game.game_pk, matchup, "R0", f"game_type={game.game_type}")
    if game.status != "Preview":
        return Pass(game.game_pk, matchup, "R0", f"status={game.status}")
    if odds_event_id is None or prices is None:
        return Pass(game.game_pk, matchup, "R0", "no matched odds event")

    home_ml, away_ml = prices.home_ml_latest, prices.away_ml_latest
    if home_ml is None or away_ml is None:
        return Pass(game.game_pk, matchup, "R0", "incomplete moneyline")

    home_is_fav = home_ml <= away_ml
    fav_team, fav_ml = (game.home_team, home_ml) if home_is_fav else (game.away_team, away_ml)
    dog_team, dog_ml = (game.away_team, away_ml) if home_is_fav else (game.home_team, home_ml)

    # R1 — day/slot classification. Hybrid days without a usable start time
    # cannot be slotted (historical data has no game times) — skip those.
    dtype = day_type(to_et(game.start_utc).date(), cfg)
    if dtype == "HYBRID" and game.start_utc is None:
        return Pass(game.game_pk, matchup, "R1", "hybrid day without start time")
    slot = slot_type(game.start_utc, cfg)

    # R2 — movement on the favorite's ML between open and latest.
    fav_open = prices.home_ml_open if home_is_fav else prices.away_ml_open
    signal: MovementSignal = movement_signal(fav_open, fav_ml, cfg)

    # R3 — base selection by slot type. Public money side = the favorite when
    # the favorite shortened; Vegas side = the drift beneficiary (the
    # underdog) when the favorite drifted. Neutral movement falls back to the
    # dossier's ERA edge, else pass.
    rule_id = "R3"
    if signal.direction == "public":
        selection = fav_team if slot == "P" else dog_team
        rationale_core = (
            f"fav ML shortened {signal.open_price:+.0f}->{signal.latest_price:+.0f}"
        )
    elif signal.direction == "vegas":
        selection = dog_team if slot == "V" else fav_team
        rationale_core = (
            f"fav ML drifted {signal.open_price:+.0f}->{signal.latest_price:+.0f}"
        )
    else:
        # Doc §5: "evaluate recent game outcomes, pitcher performance, and
        # trends" — the dossier cascade breaks the tie when the line is quiet.
        dcfg = cfg.get("dossier", {})
        edge = dossier.era_edge_side()
        rule_id = "R3_era"
        rationale_core = f"no movement; ERA edge {dossier.era_home} vs {dossier.era_away}"
        if edge is None:
            edge = dossier.form_edge_side(int(dcfg.get("min_last10_win_gap", 3)))
            rule_id = "R3_form"
            rationale_core = (
                f"no movement; last-10 form {dossier.last10_wins_home}"
                f"-{dossier.last10_wins_away} (home-away wins)"
            )
        if edge is None:
            edge = dossier.series_edge_side(int(dcfg.get("min_series_lead", 2)))
            rule_id = "R3_series"
            rationale_core = (
                f"no movement; season series {dossier.series_wins_home}"
                f"-{dossier.series_wins_away} (home-away)"
            )
        if edge is None:
            return Pass(
                game.game_pk, matchup, "R3", "no movement signal, no dossier edge"
            )
        selection = game.home_team if edge == "home" else game.away_team

    sel_ml = home_ml if selection == game.home_team else away_ml
    market, line = "ml", None

    # R4 — evenly matched public slot -> underdog run line +1.5.
    th = cfg["thresholds"]
    evenly_matched = abs(fav_ml) <= th["evenly_matched_max_abs_ml"] and (
        dossier.era_diff is None or dossier.era_diff <= th["evenly_matched_max_era_diff"]
    )
    if slot == "P" and evenly_matched:
        rule_id, market, line = "R4", "rl", 1.5
        selection, sel_ml = dog_team, dog_ml
        rationale_core += f"; evenly matched (fav {fav_ml:+.0f}) -> dog +1.5"

    # R5 — Vegas slot with the favorite selected -> favorite run line -1.5.
    if slot == "V" and selection == fav_team and market == "ml":
        rule_id, market, line = "R5", "rl", -1.5
        rationale_core += "; V slot favorite -> fav -1.5"

    # R6 — first meeting: ML/RL only (the MVP's pick set is already ML/RL;
    # recorded for the ledger breakdown).
    if dossier.first_meeting:
        rationale_core += "; first meeting (ML/RL only)"

    # R7 — heavy favorite handling.
    if market == "ml" and sel_ml <= -abs(th["heavy_fav_abs_ml"]):
        if th["heavy_fav_action"] == "pass":
            return Pass(game.game_pk, matchup, "R7", f"heavy favorite {sel_ml:+.0f}")
        rule_id, market, line = "R7", "rl", -1.5
        rationale_core += f"; heavy fav {sel_ml:+.0f} -> fav -1.5"

    # R8 — sanity veto (doc §4: "verify the line makes sense").
    prev_diff = (
        dossier.prev_run_diff_home
        if selection == game.home_team
        else dossier.prev_run_diff_away
    )
    sel_era = dossier.era_home if selection == game.home_team else dossier.era_away
    opp_era = dossier.era_away if selection == game.home_team else dossier.era_home
    if (
        prev_diff is not None
        and prev_diff <= -5
        and sel_era is not None
        and opp_era is not None
        and sel_era - opp_era > 1.5
    ):
        return Pass(
            game.game_pk,
            matchup,
            "R8_veto",
            f"{selection} lost last game by {-prev_diff} with ERA {sel_era} vs {opp_era}",
        )

    # Price the final selection in its final market. If the run line is not
    # priced, fall back to the moneyline version of the pick.
    if market == "rl":
        rl_price = (
            prices.home_rl_price if selection == game.home_team else prices.away_rl_price
        )
        if rl_price is None:
            market, line, price = "ml", None, sel_ml
        else:
            price = rl_price
    else:
        price = sel_ml

    start_et = to_et(game.start_utc)
    return Pick(
        pick_id=f"{game.game_pk}-{market}-{game.game_date_et.replace('-', '')}",
        game_pk=game.game_pk,
        odds_event_id=odds_event_id,
        game_date_et=game.game_date_et,
        matchup=matchup,
        start_time_et=start_et.strftime("%Y-%m-%d %H:%M"),
        day_type=dtype,
        slot_type=slot,
        rule_id=rule_id,
        market=market,
        selection=selection,
        line=line,
        price_american=price,
        price_decimal=american_to_decimal(price),
        open_price=signal.open_price,
        latest_price=signal.latest_price,
        movement_cents=signal.delta_cents,
        rationale=f"{dtype} day / {slot} slot; {rationale_core}",
    )
