"""CLV fill: snapshot selection, sign convention, null-when-uncovered,
exact-point run-line pricing, idempotency."""

import pandas as pd

from panthera_mvp import store
from panthera_mvp.clv import fill_clv


def _line_row(label, ts, market, outcome, price, point=float("nan")):
    return {
        "snapshot_ts_utc": ts,
        "snapshot_label": label,
        "odds_event_id": "ev1",
        "game_pk": 776001,
        "game_date_et": "2026-08-01",
        "commence_time_utc": "2026-08-01T23:05:00Z",
        "home_team": "Boston Red Sox",
        "away_team": "New York Yankees",
        "bookmaker": "dk",
        "market": market,
        "outcome": outcome,
        "point": point,
        "price_american": price,
        "price_decimal": 2.0,
    }


def _seed_game():
    store.upsert_games(
        pd.DataFrame(
            [
                {c: None for c in store.GAMES_COLUMNS}
                | {
                    "game_pk": 776001,
                    "game_date_et": "2026-08-01",
                    "start_time_utc": "2026-08-01T23:05:00Z",
                    "status": "Final",
                }
            ]
        )
    )


def _seed_pick(pick_id, market="ml", price=-140.0, line=None, created="2026-08-01T21:00:00Z"):
    store.append_picks(
        pd.DataFrame(
            [
                {c: None for c in store.PICKS_COLUMNS}
                | {
                    "pick_id": pick_id,
                    "strategy_id": pick_id.split("-")[0],
                    "created_ts_utc": created,
                    "game_date_et": "2026-08-01",
                    "game_pk": 776001,
                    "odds_event_id": "ev1",
                    "market": market,
                    "selection": "Boston Red Sox",
                    "line": line,
                    "price_american": price,
                    "stake": 100,
                    "status": "pending",
                }
            ]
        )
    )


def test_close_strictly_after_creation_and_sign(tmp_root):
    _seed_game()
    # Pick priced at the 21:00Z pregame snapshot; close at 22:20Z shortens
    # BOS -140 -> -150: the market moved against us AFTER the bet -> +10 CLV.
    lines = pd.DataFrame(
        [
            _line_row("pregame", "2026-08-01T21:00:00Z", "h2h", "Boston Red Sox", -140),
            _line_row("close", "2026-08-01T22:20:00Z", "h2h", "Boston Red Sox", -150),
        ]
    )
    store.append_lines(lines)
    _seed_pick("pv_v2-776001-ml-20260801", created="2026-08-01T21:00:00Z")
    assert fill_clv() == 1
    row = store.load_picks().iloc[0]
    assert row["close_price"] == -150
    assert row["clv_cents"] == 10.0
    # Idempotent: nulls-only fill.
    assert fill_clv() == 0


def test_uncovered_pick_stays_null(tmp_root):
    """No snapshot strictly between creation and start -> null, never zero.
    (The pregame snapshot that priced the pick must not count as its close.)"""
    _seed_game()
    store.append_lines(
        pd.DataFrame(
            [_line_row("pregame", "2026-08-01T21:00:00Z", "h2h", "Boston Red Sox", -140)]
        )
    )
    _seed_pick("pv_v2-776001-ml-20260801", created="2026-08-01T21:00:00Z")
    assert fill_clv() == 0
    row = store.load_picks().iloc[0]
    assert pd.isna(row["close_price"]) and pd.isna(row["clv_cents"])


def test_rl_close_uses_exact_point(tmp_root):
    """Alternate spread lines (±3.5 etc.) must not pollute the RL close —
    only rows at the pick's own line count."""
    _seed_game()
    lines = pd.DataFrame(
        [
            _line_row("pregame", "2026-08-01T21:00:00Z", "spreads", "Boston Red Sox", -160, 1.5),
            _line_row("close", "2026-08-01T22:20:00Z", "spreads", "Boston Red Sox", -170, 1.5),
            _line_row("close", "2026-08-01T22:20:00Z", "spreads", "Boston Red Sox", 120, 3.5),
            _line_row("close", "2026-08-01T22:20:00Z", "spreads", "Boston Red Sox", 300, -1.5),
        ]
    )
    store.append_lines(lines)
    _seed_pick(
        "pv_v2-776001-rl-20260801", market="rl", price=-160.0, line=1.5,
        created="2026-08-01T21:00:00Z",
    )
    assert fill_clv() == 1
    row = store.load_picks().iloc[0]
    assert row["close_price"] == -170  # the +3.5/-1.5 rows are ignored
    assert row["clv_cents"] == 10.0
