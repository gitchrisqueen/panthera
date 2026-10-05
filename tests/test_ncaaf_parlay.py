"""cfb_spread_total_parlay: signals S1-S6, conflict/same-game rules, best
available pricing, ticket building and day guards, the decision window, and
prep -> picks -> grade -> report end to end on the synthetic NCAAF fixtures.
"""

import json
import shutil
from datetime import UTC, datetime

import pandas as pd
import pytest
import yaml

from panthera_mvp.ncaaf import parlay, store

STRATEGY_YAML = "config/ncaaf_strategies/cfb_spread_total_parlay.yaml"
NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)


@pytest.fixture
def scfg():
    from conftest import REPO

    with open(REPO / STRATEGY_YAML) as fh:
        return yaml.safe_load(fh)


def game(eid, home, away, start, **kw):
    row = {
        "event_id": eid, "game_date_et": start[:10], "start_time_utc": start,
        "home_team": home, "away_team": away, "home_rank": None, "away_rank": None,
        "neutral_site": False, "conference_game": True, "venue": f"{home} Stadium",
        "indoor": False, "status": "Scheduled", "home_score": None, "away_score": None,
        "home_school": home.split()[0], "away_school": away.split()[0],
    }
    return row | kw


def line_rows(eid, home, away, ts, spread=None, total=None, book="dk", price=-110):
    """Odds rows for one book: spread is the home point."""
    rows = []
    base = {"snapshot_ts_utc": ts, "event_id": eid, "home_team": home, "away_team": away,
            "bookmaker": book, "price_american": price,
            "price_decimal": round(1 + 100 / abs(price), 4) if price < 0 else 1 + price / 100}
    if spread is not None:
        rows += [base | {"market": "spreads", "outcome": home, "point": spread},
                 base | {"market": "spreads", "outcome": away, "point": -spread}]
    if total is not None:
        rows += [base | {"market": "totals", "outcome": "Over", "point": total},
                 base | {"market": "totals", "outcome": "Under", "point": total}]
    return rows


OPEN, DEC = "2026-10-01T12:00:00Z", "2026-10-03T15:00:00Z"


def view(spread_open=-3.0, spread_now=-3.0, total_open=50.0, total_now=50.0, **kw):
    games = pd.DataFrame([game("1", "Home Hawks", "Away Owls", "2026-10-03T19:00:00Z", **kw)])
    lines = pd.DataFrame(
        line_rows("1", "Home Hawks", "Away Owls", OPEN, spread_open, total_open)
        + line_rows("1", "Home Hawks", "Away Owls", DEC, spread_now, total_now)
    )
    return parlay.build_views(games, lines, DEC)[0]


def sigs(v, scfg, schedules=None, sp=None, wind=None):
    return [(s.signal_id, s.market, s.side)
            for s in parlay.game_signals(v, scfg, schedules or {}, sp or {}, wind or {})]


# --- views ------------------------------------------------------------------------


def test_build_views_consensus_and_orientation():
    games = pd.DataFrame([game("9", "Hawaii Rainbow Warriors", "San Jose State Spartans",
                               "2026-10-03T19:00:00Z", neutral_site=True)])
    # The odds feed lists the neutral-site game the other way round.
    rows = []
    for book, pt in (("a", -3.0), ("b", -3.5), ("c", -2.5)):
        rows += line_rows("9", "San Jose State Spartans", "Hawaii Rainbow Warriors", DEC,
                          spread=pt, total=55.0, book=book)
    v = parlay.build_views(games, pd.DataFrame(rows), DEC)[0]
    assert v.odds_home == "Hawaii Rainbow Warriors"
    assert v.spread_now == 3.0  # median SJSU -3 -> Hawaii (ESPN home) +3
    assert v.spread_open == 3.0 and v.total_now == 55.0


def test_open_is_first_snapshot_and_later_rows_are_ignored():
    games = pd.DataFrame([game("1", "Home Hawks", "Away Owls", "2026-10-03T19:00:00Z")])
    lines = pd.DataFrame(
        line_rows("1", "Home Hawks", "Away Owls", OPEN, -3.0, 50.0)
        + line_rows("1", "Home Hawks", "Away Owls", DEC, -5.0, 47.0)
        + line_rows("1", "Home Hawks", "Away Owls", "2026-10-03T23:00:00Z", -9.0, 40.0)
    )
    v = parlay.build_views(games, lines, DEC)[0]
    assert (v.spread_open, v.spread_now, v.total_open, v.total_now) == (-3.0, -5.0, 50.0, 47.0)


# --- signals ------------------------------------------------------------------------


