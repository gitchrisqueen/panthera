"""Tests for `panthera-mvp doctor`.

The checks here were calibrated against the real live history, so the fixtures
reproduce real days rather than inventing shapes — see
tests/fixtures/health/README.md. The two that matter most:

- `test_slate_shutout_fires_on_first_day` — the outage became detectable on
  2026-09-29 and the check must fire that day, not a week later.
- `test_slate_shutout_silent_when_one_strategy_picks` — the real 2026-09-23
  near-miss, where two strategies uniform-passed while three picked. A check
  that cried on that day would be muted long before the real outage arrived.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from panthera_mvp import doctor, store

REPO = Path(__file__).resolve().parents[1]

STRATEGIES = ["pv_v3", "pv_orig", "fav_ml", "sharp_split", "fade_public"]
SPLITS_STRATEGIES = ["sharp_split", "fade_public"]
PICKING_STRATEGIES = ["fav_ml", "pv_orig", "pv_v3"]


@pytest.fixture
def health_root(tmp_root):
    """`tmp_root` plus the REAL config/health.yaml, so these tests exercise
    the thresholds that actually ship rather than convenient ones."""
    shutil.copy(REPO / "config" / "health.yaml", tmp_root / "config" / "health.yaml")
    return tmp_root


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------


def write_games(*, days: dict[str, int], game_type: str = "R", status: str = "Final"):
    """`{et_date: n_games}` -> games.csv. game_pk is deterministic per day so
    picks and passes can refer to it."""
    rows = []
    for day, n in days.items():
        for i in range(n):
            rows.append(
                {
                    "game_pk": _pk(day, i),
                    "game_date_et": day,
                    "game_type": game_type,
                    "status": status,
                    "home_score": 4,
                    "away_score": 2,
                    "start_time_utc": f"{day}T23:05:00Z",
                }
            )
    store.upsert_games(pd.DataFrame(rows))


def _pk(day: str, i: int) -> int:
    return int(day.replace("-", "")[2:]) * 100 + i


def write_passes(*, day: str, strategies: list[str], n_games: int, reason: str):
    store.append_passes(
        pd.DataFrame(
            [
                {
                    "ts_utc": f"{day}T14:41:38Z",
                    "run_label": "morning",
                    "strategy_id": sid,
                    "game_pk": _pk(day, i),
                    "game_date_et": day,
                    "reason": reason,
                }
                for sid in strategies
                for i in range(n_games)
            ]
        )
    )


def write_picks(*, day: str, strategies: list[str], n_games: int = 1, status: str = "win"):
    from conftest import make_pick

    store.append_picks(
        pd.DataFrame(
            [
                make_pick(
                    f"{sid}-{_pk(day, i)}",
                    status,
                    66.67 if status == "win" else None,
                    strategy_id=sid,
                    game_pk=_pk(day, i),
                    settled=f"{day}T23:00:00Z" if status != "pending" else "",
                )
                | {"game_date_et": day}
                for sid in strategies
                for i in range(n_games)
            ]
        )
    )


def findings(sport="mlb", **kw):
    cfg = doctor.load_health_config()
    return doctor.run_checks(sport=sport, cfg=cfg, **kw)["findings"]


def of(fs, check):
    return [f for f in fs if f.check == check]


# --------------------------------------------------------------------------
# H01 slate_shutout — the check that catches the real outage
# --------------------------------------------------------------------------


def test_slate_shutout_fires_on_first_day(health_root, monkeypatch):
    """2026-09-29: four postseason games, five strategies, zero picks, every
    pass reading the same reason key. Measured over 73 live slate days this
    pattern had zero false positives, so it alerts on day one."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-30").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    write_passes(
        day="2026-09-29",
        strategies=STRATEGIES,
        n_games=4,
        reason="[R0] excluded_game_type=F",
    )

    hits = of(findings(since="2026-09-01"), "slate_shutout")
    assert len(hits) == 1
    f = hits[0]
    assert f.level == "fail"
    assert f.fingerprint == "mlb/slate_shutout"
    assert f.since == "2026-09-29"
    assert f.evidence["reason_key"] == "excluded_game_type"
    assert f.evidence["consecutive_slate_days"] == 1
    assert sorted(f.evidence["strategies"]) == sorted(STRATEGIES)
    assert f.suggested_command == "panthera-mvp doctor --sport mlb"


