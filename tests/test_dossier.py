from panthera_mvp.strategy.dossier import Dossier, SeasonContext


def _ctx() -> SeasonContext:
    ctx = SeasonContext()
    # NYY beat BOS twice, lost once; NYY crushed by TB in their latest game.
    ctx.add_final("NYY", "BOS", 5, 3)
    ctx.add_final("NYY", "BOS", 4, 2)
    ctx.add_final("BOS", "NYY", 7, 6)
    ctx.add_final("TB", "NYY", 9, 2)
    return ctx


def test_prev_run_diff_is_latest_game():
    ctx = _ctx()
    assert ctx.prev_run_diff("NYY") == -7  # lost 2-9 to TB
    assert ctx.prev_run_diff("BOS") == 1
    assert ctx.prev_run_diff("ATL") is None


def test_last_n_wins_window():
    ctx = _ctx()
    assert ctx.last_n_wins("NYY") == (2, 4)
    assert ctx.last_n_wins("NYY", n=2) == (0, 2)  # last two: loss, loss


def test_series_wins_order_independent():
    ctx = _ctx()
    assert ctx.series_wins("NYY", "BOS") == (2, 1)
    assert ctx.series_wins("BOS", "NYY") == (1, 2)
    assert ctx.series_wins("NYY", "ATL") == (0, 0)


def test_from_context_fills_dossier():
    ctx = _ctx()
    d = Dossier.from_context(ctx, home_key="BOS", away_key="NYY", era_home=4.0)
    assert d.prev_run_diff_home == 1
    assert d.prev_run_diff_away == -7
    assert d.last10_wins_home == 1 and d.last10_games_home == 3
    assert d.series_wins_home == 1 and d.series_wins_away == 2
    assert d.first_meeting is False
    fresh = Dossier.from_context(ctx, home_key="ATL", away_key="MIA")
    assert fresh.first_meeting is True


def test_form_edge_requires_gap():
    d = Dossier(last10_wins_home=7, last10_wins_away=4)
    assert d.form_edge_side(min_win_gap=3) == "home"
    assert d.form_edge_side(min_win_gap=4) is None
    assert Dossier(last10_wins_home=2, last10_wins_away=8).form_edge_side(3) == "away"
    assert Dossier().form_edge_side(3) is None


def test_series_edge_requires_lead():
    d = Dossier(series_wins_home=0, series_wins_away=3)
    assert d.series_edge_side(min_lead=2) == "away"
    assert d.series_edge_side(min_lead=4) is None
    assert Dossier().series_edge_side(2) is None
