"""College baseball plumbing (issue #52): ncaa-api + ESPN parsers, URL
building, name/doubleheader matching, the season gate, pick grading, and the
games -> ESPN fallback -> grade path end to end.

The fixtures under tests/fixtures/college_baseball/ are SYNTHETIC — the dev
sandbox cannot reach ncaa-api.henrygd.me, ESPN or The Odds API. The
ncaa-api shape follows that project's `convertToOldFormat` source (names.full
and conference names empty since 2025; gameState final|live|pre); ESPN and
Odds API shapes follow the existing MLB/NCAAF fixtures. The 2026-05-01 slate
models a Florida St. @ Miami (FL) doubleheader whose game 2 ncaa-api never
marks final (ESPN settles it), a postponement, a run-rule final, a TBA start
and a next-day game. Replace with recorded payloads from the
ncaabase-capture workflow once it has run.
"""

import json
import shutil

import pandas as pd
import pytest
import yaml

from conftest import FIXTURES, REPO
from panthera_mvp.clients import college_baseball as cb
from panthera_mvp.ncaabase import grading, matching, store
from panthera_mvp.ncaabase.config import in_season, load_ncaabase_config
from panthera_mvp.timeutil import parse_utc

DAY = "2026-05-01"
REPO_CONFIG = "config/ncaabase.yaml"


def _repo_cfg() -> dict:
    return yaml.safe_load((REPO / REPO_CONFIG).read_text())


def _payload() -> dict:
    return json.loads((FIXTURES / "college_baseball" / f"ncaa_scoreboard_{DAY}.json").read_text())


@pytest.fixture
def cbb_dir(fixtures_dir):
    return fixtures_dir / "college_baseball"


@pytest.fixture
def ncaa_payload(cbb_dir):
    return json.loads((cbb_dir / f"ncaa_scoreboard_{DAY}.json").read_text())


@pytest.fixture
def espn_games(cbb_dir):
    payload = json.loads((cbb_dir / f"espn_college_baseball_{DAY}.json").read_text())
    return cb.parse_espn_scoreboard(payload)


@pytest.fixture
def cbb_root(tmp_path, monkeypatch, cbb_dir):
    from panthera_mvp.ncaabase import pipeline

    monkeypatch.setenv("PANTHERA_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / REPO_CONFIG, tmp_path / REPO_CONFIG)
    for env, name in [
        ("PANTHERA_NCAABASE_NCAA_FIXTURE", f"ncaa_scoreboard_{DAY}.json"),
        ("PANTHERA_NCAABASE_ESPN_FIXTURE", f"espn_college_baseball_{DAY}.json"),
        ("PANTHERA_NCAABASE_ODDS_FIXTURE", "odds_ncaabase_snapshot.json"),
    ]:
        monkeypatch.setenv(env, str(cbb_dir / name))
    # The morning after the slate: every 2026-05-01 game has started.
    monkeypatch.setattr(pipeline, "_now", lambda: parse_utc("2026-05-02T14:00:00Z"))
    return tmp_path


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload, status=200):
        self.calls, self.payload, self.status = [], payload, status

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return FakeResp(self.payload, self.status)


# --- clients ---------------------------------------------------------------


def test_parse_schedule(ncaa_payload):
    games = {g.game_id: g for g in cb.parse_schedule(ncaa_payload, DAY)}
    assert len(games) == 7
    lsu = games["6600001"]
    assert (lsu.home_team, lsu.away_team, lsu.home_seo) == ("LSU", "Texas A&M", "lsu")
    assert (lsu.status, lsu.home_score, lsu.away_score, lsu.score_source) == ("Final", 7, 5, "ncaa")
    assert (lsu.home_rank, lsu.away_rank, lsu.home_conference) == (3, None, "sec")
    assert lsu.start_time_utc == "2026-05-01T22:00:00Z" and not lsu.start_time_tba
    g2 = games["6600003"]
    assert g2.status == "Scheduled" and g2.home_score is None and g2.score_source == ""
    assert games["6600004"].status == "Postponed"  # read from currentPeriod/finalMessage
    run_rule = games["6600005"]  # no epoch: 6:00PM ET on the startDate
    assert run_rule.start_time_utc == "2026-05-01T22:00:00Z"
    assert (run_rule.status, run_rule.current_period) == ("Final", "FINAL/7")
    assert (run_rule.away_score, run_rule.home_score) == (12, 2)
    tba = games["6600006"]
    assert tba.start_time_tba and tba.start_time_utc == "2026-05-01T04:00:00Z"  # ET midnight
    assert games["6600007"].game_date_et == "2026-05-02"


