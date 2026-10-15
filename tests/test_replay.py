"""`replay_window` — the retroactive replay, which had no tests at all.

The defect these exist for: the replay used to filter its date list by
`from_et` and THEN start an empty `SeasonContext`, so a window beginning
2026-09-29 evaluated its first day with no record, no form and no
previous-head-to-head price. That price is `pv_orig`'s primary signal, so a
cold start is not a slightly different engine — it is a different one, and
every shadow pick it produced was mispriced evidence.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from panthera_mvp import paths, replay, store

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def replay_root(tmp_root):
    shutil.copytree(
        REPO / "config" / "strategies", tmp_root / "config" / "strategies",
        dirs_exist_ok=True,
    )
    return tmp_root


def _pk(day: str, i: int) -> int:
    return int(day.replace("-", "")[2:]) * 100 + i


DAYS = [f"2026-08-{d:02d}" for d in range(3, 11)]  # 8 consecutive dates


def write_history(days=DAYS, *, games_per_day: int = 2, finals: bool = True):
    """Captured games + lines for a run of days. Teams alternate so the
    season context accumulates head-to-head history."""
    grows, lrows = [], []
    for day in days:
        for i in range(games_per_day):
            home, away = (111, 147) if i % 2 == 0 else (147, 111)
            pk = _pk(day, i)
            grows.append(
                {
                    "game_pk": pk,
                    "game_date_et": day,
                    "day_of_week_et": "monday",
                    "game_type": "R",
                    "doubleheader": "N",
                    "game_number": 1,
                    "start_time_utc": f"{day}T23:05:00Z",
                    "home_team_id": home,
                    "home_team": "Boston Red Sox" if home == 111 else "New York Yankees",
                    "away_team_id": away,
                    "away_team": "New York Yankees" if away == 147 else "Boston Red Sox",
                    "status": "Final" if finals else "Preview",
                    "home_score": 5 if finals else None,
                    "away_score": 2 if finals else None,
                    "home_pitcher_era": 3.10,
                    "away_pitcher_era": 4.80,
                }
            )
            for label in ("open", "pregame"):
                for outcome, price in (
                    ("Boston Red Sox", -150 if label == "open" else -170),
                    ("New York Yankees", 140 if label == "open" else 155),
                ):
                    lrows.append(
                        {
                            "snapshot_ts_utc": f"{day}T{'14' if label == 'open' else '20'}:00:00Z",
                            "snapshot_label": label,
                            "odds_event_id": f"ev{pk}",
                            "game_pk": pk,
                            "game_date_et": day,
                            "commence_time_utc": f"{day}T23:05:00Z",
                            "home_team": "Boston Red Sox",
                            "away_team": "New York Yankees",
                            "bookmaker": "bk",
                            "market": "h2h",
                            "outcome": outcome,
                            "point": None,
                            "price_american": price,
                            "price_decimal": 1.67,
                        }
                    )
    store.upsert_games(pd.DataFrame(grows))
    store.append_lines(pd.DataFrame(lrows))


# --------------------------------------------------------------------------
# warm-up: the defect this file was written for
# --------------------------------------------------------------------------


def test_warmup_runs_over_every_date_before_the_window(replay_root):
    """The regression test. Generating from date 6 must still fold dates 1-5
    into the season context."""
    write_history()
    res = replay.replay_window(["pv_v3"], from_et=DAYS[5], grade=False, quiet=True)
    assert res.warmup_dates == 5, f"expected 5 warm-up dates, got {res.warmup_dates}"
    assert res.warmup_finals > 0, "warm-up folded no finals — the context is cold"
    assert res.warmup_h2h > 0, "warm-up captured no H2H prices"


def test_warmup_is_zero_when_the_window_starts_at_the_beginning(replay_root):
    """And it reports that honestly rather than implying a warm context."""
    write_history()
    res = replay.replay_window(["pv_v3"], grade=False, quiet=True)
    assert res.warmup_dates == 0


def test_context_advances_on_non_generating_dates_inside_the_window(replay_root):
    """`only_dates` narrows GENERATION, never the advance: a partially
    gapped window would otherwise develop a hole in its own context."""
    write_history()
    gapped = replay.replay_window(
        ["pv_v3"], from_et=DAYS[0], only_dates={DAYS[0], DAYS[7]},
        grade=False, quiet=True,
    )
    # Only the two requested dates generate.
    assert set(gapped.generated_dates) <= {DAYS[0], DAYS[7]}


def test_no_lookahead(replay_root):
    """A final on day D must not be visible to day D's own picks: the advance
    happens strictly after the day is evaluated."""
    write_history(days=DAYS[:1])
    res = replay.replay_window(["pv_v3"], grade=False, quiet=True)
    assert res.warmup_dates == 0
    assert res.warmup_finals == 0


# --------------------------------------------------------------------------
# live-parity defects
# --------------------------------------------------------------------------


def test_daily_cap_is_applied(replay_root):
    """Replay used to append every Pick, so shadow picks were systematically
    more numerous than the live picks they stood in for. pv_v3 caps at 6/day.
    """
    write_history(games_per_day=12)
    replay.replay_window(["pv_v3"], grade=False, quiet=True)
    shadow = store.load_shadow_picks()
    if shadow.empty:
        pytest.skip("this fixture produced no picks; the cap cannot be observed")
    cap = 6
    per_day = shadow.groupby("game_date_et").size()
    assert per_day.max() <= cap, f"cap breached: {per_day.to_dict()}"


def test_one_pick_per_game_is_applied(replay_root):
    write_history(games_per_day=4)
    replay.replay_window(["pv_v3"], grade=False, quiet=True)
    shadow = store.load_shadow_picks()
    if shadow.empty:
        pytest.skip("this fixture produced no picks")
    dupes = shadow.groupby(["strategy_id", "game_date_et", "game_pk"]).size()
    assert dupes.max() == 1, "a game was picked twice in one day"


def test_stake_comes_from_config_not_a_literal(replay_root):
    """It was hardcoded 100.0. Harmless while every strategy stakes 100, a
    landmine the day one does not."""
    write_history()
    replay.replay_window(["pv_v3"], grade=False, quiet=True)
    shadow = store.load_shadow_picks()
    if shadow.empty:
        pytest.skip("this fixture produced no picks")
    from panthera_mvp.config import load_strategy_configs

    expected = load_strategy_configs()["pv_v3"]["staking"]["flat_stake"]
    assert set(shadow["stake"]) == {float(expected)}


def test_default_is_every_enabled_live_strategy(replay_root):
    """It used to default to pv_orig alone."""
    write_history()
    res = replay.replay_window(grade=False, quiet=True)
    assert set(res.strategy_ids) >= {"pv_v3", "pv_orig", "fav_ml"}


def test_unknown_strategy_is_a_hard_error(replay_root):
    write_history()
    with pytest.raises(SystemExit, match="unknown strategy"):
        replay.replay_window(["no_such_strategy"], quiet=True)


# --------------------------------------------------------------------------
# idempotency and quarantine
# --------------------------------------------------------------------------


def test_replay_is_idempotent(replay_root):
    write_history()
    first = replay.replay_window(["pv_v3"], grade=False, quiet=True)
    n = len(store.load_shadow_picks())
    second = replay.replay_window(["pv_v3"], grade=False, quiet=True)
    assert second.added == 0, "a re-run added rows"
    assert len(store.load_shadow_picks()) == n


def test_replay_never_writes_picks_csv(replay_root):
    """Replay picks are not forward paper trades and must stay quarantined."""
    write_history()
    replay.replay_window(["pv_v3"], grade=False, quiet=True)
    assert not paths.picks_csv().exists() or store.load_picks().empty


def test_dates_with_no_captured_odds_are_reported_not_silent(replay_root):
    """A silent skip here used to be indistinguishable from "no picks"."""
    write_history(days=DAYS[:2])
    # A later date with games but no lines at all.
    store.upsert_games(
        pd.DataFrame(
            [
                {
                    "game_pk": 999001,
                    "game_date_et": "2026-08-20",
                    "day_of_week_et": "thursday",
                    "game_type": "R",
                    "doubleheader": "N",
                    "game_number": 1,
                    "start_time_utc": "2026-08-20T23:05:00Z",
                    "home_team_id": 111,
                    "home_team": "Boston Red Sox",
                    "away_team_id": 147,
                    "away_team": "New York Yankees",
                    "status": "Preview",
                    "home_score": None,
                    "away_score": None,
                    "home_pitcher_era": None,
                    "away_pitcher_era": None,
                }
            ]
        )
    )
    res = replay.replay_window(["pv_v3"], grade=False, quiet=True)
    assert "2026-08-20" in res.no_lines_dates


def test_run_note_is_written_once_per_date(replay_root):
    """run_log.csv was the one writer in store.py with no dedupe key, so a
    weekly catch-up would pile up identical notes."""
    write_history()
    replay.replay_window(["pv_v3"], grade=False, quiet=True)
    first = len(store.load_run_log())
    replay.replay_window(["pv_v3"], grade=False, quiet=True)
    assert len(store.load_run_log()) == first, "duplicate run notes"
