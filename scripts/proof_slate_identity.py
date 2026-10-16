"""Refactor proof: extracting `evaluate_slate` changes no pick.

PR 3a moved the per-slate evaluation loop out of `pipeline._strategy_picks`
into `strategy/slate.py::evaluate_slate` so the live pipeline and the replay
share one implementation; `replay.py` was converted in PR 3b and now calls
it too. This proof covers the pipeline arm, which decides every live pick,
so "no behavior change" has to be demonstrated, not asserted.

This replays BOTH implementations over the pipeline's own captured history
(`data/games/games.csv` + `data/odds/lines.csv`, offline, no API credits):

  OLD: the pre-refactor loop from pipeline.py at the commit before the
       extraction, with its one `now_utc()` call replaced by an injected
       `as_of` so the two arms cannot differ by wall clock. NOT verbatim:
       it calls the moved helpers (build_dossier / pick_row / slot_map_for)
       from their new home, so those are shared by both arms and are
       outside what this proof compares;
  NEW: `strategy/slate.py::evaluate_slate` through the refactored
       `pipeline._strategy_picks`'s own argument shape.

and asserts the emitted ledger rows are field-for-field identical, for every
enabled live strategy, on every captured slate day, under both cutoff shapes
(`as_of=None`, the dry-run/whole-slate case, and a pinned mid-morning
`as_of`, the live case that skips games already under way).

`created_ts_utc` is excluded: `pick_row` stamps it from the clock, so it
differs between two runs of the SAME code and proves nothing. Everything else
is compared, `pick_id` and `config_hash` included.

Why both arms pin the clock: `splits_signal._splits_guards` ages captured
splits against `now_utc()`, so a splits row sitting on the staleness boundary
reads fresh for one arm and stale for the other, and the comparison goes
flaky. Pinned per day to that day's own capture time.

Run from the repo root: .venv/bin/python scripts/proof_slate_identity.py
(it imports panthera_mvp, so it needs the editable install)
Writes docs/proofs/slate-identity.md and exits non-zero on any mismatch.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

from panthera_mvp import store
from panthera_mvp.clients import mlb
from panthera_mvp.config import config_hash, load_strategy_configs
from panthera_mvp.strategy import splits_signal
from panthera_mvp.strategy.dossier import SeasonContext
from panthera_mvp.strategy.movement import extract_game_prices, extract_totals_prices
from panthera_mvp.strategy.registry import StrategyContext, engines
from panthera_mvp.strategy.rules import Pass, Pick
from panthera_mvp.strategy.season import in_scope
from panthera_mvp.strategy.slate import build_dossier, evaluate_slate, pick_row, slot_map_for
from panthera_mvp.timeutil import ET, parse_utc

OUT = Path("docs/proofs/slate-identity.md")

#: Excluded from the comparison: stamped from the clock by `pick_row`, so it
#: differs between two runs of identical code.
VOLATILE = ("created_ts_utc",)


def _old_loop(
    sid, scfg, games, events_by_pk, lines_today, season_ctx, snap_label,
    window, d, as_of_et, existing_pks, budget, splits_lookup,
):
    """The pre-refactor `_strategy_picks` inner loop, verbatim except that its
    `now_utc().astimezone(ET)` is the injected `as_of_et` and the budget /
    already-picked set are passed in rather than read from the ledger."""
    engine = engines()[scfg["strategy"]["engine"]]
    chash = config_hash(scfg)
    slot_map = slot_map_for(scfg, games, d)

    end_h, end_m = window
    picks: list[Pick] = []
    passes: list[Pass] = []
    for g in games:
        start_et = g.start_utc.astimezone(ET)
        if (start_et.hour, start_et.minute) > (end_h, end_m):
            continue
        if as_of_et is not None and start_et <= as_of_et:
            continue
        if scfg["bet_limits"]["one_pick_per_game"] and g.game_pk in existing_pks:
            continue
        event_id = events_by_pk.get(g.game_pk)
        prices = (
            extract_game_prices(
                lines_today, event_id, g.home_team, g.away_team, latest_label=snap_label
            )
            if event_id
            else None
        )
        totals = (
            extract_totals_prices(lines_today, event_id, latest_label=snap_label)
            if event_id and scfg["strategy"]["engine"] == "orig_rules"
            else None
        )
        ctx = StrategyContext(
            game=g,
            odds_event_id=event_id,
            prices=prices,
            totals=totals,
            slot_type=slot_map.get(g.game_pk),
            dossier=build_dossier(g, season_ctx, scfg),
            cfg=scfg,
            splits=splits_lookup(g) if splits_lookup else None,
        )
        result = engine(ctx)
        if isinstance(result, Pick):
            picks.append(result)
        elif isinstance(result, Pass):
            passes.append(result)
    if budget is not None:
        picks = picks[:budget]
    return [pick_row(p, sid, scfg, chash) for p in picks], passes


def _games_for(day_games) -> list:
    out = []
    for row in day_games.itertuples(index=False):
        out.append(
            mlb.GameInfo(
                game_pk=int(row.game_pk),
                game_date_et=str(row.game_date_et),
                game_type=str(row.game_type),
                status="Preview",
                detailed_state="Scheduled",
                start_utc=parse_utc(str(row.start_time_utc)),
                doubleheader=str(row.doubleheader) if pd.notna(row.doubleheader) else "N",
                game_number=int(row.game_number) if pd.notna(row.game_number) else 1,
                home_team_id=int(row.home_team_id),
                home_team=str(row.home_team),
                away_team_id=int(row.away_team_id),
                away_team=str(row.away_team),
                home_pitcher=None,
                away_pitcher=None,
            )
        )
    return out


def _splits_lookup(splits_today):
    """Bound to this day's frame, so the loop variable cannot leak into it."""
    if splits_today.empty:
        return None

    def lookup(g):
        return splits_signal.extract_game_splits(splits_today, g.game_pk, g.start_utc)

    return lookup


