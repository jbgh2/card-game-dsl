# The generalization path: from cards to boards to card-defined rules

*Status: exploratory sketches — further from commitment than
[kernel-extensibility.md](kernel-extensibility.md). Nothing here is
settled spec, and nothing here should be built speculatively. Each
axis names the witness games that would test it; per corpus-first
discipline, an axis graduates by a witness game entering
[games/_candidates.md](../games/_candidates.md) and forcing an open
question, never by implementing the sketch directly. The value of this
note is the direction and the convergences, not the details.*

## 0. The destination and the organizing principle

The long-term goal is all fixed-outcome board games OpenSpiel can
host, not just card games. Cards were the entry point because they are
a high-affordance token over a broad but tractable surface; the parts
of the design that carried the corpus — zones, per-observer
projections, phases, the closed operation vocabulary — are not
card-specific.

Two principles organize everything below. They generalize the current
design rather than amending it:

1. **Identity is kernel; meaning is never state.** The kernel tracks
   *which object is where* (and, per axis 2, in what pose). What an
   object *means* — its role, value, effect, even which rule it
   enables — is always a pure function of (identity, pose, zone,
   phase). Meaning is interpretation, not stored state, so it can
   never desynchronize from what observers were shown.

2. **Extensions compute; only the kernel acts.** The safe extension
   seam is: pure functions (legality predicates, valuations,
   combination enumeration, scoring — freely authorable, even foreign)
   over a **closed verb kernel** (move contents, mutate public state,
   open a decision over a declared finite domain, emit observations
   through projections). An extension may compute anything but may only
   act through kernel verbs, so information sets derive *no matter
   what the extension computes*. This is the inverse of the
   `instantiate` escape hatch, which hands over the world and hopes;
   the goal is hooks that **cannot** be careless, not hooks that are
   careful. Two clauses are load-bearing for the OpenSpiel target:
   foreign functions must be deterministic (replay and the swap proofs
   depend on it), and anything feeding a decision must have a finite,
   declared domain (see
   [open-questions/move-parameter-domains.md](../open-questions/move-parameter-domains.md)).

The broad-sweep stress test supplied the existence proof for the seam:
games fitting none of the built-in round forms ran anyway on raw
`offer` + `repeat` + `move`, and the gaps that were found clustered in
pure computation (subset selection, valuations, arithmetic), not in
"we need arbitrary state mutation."

## 1. Axis: topology (boards)

The one genuinely new *axis* boards demand. Zones today are bags; a
board is a position-indexed zone family plus an **adjacency relation**
the expression language can consult. The knowledge model is untouched
— projections do not care about geometry — but the query language is
where it bites: placement legality ("adjacent to your road"), movement
("along this line until blocked"), and above all
**region/connectivity queries** (captures, longest-road, area
scoring), which are transitive-closure / fixed-point computations the
deliberately non-recursive expression sublanguage cannot express. Some
bounded reachability primitive is the real design object; everything
else is representation.

Notable: most board games are perfect-information, i.e. the *trivial*
case of the language's hardest machinery. Even the canonical
hidden-piece game fits the existing model: Stratego is square-indexed
zones whose occupancy/owner project publicly while piece identity
projects hidden — containment-style hiding, exactly per
[decisions.md](../decisions.md) "Hidden information lives only in
zones."

Witness ladder: Backgammon (track + dice + doubling, cheapest entry) →
Stratego (attribute hiding on the existing model) → a Catan- or
Go-shaped game (forces the fixed-point queries). Dice are mid-game
chance nodes — a small `roll` primitive; OpenSpiel hosts them natively.

Risk to hold in view: boards arriving as per-game Python mechanics
before the topology sublanguage exists would recreate the
`instantiate` info-set debt at ten times the scale.

## 2. Axis: pose and declared projections

Three independent needs converged on one extension of the knowledge
model, which is the usual sign it is the right next kernel-adjacent
design after topology.

**Pose.** Double-sided cards (Uno Flip), orientation-aware cards
(dnup), tapped/promoted pieces: a per-object pose record (`face`,
`orientation`) living with the object in its zone, mutated by one new
kernel verb (`flip`/`orient`) that emits observations like any
movement. "Hidden information lives only in zones" survives unchanged.
Content types themselves become declarable (faces and attributes as
structured fields) — the same closed-registry medicine already filed
for decks.

**Attribute-level projections.** Uno Flip's hand — owner sees the
active face, opponents see the *inactive* face of the same cards — is
not expressible as whole-identity projections. Stratego's
position-public/type-hidden is the same shape. Projections need to
address *aspects* of contents, not only whole identities.

**Declared (computed) projections.** Sealed money bids reveal a
*total* without revealing composition: an observer sees
`sum(pay_value(c))` over a zone whose identities stay hidden.
[decisions.md](../decisions.md) already defines a projection as "a
function from full zone contents to some derived value" — the six
standard projections are the blessed instances. The generalization is
**user-declared pure projections**: a zone may project a declared pure
function of its contents to named observers. Info-set safe by the
axis-0 argument: the function is pure and the kernel owns emission;
candidate-set semantics work unchanged.

