"""NCAAF week ingest (ESPN week mode + CFBD primary), CFBD rankings/teams/
team-stats parsers, the ncaa-api client, and the grade-time finals fallback
chain (ESPN -> CFBD -> ncaa-api).

All new fixtures are SYNTHETIC, hand-written from the documented response
shapes (the dev sandbox's proxy blocks ESPN, CFBD and ncaa-api.henrygd.me):
cfbd_week_games/lines/teams/rankings/season_stats.json follow CFBD v2
camelCase; ncaa_api_scoreboard.json follows ncaa-api's
`games[].game.{gameID, startTimeEpoch, gameState, home/away.{score, winner,
names.{short, seo, char6}}}`. They describe the same 2026 week-6 slate as
espn_cfb_scoreboard.json, keyed by the same ids (CFBD game id == ESPN event
id), plus: a neutral-site game whose home/away is swapped between feeds, a
CFBD-only game (Ohio State), a school-name disagreement on a shared id (App
State) and NCAA.com's abbreviated names ("San Jose St.", "Miami (FL)").
Replace with recorded payloads from the ncaaf-capture workflow.
"""

import json
import shutil
from dataclasses import replace

import pandas as pd
import pytest

from panthera_mvp.clients import cfbd, espn_cfb, ncaa_api
from panthera_mvp.ncaaf import sources, store

REPO_CONFIG = "config/ncaaf.yaml"


@pytest.fixture
def cfb_dir(fixtures_dir):
    return fixtures_dir / "ncaaf"


def _load(cfb_dir, name):
    return json.loads((cfb_dir / name).read_text())


@pytest.fixture
def espn_games(cfb_dir):
    return espn_cfb.parse_scoreboard(_load(cfb_dir, "espn_cfb_scoreboard.json"))


@pytest.fixture
def display(cfb_dir):
    teams = cfbd.parse_teams(_load(cfb_dir, "cfbd_teams.json"))
    return dict(zip(teams["school"], teams["display_name"], strict=True))


@pytest.fixture
def cfbd_games(cfb_dir, display):
    return sources.cfbd_to_games(cfbd.parse_games(_load(cfb_dir, "cfbd_week_games.json")), display)


@pytest.fixture
def cfb_root(tmp_path, monkeypatch, cfb_dir):
    from conftest import REPO

    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / REPO_CONFIG, tmp_path / REPO_CONFIG)
    monkeypatch.setenv("PANTHERA_NCAAF_ESPN_FIXTURE", str(cfb_dir / "espn_cfb_scoreboard.json"))
    monkeypatch.setenv("PANTHERA_NCAAF_ODDS_FIXTURE", str(cfb_dir / "odds_ncaaf_snapshot.json"))
    monkeypatch.delenv("CFBD_API_KEY", raising=False)
    return tmp_path


@pytest.fixture
def fake_cfbd(monkeypatch, cfb_dir):
    """CFBD reachable: cfbd.get serves the week fixtures by endpoint."""
    calls = []
    payloads = {
        "games": "cfbd_week_games.json",
        "lines": "cfbd_week_lines.json",
        "teams/fbs": "cfbd_teams.json",
    }

    def get(endpoint, params, api_key, session=None):
        calls.append((endpoint, dict(params)))
        return _load(cfb_dir, payloads[endpoint])

    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    monkeypatch.setattr(cfbd, "get", get)
    return calls


# --- clients ---------------------------------------------------------------


def test_espn_scoreboard_params():
    assert espn_cfb.scoreboard_params(date_et="2026-10-03") == {
        "dates": "20261003", "groups": "80", "limit": 300,
    }
    assert espn_cfb.scoreboard_params(season=2026, week=5) == {
        "dates": "2026", "seasontype": 2, "week": 5, "groups": "80", "limit": 300,
    }
    assert espn_cfb.scoreboard_params(season=2026, week=1, season_type="postseason")[
        "seasontype"
    ] == 3
    with pytest.raises(ValueError):
        espn_cfb.scoreboard_params(season=2026)
    with pytest.raises(ValueError):
        espn_cfb.scoreboard_params(season=2026, week=5, season_type="spring")


def test_espn_week_fetch_keeps_fbs_group(cfb_dir):
    sent = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return _load(cfb_dir, "espn_cfb_scoreboard.json")

    class Sess:
        def get(self, url, params, timeout):
            sent.append(params)
            return Resp()

    games = espn_cfb.get_week_scoreboard(2026, 6, session=Sess())
    assert sent[0]["groups"] == "80" and sent[0]["week"] == 6 and len(games) == 5


