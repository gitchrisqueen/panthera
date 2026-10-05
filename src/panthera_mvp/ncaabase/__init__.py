"""NCAA Division I college baseball data plumbing (GitHub issue #52).

Mirrors ncaaf/: own config (config/ncaabase.yaml), own data tree
(data/ncaabase/), own CLI group (`panthera-mvp ncaabase ...`). No strategy
yet — this is schedule + finals ingestion, an optional (off by default) odds
snapshot, and a single-bet pick ledger with a grader ready for one.

- `config.py`   — loads config/ncaabase.yaml; season-window check.
- `matching.py` — outside names (ESPN, Odds API) <-> NCAA games, by
                  normalized name + start-time proximity (doubleheaders).
- `store.py`    — games / lines / picks CSVs.
- `grading.py`  — ml / run line / total settlement.
- `pipeline.py` — `panthera-mvp ncaabase ...` commands.
"""