def test_slate_shutout_silent_on_a_normal_day(health_root, monkeypatch):
    """2026-09-24 shape: twelve games, picks made, no passes."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-25").date())
    write_games(days={"2026-09-24": 12})
    write_picks(day="2026-09-24", strategies=PICKING_STRATEGIES, n_games=2)
    assert of(findings(since="2026-09-01"), "slate_shutout") == []


def test_slate_shutout_silent_when_one_strategy_picks(health_root, monkeypatch):
    """The real 2026-09-23 near-miss, and the check's hardest case.

    `fade_public` and `sharp_split` passed all 16 games for one shared reason
    while `fav_ml`, `pv_orig` and `pv_v3` produced picks. The pipeline was
    healthy. A shutout check that fired here would be muted within a week and
    would have been muted when the real outage came.
    """
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-24").date())
    write_games(days={"2026-09-23": 16})
    write_passes(
        day="2026-09-23",
        strategies=SPLITS_STRATEGIES,
        n_games=16,
        reason="[FP_ml] no-splits: none captured for game",
    )
    write_picks(day="2026-09-23", strategies=PICKING_STRATEGIES, n_games=2)

    assert of(findings(since="2026-09-01"), "slate_shutout") == []


def test_slate_shutout_needs_min_strategies(health_root, monkeypatch):
    """With one strategy running, "they all agree" is not evidence."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-30").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    write_passes(
        day="2026-09-29", strategies=["pv_v3"], n_games=4, reason="[R0] excluded_game_type=F"
    )
    assert of(findings(since="2026-09-01"), "slate_shutout") == []


def test_slate_shutout_ignores_a_resolved_streak(health_root, monkeypatch):
    """A shutout that already recovered is history, not an alert."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-01").date())
    write_games(days={"2026-09-29": 4, "2026-09-30": 4}, game_type="F")
    write_passes(
        day="2026-09-29", strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
    )
    write_picks(day="2026-09-30", strategies=PICKING_STRATEGIES, n_games=1)
    assert of(findings(since="2026-09-01"), "slate_shutout") == []


# --------------------------------------------------------------------------
# H02 uniform_pass
# --------------------------------------------------------------------------


def _uniform_run(days: list[str], picking: list[str] | None = None):
    """A uniform-pass run for the splits strategies over `days`. `picking`
    keeps H01 quiet so H02 is what is under test."""
    write_games(days=dict.fromkeys(days, 4))
    for day in days:
        write_passes(
            day=day,
            strategies=SPLITS_STRATEGIES,
            n_games=4,
            reason="[FP_ml] no-splits: none captured for game",
        )
        write_picks(day=day, strategies=picking or PICKING_STRATEGIES, n_games=1)


def test_uniform_pass_silent_below_threshold(health_root, monkeypatch):
    """Two consecutive days is the longest run measured as LEGITIMATE in the
    pre-outage history, so it must not alert."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-25").date())
    _uniform_run(["2026-09-23", "2026-09-24"])
    assert of(findings(since="2026-09-01"), "uniform_pass") == []


def test_uniform_pass_warns_at_three(health_root, monkeypatch):
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-26").date())
    _uniform_run(["2026-09-23", "2026-09-24", "2026-09-25"])
    hits = of(findings(since="2026-09-01"), "uniform_pass")
    assert len(hits) == 1
    assert hits[0].level == "warn"
    assert hits[0].evidence["max_consecutive_slate_days"] == 3


def test_uniform_pass_fails_at_four(health_root, monkeypatch):
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-27").date())
    _uniform_run(["2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26"])
    hits = of(findings(since="2026-09-01"), "uniform_pass")
    assert len(hits) == 1 and hits[0].level == "fail"


