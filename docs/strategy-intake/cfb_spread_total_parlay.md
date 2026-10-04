# Intake: `cfb_spread_total_parlay` (college football)

**Status:** not registered. Export received 2026-10-04. Panthera can't
register it yet because both rules are `discretionary: true` and timing,
staking and limits are all `UNKNOWN`. The NCAAF data plumbing is built so the
engine can be written as soon as the follow-up below comes back.

The raw export is **not committed**. The author hasn't yet agreed to it
going into this public repo (step 3 of `EXPORT_PROMPT.md`).

## What the export says (summary)

- **Sport / markets:** NCAAF spreads and totals, combined into parlays
  priced around +600 to +1000. Moneyline legs are allowed only when "highly
  probable" and on the same team as a spread leg on the ticket (R1).
- **Leg selection (R2):** judgment over five angles. These are line
  movement / sharp money, situational spots (letdown / look-ahead), weather,
  advanced efficiency metrics, and injury reports.
- **Worked example (only one):** 2026-10-03, a 3-leg ticket: BYU -6.5,
  Miami -15.5, Texas Tech -13.5, about +600, reported as a win. Three -110
  legs come to +596, which matches. `tests/test_ncaaf.py` replays it
  end to end on synthetic finals.
- **Track record:** 1 ticket. This is context, not evidence.

## Input mapping (`available_in_panthera` after the plumbing)

| Export input | Source now in Panthera | Live | Backtest |
|---|---|---|---|
| line_movement | Odds API NCAAF snapshots (`ncaaf snapshot`, open → pregame → close); CFBD `/lines` `spreadOpen` → `spread` | yes (3 cr/snapshot) | yes (CFBD, open/close only) |
| sharp money (splits) | Lumify is MLB-only in Panthera today | no | no |
| situational_spot | ESPN rank + CFBD schedule (previous/next opponent, rank, result) | yes | yes |
| weather | Open-Meteo kickoff hour by venue lat/lon (CFBD `/venues`, dome flag) | yes | yes (archive API) |
| advanced_metrics | CFBD SP+ (overall / offense / defense) | yes | yes |
| injury_report | none found that is free and structured | no | no |

## Path to registration

1. Send the follow-up prompt below to the author's chat. Paste the YAML it
   returns into the session.
2. Turn each answered threshold into a field in
   `config/strategies/cfb_spread_total_parlay.yaml`. Drop or replace any rule
   that stays judgment-only. Note which inputs were dropped (injuries and
   splits are likely candidates).
3. Write the engine in `src/panthera_mvp/strategy/` (inputs: game, lines,
   SP+, schedule context, weather; output: zero or more tickets). Every
   worked example must reproduce the author's ticket.
4. Backtest on CFBD seasons (`ncaaf cfbd-pull --seasons 2015-2025`). Price
   each leg at -110 unless the history has prices. Then pre-register the
   verdict and screen thresholds, set `kind: forward_test`, and run the
   remaining 2026 Saturdays.
5. Budget: this uses 1 of the 2 new forward-test slots allowed per season
   (`docs/mvp-design.md`).

---

## Follow-up prompt for the author's assistant

Paste everything between the markers into the same chat that produced the
export.

====================== COPY FROM HERE ======================

Thanks, the export was clear. My friend's system tests strategies by
running the rules mechanically and paper-trading every pick. Right now
nothing in the export can run that way, because both rules are judgment
calls and timing, staking and limits are UNKNOWN. I need a follow-up that
turns my judgment into numbers. Same ground rules as before:

- Answer for how I **actually** bet. Don't invent a rule I don't use. If I
  haven't told you, write `UNKNOWN` and ask me. Better still, ask me the
  questions one at a time first, then write the YAML.
- Every threshold must be a number a program can check. For example, "spread
  moved 1.5+ points toward the side between open and kickoff" works. "Sharp
  money is on it" does not.
- Where I offer a proposed rule below, mark it `ACCEPT`, `REJECT`, or
  `CHANGE: <my version>`. Don't accept on my behalf.
- If a proposed rule is close but wrong, change the number. Don't reject the
  whole idea.

Questions (the proposed rules are suggestions to react to, not my answers):

1. **Timing.** On which day(s) and at what time (ET) do I pick legs and
   place the ticket? Which line do I read: a specific sportsbook (which one?)
   or the best available? Proposal: Saturday games only, decided about 1 hour
   before the earliest leg's kickoff, using DraftKings lines.
