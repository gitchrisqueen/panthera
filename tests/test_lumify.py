import json

import pandas as pd

from panthera_mvp import store
from panthera_mvp.clients import lumify
from panthera_mvp.pipeline import match_splits_to_games
from panthera_mvp.report import write_daily_report


def _fixture(fixtures_dir):
    with open(fixtures_dir / "lumify_splits.json") as fh:
        return json.load(fh)


def test_normalize_flattens_consensus_paths(tmp_root, fixtures_dir):
    df = lumify.normalize(_fixture(fixtures_dir), "2026-08-01")
    assert len(df) == 10  # 6 metrics for game 1 + 4 for game 2
    yankees = df[df["lumify_event_id"] == 90001]
    away_tickets = yankees[yankees["metric"] == "moneyline.away.tickets_pct"]
    assert away_tickets.iloc[0]["value"] == 62
    assert set(df["event_name"]) == {
        "New York Yankees @ Boston Red Sox",
        "Los Angeles Dodgers @ San Diego Padres",
    }


def test_normalize_skips_unavailable_and_nonpercent(tmp_root):
    results = [
        {
            "event": {"id": 1, "name": "A @ B", "starts_at": "2026-08-01T23:00:00Z"},
            "splits": {
                "available": True,
                "consensus": {"moneyline": {"home": {"tickets_pct": 150, "note": "x"}}},
            },
        }
    ]
    df = lumify.normalize(results, "2026-08-01")
    assert df.empty  # 150 is not a percentage; strings ignored


def test_append_splits_upserts_by_key(tmp_root, fixtures_dir):
    df = lumify.normalize(_fixture(fixtures_dir), "2026-08-01")
    assert lumify.append_splits(df) == 10
    refreshed = df.copy()
    refreshed["value"] = refreshed["value"] + 1
    assert lumify.append_splits(refreshed) == 10  # re-fetch replaces same keys
    stored = lumify.load_splits()
    assert len(stored) == 10
    assert (
        stored[stored["metric"] == "moneyline.away.tickets_pct"]["value"].iloc[0] == 63
    )


def test_morning_and_pregame_snapshots_coexist(tmp_root, fixtures_dir):
    morning = lumify.normalize(_fixture(fixtures_dir), "2026-08-01", "morning")
    pregame = lumify.normalize(_fixture(fixtures_dir), "2026-08-01", "pregame")
    pregame["value"] = pregame["value"] + 5
    lumify.append_splits(morning)
    lumify.append_splits(pregame)
    stored = lumify.load_splits()
    assert len(stored) == 20  # both snapshots kept
    assert set(stored["snapshot_label"]) == {"morning", "pregame"}


def test_legacy_rows_without_label_migrate_to_manual(tmp_root, fixtures_dir):
    df = lumify.normalize(_fixture(fixtures_dir), "2026-08-01", "manual")
    legacy = df.drop(columns=["snapshot_label"])
    path = lumify.splits_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy.to_csv(path, index=False)
    fresh = lumify.normalize(_fixture(fixtures_dir), "2026-08-01", "morning")
    lumify.append_splits(fresh)
    stored = lumify.load_splits()
    assert set(stored["snapshot_label"]) == {"manual", "morning"}
    assert len(stored) == 20


def test_match_splits_to_games(tmp_root, fixtures_dir):
    df = lumify.normalize(_fixture(fixtures_dir), "2026-08-01")
    games = pd.DataFrame(
        [
            {c: None for c in store.GAMES_COLUMNS}
            | {
                "game_pk": 776001,
                "game_date_et": "2026-08-01",
                "home_team_id": 111,
                "away_team_id": 147,
            },
            {c: None for c in store.GAMES_COLUMNS}
            | {
                "game_pk": 776002,
                "game_date_et": "2026-08-01",
                "home_team_id": 135,
                "away_team_id": 119,
            },
        ]
    )
    matched = match_splits_to_games(df, games)
    assert set(matched["game_pk"].dropna()) == {776001, 776002}


def test_daily_report_includes_splits_section(tmp_root, fixtures_dir, cfg):
    df = lumify.normalize(_fixture(fixtures_dir), "2026-08-01")
    lumify.append_splits(df)
    path = write_daily_report("2026-08-01", cfg, credits_note="")
    text = path.read_text()
    assert "Public betting splits" in text
    assert "moneyline.away.tickets_pct=62" in text
    assert "New York Yankees @ Boston Red Sox" in text


def test_credit_guard(tmp_root):
    lumify.record_credits(lumify.SplitsCreditInfo(used=960, remaining=40))
    import pytest

    with pytest.raises(lumify.LumifyCreditGuardError):
        lumify.fetch_splits_for_date("lmfy-test", "2026-08-01", min_credits_reserve=50)
