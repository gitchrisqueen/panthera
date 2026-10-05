"""NCAAF plumbing: ESPN/CFBD/Open-Meteo parsers, odds<->ESPN matching, leg
and parlay grading, and the snapshot -> ticket -> grade path end to end.

The fixtures under tests/fixtures/ncaaf/ are SYNTHETIC: they model the author's
2026-10-03 worked example (BYU -6.5, Miami -15.5, Texas Tech -13.5,
"~+600", reported as a win) with invented final scores that cover all three
legs, plus a neutral-site home/away swap, a postponed game and an FCS event
with no ESPN FBS match. Replace with recorded payloads from the
ncaaf-capture workflow once it has run.
"""

import json
import shutil

import pytest

from panthera_mvp.clients import cfbd, espn_cfb, odds, weather
from panthera_mvp.ncaaf import grading, matching, store

REPO_CONFIG = "config/ncaaf.yaml"


@pytest.fixture
def cfb_dir(fixtures_dir):
    return fixtures_dir / "ncaaf"


@pytest.fixture
def cfb_games(cfb_dir):
    with open(cfb_dir / "espn_cfb_scoreboard.json") as fh:
        return espn_cfb.parse_scoreboard(json.load(fh))


@pytest.fixture
def cfb_root(tmp_path, monkeypatch, cfb_dir):
    from conftest import REPO

    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / REPO_CONFIG, tmp_path / REPO_CONFIG)
    monkeypatch.setenv("PANTHERA_NCAAF_ESPN_FIXTURE", str(cfb_dir / "espn_cfb_scoreboard.json"))
    monkeypatch.setenv("PANTHERA_NCAAF_ODDS_FIXTURE", str(cfb_dir / "odds_ncaaf_snapshot.json"))
    return tmp_path


# --- clients ---------------------------------------------------------------


def test_espn_cfb_parse(cfb_games):
    by_id = {g.event_id: g for g in cfb_games}
    assert len(cfb_games) == 5
    byu = by_id["401900001"]
    assert (byu.home_team, byu.away_team) == ("BYU Cougars", "TCU Horned Frogs")
    assert (byu.home_rank, byu.away_rank) == (18, None)  # 99 = unranked
    assert (byu.status, byu.home_score, byu.away_score) == ("Final", 31, 21)
    # 00:00Z Oct 4 is 20:00 ET Oct 3 — belongs to the Oct 3 slate.
    assert by_id["401900003"].game_date_et == "2026-10-03"
    assert by_id["401900004"].neutral_site and by_id["401900004"].indoor
    postponed = by_id["401900005"]
    assert postponed.status == "Postponed" and postponed.home_score is None


def test_odds_sport_key_routes_url():
    calls = []

    class Resp:
        headers = {"x-requests-used": "3", "x-requests-remaining": "497"}

        def raise_for_status(self):
            pass

        def json(self):
            return []

    class Sess:
        def get(self, url, params, timeout):
            calls.append(url)
            return Resp()

    odds.fetch_snapshot("k", session=Sess(), sport_key=odds.NCAAF_SPORT_KEY)
    odds.fetch_snapshot("k", session=Sess())
    assert calls[0].endswith("/sports/americanfootball_ncaaf/odds")
    assert calls[1] == odds.BASE  # MLB default unchanged


def test_cfbd_parsers(cfb_dir):
    load = lambda name: json.loads((cfb_dir / name).read_text())  # noqa: E731
    games = cfbd.parse_games(load("cfbd_games.json"))
    assert games.loc[0, "home_team"] == "Miami" and games.loc[0, "home_points"] == 38
    lines = cfbd.parse_lines(load("cfbd_lines.json"))
    assert len(lines) == 2  # the line-less BYU game yields no rows
    cons = lines[lines["provider"] == "consensus"].iloc[0]
    assert (cons["spread_open"], cons["spread"]) == (-13.5, -15.5)
    assert lines[lines["provider"] == "Bovada"].iloc[0]["spread"] == -16.0  # str -> float
    sp = cfbd.parse_sp_ratings(load("cfbd_sp.json"))
    assert list(sp["team"]) == ["Miami"]  # national averages row dropped
    venues = cfbd.parse_venues(load("cfbd_venues.json")).set_index("venue_id")
    assert venues.loc[3687, "latitude"] == 32.747 and venues.loc[3687, "dome"]
    assert venues.loc[3958, "longitude"] == -80.239


def test_cfbd_requires_key():
    with pytest.raises(cfbd.CfbdError):
        cfbd.get("games", {"year": 2023}, api_key="")


def test_open_meteo_kickoff_hour(cfb_dir):
    payload = json.loads((cfb_dir / "open_meteo_hourly.json").read_text())
    w = weather.parse_hourly(payload, "2026-10-03T19:30:00Z")
    assert (w.wind_mph, w.gust_mph, w.temperature_f) == (16.4, 24.6, 85.0)
    assert weather.parse_hourly(payload, "2026-10-04T19:30:00Z") is None


# --- matching ---------------------------------------------------------------


def test_normalize_name():
    assert matching.normalize_name("Hawai'i Rainbow Warriors") == "hawaii rainbow warriors"
    assert matching.normalize_name("San José State Spartans") == "san jose state spartans"
    assert matching.normalize_name("Texas A&M Aggies") == "texas a and m aggies"
    assert matching.normalize_name("Miami (OH) RedHawks") != matching.normalize_name(
        "Miami Hurricanes"
    )