def test_uniform_pass_counts_slate_days_not_calendar_days(health_root, monkeypatch):
    """2026-09-28, 10-02 and 10-09 had no games at all. A calendar-day counter
    resets on every off-day, which would have scored the real 14-day outage as
    three short runs and alerted on none of them."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-05").date())
    # Three slate days spanning eight calendar days, with gaps between each.
    _uniform_run(["2026-09-27", "2026-09-30", "2026-10-04"])
    hits = of(findings(since="2026-09-01"), "uniform_pass")
    assert len(hits) == 1, "off-days must not reset the streak"
    assert hits[0].evidence["max_consecutive_slate_days"] == 3


def test_uniform_pass_is_one_finding_per_sport(health_root, monkeypatch):
    """`fingerprint` is sport/check and the issue reconciler treats it as an
    identity, so several strategies must aggregate into ONE finding or they
    would collapse into one arbitrary issue."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-26").date())
    _uniform_run(["2026-09-23", "2026-09-24", "2026-09-25"])
    hits = of(findings(since="2026-09-01"), "uniform_pass")
    assert len(hits) == 1
    assert sorted(hits[0].evidence["strategies"]) == sorted(SPLITS_STRATEGIES)


def test_uniform_pass_dropped_when_shutout_covers_the_same_cause(health_root, monkeypatch):
    """One cause, one alert. H01 already reports that every strategy fell
    silent for this reason; repeating it per strategy is the same alert twice,
    and noise is how a health check gets muted."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-01").date())
    days = ["2026-09-27", "2026-09-29", "2026-09-30"]
    write_games(days=dict.fromkeys(days, 4), game_type="F")
    for day in days:
        write_passes(
            day=day, strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
        )
    fs = findings(since="2026-09-01")
    assert len(of(fs, "slate_shutout")) == 1
    assert of(fs, "uniform_pass") == [], "H02 must not duplicate H01's cause"


# --------------------------------------------------------------------------
# idle, availability, and the other checks
# --------------------------------------------------------------------------


def test_idle_sport_is_never_a_failure(health_root, monkeypatch):
    """Out of season nothing is wrong. A tool that cries through every
    offseason is a tool nobody reads."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-12-20").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    write_passes(
        day="2026-09-29", strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
    )
    result = doctor.run_checks(sport="mlb", cfg=doctor.load_health_config(), since="2026-09-01")
    assert [s["state"] for s in result["sports"]] == ["idle"]

    # Only the WINDOW checks go quiet. H07/H08/H09 measure correctness rather
    # than activity and must keep their level out of season — a strategy whose
    # hash left its lineage is just as broken in December.
    window = {"slate_shutout", "uniform_pass", "data_staleness", "snapshot_coverage",
              "pending_age", "unmatched_slate"}
    noisy = [f for f in result["findings"] if f.check in window and f.level in ("fail", "warn")]
    assert not noisy, f"window checks must be informational when idle: {noisy}"


def test_absent_sport_is_a_finding_not_a_crash(health_root, monkeypatch):
    """data/ncaabase/ does not exist in this repo. doctor must say so, not
    traceback — one unset sport cannot be allowed to hide the others."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-05-01").date())
    result = doctor.run_checks(
        sport="ncaabase", cfg=doctor.load_health_config(), since="2026-04-01"
    )
    assert doctor.exit_code(result["findings"]) != doctor.EXIT_BROKEN
    assert all(f.level != "fail" for f in result["findings"])


def test_pending_age_explains_a_scoreless_final(health_root, monkeypatch):
    """A game that is Final with no score can never settle, however often the
    grader runs. Saying which game, and why, is the difference between a
    useful finding and 'something is stale'."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-15").date())
    # A recent slate day keeps MLB ACTIVE; otherwise the sport reads as idle
    # and every window finding is informational. This mirrors the live repo,
    # where games run to 2026-10-14 while a pick from 09-27 is still pending.
    write_games(days={"2026-10-14": 2}, game_type="L")
    store.upsert_games(
        pd.DataFrame(
            [
                {
                    "game_pk": _pk("2026-09-27", 0),
                    "game_date_et": "2026-09-27",
                    "game_type": "R",
                    "status": "Final",
                    "home_score": None,
                    "away_score": None,
                    "start_time_utc": "2026-09-27T23:05:00Z",
                }
            ]
        )
    )
    write_picks(day="2026-09-27", strategies=["pv_v3"], status="pending")
    write_picks(day="2026-10-14", strategies=["pv_v3"], n_games=2)

    hits = of(findings(since="2026-09-01"), "pending_age")
    assert len(hits) == 1
    assert hits[0].level == "fail"  # 18 days > fail_days 7
    assert "no score recorded" in hits[0].detail
    assert hits[0].evidence["scoreless_final_games"] == [_pk("2026-09-27", 0)]


