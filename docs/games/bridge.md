# Bridge (rubber, simplified)

The companion formal file is [bridge.cardlang](bridge.cardlang); this is the
readable twin. Rubber Bridge with the standard below-the-line / above-the-line
scoring, game and rubber bonuses, slam bonuses, and vulnerability; honors and
the finer doubled-penalty table are simplified. One rubber is played (first side
to two games) and the side with the higher total wins.

Each hand:

1. Deal 13 cards each.
2. **Auction** — ascending bids over the strain order C D H S NT, with double and
   redouble; the auction ends when three passes follow a call. The final bid is
   the contract; declarer is the first of that side to have named the strain.
   (If all four pass, the hand is redealt.)
3. **Play** — the declarer's left-hand opponent leads; thirteen tricks, follow
   suit if able (Bridge has no head-or-trump obligation). The trump is the
   contract's strain, or none for a no-trump contract.
4. **Score** — the contract is *made* if declarer's side took 6 + level tricks.
   Made: the trick value goes below the line (20/trick in a minor, 30 in a major,
   30 + 10 in no-trump), times the doubling multiplier; overtricks and slam
   bonuses go above the line. Set: the defenders score the undertrick penalty
   above the line. When a side's below-the-line total crosses 100 it wins a game
   (bonus 300, or 500 when vulnerable), the below-the-line counters reset, and a
   second game ends the rubber (bonus 500/700).

The thirteen tricks run on the trick form of the kernel `round` construct; the
auction runs on its auction form — a continuous ring over the bid vocabulary
(`offering [pass, submit_bid, double, redouble] … until …`), threading the
standing contract through the phase's accumulator state. The auction phase
declares a typed outcome — `contract_finalized(declarer, level, strain, doubling)`
or `all_pass` — and the `produces:` consumer either routes on into play or skips
the passed-out hand (see [decisions.md](../decisions.md) "Typed phase outcomes").
Random bids are capped at level 3 so rubbers stay
a realistic dozen-odd hands — game-level and slam contracts are unreachable under
random play (their scoring is implemented but unexercised; issue #415 holds the
cap's own reckoning). The dummy is modelled: once a contract stands, declarer's
partner lays their thirteen cards into `dummy_hand`, a `PublicHand` every seat
sees in full, and declarer decides dummy's plays through the Delegated Play
helpers (`chooser_for` / `play_source_for`, [decisions.md](../decisions.md)
"Delegated play") while the tricks stay dummy's. One declared deviation from
the real game: the exposure precedes the opening lead rather than following
it, so the leader chooses with sight of dummy — the kernel round is atomic
per trick, and the mid-trick instant real Bridge exposes at is not a
statement site.
