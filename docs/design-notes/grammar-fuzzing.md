# Grammar fuzzing: mechanized surface totality

**Status: implemented (T1/T2/T3); T4/T5 deferred.** This was the
implementation plan for the fuzzing work — corpus mutation and
grammar-directed generation behind one oracle. The suite now lives at
`tests/fuzz/` — see issue #109 for T4/T5's deferral and the six findings
the discovery sweep surfaced (recorded, not fixed, in `tests/fuzz/findings.py`'s
`KNOWN_FINDINGS`), and the reasoning for deferring T4 (grammar-directed
generation) and T5 (mechanized shrinking — every finding above was shrunk by
hand instead). This file stays as the design record; `tests/fuzz/oracle.py`,
`mutate.py`, and `test_fuzz.py` carry the implementation-level detail
(module docstrings, completeness ledgers) from here on. It ran after the
metamorphic suite ([metamorphic-suite.md](metamorphic-suite.md)):
metamorphic failures are near-always real bugs, while a fuzzer needs an
initial triage round before it earns its keep.

## The oracle

Every input either passes the front-end pipeline or fails as a located
`DiagnosticError`; **any other exception is a finding** — the wrong-channel
defect class (decisions.md "Closed-domain completeness"; severity 5 in the
review skill's order). Inputs that pass the pipeline are additionally run
through a bounded random playout asserting the runtime-net invariants
(implementation.md): the game terminates, the legal-move set is non-empty
until terminal, scores reconcile.

Hand-written misuse probes cover the wrong sentences someone thought of; a
generator covers the ones nobody did. The corpus exercises a sliver of the
grammar's sentence space — decisions.md says exactly this about corpus-first
coverage — and this harness is the standing sweep for the two loudness
defect classes: raw-exception escapes, and accepted sentences that crash
downstream instead of being rejected at the Owner Guard that owns them.

## Shape

A `tests/fuzz/` package, built in two stages.

**Stage 1 — corpus mutation** (cheap, high yield): token- and line-level
mutations of `docs/games/*.cardlang` — delete a clause or line, duplicate a
declaration, swap adjacent tokens, rename one occurrence of an identifier,
truncate a block — each mutant fed to `pipeline.check_dsl` under the oracle.
This stage alone should surface wrong-channel findings; each is triaged
Owner Guard / Shadow Guard / missing Owner Guard per the write-time triage before it is fixed.

**Stage 2 — grammar-directed generation**: a sentence generator walking
`cardlang/grammar/cardlang.lark` directly — depth-bounded rule expansion with
terminals drawn from realistic pools (real zone, rank, and suit names), so
generated sentences reach past the parser into resolve and typecheck. No
pretty-printer exists in the repo, so generating *text* from the grammar is
the right lever: it needs no new AST machinery and exercises parse itself.
Hypothesis is the suggested engine (a new `dev` extra) for its shrinking; a
hand-rolled generator with a delta-debugging shrinker is the fallback if
Hypothesis fights the Lark dialect — decided at implementation time.

## Constraints that keep it honest

- **CI is deterministic.** A fixed seed list checked into the test module,
  sized to a ~30–60 s budget. The open-ended run is a separate,
  env-var-gated mode (`FUZZ_BUDGET_SECONDS=…`) for local or scheduled use. A
  flaky CI fuzzer gets deleted; a deterministic one gets kept.
- **Findings are minimized, then made permanent.** Every finding is shrunk to
  the smallest input that still trips the oracle, and once fixed lands as a
  rejection-corpus case (`tests/rejections/`) — the fuzzer *feeds* the
  rejection corpus, it does not replace it. That rule lives in the oracle
  module's docstring and in building.md.
- **Playout invariants pin `PYTHONHASHSEED`** (set-iteration nondeterminism
  in `legal_cards`).
- **The ledger states the honest residual up front**: generation is
  depth-bounded and weighted, so deep nesting and rare-terminal combinations
  are sampled, not covered.

## Acceptance

Done means: the oracle module and mutation stage run in ordinary CI on the
fixed seed set; the generator stage covers every grammar rule at least once
per CI run (pinned against the grammar file, so a new production without
generator support fails the pin rather than being silently unexercised); and
the feed-forward rule — shrunken finding becomes rejection-corpus case — has
been exercised at least once end to end.
