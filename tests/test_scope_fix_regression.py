"""Evidence that the 2026-10-15 postseason scope fix is domain-EXTENDING.

`src/panthera_mvp/CLAUDE.md` forbids extending a strategy's `hash_lineage`
across a behavioral change — new behavior means a new strategy id and fresh
counters. The scope fix moved every live strategy's `config_hash`, so pooling
the pre-fix and post-fix picks needs this file to be true:

    restricted to the games the OLD config admitted (game_type == "R"), the
    pre-fix and post-fix configs are the same decision function.

If that holds, no pick already in the ledger would have been different, the
pre-fix sample is not contaminated by pooling, and the lineage may be
extended. If it ever stops holding, the lineage appends in
config/strategies/*.yaml are no longer justified and those strategies must be
re-registered under new ids. This is the precondition, not a formality.

**What makes this a proof and not a tautology.** An earlier version of this
file compared two gate FUNCTIONS over contexts built with `splits=None` and
an empty `Dossier()`. On a population already filtered to `game_type == "R"`
both gates return True, so the comparison could not distinguish them; worse,
with no splits every `sharp_split`/`fade_public` context short-circuited at
`_splits_guards` and with an empty dossier `_build_season_context` — the
other half of the change — was never exercised at all. Two of the four
lineage extensions rested on nothing.

Why the SeasonContext half can agree and still be meaningful: the two arms
build genuinely different contexts — under the legacy whitelist a postseason
final never enters the dossier, under the current config it does — but every
regular-season game in a season PRECEDES every postseason game in it, so no
regular-season decision can ever see the difference. That is a structural
argument, not an accident of this dataset, and the replay below exercises the
path rather than assuming it.

This version fixes all three:
  - both arms run the REAL configs, differing only in the `season` block, fed
    through the one scope reader (`strategy/season.py`), so it compares
    configs rather than functions;
  - contexts carry the captured splits from `data/splits/splits.csv`, so the
    splits engines reach their real decision path;
  - the dossier is a real `SeasonContext` accumulated day by day with no
    lookahead, built under each arm's own scope rule, so the
    `_build_season_context` change is inside the comparison;
  - `test_negative_control_proof_has_teeth` asserts the comparison FAILS
    when the gate genuinely differs, so a future refactor cannot quietly
    turn it back into a tautology.

What the fix DOES change is the population: postseason games the day map was
never calibrated on. That is disclosed in BETTING_REPORT.md's regime caveat
and the per-strategy by-phase split, not hidden behind the hash.

The proof runs over the real captured history in `data/`, not a fixture — the
bug it guards against was a wrong value in a real config file.
"""

from __future__ import annotations

import copy
import importlib
import inspect
import pkgutil

import pandas as pd
import pytest

import panthera_mvp
from panthera_mvp import paths, store
from panthera_mvp.clients.mlb import GameInfo
from panthera_mvp.config import load_strategy_configs
from panthera_mvp.strategy.daytype import day_type
from panthera_mvp.strategy.dossier import Dossier, SeasonContext
from panthera_mvp.strategy.movement import extract_game_prices, extract_totals_prices
from panthera_mvp.strategy.registry import StrategyContext, engines
from panthera_mvp.strategy.season import in_scope
from panthera_mvp.strategy.slots import assign_slots
from panthera_mvp.strategy.splits_signal import extract_game_splits
from panthera_mvp.timeutil import parse_utc

#: Exhibition codes the current config excludes.
EXHIBITION = ("S", "E", "A", "I")

#: `splits_signal._splits_guards` ages captured splits against `now_utc()`.
#: Wall clock would make this file flaky — the two arms run seconds apart, so
#: a splits row sitting on the `max_staleness_hours` boundary can read fresh
#: for one arm and stale for the other, and the whole premise here is that
#: both arms see identical inputs. `_replay` pins this to each day's own
#: capture time + 1h, which is both deterministic and what a real pick run
#: sees.
_FAKE_NOW: list = [None]


@pytest.fixture(autouse=True)
def _pinned_splits_clock(monkeypatch):
    import panthera_mvp.strategy.splits_signal as splits_signal

    real = splits_signal.now_utc
    monkeypatch.setattr(
        splits_signal, "now_utc", lambda: _FAKE_NOW[0] or real()
    )

