"""Offline integration tests for the multi-strategy picks pipeline.

Fully network-free: MLB schedule via PANTHERA_MLB_FIXTURE, odds via
PANTHERA_ODDS_FIXTURE, and a monkeypatched clock (fixture dates never equal
the real "today", so without the clock these tests would pass vacuously on
the empty-lines early return)."""

import json
from datetime import UTC, datetime

import pytest

from panthera_mvp import store
from panthera_mvp.pipeline import cmd_picks, cmd_snapshot

FIXTURE_DATE = "2026-08-01"

FAV_ML_YAML = """\
strategy:
  id: fav_ml
  engine: fav_ml
  enabled: true
  kind: baseline
  scope: [live, backtest]
  registered_at: "2026-08-17"
  hash_lineage: []
verdict: null
screen: {checkpoints: [100, 200]}
bet_limits: {max_picks_per_day: null, one_pick_per_game: true}
staking: {flat_stake: 100}
"""


@pytest.fixture
def clock(monkeypatch):
    """Freezable clock driving pipeline.now_utc (and thus today_et)."""
    state = {"now": datetime(2026, 8, 1, 14, 50, tzinfo=UTC)}
    monkeypatch.setattr("panthera_mvp.pipeline.now_utc", lambda: state["now"])
    return state


@pytest.fixture
def multi_env(tmp_root, fixtures_dir, monkeypatch, clock):
    """Two live strategies (pv_v2 capped at 2/day + uncapped fav_ml) and both
    fixtures wired. pv_v2's cap is 2 so the per-day budget is observable."""
    sdir = tmp_root / "config" / "strategies"
    (sdir / "fav_ml.yaml").write_text(FAV_ML_YAML)
    pv = (sdir / "pv_v2.yaml").read_text().replace("max_picks_per_day: 6", "max_picks_per_day: 2")
    (sdir / "pv_v2.yaml").write_text(pv)
    monkeypatch.setenv("PANTHERA_MLB_FIXTURE", str(fixtures_dir / "mlb_schedule.json"))
    monkeypatch.setenv("PANTHERA_ODDS_FIXTURE", str(fixtures_dir / "odds_snapshot.json"))
    return tmp_root


def _snapshot(label: str, monkeypatch, tmp_root, fixtures_dir, move_team=None, move_cents=0):
    """Take a dry-run snapshot; optionally shorten `move_team`'s ML price by
    `move_cents` to create a movement signal."""
    if move_team:
        events = json.load(open(fixtures_dir / "odds_snapshot.json"))
        for ev in events:
            for book in ev["bookmakers"]:
                for market in book["markets"]:
                    if market["key"] != "h2h":
                        continue
                    for out in market["outcomes"]:
                        if out["name"] == move_team:
                            out["price"] -= move_cents  # -130 -> -150: shortened
        moved = tmp_root / f"odds_{label}.json"
        moved.write_text(json.dumps(events))
        monkeypatch.setenv("PANTHERA_ODDS_FIXTURE", str(moved))
    else:
        monkeypatch.setenv("PANTHERA_ODDS_FIXTURE", str(fixtures_dir / "odds_snapshot.json"))
    cmd_snapshot(label, dry_run=True)


