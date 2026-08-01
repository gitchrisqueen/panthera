import pandas as pd

from panthera_mvp import store
from panthera_mvp.clients import odds


def _lines_df():
    events = [
        {
            "id": "e1",
            "commence_time": "2026-08-01T23:05:00Z",
            "home_team": "Boston Red Sox",
            "away_team": "New York Yankees",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Red Sox", "price": 130},
                                {"name": "New York Yankees", "price": -155},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    df = odds.normalize(events, "2026-08-01T14:35:00Z", "open")
    df["game_date_et"] = "2026-08-01"
    df["game_pk"] = 776001
    return df


def test_append_lines_dedupes(tmp_root):
    df = _lines_df()
    assert store.append_lines(df) == 2
    # Re-running the same snapshot appends nothing.
    assert store.append_lines(df) == 0
    assert len(store.load_lines()) == 2


def test_append_picks_idempotent(tmp_root):
    pick = pd.DataFrame(
        [{c: None for c in store.PICKS_COLUMNS} | {"pick_id": "p1", "status": "pending"}]
    )
    assert store.append_picks(pick) == 1
    assert store.append_picks(pick) == 0


def test_settle_picks_only_touches_pending(tmp_root):
    picks = pd.DataFrame(
        [
            {c: None for c in store.PICKS_COLUMNS}
            | {"pick_id": "p1", "status": "pending", "stake": 100},
            {c: None for c in store.PICKS_COLUMNS}
            | {"pick_id": "p2", "status": "win", "profit": 90.91, "stake": 100},
        ]
    )
    store.append_picks(picks)
    settlements = pd.DataFrame(
        [
            {"pick_id": "p1", "status": "loss", "settled_ts_utc": "t",
             "final_score": "s", "profit": -100.0},
            {"pick_id": "p2", "status": "loss", "settled_ts_utc": "t",
             "final_score": "s", "profit": -100.0},
        ]
    )
    assert store.settle_picks(settlements) == 1  # p2 already settled
    loaded = store.load_picks().set_index("pick_id")
    assert loaded.at["p1", "status"] == "loss"
    assert loaded.at["p2", "status"] == "win"  # untouched


def test_upsert_games_replaces_by_pk(tmp_root):
    g1 = pd.DataFrame([{c: None for c in store.GAMES_COLUMNS}
                       | {"game_pk": 1, "game_date_et": "2026-08-01", "status": "Preview"}])
    store.upsert_games(g1)
    g2 = g1.copy()
    g2["status"] = "Final"
    store.upsert_games(g2)
    games = store.load_games()
    assert len(games) == 1
    assert games.iloc[0]["status"] == "Final"
