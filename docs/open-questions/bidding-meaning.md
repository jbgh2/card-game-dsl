# Bidding meaning

**Tier 2 — high impact, blocked on a data point.**

The Auction mechanic exposes `current_bid` as an integer with no
semantic. This makes games legible only to readers who already
know them. In Pinochle the bid is a total-points target; in
Spades a trick-count target; in Bridge a contract; in Oh Hell an
exact-tricks target per player.

Auction should take a `bid_meaning` or `bid_interprets_as`
parameter that declares what the bid value targets.

**Blocker:** Bridge's full bidding mechanic (with doubling) and a
third bidding game (Oh Hell or Wizard) in the corpus. Two data
points (Spades, Pinochle) plus a sketched third (Bridge with
contracts) aren't enough to pin down the right parameter shape.
