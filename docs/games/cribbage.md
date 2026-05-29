# Cribbage

Two-player six-card Cribbage. First to 121 points, scored from multiple
sources: pegging events fire during play; the show counts combinations
in each player's hand plus the dealer's crib, against a shared starter
card. Source: [Pagat](https://www.pagat.com/adders/crib6.html).

Cribbage is the corpus's first game with:

- A scoring stream that fires *during* play (the pegging score), expressed
  via `triggered_by:` clauses on scoring components. See decisions.md
  "Triggered scoring components".
- A *crib*: a face-down zone owned by the dealer but populated by both
  players' discards. New zone-ownership shape.
- A *starter*: a single public card revealed at cut, used by every
  show-time hand evaluation including the crib.
- Game-termination mid-phase: a player who pegs past 120 wins
  immediately, possibly during pegging or even on the starter cut.
- Sequential `apply_components:` batches in one phase. The show is
  three batches (non-dealer hand, dealer hand, crib), settled in
  rulebook order, with the hand_sequence early-termination check
  observed between each. Within each batch the components remain
  internally unordered. See decisions.md, "Mutation semantics".

```
game Cribbage {

  players: 2
  direction: clockwise   // irrelevant with 2 players; included for uniformity

  cards: standard52
  ranking: A 2 3 4 5 6 7 8 9 10 J Q K   // A low; J/Q/K all worth 10 for pegging

  zones {
    deck                : Deck
    hand[player]        : Hand<player>
    crib                : FaceDownPile         // owned by dealer, fed by both
    starter             : Discard              // one card, face-up, visible to all
    play_pile           : TrickPile            // current pegging round
    played[player]      : PlayerPile<player>   // pegged cards (face down between rounds)
  }

  state {
    // Game-level: persists across hands.
    score[player] : Integer = 0
  }

  // === Top-level phase sequence ===

  phase hand_sequence repeats until any score >= 121 {
    // Score-cap check at hand boundary catches end-of-show winners.
    // Mid-hand winners are caught by the early_termination clause on
    // each pegging round (see below).

    state {
      // Per-hand: reset each hand.
      running_total : Integer = 0
      last_pegger   : Player? = none           // player who last played, for go/last-card
    }

    phase setup {
      shuffle deck
      deal 6 cards from deck to each hand
      dealer := other player    // dealer rotates per hand
    }

    phase discard {
      active_rules: [DiscardExactlyTwo]
      legal_moves: [discard_to_crib]

      each player simultaneously:
        choose 2 cards from hand[player]
        transfer chosen cards from hand[player] to crib
    }

    phase cut_starter {
      // Non-dealer cuts the remainder of the deck; dealer reveals the
      // top of the lower portion as the starter.
      reveal top of deck to starter
      // His Heels fires here if applicable (see scoring components below).
    }

    phase pegging {
      state {
        leader : Player = other player than dealer   // non-dealer leads first round
      }

      legal_moves: [play_card, declare_go]

      // Run pegging rounds until both hands are empty.
      repeat until all hands empty {
        instantiate PeggingRound (leader = leader)

        // The PeggingRound mechanic sets `last_pegger` on exit and
        // returns the player who plays first in the next round
        // (= other player than last_pegger).
        leader := other player than last_pegger
      }
    }

    phase show {
      // Order matters: non-dealer counts first, then dealer's hand,
      // then the crib. The rulebook is explicit that these happen
      // sequentially: if non-dealer pegs past 120, the game ends and
      // the dealer never scores. Three sequential batches, with the
      // hand_sequence early-termination check between each, match
      // the rulebook's serial settlement.

      let non_dealer = other player than dealer

      apply_components: [
        ShowFifteens(scoring_hand = hand[non_dealer], owner = non_dealer),
        ShowPairs   (scoring_hand = hand[non_dealer], owner = non_dealer),
        ShowRuns    (scoring_hand = hand[non_dealer], owner = non_dealer),
        ShowFlush   (scoring_hand = hand[non_dealer], owner = non_dealer, flush_mode = hand),
        ShowHisNob  (scoring_hand = hand[non_dealer], owner = non_dealer)
      ]

      apply_components: [
        ShowFifteens(scoring_hand = hand[dealer], owner = dealer),
        ShowPairs   (scoring_hand = hand[dealer], owner = dealer),
        ShowRuns    (scoring_hand = hand[dealer], owner = dealer),
        ShowFlush   (scoring_hand = hand[dealer], owner = dealer, flush_mode = hand),
        ShowHisNob  (scoring_hand = hand[dealer], owner = dealer)
      ]

      apply_components: [
        ShowFifteens(scoring_hand = crib, owner = dealer),
        ShowPairs   (scoring_hand = crib, owner = dealer),
        ShowRuns    (scoring_hand = crib, owner = dealer),
        ShowFlush   (scoring_hand = crib, owner = dealer, flush_mode = crib),
        ShowHisNob  (scoring_hand = crib, owner = dealer)
      ]

      // Reset zones for the next deal.
      move all cards from played[player]  to deck for each player
      move all cards from hand[player]    to deck for each player
      move all cards from crib            to deck
      move starter                        to deck
    }
  }

  winner: first player to reach 121
}

// =====================================================================
// PeggingRound mechanic
// =====================================================================

// One round of pegging: the running total starts at 0, players
// alternate, and the round ends when both players have said `go`
// or when a play brings the total to exactly 31, or when both hands
// are empty.

mechanic PeggingRound (leader: Player) {
  state {
    consecutive_gos : Integer = 0
    last_played    : Player?  = none
  }

  // Mid-round, watch for the game-ending score threshold.
  early_termination: any score >= 121
  // `early_termination` here means "abandon the round and signal the
  // enclosing hand_sequence to abandon too". See
  // open-questions/game-mid-phase-termination.md.

  active_rules: [CannotExceedThirtyOne]
  legal_moves: [play_card, declare_go]

  let active = leader

  repeat until consecutive_gos >= 2 or hand[active].is_empty and hand[other].is_empty {
    offer action to active:
      if hand[active].has_card playable_under(31):
        play_card:
          choose card c from hand[active] where running_total + value(c) <= 31
          transfer c from hand[active] to play_pile
          running_total += value(c)
          last_played   := active
          last_pegger   := active
          consecutive_gos := 0
          // Triggered scoring components fire on this play_card event.
      else:
        declare_go:
          consecutive_gos += 1
          // No state change beyond the gos counter.

    active := other player than active
  }

  // Round end: award the "last card" point if the round didn't close
  // on exactly 31. The PeggingLastCard scoring component handles this
  // via triggered_by on the end_of_round event emitted here.
  emit end_of_round event {
    last_total  : Integer = running_total
    last_player : Player  = last_played
  }

  // Reset for next round.
  move all cards from play_pile to played[player_who_played(card)] for each card
  running_total   := 0
}

// =====================================================================
// Move types
// =====================================================================

move_type discard_to_crib {
  source: hand[active_player]
  destination: crib
  // Each player discards exactly two cards. See DiscardExactlyTwo rule.
}

move_type play_card {
  source: hand[active_player]
  destination: play_pile
  // Cards keep their pegging value (A=1, 2..10=face, J/Q/K=10).
  // value(c) is stdlib: see "Card value functions" in library.md.
}

move_type declare_go {
  // No card moved; marker that the active player cannot play under 31.
  preconditions: no card in hand[active_player] has value <= (31 - state.running_total)
}

// =====================================================================
// Rules
// =====================================================================

rule DiscardExactlyTwo {
  constrains: discard_to_crib
  demands: each player chooses exactly 2 cards
}

rule CannotExceedThirtyOne {
  constrains: play_card
  demands: cards c where state.running_total + value(c) <= 31
  // If unsatisfiable, the player must declare_go.
}

// =====================================================================
// Triggered scoring components (fire during play)
// =====================================================================

// Each fires on a specific event. The `triggered_by:` clause names the
// event and (optionally) constrains the firing predicate. See
// decisions.md "Triggered scoring components".

scoring_component HisHeels {
  triggered_by: cut_starter event where starter.rank == J
  ScoreDelta { score[dealer] += 2 }
}

scoring_component PeggingFifteen {
  triggered_by: play_card event where running_total == 15 after the play
  ScoreDelta { score[active_player] += 2 }
}

scoring_component PeggingThirtyOne {
  triggered_by: play_card event where running_total == 31 after the play
  ScoreDelta { score[active_player] += 2 }
}

scoring_component PeggingPair {
  // Pair = last 2 cards same rank: 2 points
  // Pair royal = last 3 cards same rank: 6 points
  // Double pair royal = last 4 cards same rank: 12 points
  triggered_by: play_card event where play_pile.suffix_same_rank_count >= 2
  let n = play_pile.suffix_same_rank_count
  let points = n × (n - 1)             // 2, 6, 12 for n = 2, 3, 4
  ScoreDelta { score[active_player] += points }
}

scoring_component PeggingRun {
  // Run = longest sequence in play_pile suffix that forms a run of length ≥ 3
  // when sorted (cards need not have been played in run order).
  triggered_by: play_card event where play_pile.longest_suffix_run_length >= 3
  let n = play_pile.longest_suffix_run_length
  ScoreDelta { score[active_player] += n }
}

scoring_component PeggingLastCard {
  // 1 point for last card of round, but only if the round did not close
  // on exactly 31 (the PeggingThirtyOne is the alternative, not stackable).
  triggered_by: end_of_round event where last_total < 31
  ScoreDelta { score[last_player] += 1 }
}

// =====================================================================
// Show scoring components (per-hand, applied at end of pegging)
// =====================================================================

// Each fires once per scoring batch (non-dealer hand, dealer hand,
// or crib). Five cards are evaluated: the four-card scoring_hand
// plus the starter.

scoring_component ShowFifteens (scoring_hand, owner) {
  let five = scoring_hand + starter
  let count = number of subsets of `five` whose values sum to 15
  ScoreDelta { score[owner] += 2 × count }
}

scoring_component ShowPairs (scoring_hand, owner) {
  let five = scoring_hand + starter
  let count = number of unordered pairs of equal-rank cards in `five`
  ScoreDelta { score[owner] += 2 × count }
  // 3-of-a-kind has 3 pairs (6 pts); 4-of-a-kind has 6 pairs (12 pts).
}

scoring_component ShowRuns (scoring_hand, owner) {
  let five = scoring_hand + starter
  // Find the longest run length L ≥ 3 over `five` (ignoring suits).
  // Count K = number of distinct length-L runs (multiple if duplicates).
  let L = longest_run_length(five)
  let K = run_multiplicity(five, L)
  if L >= 3:
    ScoreDelta { score[owner] += L × K }
}

scoring_component ShowFlush (scoring_hand, owner, flush_mode) {
  // flush_mode == hand: 4 cards same suit = 4; +1 if starter same suit = 5.
  // flush_mode == crib: only scores 5 if all 5 (crib + starter) same suit.
  let suit = scoring_hand.first.suit
  let hand_uniform = all four cards of scoring_hand are suit
  match flush_mode:
    hand:
      if hand_uniform:
        let bonus = 1 if starter.suit == suit else 0
        ScoreDelta { score[owner] += 4 + bonus }
    crib:
      if hand_uniform and starter.suit == suit:
        ScoreDelta { score[owner] += 5 }
}

scoring_component ShowHisNob (scoring_hand, owner) {
  if scoring_hand contains the J of suit == starter.suit:
    ScoreDelta { score[owner] += 1 }
}
```
