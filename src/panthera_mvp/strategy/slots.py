"""Slot assignment from the shape of a day's schedule (doc §2, P1 05:23-13:44,
103:57-108:38).

The live engine (daytype.py::slot_type) treats every game on a P day as a P
slot and every game on a V day as a V slot. The source strategy does not: it
walks the day's distinct start times in order and flips slots at specific
points. Concretely, for one calendar ET day:

  1. Group games by distinct ET start time -> ordered list of slots. Each
     slot has a "base type": the day type (P or V), or — on a hybrid
     Wednesday — P before hybrid_boundary_hour_et and V at/after it (doc §2;
     P1 10:34, presenter works in CST, so the ET boundary is +1h).
  2. The FIRST slot of the WHOLE DAY is the INVERSE of its base type.
  3. Every other slot inherits its base type...
  4. ...EXCEPT a slot with 2+ games at the same start time, which flips to
     the inverse for that slot only.
  5. The LAST slot of the WHOLE DAY is the INVERSE of the type the previous
     slot ended up with (a "chunk" = a maximal run of same-typed slots).

On a hybrid day the halftime boundary (rule 1) is *only* a base-type change —
it does not itself trigger an inversion. P1's live walkthrough confirms this
explicitly: the first post-halftime slot inherits Vegas directly ("we got
Vegas at 5:10... all of that's gonna be Vegas"), it is NOT re-inverted the
way the whole day's first slot is. Only the day's global first and last
slots get the rule-2/rule-5 treatment.
"""

from __future__ import annotations

from datetime import datetime

from ..timeutil import to_et

INVERSE = {"P": "V", "V": "P"}


def _base_type(start_et: datetime, day_type: str, hybrid_boundary_hour_et: int) -> str:
    if day_type != "HYBRID":
        return day_type
    return "P" if start_et.hour < hybrid_boundary_hour_et else "V"


def assign_slots(
    games: list[tuple[int, datetime]], day_type: str, hybrid_boundary_hour_et: int
) -> dict[int, str]:
    """games: [(game_pk, start_utc)] for ALL games on one ET calendar day.
    day_type: "P", "V", or "HYBRID". Returns {game_pk: "P"|"V"}."""
    if not games:
        return {}

    et_games = sorted(
        ((pk, to_et(start)) for pk, start in games), key=lambda gt: gt[1]
    )

    # Group into ordered slots by distinct start time; each slot's base type
    # comes from the day type (constant) or the hybrid half its time falls in.
    slot_times: list[datetime] = []
    slot_games: list[list[int]] = []
    slot_base: list[str] = []
    for pk, start in et_games:
        base = _base_type(start, day_type, hybrid_boundary_hour_et)
        if not slot_times or start != slot_times[-1]:
            slot_times.append(start)
            slot_games.append([pk])
            slot_base.append(base)
        else:
            slot_games[-1].append(pk)

    n = len(slot_games)
    slot_type: list[str] = list(slot_base)
    slot_type[0] = INVERSE[slot_base[0]]  # rule 2: whole-day first slot inverse
    for i in range(1, n):
        # rule 3/4: inherits this slot's own base type, except a "double slot"
        # (2+ games sharing a start time), which flips for that slot only.
        slot_type[i] = INVERSE[slot_base[i]] if len(slot_games[i]) >= 2 else slot_base[i]
    if n > 1:
        # rule 5: whole-day last slot inverse of the previous slot's type.
        slot_type[n - 1] = INVERSE[slot_type[n - 2]]

    out: dict[int, str] = {}
    for pks, stype in zip(slot_games, slot_type, strict=True):
        for pk in pks:
            out[pk] = stype
    return out