def test_s1_s2_line_moves(scfg):
    assert sigs(view(spread_open=-3, spread_now=-4.5), scfg) == [("S1", "spread", "home")]
    assert sigs(view(spread_open=-3, spread_now=-1.5), scfg) == [("S1", "spread", "away")]
    assert sigs(view(spread_open=-3, spread_now=-4), scfg) == []  # 1 point < 1.5
    assert sigs(view(total_open=50, total_now=52), scfg) == [("S2", "total", "over")]
    assert sigs(view(total_open=50, total_now=48.5), scfg) == []


def test_s3_letdown_and_s4_look_ahead(scfg):
    v = view(spread_open=-12, spread_now=-12)
    prior = pd.DataFrame([
        game("p", "Home Hawks", "Ranked Rams", "2026-09-26T19:00:00Z", status="Final",
             home_score=30, away_score=20, away_rank=8),
    ])
    sched = parlay.team_schedules(prior)
    assert sigs(v, scfg, schedules=sched) == [("S3", "spread", "away")]

    lost = prior.assign(home_score=10)
    assert sigs(v, scfg, schedules=parlay.team_schedules(lost)) == []
    small_fav = view(spread_open=-9.5, spread_now=-9.5)
    assert sigs(small_fav, scfg, schedules=sched) == []

    nxt = pd.DataFrame([game("n", "Ranked Rams", "Away Owls", "2026-10-10T19:00:00Z",
                             home_rank=5)])
    dog_fav = view(spread_open=11, spread_now=11)  # Away Owls favored by 11
    assert sigs(dog_fav, scfg, schedules=parlay.team_schedules(nxt)) == [
        ("S4", "spread", "home")
    ]


def test_s5_wind_needs_an_outdoor_venue(scfg):
    assert sigs(view(), scfg, wind={"1": 18.0}) == [("S5", "total", "under")]
    assert sigs(view(), scfg, wind={"1": 12.0}) == []
    assert sigs(view(indoor=True), scfg, wind={"1": 25.0}) == []
    assert sigs(view(indoor=None), scfg, wind={"1": 25.0}) == []


def test_s6_sp_plus_edge(scfg):
    sp = {"home": 10.0, "away": 5.0}  # +5 +2.5 HFA = home by 7.5 vs -3 -> edge 4.5
    assert sigs(view(), scfg, sp=sp) == [("S6", "spread", "home")]
    assert sigs(view(neutral_site=True), scfg, sp=sp) == []  # 5.0 - 3 = 2
    assert sigs(view(spread_open=-14, spread_now=-14), scfg, sp=sp) == [
        ("S6", "spread", "away")
    ]


# --- legs ------------------------------------------------------------------------


def test_conflict_skips_the_game(scfg):
    v = view(spread_open=-3, spread_now=-5)
    s = [parlay.Signal("S1", "spread", "home", ""), parlay.Signal("S6", "spread", "away", "")]
    leg, note = parlay.qualify(v, s, scfg)
    assert leg is None and "conflicting spread" in note


def test_one_leg_per_game_more_signals_then_spread(scfg):
    v = view()
    tie = [parlay.Signal("S2", "total", "over", ""), parlay.Signal("S6", "spread", "home", "")]
    assert parlay.qualify(v, tie, scfg)[0].market == "spread"
    more = tie + [parlay.Signal("S5", "total", "over", "")]
    leg = parlay.qualify(v, more, scfg)[0]
    assert (leg.market, leg.selection, leg.signal_ids) == ("total", "Over", "S2+S5")


def test_best_available_price():
    games = pd.DataFrame([game("1", "Home Hawks", "Away Owls", "2026-10-03T19:00:00Z")])
    rows = (line_rows("1", "Home Hawks", "Away Owls", DEC, -6.5, 52.5, book="a")
            + line_rows("1", "Home Hawks", "Away Owls", DEC, -6.0, 51.5, book="b", price=-115)
            + line_rows("1", "Home Hawks", "Away Owls", DEC, -6.0, 52.5, book="c", price=-105))
    v = parlay.build_views(games, pd.DataFrame(rows), DEC)[0]
    home = parlay.best_price(v, "spread", "home")
    assert (home["point"], home["bookmaker"]) == (-6.0, "c")  # fewer points, then price
    assert parlay.best_price(v, "spread", "away")["point"] == 6.5
    assert parlay.best_price(v, "total", "under")["point"] == 52.5
    assert parlay.best_price(v, "total", "over")["point"] == 51.5


# --- the day ------------------------------------------------------------------------


def slate(n, start_hours=(19, 20, 21, 22)):
    games, rows = [], []
    for i in range(n):
        eid, home, away = str(i), f"Home{i} Hawks", f"Away{i} Owls"
        start = f"2026-10-03T{start_hours[i]:02d}:00:00Z"
        games.append(game(eid, home, away, start))
        rows += line_rows(eid, home, away, OPEN, -3.0, 50.0)
        rows += line_rows(eid, home, away, DEC, -5.0, 50.0)  # S1 home on every game
    return parlay.build_views(pd.DataFrame(games), pd.DataFrame(rows), DEC)


