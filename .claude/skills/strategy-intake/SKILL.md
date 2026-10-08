---
name: strategy-intake
description: Turn an outside betting strategy (described in chat, or returned as a Strategy Export YAML from docs/strategy-intake/EXPORT_PROMPT.md) into a registered, paper-traded Panthera strategy - config/strategies/<id>.yaml plus engine wiring, tests from the author's worked examples, a zero-credit replay, and the regenerated report - without spending Odds API credits or breaking the pre-registration protocol.
when_to_use: Use when someone hands over a strategy to test ("register this strategy", "paper-trade my friend's system", "here is the export YAML", "add a new strategy to the registry"). Not for changing an already-registered strategy - a behavior change needs a new id - and not for retuning P/V thresholds (that is `panthera-mvp calibrate`).
allowed-tools: Read, Edit, Write, Bash(git fetch:*), Bash(git switch:*), Bash(git status:*), Bash(git restore:*), Bash(git clean:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(gh pr create:*), Bash(grep:*), Bash(python3.12 -m venv:*), Bash(.venv/bin/pip install:*), Bash(.venv/bin/pytest:*), Bash(.venv/bin/ruff check:*), Bash(.venv/bin/python -c:*), Bash(.venv/bin/panthera-mvp replay:*), Bash(.venv/bin/panthera-mvp backtest:*), Bash(.venv/bin/panthera-mvp report), Bash(.venv/bin/panthera-mvp status)
---

# Strategy intake

Source of truth for the procedure: `docs/strategy-intake/EXPORT_PROMPT.md`
(prompt + intake steps) and `docs/mvp-design.md` (registration protocol).
Prior intakes to copy from: `config/strategies/fade_public.yaml` (MLB
forward test), `pv_v3.yaml` (hash_lineage pinning), and
`docs/strategy-intake/cfb_spread_total_parlay.md` (NCAAF, discretionary
rules turned into proxies). Hard rules for the whole run:

- Never run `snapshot`, `splits` or `picks` without `--dry-run`. Live Odds
  API calls happen only in the scheduled workflows (budget:
  `.github/workflows/CLAUDE.md`, "Credit budgets").
- `data/` and `reports/` are bot-owned. Commands below write to them for
  inspection only; restore them before committing.
- Never invent a rule. A gap is `UNKNOWN` until the author answers.

## Steps

1. **Branch and baseline (5 min).** `git fetch origin && git switch -c
   strategy/<id> origin/main`. If `.venv` is missing: `python3.12 -m venv
   .venv && .venv/bin/pip install -e ".[dev]"`. Run `.venv/bin/pytest tests/
   -q`. Verify: all pass before you change anything.

2. **Check the registration budget (2 min).** `grep -n "budget:"
   docs/mvp-design.md`. Verify: fewer than 2 forward tests registered beyond
   the launch set this season. If the budget is spent, stop and tell the
   owner; do not register.

3. **Get a Strategy Export (10 min of your time; the author's answers may
   take days).** If you have only a chat description, send the author the
   prompt between the `====` lines of `EXPORT_PROMPT.md`; do not fill the
   schema from your own reading of the chat. Keep the returned YAML outside
   git unless the author agrees it can be public (this repo is public).
   Verify: one fenced `yaml` block with `schema_version: "1.0"`.

4. **Resolve every gap (15 min).** List each `UNKNOWN`,
   `discretionary: true` rule and `unanswered_questions` item. For each,
   record the author's answer or a mechanical proxy the author confirmed in
   words (an echoed "accept" is not confirmation). Verify: no rule left
   that needs judgment to evaluate. If nearly every field is `UNKNOWN`, the
   assistant skipped the interview; ask the author directly.

5. **Map inputs and pick the registry (10 min).** For each `inputs[]`
   entry, name the Panthera field it reads (table in `EXPORT_PROMPT.md`).
   An `available_in_panthera: no` input means drop the rule or ship a new
   client plus fixtures in a separate PR first; write down which. Sport
   decides the home: MLB goes to `config/strategies/`; NCAAF goes to
   `config/ncaaf_strategies/` with its engine in `src/panthera_mvp/ncaaf/`;
   for NCAAF, steps 6–10 change as set out in "NCAAF strategies" below.
   Verify: every rule's condition names only mapped fields.

6. **Choose or write the engine (20 min).** Prefer an existing engine
   from `engines()` in `src/panthera_mvp/strategy/registry.py` (`pv_rules`,
   `orig_rules`, `fav_ml`, `dog_ml`, `sharp_split`, `fade_public`) when the
   export is a re-parameterization. Otherwise add one pure function
   `StrategyContext -> Pick | Pass | None` under `src/panthera_mvp/strategy/`
   and register it in `engines()`; add it to `BACKTESTABLE_ENGINES` only if
   it reads no splits. No thresholds in code; read every number from the
   YAML. Verify: `.venv/bin/ruff check src tests` passes.

7. **Write `config/strategies/<id>.yaml` (15 min).** Model it on
   `fade_public.yaml`: `strategy.id` equal to the filename stem
   (`[a-z0-9_]+`), `engine`, `enabled: true`, `kind: forward_test`, `scope`,
   `registered_at` (today, ET), `hypothesis` from the export's `thesis`,
   every threshold from the export, `bet_limits.max_picks_per_day` stated
   explicitly (null = uncapped), `staking.flat_stake`, and `verdict` /
   `screen` set now, before the first pick. Header comment: where each
   number came from and which proxies stand in for `UNKNOWN`s. Verify: the
   step 8 command loads it without a `StrategyConfigError`.

8. **Pin the hash (3 min).** Run
   `.venv/bin/python -c "from panthera_mvp.config import load_strategy_configs, config_hash; from panthera_mvp.strategy.registry import engines; c=load_strategy_configs(set(engines())); print(config_hash(c['<id>']))"`
   and set `hash_lineage: [<hash>]`. Verify: re-running prints the same
   hash, and the other strategies' hashes are unchanged (run it with
   `{k: config_hash(v) for k, v in c.items()}` before and after).

