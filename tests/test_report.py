import pandas as pd

from panthera_mvp import paths, store
from panthera_mvp.report import write_daily_report, write_ledger_report


def _pick(pick_id, status="pending", profit=None, rule_id="R3", settled=""):
    return {c: None for c in store.PICKS_COLUMNS} | {
        "pick_id": pick_id,
        "game_pk": 1,
        "game_date_et": "2026-08-01",
        "matchup": "NYY @ BOS",
        "start_time_et": "2026-08-01 19:05",
        "day_type": "P",
        "slot_type": "P",
        "rule_id": rule_id,
        "market": "ml",
        "selection": "New York Yankees",
        "price_american": -150,
        "price_decimal": 1.6667,
        "stake": 100,
        "movement_cents": 20,
        "rationale": "test",
        "status": status,
        "settled_ts_utc": settled,
        "profit": profit,
        "final_score": "NYY 5 - BOS 3" if status != "pending" else None,
    }


def test_empty_ledger_report(tmp_root, cfg):
    path = write_ledger_report(cfg)
    text = path.read_text()
    assert "No picks recorded yet" in text


def test_ledger_report_with_grades(tmp_root, cfg):
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick("b", "loss", -100.0, rule_id="R4", settled="2026-08-02T14:00:00Z"),
                _pick("c"),
            ]
        )
    )
    text = write_ledger_report(cfg).read_text()
    assert "1-1-0" in text
    assert "INCONCLUSIVE" in text  # far below 100 graded picks
    assert "R4" in text and "R3" in text
    assert "Pending picks:** 1" in text


def test_daily_report(tmp_root, cfg):
    store.append_picks(pd.DataFrame([_pick("a")]))
    path = write_daily_report("2026-08-01", cfg, credits_note="437 remaining")
    text = path.read_text()
    assert "Today's picks" in text
    assert "NYY @ BOS" in text
    assert "437 remaining" in text
    assert path == paths.reports_dir() / "daily" / "2026-08-01.md"
