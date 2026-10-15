# `doctor` test fixtures

**There are no CSVs in this directory.** Every fixture `tests/test_doctor.py`
uses is built in-test by its `write_games` / `write_picks` / `write_passes`
helpers — that is the single source of truth, and this file only explains
which real days those builders reproduce and why.

The shapes come from three real days in the live history, because the checks
they exercise were calibrated on that history:

- **`2026-09-29`** — the first postseason slate day. Four games, five
  strategies, zero picks, every pass reading one shared reason key. The builder uses the post-fix
  spelling `excluded_game_type=F`; the real rows that day read the pre-fix
  `[R0] game_type=F`, since the gate was still a whitelist then. Only the
  key matters to the check, and it is the same either way. This is
  the day H01 `slate_shutout` first fires, and the day the stall that began
  after the 2026-09-27 pick became detectable.
- **`2026-09-23`** — the near-miss. Sixteen games; `fav_ml`, `pv_orig` and
  `pv_v3` all produced picks while `fade_public` and `sharp_split` passed
  every game for one shared reason (`no-splits: none captured for game`).
  H01 must stay SILENT here. This is the check's hardest case and the reason
  it requires *every* evaluated strategy to be silent rather than merely
  several.
- **`2026-09-24`** — an ordinary day, simplified: twelve games with picks
  and no passes. Unlike the other two this is NOT the real day's shape
  (2026-09-24 actually had 29 picks and 25 passes); the builder keeps only
  what H01 needs — at least one strategy that picked — so the assertion
  reads clearly.

Kept as a directory with only this README on purpose: the next person to add
a `doctor` fixture should extend the in-test builders rather than start a
parallel set of CSVs that can drift from them.
