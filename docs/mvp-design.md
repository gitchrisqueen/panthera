# MVP Design — Strategy Formalization & Parameter Glossary

Goal: **prove or falsify** the betting process in
`sports_betting_process.md` with an automated, zero-cost pipeline. This doc
maps each statement in that outline to executable rules and named parameters.

## The testable hypothesis

1. Each day of week is a **Public (P)** or **Vegas (V)** day (Wednesday
   hybrid: before ~4 PM ET public, after Vegas).
2. Line movement direction reveals which camp's money arrived: a side's
   price **shortening** (−160 → −180, +120 → +105) = public money; a side's
   price **drifting** (−180 → −160) = Vegas/sharp positioning.
3. Betting the side matching the day/slot type (public side on P slots,
   Vegas side on V slots), with the documented sub-rules, beats the vig.

## Rule table — incumbent engine (`src/panthera_mvp/strategy/rules.py`)

This table documents the **incumbent `pv_rules` engine** (`pv_v2`/`pv_v3`)
as originally formalized from the bullet-point summary. It has known
discrepancies against the source recordings — see "Alignment with the
source recordings" below — deliberately left as-is per the multi-strategy
protocol (`pv_v2`/`pv_v3` are frozen controls, not patched in place). The
aligned reading lives in a separate engine, `strategy/orig_rules.py`
(rule ids O0–O7; its own docstring is the rule table for that engine).

| ID | Doc § | Rule | Parameters (config/strategy.yaml) |
|---|---|---|---|
| R0 | §6 | Regular-season games only; must be upcoming and priced | `season.game_types` |
| R1 | §2 | Day type from map; hybrid slots split at boundary hour | `day_map`, `hybrid_boundary_hour_et` |
| R2 | §1 | Movement on favorite's consensus ML (median of books), open → latest snapshot; below threshold = neutral | `movement.min_move_cents` |
| R3 | §5 | P slot backs public side; V slot backs Vegas side; neutral movement falls back through the dossier cascade: ERA edge (`R3_era`) → last-10 form (`R3_form`) → season-series lead (`R3_series`) → pass | `dossier.last10_n`, `min_last10_win_gap`, `min_series_lead` |
| R4 | §6 | Evenly-matched P slot → underdog run line +1.5 | `thresholds.evenly_matched_max_abs_ml`, `evenly_matched_max_era_diff` |
| R5 | §6 | V slot with favorite selected → favorite run line −1.5 | — |
| R6 | §6 | First meeting of season → ML/RL only | derived from schedule |
| R7 | §6 | Heavy favorite → convert to fav −1.5 (or pass) | `thresholds.heavy_fav_abs_ml`, `heavy_fav_action` |
| R8 | §4 | Veto when movement contradicts a ≥5-run blowout loss + >1.5 ERA deficit | fixed, logged as `R8_veto` |

Every pick records its terminal `rule_id`, full rationale, and a
`config_hash`, so `reports/BETTING_REPORT.md` can break results down by rule
— that's how we learn **which** sub-rules carry (or sink) the strategy.

## Alignment with the source recordings (2026-08-19)

`sports_betting_process.md` is a lossy bullet-point summary of two Zoom
training recordings ("Line Reading Training" Parts 1 & 2, June 2024,
presenter Kendrick Smith / "Ken the Millionaire", Google Drive PANTHERA
folder — see `docs/source-material.md`). The summary dropped enough detail
that the implemented engine (`pv_rules`/`pv_v2`/`pv_v3`) ended up testing a
different strategy from the one the recordings describe. Full analysis,
transcript citations, and the corrected rules live in the rewritten
`docs/sports_betting_process.md`; the short version:

