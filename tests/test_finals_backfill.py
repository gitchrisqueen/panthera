"""A game stored `Final` with no score must still be fillable.

The live defect these tests pin: every sport's finals fallback selected its
targets by STATUS alone — MLB `status != "Final"`, NCAAF `~status.isin(SETTLED)`,
college baseball `status.isin(UNSETTLED)`. All three excluded a row recorded
`Final` with a NULL score, which is the one state that most needs a fallback:
`grading` settles from the score, so a pick on such a game can never settle at
all. On 2026-09-27 the MLB API returned game 823490 (Yankees/Orioles) as Final
with no linescore and three picks sat pending for 18 days behind it.

Each test below starts from that exact row shape, so none of them can pass
against the old status-only guard. The sibling sports' arms of the same fix
are tested beside their own fixtures, in `test_ncaabase.py` and
`test_ncaaf_week.py`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from panthera_mvp import paths, pipeline, store
from panthera_mvp.clients import espn
from panthera_mvp.grading import grade_pending
from panthera_mvp.matching import nearest_start

REPO = Path(__file__).resolve().parents[1]
DAY = "2026-08-01"
PK = 776001
DOUBLEHEADER_FIXTURE = "espn_scoreboard_doubleheader.json"


def _game(status="Final", home_score=None, away_score=None, score_source="mlb"):
    """The live shape of games.csv row 823490: Final, no scores, and the
    derived columns `_refresh_games` computes from `score or 0`."""
    return {c: None for c in store.GAMES_COLUMNS} | {
        "game_pk": PK,
        "game_date_et": DAY,
        "home_team": "Boston Red Sox",
        "away_team": "New York Yankees",
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "score_source": score_source,
    }


def _pick(pick_id="p1", selection="New York Yankees"):
    return {c: None for c in store.PICKS_COLUMNS} | {
        "pick_id": pick_id,
        "game_pk": PK,
        "game_date_et": DAY,
        "market": "ml",
        "selection": selection,
        "price_decimal": 1.9091,
        "stake": 100,
        "status": "pending",
    }


@pytest.fixture
def health_config(tmp_root):
    """`tmp_root` plus the REAL config/health.yaml, which carries the
    fallback's `grading.espn_fallback` tolerances.

    Copied per-test rather than into `tmp_root` itself, because
    `test_doctor.py` pins doctor's exit-3-on-a-missing-health.yaml behaviour
    against a root that deliberately has none.
    """
    shutil.copy(REPO / "config" / "health.yaml", tmp_root / "config" / "health.yaml")
    return tmp_root


@pytest.fixture
def espn_final(monkeypatch, espn_payload):
    """`espn.get_scoreboard` answered from tests/fixtures/espn_scoreboard.json
    through the real parser — Red Sox 3, Yankees 5, completed. No network."""
    calls = []

    def fake(date_et, session=None):
        calls.append(date_et)
        return espn.parse_scoreboard(espn_payload)

    monkeypatch.setattr(pipeline.espn, "get_scoreboard", fake)
    return calls


# --------------------------------------------------------------------------
# the mask itself
# --------------------------------------------------------------------------


def test_needs_final_admits_final_with_a_missing_score():
    """The regression in one assertion: Final+NULL is selectable, and a
    complete final is not. `status != "Final"` alone fails the first row."""
    games = pd.DataFrame(
        [
            _game(),  # Final, both scores NULL  -> fillable
            _game(home_score=3, away_score=None),  # half a score -> fillable
            _game(status="Preview"),  # not played yet   -> fillable
            _game(home_score=3, away_score=5),  # complete final  -> NOT
        ]
    )
    assert pipeline._needs_final(games).tolist() == [True, True, True, False]


# --------------------------------------------------------------------------
# MLB end to end
# --------------------------------------------------------------------------


def test_espn_fallback_fills_a_final_with_no_score_and_grading_settles(
    tmp_root, espn_final
):
    """End to end on the live bug: Final-with-no-score + a pending pick, the
    ESPN fixture carrying the score, and the pick settled from it."""
    store.upsert_games(pd.DataFrame([_game()]))
    store.append_picks(pd.DataFrame([_pick()]))
    assert grade_pending().empty  # cannot settle: no score to settle from

    assert pipeline._espn_fallback(DAY) == 1
    assert espn_final == [DAY]

    game = store.load_games().set_index("game_pk").loc[PK]
    assert (game["status"], game["score_source"]) == ("Final", "espn")
    assert (int(game["home_score"]), int(game["away_score"])) == (3, 5)
    assert game["winner"] == "New York Yankees"
    assert (int(game["run_diff"]), int(game["total_runs"])) == (2, 8)

    settled = grade_pending()
    assert len(settled) == 1
    assert settled.iloc[0]["status"] == "win"
    assert settled.iloc[0]["final_score"] == "New York Yankees 5 - Boston Red Sox 3"
    assert store.load_picks().iloc[0]["status"] == "win"


def test_fallback_never_rewrites_a_complete_final(tmp_root, espn_final):
    """A final the store already has, with a score ESPN disagrees with, is
    left alone — the fallback fills holes, it does not restate finals."""
    store.upsert_games(pd.DataFrame([_game(home_score=1, away_score=0)]))

    assert pipeline._espn_fallback(DAY) == 0
    assert espn_final == []  # no hole on this date, so no network call at all

    game = store.load_games().set_index("game_pk").loc[PK]
    assert (int(game["home_score"]), int(game["away_score"])) == (1, 0)
    assert game["score_source"] == "mlb"


def test_cmd_grade_runs_the_fallback_when_the_mlb_refresh_succeeds(
    tmp_root, monkeypatch, espn_final
):
    """The other half of the defect: the fallback used to run only when
    `_refresh_games` RAISED. The MLB API also fails by succeeding with a hole,
    which is how 823490 got its empty score in the first place, so a
    successful refresh must not skip the fallback."""
    store.upsert_games(pd.DataFrame([_game()]))
    store.append_picks(pd.DataFrame([_pick()]))
    # A refresh that succeeds and re-asserts the hole, exactly as the live
    # MLB API did for 823490 (status Final, scores absent).
    monkeypatch.setattr(
        pipeline,
        "_refresh_games",
        lambda d: store.upsert_games(pd.DataFrame([_game()])) or [],
    )
    pipeline.cmd_grade(DAY)

    assert espn_final == [DAY]
    assert store.load_picks().iloc[0]["status"] == "win"


# --------------------------------------------------------------------------
# the write path: a filled score has to survive the next refresh
# --------------------------------------------------------------------------


def test_upsert_games_never_blanks_a_stored_score(tmp_root):
    """`snapshot` and `picks` both call `_refresh_games`, and neither has a
    fallback behind it. Without this guard the next run of either wiped the
    score the fallback had just filled, so the repair never lasted a day."""
    store.upsert_games(pd.DataFrame([_game(home_score=3, away_score=5, score_source="espn")]))

    store.upsert_games(pd.DataFrame([_game()]))  # MLB API: Final, no linescore

    game = store.load_games().set_index("game_pk").loc[PK]
    assert (int(game["home_score"]), int(game["away_score"])) == (3, 5)
    assert game["score_source"] == "espn"


def test_upsert_games_still_replaces_a_scored_row_with_a_corrected_score(tmp_root):
    """The guard rejects an ABSENT score, not a different one — a genuine
    correction still lands, so this is not a blanket freeze on finals."""
    store.upsert_games(pd.DataFrame([_game(home_score=3, away_score=5)]))
    store.upsert_games(pd.DataFrame([_game(home_score=4, away_score=5)]))

    game = store.load_games().set_index("game_pk").loc[PK]
    assert (int(game["home_score"]), int(game["away_score"])) == (4, 5)


def test_repair_survives_a_snapshot_style_refresh(tmp_root, espn_final):
    """The two halves together: fill the hole, then let a refresh that still
    reports no linescore run over it. The pick stays settled and the score
    stays on the row."""
    store.upsert_games(pd.DataFrame([_game()]))
    store.append_picks(pd.DataFrame([_pick()]))
    pipeline._espn_fallback(DAY)
    grade_pending()

    store.upsert_games(pd.DataFrame([_game()]))  # a later snapshot's refresh

    game = store.load_games().set_index("game_pk").loc[PK]
    assert (int(game["home_score"]), int(game["away_score"])) == (3, 5)
    assert store.load_picks().iloc[0]["status"] == "win"


def test_fallback_writes_nothing_when_it_fills_nothing(tmp_root, monkeypatch):
    """An ESPN scoreboard with no usable final must not rewrite games.csv."""
    store.upsert_games(pd.DataFrame([_game()]))
    before = paths.games_csv().read_text()
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", None, None, False)
        ],
    )

    assert pipeline._espn_fallback(DAY) == 0
    assert paths.games_csv().read_text() == before


# --------------------------------------------------------------------------
# the game that actually blocked the three picks: a rain-out stored as Final
# --------------------------------------------------------------------------
#
# `panthera-mvp doctor` reported game 823490 as "Final with no score recorded"
# and suggested backfilling the score. There is no score to backfill: the MLB
# API returns it as abstractGameState "Final", detailedState "Cancelled",
# reason "Rain". tests/fixtures/mlb_schedule_cancelled.json is that live
# `/schedule` response, captured WITHOUT the `hydrate` parameter the pipeline
# sends — so it carries the status block this fix turns on, but no
# `probablePitcher`, and therefore no ERAs.
# ESPN has no final for it either. The row was unsettleable because
# the pipeline stored `abstractGameState`, which cannot express "called off",
# so grading could neither settle it nor reach its void branch.


CANCELLED_FIXTURE = "mlb_schedule_cancelled.json"


def test_stored_status_reads_called_off_from_detailed_state(fixtures_dir):
    """The mapping, per detailedState head. `abstractGameState` is "Final" for
    every row here, so anything reading it alone sees a settled game."""
    from dataclasses import replace

    from panthera_mvp.clients import mlb

    with open(fixtures_dir / CANCELLED_FIXTURE) as fh:
        game = mlb.parse_schedule(json.load(fh))[0]
    assert (game.status, game.detailed_state) == ("Final", "Cancelled")
    assert mlb.stored_status(game) == "Cancelled"

    def with_state(detailed, abstract="Final"):
        return mlb.stored_status(
            replace(game, detailed_state=detailed, status=abstract)
        )

    assert with_state("Canceled") == "Cancelled"  # MLB writes both spellings
    assert with_state("Postponed") == "Postponed"
    assert with_state("Suspended: Rain") == "Suspended"  # reason suffix
    # A game that HAS a score, and one still being played, pass through.
    assert with_state("Completed Early: Rain") == "Final"
    assert with_state("Final") == "Final"
    assert with_state("Delayed Start: Rain", abstract="Live") == "Live"
    assert with_state("Scheduled", abstract="Preview") == "Preview"


def test_refresh_stores_a_rain_out_as_cancelled_with_no_derived_result(
    tmp_root, monkeypatch, fixtures_dir
):
    """`_refresh_games` must not write a called-off game as Final, and must not
    invent a 0-0 result for it — the live row carried winner=Baltimore Orioles,
    run_diff=0, total_runs=0 for a game that was never played."""
    monkeypatch.setenv("PANTHERA_MLB_FIXTURE", str(fixtures_dir / CANCELLED_FIXTURE))

    pipeline._refresh_games("2026-09-27")

    game = store.load_games().set_index("game_pk").loc[823490]
    assert game["status"] == "Cancelled"
    assert pd.isna(game["home_score"]) and pd.isna(game["away_score"])
    for col in ("winner", "run_diff", "total_runs"):
        assert pd.isna(game[col]), f"{col} was derived for a game never played"


def test_grade_voids_picks_on_a_cancelled_game(tmp_root, monkeypatch, fixtures_dir):
    """The live outcome: the three picks on 823490 void rather than stay
    pending forever. `grading`'s void branch already existed — the pipeline
    simply never wrote a status it could match."""
    monkeypatch.setenv("PANTHERA_MLB_FIXTURE", str(fixtures_dir / CANCELLED_FIXTURE))
    picks = pd.DataFrame(
        [
            _pick(pid, sel) | {"game_pk": 823490, "game_date_et": "2026-09-27"}
            for pid, sel in [
                ("fav_ml-823490-ml-20260927", "New York Yankees"),
                ("pv_v3-823490-ml-20260927", "New York Yankees"),
                ("sharp_split-823490-ml-20260927", "Baltimore Orioles"),
            ]
        ]
    )
    store.append_picks(picks)

    pipeline._refresh_games("2026-09-27")
    settled = grade_pending()

    assert len(settled) == 3
    assert set(settled["status"]) == {"void"}
    assert set(settled["profit"]) == {0.0}
    assert store.load_picks()["status"].tolist() == ["void"] * 3


def test_fallback_does_not_reopen_a_called_off_game(tmp_root, espn_final):
    """Parity with NCAAF and college baseball: a called-off row is not a hole
    to fill. ESPN keeps stale 0-0 rows for rain-outs, and MLB stays the
    authority if the game is ever resumed."""
    store.upsert_games(pd.DataFrame([_game(status="Cancelled")]))

    assert pipeline._espn_fallback(DAY) == 0
    assert espn_final == []

    assert store.load_games().iloc[0]["status"] == "Cancelled"


# --------------------------------------------------------------------------
# a suspended game is resumed, so it must not void (gauntlet round 1, E/H)
# --------------------------------------------------------------------------


def test_suspended_is_not_voided_and_settles_once_resumed(tmp_root):
    """MLB resumes a suspended game under the same gamePk, so a pick on it
    stays pending until the real final arrives.

    This is the one called-off status that does NOT mean "no score will ever
    exist". Voiding it would be irreversible — `store.settle_picks` only
    rewrites rows still `pending` — so the true win/loss could never land.
    College baseball already settles it this way
    (`test_ncaabase.py`: `pick("Suspended") is None  # resumed later`).
    """
    store.upsert_games(pd.DataFrame([_game(status="Suspended")]))
    store.append_picks(pd.DataFrame([_pick()]))

    assert grade_pending().empty, "a suspended game was voided"
    assert store.load_picks().iloc[0]["status"] == "pending"

    # Resumed and completed the next day: the pick settles on the real result.
    store.upsert_games(pd.DataFrame([_game(home_score=3, away_score=5)]))
    settled = grade_pending()
    assert len(settled) == 1
    assert settled.iloc[0]["status"] == "win"


def test_cancelled_and_postponed_still_void(tmp_root):
    """The two statuses that DO mean no score will ever exist. Guards the
    narrowing above against going too far."""
    for status in ("Cancelled", "Postponed"):
        store.upsert_games(pd.DataFrame([_game(status=status)]))
        store.append_picks(pd.DataFrame([_pick(pick_id=f"p-{status}")]))

    settled = grade_pending()
    assert set(settled["status"]) == {"void"}


def test_void_vocabulary_has_exactly_one_definition():
    """`grading` reads the same constant the pipeline writes, so a new
    called-off head cannot be settled by one and ignored by the other."""
    import inspect

    from panthera_mvp import grading as grading_mod
    from panthera_mvp.clients import mlb

    assert mlb.VOID_STATUSES == ("Cancelled", "Postponed")
    assert "Suspended" in mlb.CALLED_OFF_STATUSES  # not reopened by ESPN...
    assert "Suspended" not in mlb.VOID_STATUSES  # ...but never voided
    # The literal tuple is gone from grading: it reads the constant.
    src = inspect.getsource(grading_mod)
    assert '"Postponed"' not in src and "'Postponed'" not in src
    assert "VOID_STATUSES" in src


# --------------------------------------------------------------------------
# a doubleheader is ambiguous, so it is skipped, not guessed (round 1, E/H)
# --------------------------------------------------------------------------


def test_parse_scoreboard_carries_the_start_time(espn_payload, fixtures_dir):
    """The new client field, from the fixtures and through the real parser.

    `EspnGame` carried no start time, which is the whole reason the fallback
    could not tell two games of one matchup apart. ESPN publishes it as
    `competitions[].date`; it is stored UTC ISO-8601, like every other start
    time in the repo.
    """
    [one] = espn.parse_scoreboard(espn_payload)
    assert one.start_time_utc == "2026-08-01T17:05:00Z"

    with open(fixtures_dir / DOUBLEHEADER_FIXTURE) as fh:
        both = espn.parse_scoreboard(json.load(fh))
    assert [g.start_time_utc for g in both] == [
        "2026-08-01T17:05:00Z",
        "2026-08-01T23:15:00Z",
    ]
    # Same matchup, both completed: the payload shape that used to be
    # unsplittable.
    assert {(g.home_team, g.away_team) for g in both} == {
        ("Boston Red Sox", "New York Yankees")
    }

    # A payload without a date still yields the event. Dropping it would make
    # an ordinary unique-matchup date unfillable, which is a second hole, not
    # a fix.
    [dateless] = espn.parse_scoreboard(
        {"events": [{"competitions": [c | {"date": None}
                     for c in espn_payload["events"][0]["competitions"]]}]}
    )
    assert dateless.start_time_utc == ""


def test_nearest_start_window_and_ambiguity():
    """The shared decision, in isolation: outside the window is not a
    candidate, a clear nearest wins, and two near-equal gaps are refused.

    This is the rule `ncaabase/matching.py` already ran on and MLB now shares
    (`matching.nearest_start`), so it is pinned once rather than per caller.
    """
    # Nothing inside a 1h window when the only candidate is 2h away.
    assert nearest_start([(7200.0, "a", 1)], 1, 60) == "no game within the start-time window"
    # A clear nearest: 0s vs 6h10m, the real split-doubleheader gap.
    assert nearest_start([(0.0, "a", 1), (22200.0, "b", 2)], 8, 60) == ("a", 1)
    # 30 minutes apart is inside the 60-minute ambiguity window: refused.
    reason = nearest_start([(0.0, "a", 1), (1800.0, "b", 2)], 8, 60)
    assert isinstance(reason, str) and "ambiguous between a and b" in reason


def test_doubleheader_fills_only_the_game_with_the_hole(
    health_config, monkeypatch, fixtures_dir
):
    """The behaviour PR #69 could not deliver: game 1 complete, game 2 a
    score hole, and the fallback fills game 2 alone.

    #69 made an ambiguous match fail closed, which was right and incomplete:
    the guard was matchup-wide, so this date — one settled game, one hole —
    was refused forever rather than half-filled. The ESPN events now carry
    start times and are keyed onto one stored row each.

    Note what the scores prove. Game 1 was Red Sox 6, Yankees 0; game 2 was
    Yankees 9, Red Sox 2. The pending pick is the Yankees on GAME 2, so it
    can only settle `win` if game 2's score — not game 1's, and not either
    broadcast to both rows — reached its row.
    """
    store.upsert_games(
        pd.DataFrame(
            [
                _game(home_score=6, away_score=0)
                | {
                    "game_pk": 1,
                    "doubleheader": "S",
                    "game_number": 1,
                    "start_time_utc": "2026-08-01T17:05:00Z",
                    "winner": "Boston Red Sox",
                },
                _game()  # Final, no score: the hole
                | {
                    "game_pk": 2,
                    "doubleheader": "S",
                    "game_number": 2,
                    "start_time_utc": "2026-08-01T23:15:00Z",
                },
            ]
        )
    )
    store.append_picks(pd.DataFrame([_pick() | {"game_pk": 2}]))
    with open(fixtures_dir / DOUBLEHEADER_FIXTURE) as fh:
        payload = json.load(fh)
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: espn.parse_scoreboard(payload),
    )

    assert pipeline._espn_fallback(DAY) == 1

    games = store.load_games().set_index("game_pk")
    # Game 2 got game 2's score, from ESPN.
    assert (int(games.at[2, "home_score"]), int(games.at[2, "away_score"])) == (2, 9)
    assert games.at[2, "winner"] == "New York Yankees"
    assert games.at[2, "score_source"] == "espn"
    # Game 1 is untouched, still attributed to the MLB API.
    assert (int(games.at[1, "home_score"]), int(games.at[1, "away_score"])) == (6, 0)
    assert games.at[1, "score_source"] == "mlb"

    grade_pending()
    assert store.load_picks().iloc[0]["status"] == "win"

    # Game 1's ESPN event landed on game 1, found it already final and did
    # nothing. It is not an unmatched event, so it leaves no run note: a
    # settled doubleheader that reports an ambiguity every morning is noise
    # in a file that is committed and rendered into the daily report.
    assert store.load_run_log().empty


def test_doubleheader_is_skipped_not_guessed(health_config, monkeypatch, capsys):
    """Ambiguity still fails closed — now measured on start times.

    Rewritten from PR #69's version of this test, which asserted that ANY
    doubleheader date was skipped, because `EspnGame` carried no start time
    at all. That is no longer the behaviour: a split doubleheader is now
    split. What survives is the rule it was really defending — a match that
    cannot be decided is reported, never guessed — so the case is now the
    traditional (same-admission) doubleheader, whose two games start 30
    minutes apart on both sides, inside `ambiguity_minutes`.
    `data/games/games.csv` holds the real split pair (823501 and 823539, both
    2026-08-29 Red Sox at Yankees).
    """
    store.upsert_games(
        pd.DataFrame(
            [
                _game() | {"game_pk": 1, "game_number": 1,
                           "start_time_utc": "2026-08-01T17:05:00Z"},
                _game() | {"game_pk": 2, "game_number": 2,
                           "start_time_utc": "2026-08-01T17:35:00Z"},
            ]
        )
    )
    store.append_picks(pd.DataFrame([_pick() | {"game_pk": 1}]))
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", 3, 5, True,
                          "2026-08-01T17:05:00Z"),
            espn.EspnGame("Boston Red Sox", "New York Yankees", 1, 0, True,
                          "2026-08-01T17:35:00Z"),
        ],
    )

    assert pipeline._espn_fallback(DAY) == 0
    err = capsys.readouterr().err
    assert "ESPN match refused" in err
    assert "two ESPN events for it start within 60 minutes of each other" in err

    games = store.load_games().set_index("game_pk")
    for pk in (1, 2):
        assert pd.isna(games.at[pk, "home_score"]), "a guessed score was written"
    assert store.load_picks().iloc[0]["status"] == "pending"

    # Durable, not just stderr: an Actions log expires, and this is the only
    # trace of a hole that will not be filled. Reported once for the matchup,
    # not once per event.
    notes = store.load_run_log()
    assert list(notes["kind"]) == ["ambiguous_espn_match"]
    assert notes.iloc[0]["game_date_et"] == DAY
    assert "must not be hand-edited" in notes.iloc[0]["note"]


def test_two_rows_too_close_to_split_are_refused(health_config, monkeypatch, capsys):
    """The other half of the ambiguity rule: the ROWS are what cannot be told
    apart.

    One completed ESPN event, two stored games 30 minutes apart — the shape
    when ESPN published only one game of a traditional doubleheader. The
    event is inside the window of both rows, so `matching.nearest_start`
    refuses it rather than taking the nearer by 30 minutes.
    """
    store.upsert_games(
        pd.DataFrame(
            [
                _game() | {"game_pk": 1, "game_number": 1,
                           "start_time_utc": "2026-08-01T17:05:00Z"},
                _game() | {"game_pk": 2, "game_number": 2,
                           "start_time_utc": "2026-08-01T17:35:00Z"},
            ]
        )
    )
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", 3, 5, True,
                          "2026-08-01T17:05:00Z"),
        ],
    )

    assert pipeline._espn_fallback(DAY) == 0
    assert "ambiguous between game_pk 1 and game_pk 2" in capsys.readouterr().err
    games = store.load_games().set_index("game_pk")
    for pk in (1, 2):
        assert pd.isna(games.at[pk, "home_score"])
    assert list(store.load_run_log()["kind"]) == ["ambiguous_espn_match"]


def test_doubleheader_with_no_stored_start_times_is_still_skipped(
    health_config, monkeypatch, capsys
):
    """A gap needs both sides. A stored row with no `start_time_utc` is not a
    candidate, so a doubleheader whose rows carry no start times stays
    skipped — the matching is an extra way to decide, never a reason to
    lower the bar."""
    store.upsert_games(
        pd.DataFrame([_game() | {"game_pk": 1}, _game() | {"game_pk": 2}])
    )
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", 3, 5, True,
                          "2026-08-01T17:05:00Z"),
        ],
    )

    assert pipeline._espn_fallback(DAY) == 0
    assert "no game within the start-time window" in capsys.readouterr().err
    assert list(store.load_run_log()["kind"]) == ["ambiguous_espn_match"]


def test_two_espn_events_at_one_time_are_refused_whatever_the_order(
    health_config, monkeypatch, capsys
):
    """ESPN's feed order must never decide which row a score lands on.

    When ESPN misreports game 2's start as game 1's, the two events cannot be
    told apart, so the matchup is refused. Both orderings are asserted,
    because "the first one wins" is exactly the defect: with a greedy
    assignment, reversing these two entries moves game 2's score onto game
    1's row, and `store.settle_picks` only rewrites rows still `pending`, so
    that settlement would be permanent.
    """
    e1 = espn.EspnGame("Boston Red Sox", "New York Yankees", 6, 0, True,
                       "2026-08-01T17:05:00Z")
    e2 = espn.EspnGame("Boston Red Sox", "New York Yankees", 2, 9, True,
                       "2026-08-01T17:05:00Z")  # ESPN's time is wrong here
    for order in ([e1, e2], [e2, e1]):
        store.upsert_games(
            pd.DataFrame(
                [
                    _game() | {"game_pk": 1, "game_number": 1,
                               "start_time_utc": "2026-08-01T17:05:00Z"},
                    _game() | {"game_pk": 2, "game_number": 2,
                               "start_time_utc": "2026-08-01T23:15:00Z"},
                ]
            )
        )
        monkeypatch.setattr(
            pipeline.espn, "get_scoreboard", lambda d, session=None, o=order: o
        )

        assert pipeline._espn_fallback(DAY) == 0

        games = store.load_games().set_index("game_pk")
        for pk in (1, 2):
            assert pd.isna(games.at[pk, "home_score"]), "feed order decided a score"
    assert "two ESPN events for it start within 60 minutes" in capsys.readouterr().err
    assert list(store.load_run_log()["kind"]) == ["ambiguous_espn_match"]


def test_two_espn_events_against_one_stored_row_still_key_by_time(
    health_config, monkeypatch, capsys
):
    """The stored side being unique does not make the ESPN side unique.

    A split doubleheader announced after the last schedule refresh leaves one
    stored row and two completed ESPN events. Gating the keying on the stored
    row count alone sent this down the unique path, where the first event in
    ESPN's order filled the row — so listing game 2 first put game 2's score
    on game 1. Here game 2 is listed first and the row still gets game 1's
    score, because the match is decided by the clock, not the feed.
    """
    store.upsert_games(
        pd.DataFrame(
            [_game() | {"game_pk": 1, "game_number": 1,
                        "start_time_utc": "2026-08-01T17:05:00Z"}]
        )
    )
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", 2, 9, True,
                          "2026-08-01T23:15:00Z"),  # game 2, listed first
            espn.EspnGame("Boston Red Sox", "New York Yankees", 6, 0, True,
                          "2026-08-01T17:05:00Z"),  # game 1
        ],
    )

    assert pipeline._espn_fallback(DAY) == 1

    games = store.load_games().set_index("game_pk")
    assert (int(games.at[1, "home_score"]), int(games.at[1, "away_score"])) == (6, 0)
    # Game 2 has no stored row, so its event is reported rather than dropped.
    assert "no game within the start-time window" in capsys.readouterr().err
    assert list(store.load_run_log()["kind"]) == ["ambiguous_espn_match"]


def test_a_settled_doubleheader_reports_nothing(health_config, monkeypatch, fixtures_dir):
    """An unsplittable doubleheader with no hole is not a finding.

    The run log is committed and rendered as bullets in the daily report, so
    a date whose doubleheader is already settled must not log an ambiguity
    every time `grade` runs — several times a day, indefinitely. Only a
    matchup with something open is considered at all.
    """
    store.upsert_games(
        pd.DataFrame(
            [
                # Settled, and with no stored start times, so the events of
                # this matchup could not be keyed onto a row even if asked.
                _game(home_score=6, away_score=0) | {"game_pk": 1, "game_number": 1},
                _game(home_score=2, away_score=9) | {"game_pk": 2, "game_number": 2},
                # A different matchup, with the hole.
                _game() | {"game_pk": 3, "home_team": "Chicago Cubs",
                           "away_team": "St. Louis Cardinals"},
            ]
        )
    )
    with open(fixtures_dir / DOUBLEHEADER_FIXTURE) as fh:
        dh = espn.parse_scoreboard(json.load(fh))
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: dh
        + [
            espn.EspnGame("Chicago Cubs", "St. Louis Cardinals", 4, 1, True,
                          "2026-08-01T20:05:00Z"),
        ],
    )

    assert pipeline._espn_fallback(DAY) == 1

    games = store.load_games().set_index("game_pk")
    assert (int(games.at[3, "home_score"]), int(games.at[3, "away_score"])) == (4, 1)
    assert store.load_run_log().empty


def test_a_broken_health_yaml_costs_only_the_espn_repair(tmp_root, monkeypatch):
    """`grade` must not be able to die of a config file it never used to read.

    `_espn_match_window` raises on a health.yaml that is absent, invalid, or
    missing `grading.espn_fallback`. That load happens inside `grade`, whose
    actual job is settling picks — and in .github/workflows/mvp-morning.yml
    the grade step has no continue-on-error, so an exception escaping here
    would also skip the snapshot, splits, picks and commit steps and the
    morning would produce no data at all. The blast radius is the ESPN repair
    for that one date.

    Here the date holds both shapes: a doubleheader matchup (which needs the
    config and therefore fails) and an ordinary matchup with a hole and a
    pending pick (which must still fill and settle).
    """
    stripped = "\n".join(
        line
        for line in (REPO / "config" / "health.yaml").read_text().splitlines()
        if not line.startswith(("grading:", "  ", "    "))
        or not line.strip()
    )
    (tmp_root / "config" / "health.yaml").write_text(
        yaml.safe_dump({"doctor": yaml.safe_load(stripped or "{}").get("doctor", {})})
    )
    assert "grading" not in yaml.safe_load(
        (tmp_root / "config" / "health.yaml").read_text()
    )

    store.upsert_games(
        pd.DataFrame(
            [
                _game() | {"game_pk": 1, "game_number": 1,
                           "start_time_utc": "2026-08-01T17:05:00Z"},
                _game() | {"game_pk": 2, "game_number": 2,
                           "start_time_utc": "2026-08-01T23:15:00Z"},
                _game() | {"game_pk": 3, "home_team": "Chicago Cubs",
                           "away_team": "St. Louis Cardinals",
                           "start_time_utc": "2026-08-01T20:05:00Z"},
            ]
        )
    )
    store.append_picks(
        pd.DataFrame([_pick("p3", "St. Louis Cardinals") | {"game_pk": 3}])
    )
    monkeypatch.setattr(pipeline, "_refresh_games", lambda d: [])
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", 6, 0, True,
                          "2026-08-01T17:05:00Z"),
            espn.EspnGame("Boston Red Sox", "New York Yankees", 2, 9, True,
                          "2026-08-01T23:15:00Z"),
            espn.EspnGame("Chicago Cubs", "St. Louis Cardinals", 1, 4, True,
                          "2026-08-01T20:05:00Z"),
        ],
    )

    pipeline.cmd_grade(DAY)

    games = store.load_games().set_index("game_pk")
    # The ordinary matchup is unique on both sides, so it never reads the
    # config: it filled, and its pick settled.
    assert (int(games.at[3, "home_score"]), int(games.at[3, "away_score"])) == (1, 4)
    assert store.load_picks().iloc[0]["status"] == "win"
    # The doubleheader is the only casualty.
    assert pd.isna(games.at[1, "home_score"])
    assert pd.isna(games.at[2, "home_score"])


def test_espn_match_window_comes_from_health_yaml():
    """The tolerances are config, not engine constants — and they are NOT in
    config/strategy.yaml or a config/strategies/*.yaml, where every
    non-excluded key is hashed into every pick's `config_hash`."""
    window_hours, ambiguity_minutes = pipeline._espn_match_window()
    assert (window_hours, ambiguity_minutes) == (4.0, 60.0)

    raw = yaml.safe_load((paths.config_dir() / "health.yaml").read_text())
    assert raw["grading"]["espn_fallback"] == {
        "window_hours": 4,
        "ambiguity_minutes": 60,
    }
    for path in [paths.config_dir() / "strategy.yaml"] + sorted(
        (paths.config_dir() / "strategies").glob("*.yaml")
    ):
        assert "espn_fallback" not in path.read_text(), (
            f"{path.name} is hashed into every pick; a grading tolerance there "
            "would move every strategy's config_hash"
        )


def test_an_unmapped_final_with_no_score_leaves_a_run_note(
    tmp_root, monkeypatch, fixtures_dir, capsys
):
    """The shape that stranded 823490, when `detailedState` carries a head
    `_CALLED_OFF` does not know: the row is about to be stored Final with no
    score, so say so durably instead of storing another silent dead end."""
    from dataclasses import replace

    from panthera_mvp.clients import mlb

    with open(fixtures_dir / CANCELLED_FIXTURE) as fh:
        payload = json.load(fh)
    # An unknown terminal state: not in _CALLED_OFF, so it stores as Final.
    payload["dates"][0]["games"][0]["status"]["detailedState"] = "Forfeited"
    path = tmp_root / "mlb_forfeited.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("PANTHERA_MLB_FIXTURE", str(path))

    pipeline._refresh_games("2026-09-27")

    assert mlb.stored_status(
        replace(
            mlb.parse_schedule(payload)[0], detailed_state="Forfeited", status="Final"
        )
    ) == "Final"
    assert "is not a known called-off state" in capsys.readouterr().err
    notes = store.load_run_log()
    assert list(notes["kind"]) == ["unmapped_final_no_score"]
    assert "_CALLED_OFF" in notes.iloc[0]["note"]

    # A game stuck in an unmapped state is re-examined by every refresh —
    # several times a day, indefinitely — and each note renders as a bullet in
    # the daily report, so an identical note must not be appended again.
    pipeline._refresh_games("2026-09-27")
    pipeline._refresh_games("2026-09-27")
    assert len(store.load_run_log()) == 1


def test_a_second_matchup_on_the_same_date_still_fills(tmp_root, espn_final):
    """The refusal is keyed on the matchup, not on the date: a different
    matchup on the same date is unambiguous and still gets filled.

    Renamed from `test_a_lone_game_on_a_doubleheader_date_still_fills`: the
    two rows here are two different matchups, which is not a doubleheader, so
    the old name described a case the body never built.
    """
    store.upsert_games(
        pd.DataFrame(
            [
                _game() | {"game_pk": 1},
                _game()
                | {
                    "game_pk": 2,
                    "home_team": "Chicago Cubs",
                    "away_team": "St. Louis Cardinals",
                },
            ]
        )
    )

    assert pipeline._espn_fallback(DAY) == 1

    games = store.load_games().set_index("game_pk")
    assert (int(games.at[1, "home_score"]), int(games.at[1, "away_score"])) == (3, 5)
    assert pd.isna(games.at[2, "home_score"])  # no ESPN event for that matchup


def test_upsert_does_not_freeze_an_in_progress_row(tmp_root):
    """The no-blank guard keys on a COMPLETE final, not on "has a score": a
    Live row carries a score too, and freezing those would discard the very
    correction saying the game was called off mid-play."""
    store.upsert_games(pd.DataFrame([_game(status="Live", home_score=0, away_score=0)]))

    store.upsert_games(pd.DataFrame([_game(status="Suspended")]))

    assert store.load_games().iloc[0]["status"] == "Suspended"
