# Oh Hell

Four-player Oh Hell (also Blackout, Up and Down the River, Contract
Whist). Each hand: bid exactly the number of tricks you'll take. Hit
your bid → 10-point bonus on top of 1 point per trick won. Miss your
bid (over OR under) → 1 point per trick won only. Sequence of hands
varies in size: 10 down to 1, then 1 back up to 10 (19 hands per
game). Source: [Pagat](https://www.pagat.com/exact/ohhell.html).

Oh Hell is the corpus's third bidding game. The bid value is an
*exact-tricks target per player*, distinct from Spades'
threshold-tricks and Pinochle's total-points. Like Spades, it uses
per-player inline bidding rather than the ascending `Auction`
mechanic (which fits Pinochle). See decisions.md "Bidding patterns".

The **hook rule** is the interesting wrinkle: the dealer (who bids
last) cannot bid such that the total of all bids equals the number
of tricks available. Somebody always has to miss. A rule that reads
the bids of *prior* players in real-time.

```
game OhHell {

  players: 4
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck              : Deck
    hand[player]      : Hand<player>
    trump_indicator   : Discard                  // face-up card determining trump
    trick_pile        : TrickPile
    captured[player]  : PlayerPile<player>       // tricks won (kept for observation history)
  }

  state {
    // Game-level: persists across hands.
    score[player] : Integer = 0
  }

  // === Top-level phase sequence ===

  phase hand_sequence repeats until hand_index >= 19 {
    state {
      // Per-game progression across the 19 hands.
      hand_index : Integer = 0
    }

    // Hand size sequence for 4 players: 10, 9, ..., 1, 2, ..., 10.
    let hand_size = if hand_index <= 9 then 10 - hand_index else hand_index - 8

    state {
      // Per-hand: resets each hand.
      bid[player]        : Integer? = none
      tricks_won[player] : Integer  = 0
      trump              : Suit?    = none
    }

    phase setup {
      shuffle deck
      deal hand_size cards from deck to each hand
      reveal top of deck to trump_indicator
      trump := suit of trump_indicator
      dealer := dealer.left                       // rotate per hand
    }

    phase bidding {
      active_rules: [BidIsInRange, DealerHookConstraint]
      legal_moves:  [submit_bid]

      each player in turn starting from dealer.left:
        action submit_bid:
          choose integer b from 0 to hand_size
          bid[active_player] := b
    }

    phase play {
      state {
        leader : Player = dealer.left
      }

      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      repeat hand_size times {
        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = hand,
          play_zone    = trick_pile,
          play_rules   = active_rules,
          outcome      = TrumpedHighestOfLedSuit(trump = trump),
          routing      = move all cards from trick_pile to captured[outcome]
        )
        tricks_won[outcome] += 1
        leader := outcome
      }
    }

    phase scoring {
      let result = OhHellHandResult(bid, tricks_won)
      apply_components: [TricksAndExactBonus]

      // Reset zones for the next hand.
      move all cards from captured[player] to deck for each player
      move all cards from hand[player]     to deck for each player
      move trump_indicator                 to deck
    }

    hand_index += 1
  }

  winner: player with highest score
}

// =====================================================================
// Types
// =====================================================================

type OhHellHandResult = {
  bid[player]        : Integer
  tricks_won[player] : Integer
}

// =====================================================================
// Scoring components
// =====================================================================

scoring_component TricksAndExactBonus (result) {
  // 1 point per trick won. +10 bonus if the bid was hit exactly.
  // Missing (over OR under) costs the bonus only — never goes negative.
  // This is Pagat's "most widespread" scoring method.
  let delta[player] = 0 for each player
  for each player p:
    delta[p] += result.tricks_won[p]
    if result.tricks_won[p] == result.bid[p]:
      delta[p] += 10
  ScoreDelta { score[p] += delta[p] for each player p }
}

// =====================================================================
// Rules
// =====================================================================

rule BidIsInRange {
  constrains: submit_bid
  demands: integers in 0..hand_size
}

rule DealerHookConstraint {
  // The dealer bids last. The total of all bids may not equal the
  // hand size, so somebody must miss. The dealer's bid is constrained
  // to avoid the value that would make the bids sum to hand_size.
  constrains: submit_bid
  applies_when: active_player == dealer
  demands:
    let prior_sum = sum of bid[p] for p in players where p != dealer
                                       and bid[p] != none
    let forbidden = hand_size - prior_sum
    integers in 0..hand_size, excluding forbidden if forbidden is in range
}
```
