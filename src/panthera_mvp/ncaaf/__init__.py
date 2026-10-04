"""NCAAF (college football) data plumbing.

Built for the cfb_spread_total_parlay intake (an outside author's strategy; see
docs/strategy-intake/cfb_spread_total_parlay.md). Kept apart from the MLB
pipeline on purpose: own config (config/ncaaf.yaml), own data tree
(data/ncaaf/), own ledger (parlay tickets, not single picks). Nothing here
generates picks yet — the engine waits on the author's follow-up answers.

- `config.py`   — loads config/ncaaf.yaml.
- `matching.py` — Odds API event <-> ESPN event id, by normalized names.
- `store.py`    — games / lines / tickets / ticket_legs CSVs.
- `grading.py`  — spread/total/moneyline legs and parlay tickets.
- `pipeline.py` — `panthera-mvp ncaaf ...` commands.
"""
