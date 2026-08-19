from datetime import UTC, datetime

from panthera_mvp.strategy.daytype import day_type, slot_type


def test_day_type_uses_map(cfg):
    # 2026-08-01 is a Saturday -> V in the (corrected) default map.
    assert day_type(datetime(2026, 8, 1).date(), cfg) == "V"
    # 2026-08-03 is a Monday -> P.
    assert day_type(datetime(2026, 8, 3).date(), cfg) == "P"
    # 2026-08-05 is a Wednesday -> HYBRID.
    assert day_type(datetime(2026, 8, 5).date(), cfg) == "HYBRID"


def test_slot_inherits_day_type_on_plain_days(cfg):
    # Monday 7:05 PM ET start = 23:05 UTC (EDT).
    start = datetime(2026, 8, 3, 23, 5, tzinfo=UTC)
    assert slot_type(start, cfg) == "P"


def test_hybrid_wednesday_boundary(cfg):
    # Corrected boundary is 5pm CST = 18:00 ET (P1 10:34; presenter works in
    # CST throughout, e.g. writing a 12:20 PM ET game as "11:20 AM").
    # Wednesday 1:05 PM ET (17:05 UTC in August) -> before 18:00 ET -> P slot.
    afternoon = datetime(2026, 8, 5, 17, 5, tzinfo=UTC)
    assert slot_type(afternoon, cfg) == "P"
    # Wednesday 7:05 PM ET (23:05 UTC) -> at/after 18:00 ET -> V slot.
    evening = datetime(2026, 8, 5, 23, 5, tzinfo=UTC)
    assert slot_type(evening, cfg) == "V"
    # Exactly 6:00 PM ET is a Vegas slot (boundary is inclusive).
    boundary = datetime(2026, 8, 5, 22, 0, tzinfo=UTC)
    assert slot_type(boundary, cfg) == "V"


def test_late_night_game_belongs_to_et_date(cfg):
    # Sunday 10:40 PM ET start = Monday 02:40 UTC; ET date must be Sunday.
    start = datetime(2026, 8, 3, 2, 40, tzinfo=UTC)
    assert slot_type(start, cfg) == "V"  # Sunday=V, not Monday=P
