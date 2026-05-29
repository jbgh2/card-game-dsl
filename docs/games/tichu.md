# Tichu

Partnership climbing game (Schmid, 1991). 4 players in fixed
partnerships, 56-card deck (standard 52 plus four special cards:
Mahjong, Dog, Phoenix, Dragon). Rules source: Fata Morgana English
edition.

Tichu is the corpus's first climbing-game and its first game with
non-suit/rank cards. Several constructs below are new — they're flagged
inline by linking the open-question file that names them.

```
game Tichu {

  players: 4
  partnerships: [[N, S], [E, W]]
  direction: counterclockwise

  // 52 standard cards plus four uniquely-named special cards.
  cards: {
    suits: [S, H, D, C]
    ranks: [2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A]
    specials: [Mahjong, Dog, Phoenix, Dragon]
    // `specials:` is new — see open-questions/special-cards-declaration.md.
  }

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[team]   : TeamPile<team>
    discard          : Discard           // Dog goes here when played (no capture)
  }

  state {
    // Game-level: persists across hands.
    score[team] : Integer = 0
  }

  // === Top-level phase sequence ===

  phase hand_sequence repeats until any team.score >= 1000 {
    state {
      // Per-hand: resets each hand.
      tichu_called[player]        : Boolean = false
      grand_tichu_called[player]  : Boolean = false
      first_out                   : Player? = none
      second_out                  : Player? = none
      active_wish                 : Rank?   = none
    }

    // ----- Staged deal: 8 cards, Grand Tichu window, then 6 more -----

    phase deal_first_eight {
      shuffle deck
      deal 8 cards from deck to each hand
    }

    phase grand_tichu_window {
      legal_moves: [+ call_grand_tichu]
      // `+ X` operator on legal_moves — see decisions.md
      // ("Sub-phase rule and legal-move deltas").

      each player simultaneously may submit call_grand_tichu
      // "may submit" is a new optional-move form — see
      // open-questions/optional-window-moves.md.
    }

    phase deal_remaining_six {
      deal 6 cards from deck to each hand
    }

    // ----- Pushing: one card to each other player, simultaneously -----

    phase pushing {
      active_rules: [PushExactlyOneCardToEachOther]
      legal_moves:  [push_card]

      each player simultaneously:
        for each other player q:
          choose 1 card from hand[player]
          transfer chosen card from hand[player] to hand[q]
    }

    // ----- Play -----

    phase play {
      state {
        leader : Player = player_holding(Mahjong)
      }

      active_rules: [
        MustMatchLedCombinationType,
        MustBeatPreviousCombination,
      ]
      legal_moves: [play_combination, pass]
      out_of_turn_legal: bombs   // see open-questions/out-of-turn-moves.md

      // Sub-phase: the Mahjong wish is active. Entry and exit are
      // governed by the predicate; the sub-phase is active for as long
      // as `active_wish` is set. See decisions.md "Sub-phase entry
      // and exit".
      phase wish_active when active_wish != none {
        active_rules: [+ MustPlayWishedRankIfAble]
      }

      // Sub-phase: Tichu calls still allowed for a player who has not yet
      // played. Per-player closing — see
      // open-questions/per-player-sub-phases.md.
      phase tichu_window per_player {
        legal_moves: [+ call_tichu]
        transition_to: closed when this player plays their first
                       combination
      }

      // Trick loop.
      repeat until exactly one player still holds cards {
        instantiate ClimbingTrick (
          participants      = all players still holding cards,
          leader            = leader,
          source_zone       = hand,
          play_zone         = trick_pile,
          play_rules        = active_rules,
          outcome           = ClimbingTrickWinner,
          routing           = TichuTrickRouting,
          early_termination = (state) ⇒ state.last_play.is_dog
        )

        // Determine next leader. The Dog gives lead to partner; otherwise
        // the trick winner leads (skipping past empty hands).
        if last trick ended by Dog:
          leader := outcome.partner
        else:
          leader := outcome
        if hand[leader] is empty:
          leader := next non-empty player counterclockwise from leader

        // Record finishing order.
        for each player p who emptied their hand on this trick:
          if first_out == none:        first_out := p
          else if second_out == none:  second_out := p
      }
    }

    // ----- Scoring -----

    phase scoring {
      let last_player   = the one player still holding cards
      let winning_team  = team_of(first_out)
      let losing_team   = other team

      apply_components: [
        if first_out and second_out and team_of(second_out) == winning_team:
          DoubleVictoryScoring(winner = winning_team)
        else:
          CardPointScoring(last_player = last_player, winner = winning_team),
        TichuCallScoring()
      ]
    }
  }

  winner: team with highest score
  // In the tied-at-1000 case, whichever team has more points wins.
}

// =====================================================================
// Move types
// =====================================================================

// play_combination supersedes play_to_trick. Plays a set of cards
// forming a single Combination value (single cards are length-1
// combinations).
move_type play_combination {
  source: hand[active_player]
  destination: trick_pile
  carries: combination : Combination
  out_of_turn_legal: when combination.is_bomb
}

move_type pass {
  // Three successive passes end the trick.
}

move_type push_card {
  source: hand[active_player]
  destination: hand[recipient]   // recipient bound at choice time
}

// Tichu calls — declared rather than played.
move_type call_tichu        { sets: tichu_called[active_player] := true }
move_type call_grand_tichu  { sets: grand_tichu_called[active_player] := true }

// =====================================================================
// Types
// =====================================================================

type Combination = oneof {
  Single(rank: ExtendedRank)
  Pair(rank: Rank)
  Triple(rank: Rank)
  ConsecutivePairs(start: Rank, length: Integer)      // length ≥ 2 pairs
  FullHouse(triple_rank: Rank, pair_rank: Rank)
  Straight(start: Rank, length: Integer)              // length ≥ 5
  Bomb4(rank: Rank)                                   // four of a kind
  BombStraightFlush(suit: Suit, start: Rank, length: Integer)   // length ≥ 5
  DogLead                                             // Dog played alone
}
derived {
  Combination.is_bomb = self matches Bomb4 | BombStraightFlush
  Combination.is_dog  = self matches DogLead
}

// ExtendedRank covers ranks 2..A plus the special positions.
// Phoenix's single-card rank is contextual (half a rank above the last
// play); see open-questions/special-cards-declaration.md.
type ExtendedRank =
  | Rank
  | MahjongRank                        // = 1, lowest
  | DragonRank                         // = highest single
  | PhoenixRank(base_rank: Rank?)      // = base + 0.5; 1.5 if led

// =====================================================================
// Rules
// =====================================================================

rule MustMatchLedCombinationType {
  constrains: play_combination
  applies_when: state.trick.lead_combination != none
                and not move.combination.is_bomb
  demands: combinations c where c.type == state.trick.lead_combination.type
                              and c.length == state.trick.lead_combination.length
}

rule MustBeatPreviousCombination {
  constrains: play_combination
  applies_when: state.trick.last_play != none
                and not move.combination.is_bomb
  demands: combinations c where c.rank > state.trick.last_play.rank
}

rule MustPlayWishedRankIfAble {
  constrains: play_combination
  applies_when: state.active_wish != none
                and hand[active_player] contains a card of rank state.active_wish
                and some legal combination from hand[active_player]
                       contains a card of rank state.active_wish
  demands: combinations c that include at least one card of rank state.active_wish
  if_impossible: no constraint   // wish unfulfillable this turn ⇒ ordinary rules apply
}

rule PushExactlyOneCardToEachOther {
  constrains: push_card
  demands: each player chooses 3 distinct cards, one for each non-self player
}

// =====================================================================
// Climbing-game outcome and routing
// =====================================================================

outcome ClimbingTrickWinner = (played_cards, trick_state) ⇒
  trick_state.last_non_pass_player

routing TichuTrickRouting = (played_cards, trick_state, winner) ⇒
  if trick_state.last_play.is_dog:
    all cards from trick_pile to discard
  elif winner played Dragon as the winning single:
    all cards from trick_pile to captured[team of (winner chooses one opponent)]
    // see open-questions/choice-embedded-routing.md
  else:
    all cards from trick_pile to captured[team_of(winner)]

// =====================================================================
// Scoring components
// =====================================================================

scoring_component DoubleVictoryScoring (winner) {
  // Going out 1st and 2nd as the same partnership skips card counting.
  ScoreDelta { score[winner] += 200 }
}

scoring_component CardPointScoring (last_player, winner) {
  let losing_team = team_of(last_player)

  // Last player's remaining hand → opposing team's captured pile.
  // Last player's already-captured tricks → first_out's captured pile.
  move all cards from hand[last_player]      to captured[other team than losing_team]
  move all cards from captured[losing_team]  to captured[winner]

  let delta[team] = 0 for each team
  for each team t:
    delta[t] += sum over captured[t]:
                  if card == Dragon:         25
                  elif card == Phoenix:     -25
                  elif card.rank in [K, 10]: 10
                  elif card.rank == 5:        5
                  else:                       0
  ScoreDelta { score[t] += delta[t] for each team t }
}

scoring_component TichuCallScoring () {
  // ±100 / ±200 per player based on whether they went out first.
  let delta[team] = 0 for each team
  for each player p:
    let bonus =
      if grand_tichu_called[p]: 200
      elif tichu_called[p]:     100
      else: 0
    if p == first_out: delta[team_of(p)] += bonus
    else:              delta[team_of(p)] -= bonus
  ScoreDelta { score[t] += delta[t] for each team t }
}
```
