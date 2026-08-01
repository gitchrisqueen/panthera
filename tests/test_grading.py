import pandas as pd

from panthera_mvp import store
from panthera_mvp.grading import grade_pending


def _pick(pick_id, market, selection, line=None, price_decimal=1.9091, status="pending"):
    return {c: None for c in store.PICKS_COLUMNS} | {
        "pick_id": pick_id,
        "game_pk": 776001,
        "game_date_et": "2026-08-01",
        "market": market,
        "selection": selection,
        "line": line,
        "price_decimal": price_decimal,
        "stake": 100,
        "status": status,
    }


def _game(status="Final", home_score=3, away_score=5):
    return {c: None for c in store.GAMES_COLUMNS} | {
        "game_pk": 776001,
        "game_date_et": "2026-08-01",
        "home_team": "Boston Red Sox",
        "away_team": "New York Yankees",
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
    }


def test_ml_win_and_loss(tmp_root):
    store.append_picks(pd.DataFrame([
        _pick("w", "ml", "New York Yankees"),
        _pick("l", "ml", "Boston Red Sox"),
    ]))
    store.upsert_games(pd.DataFrame([_game()]))
    settled = grade_pending()
    assert len(settled) == 2
    by_id = settled.set_index("pick_id")
    assert by_id.at["w", "status"] == "win"
    assert by_id.at["w", "profit"] == 90.91
    assert by_id.at["l", "status"] == "loss"
    assert by_id.at["l", "profit"] == -100.0


def test_run_line_dog_covers_losing_by_one(tmp_root):
    store.append_picks(pd.DataFrame([_pick("d", "rl", "Boston Red Sox", line=1.5)]))
    store.upsert_games(pd.DataFrame([_game(home_score=4, away_score=5)]))
    settled = grade_pending()
    assert settled.iloc[0]["status"] == "win"


def test_run_line_fav_needs_two(tmp_root):
    store.append_picks(pd.DataFrame([
        _pick("f1", "rl", "New York Yankees", line=-1.5),
    ]))
    store.upsert_games(pd.DataFrame([_game(home_score=4, away_score=5)]))  # win by 1
    settled = grade_pending()
    assert settled.iloc[0]["status"] == "loss"


def test_total_push_returns_stake(tmp_root):
    store.append_picks(pd.DataFrame([_pick("t", "total", "Over", line=8.0)]))
    store.upsert_games(pd.DataFrame([_game(home_score=3, away_score=5)]))  # total 8
    settled = grade_pending()
    assert settled.iloc[0]["status"] == "push"
    assert settled.iloc[0]["profit"] == 0.0


def test_postponed_voids(tmp_root):
    store.append_picks(pd.DataFrame([_pick("v", "ml", "New York Yankees")]))
    store.upsert_games(pd.DataFrame([
        _game(status="Postponed", home_score=None, away_score=None)
    ]))
    settled = grade_pending()
    assert settled.iloc[0]["status"] == "void"
    assert settled.iloc[0]["profit"] == 0.0


def test_unfinished_game_stays_pending(tmp_root):
    store.append_picks(pd.DataFrame([_pick("p", "ml", "New York Yankees")]))
    store.upsert_games(pd.DataFrame([
        _game(status="Live", home_score=1, away_score=0)
    ]))
    settled = grade_pending()
    assert settled.empty
    assert store.load_picks().iloc[0]["status"] == "pending"
