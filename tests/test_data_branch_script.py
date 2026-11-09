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


def _refused(repos, setup, *args, env=None):
    """Run pull, apply `setup(work)`, push, and assert it was refused with origin unchanged."""
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")
    setup(work)
    proc = subprocess.run(
        ["bash", str(SCRIPT), "push", "data: x", *args], cwd=work, capture_output=True,
        text=True, env={**ENV, **(env or {})},
    )
    assert proc.returncode != 0, proc.stdout
    assert _git(origin, "rev-parse", "data") == before
    return proc


def _bulk(work: Path, n: int = 3000) -> None:
    bulk = work / "data" / "bulk"
    bulk.mkdir()
    for i in range(n):
        (bulk / f"{'p' * 40}_{i:05d}.csv").write_text(f"{i}\n")


def test_forbidden_path_sorted_first_in_a_huge_list_is_still_refused(repos):
    """grep -q stops at the first match; a pipe writer then dies of SIGPIPE (guard fails open)."""

    def setup(work):
        _bulk(work)
        (work / "data" / "a_picks.csv").write_text("x\n")

    proc = _refused(repos, setup, "--forbid", r"^data/a_picks\.csv$")
    assert "refusing to commit a path" in proc.stdout


def test_secret_on_the_first_line_of_a_huge_add_is_refused(repos):
    def setup(work):
        (work / "data" / "a_leak.txt").write_text("apiKey=0123456789abcdef0123\n")
        _bulk(work)

    proc = _refused(repos, setup)
    assert "API key or auth header" in proc.stdout


@pytest.mark.parametrize(
    "arg", [["--forbid", "("], ["--forbidd", "x"], ["--forbid"], ["--forbid", "a", "extra"]]
)
def test_bad_forbid_arguments_are_rejected_not_ignored(repos, arg):
    proc = _refused(repos, lambda w: (w / "data" / "n.csv").write_text("n\n"), *arg)
    assert proc.returncode == 2


@pytest.mark.parametrize(
    "content",
    [
        "+apiKey=0123456789abcdef0123",
        '{"Authorization": "Bearer abc.def"}',
        "{'apiKey': 'ABCDEF-0123456789-abcdef'}",
        "api_key = 0123456789abcdef0123",
        "x?apiKey%3D0123456789abcdef0123",
    ],
)
def test_more_secret_shapes_are_refused(repos, content):
    _refused(repos, lambda w: (w / "data" / "s.txt").write_text(content + "\n"))


def test_secret_in_a_file_with_a_nul_byte_is_refused(repos):
    def setup(work):
        (work / "data" / "bin.dat").write_bytes(b"\x00apiKey=0123456789abcdef0123\n")

    _refused(repos, setup)


def test_a_bare_api_key_column_header_is_not_a_false_positive(repos):
    origin, work = repos
    _run(work, "pull")
    (work / "data" / "schema.csv").write_text("snapshot_ts,api_key,market\n")
    assert "pushed to origin/data" in _run(work, "push", "data: header").stdout


def test_env_secret_value_anywhere_in_the_delta_is_refused(repos):
    def setup(work):
        (work / "data" / "d.txt").write_text("blob zzTOPSECRETVALUEzz blob\n")

    proc = _refused(repos, setup, env={"ODDS_API_KEY": "zzTOPSECRETVALUEzz"})
    assert "value of ODDS_API_KEY" in proc.stdout


@pytest.mark.parametrize("name", [".env", ".env.local", "id_rsa", "deploy.pem", "x.key"])
def test_credential_looking_filenames_are_refused(repos, name):
    _refused(repos, lambda w: (w / "data" / name).write_text("x\n"))


def test_data_branch_may_not_be_main(repos):
    _origin, work = repos
    proc = subprocess.run(
        ["bash", str(SCRIPT), "pull"], cwd=work, capture_output=True, text=True,
        env={**ENV, "DATA_BRANCH": "main"},
    )
    assert proc.returncode == 2


def test_push_does_not_touch_the_shared_git_identity(repos):
    _origin, work = repos
    _git(work, "config", "user.name", "Human")
    _run(work, "pull")
    (work / "reports" / "R.md").write_text("new\n")
    _run(work, "push", "data: ident")
    assert _git(work, "config", "user.name") == "Human"


DATA_WORKFLOWS = [
    "mvp-morning", "mvp-pregame", "mvp-close", "mvp-splits", "ncaaf",
    "ncaaf-capture", "ncaabase-capture", "panthera-catchup", "mvp-calibrate",
]
READERS = ["health", "pages"]


@pytest.mark.parametrize("name", DATA_WORKFLOWS + READERS)
def test_workflow_overlays_data_before_it_runs(name):
    jobs = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text())["jobs"]
    job = next(  # the job that pulls data (ncaaf.yml also has a gate job before it)
        j["steps"] for j in jobs.values()
        if any("data_branch.sh pull" in str(s.get("run", "")) for s in j["steps"])
    )
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