def test_pending_age_does_not_prescribe_grade_for_a_suspended_game(
    health_root, monkeypatch
):
    """A suspended game is resumed under the same game_pk, so its picks are
    correctly pending and `grade` cannot change that.

    H05 used to recognise only `Final` with no score, so it reported a
    suspended game as a stalled grader and told the operator to run
    `panthera-mvp grade --date ...` — a no-op. An alert that prescribes a
    no-op trains the operator to ignore it (doctor's own rule).
    """
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-15").date())
    write_games(days={"2026-10-14": 2}, game_type="L")
    store.upsert_games(
        pd.DataFrame(
            [
                {
                    "game_pk": _pk("2026-09-27", 0),
                    "game_date_et": "2026-09-27",
                    "game_type": "R",
                    "status": "Suspended",
                    "home_score": None,
                    "away_score": None,
                    "start_time_utc": "2026-09-27T23:05:00Z",
                }
            ]
        )
    )
    write_picks(day="2026-09-27", strategies=["pv_v3"], status="pending")
    write_picks(day="2026-10-14", strategies=["pv_v3"], n_games=2)

    hits = of(findings(since="2026-09-01"), "pending_age")
    assert len(hits) == 1
    pk = _pk("2026-09-27", 0)
    assert f"game {pk} is Suspended with no score recorded" in hits[0].detail
    assert "resumed under the same game_pk" in hits[0].detail
    # The dead-end advice is gone, and so is the one that cannot work here.
    assert "score is backfilled" not in hits[0].detail
    assert hits[0].suggested_command is None


def test_pending_age_keeps_grade_when_one_game_can_still_be_backfilled(
    health_root, monkeypatch
):
    """A MIXED date: one suspended game and one scoreless `Final`.

    The suspended one is waiting on a resumption; the Final one is a fault that
    something must backfill. A single verdict for both prescribed a no-op for
    the suspended half, so the detail is per game, and `grade` is offered
    because it can still change the Final row.
    """
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-15").date())
    write_games(days={"2026-10-14": 2}, game_type="L")
    rows = []
    for i, status in enumerate(("Suspended", "Final")):
        rows.append(
            {
                "game_pk": _pk("2026-09-27", i),
                "game_date_et": "2026-09-27",
                "game_type": "R",
                "status": status,
                "home_score": None,
                "away_score": None,
                "start_time_utc": "2026-09-27T23:05:00Z",
            }
        )
    store.upsert_games(pd.DataFrame(rows))
    write_picks(day="2026-09-27", strategies=["pv_v3"], n_games=2, status="pending")
    write_picks(day="2026-10-14", strategies=["pv_v3"], n_games=2)

    hits = of(findings(since="2026-09-01"), "pending_age")
    assert len(hits) == 1
    detail = hits[0].detail
    susp, final = _pk("2026-09-27", 0), _pk("2026-09-27", 1)
    # Each game carries its OWN reason.
    assert f"game {susp} is Suspended" in detail
    assert "resumed under the same game_pk" in detail
    assert f"game {final} is Final" in detail
    assert "score is backfilled" in detail
    # `grade` is still worth running: it can change the Final row.
    assert hits[0].suggested_command is not None
    assert "grade --date 2026-09-27" in hits[0].suggested_command


