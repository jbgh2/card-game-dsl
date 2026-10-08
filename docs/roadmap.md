# Roadmap

The deferred **work** lives in the GitHub tracker
(<https://github.com/jbgh2/card-game-dsl/issues>), not here. This file keeps
only the two things that are not work items: what is out of scope for the
current phase, and the ledger of grammar surface the checker deliberately
defers. Both are properties of the language as it stands, so they belong with
the spec.

## Where the work is tracked

- **What is being finished now, and what comes after** — the open
  [milestones](https://github.com/jbgh2/card-game-dsl/milestones) are the
  units in progress, and [issue #143](https://github.com/jbgh2/card-game-dsl/issues/143),
  the pinned queue, orders the units after them
  ([harness.md](harness.md), "The Ready Front"). Every unit names the
  Destination below that it advances.
- **Open design questions and their priority** —
  [open-questions/_index.md](open-questions/_index.md).
- **The game pipeline** — [games/_candidates.md](games/_candidates.md).
- **Everything else** — one issue per deferred item. An issue blocked on a
  corpus game carries `blocked:needs-witness` and names that game in its body;
  `epic` issues are checklist containers for multi-stage workstreams.

A deferred cell cites its issue as `issue #N` beside the guard that makes it
loud (decisions.md "Closed-domain completeness"). Every issue's
`## Provenance` line names the roadmap item it came from.

One carve-out: a *designed constraint* — a recorded trap, deliberately
not-to-be-fixed — is not work and records at the construct it constrains
rather than in an issue, saying that it is designed. See CLAUDE.md, "The
tracker".

## Destinations

A Destination is a finished state of the project, stated in the present
tense, with the query that reads today's distance from it. The
Destinations say what every unit of work builds toward; the milestones and
[issue #143](https://github.com/jbgh2/card-game-dsl/issues/143) say which
unit is next ([harness.md](harness.md), "The work graph"). Each milestone's
description opens with the Destination it advances, or `Upkeep` when it
advances none, and at most one open milestone is Upkeep. The direction
review reads the distances every run (`python -m tools.destinations`,
derived on demand and never checked in) and promotes the next unit of
whichever Destination has not moved. Only the operator adds or retires a
Destination.

- **OpenSpiel plays every game.** Every corpus game, as its rules source
  states it, is a game OpenSpiel's imperfect-information algorithms run on:
  the IS-MCTS family determinizes it, tensor-based learners have an
  information-state tensor derived from zone visibility, and chance is
  explicit. Held by [#141](https://github.com/jbgh2/card-game-dsl/issues/141),
  [#139](https://github.com/jbgh2/card-game-dsl/issues/139),
  [#99](https://github.com/jbgh2/card-game-dsl/issues/99) and the reads in
  [#469](https://github.com/jbgh2/card-game-dsl/issues/469). Distance: the
  adapter's tensor and determinization facts, and the read ledger's unread
  games.
- **Python only scores.** A game is written in the DSL alone; where a
  game names native Python, the function scores a holding and decides
  nothing else — no legality, no bid ladder, no seat selection, no
  combination model. Held by
  [#248](https://github.com/jbgh2/card-game-dsl/issues/248). Distance:
  every game-local native the corpus names, with its call sites, read
  against that sentence.
- **One meaning, written once.** Each construct's meaning is stated in one
  place and both the checker and the runtime derive from it; a name
  resolves by declaration, never by precedence; a new game adds no
  grammar. Held by
  [open-questions/name-namespaces.md](open-questions/name-namespaces.md)
  and the class the direction review tracks as "a sentence the checker
  passes does something else". Distance: grammar rules and keywords
  against corpus size at every verdict, and the class's inflow against its
  closure (the review's fourth check).
- **Boards.** The topology witness ladder in
  [games/_candidates.md](games/_candidates.md) plays: a board game enters
  the corpus by the same path as a card game, with the two open questions
  the ladder's first rungs force settled. Held by
  [design-notes/board-topology.md](design-notes/board-topology.md).
  Distance: the ladder's rungs in the corpus.

## Out of scope

CCG-style card effects (Magic, Yu-Gi-Oh!) are out of initial scope; the Forge
text-DSL pattern (one mini-language per card) is the reference if and when we
tackle them. Deck-builders are deferred alongside them, though the deferral is
narrower than the grouping suggests —
[design-notes/deck-builder-onramp.md](design-notes/deck-builder-onramp.md)
reframes it. Per-card mutable attributes (tapping, counters, status effects)
are not part of the surface, since the oriented- and CCG-style card state they
would serve is what is deferred here.

Collusion and cheating are out of scope, and the engine assumes Honest
Play: a seat discloses what the rules say it must, and information
reaches it through its zones' declared projections, the public state
variables, and the observations its moves emit (decisions.md, "Honest
Play is assumed, so a rule reading concealed cards is mis-modelled"). Signalling outside the declared moves,
misreporting a holding, peeking past a projection, and what a game does
when it catches one are undesigned; issue #717 holds what relaxing the
assumption would take. A bluff is not in this list — a move whose truth
nothing checks is already expressible.

## Grammar surface deferred by the checker

Grammatically valid forms are statically rejected until a game needs them
(decisions.md "Surface totality": rejected loudly rather than silently
ignored). Movements: the per-transfer `visibility =` override (visibility derives from
the declared zone types; the override's semantics is
[open-questions/move-level-visibility.md](open-questions/move-level-visibility.md)),
and resource transfers (`move 2 chips …` — the corpus keeps chips/coins as
Integer state; moving resources through zones is undesigned). Elsewhere:
`override` rule deltas in `active_rules:`, `before_each`/`after_each` on a
phase with no iteration, transition events other than `play_to_trick`, a
trick or climb round naming a move type its form cannot run, and duplicate
`state { }` blocks.
Rules bind at one decision site — the trick round's card decision — so the
rule surface that cannot fire there is rejected with it: a `constrains:`
naming another move type or omitted entirely, and a rule carrying neither `demands:` nor
`exempts:` (it cannot change what is legal). Counts and move shapes are
stated where the move is made instead — a transfer's `chosen N`, a move
type's `when:` guard. These lift together when rule application widens
beyond trick play, which is
[open-questions/rule-scope-beyond-trick-play.md](open-questions/rule-scope-beyond-trick-play.md)
— the same cliff as the already-deferred non-`play_to_trick` transition
events above. One consequence is recorded here because it was a real
narrowing: a family library could not declare a rule, because an
enforceable rule must name a zone and a `requires { }` contract named
state only. **The contract now names zones too**, so that particular
blockage is gone; whether a library rule is useful end to end is
untested, because no library declares one. The standard library's rules
are spliced by a separate path that has no contract to violate — which
is epic #181.
Counting is the card-query form (`number of cards in … [where <pred>]`);
the retired `count over` comprehension (whose body was silently
discarded) does not parse.
Rule-template parameters (`rule X(suit: Suit)`) support the Suit domain
only, and one instantiation per rule name per game — both rejected loudly,
lifted when a game needs more. Quantifier / `for each` roles are the closed
set player/team/suit/rank; `each … simultaneously` is player-only.
Value-domain-indexed state (`state { seen[rank] : Integer = 0 }` as a
per-rank tally) is rejected: a zone or state index must be a
`zone_key_of` domain (player/team — `cardlang/domains.py`), because the
runtime keys those stores by an observer-anchored member set. A family
library's `requires { seen[rank] : Integer }` is rejected on the same
grounds and to the library's own author, since a requirement names
state the including game declares and no game may declare that index. A
per-value tally is expressible today as per-player state plus a query;
lift the guard when a game genuinely wants the store (the runtime's
key-set plumbing already reads the domain table, so the extension is a
table row plus an observation-encoding decision, not a rewrite).
The `turns` form has no `direction` override clause (rotation follows the
game's declared direction; not grammar until a game needs a mid-game or
per-loop override). Joint-predicate selection: `jointly` under a `random`
or dealt selection is rejected (a subset decision needs a decider; a
uniform-random satisfying subset has no corpus user), `some` without
`jointly` is rejected (nothing owns the size), `jointly` with `to each`
is rejected (each destination seat would become its own subset decider —
a real semantic no game has asked for; note the pre-existing non-joint
`chosen … to each` DOES reassign the decider per parcel the same way,
unexercised by the corpus and undocumented — the same decision awaits
whichever game first wants either shape), and the subset enumeration
refuses source pools past 16 cards at runtime rather than hanging
(`cardlang/runtime/execute.py`, `_JOINT_ENUMERATION_BOUND`). Transfer
amounts: negative is a typed runtime error everywhere and a zero `chosen`
amount is refused as a vacuous decision (`_check_count`), while a zero
dealt/`random` amount stays an accepted no-op (a computed "deal what
remains" may legitimately be zero). On the
OpenSpiel side, a joint predicate must root in a call with a registered
subset codec (`cardlang/runtime/primitives.py`, `joint_codec_function` — the
climb-codec pattern); an inline or unregistered predicate, a game mixing
climb and joint selections, or two joint predicates wanting different
codecs are each a loud `NotImplementedError` at action-space
construction, lifted when a game forces the composed-combo-block design.
Joint selections on a deck with duplicate identical cards (pinochle48,
doppelkopf48, coup15, canasta108) are refused there too: the combo block
canonicalizes subsets by frozenset, which collapses copies — {K♠, K♠}
would collide with {K♠} — so the encoding needs a multiset-safe
canonicalization no game has forced (Canasta, the first duplicate-deck
melding game, deliberately encodes melds per card through the card block
instead — copies share an id soundly there, since identical cards are
interchangeable).
