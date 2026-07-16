# Grammar-Directed Generation and Mutation Fuzzing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** mechanize surface totality beyond hand-written probes. Two program
sources — mutations of corpus games, and programs generated from the grammar
itself — driven through one oracle: **every input either passes the pipeline
or fails as a located `DiagnosticError`; any other exception is a finding**
(the wrong-currency defect class, severity 5 in the review skill's order).
Programs that pass the pipeline additionally satisfy the runtime invariants
(bounded playout terminates; the legal-move set is non-empty until terminal;
scores reconcile — the "runtime net" invariants in implementation.md).

**Why:** hand-written misuse probes cover the wrong sentences someone thought
of; a generator covers the ones nobody did. The corpus exercises a sliver of
the grammar's sentence space (decisions.md "Closed-domain completeness" says
exactly this about corpus-first coverage), and the harness this plan builds is
the standing sweep for the two loudness defect classes: raw-exception escapes
and accepted-but-ignored sentences that crash later instead of being rejected.

**Sequencing note:** do the metamorphic suite first
(2026-07-15-metamorphic-suite.md) — its failures are near-always real bugs,
while a fuzzer needs an initial triage round to burn off uninteresting
findings before it earns its keep.

**Architecture:** `tests/fuzz/` package. Stage 1 is corpus mutation (cheap,
high yield): token- and line-level mutations of `docs/games/*.cardlang` —
delete a clause/line, duplicate a declaration, swap adjacent tokens, rename
one occurrence of an identifier, truncate a block — each mutant fed to
`pipeline.check_dsl` under the crash-vs-diagnostic oracle. Stage 2 is
grammar-directed generation: a sentence generator walking
`cardlang/grammar/cardlang.lark`'s rules directly (depth-bounded expansion
with weighted terminals drawn from realistic pools: real zone/rank/suit
names so sentences reach past the parser into resolve/typecheck). No
pretty-printer exists in the repo, so generating TEXT from the grammar is the
right lever — it needs no new AST machinery and exercises parse itself.
Hypothesis is the suggested engine (add to `dev` extras) for its shrinking;
a hand-rolled generator with a manual delta-debugging shrinker is the
fallback if Hypothesis's grammar support fights the Lark dialect.

**Tech Stack:** Python 3.11, pytest, mypy --strict, Hypothesis (new dev
dependency — decide at execution time), no pyspiel requirement.

## Global Constraints

- `mypy` (bare) and `pytest -q` pass before any push (CLAUDE.md).
- CI mode is DETERMINISTIC: a fixed seed list checked into the test module,
  small enough for a ~30–60 s budget. The open-ended run is a separate
  env-var-gated mode (`FUZZ_BUDGET_SECONDS=...`) for local/scheduled use —
  a flaky CI fuzzer gets deleted, a deterministic one gets kept.
- Findings are minimized before filing: shrink to the smallest input that
  still trips the oracle, and record it as a rejection-corpus case
  (`tests/rejections/`) once fixed — the fuzzer FEEDS the rejection corpus,
  it does not replace it.
- Playout invariants pin `PYTHONHASHSEED` (set-iteration nondeterminism in
  `legal_cards`).
- The oracle module carries a completeness ledger; the honest residual to
  record up front: generation is depth-bounded and weighted, so deep
  nesting and rare-terminal combinations are sampled, not covered.

## Tasks

- [ ] **T1 — Oracle harness.** `tests/fuzz/oracle.py`: run text through
  `pipeline.check_dsl`; classify {passes, DiagnosticError, OTHER}; OTHER
  renders the input, the exception, and the pipeline stage that raised.
- [ ] **T2 — Corpus mutation fuzzer.** The five mutation operators above,
  applied to every corpus game; deterministic CI seed set + budgeted local
  mode. Expect this stage alone to surface wrong-currency findings — triage
  each as wall / backstop / missing wall per decisions.md write-time triage
  before fixing.
- [ ] **T3 — Playout invariants for passing inputs.** Mutants/generated
  programs that pass the pipeline get a bounded random playout asserting
  termination, non-empty legal set until terminal, and score reconciliation.
- [ ] **T4 — Grammar-directed sentence generator.** Depth-bounded walk of the
  Lark grammar with realistic terminal pools; same oracle; same seed
  discipline.
- [ ] **T5 — Shrinking.** Hypothesis-native if Hypothesis was adopted;
  otherwise line/token delta-debugging against the oracle verdict.
- [ ] **T6 — Feed-forward rule.** Document (in the oracle module docstring
  and a line in docs/building.md): every fixed finding lands with its
  shrunken input as a rejection-corpus case, so the fuzzer's discoveries
  become permanent regression artifacts.