def test_ticket_takes_top_three(scfg):
    views = slate(4)
    sp = {"home3": 20.0, "away3": 0.0}  # game 3 gets S1 + S6
    d = parlay.decide_day(views, scfg, NOW, {}, sp, {})
    assert d.status == "ticket" and len(d.qualifiers) == 4
    assert [lg.event_id for lg in d.ticket_legs] == ["3", "0", "1"]
    assert d.price_decimal == pytest.approx(1.9091 ** 3, abs=1e-3)
    assert d.price_american == 596 and d.in_band is False  # target band, not a filter


def test_too_few_legs_and_min_lead(scfg):
    d = parlay.decide_day(slate(2), scfg, NOW, {}, {}, {})
    assert d.status == "no_ticket" and len(d.qualifiers) == 2
    late = datetime(2026, 10, 3, 18, 50, tzinfo=UTC)  # game 0 is 10 min away
    d = parlay.decide_day(slate(4), scfg, late, {}, {}, {})
    assert [lg.event_id for lg in d.ticket_legs] == ["1", "2", "3"]


def test_day_guards(scfg):
    assert parlay.decide_day(slate(4), scfg, NOW, {}, {}, {}, tickets_today=1).status == "skip"
    d = parlay.decide_day(slate(4), scfg, NOW, {}, {}, {}, lost_yesterday=True)
    assert d.status == "skip" and "lost" in d.reason


def test_prior_day_lost():
    tickets = pd.DataFrame([{"ticket_id": "t", "strategy_id": "s", "game_date_et": "2026-10-02",
                             "status": "pending"}])
    legs = pd.DataFrame([{"ticket_id": "t", "status": "win"}, {"ticket_id": "t", "status": "loss"}])
    assert parlay.prior_day_lost(tickets, legs, "s", "2026-10-03")  # a leg already lost
    assert not parlay.prior_day_lost(tickets, legs.assign(status="pending"), "s", "2026-10-03")
    assert not parlay.prior_day_lost(tickets, legs, "s", "2026-10-04")
    assert parlay.prior_day_lost(tickets.assign(status="loss"), legs, "s", "2026-10-03")


def test_decision_window(scfg):
    from panthera_mvp.ncaaf.picks import in_decision_window

    cfg = {"schedule": {"decision_window_halfwidth_minutes": 30}}
    games = pd.DataFrame([game("1", "Home Hawks", "Away Owls", "2026-10-03T16:00:00Z"),
                          game("2", "H2 Hawks", "A2 Owls", "2026-10-03T23:00:00Z")])
    at = lambda h, m: datetime(2026, 10, 3, h, m, tzinfo=UTC)  # noqa: E731
    assert in_decision_window(games, "2026-10-03", at(15, 0), scfg, cfg)[0]  # 60 min
    assert in_decision_window(games, "2026-10-03", at(14, 31), scfg, cfg)[0]  # 89
    assert not in_decision_window(games, "2026-10-03", at(14, 30), scfg, cfg)[0]  # 90
    assert not in_decision_window(games, "2026-10-03", at(15, 31), scfg, cfg)[0]  # 29
    # Game 1 has started: the next kickoff (23:00) drives the window.
    assert in_decision_window(games, "2026-10-03", at(22, 0), scfg, cfg)[0]
    assert not in_decision_window(games, "2026-10-04", at(15, 0), scfg, cfg)[0]


# --- end to end ---------------------------------------------------------------------


@pytest.fixture
def cfb_strategy_root(tmp_path, monkeypatch, fixtures_dir):
    from conftest import REPO

    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config" / "ncaaf_strategies").mkdir(parents=True)
    shutil.copy(REPO / "config/ncaaf.yaml", tmp_path / "config/ncaaf.yaml")
    shutil.copy(REPO / STRATEGY_YAML, tmp_path / STRATEGY_YAML)
    cfb = fixtures_dir / "ncaaf"
    monkeypatch.setenv("PANTHERA_NCAAF_ESPN_FIXTURE", str(cfb / "espn_cfb_scoreboard.json"))
    monkeypatch.setenv("PANTHERA_NCAAF_ODDS_FIXTURE", str(cfb / "odds_ncaaf_snapshot.json"))
    monkeypatch.delenv("CFBD_API_KEY", raising=False)
    return tmp_path