Multi-use cards (Race for the Galaxy: same card as world / payment /
good) need *none* of this — role is the zone, value is a pure
function, goods are `count_only` tokens. Variable card values likewise:
static value is a content-type attribute (a filed gap — Gin, Blackjack
and Casino all worked around its absence), contextual value is
per-use pure functions (Cribbage's `peg_value` is the corpus
precedent).

Witnesses: Uno Flip (split-face visibility), dnup (orientation),
Stratego (type hiding), any sealed-bid auction game (computed
projections). Hint-economy games (Hanabi) additionally need the
documented-but-unbuilt `announce` epistemic op: a *chosen* emission of
a declared projection over another player's zone.

## 3. Axis: rules as selectable values

Fluxx's design answer is already on its own table: **the rules in play
are cards in a public zone.** Model it exactly that literally. Rules
stay named, statically-checked `rule` declarations; a rule card's
meaning is a pure function of identity referencing one of them; and
`active_rules` gains a zone-derived component
(`active_rules: [base] + rules_of(rules_in_play)`). Numeric-rule
replacement (Draw 3 supersedes Draw 2) is zone discipline — the new
card displaces the old. Goals are one card in a `goal` zone with a
termination predicate dispatching over a closed set. Because
`rules_in_play` is public, legality stays knowledge-consistent for
free; because the rule set is closed, checking and the OpenSpiel
action space stay static.

**The guardrail: rules may be selected, never synthesized.** That is
the line between Fluxx (closed printed set — in) and Mao (open rule
space — out, for OpenSpiel too). Composition is deliberately
conservative — set-union plus category-replacement — until a real
game forces more.

Standard-deck stepping stones exist, so this axis does not depend on a
dedicated-deck scope decision: President's *revolution* variant (a
play inverts the ranking mid-hand) is `active_rules`-from-state at
one-card scale, and Schnapsen's talon closure (in the corpus, currently
escape-hatched) is a mode flip changing follow rules mid-hand.

## 4. Horizon: effect composition and deck-scoped compilation (CCGs)

Deck-scoping restores both core bets for CCG-shaped games: a *match*
is compiled from a rules core plus the chosen decklists, so the card
set is closed per instance and each deck pair is a distinct OpenSpiel
game with a fixed action space. The card pool then stops being
"content" and becomes what the stdlib already is — a library of
statically-checked rule fragments; CCG keyword systems (flying, haste)
are independent evidence that the domain converges on exactly this
discipline.

The true frontier is not cardinality but **composition**: continuous
effects do not union ("all creatures get +1/+1" × "target loses all
abilities" needs ordering), which is why Magic's comprehensive rules
carry a seven-layer, dependency-ordered application system. An
**effect-composition algebra** is the third genuinely new design axis
(after topology and declared projections). Everything else is heavy
but familiar: the stack is a dense priority loop
([open-questions/out-of-turn-moves.md](../open-questions/out-of-turn-moves.md)
is its seed), targeting is parameter domains over object references,
face-down cards are pose, hands/libraries are ordinary zones — the
knowledge machinery, this language's hardest subsystem, is the *easy*
part of the CCG target.

Boundary fact that makes scoping non-negotiable: unrestricted Magic is
proven Turing-complete, so the fully general problem is closed to
everyone, OpenSpiel included. Deck-scoping plus a declared game-length
bound ([open-questions/game-length-bounds.md](../open-questions/game-length-bounds.md))
is the only coherent target.

Ladder, each rung a real game: rule *selection*
(Revolution-President) → rule zones (Fluxx) → composition-lite →
Portal-scale Magic (the official starter set that removed instants and
the stack) → priority/stack.

## 5. The boundary inventory (known out, or not-yet)

Games OpenSpiel hosts that this design deliberately or currently does
not, with the reason:

- **Attempt-feedback games** (Kriegspiel, phantom tic-tac-toe): the
  player does not know their legal moves; referee rejection *is* the
  information. Encodable manually (attempt-moves with conditional
  effects) but unsupported as a pattern — and they expose a soundness
  edge worth a static check regardless: nothing today stops a rule's
  `demands` from reading hidden zones, which would leak information
  through the legal-move set itself. The swap proofs catch it
  dynamically; a "legality reads only observer-visible information"
  lint would catch it statically.
- **Hint economies** (Hanabi): blocked on declared projections +
  `announce` (axis 2), plus a dedicated-deck scope decision.
- **Simultaneous reveal** (Goofspiel — a standard 52-card game already
  in OpenSpiel): the kernel is sequential; `each player
  simultaneously:` is thin. Sequentialize-with-concealment is
  info-set-equivalent, so this is a transform to build, not a wall.
  Goofspiel is likely the cheapest witness this note names.
- **Open rule spaces** (Mao): out by the axis-3 guardrail, and out for
  OpenSpiel too.
- **Real-time / dexterity / unbounded play**: out for both, unchanged.