def test_parse_schedule_final_without_score_is_not_settled():
    payload = {"games": [{"game": {
        "gameID": "1", "gameState": "final", "startDate": "05/01/2026", "startTimeEpoch": "",
        "startTime": "TBA", "home": {"score": "", "names": {"short": "A"}},
        "away": {"score": "", "names": {"short": "B"}}}}]}
    (g,) = cb.parse_schedule(payload, DAY)
    assert g.status == "InProgress" and g.home_score is None


def test_get_schedule_daily_url_and_date_filter(ncaa_payload):
    sess = FakeSession(ncaa_payload)
    games = cb.get_schedule(DAY, base_url="https://ncaa.example/", session=sess)
    assert sess.calls[0][0] == "https://ncaa.example/scoreboard/baseball/d1/2026/05/01/all-conf"
    assert len(games) == 6 and "6600007" not in {g.game_id for g in games}
    with pytest.raises(RuntimeError):  # 404 may be an upstream failure, not "no games"
        cb.get_schedule(DAY, session=FakeSession({}, status=404))


def test_get_schedule_range_one_call_per_day(ncaa_payload):
    sess = FakeSession(ncaa_payload)
    cb.get_schedule_range("2026-04-30", "2026-05-02", session=sess, pause_s=0)
    assert [c[0].rsplit("/d1/", 1)[1] for c in sess.calls] == [
        "2026/04/30/all-conf", "2026/05/01/all-conf", "2026/05/02/all-conf",
    ]


def test_parse_espn_scoreboard(espn_games):
    by_id = {e.event_id: e for e in espn_games}
    assert len(espn_games) == 5
    g2 = by_id["401700003"]
    assert g2.home_names == ["Miami", "Miami Hurricanes"]
    assert (g2.status, g2.home_score, g2.away_score) == ("Final", 6, 2)
    assert by_id["401700004"].status == "Postponed" and by_id["401700004"].home_score is None
    assert by_id["401700005"].status == "Scheduled"


def test_get_espn_scoreboard_params():
    sess = FakeSession({"events": []})
    cb.get_espn_scoreboard(DAY, session=sess)
    cb.get_espn_scoreboard(DAY, group="26", session=sess)
    assert sess.calls[0] == (cb.ESPN_BASE, {"dates": "20260501", "limit": 500})
    assert sess.calls[1][1]["groups"] == "26"


# --- matching ---------------------------------------------------------------


def test_canon_and_fits():
    assert matching.canon("Florida St.") == matching.canon("Florida State") == "florida state"
    assert matching.canon("N.C. State") == "nc state"
    keys = matching.team_keys("Texas A&M", "texas-am")
    assert matching.fits(["Texas A&M Aggies"], keys, {})
    assert not matching.fits(["Texas Longhorns"], keys, {})
    # "Miami" alone is the Miami (FL) collision: only the alias resolves it.
    mia = matching.team_keys("Miami (FL)", "miami-fl")
    assert not matching.fits(["Miami"], mia, {})
    assert matching.fits(["Miami"], mia, matching.alias_map({"Miami": "Miami (FL)"}))
    assert not matching.fits(["Miami (OH) RedHawks"], mia, {})