def test_match_events(cfb_dir, cfb_games):
    events = json.loads((cfb_dir / "odds_ncaaf_snapshot.json").read_text())
    matched, unmatched = matching.match_events(events, cfb_games)
    assert matched == {
        "cfb-tcu-byu": "401900001",
        "cfb-clem-mia": "401900002",
        "cfb-col-ttu": "401900003",
        "cfb-haw-sjsu-neutral": "401900004",  # home/away swapped + accents
    }
    assert len(unmatched) == 1 and "cfb-fcs-unmatched" in unmatched[0]


def test_match_events_alias_and_window(cfb_games):
    ev = {
        "id": "x",
        "commence_time": "2026-10-03T19:30:00Z",
        "home_team": "Miami (FL) Hurricanes",
        "away_team": "Clemson Tigers",
    }
    assert matching.match_events([ev], cfb_games)[0] == {}
    aliases = {"Miami (FL) Hurricanes": "Miami Hurricanes"}
    assert matching.match_events([ev], cfb_games, aliases)[0] == {"x": "401900002"}
    late = ev | {"commence_time": "2026-10-04T03:30:00Z"}  # 8h off
    assert matching.match_events([late], cfb_games, aliases)[0] == {}


# --- grading ----------------------------------------------------------------

GAME = {"status": "Final", "home_team": "BYU Cougars", "away_team": "TCU Horned Frogs",
        "home_score": 31, "away_score": 21}


@pytest.mark.parametrize(
    "market,selection,line,expected",
    [
        ("spread", "BYU Cougars", -6.5, "win"),
        ("spread", "TCU Horned Frogs", 6.5, "loss"),
        ("spread", "BYU Cougars", -10, "push"),
        ("spread", "TCU Horned Frogs", 10.5, "win"),
        ("moneyline", "TCU Horned Frogs", None, "loss"),
        ("moneyline", "byu cougars", None, "win"),
        ("total", "Over", 52.5, "loss"),
        ("total", "Under", 52.5, "win"),
        ("total", "Over", 52, "push"),
    ],
)
def test_grade_leg(market, selection, line, expected):
    status, final = grading.grade_leg(market, selection, line, GAME)
    assert status == expected
    assert final == "TCU Horned Frogs 21 - BYU Cougars 31"


def test_grade_leg_pending_void_and_unknown_team():
    def leg(status):
        return grading.grade_leg("spread", "BYU Cougars", -6.5, GAME | {"status": status})

    assert leg("Scheduled") is None
    assert leg("Postponed")[0] == "void"
    with pytest.raises(ValueError):
        grading.grade_leg("spread", "Utah Utes", -6.5, GAME)


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["win", "win", "win"], ("win", 6.958)),
        (["win", "loss", "pending"], ("loss", None)),  # a loss settles at once
        (["win", "pending", "win"], ("pending", None)),
        (["win", "push", "win"], ("win", 3.6447)),  # push leg drops out
        (["void", "push", "push"], ("push", 1.0)),
    ],
)
def test_settle_ticket(statuses, expected):
    assert grading.settle_ticket(statuses, [1.9091] * 3) == expected


# --- end to end ---------------------------------------------------------------


def test_snapshot_ticket_grade_end_to_end(cfb_root, monkeypatch):
    """The author's worked example as a ticket: three -110 spread legs ->
    decimal 6.958 (+596, his "~+600"), graded a win on the synthetic finals."""
    from panthera_mvp.ncaaf import pipeline

    monkeypatch.setattr(pipeline, "_today_et", lambda: "2026-10-03")
    pipeline.cmd_snapshot("pregame", dry_run=True)
    pipeline.cmd_snapshot("pregame", dry_run=True)  # idempotent
    lines = store.load_lines()
    assert len(lines) == 14
    assert set(lines["event_id"].dropna()) == {"401900001", "401900002", "401900003", "401900004"}
    assert lines[lines["odds_event_id"] == "cfb-fcs-unmatched"]["event_id"].isna().all()

    games = store.load_games().set_index("event_id")
    legs = []
    spreads = lines[lines["market"] == "spreads"]
    for n, team in enumerate(["BYU Cougars", "Miami Hurricanes", "Texas Tech Red Raiders"], 1):
        row = spreads[spreads["outcome"] == team].iloc[0]
        legs.append({
            "ticket_id": "T1", "leg_no": n, "event_id": row["event_id"],
            "matchup": f"{row['away_team']} @ {row['home_team']}",
            "start_time_utc": games.loc[row["event_id"], "start_time_utc"],
            "market": "spread", "selection": team, "line": row["point"],
            "price_american": row["price_american"], "price_decimal": row["price_decimal"],
            "bookmaker": row["bookmaker"],
        })
    price = round(1.9091 ** 3, 4)
    assert store.append_ticket(
        {"ticket_id": "T1", "strategy_id": "worked_example", "game_date_et": "2026-10-03",
         "n_legs": 3, "price_decimal": price, "stake": 100}, legs
    )
    assert not store.append_ticket({"ticket_id": "T1"}, legs)  # immutable

    pipeline.cmd_grade()
    t = store.load_tickets().iloc[0]
    assert t["status"] == "win"
    assert t["settled_price_decimal"] == pytest.approx(6.958)
    assert t["profit"] == pytest.approx(595.8)
    assert set(store.load_legs()["status"]) == {"win"}
    pipeline.cmd_grade()  # re-run is a no-op
    assert store.load_tickets().iloc[0]["profit"] == pytest.approx(595.8)