def test_lineage_drift_detects_an_undeclared_hash(health_root, monkeypatch):
    """A live strategy whose current hash left its own lineage has its verdict
    countdown frozen — the half-finished state of a config change."""
    sdir = health_root / "config" / "strategies"
    text = (sdir / "pv_v2.yaml").read_text()
    (sdir / "pv_v2.yaml").write_text(
        text.replace("enabled: true", "enabled: true").replace(
            "hash_lineage: [6f0d0924d4]", "hash_lineage: [deadbeef99]"
        )
    )
    hits = of(doctor.check_lineage_drift(doctor.load_health_config()), "lineage_drift")
    assert [f.level for f in hits] == ["fail"]
    assert hits[0].evidence["hash_lineage"] == ["deadbeef99"]


def test_empty_lineage_is_not_drift(health_root):
    """`hash_lineage: []` means "pool every hash" (report.py), not
    "undeclared". Treating it as drift would alert forever on the baselines."""
    sdir = health_root / "config" / "strategies"
    text = (sdir / "pv_v2.yaml").read_text()
    (sdir / "pv_v2.yaml").write_text(text.replace("hash_lineage: [6f0d0924d4]", "hash_lineage: []"))
    assert doctor.check_lineage_drift(doctor.load_health_config()) == []


def test_config_sanity_reports_a_retired_key(health_root):
    """strategy/season.py's tripwire surfaces as an alert, not a crashed cron."""
    cfgp = health_root / "config" / "strategy.yaml"
    cfgp.write_text(
        cfgp.read_text().replace(
            'exclude_game_types: ["S", "E", "A", "I"]', 'game_types: ["R"]'
        )
    )
    hits = of(doctor.check_config_sanity(doctor.load_health_config()), "config_sanity")
    assert [f.level for f in hits] == ["fail"]
    assert "retired" in hits[0].detail


# --------------------------------------------------------------------------
# contract with the workflow: exit codes, JSON shape, fingerprints
# --------------------------------------------------------------------------


def test_exit_codes(health_root):
    ok = []
    warn = [doctor.Finding("H0", "c", "mlb", "warn", "t")]
    fail = [doctor.Finding("H0", "c", "mlb", "fail", "t")]
    assert doctor.exit_code(ok) == doctor.EXIT_OK
    assert doctor.exit_code(warn) == doctor.EXIT_WARN
    assert doctor.exit_code(fail) == doctor.EXIT_FAIL
    assert doctor.exit_code(warn, strict=True) == doctor.EXIT_FAIL
    assert doctor.exit_code(fail, strict=True) == doctor.EXIT_FAIL
    assert doctor.exit_code([*warn, *fail]) == doctor.EXIT_FAIL


def test_exit_zero_always_returns_zero(health_root, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-30").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    write_passes(
        day="2026-09-29", strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
    )
    assert doctor.cmd_doctor(sport="mlb") == doctor.EXIT_FAIL
    assert doctor.cmd_doctor(sport="mlb", exit_zero=True) == doctor.EXIT_OK


def test_missing_health_config_exits_broken(tmp_root, capsys):
    """Exit 3, never 0: "doctor could not run" must not read as "nothing
    wrong". tmp_root deliberately has no health.yaml."""
    assert doctor.cmd_doctor() == doctor.EXIT_BROKEN
    assert "cannot run" in capsys.readouterr().out


def test_json_carries_every_key_the_workflow_reads(health_root, monkeypatch, capsys):
    """.github/workflows/health.yml's reconciler reads these by name; renaming
    one silently stops the alerting rather than failing loudly."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-30").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    write_passes(
        day="2026-09-29", strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
    )
    doctor.cmd_doctor(sport="mlb", as_json=True, exit_zero=True)
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema"] == 1
    for key in ("generated_ts_utc", "today_et", "exit_code", "summary", "findings"):
        assert key in payload
    assert set(payload["summary"]) == {"fail", "warn", "info"}
    for f in payload["findings"]:
        for key in (
            "id",
            "check",
            "sport",
            "level",
            "fingerprint",
            "title",
            "detail",
            "evidence",
            "suggested_command",
        ):
            assert key in f, f"workflow reads `{key}`"
        assert f["level"] in doctor.LEVELS


def test_fingerprints_are_unique_within_a_run(health_root, monkeypatch):
    """The reconciler keeps one open issue per fingerprint, so two findings
    sharing one would make a run's alerting non-deterministic."""
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-10-01").date())
    days = ["2026-09-27", "2026-09-29", "2026-09-30"]
    write_games(days=dict.fromkeys(days, 4), game_type="F")
    for day in days:
        write_passes(
            day=day, strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
        )
    write_picks(day="2026-09-27", strategies=["pv_v3"], status="pending")

    fs = findings(sport="all", since="2026-09-01")
    prints = [f.fingerprint for f in fs]
    assert len(prints) == len(set(prints)), f"duplicate fingerprints: {prints}"