def test_match_espn_doubleheader_and_postponement(ncaa_payload, espn_games):
    games = [g.__dict__ for g in cb.parse_schedule(ncaa_payload, DAY)]
    aliases = _repo_cfg()["matching"]["team_aliases"]
    matched, unmatched = matching.match_espn(games, espn_games, aliases)
    ids = {gid: e.event_id for gid, (e, _) in matched.items()}
    assert ids["6600002"] == "401700002" and ids["6600003"] == "401700003"  # by start time
    assert ids["6600004"] == "401700004"
    assert "6600006" not in ids  # TBA start (ET midnight) is outside the window
    assert any("6600006" in m for m in unmatched)


def test_match_espn_ambiguous_doubleheader_is_skipped(espn_games):
    game = {"game_id": "x", "home_team": "Miami (FL)", "away_team": "Florida St.",
            "home_seo": "miami-fl", "away_seo": "florida-st",
            "start_time_utc": "2026-05-01T19:00:00Z"}
    matched, unmatched = matching.match_espn([game], espn_games, {"Miami": "Miami (FL)"})
    assert matched == {}  # 2h from game 1 and 2h05 from game 2: never guessed
    assert "ambiguous" in unmatched[0]


def test_match_espn_swapped_home_away():
    game = {"game_id": "n1", "home_team": "LSU", "away_team": "Texas A&M",
            "start_time_utc": "2026-05-01T22:00:00Z"}
    neutral = cb.EspnBaseballGame("e1", "2026-05-01T22:00:00Z", ["Texas A&M"], ["LSU"],
                                  "Final", 5, 7)
    matched, _ = matching.match_espn([game], [neutral])
    assert matched["n1"] == (neutral, True)


def test_match_odds_events(cbb_dir, ncaa_payload):
    events = json.loads((cbb_dir / "odds_ncaabase_snapshot.json").read_text())
    games = [g.__dict__ for g in cb.parse_schedule(ncaa_payload, DAY)]
    aliases = _repo_cfg()["matching"]["team_aliases"]
    matched, unmatched = matching.match_odds_events(events, games, aliases)
    assert matched == {
        "cbb-tamu-lsu": "6600001",
        "cbb-fsu-mia-g1": "6600002",
        "cbb-fsu-mia-g2": "6600003",
    }
    assert {u.split(":")[0] for u in unmatched} == {"cbb-unmatched", "cbb-unpriced"}


def test_season_window():
    cfg = _repo_cfg()
    assert in_season("2026-05-01", cfg) and in_season("2026-02-01", cfg)
    assert in_season("2026-06-30", cfg)
    assert not in_season("2026-07-01", cfg) and not in_season("2026-10-04", cfg)


# --- grading ----------------------------------------------------------------

GAME = {"status": "Final", "home_team": "LSU", "away_team": "Texas A&M", "home_seo": "lsu",
        "away_seo": "texas-am", "home_score": 7, "away_score": 5}


@pytest.mark.parametrize(
    "market,selection,line,expected",
    [
        ("ml", "LSU", None, "win"),
        ("ml", "Texas A&M Aggies", None, "loss"),
        ("rl", "LSU Tigers", -1.5, "win"),
        ("rl", "Texas A&M", 1.5, "loss"),
        ("rl", "LSU", -2, "push"),
        ("rl", "Texas A&M", 2.5, "win"),
        ("total", "Over", 11.5, "win"),
        ("total", "Under", 11.5, "loss"),
        ("total", "Over", 12, "push"),
    ],
)
def test_grade_pick(market, selection, line, expected):
    status, final = grading.grade_pick(market, selection, line, GAME)
    assert status == expected
    assert final == "Texas A&M 5 - LSU 7"


def test_grade_pick_pending_void_and_unknown_team():
    def pick(status):
        return grading.grade_pick("ml", "LSU", None, GAME | {"status": status})

    assert pick("Scheduled") is None
    assert pick("Suspended") is None  # resumed later, not voided
    assert pick("Postponed")[0] == "void" and pick("Canceled")[0] == "void"
    with pytest.raises(ValueError):
        grading.grade_pick("ml", "Ole Miss", None, GAME)


