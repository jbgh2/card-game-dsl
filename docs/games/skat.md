# Skat

The companion formal file is [skat.cardlang](skat.cardlang); this is the
readable twin. Three-player Skat (DSkV / International rules, post-1999), 32-card
deck. Players bid (*Reizen*) for the right to play alone against the other two;
the declarer chooses a game type, takes or skips the two-card skat, and tries to
make the contract for a calculated game value. Thirty-six hands are played and
the highest score wins. Source: [Pagat](https://www.pagat.com/schafkopf/skat.html).

Each hand:

1. Deal 3 - 2(skat) - 4 - 3.
2. **Reizen** — middlehand bids against forehand, then rearhand against the
   survivor. A bid is any value of the fixed legal sequence (18, 20, 22, 23,
   24, 27, …) above the standing bid: normally the next, but a bidder may
   jump.
   The last bidder is declarer; if all pass, forehand may play at 18 or throw the
   hand in.
3. **Declare** — the declarer either picks up the skat (and discards two, face
   down) or plays *hand*, then names the contract: a trump suit, **Grand** (only
   the jacks are trumps), **Null** (no trumps), or **Null Ouvert** (Null with the
   declarer's hand face up). In a Suit or Grand *hand* game the declarer may
   then announce **Schneider** (to take 90+ card points), **Schwarz** (every
   trick), or **Ouvert** (every trick, hand face up); each includes the ones
   before it. An open hand is laid face up before the first lead.
4. **Play** — ten tricks. In Suit and Grand the four jacks are permanent trumps
   (C > S > H > D), above the trump-suit cards in a Suit game; non-trump cards
   rank A > 10 > K > Q > 9 > 8 > 7. Null has no trumps and ranks
   A > K > Q > J > 10 > 9 > 8 > 7; the declarer must take *no* trick, and the
   hand ends at once if they take one.
5. **Score** — only the declarer's score moves. A Suit/Grand contract needs 61+
   card points, and whatever was announced; its value is `base × multiplier`,
   the multiplier being matadors plus one for game, plus one each for hand,
   Schneider (a side under 31), Schneider announced, Schwarz (a side with no
   trick), Schwarz announced, and Ouvert — an announcement counts whether or
   not it is made. Making it scores the value; failing loses twice it — or,
   when overbid, twice the smallest multiple of the base that meets the bid.
   Null is a fixed value: 23, Null Hand 35, Null Ouvert 46, Null Ouvert Hand
   59. Pagat states the overbid rule for a base value and names none for
   Null; an overbid Null loses twice the smallest multiple of its fixed value
   that meets the bid.

The hand runs fully on the kernel. The Reizen is two sequential `turns` rings
over role-guarded two-participant sets — `bid` guarded to the speaker, `yes`
to the responder, `pass` open, so the candidate lists alternate [bid, pass] /
[yes, pass] — [pass] alone for a speaker facing the exhausted ladder, so the
responder always answers the last bid; a pass flips the `until` predicate,
and the survivor threads into the second contest
([decisions.md](../decisions.md), "Auctions, polls and betting rings are
`turns` plus `offer`", the call-and-response paragraph). A bid chooses its
rung of the ladder (`choose integer`, the Pinochle shape), and the
`skat_bid_at` primitive reads the rung's value. The contract
declaration is a pair of `offer`s (play-at-18/throw-in
on an all-pass; hand vs picking up the skat, with the two-card discard in the
`pick_up_skat` effect; the four-way game type) plus a single-seat `offer` of
`declare_suit(s : Suit)` and, in a Suit or Grand hand game, the announcement
offer. An open contract moves the declarer's hand into `open_hand[declarer]`,
a `PublicHand` zone: the movement is the exposure, every seat learning the
ten identities through the zone's declared type (the Five Hundred open-misère
shape), and the declarer plays on from it. The ten tricks are three
single-actor filtered movements per trick, ending early when a Null declarer
takes one, and the contract's order is the game's Trick Order
([decisions.md](../decisions.md), "Trick Order"): its functions read the
declared contract off the public state, which is what puts the four jacks and
the trump suit in one follow class under Suit and Grand and leaves Null
trumpless on its own rank order. Follow legality (`follows_lead`) and the
winner (`highest_by_trick_order`) are then both the language's. Scoring writes
`score[declarer]` directly through `skat_matadors`, with the overbid rule's
smallest-covering-multiple written as rounded division (`working_bid divided
by base rounded up`) in the game text.

The contract's three variables (`is_grand`, `is_null`, `trump_suit`) are
declared at game level rather than in `phase play`, because the kernel reads
the Trick Order where no phase frame stands, so its functions read game
state only; the phase clears them on
entry, so they still last exactly one hand.
