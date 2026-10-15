import pandas as pd

from conftest import make_pick as _pick
from panthera_mvp import paths, store
from panthera_mvp.report import write_daily_report, write_ledger_report


def test_empty_ledger_report(tmp_root, cfg):
    path = write_ledger_report(cfg)
    text = path.read_text()
    assert "No picks recorded yet" in text


def test_ledger_report_with_grades(tmp_root, cfg):
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick(
                    "b",
                    "loss",
                    -100.0,
                    rule_id="R4",
                    settled="2026-08-02T14:00:00Z",
                    game_pk=2,
                    market="rl",
                ),
                _pick("c", game_pk=3),
            ]
        )
    )
    text = write_ledger_report(cfg).read_text()
    assert "Strategy comparison" in text
    assert "1-1-0" in text
    assert "collecting (2/100)" in text  # far below 100 graded picks
    assert "R4" in text and "R3" in text
    assert "How to read this report" in text


def test_per_strategy_sections_do_not_blend(tmp_root, cfg):
    """Two strategies on the same slate get separate sections and separate
    records — the pre-registered criteria apply per strategy, never pooled."""
    (tmp_root / "config" / "strategies" / "fav_ml.yaml").write_text(
        "strategy: {id: fav_ml, engine: fav_ml, enabled: true, kind: baseline,\n"
        "  scope: [live, backtest], registered_at: '2026-08-17', hash_lineage: []}\n"
        "verdict: null\n"
        "screen: {checkpoints: [100, 200]}\n"
        "bet_limits: {max_picks_per_day: null, one_pick_per_game: true}\n"
        "staking: {flat_stake: 100}\n"
    )
    store.append_picks(
        pd.DataFrame(
            [
                _pick("pv_v2-1", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick(
                    "fav_ml-1",
                    "loss",
                    -100.0,
                    strategy_id="fav_ml",
                    rule_id="B_FAV",
                    config_hash="abcdef1234",
                    market="rl",
                ),
            ]
        )
    )
    text = write_ledger_report(cfg).read_text()
    assert "## Strategy: pv_v2" in text
    assert "## Strategy: fav_ml" in text
    assert "1-0-0" in text  # pv_v2 alone, not blended
    # Baseline: no verdict, screen only.
    assert "No verdict criteria" in text


def test_out_of_lineage_hash_renders_screen_not_verdict(tmp_root, cfg):
    """Picks under a config_hash outside hash_lineage form a SCREEN segment;
    the verdict pools only the declared lineage."""
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick(
                    "b",
                    "loss",
                    -100.0,
                    settled="2026-08-02T14:00:00Z",
                    game_pk=2,
                    config_hash="newhash9999",
                ),
            ]
        )
    )
    text = write_ledger_report(cfg).read_text()
    assert "SCREEN segment** `newhash9999`" in text
    assert "collecting data.** 1/100" in text  # verdict pool = lineage only


def test_daily_report(tmp_root, cfg):
    store.append_picks(pd.DataFrame([_pick("a")]))
    path = write_daily_report("2026-08-01", cfg, credits_note="437 remaining")
    text = path.read_text()
    assert "Today's picks" in text
    assert "NYY @ BOS" in text
    assert "437 remaining" in text
    assert path == paths.reports_dir() / "daily" / "2026-08-01.md"


def test_daily_report_two_picks_one_game_joined_rendering(tmp_root, cfg):
    """Regression for the duplicated-game_pk splits cell: the old
    `.set_index(...).loc[pk]` interpolated a DataFrame repr (garbled
    markdown, no exception). Both picks must render joined with '; ' and the
    row must stay a single line."""
    from panthera_mvp.clients import lumify

    store.append_picks(
        pd.DataFrame(
            [
                _pick("pv_v2-1", game_pk=776001),
                _pick(
                    "fav_ml-1",
                    strategy_id="fav_ml",
                    rule_id="B_FAV",
                    game_pk=776001,
                    selection="Boston Red Sox",
                ),
            ]
        )
    )
    splits = pd.DataFrame(
        [
            {
                "fetched_ts_utc": "2026-08-01T15:00:00Z",
                "game_date_et": "2026-08-01",
                "snapshot_label": "morning",
                "lumify_event_id": 5,
                "event_name": "NYY @ BOS",
                "starts_at_utc": "2026-08-01T23:05:00Z",
                "captured_at": "2026-08-01T14:55:00Z",
                "game_pk": 776001,
                "metric": "moneyline.home.bets_pct",
                "value": 40.0,
            }
        ]
    )
    lumify.append_splits(splits)
    text = write_daily_report("2026-08-01", cfg, credits_note="").read_text()
    row = [ln for ln in text.splitlines() if "moneyline.home.bets_pct" in ln]
    assert len(row) == 1
    assert "New York Yankees (pv_v2/R3); Boston Red Sox (fav_ml/B_FAV)" in row[0]


def test_passes_render_net_of_later_picks(tmp_root, cfg):
    """A morning pass followed by a pick for the same strategy+game must not
    appear in the passes section; a pass with no later pick must."""
    store.append_passes(
        pd.DataFrame(
            [
                {
                    "ts_utc": "t1",
                    "run_label": "morning",
                    "strategy_id": "pv_v2",
                    "game_pk": 1,
                    "game_date_et": "2026-08-01",
                    "reason": "[R3] no movement",
                },
                {
                    "ts_utc": "t1",
                    "run_label": "morning",
                    "strategy_id": "pv_v2",
                    "game_pk": 99,
                    "game_date_et": "2026-08-01",
                    "reason": "[R0] no matched odds event",
                },
            ]
        )
    )
    store.append_picks(pd.DataFrame([_pick("a", game_pk=1)]))
    text = write_daily_report("2026-08-01", cfg, credits_note="").read_text()
    assert "game 99" in text
    assert "game 1:" not in text  # later pick supersedes the pass


def _games(*rows) -> pd.DataFrame:
    """Minimal games.csv — only the two columns the phase lookup reads."""
    return pd.DataFrame(
        [{"game_pk": pk, "game_type": gt} for pk, gt in rows],
        columns=["game_pk", "game_type"],
    )


def test_regular_season_ledger_shows_no_postseason_caveat(tmp_root, cfg):
    """The common case stays uncluttered: no caveat and no by-phase line when
    the ledger holds nothing but regular-season picks."""
    store.upsert_games(_games((1, "R"), (2, "R")))
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick("b", "loss", -100.0, game_pk=2, settled="2026-08-02T14:00:00Z"),
            ]
        )
    )
    text = write_ledger_report(cfg).read_text()
    assert "different regime" not in text
    assert "By phase" not in text


def test_postseason_pick_adds_caveat_and_by_phase_split(tmp_root, cfg):
    """A postseason pick is pooled into the same verdict segment — the engine
    is unchanged — but the report must say the population is not like-for-like
    and show the split. Regression guard for the 2026-10-15 scope fix."""
    store.upsert_games(_games((1, "R"), (2, "L")))  # L = LCS
    store.append_picks(
        pd.DataFrame(
            [
                _pick("a", "win", 66.67, settled="2026-08-02T14:00:00Z"),
                _pick("b", "loss", -100.0, game_pk=2, settled="2026-10-14T14:00:00Z"),
            ]
        )
    )
    text = write_ledger_report(cfg).read_text()
    assert "**Postseason picks are a different regime.**" in text
    assert "- **By phase:** regular 1 graded" in text
    assert "postseason 1 graded" in text
    # Pooled, not quarantined: both picks still count in the one record.
    assert "1-1-0" in text
