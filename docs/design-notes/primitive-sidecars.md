# Game primitives: from Primitive registries to sealed sidecars

*Status: design analysis / proposal — not a settled decision. The committed
spec is in [decisions.md](../decisions.md); the sanctioned role of game-local
Python is described in [library.md](../library.md) "Native functions" and the
history that produced it in [kernel-migration.md](../kernel-migration.md).
This note is about the package boundary and the primitive interface, not the
language surface.*

## 1. The problem: the stdlib is full of games

The standing policy after `instantiate` was deleted is clear: Python is
allowed for **pure value computation** — scorers, trick winners, legality
tables, bid ladders — and never for mechanics, movement, or decisions. Every
game-local primitive in the corpus conforms in spirit: `pot_share`,
`pinochle_meld_value`, `skat_next_bid`, `cribbage_show_value` are all reads.

The implementation of that policy drifted from its intent in three ways.
One remains open; the migration has closed the other two, and each is
marked with what closed it so this section states the live problem rather
than the original one:

1. **The language package contains game knowledge.** Game modules sit in
   `cardlang/runtime/` beside the engine core, and the large majority of
   `CALL_FUNCS` (`cardlang/builtins/functions.py`) is game-prefixed —
   a cluster per corpus game that needs primitives (`tichu_*`, `canasta_*`,
   `skat_*`, `gin_*`, ...), against a remainder of genuinely general names.
   That split is a proportion, not a tally, on purpose: the stages below
   move primitives out of the registry, so an exact count would rot behind
   them ([decisions.md](../decisions.md) "Prose names the registry, never
   the cardinality"). "Stdlib" is a misnomer for most of its contents.
   Adding a corpus game
   means editing three language-package files: the name registry,
   `signatures.py`, and a hand-written `match` arm in
   `cardlang/runtime/primitives.py` — a hand-enumerated dispatch over what
   should be a registry-derived one, the shape
   [decisions.md](../decisions.md) "Closed-domain completeness" warns
   against.
2. **Purity was conventional, not structural — CLOSED by stage 2.** A
   primitive used to receive `Ctx`, the engine's whole internal state
   object, and self-serve from it; nothing structural stopped a "pure
   read" from mutating state, making a decision, or reading a hidden zone
   it had no business seeing. It now receives values only, so those are
   not expressible. What survives is a granularity question, not a safety
   one (§3).
3. **A registered primitive is not a read at all.** A trace emitter for the
   playout harness, called as `let summary = f()` for the side effect alone,
   is harness instrumentation leaking into the rules text. No such call
   survives: §4's first stage evicted the emitters whose facts derive from
   movement views, and its third evicted the one whose facts are public
   state, which the harness reads off the terminal world where the
   information state reads it (issue #142).

That leaves item 1, which is stage 4's, and it is the reason this note
exists: the central placement is not protecting anything. It is a
migration artifact: the primitives were extracted *out of* `instantiate` mechanics
during the kernel migration, and the path of least resistance left them
where the mechanics had lived. What actually separates a sanctioned
primitive from `instantiate` hell is not where its file sits — it is what
its interface lets it touch.

## 2. The end state: sealed sidecars, declared in the game file

The target model has three parts.

**Narrow interface — values in, value out.** A primitive's signature names
value types (`Card`, `Player`, `Integer`, and a collection of one of them,
spelled `Collection<Card>`); it never
receives `Ctx` or any engine-internal handle. A function that computes a
cribbage show score from a hand and its starter cannot participate in
mechanics, mutate state, or observe anything it was not handed — the
property is structural, so it holds for the next game without review.

**A `primitives { }` declaration block in the game file.** The `.cardlang`
declares what it borrows from outside the DSL:

```
primitives {
  pot_share(p : Player) : Integer
      reads committed, hole, upcards
  skat_matadors(p : Player) : Integer
      reads hand[p], skat
}
```

An entry is a colon-row, like every other declaration in this language
(`zones`, `state`, `card_points`, `require`); the arrow an earlier sketch
carried is foreign to a surface that has never used one, and writing it gets
a rejection naming the colon form. The block sits beside `uses`, and a
library may not carry one: a primitive's meaning belongs to ONE game, so a
shared library declaring one would be the cross-game coupling the block ends.

The declaration carries the typed signature and — the load-bearing clause —
**what state and zones the implementation reads**. A bare name grants the
whole declaration (`reads hand`, every seat's); an indexed one narrows to the
instance the call names (`reads hand[p]`, keyed by a parameter of the same
entry), which is what makes a call stop materializing rows it never touches.
Pure reads are permitted
to touch hidden zones (`pinochle_meld_value` reads a concealed hand;
`skat_matadors` reads hand plus skat — the reason matadors must be a `let`
and never public state), so every primitive is a small information-flow
decision. Declared reads make that decision visible to the checker instead
of a reviewer: if a primitive reads `hand[declarer]` and its result flows
into public state, the implied reveal is derivable — the derived-info-set
story ([decisions.md](../decisions.md) "Knowledge, visibility, and the
projection model") extended to the one place Python still participates. That
derivation is recorded work, not built (issue #471); what the clause does
today is make the read declared and checked.

The resolver checks the block both ways: declared-but-unimplemented is a
compile diagnostic against the one names-only implementation index, and
implemented-but-undeclared is the corpus reconciliation pin's — the two sides
are independently authored, so reconciling them IS the check. The runtime
hands the implementation exactly the declared reads, nothing more.

**Co-location.** With the interface sealed and the declaration in the game
file, the implementation's location stops mattering for safety — so it moves
next to the game it serves, and the language package
(`cardlang/stdlib`, `cardlang/runtime`) becomes game-independent. The
genuinely general names stay in the stdlib: `team_of`, `player_holding`,
`suit_of`, `rank_value`, `card_points`, `error` (and `best_five_card_hand`,
specified in [library.md](../library.md) but not yet wired) — and
the poker-*family* selectors (`bring_in_seat`, `first_to_act_seat`)
graduate there at their second witness, per the usual corpus-first
promotion (the Hold'em games, with no bring-in, are not it). The pot-share
queries stay per-game — each declares its own reads — over the family-wide
`poker.side_pot_payouts`.

**What this is not.** The [[instantiate-lesson]]
([principles.md](../principles.md)) stands untouched: no control flow, no
movement, no decisions, no mutation in Python — hell was Python holding
mechanics and touching state invisibly, not Python computing a score from a
handful of cards. Sidecars do not reopen the escape hatch *because* the
interface cannot express one.

## 3. What blocks it today

- **Granularity, not the handle.** The `Ctx` coupling is gone: no game
  module names `Ctx`, `RuntimeState`, `ZoneStore` or `Chooser`, so a
  primitive structurally cannot mutate state, make a decision, or read a
  name its module never declared (stage 2; the crossed Owner Guard in
  `tests/test_primitive_narrowing.py`). What remains is a GRANULARITY
  question with two halves, and only one is still open. The name-keyed half
  is per-primitive for a game that declares a `primitives { }` block — its
  entry's own `reads` clause is the row, and an indexed read materializes
  the one instance the call names — and module-granular for a game that
  declares none, where `PRIMITIVE_READS` is the declaration. That is what
  3b's corpus sweep closes for the rest. The engine-structural half, the
  closed `EngineFacts` set, is whole under both regimes: its field names are
  not spellable in a `reads` clause, so every primitive receives every fact
  (issue #474). It is not only precision: an undeclared row is a row nothing
  materializes, and a unit test of one primitive declares only what that
  primitive touches.
- **The trace emitters.** A function called for a side effect rather than a
  value is not a primitive and cannot be declared as one. `coup_note_reveal`,
  `tichu_hand_summary` and `coup_game_summary` are gone from all three tables
  and from both games' rules text (including Coup's two dead `let`s); the
  harness derives their facts (`tests/playout_trace.py`) — the zone facts
  from the observation events the kernel already emits, and the public state
  variables off the terminal world, which is where the information state
  reads them. No call-position Primitive emits: a game module holds no
  tracer, and the shape that let one return its events as data retired with
  the last emitter.
- **The climb queries and outcome functions.** `bigtwo_lead_options` /
  `tichu_follows` and the game-named outcome functions are named in `round`
  clauses, not called as `f(...)`. Their interface is narrowed like every
  other primitive's (the round machinery binds their bundles through
  `stdlib.climb_row`), but they still need their own DECLARATION slots in
  the `primitives { }` block, because their signatures are mechanic-driven
  rather than free-form. Same principle, separate wiring.
- **Registry derivation.** Whatever the placement, registry, signatures, and
  dispatch should derive from the declarations rather than being maintained
  as three parallel tables with a hand-written `match`; a static test pins
  the derivation complete, per "Closed-domain completeness".

## 4. Why the stages run in this order

Each stage exists to shrink the problem the next one faces, which is what
fixes the order. Evicting the trace emitters comes first because they are
not primitives at all: removing them shrinks the domain every later stage
quantifies over, and it is independent of the rest. Narrowing the
interface comes before the declaration block so the corpus proves the
sealed signatures suffice before any grammar surface is spent on them — a
`primitives { }` block designed against signatures that turn out not to
close would be surface totality paid twice. The block precedes
co-location because the loader needs a declaration to resolve a moved
implementation from. Co-location comes last because, with the interface
sealed and the reads declared, placement no longer carries any safety
weight — it is the payoff, not the mechanism.

§5 is the PR-sized execution plan over this order, and is the authority on
each stage's scope, acceptance criteria, and status.

## 5. Execution plan

Ratified 2026-07-19: sidecars land before the combinations construct — see
[combination-scoring.md](combination-scoring.md).

PR-sized stages, each independently green under the full gates (bare
`mypy`, full `pytest -q`; the surface-totality audit wherever a registry
or grammar changes). Goldens policy is stated per stage — "byte-identical"
is the gauge except where noted.

**Stage 1 — evict the trace emitters (S, one PR). Landed.**
`coup_note_reveal` and `tichu_hand_summary` are out of all three tables and
their runtime modules, and their call sites (including Coup's dead
`let noted =` line) are out of the game files; the harness reproduces the
trace information from the observation events the kernel already emits
(`tests/playout_trace.py`, grid and ledger in
`tests/test_trace_emitter_eviction.py`). Goldens stayed byte-identical, so
no regeneration was needed. The misuse probe holds: calling a removed name
yields the standard unknown-function diagnostic. `coup_game_summary` follows
in stage 3's closing change, into the same grid and the same rejection
pattern.

**Stage 2 — narrow the interface (M). Landed.** For each game primitive, split surface from
implementation: the game-file call and its checker signature stay
EXACTLY as they are; the implementation is rewritten
values-in/value-out, and the dispatch layer binds what the
implementation may see and passes plain values. Scorers first, the
accumulator-readers (`pot_share`) and trick-terminal readers last.
Acceptance per PR: no `Ctx` reaches any game module (the crossed Owner Guard
in `tests/test_primitive_narrowing.py`), the declared-reads pins hold,
goldens byte-identical — this stage is a pure refactor.

What a primitive may see is TWO axes, not one. `PRIMITIVE_READS` is
the authored inventory of the name-keyed half only; the
engine-structural half (the seating ring, `team_of`/`teams`,
`rank_index`, the two round-state views, the acting player) had no
declaration anywhere and is now the closed `EngineFacts` field set in
`cardlang/runtime/narrowing.py`. Both bundles are MODULE-granular this
stage; the design note's §2 end state is per-primitive, which is what
stage 3's `reads` clause buys — and it buys two concrete things
beyond precision: a primitive stops paying to materialize rows it
never reads, and a fixture stops having to declare names its
primitive never touches.

All fifteen game modules are narrowed: no `Ctx`, `RuntimeState`,
`ZoneStore` or `Chooser` reaches any of them, pinned by the crossed
grid in `tests/test_primitive_narrowing.py` (every module x every
handle `Ctx` exposes, with nothing excused). The climb queries are
included — they are invoked by the round machinery rather than
through `call`, so `mechanics.py` binds their bundles via
`stdlib.climb_row`. Goldens byte-identical throughout.

A primitive that emits is not values-out. Four game-local trick winners
and `coup_game_summary` computed a value AND emitted the engine's own
trace vocabulary from a game-local site; emitting needs the tracer, which
is the handle this stage removes, so they returned `(value, events)` and
the dispatch performed the emission — same events, same order,
byte-identical goldens. The trick winners have since retired onto the
Trick Order, whose call form emits nothing, and the last emitter is
evicted, so no Primitive returns events and the shape is gone.

Risk closed: `pot_share`'s surface signature does NOT have to change.
The core under it is already pure and values-in — `stud.showdown_hands`
assembles the `hole`/`upcards` holdings, `poker.side_pot_payouts` layers
`in_hand`/`committed`/`folded` over them — so `pot_share(p :
Player) -> Integer` survives the narrowing intact.

**Stage 3 — the `primitives { }` block (the audit stage), split 3a/3b.**
Split because the block and the corpus sweep answer different questions
and the second is only safe once the first is checked: 3a lands the
surface and makes the coexistence window a CHECKED regime; 3b closes it.

**Stage 3a — the block, the checks, the derivation. Landed.** Grammar:
`name(param : Type, ...) : Type reads <names>`, a game clause beside
`uses`, with reject arms for the colon habit, the arrow, and a `=`
default. Resolve validates the block whole — duplicate entries, Builtin
and own-definition collisions, the five round-slot namespaces the block
does not cover, declared types against the spellable set, and every
`reads` name classified against the game's own `zones { }` and
`state { }` by one exhaustive classifier — and declared-but-unimplemented
is a compile diagnostic against the names-only implementation index. A
`reads` name denotes ONE declaration: the clause is a single flat
namespace over the four a keyed name can be declared in (the game's
`state { }`, a phase's, an indexed `zones { }` declaration, an unindexed
one), and a name in two of them is refused with the collision named,
including the cross-level pair the classification alone cannot reveal —
a phase's state variable against a zone, which classifies silently as
the zone. Whether a declared read SUFFICES for its implementation is a
fact about Python and stays the playout's to answer; it answers in the
declaration's own typed channel, naming the primitive and the clause to
extend.
Typecheck materializes the declared `Sig`, and it is that signature the
runtime's `coerce_args` freezes against. The driver builds the dispatch
table at load, so a primitive has no hand-written arm at all; a game's
`f(...)` calls resolve against its own namespace, which closes the
cross-game leakage (issue #364). The reads clause is per-primitive and per-CALL: an indexed
read materializes the one instance the call names. Scope Owner Guard:
the clause is checked for name validity and drives what the dispatch
hands over — the derived-reveal analysis (hidden reads flowing into
public state) is recorded follow-on work (issue #471), not silently
absent, and the engine-fact half of what a primitive sees stays whole
behind a refusal citing issue #474. ZERO corpus game files change; the
witness is a fixture game that declares, calls and plays
(`tests/fixtures/primitives_witness.cardlang`). Goldens byte-identical
over behavior and observation. Audit artifacts: the grid and its
completeness ledger in `tests/test_primitives_block.py`, the misuse
probes there, and the corpus reconciliation pin with both reddening
mutations demonstrated.

**Stage 3b — the corpus sweep and the legacy deletion. Done.** Every
game with a primitive gains its block (the lockstep rule), the authored
CALL-namespace `PRIMITIVE_READS` rows and the hand-written dispatch arms
for those names go, and the coexistence window closes. Not every row of a
declaring game goes: a row serving a WALLED namespace outlives its game's
block, because the block covers the call position while a climb or auction
binder holds its own row at load — so the reconciliation pin quantifies per
ROW, permitting exactly the rows those binders bind. Its own plan.
Behavior unchanged, goldens byte-identical. The sweep is done and the
tables that served the other route are deleted: no call-namespace row is
left, no runtime module holds a `call` arm for a Primitive, and a
Primitive's signature is a column on its implementation row rather than an
entry in the Builtins' table. Stage 3 is closed; stage 4 is next.

Which games have migrated is a query, not a number: the games whose
`primitives { }` block the corpus holds
(`rg -l 'primitives \{' docs/games/`), against the call-namespace rows
`PRIMITIVE_READS` still carries. That second set is empty: every row the
registry holds is a walled binder's, so a row standing there is a wall's
record and never an unswept game.

The wave's most common asymmetry is the one the [[phase-scoped-read]]
answers: an authored row may name a variable a PHASE declares, because a
row materializes against the live frame, while a declaration is a game
clause. The block reaches such a name by NAMING its phase — `reads
hand[p], trump_suit in hand_sequence` — which settles which declaration is
meant (sibling phases may legally declare one name) and commits the entry
to being called only where that phase runs. The phases one clause names
must nest, and the innermost of them is the one that sets the region — a
commitment the resolver checks rather than takes on trust. Which games carry one is the
derivation, run per game and not recalled: a row's `state_vars`
intersected with `phase_local_state_names`. Hoisting such a variable to
game level instead is not a neutral edit — a `repeat until` phase
re-initializes its state block on re-entry — so the tail is what keeps the
migration a migration rather than a game change.

**Stage 4 — co-locate (M).** Implementations move out of
`cardlang/runtime/` to live with their games; the loader resolves
them from the declaration; `cardlang/stdlib` keeps only
game-independent names (`team_of`, `player_holding`, `rank_value`,
poker-family selectors pending their second witness). Placement of
the moved files (a corpus-adjacent directory vs beside the game
docs) is the implementing session's one open decision. Goldens
byte-identical.

**Stage 5 — Salvo round 5 rides it (back in the experiment). Landed;
the arena run is what the round still owes.** The `standard54` deck row
carries registry-derived test coverage; salvo.cardlang takes the deck, an
explicit ranking with `Joker`, the joker branch in `loc_value`, the
filtered location deal, and a `primitives { salvo_combos(p : Player,
loc : Integer) : Integer }` sidecar carrying the frequency-core table (it
migrates to the `combinations` construct when tier 1 lands — the visible
burn-down §6 promises). The rig mirrors are written from Salvo's DESIGN.md
rather than from the sidecar, so their per-playout pins compare two
independent authorings of the table; the arena reports per-type combo
incidence, which is what re-tunes the values. This is also the stage that
made the declaration route explicit: a Primitive has no `call` arm, which
the dispatch-split grid, the signature reconciliation and the
declared-reads scan each state rather than assume. Arena re-runs and REPORT verdicts close the
round.

## 6. One pressure to preserve

The declaration block doubles as a per-game inventory of exactly what is
not yet expressible in the DSL — which is what these primitives are, and
why the tracker's generalization work (issues #115 and #140 — the
`scoring_component` subsystem, the shared combination model, in-DSL outcome
expressions) should keep burning them down. Sidecars being well-designed
must not make them so comfortable that the burn-down stops: a shrinking
`primitives { }` block is the visible score.
