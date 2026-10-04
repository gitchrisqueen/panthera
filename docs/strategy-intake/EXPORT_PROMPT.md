# Strategy Export Prompt

A copy-paste prompt that gets a betting strategy **out of someone else's AI
chat** (ChatGPT, Claude, Gemini, …) as a structured spec Panthera can register
and paper-trade. Written 2026-09-27 to replace a lost earlier version.

## How to use it

1. Send the person everything between the two `====` lines below. They paste it
   into **the same chat session that holds their strategy**, so the assistant
   can draw on the conversation history.
2. The assistant asks them clarifying questions first. They answer, and then it
   produces one fenced `yaml` block (the **Strategy Export**).
3. They send that block back to you. Save it as
   `docs/strategy-intake/<strategy_id>.export.yaml` (only if they agree it can
   go in this **public** repo; otherwise keep it outside git).
4. Intake into Panthera (a Claude session can do this from the export):
   - Check `unanswered_questions` and every `UNKNOWN` and `discretionary: true`
     item. Get each one resolved or replaced by a mechanical proxy before
     registering. An engine can't run a rule that reads "use your gut".
     If nearly every field is `UNKNOWN`, the assistant skipped the interview.
     Don't send a follow-up that says both "ask me first" and "output only
     YAML", because the assistant obeys the second part. Ask the person
     directly, or use a two-step prompt where YAML is forbidden until every
     answer is in (see `cfb_spread_total_parlay.md`, Round 2).
   - Map each `inputs[]` entry to a field Panthera already has (see the table
     in the prompt). Anything marked `available_in_panthera: no` needs a new
     client plus fixtures, or the rule is dropped. Record which one you chose.
   - Write the engine in `src/panthera_mvp/strategy/` and register it in
     `strategy/registry.py`. Add `config/strategies/<id>.yaml` with every
     threshold from the export and a `hypothesis` taken from `thesis`. Set
     `kind: forward_test`, `registered_at`, and pre-registered `verdict` /
     `screen` criteria **before the first pick**. Mind the registration
     budget in `docs/mvp-design.md`: at most 2 new forward tests per season.
   - Turn the export's `worked_examples` into unit tests on fixtures. If the
     engine doesn't reproduce the person's own decisions, the translation is
     wrong.
   - Add any new rule ids or terms to `config/glossary.yaml`.

## Why it's shaped this way

- **One mechanical rule per line with numeric thresholds.** Panthera's engines
  are pure functions over snapshot data. Vague rules ("sharp money",
  "value") have to become a number or a field before they can run.
- **UNKNOWN beats invention.** An assistant asked to "export the strategy" will
  happily fill gaps with plausible-sounding rules. That tests *its* strategy,
  not the person's. The prompt forbids guessing and makes it list the gaps.
- **Worked examples.** Real past bets with the reasoning are the only way to
  check that the rules as written are the rules as practiced.
- **Claimed track record kept separate.** The person's reported results are
  context, not evidence. Panthera's own forward test is the evidence.
- **Sport-agnostic.** Panthera runs MLB today, but the schema works for any
  sport. The `available_in_panthera` flags show what can be tested now.

---

====================== COPY FROM HERE ======================

I want to export the sports-betting strategy we've worked on in this conversation into a precise, machine-readable spec. A friend is going to paper-trade it automatically to test it: their system takes odds snapshots several times a day, applies the rules mechanically, grades every pick after the game, and tracks ROI and closing-line value. Nothing is placed with real money. For this to work, the export has to describe the strategy **as I actually use it**, precisely enough that a program can make the same bet I would, or pass when I'd pass.

**Ground rules (please follow them strictly):**

1. Use only what I've told you in this conversation and what I tell you now. **Do not invent, "improve", or fill in rules.** Where something is missing or vague, write `UNKNOWN` and add it to `unanswered_questions`. Don't guess.
2. Keep what I *do* separate from *why* I think it works. Rules go in `rules`; beliefs and reasoning go in `thesis` and `rationale`.
3. Every rule has to be mechanical: a condition over data that a program could check, with explicit numbers (for example "moneyline between -120 and +120", not "evenly matched"). If a step depends on my judgment, mark it `discretionary: true`, describe how I actually decide, and propose a mechanical proxy for me to confirm or reject.
4. Use American odds, US/Eastern times, and state which sportsbook or consensus line the rule reads when it matters.

