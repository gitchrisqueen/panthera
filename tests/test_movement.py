from panthera_mvp.strategy.movement import american_cost, movement_signal


def test_american_cost_orders_expensiveness():
    # -180 costs more than -160; +105 costs more than +120.
    assert american_cost(-180) > american_cost(-160)
    assert american_cost(105) > american_cost(120)
    assert american_cost(-110) > american_cost(100) > american_cost(110)


def test_shortening_favorite_is_public(cfg):
    # -160 -> -180: line got more expensive = public money.
    sig = movement_signal(-160, -180, cfg)
    assert sig.direction == "public"
    assert sig.delta_cents == 20


def test_drifting_favorite_is_vegas(cfg):
    # -180 -> -160: line pays more = Vegas.
    sig = movement_signal(-180, -160, cfg)
    assert sig.direction == "vegas"
    assert sig.delta_cents == -20


def test_positive_odds_quadrants(cfg):
    # +120 -> +105 is shortening (public); +105 -> +120 is drifting (vegas).
    assert movement_signal(120, 105, cfg).direction == "public"
    assert movement_signal(105, 120, cfg).direction == "vegas"


def test_cross_zero_movement(cfg):
    # -105 -> +115 crosses the boundary: side now pays more = vegas.
    sig = movement_signal(-105, 115, cfg)
    assert sig.direction == "vegas"


def test_small_move_is_neutral(cfg):
    # Default min_move_cents = 10; a 5-cent move is noise.
    assert movement_signal(-160, -165, cfg).direction == "neutral"


def test_missing_prices_are_neutral(cfg):
    assert movement_signal(None, -150, cfg).direction == "neutral"
    assert movement_signal(-150, None, cfg).direction == "neutral"
    assert movement_signal(-150, -150, cfg).direction == "neutral"
