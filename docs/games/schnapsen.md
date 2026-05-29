# Schnapsen

Two-player point-trick game of the Ace-Ten / Marriage group. 20-card
deck, target 66 card points per hand, game played to 7 game points
(scored downward). Soft Schnapsen, Austrian rules. Source:
[Pagat](https://www.pagat.com/marriage/schnaps.html).

Schnapsen is the corpus's first two-player game and the first game
whose trick rules change mid-hand. The mid-hand rule flip is expressed
as a sub-phase that *adds* the strict-follow rule set on top of an
unrestricted parent — matching how the rulebook actually reads ("there
is no obligation to follow suit until the talon is exhausted or
closed, at which point the tricks remaining in hand are played out
strictly").

```
game Schnapsen {

  players: 2
  direction: clockwise   // irrelevant with 2 players; included for uniformity

  cards: {
    suits: [S, H, D, C]
    ranks: [J, Q, K, 10, A]            // J lowest, A highest; 10 above K
  }

  zones {
    deck                 : Deck
    talon                : FaceDownPile            // remaining undealt cards
    trump_indicator      : Discard                 // the face-up trump card
    hand[player]         : Hand<player>
    trick_pile           : TrickPile
    captured[player]     : PlayerPile<player>
  }

  state {
    // Game-level: persists across hands.
    game_score[player] : Integer = 7               // scored downward; 0 wins
  }

  // === Top-level phase sequence ===

  phase hand_sequence repeats until any game_score <= 0 {
    state {
      // Per-hand: reset each hand.
      trump                       : Suit?    = none
      card_points[player]         : Integer  = 0
      tricks_won[player]          : Integer  = 0
      pending_marriage[player]    : Integer  = 0   // credited when player takes any trick
      talon_closed_by             : Player?  = none
      // Viennese-closing snapshot — captured when a player closes the talon.
      closer_card_points          : Integer  = 0
      closer_opp_card_points      : Integer  = 0
      closer_opp_tricks           : Integer  = 0
    }

    phase setup {
      shuffle deck
      deal 3 cards from deck to each hand
      flip top of deck face-up onto trump_indicator
      trump := suit of trump_indicator.top
      deal 2 cards from deck to each hand
      move remaining deck cards onto talon (crosswise over trump_indicator
        so the trump remains visible)
      dealer := other player                     // dealer rotates per hand
    }

    phase play {
      state {
        leader : Player = other player than dealer       // non-dealer leads first
      }

      // Parent rule set is empty: trick-and-draw permits any play.
      active_rules: []
      legal_moves: [play_to_trick, declare_marriage, claim_66]

      phase talon_open {
        legal_moves: [+ exchange_trump_jack, + close_talon]
        // Two moves are sub-phase-local: trump-Jack exchange and
        // talon closing both vanish once the talon is closed/exhausted.
        // See decisions.md ("Sub-phase rule and legal-move deltas").

        transition_to: talon_closed
          when close_talon move played
          or talon becomes empty

        // Trick loop: trick, draw, repeat.
        repeat {
          instantiate Trick (
            participants = all players,
            leader       = leader,
            source_zone  = hand,
            play_zone    = trick_pile,
            play_rules   = active_rules,
            outcome      = TrumpedHighestOfLedSuit(trump = trump),
            routing      = all cards from trick_pile to captured[outcome]
          )

          card_points[outcome] += sum of card values played to this trick
          tricks_won[outcome]  += 1

          // Credit any pending marriage now that the marriage-declarer has
          // taken at least one trick.
          if pending_marriage[outcome] > 0:
            card_points[outcome] += pending_marriage[outcome]
            pending_marriage[outcome] := 0

          // Last-card-of-talon rule: face-down card to winner, face-up
          // trump to loser. Triggers transition_to into talon_closed.
          if talon has exactly 2 cards left and not closed:
            deal 1 card from talon to hand[outcome]
            move trump_indicator to hand[other player than outcome]
            // talon now empty → sub-phase transition fires
          else:
            deal 1 card from talon to hand[outcome]
            deal 1 card from talon to hand[other player than outcome]

          leader := outcome
        }
      }

      phase talon_closed {
        active_rules: [+ MustFollowSuit, + MustHeadIfFollowing, + MustTrumpIfVoid]
        // Strict play. See decisions.md
        // ("Sub-phase rule and legal-move deltas").

        // Trick loop: no drawing.
        repeat until all hands empty or any player claim_66 played {
          instantiate Trick (
            participants = all players,
            leader       = leader,
            source_zone  = hand,
            play_zone    = trick_pile,
            play_rules   = active_rules,
            outcome      = TrumpedHighestOfLedSuit(trump = trump),
            routing      = all cards from trick_pile to captured[outcome]
          )

          card_points[outcome] += sum of card values played to this trick
          tricks_won[outcome]  += 1

          if pending_marriage[outcome] > 0:
            card_points[outcome] += pending_marriage[outcome]
            pending_marriage[outcome] := 0

          leader := outcome
        }
      }
    }

    phase scoring → outcome { closer_won | closer_lost | won_by_claim | last_trick_default } {
      // Score in game points, deducted from game_score (which starts at 7).
      // The five settlement shapes:
      //   - correct claim of 66 (no close):      1 / 2 / 3 by opponent tier
      //   - correct claim after closing:         1 / 2 / 3 by opponent's tier at moment of close
      //   - failed close (closer didn't reach 66): 2 / 3 to opponent
      //   - opponent of closer reaches 66 first:   2 / 3 to opponent
      //   - last trick taken with neither claim:  1 to last-trick winner

      let claimer = the player whose claim_66 produced this phase (if any)

      if claimer != none and card_points[claimer] >= 66:
        let opp = other player than claimer
        let opp_cp     = if talon_closed_by == claimer then closer_opp_card_points else card_points[opp]
        let opp_tricks = if talon_closed_by == claimer then closer_opp_tricks      else tricks_won[opp]
        let game_pts =
          if opp_tricks == 0:                       3   // Schwarz
          elif opp_cp < 33:                         2   // Schneider
          else:                                     1
        game_score[claimer] -= game_pts
        resolve won_by_claim

      elif claimer != none and card_points[claimer] < 66:
        // False claim: opponent scores 2 (3 if claimer was their first trick).
        let opp = other player than claimer
        let game_pts = if tricks_won[opp] == 0 then 3 else 2
        game_score[opp] -= game_pts
        resolve closer_lost when talon_closed_by == claimer else won_by_claim

      elif talon_closed_by != none:
        // Closer failed to claim before hand ended.
        let closer = talon_closed_by
        let opp = other player than closer
        let game_pts = if closer_opp_tricks == 0 then 3 else 2
        game_score[opp] -= game_pts
        resolve closer_lost

      else:
        // Nobody closed, nobody claimed, hands ran out.
        let winner = player who took the last trick
        game_score[winner] -= 1
        resolve last_trick_default
    }
  }

  winner: first player whose game_score <= 0
}

// =====================================================================
// Move types
// =====================================================================

// play_to_trick: standard (see games/hearts.md, games/spades.md).

// declare_marriage: lead K or Q of a same-suit pair, score pending.
move_type declare_marriage {
  source: hand[active_player]
  destination: trick_pile
  preconditions: active_player is leading
              and tricks_won[active_player] + tricks_won[other] >= 0  // soft rule: declarable at any lead
              and hand[active_player] contains both K and Q of some suit S
  carries: declared_suit : Suit
  effect:
    let value = if declared_suit == trump then 40 else 20
    if tricks_won[active_player] > 0:
      card_points[active_player] += value
    else:
      pending_marriage[active_player] += value
    // The actual lead — K or Q — is the trick play; the other card stays
    // in hand but is revealed to both players.
    reveal partner card of declared marriage
}

// exchange_trump_jack: swap J of trump in hand for the trump indicator.
move_type exchange_trump_jack {
  source: hand[active_player]
  destination: trump_indicator
  preconditions: active_player is leading
              and hand[active_player] contains J of trump
  effect:
    swap J of trump (in hand) with the card on trump_indicator
}

// close_talon: flip trump indicator face-down on talon; talon stops drawing.
move_type close_talon {
  preconditions: active_player is leading
              and talon.size >= 2     // can only close while talon has draws
  effect:
    flip trump_indicator face-down onto talon
    talon_closed_by := active_player
    // Snapshot opponent state for Viennese closing scoring.
    closer_card_points     := card_points[active_player]
    closer_opp_card_points := card_points[other player than active_player]
    closer_opp_tricks      := tricks_won [other player than active_player]
}

// claim_66: assert you have ≥ 66 card points. Verified in scoring.
move_type claim_66 {
  preconditions: active_player just won a trick or just declared a marriage
  effect:
    // No state change; the scoring phase reads card_points and settles.
    transition to scoring with claimer := active_player
}

// =====================================================================
// Rules
// =====================================================================

// MustFollowSuit, MustHeadIfFollowing, MustTrumpIfVoid: see games/pinochle.md.
// Schnapsen's MustHeadIfFollowing is the same shape as Pinochle's
// (must play higher of led suit if able; fall back to any of led suit).
// Schnapsen has no MustOvertrumpIfTrumping — the rule does not appear in
// the strict-play sub-phase.
```
