## Typed phase outcomes

Some phases have more than one legitimate way to end. Pinochle's
`declare_trump` phase resolves either as "trump declared" or as "the
bidder had no marriage and abandoned the contract." Bridge's `bidding`
phase resolves either as a final contract with a declarer or as "all
four players passed without bidding."

A phase declares its outcome type in its signature:

```text
phase declare_trump → outcome { trump_declared(Suit) | bid_abandoned }
```

The enclosing structure pattern-matches on the outcome:

```text
declare_trump produces:
  trump_declared(t) { continue to melding }
  bid_abandoned {
    score[high_bidder.team] -= current_bid
    skip to next hand
  }
```

This makes failure-by-design a first-class concept without exception
ceremony. Most phases still have a single implicit success outcome;
the typed-outcome syntax appears only when a phase can resolve more
than one way.

Rules signal "satisfied" or "unsatisfiable" without dictating what
happens next. A rule that finds no legal move in its `demands`
reports unsatisfiable; the enclosing phase interprets that signal in
context. The phase decides whether unsatisfiable means error, fallback,
or a typed outcome other than success.

**Rings and rounds produce typed outcomes the same way.** A bidding ring
that resolves to a tagged value `produce`s it, from the phase state its
moves wrote, once the ring closes: Bridge's auction produces
`contract_finalized(declarer, level, strain, doubling) | all_pass`,
Pinochle's produces `bid_won(declarer, bid)`, Tarot's
`taken(taker, level) | thrown_in`; the trick `round`'s `winner` function
produces a Player. (A ring with nothing to tag — Skat's Reizen, a betting
street — produces nothing and threads phase state instead.) The enclosing
structure pattern-matches on the produced value the same way it does for
phase outcomes:

```text
bidding produces:
  taker_chosen(_, level) {
    if level is Petite or level is Garde { continue to chien_visible }
    else { continue to play }
  }
  all_pass { skip to next hand }
```

A trick or climb round's selected player is also available as the bare
`winner` pronoun in the enclosing body, immediately after the `round`: Hearts
follows its trick `round` with `leader := winner`. The two paths are
disjoint — a tagged result reaches its consumer through `produces:`, never
through the pronoun, and `winner` is the only value a `round` binds.

Mechanics and phases are *not* further unified at the construct
level. The distinction stays:

- A **mechanic** is a named, parameterized, reusable unit — the shape for
  a chunk of logic that appears in multiple games. The corpus holds one:
  the poker street, a `poker_betting` library procedure over the `turns`
  ring. The trick and the climbing trick are configurations of the kernel
  `round` construct, every auction and poll is a `turns` ring with an
  `offer` body, and every formerly-Python hand engine is DSL over them.
  The category grows by in-DSL definitions promoted corpus-first (an
  ascending auction, real response windows).
- A **phase** is a positional unit in the phase tree, not parameterized
  and not reusable across games. It's the right shape when a chunk
  appears at a specific position with semantics tied to where it sits.

Both can produce typed outcomes; both can be dispatched on. What
the typed-outcome system unifies is the *result discipline* — every
named piece of game logic that resolves to a value uses the same
tagged-value protocol — not the structural distinction between
"reusable abstraction" and "positional step."