def test_espn_parse_season_week_school(espn_games):
    byu = next(g for g in espn_games if g.event_id == "401900001")
    assert (byu.season, byu.season_type, byu.week) == (2026, "regular", 6)
    assert (byu.home_school, byu.away_school, byu.score_source) == ("BYU", "TCU", "espn")
    postponed = next(g for g in espn_games if g.event_id == "401900005")
    assert postponed.score_source == ""


def test_ncaa_api_parse(cfb_dir):
    games = ncaa_api.parse_scoreboard(_load(cfb_dir, "ncaa_api_scoreboard.json"))
    assert len(games) == 5
    byu = games[0]
    assert (byu.game_id, byu.state, byu.home_score, byu.away_score) == ("6400001", "final", 31, 21)
    assert byu.start_time_utc == "2026-10-03T23:30:00Z" and byu.game_date_et == "2026-10-03"
    # 00:00Z Oct 4 is 20:00 ET Oct 3.
    assert games[2].game_date_et == "2026-10-03"
    pre = games[4]
    assert pre.state == "pre" and pre.home_score is None
    assert ncaa_api.scoreboard_path(2026, 5) == "/scoreboard/football/fbs/2026/05/all-conf"
    assert ncaa_api.scoreboard_path(2026, 1, "postseason").endswith("/2026/P/all-conf")


def test_cfbd_teams_rankings_stats_parsers(cfb_dir, display):
    assert display["Miami"] == "Miami Hurricanes"
    assert display["Hawai'i"] == "Hawai'i Rainbow Warriors"
    assert display["Appalachian State"] == "Appalachian State"  # no mascot -> school
    rk = cfbd.parse_rankings(_load(cfb_dir, "cfbd_rankings.json"))
    ap = rk[rk["poll"] == "AP Top 25"].set_index("school")
    assert len(rk) == 3 and ap.loc["Miami", "rank"] == 6 and ap.loc["Miami", "week"] == 6
    st = cfbd.parse_season_stats(_load(cfb_dir, "cfbd_season_stats.json"))
    wide = st.pivot(index="team", columns="stat", values="value")
    assert wide.loc["Clemson", "totalYards"] == 2198  # str -> number
    assert wide.loc["Miami", "turnovers"] == 4


# --- week merge ---------------------------------------------------------------


def test_cfbd_to_games(cfbd_games):
    by_id = {g.event_id: g for g in cfbd_games}
    assert len(cfbd_games) == 6
    mia = by_id["401900002"]
    assert (mia.home_team, mia.away_team, mia.home_school) == (
        "Miami Hurricanes", "Clemson Tigers", "Miami",
    )
    assert (mia.status, mia.home_score, mia.score_source, mia.week) == ("Final", 38, "cfbd", 6)
    assert by_id["401900006"].status == "Scheduled" and by_id["401900006"].home_score is None


def test_merge_week(espn_games, cfbd_games):
    games, warnings = sources.merge_week(espn_games, cfbd_games)
    by_id = {g.event_id: g for g in games}
    assert sorted(by_id) == [f"40190000{i}" for i in range(1, 7)]
    # Shared id, swapped home/away: ESPN's row (and orientation) is kept.
    haw = by_id["401900004"]
    assert (haw.home_team, haw.home_score, haw.away_score) == ("Hawai'i Rainbow Warriors", 27, 24)
    # CFBD-only game stored under its id with display names.
    osu = by_id["401900006"]
    assert (osu.home_team, osu.away_team) == ("Ohio State Buckeyes", "Michigan State Spartans")
    # Schools disagree on a shared id: logged, ESPN row kept untouched.
    assert len(warnings) == 1 and "401900005" in warnings[0]
    assert by_id["401900005"].status == "Postponed"


def test_merge_week_cfbd_fills_espn_lag(espn_games, cfbd_games):
    """ESPN still shows the neutral-site game live; CFBD has the final. The
    score lands on the right teams despite the swapped home/away."""
    lagging = [
        replace(g, status="InProgress", home_score=None, away_score=None, score_source="")
        if g.event_id == "401900004" else g
        for g in espn_games
    ]
    games, _ = sources.merge_week(lagging, cfbd_games)
    haw = next(g for g in games if g.event_id == "401900004")
    assert (haw.status, haw.home_score, haw.away_score, haw.score_source) == (
        "Final", 27, 24, "cfbd",
    )


