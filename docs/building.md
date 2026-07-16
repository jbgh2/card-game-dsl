# Building the front end

This is the execution blueprint for the v1 tooling whose rationale lives in
[implementation.md](implementation.md). That file is the *why* — the goal, the
scope boundary, and the settled decisions (Python + Lark, the validated IR as
the contract, the corpus as test suite). This file is the *how* — the
architecture, the disciplined workflow, and the gates that keep "no hand-waving"
mechanical rather than aspirational.

The tool is a Python package, `cardlang`. Its job is to take a game written in
the DSL and carry it through to a validated, serializable IR, failing loudly at
the exact point where the spec is still imprecise.

## The pass pipeline

The front end is a sequence of pure stages, each a function from one typed value
to the next. No stage reaches forward; a later stage consumes only the previous
stage's output type. This is what makes each stage independently testable and
lets the IR be snapshotted.

```
source (.md fenced block)
   │  extract
   ▼
raw DSL text ──parse──▶ typed AST ──resolve──▶ resolved AST ──typecheck──▶
   checked AST ──expand──▶ procedure-free AST ──deck-capacity──▶ checked AST
      ├──▶ runtime / OpenSpiel adapter (consume the checked AST directly)
      └──emit──▶ validated IR (JSON — sidecar for the CLI and goldens)
```

- **extract** — game files are Markdown; the DSL lives in fenced code blocks. A
  small, well-tested extractor pulls the block(s) and feeds every downstream
  stage. It is the only stage that knows about Markdown.
- **parse** — a Lark grammar plus a `Transformer` produces a typed AST. Grammar
  development starts on the Earley parser (it parses any context-free grammar and
  reports ambiguity — itself a crispness check) and tightens toward LALR (which
  forces a deterministic grammar). One AST node kind per primitive in
  [model.md](model.md).
- **resolve** — name resolution over lexically-nested scopes (game → phase →
  sub-phase → mechanic-internal `state {}`, per [decisions.md](decisions.md),
  "State scoping"). Every `constrains:`, every `active_rules:` entry, every
  zone/type/rule/mechanic reference, and every `state.*` access resolves to a
  declaration, or fails with a span.
- **typecheck** — the typed object model from [decisions.md](decisions.md):
  zone parameterization (`Hand<Owner>`), the `<>` value-parameter rule (a
  `Player` in type-parameter position — its own rule, not ordinary generics),
  visibility-projection enums, rule-clause types (`applies_when` is a predicate,
  `demands` returns candidate moves, `if_impossible` is a fallback), mechanic
  `outcome`/`routing` signatures, scoring components producing `ScoreDelta`, and
  exhaustiveness of matches on typed phase/mechanic outcomes.
- **expand** — procedure expansion: every `run` site is spliced by value into a
  hygienic `Block` and `Game.procedures` is emptied, so no later stage ever sees
  a `RunStmt`. It sits after typecheck (a procedure's parameter types can only be
  enforced while the call site exists) and before deck-capacity (everything
  downstream is entitled to a procedure-free tree).
- **deck-capacity** — a conservative static check: for each per-hand window (the
  deals between deck resets) it bounds the worst-case cards dealt from the deck and
  errors if that exceeds the deck's capacity, so a too-large player count (an
  8-player Seven-Card Stud, a 5-player Bridge) is a compile error, not a runtime
  crash on an exhausted deck. It never rejects a valid game: a deal it cannot bound
  — `deal all`, a non-literal amount, a deal inside `repeat until` — contributes
  nothing; a guarded deal (`if`) counts as taken and a per-player deal (`for each
  player` / `to each`) multiplies by the player count (the high end of a range).
- **emit** — renders the checked AST as the validated IR. This is a **sidecar**:
  the runtime and the OpenSpiel adapter consume the checked AST directly
  (`pipeline.check_source` → `runtime/driver.play_game`); the IR serves the CLI
  and the golden-file snapshots, kept in lockstep by the goldens.

Each pass states its binding contract — what it assumes, what it establishes,
and what becomes illegal after it — in the `Contract` block of its module
docstring (`cardlang/parse.py` through `cardlang/ir.py`). Those blocks are the
authoritative per-pass reference; a check is placed by consulting the owning
pass's contract, per [decisions.md](decisions.md), "Closed-domain completeness"
(write-time triage).

