"""The lab's vectorised rules and the live engine must pick the same legs.

Random slates (spreads, totals, several books, ranks, SP+, wind, domes, missing
markets, kickoffs inside the minimum lead) run through `parlay.decide_day` and
through `build_feature_rows` -> `qualify_frame`. Any disagreement is a bug in the
lab, because the engine is what is paper-traded.
"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
import yaml

from panthera_mvp.lab import ncaaf_rules, store
from panthera_mvp.lab.features import FEATURE_COLUMNS, build_feature_rows
from panthera_mvp.ncaaf import parlay
from panthera_mvp.ncaaf.sources import school_key

STRATEGY_YAML = "config/ncaaf_strategies/cfb_spread_total_parlay.yaml"
NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
OPEN, DEC = "2026-10-01T12:00:00Z", "2026-10-03T15:00:00Z"
FEATURE_CFG = {"home_field_points": 2.5, "max_gap_days": 15}


@pytest.fixture
def scfg():
    from conftest import REPO

    with open(REPO / STRATEGY_YAML) as fh:
        return yaml.safe_load(fh)


def params_from(scfg) -> dict:
    s = scfg["signals"]
    return {
        "min_lead_minutes": scfg["decision"]["min_lead_minutes"],
        "signals": {k: {kk: vv for kk, vv in s[k].items()}
                    for k in ("line_move_spread", "line_move_total", "letdown", "look_ahead",
                              "weather_wind_under", "sp_plus_edge")},
        "legs": {"min_signals": scfg["legs"]["min_signals"]},
        "ticket": {"max_bets_per_day": None, "max_price_american": None, "rank_by": "strength"},
        "bet_limits": {"skip_day_after_loss": False},
    }


def _price_rows(eid, home, away, ts, spread, total, book, price):
    dec = round(1 + 100 / abs(price), 4) if price < 0 else 1 + price / 100
    base = {"snapshot_ts_utc": ts, "event_id": eid, "home_team": home, "away_team": away,
            "bookmaker": book, "price_american": price, "price_decimal": dec}
    rows = []
    if spread is not None:
        rows += [base | {"market": "spreads", "outcome": home, "point": spread},
                 base | {"market": "spreads", "outcome": away, "point": -spread}]
    if total is not None:
        rows += [base | {"market": "totals", "outcome": "Over", "point": total},
                 base | {"market": "totals", "outcome": "Under", "point": total}]
    return rows


def random_slate(seed: int, n: int = 90):
    rng = np.random.default_rng(seed)
    games, lines, sched, sp, wind = [], [], [], {}, {}
    for i in range(n):
        eid, home, away = str(i), f"H{i} Hawks", f"A{i} Owls"
        minute = int(rng.choice([5, 14, 15, 16, 40]))  # some inside the 15-minute lead
        hour = int(rng.integers(15, 23))
        start = f"2026-10-03T{hour:02d}:{minute:02d}:00Z"
        indoor = [True, False, None][int(rng.integers(0, 3))]
        games.append({
            "event_id": eid, "game_date_et": "2026-10-03", "start_time_utc": start,
            "home_team": home, "away_team": away, "home_rank": None, "away_rank": None,
            "neutral_site": bool(rng.random() < 0.15), "conference_game": True,
            "venue": f"{home} Stadium", "indoor": indoor, "status": "Scheduled",
            "home_score": None, "away_score": None,
            "home_school": f"H{i}", "away_school": f"A{i}",
        })
        has_spread, has_total = rng.random() < 0.9, rng.random() < 0.9
        base_s = float(rng.choice(np.arange(-24, 24.5, 0.5)))
        base_t = float(rng.choice(np.arange(38, 70, 0.5)))
        for ts, shift_s, shift_t in ((OPEN, 0.0, 0.0),
                                     (DEC, float(rng.choice([0, 0, 1, 2, -1, -2.5])),
                                      float(rng.choice([0, 0, 1, 2.5, -2, -3])))):
            for b in range(int(rng.integers(1, 4))):
                lines += _price_rows(
                    eid, home, away, ts,
                    base_s + shift_s + 0.5 * int(rng.integers(-1, 2)) if has_spread else None,
                    base_t + shift_t + 0.5 * int(rng.integers(-1, 2)) if has_total else None,
                    f"book{b}", int(rng.choice([-120, -115, -110, -105, 100])),
                )
        # Prior / next games for the two teams (ranked opponents, wins and losses).
        for team, side in ((home, "home"), (away, "away")):
            if rng.random() < 0.5:
                opp_rank = float(rng.integers(1, 40)) if rng.random() < 0.8 else None
                won = rng.random() < 0.6
                sched.append({
                    "event_id": f"p{i}{side}", "game_date_et": "2026-09-26",
                    "start_time_utc": "2026-09-26T19:00:00Z",
                    "home_team": team, "away_team": f"Opp{i}{side} X", "home_rank": None,
                    "away_rank": opp_rank, "status": "Final" if rng.random() < 0.9 else "Scheduled",
                    "home_score": 30 if won else 10, "away_score": 20,
                })
            if rng.random() < 0.5:
                sched.append({
                    "event_id": f"n{i}{side}", "game_date_et": "2026-10-10",
                    "start_time_utc": "2026-10-10T19:00:00Z",
                    "home_team": team, "away_team": f"Nxt{i}{side} X", "home_rank": None,
                    "away_rank": float(rng.integers(1, 40)) if rng.random() < 0.8 else None,
                    "status": str(rng.choice(["Scheduled", "Postponed"], p=[0.9, 0.1])),
                    "home_score": None, "away_score": None,
                })
        if rng.random() < 0.8:
            sp[school_key(f"H{i}")] = float(rng.normal(8, 9))
        if rng.random() < 0.8:
            sp[school_key(f"A{i}")] = float(rng.normal(8, 9))
        if rng.random() < 0.6:
            wind[eid] = float(rng.choice([5, 12, 15, 16, 22]))
    games_df = pd.DataFrame(games)
    views = parlay.build_views(games_df, pd.DataFrame(lines), DEC)
    schedules = parlay.team_schedules(pd.DataFrame(sched)) if sched else {}
    return views, schedules, sp, wind


def engine_legs(scfg, views, schedules, sp, wind) -> set:
    d = parlay.decide_day(views, scfg, NOW, schedules, sp, wind)
    return {(lg.event_id, lg.market, lg.side, lg.line, lg.signal_ids, round(lg.price_decimal, 4))
            for lg in d.qualifiers}


def lab_legs(bets: pd.DataFrame) -> set:
    return {(r.event_id, r.market, r.side, r.line, r.signal_ids, round(r.price_decimal, 4))
            for r in bets.itertuples()}


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_lab_rules_match_the_engine(scfg, seed):
    views, schedules, sp, wind = random_slate(seed)
    assert len(views) > 50
    want = engine_legs(scfg, views, schedules, sp, wind)
    assert len(want) >= 5  # the slate must actually exercise the signals

    rows = build_feature_rows(views, schedules, sp, wind, "2026-10-03", DEC, NOW,
                              feature_cfg=FEATURE_CFG)
    assert list(rows[0]) == FEATURE_COLUMNS
    got = lab_legs(ncaaf_rules.qualify_frame(pd.DataFrame(rows), params_from(scfg)))
    assert got == want

    # Same answer one row at a time (the qualify_row API).
    one_by_one = set()
    for r in rows:
        for b in ncaaf_rules.qualify_row(r, params_from(scfg)):
            one_by_one.add((b["event_id"], b["market"], b["side"], b["line"],
                            b["signal_ids"], round(b["price_decimal"], 4)))
    assert one_by_one == want


def test_every_signal_and_both_markets_are_exercised(scfg):
    seen = set()
    for seed in range(1, 7):
        views, schedules, sp, wind = random_slate(seed)
        for lg in parlay.decide_day(views, scfg, NOW, schedules, sp, wind).qualifiers:
            seen.update(lg.signal_ids.split("+"))
    assert seen >= {"S1", "S2", "S3", "S4", "S5", "S6"}


def test_parity_survives_the_csv_round_trip(scfg, tmp_path, monkeypatch):
    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    views, schedules, sp, wind = random_slate(7)
    want = engine_legs(scfg, views, schedules, sp, wind)
    rows = build_feature_rows(views, schedules, sp, wind, "2026-10-03", DEC, NOW,
                              feature_cfg=FEATURE_CFG)
    assert store.append_features("ncaaf", rows) == len(rows)
    loaded = store.load_features("ncaaf")
    got = lab_legs(ncaaf_rules.qualify_frame(loaded, params_from(scfg)))
    assert got == want


def test_a_disabled_signal_stops_firing(scfg):
    views, schedules, sp, wind = random_slate(2)
    rows = pd.DataFrame(build_feature_rows(views, schedules, sp, wind, "2026-10-03", DEC, NOW,
                                           feature_cfg=FEATURE_CFG))
    p = params_from(scfg)
    p["signals"]["sp_plus_edge"]["enabled"] = False
    ids = set("+".join(ncaaf_rules.qualify_frame(rows, p)["signal_ids"]).split("+"))
    assert "S6" not in ids
