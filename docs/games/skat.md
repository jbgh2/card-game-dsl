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

The hand engine — Reizen, the contract choice, the per-contract trump structure,
and the scoring — runs in the built-in `SkatHand` mechanic (the auction and the
three trump structures are not yet expressible in the rule DSL). The cardlang holds the deal, hand counting, and
termination.

```
game Skat {

  players: 3
  direction: clockwise

  cards: skat32
  ranking: A 10 K Q J 9 8 7

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    skat             : FaceDownPile        // the two-card widow
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }

  state {
    score[player] : Integer = 0
    hands_played  : Integer = 0
  }

  phase hand_sequence repeats until hands_played >= 36 {
    state {
      dealer : Player = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 3 cards from deck to each hand
      deal 2 cards from deck to skat
      deal 4 cards from deck to each hand
      deal 3 cards from deck to each hand
      dealer := dealer offset_by left
    }

    phase play {
      legal_moves: [
        pass, bid, yes, play_at_eighteen, throw_in,
        pick_up_skat, declare_hand,
        declare_suit_diamonds, declare_suit_hearts, declare_suit_spades,
        declare_suit_clubs, declare_grand, declare_null,
        play_to_trick
      ]
      instantiate SkatHand(forehand = dealer offset_by left)
    }

    after_each {
      hands_played += 1
    }
  }

  winner: highest score
}
```