## The AST↔IR seam

The IR is the **resolved AST — not desugared**. Library
constructs (`Hand<Owner>`, the `round` construct — including its betting form —
and `ChallengeWindow`) are preserved as first-class IR nodes carrying their
resolved bindings. They are not lowered to primitives: `round`
and the challenge mechanic are control-flow units whose semantics live in the
runtime's interpreters (`cardlang/runtime/mechanics.py`) — lowering them in the
IR would state that meaning a second time, and the two would drift. Keeping the
IR at the resolved-AST level keeps it in lockstep with the checked AST the
runtime and OpenSpiel adapter consume, and keeps a non-Python runtime an open
choice: the serialized IR is the boundary such a runtime would read (see
[implementation.md](implementation.md), "The validated IR is the contract").
The front end stops at this seam.

## The expression sublanguage

A distinct grammar module, reused everywhere an expression appears: `applies_when`
predicates, the `demands`/`routing`/`outcome` functions, `let` bindings,
comprehensions (`sum of (if … then … elif … else …) over cards in captured[p]`), choice
expressions (`<actor> chooses <description>`), and zone-query chains
(`cards in hand where card.suit is state.led_suit`). This is the hard
part of the grammar and where most of the corpus's informal prose hides. It has
its own node hierarchy, its own fixtures, and its own type rules, checked against
the stdlib `ZoneContents` query API in [decisions.md](decisions.md).

## Typed-AST discipline

AST nodes are frozen dataclasses forming a closed union (`Node = Phase | Rule |
MoveType | …`). Every consumer dispatches with structural `match` ending in
`typing.assert_never(node)`, and the package is checked under `mypy --strict`.
Adding a node kind without handling it in every consumer is therefore a type
error, not a silent gap. This is the mechanism that makes exhaustiveness a
checked invariant rather than a hope, recovering in Python the discipline an ML
or Rust front end would get from the compiler.

## Formalization: the four categories

A large fraction of the corpus is English standing in for semantics — `demands:
the move must consist of exactly 3 cards`, `let bringer = player with lowest door
card (ties: lowest suit)`, `phase hand repeats while at least 2 players want to
play`. A grammar cannot parse English, so formalizing the corpus is in scope and
drives the grammar order: a game that still contains un-triaged prose cannot
reach green.

Every construct is classified into exactly one category. The two not-yet-formal
categories are kept rigorously apart — *deferred implementation* (the spec is
complete, only runtime code is missing) is a different thing from a *language gap*
(the spec cannot express it), and conflating them is how hand-waving hides. They
live in different places and have different exit conditions.

- **`formal`** — already machine-parseable. Most phase/zone/rule scaffolding.

- **`needs-formalizing`** — prose standing in for something the current DSL can
  already express (a predicate, a zone query, a `let`, an operation body).
  Rewritten into formal syntax now, with no residue. Includes large operation
  bodies (e.g. `reconcile_pots`) when existing constructs suffice.

- **`runtime-primitive`** — a pure, total stdlib function with a complete,
  unambiguous typed signature and standard, well-known semantics whose *body is a
  runtime computation* (e.g. `best_five_card_hand : Set<Card> → HandRank`). This
  is not a gap: the DSL fully expresses the interface, and the front end — a
  compile-time net — resolves and type-checks every call site against the
  signature. The body belongs to the deferred runtime milestone. These are
  ordinary stdlib declarations in `cardlang/stdlib/`, enumerated with their
  signatures so the deferred-implementation surface is visible, not implied.

- **`language-gap`** — a construct the DSL genuinely cannot yet express: a real
  syntactic or semantic limitation. Not a stub the checker waves through; an open
  design question, written up in `open-questions/<slug>.md`
  ([maintaining.md](maintaining.md)), named by the exact game and construct that
  exposes it, and either resolved (extend the language, after which it becomes
  `needs-formalizing`) or explicitly deferred with the missing feature stated.
  The v1 target is zero unresolved language gaps in the corpus; any that remain
  are loud, named, and tied to a specific open question — never a silent body.

