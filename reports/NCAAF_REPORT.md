# NCAAF strategies

_Generated 2026-10-09T13:31:29Z by `panthera-mvp ncaaf report` from `data/ncaaf/tickets/`. Do not edit._

Paper trades only: flat stakes, no real money. Intake record and the author's answers: `docs/strategy-intake/`.

## cfb_spread_total_parlay

**forward_test**, registered 2026-10-05, enabled. Hash lineage: e96612a177.

> An outside author's NCAAF parlay method beats the parlay vig: one 3-leg spread/total ticket per game day, legs chosen when any one of six mechanical angles fires (line move with the market, letdown and look-ahead fades of 10+ favorites, wind unders, SP+ disagreeing with the spread) and no angle contradicts it. Injury and rivalry inputs the author uses are NOT observable here and are dropped, and leg count, leg selection and same-game policy are Panthera proxies — so this tests the mechanical core of the method, not the author's full judgment.

**Pre-registered evaluation:** no verdict (SCREEN only). Ticket checkpoints [25, 50]; qualifying-leg checkpoints [100, 300]. A 3-leg ticket at -110 legs pays +596, so tickets break even at a 14.4% hit rate; single legs at 52.4%.

### Tickets

**In lineage:**

- Tickets: 1 (0-1-0 W-L-P, 0 pending)
- Staked $100, profit $-100.00, ROI -100.0%

| Date | Legs | Price | Status | Profit |
|---|---|---|---|---|
| 2026-10-08 | Arkansas State Red Wolves -3 (loss)<br>Liberty Flames -13 (win)<br>South Florida Bulls +6.5 (loss) | +608 | loss | $-100.00 |

### Single bets

Every qualifying leg as a $100 straight bet at its best-available price (break-even 52.4% at -110). Descriptive: the strategy's bet is still the ticket.

- Singles: 5 (2-3-0 W-L-P, 0 pending)
- Staked $500, profit $-116.37, ROI -23.3%

| Date | Pick | Matchup | Price | Signals | Result | P/L |
|---|---|---|---|---|---|---|
| 2026-10-08 | South Florida Bulls +6.5 | South Florida Bulls @ UTSA Roadrunners | -108 | S6 | loss | $-100.00 |
| 2026-10-08 | Arkansas State Red Wolves -3 | South Alabama Jaguars @ Arkansas State Red Wolves | -106 | S1+S6 | loss | $-100.00 |
| 2026-10-08 | Liberty Flames -13 | Sam Houston Bearkats @ Liberty Flames | -112 | S6 | win | $+89.29 |
| 2026-10-07 | Florida International Panthers -6.5 | New Mexico State Aggies @ Florida International Panthers | -106 | S6 | win | $+94.34 |
| 2026-10-07 | Jacksonville State Gamecocks -2.5 | Jacksonville State Gamecocks @ Kennesaw State Owls | -124 | S6 | loss | $-100.00 |

### Qualifying legs by signal

Every leg the engine found qualifying, on the ticket or not, graded at its best-available line. A leg fired by several signals counts under each.

| Signal | Legs | W-L-P | Win % | vs 52.4% |
|---|---|---|---|---|
| S1 | 1 | 0-1-0 | 0.0% | -47.6 pts |
| S6 | 5 | 2-3-0 | 40.0% | -7.6 pts |

### Decisions

no_ticket: 2, ticket: 1

| Date | Decision | Reason |
|---|---|---|
| 2026-10-08 | ticket | 3 qualifying leg(s); top 3 taken |
| 2026-10-07 | no_ticket | 2 qualifying leg(s); a ticket needs 3 |
| 2026-10-06 | no_ticket | 0 qualifying leg(s); a ticket needs 3 |
