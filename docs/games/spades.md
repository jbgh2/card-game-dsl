# Spades

```
game Spades {

  players: 4
  partnerships: [[N, S], [E, W]]
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  trump: spades

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[team]   : TeamPile<team>
  }

  state {
    // Game-level: persist across hands.
    bags[team]   : Integer = 0
    score[team]  : Integer = 0
  }

  phase hand_sequence repeats until any team.score >= 500 {
    state {
      // Per-hand: reset each hand.
      bid[player]        : Integer = unset
      tricks_won[team]   : Integer = 0
      tricks_won[player] : Integer = 0     // needed for Nil scoring
    }

    phase setup {
      shuffle(deck)
      deal 13 cards from deck to each hand
      dealer := dealer.left                 // rotate per hand
    }

    phase bidding {
      active_rules: [BidIsZeroToThirteen]
      legal_moves:  [submit_bid]

      each player in turn starting from dealer.left:
        action submit_bid:
          choose integer from 0 to 13
          bid[player] := chosen
    }

    phase play {
      state {
        // Per-play: persists across all tricks in this hand.
        leader : Player = dealer.left
      }

      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      phase spades_not_broken {
        active_rules: [+ NoLeadingSpadesUntilBroken]
        transition_to: spades_broken when play_to_trick where card.suit == spades
      }

      phase spades_broken {
        // inherits parent's MustFollowSuit only
      }

      phase first_trick {
        active_rules: [+ NoLeadingSpadesOnFirstTrick]
        // (some variants also forbid playing spades on first trick at all;
        //  this variant only forbids leading them)
        duration: one trick
      }

      repeat 13 times {
        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = hand,
          play_zone    = trick_pile,
          play_rules   = active_rules,
          outcome      = TrumpedHighestOfLedSuit(trump = spades),
          routing      = move all cards from trick_pile to captured[team_of(outcome)]
        )

        tricks_won[team_of(outcome)] += 1
        tricks_won[outcome] += 1
        leader := outcome
      }
    }

    phase scoring {
      let result = SpadesHandResult(bid, tricks_won)

      apply_components: [NilScoring, ContractScoring]

      // BagOverflow is a triggered component — see decisions.md
      // "Triggered scoring components".
    }
  }

  winner: team with highest score
}

// === Types ===

type SpadesHandResult = {
  bid[player]        : Integer
  tricks_won[team]   : Integer
  tricks_won[player] : Integer
}

// === Scoring components ===

scoring_component NilScoring (result) {
  // Per-player +100 if a Nil bidder takes zero tricks, -100 otherwise.
  let delta[team] = 0 for each team
  for each player p where result.bid[p] == 0:
    let team = team_of(p)
    if result.tricks_won[p] == 0:
      delta[team] += 100
    else:
      delta[team] -= 100
  ScoreDelta { score[t] += delta[t] for each team t }
}

scoring_component ContractScoring (result) {
  // Per-team: 10×bid on success (plus bags for overtricks), -10×bid on failure.
  let delta_score[team] = 0 for each team
  let delta_bags[team]  = 0 for each team
  for each team t:
    let non_nil_bid = sum of result.bid[p] for p in t where result.bid[p] > 0
    if result.tricks_won[t] >= non_nil_bid:
      delta_score[t] += 10 * non_nil_bid
      delta_bags[t]  += result.tricks_won[t] - non_nil_bid
    else:
      delta_score[t] -= 10 * non_nil_bid
  ScoreDelta {
    score[t] += delta_score[t] for each team t
    bags[t]  += delta_bags[t]  for each team t
  }
}

scoring_component BagOverflow {
  // Fires when a team's bag counter crosses 10. Each overflow costs
  // 100 score and decrements the counter by 10; a team that
  // accumulates 20+ bags in one hand may trigger this multiple times,
  // which the per-firing semantics handle naturally.
  triggered_by: after apply_components
    where any team t has bags[t] crosses 10
  let t = the team whose bags crossed
  ScoreDelta {
    score[t] -= 100
    bags[t]  -= 10
  }
}

// === Spades-specific rules ===

rule BidIsZeroToThirteen {
  constrains: submit_bid
  demands: integers in 0..13
}

rule NoLeadingSpadesUntilBroken {
  constrains: play_to_trick
  applies_when: trick.led_suit is none
  demands: hand.where(c ⇒ c.suit != spades)
}

rule NoLeadingSpadesOnFirstTrick {
  constrains: play_to_trick
  applies_when: trick.led_suit is none
  demands: hand.where(c ⇒ c.suit != spades)
}

// === Standard library outcome function ===

outcome TrumpedHighestOfLedSuit (trump_suit) = (played_cards, trick_state) ⇒
  let trumps_played = played_cards.filter(c ⇒ c.suit == trump_suit)
  if trumps_played.non_empty:
    player_of(argmax trumps_played by rank)
  else:
    player_of(argmax played_cards.filter(c ⇒ c.suit == trick_state.led_suit) by rank)
```
