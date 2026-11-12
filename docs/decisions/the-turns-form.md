## The `turns` form

The turn loop beneath the round forms — for every ring whose turn is a
*body of statements*: a single `offer` (an auction, a poll, a betting
street — "Auctions, polls and betting rings are `turns` plus `offer`"
below), draw-then-discard shapes, ask-and-resolve shapes, anything with
statement structure per turn. The round forms, by contrast, move cards
through a trick:

```text
turns <binder> from <leader> over <participants>
      until <pred> [again <state-var>] { <statements> }
```

The binder names the current player, who is also the acting player — exactly
`for each`'s per-iteration binding, one player at a time — so a `chosen`
transfer or `offer` in the body is attributed to the turn-holder without a
cursor variable. The form owns what every hand-rolled turn loop re-implements
(and where the stress-sweep's runtime failures clustered): **rotation**
(advance in game direction to the next seat satisfying the participants
predicate, re-evaluated per advance, so elimination falls out), **termination
placement** (`until` is checked at each turn boundary, before the first turn
too — the zero-iteration run always exists), and the **go-again axis**
(`again` names a declared Boolean state variable the body's move effects
write; a turn ending with it true repeats the same player — Go Fish's
hit-or-matching-draw. The form CONSUMES the flag, resetting it to false as it
reads it at the boundary, so a stale write buys at most one repeat and can
never silently monopolize the loop — only a write during the turn keeps the
turn. The flag also dies with its ring: whatever ends the ring — its `until`,
a `produce`, a hand skip, a jump — consumes a flag its last turn wrote, so it
never buys the next ring's leader a turn, while a decision suspended mid-turn
leaves the paused world as it is. A ring inside a ring, written there or in a
procedure it runs, names its own flag: one shared would be the inner turn's and
the outer turn's at once, and is refused). The leader expression is read once, at the first turn, and must name a
real seat — a non-seat value (an out-of-range Integer, a loose pronoun) is a
typed runtime error at the bind, the same seat guard `as` and `offer` carry. A
full lap finding no eligible participant is a loud runtime error, the `offer`
no-legal-move rule one construct up; a decisionless body that never
terminates hits the same iteration guard as `repeat until`, and a body that
makes picks ends at the game's bound ("Game length as a declared contract").

```cardlang-fragment turns_form
turns t from 0 over players where not eliminated[player]
      until (number of players where not eliminated[player]) is 0 {
  score[t] += 1
  eliminated[t] := true
}
```

Gin Rummy's draw-discard cycle is the strict-alternation anchor; Go Fish is
the go-again anchor (its move effect writes `went_again` instead of mutating
a cursor). A ring whose every turn IS one flat candidate list — an auction,
a poll, a betting street — is this form with an `offer` body ("Auctions,
polls and betting rings are `turns` plus `offer`"), and Schnapsen's leader,
one seat asked until it leads, is an `offer` inside `repeat until`. A
`direction` override clause is deliberately not
grammar: no corpus user ([roadmap.md](../roadmap.md), "Grammar surface deferred
by the checker"). The form emits no observations of its own — the body's
decisions emit through their own sites, and rotation is derivable from
state — so information sets are unchanged by construction.