- **The Mon–Sun P/V map IS stated directly** (P1 02:10, restated 99:41):
  Mon=P, Tue=V, Wed=HYBRID, Thu=V, Fri=P, Sat=V, Sun=V. The claim below (in
  the original text, kept for the record) that it "is not written anywhere"
  was wrong — the presenter states it twice, unhedged, "extremely rare...
  maybe 1% of the time" that it deviates. The 64-day-map × 2,304-config
  sweep that followed from that claim picked **VVHPPPP**, nearly the
  inverse of the documented **PVHVPVV** (Saturday and Sunday both flipped),
  on +1.40% validation ROI against −1.83% train — a sweep artifact, not a
  finding: 768 distinct hypotheses, zero positive on both splits. It ran
  live as `pv_v2`/`pv_v3` for their entire history; both are −15.6%/−29.9%
  ROI live as of 2026-08-19. The day map is a **documented constant** now
  (`config/strategy.yaml`) and is no longer swept.
- The engine was also missing: the shape-of-day slot algorithm
  (`strategy/slots.py`), a day-over-day-vs-previous-head-to-head primary
  signal with a natural-vs-scam classifier (`strategy/scam.py`) instead of
  raw movement-direction mapping, the per-day play policy (Tue/Sun totals
  primary, Thu/Sat off unless a big scam, Wed public-first-half-only,
  Vegas-days-Vegas-slots-only discipline), the "-160 or cheaper" public
  price filter, and a totals engine. The heavy-favorite rule
  (`heavy_fav_action`) was inverted from "pass" to "convert to a run line
  and bet it."
- A backtest loader bug compounded this: the sbro archives' run-line odds
  and totals prices sit in *unnamed* columns and were silently dropped, so
  every backtested run-line pick fell back to a moneyline bet. R4/R5/R7
  were never actually tested pre-2026-08-19, and the calibration that chose
  the inverted day map ran on that contaminated data.

**Resolution:** a new strategy, `pv_orig` (`strategy/orig_rules.py`,
`config/strategies/pv_orig.yaml`), implements the recordings faithfully as
a from-scratch engine rather than a patch to `pv_rules` — the two disagree
structurally and the multi-strategy protocol forbids changing a live id's
behavior in place. `pv_v2`/`pv_v3` are untouched and continue as labeled
controls; the falsification stands for THEIR engine, not for the strategy
the source material actually describes.

`pv_orig`'s own genuine unknowns (merit-score thresholds, "big scam"
magnitude — the source's read there is qualitative, "does it make sense?")
were swept honestly on a 2014–2019 train / 2021 validate split
(`backtest/calibrate.py::sweep_orig`, `reports/CALIBRATION.md`): the chosen
config (`mm2.0-mp10.0-bs100-e120`) shows +2.86% train / +2.33% validate
ROI, and — unlike the original day-map sweep — every one of the top 10
configs by validation ROI is positive on BOTH splits. Applied to
`pv_orig.yaml` 2026-08-19 (see its `meta:` block). Still noisy at n=303
validate bets (SE≈6pts) and a single validation season: a real,
stability-backed prior to confirm live, not proof.

## Data sources (all free)

| Source | Auth | Used for |
|---|---|---|
| MLB Stats API (`statsapi.mlb.com`) | none | schedule, probable pitchers + ERA, finals, meetings |
| The Odds API | `ODDS_API_KEY` (500 credits/mo free) | ML/run line/totals snapshots, 3 credits each, 3×/day |
| ESPN scoreboard API | none | backup finals for grading |
| sportsbookreviewsonline archives | none | historical open/close odds for calibration |

## Movement measurement honesty

- **Live:** movement = open (10:35 ET) → pregame (16:50) snapshots from our
  own collection. The doc's "12 PM check" (§4) was a manual mid-day glance
  at already-open lines, not a second pricing anchor any pick actually
  reads — the `midday` snapshot that mirrored it was retired 2026-08-19
  (`.github/workflows/CLAUDE.md`) since no scheduled picks run ever
  selected it as a movement endpoint; `open` → `pregame` is the real signal
  path.