def test_two_strategies_distinct_rows_and_caps(
    multi_env, fixtures_dir, monkeypatch, clock
):
    tmp_root = multi_env
    _snapshot("open", monkeypatch, tmp_root, fixtures_dir)

    # Morning-labeled run at 11:30 ET (inside the late-run grace window).
    # Fixture game 1 has an ERA edge, so pv_v2 picks it via the neutral-
    # movement dossier cascade; movement_cents MUST be 0 — the morning run's
    # endpoint is the `open` snapshot even when later labels exist. 2026-08-01
    # is a Saturday -> V slot in the corrected default day map, so the
    # ERA-favored side (a V-slot favorite) converts ML -> run line via R5.
    clock["now"] = datetime(2026, 8, 1, 15, 30, tzinfo=UTC)
    cmd_picks("23:59", run_label="morning")
    picks = store.load_picks()
    pv = picks[picks["strategy_id"] == "pv_v2"]
    assert len(pv) == 1
    assert pv.iloc[0]["pick_id"] == "pv_v2-776001-rl-20260801"
    assert pv.iloc[0]["rule_id"] == "R5"
    assert float(pv.iloc[0]["movement_cents"]) == 0.0
    assert len(picks[picks["strategy_id"] == "fav_ml"]) == 2

    # Game 2 (no ERAs, no movement) is a durable pass with its run label.
    passes = store.load_passes()
    pv_passes = passes[passes["strategy_id"] == "pv_v2"]
    assert len(pv_passes) == 1
    assert pv_passes.iloc[0]["game_pk"] == 776002
    assert pv_passes.iloc[0]["run_label"] == "morning"
    assert "no movement signal" in pv_passes.iloc[0]["reason"]

    # Midday snapshot shortens the Dodgers (game 2 favorite) by 20 cents.
    clock["now"] = datetime(2026, 8, 1, 16, 35, tzinfo=UTC)
    _snapshot(
        "midday", monkeypatch, tmp_root, fixtures_dir,
        move_team="Los Angeles Dodgers", move_cents=20,
    )

    # Manual run uses the latest label (midday): pv_v2 now sees the move on
    # game 2 and picks it. movement_cents == 20 proves the endpoint.
    clock["now"] = datetime(2026, 8, 1, 16, 40, tzinfo=UTC)
    cmd_picks("23:59", run_label="manual")
    picks = store.load_picks()
    pv = picks[picks["strategy_id"] == "pv_v2"]
    assert len(pv) == 2
    game2 = pv[pv["game_pk"] == 776002].iloc[0]
    assert float(game2["movement_cents"]) == 20.0

    # Same game carries two strategies' rows with distinct pick_ids (pv_v2's
    # is a run line here — see the R5 note above).
    game1 = picks[picks["game_pk"] == 776001]
    assert sorted(game1["pick_id"]) == [
        "fav_ml-776001-ml-20260801",
        "pv_v2-776001-rl-20260801",
    ]

    # Per-day cap counts picks already recorded today across runs: pv_v2's
    # budget (cap 2) is spent, so a later run adds nothing — the old
    # per-invocation cap would have granted a fresh budget here. fav_ml is
    # blocked per-strategy by one_pick_per_game.
    clock["now"] = datetime(2026, 8, 1, 21, 0, tzinfo=UTC)
    cmd_picks("23:59", run_label="manual")
    assert len(store.load_picks()) == 4

    # Idempotent re-run adds nothing anywhere.
    cmd_picks("23:59", run_label="manual")
    assert len(store.load_picks()) == 4


def test_engine_error_is_isolated(multi_env, fixtures_dir, monkeypatch, clock):
    tmp_root = multi_env
    _snapshot("open", monkeypatch, tmp_root, fixtures_dir)

    (tmp_root / "config" / "strategies" / "boom.yaml").write_text(
        FAV_ML_YAML.replace("id: fav_ml", "id: boom").replace("engine: fav_ml", "engine: boom")
    )

    def boom_engine(ctx):
        raise RuntimeError("kaboom")

    import panthera_mvp.pipeline as pipeline
    import panthera_mvp.strategy.registry as registry

    real = registry.engines()
    monkeypatch.setattr(pipeline, "engines", lambda: {**real, "boom": boom_engine})

    clock["now"] = datetime(2026, 8, 1, 15, 0, tzinfo=UTC)
    cmd_picks("23:59", run_label="morning")

    # boom raised, but fav_ml's slate survived and the error is durable.
    picks = store.load_picks()
    assert len(picks[picks["strategy_id"] == "fav_ml"]) == 2
    log = store.load_run_log()
    errors = log[log["kind"] == "engine_error"]
    assert len(errors) == 1
    assert "boom" in errors.iloc[0]["note"] and "kaboom" in errors.iloc[0]["note"]


def test_daily_cap_semantics_marker_in_hash(multi_env):
    """cap_semantics lives in base bet_limits and is hashed — the segment
    split between pre-fix and post-fix picks is mechanical, not manual."""
    from panthera_mvp.config import config_hash, load_strategy_configs

    cfgs = load_strategy_configs()
    pv = cfgs["pv_v2"]
    assert pv["bet_limits"]["cap_semantics"] == "per_day"
    h1 = config_hash(pv)
    import copy

    pv2 = copy.deepcopy(pv)
    pv2["bet_limits"]["cap_semantics"] = "per_invocation"
    assert config_hash(pv2) != h1
    # Metadata edits never change the hash (no self-reference).
    pv3 = copy.deepcopy(pv)
    pv3["strategy"]["hash_lineage"] = ["deadbeef00"]
    pv3["strategy"]["enabled"] = False
    pv3["verdict"] = None
    assert config_hash(pv3) == h1
