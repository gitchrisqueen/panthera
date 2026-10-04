# Intake: `cfb_spread_total_parlay` (college football)

**Status:** not registered. Export received 2026-10-04. Panthera can't
register it yet because both rules are `discretionary: true` and timing,
staking and limits are all `UNKNOWN`. The follow-up came back the same day
with **no answers** (see "Follow-up round 1" below). The NCAAF data plumbing
is built so the engine can be written as soon as real answers arrive.

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

1. Get real answers using Round 2 below (option A, the direct questionnaire,
   is recommended). Paste the reply into the session.
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

## Follow-up round 1 (2026-10-04): returned unanswered

The author's assistant sent back the follow-up YAML with every timing,
signal, ticket, staking and limit field set to `UNKNOWN`. `still_unknown`
is just the 11 questions restated. It skipped the interview. The old
follow-up prompt said both "ask me the questions one at a time first" and
"Output **only** this YAML". The assistant obeyed the second line, so the
author was never asked anything. The `[600, 1000]` price band and
`[-300, -150]` moneyline range in the reply are the prompt's own proposals
echoed back, not answers.

The one new fact is a second card from 2026-10-03, built in the morning but
**not placed**: Auburn/Tennessee Under 54.5, Iowa +14.5 vs Ohio State, BYU
-6.5 vs TCU. It shows totals and underdog-spread legs in practice, and BYU
-6.5 also appears on the placed ticket. It isn't a bet, so it can't be graded
as one. Ask why it wasn't placed, because that answer is a skip rule.

## Round 2: getting the answers

The answers live in the author's head, not in the chat history, so the
assistant can't fill them in alone. There are two ways to get them.
**Option A is recommended.**

### Option A: send the author the questions directly

Text the questionnaire below to the author. Short answers are fine, and so is
"don't know". Paste the reply into a Panthera session, and Claude writes the
follow-up YAML from it.

====================== COPY FROM HERE ======================

Quick questions so my system can paper-trade your college football parlays
exactly the way you bet them. Short answers are fine, and "don't know" or "it
depends" is a real answer. For each suggested rule, reply **yes**, **no**, or
give your own number.

1. **When:** Saturdays only? What time do you lock the ticket (for example,
   1 hour before the first kickoff)? Which sportsbook's lines do you use?
2. **Line moves:** Suggested rule: a spread move of 1.5+ points (or a total
   move of 2+) since open, and you bet with the move. Yes / no / your number?
   Do you ever bet against a move? Do you look at ticket % vs money %?
3. **Letdown:** Suggested rule: a team that beat a ranked team or rival last
   week and is favored by 10+ this week, so you take the other side. Yes / no
   / your numbers?
4. **Look-ahead:** Suggested rule: a team with a ranked opponent next week
   that is favored by 10+ this week, so you take the other side. Yes / no /
   your numbers?
5. **Weather:** Suggested rule: an outdoor game with wind of 15+ mph, so the
   under is in play. Yes / no / your number? Do rain or cold matter?
6. **Metrics:** Which ones do you use (SP+, FPI, EPA, something else)?
   Suggested rule: the rating disagrees with the spread by 4+ points, so you
   take the side the rating likes. Yes / no / your number?
7. **Injuries:** Suggested rule: if the starting QB is out, you skip that
   game. Yes / no? Anything finer than that?
8. **Combining:** How many of those reasons does a game need before it makes
   the ticket? What if two reasons point opposite ways?
9. **Ticket:** How many legs (min and max)? Is +600 to +1000 a must, or just
   a target? If too many games qualify, which do you keep? Can you take
   spread + total from the same game?
10. **Moneyline legs:** Only at -150 to -300, and only on a team you already
    have on the spread? Does it replace that spread leg or go alongside it?
11. **Money:** How much per ticket? Most tickets in a Saturday? When do you
    skip a Saturday entirely? Why didn't you place the Auburn-under / Iowa
    +14.5 / BYU card on Oct 3?
12. **History:** Every CFB parlay you remember, **losses too**: date, legs
    with lines, price, result, and why you picked each leg. Five or more
    would be great.

======================= COPY TO HERE =======================

### Option B: run it through the author's assistant in two steps

Use this if the author prefers to answer inside the same chat. **Step 1**
forbids YAML, so the assistant has to ask. **Step 2** is sent only after
every question has an answer.

**Step 1: paste into the author's chat**

====================== COPY FROM HERE ======================

Your last follow-up YAML came back all UNKNOWN because you never asked me
the questions. The answers aren't in this chat; they're in my head. Let's
fix that.

**Do not write any YAML in this reply or the next ones until I type "WRITE
THE YAML".**

Interview me instead. Ask the 11 questions from the `still_unknown` list
in your last reply **one at a time**, in order. For each one that has a
proposed rule, tell me the proposal and ask me to reply ACCEPT, REJECT,
or CHANGE with my own number. Wait for my answer before the next question.
If my answer is vague ("it depends", "when it feels right"), ask one
follow-up that turns it into a number. If I still can't give one, record it
as UNKNOWN and move on. Don't invent an answer for me. For question 11
(history), also ask why I didn't place the Oct 3 card (Auburn/Tennessee
Under 54.5, Iowa +14.5, BYU -6.5).

Start with question 1 now.

======================= COPY TO HERE =======================

**Step 2: paste after the last answer**

====================== COPY FROM HERE ======================

WRITE THE YAML. Fill in this schema using **only** the answers I gave in
this interview. Use UNKNOWN wherever I said I didn't know, and copy each
ACCEPT / REJECT / CHANGE verdict exactly. Output only the YAML block.

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
