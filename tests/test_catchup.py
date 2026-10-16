"""`panthera-mvp catchup` — gap detection and the invariants around repair.

The one that must never be deleted is
`test_catchup_never_writes_picks_csv`: a backdated pick is not a forward
paper trade, so repairs belong in the quarantined shadow ledger. There is no
code path from catchup to `picks.csv`, and this is what keeps it that way.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from panthera_mvp import catchup, paths, store

REPO = Path(__file__).resolve().parents[1]

LIVE = ["pv_v3", "pv_orig", "fav_ml", "sharp_split", "fade_public"]


@pytest.fixture
def catchup_root(tmp_root):
    """`tmp_root` plus the REAL config/health.yaml, so these exercise the
    `void_pass_reasons` list that actually ships."""
    shutil.copy(REPO / "config" / "health.yaml", tmp_root / "config" / "health.yaml")
    # The ncaabase arm reads its own config; without it `catchup --sport
    # ncaabase` exits before the behaviour under test.
    shutil.copy(
        REPO / "config" / "ncaabase.yaml", tmp_root / "config" / "ncaabase.yaml"
    )
    shutil.copytree(
        REPO / "config" / "strategies", tmp_root / "config" / "strategies",
        dirs_exist_ok=True,
    )
    return tmp_root


def _pk(day: str, i: int) -> int:
    return int(day.replace("-", "")[2:]) * 100 + i


def write_games(days: dict[str, int], *, game_type: str = "R"):
    rows = [
        {
            "game_pk": _pk(day, i),
            "game_date_et": day,
            "game_type": game_type,
            "status": "Final",
            "home_score": 4,
            "away_score": 2,
            "start_time_utc": f"{day}T23:05:00Z",
            # The replay rebuilds a GameInfo from these, so a partial row
            # here fails inside replay rather than in detection.
            "day_of_week_et": "monday",
            "doubleheader": "N",
            "game_number": 1,
            "home_team_id": 111,
            "home_team": "Boston Red Sox",
            "away_team_id": 147,
            "away_team": "New York Yankees",
            "home_pitcher_era": 3.10,
            "away_pitcher_era": 2.95,
        }
        for day, n in days.items()
        for i in range(n)
    ]
    store.upsert_games(pd.DataFrame(rows))


def write_lines(days: dict[str, int]):
    """Priced rows shaped like `clients/odds.py` writes them: gap detection
    only asks whether a game_pk appears at all, but the repair path replays
    through `extract_game_prices`, which needs the real columns."""
    rows = [
        {
            "game_date_et": day,
            "snapshot_label": "pregame",
            "snapshot_ts_utc": f"{day}T20:00:00Z",
            "odds_event_id": f"ev{_pk(day, i)}",
            "game_pk": _pk(day, i),
            "commence_time_utc": f"{day}T23:05:00Z",
            "home_team": "Boston Red Sox",
            "away_team": "New York Yankees",
            "bookmaker": "bk",
            "market": "h2h",
            "outcome": "Boston Red Sox",
            "point": None,
            "price_american": -110,
            "price_decimal": 1.9091,
        }
        for day, n in days.items()
        for i in range(n)
    ]
    store.append_lines(pd.DataFrame(rows))


def write_passes(day: str, strategies: list[str], n: int, reason: str, *, offset: int = 0):
    store.append_passes(
        pd.DataFrame(
            [
                {
                    "ts_utc": f"{day}T14:41:38Z",
                    "run_label": "morning",
                    "strategy_id": sid,
                    "game_pk": _pk(day, i + offset),
                    "game_date_et": day,
                    "reason": reason,
                }
                for sid in strategies
                for i in range(n)
            ]
        )
    )


def write_picks(day: str, strategies: list[str], n: int = 1):
    from conftest import make_pick

    store.append_picks(
        pd.DataFrame(
            [
                make_pick(
                    f"{sid}-{_pk(day, i)}", "win", 66.67,
                    strategy_id=sid, game_pk=_pk(day, i),
                    settled=f"{day}T23:00:00Z",
                )
                | {"game_date_et": day}
                for sid in strategies
                for i in range(n)
            ]
        )
    )


def _gaps(day_from="2026-09-01", day_to="2026-12-31"):
    cfg = catchup.load_health_config()
    return catchup.detect_mlb_gaps(cfg, day_from, day_to)


# --------------------------------------------------------------------------
# the three states
# --------------------------------------------------------------------------


def test_never_ran_is_a_gap(catchup_root):
    """State 1: no picks and no passes at all, while priced games existed."""
    write_games({"2026-09-29": 4})
    write_lines({"2026-09-29": 4})
    gaps, partial, _ = _gaps()
    assert {g.date_et for g in gaps} == {"2026-09-29"}
    assert {g.reason for g in gaps} == {"never_ran"}
    assert not partial


def test_ran_and_legitimately_passed_is_not_a_gap(catchup_root):
    """State 2: the engine had its say. Re-running would be wrong.

    This is the case the first draft of the detector got wrong: it judged per
    GAME, so a day where a strategy legitimately picked nothing looked like a
    gap for every game outside the run's window.
    """
    write_games({"2026-09-29": 4})
    write_lines({"2026-09-29": 4})
    write_passes("2026-09-29", LIVE, 4, "[O1_off_day] saturday is an off day")
    gaps, partial, _ = _gaps()
    assert gaps == []
    assert not partial


def test_ran_under_a_corrected_config_is_a_gap(catchup_root):
    """State 3: it ran, it wrote passes, and every one came from a gate that
    no longer exists. Invisible to any "did it run?" test — this is the state
    the 2026-09-29 outage was in."""
    write_games({"2026-09-29": 4})
    write_lines({"2026-09-29": 4})
    write_passes("2026-09-29", LIVE, 4, "[R0] game_type=F")
    gaps, partial, _ = _gaps()
    assert {g.date_et for g in gaps} == {"2026-09-29"}
    assert {g.reason for g in gaps} == {"voided_config"}
    assert sorted({g.strategy_id for g in gaps}) == sorted(LIVE)


def test_one_surviving_pass_means_the_day_is_not_a_gap(catchup_root):
    """A mix of void and valid passes means the engine still had its say."""
    write_games({"2026-09-29": 4})
    write_lines({"2026-09-29": 4})
    write_passes("2026-09-29", ["pv_v3"], 2, "[R0] game_type=F")
    # offset so this does not collide with the void rows on PASSES_KEY
    write_passes("2026-09-29", ["pv_v3"], 1, "[R3] no movement signal", offset=2)
    gaps, _, _ = _gaps()
    assert "pv_v3" not in {g.strategy_id for g in gaps}


def test_unpriced_games_are_not_gaps(catchup_root):
    """A game with no captured odds could never have been evaluated, so its
    absence is never evidence of a gap."""
    write_games({"2026-09-29": 4})  # no lines at all
    gaps, _, _ = _gaps()
    assert gaps == []


def test_out_of_scope_games_are_not_gaps(catchup_root):
    """Spring training is excluded by config, so a slate of it is not a gap."""
    write_games({"2026-03-05": 4}, game_type="S")
    write_lines({"2026-03-05": 4})
    gaps, _, _ = _gaps("2026-03-01", "2026-03-31")
    assert gaps == []


def test_partial_gap_is_reported_not_acted_on(catchup_root):
    """Picks made AND void passes present: repairing would mean re-opening
    that day's pick budget, which touches picks.csv semantics."""
    write_games({"2026-09-29": 4})
    write_lines({"2026-09-29": 4})
    write_picks("2026-09-29", ["pv_v3"], 1)
    write_passes("2026-09-29", ["pv_v3"], 2, "[R0] game_type=F")
    gaps, partial, _ = _gaps()
    assert "pv_v3" not in {g.strategy_id for g in gaps}
    assert any("partial gap" in line for line in partial)