def test_cfbd_week_lines(cfb_dir, espn_games, cfbd_games, display):
    games, _ = sources.merge_week(espn_games, cfbd_games)
    lines = sources.cfbd_week_lines(
        cfbd.parse_lines(_load(cfb_dir, "cfbd_week_lines.json")), games, display,
        "regular", "2026-10-02T12:00:00Z",
    )
    assert list(lines.columns) == sources.CFBD_LINES_COLUMNS
    assert len(lines) == 4
    neutral = lines[(lines["event_id"] == "401900004") & (lines["provider"] == "consensus")].iloc[0]
    # CFBD's home team keeps the spread sign, named in ESPN's spelling.
    assert (neutral["home_team"], neutral["spread"]) == ("San José State Spartans", 2.5)
    assert set(lines["event_id"]) == {"401900001", "401900004", "401900006"}


# --- finals fallbacks -----------------------------------------------------------


def _open_rows(espn_games):
    return [
        {**g.__dict__, "status": "Scheduled", "home_score": None, "away_score": None,
         "score_source": ""}
        for g in espn_games
    ]


def test_school_key():
    assert sources.school_key("San Jose St.") == sources.school_key("San José State")
    assert sources.school_key("Hawaii") == sources.school_key("Hawai'i")
    assert sources.school_key("Miami (FL)", {"Miami (FL)": "Miami"}) == "miami"
    assert sources.school_key("Miami (OH)") != sources.school_key("Miami")


def test_finals_from_ncaa(cfb_dir, espn_games):
    ncaa = ncaa_api.parse_scoreboard(_load(cfb_dir, "ncaa_api_scoreboard.json"))
    rows = _open_rows(espn_games)
    filled, unmatched = sources.finals_from_ncaa(rows, ncaa, {"Miami (FL)": "Miami"})
    by_id = {r["event_id"]: r for r in filled}
    assert sorted(by_id) == ["401900001", "401900002", "401900003", "401900004"]
    assert (by_id["401900004"]["home_score"], by_id["401900004"]["away_score"]) == (27, 24)
    assert by_id["401900002"]["score_source"] == "ncaa_api"
    # App State game is still "pre" on NCAA.com -> not filled, logged.
    assert len(unmatched) == 1 and "401900005" in unmatched[0]
    # Without the alias "Miami (FL)" is unknown: logged, never guessed.
    filled, unmatched = sources.finals_from_ncaa(rows, ncaa)
    assert "401900002" not in {r["event_id"] for r in filled}
    assert any("401900002" in m for m in unmatched)


def test_finals_from_ncaa_ambiguous_is_skipped(cfb_dir, espn_games):
    ncaa = ncaa_api.parse_scoreboard(_load(cfb_dir, "ncaa_api_scoreboard.json"))
    dup = replace(ncaa[0], game_id="dup")
    filled, unmatched = sources.finals_from_ncaa(_open_rows(espn_games)[:1], ncaa + [dup])
    assert filled == [] and "2 NCAA.com finals" in unmatched[0]


def test_finals_from_cfbd_swapped(espn_games, cfbd_games):
    filled = sources.finals_from_cfbd(_open_rows(espn_games), cfbd_games)
    by_id = {r["event_id"]: r for r in filled}
    assert set(by_id) == {"401900001", "401900002", "401900003", "401900004"}
    assert (by_id["401900004"]["home_score"], by_id["401900004"]["away_score"]) == (27, 24)


def test_upsert_never_downgrades_final(cfb_root, espn_games):
    store.upsert_games(pd.DataFrame([g.__dict__ for g in espn_games]))
    store.upsert_games(pd.DataFrame(_open_rows(espn_games)))
    games = store.load_games().set_index("event_id")
    assert games.loc["401900001", "status"] == "Final"
    assert games.loc["401900001", "home_score"] == 31
    assert games.loc["401900005", "status"] == "Scheduled"  # was not Final


# --- end to end ---------------------------------------------------------------


def test_week_snapshot_with_cfbd(cfb_root, fake_cfbd):
    """Acceptance: one snapshot command ingests the full week with lines
    attached — Odds API lines matched to the week's games, CFBD lines stored
    alongside — and re-running it changes nothing."""
    from panthera_mvp.ncaaf import pipeline

    pipeline.cmd_snapshot("open", dry_run=True, week=6, season=2026)
    pipeline.cmd_snapshot("open", dry_run=True, week=6, season=2026)
    games = store.load_games()
    assert len(games) == 6 and set(games["week"]) == {6}
    lines = store.load_lines()
    assert len(lines) == 14
    assert set(lines["event_id"].dropna()) == {"401900001", "401900002", "401900003", "401900004"}
    cl = store.load_cfbd_lines()
    assert len(cl) == 4 and set(cl["season_type"]) == {"regular"}
    # games/lines are re-fetched (live week), teams come from the cache.
    assert [c[0] for c in fake_cfbd].count("teams/fbs") == 1
    assert ("games", {"year": 2026, "week": 6, "seasonType": "regular",
                      "classification": "fbs"}) in fake_cfbd


