"""Golden-example tests for strategy/orig_rules.py, reproducing worked
examples from the source transcripts (P1 = notes/GMT20240619-014815, P2 =
notes/GMT20240627-021203). These are the real fidelity check: if the engine
disagrees with a worked example, the engine is wrong."""

from datetime import UTC, datetime

from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.strategy.dossier import Dossier
from panthera_mvp.strategy.movement import TotalsPrices
from panthera_mvp.strategy.orig_rules import generate_pick
from panthera_mvp.strategy.rules import GamePrices, Pass, Pick

CFG = {
    "season": {"game_types": ["R"]},
    "day_map": {
        "monday": "P",
        "tuesday": "V",
        "wednesday": "HYBRID",
        "thursday": "V",
        "friday": "P",
        "saturday": "V",
        "sunday": "V",
    },
    "hybrid_boundary_hour_et": 18,
    "movement": {"min_move_cents": 5},
    "thresholds": {
        "evenly_matched_max_abs_ml": 130,
        "evenly_matched_max_era_diff": 0.75,
        "public_max_abs_price": 160,
        "heavy_fav_abs_ml": 200,
    },
    "scam": {
        "merit_weights": {
            "season_win_gap": 1.0,
            "prev_opponent_rank_gap": 0.15,
            "last10_win_gap": 1.5,
            "ats_streak_gap": 1.0,
            "era_edge": 2.0,
        },
        "min_merit_score": 1.0,
        "min_price_delta_cents": 5.0,
    },
    "day_policy": {"big_scam_min_price_delta_cents": 60},
    "totals": {"min_point_move": 0.5},
}


def _game(home, away, start, **kw) -> GameInfo:
    defaults = dict(
        game_pk=1,
        game_date_et=start.strftime("%Y-%m-%d"),
        game_type="R",
        status="Preview",
        detailed_state="Scheduled",
        start_utc=start,
        doubleheader="N",
        game_number=1,
        home_team_id=1,
        home_team=home,
        away_team_id=2,
        away_team=away,
    )
    defaults.update(kw)
    return GameInfo(**defaults)


def test_red_sox_blue_jays_public_evenly_matched_dog_run_line():
    """P1 31:39-42:19: Red Sox @ Blue Jays, public slot. Records/ERA nearly
    even (2 wins separating); Red Sox had just beaten the #1 team (Yankees)
    while the Jays beat the #4 team -- merit favors Red Sox. Previous H2H:
    Red Sox +130 / Jays -164. Today: Red Sox +102 / Jays -122 -- Red Sox
    shortened 28pts, matching merit -> natural public movement. Evenly
    matched (fav ML -122, within 130) -> the pick was "Red Sox plus one and
    a half", not the moneyline."""
    game = _game(
        home="Toronto Blue Jays",
        away="Boston Red Sox",
        start=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),  # Monday -> P day
    )
    prices = GamePrices(
        home_ml_open=-118, away_ml_open=108,
        home_ml_latest=-122, away_ml_latest=102,
        home_rl_price=-145, away_rl_price=125,
    )
    dossier = Dossier(
        era_home=3.80, era_away=3.80,  # "very similar" -- doc doesn't cite a gap
        season_wins_home=44, season_losses_home=40,
        season_wins_away=42, season_losses_away=40,
        prev_opponent_rank_home=4, prev_opponent_rank_away=1,
        # Red Sox on a 3-game H2H covering streak (P1 39:41).
        ats_streak_home=0, ats_streak_away=3,
        prev_h2h_ml_home=-164, prev_h2h_ml_away=130,
    )
    result = generate_pick(game, "e", prices, None, dossier, "P", CFG)
    assert isinstance(result, Pick), result
    assert result.rule_id == "O5"
    assert result.market == "rl"
    assert result.line == 1.5
    assert result.selection == "Boston Red Sox"


