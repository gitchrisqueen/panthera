"""scripts/ci/ncaaf_gate.py (issue #79) and scripts/ci/validate_inputs.sh (issue #80),
plus structural guards on the workflows they are wired into."""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

_spec = importlib.util.spec_from_file_location(
    "ncaaf_gate", ROOT / "scripts" / "ci" / "ncaaf_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules["ncaaf_gate"] = gate
_spec.loader.exec_module(gate)

SETTINGS = (60, 15, 30)  # decide when the first kickoff is under 90 minutes away
NOW = datetime(2026, 11, 7, 15, 30, tzinfo=UTC)  # Sat 10:30 ET


def _game(start: str, day: str = "2026-11-07", status: str = "Scheduled") -> dict:
    return {"game_date_et": day, "start_time_utc": start, "status": status}


# ---- decide() mirrors in_decision_window ---------------------------------------------


def test_go_when_first_kickoff_is_inside_the_window():
    go, why = gate.decide(NOW, [_game("2026-11-07T16:45:00Z")], set(), SETTINGS)
    assert go and "75 min" in why


def test_no_go_when_first_kickoff_is_far_away():
    go, why = gate.decide(NOW, [_game("2026-11-07T20:00:00Z")], set(), SETTINGS)
    assert not go and "decide under 90" in why


def test_kickoff_inside_min_lead_is_ignored_like_the_real_code():
    # 10 minutes away is under min_lead (15): not eligible, so the next game decides.
    games = [_game("2026-11-07T15:40:00Z"), _game("2026-11-07T20:00:00Z")]
    assert gate.decide(NOW, games, set(), SETTINGS)[0] is False


def test_no_go_without_games_today_or_when_already_decided():
    assert gate.decide(NOW, [], set(), SETTINGS)[0] is False
    tomorrow = [_game("2026-11-08T17:00:00Z", "2026-11-08")]
    assert gate.decide(NOW, tomorrow, set(), SETTINGS)[0] is False
    today = [_game("2026-11-07T16:45:00Z")]
    assert gate.decide(NOW, today, {"2026-11-07"}, SETTINGS)[0] is False


def test_only_scheduled_games_count():
    done = [_game("2026-11-07T16:45:00Z", status="Final")]
    assert gate.decide(NOW, done, set(), SETTINGS)[0] is False


def test_live_settings_match_the_configs():
    assert gate.load_settings() == SETTINGS


# ---- fixture path handling -------------------------------------------------------------


@pytest.mark.parametrize(
    "arg",
    [
        "/etc/passwd",
        "tests/fixtures/ncaaf/../../../pyproject.toml",
        "tests/fixtures/odds_snapshot.json",
        "tests/fixtures/ncaaf/odds_ncaaf_snapshot.txt",
        "tests/fixtures/ncaaf/does_not_exist.json",
        "pyproject.toml",
    ],
)
def test_fixture_outside_the_fixture_dir_is_rejected(arg):
    with pytest.raises(gate.FixtureRejected):
        gate.resolve_fixture(arg)


def test_symlink_escaping_the_fixture_dir_is_rejected(tmp_path):
    link = gate.FIXTURE_DIR / "zz_escape_test.json"
    target = tmp_path / "outside.json"
    target.write_text("{}")
    link.symlink_to(target)
    try:
        with pytest.raises(gate.FixtureRejected):
            gate.resolve_fixture("tests/fixtures/ncaaf/zz_escape_test.json")
    finally:
        link.unlink()


def _run_gate(tmp_path: Path, **env) -> tuple[int, dict[str, str]]:
    out = tmp_path / "out"
    out.write_text("")
    full = {k: v for k, v in os.environ.items() if not k.startswith("GATE_")}
    full.update({"GITHUB_OUTPUT": str(out), **env})
    proc = subprocess.run(
        [
            sys.executable, "-I", str(ROOT / "scripts" / "ci" / "ncaaf_gate.py"),
            "--games-csv", str(tmp_path / "games.csv"),
            "--decisions-csv", str(tmp_path / "dec.csv"),
        ],
        env=full, capture_output=True, text=True,
    )
    lines = out.read_text().splitlines()
    return proc.returncode, dict(line.split("=", 1) for line in lines if "=" in line)


def test_fixture_go_and_no_go_write_outputs(tmp_path):
    code, out = _run_gate(
        tmp_path, GATE_EVENT="workflow_dispatch",
        GATE_FIXTURE="tests/fixtures/ncaaf/gate_go.json",
    )
    assert code == 0 and out["go"] == "true" and out["fixture"] == "true"
    code, out = _run_gate(
        tmp_path, GATE_EVENT="workflow_dispatch",
        GATE_FIXTURE="tests/fixtures/ncaaf/gate_nogo.json",
    )
    assert code == 0 and out["go"] == "false" and out["fixture"] == "true"


def test_non_fixture_path_exits_2_and_writes_no_go(tmp_path):
    code, out = _run_gate(tmp_path, GATE_EVENT="workflow_dispatch", GATE_FIXTURE="pyproject.toml")
    assert code == 2 and "go" not in out


# ---- fail open ------------------------------------------------------------------------

AUTO = "5 13-23,0-4 * 8-12,1 *"


@pytest.mark.parametrize(
    "env",
    [
        {"GATE_EVENT": "workflow_dispatch"},
        {"GATE_EVENT": "schedule", "GATE_SCHEDULE": "10 23 * 8-12,1 0,3"},  # prep
        {"GATE_EVENT": "schedule", "GATE_SCHEDULE": "15 13 * 8-12,1 *"},  # grade
        {"GATE_EVENT": "schedule", "GATE_SCHEDULE": "1 2 3 4 5"},  # unknown cron
        {"GATE_EVENT": "schedule", "GATE_SCHEDULE": AUTO},  # auto, input files missing
    ],
)
def test_anything_unproven_is_go(tmp_path, env):
    code, out = _run_gate(tmp_path, **env)
    assert code == 0 and out["go"] == "true"


def test_corrupt_games_file_fails_open(tmp_path):
    (tmp_path / "games.csv").write_text("not,a,games\nfile\n")
    (tmp_path / "dec.csv").write_text("strategy_id,game_date_et\n")
    code, out = _run_gate(tmp_path, GATE_EVENT="schedule", GATE_SCHEDULE=AUTO)
    assert code == 0 and out["go"] == "true"


def test_auto_run_with_no_games_is_no_go(tmp_path):
    (tmp_path / "games.csv").write_text("game_date_et,start_time_utc,status\n")
    (tmp_path / "dec.csv").write_text("strategy_id,game_date_et\n")
    code, out = _run_gate(tmp_path, GATE_EVENT="schedule", GATE_SCHEDULE=AUTO)
    assert code == 0 and out["go"] == "false"


def test_gate_crons_are_the_auto_crons_of_ncaaf_yml():
    text = (WORKFLOWS / "ncaaf.yml").read_text()
    auto = re.findall(r'"([^"]+)"\)\s+echo "task=auto"', text)
    assert set(auto) == gate.AUTO_CRONS


# ---- validate_inputs.sh -----------------------------------------------------------------


def _validate(*specs: str, **env: str) -> int:
    return subprocess.run(
        ["bash", str(ROOT / "scripts" / "ci" / "validate_inputs.sh"), *specs],
        env={**os.environ, **env}, capture_output=True, text=True,
    ).returncode


@pytest.mark.parametrize(
    "kind,good,bad",
    [
        ("date", "2026-11-07", "2026-11-07; echo pwned"),
        ("week", "10", "1 2"),
        ("year", "2026", "20266"),
        ("range", "2014-2019", "2014"),
        ("seasons", "2015-2025", "$(id)"),
        ("seasons", "2025", "2025\n2026"),
    ],
)
def test_validate_inputs(kind, good, bad):
    assert _validate(f"V:{kind}", V=good) == 0
    assert _validate(f"V:{kind}", V="") == 0
    assert _validate(f"V:{kind}", V=bad) == 1


def test_validate_inputs_rejects_unknown_kind():
    assert _validate("V:nonsense", V="x") == 2


# ---- workflow structure ----------------------------------------------------------------


def _wf(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text())


WRITERS = [
    "mvp-morning", "mvp-pregame", "mvp-close", "mvp-splits", "mvp-calibrate",
    "ncaaf-capture", "ncaabase-capture", "panthera-catchup", "ncaaf",
]
READ_ONLY = ["site-audit", "mvp-debug-era", "health", "pages", "ci", "todo-to-issue"]


@pytest.mark.parametrize("name", WRITERS + READ_ONLY)
def test_workflow_token_defaults_to_read(name):
    perms = _wf(name)["permissions"]
    assert perms.get("contents") == "read"


@pytest.mark.parametrize("name", WRITERS)
def test_only_the_data_job_writes(name):
    jobs = _wf(name)["jobs"]
    writers = [j for j, s in jobs.items() if s.get("permissions", {}).get("contents") == "write"]
    assert len(writers) == 1, f"{name}: {writers}"


@pytest.mark.parametrize(
    "name",
    ["ncaaf", "ncaaf-capture", "ncaabase-capture", "mvp-calibrate", "mvp-debug-era", "mvp-splits"],
)
def test_dispatch_inputs_never_reach_a_run_script(name):
    for job in _wf(name)["jobs"].values():
        for step in job["steps"]:
            assert "${{ inputs." not in str(step.get("run", "")), (name, step.get("name"))


def test_ncaaf_job_is_gated_fail_open():
    spec = _wf("ncaaf")["jobs"]
    assert spec["run"]["needs"] == "gate"
    cond = " ".join(str(spec["run"]["if"]).split())
    assert "needs.gate.result != 'success'" in cond
    assert "needs.gate.outputs.go == 'true'" in cond
    assert "!cancelled()" in cond
    assert spec["run"]["env"]["GATE_FIXTURE"] == "${{ inputs.gate_fixture }}"
    dry = next(s for s in spec["run"]["steps"] if s.get("name") == "Effective dry run")
    assert '-n "$GATE_FIXTURE"' in dry["run"]
    gate_step = next(s for s in spec["gate"]["steps"] if s.get("id") == "gate")
    assert gate_step["env"]["GATE_FIXTURE"] == "${{ inputs.gate_fixture }}"


def test_pages_build_is_skipped_only_when_unchanged():
    spec = _wf("pages")["jobs"]
    assert spec["deploy"]["if"] == "needs.build.outputs.build == 'true'"
    change = next(s for s in spec["build"]["steps"] if s.get("id") == "change")
    assert "workflow_dispatch" in change["run"] and "build=true" in change["run"]
