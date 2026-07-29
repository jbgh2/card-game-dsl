# Roadmap

The deferred **work** lives in the GitHub tracker
(<https://github.com/jbgh2/card-game-dsl/issues>), not here. This file keeps
only the two things that are not work items: what is out of scope for the
current phase, and the ledger of grammar surface the checker deliberately
defers. Both are properties of the language as it stands, so they belong with
the spec.

## Where the work is tracked

- **Cross-cutting task sequence** — [issue #143](https://github.com/jbgh2/card-game-dsl/issues/143),
  the pinned ordering issue. It is the authority on what to build next and in
  what order.
- **Open design questions and their priority** —
  [open-questions/_index.md](open-questions/_index.md).
- **The game pipeline** — [games/_candidates.md](games/_candidates.md).
- **Everything else** — one issue per deferred item. An issue blocked on a
  corpus game carries `blocked:needs-witness` and names that game in its body;
  `epic` issues are checklist containers for multi-stage workstreams.

A deferred cell recorded in a completeness ledger cites its issue as
`issue #N` (decisions.md "Closed-domain completeness"). Every issue's
`## Provenance` line names the roadmap item it came from.

One carve-out: a residual that is *not work* — a recorded constraint or trap,
deliberately not-to-be-fixed — records in its own test-module ledger rather
than in an issue, and that ledger says so. See CLAUDE.md, "The tracker".

## Out of scope

CCG-style card effects (Magic, Yu-Gi-Oh!) are out of initial scope; the Forge
text-DSL pattern (one mini-language per card) is the reference if and when we
tackle them. Deck-builders are deferred alongside them, though the deferral is
narrower than the grouping suggests —
[design-notes/deck-builder-onramp.md](design-notes/deck-builder-onramp.md)
reframes it. Per-card mutable attributes (tapping, counters, status effects)
are not part of the surface, since the oriented- and CCG-style card state they
would serve is what is deferred here.

## Grammar surface deferred by the checker

Grammatically valid forms are statically rejected until a game needs them
(decisions.md "Surface totality": rejected loudly rather than silently
ignored). Movements: the
`in <zone>` form (the verb implying its destination — `muck one cards in
discard`), the per-movement `visibility =` override (visibility derives from
the declared zone types; the override's semantics is
[open-questions/move-level-visibility.md](open-questions/move-level-visibility.md)),
and resource movements (`move 2 chips …` — the corpus keeps chips/coins as
Integer state; moving resources through zones is undesigned). Elsewhere:
`override` rule deltas in `active_rules:`, `before_each`/`after_each` on a
phase with no iteration, transition events other than `play_to_trick`, a
trick round naming a move type its form cannot run, duplicate
`state { }` blocks, and named call arguments (`f(x = 1)` — rejected until
a game needs the surface; positional arguments are the implemented form).
Rules bind at one decision site — the trick round's card decision — so the
rule surface that cannot fire there is rejected with it: a `constrains:`
naming another move type or omitted entirely, the `demands: actions where
<pred>` move-shape predicate, and a rule carrying neither `demands:` nor
`exempts:` (it cannot change what is legal). Counts and move shapes are
stated where the move is made instead — a movement's `chosen N`, a move
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
grounds and in the library's own currency, since a requirement names
state the including game declares and no game may declare that index. A
per-value tally is expressible today as per-player state plus a query;
lift the wall when a game genuinely wants the store (the runtime's
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
(`cardlang/runtime/execute.py`, `_JOINT_ENUMERATION_BOUND`). Movement
amounts: negative is a typed runtime error everywhere and a zero `chosen`
amount is refused as a vacuous decision (`_check_count`), while a zero
dealt/`random` amount stays an accepted no-op (a computed "deal what
remains" may legitimately be zero). On the
OpenSpiel side, a joint predicate must root in a call with a registered
subset codec (`cardlang/runtime/stdlib.py`, `joint_codec_function` — the
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
