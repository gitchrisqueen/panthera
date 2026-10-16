"""Every `scripts/proof_*.py` must still import.

`scripts/proof_refactor_identity.py` sat broken with a dead import after the
`evaluate_slate` extraction moved the symbols it used, and nothing caught it:
ruff does no cross-module resolution, so a `from x import y` naming a symbol
that no longer exists is invisible to it (and the name WAS used, so not even
F401), and pytest collects only `tests/`. Linting `scripts/` does not close
this; importing them does.

Import only — `main()` is never called, so nothing reads the datastore,
touches the network or writes a proof doc.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

SCRIPTS = sorted((pathlib.Path(__file__).resolve().parents[1] / "scripts").glob("proof_*.py"))


def test_there_are_proof_scripts_to_check():
    """Guard against the glob silently matching nothing."""
    assert SCRIPTS, "no scripts/proof_*.py found — has the directory moved?"


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.stem)
def test_proof_script_imports(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        # A script may exit during import when run outside a repo checkout;
        # that is not the breakage this test is about.
        pass
