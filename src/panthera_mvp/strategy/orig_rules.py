"""The aligned engine (pv_orig) — a faithful reading of the source recordings
(notes/GMT20240619-014815 and GMT20240627-021203 transcripts, cited P1/P2
below), built as a StrategyContext -> Pick|Pass|None engine (registry.py).

This is deliberately a SEPARATE engine from rules.py's incumbent `pv_rules`
(pv_v2/pv_v3), not a patch to it -- the two disagree on nearly every
structural point (see docs/mvp-design.md's discrepancy list) and the
multi-strategy protocol forbids changing a live id's behavior in place.

Gate order (rule ids stamped on every Pick/Pass):
  O0  regular season, upcoming, priced                  (mirrors rules.R0)
  O1  day policy: which days play, and what they play    (P2 02:22-11:41)
  O2  slot assignment + per-day slot discipline           (strategy/slots.py,
      P1 05:23-13:44; P2 19:48 "Vegas days, Vegas slots only")
  O3  totals path (Tue/Sun primary; never on a season-first meeting)
  O4  ML/RL natural-vs-scam classification + side          (strategy/scam.py)
  O5  evenly-matched -> P slot backs the dog +1.5           (P1 40:17-41:24)
  O6  public-slot price filter: -160 or cheaper              (P1 19:32)
  O7  heavy favorite (<= -200) -> pass, never a play          (P1 83:43)
"""

from __future__ import annotations

from ..clients.mlb import GameInfo
from ..timeutil import day_of_week, to_et
from .dossier import Dossier
from .movement import TotalsPrices, american_cost
from .rules import GamePrices, Pass, Pick, american_to_decimal
from .scam import ScamSignal, classify

#: Days the engine is OFF by default -- only an outlier ("big") scam earns a
#: play (doc P2 03:04-03:53: "Thursday and Saturday can be two of the most
#: weirdest days... I would say to either take the day off or... only touch
#: it if it's a big scam").
OFF_DAYS = {"thursday", "saturday"}

#: Days whose PRIMARY market is totals rather than ML/RL (P2 02:34, 11:41).
TOTALS_PRIMARY_DAYS = {"tuesday", "sunday"}


def _big_scam(signal: ScamSignal, cfg: dict) -> bool:
    threshold = float(cfg.get("day_policy", {}).get("big_scam_min_price_delta_cents", 40))
    return signal.classification == "scam" and abs(signal.price_delta_cents) >= threshold


def _ml_rl_side(
    game: GameInfo,
    prices: GamePrices,
    dossier: Dossier,
    slot: str,
    cfg: dict,
) -> tuple[str, ScamSignal, MovementLike] | None:
    """Returns (selected_team, scam_signal, intraday_signal) or None if there
    is no qualifying signal at all (O4's "no play" outcome)."""
    home_ml, away_ml = prices.home_ml_latest, prices.away_ml_latest
    if home_ml is None or away_ml is None:
        return None
    signal = classify(dossier, home_ml, away_ml, cfg)

    # Secondary/intraday confirmation (doc P2 34:46-35:05): today's own
    # open->latest move, >= min_move_cents in the direction the slot wants.
    scfg = cfg.get("movement", {})
    min_move = float(scfg.get("min_move_cents", 5))
    intraday = None
    if prices.home_ml_open is not None and prices.away_ml_open is not None:
        home_delta = american_cost(home_ml) - american_cost(prices.home_ml_open)
        away_delta = american_cost(away_ml) - american_cost(prices.away_ml_open)
        intraday = home_delta - away_delta  # positive = home shortened vs away

    # Both branches back the side the PRICE actually moved toward -- on a
    # public slot that side agrees with merit by definition ("natural"); on a
    # Vegas slot it's the side merit does NOT support ("scam"), and the doc's
    # worked V-slot examples all back the side the market moved toward, not
    # the side the recent-form narrative would suggest (Athletics/Twins P1
    # 50:34: Twins' better record/ERA/big prior win is the "merit" side, but
    # their price LENGTHENED -- the pick was Athletics, the side the price
    # moved toward. Tigers/Nationals P1 56:26: Nationals' hot streak is
    # "merit", but their price lengthened too -- the pick was Tigers).
    if slot == "P":
        wanted_classification = "natural"
    else:
        wanted_classification = "scam"
    if signal.classification != wanted_classification or signal.price_moved_toward is None:
        return None
    if intraday is not None and abs(intraday) >= min_move:
        moved_home = intraday > 0
        if moved_home != (signal.price_moved_toward == "home"):
            return None  # intraday contradicts the primary read
    side = signal.price_moved_toward

    team = game.home_team if side == "home" else game.away_team
    return team, signal, intraday


