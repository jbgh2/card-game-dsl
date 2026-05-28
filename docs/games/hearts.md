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
      // Per-hand: resets each hand.
      pass_direction : Direction = left
    }

    phase setup {
      shuffle deck
      deal 13 cards from deck to each hand
      rotate pass_direction through [left, right, across, none]
    }

    phase passing when pass_direction != none {
      active_rules: [PassExactlyThreeCards]
      legal_moves:  [transfer_between_hands]

      each player simultaneously:
        transfer chosen 3 cards
          from hand[player]
          to   hand[player offset_by pass_direction]
    }

    phase first_trick {
      state {
        // Per-first_trick: a single trick.
        leader : Player = player_holding(2 of clubs)
      }

      active_rules: [
        MustFollowSuit,
        MustLeadTwoOfClubsOnFirstPlay,
        NoPenaltyCardsOnFirstTrick
      ]
      legal_moves: [play_to_trick]

      instantiate Trick (
        participants = all players,
        leader       = leader,
        source_zone  = hand,
        play_zone    = trick_pile,
        play_rules   = active_rules,
        outcome      = highest_of_led_suit,
        routing      = all cards from trick_pile to captured[outcome]
      )
    }

    phase play {
      state {
        // Per-play: persists across all non-first tricks in this hand.
        leader : Player = outcome of last trick from first_trick
      }

      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      phase hearts_not_broken {
        active_rules: [+ NoLeadingHeartsUntilBroken]
        transition_to: hearts_broken when any heart_played event fires
      }

      phase hearts_broken {
        // inherits parent's MustFollowSuit only
      }

      // Body: loop tricks until hands empty.
      repeat until all hands empty {
        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = hand,
          play_zone    = trick_pile,
          play_rules   = active_rules,                    // resolves at runtime
          outcome      = highest_of_led_suit,
          routing      = all cards from trick_pile to captured[outcome]
        )
        leader := outcome of last trick
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
  // if_impossible defaults to any card in hand
}

rule NoLeadingHeartsUntilBroken {
  constrains: play_to_trick
  applies_when: state.led_suit is none   // i.e., leading
  demands: hand.where(c ⇒ c.suit != hearts)
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
}
```
