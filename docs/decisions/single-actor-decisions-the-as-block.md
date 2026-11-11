## Single-actor decisions: the `as` block

When one *named* player decides — a chosen discard, a follower's answer to a led
card, a victim flipping one of their own cards — the binder is `as`:

```cardlang-fragment as_taker
as taker {
  move chosen 6 cards from hand[taker] where is_pref_discard(card) to discard[taker]
}
```

`as <player-expr> { … }` evaluates its player expression in the **outer** context,
binds the acting player to that one player, and runs its body **once** as a block
scope (its `let`s do not escape; state writes and card moves persist). It is the
statement-level companion to `for each player` (everyone decides) and the
simultaneous pass — the form for exactly one decider. The player expression must be
a `Player`; anything else is a type error.

It exists because a `chosen` transfer needs an acting player, and binding one
belongs in the construct that says *who decides*, not in a loop that iterates
everyone. Pressed into service for a single decider, `for each player p: if p
is <who> { … }` carries two latent failures `as` forecloses (the same `for
each` stays correct — and stays in the language — for genuine per-player work,
a scoring pass or a deal to everyone):

- **It captures `actor`.** `for each player p:` rebinds the acting player for its
  body, and `actor` *reads* the acting player, so `if p is actor { … }` would be
  true for **every** `p` — which is why the comparison is refused outright (see
  "Naming the acting player twice", below). `as` evaluates its player *before* the
  rebind, so `as actor { … }` is idempotent and `as challenger { … }` reads the
  state variable — neither can be captured.
- **It re-reads its guard mid-pass.** When the body mutates the guard variable, a
  later player in the same pass re-matches and takes a second turn — an
  order-dependent double-execution. `as` runs its body once, so one written turn is
  one turn. This one no Owner Guard can catch — whether the body writes the guard is a
  question about paths, not names — so it remains the reason to reach for `as`
  even where the comparison would be legal.

`as` uses the same actor-binding runtime path the loop reached indirectly, so it
emits no new observations. Its gain for the OpenSpiel target is that the decision
node's chooser is **statically** readable — one named player at the statement —
rather than recoverable only by evaluating a predicate. Reading a procedure
parameter inside an `as` block is safe for the same reason it is inside any
actor-rebinding body: arguments are evaluated once in the caller's context
([Named procedures](named-procedures.md#named-procedures)), so Coup's `lose_influence(victim)` runs
`as victim { … }` with no capture.