- **Backtest:** only open→close exists in free archives — a coarse proxy.
  Hybrid Wednesday is untestable historically (no start times). Both
  limitations are stated in `reports/CALIBRATION.md`; forward paper-trading
  is the real test.

## Fidelity to the strategy document

Status of every data input named in §3/§5 ("evaluate recent game outcomes,
pitcher performance, and trends"), for the **incumbent `pv_rules`
(pv_v2/pv_v3) engine**:

| Doc input | Status |
|---|---|
| Pitcher performance (ERA comparison) | ✅ Implemented — probable-pitcher season ERA feeds `R3_era`, R4's evenness check, and the R8 veto |
| Recent game outcomes (previous game) | ✅ Implemented — previous-game run differential from a league-wide season context; powers the R8 veto |
| Last-10 record | ✅ Implemented — last-10 ML wins per team; `R3_form` tiebreak (ATS last-10 not tracked: historical archives lack it, so ML-only keeps live and backtest consistent) |
| Head-to-head / season series | ✅ Implemented — season-series win counts; `R3_series` tiebreak and the first-meeting flag (R6) |
| Trends *within* a series | ⚠️ Not distinguished from overall series record |
| O/U trends | ❌ Not collected; **no totals picks are generated** — deferred until the ML/RL core has a track record |
| Public vs Vegas money | ✅ Movement-inferred (R2/R3) + directly measured betting splits (Lumify), the latter observational only |
| 12 PM check / final pre-game scan | ✅ Midday + pregame snapshots |

The season context is built from one league-wide MLB schedule call per picks
run (live) and incrementally per season in backtests (strictly prior games
only — no lookahead).

**`pv_orig` (`strategy/orig_rules.py`)** closes every one of the above gaps
except two: it adds a real totals engine (`O3_totals`, gated on the
first-season-meeting exclusion), full-season W-L record, previous-opponent
strength, and ATS/cover streaks (`strategy/dossier.py`'s merit inputs) feed
`strategy/scam.py`'s natural-vs-scam classifier instead of raw movement
direction. Remaining gaps, both documented rather than hidden: (1) ATS
streaks and the previous-H2H-meeting price (the primary signal) are only
as deep as this pipeline's own captured odds history — sparse near launch,
exactly like the ERA gap below; (2) no historical starter ERA (the sbro
archives carry pitcher names, not ERAs), so ERA-dependent gates are
partly dormant in the `pv_orig` backtest the same way they were for
`pv_rules`.

### Strategy version history

Picks are segmentable by `config_hash` + `rule_id`, so eras never mix:

- **v1 (2026-08-01):** day/slot + movement + ERA fallback; R8 defined but its
  previous-game input was not populated live (it could never fire).
- **v2 (2026-08-02):** dossier completed — previous-game run differential
  (activates R8), last-10 form (`R3_form`) and season-series (`R3_series`)
  tiebreaks per doc §3/§5. Calibration re-run under the v2 engine.
- **v3 / strategy `pv_v3` (2026-08-16):** ERA actually flows. The live
  schedule hydrate had silently never returned pitcher stats (probe: actions
  run 31966193151), so `R3_era`, R4's ERA-evenness check, and the ERA half of
  the R8 veto were structurally dormant through every v1/v2 pick. Fixed via
  the `probablePitcher,person(stats(type=season))` hydrate. Behavior change ⇒
  new strategy id per protocol: `pv_v2` retired (its frozen verdict segment
  stays in the report), `pv_v3` registered with identical parameters, a
  `data_sources.era_hydrate` behavioral marker, and a fresh 100-graded-pick
  verdict clock.
- **`pv_orig` (2026-08-19):** not a `pv_rules` version — a separate engine
  (`strategy/orig_rules.py`) implementing the source recordings directly
  (day map, slot algorithm, natural-vs-scam classifier, day policy, price
  filter, totals; see "Alignment with the source recordings" above).
  Registered with a fresh clock; `pv_v2`/`pv_v3` continue unchanged as
  labeled controls.

## Verdict criteria (pre-registered)

Criteria are **per-strategy**, declared in each strategy's YAML at
registration and rendered in every ledger update — no moving goalposts.
pv_orig and pv_v3 carry the original criteria (first pre-registered 2026-07-31
for the now-retired pv_v2, whose frozen 93-pick segment remains in the ledger):
after **100 graded picks**, ROI > 0% → supported; ROI < −5% → falsified;
otherwise keep collecting. Flat $100 stakes.

## Multi-strategy framework (2026-08-17)

The pipeline runs N strategies in parallel over one shared slate (zero extra
API credits). A **strategy** = an engine (pure function
`StrategyContext -> Pick | Pass | None`, registered in
`strategy/registry.py`) + a YAML in `config/strategies/<id>.yaml` carrying
its id, scope, behavioral parameters, bet limits, and evaluation criteria.

**Lifecycle:** register (YAML committed with `registered_at`, hypothesis,
and criteria — all before the first pick) → forward-test → per-strategy
verdict or SCREEN → retire or continue as a labeled control. Evaluation
starts at registration; earlier data is an excluded exploration window.

**Segments and lineage.** `config_hash` covers only behavioral parameters
(the `strategy`/`verdict`/`screen`/`meta` blocks are excluded, so editing a
hypothesis or lineage never changes it). Each strategy declares a
`hash_lineage`: the hashes whose picks pool into its verdict. Any behavioral
change — config or code semantics (code changes must bump a hashed marker,
e.g. `bet_limits.cap_semantics`) — produces a new hash outside the lineage,
and those picks render as a separate SCREEN segment with fresh counters.
A verdict-eligible successor requires a new strategy id.

**Worked example (the cap fix):** the original per-invocation daily cap let
morning+pregame runs place 7–8 picks/day vs the configured 6 on 4 of the
first 15 live days. The per-day fix is a declared behavior change: pv_v2's
verdict prints on the pre-fix segment only (`hash_lineage: [6f0d0924d4]`),
and post-fix picks form a SCREEN segment. Proofs: replaying the per-day cap
over the live ledger drops exactly 6 picks worth +$285.19
(`docs/proofs/cap-delta.md`); the refactor itself is behavior-identical on
replayed slates (`docs/proofs/refactor-identity.md`).

**Evaluation honesty** (printed in the ledger header): per-strategy SE from
that strategy's own realized SD; both nulls stated (zero-edge and
pays-the-vig); a 0% SUPPORTED bar is a 50% coin flip at any n, and even the
forward-test template (n=300, +2%/−5%) has 37%/21% false-print rates under a
zero-edge null with 50% power against a true +2% edge — paper-ROI verdicts
are screens by nature; replication and CLV direction are the corroborating
instruments. **Registration budget:** at most 2 new forward_test strategies
per season beyond the launch set (registering k null strategies at the +2%
bar gives P(≥1 false SUPPORTED) ≈ 1−0.63^k — 75% at k=3). Splits strategies
run under a pre-registered credit-budget stopping rule with SCREEN-only
evaluation; extending a budget after seeing interim results permanently
downgrades the strategy to exploratory.

**Launch set:** `pv_v2` (retired control), `pv_v3` (incumbent control,
ERA-active), `pv_orig` (aligned engine, registered 2026-08-19 — see
"Alignment with the source recordings" above), `fav_ml` (live vig-anchor
baseline, uncapped by design), `dog_ml` (backtest-only baseline),
`sharp_split` + `fade_public` (splits forward-tests, disabled until their
volume-rule thresholds are set on post-fetch-fix data — see their YAMLs).
Explicitly rejected: registering any further sweep-derived P/V *day-map*
variant as a "winner" for the `pv_rules` engine (that sweep is retired; the
day map is now a documented constant, not a calibrated unknown — see
above).
