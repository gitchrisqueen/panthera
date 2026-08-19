# The Sports Betting Process — "Line Reading Training"

Faithful transcription of the source recordings (see `docs/source-material.md`
for provenance). Rewritten 2026-08-19 from the transcripts directly — the
previous version of this file was a lossy bullet-point summary that dropped
enough detail to send the implementation off in the wrong direction (see
`docs/mvp-design.md`'s "Alignment with the source recordings" section for
the measured impact). That old text is kept verbatim in the Appendix at the
bottom, marked as superseded.

Citations are `[mm:ss]` timestamps: **P1** = `notes/GMT20240619-014815/transcript.txt`,
**P2** = `notes/GMT20240627-021203/transcript.txt`.

## §1. Vocabulary

- **Public (P) day/slot** vs. **Vegas (V) day/slot**: which "camp" the line
  is being moved for/against. [P1 01:40]
- **Run line**: MLB's spread, almost always ±1.5 (unlike NBA-scale spreads),
  "because the spread is so small... we really have to dive into reading
  the lines." [P1 17:28-18:05]
- **ERA** (earned run average): runs a pitcher allows per 9 innings — lower
  is better. [P1 16:39]
- **Line movement, "cheaper" vs. "more expensive"**: American odds getting
  MORE negative (e.g. −160 → −180) = the price is getting **more
  expensive** to bet (put down more to win the same $100); getting LESS
  negative or moving toward/through positive = getting **cheaper**.
  [P1 18:47-20:00] Concretely: "if it opens up at minus 160, you want to
  see that... minus 165, minus 170... that's the type of movement you want
  to see when it comes to a public slot" (getting more expensive = public
  money piling in). [P1 19:02-19:32]

## §2. The weekly public/Vegas/hybrid schedule

Stated directly, twice, unhedged:

> "Mondays and Fridays are going to be public days... Tuesday is going to be
> a Vegas day. Wednesday is going to be a hybrid day. Thursday is going to
> be a Vegas day... Friday typically payday for majority of people, so it's
> also a very easy day similar to Monday, and then the weekend — majority of
> people are at home all weekend... both Saturday and Sunday are both going
> to be Vegas days." [P1 02:10-04:22]

Restated in the live walkthrough: "Monday, public day. Tuesday, Vegas day.
Wednesday, hybrid day. Thursday, Vegas day. Friday, public day. Saturday and
Sunday, Vegas days." [P1 99:41-99:53] And on deviations: "extremely rare...
maybe 1% of the time." [P1 112:21-112:30]

| Day | Type |
|---|---|
| Monday | Public |
| Tuesday | Vegas |
| Wednesday | Hybrid |
| Thursday | Vegas |
| Friday | Public |
| Saturday | Vegas |
| Sunday | Vegas |

**Psychology** (paraphrased, [P1 02:45-04:27]): Monday, bettors are back
from the weekend chasing easy money — books let them win. Tuesday, "Vegas
takes the bread back." Wednesday splits: early games (people at work) stay
easy; late games (people home, focused) get hard. Thursday is one of the
hardest days of the week. Friday is payday — easy again. The weekend, people
are home all day looking to make money, so Vegas collects again.

### Slot assignment within a day

Within one calendar day, distinct start times form ordered "slots." The
rule (implemented in `strategy/slots.py`):

1. Group the day's games by distinct start time.
2. **The first slot of the day is the inverse of the day type.**
   [P1 05:23, 08:38, 10:34]
3. Every other slot inherits the day type...
4. ...**except a slot with 2 or more games at the same start time, which
   flips to the inverse** for that slot only, then the next slot reverts.
   [P1 05:53-06:23, 09:18]
5. **The last slot of the day is the inverse of whatever the previous chunk
   was.** [P1 06:47, 09:39]

> "If it's a public day, the first time slot is going to be Vegas... After
> that, the rest is going to be public unless there's a specific time slot
> that has two or more games in it... the last slot will be inverse from
> whatever chunk was previously." [P1 05:23-06:47]

### Hybrid Wednesday

Two halves, split at **5 PM CST = 6 PM (18:00) ET** — the presenter works in
CST throughout and even converts a 12:20 PM ET game to "11:20 AM" on
screen [P1 571-578]:

> "On a hybrid day, the first time slot of the day is going to be Vegas.
> After you switch from that first time slot, then... it switches to
> public... [at] halftime... after that, the games are going to be Vegas."
> [P1 10:34-13:44]

The **halftime boundary itself is not an inversion point** — only the
day's global first slot (pre-halftime) and global last slot (post-halftime)
get inverted; the first slot right after halftime inherits Vegas directly.
Confirmed in the live walkthrough: "we got Vegas at 11:20am... [pre-halftime,
no doubles] all of that's going to be public... [post-halftime, no doubles]
all of that's going to be Vegas... last slot always inverse of the previous
chunk." [P1 104:57-108:38]