#: Minimums the docs and the pv_v3 YAML comment cite. Asserted so the written
#: claim cannot drift away from what the proof actually covers.
MIN_GAMES, MIN_DATES = 793, 59


def _live_strategy_ids() -> list[str]:
    """Derived, never hardcoded: the same predicate test_live_config.py uses,
    so a sixth live strategy joins the proof automatically instead of
    escaping it."""
    return sorted(
        sid
        for sid, cfg in load_strategy_configs(known_engines=set(engines())).items()
        if cfg["strategy"].get("enabled") and "live" in cfg["strategy"]["scope"]
    )


def _legacy_cfg(scfg: dict, observed: set[str]) -> dict:
    """The strategy's real config with ONLY the season block rolled back.

    The retired value was the whitelist `season.game_types: ["R"]`, and
    `strategy/season.py` now refuses that key outright, by design. Rather than
    monkeypatch the gate — which would compare two FUNCTIONS and leave the
    shipped reader untested — the whitelist is re-expressed as the blacklist
    that is equivalent to it over this population: exclude every gameType the
    captured history actually contains except "R", plus the exhibition codes.
    Both arms then run real configs through the one shipped reader.

    The two forms differ only on a code that appears in neither the data nor
    EXHIBITION — an unknown future code, which the whitelist would exclude and
    the blacklist admits. That difference IS the fix, it cannot arise on
    captured data, and it is outside the domain this claim is about.
    """
    out = copy.deepcopy(scfg)
    out["season"] = {
        "exclude_game_types": sorted((observed - {"R"}) | set(EXHIBITION))
    }
    return out


def _has_source(module) -> bool:
    try:
        inspect.getsource(module)
    except (OSError, TypeError):
        return False
    return True


def test_every_scope_reader_is_covered():
    """Every module that reads game-type scope must be one this file knows
    about. Scans the WHOLE package, not just `strategy/` — `pipeline.py` is a
    reader too (src/panthera_mvp/CLAUDE.md), and the earlier version of this
    test missed it."""
    readers = set()
    failed: list[str] = []
    for info in pkgutil.walk_packages(panthera_mvp.__path__, "panthera_mvp."):
        if ".dashboard_static" in info.name:
            continue
        try:
            module = importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            # A module that cannot be imported would escape the scan silently,
            # which is the same blind spot this test exists to close.
            failed.append(f"{info.name}: {type(exc).__name__}: {exc}")
            continue
        if info.name == "panthera_mvp.strategy.season":
            continue
        # Both forms of reading scope: the `in_scope` helper, and a direct
        # `excluded_game_types` call (doctor.py's config check does this).
        src = inspect.getsource(module) if _has_source(module) else ""
        if hasattr(module, "in_scope") or "excluded_game_types(" in src:
            readers.add(info.name)
    assert not failed, "modules that would escape the scan: " + "; ".join(failed)
    expected = {
        # Validates the key eagerly at load time so a scope fault fails the
        # run instead of being isolated per-strategy.
        "panthera_mvp.config",
        # Replays and repairs advance their own SeasonContext and decide which
        # dates a strategy should have evaluated, so both read scope.
        "panthera_mvp.catchup",
        "panthera_mvp.pipeline",
        "panthera_mvp.replay",
        "panthera_mvp.strategy.orig_rules",
        "panthera_mvp.strategy.registry",
        "panthera_mvp.strategy.rules",
        "panthera_mvp.strategy.splits_signal",
    }
    # doctor.py reads scope only to validate it (H09), and ships in a later
    # PR; accept it without requiring it.
    optional = {"panthera_mvp.doctor"}
    assert readers - optional == expected, f"scope readers changed: {sorted(readers)}"


