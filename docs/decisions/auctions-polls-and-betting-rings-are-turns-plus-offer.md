## Auctions, polls and betting rings are `turns` plus `offer`

A bidding ring, a betting street, a quiescence-lap poll and a declaration
round are one loop: walk the seats from a start seat, over a participants
predicate re-evaluated each turn, until a predicate holds, asking each seat
one flat offering. That loop is the `turns` form with an `offer` body ("The
`turns` form", below), and no form of `round` exists for it: a mechanic
enters as a definition over the kernel, never as a production ("Interactive
decisions: a kernel and an in-DSL standard library"). The surface, in
Bridge:

```text
turns bidder from dealer over all players
      until (made_bid and passes >= 3) or (not made_bid and passes >= 4) {
  offer to bidder one of [pass, submit_bid, double, redouble]
}
```

- **Move vocabulary.** Each turn presents the acting seat **one flat
  candidate list** of the legal concrete moves — every parameterized
  `move_type` expanded over its value-domain and guard-filtered, plus the
  nullary moves, in the order the offering lists them — resolved by a
  **single** decision (one chooser draw). This is not stylistic: the target
  runtime (OpenSpiel) mandates one finite, enumerable action set per
  decision node, so a turn is one node over a flat set, never an outer
  move-type choice followed by an inner parameter choice. Bridge's
  `submit_bid(strain : Suit?)` expands to one bid per strain whose cheapest
  beating level is still legal; `pass`/`double`/`redouble` are nullary. The
  declared domain set each parameter draws from, and the cross-product rule
  for a multi-parameter move type, are "Declared parameter domains," below.
- **The ring's bookkeeping is the game's own.** The pass count, the acted
  flags, the roles that steer a call-and-response ring belong to the ring's
  Decision Episode ([glossary/decision-episode.md](../glossary/decision-episode.md)):
  the game clears them where the ring closes, or declares them in a
  sub-phase that ends with it, so the information state during play names
  no ring already closed (pinned at
  `tests/test_offering_round_state_freshness.py`). The ring's result — the
  contract, the taker, the trump — is read all through play and stays.
- **The ring (`over`) is explicit; there is no silent skip.** A seat
  offered a turn always has at least one legal move — the finite-action
  invariant of a decision node. The game states *who is still in the ring*
  through the participants clause (`over <players> [where <predicate>]`)
  and *when the bidding closes* through `until`. A seat that has dropped out
  (passed for good, folded) is excluded by the participants predicate, and
  "all but one has passed" is a termination predicate — neither is an
  engine default. So a seat with no legal move is a **malformed game** (a
  missing always-legal move, or a participants filter that should have
  dropped the seat), reported as an error, never a silently skipped turn.
  Bridge keeps every seat in the ring with an always-legal `pass`. The
  participants predicate is **re-evaluated each turn**: a ring that
  *shrinks* as seats drop out (Pinochle's passed bidders and the standing
  high bidder, Stud's folders) drops a seat the moment the predicate stops
  holding for it, so it is never offered another turn and consumes no draw;
  a start seat the predicate excludes takes no turn, and the ring opens at
  the first eligible seat after it. A static ring (Bridge's `all players`)
  is the invariant case.
- **Order.** The ring is traversed one way: the turn advances past the seat
  that acted, so the next *seat* is offered, wrapping. That is poker's
  order as much as an auction's: the seats *behind* the aggressor are the
  next ones reached; the participants filter is re-evaluated each turn, so
  the seats a bet re-opened come back when the ring returns to them; and
  `until` is checked before each ask, so the ring closes mid-lap the moment
  nobody is pending. A ring runs in the game's `direction` (Tarot's is
  counterclockwise).
- **Call-and-response is a configuration, not an order value.** Skat's
  Reizen — a speaker naming successive ladder values against a responder
  who holds or passes, twice in sequence with the survivor advancing — runs
  on the plain ring: `turns bidder from speaker over players where player is
  speaker or player is responder until <someone passed>`, with `bid`
  guarded to the speaker (and to a ladder with a rung left) and `yes` to
  the responder. Role-dependent vocabularies are move guards (the
  speaker's candidates filter to `[bid, pass]`, or to `[pass]` alone once
  the ladder is exhausted, the responder's to `[yes, pass]`); conditional
  participation is the `until` predicate, checked before each ask (a pass
  ends the contest, so the responder always answers the last bid); the
  speaks-before-his-seat reorder is `from speaker`; and the two sequential
  contests are two rings threading the survivor through phase state.
- **Accumulator.** The decision-relevant running state (Bridge's standing
  level, strain, doubling, high bidder, pass count) is ordinary **phase
  state**, read and written by the move-type effects and read by the
  termination predicate. No separate accumulator construct, and no hidden
  history: a result the rules state over the bids' history is state the
  bids write as they are made — Bridge's declarer is the first player of
  the high side to have bid the final strain, so each side's first bidder
  of each strain is recorded in `submit_bid`'s effect, and the contract is a
  read of it when the ring closes.
- **Termination (`until`).** A predicate over that state, checked before
  each ask (Bridge: three passes after a bid, four with no bid).
- **Result.** The ring yields nothing of its own. The statements after it
  read the terminal state: in an outcome phase they `produce` the typed
  outcome ("Typed phase outcomes" — Bridge's `contract_finalized(...) |
  all_pass`, Pinochle's `bid_won(...)`, Tarot's `taken(...) | thrown_in`);
  elsewhere they assign (Skat's survivor). A betting street produces
  nothing: each move mutates the shared chip and fold state, so when the
  ring closes the surrounding body deals the next street or settles.
- **One seat.** A single seat asked until it acts is `repeat until <pred>
  { offer to <seat> one of [...] }` — Schnapsen's leader, whose free actions
  leave the pile empty; a seat asked once is a plain `offer` (Pinochle's
  trump declaration, each half of its exchange, its concession).
- **A betting street is the family library's.** `poker_betting`'s
  `betting_street(first, bet_size, big_size)` is the ring written once, with
  the family's whole vocabulary, opening the street on entry and closing it
  on exit, and every poker game runs it; `fold` is the game's own by
  contract ("Family libraries"), because folding touches the game's zones.

A ring's only decision points are these per-turn draws, and the statements
after it consume no randomness. So two rings that present the same per-turn
candidate lists (same length and order) play identically under a random
playout — the property that lets a mechanic be re-expressed in this form
without changing behaviour.
