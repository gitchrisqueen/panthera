from datetime import UTC, datetime

from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.strategy.dossier import Dossier
from panthera_mvp.strategy.rules import GamePrices, Pass, Pick, generate_pick


def _game(**kw) -> GameInfo:
    defaults = dict(
        game_pk=776001,
        game_date_et="2026-08-03",  # Monday -> P day in both old and new day maps
        game_type="R",
        status="Preview",
        detailed_state="Scheduled",
        start_utc=datetime(2026, 8, 3, 23, 5, tzinfo=UTC),
        doubleheader="N",
        game_number=1,
        home_team_id=111,
        home_team="Boston Red Sox",
        away_team_id=147,
        away_team="New York Yankees",
    )
    defaults.update(kw)
    return GameInfo(**defaults)


def _prices(**kw) -> GamePrices:
    defaults = dict(
        home_ml_open=140,
        away_ml_open=-160,
        home_ml_latest=155,
        away_ml_latest=-180,
        home_rl_price=-125,
        away_rl_price=105,
    )
    defaults.update(kw)
    return GamePrices(**defaults)


def test_r0_excludes_spring_training(cfg):
    result = generate_pick(_game(game_type="S"), "e", _prices(), Dossier(), cfg)
    assert isinstance(result, Pass) and result.rule_id == "R0"


def test_r0_excludes_started_games(cfg):
    result = generate_pick(_game(status="Live"), "e", _prices(), Dossier(), cfg)
    assert isinstance(result, Pass) and result.rule_id == "R0"


def test_r0_requires_odds(cfg):
    result = generate_pick(_game(), None, None, Dossier(), cfg)
    assert isinstance(result, Pass) and result.rule_id == "R0"


def test_p_slot_public_shortening_backs_favorite(cfg):
    # Monday (P). Favorite (away, -160 -> -180) shortened = public on fav.
    result = generate_pick(_game(), "e", _prices(), Dossier(), cfg)
    assert isinstance(result, Pick)
    assert result.selection == "New York Yankees"
    assert result.rule_id == "R3"
    assert result.market == "ml"
    assert result.price_american == -180


def test_v_slot_vegas_drift_backs_underdog(cfg):
    # Sunday (V in default map). Favorite drifted -180 -> -160 = Vegas on dog.
    game = _game(
        game_date_et="2026-08-02",
        start_utc=datetime(2026, 8, 2, 23, 5, tzinfo=UTC),
    )
    prices = _prices(
        away_ml_open=-180, away_ml_latest=-160, home_ml_open=160, home_ml_latest=140
    )
    result = generate_pick(game, "e", prices, Dossier(), cfg)
    assert isinstance(result, Pick)
    assert result.selection == "Boston Red Sox"
    assert result.market == "ml"


def test_r4_evenly_matched_public_slot_takes_dog_run_line(cfg):
    # Monday (P), fav -120 (within 130), movement public.
    prices = _prices(
        away_ml_open=-105,
        away_ml_latest=-120,
        home_ml_open=-105,
        home_ml_latest=100,
        home_rl_price=-140,
    )
    result = generate_pick(_game(), "e", prices, Dossier(), cfg)
    assert isinstance(result, Pick)
    assert result.rule_id == "R4"
    assert result.market == "rl"
    assert result.line == 1.5
    assert result.selection == "Boston Red Sox"
    assert result.price_american == -140


def test_r5_vegas_slot_favorite_takes_run_line(cfg):
    # Sunday (V), favorite shortened (public) -> V slot backs the dog...
    # so to hit R5 we need the Vegas side to be the favorite, which the
    # engine only selects via the ERA fallback on neutral movement.
    game = _game(
        game_date_et="2026-08-02",
        start_utc=datetime(2026, 8, 2, 23, 5, tzinfo=UTC),
    )
    prices = _prices(
        away_ml_open=-160, away_ml_latest=-162, away_rl_price=110
    )  # movement below threshold -> neutral
    dossier = Dossier(era_home=4.5, era_away=3.0)  # away (favorite) has edge
    result = generate_pick(game, "e", prices, dossier, cfg)
    assert isinstance(result, Pick)
    assert result.rule_id == "R5"
    assert result.market == "rl"
    assert result.line == -1.5
    assert result.selection == "New York Yankees"
    assert result.price_american == 110