@pytest.fixture(scope="module")
def captured():
    """Every captured slate day, with odds, splits and finals already
    extracted per game.

    Module-scoped and extracted once: prices, totals and splits depend only on
    the captured data, never on the arm or the strategy, and re-deriving them
    for each of the twelve replays below dominated the runtime.
    """
    if not paths.games_csv().exists() or not paths.lines_csv().exists():
        pytest.skip("no captured history in this checkout")
    games, lines = store.load_games(), store.load_lines()
    if games.empty or lines.empty:
        pytest.skip("no captured history in this checkout")
    from panthera_mvp.clients.lumify import load_splits

    splits = load_splits()
    lines = lines.dropna(subset=["game_pk"]).astype({"game_pk": int})

    days = []
    for day in sorted(games["game_date_et"].unique()):
        day_games = games[games["game_date_et"] == day]
        lines_today = lines[lines["game_date_et"] == day]
        if lines_today.empty:
            continue
        splits_today = (
            splits[splits["game_date_et"] == day] if not splits.empty else splits
        )
        events = (
            lines_today.drop_duplicates("game_pk")
            .set_index("game_pk")["odds_event_id"]
            .to_dict()
        )
        captured_at = (
            pd.to_datetime(splits_today["captured_at"], utc=True, errors="coerce").max()
            if not splits_today.empty and "captured_at" in splits_today.columns
            else pd.NaT
        )
        entries, finals = [], []
        for row in day_games.itertuples(index=False):
            if str(row.status) == "Final" and pd.notna(row.home_score):
                finals.append(
                    (
                        str(row.game_type),
                        row.home_team_id,
                        row.away_team_id,
                        int(row.home_score),
                        int(row.away_score),
                    )
                )
            if str(row.game_type) != "R":
                continue  # the claim is about the OLD config's domain only
            game = _game_info(row)
            event_id = events.get(game.game_pk)
            entries.append(
                {
                    "game": game,
                    "event_id": event_id,
                    "prices": (
                        extract_game_prices(
                            lines_today, event_id, game.home_team, game.away_team
                        )
                        if event_id
                        else None
                    ),
                    "totals": (
                        extract_totals_prices(lines_today, event_id)
                        if event_id
                        else None
                    ),
                    "splits": extract_game_splits(
                        splits_today, game.game_pk, game.start_utc
                    ),
                    "era_home": (
                        row.home_pitcher_era if pd.notna(row.home_pitcher_era) else None
                    ),
                    "era_away": (
                        row.away_pitcher_era if pd.notna(row.away_pitcher_era) else None
                    ),
                }
            )
        days.append(
            {
                "date": day,
                "entries": entries,
                "finals": finals,
                "splits_captured_at": None if pd.isna(captured_at) else captured_at,
            }
        )

    has_splits = not splits.empty
    return {"days": days, "games": games, "has_splits": has_splits}


def _game_info(row) -> GameInfo:
    """Always Preview: a replay decides as the pick run did, before the game."""
    return GameInfo(
        game_pk=int(row.game_pk),
        game_date_et=str(row.game_date_et),
        game_type=str(row.game_type),
        status="Preview",
        detailed_state="Scheduled",
        start_utc=parse_utc(str(row.start_time_utc)),
        doubleheader=str(row.doubleheader) if pd.notna(row.doubleheader) else "N",
        game_number=int(row.game_number) if pd.notna(row.game_number) else 1,
        home_team_id=int(row.home_team_id),
        home_team=str(row.home_team),
        away_team_id=int(row.away_team_id),
        away_team=str(row.away_team),
    )


