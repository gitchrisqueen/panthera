"""`panthera-mvp catchup` — find the days the pipeline missed and repair them.

The remediator half of the pair `doctor` detects for. On 2026-09-29 a config
whitelist made every live strategy pass on every postseason game; the
workflows stayed green, the data stayed current, and 14 slate days produced
no picks. `doctor` now catches that within a day. This fills the hole it
leaves behind.

**What a gap is.** Not "the day has no picks", and not "the day has no pass
rows" either — the outage WROTE pass rows, 145 of them, so any "did it run?"
test sees a healthy day. There are three states:

  1. never ran          — no picks, no passes.
  2. ran and passed     — passes whose reasons still reflect the engine's
                          judgement. NOT a gap; re-running would be wrong.
  3. ran under a config since corrected — pass rows produced by a gate that
                          no longer exists. A gap, and invisible to (1)'s test.

State 3 is only knowable because a human lists the invalidated pass-reason
prefixes in `config/health.yaml` (`catchup.mlb.void_pass_reasons`) after
diagnosing the fault. Deciding that a past pass was WRONG is a judgment, not
a computation — so the automatic part of this is state 1, and state 3 becomes
one config line once `doctor` has surfaced the cause. The self-healing claim
rests on the pair, never on this command alone.

**Where repairs go.** `data/picks/shadow_picks.csv`, never `picks.csv`. A
backdated pick is not a forward paper trade: the result is already known, and
CLV is structurally unfillable for it (`clv.py` needs a snapshot strictly
after `created_ts_utc`). `report.py` renders the shadow ledger as an
explicitly non-evaluable section. There is no code path from here to
`picks.csv`, and the workflow asserts that again before it commits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

from . import store
from .doctor import load_health_config, today_et
from .strategy.registry import engines
from .strategy.season import in_scope
from .timeutil import now_utc, utc_iso

SPORTS = ("mlb", "ncaaf", "ncaabase")


@dataclass
class Gap:
    sport: str
    strategy_id: str
    date_et: str
    missing_games: int
    reason: str  # never_ran | voided_config


@dataclass
class CatchupReport:
    today_et: str
    window: tuple[str, str]
    gaps: list[Gap] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    shadow_added: int = 0
    graded: int = 0
    dry_run: bool = True

    def as_dict(self) -> dict:
        return {
            "schema": 1,
            "generated_ts_utc": utc_iso(now_utc()),
            "today_et": self.today_et,
            "window": {"from": self.window[0], "to": self.window[1]},
            "dry_run": self.dry_run,
            "gaps": [vars(g) for g in self.gaps],
            "partial_gaps": self.partial,
            "notes": self.notes,
            "shadow_rows_added": self.shadow_added,
            "graded": self.graded,
        }


def _void_prefixes(cfg: dict, sport: str) -> tuple[str, ...]:
    block = (cfg.get("catchup") or {}).get(sport) or {}
    return tuple(block.get("void_pass_reasons") or ())


def _is_void(reason: str, prefixes: tuple[str, ...]) -> bool:
    """A pass reason is void if it carries any invalidated prefix. Reasons are
    stored with a `[RULE_ID] ` prefix, so this is a substring test."""
    r = str(reason)
    return any(p in r for p in prefixes)


def detect_mlb_gaps(
    cfg: dict, from_et: str, to_et: str
) -> tuple[list[Gap], list[str], list[str]]:
    """Returns (gaps, partial-gap descriptions, notes).

    The decision is per (strategy, DAY), not per game, and that distinction
    is the whole correctness of this function. A live run evaluates only the
    games starting inside its window and not yet under way, so on any healthy
    day some games produce neither a pick nor a pass. Judging per game
    therefore flags every day a strategy legitimately made no picks: the
    first draft of this reported 8 false-positive dates where `pv_orig` had
    written perfectly good passes ("saturday is an off day", "no natural/scam
    signal for this slot") and `sharp_split` had written "no-divergence".

    Per (strategy, date), with `ran` meaning the ledger holds ANY pick or
    pass from that strategy that day:

        never_ran      not `ran`, while at least one in-scope game that day
                       had captured odds — the run simply did not happen.
        voided_config  `ran`, no picks, and EVERY pass carries a reason
                       prefix that `catchup.<sport>.void_pass_reasons` marks
                       as invalidated by a config fix. This is the state the
                       2026-09-29 outage was in: it ran, it wrote 145 passes,
                       and all of them were produced by a gate that no longer
                       exists.
        otherwise      not a gap. `ran` with a pick, or with one surviving
                       pass, means the engine had its say.

    A day that `ran`, made picks, AND carries void passes is a PARTIAL gap:
    reported, never repaired, because repairing it would mean re-opening that
    day's pick budget, and that touches `picks.csv` semantics.
    """
    from .config import config_hash, load_strategy_configs

    games, lines = store.load_games(), store.load_lines()
    picks, passes = store.load_picks(), store.load_passes()
    done = store.load_catchup_log()
    notes: list[str] = []
    if games.empty:
        return [], [], ["no captured games; nothing to detect"]

    strategies = load_strategy_configs(known_engines=set(engines()))
    live = {
        sid: scfg
        for sid, scfg in sorted(strategies.items())
        if scfg["strategy"].get("enabled") and "live" in scfg["strategy"]["scope"]
    }
    prefixes = _void_prefixes(cfg, "mlb")

    priced = (
        set(lines.dropna(subset=["game_pk"]).astype({"game_pk": int})["game_pk"])
        if not lines.empty
        else set()
    )
    gaps: list[Gap] = []
    partial: list[str] = []

    dates = [
        d for d in sorted(games["game_date_et"].unique()) if from_et <= d <= to_et
    ]
    for sid, scfg in live.items():
        chash = config_hash(scfg)
        completed = (
            set(
                done[
                    (done["sport"] == "mlb")
                    & (done["strategy_id"] == sid)
                    & (done["config_hash"] == chash)
                ]["game_date_et"].astype(str)
            )
            if not done.empty
            else set()
        )
        for d in dates:
            if d in completed:
                continue  # repaired under this very config; not a gap again
            day = games[games["game_date_et"] == d]
            # Only games this config admits AND that had captured odds: an
            # unpriced game could never have been evaluated, so its absence
            # is never evidence of a gap.
            playable = {
                int(r.game_pk)
                for r in day.itertuples(index=False)
                if in_scope(str(r.game_type), scfg) and int(r.game_pk) in priced
            }
            if not playable:
                continue
            mine_p = (
                picks[(picks["game_date_et"] == d) & (picks["strategy_id"] == sid)]
                if not picks.empty
                else picks
            )
            mine_z = (
                passes[(passes["game_date_et"] == d) & (passes["strategy_id"] == sid)]
                if not passes.empty
                else passes
            )
            ran = not mine_p.empty or not mine_z.empty
            void_passes = (
                [r for r in mine_z.itertuples(index=False) if _is_void(r.reason, prefixes)]
                if not mine_z.empty
                else []
            )

            if not ran:
                gaps.append(
                    Gap("mlb", sid, d, len(playable), "never_ran")
                )
                continue
            if not mine_p.empty:
                if void_passes:
                    partial.append(
                        f"{sid} {d}: {len(mine_p)} pick(s) made but "
                        f"{len(void_passes)} pass(es) came from a corrected "
                        "config — partial gap, reported only"
                    )
                continue
            if void_passes and len(void_passes) == len(mine_z):
                gaps.append(
                    Gap("mlb", sid, d, len(playable), "voided_config")
                )
    if prefixes:
        notes.append(
            f"mlb void_pass_reasons in effect: {', '.join(prefixes)} "
            "(config/health.yaml)"
        )
    return gaps, partial, notes


def _default_window(cfg: dict, from_et: str | None, to_et: str | None):
    """`to` defaults to YESTERDAY, never today: today belongs to the live
    morning and pregame runs, and a catch-up racing them would write shadow
    picks for a slate still being decided."""
    today = today_et()
    to_et = to_et or str(today - timedelta(days=1))
    lookback = int((cfg.get("catchup") or {}).get("max_lookback_days", 45))
    floor = str(today - timedelta(days=lookback))
    from_et = from_et or floor
    truncated = from_et < floor
    return (max(from_et, floor), to_et), truncated, floor


def _rebuild_markers(
    sport: str,
    win_from: str,
    win_to: str,
    strategy: list[str] | None,
    *,
    explicit: bool,
    yes: bool,
    dry_run: bool,
) -> list[str]:
    """Forget completion markers in the window so those dates are detected as
    gaps again.

    Markers only. Shadow rows stay: `append_shadow_picks` dedupes on
    `pick_id`, so replaying an unchanged config adds none, and a changed
    config legitimately adds the rows it now produces.
    """
    if not explicit:
        return ["--rebuild needs an explicit --from and --to; nothing removed"]
    done = store.load_catchup_log()
    rows = (
        done[done["sport"].astype(str) == sport] if not done.empty else done
    )
    if strategy and not rows.empty:
        rows = rows[rows["strategy_id"].astype(str).isin(strategy)]
    dates = (
        {d for d in rows["game_date_et"].astype(str) if win_from <= d <= win_to}
        if not rows.empty
        else set()
    )
    if not dates:
        return [f"--rebuild found no completion markers in {win_from}..{win_to}"]
    if not yes:
        return [
            f"--rebuild would forget {len(dates)} marked date(s) in "
            f"{win_from}..{win_to}; needs --yes; nothing removed"
        ]
    if dry_run:
        return [
            f"--rebuild (dry run) would forget {len(dates)} marked date(s) "
            f"in {win_from}..{win_to}"
        ]
    removed = store.drop_catchup_log(sport, dates, strategy_ids=strategy)
    return [f"--rebuild forgot {removed} completion marker(s)"]


def cmd_catchup(
    sport: str = "all",
    from_et: str | None = None,
    to_et: str | None = None,
    strategy: list[str] | None = None,
    dry_run: bool = False,
    rebuild: bool = False,
    as_json: bool = False,
    no_network: bool = False,
    yes: bool = False,
) -> int:
    cfg = load_health_config()
    (win_from, win_to), truncated, floor = _default_window(cfg, from_et, to_et)
    report = CatchupReport(
        today_et=str(today_et()), window=(win_from, win_to), dry_run=dry_run
    )
    if truncated:
        report.notes.append(
            f"window floored at {floor} by catchup.max_lookback_days; dates "
            f"before it were NOT examined"
        )

    sports = list(SPORTS) if sport == "all" else [sport]

    if "mlb" in sports:
        if rebuild:
            # Before detection, and over the whole requested window. A date
            # already marked complete is skipped by `detect_mlb_gaps`, so
            # dropping markers for the dates it DID return could never
            # re-open the ones `--rebuild` exists to re-open.
            report.notes += _rebuild_markers(
                "mlb",
                win_from,
                win_to,
                strategy,
                explicit=from_et is not None and to_et is not None,
                yes=yes,
                dry_run=dry_run,
            )
        gaps, partial, notes = detect_mlb_gaps(cfg, win_from, win_to)
        report.gaps += gaps
        report.partial += partial
        report.notes += notes
        gap_dates = sorted({g.date_et for g in gaps})
        sids = sorted({g.strategy_id for g in gaps})
        if strategy:
            sids = [s for s in sids if s in strategy]
            gap_dates = sorted(
                {g.date_et for g in gaps if g.strategy_id in strategy}
            )
        if gap_dates and not dry_run:
            from .replay import replay_window

            res = replay_window(
                strategy_ids=sids or None,
                from_et=min(gap_dates),
                to_et=max(gap_dates),
                only_dates=set(gap_dates),
                grade=True,
                run_label="catchup",
                quiet=as_json,
            )
            report.shadow_added = res.added
            report.graded = res.graded
            store.append_catchup_log(
                pd.DataFrame(
                    [
                        {
                            "ts_utc": utc_iso(now_utc()),
                            "sport": "mlb",
                            "strategy_id": g.strategy_id,
                            "game_date_et": g.date_et,
                            "outcome": g.reason,
                            "shadow_rows_added": res.added,
                            "config_hash": _hash_for(g.strategy_id),
                        }
                        for g in gaps
                        if not strategy or g.strategy_id in strategy
                    ]
                )
            )

    if "ncaaf" in sports:
        report.notes.append(
            "ncaaf: detection and grading only — no retroactive tickets. "
            "cfb_spread_total_parlay decides inside a kickoff-relative window "
            "against a decision-<date> snapshot taken at that moment; "
            "rebuilding a ticket from the week's open snapshot would be a "
            "different strategy writing to a real ledger."
        )
        if not no_network and not dry_run:
            from .ncaaf.pipeline import cmd_grade as ncaaf_grade

            ncaaf_grade(None)

    if "ncaabase" in sports:
        report.notes.append(
            "ncaabase: no strategy is registered, so catch-up is data backfill "
            "only (games + grade), and it no-ops outside the season window in "
            "config/ncaabase.yaml."
        )
        if not no_network and not dry_run:
            from .ncaabase.pipeline import cmd_games as nb_games
            from .ncaabase.pipeline import cmd_grade as nb_grade

            nb_games(None)
            nb_grade(None)

    if as_json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        _render(report)
    return 0


def _hash_for(sid: str) -> str:
    from .config import config_hash, load_strategy_configs

    return config_hash(load_strategy_configs(known_engines=set(engines()))[sid])


def _render(r: CatchupReport) -> None:
    print(
        f"panthera-mvp catchup — {r.today_et} ET — window {r.window[0]}..{r.window[1]}"
        + ("  (dry run)" if r.dry_run else "")
    )
    print()
    if not r.gaps:
        print("no gaps detected")
    else:
        by_date: dict[str, list[Gap]] = {}
        for g in r.gaps:
            by_date.setdefault(g.date_et, []).append(g)
        print(f"{len(r.gaps)} gap(s) over {len(by_date)} date(s):")
        for d in sorted(by_date):
            gs = by_date[d]
            sids = ", ".join(sorted(g.strategy_id for g in gs))
            why = sorted({g.reason for g in gs})
            print(f"  {d}  {sids}  ({'/'.join(why)})")
    if r.partial:
        print()
        print("partial gaps (reported, never repaired — see the module docstring):")
        for line in r.partial:
            print(f"  {line}")
    if r.notes:
        print()
        for n in r.notes:
            print(f"note: {n}")
    print()
    if r.dry_run:
        print("dry run: nothing written")
    else:
        print(
            f"{r.shadow_added} shadow pick(s) added, {r.graded} graded "
            "(data/picks/shadow_picks.csv — never picks.csv)"
        )
