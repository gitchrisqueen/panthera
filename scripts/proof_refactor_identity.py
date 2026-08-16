"""Migration proof (a): the multi-strategy refactor does not change pv_v2.

Replays real slates (lines.csv + games.csv, no network) through BOTH code
paths with byte-identical inputs:

  OLD: `generate_pick(...)` called directly with the pipeline config
       (base strategy.yaml + strategy.calibrated.yaml), as the pre-framework
       cmd_picks did;
  NEW: the registry adapter (`_pv_rules`) with config/strategies/pv_v2.yaml
       (behavioral params inlined) + the `_pick_row` builder.

and asserts row-equality on every behavior-bearing field — explicitly
excluding pick_id / config_hash / strategy_id, which legitimately change.

Scope of the claim: refactor identity on identical inputs. This is NOT a
reproduction of the live ledger rows (the live runs had full-season dossier
context that an offline replay cannot rebuild; both sides here share the
same games.csv-derived context, so the comparison isolates the refactor).
Cap-semantics differences are proven separately (proof_cap_delta.py) — this
replay uses days where the cap never binds.

Run from the repo root: python scripts/proof_refactor_identity.py
Writes docs/proofs/refactor-identity.md and exits non-zero on any mismatch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panthera_mvp import store  # noqa: E402
from panthera_mvp.clients.mlb import GameInfo  # noqa: E402
from panthera_mvp.config import config_hash, load_config, load_strategy_configs  # noqa: E402
from panthera_mvp.pipeline import _build_dossier, _pick_row  # noqa: E402
from panthera_mvp.strategy.dossier import SeasonContext  # noqa: E402
from panthera_mvp.strategy.movement import extract_game_prices  # noqa: E402
from panthera_mvp.strategy.registry import StrategyContext, _pv_rules  # noqa: E402
from panthera_mvp.strategy.rules import Pick, generate_pick  # noqa: E402
from panthera_mvp.timeutil import parse_utc  # noqa: E402

REPLAY_DATES = ["2026-08-03", "2026-08-16"]  # <=6-pick days: cap never binds

COMPARE_FIELDS = [
    "game_pk",
    "market",
    "selection",
    "line",
    "price_american",
    "rule_id",
    "day_type",
    "slot_type",
    "open_price",
    "latest_price",
    "movement_cents",
    "rationale",
]


def _games_for(date_et: str, games_df: pd.DataFrame) -> list[GameInfo]:
    rows = games_df[games_df["game_date_et"] == date_et]
    out = []
    for _, r in rows.iterrows():
        out.append(
            GameInfo(
                game_pk=int(r["game_pk"]),
                game_date_et=str(r["game_date_et"]),
                game_type=str(r["game_type"]),
                status="Preview",  # replay: both paths see the pre-game state
                detailed_state="Scheduled",
                start_utc=parse_utc(str(r["start_time_utc"])),
                doubleheader=str(r["doubleheader"]),
                game_number=int(r["game_number"]),
                home_team_id=int(r["home_team_id"]),
                home_team=str(r["home_team"]),
                away_team_id=int(r["away_team_id"]),
                away_team=str(r["away_team"]),
            )
        )
    return out


def _season_context_before(date_et: str, games_df: pd.DataFrame) -> SeasonContext:
    ctx = SeasonContext()
    finals = games_df[
        (games_df["game_date_et"] < date_et)
        & (games_df["status"] == "Final")
        & (games_df["game_type"] == "R")
    ].sort_values(["game_date_et", "start_time_utc"])
    for _, r in finals.iterrows():
        if pd.notna(r["home_score"]) and pd.notna(r["away_score"]):
            ctx.add_final(
                int(r["home_team_id"]),
                int(r["away_team_id"]),
                int(r["home_score"]),
                int(r["away_score"]),
            )
    return ctx


def main() -> None:
    lines = store.load_lines()
    games_df = store.load_games()
    old_cfg = load_config()  # base + calibrated: the pre-framework pipeline config
    new_cfg = load_strategy_configs()["pv_v2"]

    report = [
        "# Migration proof (a): refactor identity for pv_v2",
        "",
        "Old path: `generate_pick` + pipeline config (base+calibrated). "
        "New path: registry `_pv_rules` + `config/strategies/pv_v2.yaml` + "
        "`_pick_row`. Identical inputs (lines.csv + games.csv replay; shared "
        "games.csv-derived season context). Compared fields: "
        f"`{'`, `'.join(COMPARE_FIELDS)}` — `pick_id`/`config_hash`/"
        "`strategy_id` excluded (they legitimately change).",
        "",
        f"Old config hash: `{config_hash(old_cfg)}` · new: `{config_hash(new_cfg)}` "
        "— identical here because pv_v2.yaml's inlined parameters replicate "
        "base+calibrated exactly under the new hash function. Both differ "
        "from the legacy live hash `6f0d0924d4` (computed by the old hash "
        "function over the whole dict incl. `meta`), which is why the ledger "
        "segments at the framework boundary. Neither path applies a bet cap "
        "in this replay — cap-semantics differences are proven separately in "
        "cap-delta.md.",
        "",
    ]
    failures = 0
    for date_et in REPLAY_DATES:
        lines_day = lines[lines["game_date_et"] == date_et]
        games = _games_for(date_et, games_df)
        ctx_season = _season_context_before(date_et, games_df)
        events_by_pk = (
            lines_day.dropna(subset=["game_pk"])
            .drop_duplicates("game_pk")
            .set_index("game_pk")["odds_event_id"]
            .to_dict()
        )
        rows_old, rows_new = [], []
        for g in games:
            event_id = events_by_pk.get(g.game_pk)
            prices = (
                extract_game_prices(lines_day, event_id, g.home_team, g.away_team)
                if event_id
                else None
            )
            old = generate_pick(
                g, event_id, prices, _build_dossier(g, ctx_season, old_cfg), old_cfg
            )
            new = _pv_rules(
                StrategyContext(
                    game=g,
                    odds_event_id=event_id,
                    prices=prices,
                    dossier=_build_dossier(g, ctx_season, new_cfg),
                    cfg=new_cfg,
                )
            )
            if isinstance(old, Pick):
                rows_old.append({f: getattr(old, f) for f in COMPARE_FIELDS})
            if isinstance(new, Pick):
                rows_new.append(
                    {
                        f: _pick_row(new, "pv_v2", new_cfg, config_hash(new_cfg))[f]
                        for f in COMPARE_FIELDS
                    }
                )
        same = rows_old == rows_new
        if not same:
            failures += 1
        report += [
            f"## {date_et}",
            "",
            f"- old path picks: {len(rows_old)} · new path picks: {len(rows_new)}",
            f"- field-identical: **{'YES' if same else 'NO'}**",
            "",
        ]
        for r in rows_new:
            report.append(
                f"- {r['game_pk']} {r['selection']} {r['market']} "
                f"{r['price_american']:+.0f} [{r['rule_id']}]"
            )
        report.append("")
        if not same:
            report += ["```diff", f"old: {rows_old}", f"new: {rows_new}", "```", ""]

    out = Path("docs/proofs/refactor-identity.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n")
    print(f"wrote {out}; {'PASS' if failures == 0 else 'FAIL'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
