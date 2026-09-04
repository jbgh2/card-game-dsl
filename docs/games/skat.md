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
   survivor; bids climb the fixed legal sequence (18, 20, 22, 23, 24, 27, …).
   The last bidder is declarer; if all pass, forehand may play at 18 or throw the
   hand in.
3. **Declare** — the declarer either picks up the skat (and discards two) or
   plays *hand*, then names the contract: a trump suit, **Grand** (only the jacks
   are trumps), or **Null** (no trumps).
4. **Play** — ten tricks. In Suit and Grand the four jacks are permanent trumps
   (C > S > H > D), above the trump-suit cards in a Suit game; non-trump cards
   rank A > 10 > K > Q > 9 > 8 > 7. Null has no trumps and ranks
   A > K > Q > J > 10 > 9 > 8 > 7; the declarer must take *no* trick.
5. **Score** — only the declarer's score moves. A Suit/Grand contract needs 61+
   card points; its value is `base × multiplier`, the multiplier being matadors
   plus one for game, plus one each for hand, Schneider (a side under 31), and
   Schwarz (a side with no trick). Making it scores the value; failing loses
   twice it — or, when overbid, twice the smallest multiple of the base that
   meets the bid. Null is a fixed value (23, or 35 played from the hand).

The hand runs fully on the kernel. The Reizen is two sequential auction
`round`s over role-guarded two-participant rings — `bid` guarded to the
speaker, `yes` to the responder, `pass` open, so the candidate lists alternate
[bid, pass] / [yes, pass]; a pass (or the exhausted 62-value ladder) flips the
`until` predicate, and the survivor threads into the second contest
([decisions.md](../decisions.md), "The auction form of `round`", the
call-and-response bullet). The contract declaration is a pair of `offer`s
(play-at-18/throw-in on an all-pass; hand vs picking up the skat, with the
two-card discard in the `pick_up_skat` effect; the three-way game type) plus a
one-draw `declare_suit(s : Suit)` round. The ten tricks are three single-actor
filtered movements per trick, and the contract's order is the game's Trick
Order ([decisions.md](../decisions.md), "Trick Order"): its rows read the
declared contract off the public state, which is what puts the four jacks and
the trump suit in one follow class under Suit and Grand and leaves Null
trumpless on its own rank order. Follow legality (`follows_lead`) and the
winner (`highest_by_trick_order`) are then both the language's. Scoring writes
`score[declarer]` directly through `skat_matadors`, with the overbid rule's
smallest-covering-multiple written as rounded division (`working_bid divided
by base rounded up`) in the game text.

The contract's three variables (`is_grand`, `is_null`, `trump_suit`) are
declared at game level rather than in `phase play`, because a `trick_order`
block is a game clause and sees game state only; the phase clears them on
entry, so they still last exactly one hand.