def test_doctor_makes_no_network_calls(health_root, monkeypatch):
    """Every input is a committed CSV — including the credit balance, which
    comes from data/odds/credit_log.csv, not the API. A health check that
    spends credits or hangs on a timeout is worse than none."""
    import requests

    def boom(*a, **kw):
        raise AssertionError("doctor must not make network calls")

    monkeypatch.setattr(requests.Session, "request", boom)
    monkeypatch.setattr(requests, "get", boom, raising=False)
    monkeypatch.setattr(requests, "post", boom, raising=False)
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-30").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    write_passes(
        day="2026-09-29", strategies=STRATEGIES, n_games=4, reason="[R0] excluded_game_type=F"
    )
    doctor.cmd_doctor(sport="all", exit_zero=True)


def test_text_render_is_not_empty_and_names_each_sport(health_root, monkeypatch):
    monkeypatch.setattr(doctor, "today_et", lambda: pd.Timestamp("2026-09-30").date())
    write_games(days={"2026-09-29": 4}, game_type="F")
    result = doctor.run_checks(sport="all", cfg=doctor.load_health_config(), since="2026-09-01")
    text = doctor.render_text(result)
    for sport in ("MLB", "NCAAF", "NCAABASE"):
        assert sport in text


def test_reason_key_extraction():
    assert doctor.reason_key("[R0] excluded_game_type=D") == "excluded_game_type"
    assert doctor.reason_key("[FP_ml] game_type=L") == "game_type"
    # Prose reasons have no `=`, so the whole reason is its own key — which is
    # what we want: per-game detail like "heavy favorite -220" varies between
    # games and so never looks uniform.
    assert (
        doctor.reason_key("[FP_ml] no-splits: none captured for game")
        == "no-splits: none captured for game"
    )


def test_every_suggested_command_names_a_real_subcommand():
    """An alert whose remediation is a command that does not exist teaches the
    reader to distrust the alert.

    H01 shipped `panthera-mvp catchup --sport mlb --from <date>` into a
    copy-pasteable block in the GitHub issue while no `catchup` subparser
    existed. Static on purpose: it covers every `panthera-mvp ...` string in
    doctor.py, not only the findings some fixture happens to trigger.
    """
    import panthera_mvp.cli as cli_mod
    import panthera_mvp.doctor as doctor_mod

    cli_src = Path(cli_mod.__file__).read_text()
    known = set(re.findall(r'sub\.add_parser\(\s*"([a-z0-9_-]+)"', cli_src))
    assert known, "could not recover the CLI subcommand list from cli.py"

    doctor_src = Path(doctor_mod.__file__).read_text()
    suggested = set(re.findall(r"panthera-mvp ([a-z0-9_-]+)", doctor_src))
    assert suggested, "doctor.py suggests no commands at all — did the format change?"

    unknown = sorted(suggested - known)
    assert not unknown, (
        f"doctor.py suggests commands that do not exist: {unknown} "
        f"(known subcommands: {sorted(known)})"
    )


def test_suggested_commands_target_the_finding_s_own_sport():
    """`grade` WRITES. H05 emitted `panthera-mvp grade` for every sport, so a
    copy-paste from an NCAAF finding would have graded MLB while the NCAAF
    pick it was about stayed pending."""
    from panthera_mvp.doctor import _cli_prefix

    assert _cli_prefix("mlb") == ""
    assert _cli_prefix("ncaaf") == "ncaaf "
    assert _cli_prefix("ncaabase") == "ncaabase "