def test_prep_picks_grade_report_end_to_end(cfb_strategy_root, monkeypatch):
    """The fixture slate is the author's 2026-10-03 card. With SP+ (synthetic
    ratings) favoring BYU, Miami and Texas Tech by 4+ over the spread, the
    engine builds the author's actual ticket and the synthetic finals grade it
    a win. Prep and picks share one fixture snapshot, so no line moves."""
    from panthera_mvp.clients import cfbd
    from panthera_mvp.ncaaf import picks, pipeline
    from panthera_mvp.ncaaf.report import write_report

    monkeypatch.setattr(pipeline, "_today_et", lambda: "2026-10-03")
    monkeypatch.setattr(picks, "_now", lambda: datetime(2026, 10, 3, 18, 0, tzinfo=UTC))
    picks.cmd_prep(odds_mode="dry_run")
    # The fixture games are stored Final, so prep sees nothing upcoming and
    # skips its paid open snapshot; take it directly instead.
    assert store.load_lines().empty
    pipeline.cmd_snapshot("open", dry_run=True)

    season = int(store.load_games()["season"].dropna().iloc[0])
    sp = [{"year": season, "team": t, "rating": r} for t, r in
          (("BYU", 20.0), ("TCU", 0.0), ("Miami", 30.0), ("Clemson", 5.0),
           ("Texas Tech", 25.0), ("Colorado", 2.0))]
    path = cfbd.cache_path("ratings/sp", {"year": season})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sp))

    # --auto outside the decision window (the fixture games are stored Final,
    # so nothing is upcoming): no snapshot, no writes.
    n_lines = len(store.load_lines())
    picks.cmd_picks(auto=True, dry_run=True)
    assert store.load_decisions().empty and len(store.load_lines()) == n_lines

    picks.cmd_picks(dry_run=True)
    labels = set(store.load_lines()["snapshot_label"])
    assert labels == {"open", "decision-2026-10-03"}
    t = store.load_tickets()
    assert len(t) == 1 and t.iloc[0]["n_legs"] == 3
    legs = store.load_legs().sort_values("leg_no")
    assert list(legs["selection"]) == ["Miami Hurricanes", "BYU Cougars", "Texas Tech Red Raiders"]
    assert list(legs["line"]) == [-15.5, -6.5, -13.5]
    q = store.load_qualifiers()
    assert set(q["signal_ids"]) == {"S6"} and q["on_ticket"].all()
    d = store.load_decisions()
    assert list(d["status"]) == ["ticket"]

    picks.cmd_picks(dry_run=True)  # already decided: no-op
    assert len(store.load_decisions()) == 1 and len(store.load_tickets()) == 1

    pipeline.cmd_grade()
    t = store.load_tickets().iloc[0]
    assert t["status"] == "win" and t["profit"] == pytest.approx(595.8, abs=0.1)
    assert set(store.load_qualifiers()["status"]) == {"win"}

    text = open(write_report()).read()
    assert "## cfb_spread_total_parlay" in text
    assert "| S6 | 3 | 3-0-0 | 100.0% |" in text


def test_each_day_gets_its_own_decision_rows(cfb_strategy_root, monkeypatch):
    """lines.csv dedupes on (event date, label, ...): a second day's decision
    snapshot must still store rows for games an earlier one already priced."""
    from panthera_mvp.ncaaf import pipeline

    monkeypatch.setattr(pipeline, "_today_et", lambda: "2026-10-01")
    pipeline.cmd_snapshot("decision-2026-10-01", dry_run=True)
    n = len(store.load_lines())
    pipeline.cmd_snapshot("decision-2026-10-03", dry_run=True)
    assert len(store.load_lines()) == 2 * n


# --- registration ---------------------------------------------------------------------


def test_registered_hash_is_in_lineage():
    """A behavioral edit to the YAML changes config_hash; the registered id
    must then move to a new strategy id, not silently extend its lineage."""
    from panthera_mvp.config import config_hash
    from panthera_mvp.ncaaf.config import load_ncaaf_strategies

    cfg = load_ncaaf_strategies()["cfb_spread_total_parlay"]
    assert config_hash(cfg) in cfg["strategy"]["hash_lineage"]
    assert cfg["strategy"]["kind"] == "forward_test" and cfg["verdict"] is None


def test_ncaaf_strategy_loader_rejects_bad_files(tmp_path, monkeypatch):
    from panthera_mvp.config import StrategyConfigError
    from panthera_mvp.ncaaf.config import load_ncaaf_strategies

    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    sdir = tmp_path / "config" / "ncaaf_strategies"
    sdir.mkdir(parents=True)
    (sdir / "x.yaml").write_text("strategy: {id: y, engine: cfb_parlay}\n")
    with pytest.raises(StrategyConfigError, match="filename stem"):
        load_ncaaf_strategies()
    (sdir / "x.yaml").write_text("strategy: {id: x, engine: pv_rules}\n")
    with pytest.raises(StrategyConfigError, match="unknown NCAAF engine"):
        load_ncaaf_strategies()