2. **Line movement / sharp money.** What counts as a signal? Proposal: the
   spread moved at least 1.5 points (or the total at least 2 points) between
   the opening line and the decision time, and I bet *with* the move. Do I
   ever bet *against* a move? Do I use ticket% vs money% splits? If so, give
   the cutoff (for example, money% minus ticket% at least 15 on the same side).
3. **Situational spots.** Define letdown and look-ahead with numbers.
   Proposal: *letdown* means the team beat a ranked opponent or a rival last
   week and is favored by 10+ this week, so fade them or take the underdog
   spread. *Look-ahead* means the team plays a ranked opponent next week and
   is favored by 10+ this week, so fade them. Which direction does each spot
   push me?
4. **Weather.** When does weather make me bet a total? Proposal: at an
   outdoor stadium, wind of 15+ mph at kickoff means the under is
   eligible. Do rain or cold matter, and at what levels?
5. **Advanced metrics.** Which metrics exactly, and with what cutoffs? Panthera
   has SP+ ratings (overall, offense, defense). Proposal: the SP+ rating
   difference (adjusted ~2.5 points for home field) disagrees with the spread
   by 4+ points, and I take the side SP+ favors. If I use something else
   (EPA/play, success rate, FPI), name it and give the cutoff.
6. **Injuries.** Which injuries change a decision? Proposal: if a team's
   starting QB is ruled out, skip any leg on that game. If I use injuries for
   anything finer, describe it. Note that injury data is the hardest to
   automate and may be dropped from the test.
7. **Combining angles.** How many angles must agree before a game becomes a
   leg (1? 2? weighted?)? What happens if two angles point opposite ways on
   the same game?
8. **Building the ticket.** How many legs (min and max)? Must the combined
   price fall within +600 to +1000, or is that only a target? When more legs
   qualify than I need, which do I keep (strongest signal, earliest
   kickoff)? Can two legs come from the same game (spread + total)?
9. **Moneyline exception (R1).** Accept or reject: a moneyline leg is allowed
   only at -300 to -150, and only on the same team as a spread leg already
   on the ticket. If accepted, does it replace that spread leg or sit
   alongside it?
10. **Staking and limits.** How much per ticket (flat units? how much is one
    unit?) and how many tickets per Saturday at most? When do I skip a whole
    day?
11. **More history.** List every college-football parlay I've told you
    about, **including losses**, with the date, each leg and its line, the
    price, the result, and which rule picked each leg. Five or more tickets
    would be ideal. Losses matter as much as wins for checking the rules.

Output **only** this YAML, with no prose before or after it:

```yaml
schema_version: "1.0-followup"
strategy_id: "cfb_spread_total_parlay"
answered_at: "<YYYY-MM-DD>"
timing:
  game_days: []            # e.g. ["Sat"]
  decision_time_et: ""     # e.g. "60 minutes before first leg kickoff"
  line_source: ""          # book name, or "best available"
signals:                   # one entry per angle; drop ones I don't use
  - id: "S1"
    angle: "line_movement" # line_movement | splits | letdown | look_ahead | weather | metrics | injury
    market: "spread"       # spread | total
    condition: ""          # numeric, e.g. "abs(close_spread - open_spread) >= 1.5"
    direction: ""          # which side it picks, e.g. "side the line moved toward"
    proposal_verdict: ""   # ACCEPT | REJECT | CHANGE: ...
leg_qualification: ""      # e.g. ">= 2 signals agree on the same side; any conflict = skip game"
ticket:
  min_legs: UNKNOWN
  max_legs: UNKNOWN
  price_band_american: [600, 1000]
  price_band_is_hard_rule: UNKNOWN
  selection_when_too_many_legs: ""
  same_game_legs_allowed: UNKNOWN
moneyline_exception:
  proposal_verdict: ""     # ACCEPT | REJECT | CHANGE: ...
  price_range: [-300, -150]
  replaces_spread_leg: UNKNOWN
injuries:
  rule: ""
staking:
  stake_per_ticket_units: UNKNOWN
  unit_definition: ""
limits:
  max_tickets_per_day: UNKNOWN
  skip_day_conditions: []
history:
  - date: ""
    legs: []               # e.g. ["BYU -6.5 (-110)", "Miami -15.5 (-110)"]
    ticket_price: ""
    result: ""             # win | loss | push
    signal_ids_per_leg: [] # which S-ids picked each leg
    source: ""             # "from this conversation" | "user stated"
still_unknown: []          # anything I couldn't answer
```

======================= COPY TO HERE =======================
