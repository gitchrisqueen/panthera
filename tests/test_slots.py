"""Golden-example tests for strategy/slots.py, reproducing the schedule
walkthroughs the presenter narrates live in Part 1 of the transcript
(timestamps below cite notes/GMT20240619-014815/transcript.txt)."""

from datetime import UTC, datetime, timedelta, timezone

from panthera_mvp.strategy.slots import assign_slots

ET = timezone(timedelta(hours=-4))  # EDT, matches the June 2024 recordings


def _et(h, m=0):
    return datetime(2024, 6, 18, h, m, tzinfo=ET)


def _utc(h, m=0):
    return _et(h, m).astimezone(UTC)


def test_public_day_walkthrough():
    """P1 05:23-08:11: public day. First slot inverse (V); a lone-game middle
    slot stays P; the one double-game slot flips to V; the tail (no more
    doubles) is P; the day's last slot inverts the previous (P) chunk to V."""
    games = [
        (1, _utc(16, 10)),  # first slot -> V (inverse of P)
        (2, _utc(17, 5)),  # solo -> P
        (3, _utc(17, 40)),  # double -> V
        (4, _utc(17, 40)),  # double -> V
        (5, _utc(18, 10)),  # solo -> P
        (6, _utc(19, 5)),  # solo, but LAST slot -> inverse of prev (P) -> V
    ]
    got = assign_slots(games, "P", hybrid_boundary_hour_et=18)
    assert got == {1: "V", 2: "P", 3: "V", 4: "V", 5: "P", 6: "V"}


def test_vegas_day_walkthrough():
    """P1 08:38-09:48: Vegas day. First slot inverse (P); a run of solo slots
    stays V; the double at 6:40 flips to P; reverts to V; last slot inverts
    the previous (V) chunk to P."""
    games = [
        (1, _utc(13, 5)),  # first slot -> P (inverse of V)
        (2, _utc(15, 10)),  # solo -> V
        (3, _utc(18, 40)),  # double -> P
        (4, _utc(18, 40)),  # double -> P
        (5, _utc(19, 10)),  # solo -> V
        (6, _utc(20, 5)),  # last slot -> inverse of prev (V) -> P
    ]
    got = assign_slots(games, "V", hybrid_boundary_hour_et=18)
    assert got == {1: "P", 2: "V", 3: "P", 4: "P", 5: "V", 6: "P"}


def test_hybrid_day_full_walkthrough():
    """P1 103:57-108:38: the live June 18 hybrid build-out. First slot of the
    WHOLE day (11:20 ET, pre-halftime => public base) inverts to Vegas; the
    rest of the pre-halftime half (no doubles) stays Public; the first slot
    after halftime (Vegas base) is NOT re-inverted -- it inherits Vegas
    directly, exactly as the presenter narrates ("we got Vegas at 5:10...
    all of that's gonna be Vegas"); a double slot flips to Public; the day's
    LAST slot inverts the previous (Vegas) chunk to Public."""
    games = [
        (1, _utc(11, 20)),  # day's first slot, pre-boundary base P -> V
        (2, _utc(11, 40)),  # solo, base P -> P
        (3, _utc(14, 15)),  # solo, base P -> P
        (4, _utc(18, 10)),  # solo, base V -> V (post-boundary base, no invert)
        (5, _utc(18, 40)),  # double, base V -> P
        (6, _utc(18, 40)),  # double, base V -> P
        (7, _utc(19, 10)),  # solo, base V -> V
        (8, _utc(21, 5)),  # day's LAST slot -> inverse of prev (V) -> P
    ]
    got = assign_slots(games, "HYBRID", hybrid_boundary_hour_et=18)
    assert got == {1: "V", 2: "P", 3: "P", 4: "V", 5: "P", 6: "P", 7: "V", 8: "P"}


def test_hybrid_boundary_is_18_et_not_16():
    """5pm CST (the presenter's stated cutoff) = 6pm ET, not the live repo's
    16:00 ET default. A 17:30 ET game must fall in the pre-halftime (Public
    base) half."""
    games = [(1, _utc(12, 0)), (2, _utc(17, 30))]
    got = assign_slots(games, "HYBRID", hybrid_boundary_hour_et=18)
    # Both pre-boundary -> both base P; first inverts to V, last inverts prev (V) -> P.
    assert got == {1: "V", 2: "P"}


def test_single_game_day_has_no_slots_to_invert():
    games = [(1, _utc(19, 5))]
    assert assign_slots(games, "P", hybrid_boundary_hour_et=18) == {1: "V"}


def test_empty_day():
    assert assign_slots([], "V", hybrid_boundary_hour_et=18) == {}
