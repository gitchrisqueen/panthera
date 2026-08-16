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


def _pick_row(pick_id, strategy_id="pv_v2", game_pk=1, market="ml", **kw):
    return {c: None for c in store.PICKS_COLUMNS} | {
        "pick_id": pick_id,
        "strategy_id": strategy_id,
        "game_pk": game_pk,
        "game_date_et": "2026-08-01",
        "market": market,
        "status": "pending",
    } | kw


def test_append_picks_idempotent(tmp_root):
    pick = pd.DataFrame([_pick_row("pv_v2-1-ml-20260801")])
    assert store.append_picks(pick) == 1
    # Same (strategy, game, market, date): append-once, even under a new id.
    renamed = pick.assign(pick_id="pv_v2-1-ml-20260801-x")
    assert store.append_picks(renamed) == 0


def test_second_strategy_same_game_market_is_distinct(tmp_root):
    a = pd.DataFrame([_pick_row("pv_v2-1-ml-20260801")])
    b = pd.DataFrame([_pick_row("fav_ml-1-ml-20260801", strategy_id="fav_ml")])
    assert store.append_picks(a) == 1
    assert store.append_picks(b) == 1
    assert len(store.load_picks()) == 2


def test_legacy_schema_csv_gains_new_columns(tmp_root):
    """A pre-framework 25-column picks.csv must load (and round-trip through
    append/settle) with the new columns present as nulls."""
    from panthera_mvp import paths

    legacy_cols = [
        c for c in store.PICKS_COLUMNS
        if c not in ("strategy_id", "close_price", "clv_cents")
    ]
    legacy = pd.DataFrame(
        [
            {c: None for c in legacy_cols}
            | {
                "pick_id": "824485-rl-20260801",
                "game_pk": 824485,
                "game_date_et": "2026-08-01",
                "market": "rl",
                "status": "pending",
                "stake": 100,
            }
        ]
    )
    paths.picks_csv().parent.mkdir(parents=True, exist_ok=True)
    legacy.to_csv(paths.picks_csv(), index=False)

    loaded = store.load_picks()
    assert list(loaded.columns) == store.PICKS_COLUMNS
    assert pd.isna(loaded.iloc[0]["strategy_id"])

    # Appending through the new schema keeps all columns.
    assert store.append_picks(pd.DataFrame([_pick_row("pv_v2-9-ml-20260801", game_pk=9)])) == 1
    reloaded = store.load_picks()
    assert list(reloaded.columns) == store.PICKS_COLUMNS
    assert len(reloaded) == 2


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