# --------------------------------------------------------------------------
# invariants
# --------------------------------------------------------------------------


def test_catchup_never_writes_picks_csv(catchup_root):
    """The invariant that must never break. Do not delete this test."""
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_picks("2026-09-28", ["pv_v3"], 1)  # so picks.csv exists
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")

    before = hashlib.sha256(paths.picks_csv().read_bytes()).hexdigest()
    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    after = hashlib.sha256(paths.picks_csv().read_bytes()).hexdigest()
    assert before == after, "catchup modified data/picks/picks.csv"


def test_completion_marker_stops_redetection(catchup_root):
    """Gap detection is otherwise not self-limiting: the repair goes to the
    shadow ledger, so picks.csv stays empty for a repaired date and the same
    gap would be re-detected forever."""
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    assert _gaps()[0], "precondition: the date is a gap"

    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    assert _gaps()[0] == [], "repaired date was detected again"


def test_marker_reopens_the_date_after_a_config_change(catchup_root):
    """Keyed on config_hash, so a later config change correctly re-opens it."""
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    assert _gaps()[0] == []

    log = store.load_catchup_log()
    log["config_hash"] = "deadbeef00"
    log.to_csv(store.catchup_log_path(), index=False)
    assert _gaps()[0], "a config change must re-open the date"


