# A first-class binder for single-actor decisions

**Tier 3 — medium impact, narrow scope.** The corpus and the broad-sweep
stress test (branch `stress-test/broad-sweep`) both lean on the same idiom to
direct a `chosen` decision at one specific player:

```
for each player p: if p == taker {
  move chosen 6 cards from hand[p] where c => is_pref_discard(c) to discard
}
```

French Tarot invented it (the chien discard), Cribbage uses it, Schnapsen
uses it (the follower's answer to a led card), and three
stress-branch games rediscovered it independently (President ×4, Cheat ×2,
Durak). It exists because a `chosen` movement needs an actor binding
(`ctx.require_actor`), and the only statement-level constructs that supply
one are a `for each player` loop and a `move_type` effect body. So "one named
player decides" is spelled "loop over everyone and skip all but one."

## Why it matters beyond aesthetics

The loop-and-skip shape actively obscures the decision site. Statically,
every player is a potential actor at that statement; only evaluating the
`if` reveals that exactly one is. Anything that wants to *derive* structure
from the program — the decision-interpreter direction in
[design-notes/kernel-extensibility.md](../design-notes/kernel-extensibility.md),
OpenSpiel decision-node attribution, a future static check that every
`chosen` has a well-defined chooser — must see through the idiom instead of
reading it. A binder says what is happening:

```
as taker {
  move chosen 6 cards from hand[taker] where c => is_pref_discard(c) to discard
}
```

## The options

- **Add `as <player-expr> { ... }`.** A statement block that evaluates the
  expression to one player and binds the actor context for its body. Small
  grammar addition; the runtime plumbing (`ctx.acting_as`) already exists —
  the loop idiom reaches the same code path indirectly.
- **Bless the loop idiom in the docs and do nothing.** Zero cost; keeps the
  construct count down. But it leaves the decision site derivable only by
  predicate analysis, and the idiom's repeated independent rediscovery shows
  authors reach for a binder that isn't there.
- **Fold into the `turns` form's binder** (see
  [turn-loop-form](turn-loop-form.md)) and skip the standalone block.
  Insufficient alone: the corpus's uses (Tarot's chien, Cribbage's crib,
  exchange phases) are not turn loops.

**Current recommendation: add the `as` block.** It is the smallest construct
in this batch, the runtime already supports the semantics, and it converts
an idiom every fifth game reinvents into a statically readable decision
site. When adopted, rewrite the corpus uses in the same change (per
[maintaining.md](../maintaining.md), games move in lockstep).

Related: [decisions.md](../decisions.md) "No implicit actions" (why
decisions must have an attributable actor at all);
[turn-loop-form](turn-loop-form.md) (the loop-level companion).