def _strip(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k not in VOLATILE} for r in rows]


def main() -> int:
    games_df, lines = store.load_games(), store.load_lines()
    if games_df.empty or lines.empty:
        print("no captured history; nothing to prove", file=sys.stderr)
        return 1
    lines = lines.dropna(subset=["game_pk"]).astype({"game_pk": int})

    splits = splits_signal.pd.DataFrame()
    try:
        from panthera_mvp.clients.lumify import load_splits

        splits = load_splits()
    except Exception as exc:  # noqa: BLE001 - proof records it rather than dying
        print(f"[warn] splits unavailable: {exc}", file=sys.stderr)

    strategies = {
        sid: cfg
        for sid, cfg in sorted(load_strategy_configs(known_engines=set(engines())).items())
        if cfg["strategy"].get("enabled") and "live" in cfg["strategy"]["scope"]
    }

    days = sorted(games_df["game_date_et"].unique())
    # What this run read, stamped into the report so the counts date
    # themselves rather than standing as bare assertions.
    games_rows = len(games_df)
    # Splits too: an absent splits.csv does NOT raise (load_splits returns an
    # empty frame), so fade_public and sharp_split would quietly emit far
    # fewer picks and the doc would still read "0 mismatches".
    splits_rows = len(splits)
    latest_day = str(games_df["game_date_et"].max())
    real_now = splits_signal.now_utc
    compared = mismatched = 0
    picks_seen = 0
    detail: list[str] = []

    for sid, scfg in strategies.items():
        ctx = SeasonContext()
        sid_mismatch = 0
        sid_picks = 0
        for day in days:
            day_games_df = games_df[games_df["game_date_et"] == day]
            lines_today = lines[lines["game_date_et"] == day]
            splits_today = (
                splits[splits["game_date_et"] == day] if not splits.empty else splits
            )
            if not lines_today.empty:
                events_by_pk = (
                    lines_today.drop_duplicates("game_pk")
                    .set_index("game_pk")["odds_event_id"]
                    .to_dict()
                )
                games = _games_for(day_games_df)

                # Pin the clock splits staleness is measured against, or the
                # two arms can straddle the boundary and the proof goes flaky.
                cap = (
                    pd.to_datetime(splits_today["captured_at"], utc=True, errors="coerce").max()
                    if not splits_today.empty and "captured_at" in splits_today.columns
                    else pd.NaT
                )
                pinned = (
                    (cap + pd.Timedelta(hours=1)).to_pydatetime()
                    if not pd.isna(cap)
                    else None
                )
                splits_signal.now_utc = (lambda v: (lambda: v or real_now()))(pinned)
                lookup = _splits_lookup(splits_today)

                # Both cutoff shapes: the dry-run whole-slate case and the
                # live case that skips games already under way.
                cutoffs = [None]
                starts = [g.start_utc.astimezone(ET) for g in games]
                if starts:
                    cutoffs.append(min(starts) + timedelta(minutes=45))

                for as_of in cutoffs:
                    for window in [(16, 0), (23, 59)]:
                        for budget in (None, 2):
                            # An engine that raises is compared as its
                            # exception, not propagated: the captured history
                            # holds at least one unusable price (a 0.0 that
                            # makes american_to_decimal divide by zero), and
                            # the question here is whether the two arms behave
                            # IDENTICALLY, errors included. Live, cmd_picks
                            # isolates the same exception per strategy.
                            try:
                                old_rows, old_passes = _old_loop(
                                    sid, scfg, games, events_by_pk, lines_today, ctx,
                                    "pregame", window, day, as_of, set(), budget, lookup,
                                )
                                old_out = (_strip(old_rows), [repr(x) for x in old_passes])
                            except Exception as exc:  # noqa: BLE001
                                old_rows = []
                                old_out = f"RAISED {type(exc).__name__}: {exc}"
                            chash = config_hash(scfg)
                            try:
                                new = evaluate_slate(
                                    engine=engines()[scfg["strategy"]["engine"]],
                                    scfg=scfg,
                                    games=games,
                                    events_by_pk=events_by_pk,
                                    lines_today=lines_today,
                                    season_ctx=ctx,
                                    snap_label="pregame",
                                    window=window,
                                    date_et=day,
                                    as_of_et=as_of,
                                    already_picked_pks=set(),
                                    budget=budget,
                                    splits_lookup=lookup,
                                )
                                new_rows = [pick_row(p, sid, scfg, chash) for p in new.picks]
                                new_out = (_strip(new_rows), [repr(x) for x in new.passes])
                            except Exception as exc:  # noqa: BLE001
                                new_rows = []
                                new_out = f"RAISED {type(exc).__name__}: {exc}"
                            compared += 1
                            sid_picks += len(new_rows)
                            if old_out != new_out:
                                sid_mismatch += 1
                                if sid_mismatch <= 3:
                                    detail.append(
                                        f"- MISMATCH {sid} {day} as_of={as_of} "
                                        f"window={window} budget={budget}: "
                                        f"{len(old_rows)} old vs {len(new_rows)} new"
                                    )
                splits_signal.now_utc = real_now

            # Advance the season context after the day — no lookahead.
            for row in day_games_df[day_games_df["status"] == "Final"].itertuples(index=False):
                if pd.isna(row.home_score) or pd.isna(row.away_score):
                    continue
                if not in_scope(str(row.game_type), scfg):
                    continue
                ctx.add_final(
                    row.home_team_id, row.away_team_id,
                    int(row.home_score), int(row.away_score),
                )
        mismatched += sid_mismatch
        picks_seen += sid_picks
        detail.append(
            f"| `{sid}` | {sid_picks} | {'**MISMATCH**' if sid_mismatch else 'identical'} |"
        )

    report = [
        "# Refactor proof: `evaluate_slate` extraction is pick-identical",
        "",
        "Generated by `.venv/bin/python scripts/proof_slate_identity.py` "
        "(offline; reads `data/games/games.csv` + `data/odds/lines.csv`, no "
        "network, no API credits).",
        "",
        "PR 3a moved the per-slate evaluation loop out of "
        "`pipeline._strategy_picks` into `strategy/slate.py::evaluate_slate`. "
        "That loop decides every live pick, so this replays the pre-refactor "
        "loop and the extracted one over the same captured history with the "
        "same inputs and compares the ledger rows they emit, field for field "
        "(`created_ts_utc` excluded — `pick_row` stamps it from the clock, so "
        "it differs between two runs of identical code).",
        "",
        f"Scenarios compared: **{compared}** — every enabled live strategy "
        f"x {len(days)} captured slate days x two cutoff shapes (whole-slate "
        "and a pinned live cutoff) x two windows (16:00, 23:59) x two budgets "
        f"(uncapped, 2). Picks emitted across them: **{picks_seen}**.",
        "",
        f"**Mismatches: {mismatched}.**",
        "",
        # Stamp what the run actually read. Without it the counts above are
        # a bare assertion: `data/` grows on every bot commit, so a reader
        # months later cannot tell whether they describe the history they
        # are looking at. Re-rendering this in CI would be the wrong fix —
        # it would take minutes and redden on honest data growth — so the
        # doc dates itself instead.
        "**One known, intended non-identity.** The pre-refactor loop read the "
        "clock per game (`start_et <= now_utc()`); the extracted loop takes a "
        "single hoisted `as_of`. Both arms below use the hoisted form, so the "
        "comparison cannot see it. The effect is that a game whose start time "
        "passes mid-loop is now judged consistently across the slate instead "
        "of flipping partway through — it cannot produce a pick the old code "
        "would not have made earlier in the same loop, but it is a difference "
        "and this proof is not evidence about it.",
        "",
        "**What the proof does NOT cover.** `build_dossier`, `pick_row` and "
        "`slot_map_for` moved modules unchanged, and BOTH arms import the new "
        "copies, so they are outside the comparison; the diff is their "
        "evidence. The proof also calls `evaluate_slate` directly rather than "
        "`pipeline._strategy_picks`, so the `dry_run -> as_of_et=None` mapping "
        "and the ledger-derived budget are not exercised here (they are "
        "covered by `tests/test_slate.py` and the pipeline tests).",
        "",
        f"_Data basis: `data/games/games.csv` at {games_rows} rows, latest "
        f"`game_date_et` {latest_day}; `data/splits/splits.csv` at "
        f"{splits_rows} rows. The counts above describe that snapshot; "
        f"regenerate after the datastore grows._",
        "",
        "| strategy | picks emitted | result |",
        "|---|---|---|",
    ]
    report += [d for d in detail if d.startswith("|")]
    extras = [d for d in detail if not d.startswith("|")]
    if extras:
        report += ["", "## Mismatch detail", ""] + extras
    report += [
        "",
        "The splits staleness clock is pinned per day to that day's own "
        "capture time: `splits_signal._splits_guards` ages captured splits "
        "against `now_utc()`, so an unpinned comparison straddles the "
        "staleness boundary and goes flaky.",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report += [
        "",
        "## Rollback and ownership",
        "",
        "**Owner:** the repo owner, Christopher Queen (`@gitchrisqueen`). No",
        "on-call rotation.",
        "",
        "**Revert:** `git revert` the squash commit of PR #70 on `main`. It is",
        "self-contained — `replay.py` is untouched by it and the 28-column",
        "pick schema does not change — so nothing else has to move with it.",
        "",
        "**Detection is manual, and this is the important part.** `config_hash`",
        "is computed over the strategy YAML, NOT over code, so a behaviour",
        "regression inside the evaluation loop does not move any hash:",
        "`hash_lineage` and `tests/test_live_config.py` cannot see it. Picks",
        "are append-once and settle in place, so a wrong pick cannot be",
        "un-written by reverting the code. On the first scheduled run after",
        "this merges, compare that run's new rows in `data/picks/picks.csv`",
        "against what the previous commit produced for the same slate; the",
        "offline check needs no API credits:",
        "",
        "Run it on a date that HAS odds rows: `cmd_picks` returns early with",
        "\"no odds lines for today\" when it does not, both arms then write",
        "nothing, and an empty diff would read as \"no regression\" while",
        "proving nothing. The guard below fails loudly on that.",
        "",
        "```bash",
        "# Two checkouts, one datastore copy each, the SAME recorded schedule;",
        "# diff the picks they produce. Never `git stash` for this: the stash",
        "# stack is shared across worktrees and other sessions may be using it.",
        "BASE=$(git rev-parse HEAD~1)          # the commit before the merge",
        "OUT=$(mktemp -d)",
        "for REF in HEAD \"$BASE\"; do",
        "  WT=$(mktemp -d); CHECK=$(mktemp -d)",
        "  git worktree add -q --detach \"$WT\" \"$REF\"",
        "  cp -R data config \"$CHECK\"/   # BOTH: paths.config_dir() is $ROOT/config",
        "  (cd \"$WT\" && python3.12 -m venv .venv && .venv/bin/pip install -q -e .",
        "   # PANTHERA_MLB_FIXTURE, not _ODDS_: `picks` reads the schedule, and",
        "   # without it _refresh_games calls statsapi.mlb.com for real.",
        "   export PANTHERA_ROOT=\"$CHECK\"",
        "   export PANTHERA_MLB_FIXTURE=\"$WT/tests/fixtures/mlb_schedule.json\"",
        "   .venv/bin/panthera-mvp picks --window-end-et 23:59 --label manual)",
        "  cp \"$CHECK\"/data/picks/picks.csv \"$OUT/picks-${REF//\\//_}.csv\"",
        "  git worktree remove --force \"$WT\"",
        "done",
        "",
        "# Both arms must have produced something, or the diff is vacuous.",
        "for f in \"$OUT\"/picks-*.csv; do",
        "  [ \"$(wc -l < \"$f\")\" -gt 1 ] || { echo \"VACUOUS: $f has no picks\"; exit 1; }",
        "done",
        "diff \"$OUT/picks-HEAD.csv\" \"$OUT/picks-$BASE.csv\"",
        "```",
        "",
        "Expect no difference in any behaviour-bearing column. `pick_id`,",
        "`created_ts_utc` and `config_hash` are not behaviour: the first two",
        "are stamped per run and the third moves with the strategy YAML.",
        "",
        "**Containment for rows already written.** Picks are append-once and",
        "settle in place, and `config_hash` covers only the YAML — so picks",
        "made by a regressed loop cannot be un-written OR segmented out of a",
        "strategy's verdict sample by hash. If a regression reaches the",
        "ledger: record the affected `pick_id`s in a run note and in",
        "`reports/BETTING_REPORT.md`, then treat re-registering the affected",
        "strategies under new ids with fresh counters as the remedy — which is",
        "a behavioural-change call under `src/panthera_mvp/CLAUDE.md`, so it is",
        "Christopher's, not an agent's.",
        "",
        "**Trigger:** a slate where the strategies pick a different set of",
        "games than the pre-merge code did on the same inputs, or a capped day",
        "that keeps later games than it used to (the truncation bias depends",
        "on the caller passing schedule order — see",
        "`tests/test_slate.py::test_the_cap_follows_input_order_not_start_time`).",
        "",
        "**Not a trigger:** a change in which games are skipped as already",
        "started. The clock is now read once per slate rather than per game,",
        "which is the known non-identity recorded above.",
        "",
    ]
    OUT.write_text("\n".join(report))
    print(f"wrote {OUT}; {compared} scenarios, {picks_seen} picks, "
          f"{mismatched} mismatches — {'PASS' if mismatched == 0 else 'FAIL'}")
    return 1 if mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
