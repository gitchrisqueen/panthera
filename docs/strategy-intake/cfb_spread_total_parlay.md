# Intake: `cfb_spread_total_parlay` (college football)

**Status:** **registered 2026-10-05** as a SCREEN-only forward test
(`config/ncaaf_strategies/cfb_spread_total_parlay.yaml`, engine
`src/panthera_mvp/ncaaf/parlay.py`, runs in `.github/workflows/ncaaf.yml`,
reports to `reports/NCAAF_REPORT.md`). Live once the PR merges to `main`.
The author's round-2 answers (via their assistant, Muse, on issue #55's
questionnaire) are mapped below; four ticket-building answers are still
`UNKNOWN` and run on labelled proxies.

The raw exports are **not committed**; the numbers they contain are, in the
strategy YAML.

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

## Round 3 (sent 2026-10-05): remaining questions

Posted at the top of issue #55, which is now locked: comments are closed, so
nobody can post instructions the author's assistant might follow. Rounds 1–2
are collapsed and marked answered. The 12 questions cover the four ticket
proxies, rivals, injuries beyond QB-out, the moneyline trigger, stake and
sportsbook, why the Oct 3 card wasn't placed, which angle picked each Oct 3
leg, more history, and best days.

Each question is asked open-ended first; Panthera's proxy is shown only
after the author answers, and a bare "accept" is recorded as `ECHO` (round 1
failed by echoing the suggested numbers back as answers). Answers come back
privately to Christopher (template `schema_version: "1.0-round3"`).

**Pre-committed decision, 2026-10-18.** Whether to register
`cfb_spread_total_parlay_v2` is decided on that date from the round-3 answers
alone, never from how v1's live tickets are doing (deciding after watching
results is peeking). A v2 uses the last forward-test slot of the 2026 budget
(`docs/mvp-design.md`). v1 keeps running unchanged either way.

## Round 2 answers (2026-10-04) -> the strategy YAML

| Author's answer | In the YAML | Status |
|---|---|---|
| Any day with games; decide 60 min before the earliest leg's kickoff | `decision.minutes_before_first_kickoff: 60`; hourly cron with a ±30 min window | AUTHOR |
| Best available line | best point, then price, among the snapshot's US books; signals read the median line | AUTHOR + proxy detail |
| S1 spread move ≥ 1.5, with the move | `signals.line_move_spread`; "open" = the first Panthera snapshot that priced the game | AUTHOR (ACCEPT) |
| S2 total move ≥ 2, with the move | `signals.line_move_total` | AUTHOR (ACCEPT) |
| S3 letdown: beat a ranked team **or rival**, favored by 10+ → other side | `signals.letdown`; "last week" = the previous game within 15 days | AUTHOR; **rival half dropped** (no data) |
| S4 look-ahead: ranked opponent next, favored by 10+ → other side | `signals.look_ahead` | AUTHOR (ACCEPT) |
| S5 outdoor, wind ≥ 15 mph at kickoff → under | `signals.weather_wind_under` (Open-Meteo at CFBD venue coordinates) | AUTHOR (ACCEPT); needs `CFBD_API_KEY` |
| S6 SP+ vs spread ≥ 4 (HFA 2.5) → SP+ side | `signals.sp_plus_edge` | AUTHOR (ACCEPT); needs `CFBD_API_KEY` |
| S7 starting QB out → skip game | `signals.qb_out_skip: {enabled: false}` | **dropped** (no free injury feed) |
| One angle is enough; opposite angles → skip the game | `legs.min_signals: 1`, `legs.conflict: skip_game` | AUTHOR |
| Moneyline legs -300 to -150, alongside the spread leg | `legs.moneyline_legs: false` | AUTHOR accepted, but gave no trigger for *when* → never added |
| Min/max legs | `ticket.legs_per_ticket: 3` | **PROXY** (UNKNOWN; both cards shown were 3 legs) |
| +600 to +1000 hard or target | target, recorded as `in_band` | **PROXY** (UNKNOWN) |
| Which legs when too many qualify | most signals, then earliest kickoff | **PROXY** (UNKNOWN) |
| Two legs from one game | no (`legs.same_game_legs: false`) | **PROXY** (UNKNOWN) |
| Flat $50–100 per ticket | `staking.flat_stake: 100` | AUTHOR range; $100 ledger convention |
| Max 1 ticket a day; skip the day after a loss | `bet_limits` | AUTHOR |

Still unknown and worth asking the author: the four proxies above, why the
Oct 3 morning card wasn't placed, and which angle picked each leg of the
two known cards. Their past tickets can't be replayed through the engine
until those are known. Changing any behavioral value after the first live
ticket needs a new strategy id (protocol), so answers that change a proxy
should land **before** the PR merges.

**What the forward test measures.** Tickets are SCREEN only: at ~+600 the
per-ticket SD is ~2.3× the stake, so SE(ROI) is still ~33 points at 50
tickets. Every qualifying leg (on the ticket or not) is graded and reported
per signal against the -110 breakeven (52.4%); that is the faster, partial
read on which angles carry the method.

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

## Round 2: how the answers were collected

The answers live in the author's head, not in the chat history, so the
assistant can't fill them in alone.

**In use (2026-10-04):** the author's assistant is Muse, not ChatGPT. The
full questionnaire, interview rules and answer template are posted as a
public issue Muse can read directly:
[#55](https://github.com/gitchrisqueen/panthera/issues/55). Answers come back
as a comment on #55 or privately to Christopher. The two options below are
fallbacks. **Option A is recommended** if the issue route stalls.

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