### Per-day play policy (P2)

A second-layer refinement on top of the schedule, from ~a month of testing:

> "On Mondays... the Monday moneyline spread picks, that's primarily what I
> focus on... Tuesday, my top play... was over-under, that's the primary
> thing you should be looking for, and then a moneyline and spread scam
> secondary... Wednesday... pretty much like public slots the first half of
> the day... Thursday... I found out for me personally that Thursday and
> Saturday can be two of the most weirdest days. Vegas is out for blood...
> take either the day off, or... only touch it if it's a big scam."
> [P2 02:22-03:53]

| Day | Type | Policy |
|---|---|---|
| Mon | P | Moneyline & spread; primarily public slots |
| Tue | V | **Totals primary**, moneyline/spread scam secondary |
| Wed | HYBRID | Public slots, first half only; never the day's first (Vegas) slot; 2nd-half Vegas slot only on a big scam |
| Thu | V | **Off** unless an obvious big scam (game-3/4 trend-breaker) |
| Fri | P | Same as Monday (game 1 of series) |
| Sat | V | **Off** |
| Sun | V | Moneyline/spread or totals trend-break |

Slot discipline, stated directly: "if it's a Vegas day, do not touch a
public slot... Vegas days, Vegas slots only... on public days... primarily
focus on the public slots, but it's okay to touch a little Vegas scam here
and there if it makes sense" — but only if it's "outrageous," not "a little
light scam." [P2 19:05-19:48, 12:07-12:25]

## §3. The "skeleton" pre-pick checklist

> "Number one, I always like to look at is the previous game lines and the
> outcome... Then I'm going to look at the current game lines... you want to
> do a record comparison... the ERA comparison... a head-to-head [and]
> season series analysis... Action Network's situational results — moneyline
> and spread, last 10, home/away, favorite/underdog." [P1 23:19-26:19]

Tools: **Action Network** for odds/trends/situational splits; **MLB.com**
for the most current records; **scoresandodds.com** for historical odds
when head-to-head data from the current season is sparse. [P1 24:11,
81:55-83:21]

## §4. The core signal — line movement vs. what actually happened

Two distinct comparisons, not one:

- **Primary: today's price vs. the same team's price in the previous
  head-to-head meeting** (usually the prior game of the same series).
  Every worked example leads with this — e.g. "the Red Sox, their money
  line got 28 points cheaper" [P1 33:20], "a hundred point cheaper drop"
  [P1 46:59], "110-point difference" [P1 50:34], Guardians "−102 → +130 →
  +195" across three straight days [P2 05:33-08:11].
- **Secondary/confirming: today's own intraday movement**, open price vs.
  current. Concrete trigger: "I typically like to see at least like five
  points paying less in public... if it's five plus, I'm usually good to
  go," checked again ~30-60 minutes before game time to avoid late
  reversals. [P2 34:46-35:24, P1 88:21]

**Natural vs. scam**: does the movement make sense given the team's recent
merit (last game's result, strength of the previous opponent, record, ERA,
ATS streak)?

> "That's a natural line movement. That's what we want to see... A team
> that basically smacked the team the day before and now natural movement
> would be their odds getting cheaper." [P1 43:44, 28:02-28:32]

> "Why would Vegas all of a sudden now want to pay out 28 points more
> expensive for the Nationals? Like, that makes absolutely no sense."
> [P1 57:47]

**Public slots ride natural movement** (back the side price and merit agree
on). **Vegas slots fade a scam** — and every worked Vegas-slot example backs
the side the *price* moved toward, not the side the recent-form narrative
would suggest: Athletics/Twins (Twins had the better record/ERA/a big
recent win — the "merit" side — but their price *lengthened*, i.e. got
cheaper; the pick was Athletics, the side price moved toward) [P1 50:34-56:03];
Tigers/Nationals (Nationals' hot streak is "merit," but their price
lengthened too; the pick was Tigers) [P1 56:26-61:32, P2 23:00-26:27].
Section §4 in `docs/mvp-design.md`'s rule table (R8, the incumbent
`pv_rules` engine's sanity veto) approximates this qualitatively — the
aligned engine (`strategy/scam.py`) implements it directly as a merit score
vs. price-movement-direction classifier.

## §5. Evenness, confidence, and safety

> "When teams are evenly matched [record/ERA both close]... in public, the
> underdog... should cover because they're expecting it to be a close
> game... But once you enter into Vegas, now you want to be thinking that
> the favorite can smack the underdog." [P1 40:17-41:10, 60:00-60:25]

