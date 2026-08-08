# Principles

> A living design document for a domain-specific language describing card games
> played with one or more standard 52-card decks (plus jokers).
> Target runtime: OpenSpiel (for AI compatibility), though the DSL itself is
> designed independently and compiles to it later.

## High-level goal

Build a DSL that lets a card-game designer or enthusiast describe games (initially:
the standard-deck family — trick-takers, shedders, matchers, rummy, patience,
casino games) in a form that:

- Reads close to how a rulebook describes the game.
- Compresses common patterns into a reusable library of mechanics, rules, and
  move types.
- Supports variants as sibling games composed from a shared core.
- Compiles cleanly to OpenSpiel — **the invariant output target** — so existing
  imperfect-information AI algorithms (Information-Set MCTS, CFR, deep RL,
  determinization) work out of the box. The load-bearing, genuinely hard part is
  that information sets are *derived* from zone visibility, not hand-authored per
  game (see "Visibility as a first-class property" below); a design that cannot
  compile to OpenSpiel with correct derived info sets is not finished.
- Keeps no escape hatch to a lower-level API: the corpus proved the kernel
  can hold every mechanic, and the hand-written ones were retired (the
  `instantiate` construct is deleted). **The lesson that retired them
  stands: a hand-written mechanic bypasses info-set derivation, so any
  future escape hatch would be info-set *debt* against the OpenSpiel
  target, not a finished solution** (see
  [design-notes/kernel-extensibility.md](design-notes/kernel-extensibility.md), §6).

**Out of scope (initially):** Collectible card games (Magic, etc.) and
deck-builders. These need an effects-text sub-language and consciously
sub-Turing semantics. We'll revisit once the standard-deck DSL is solid.

## Design principles

These have emerged from working through three games and several rounds of
abstraction discussion. They guide tradeoffs as the design evolves.

### Corpus first, abstraction second

Don't design top-down from a clean theoretical model. Implement real games from
a real reference (Pagat is the chosen corpus) and let the primitives emerge.

### Three implementations before abstracting

Resist the temptation to extract a pattern after one or two examples. Wait
until three games have demonstrated the same pattern in the same place.
Examples in the current corpus: the trick `round` configuration stabilized once
Hearts, Getaway, and Spades all played tricks the same way;
constraint composition was validated against four games including
Pinochle, whose four-rule play stack is the most demanding case in
the corpus.

### Accepted means honored (total surface)

The corpus-first gate bounds *which* constructs exist; it never licenses a
construct that half-works. Once a construct is admitted, its surface is total:
every combination the grammar accepts either has defined, tested semantics or
is rejected loudly at check time. A clause that parses but is silently ignored
at runtime is the worst failure mode this project can ship — a designer who
writes a legal sentence must get the behavior or an error, never a silent
misread. The normative rule is [decisions.md](decisions.md), "Surface
totality".

### One spelling per concept

The language has two machine audiences beyond its human designers: OpenSpiel
(the compilation target) and LLMs, which read game files as player seats and
write them as authors under a generate–check–repair loop. Reading rewards an
English-shaped surface (a rulebook-shaped sentence is comprehensible without
simulating code, and recruits what a reader already knows about card-game
convention); writing punishes it, because English invites paraphrase — a
surface that reads like English implies *any* English phrasing works, when
exactly one does (the AppleScript trap; the success case is SQL: English-ish
but famously regular).

The resolution is a normative rule for all surface work: **friendliness comes
from familiar words in regular positions, never from accepting multiple
phrasings because they all sound right.** When a new form is proposed, the
test is: does it add a concept, or a second way to say an existing one? A
second spelling is a defect — it widens the paraphrase surface a model (or a
designer) can wander into, and it costs corpus-drift risk on top. The same
rule is why a loud, specific rejection matters doubly: it is the repair
signal the authoring loop runs on, and the corpus
([maintaining.md](maintaining.md) rule 2) is the few-shot library that
teaches the one true phrasing. The register itself — words for logic,
equality, and quantification; symbols for arithmetic, ordering, and state
change — is [decisions.md](decisions.md), "The expression register".

### Composition over inheritance

Games are bags of named mechanics + parameters + phase structure. No game
"inherits from" another, and none is a diff against another: **variants are
sibling games composed from a shared core**, each a complete description in its
own file. Mechanics are independently defined and reusable across games; what
two variants share is factored into a family library they both name
([decisions.md](decisions.md), "Family libraries"), and what differs each
states outright.