MovementLike = float | None


def generate_pick(  # noqa: PLR0911 - a gate chain reads better flat than nested
    game: GameInfo,
    odds_event_id: str | None,
    prices: GamePrices | None,
    totals: TotalsPrices | None,
    dossier: Dossier,
    slot_type: str | None,
    cfg: dict,
) -> Pick | Pass | None:
    matchup = f"{game.away_team} @ {game.home_team}"

    # O0 — regular season, still upcoming, and priced.
    if game.game_type not in cfg["season"]["game_types"]:
        return Pass(game.game_pk, matchup, "O0", f"game_type={game.game_type}")
    if game.status != "Preview":
        return Pass(game.game_pk, matchup, "O0", f"status={game.status}")
    if odds_event_id is None or prices is None:
        return Pass(game.game_pk, matchup, "O0", "no matched odds event")
    if slot_type is None:
        return Pass(game.game_pk, matchup, "O0", "slot could not be assigned")

    dow = day_of_week(to_et(game.start_utc).date())
    day_type = cfg["day_map"][dow]

    # O2 — slot discipline (P2 19:48): a Vegas DAY only plays Vegas slots. A
    # public day plays public slots primarily; a Vegas slot on a public day
    # is allowed later, but only past the O7 big-scam gate.
    day_is_vegas = day_type == "V" or (day_type == "HYBRID" and dow == "wednesday")
    slot_mismatch = (day_type == "V" and slot_type == "P") or (
        dow == "wednesday" and slot_type == "V"
    )

    # O1 — day policy.
    market_signal: ScamSignal | None = None
    intraday: MovementLike = None
    if dow in OFF_DAYS:
        result = _ml_rl_side(game, prices, dossier, slot_type, cfg)
        if result is None or not _big_scam(result[1], cfg):
            return Pass(game.game_pk, matchup, "O1_off_day", f"{dow} is an off day, no big scam")
        selection, market_signal, intraday = result
        rule_id, rationale_core = "O1_big_scam", f"{dow} off-day big scam ({dow})"
        market, line = "ml", None
    elif dow == "wednesday" and slot_type == "V":
        result = _ml_rl_side(game, prices, dossier, slot_type, cfg)
        if result is None or not _big_scam(result[1], cfg):
            return Pass(
                game.game_pk, matchup, "O1_wed_second_half",
                "Wednesday Vegas half requires a big scam",
            )
        selection, market_signal, intraday = result
        rule_id, rationale_core = "O1_big_scam", "Wednesday 2nd-half big scam"
        market, line = "ml", None
    elif slot_mismatch:
        # Vegas day + public slot: only an "outrageous" scam earns a play
        # (P2 19:48; P2 12:07 "don't look at something and be like oh yeah
        # this is a little light scam... it needs to be something
        # outrageous").
        result = _ml_rl_side(game, prices, dossier, slot_type, cfg)
        if result is None or not _big_scam(result[1], cfg):
            return Pass(
                game.game_pk, matchup, "O2_slot_mismatch",
                f"{day_type} day, {slot_type} slot -- no outrageous scam",
            )
        selection, market_signal, intraday = result
        rule_id, rationale_core = "O2_outrageous_scam", f"{day_type} day {slot_type}-slot scam"
        market, line = "ml", None
    else:
        # Normal in-policy slot. Totals-primary days try totals first.
        if dow in TOTALS_PRIMARY_DAYS and totals is not None:
            totals_pick = _totals_pick(game, matchup, totals, dossier, day_is_vegas, cfg)
            if totals_pick is not None:
                return totals_pick
        result = _ml_rl_side(game, prices, dossier, slot_type, cfg)
        if result is None:
            return Pass(game.game_pk, matchup, "O4", "no natural/scam signal for this slot")
        selection, market_signal, intraday = result
        rule_id = "O4"
        rationale_core = f"{day_type} day / {slot_type} slot {market_signal.classification}"
        market, line = "ml", None

    sel_ml = prices.home_ml_latest if selection == game.home_team else prices.away_ml_latest

    # O5 — evenly matched public slot -> underdog run line +1.5. Confidence
    # in the RL is the source's stated reason to prefer the safer moneyline
    # on a Vegas-slot favorite pick (P1 61:02) -- so a V-slot favorite pick
    # stays ML even when evenly matched; only the P-slot dog upgrades to RL.
    th = cfg.get("thresholds", {})
    fav_ml_abs = min(abs(prices.home_ml_latest or 0), abs(prices.away_ml_latest or 0))
    evenly_matched = fav_ml_abs <= th.get("evenly_matched_max_abs_ml", 130) and (
        dossier.era_diff is None or dossier.era_diff <= th.get("evenly_matched_max_era_diff", 0.75)
    )
    if slot_type == "P" and evenly_matched and market_signal is not None:
        home_ml, away_ml = prices.home_ml_latest, prices.away_ml_latest
        if home_ml is not None and away_ml is not None:
            dog_side = "home" if home_ml > away_ml else "away"
            dog_team = game.home_team if dog_side == "home" else game.away_team
            rl_price = prices.home_rl_price if dog_side == "home" else prices.away_rl_price
            if rl_price is not None:
                selection, market, line, sel_ml = dog_team, "rl", 1.5, rl_price
                rule_id = "O5"
                rationale_core += "; evenly matched -> dog +1.5"

    # O7 — heavy favorite: pass, never a play (P1 83:43 "parlay breakers").
    # Checked before O6: it is a slot-agnostic, unconditional rule ("I
    # personally skipped a game... not touching the money line on that
    # game" -- no public/Vegas qualifier), so it is the more specific reason
    # whenever both would reject the same pick.
    heavy_abs = th.get("heavy_fav_abs_ml", 200)
    if market == "ml" and sel_ml is not None and sel_ml <= -abs(heavy_abs):
        return Pass(game.game_pk, matchup, "O7", f"heavy favorite {sel_ml:+.0f}")

    # O6 — public-slot price filter (P1 19:32, repeated 3x): "-160 or
    # cheaper" -- he will NOT bet a favorite pricier than -160 (-170, -180,
    # ...), but -160 itself, any cheaper favorite, or any dog price is fine.
    # Applies only when the FINAL slot is public. NOTE: his own Nationals @
    # Marlins worked example (P1 47:56) takes "Nationals money line minus
    # 180" -- which fails this rule under a strict reading. That tension is
    # in the source itself (the -160 line is stated as a firm, repeated
    # rule; the worked example doesn't honor it), not a bug here -- the rule
    # is kept as literally stated rather than loosened to fit one example.
    if slot_type == "P" and sel_ml is not None:
        max_public_price = th.get("public_max_abs_price", 160)
        if sel_ml < -max_public_price:
            return Pass(
                game.game_pk, matchup, "O6",
                f"public slot price {sel_ml:+.0f} more expensive than -{max_public_price}",
            )

    if sel_ml is None:
        return Pass(game.game_pk, matchup, rule_id, "selection has no price")

    start_et = to_et(game.start_utc)
    return Pick(
        pick_id=f"{game.game_pk}-{market}-{game.game_date_et.replace('-', '')}",
        game_pk=game.game_pk,
        odds_event_id=odds_event_id,
        game_date_et=game.game_date_et,
        matchup=matchup,
        start_time_et=start_et.strftime("%Y-%m-%d %H:%M"),
        day_type=day_type,
        slot_type=slot_type,
        rule_id=rule_id,
        market=market,
        selection=selection,
        line=line,
        price_american=sel_ml,
        price_decimal=american_to_decimal(sel_ml),
        open_price=(
            prices.home_ml_open if selection == game.home_team else prices.away_ml_open
        ),
        latest_price=(
            prices.home_ml_latest if selection == game.home_team else prices.away_ml_latest
        ),
        movement_cents=intraday or 0.0,
        rationale=f"{day_type} day / {slot_type} slot; {rationale_core}",
    )


