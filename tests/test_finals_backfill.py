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

import pandas as pd
import pytest

from panthera_mvp import paths, pipeline, store
from panthera_mvp.clients import espn
from panthera_mvp.grading import grade_pending

DAY = "2026-08-01"
PK = 776001


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
# reason "Rain" (tests/fixtures/mlb_schedule_cancelled.json is that live
# response). ESPN has no final for it either. The row was unsettleable because
# the pipeline stored `abstractGameState`, which cannot express "called off",
# so grading could neither settle it nor reach its void branch.


CANCELLED_FIXTURE = "mlb_schedule_cancelled.json"


def test_stored_status_reads_called_off_from_detailed_state(fixtures_dir):
    """The mapping, per detailedState head. `abstractGameState` is "Final" for
    every row here, so anything reading it alone sees a settled game."""
    import json
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


def test_doubleheader_is_skipped_not_guessed(tmp_root, monkeypatch, capsys):
    """(date, home_team, away_team) is not unique for a split doubleheader,
    and `EspnGame` carries no start time to split them.

    Writing anyway broadcast one game's score to both rows, and
    `grade_pending` then settled a pick from whichever score happened to land
    — permanently. `data/games/games.csv` holds real examples (823501 and
    823539, both 2026-08-29 Yankees vs Red Sox).
    """
    store.upsert_games(
        pd.DataFrame(
            [
                _game() | {"game_pk": 1, "game_number": 1},
                _game() | {"game_pk": 2, "game_number": 2},
            ]
        )
    )
    store.append_picks(pd.DataFrame([_pick() | {"game_pk": 1}]))
    monkeypatch.setattr(
        pipeline.espn,
        "get_scoreboard",
        lambda d, session=None: [
            espn.EspnGame("Boston Red Sox", "New York Yankees", 3, 5, True),
            espn.EspnGame("Boston Red Sox", "New York Yankees", 1, 0, True),
        ],
    )

    assert pipeline._espn_fallback(DAY) == 0
    assert "ambiguous ESPN match" in capsys.readouterr().err

    games = store.load_games().set_index("game_pk")
    for pk in (1, 2):
        assert pd.isna(games.at[pk, "home_score"]), "a guessed score was written"
    assert store.load_picks().iloc[0]["status"] == "pending"

    # Durable, not just stderr: an Actions log expires, and this is the only
    # trace of a hole that will not be filled.
    notes = store.load_run_log()
    assert list(notes["kind"]) == ["ambiguous_espn_match"]
    assert notes.iloc[0]["game_date_et"] == DAY
    assert "must not be hand-edited" in notes.iloc[0]["note"]


def test_an_unmapped_final_with_no_score_leaves_a_run_note(
    tmp_root, monkeypatch, fixtures_dir, capsys
):
    """The shape that stranded 823490, when `detailedState` carries a head
    `_CALLED_OFF` does not know: the row is about to be stored Final with no
    score, so say so durably instead of storing another silent dead end."""
    import json
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


def test_a_lone_game_on_a_doubleheader_date_still_fills(tmp_root, espn_final):
    """The skip is keyed on the matchup, not on the date: a different matchup
    on the same date is unambiguous and still gets filled."""
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
