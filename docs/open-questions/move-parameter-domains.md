# Declared parameter domains as the action-space contract

**Tier 1 — high impact, enough data to commit.** Surfaced across three
independent games in the broad-sweep stress test (branch
`stress-test/broad-sweep`, `stress-test/FINDINGS.md`): Go Fish, Ninety-Nine,
and Canasta each needed a player decision parameterized over something other
than a suit, and each was forced into the same distortion because move-type
parameters can only range over `Suit`/`Suit?` and only the auction form of
`round` enumerates them at all.

Two restrictions compose into the wall:

1. `enumerate_domain` (cardlang/runtime/mechanics.py) supports `Suit` and
   `Suit?` only — `Rank`, `Player`, and bounded-`Integer` parameters
   typecheck but raise `NotImplementedError` at the decision site.
2. The plain `offer` statement rejects parameterized move types outright
   (cardlang/resolve.py: "only an auction round offering can enumerate its
   parameter"), so outside an auction there is no parameter enumeration
   even for `Suit`.

The forced workaround is the **nullary-move-type explosion**: Ninety-Nine
declares 14 separate move types where one `play_card(delta: Integer)` was the
natural encoding; Go Fish narrows "ask any player for any rank you hold" to
three fixed seat-relations crossed with a fixed rank cycle; Canasta declares a
move type per meldable rank.

## Why this is more than ergonomics

The OpenSpiel target requires a **fixed, enumerable action space**
(`num_distinct_actions`) declared up front, with per-state legality as a mask
over it. Declared finite parameter domains *are* that contract: a move type
whose parameters range over declared enumerable domains gives the adapter the
action space by construction, instead of the adapter reverse-engineering it
from runtime behavior. The nullary explosion is the author hand-compiling
exactly the enumeration the language should own.

A corollary constraint the same decision should settle: `choose integer in
lo..hi` with a *runtime-computed* bound is hostile to a fixed action space.
The OpenSpiel-idiomatic shape is a statically bounded domain with dynamic
legality narrowing; whether runtime bounds are rejected, widened to a
declared static bound, or compiled to a masked static range is part of this
question.

## The options

- **Extend domains + let `offer` enumerate.** `enumerate_domain` grows
  `Rank`, `Player`, and statically-bounded `Integer` cases; `offer` expands a
  parameterized move type into its (guard-filtered) instances the same way
  the auction form already does. Smallest step; keeps today's surface syntax.
- **Declared domains on the move type.** A `domain:` clause per parameter
  (e.g. `play_card(delta: Integer in -10..99)`) that resolve checks and the
  adapter reads directly for `num_distinct_actions`. Slightly more syntax;
  makes the action-space contract explicit and static rather than inferred
  from the type.
- **Defer.** Leaves the nullary explosion as the sanctioned idiom. Rejected
  by the evidence: three independent games hit it in one sweep, and the
  workaround actively obscures the action space the adapter needs.

**Current recommendation: both of the first two, staged.** Extend
`enumerate_domain` and `offer` first (unblocks the pattern), then add the
explicit `domain:`/bounded-type surface so the static action space is
declared, not inferred. Rank and Player are closed finite sets the runtime
already knows; bounded Integer needs the static-bound rule above.

An adjacent instance is planned rather than hypothetical: the Schnapsen
migration ([kernel-migration.md](../kernel-migration.md), Workstream 4) needs
a `Card` move parameter (`play_card(c : Card)` in the leader's mixed
vocabulary), with exactly the shape this question recommends — the *static*
domain is the declared deck, encoding onto the existing per-card action ids
(so a card play has one id whether it is a vocabulary move or a plain card
play, and `num_distinct_actions` does not grow), while the *runtime*
candidate set narrows to the actor's live hand, in hand order. Whatever
surface this question settles should subsume that case rather than leave
`Card` a special one.

Related: [decisions.md](../decisions.md) "The auction form of `round`" (the
one construct that enumerates parameters today) and "No implicit actions";
[phase-legal-moves](phase-legal-moves.md) (what a declared move vocabulary is
for — the same static-contract instinct at phase level).
