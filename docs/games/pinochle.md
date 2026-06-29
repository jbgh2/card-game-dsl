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

The ascending auction runs on the kernel `round` (a shrinking participants ring
over the `submit_bid`/`pass` vocabulary below, settling on a declarer and his
bid). The trump declaration, the meld scoring, and the strict trick play run in
the `PinochleRest` mechanic — the strict-trick legality rules recur but aren't
lifted into the rule DSL yet; the cardlang below holds the deal, the auction, the
contract settlement, and termination.

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

    phase auction -> outcome { bid_won(Player, Integer) } {
      state {
        passed[player] : Boolean = false
        bids           : Integer = 0
        lead_bidder    : Player? = none
        working_bid    : Integer = 0
        opener         : Player? = none
      }
      opener := dealer offset_by left
      round offering [submit_bid, pass] from opener
            over players where not passed[player]
                              and (lead_bidder is none or player != lead_bidder)
            until (number of players where not passed[player]) <= 1 or bids >= 16
            outcome pinochle_auction_outcome
    }
    auction produces:
      bid_won(d, c) { high_bidder := d  current_bid := c  continue to play }

    phase play {
      legal_moves: [declare_trump_suit, play_to_trick]
      instantiate PinochleRest(declarer = high_bidder)
    }

    phase scoring {
      if bid_abandoned {
        score[team_of(high_bidder)] -= current_bid
      } else {
        for each team t:
          if t == team_of(high_bidder) {
            if team_score_in_hand(t) >= current_bid {
              score[t] += team_score_in_hand(t)
            } else {
              score[t] -= current_bid
            }
          } else {
            score[t] += team_score_in_hand(t)
          }
      }
    }
  }

  winner: highest score
}

// The bid value is derived, not chosen: 50 to open, then a fixed 10 higher.
move_type submit_bid {
  effect {
    working_bid := if working_bid == 0 then 50 else working_bid + 10
    lead_bidder := actor
    bids        := bids + 1
  }
}
move_type pass { effect { passed[actor] := true } }

// A team's total for the hand: meld plus tricks. Named so the bidder's
// make-the-bid test and every team's payout add the same total from one place.
function team_score_in_hand(t : Team) = meld_score[t] + trick_score[t]
```