There is deliberately no delta mechanism — no way to write a game as
"the base, but with these changes". Three things rule it out. A delta cannot
satisfy the acceptance test that a non-player reads one file cold and plays a
hand: you cannot play from a diff. It is the inheritance-shaped answer, and its
presence pulls every adjacent design (imports especially) toward override.
And it inverts the work: a delta lets an author skip deciding what is essential
to the family versus incidental to one member, which is precisely the decision
factoring a shared core forces them to make.

This is the same intellectual move ECS made for game-engine entities, React
made when it moved to hooks, and the GoF book made back in 1994. The principle
applies because card-game mechanics are combinable behaviors, and inheritance
hierarchies are the wrong shape for combinable behaviors.

### Two-layer architecture: small core, rich library

The DSL has a small set of deep primitives (zones, phases, moves, rules,
events) that are domain-neutral. On top of them lives a library of named
card-game compositions (Trick, Bidding, MustFollowSuit, etc.) written in the
DSL itself. Most users only touch the library. The library is the language for
90% of users; the primitives are the language for the 10% pushing the edges.

This mirrors SQL (primitives + standard library of patterns), Python (language
+ stdlib), CSS (properties + named shorthand values). The library is what
makes the DSL ergonomic; the primitives are what make it extensible.

### Domain vocabulary in the syntax

When the domain has standardized terminology (trick, lead, follow, trump,
meld), build it into the language as named library items, not as user-defined
abstractions. The vocabulary IS the syntax. Lessons from PuzzleScript and
Forge: when domain words are first-class, the language reads like the domain
describes itself.

### Mainstream syntax unless the domain pushes back

When a syntactic choice has a dominant mainstream convention, follow
it. Readers arrive with expectations from other languages; gratuitous
novelty taxes them for no gain. Function calls use `()`, indexing uses
`[]`, type parameters use `<>`, blocks use `{}`, comments use `//`.
Deviate only when the mainstream form would be unwieldy for the
domain.

The clearest example of a deliberate deviation is library type
parameters like `PrivateHand<Owner>`. Strictly speaking, `Owner` is a
value (a specific Player), not a type — mainstream languages reserve
`<>` for type variables and would expect `PrivateHand(owner: Player)`
or similar. But `PrivateHand<Owner>` reads cleaner; the parameter is
"type-shaping" in the sense that it specializes the visibility
projection per-owner, and the angle-bracket form makes that visible
without the verbosity of a separate parameter clause. Zone declarations
read as one-liners (`hand[player] : Hand<player>`) rather than two-part
declarations, which is a real win at the call site.

The test for any future deviation: would the mainstream form make the
common case noticeably worse? If yes, deviate and document. If no,
follow convention.

### Visibility as a first-class property of zones

Every zone declares who can see its contents. Information sets are *derived*
from zone visibility plus the observation events emitted by moves — never
authored by hand. This is the GDL-II `sees`/`random` semantics, made
operational. Visibility belongs to the zone, not to operations on the zone.

**This derivation is the hardest, most load-bearing requirement in the whole
design.** It is what makes OpenSpiel an achievable target rather than a per-game
hand-coding exercise, and it is the property that any new mechanic or construct
must preserve. It is realized across the whole corpus: every game's decisions
run on kernel sites that emit observation events through the declared zone
projections, and the readiness proofs cover every corpus game
(`tests/openspiel_ready/`; the history of closing this per game is in
[kernel-migration.md](kernel-migration.md)). Any future construct that runs a
decision outside the observation-event stream reopens the debt — don't.

### Explicit over implicit; defaults instead of boilerplate

When something is a frequent pattern, make it the default — but make it
overridable explicitly. Example: `if_impossible: any card in hand` is the
default fallback for a rule. Rules that want strict behavior override it
explicitly. Cleanest of both worlds: rulebook reads cleanly, exceptions are
visible.

### The DSL should be readable enough that a non-player can learn the game from it

The acceptance test for any game block: a reader who doesn't know
the game can read the file cold and play a hand. Failure is
concrete — the reader's wrong guesses point to exactly which DSL
constructs aren't communicating their intent.

## Architectural principles