The triage table lives in this file (below) and classifies every non-`formal`
construct. Worked example — `reconcile_pots`: the triage *decides* rather than
parking it. If the pot-restructuring is expressible with existing loops, `let`,
`transfer`, and zone-queries, it is `needs-formalizing` and the body is written.
If it needs something the language lacks — e.g. referring to "the pot that was
current at the time a player folded" (event-indexed state) — that specific missing
feature becomes a `language-gap` open question. The prose-comment algorithm in the
corpus today is not an acceptable resting state under either outcome.

The stdlib of query primitives grows so prose becomes formal calls. The library
already names many query shapes (`highest … over`, `cards in … where`, `offset_by`); the
rest are formalized as named, typed stdlib functions defined as data in
`cardlang/stdlib/`. This is corpus-first: a primitive enters the stdlib because a
game needs it. Unicode operators (`=>`, `union`, `*` for `⇒`, `∪`, `×`) get ASCII
spellings fixed by the grammar, and the game files are updated to match.

**Grammar-growth guard.** Before adding a production for a new surface verb,
classify it into an existing operation family (movement sugar, an epistemic
op; see [decisions.md](decisions.md) "The operation vocabulary") or an
existing primitive; add a new family or core production only if it genuinely
fits none. A rulebook verb is presumed sugar over an existing primitive until
proven otherwise. This is the standing guard against a per-verb production
explosion — the failure mode that bakes the library into the core and
multiplies IR node-kinds.

### Triage table

Populated as games are brought into the harness. One row per non-`formal`
construct.

**Hearts.** The formalized form is `docs/games/hearts.cardlang`, read alongside
`docs/games/hearts.md`.

| Construct (prose in hearts.md) | Category | Resolution in hearts.cardlang |
|--------------------------------|----------|-------------------------------|
| `repeats until any cumulative_score >= 100` | needs-formalizing | explicit quantifier: `repeat until (any player where cumulative_score[player] >= 100)` |
| `repeat until all hands empty` | needs-formalizing | `repeat until (all players where hand[player] is empty)` |
| `sum over captured[p]: if … then …` | needs-formalizing | implicit binder: `sum of … over cards in captured[p]` |
| `queen_of_spades`, `2 of clubs` | needs-formalizing | card literal `RANK of SUIT`: `Q of spades`, `2 of clubs` |
| shoot-the-moon (`if p shot the moon: 0 else 26`) | needs-formalizing | explicit: shooter (`base[p] is 26`) scores 0, others 26 |
| `the move must consist of exactly 3 cards` | decision: demand-clause-shape | `demands: actions where action.card_count is 3` — `demands` has two forms: a card-set filter, or `actions where <move-predicate>`. Recurs in Stud/Cribbage/Tichu; promote to decisions.md |
| `player_holding(2 of clubs)` | runtime-primitive | `player_holding(Card) -> Player` (stdlib query) |
| `highest_of_led_suit` (round outcome) | runtime-primitive | `(played, state) -> Player` named outcome function |
| `hand.where(c => …)`, `hand.cards_of_suit(s)` | runtime-primitive | the card queries: `cards in hand where <pred>` (binds `card`) |
| `move.card_count` | runtime-primitive | `Move.card_count -> Integer` |
| `play_to_trick`, `transfer_between_hands` | runtime-primitive | move types (library.md); the trick itself is the formal `round` construct |
| `transition_to: … when any heart_played event fires` | decision (existing) | no ad-hoc events: `transition_to: hearts_broken when play_to_trick where action.card.suit is hearts` — the move-event + `where` form already used by `triggered_by:` (decisions.md, "Triggered scoring components"; "Event-driven sub-phase transitions") |
| `outcome of last trick from first_trick` | decision: hoist-to-scope | construct removed; `leader` lives in the enclosing phase state, seeded by `first_trick` and read by `play` via lexical scope. Bare `outcome` (the just-run mechanic) stays. Affects Bridge/Getaway too |

## Disciplined workflow

"Disciplined" here means mechanics, not good intentions.

1. **Walking skeleton first.** Before any real corpus game, the entire pipeline
   (extract → parse → resolve → typecheck → emit IR) runs end-to-end on a
   synthetic minimal game — a deck, a deal, one rule, one trick. Every seam is
   proven before any breadth.