def test_nationals_marlins_public_natural_favorite_moneyline():
    """P1 42:33-48:32: Nationals @ Marlins, public slot. Nationals: clearly
    better record (9-win gap), better ERA, just beat a much stronger
    previous opponent than the Marlins did. Previous H2H: Nationals +120;
    today: shortened -- matching merit -> natural. NOT evenly matched
    (9-win gap), so the pick stays the moneyline.

    NOTE: the documented price itself was "Nationals money line minus 180"
    (P1 47:56) -- worse than his own repeated "-160 or cheaper" public-slot
    rule (O6). That tension is in the source material, not this test: O6 is
    kept as literally, repeatedly stated rather than loosened to fit this
    one example (see the O6 comment in orig_rules.py), so this test uses a
    -155 price to isolate and verify the classification/side logic (O4)
    independently of that separate, already-covered O6 gate."""
    game = _game(
        home="Washington Nationals",
        away="Miami Marlins",
        start=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),  # Monday -> P day
    )
    prices = GamePrices(
        home_ml_open=-145, away_ml_open=125,
        home_ml_latest=-155, away_ml_latest=135,
        home_rl_price=-125, away_rl_price=105,
    )
    dossier = Dossier(
        era_home=3.20, era_away=4.60,
        season_wins_home=41, season_losses_home=32,
        season_wins_away=32, season_losses_away=41,
        prev_opponent_rank_home=1, prev_opponent_rank_away=10,
        prev_h2h_ml_home=120, prev_h2h_ml_away=-146,
    )
    result = generate_pick(game, "e", prices, None, dossier, "P", CFG)
    assert isinstance(result, Pick), result
    assert result.market == "ml"
    assert result.selection == "Washington Nationals"
    assert result.rule_id == "O4"


def test_tigers_nationals_vegas_fade_backs_the_ml_favorite():
    """P1 56:26-61:32 / P2 23:00-26:27: Tigers @ Nationals, Vegas slot.
    Nationals were on a hot streak (5-game win streak, beat a stronger
    team) yet their line got MORE expensive (inflated) -- a scam. Vegas
    slot fades the scam and backs the side merit does NOT currently
    reward: the Tigers, at their own moneyline (his stated preference over
    the run line when he "likes the -1.5", P1 61:02)."""
    game = _game(
        home="Washington Nationals",
        away="Detroit Tigers",
        start=datetime(2026, 8, 4, 23, 5, tzinfo=UTC),  # Tuesday -> V day
    )
    prices = GamePrices(
        home_ml_open=118, away_ml_open=-138,
        home_ml_latest=130, away_ml_latest=-150,
        home_rl_price=155, away_rl_price=-135,
    )
    dossier = Dossier(
        era_home=4.73, era_away=4.20,
        season_wins_home=32, season_losses_home=35,
        season_wins_away=32, season_losses_away=35,
        last10_wins_home=7, last10_games_home=10,
        last10_wins_away=4, last10_games_away=10,
        prev_h2h_ml_home=102, prev_h2h_ml_away=-122,
    )
    result = generate_pick(game, "e", prices, None, dossier, "V", CFG)
    assert isinstance(result, Pick), result
    assert result.selection == "Detroit Tigers"
    assert result.market == "ml"
    assert result.rule_id == "O4"


def test_heavy_favorite_passes_never_converts_to_run_line():
    """P1 83:43-85:17: ML <= -200 is a parlay breaker -- skip the game
    entirely, never converted to a run line (contrast with the incumbent
    pv_rules engine's R7)."""
    game = _game(
        home="Los Angeles Dodgers",
        away="Colorado Rockies",
        start=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),
    )
    prices = GamePrices(
        home_ml_open=-190, away_ml_open=165,
        home_ml_latest=-230, away_ml_latest=195,
        home_rl_price=-115, away_rl_price=-105,
    )
    dossier = Dossier(
        era_home=3.0, era_away=4.5,
        season_wins_home=50, season_losses_home=25,
        season_wins_away=25, season_losses_away=50,
        prev_h2h_ml_home=-160, prev_h2h_ml_away=140,
    )
    result = generate_pick(game, "e", prices, None, dossier, "P", CFG)
    assert isinstance(result, Pass)
    assert result.rule_id == "O7"


