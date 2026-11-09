# Intake: `cfb_spread_total_parlay_v2` (college football)

**Status:** registered 2026-11-09 as a SCREEN-only forward test
(`config/ncaaf_strategies/cfb_spread_total_parlay_v2.yaml`, same engine as v1,
`src/panthera_mvp/ncaaf/parlay.py`). Live once the PR merges to `main`. It uses
the last forward-test slot of the 2026 registration budget (`docs/mvp-design.md`).

## Why a v2

v1 (`cfb_spread_total_parlay`) is an outside author's parlay method. Its round-3
questionnaire (issue #55) was never answered: the author could not answer the
open questions, and the 2026-10-18 decision date passed with no answers. The
owner's instruction on 2026-11-09 was to settle the open questions by research
instead, finish the strategy, and run it. v2 is that result. v1 keeps running
unchanged as the control (same YAML, same hash `e96612a177`, same ledger).

The research was done on 2026-11-09 by a research agent (web search; some
journal articles were read as abstracts and search summaries only, and are
marked below). The sources are linked; none of the effect sizes was
independently re-derived except where stated.

## What the research found

**Structure.** Three -110 legs in a parlay pay +595.8. The break-even hit rate
is 14.37% per ticket (52.38% cubed) against 52.38% per leg for a straight bet.
If every leg has a true +2% ROI, a parlay of them has +6.1%; if the legs have no
edge, the parlay loses about 13% against 4.5% for singles. A parlay amplifies a
real edge and a missing edge by the same factor, and it carries about 2.5 times
the risk per dollar. Correlation helps only same-game legs, which books price.
No source found shows a parlay beating the same legs bet straight. College
teasers are rarely +EV
([TheLines 2021](https://www.thelines.com/college-football-teasers-study-2021/),
analyst-level). So v2 bets straight.

**Signals.**

| Signal | Outside evidence | Strength | v2 |
|---|---|---|---|
| S5 wind under | [Borghesi 2008](https://www.tandfonline.com/doi/full/10.1080/09603100701335432) (NFL, 1984-2004: wind lowers scoring and the market under-reacts; read via summary); [Football Study Hall 2018](https://www.footballstudyhall.com/2018/6/25/17500384/football-betting-windy-conditions-effect) (7,323 games: unders hit 54.7% above 10 mph and about 58% above 15 mph, about 250 games; the lines used are not stated). | The best of the six, but blog-level for college and old. | staked |
| S6 SP+ vs spread >= 4 | [Fair and Oster 2007](https://ideas.repec.org/a/sae/jospec/v8y2007i1p3-18.html): rankings add nothing once the spread is in the model (1,582 games). Connelly's SP+ records are anecdotal and not against closing lines. | Peer-reviewed says priced in; the SP+ record is anecdotal. Kept as a clean test, not retuned. | staked |
| S1, S2 line move | Peer-reviewed work is thin and mixed. The engine buys after the move, so the information is already in the price. | Thin. | off in v2; v1 still grades them |
| S3, S4 letdown, look-ahead | No peer-reviewed study found; a 38-62 ATS claim rests on about 100 games and a self-reported method; one source says the spread usually prices these spots. | Folklore. | off in v2; v1 still grades them |

No source shows a college-football edge that survives the vig except possibly
the wind under, and those numbers are old.

**What 49 singles and 4 tickets tell us (2026-11-09).** Nothing. The standard
error of ROI is about 13.6 points at 49 singles, so -14.1% is about one standard
error below zero. The chance of 22 or fewer wins in 49 at 52.4% is about 18%.
The chance of going 0-4 on tickets at a 14.4% hit rate is about 54%. The
per-signal records (5 to 28 legs each) are noise.

## The 12 open questions, and what v2 does instead

| # | Question | v1 proxy | v2 (research) |
|---|---|---|---|
| 1 | Legs per ticket | 3, skip if fewer | no tickets: straight bets |
| 2 | Price band +600/+1000 | target only | dropped; skip any bet priced worse than -115 |
| 3 | Which legs when many qualify | most signals, then earliest | strongest signal first (wind mph or SP+ gap in points), at most 6 a day |
| 4 | Two legs from one game | never | never: one bet per game |
| 5 | Rivalry | not used | not used: no feed, and closing spreads mostly price it ([Cox 2026](https://link.springer.com/article/10.1007/s12197-026-09786-6), read via summary) |
| 6 | Injuries | not used | not used: no feed. A skip-when-the-spread-moved-3+ proxy was suggested and is not adopted (an unverified hypothesis) |
| 7 | When to add a moneyline | never | never |
| 8 | Stake and book | $100, best line | $100 flat, best line (and skip worse than -115) |
| 9 | Why the Oct 3 card was not placed | - | unrecoverable discretion: v2 has no discretionary skips |
| 10 | Reasons for the Oct 3 legs | - | unrecoverable; the engine now logs signals per leg |
| 11 | Other remembered tickets | - | not used: recall-biased |
| 12 | Best days | any day | any day; skip-day-after-loss dropped (days are independent) |

## What v2 is

Same engine, `ticket.structure: singles`: every qualifying S5 or S6 leg is a
one-leg ticket of $100 at its best-available price, strongest first, at most 6 a
day, nothing priced worse than -115. A leg's strength is its biggest signal
strength: wind in mph (S5) or the SP+ gap in points (S6); a game that fires both
is ranked by the larger number, and the two units are not comparable, so this is
a fixed ordering rule, not a claim that 20 mph beats 20 points. The day's
decision is made once, at the same time as v1's, from the same snapshot (no
extra Odds API credits).

Every parlay-path value is untouched: v1's config hash is `e96612a177` before
and after this change, and a test pins it.

## Falsification and honest sample sizes

No ROI verdict is reachable this season, so `verdict: null` (SCREEN only). These
sample sizes are the research agent's calculations (SD 0.952 per $1 on a -110
bet; alpha 0.05 two-sided, 80% power), not published figures:

| To tell this from zero | Straight bets needed |
|---|---|
| +5% ROI | about 2,800 |
| +2% ROI | about 17,800 |

Stated before the first bet, v2 is read as falsified if any of these holds:

1. wind unders (S5) win 52.4% or less over 300 graded bets;
2. SP+ legs (S6) win 52.4% or less over 300 graded bets;
3. ROI is below -7% after 300 graded bets (about 1.28 standard errors below
   zero at that sample, so a break-even bettor reaches it about one time in ten).

## Not done (follow-ups, not claims)

- **Closing-line value for NCAAF.** The research's best early read is CLV, which
  is far less noisy than P/L. NCAAF has no closing snapshot (it would cost
  credits) and no CLV column. Not built here.
- **A travel and time-zone signal.** One paper supports it
  ([Coleman 2017](https://journals.sagepub.com/doi/abs/10.1177/1527002515574514),
  read via summary; effect size unverified). Not built; v2 does not stake it.
- **Median-book ledger.** The research suggested a second ledger at the median
  book. Not built.
- **Tuning.** v2's thresholds are the author's numbers carried over and are not
  tuned. Any later tuning is a separate loop (`docs/lab/PROGRAM.md` once the lab
  lands) and never changes v2: a behavior change needs a new strategy id.