def test_side_prefers_exact_over_prefix():
    game = {"home_team": "Texas", "away_team": "Texas A&M"}
    assert matching.side("Texas", game) == "home"
    # Fits both "texas" and "texas a and m" by prefix: the longer key wins.
    assert matching.side("Texas A&M Aggies", game) == "away"
    assert matching.side("Texas Longhorns", game) == "home"


# --- end to end ---------------------------------------------------------------


def _pick(pid, game_id, market, selection, line, price_decimal):
    return {"pick_id": pid, "strategy_id": "test", "game_date_et": DAY, "game_id": game_id,
            "market": market, "selection": selection, "line": line,
            "price_decimal": price_decimal, "stake": 100}


def test_games_fallback_and_grade_end_to_end(cbb_root):
    """Acceptance: ingest the 2026-05-01 slate, then `grade` settles finals —
    including the doubleheader game ncaa-api never marked final (from ESPN) —
    and settles picks on them. Re-runs are no-ops."""
    from panthera_mvp.ncaabase import pipeline

    pipeline.cmd_games(DAY)
    games = store.load_games().set_index("game_id")
    assert len(games) == 6  # the 05/02 game is filtered out
    # `games` already ran the fallback: every started game ESPN finished is final.
    assert games.loc["6600003", "status"] == "Final"
    assert (games.loc["6600003", "home_score"], games.loc["6600003", "away_score"]) == (6, 2)
    assert games.loc["6600003", "score_source"] == "espn"
    assert games.loc["6600003", "espn_event_id"] == "401700003"
    assert games.loc["6600002", "score_source"] == "ncaa"
    assert games.loc["6600004", "status"] == "Postponed"
    assert games.loc["6600006", "status"] == "Scheduled"  # TBA, unmatched: left alone

    # A later ncaa-api refresh still saying "pre" must not un-settle game 2.
    pipeline.cmd_games(DAY)
    assert store.load_games().set_index("game_id").loc["6600003", "status"] == "Final"

    for p in [
        _pick("p-ml", "6600001", "ml", "LSU Tigers", None, 1.6667),
        _pick("p-rl", "6600003", "rl", "Miami (FL)", -1.5, 2.1),
        _pick("p-tot", "6600002", "total", "Over", 9.5, 1.9091),
        _pick("p-void", "6600004", "ml", "Mississippi St.", None, 1.8),
        _pick("p-open", "6600006", "ml", "Arkansas", None, 1.5),
    ]:
        assert store.append_pick(p)
    assert not store.append_pick(_pick("p-ml", "6600001", "ml", "Texas A&M", None, 2.0))

    pipeline.cmd_grade()
    picks = store.load_picks().set_index("pick_id")
    assert picks["status"].to_dict() == {
        "p-ml": "win", "p-rl": "win", "p-tot": "loss", "p-void": "void", "p-open": "pending",
    }
    assert picks.loc["p-ml", "profit"] == pytest.approx(66.67)
    assert picks.loc["p-rl", "profit"] == pytest.approx(110.0)
    assert picks.loc["p-tot", "profit"] == -100
    assert picks.loc["p-void", "profit"] == 0
    assert picks.loc["p-rl", "final_score"] == "Florida St. 2 - Miami (FL) 6"
    settled_at = picks.loc["p-ml", "settled_ts_utc"]

    pipeline.cmd_grade()  # re-run: nothing re-settled
    again = store.load_picks().set_index("pick_id")
    assert again.loc["p-ml", "settled_ts_utc"] == settled_at
    assert again.loc["p-open", "status"] == "pending"


def test_espn_fallback_runs_when_ncaa_api_fails(cbb_root, monkeypatch):
    from panthera_mvp.ncaabase import pipeline

    games = [g.__dict__ for g in cb.parse_schedule(_payload(), DAY) if g.game_date_et == DAY]
    store.upsert_games(pd.DataFrame(games))
    monkeypatch.setenv("PANTHERA_NCAABASE_NCAA_FIXTURE", str(cbb_root / "missing.json"))
    pipeline.cmd_grade(DAY)
    g = store.load_games().set_index("game_id").loc["6600003"]
    assert (g["status"], g["score_source"]) == ("Final", "espn")


