# A first-class binder for single-actor decisions

**Tier 1 — a correctness fix, and commit-ready.** Promoted from Tier 3: the
idiom this replaces does not merely read badly, it silently captures the `actor`
pronoun (below), and the corpus has been hand-working-around that without naming
it. The runtime plumbing (`ctx.acting_as`) already exists. The corpus and the
broad-sweep
stress test (branch `stress-test/broad-sweep`) both lean on the same idiom to
direct a `chosen` decision at one specific player:

```
for each player p: if p is taker {
  move chosen 6 cards from hand[p] where is_pref_discard(card) to discard
}
```

French Tarot invented it (the chien discard), Cribbage uses it, Schnapsen
uses it (the follower's answer to a led card), and three
stress-branch games rediscovered it independently (President ×4, Cheat ×2,
Durak). It exists because a `chosen` movement needs an actor binding
(`ctx.require_actor`), and the only statement-level constructs that supply
one are a `for each player` loop and a `move_type` effect body. So "one named
player decides" is spelled "loop over everyone and skip all but one."

## It is not only aesthetics: the idiom silently breaks `actor`

The loop-and-skip shape does not merely obscure the decision site — it **captures
the `actor` pronoun**, and the corpus has been working around that by hand without
naming it.

`for each player p:` binds the acting player for its body (`ctx.acting_as(p)`) —
that is precisely how it directs the `chosen` decision at `p`. But `actor` *reads*
the acting player. So inside the loop, `actor` means `p`, and the guard everyone
writes to single one player out:

```
for each player p: if p is actor { … }      // true for EVERY p
```

is true for **every** player. Probed directly: a three-player game whose move
effect ran `for each player q: if q is actor { hits[q] += 1 }` scored
`{0:1, 1:1, 2:1}` — all three "matched". There is no wall; it type-checks and runs.

Coup had already hit this and paid for it in paste. Its influence-loss block
appears in two hand-written variants — the loop-and-skip form for a state-bound
victim (`challenger`, `blocker`, `target`) and a separate, un-looped form for the
actor — for no stated reason other than that the first one does not work with
`actor`. Naming the block as a procedure forced the issue into the open: a
procedure substitutes an *unevaluated argument*, so `run lose_influence(actor)`
puts `actor` inside whatever the body wraps it in, and the checker now rejects
reading a parameter under an actor-rebinding construct
([../decisions.md](../decisions.md) "Named procedures"). That wall makes
procedures safe; it does nothing for the idiom written inline, which is still
silently wrong and still the only way to say "one named player decides".

An `as` block fixes it at the root, because it evaluates its player expression in
the OUTER context and *then* rebinds — so `as actor { … }` is idempotent and
`as challenger { … }` reads the state variable, and neither can be captured. The
loop form evaluates the guard *inside* the rebinding, which is the bug.

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
  move chosen 6 cards from hand[taker] where is_pref_discard(card) to discard
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

**Current recommendation: add the `as` block.** It is now the highest-value
small construct outstanding: a correctness fix, not only a readability one. It is
the smallest construct in this batch, the runtime already supports the semantics, and it converts
an idiom every fifth game reinvents into a statically readable decision
site. When adopted, rewrite the corpus uses in the same change (per
[maintaining.md](../maintaining.md), games move in lockstep).

Related: [decisions.md](../decisions.md) "No implicit actions" (why
decisions must have an attributable actor at all);
[turn-loop-form](turn-loop-form.md) (the loop-level companion).