def test_rebuild_reopens_a_repaired_date(catchup_root, capsys):
    """The regression test for a `--rebuild` that could not rebuild.

    It used to drop markers for the gaps DETECTION returned, and detection
    skips any date already marked complete — so the one in-product redo
    lever could never re-open the date it was aimed at.
    """
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    assert _gaps()[0] == [], "precondition: the date is marked complete"
    capsys.readouterr()

    catchup.cmd_catchup(
        sport="mlb",
        from_et="2026-09-29",
        to_et="2026-09-29",
        rebuild=True,
        yes=True,
        dry_run=False,
        no_network=True,
    )
    out = capsys.readouterr().out
    assert "--rebuild forgot" in out
    assert "2026-09-29" in out and "gap(s)" in out, out


def test_rebuild_refuses_an_unbounded_window(catchup_root, capsys):
    """`--rebuild` over the default 45-day window would forget every marker
    the pipeline has, so it demands an explicit --from/--to."""
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    before = len(store.load_catchup_log())

    catchup.cmd_catchup(
        sport="mlb", rebuild=True, yes=True, dry_run=False, no_network=True
    )
    assert "needs an explicit --from and --to" in capsys.readouterr().out
    assert len(store.load_catchup_log()) == before


def test_rebuild_needs_yes(catchup_root, capsys):
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    before = len(store.load_catchup_log())

    catchup.cmd_catchup(
        sport="mlb",
        from_et="2026-09-29",
        to_et="2026-09-29",
        rebuild=True,
        dry_run=False,
        no_network=True,
    )
    assert "needs --yes" in capsys.readouterr().out
    assert len(store.load_catchup_log()) == before


def test_rebuild_stays_inside_the_named_strategies(catchup_root, capsys):
    """Markers are keyed per strategy; a rebuild aimed at one strategy must
    not re-open the date for the others that share it."""
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    catchup.cmd_catchup(sport="mlb", dry_run=False, no_network=True)
    others = sorted(set(store.load_catchup_log()["strategy_id"]) - {LIVE[0]})
    assert others, "precondition: more than one strategy was marked"
    capsys.readouterr()

    catchup.cmd_catchup(
        sport="mlb",
        from_et="2026-09-29",
        to_et="2026-09-29",
        strategy=[LIVE[0]],
        rebuild=True,
        yes=True,
        dry_run=True,
        no_network=True,
    )
    note = capsys.readouterr().out
    assert "--rebuild (dry run) would forget 1 marked date(s)" in note, note
    assert not store.load_catchup_log().empty, "a dry run removes nothing"

    store.drop_catchup_log("mlb", {"2026-09-29"}, strategy_ids=[LIVE[0]])
    left = sorted(set(store.load_catchup_log()["strategy_id"]))
    assert LIVE[0] not in left and left == others


