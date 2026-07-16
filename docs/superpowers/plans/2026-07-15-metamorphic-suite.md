# Metamorphic Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A suite of semantics-preserving transformations, each applied to
every corpus game and checked by paired playout: transform the game, replay
both variants under the same seed and scripted decisions, and require the
traces to agree (modulo the transform's own renaming map). Metamorphic checks
need no second implementation — the DSL is tested against itself — and a
failure is almost always a real bug (a meaning the pipeline attached to
something the spec says is meaningless: a name's spelling, declaration order,
a suit's identity, the `run`/inline distinction).

**Why now:** the differential harness (native GOPS) covers one game against
one hand-coded oracle; goldens pin byte-stability but not *invariance*. The
four transforms below each pin an equivalence the spec already asserts
implicitly, and one of them (inline-vs-`run`) is the exact invariant the
by-value expansion bug violated — currently pinned only by its specific
regression test.

**Architecture:** transforms are pure `Game -> Game` functions over the
*checked* AST (the `dataclasses.replace` walk idiom from `cardlang/resolve.py`
/ `cardlang/expand.py`), applied AFTER `pipeline.check_source` so both
variants are known-valid. Playout via the existing seams:
`runtime/driver.play_game` with a fixed seed and a deterministic chooser
(greedy-first, as in `tests/openspiel_ready/harness.py`), captured through the
one `Ctx.observer`/tracer seam. Comparison is trace-level: sequence of
decisions, movements, and final `GameResult`, with a per-transform
`rename: dict[str, str]` hook applied to one side before comparing (identity
for transforms that rename nothing). New module `tests/metamorphic/` with a
shared pairing harness and one test module per transform, parametrized over
the corpus glob.

**Tech Stack:** Python 3.11, pytest, mypy --strict (covers `tests/`), no new
dependencies. No pyspiel needed (runtime-level, not adapter-level).

## Global Constraints

- `mypy` (bare) and `pytest -q` (full suite) pass before any push (CLAUDE.md).
- `PYTHONHASHSEED` must be pinned in every paired playout — `legal_cards`
  returns a set, and unpinned hash randomization makes trace comparison flaky
  (see the exact-score tests for the idiom).
- Transforms run on the checked AST and must RE-CHECK the transformed tree
  (`resolve`/`typecheck` again) before playout — a transform that produces an
  unresolvable tree is a harness bug, and failing loudly there keeps the suite
  honest.
- Each transform's test module carries a completeness ledger
  (property / domain / registry / covered / sampled / residual) per
  decisions.md "Closed-domain completeness"; the domain is "corpus games ×
  seeds", registry is the corpus glob.
- No golden churn: this suite is additive proof machinery.

## Tasks

- [ ] **T1 — Pairing harness.** `tests/metamorphic/pairing.py`: run
  `(game, transformed, seed)` to paired traces with the rename hook; a
  deterministic scripted chooser shared with (or lifted from) the readiness
  harness; loud failure rendering (first divergent step, both sides).
- [ ] **T2 — α-rename.** Rename every zone, state variable, and (where games
  name them) player/team identifier via a generated map; expected: traces
  identical after applying the map to names embedded in events. Catches any
  site that switches on a name's spelling rather than its declaration.
- [ ] **T3 — Inline-vs-`run`.** For every corpus game and test fixture with
  procedures: variant A is the game as written; variant B has each `run`
  site replaced at SOURCE level by the procedure body with `let`-bound
  arguments (the expansion the spec defines, performed textually). Expected:
  identical traces. Design decision at execution time: source-level splice
  (tests the whole pipeline end to end, preferred) vs AST-level comparison
  against `expand`'s output (weaker — shares code with the thing tested).
- [ ] **T4 — Suit relabeling.** Apply a suit permutation to the deck, every
  suit literal, and the initial conditions; expected: outcomes are the same
  game under the permutation (traces agree after mapping suits). This is the
  runtime-level cousin of the readiness proofs' suit-axis swap classes —
  reuse their equivalence-class reasoning for which games admit which
  permutations (a game whose rules name a specific suit, e.g. Hearts,
  admits only permutations fixing that suit; derive admissible permutations
  from the game's suit literals, don't hand-list them).
- [ ] **T5 — Declaration reorder.** Permute declaration order where the spec
  says order is irrelevant (zones, state vars, move types, rules — confirm
  each against decisions.md before including; anything order-sensitive is
  excluded WITH a comment citing the spec section). Expected: identical
  traces and identical diagnostics on the rejection corpus.
- [ ] **T6 — Wire into CI** as part of the ordinary suite (small fixed seed
  set per game; runtime budget ~tens of seconds), with an env-var knob for a
  longer local run.
