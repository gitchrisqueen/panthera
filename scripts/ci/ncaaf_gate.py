#!/usr/bin/env python3
"""Cheap pre-check for ncaaf.yml: skip the job before `pip install` when a scheduled
`ncaaf picks --auto` run provably has nothing to do (issue #79, Actions standard rule 10).

Stdlib only, so it runs before any install. It mirrors the no-op arms of
`ncaaf.picks.cmd_picks` / `in_decision_window` and is deliberately conservative.
A day counts as decided only when EVERY enabled strategy in config/ncaaf_strategies/
has a decision row for it. The decision window comes from STRATEGY's YAML, so every
enabled strategy must share its timing (a test pins that). Anything it cannot prove
(a dispatch, a prep or grade cron, an unknown cron string,
a missing or unreadable file, any exception) is "go". Fail open, never closed.

Inputs come from the environment, never from interpolated workflow text:
  GATE_EVENT     github.event_name
  GATE_SCHEDULE  github.event.schedule
  GATE_FIXTURE   optional `gate_fixture` dispatch input: a JSON file under
                 tests/fixtures/ncaaf/ that supplies `now_utc`, `games` and
                 `decided_days` instead of the real clock and data. A fixture run
                 evaluates the auto logic regardless of event, and the workflow
                 forces dry_run so it writes nothing. Any other path is rejected
                 (exit 2).

Writes `go=true|false`, `fixture=true|false` and `reason=...` to $GITHUB_OUTPUT.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ncaaf"
STRATEGY = "cfb_spread_total_parlay"
ET = ZoneInfo("America/New_York")
# The two half-hourly crons in ncaaf.yml whose task is `auto`. Every other schedule
# string (prep, grade, anything new) is "go". Keep in step with the `Which task` case.
AUTO_CRONS = {"5 13-23,0-4 * 8-12,1 *", "35 15-23,0-4 * 8-12,1 *"}


class FixtureRejected(ValueError):
    pass


def resolve_fixture(arg: str) -> Path:
    """The fixture file, only if it is a real .json file under tests/fixtures/ncaaf/."""
    if not arg.startswith("tests/fixtures/ncaaf/") or ".." in Path(arg).parts:
        raise FixtureRejected(f"fixture path must be relative and under {FIXTURE_DIR}: {arg!r}")
    path = (ROOT / arg).resolve()
    if not path.is_relative_to(FIXTURE_DIR.resolve()) or path.suffix != ".json":
        raise FixtureRejected(f"fixture must be a .json file under tests/fixtures/ncaaf/: {arg!r}")
    if not path.is_file():
        raise FixtureRejected(f"fixture not found: {arg!r}")
    return path


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def config_number(path: Path, key: str) -> int:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(\d+)\b", path.read_text(), re.M)
    if not match:
        raise ValueError(f"{key} not found in {path}")
    return int(match.group(1))


def enabled_strategies() -> set[str]:
    """Ids of the NCAAF strategies whose `strategy:` block says `enabled: true`. Raises
    when none can be read, so the gate fails open instead of treating "no strategies" as
    "everything decided"."""
    ids: set[str] = set()
    for path in sorted((ROOT / "config" / "ncaaf_strategies").glob("*.yaml")):
        text = path.read_text()
        block = re.search(r"^strategy:\s*\n((?:[ \t]+.*\n|\s*\n)+)", text, re.M)
        if not block:
            raise ValueError(f"no strategy block in {path.name}")
        enabled = re.search(r"^\s+enabled:\s*(true|false)\b", block.group(1), re.M)
        sid = re.search(r"^\s+id:\s*(\S+)", block.group(1), re.M)
        if not enabled or not sid:
            raise ValueError(f"strategy.id or strategy.enabled missing in {path.name}")
        if enabled.group(1) == "true":
            ids.add(sid.group(1))
    if not ids:
        raise ValueError("no enabled NCAAF strategy found")
    return ids


def load_settings() -> tuple[int, int, int]:
    strategy = ROOT / "config" / "ncaaf_strategies" / f"{STRATEGY}.yaml"
    return (
        config_number(strategy, "minutes_before_first_kickoff"),
        config_number(strategy, "min_lead_minutes"),
        config_number(ROOT / "config" / "ncaaf.yaml", "decision_window_halfwidth_minutes"),
    )


def decided_days(decisions: list[dict], enabled: set[str]) -> set[str]:
    """Days on which EVERY enabled strategy has a decision row. A day one strategy has
    not decided (a new strategy, or one whose decision failed before its row) stays "go"."""
    by_day: dict[str, set[str]] = {}
    for row in decisions:
        by_day.setdefault(row["game_date_et"], set()).add(row["strategy_id"])
    return {day for day, ids in by_day.items() if enabled <= ids}


def decide(
    now: datetime, games: list[dict], decided_days: set[str], settings: tuple[int, int, int]
) -> tuple[bool, str]:
    """(go, why). Same rule as `in_decision_window`, plus the one-decision-per-day skip."""
    target, lead_min, half = settings
    day = now.astimezone(ET).date().isoformat()
    if day in decided_days:
        return False, f"every enabled strategy already decided {day}"
    lead = timedelta(minutes=lead_min)
    starts = sorted(
        start
        for start in (
            parse_utc(g["start_time_utc"])
            for g in games
            if g.get("game_date_et") == day
            and g.get("status") == "Scheduled"
            and g.get("start_time_utc")
        )
        if start - now >= lead
    )
    if not starts:
        return False, f"no upcoming FBS games stored for {day}"
    minutes = (starts[0] - now).total_seconds() / 60
    if minutes < target + half:
        return True, f"first kickoff in {minutes:.0f} min"
    return False, f"first kickoff in {minutes:.0f} min (decide under {target + half})"


def read_csv(path: str, required: set[str]) -> list[dict]:
    """Rows of a CSV, only if its header has the columns the gate reads. A file that is
    empty or garbled must raise (and so fail open), not read as "no games"."""
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"{path} is missing columns {sorted(required)}")
        return list(reader)


def emit(go: bool, reason: str, fixture: bool) -> None:
    # No raw newline may start a new output line.
    reason = re.sub(r"[^\x20-\x7e]", "?", reason)[:300]
    line = f"go={str(go).lower()}\nfixture={str(fixture).lower()}\nreason={reason}\n"
    print(line, end="")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as handle:
            handle.write(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as handle:
            handle.write(f"ncaaf gate: go={str(go).lower()} ({reason})\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-csv")
    parser.add_argument("--decisions-csv")
    args = parser.parse_args(argv)

    fixture_arg = os.environ.get("GATE_FIXTURE", "").strip()
    if fixture_arg:
        try:
            path = resolve_fixture(fixture_arg)
        except FixtureRejected as exc:
            print(f"::error::{exc}")
            return 2
        try:
            data = json.loads(path.read_text())
            go, why = decide(
                parse_utc(data["now_utc"]),
                data["games"],
                set(data.get("decided_days", [])),
                load_settings(),
            )
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            kind = type(exc).__name__
            print(f"::error::fixture {fixture_arg} is not a valid gate fixture: {kind}")
            return 2
        emit(go, f"fixture {fixture_arg}: {why}", True)
        return 0

    try:
        if os.environ.get("GATE_EVENT") != "schedule":
            emit(True, "not a scheduled run", False)
            return 0
        if os.environ.get("GATE_SCHEDULE") not in AUTO_CRONS:
            emit(True, "scheduled task is not the half-hourly auto run", False)
            return 0
        if not (args.games_csv and args.decisions_csv):
            emit(True, "gate inputs missing (fail open)", False)
            return 0
        decisions = read_csv(args.decisions_csv, {"strategy_id", "game_date_et"})
        decided = decided_days(decisions, enabled_strategies())
        games = read_csv(args.games_csv, {"game_date_et", "start_time_utc", "status"})
        go, why = decide(datetime.now(UTC), games, decided, load_settings())
        emit(go, why, False)
    except Exception as exc:  # noqa: BLE001 - fail open on anything unexpected
        emit(True, f"gate error, failing open: {type(exc).__name__}: {exc}", False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
