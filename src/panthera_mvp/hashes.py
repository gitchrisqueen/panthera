"""`panthera-mvp hashes` — print each strategy's config_hash and lineage.

A pick records the `config_hash` of the parameters that produced it, and a
strategy's `hash_lineage` declares which hashes may be pooled into one
evaluation. When a config edit moves a hash out of its own lineage, the report
silently splits the ledger into separate segments and every verdict countdown
stalls — see src/panthera_mvp/CLAUDE.md.

Amending a lineage therefore means reading the post-edit hash off the merged
config, and the procedure recurs often enough that a copy-pasted one-liner is
how lineages get recorded wrong. This prints them.
"""

from __future__ import annotations

import json
from typing import Any

from .config import config_hash


def _rows(sport: str) -> list[dict[str, Any]]:
    if sport == "ncaaf":
        from .ncaaf.config import load_ncaaf_strategies

        configs = load_ncaaf_strategies()
    else:
        from .config import load_strategy_configs
        from .strategy.registry import engines

        configs = load_strategy_configs(known_engines=set(engines()))

    out = []
    for sid, cfg in sorted(configs.items()):
        meta = cfg.get("strategy", {})
        chash = config_hash(cfg)
        lineage = [str(h) for h in meta.get("hash_lineage") or []]
        out.append(
            {
                "sport": sport,
                "strategy_id": sid,
                "config_hash": chash,
                "hash_lineage": lineage,
                "enabled": bool(meta.get("enabled")),
                "scope": list(meta.get("scope") or []),
                # An EMPTY lineage means "pool every hash" (report.py's
                # `if lineage else graded`), not "nothing declared" — so it is
                # never drift. Only a non-empty lineage can exclude its own
                # current hash.
                "in_lineage": (not lineage) or chash in lineage,
            }
        )
    return out


def cmd_hashes(sport: str = "all", as_json: bool = False) -> None:
    sports = ["mlb", "ncaaf"] if sport == "all" else [sport]
    rows: list[dict[str, Any]] = []
    for s in sports:
        rows.extend(_rows(s))

    if as_json:
        print(json.dumps({"schema": 1, "strategies": rows}, indent=2))
        return

    width = max((len(r["strategy_id"]) for r in rows), default=10)
    print(f"{'sport':9s} {'strategy':{width}s} {'config_hash':12s} ok  lineage")
    for r in rows:
        flag = "  " if r["in_lineage"] else "!!"
        state = "" if r["enabled"] else "  (disabled)"
        scope = "/".join(r["scope"])
        lineage = ", ".join(r["hash_lineage"]) or "[] (pools every hash)"
        print(
            f"{r['sport']:9s} {r['strategy_id']:{width}s} {r['config_hash']:12s} "
            f"{flag}  {lineage}  [{scope}]{state}"
        )

    # Only an ENABLED LIVE strategy can be harmed by drift: a disabled one
    # generates no further picks, so its frozen segment is the intent.
    drifted = [r for r in rows if not r["in_lineage"] and r["enabled"]]
    dormant = [r for r in rows if not r["in_lineage"] and not r["enabled"]]
    if dormant:
        print()
        print(
            "   (disabled, drift expected: "
            + ", ".join(r["strategy_id"] for r in dormant)
            + ")"
        )
    if drifted:
        print()
        print(
            f"!! {len(drifted)} enabled strategy/strategies whose current hash is "
            "NOT in their declared hash_lineage:"
        )
        for r in drifted:
            print(f"   {r['strategy_id']}: {r['config_hash']} not in {r['hash_lineage']}")
        print(
            "   Their picks will render as a separate segment and their verdict "
            "countdown will not advance. Amend hash_lineage, or register a new "
            "strategy id — see src/panthera_mvp/CLAUDE.md."
        )