A summary of the design's load-bearing decisions. Each principle has
a pointer to the underlying specification in [decisions.md](decisions.md)
or elsewhere.

**Composition over inheritance.** A game is a tree of phases plus a
set of mechanics, rules, and scoring components composed by name.
There is no game-class hierarchy and no delta mechanism; variants are
sibling games over a shared core. (See "Composition over inheritance"
above.)

**Phases organize game time.** Phases are the primary structural
unit; they carry an active rule set, declare legal moves, and
optionally resolve to a typed outcome. Sub-phases inherit and extend
parent rule sets. (See [model.md](model.md).)

**Rules are reusable named constraints on move types.** A rule
constrains a specific move type with an applicability predicate and
a demand. Multiple active rules compose by intersection over the
candidate moves. (See [model.md](model.md), "What rules really are".)

**Move types are first-class.** A move type names a pattern of
transfer between zones; the same move type (e.g., `play_to_trick`)
is reused across games. Moves carry cards or resources. (See
[library.md](library.md), "Move types".)

**Zones hold cards or resources.** A zone is a typed container
(`Zone<Card>` or `Zone<Resource>`) parameterized by what it holds.
Library types (`Hand<Owner>`, `Deck`, `TrickPile`, `ChipStack<Owner>`,
etc.) compress common configurations into one-line declarations.
(See [library.md](library.md), "Types".)

**Visibility is per-observer projection assignment.** Every zone
declares which projection of its contents each observer sees
(identity, count_by_type, count_only, existence_only, trivial).
Knowledge is derived from observation events emitted as moves
project through these visibility settings. Perfect recall by default;
`forget` is the documented escape hatch. (See [decisions.md](decisions.md),
"Knowledge, visibility, and the projection model".)

**State is lexically scoped.** A variable lives as long as the phase
instance that lexically encloses its declaration. Refactoring a
phase carries its state with it. Mutation within a phase body is
sequential, with `apply_components:` as the one batched-write
exception. (See [decisions.md](decisions.md), "State scoping" and
"Mutation semantics".)

**Round forms own their internal state.** The trick, auction, betting, and
climbing forms of the kernel `round` thread their accumulator through the
round's own state frame (readable as `state.x` during and just after the
round); games don't redeclare what a form tracks. No Python mechanic
remains — every game is DSL over the kernel. (See
[library.md](library.md), "Mechanics".)

**Typed phase outcomes route control flow at the phase boundary.**
A phase can resolve to one of several typed outcomes; the enclosing
phase pattern-matches on the outcome. Avoids exception-style escape
ceremony for legitimate failure cases. (See [decisions.md](decisions.md),
"Typed phase outcomes".)

**Scoring composes from named components.** Scoring is `apply_components:
[Component1, Component2, ...]` summing each component's `ScoreDelta`.
Threshold-triggered bonuses (game/rubber bonuses, bag-overflow
penalties) remain imperative post-component checks. (See
[library.md](library.md), "Scoring components".)

**Typed object model.** Cards, players, teams, zones,
contracts, hand results, and other game objects are typed.
User-defined types support optional `derived` fields. Stdlib types
(Card, Resource, Player, Partnership, Seating, Zone, ZoneContents)
are built in. (See [library.md](library.md), "Types" and
[decisions.md](decisions.md), "Typed object model".)

**Vocabulary in the syntax.** Domain words from rulebooks — the `round`
construct (its trick / auction / betting forms), `Hand`, `Deck`, `Discard`,
`Muck`, `ChipStack`, `ChallengeWindow`, `MustFollowSuit` — are first-class names
in the library rather than abstractions the user has to invent. (See "Domain
vocabulary in the syntax" above and [library.md](library.md).)

**Two-layer architecture.** A small set of deep primitives
supports a richer library of named compositions. Most users
write only in the library layer; the primitives are available when
the library doesn't cover a case. (See "Two-layer architecture"
above; [model.md](model.md) for primitives, [library.md](library.md)
for the library.)

**Defaults aligned to the common case.**

- `if_impossible` on a rule: any move legal under this move type.
- Visibility on a zone: identity-projection to all unless declared otherwise.
- State scoping: lexical, by the enclosing phase.
- Mutation within a phase body: sequential.
- Knowledge tracking: perfect-recall.
- Rules in a sub-phase: added to the parent's rule set.
