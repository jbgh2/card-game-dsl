# Getaway (Bhabhi)

```
game Getaway {

  players: 3..8
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    hand[player]   : Hand<player>
    trick_pile     : TrickPile
    waste          : RandomizedPile          // cards entered publicly, positionally shuffled — outcome draws random
  }

  phase game_sequence {
    state {
      // Game-level: persists for the whole game.
      eliminated[player] : Boolean = false
    }

    phase setup {
      deal all cards from deck as-equally-as-possible to each hand
    }

    phase first_trick {
      state {
        // Per-first_trick: a single trick. Leader is forced.
        leader : Player = player_holding(ace of spades)
      }

      // forced lead: AS only
      active_rules: [
        MustFollowSuit,
        MustLeadAceOfSpadesOnFirstPlay,
        FirstTrickAlwaysGoesToWaste
      ]
      legal_moves: [play_to_trick]

      instantiate Trick (
        participants     = all players,
        leader           = leader,
        source_zone      = hand,
        play_zone        = trick_pile,
        play_rules       = active_rules,
        early_termination = on_play_of_tochoo,
        outcome          = highest_of_led_suit,
        routing          = all cards from trick_pile to waste
      )
    }

    phase play {
      state {
        // Per-play: persists across all non-first tricks.
        leader : Player = outcome of last trick from first_trick
      }

      active_rules: [MustFollowSuit, OptionalStealLeftIfAlone]
      legal_moves:  [play_to_trick, steal_left]

      repeat until exactly one player has cards {

        // optional pre-trick steal action
        offer optional_action steal_left to leader

        instantiate Trick (
          participants     = players where not eliminated,
          leader           = leader,
          source_zone      = hand,
          play_zone        = trick_pile,
          play_rules       = active_rules,
          early_termination = on_play_of_tochoo,
          outcome          = highest_of_led_suit,
          routing          = GetawayRouting
        )

        // post-trick: outcome leads next; check eliminations
        leader := outcome
        for each player p: if p.hand is empty: eliminated[p] := true

        // post-trick: if outcome has no cards and game continues, draw from waste
        if outcome.hand is empty and active_players > 1:
          outcome draws random card from waste
          outcome must lead it next trick
      }
    }
  }

  loser: the one player with cards remaining
}

routing GetawayRouting (trick_pile_contents, trick_state, outcome) {
  // trick_state.trick_terminated_early is read from the enclosing Trick
  // mechanic's own state (declared inside Trick, not in the game).
  if trick_state.trick_terminated_early:
    move all to outcome.hand              // pickup: outcome is the loser
  else:
    move all to waste                     // everyone followed: cards discarded
}

// === Getaway-specific rules ===

rule MustLeadAceOfSpadesOnFirstPlay {
  constrains: play_to_trick
  applies_when: trick.led_suit is none       // reads led_suit from the Trick mechanic's state
  demands: hand.where(c ⇒ c == ace of spades)
  if_impossible: error("first lead must be the ace of spades")
}

rule FirstTrickAlwaysGoesToWaste {
  // This is really a routing constraint, not a play constraint.
  // Encoded here as a phase-level routing override.
  applies_during: first_trick phase
  override_routing: all cards from trick_pile to waste
}

rule OptionalStealLeftIfAlone {
  constrains: steal_left
  applies_when: leader is the only player with cards in their hand
                and other players still have cards in waste
  demands: a steal_left move is permitted (not required)
}
```
