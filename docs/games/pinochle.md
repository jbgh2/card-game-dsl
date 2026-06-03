# Pinochle

Partnership Bid Pinochle, single-deck, 4 players. Melding is hand-waved as
a parameterized mechanic invocation.

```
game Pinochle {

  // Partnership Bid Pinochle, single deck.
  // 4 players in fixed partnerships, sitting opposite.
  // Goal: be the first team to reach 150 points.
  // Points come from both meld and tricks.

  players: 4
  partnerships: [[N, S], [E, W]]
  direction: clockwise

  // Pinochle deck: 48 cards, two copies each of A 10 K Q J 9 in each suit.
  // Ranking is unusual: 10 sits between K and A. See library.md "Stdlib decks".
  cards: pinochle48

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[team]   : TeamPile<team>
    meld_area[team]  : TeamPile<team>       // melded cards displayed face-up
  }

  state {
    // Game-level: persist across hands.
    score[team] : Integer = 0
  }

  // === Phase sequence with typed-outcome routing ===

  phase hand_sequence repeats until any team.score >= 150 {
    state {
      // Per-hand: reset each hand.
      trump             : Suit?    = none
      current_bid       : Integer  = 0
      high_bidder       : Player?  = none
      meld_score[team]  : Integer  = 0
      trick_score[team] : Integer  = 0
    }

    phase setup {
      shuffle deck
      deal 12 cards from deck to each hand
      dealer := dealer.left          // rotate per hand
    }

    phase bidding {
      active_rules: [BidExceedsCurrent, BidIsLegalIncrement]
      legal_moves:  [submit_bid, pass]

      instantiate Auction (
        participants    = all players,
        opener          = dealer.left,
        opening_bid     = 50,
        increment       = 10,
        outcome         = (final_bid, last_active_player) ⇒ {
          current_bid := final_bid
          high_bidder := last_active_player
        }
      )
    }

    // declare_trump can resolve two ways: a suit is declared, or the
    // bidder has no marriage and abandons the contract.
    declare_trump produces:
      trump_declared(t):
        continue to melding
      bid_abandoned:
        score[high_bidder.team] -= current_bid
        skip to next hand

    phase melding {
      instantiate MeldingPhase (
        participants  = all players,
        scoring_table = standard_pinochle_meld,
        trump         = trump,
        records_to    = meld_score[team]
      )
    }

    phase play {
      state {
        // Per-play: persists across all tricks in this hand.
        leader : Player = high_bidder
      }

      active_rules: [
        MustFollowSuit,
        MustHeadIfFollowing,
        MustTrumpIfVoid,
        MustOvertrumpIfTrumping
      ]
      legal_moves: [play_to_trick]

      repeat 12 times {
        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = hand,
          play_zone    = trick_pile,
          play_rules   = active_rules,
          outcome      = TrumpedHighestOfLedSuit(trump = trump),
          routing      = move all cards from trick_pile to captured[team_of(outcome)]
        )
        leader := outcome
      }
    }

    phase scoring {
      // bid_abandoned never reaches here — handled in hand_sequence above.

      for each team t:
        trick_score[t] := sum over captured[t]:
                            if card.rank in [A, 10, K]: 10
                            else: 0
        if t took the last trick: trick_score[t] += 10

      let bidder_team       = high_bidder.team
      let bidder_team_total = meld_score[bidder_team] + trick_score[bidder_team]
      let other_team        = other team

      if bidder_team_total >= current_bid:
        score[bidder_team] += bidder_team_total
        score[other_team]  += meld_score[other_team] + trick_score[other_team]
      else:
        score[bidder_team] -= current_bid
        score[other_team]  += meld_score[other_team] + trick_score[other_team]
    }
  }

  winner: team with highest score
}

// === Phase with typed outcome ===

phase declare_trump → outcome { trump_declared(Suit) | bid_abandoned } {
  active_rules: [MustHaveMarriageInDeclaredSuit]
  legal_moves:  [declare_trump_suit]

  offer action to high_bidder:
    if high_bidder.hand has marriage in any suit:
      choose suit S where high_bidder.hand has marriage in S
      trump := S
      resolve trump_declared(S)
    else:
      resolve bid_abandoned
}

// === Mechanics ===

mechanic Auction (
  participants    : List<Player>
  opener          : Player
  opening_bid     : Integer
  increment       : Integer
  outcome         : (final_bid, last_active_player) → effect
) {
  state {
    // Per-auction: lives for one Auction instance.
    current_bid     : Integer = 0
    last_bidder     : Player? = none
    passed[player]  : Boolean = false
  }

  repeat until exactly one player has not passed
            or all players have had a turn and only one bid stands {
    let active_player = next non-passed player starting from opener

    offer action to active_player: one of
      submit_bid:
        choose Integer with bid > current_bid
                          and (bid - opening_bid) divisible by increment
        current_bid := bid
        last_bidder := active_player
      pass:
        passed[active_player] := true
  }

  outcome(current_bid, last_bidder)
}

// === Rules ===

rule BidExceedsCurrent {
  constrains: submit_bid
  demands: bids strictly greater than state.current_bid
}

rule BidIsLegalIncrement {
  constrains: submit_bid
  demands: bids of the form 50 + (10 × n) for n ≥ 0
}

rule MustHaveMarriageInDeclaredSuit {
  constrains: declare_trump_suit
  demands: suits S where high_bidder.hand contains both K of S and Q of S
  // No if_impossible clause: the rule reports unsatisfiable, the phase
  // resolves to bid_abandoned, and hand_sequence handles it. The rule
  // doesn't know about scoring or what happens next.
}

rule MustFollowSuit {
  // standard library rule, repeated here for reference
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
}

rule MustHeadIfFollowing {
  // When following suit, must beat the highest card of led suit played
  // so far in this trick, if able.
  constrains: play_to_trick
  applies_when: state.led_suit is not none
                and hand.has_card_of_suit(state.led_suit)
  demands:
    let following = hand.cards_of_suit(state.led_suit)
    let highest_so_far = trick_pile.highest_of_suit(state.led_suit)
    following.where(c ⇒ c.rank > highest_so_far.rank)
  if_impossible: following     // can follow but can't beat: any follow-suit card
}

rule MustTrumpIfVoid {
  // When void in led suit, must play a trump if able.
  constrains: play_to_trick
  applies_when: state.led_suit is not none
                and not hand.has_card_of_suit(state.led_suit)
                and state.led_suit != state.trump
  demands: hand.cards_of_suit(state.trump)
}

rule MustOvertrumpIfTrumping {
  // When trumping (because void in led suit) and trumps have already been
  // played, must beat the highest trump played so far if able.
  constrains: play_to_trick
  applies_when: state.led_suit is not none
                and not hand.has_card_of_suit(state.led_suit)
                and state.led_suit != state.trump
                and hand.has_card_of_suit(state.trump)
                and trick_pile.contains_card_of_suit(state.trump)
  demands:
    let trumps = hand.cards_of_suit(state.trump)
    let highest_trump_played = trick_pile.highest_of_suit(state.trump)
    trumps.where(c ⇒ c.rank > highest_trump_played.rank)
  if_impossible: trumps        // can trump but can't overtrump: any trump
}
```
