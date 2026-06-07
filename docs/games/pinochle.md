# Pinochle

The companion formal file is [pinochle.cardlang](pinochle.cardlang); this is the
readable twin. Partnership Bid Pinochle, single 48-card pack (two copies each of
A 10 K Q J 9 per suit; 10 ranks between K and A), four players in fixed
partnerships sitting across. First team to **150** wins.

Each hand:

1. Deal 12 cards each.
2. **Auction** — an ascending bid opening at 50 and rising in 10s; players pass
   out, the last bidder takes the contract.
3. **Declare trump** — the high bidder names a suit he holds a *marriage* (K-Q)
   in. With no marriage anywhere he abandons the bid and his side is set back by
   the bid amount.
4. **Meld** — both sides score their meld combinations (runs, marriages, dix,
   pinochle, and the four-around sets — the standard single-pack values, with
   doubles scoring the published double values).
5. **Play** — twelve strict tricks: follow suit and head the led suit if you
   can; if void, trump and over-trump if you can. A/10/K captured score 10 each,
   and the last trick is worth 10 (250 trick points in all).
6. **Score** — the bidding side adds meld + tricks if it reached its bid, else is
   set back by the bid; the other side always adds its meld + tricks.

The hand engine — the auction, the trump declaration, the meld scoring, and the
strict trick play — runs in the built-in `PinochleHand` mechanic. Auctions vary
in shape across the corpus and the strict-trick legality rules recur, so neither
is lifted into the rule DSL yet (flagged in IMPLEMENTATION_LOG.md); the cardlang
below holds the deal, the contract settlement, and termination.

```
game Pinochle {

  players: 4
  partnerships: [[0, 2], [1, 3]]   // partners sit across the four-hand ring
  direction: clockwise

  cards: pinochle48
  ranking: A 10 K Q J 9            // 10 sits between K and A

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
  }

  state {
    // Game-level: persist across hands.
    score[team] : Integer = 0
  }

  phase hand_sequence repeats until (any team t: score[t] >= 150) {
    state {
      dealer            : Player  = 0
      trump_suit        : Suit?   = none
      current_bid       : Integer = 0
      high_bidder       : Player? = none
      bid_abandoned     : Boolean = false
      meld_score[team]  : Integer = 0
      trick_score[team] : Integer = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 12 cards from deck to each hand
      dealer := dealer offset_by left
      for each team t: meld_score[t] := 0
      for each team t: trick_score[t] := 0
      bid_abandoned := false
    }

    phase play {
      legal_moves: [submit_bid, pass, declare_trump_suit, play_to_trick]
      instantiate PinochleHand(opener = dealer offset_by left)
    }

    phase scoring {
      if bid_abandoned {
        score[team_of(high_bidder)] -= current_bid
      } else {
        for each team t:
          if t == team_of(high_bidder) {
            if meld_score[t] + trick_score[t] >= current_bid {
              score[t] += meld_score[t] + trick_score[t]
            } else {
              score[t] -= current_bid
            }
          } else {
            score[t] += meld_score[t] + trick_score[t]
          }
      }
    }
  }

  winner: highest score
}
```
