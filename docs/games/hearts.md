# Hearts

```
game Hearts {

  players: 4
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }

  state {
    // Game-level: persists across hands.
    cumulative_score[player] : Integer = 0
  }

  // === Top-level phase sequence ===

  phase hand_sequence repeats until any cumulative_score >= 100 {
    state {
      // Loop state: persists across hands; before_each rotates it each hand,
      // so starting at `hold` makes hand 1 pass left.
      pass_direction : Direction = hold
      // Trick leader, threaded from first_trick into play by lexical scope.
      leader         : Player?   = none
    }

    before_each {
      move all cards to deck    // gather the previous hand's cards back home
      shuffle deck
      deal 13 cards from deck to each hand
      rotate pass_direction through [left, right, across, hold]
    }

    phase passing when pass_direction != hold {
      active_rules: [PassExactlyThreeCards]
      legal_moves:  [transfer_between_hands]

      each player simultaneously:
        transfer chosen 3 cards
          from hand[player]
          to   hand[player offset_by pass_direction]
    }

    phase first_trick {
      active_rules: [
        MustFollowSuit,
        MustLeadTwoOfClubsOnFirstPlay,
        NoPenaltyCardsOnFirstTrick
      ]
      legal_moves: [play_to_trick]

      leader := player_holding(2 of clubs)
      round play_to_trick from leader over all players source hand into trick_pile
            outcome highest_of_led_suit
      move all cards from trick_pile to captured[outcome]
      leader := outcome
    }

    phase play {
      // Continues from the enclosing `leader`, set by first_trick.
      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      phase hearts_not_broken {
        active_rules: [+ NoLeadingHeartsUntilBroken]
        transition_to: hearts_broken when play_to_trick where action.card.suit == hearts
      }

      phase hearts_broken {
        // inherits parent's MustFollowSuit only
      }

      // Body: loop tricks until hands empty.
      repeat until all hands empty {
        round play_to_trick from leader over all players source hand into trick_pile
              outcome highest_of_led_suit
        move all cards from trick_pile to captured[outcome]
        leader := outcome
      }
    }

    phase scoring {
      // base and hand_score are phase-local lets, not declared state.
      let base[p] = sum over captured[p]:
                      if card.suit == hearts          then 1
                      elif card == queen_of_spades    then 13
                      else 0

      let hand_score[p] =
        if any player p has base[p] == 26:                // shoot the moon
          if p shot the moon: 0 else: 26
        else:
          base[p]

      for each player p: cumulative_score[p] += hand_score[p]
    }
  }

  winner: lowest cumulative_score
}

// === Hearts-specific rules ===

rule MustLeadTwoOfClubsOnFirstPlay {
  constrains: play_to_trick
  applies_when: state.led_suit is none      // i.e., leading
  demands: hand.where(c ⇒ c == 2 of clubs)
  if_impossible: error("first lead must be 2 of clubs; only the holder can lead")
}

rule NoPenaltyCardsOnFirstTrick {
  constrains: play_to_trick
  applies_when: always   // already scoped to the first_trick sub-phase
  demands: hand.where(c ⇒ c.suit != hearts and c != queen_of_spades)
  if_impossible: hand   // only penalty cards in hand: play one
}

rule NoLeadingHeartsUntilBroken {
  constrains: play_to_trick
  applies_when: state.led_suit is none   // i.e., leading
  demands: hand.where(c ⇒ c.suit != hearts)
  if_impossible: hand   // only hearts left: a heart must be led
}

rule PassExactlyThreeCards {
  constrains: transfer_between_hands
  demands: the move must consist of exactly 3 cards
}

// === Standard library rule ===

rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
  if_impossible: hand   // void in the led suit: play any card
}
```
