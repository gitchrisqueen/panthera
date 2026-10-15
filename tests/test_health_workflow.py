"""Guards for .github/workflows/health.yml's inline reconciler JavaScript.

The reconciler runs unattended with `issues: write` on a public repo and is
never exercised by the Python suite, so without these it would first execute
on `main` after merge. Two things are checked: that it parses, and that it
refuses to act on anything it did not create.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "health.yml"


def _reconciler_script() -> str:
    spec = yaml.safe_load(WORKFLOW.read_text())
    for job in spec["jobs"].values():
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/github-script"):
                return step["with"]["script"]
    raise AssertionError("no actions/github-script step in health.yml")


def test_reconciler_javascript_parses():
    """`node --check` on the inline script. A syntax error here would mean a
    red scheduled job and no health alerting at all, discovered only in
    production."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    # actions/github-script runs the body inside an async wrapper, so its
    # top-level `await` is legal there but not to a bare `node --check`.
    # Wrap it the same way before checking.
    wrapped = "(async () => {\n" + _reconciler_script() + "\n})()\n"
    proc = subprocess.run(
        [node, "--check", "-"], input=wrapped, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_reconciler_only_adopts_issues_it_opened():
    """Provenance before the marker.

    `issues.listForRepo` also returns pull requests, and both the label and
    the body are contributor-controlled. Without these two guards a PR — or a
    human bug report about this feature quoting the marker line out of this
    very file — is adopted as a stale fingerprint and auto-closed by a token
    with issues:write.
    """
    script = _reconciler_script()
    # Both guards must come before the line that adopts an issue, not merely
    # exist somewhere in the file.
    adopt = script.index("byFingerprint.set(")
    before = script[:adopt]
    assert "if (issue.pull_request) continue;" in before
    assert "github-actions[bot]" in before