def test_r3_neutral_no_dossier_edge_passes(cfg):
    prices = _prices(away_ml_open=-160, away_ml_latest=-162)
    result = generate_pick(_game(), "e", prices, Dossier(), cfg)
    assert isinstance(result, Pass)
    assert result.rule_id == "R3"


def test_r3_form_fallback_on_neutral_movement(cfg):
    # No ERA data; away team is 8-2 in its last 10 vs home 3-7 -> form edge.
    prices = _prices(away_ml_open=-160, away_ml_latest=-162)
    dossier = Dossier(
        last10_wins_home=3,
        last10_games_home=10,
        last10_wins_away=8,
        last10_games_away=10,
    )
    result = generate_pick(_game(), "e", prices, dossier, cfg)
    assert isinstance(result, Pick)
    assert result.rule_id == "R3_form"
    assert result.selection == "New York Yankees"
    assert "last-10 form 3-8" in result.rationale


def test_r3_series_fallback_when_form_is_close(cfg):
    # No ERA, last-10 gap below threshold, but home leads the series 4-1.
    prices = _prices(away_ml_open=-160, away_ml_latest=-162)
    dossier = Dossier(
        last10_wins_home=5,
        last10_wins_away=6,
        series_wins_home=4,
        series_wins_away=1,
    )
    result = generate_pick(_game(), "e", prices, dossier, cfg)
    assert isinstance(result, Pick)
    assert result.rule_id == "R3_series"
    assert result.selection == "Boston Red Sox"
    assert "season series 4-1" in result.rationale


def test_era_edge_outranks_form_and_series(cfg):
    prices = _prices(away_ml_open=-160, away_ml_latest=-162)
    dossier = Dossier(
        era_home=3.0,
        era_away=5.0,
        last10_wins_home=2,
        last10_wins_away=9,
        series_wins_home=0,
        series_wins_away=5,
    )
    result = generate_pick(_game(), "e", prices, dossier, cfg)
    assert isinstance(result, Pick)
    # ERA edge (home, 3.0 < 5.0) wins the cascade despite away's superior
    # form and series lead.
    assert result.rule_id == "R3_era"
    assert result.selection == "Boston Red Sox"


def test_r7_heavy_favorite_converts_to_run_line(cfg):
    # Monday (P), fav -210 -> -230 shortened; ML pick would be -230 -> R7.
    cfg["thresholds"]["heavy_fav_action"] = "run_line"  # default is now "pass"
    prices = _prices(
        away_ml_open=-210,
        away_ml_latest=-230,
        home_ml_open=180,
        home_ml_latest=195,
        away_rl_price=-115,
    )
    result = generate_pick(_game(), "e", prices, Dossier(), cfg)
    assert isinstance(result, Pick)
    assert result.rule_id == "R7"
    assert result.market == "rl"
    assert result.line == -1.5
    assert result.price_american == -115


def test_r7_pass_mode(cfg):
    cfg["thresholds"]["heavy_fav_action"] = "pass"
    prices = _prices(
        away_ml_open=-210, away_ml_latest=-230, home_ml_open=180, home_ml_latest=195
    )
    result = generate_pick(_game(), "e", prices, Dossier(), cfg)
    assert isinstance(result, Pass) and result.rule_id == "R7"


def test_r8_veto(cfg):
    # Movement backs the Yankees, but they lost their last game by 6 and have
    # a much worse ERA -> veto.
    dossier = Dossier(
        era_home=3.0, era_away=5.0, prev_run_diff_away=-6, prev_run_diff_home=2
    )
    result = generate_pick(_game(), "e", _prices(), dossier, cfg)
    assert isinstance(result, Pass)
    assert result.rule_id == "R8_veto"


def test_rl_fallback_to_ml_when_unpriced(cfg):
    cfg["thresholds"]["heavy_fav_action"] = "run_line"  # default is now "pass"
    prices = _prices(
        away_ml_open=-210,
        away_ml_latest=-230,
        home_ml_open=180,
        home_ml_latest=195,
        away_rl_price=None,
    )
    result = generate_pick(_game(), "e", prices, Dossier(), cfg)
    assert isinstance(result, Pick)
    assert result.market == "ml"
    assert result.price_american == -230


def test_first_meeting_recorded_in_rationale(cfg):
    result = generate_pick(_game(), "e", _prices(), Dossier(first_meeting=True), cfg)
    assert isinstance(result, Pick)
    assert "first meeting" in result.rationale
