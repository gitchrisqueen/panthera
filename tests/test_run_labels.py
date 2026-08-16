"""Stage-0 guards: snapshot-label vs picks-run-label mapping, the CLV-only
`close` label, run-note persistence, and the Lumify fetch window filters."""

import sys
import types
from datetime import UTC

import pandas as pd
import pytest

from panthera_mvp import store
from panthera_mvp.pipeline import _resolve_snapshot_label
from panthera_mvp.strategy.movement import extract_game_prices


def _lines(labels_ts: list[tuple[str, str]]) -> pd.DataFrame:
    """Minimal lines table: one h2h consensus row per (label, ts) per team."""
    rows = []
    for label, ts in labels_ts:
        for team, price in (("Home", -140), ("Away", 120)):
            rows.append(
                {
                    "snapshot_ts_utc": ts,
                    "snapshot_label": label,
                    "odds_event_id": "ev1",
                    "game_date_et": "2026-08-01",
                    "market": "h2h",
                    "outcome": team,
                    "point": float("nan"),
                    "price_american": price,
                }
            )
    return pd.DataFrame(rows)


DAY = [
    ("open", "2026-08-01T14:50:00Z"),
    ("midday", "2026-08-01T16:33:00Z"),
    ("pregame", "2026-08-01T21:00:00Z"),
    ("close", "2026-08-01T22:20:00Z"),
]


def test_morning_run_maps_to_open():
    label, degraded = _resolve_snapshot_label("morning", _lines(DAY))
    assert (label, degraded) == ("open", False)


def test_pregame_run_maps_to_pregame():
    label, degraded = _resolve_snapshot_label("pregame", _lines(DAY))
    assert (label, degraded) == ("pregame", False)


def test_manual_run_uses_latest_but_never_close():
    label, degraded = _resolve_snapshot_label("manual", _lines(DAY))
    assert (label, degraded) == ("pregame", False)


def test_missing_pregame_snapshot_degrades_to_midday():
    # Credit guard skipped the pregame snapshot: fall back to the latest
    # earlier label rather than zeroing out the slate.
    day = [t for t in DAY if t[0] != "pregame"]
    label, degraded = _resolve_snapshot_label("pregame", _lines(day))
    assert (label, degraded) == ("midday", True)


def test_no_snapshots_at_all():
    label, degraded = _resolve_snapshot_label("morning", _lines([("close", DAY[3][1])]))
    assert label is None


def test_extract_game_prices_uses_explicit_label():
    lines = _lines(DAY)
    # Make the pregame consensus differ from close so the endpoint is visible.
    lines.loc[
        (lines["snapshot_label"] == "pregame") & (lines["outcome"] == "Home"),
        "price_american",
    ] = -155
    lines.loc[
        (lines["snapshot_label"] == "close") & (lines["outcome"] == "Home"),
        "price_american",
    ] = -170
    prices = extract_game_prices(lines, "ev1", "Home", "Away", latest_label="pregame")
    assert prices.home_ml_latest == -155


def test_extract_game_prices_never_infers_close():
    lines = _lines(DAY)
    lines.loc[
        (lines["snapshot_label"] == "close") & (lines["outcome"] == "Home"),
        "price_american",
    ] = -170
    # No explicit label: inference must stop at pregame, not close.
    prices = extract_game_prices(lines, "ev1", "Home", "Away")
    assert prices.home_ml_latest == -140


def test_run_notes_persist_and_load(tmp_root):
    store.append_run_note("2026-08-01", "pregame", "late_run", "started 250 min late")
    store.append_run_note("2026-08-01", "morning", "degraded_snapshot", "no open rows")
    log = store.load_run_log()
    assert len(log) == 2
    assert set(log["kind"]) == {"late_run", "degraded_snapshot"}


class _FakeEvents:
    def __init__(self, listings: dict, splits_by_id: dict, calls: list):
        self._listings = listings
        self._splits = splits_by_id
        self.calls = calls

    def list(self, league=None, date=None, limit=None):
        return {"events": self._listings.get(date, [])}

    def splits(self, ev_id):
        self.calls.append(ev_id)
        return self._splits.get(ev_id, {"available": False})


def _install_fake_lumify(monkeypatch, listings, splits_by_id, calls):
    fake = types.ModuleType("lumify")

    class Lumify:
        def __init__(self, api_key=None):
            self.events = _FakeEvents(listings, splits_by_id, calls)

    fake.Lumify = Lumify
    fake.get_meta = lambda payload: None
    monkeypatch.setitem(sys.modules, "lumify", fake)


@pytest.fixture
def frozen_noon_et(monkeypatch):
    """Freeze 'now' at 2026-08-01 12:00 ET (16:00 UTC)."""
    from datetime import datetime

    fixed = datetime(2026, 8, 1, 16, 0, tzinfo=UTC)
    monkeypatch.setattr("panthera_mvp.clients.lumify.now_utc", lambda: fixed)
    return fixed


def test_fetch_queries_both_utc_dates_and_filters_et_day(
    tmp_root, monkeypatch, frozen_noon_et
):
    calls: list = []
    listings = {
        # UTC Aug 1 listing: an afternoon ET game + a game that already ended
        # (started before frozen now) + a game on the previous ET day.
        "2026-08-01": [
            {"id": 1, "name": "A @ B", "starts_at": "2026-08-01T17:05:00Z"},  # 13:05 ET
            {"id": 2, "name": "C @ D", "starts_at": "2026-08-01T15:00:00Z"},  # started
            {"id": 3, "name": "E @ F", "starts_at": "2026-08-01T02:10:00Z"},  # Jul 31 ET
        ],
        # UTC Aug 2 listing: the West-Coast evening game (20:40 ET Aug 1) that
        # the old single-date fetch structurally missed.
        "2026-08-02": [
            {"id": 4, "name": "G @ H", "starts_at": "2026-08-02T00:40:00Z"},
        ],
    }
    splits = {
        i: {"available": True, "captured_at": "2026-08-01T15:59:00Z", "consensus": {}}
        for i in (1, 2, 3, 4)
    }
    _install_fake_lumify(monkeypatch, listings, splits, calls)
    from panthera_mvp.clients.lumify import fetch_splits_for_date

    results, _info = fetch_splits_for_date("key", "2026-08-01", window="all")
    # Only the future games on the Aug 1 ET day get a splits call.
    assert sorted(calls) == [1, 4]
    assert {r["event"]["id"] for r in results} == {1, 4}


def test_fetch_morning_window_scopes_to_pre_1600_et(
    tmp_root, monkeypatch, frozen_noon_et
):
    calls: list = []
    listings = {
        "2026-08-01": [
            {"id": 1, "name": "A @ B", "starts_at": "2026-08-01T17:05:00Z"},  # 13:05 ET
            {"id": 5, "name": "I @ J", "starts_at": "2026-08-01T23:10:00Z"},  # 19:10 ET
        ],
    }
    splits = {
        i: {"available": True, "captured_at": "2026-08-01T15:59:00Z", "consensus": {}}
        for i in (1, 5)
    }
    _install_fake_lumify(monkeypatch, listings, splits, calls)
    from panthera_mvp.clients.lumify import fetch_splits_for_date

    results, _info = fetch_splits_for_date("key", "2026-08-01", window="morning")
    # Evening game skipped (the pregame fetch covers it fresher); one list call
    # only — the <16:00 ET window never rolls into the next UTC date.
    assert calls == [1]
