"""scripts/ci/data_branch.sh: bot data rides the `data` branch, not protected main.

Runs the real script against a local bare repo standing in for origin, so no
network and no real branch is touched. The workflow YAML is checked for the
wiring that cannot be exercised here (every committing workflow uses the
script; none pushes to the ref it was started on).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci" / "data_branch.sh"
WORKFLOWS = ROOT / ".github" / "workflows"

_TOOLS_OK = bool(shutil.which("git") and shutil.which("rsync") and shutil.which("bash"))
if os.environ.get("CI") and not _TOOLS_OK:  # a runner without rsync must not pass silently
    raise RuntimeError("git, rsync and bash are required in CI")
pytestmark = pytest.mark.skipif(not _TOOLS_OK, reason="git, rsync and bash required")

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def _run(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=cwd, env=ENV, capture_output=True, text=True,
        check=check,
    )


@pytest.fixture()
def repos(tmp_path: Path):
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _git(seed, "remote", "add", "origin", str(origin))
    (seed / "code.txt").write_text("code\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "code")
    _git(seed, "push", "origin", "main")

    _git(seed, "checkout", "--orphan", "data")
    _git(seed, "rm", "-rf", "--quiet", ".")
    (seed / "data" / "picks").mkdir(parents=True)
    (seed / "data" / "picks" / "picks.csv").write_text("a\n")
    (seed / "data" / "old.csv").write_text("old\n")
    (seed / "reports").mkdir()
    (seed / "reports" / "R.md").write_text("report v1\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "seed data")
    _git(seed, "push", "origin", "data")

    work = tmp_path / "work"
    _git(tmp_path, "clone", "--quiet", str(origin), str(work))
    return origin, work


def test_pull_overlays_data_and_keeps_main_docs(repos):
    _origin, work = repos
    (work / "data").mkdir()
    (work / "data" / "CLAUDE.md").write_text("docs owned by main\n")
    (work / "data" / "stale.csv").write_text("not on data branch\n")

    _run(work, "pull")

    assert (work / "data" / "picks" / "picks.csv").read_text() == "a\n"
    assert (work / "reports" / "R.md").read_text() == "report v1\n"
    assert not (work / "data" / "stale.csv").exists(), "overlay must delete strays"
    assert (work / "data" / "CLAUDE.md").exists(), "main's CLAUDE.md is never touched"


def test_push_lands_on_data_branch_and_never_touches_main(repos):
    origin, work = repos
    main_before = _git(origin, "rev-parse", "main")
    _run(work, "pull")
    (work / "data" / "picks" / "picks.csv").write_text("a\nb\n")
    (work / "data" / "old.csv").unlink()
    (work / "reports" / "R.md").write_text("report v2\n")

    out = _run(work, "push", "data: test [skip ci]")

    assert "pushed to origin/data" in out.stdout
    assert _git(origin, "rev-parse", "main") == main_before
    assert _git(origin, "show", "data:data/picks/picks.csv") == "a\nb"
    assert _git(origin, "show", "data:reports/R.md") == "report v2"
    assert "old.csv" not in _git(origin, "ls-tree", "-r", "--name-only", "data")
    assert _git(origin, "log", "-1", "--format=%s", "data") == "data: test [skip ci]"


def test_push_with_no_change_makes_no_commit(repos):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")

    out = _run(work, "push", "data: noop")

    assert "No changes to commit." in out.stdout
    assert _git(origin, "rev-parse", "data") == before


def test_push_writes_pushed_output_only_when_it_pushes(repos, tmp_path):
    _origin, work = repos
    gh_out = tmp_path / "gh_output"
    gh_out.write_text("")
    env_run = lambda *a: subprocess.run(  # noqa: E731
        ["bash", str(SCRIPT), *a], cwd=work, capture_output=True, text=True, check=True,
        env={**ENV, "GITHUB_OUTPUT": str(gh_out)},
    )
    env_run("pull")
    env_run("push", "data: noop")
    assert gh_out.read_text() == ""

    (work / "reports" / "R.md").write_text("changed\n")
    env_run("push", "data: changed")
    assert "pushed=true" in gh_out.read_text()


def test_forbid_blocks_a_matching_path(repos):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")
    (work / "data" / "picks" / "picks.csv").write_text("tampered\n")

    proc = _run(work, "push", "data: bad", "--forbid", r"^data/picks/picks\.csv$", check=False)

    assert proc.returncode == 1
    assert "refusing to commit" in proc.stdout
    assert _git(origin, "rev-parse", "data") == before


def test_push_rebases_onto_a_concurrent_writer(repos, tmp_path):
    origin, work = repos
    _run(work, "pull")
    (work / "reports" / "R.md").write_text("mine\n")

    # Another writer lands a commit on data after our pull, in a different file.
    other = tmp_path / "other"
    _git(tmp_path, "clone", "--quiet", "-b", "data", str(origin), str(other))
    (other / "data" / "other.csv").write_text("theirs\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "other writer")
    _git(other, "push", "origin", "data")

    _run(work, "push", "data: mine")

    assert _git(origin, "show", "data:reports/R.md") == "mine"
    assert _git(origin, "show", "data:data/other.csv") == "theirs", "concurrent file was lost"


def test_second_pull_sees_what_was_pushed_in_between(repos):
    origin, work = repos
    _run(work, "pull")
    (work / "reports" / "R.md").write_text("v2 from first run\n")
    _run(work, "push", "data: first")

    other = work.parent / "other2"
    _git(work.parent, "clone", "--quiet", "-b", "data", str(origin), str(other))
    (other / "data" / "later.csv").write_text("later\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "later")
    _git(other, "push", "origin", "data")

    _run(work, "pull")

    assert (work / "data" / "later.csv").read_text() == "later\n"
    assert _git(work / ".databranch", "rev-parse", "HEAD") == _git(origin, "rev-parse", "data")


def test_push_without_pull_is_refused(repos):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    (work / "data").mkdir()
    (work / "data" / "x.csv").write_text("x\n")

    proc = _run(work, "push", "data: no pull", check=False)

    assert proc.returncode == 1
    assert "needs a prior pull" in proc.stdout
    assert _git(origin, "rev-parse", "data") == before


def test_same_file_conflict_fails_cleanly_and_saves_the_delta(repos, tmp_path):
    origin, work = repos
    env = {**ENV, "RUNNER_TEMP": str(tmp_path)}
    run = lambda *a, **k: subprocess.run(  # noqa: E731
        ["bash", str(SCRIPT), *a], cwd=work, env=env, capture_output=True, text=True, **k
    )
    assert run("pull").returncode == 0
    (work / "reports" / "R.md").write_text("mine\n")

    other = tmp_path / "other3"
    _git(tmp_path, "clone", "--quiet", "-b", "data", str(origin), str(other))
    (other / "reports" / "R.md").write_text("theirs\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "conflicting writer")
    _git(other, "push", "origin", "data")
    theirs = _git(origin, "rev-parse", "data")

    proc = run("push", "data: mine")

    assert proc.returncode == 1
    assert "conflicted" in proc.stdout
    assert _git(origin, "rev-parse", "data") == theirs
    assert _git(work / ".databranch", "status", "--porcelain") == ""
    assert "mine" in (tmp_path / "data-delta.patch").read_text()


def test_forbid_survives_a_huge_path_list_and_a_rename_away(repos):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")
    bulk = work / "data" / "bulk"
    bulk.mkdir()
    for i in range(3000):
        (bulk / f"{'p' * 40}_{i:05d}.csv").write_text(f"{i}\n")
    (work / "data" / "picks" / "picks.csv").rename(work / "data" / "picks" / "moved.csv")

    proc = _run(work, "push", "data: big", "--forbid", r"^data/picks/picks\.csv$", check=False)

    assert proc.returncode == 1
    assert _git(origin, "rev-parse", "data") == before


@pytest.mark.parametrize(
    "line",
    ["https://x.example/odds?apiKey=0123456789abcdef0123", "Authorization: Bearer abc.def"],
)
def test_secret_looking_data_is_refused(repos, line):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")
    (work / "data" / "odds").mkdir()
    (work / "data" / "odds" / "log.txt").write_text(line + "\n")

    proc = _run(work, "push", "data: leak", check=False)

    assert proc.returncode == 1
    assert "API key or auth header" in proc.stdout
    assert _git(origin, "rev-parse", "data") == before


def test_symlinks_are_never_copied_in_either_direction(repos):
    origin, work = repos
    _run(work, "pull")
    (work / "data" / "link").symlink_to("/etc/hostname")
    _run(work, "push", "data: link")
    assert "data/link" not in _git(origin, "ls-tree", "-r", "--name-only", "data")


def test_changed_contract(repos):
    _origin, work = repos
    run = lambda *a: _run(work, "changed", *a, check=False).returncode  # noqa: E731
    _run(work, "pull")
    assert run("data/picks") == 1  # identical
    assert run("data/nowhere") == 1  # absent on both sides
    (work / "data" / "picks" / "picks.csv").write_text("changed\n")
    assert run("data/picks") == 0  # different
    (work / "data" / "newdir").mkdir()
    (work / "data" / "newdir" / "a.csv").write_text("a\n")
    assert run("data/newdir") == 0  # present on one side only


DATA_WORKFLOWS = [
    "mvp-morning", "mvp-pregame", "mvp-close", "mvp-splits", "ncaaf",
    "ncaaf-capture", "ncaabase-capture", "panthera-catchup", "mvp-calibrate",
]
READERS = ["health", "pages"]


@pytest.mark.parametrize("name", DATA_WORKFLOWS + READERS)
def test_workflow_overlays_data_before_it_runs(name):
    steps = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text())["jobs"]
    job = next(iter(steps.values()))["steps"]
    runs = [str(s.get("run", "")) for s in job]
    pull = next(i for i, r in enumerate(runs) if "data_branch.sh pull" in r)
    checkout = next(
        i for i, s in enumerate(job) if str(s.get("uses", "")).startswith("actions/checkout")
    )
    assert checkout < pull


@pytest.mark.parametrize("name", DATA_WORKFLOWS)
def test_workflow_pushes_through_the_script_not_to_its_own_ref(name):
    text = (WORKFLOWS / f"{name}.yml").read_text()
    assert "git push" not in text, f"{name}: direct push to a protected ref"
    assert "git add data" not in text
    assert "data_branch.sh push" in text