def _replay(captured, scfg: dict, *, scope) -> list[str]:
    """Replay every captured slate day under one arm's config and scope rule.

    Mirrors the live pipeline: a SeasonContext accumulated day by day (so the
    `_build_season_context` scope change is inside the comparison), the real
    captured splits, real slot assignment. Picks are generated only for games
    the OLD config admitted — the domain the claim is about — while the
    context advances over every final THAT ARM's scope admits, which is
    exactly where the two arms can diverge.

    An engine that raises is recorded as its exception rather than propagated:
    the captured history contains at least one unusable price (a 0.0 that
    makes `american_to_decimal` divide by zero), and the question here is
    whether the two arms behave IDENTICALLY, errors included. Live, the same
    exception is isolated per strategy by cmd_picks.
    """
    boundary = int(scfg.get("hybrid_boundary_hour_et", 18))
    last10 = int(scfg.get("dossier", {}).get("last10_n", 10))
    engine = engines()[scfg["strategy"]["engine"]]
    ctx = SeasonContext()
    out: list[str] = []

    for day in captured["days"]:
        cap = day["splits_captured_at"]
        _FAKE_NOW[0] = (
            (cap + pd.Timedelta(hours=1)).to_pydatetime() if cap is not None else None
        )
        dtype = day_type(pd.Timestamp(day["date"]).date(), scfg)
        slot_map = assign_slots(
            [(e["game"].game_pk, e["game"].start_utc) for e in day["entries"]],
            dtype,
            boundary,
        )
        for entry in day["entries"]:
            game = entry["game"]
            dossier = Dossier.from_context(
                ctx,
                home_key=game.home_team_id,
                away_key=game.away_team_id,
                era_home=entry["era_home"],
                era_away=entry["era_away"],
                last10_n=last10,
            )
            sctx = StrategyContext(
                game=game,
                odds_event_id=entry["event_id"],
                prices=entry["prices"],
                totals=entry["totals"],
                dossier=dossier,
                splits=entry["splits"],
                slot_type=slot_map.get(game.game_pk),
                cfg=scfg,
            )
            try:
                out.append(repr(engine(sctx)))
            except Exception as exc:  # compared, not swallowed — see docstring
                out.append(f"RAISED {type(exc).__name__}: {exc}")

        # Advance AFTER the day's picks — no lookahead — over the finals THIS
        # ARM's scope admits. Under the legacy whitelist a postseason final
        # never enters the context; under the current config it does.
        for game_type, home_id, away_id, home_score, away_score in day["finals"]:
            if not scope(game_type, scfg):
                continue
            ctx.add_final(home_id, away_id, home_score, away_score)
    return out


def test_proof_covers_the_history_the_docs_claim(captured):
    """docs/mvp-design.md and config/strategies/pv_v3.yaml cite '793 games, 59
    dates'. Assert it here so the written claim cannot drift from the proof."""
    regular = captured["games"][captured["games"]["game_type"] == "R"]
    assert len(regular) >= MIN_GAMES
    assert regular["game_date_et"].nunique() >= MIN_DATES


def test_captured_splits_reach_the_splits_engines(captured):
    """Guard against the tautology the earlier version shipped: if every
    splits context were empty, sharp_split and fade_public would short-circuit
    at `_splits_guards` and their lineage extensions would rest on nothing."""
    assert captured["has_splits"], "no captured splits — the splits arms prove nothing"
    scfg = load_strategy_configs(known_engines=set(engines()))["sharp_split"]
    outcomes = _replay(captured, scfg, scope=in_scope)
    reached = [
        o for o in outcomes if "no-splits" not in o and "stale" not in o
    ]
    assert reached, (
        "every sharp_split context short-circuited in _splits_guards (missing or "
        "stale splits), so the sharp_split/fade_public lineage extensions would "
        "rest on nothing"
    )


@pytest.mark.parametrize("strategy_id", _live_strategy_ids())
def test_scope_fix_is_domain_extending_only(strategy_id, captured):
    scfg = load_strategy_configs(known_engines=set(engines()))[strategy_id]
    observed = set(captured["games"]["game_type"].astype(str))
    current = _replay(captured, scfg, scope=in_scope)
    legacy = _replay(captured, _legacy_cfg(scfg, observed), scope=in_scope)

    assert current, "the proof is vacuous if it compared no games"
    assert legacy == current, (
        f"{strategy_id}: the scope fix changed a decision on a regular-season "
        "game. It is NOT domain-extending, so extending hash_lineage in "
        "config/strategies/ is no longer justified — register a new strategy id."
    )


def test_negative_control_proof_has_teeth(captured):
    """The comparison must be able to FAIL. Break the gate so it excludes
    regular-season games and assert the two arms diverge — without this, a
    refactor could quietly turn the proof above back into a tautology."""
    scfg = load_strategy_configs(known_engines=set(engines()))["pv_v3"]
    broken = copy.deepcopy(scfg)
    broken["season"] = {"exclude_game_types": ["R", "S", "E", "A", "I"]}

    honest = _replay(captured, scfg, scope=in_scope)
    sabotaged = _replay(captured, broken, scope=in_scope)
    assert honest != sabotaged, "the proof cannot detect a broken gate"