**Step 1: interview me first.** Before writing the export, read back your understanding of the strategy in 5–10 plain bullets. Then ask me **up to 10** targeted questions about the biggest gaps, especially:
- Which sport(s) and leagues, and which markets (moneyline, run line or spread, totals, props, live).
- *When* I make the decision (morning, an hour before first pitch, at close?) and which line I compare against (opening, yesterday's, current).
- The exact thresholds: price ranges, line-movement sizes, percentages, and the stats I use with their cutoffs.
- When I pass. What makes me skip a game or a whole day?
- How much I bet (flat, units, confidence-scaled, Kelly) and my limits (max bets per day, one per game, correlated bets).
- Conflicts: what wins when two rules point opposite ways.
- Data I look at that isn't odds (pitchers, injuries, weather, public betting %, trends, rest, travel) and where I get it.

Wait for my answers. Then do Step 2.

**Step 2: produce the export.** Output **one** fenced code block, language `yaml`, following this schema exactly. Keep every key. Use `UNKNOWN` or `[]` for missing values, and add no keys outside the schema except under `notes`.

```yaml
schema_version: "1.0"
exported_at: "YYYY-MM-DD"
exported_by: "assistant name and model, if known"
strategy:
  id: "short_snake_case_name"          # e.g. "reverse_line_dog"
  name: "Human-readable name"
  author: "who created it"
  sport: ["MLB"]                      # list; leagues/sports it applies to
  markets: ["moneyline"]              # moneyline | run_line | spread | total | prop | live
  status: "in use | retired | idea"
  thesis: >
    One paragraph: what market inefficiency this exploits and why the edge
    should exist.

timing:
  decision_time_et: "e.g. 10:30 and again 30 min before first pitch"
  line_compared_against: "opening | previous day | earlier snapshot | UNKNOWN"
  line_source: "consensus / specific book / UNKNOWN"
  bet_placed_at: "when the bet is actually placed relative to the decision"

inputs:                                # every data point any rule reads
  - name: "home_ml_open"
    description: "Home moneyline at market open"
    source: "where I get it"
    timing: "when it's captured"
    available_in_panthera: "yes | no | partial"   # see table below

eligibility:                           # filters applied before any rule
  - id: "E1"
    condition: "precise, checkable condition"
    action: "skip game | skip day"

rules:                                 # ordered; first match wins unless stated
  - id: "R1"
    priority: 1
    description: "plain-English summary"
    condition: "precise boolean logic using names from inputs, with numbers"
    action:
      market: "moneyline | run_line | spread | total | pass"
      side: "home | away | favorite | underdog | over | under | team whose line moved toward it ..."
      line: "e.g. -1.5, or null"
      price_limit: "don't bet if worse than X, or null"
    stake_units: 1
    discretionary: false
    mechanical_proxy: null             # required when discretionary: true
    rationale: "why I think this rule works"

conflict_resolution: "what happens when rules disagree or several fire on one game"

staking:
  method: "flat | units | confidence-scaled | kelly | other"
  unit_definition: "e.g. 1% of bankroll, or $100"
  details: "any scaling rules"

limits:
  max_bets_per_day: UNKNOWN
  one_bet_per_game: UNKNOWN
  other: []

pass_conditions:                       # when no bet is made, beyond eligibility
  - "condition"

worked_examples:                       # 3–10 REAL past decisions, bets AND passes
  - date: "YYYY-MM-DD"
    game: "Away @ Home"
    lines_seen: "open/current prices I looked at"
    other_data: "pitchers, stats, % etc. I used"
    decision: "bet X at price Y | pass"
    rule_ids: ["R1"]
    result: "win | loss | push | n/a"
    source: "from this conversation | recalled by me"

claimed_track_record:                  # what I report; the test will verify it independently
  period: "UNKNOWN"
  bets: UNKNOWN
  record: "W-L-P or UNKNOWN"
  roi_pct: UNKNOWN
  how_tracked: "spreadsheet / memory / app / UNKNOWN"

known_weaknesses: []                   # situations where I know it struggles
unanswered_questions: []               # every gap you could NOT resolve
notes: ""                              # anything that doesn't fit above
```

**Data the paper-trading system already has (MLB),** used to fill `available_in_panthera`:

| Available now | Details |
|---|---|
| Moneyline odds | consensus home/away price at open (~10:35 ET), pregame (~16:50 ET), and close; line movement between them |
| Run line (±1.5) and totals | price and point, open and latest |
| Game info | date, start time ET, home/away, day of week, doubleheaders |
| Probable starting pitchers | season ERA for each starter |
| Team form | last-10 record, season W-L, standings rank, current series record, previous game's run differential, previous opponent's rank, ATS/cover streak, first meeting of the season |
| Public betting splits | % of tickets and % of money (handle) on each moneyline side, morning and pregame |

Not available yet (mark `no`): injuries and lineups, weather, umpires, bullpen usage, advanced stats (xFIP, wRC+, etc.), player props, live/in-game odds, specific-sportsbook lines (only a consensus line), and anything from a paid service. It's fine for the strategy to need these. Just flag them honestly.

**Step 3: self-check.** After the yaml block, list: (a) every rule you marked `discretionary`, (b) every `UNKNOWN`, and (c) anything in the export that I didn't explicitly tell you, which should be nothing. Then ask me to confirm the export matches how I really bet.

======================= COPY TO HERE =======================