def test_dry_run_writes_nothing(catchup_root):
    write_games({"2026-09-29": 2})
    write_lines({"2026-09-29": 2})
    write_passes("2026-09-29", LIVE, 2, "[R0] game_type=F")
    catchup.cmd_catchup(sport="mlb", dry_run=True, no_network=True)
    assert store.load_catchup_log().empty
    assert store.load_shadow_picks().empty


def test_window_floors_at_max_lookback_and_says_so(catchup_root):
    """A silently truncated catch-up is indistinguishable from a complete
    one, so the floor is reported."""
    cfg = catchup.load_health_config()
    (win_from, _), truncated, floor = catchup._default_window(cfg, "2020-01-01", None)
    assert truncated and win_from == floor


def test_to_defaults_to_yesterday_because_today_belongs_to_the_live_runs(
    catchup_root,
):
    """Excluding today is DELIBERATE, not an off-by-one. Do not "fix" it.

    Today's slate is still being decided: the morning run picks against the
    `open` snapshot and the pregame run against `pregame`, hours apart. A
    catch-up that included today would race them and write shadow picks for
    games the live pipeline is still working, and the shadow ledger would
    then hold retroactive rows for a day that was never actually missed.

    Pinned to exactly yesterday rather than "any earlier date", so a bug that
    moved the default a week back would fail this too.
    """
    from datetime import timedelta

    cfg = catchup.load_health_config()
    (_, win_to), _, _ = catchup._default_window(cfg, None, None)
    assert win_to == str(catchup.today_et() - timedelta(days=1))


def test_an_explicit_to_is_still_honoured(catchup_root):
    """The guard is on the DEFAULT, not a prohibition: an operator who
    deliberately passes `--to <today>` gets it, because they have chosen to
    accept the race the default avoids."""
    cfg = catchup.load_health_config()
    today = str(catchup.today_et())
    (_, win_to), _, _ = catchup._default_window(cfg, None, today)
    assert win_to == today


def test_void_prefix_match_is_substring_not_startswith(catchup_root):
    """Reasons are stored with a `[RULE_ID] ` prefix, so a startswith test
    would never match the shipped rows."""
    assert catchup._is_void("[R0] game_type=F", ("game_type=",))
    assert not catchup._is_void("[R3] no movement signal", ("game_type=",))


def test_ncaabase_catchup_touches_no_network_out_of_season(catchup_root, monkeypatch):
    """Out of season and with nothing unsettled, the arm makes no call.

    Deliberately run with `no_network=False`: passing True short-circuits the
    whole branch, so the earlier version of this test asserted nothing about
    the behaviour its name claimed.
    """
    from panthera_mvp.ncaabase import pipeline as nb

    calls: list[str] = []
    monkeypatch.setattr(nb, "refresh_date", lambda d, cfg: calls.append(d))
    catchup.cmd_catchup(sport="ncaabase", dry_run=False, no_network=False)
    assert calls == []
    assert store.load_shadow_picks().empty


def test_ncaabase_grade_is_not_season_gated(catchup_root, monkeypatch):
    """The honest limit the module note now states: only `games` is gated.

    `grade` refreshes any date that still carries an unsettled game, in any
    month — out of season it is quiet only while nothing is left unsettled.
    """
    from panthera_mvp.ncaabase import pipeline as nb
    from panthera_mvp.ncaabase import store as nb_store

    # Inside `grade.lookback_days` (3) and already started, so the date is
    # unsettled business today whatever today is; October is out of season.
    yesterday = str(catchup.today_et() - timedelta(days=1))
    nb_store.upsert_games(
        pd.DataFrame(
            [{
                "game_id": "99",
                "game_date_et": yesterday,
                "start_time_utc": f"{yesterday}T00:05:00Z",
                "home_team": "Florida St.",
                "away_team": "Miami (FL)",
                "status": "Scheduled",
            }]
        )
    )
    calls: list[str] = []
    monkeypatch.setattr(nb, "refresh_date", lambda d, cfg: calls.append(d))
    catchup.cmd_catchup(sport="ncaabase", dry_run=False, no_network=False)
    assert calls == [yesterday], calls
