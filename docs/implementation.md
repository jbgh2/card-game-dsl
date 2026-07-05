# Implementation plan

The language is designed independently of any runtime (see
[principles.md](principles.md) and [roadmap.md](roadmap.md), "OpenSpiel
compilation"). This file covers the first tooling built *for* the
language: the parser and static checker that make the spec executable
enough to verify it is precise. It records the decisions behind that
tooling so they don't have to be re-derived. The execution blueprint —
architecture, disciplined workflow, and CI gates — lives in
[building.md](building.md).

## Goal of v1

Prove the spec is **buildable as a DSL** — precise enough that a parser
plus a static checker can accept the whole corpus with no hand-waving.

The corpus ([games/](games/), 14 games today) is the test suite. Every
game that fails to parse or type-check points at exactly the place where
the spec
is still vague. This is deliberately a **compile-time net**: it catches
the class of problems a grammar and a type checker catch — unparseable
syntax, unresolved names, type mismatches, undefined mechanics — before
any game is run. Runtime problems are a later net (see "Milestone
boundary").

## Scope

In scope (the compile-time net):

- A **formal grammar and parser** for the surface syntax, producing a
  typed AST.
- **Static semantic checks**: name resolution, type checking,
  exhaustiveness, an explicit no-placeholder audit, and a deck-capacity
  check (worst-case cards dealt per hand vs the deck size, so a too-large
  player count is a compile error, not a runtime exhausted-deck crash).
- The **corpus as acceptance harness**: every game parses and checks, or
  fails loudly.

Out of scope, deferred (with why):

- **An executable interpreter** — the runtime net (empty legal-move
  sets, non-termination, scores that don't reconcile). The next
  milestone, not this one.
- **OpenSpiel integration** — `pyspiel` game registration,
  `information_state_tensor`, `chance_outcomes`. Deferred per
  [roadmap.md](roadmap.md); reached through the IR (see decision 2),
  not coupled to the front end.
- **Performance work** — codegen, an RBG-style compiled core. Far later;
  irrelevant at corpus scale.

## Decisions

These are the settled positions this plan rests on.

### 1. Build the front end in Python with Lark

The v1 task is exploratory: iterate hard on the surface syntax until it
is crisp. Lark suits that loop — an EBNF-style grammar (close to ANTLR's,
so prior ANTLR experience transfers) read at runtime with no
generate-compile step, a `Transformer` to shape the parse tree into a
typed AST, and a switch between the Earley parser (parses any
context-free grammar, reports ambiguity) and LALR (fast, forces a
deterministic grammar — itself a crispness check). Python is also the
same language as the eventual OpenSpiel adapter, so the toolchain stays
single-language end to end.

The discipline a dynamically-typed host lacks is recovered with
dataclasses, structural `match`, `typing.assert_never` on AST unions, and
a strict `mypy` configuration. The corpus is the real exhaustiveness
check regardless of host language.

**Rust (or an ML such as OCaml) considered and deferred.** It is the
better language for *building a compiler* — algebraic data types model
the AST exactly, exhaustive `match` makes an incomplete checker a compile
error, and diagnostic crates (miette, ariadne) give span-precise errors.
But the borrow-checker learning tax falls precisely on exploratory,
fast-iteration work, which is the opposite of what v1 needs, and Rust is
not an OpenSpiel shortcut (see decision 3). Revisit only if the tool
grows into a long-lived production compiler; decision 2 keeps that port
from being a one-way door.

### 2. The validated IR is the contract

The compiler's real output is a **validated, typed intermediate
representation** (serializable, e.g. JSON), not the in-memory host AST.
Everything downstream — the future interpreter, the OpenSpiel adapter,
any codegen — consumes the IR. This decouples the front-end language from
the runtime language: the front end can stay Python (or later move to
Rust) without dictating how games are eventually fed to OpenSpiel.

### 3. OpenSpiel new-game registration is Python or C++ only

OpenSpiel's Rust bindings are auto-generated FFI over the C++ core,
limited to the core API and random-simulation tests — they let Rust
*consume* existing OpenSpiel games, not *implement* a new one that CFR or
IS-MCTS can drive. New-game registration is C++ or Python only. Python is
therefore the easier runtime path. This reinforces decision 1 but does
not constrain it: decision 2's IR boundary means the runtime adapter's
language is an independent choice made later.

### 4. The corpus is the test suite

Consistent with corpus-first development ([principles.md](principles.md),
"Corpus first, abstraction second"), every game in the corpus must parse
and check. A
game that cannot is a spec bug, not a tooling limitation — the same
standard [CLAUDE.md](../CLAUDE.md) applies to games using obsolete syntax.

## v1 build plan

### A. Grammar and parser

Write the Lark grammar from the surface syntax shown in
[model.md](model.md), [library.md](library.md), and the game files. Start
on the Earley parser to surface ambiguity, then tighten toward LALR so
the grammar is provably deterministic. Use a `Transformer` to produce a
typed AST of Python dataclasses — one node kind per primitive in the
[model.md](model.md) table (Card, Resource, Zone, Phase, Rule, MoveType,
Move, observation/memory operations, scoring component, user-defined
type, and the game-level blocks).

*Forcing function:* wherever the syntax across the docs is inconsistent
or underspecified, the grammar can't be written or a game won't parse.

### B. Semantic model and symbol resolution

Resolve names across every block: zones, move types, rules, mechanics,
user-defined types, state variables, players and partnerships, scoring
components, and stdlib functions. Build scopes following lexical phase
nesting (see [decisions.md](decisions.md), "State scoping"), including
mechanic-internal state blocks that rules read by lexical scope (e.g. a
still-Python `SchnapsenHand`'s endgame state).

*Forcing function:* every `constrains: <move_type>`, every
`active_rules: [...]` entry, every type and zone reference must resolve.

### C. Type checker

Check against the typed object model ([decisions.md](decisions.md),
"Typed object model"): zone parameterization (`Hand<Owner>`), generic
parameters, the visibility-projection enum on each zone, rule clause
types (`applies_when` is a state predicate; `demands` returns a set of
candidate moves; `if_impossible` is a fallback), the `round`'s
`outcome` and `early`-predicate function signatures, scoring components producing
`ScoreDelta`, and exhaustiveness of pattern matches on typed phase
outcomes ([decisions.md](decisions.md), "Typed phase outcomes").

Handle the `<>` "type-shaping" value parameters explicitly: in
`PrivateHand<Owner>` the parameter is a value (a `Player`) in
type-parameter position, a deliberate deviation noted in
[principles.md](principles.md). The checker needs a specific rule for it.

*Forcing function:* this is where most hand-waving dies — a `demands`
clause referencing a field that doesn't exist, an outcome function
returning the wrong type, a non-exhaustive outcome match.

### D. Placeholder and completeness audit

A dedicated pass that flags declared-but-undefined constructs and the
items the docs currently hand-wave — among them `BridgeAuction` and
`MeldingPhase` (both placeholders in [library.md](library.md)) and the
`NoLeadingSuitUntilBroken(suit)` generalization candidate. For each,
decide: define it now, or mark it an explicit typed stub the checker
tolerates with a warning. The goal is that hand-waving becomes a
**visible, enumerated list** rather than silent gaps.

This pass also owns **combination validity** ([decisions.md](decisions.md),
"Surface totality"): the checker encodes which clause combinations the runtime
supports, so an accepted-but-unsupported combination fails at check time with a
clear message — never at play time, and never silently. New grammar surface
lands with either runtime support or a checker rejection in the same change.

### E. Diagnostics and harness

Error reporting carries line and column plus the offending source line
with a marker (Lark's `get_context`) and the expected-token set; the
tool's value is the quality of these messages. The harness is a runner
that parses and checks every corpus game, asserts zero errors (or a known
stub allowlist), and runs in CI. Adding a game means adding a corpus
file; a red run means the spec is imprecise.

## Milestone boundary

v1 is done when the grammar parses every corpus game, the checker
resolves every name and type, and the only remaining gaps are an explicit,
enumerated stub list — nothing silent.

The next milestone is the **runtime net**: an executable interpreter plus
random-playout invariants (the game always terminates, the legal-move set
is never empty unless the state is terminal, scores reconcile). OpenSpiel
integration follows that, through the IR.

The random-playout interpreter ignores visibility: every legality rule
reads only the acting player's own hand plus public trick/game state, so a
uniform-random driver needs no per-observer projection. Deriving each
player's information set from zone visibility — the `information_state_tensor`
work — is the OpenSpiel milestone, not the runtime net.

## Risks and things to watch

- The surface syntax may be inconsistent across game files written at
  different points in the design. The first grammar pass will expose
  this and may require edits to the spec — that is the point, but budget
  for spec churn while the grammar stabilizes.
- The `<>` value-parameter deviation needs its own checker rule (see C);
  it is not ordinary generics.
- `demands`, `outcome`, and `routing` are functions. v1 type-checks their
  signatures but cannot validate their behavior — that is a runtime-net
  concern. Don't over-invest in statically proving runtime properties.
- Mechanic-internal state being in scope for rules via lexical nesting
  means symbol resolution must model mechanic state blocks, not just
  phase and game scopes.
