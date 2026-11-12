## Loop lifecycle: `before_each` and `after_each`

A `repeat until` phase runs per-iteration setup and teardown through two
optional hooks, siblings of its `state` block and distinct from its
sub-phases:

- **`before_each { … }`** runs at the start of every iteration (after the
  termination predicate is checked, before the body sub-phases). It is where a
  hand is prepared — gather, shuffle, deal.
- **`after_each { … }`** runs at the end of every iteration that started,
  *including one the termination predicate abandons mid-body*. This is the
  guarantee a trailing sub-phase cannot give: under continuous evaluation
  ("Loop termination semantics" above) a loop can exit mid-iteration, and a
  "last sub-phase = cleanup" would be skipped — whereas `after_each` always
  runs (the test-framework `afterEach` semantic). The one end it does not
  follow is a Length Stop, where the game ends at the stopped pick ("Game
  length as a declared contract"). Oh Hell, French Tarot, and
  Skat use `after_each` for end-of-hand teardown.

The loop's `state { }` initializes once and **persists** across iterations;
the hooks run **each** iteration. That separates per-game state from
per-iteration work. Phase-specific setup stays inside the phase as its first
statements (Hearts' `play` sets its own leader); the hooks are only for
the per-iteration boundary. Finer per-phase hooks (`before <phase>`) are
deliberately *not* provided until a game requires them.

Hearts uses `before_each` to gather the previous hand's cards, shuffle, and
deal:

```cardlang-fragment before_each
before_each {
  move all cards to deck
  shuffle deck
  deal 13 cards from deck to each hand
  rotate pass_direction through [left, right, across, hold]
}
```

`move all cards to deck` is a destination-only **gather** transfer (no `from`):
it collects every card from all other zones into the named zone. A `Deck`-typed
zone is initialized at game start holding the deck's cards, so the first
`before_each` gather is a no-op and the deal is well-defined.

A gather collects zones in **lexicographic zone-name order** — singleton zones
and indexed families in one sorted namespace, a family's instances in its index
domain's order (players in seating order, teams in team order). The collection
order is observable twice over: each non-empty zone emits its own transfer
event (shaping every player's observation log, hence information sets), and the
collected cards stack into the destination in collection order (feeding the
next same-seed shuffle). Making the order canonical is what keeps the `zones { }`
block a pure declaration: its order is presentational everywhere in the
language, and reordering it never changes a playout.