9. **Tests from the worked examples (20 min).** Turn each
   `worked_examples` entry (bets and passes) into a unit test on fixtures,
   following `tests/test_registry.py`. Add new rule ids and terms to
   `config/glossary.yaml`. Verify: `.venv/bin/pytest tests/ -q` passes,
   including `tests/test_glossary.py`. If the engine does not reproduce
   the author's own decisions, the translation is wrong; go back to step 4.

10. **Zero-credit dry run (10 min).** `.venv/bin/panthera-mvp replay
    --strategy <id>` (replays captured odds; no API calls). For a
    backtestable engine, also `.venv/bin/panthera-mvp backtest --strategy
    <id>`. Then `.venv/bin/panthera-mvp report` and read the new strategy's
    section in `reports/BETTING_REPORT.md`. Verify: picks or passes appear
    with plausible volume against the export's `limits.max_bets_per_day`
    and the registered YAML's `bet_limits.max_picks_per_day`.
    `.venv/bin/panthera-mvp status` shows the credit balance; it must not
    have moved.

11. **Credit check (5 min).** A strategy that reads the existing MLB
    snapshots costs 0 extra credits. If it needs a new market, label or
    sport snapshot, compute its monthly credits (3 per snapshot) against
    the free-tier total and the per-sport reserves in
    `.github/workflows/CLAUDE.md` and `config/ncaaf.yaml`, and stop for the
    owner's approval before touching a workflow.

12. **Record and open the PR (15 min).** `git restore data reports`, then
    `git clean -n data reports` to list what the runs created and
    `git clean -f data reports` to drop it. Write
    `docs/strategy-intake/<id>.md` (summary, input mapping, every proxy)
    and update the "Registered beyond the launch set" line in
    `docs/mvp-design.md`. Verify `git status` shows no `data/` or
    `reports/` paths, then commit, push and `gh pr create`. Do not merge;
    the owner merges, and the strategy goes live only after merge to `main`.

## NCAAF strategies

The verify commands in steps 7, 8 and 10 cover only `config/strategies/`
and MLB: `load_strategy_configs`, `replay`, `backtest` and `report` never
read `config/ncaaf_strategies/`, and there is no NCAAF replay or backtest
command. For an NCAAF strategy use these instead:

- **Step 6.** The engine goes in `src/panthera_mvp/ncaaf/` (pure, like
  `parlay.py`), and its name goes in `NCAAF_ENGINES` in
  `src/panthera_mvp/ncaaf/config.py`, not in `registry.engines()`.
- **Step 7.** Model the YAML on
  `config/ncaaf_strategies/cfb_spread_total_parlay.yaml`. Each NCAAF YAML
  is complete, with no base file to merge, and its daily limit is
  `bet_limits.max_tickets_per_day`. Verify that it loads:
  `.venv/bin/python -c "from panthera_mvp.config import config_hash; from panthera_mvp.ncaaf.config import load_ncaaf_strategies; print({k: config_hash(v) for k, v in load_ncaaf_strategies().items()})"`
  raises no `StrategyConfigError`.
- **Step 8.** Take `<id>`'s hash from that same command for
  `hash_lineage`. Re-run it to confirm the hash is stable and
  `cfb_spread_total_parlay`'s is unchanged.
- **Steps 9–10.** Write the tests in `tests/test_ncaaf_parlay.py`'s
  pattern. Include an end-to-end test like
  `test_prep_picks_grade_report_end_to_end`, which runs prep, picks,
  grade and report against the ESPN and odds fixtures under a temporary
  `PANTHERA_ROOT`, and a hash-in-lineage test like
  `test_registered_hash_is_in_lineage`. That end-to-end test is the
  zero-credit dry run. Do not run `panthera-mvp ncaaf picks` against the
  repo's `data/`: it refreshes games from ESPN, writes a decision, and
  without `--dry-run` it buys an odds snapshot. Verify:
  `.venv/bin/pytest tests/ -q` passes, and `.venv/bin/panthera-mvp status`
  shows the credit balance has not moved.
