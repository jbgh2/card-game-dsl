# Bridge (rubber, simplified)

Rubber Bridge, simplified: honors and finer bonuses omitted. Game/rubber
bonuses kept. Bidding is hand-waved as a mechanic invocation, following
the Pinochle precedent for melding.

```
game Bridge {

  // Rubber Bridge, simplified: honors and insult bonuses omitted.
  // Goal: be the first side to win a rubber (two games).
  // A "game" is won when a side accumulates 100+ below-the-line points
  // across one or more hands.

  players: 4
  partnerships: [[N, S], [E, W]]
  direction: clockwise

  cards: standard52
  ranking: 2 3 4 5 6 7 8 9 10 J Q K A
  suit_order_for_bidding: [C, D, H, S, NT]   // C lowest, NT highest

  zones {
    deck                    : Deck
    private_hand[player]    : Hand<player>
    dummy_hand[player]      : PublicHand<player>            // ownership without privacy; populated mid-hand
    trick_pile              : TrickPile
    captured[partnership]   : TeamPile<partnership>
  }

  // === Top-level phase sequence ===

  phase rubber repeats until any partnership.games_won >= 2 {
    state {
      // Per-rubber: persist across hands within a rubber.
      games_won[partnership]              : Integer = 0
      above_line[partnership]             : Integer = 0
      below_line_current_game[partnership]: Integer = 0   // resets when a game is won
    }

    phase hand_sequence {
      state {
        // Per-hand: reset each hand.
        contract                  : Contract? = none
        declarer                  : Player?   = none
        dummy                     : Player?   = none
        tricks_taken[partnership] : Integer   = 0
        dummy_revealed            : Boolean   = false
      }

      phase setup {
        shuffle deck
        deal 13 cards from deck to each private_hand
        dealer := dealer.left                 // rotate per hand
      }

      phase bidding → outcome {
        contract_made(Contract, Player) | all_pass
      } {
        // Hand-waved as a mechanic; details (doubles, redoubles, conventions)
        // are explicitly out of scope. Resolves to one of:
        //   contract_made(c, d): a final contract c with declarer d
        //   all_pass: all four players passed without bidding
        //
        // Known gap: the standard Auction mechanic from Pinochle handles
        // ascending bids but does not yet model doubling/redoubling. Treat
        // BridgeAuction as a future-defined specialization.
        //
        // PLACEHOLDER: `final_state.*` dot-accesses below are invented
        // syntax against an undeclared type. They await the typed object
        // model (decisions.md). Treat them as a sketch of intent, not
        // real code.

        instantiate BridgeAuction (
          participants  = all players,
          opener        = dealer,
          outcome       = (final_state) ⇒ {
            if final_state.any_bid_made:                                      // PLACEHOLDER
              contract_made(final_state.final_contract,                       // PLACEHOLDER
                            final_state.first_to_bid_strain_in_winning_partnership)  // PLACEHOLDER
            else:
              all_pass
          }
        )
      }

      bidding produces:
        all_pass:
          skip to next hand                       // redeal, no scoring
        contract_made(c, d):
          contract := c
          declarer := d
          dummy    := d.partner
          continue to opening_lead

      phase opening_lead {
        state {
          // Per-opening_lead: a single trick. Leader is declarer's LHO.
          leader : Player = declarer.LHO
        }

        // One trick, played before dummy is revealed.
        active_rules: [MustFollowSuit]
        legal_moves:  [play_to_trick]

        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = play_source_for(actor),   // see dummy machinery below
          chooser_for  = chooser_for,              // identity-default; only matters after dummy is revealed
          play_zone    = trick_pile,
          play_rules   = active_rules,
          outcome      = TrumpedHighestOfLedSuit(trump = contract.suit),
          routing      = all cards from trick_pile to captured[partnership_of(outcome)]
        )

        tricks_taken[partnership_of(outcome)] += 1
      }

      phase reveal_dummy {
        // Structurally identical to a `setup` phase: state mutation only,
        // no active rules, no legal moves. Named as a phase because that's
        // how rulebooks describe it ("dummy reveals their hand").
        move all cards from private_hand[dummy] to dummy_hand[dummy]
        dummy_revealed := true
      }

      phase play {
        state {
          // Per-play: persists across all remaining tricks in this hand.
          leader : Player = outcome of last trick from opening_lead
        }

        active_rules: [MustFollowSuit]
        legal_moves:  [play_to_trick]

        repeat 12 times {
          instantiate Trick (
            participants = all players,
            leader       = leader,
            source_zone  = play_source_for(actor),
            chooser_for  = chooser_for,
            play_zone    = trick_pile,
            play_rules   = active_rules,
            outcome      = TrumpedHighestOfLedSuit(trump = contract.suit),
            routing      = all cards from trick_pile to captured[partnership_of(outcome)]
          )
          tricks_taken[partnership_of(outcome)] += 1
          leader := outcome
        }
      }

      phase scoring {
        // The contract was made if declarer's side took at least
        // (6 + contract.level) tricks.
        let declarer_side     = partnership_of(declarer)
        let defender_side     = other partnership
        let tricks_required   = 6 + contract.level
        let tricks_actual     = tricks_taken[declarer_side]
        let result            = HandResult(contract, declarer_side, defender_side,
                                           tricks_actual, tricks_required)

        // Composition of scoring components. Each component returns a
        // ScoreDelta (above-line and below-line contributions per partnership);
        // the phase sums them.
        apply_components: [
          ContractTrickScore,
          OvertrickScore,
          UndertrickPenalty,
          SlamBonus
        ]

        // GameBonus and the games_won/below-line reset are triggered
        // components — see decisions.md "Triggered scoring components".
      }
    }
  }

  phase rubber_complete {
    // RubberBonus is triggered on the rubber.games_won >= 2 threshold;
    // this phase exists as the boundary that the outer `rubber` loop
    // ends on. See decisions.md "Triggered scoring components".
  }

  winner: partnership with highest (above_line + below_line_current_game)
}

// === Types ===

type Contract = {
  level         : Integer in 1..7
  suit          : Suit | NT
  doubled_state : Doubled | Redoubled | Undoubled
}

type HandResult = {
  contract        : Contract
  declarer_side   : Partnership
  defender_side   : Partnership
  tricks_actual   : Integer
  tricks_required : Integer
}
derived {
  made = tricks_actual >= tricks_required
}

type ScoreDelta = {
  above_line[partnership] : Integer
  below_line[partnership] : Integer
}

// === Scoring components ===

// Each component is a function: HandResult → ScoreDelta.
// Components read per-rubber game state directly (e.g., via the free
// function `is_vulnerable(partnership)`, which reads games_won state).
// The scoring phase sums their deltas and applies the result.

scoring_component ContractTrickScore (result) {
  if not result.made: return zero
  let per_trick = per_trick_value(result.contract.suit, result.contract.doubled_state)
  let bonus_for_first_NT = if result.contract.suit == NT then 10 else 0
  let raw = per_trick * result.contract.level + bonus_for_first_NT
  let multiplier = double_multiplier(result.contract.doubled_state)
  ScoreDelta { below_line[result.declarer_side] += raw * multiplier }
}

scoring_component OvertrickScore (result) {
  if not result.made: return zero
  let overtricks = result.tricks_actual - result.tricks_required
  if overtricks == 0: return zero
  let per_overtrick = overtrick_value(
        result.contract.suit,
        result.contract.doubled_state,
        is_vulnerable(result.declarer_side))
  ScoreDelta { above_line[result.declarer_side] += per_overtrick * overtricks }
}

scoring_component UndertrickPenalty (result) {
  if result.made: return zero
  let undertricks = result.tricks_required - result.tricks_actual
  let penalty = undertrick_penalty_total(
        undertricks,
        result.contract.doubled_state,
        is_vulnerable(result.declarer_side))
  ScoreDelta { above_line[result.defender_side] += penalty }
}

scoring_component SlamBonus (result) {
  if not result.made: return zero
  let vuln = is_vulnerable(result.declarer_side)
  if result.contract.level == 6:
    ScoreDelta { above_line[result.declarer_side] += if vuln then 750 else 500 }
  elif result.contract.level == 7:
    ScoreDelta { above_line[result.declarer_side] += if vuln then 1500 else 1000 }
  else:
    return zero
}

scoring_component GameBonus {
  // Fires when either partnership's below-line score crosses 100.
  // Awards the game bonus, increments games_won, and resets the
  // below-line counter for BOTH partnerships.
  triggered_by: after apply_components
    where any partnership p has below_line_current_game[p] crosses 100
  let winner = the partnership that crossed
  let opp    = other partnership
  let bonus  = if games_won[opp] == 0 then 300 else 500
  ScoreDelta {
    above_line[winner]                  += bonus
    games_won[winner]                   += 1
    below_line_current_game[partnership] := 0 for each partnership
  }
}

scoring_component RubberBonus {
  // Fires when a partnership wins its second game.
  triggered_by: after apply_components
    where any partnership p has games_won[p] crosses 2
  let winner = partnership with games_won >= 2
  let loser  = other partnership
  let bonus  = if games_won[loser] == 0 then 700 else 500   // unbroken vs broken rubber
  ScoreDelta { above_line[winner] += bonus }
}

// === Dummy-play machinery ===

// Bridge separates the *actor* (the player on the move) from the
// *chooser* (the player making the choice) once dummy is revealed.
// Dummy is the actor of record for their cards; declarer picks them.
// See decisions.md "Delegated play".

play_source_for(actor) =
  if actor == declarer.partner and dummy_revealed:
    dummy_hand[actor]                     // dummy's cards play from the public zone
  else:
    private_hand[actor]

chooser_for(actor) =
  if actor == declarer.partner and dummy_revealed:
    declarer                              // declarer picks for dummy
  else:
    actor                                 // every other actor chooses for themselves

// === Helpers ===

per_trick_value(suit, doubled_state) =
  match suit:
    C, D       → 20
    H, S       → 30
    NT         → 30   // (first NT trick gets +10, handled in component)

double_multiplier(doubled_state) =
  match doubled_state:
    Undoubled  → 1
    Doubled    → 2
    Redoubled  → 4

overtrick_value(suit, doubled_state, vulnerable) =
  match doubled_state:
    Undoubled  → per_trick_value(suit, Undoubled)
    Doubled    → if vulnerable then 200 else 100
    Redoubled  → if vulnerable then 400 else 200

undertrick_penalty_total(n, doubled_state, vulnerable) =
  // Escalating per-undertrick penalty; standard rubber bridge table.
  ...   // table lookup, omitted for brevity

is_vulnerable(partnership) =
  games_won[partnership] >= 1     // reads per-rubber game state directly
```
