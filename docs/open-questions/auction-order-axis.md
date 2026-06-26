# Auction order: call-and-response

**Tier 2 — high impact, blocked on a second instance (or explicit sign-off).**

The auction form of `round` ([decisions.md](../decisions.md), "The auction form
of `round`") walks a single ring in seat order: each turn the next participant in
`turn_order_from` is offered the move vocabulary, the participants predicate may
shrink the ring, and `until` closes it. Bridge, Pinochle, and Tarot are all this
shape — one continuous (or single-pass) ring, one vocabulary, seat-order turns.

Skat's **Reizen** is not. It is a call-and-response between *pairs* of players:

- Two sequential contests — Middlehand bids against Forehand, then Rearhand bids
  against the winner of the first.
- Within a contest the **speaker** names successive values (`bid` / `pass`) and
  the **responder** answers (`yes` / `pass`); the speaker and responder have
  *different vocabularies*, and the responder is only offered a turn *if the
  speaker bids* (conditional participation).
- The bid ladder (18, 20, 22, 23, 24, …) is forced, not chosen — the value
  advances when "bid" is chosen rather than being a candidate.

This cannot be expressed as a value on the current **order** axis (turn-from-a-
seat / priority / simultaneous):

1. **Role-dependent vocabularies** — a ring offers every participant the same
   vocabulary per turn; Reizen's speaker and responder differ by role, not seat.
2. **Conditional participation** — the responder is skipped when the speaker
   passes; a ring offers each in-ring participant unconditionally.
3. **Seat reorder** — when Forehand wins the first contest, the second contest
   has Rearhand speak *before* Forehand responds, the reverse of their seat
   order. A participants filter can *skip* seats but cannot *reorder* them.

This is exactly the "possible new axis" the migration brief flagged
([kernel-migration.md](../kernel-migration.md), Workstream 1 checkpoint): a
genuine language gap, to be surfaced as an open question rather than special-cased
with an engine hook.

The options:

- **A new `order` value `call_and_response`** — a paired speaker/responder
  alternation that carries the winner into the next pairing. Clean and
  declarative, mirroring the existing order values. But it is a kernel axis
  addition (a major change requiring explicit sign-off, per decisions.md), and
  the corpus has exactly **one** instance — adding a closed-axis value for a
  single game cuts against "promote at the third instance".
- **Two-round composition in the game body** — express each contest as its own
  `round`. But a contest is itself not a plain ring (role-dependent vocabulary +
  conditional participation), so this does not cleanly reduce to the existing
  auction form either, and it pushes turn-cycling back into per-game body code —
  the very thing the auction form exists to avoid.
- **Defer — keep Reizen in the `run_skat_hand` mechanic** until a second
  call-and-response game appears (or sign-off is given to add the axis now). The
  rest of the kernel migration proceeds; Skat's auction is the one piece left in
  Python, tracked here.

**Current recommendation: defer.** One instance is too few to commit a new
closed-axis value, and the composition route is not clean. Keep `run_skat_hand`
as-is and revisit when a second call-and-response auction (or a maintainer
sign-off) forces the decision — at which point this promotes to a decisions.md
entry describing the chosen `order` value.

Related: [decisions.md](../decisions.md) "The auction form of `round`" (the closed
axes), [kernel-migration.md](../kernel-migration.md) Workstream 1 (the checkpoint
and the deferral).