def _totals_pick(
    game: GameInfo,
    matchup: str,
    totals: TotalsPrices,
    dossier: Dossier,
    day_is_vegas: bool,
    cfg: dict,
) -> Pick | Pass | None:
    """Totals path (doc P1 76:35-80:42, P2 14:51-19:05). Never on the first
    meeting of the SEASON (P1 85:38, P2 18:23) -- first meeting of a *series*
    is fine, that distinction is exactly Dossier.first_meeting."""
    if dossier.first_meeting:
        return Pass(
            game.game_pk, matchup, "O3_first_meeting",
            "no totals on a season-first meeting",
        )
    if totals.open_point is None or totals.latest_point is None:
        return None
    moved = totals.latest_point - totals.open_point
    tcfg = cfg.get("totals", {})
    min_move = float(tcfg.get("min_point_move", 0.5))
    if abs(moved) < min_move:
        return None

    # Historical scoring support for today's CURRENT total (P1 77:18, P2
    # 15:21): last-4 H2H combined runs, last-5 combined runs per side, and
    # the two starters' ERA sum. If the data supports a total meaningfully
    # BELOW where the line now sits, and the line moved UP (or vice-versa),
    # the move is unsupported -- bet the direction it moved.
    era_sum = None
    if dossier.era_home is not None and dossier.era_away is not None:
        era_sum = dossier.era_home + dossier.era_away
    supports = [
        v for v in (
            dossier.last4_h2h_combined_runs,
            dossier.last5_combined_runs_home,
            dossier.last5_combined_runs_away,
            era_sum,
        ) if v is not None
    ]
    if not supports:
        return None
    expected = sum(supports) / len(supports)
    unsupported = (moved > 0 and expected < totals.latest_point) or (
        moved < 0 and expected > totals.latest_point
    )
    if not unsupported:
        return None

    side = "over" if moved > 0 else "under"
    price = totals.over_price if side == "over" else totals.under_price
    if price is None:
        return None
    start_et = to_et(game.start_utc)
    return Pick(
        pick_id=f"{game.game_pk}-total-{game.game_date_et.replace('-', '')}",
        game_pk=game.game_pk,
        odds_event_id="",  # filled by the pipeline row builder
        game_date_et=game.game_date_et,
        matchup=matchup,
        start_time_et=start_et.strftime("%Y-%m-%d %H:%M"),
        day_type="V" if day_is_vegas else "P",
        slot_type="V" if day_is_vegas else "P",
        rule_id="O3_totals",
        market="total",
        selection=side,
        line=totals.latest_point,
        price_american=price,
        price_decimal=american_to_decimal(price),
        open_price=totals.open_point,
        latest_price=totals.latest_point,
        movement_cents=moved,
        rationale=(
            f"totals: line moved {totals.open_point}->{totals.latest_point}, "
            f"historical support {expected:.1f} contradicts the move -> {side}"
        ),
    )