@pytest.mark.parametrize("name", DATA_WORKFLOWS)
def test_failed_push_uploads_the_delta_after_the_push_step(name):
    jobs = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text())["jobs"]
    steps = next(
        j["steps"] for j in jobs.values()
        if any("data_branch.sh push" in str(s.get("run", "")) for s in j["steps"])
    )
    push = next(i for i, s in enumerate(steps) if "data_branch.sh push" in str(s.get("run", "")))
    keep = steps[push + 1]
    assert keep["if"] == "failure()"
    assert keep["uses"].startswith("actions/upload-artifact")
    assert keep["with"]["path"] == "${{ runner.temp }}/data-delta.patch"
    assert keep["with"]["overwrite"] is True
    assert keep["with"]["retention-days"] == 14
    assert {"ODDS_API_KEY", "LUMIFY_API_KEY", "CFBD_API_KEY"} <= set(steps[push]["env"])


def _no_identity_env(tmp_path: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    home = tmp_path / "emptyhome"
    home.mkdir(exist_ok=True)
    return {**env, "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": str(home)}


def test_rebase_and_commit_work_with_no_git_identity_configured(repos, tmp_path):
    """Runners have no git identity; the rebase after a lost race needs a committer too."""
    origin, work = repos
    env = _no_identity_env(tmp_path)
    run = lambda *a: subprocess.run(  # noqa: E731
        ["bash", str(SCRIPT), *a], cwd=work, env=env, capture_output=True, text=True
    )
    assert run("pull").returncode == 0
    (work / "reports" / "R.md").write_text("mine\n")

    other = tmp_path / "other4"
    _git(tmp_path, "clone", "--quiet", "-b", "data", str(origin), str(other))
    (other / "data" / "other.csv").write_text("theirs\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "other writer")
    _git(other, "push", "origin", "data")

    proc = run("push", "data: mine")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _git(origin, "show", "data:reports/R.md") == "mine"
    assert _git(origin, "show", "data:data/other.csv") == "theirs"


def test_a_failing_git_diff_aborts_the_push(repos, tmp_path):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")
    (work / "data" / "n.csv").write_text("n\n")
    stub = tmp_path / "stub"
    stub.mkdir()
    real = shutil.which("git")
    (stub / "git").write_text(
        '#!/bin/bash\ncase "$*" in *"-U0"*) exit 1;; esac\nexec ' + real + ' "$@"\n'
    )
    (stub / "git").chmod(0o755)

    proc = subprocess.run(
        ["bash", str(SCRIPT), "push", "data: x"], cwd=work, capture_output=True, text=True,
        env={**ENV, "PATH": f"{stub}:{os.environ['PATH']}"},
    )

    assert proc.returncode != 0
    assert _git(origin, "rev-parse", "data") == before


def test_hostile_filename_cannot_inject_a_workflow_command(repos):
    origin, work = repos
    before = _git(origin, "rev-parse", "data")
    _run(work, "pull")
    (work / "data" / "x\n::error::pwned\n").mkdir()
    (work / "data" / "x\n::error::pwned\n" / ".env").write_text("k\n")

    proc = _run(work, "push", "data: bad", check=False)

    assert proc.returncode == 1
    assert _git(origin, "rev-parse", "data") == before
    own = [line for line in proc.stdout.splitlines() if line.startswith("::")]
    assert own == ["::error::refusing to commit a credential-looking filename"]


def test_credential_filenames_are_matched_case_insensitively(repos):
    _refused(repos, lambda w: (w / "data" / "ID_RSA").write_text("x\n"))
    _refused(repos, lambda w: (w / "data" / "Service-Account-prod.json").write_text("x\n"))


def test_env_secret_with_a_trailing_newline_does_not_refuse_every_push(repos):
    origin, work = repos
    _run(work, "pull")
    (work / "data" / "ok.csv").write_text("fine\n")
    proc = subprocess.run(
        ["bash", str(SCRIPT), "push", "data: ok"], cwd=work, capture_output=True, text=True,
        env={**ENV, "ODDS_API_KEY": "abcdefghijklmnop\n"},
    )
    assert proc.returncode == 0, proc.stdout


def test_a_successful_push_leaves_no_patch_behind(repos, tmp_path):
    _origin, work = repos
    env = {**ENV, "RUNNER_TEMP": str(tmp_path)}
    run = lambda *a: subprocess.run(  # noqa: E731
        ["bash", str(SCRIPT), *a], cwd=work, env=env, capture_output=True, text=True, check=True
    )
    run("pull")
    (work / "reports" / "R.md").write_text("changed\n")
    run("push", "data: ok")
    assert not (tmp_path / "data-delta.patch").exists()


def test_a_symlinked_data_dir_on_the_branch_is_refused(repos, tmp_path):
    origin, work = repos
    other = tmp_path / "evil"
    _git(tmp_path, "clone", "--quiet", "-b", "data", str(origin), str(other))
    _git(other, "rm", "-r", "--quiet", "reports")
    (other / "reports").symlink_to("/etc")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "symlink")
    _git(other, "push", "origin", "data")

    proc = _run(work, "pull", check=False)

    assert proc.returncode == 1
    assert "symlink" in proc.stdout
