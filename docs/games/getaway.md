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
      // Trick leader, threaded from first_trick into play by lexical scope.
      leader             : Player  = none
    }

    phase setup {
      deal all cards from deck as-equally-as-possible to each hand
    }

    phase first_trick {
      // forced lead: AS only
      active_rules: [
        MustFollowSuit,
        MustLeadAceOfSpadesOnFirstPlay
      ]
      // First-trick-to-waste isn't a rule — it's a Trick routing
      // parameter. See the `routing =` line in the Trick instantiation
      // below, and decisions.md "Trick mechanic parameters vs rules".
      legal_moves: [play_to_trick]

      leader := player_holding(ace of spades)
      instantiate Trick (
        participants     = all players,
        leader           = leader,
        source_zone      = hand,
        play_zone        = trick_pile,
        play_rules       = active_rules,
        early_termination = on_play_of_tochoo,
        outcome          = highest_of_led_suit,
        routing          = move all cards from trick_pile to waste
      )
      leader := outcome
    }

    phase play {
      // Continues from the enclosing `leader`, set by first_trick.
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

rule OptionalStealLeftIfAlone {
  constrains: steal_left
  applies_when: leader is the only player with cards in their hand
                and other players still have cards in waste
  demands: a steal_left move is permitted (not required)
}
```
