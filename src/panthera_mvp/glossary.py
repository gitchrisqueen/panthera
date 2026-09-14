"""Public-vocabulary glossary — one YAML, three renderings.

`config/glossary.yaml` is the single source of truth for every acronym, column
header, badge and rule id the public surfaces name: the dashboard's tables (via
`site/glossary.json` and the `[data-term]` info affordances in
`dashboard_static/`), the `glossary.html` page, and the "## Glossary" section of
`reports/BETTING_REPORT.md`. Same relationship `dashboard.py` has with
`report.py`'s stat helpers — the site and the markdown cannot drift, because they
read one file rather than two copies of the same prose.

A missing or invalid glossary is a **hard** error, not a silent skip: a
term-less build ships dead `#fragment` links to every reader of the published
site, and it would go unnoticed because the pages otherwise render fine.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import paths

#: Rule ids as they are stamped on a Pick/Pass. Deliberately matched against
#: source rather than kept as a list here: `rules.py`'s docstring documents
#: R2/R6/R8, which no code path has ever emitted, so a hand-kept list would
#: demand definitions for ids that do not exist and miss ids that do.
RULE_ID_RE = re.compile(r'"((?:R\d|O\d|B_|FP_|SS_)[A-Za-z0-9_]*)"')

SLUG_RE = re.compile(r"^[a-z0-9_]+$")
VALID_GROUPS = {"column", "metric", "badge", "rule", "concept", "market"}
SHORT_MAX = 200


class GlossaryError(RuntimeError):
    """config/glossary.yaml is missing, unparseable, or violates its contract."""


def glossary_path() -> Path:
    return paths.config_dir() / "glossary.yaml"


def _validate(data: dict, path: Path) -> dict:
    if not isinstance(data, dict):
        raise GlossaryError(f"{path}: top level must be a mapping")
    terms = data.get("terms")
    if not isinstance(terms, dict) or not terms:
        raise GlossaryError(f"{path}: 'terms' must be a non-empty mapping")

    for slug, entry in terms.items():
        where = f"{path}: term {slug!r}"
        if not SLUG_RE.match(str(slug)):
            raise GlossaryError(f"{where}: slug must match {SLUG_RE.pattern} "
                                "(it is used as a URL fragment)")
        if not isinstance(entry, dict):
            raise GlossaryError(f"{where}: must be a mapping")
        for field in ("label", "short"):
            if not str(entry.get(field, "")).strip():
                raise GlossaryError(f"{where}: missing required field {field!r}")
        short = str(entry["short"]).strip()
        if len(short) > SHORT_MAX:
            raise GlossaryError(f"{where}: 'short' is {len(short)} chars "
                                f"(max {SHORT_MAX}) — it has to fit in a tooltip")
        if "\n" in short:
            raise GlossaryError(f"{where}: 'short' must be a single line")
        if "**" in short:
            raise GlossaryError(f"{where}: 'short' is rendered as plain text "
                                "in a title= attribute — no markdown")
        group = entry.get("group")
        if group is not None and group not in VALID_GROUPS:
            raise GlossaryError(f"{where}: unknown group {group!r} "
                                f"(expected one of {sorted(VALID_GROUPS)})")

    # Cross-references resolve only after every term is known.
    for slug, entry in terms.items():
        for ref in entry.get("see_also") or []:
            if ref not in terms:
                raise GlossaryError(f"{path}: term {slug!r} has see_also {ref!r}, "
                                    "which is not defined")

    for table, slugs in (data.get("columns") or {}).items():
        for slug in slugs:
            if slug not in terms:
                raise GlossaryError(f"{path}: columns.{table} lists {slug!r}, "
                                    "which is not defined")
    for slug in data.get("badges") or []:
        if slug not in terms:
            raise GlossaryError(f"{path}: badges lists {slug!r}, which is not defined")

    declared = {g["id"] for g in data.get("groups") or []}
    used = {e.get("group") for e in terms.values() if e.get("group")}
    if used - declared:
        raise GlossaryError(f"{path}: groups {sorted(used - declared)} are used by "
                            "terms but missing from the 'groups' render order")
    return data


def load_glossary() -> dict:
    """Parse and validate config/glossary.yaml. Raises GlossaryError."""
    path = glossary_path()
    if not path.exists():
        raise GlossaryError(
            f"{path} does not exist — the dashboard and the markdown report both "
            "render definitions from it"
        )
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise GlossaryError(f"{path}: {exc}") from exc
    return _validate(data, path)


def term(slug: str) -> dict:
    """One term, or raise if it is not defined."""
    terms = load_glossary()["terms"]
    if slug not in terms:
        raise GlossaryError(f"no glossary term {slug!r}")
    return terms[slug]


def rule_slug(rule_id: str) -> str:
    """The glossary slug for a rule id as stamped on a pick (R3_era -> rule_r3_era)."""
    return f"rule_{rule_id.lower()}"


def source_rule_ids(root: Path | None = None) -> set[str]:
    """Every rule id literal the strategy engines can stamp on a pick.

    Scanned out of the engine source on purpose — see RULE_ID_RE. This is what
    lets tests/test_glossary.py fail the moment a new rule ships without a
    definition, instead of the id surfacing undefined on the public site.
    """
    base = Path(root) if root else Path(__file__).resolve().parent
    found: set[str] = set()
    for py in sorted((base / "strategy").glob("*.py")):
        found |= set(RULE_ID_RE.findall(py.read_text()))
    return found


def glossary_payload() -> dict:
    """The JSON the dashboard fetches: terms plus the page's section order."""
    data = load_glossary()
    return {
        "version": data.get("version", 1),
        "groups": data.get("groups") or [],
        "terms": data["terms"],
    }


def glossary_markdown_section(site_url: str | None = None) -> list[str]:
    """The "## Glossary" section appended to reports/BETTING_REPORT.md.

    Same definitions the site renders, so a reader of the markdown is never
    worse off than a reader of the dashboard.
    """
    data = load_glossary()
    terms = data["terms"]
    url = site_url or "https://gitchrisqueen.github.io/panthera/glossary.html"

    lines = [
        "",
        "## Glossary",
        "",
        "Plain-language definitions for every column, badge and rule id above. "
        f"Also published at <{url}>.",
    ]
    for group in data.get("groups") or []:
        rows = sorted(
            ((slug, e) for slug, e in terms.items() if e.get("group") == group["id"]),
            key=lambda kv: kv[1]["label"].lower(),
        )
        if not rows:
            continue
        lines += ["", f"### {group['title']}", "", "| Term | Definition |", "|---|---|"]
        for _slug, entry in rows:
            short = str(entry["short"]).strip().replace("|", "\\|")
            lines.append(f"| {entry['label']} | {short} |")
    return lines
