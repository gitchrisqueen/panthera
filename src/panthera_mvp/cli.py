"""panthera-mvp command-line interface."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="panthera-mvp",
        description="Project Panthera MVP — MLB betting strategy validation pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_snap = sub.add_parser("snapshot", help="Take an odds snapshot")
    p_snap.add_argument("--label", required=True, choices=["open", "midday", "pregame"])
    p_snap.add_argument("--dry-run", action="store_true")

    p_picks = sub.add_parser("picks", help="Generate picks for today's games")
    p_picks.add_argument(
        "--window-end-et",
        default="23:59",
        help="Only games starting at or before this ET time (HH:MM)",
    )
    p_picks.add_argument("--dry-run", action="store_true")

    p_grade = sub.add_parser("grade", help="Settle pending picks with final scores")
    p_grade.add_argument("--date", default=None, help="Only grade picks for this ET date")

    sub.add_parser("report", help="Regenerate markdown reports")
    sub.add_parser("status", help="Show pending picks and credit balance")

    p_bt = sub.add_parser("backtest", help="Replay the rules over historical seasons")
    p_bt.add_argument("--seasons", default=None, help="e.g. 2019-2023")

    p_cal = sub.add_parser("calibrate", help="Parameter sweep over historical seasons")
    p_cal.add_argument("--train", required=True, help="e.g. 2019-2021")
    p_cal.add_argument("--validate", required=True, help="e.g. 2022-2023")
    p_cal.add_argument("--write-config", action="store_true")

    args = parser.parse_args(argv)

    # Imports deferred so `--help` stays fast and dependency-light.
    if args.command == "snapshot":
        from .pipeline import cmd_snapshot

        cmd_snapshot(args.label, dry_run=args.dry_run)
    elif args.command == "picks":
        from .pipeline import cmd_picks

        cmd_picks(args.window_end_et, dry_run=args.dry_run)
    elif args.command == "grade":
        from .pipeline import cmd_grade

        cmd_grade(args.date)
    elif args.command == "report":
        from .pipeline import cmd_report

        cmd_report()
    elif args.command == "status":
        from .pipeline import cmd_status

        cmd_status()
    elif args.command == "backtest":
        from .backtest.engine import cmd_backtest

        cmd_backtest(args.seasons)
    elif args.command == "calibrate":
        from .backtest.calibrate import cmd_calibrate

        cmd_calibrate(args.train, args.validate, args.write_config)


if __name__ == "__main__":
    main()
