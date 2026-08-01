from panthera_mvp.clients.mlb import parse_schedule
from panthera_mvp.matching import match_events, team_id


def test_team_aliases():
    assert team_id("Boston Red Sox") == 111
    assert team_id("St. Louis Cardinals") == 138
    assert team_id("St Louis Cardinals") == 138
    assert team_id("Athletics") == 133
    assert team_id("Oakland Athletics") == 133
    assert team_id("Nonexistent Nine") is None


def test_match_events_pairs_by_teams_and_time(odds_events, mlb_schedule_payload):
    games = parse_schedule(mlb_schedule_payload)
    matched, unmatched = match_events(odds_events, games)
    assert matched == {"evt-nyy-bos": 776001, "evt-lad-sd": 776002}
    assert unmatched == []


def test_unmatched_events_are_reported_not_guessed(mlb_schedule_payload):
    games = parse_schedule(mlb_schedule_payload)
    stray = [
        {
            "id": "evt-unknown",
            "commence_time": "2026-08-01T23:05:00Z",
            "home_team": "Tokyo Giants",
            "away_team": "Boston Red Sox",
        }
    ]
    matched, unmatched = match_events(stray, games)
    assert matched == {}
    assert len(unmatched) == 1


def test_doubleheader_disambiguated_by_time(mlb_schedule_payload):
    games = parse_schedule(mlb_schedule_payload)
    # Duplicate game 1 as a nightcap 4 hours later.
    import copy

    g2 = copy.deepcopy(mlb_schedule_payload)
    night = copy.deepcopy(g2["dates"][0]["games"][0])
    night["gamePk"] = 776099
    night["gameDate"] = "2026-08-02T03:05:00Z"
    g2["dates"][0]["games"].append(night)
    games = parse_schedule(g2)

    events = [
        {
            "id": "evt-early",
            "commence_time": "2026-08-01T23:05:00Z",
            "home_team": "Boston Red Sox",
            "away_team": "New York Yankees",
        },
        {
            "id": "evt-late",
            "commence_time": "2026-08-02T03:00:00Z",
            "home_team": "Boston Red Sox",
            "away_team": "New York Yankees",
        },
    ]
    matched, unmatched = match_events(events, games)
    assert matched["evt-early"] == 776001
    assert matched["evt-late"] == 776099
    assert unmatched == []