So: **evenly-matched public slot → underdog +1.5** (not the moneyline —
"the safest pick was plus one and a half" [P1 41:24]). On a Vegas-slot
favorite pick, prefer the **moneyline over the run line**: "if you like the
minus 1.5, instead of you taking minus 1.5, just take the money line...
[if] you got greedy and you took minus 1.5, you lost." [P1 61:02-61:32]

## §6. Standing rules

- **Exclude spring training** from all head-to-head/trend analysis, no
  matter the result. [P1 81:06-81:23]
- **Public plays require −160 or cheaper.** "I will not enter a public play
  unless it's minus 160 or cheaper... I cannot say that enough."
  [P1 19:32-21:22, repeated 90:17]
- **Moneyline ≤ −200 is a "parlay breaker" — pass, don't bet it, don't
  convert it to a run line.** "I personally skipped a game... those are
  typically what you call parlay breakers... public bettors... take that
  money line, throw that in a parlay." [P1 83:43-85:17]
- **Never bet a total on the first meeting of the season** between two
  teams (first meeting of a *series* is fine). "Do not touch the
  over-under." [P1 85:38-86:40, P2 18:23-18:53]
- **Totals signal**: compare today's total against the last-4 head-to-head
  combined runs, both teams' last-5-game combined runs, and the two
  starters' ERA sum. When those contradict the direction the total moved,
  **bet the direction it moved** — verified on all three worked examples
  (9.5→10, over by 6; 8→9, over; 8→7.5, under). [P1 76:35-80:42,
  P2 14:51-19:05]
- **~1 pick/day at maturity.** "Me doing this for like a year into it, now
  I'm only taking like one pick a day." [P1 99:03-99:20]
- **Paper-bet 5-7 days minimum** before betting real money, targeting ~70%
  accuracy. [P1 96:15-97:28]
- **Hedge** once the opposing side's moneyline reaches ~+500 or higher.
  [P1 100:00-100:38]
- Live/in-game bets only when very confident in the original pre-game read,
  and never stack more risk on the same game. [P1 91:01-92:55]
- No exact-margin predictions — "keep it simple," cover or not.
  [P2 42:24-43:26]

## Appendix — superseded 2024-era summary

The text below is the pre-2026-08-19 version of this file, kept for the
record. It was a bullet-point paraphrase, not a transcription, and several
of its claims (day-map direction implied elsewhere in the repo, the absence
of a stated schedule) are contradicted by the transcripts above.

> ### Outline of the Sports Betting Process (Based on "Project Panthera")
>
> #### 1. **Understanding Vocabulary & Key Concepts**
>    - **Public (P) vs. Vegas (V)**: Differentiating between public betting and Vegas odds.
>    - **MLB Terminology**: Understanding terms like ERA, Run Line, Money Line (ML), Against the Spread (ATS), and Over/Under (O/U).
>    - **Line Movement**:
>      - Public: Indicates a line is becoming cheaper (e.g., -160 to -180).
>      - Vegas: Indicates a line is paying more (e.g., -180 to -160).
>
> #### 2. **Daily Process Overview**
>    - **Monday to Sunday Schedule**:
>      - Identify if the day is a Public or Vegas day.
>      - Schedule games according to time slots and analyze their betting nature.
>    - **Wednesday (Hybrid Day)**:
>      - First half of the day follows the public betting pattern, and the second half follows Vegas.
>
> #### 3. **Pre-Game Analysis**
>    - **Step 1: Initial Data Gathering**
>      - Visit MLB.com to list the game schedule with times.
>      - Identify the day type (Public/Vegas).
>      - Determine specific slots (Public/Vegas slots).
>    - **Step 2: Skeleton Foundation Dossier**:
>      - Previous game lines and outcomes.
>      - Current game lines.
>      - ERA comparison.
>      - Head-to-Head and season series analysis.
>      - Analyze trends within series.
>      - Check the last 10 games (Moneyline/ATS).
>      - Analyze Over/Under trends.
>
> #### 4. **Ongoing Monitoring**
>    - **12:00 PM Check**:
>      - Monitor line movement from the morning.
>    - **One Hour Before Game**:
>      - Conduct a final scan of all the gathered data.
>    - **Line Movement Analysis**:
>      - Verify if the line makes sense based on the previous game's performance.
>
> #### 5. **Decision Making & Betting**
>    - **Making Picks**:
>      - Use the analysis to determine whether to bet on a team (Public or Vegas).
>      - Examples: Evaluate recent game outcomes, pitcher performance, and trends to decide on Moneyline, Run Line, or O/U bets.
>
> #### 6. **Special Rules & Considerations**
>    - Exclude spring training data from analysis.
>    - Guidelines for high Moneyline odds (-200, -250, -300).
>    - Focus on Moneyline and Spread for first-time matchups.
>    - Consider underdog spread in evenly matched public slots and favorite spread in Vegas slots.
