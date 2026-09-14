"""The glossary's coverage contract.

These tests exist because the failure mode is silent: a new table column or a
new rule id ships, nothing breaks, and the public site simply renders an
acronym nobody has defined. Rather than trusting anyone to remember, the tests
scrape the dashboard's own static source and the strategy engines' source and
demand a definition for everything they actually put on screen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from panthera_mvp.dashboard import write_site
from panthera_mvp.glossary import (
    SHORT_MAX,
    GlossaryError,
    glossary_markdown_section,
    glossary_payload,
    load_glossary,
    rule_slug,
    source_rule_ids,
)
from panthera_mvp.report import write_ledger_report

STATIC = Path(__file__).resolve().parents[1] / "src" / "panthera_mvp" / "dashboard_static"
#: Every file that can put a [data-term] or a glossBadge() on screen.
UI_SOURCES = ["index.html", "calibration.html", "app.js", "calibration.js"]


def ui_text() -> str:
    return "\n".join((STATIC / name).read_text() for name in UI_SOURCES)


def wired_terms() -> set[str]:
    """Slugs the shipped UI actually references.

    Three wiring styles, all of which have to count: a literal data-term on a
    <th>, a glossBadge() call, and breakdownTable()'s keyTerm argument (those
    headers are built in JS, so their slug never appears as a literal attribute).
    """
    text = ui_text()
    return (
        set(re.findall(r'data-term="([a-z0-9_]+)"', text))
        | set(re.findall(r'glossBadge\("([a-z0-9_]+)"', text))
        | set(re.findall(r'breakdownTable\([^)]*?"([a-z0-9_]+)"\s*\)', text))
    )


# --------------------------------------------------------------- the file
def test_glossary_yaml_is_valid_and_house_style():
    terms = load_glossary()["terms"]
    assert terms, "glossary.yaml defines no terms"
    for slug, entry in terms.items():
        short = entry["short"].strip()
        assert len(short) <= SHORT_MAX, f"{slug}: 'short' too long for a tooltip"
        assert "\n" not in short, f"{slug}: 'short' must be one line"
        assert "**" not in short, f"{slug}: 'short' renders as plain text in title="
        for ref in entry.get("see_also") or []:
            assert ref in terms, f"{slug}: see_also {ref!r} is not defined"


def test_missing_glossary_is_a_hard_error(tmp_root):
    """A term-less build would ship dead #fragment links to every reader, so it
    must fail loudly rather than render an empty glossary."""
    (tmp_root / "config" / "glossary.yaml").unlink()
    with pytest.raises(GlossaryError):
        load_glossary()


# ------------------------------------------------------------- coverage
def test_every_wired_term_has_a_definition():
    terms = load_glossary()["terms"]
    missing = sorted(slug for slug in wired_terms() if slug not in terms)
    assert not missing, (
        f"the dashboard references terms with no glossary entry: {missing} — "
        "the site would render them as data-gloss=\"missing\""
    )


def test_every_declared_column_is_actually_wired():
    """The other direction: a column declared in the index but never attached to
    a <th> means the header on screen still has no affordance."""
    data = load_glossary()
    wired = wired_terms()
    declared = {slug for slugs in data["columns"].values() for slug in slugs}
    # 'roi' rides on the breakdown tables' hard-coded ROI header.
    unwired = sorted(declared - wired)
    assert not unwired, f"declared columns never wired to a <th>: {unwired}"


def test_every_badge_is_defined_and_wired():
    data = load_glossary()
    terms, text = data["terms"], ui_text()
    for slug in data["badges"]:
        assert slug in terms, f"badges lists undefined {slug!r}"
        assert f'glossBadge("{slug}"' in text, f"badge {slug!r} is never rendered"


def test_every_rule_id_in_source_has_a_glossary_entry():
    terms = load_glossary()["terms"]
    ids = source_rule_ids()
    assert len(ids) >= 26, (
        f"the rule-id scanner found only {len(ids)} ids — RULE_ID_RE has probably "
        "stopped matching how engines stamp rule ids"
    )
    missing = sorted(r for r in ids if rule_slug(r) not in terms)
    assert not missing, f"rule ids stamped on picks with no glossary entry: {missing}"


def test_no_orphan_rule_entries():
    """A rule entry with no matching engine id is stale documentation."""
    terms = load_glossary()["terms"]
    live = {rule_slug(r) for r in source_rule_ids()}
    orphans = sorted(
        slug for slug, e in terms.items() if e.get("group") == "rule" and slug not in live
    )
    assert not orphans, f"glossary defines rules no engine emits: {orphans}"


# --------------------------------------------------------------- outputs
def test_glossary_section_lands_in_the_ledger_report(tmp_root, cfg):
    text = write_ledger_report(cfg).read_text()
    assert "## Glossary" in text
    assert "### Rule ids" in text
    assert "Return on investment" in text


def test_write_site_emits_glossary_json(tmp_root, cfg):
    out = write_site(generated_by_run="manual")
    payload = json.loads((out / "glossary.json").read_text())
    assert payload["terms"] == load_glossary()["terms"]
    assert payload["groups"] == glossary_payload()["groups"]


def test_site_and_markdown_cannot_drift(tmp_root, cfg):
    """Both renderings read the same file, so a definition in one is in the other."""
    out = write_site(generated_by_run="manual")
    site_terms = json.loads((out / "glossary.json").read_text())["terms"]
    markdown = "\n".join(glossary_markdown_section())
    for entry in site_terms.values():
        assert entry["short"].replace("|", "\\|") in markdown, (
            f"{entry['label']} is on the site but not in the markdown glossary"
        )