def test_week_games_espn_only_without_key(cfb_root):
    from panthera_mvp.cli import main
    from panthera_mvp.ncaaf import pipeline

    main(["ncaaf", "games", "--week", "6", "--year", "2026"])
    assert len(store.load_games()) == 5
    assert store.load_cfbd_lines().empty
    with pytest.raises(SystemExit):
        main(["ncaaf", "games", "--week", "6", "--date", "2026-10-03"])
    assert pipeline._week_scoreboard(2026, 7, "regular", {}) == []  # other week filtered


def test_week_ingest_fails_only_when_both_sources_fail(cfb_root, monkeypatch):
    from panthera_mvp.ncaaf import pipeline

    def boom(*a, **k):
        raise RuntimeError("proxy 403")

    monkeypatch.setattr(pipeline, "_week_scoreboard", boom)
    with pytest.raises(SystemExit):
        pipeline.refresh_week(2026, 6)


def _ticket_on_open_games(espn_games):
    """Store the week's games as not-yet-final plus a 2-leg ticket on them."""
    store.upsert_games(pd.DataFrame(_open_rows(espn_games)))
    legs = [
        {"ticket_id": "T1", "leg_no": 1, "event_id": "401900001", "matchup": "TCU @ BYU",
         "start_time_utc": "2026-10-03T23:30:00Z", "market": "spread",
         "selection": "BYU Cougars", "line": -6.5, "price_american": -110,
         "price_decimal": 1.9091, "bookmaker": "draftkings"},
        {"ticket_id": "T1", "leg_no": 2, "event_id": "401900004",
         "matchup": "San José State @ Hawai'i", "start_time_utc": "2026-10-03T16:00:00Z",
         "market": "moneyline", "selection": "Hawai'i Rainbow Warriors", "line": None,
         "price_american": -140, "price_decimal": 1.7143, "bookmaker": "draftkings"},
    ]
    assert store.append_ticket(
        {"ticket_id": "T1", "strategy_id": "test", "game_date_et": "2026-10-03",
         "n_legs": 2, "price_decimal": 3.2727, "stake": 100}, legs
    )


def test_grade_falls_back_to_ncaa_api(cfb_root, monkeypatch, cfb_dir, espn_games):
    from panthera_mvp.ncaaf import pipeline

    _ticket_on_open_games(espn_games)

    def espn_down(*a, **k):
        raise RuntimeError("ESPN 503")

    calls = []

    def ncaa(season, week, season_type="regular", session=None):
        calls.append((season, week, season_type))
        return ncaa_api.parse_scoreboard(_load(cfb_dir, "ncaa_api_scoreboard.json"))

    monkeypatch.setattr(pipeline, "_scoreboard", espn_down)
    monkeypatch.setattr(ncaa_api, "get_scoreboard", ncaa)
    pipeline.cmd_grade()
    assert calls == [(2026, 6, "regular")]  # one call for the whole week
    games = store.load_games().set_index("event_id")
    assert games.loc["401900004", "score_source"] == "ncaa_api"
    # Only pending-leg games are filled; others stay open.
    assert games.loc["401900002", "status"] == "Scheduled"
    t = store.load_tickets().iloc[0]
    assert t["status"] == "win"
    assert t["profit"] == pytest.approx(round(100 * (round(1.9091 * 1.7143, 4) - 1), 2))


def test_grade_prefers_cfbd_over_ncaa_api(cfb_root, monkeypatch, fake_cfbd, espn_games):
    from panthera_mvp.ncaaf import pipeline

    _ticket_on_open_games(espn_games)

    def down(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(pipeline, "_scoreboard", down)
    monkeypatch.setattr(ncaa_api, "get_scoreboard", down)  # must not be needed
    pipeline.cmd_grade()
    games = store.load_games().set_index("event_id")
    assert set(games.loc[["401900001", "401900004"], "score_source"]) == {"cfbd"}
    assert store.load_tickets().iloc[0]["status"] == "win"
