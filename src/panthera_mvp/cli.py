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
    p_snap.add_argument(
        "--label", required=True, choices=["open", "midday", "pregame", "close"]
    )
    p_snap.add_argument("--dry-run", action="store_true")

    p_picks = sub.add_parser("picks", help="Generate picks for today's games")
    p_picks.add_argument(
        "--window-end-et",
        default="23:59",
        help="Only games starting at or before this ET time (HH:MM)",
    )
    p_picks.add_argument(
        "--label",
        default="manual",
        choices=["morning", "pregame", "manual"],
        help="Which scheduled picks run this is (maps to a snapshot label; "
        "drives the late-run guard and pass records)",
    )
    p_picks.add_argument("--dry-run", action="store_true")

    p_splits = sub.add_parser(
        "splits", help="Collect public betting splits (Lumify) for today's slate"
    )
    p_splits.add_argument(
        "--label", default="manual", choices=["morning", "pregame", "manual"]
    )
    p_splits.add_argument("--dry-run", action="store_true")

    p_grade = sub.add_parser("grade", help="Settle pending picks with final scores")
    p_grade.add_argument("--date", default=None, help="Only grade picks for this ET date")

    sub.add_parser("report", help="Regenerate markdown reports")
    sub.add_parser("status", help="Show pending picks and credit balance")

    p_pages = sub.add_parser(
        "pages", help="Build the static GitHub Pages dashboard from picks.csv"
    )
    p_pages.add_argument(
        "--run-label",
        default="manual",
        choices=["morning", "pregame", "manual"],
        help="Which scheduled run triggered this build (shown in the "
        "dashboard's freshness badge)",
    )

    p_bt = sub.add_parser("backtest", help="Replay strategies over historical seasons")
    p_bt.add_argument("--seasons", default=None, help="e.g. 2019-2023")
    p_bt.add_argument(
        "--strategy",
        default=None,
        help="Strategy id (config/strategies/<id>.yaml); default: all with "
        "backtest scope. Splits strategies are refused (no historical splits).",
    )

    p_cal = sub.add_parser("calibrate", help="Parameter sweep over historical seasons")
    p_cal.add_argument("--train", required=True, help="e.g. 2019-2021")
    p_cal.add_argument("--validate", required=True, help="e.g. 2022-2023")
    p_cal.add_argument("--write-config", action="store_true")

    p_replay = sub.add_parser(
        "replay",
        help="Retroactively replay a strategy over already-captured odds/games "
        "history (zero API cost); writes data/picks/shadow_picks.csv, never "
        "pooled into any strategy's verdict",
    )
    p_replay.add_argument("--strategy", default="pv_orig", help="Strategy id to replay")
    p_replay.add_argument("--from", dest="from_et", default=None, help="ET date, e.g. 2026-07-31")
    p_replay.add_argument("--to", dest="to_et", default=None, help="ET date, e.g. 2026-08-19")

    p_cfb = sub.add_parser(
        "ncaaf", help="College football data plumbing (games, odds, parlay grading)"
    )
    cfb = p_cfb.add_subparsers(dest="ncaaf_command", required=True)
    c_games = cfb.add_parser("games", help="Refresh ESPN FBS games for an ET date")
    c_games.add_argument("--date", default=None, help="ET date (default: today)")
    c_snap = cfb.add_parser("snapshot", help="Take an NCAAF odds snapshot")
    c_snap.add_argument("--label", required=True, choices=["open", "pregame", "close"])
    c_snap.add_argument("--dry-run", action="store_true")
    c_grade = cfb.add_parser("grade", help="Settle pending parlay tickets")
    c_grade.add_argument("--date", default=None, help="Only refresh this ET date")
    c_cfbd = cfb.add_parser("cfbd-pull", help="Cache CFBD history for backtests")
    c_cfbd.add_argument("--seasons", required=True, help="e.g. 2015-2025")
    c_cfbd.add_argument("--refresh", action="store_true")
    cfb.add_parser("status", help="NCAAF row counts and credit balance")

    # --- NCAA D1 college baseball (issue #52) ---
    p_cbb = sub.add_parser(
        "ncaabase", help="NCAA D1 college baseball plumbing (games, finals, odds, grading)"
    )
    cbb = p_cbb.add_subparsers(dest="ncaabase_command", required=True)
    b_games = cbb.add_parser("games", help="Ingest ncaa-api D1 games for an ET date")
    b_games.add_argument("--date", default=None, help="ET date (default: today)")
    b_games.add_argument("--force", action="store_true", help="Ignore the season window")
    b_snap = cbb.add_parser("snapshot", help="Take a college baseball odds snapshot")
    b_snap.add_argument("--label", required=True, choices=["open", "pregame", "close"])
    b_snap.add_argument("--dry-run", action="store_true")
    b_snap.add_argument(
        "--force", action="store_true", help="Ignore odds_api.enabled and the season window"
    )
    b_grade = cbb.add_parser("grade", help="Refresh unsettled finals; settle pending picks")
    b_grade.add_argument("--date", default=None, help="Only refresh this ET date")
    cbb.add_parser("status", help="College baseball row counts and credit balance")

    args = parser.parse_args(argv)

    # Imports deferred so `--help` stays fast and dependency-light.
    if args.command == "snapshot":
        from .pipeline import cmd_snapshot

        cmd_snapshot(args.label, dry_run=args.dry_run)
    elif args.command == "picks":
        from .pipeline import cmd_picks

        cmd_picks(args.window_end_et, dry_run=args.dry_run, run_label=args.label)
    elif args.command == "splits":
        from .pipeline import cmd_splits

        cmd_splits(label=args.label, dry_run=args.dry_run)
    elif args.command == "grade":
        from .pipeline import cmd_grade

        cmd_grade(args.date)
    elif args.command == "report":
        from .pipeline import cmd_report

        cmd_report()
    elif args.command == "status":
        from .pipeline import cmd_status

        cmd_status()
    elif args.command == "pages":
        from .pipeline import cmd_pages

        cmd_pages(run_label=args.run_label)
    elif args.command == "backtest":
        from .backtest.engine import cmd_backtest

        cmd_backtest(args.seasons, strategy=args.strategy)
    elif args.command == "calibrate":
        from .backtest.calibrate import cmd_calibrate

        cmd_calibrate(args.train, args.validate, args.write_config)
    elif args.command == "ncaaf":
        from .ncaaf import pipeline as ncaaf

        if args.ncaaf_command == "games":
            ncaaf.cmd_games(args.date)
        elif args.ncaaf_command == "snapshot":
            ncaaf.cmd_snapshot(args.label, dry_run=args.dry_run)
        elif args.ncaaf_command == "grade":
            ncaaf.cmd_grade(args.date)
        elif args.ncaaf_command == "cfbd-pull":
            ncaaf.cmd_cfbd_pull(args.seasons, refresh=args.refresh)
        elif args.ncaaf_command == "status":
            ncaaf.cmd_status()
    elif args.command == "ncaabase":
        from .ncaabase import pipeline as ncaabase

        if args.ncaabase_command == "games":
            ncaabase.cmd_games(args.date, force=args.force)
        elif args.ncaabase_command == "snapshot":
            ncaabase.cmd_snapshot(args.label, dry_run=args.dry_run, force=args.force)
        elif args.ncaabase_command == "grade":
            ncaabase.cmd_grade(args.date)
        elif args.ncaabase_command == "status":
            ncaabase.cmd_status()
    elif args.command == "replay":
        from .replay import cmd_replay

        cmd_replay(strategy=args.strategy, from_et=args.from_et, to_et=args.to_et)


if __name__ == "__main__":
    main()
