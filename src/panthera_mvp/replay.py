"""Retroactive replay — zero-API-cost backtest over the live pipeline's own
captured odds/games history (`panthera-mvp replay`).

Every live snapshot since launch (data/odds/lines.csv) and every game result
recorded since (data/games/games.csv) already exist on disk; this replays a
strategy engine over them WITHOUT taking new snapshots or spending API
credits. Output goes to data/picks/shadow_picks.csv — a SEPARATE file from
the real ledger (data/picks/picks.csv), never pooled into any strategy's
pre-registered verdict (report.py renders it as a clearly marked
RETROACTIVE section). This keeps the append-once, pre-registered-criteria
protocol intact: replay picks were not placed in real time and cannot stand
in for a forward test, however useful they are as an early read.

Caveats stated in the report, not hidden:
  - ERA is only populated in games.csv from 2026-08-16 forward (the
    probablePitcher hydrate fix) — ERA-dependent gates are partly dormant
    for earlier dates.
  - The season context (record, rank, form, ATS streaks, previous-H2H
    prices) is built ONLY from what this pipeline has itself captured —
    short and sparse near the start of the window, exactly like the
    documented gap for early-season merit inputs in live picks.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from . import store
from .clients.mlb import GameInfo
from .grading import _result_for_pick
from .strategy.daytype import day_type
from .strategy.dossier import Dossier, SeasonContext
from .strategy.movement import extract_game_prices, extract_totals_prices
from .strategy.registry import StrategyContext, engines
from .strategy.rules import Pick
from .strategy.slots import assign_slots
from .timeutil import now_utc, parse_utc, utc_iso


def _game_info(row) -> GameInfo:
    return GameInfo(
        game_pk=int(row.game_pk),
        game_date_et=str(row.game_date_et),
        game_type=str(row.game_type),
        status="Preview",  # replay always treats the game as not-yet-started
        detailed_state="Scheduled",
        start_utc=parse_utc(str(row.start_time_utc)),
        doubleheader=str(row.doubleheader) if pd.notna(row.doubleheader) else "N",
        game_number=int(row.game_number) if pd.notna(row.game_number) else 1,
        home_team_id=int(row.home_team_id),
        home_team=str(row.home_team),
        away_team_id=int(row.away_team_id),
        away_team=str(row.away_team),
    )


def _pick_row(p: Pick, strategy_id: str, chash: str) -> dict:
    return {
        "pick_id": f"{strategy_id}-{p.game_pk}-{p.market}-{p.game_date_et.replace('-', '')}",
        "strategy_id": strategy_id,
        "created_ts_utc": utc_iso(now_utc()),
        "game_date_et": p.game_date_et,
        "game_pk": p.game_pk,
        "odds_event_id": p.odds_event_id,
        "matchup": p.matchup,
        "start_time_et": p.start_time_et,
        "day_type": p.day_type,
        "slot_type": p.slot_type,
        "rule_id": p.rule_id,
        "market": p.market,
        "selection": p.selection,
        "line": p.line,
        "price_american": p.price_american,
        "price_decimal": p.price_decimal,
        "stake": 100.0,
        "open_price": p.open_price,
        "latest_price": p.latest_price,
        "movement_cents": p.movement_cents,
        "rationale": p.rationale,
        "config_hash": chash,
        "status": "pending",
        "settled_ts_utc": None,
        "final_score": None,
        "profit": None,
        "close_price": None,
        "clv_cents": None,
    }


def cmd_replay(
    strategy: str = "pv_orig", from_et: str | None = None, to_et: str | None = None
) -> None:
    from .config import config_hash, load_strategy_configs

    strategies = load_strategy_configs(known_engines=set(engines()))
    if strategy not in strategies:
        raise SystemExit(f"[replay] unknown strategy id: {strategy}")
    scfg = strategies[strategy]
    engine = engines()[scfg["strategy"]["engine"]]
    chash = config_hash(scfg)

    games = store.load_games()
    lines = store.load_lines()
    if games.empty or lines.empty:
        print("[replay] no captured games/lines to replay")
        return

    dates = sorted(games["game_date_et"].unique())
    if from_et:
        dates = [d for d in dates if d >= from_et]
    if to_et:
        dates = [d for d in dates if d <= to_et]
    if not dates:
        print("[replay] no dates in range")
        return

    boundary = int(scfg.get("hybrid_boundary_hour_et", 18))
    ctx = SeasonContext()
    rows = []
    for d in dates:
        day_games = games[games["game_date_et"] == d]
        game_infos = [_game_info(r) for r in day_games.itertuples(index=False)]
        dtype = day_type(date.fromisoformat(d), scfg)
        slot_map = assign_slots(
            [(g.game_pk, g.start_utc) for g in game_infos], dtype, boundary
        )
        lines_today = lines[lines["game_date_et"] == d]
        events_by_pk = (
            lines_today.dropna(subset=["game_pk"])
            .astype({"game_pk": int})
            .drop_duplicates("game_pk")
            .set_index("game_pk")["odds_event_id"]
            .to_dict()
        )

        for g, row in zip(game_infos, day_games.itertuples(index=False), strict=True):
            event_id = events_by_pk.get(g.game_pk)
            prices = (
                extract_game_prices(
                    lines_today, event_id, g.home_team, g.away_team,
                    latest_label="pregame",
                )
                if event_id
                else None
            )
            totals = (
                extract_totals_prices(lines_today, event_id, latest_label="pregame")
                if event_id
                else None
            )
            era_home = row.home_pitcher_era if pd.notna(row.home_pitcher_era) else None
            era_away = row.away_pitcher_era if pd.notna(row.away_pitcher_era) else None
            dossier = Dossier.from_context(
                ctx,
                home_key=g.home_team_id,
                away_key=g.away_team_id,
                era_home=era_home,
                era_away=era_away,
                last10_n=int(scfg.get("dossier", {}).get("last10_n", 10)),
            )
            ctx_kwargs = StrategyContext(
                game=g,
                odds_event_id=event_id,
                prices=prices,
                totals=totals,
                slot_type=slot_map.get(g.game_pk),
                dossier=dossier,
                cfg=scfg,
            )
            outcome = engine(ctx_kwargs)
            if isinstance(outcome, Pick):
                rows.append(_pick_row(outcome, strategy, chash))

        # Advance the season context AFTER this day's picks are generated —
        # no lookahead. Only Final games with prices contribute H2H prices.
        finals_today = day_games[day_games["status"] == "Final"]
        for row in finals_today.itertuples(index=False):
            if pd.isna(row.home_score) or pd.isna(row.away_score):
                continue
            ctx.add_final(
                row.home_team_id, row.away_team_id,
                int(row.home_score), int(row.away_score),
            )
            ev_rows = lines_today[lines_today["game_pk"] == row.game_pk]
            if ev_rows.empty:
                continue
            event_id = ev_rows.iloc[0]["odds_event_id"]
            p = extract_game_prices(lines_today, event_id, row.home_team, row.away_team)
            if p is not None:
                ctx.add_h2h_price(
                    row.home_team_id, row.away_team_id,
                    p.home_ml_latest, p.away_ml_latest,
                    p.home_rl_price, p.away_rl_price,
                )

    picks_df = pd.DataFrame(rows)
    added = store.append_shadow_picks(picks_df)
    print(f"[replay:{strategy}] {added} shadow pick(s) added over {len(dates)} date(s)")

    # Grade whatever the shadow ledger now has pending, against games.csv.
    shadow = store.load_shadow_picks()
    pending = shadow[shadow["status"] == "pending"]
    games_by_pk = games.set_index("game_pk")
    settlements = []
    for _, pick in pending.iterrows():
        pk = pick["game_pk"]
        if pk not in games_by_pk.index:
            continue
        outcome = _result_for_pick(pick, games_by_pk.loc[pk])
        if outcome is None:
            continue
        status, final_score = outcome
        stake = float(pick["stake"])
        profit = (
            round(stake * (float(pick["price_decimal"]) - 1), 2)
            if status == "win"
            else (-stake if status == "loss" else 0.0)
        )
        settlements.append(
            {
                "pick_id": pick["pick_id"],
                "status": status,
                "settled_ts_utc": utc_iso(now_utc()),
                "final_score": final_score,
                "profit": profit,
            }
        )
    graded = store.settle_shadow_picks(pd.DataFrame(settlements))
    print(f"[replay:{strategy}] {graded} shadow pick(s) graded")
