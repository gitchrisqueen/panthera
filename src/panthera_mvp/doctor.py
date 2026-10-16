"""`panthera-mvp doctor` — cross-sport staleness and health checks.

Why this exists. The last MLB pick landed on 2026-09-27 and the first
all-silent slate was 2026-09-29. Nothing crashed: every
workflow ran on schedule, odds/splits/games stayed current, and
reports/daily/*.md printed the reason — `game_type=L` — in plain text every
single day. A regular-season whitelist in config/strategy.yaml was passing on
every postseason game. It ran for 14 slate days and 145 passes because the
repo had no way to notice, not because the evidence was missing.

So the checks here are built around one idea: **a pipeline that produces
nothing while reporting success is the failure mode that hides.** H01 and H02
look for exactly that signature — every engine falling silent for the same
stated reason — rather than for an exception that was never raised.

Properties this module must keep:

- **Zero API cost.** Every input is a CSV already committed to the repo.
  `odds.last_known_remaining()` reads data/odds/credit_log.csv, not the
  network. `tests/test_doctor.py::test_doctor_makes_no_network_calls` enforces
  it by making every HTTP request raise.
- **Read-only.** A health check that writes is a health check that can break
  the thing it watches. Nothing here touches data/ or reports/.
- **Cross-sport, and tolerant of a missing sport.** Each sport's store is
  imported lazily, so an absent data tree (data/ncaabase/ does not exist
  today) is a finding, never a traceback.
- **Idle is not broken.** Out of season, every check downgrades to INFO.
  A tool that cries through every offseason is a tool nobody reads.

Thresholds live in config/health.yaml — never in config/strategy.yaml, which
is hashed into every pick's config_hash. That file's header explains why.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from . import paths
from .timeutil import ET, now_utc

SPORTS = ("mlb", "ncaaf", "ncaabase")

#: Ordered worst-first, which is also the render order.
LEVELS = ("fail", "warn", "ok", "info", "idle")

EXIT_OK = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_BROKEN = 3


class DoctorConfigError(RuntimeError):
    """config/health.yaml is missing or unusable. Exits 3: doctor could not
    run, which is a different thing from doctor finding nothing wrong, and
    must never be reported as a clean bill of health."""


@dataclass
class Finding:
    id: str
    check: str
    sport: str
    level: str
    title: str
    detail: str = ""
    since: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_command: str | None = None

    @property
    def fingerprint(self) -> str:
        """Stable identity of this finding across runs — the dedupe key for
        the GitHub issue reconciler. Deliberately excludes dates and counts so
        a worsening problem updates its issue instead of opening another."""
        return f"{self.sport}/{self.check}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "check": self.check,
            "sport": self.sport,
            "level": self.level,
            "fingerprint": self.fingerprint,
            "title": self.title,
            "detail": self.detail,
            "since": self.since,
            "evidence": self.evidence,
            "suggested_command": self.suggested_command,
        }


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def load_health_config(path: Path | None = None) -> dict[str, Any]:
    path = path or paths.config_dir() / "health.yaml"
    if not path.exists():
        raise DoctorConfigError(f"missing {path} — see the file header for its contents")
    try:
        cfg = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise DoctorConfigError(f"{path} is not valid YAML: {exc}") from exc
    if "doctor" not in cfg:
        raise DoctorConfigError(f"{path} has no `doctor:` block")
    return cfg


def _check_cfg(cfg: dict, name: str) -> dict:
    return (cfg["doctor"].get("checks") or {}).get(name) or {}


def _cli_prefix(sport: str) -> str:
    """The CLI namespace for a sport: '' for MLB, 'ncaaf ' / 'ncaabase ' else.

    H05 suggested `panthera-mvp grade` for every sport, and `grade` WRITES.
    A copy-paste from an NCAAF finding would have graded MLB while the NCAAF
    pick it was about stayed pending — a remediation that mutates the wrong
    sport is worse than none.
    """
    return "" if sport == "mlb" else f"{sport} "


def _check_enabled(cfg: dict, fn) -> bool:
    """`checks.<name>.enabled` for one check function.

    Applied centrally at dispatch so EVERY check honours it. Three of the
    nine used to test it individually and the other six ignored it, which
    left no config-level way to mute a noisy check — the only recourse was
    disabling the whole workflow, and a health check people mute wholesale is
    worse than none.
    """
    name = fn.__name__.removeprefix("check_")
    return bool(_check_cfg(cfg, name).get("enabled", True))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def today_et() -> date:
    return now_utc().astimezone(ET).date()


def _age_days(day: str, today: date) -> int:
    return (today - date.fromisoformat(str(day)[:10])).days


def reason_key(reason: Any) -> str:
    """The part of a pass reason that identifies its CAUSE, ignoring the
    per-game specifics.

    `[R0] excluded_game_type=D` -> `excluded_game_type`. A prose reason has no
    `=`, so it is its own key: `[FP_ml] no-splits: none captured for game` ->
    `no-splits: none captured for game`. That is the behavior we want — prose
    reasons are already cause-shaped, while per-game detail ("heavy favorite
    -220") varies between games and so never looks uniform.
    """
    text = re.sub(r"^\[[^\]]*\]\s*", "", str(reason))
    return text.split("=")[0].strip()


def _slate_days(games: pd.DataFrame, since: str, today: date) -> list[str]:
    """ET dates with at least one scheduled game, oldest first, bounded by the
    lookback window and never including today — today's slate is still being
    worked by the live runs."""
    if games.empty or "game_date_et" not in games.columns:
        return []
    days = {str(d) for d in games["game_date_et"].dropna()}
    return sorted(d for d in days if since <= d < str(today))


# --------------------------------------------------------------------------
# per-sport data access (lazy: a missing sport is a finding, not a crash)
# --------------------------------------------------------------------------


@dataclass
class SportData:
    sport: str
    games: pd.DataFrame
    lines: pd.DataFrame
    picks: pd.DataFrame
    passes: pd.DataFrame
    available: bool = True
    note: str = ""


_EMPTY = pd.DataFrame()


def load_sport(sport: str) -> SportData:
    """Read one sport's committed CSVs. Never raises for a sport that simply
    is not set up yet — data/ncaabase/ does not exist in this repo today."""
    try:
        if sport == "mlb":
            from . import store

            return SportData(
                sport,
                store.load_games(),
                store.load_lines(),
                store.load_picks(),
                store.load_passes(),
            )
        if sport == "ncaaf":
            from .ncaaf import store as ncaaf_store

            # NCAAF's unit of work is a parlay ticket, not a pick, and it has
            # no passes.csv; `decisions.csv` is the nearest equivalent and is
            # read by its own check rather than squeezed into this shape.
            return SportData(
                sport,
                ncaaf_store.load_games(),
                ncaaf_store.load_lines(),
                ncaaf_store.load_tickets(),
                _EMPTY,
            )
        if sport == "ncaabase":
            from .ncaabase import store as nb_store

            return SportData(
                sport,
                nb_store.load_games(),
                nb_store.load_lines(),
                nb_store.load_picks(),
                _EMPTY,
            )
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        # SystemExit is deliberately included: several config loaders raise it
        # for a missing file (ncaabase/config.py), and it is a BaseException,
        # so a bare `except Exception` would let one unset sport abort the run
        # and hide every other sport's findings.
        return SportData(
            sport, _EMPTY, _EMPTY, _EMPTY, _EMPTY, False, str(exc) or type(exc).__name__
        )
    return SportData(sport, _EMPTY, _EMPTY, _EMPTY, _EMPTY, False, "unknown sport")


def _is_idle(sport: str, data: SportData, cfg: dict, today: date) -> tuple[bool, str]:
    """Is this sport simply out of season? NCAABase answers from its own
    configured window; the others from how long ago the last game was."""
    if sport == "ncaabase":
        try:
            from .ncaabase.config import in_season, load_ncaabase_config

            nb_cfg = load_ncaabase_config()
            if not in_season(str(today), nb_cfg):
                season = nb_cfg.get("season") or {}
                return True, (
                    f"out of season (config/ncaabase.yaml "
                    f"{season.get('start')}..{season.get('end')})"
                )
        except (Exception, SystemExit):  # noqa: BLE001
            # As above: a missing config/ncaabase.yaml raises SystemExit. Fall
            # through to the games-based idle test rather than aborting.
            pass
    if data.games.empty or "game_date_et" not in data.games.columns:
        return True, "no games captured"
    last = max(str(d) for d in data.games["game_date_et"].dropna())
    limit = int((cfg["doctor"].get("idle_after_days") or {}).get(sport, 7))
    age = _age_days(last, today)
    if age > limit:
        return True, f"no games for {age}d (last {last}, idle after {limit}d)"
    return False, ""


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def _uniform_pass_day(
    picks: pd.DataFrame, passes: pd.DataFrame, sid: str, day: str
) -> str | None:
    """The single shared reason key, if this strategy produced no picks and
    every pass it wrote that day blames the same cause. None otherwise."""
    if not picks.empty and not picks[
        (picks["game_date_et"].astype(str) == day) & (picks["strategy_id"] == sid)
    ].empty:
        return None
    mine = passes[
        (passes["game_date_et"].astype(str) == day) & (passes["strategy_id"] == sid)
    ]
    if mine.empty:
        return None
    keys = {reason_key(r) for r in mine["reason"]}
    return next(iter(keys)) if len(keys) == 1 else None


def check_slate_shutout(data: SportData, cfg: dict, today: date, since: str) -> list[Finding]:
    """H01 — every evaluated strategy silent on the same day for the same
    stated reason.

    This is the check that catches the 2026-09-27 outage, and the reason it
    fires on day one is that it measured clean: 14 hits over 73 live slate
    days, the first on 2026-09-29, zero false positives before it.
    """
    c = _check_cfg(cfg, "slate_shutout")
    if not c.get("enabled", True) or data.passes.empty:
        return []
    min_strategies = int(c.get("min_strategies", 2))
    days = _slate_days(data.games, since, today)

    streak: list[tuple[str, str, list[str]]] = []
    for day in days:
        picked = (
            set()
            if data.picks.empty
            else set(data.picks[data.picks["game_date_et"].astype(str) == day]["strategy_id"])
        )
        today_passes = data.passes[data.passes["game_date_et"].astype(str) == day]
        if picked or today_passes.empty:
            streak = []
            continue
        sids = sorted({str(s) for s in today_passes["strategy_id"]})
        keys = {reason_key(r) for r in today_passes["reason"]}
        if len(sids) >= min_strategies and len(keys) == 1:
            streak.append((day, next(iter(keys)), sids))
        else:
            streak = []

    # Only a streak running up to the most recent slate day is live; an older
    # one was already resolved and would be noise.
    if not streak or not days or streak[-1][0] != days[-1]:
        return []
    if len(streak) < int(c.get("fail_after_days", 1)):
        return []

    first_day, key, sids = streak[0]
    last_day = streak[-1][0]
    last_pick = (
        None
        if data.picks.empty
        else max((str(d) for d in data.picks["game_date_et"].dropna()), default=None)
    )
    return [
        Finding(
            id="H01",
            check="slate_shutout",
            sport=data.sport,
            level="fail",
            title=(
                f"all {len(sids)} evaluated strategies produced 0 picks for "
                f"{len(streak)} consecutive slate day(s)"
            ),
            detail=(
                f"On {last_day} every evaluated strategy ({', '.join(sids)}) produced no "
                f"picks, and every pass shares the reason key `{key}`. This has held for "
                f"{len(streak)} consecutive slate day(s) since {first_day}. Last pick: "
                f"{last_pick or 'never'}. Independent engines do not fall silent for the "
                "same stated reason on the same day — look for a config or data fault, "
                "not a strategy opinion."
            ),
            since=first_day,
            evidence={
                "consecutive_slate_days": len(streak),
                "reason_key": key,
                "strategies": sids,
                "last_pick_date": last_pick,
                "last_slate_day": last_day,
            },
            # Must name a command that EXISTS — an alert whose remediation is
            # a typo teaches the reader to distrust the alert, and
            # test_every_suggested_command_names_a_real_subcommand enforces
            # it. NOT `_cli_prefix` here: `catchup` is one top-level command
            # for every sport, so `panthera-mvp ncaaf catchup` does not
            # exist. `--sport` is what keeps the repair, which writes, on the
            # finding's own sport.
            # `--dry-run` because this is pasted out of a GitHub issue into
            # whatever checkout the reader is sitting in, and `cmd_catchup`
            # writes by default. Every other manual path in the repo opens
            # the same way (.github/workflows/CLAUDE.md's testing convention).
            suggested_command=(
                f"panthera-mvp catchup --sport {data.sport} "
                f"--from {first_day} --dry-run"
            ),
        )
    ]


def check_uniform_pass(data: SportData, cfg: dict, today: date, since: str) -> list[Finding]:
    """H02 — one strategy silent for the same reason N consecutive slate days.

    Counted in slate days, not calendar days: 2026-09-28, 10-02 and 10-09 had
    no games, and a calendar counter resets on every off-day, which would have
    scored the 14-day outage as three short runs.
    """
    c = _check_cfg(cfg, "uniform_pass")
    if data.passes.empty:
        return []
    warn_after = int(c.get("warn_after_days", 3))
    fail_after = int(c.get("fail_after_days", 4))
    days = _slate_days(data.games, since, today)
    if not days:
        return []

    # One finding per sport, not per strategy: `fingerprint` is sport/check,
    # and the issue reconciler treats it as an identity, so N findings sharing
    # one fingerprint would collapse into one arbitrary issue. Affected
    # strategies go in the evidence instead.
    affected: dict[str, dict[str, Any]] = {}
    for sid in sorted({str(s) for s in data.passes["strategy_id"].dropna()}):
        run: list[tuple[str, str]] = []
        for day in days:
            key = _uniform_pass_day(data.picks, data.passes, sid, day)
            run = [*run, (day, key)] if key else []
        if not run or run[-1][0] != days[-1] or len(run) < warn_after:
            continue
        affected[sid] = {
            "days": len(run),
            "since": run[0][0],
            "reason_keys": sorted({k for _, k in run}),
        }
    if not affected:
        return []

    worst = max(v["days"] for v in affected.values())
    since = min(v["since"] for v in affected.values())
    keys = sorted({k for v in affected.values() for k in v["reason_keys"]})
    sids = sorted(affected)
    return [
        Finding(
            id="H02",
            check="uniform_pass",
            sport=data.sport,
            level="fail" if worst >= fail_after else "warn",
            title=(
                f"{len(sids)} strategy/strategies silent for up to {worst} consecutive "
                "uniform-pass slate days"
            ),
            detail=(
                ", ".join(f"{sid} ({affected[sid]['days']}d)" for sid in sids)
                + " produced no picks, passing every game for the same reason each day "
                + f"({', '.join(keys)}), since {since}. The longest legitimate run "
                + "measured over the pre-outage history was 2 slate days."
            ),
            since=since,
            evidence={
                "strategies": {sid: affected[sid] for sid in sids},
                "max_consecutive_slate_days": worst,
                "reason_keys": keys,
            },
        )
    ]


def check_data_staleness(data: SportData, cfg: dict, today: date, since: str) -> list[Finding]:
    """H03 — how old the newest captured game and odds snapshot are."""
    c = _check_cfg(cfg, "data_staleness")
    # One finding per sport: `fingerprint` is sport/check and the issue
    # reconciler treats it as an identity, so games and lines must report
    # together rather than as two findings sharing one fingerprint.
    problems: list[str] = []
    evidence: dict[str, Any] = {}
    level = "warn"
    oldest: str | None = None

    for label, frame, column, key in (
        ("games", data.games, "game_date_et", "games_max_age_days"),
        ("odds lines", data.lines, "snapshot_ts_utc", "lines_max_age_days"),
    ):
        limit = (c.get(key) or {}).get(data.sport)
        if limit is None:
            continue
        if frame.empty or column not in frame.columns:
            problems.append(f"no {label} captured at all")
            evidence[label] = {"newest": None}
            continue
        newest = max(str(v) for v in frame[column].dropna())
        age = _age_days(newest, today)
        evidence[label] = {"newest": newest, "age_days": age, "limit_days": int(limit)}
        if age > int(limit):
            problems.append(f"{label} are {age}d stale (limit {limit}d, newest {newest})")
            oldest = newest[:10] if oldest is None else min(oldest, newest[:10])
            if age > int(limit) * 2:
                level = "fail"

    if not problems:
        return []
    return [
        Finding(
            id="H03",
            check="data_staleness",
            sport=data.sport,
            level=level,
            title="; ".join(problems),
            detail=(
                "Freshness of this sport's captured data. A stale feed means the "
                "scheduled snapshot or ingest workflow is not landing: "
                + "; ".join(problems)
            ),
            since=oldest,
            evidence=evidence,
        )
    ]


def check_snapshot_coverage(
    data: SportData, cfg: dict, today: date, since: str
) -> list[Finding]:
    """H04 — MLB slate days missing a snapshot label. One scheduled workflow
    failing while the others cover for it looks like nothing at all."""
    if data.sport != "mlb":
        return []
    c = _check_cfg(cfg, "snapshot_coverage")
    required = list(c.get("mlb_required_labels") or [])
    if not required or data.lines.empty or "snapshot_label" not in data.lines.columns:
        return []
    days = _slate_days(data.games, since, today)[-int(c.get("lookback_days", 3)) :]
    missing: dict[str, list[str]] = {}
    for day in days:
        present = set(
            data.lines[data.lines["game_date_et"].astype(str) == day]["snapshot_label"]
        )
        gap = [lab for lab in required if lab not in present]
        if gap:
            missing[day] = gap
    if len(missing) < 2:  # a single day can be an in-progress slate
        return []
    labels = sorted({lab for gap in missing.values() for lab in gap})
    return [
        Finding(
            id="H04",
            check="snapshot_coverage",
            sport=data.sport,
            level="warn",
            title=f"snapshot label(s) {', '.join(labels)} missing on {len(missing)} slate days",
            detail=(
                "A label absent across several slate days means one scheduled "
                "snapshot workflow is failing silently: "
                + "; ".join(f"{d}: missing {', '.join(g)}" for d, g in sorted(missing.items()))
            ),
            since=min(missing),
            evidence={"missing_by_day": {d: g for d, g in sorted(missing.items())}},
        )
    ]


def check_pending_age(data: SportData, cfg: dict, today: date, since: str) -> list[Finding]:
    """H05 — picks still pending long after their game: a stalled grader."""
    c = _check_cfg(cfg, "pending_age")
    picks = data.picks
    if picks.empty or "status" not in picks.columns:
        return []
    pending = picks[picks["status"] == "pending"]
    if pending.empty:
        return []
    warn_days, fail_days = int(c.get("warn_days", 3)), int(c.get("fail_days", 7))
    ages = {
        str(row.game_date_et): _age_days(str(row.game_date_et), today)
        for row in pending.itertuples(index=False)
    }
    stale = {d: a for d, a in ages.items() if a > warn_days}
    if not stale:
        return []
    worst = max(stale.values())
    overdue = pending[pending["game_date_et"].astype(str).isin(stale)]
    n = len(overdue)

    # Why it cannot settle matters more than that it has not. A game still
    # "Preview" means the grader has not reached it; a game "Final" with no
    # score recorded means it never can, because grading settles from the
    # score — a different bug with a different fix.
    blocked = _unsettleable(overdue, data.games)
    extra, grade_helps = _blocked_detail(blocked)
    if blocked and not grade_helps:
        extra += (
            " Nothing to run: wait for the game to be completed and the feed to "
            "report a final. If it is abandoned without ever being called off, "
            "the score never arrives and the picks need a ruling — see "
            "docs/mvp-design.md, \"Rollback and ownership — called-off game "
            "settlement\"."
        )
    elif blocked:
        extra += " This is not a grader schedule problem."
    return [
        Finding(
            id="H05",
            check="pending_age",
            sport=data.sport,
            level="fail" if worst > fail_days else "warn",
            title=f"{n} pick(s) pending more than {warn_days}d after their game",
            detail=(
                f"Oldest is {worst} days past its game date. Grading should settle a pick "
                f"the morning after.{extra}"
            ),
            since=min(stale),
            evidence={
                "pending_n": int(n),
                "oldest_age_days": worst,
                "dates": sorted(stale),
                "scoreless_final_games": [pk for pk, _ in blocked],
            },
            # No `grade` remediation when every blocked game is simply waiting
            # to be resumed: the command would refresh, fill nothing and settle
            # nothing, and an alert that prescribes a no-op trains the operator
            # to ignore it. A date with no blocked game at all still gets it —
            # there, a stalled grader is exactly what `grade` fixes.
            suggested_command=(
                None
                if blocked and not grade_helps
                else f"panthera-mvp {_cli_prefix(data.sport)}grade --date {min(stale)}"
            ),
        )
    ]


def _unsettleable(pending: pd.DataFrame, games: pd.DataFrame) -> list[tuple[int, str]]:
    """Games a pending pick points at that carry no score and will not gain
    one from re-grading.

    Two different shapes, with two different remediations, which is why the
    status is returned alongside the game:

    - `Final` with no score — a fault. Something must backfill the score.
    - a called-off status (`clients/mlb.py::CALLED_OFF_STATUSES`) with no
      score. `Suspended` is the live one: MLB resumes the game under the same
      game_pk, so the pick is correctly pending and `grade` will not change
      that. Telling an operator to run `grade` here is advice that cannot
      work, which is the thing this check exists to avoid.
    """
    if games.empty or "game_pk" not in games.columns or "home_score" not in games.columns:
        return []
    from .clients.mlb import CALLED_OFF_STATUSES

    terminal = ("Final", *CALLED_OFF_STATUSES)
    by_pk = games.drop_duplicates("game_pk").set_index("game_pk")
    out: list[tuple[int, str]] = []
    for pk in sorted({int(x) for x in pending["game_pk"].dropna()}):
        if pk not in by_pk.index:
            continue
        row = by_pk.loc[pk]
        status = str(row.get("status", ""))
        if status in terminal and pd.isna(row.get("home_score")):
            out.append((pk, status))
    return out


def _blocked_detail(blocked: list[tuple[int, str]]) -> tuple[str, bool]:
    """Render the blocked games and say whether `grade` is worth suggesting.

    Per game, not per finding: on a mixed date one game can be waiting on a
    resumption while another is a scoreless `Final` that something must
    backfill. Lumping them under one verdict prescribed a no-op for the
    suspended half, which is the failure this helper exists to avoid.
    `grade` is offered only when at least one blocked game is a scoreless
    `Final`, i.e. only when running it could change something.
    """
    if not blocked:
        return "", False
    waiting = (
        "a suspended game is resumed under the same game_pk, so its picks are "
        "correctly pending and `grade` will not change them"
    )
    backfill = (
        "grading settles from the score, so it can never settle until the "
        "score is backfilled"
    )
    parts = [
        f"game {pk} is {st} with no score recorded — "
        + (waiting if st == "Suspended" else backfill)
        for pk, st in blocked
    ]
    grade_helps = any(st != "Suspended" for _, st in blocked)
    return " " + "; ".join(parts) + ".", grade_helps


def check_unmatched_slate(data: SportData, cfg: dict, today: date, since: str) -> list[Finding]:
    """H06 — share of the slate with no matched odds event. Catches
    matching.py alias rot, which otherwise shows up only as fewer picks."""
    c = _check_cfg(cfg, "unmatched_slate")
    if data.sport != "mlb" or data.games.empty or data.lines.empty:
        return []
    if "game_pk" not in data.lines.columns:
        return []
    days = _slate_days(data.games, since, today)[-int(c.get("lookback_days", 3)) :]
    if not days:
        return []
    limit = float(c.get("max_unpriced_pct", 50))
    worst: tuple[str, float, int, int] | None = None
    for day in days:
        slate = data.games[data.games["game_date_et"].astype(str) == day]
        if slate.empty:
            continue
        priced = set(
            int(pk)
            for pk in data.lines[data.lines["game_date_et"].astype(str) == day][
                "game_pk"
            ].dropna()
        )
        unpriced = sum(1 for pk in slate["game_pk"].dropna() if int(pk) not in priced)
        pct = 100.0 * unpriced / len(slate)
        if pct > limit and (worst is None or pct > worst[1]):
            worst = (day, pct, unpriced, len(slate))
    if worst is None:
        return []
    day, pct, unpriced, total = worst
    return [
        Finding(
            id="H06",
            check="unmatched_slate",
            sport=data.sport,
            level="warn",
            title=f"{pct:.0f}% of the {day} slate had no matched odds event",
            detail=(
                f"{unpriced} of {total} games on {day} have no odds_event_id in lines.csv. "
                "Unmatched games are logged and never guessed, so alias rot (a team rename, "
                "a new bookmaker naming convention) silently shrinks the slate — check "
                "matching.py's alias table."
            ),
            since=day,
            evidence={
                "date": day,
                "unpriced": unpriced,
                "slate": total,
                "pct": round(pct, 1),
                "limit_pct": limit,
            },
        )
    ]


def check_lineage_drift(cfg: dict) -> list[Finding]:
    """H07 — an enabled strategy whose current config_hash is absent from its
    own non-empty hash_lineage: its picks render as a separate report segment
    and its verdict countdown freezes.

    Shares `hashes._rows()` with `panthera-mvp hashes`, so the command and the
    alert can never disagree about what drift is.
    """
    if not _check_cfg(cfg, "lineage_drift").get("enabled", True):
        return []
    out: list[Finding] = []
    for sport in ("mlb", "ncaaf"):
        try:
            from .hashes import _rows

            rows = _rows(sport)
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            out.append(
                Finding(
                    id="H07",
                    check="lineage_drift",
                    sport=sport,
                    level="warn",
                    title="could not read strategy hashes",
                    detail=str(exc),
                )
            )
            continue
        # `in_lineage` is already true for an empty lineage (which means "pool
        # every hash"), and a disabled strategy's drift is intentional — its
        # frozen segment must not move.
        drifted = [r for r in rows if not r["in_lineage"] and r["enabled"]]
        for r in drifted:
            out.append(
                Finding(
                    id="H07",
                    check="lineage_drift",
                    sport=sport,
                    level="fail",
                    title=f"{r['strategy_id']}: config_hash not in its declared lineage",
                    detail=(
                        f"{r['strategy_id']}'s current config_hash {r['config_hash']} is "
                        f"absent from hash_lineage {r['hash_lineage']}. Its picks will "
                        "render as a separate SCREEN segment and its verdict countdown "
                        "will not advance. Either amend the lineage (only for a "
                        "domain-extending change, with the proof src/panthera_mvp/"
                        "CLAUDE.md requires) or register a new strategy id."
                    ),
                    evidence={
                        "strategy_id": r["strategy_id"],
                        "config_hash": r["config_hash"],
                        "hash_lineage": r["hash_lineage"],
                    },
                    suggested_command="panthera-mvp hashes",
                )
            )
    return out


def check_credit_floor(cfg: dict) -> list[Finding]:
    """H08 — Odds API credits. Reads the committed credit log, never the
    network."""
    c = _check_cfg(cfg, "credit_floor")
    from .clients import odds

    remaining = odds.last_known_remaining()
    if remaining is None:
        return [
            Finding(
                id="H08",
                check="credit_floor",
                sport="mlb",
                level="warn",
                title="no Odds API credit observation this month",
                detail=(
                    "data/odds/credit_log.csv has no row for the current UTC month, so "
                    "either no live snapshot has run or the log is not being written. "
                    "The credit guard cannot protect a balance it cannot see."
                ),
            )
        ]
    floor = int(c.get("warn_below", 60))
    if remaining >= floor:
        return []
    return [
        Finding(
            id="H08",
            check="credit_floor",
            sport="mlb",
            level="warn",
            title=f"{remaining} Odds API credits remaining (warn below {floor})",
            detail=(
                f"{remaining} credits left this month. The credit guard refuses live "
                "snapshots below each sport's reserve, so snapshots will start being "
                "skipped — NCAAF and college baseball first, by design."
            ),
            evidence={"remaining": remaining, "warn_below": floor},
        )
    ]


def check_config_sanity(cfg: dict) -> list[Finding]:
    """H09 — the strategy configs do not load at all. This is where
    strategy/season.py's retired-key tripwire surfaces as an alert rather than
    a crashed cron."""
    if not _check_cfg(cfg, "config_sanity").get("enabled", True):
        return []
    out: list[Finding] = []
    try:
        from .config import load_strategy_configs
        from .strategy.registry import engines
        from .strategy.season import excluded_game_types

        configs = load_strategy_configs(known_engines=set(engines()))
        # Loading alone does not touch the game-type scope — the retired-key
        # tripwire lives in `excluded_game_types`, which only an engine would
        # normally call. Probe every strategy's merged config explicitly, or
        # H09 would pass while every pick run fails.
        for scfg in configs.values():
            excluded_game_types(scfg)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — the thing being reported
        out.append(
            Finding(
                id="H09",
                check="config_sanity",
                sport="mlb",
                level="fail",
                title="strategy configs do not load",
                detail=(
                    f"{type(exc).__name__}: {exc}\n\nEvery pick run will fail until this "
                    "is fixed. A retired config key is the usual cause."
                ),
                evidence={"error": f"{type(exc).__name__}: {exc}"},
            )
        )
    return out


def check_scoreless_final(
    data: SportData, cfg: dict, today: date, since: str
) -> list[Finding]:
    """H10 — a row stored `Final` with no score.

    `data/CLAUDE.md` calls this "a fault, not a result": such a row can settle
    nothing, and it is how the 2026-09-27 rainout stranded three picks for 18
    days. Until now the ONLY thing that noticed was H05, and only once a pick
    on that game had been pending past its threshold — so a scoreless final
    whose picks were already settled, or that never carried a pick at all,
    was reported by nothing while still feeding the backtest and the reports.

    This reads games.csv directly, independent of any pick.
    """
    c = _check_cfg(cfg, "scoreless_final")
    if data.games.empty:
        return []
    games = data.games
    if not {"status", "home_score", "away_score"}.issubset(games.columns):
        return []
    window = games[games["game_date_et"].astype(str) >= since]
    if window.empty:
        return []
    missing = window["home_score"].isna() | window["away_score"].isna()
    bad = window[(window["status"].astype(str) == "Final") & missing]
    if bad.empty:
        return []

    key = "game_pk" if "game_pk" in bad.columns else bad.columns[0]
    ids = [str(v) for v in bad[key].tolist()[:20]]
    oldest = str(bad["game_date_et"].min())
    return [
        Finding(
            id="H10",
            check="scoreless_final",
            sport=data.sport,
            level=str(c.get("level", "warn")),
            title=f"{len(bad)} game(s) stored Final with no score",
            detail=(
                f"{len(bad)} row(s) in this sport's games.csv are `Final` with a "
                f"missing home or away score, oldest {oldest}. A Final with no "
                "score is a fault, not a result: it can settle no pick, and it "
                "still feeds the reports and the backtest. Either the feed never "
                "returned a linescore, or the game was called off and its real "
                "status was collapsed to Final \u2014 check `detailedState` for the "
                "game and let the finals fallback rewrite it. There is no "
                "one-command repair for MLB or NCAAF: see the called-off "
                "settlement section of docs/mvp-design.md."
            ),
            since=oldest,
            evidence={"count": int(len(bad)), "oldest_date": oldest, "ids": ids},
            # Only college baseball can act on this. `cmd_grade` for MLB and
            # NCAAF builds its date list from PENDING picks and `--date` only
            # filters that list — and H10 exists precisely for a game with no
            # pending pick, so the command would refresh nothing. An alert
            # that prescribes a no-op teaches the reader to ignore the alert;
            # ncaabase's cmd_grade takes the date unconditionally, so there
            # it is real.
            suggested_command=(
                f"panthera-mvp ncaabase grade --date {oldest}"
                if data.sport == "ncaabase"
                else None
            ),
        )
    ]


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

#: Checks that measure ACTIVITY over a window of slate days. These are the
#: ones an offseason makes meaningless, so they downgrade to INFO when a sport
#: is idle.
WINDOW_CHECKS = (
    check_slate_shutout,
    check_uniform_pass,
    check_data_staleness,
    check_snapshot_coverage,
    check_pending_age,
    check_unmatched_slate,
    check_scoreless_final,
)

#: H07/H08/H09 measure CORRECTNESS, not activity, and are deliberately NOT
#: downgraded when a sport is idle: a strategy whose hash left its lineage is
#: just as broken in December as in July, and the offseason is when you want
#: to find out, not the morning of opening day.
#:
#: Published in the JSON so the reconciler can tell "stopped being reported
#: because nobody looked" from "stopped being reported because it is fixed".
#: An idle sport holds its WINDOW findings open, but one of these going quiet
#: really is a fix, and an issue that can never close is noise.
ALWAYS_EVALUATED = (
    "lineage_drift",
    "credit_floor",
    "config_sanity",
    # H10 reads games.csv, so it needs a sport's data and lives in
    # WINDOW_CHECKS — but it measures CORRECTNESS, not activity. A row stored
    # Final with no score is just as wrong in December as in July, and the
    # offseason is when you want to find it rather than the morning of
    # opening day. It is therefore exempt from the idle downgrade below and
    # listed here so the issue reconciler closes it on its own merits.
    "scoreless_final",
)


def run_checks(
    sport: str = "all", cfg: dict | None = None, since: str | None = None
) -> dict[str, Any]:
    """Every finding, plus the per-sport roster needed to render "OK" lines for
    the checks that found nothing."""
    cfg = cfg or load_health_config()
    today = today_et()
    lookback = int(cfg["doctor"].get("lookback_days", 30))
    since = since or str(today - timedelta(days=lookback))

    wanted = list(cfg["doctor"].get("sports") or SPORTS) if sport == "all" else [sport]
    findings: list[Finding] = []
    sport_state: list[dict[str, Any]] = []

    for s in wanted:
        data = load_sport(s)
        if not data.available:
            sport_state.append({"sport": s, "state": "unavailable", "note": data.note})
            findings.append(
                Finding(
                    id="H00",
                    check="sport_unavailable",
                    sport=s,
                    level="warn",
                    title="sport data could not be read",
                    detail=data.note,
                )
            )
            continue

        idle, why = _is_idle(s, data, cfg, today)
        sport_state.append(
            {"sport": s, "state": "idle" if idle else "active", "note": why}
        )
        produced = [
            f
            for check in WINDOW_CHECKS
            if _check_enabled(cfg, check)
            for f in check(data, cfg, today, since)
        ]
        produced = _drop_subsumed(produced)
        if idle:
            # Out of season nothing is wrong, so ACTIVITY findings are
            # recorded for the record and never alerted on. Correctness
            # findings are not activity and keep their level.
            for f in produced:
                if f.check not in ALWAYS_EVALUATED:
                    f.level = "info"
        findings += produced

    if sport == "all" or sport == "mlb":
        for check in (check_config_sanity, check_lineage_drift, check_credit_floor):
            if _check_enabled(cfg, check):
                findings += check(cfg)

    order = {lvl: i for i, lvl in enumerate(LEVELS)}
    findings.sort(key=lambda f: (order.get(f.level, 9), f.sport, f.id))
    alert = dict(cfg["doctor"].get("alert") or {})
    alert.setdefault("open_issue_on", ["fail"])
    alert.setdefault("renotify_every_days", 7)
    return {
        "findings": findings,
        "sports": sport_state,
        "alert": alert,
        "today_et": str(today),
        "since": since,
    }


def _drop_subsumed(findings: list[Finding]) -> list[Finding]:
    """H01 already says every strategy fell silent for one shared reason, so
    the per-strategy H02 for that same reason is the same alert twice. One
    cause, one issue — a health check people mute is worse than none.
    """
    shutouts = [f for f in findings if f.check == "slate_shutout"]
    if not shutouts:
        return findings
    covered = {f.evidence.get("reason_key") for f in shutouts}
    out = []
    for f in findings:
        if f.check == "uniform_pass" and set(f.evidence.get("reason_keys") or []) <= covered:
            continue
        out.append(f)
    return out


def exit_code(findings: list[Finding], strict: bool = False) -> int:
    if any(f.level == "fail" for f in findings):
        return EXIT_FAIL
    if any(f.level == "warn" for f in findings):
        return EXIT_FAIL if strict else EXIT_WARN
    return EXIT_OK


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

_BADGE = {"fail": "FAIL", "warn": "WARN", "info": "INFO", "ok": "OK", "idle": "IDLE"}


def render_text(result: dict[str, Any]) -> str:
    findings: list[Finding] = result["findings"]
    out = [f"panthera-mvp doctor — {result['today_et']} ET — window from {result['since']}", ""]

    by_sport: dict[str, list[Finding]] = {}
    for f in findings:
        by_sport.setdefault(f.sport, []).append(f)

    for state in result["sports"]:
        s = state["sport"]
        mine = by_sport.pop(s, [])
        worst = min((f.level for f in mine), key=LEVELS.index, default="ok")
        if state["state"] == "idle":
            note = f" — {state['note']}" if state["note"] else ""
            out.append(f"{s.upper():9s} IDLE{note}")
        else:
            out.append(f"{s.upper():9s} {_BADGE.get(worst, worst.upper())}")
        if not mine:
            out.append("    no findings")
        for f in mine:
            out.append(f"    {_BADGE[f.level]:5s} {f.id}  {f.check:18s} {f.title}")
            for line in f.detail.splitlines():
                if line.strip():
                    out.append(f"               {line.strip()}")
            if f.suggested_command:
                out.append(f"               -> {f.suggested_command}")
        out.append("")

    # Cross-sport findings (H07/H08/H09) are filed under the sport they
    # concern, so anything left here had no sport roster entry.
    for s, mine in by_sport.items():
        out.append(f"{s.upper():9s} (config-level)")
        for f in mine:
            out.append(f"    {_BADGE[f.level]:5s} {f.id}  {f.check:18s} {f.title}")
            for line in f.detail.splitlines():
                if line.strip():
                    out.append(f"               {line.strip()}")
            if f.suggested_command:
                out.append(f"               -> {f.suggested_command}")
        out.append("")

    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in LEVELS}
    out.append(
        f"{counts['fail']} fail, {counts['warn']} warn, {counts['info']} informational "
        f"(idle sports)."
    )
    if not findings:
        out.append("Nothing to report.")
    return "\n".join(out)


def render_json(result: dict[str, Any], code: int) -> str:
    findings: list[Finding] = result["findings"]
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in LEVELS}
    return json.dumps(
        {
            "schema": 1,
            "generated_ts_utc": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "today_et": result["today_et"],
            "since": result["since"],
            "exit_code": code,
            "summary": {k: counts[k] for k in ("fail", "warn", "info")},
            # Emitted so .github/workflows/health.yml can READ the routing
            # knobs instead of hardcoding them. A threshold in config that
            # nothing consumes is worse than no threshold: an operator who
            # edits it to stop a flapping alert believes they are covered.
            "alert": result["alert"],
            "always_evaluated": list(ALWAYS_EVALUATED),
            "sports": result["sports"],
            "findings": [f.as_dict() for f in findings],
        },
        indent=2,
    )


def cmd_doctor(
    sport: str = "all",
    as_json: bool = False,
    since: str | None = None,
    strict: bool = False,
    exit_zero: bool = False,
) -> int:
    try:
        cfg = load_health_config()
        result = run_checks(sport=sport, cfg=cfg, since=since)
    except DoctorConfigError as exc:
        # Exit 3, never 0 — including under `--exit-zero`, which this branch
        # deliberately ignores. That flag exists so FINDINGS do not redden the
        # scheduled job; "doctor could not run" is not a finding, and the
        # comment above this line promised exit 3 while the code returned 0
        # for the one caller that matters: .github/workflows/health.yml passes
        # `--exit-zero` to both doctor steps. They stayed green and printed
        # `[doctor] cannot run: ...` into health.json, so the job failed one
        # step later, in "Reconcile health issues", when JSON.parse hit that
        # line — which reads as a broken issue bot, not a blind detector.
        print(f"[doctor] cannot run: {exc}")
        return EXIT_BROKEN

    code = exit_code(result["findings"], strict=strict)
    print(render_json(result, code) if as_json else render_text(result))
    return EXIT_OK if exit_zero else code