def test_public_slot_price_filter_rejects_expensive_favorite():
    """P1 19:32 (repeated 3x): public plays require -160 or cheaper."""
    game = _game(
        home="Boston Red Sox",
        away="New York Yankees",
        start=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),
    )
    prices = GamePrices(
        home_ml_open=-140, away_ml_open=120,
        home_ml_latest=-172, away_ml_latest=150,
        home_rl_price=-125, away_rl_price=105,
    )
    dossier = Dossier(
        era_home=3.1, era_away=4.4,
        season_wins_home=48, season_losses_home=30,
        season_wins_away=35, season_losses_away=43,
        prev_h2h_ml_home=-110, prev_h2h_ml_away=-105,
    )
    result = generate_pick(game, "e", prices, None, dossier, "P", CFG)
    assert isinstance(result, Pass)
    assert result.rule_id == "O6"


def test_thursday_is_off_without_a_big_scam():
    """P2 03:04-03:53: Thursday is an off day unless the scam is big."""
    game = _game(
        home="Washington Nationals",
        away="Detroit Tigers",
        start=datetime(2026, 8, 6, 23, 5, tzinfo=UTC),  # Thursday
    )
    prices = GamePrices(
        home_ml_open=118, away_ml_open=-138,
        home_ml_latest=125, away_ml_latest=-145,  # only a modest move
        home_rl_price=155, away_rl_price=-135,
    )
    dossier = Dossier(
        era_home=4.73, era_away=4.20,
        last10_wins_home=7, last10_games_home=10,
        last10_wins_away=4, last10_games_away=10,
        prev_h2h_ml_home=102, prev_h2h_ml_away=-122,
    )
    result = generate_pick(game, "e", prices, None, dossier, "V", CFG)
    assert isinstance(result, Pass)
    assert result.rule_id == "O1_off_day"


def test_pirates_reds_totals_bets_the_unsupported_direction():
    """P2 14:51-19:05: Pirates @ Reds. Last-4 H2H combined runs never
    exceeded 6, last-5 combined runs didn't exceed 8, ERA sum 6.94 -- all
    well under the total. The total moved UP (9.5 -> 10) anyway, which the
    presenter reads as itself the scam ("why would Vegas make it easier for
    these two teams to get another under?") and bets the direction it
    moved: the over. It hit 16 combined runs."""
    game = _game(
        home="Cincinnati Reds",
        away="Pittsburgh Pirates",
        start=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),  # Monday
    )
    totals = TotalsPrices(open_point=9.5, latest_point=10.0, over_price=-110, under_price=-110)
    dossier = Dossier(
        first_meeting=False,
        era_home=3.40, era_away=3.54,
        last5_combined_runs_home=8, last5_combined_runs_away=7,
        last4_h2h_combined_runs=6,
    )
    result = generate_pick(game, "e", None, totals, dossier, "P", CFG)
    assert result is None or isinstance(result, Pass)
    # This path is only reachable through the day-policy dispatcher on a
    # totals-primary day; Monday isn't one, so exercise _totals_pick directly.
    from panthera_mvp.strategy.orig_rules import _totals_pick

    pick = _totals_pick(game, "Pirates @ Reds", totals, dossier, day_is_vegas=False, cfg=CFG)
    assert isinstance(pick, Pick)
    assert pick.market == "total"
    assert pick.selection == "over"
    assert pick.line == 10.0


def test_totals_never_bet_on_season_first_meeting():
    """P1 85:38, P2 18:23: never bet a total on the first meeting of the
    season (first meeting of a *series* is fine -- see the other test)."""
    from panthera_mvp.strategy.orig_rules import _totals_pick

    game = _game(
        home="Cincinnati Reds",
        away="Pittsburgh Pirates",
        start=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),
    )
    totals = TotalsPrices(open_point=9.5, latest_point=10.0, over_price=-110, under_price=-110)
    dossier = Dossier(first_meeting=True)
    result = _totals_pick(game, "Pirates @ Reds", totals, dossier, day_is_vegas=False, cfg=CFG)
    assert isinstance(result, Pass)
    assert result.rule_id == "O3_first_meeting"