2. **Stage the corpus by construct-count, simplest first.** Roughly: Hearts /
   Getaway → Spades / Oh Hell → Schnapsen / Cribbage → Pinochle / Bridge → Skat /
   Tarot → Stud → Tichu / Coup (the climbing engine and the response windows
   last). Each new
   game is *expected* to expose new constructs — that is the forcing function,
   not a failure.
3. **TDD ladder, one construct per step.** A failing fixture (red) → the minimal
   grammar/resolver/checker change → green. Constructs are never batched. See the
   project's test-driven-development discipline.
4. **IR golden-file snapshots.** Each game and each key fixture has a checked-in
   IR snapshot under `tests/golden/`. IR changes surface as reviewable diffs, so
   an accidental semantic shift cannot slip through. Regeneration is an explicit,
   reviewed step.
5. **The shape of one disciplined commit:** one construct; a fixture that was red
   is now green; the IR snapshot diff is reviewed; the full corpus harness is
   still green; neither enumeration grew silently.
6. **Composition matrix per construct.** A new or extended construct's fixture
   set enumerates its composition points — the host production's other optional
   clauses × the executor branches that receive the node — with one test (or one
   static-rejection test) per cell ([decisions.md](decisions.md), "Surface
   totality"). "Accepted-but-ignored" — parses, runs, silently drops a clause —
   is the defect class the matrix exists to prevent.

## CI gates

- The corpus harness is green on every commit.
- Two enumerations, two ratchets. The `runtime-primitive` list is a declared,
  signatured stdlib surface — it may grow, but only with a typed signature, never
  a bare name. The `language-gap` list (open questions) must not grow silently and
  is driven toward zero — a new gap is admissible only as an explicit, named
  open-questions entry.
- `mypy --strict` is clean (the exhaustiveness invariant).
- Golden snapshots match.
- The composition matrix holds: every optional-clause combination the grammar
  accepts is either exercised by a fixture or rejected by the checker with a
  rejection fixture — no accepted-but-ignored cells.

## Module layout

```
pyproject.toml          # package + mypy(strict) + pytest config
cardlang/
  grammar/cardlang.lark # surface grammar; expression sublanguage as a module
  ast/nodes.py          # frozen dataclasses, closed Node union
  parse.py              # Lark + Transformer -> typed AST
  extract.py            # pull DSL from markdown fenced blocks
  resolve.py            # lexical-scope name resolution
  typecheck.py          # typed object model + exhaustiveness
  ir.py                 # type-annotated AST -> validated IR (JSON)
  diagnostics.py        # span-precise errors (Lark get_context)
  stdlib/               # library catalogue as data: types, zones, mechanics, queries
  cli.py                # parse+check a single file; emit IR
tests/
  fixtures/             # synthetic minimal game + per-construct red/green cases
  golden/               # IR snapshots
  test_corpus.py        # harness: every docs/games/*.md parses + checks
```

## Build phases

- **0. Skeleton** — package, CI, `mypy --strict`, the extractor, and the
  walking-skeleton game carried through the full pipeline.
- **A. Grammar + expression sublanguage** — Earley → LALR; the structural grammar
  plus the expression module. Drives the formalization triage.
- **B. Resolve** — lexical scopes including mechanic-internal `state {}`.
- **C. Typecheck** — the typed object model, the `<>` value-parameter rule, and
  outcome exhaustiveness.
- **D. Completeness audit** — the triage table classifying every non-`formal`
  construct: formalize the `needs-formalizing` ones, declare the
  `runtime-primitive`s with signatures, and file each `language-gap` as a named
  open question (`BridgeAuction` and `MeldingPhase` are the seed entries).
- **E. Diagnostics + harness** — span-precise errors; the corpus runner and the
  ratchet checks in CI.

Formalizing the corpus runs throughout, game by game, in lockstep with A–C.

## Milestone boundary

v1 is done when the grammar parses every corpus game, the checker resolves every
name and type, the `runtime-primitive` surface is fully signatured, and
`language-gap` is empty (or every remaining gap is a named, deferred open
question) — nothing silent, and deferred implementation never confused with a
language gap. Past this boundary sits the runtime net (the interpreter in
`cardlang/runtime/` plus random-playout invariants), which consumes the
checked AST; see [implementation.md](implementation.md), "Milestone boundary".