def test_season_gate_no_network(cbb_root, monkeypatch, capsys):
    from panthera_mvp.ncaabase import pipeline

    def boom(*a, **k):
        raise AssertionError("network call outside the season")

    monkeypatch.setattr(pipeline, "_ncaa_games", boom)
    monkeypatch.setattr(pipeline, "_now", lambda: parse_utc("2026-10-04T16:00:00Z"))
    pipeline.cmd_games()
    pipeline.cmd_snapshot("open", dry_run=True)
    pipeline.cmd_grade()  # empty store: nothing to refresh
    out = capsys.readouterr().out
    assert out.count("outside the season window") == 2 and "nothing to refresh" in out
    assert not store.load_games().shape[0]


def test_snapshot_dry_run_matches_and_is_idempotent(cbb_root, monkeypatch):
    from panthera_mvp.ncaabase import pipeline

    monkeypatch.setattr(pipeline, "_now", lambda: parse_utc("2026-05-01T14:00:00Z"))
    pipeline.cmd_snapshot("open", dry_run=True)
    pipeline.cmd_snapshot("open", dry_run=True)
    lines = store.load_lines()
    assert len(lines) == 12  # 6 + 2 + 2 + 2 (unpriced event yields nothing)
    by_event = lines.groupby("odds_event_id")["game_id"].first()
    assert by_event["cbb-fsu-mia-g2"] == "6600003"
    assert pd.isna(by_event["cbb-unmatched"])
    # Morning: nothing has started, so no ESPN fallback settled anything.
    assert store.load_games().set_index("game_id").loc["6600003", "status"] == "Scheduled"


def test_snapshot_live_disabled_and_no_priced_events(cbb_root, monkeypatch, capsys, tmp_path):
    from panthera_mvp.ncaabase import pipeline

    monkeypatch.setattr(pipeline, "_now", lambda: parse_utc("2026-05-01T14:00:00Z"))
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    pipeline.cmd_snapshot("open")  # disabled by default: skips before needing a key
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    monkeypatch.setenv("PANTHERA_NCAABASE_ODDS_FIXTURE", str(empty))
    pipeline.cmd_snapshot("open", dry_run=True)
    out = capsys.readouterr().out
    assert "odds_api.enabled is false" in out and "no priced events" in out
    assert store.load_lines().empty


def test_config_loads_from_root(cbb_root):
    cfg = load_ncaabase_config()
    assert cfg["odds_api"]["sport_key"] == "baseball_ncaa" and not cfg["odds_api"]["enabled"]


def test_snapshot_live_force_uses_baseball_ncaa_and_logs_credits(cbb_root, monkeypatch, cbb_dir):
    from panthera_mvp.clients import odds
    from panthera_mvp.ncaabase import pipeline

    events = json.loads((cbb_dir / "odds_ncaabase_snapshot.json").read_text())
    calls = []

    def fake_fetch(api_key, **kw):
        calls.append(kw)
        return events, odds.CreditInfo(used=3, remaining=400)

    monkeypatch.setattr(odds, "fetch_snapshot", fake_fetch)
    monkeypatch.setenv("ODDS_API_KEY", "k")
    monkeypatch.setattr(pipeline, "_now", lambda: parse_utc("2026-10-04T14:00:00Z"))
    pipeline.cmd_snapshot("open", force=True)  # off-season and disabled: forced
    assert calls[0]["sport_key"] == "baseball_ncaa"
    assert calls[0]["min_credits_reserve"] == 90
    assert (cbb_root / "data/ncaabase/odds/raw/2026-10-04/open.json").exists()
    assert pd.read_csv(cbb_root / "data/odds/credit_log.csv")["label"].tolist() == ["ncaabase_open"]
    assert len(store.load_lines()) == 12
