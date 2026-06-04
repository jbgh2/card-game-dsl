# Seven-Card Stud

Fixed-limit Seven-Card Stud. Cash game, fixed-limit ($5/$10 — lower
limit on third/fourth street, upper limit on fifth/sixth/seventh).
Out of scope: tournament structure, blinds-as-alternative-to-antes,
multi-hand chip accounting (stacks persist; rebuys happen between
hands; we don't model the rebuy explicitly), string bets, misdeals,
Hi-Lo split.

```
game SevenCardStud {

  players: 2..8
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2     // for showdown only; betting doesn't use rank

  resources {
    chip : Resource                          // poker chip (single denomination for simplicity)
  }

  zones {
    deck                   : Deck
    hole[player]           : Hand<player>                // face-down cards, owner sees identity
    upcards[player]        : PublicHand<player>          // face-up cards in front of player
    muck                   : Muck                        // folded cards (no longer in play; prior observations persist)
    burn                   : Burn                        // dealer burns one card per street
    stack[player]          : ChipStack<player>           // each player's chip stack; count public per stdlib
  }

  state {
    // Game-level: persist across hands.
    ante_amount      : Integer = 1                  // small ante per player
    lower_limit      : Integer = 5
    upper_limit      : Integer = 10
    bring_in_amount  : Integer = 2
  }

  phase hand repeats while at least 2 players want to play {
    state {
      // Per-hand: reset each hand.
      pots                       : List<Pot>    = [new Pot { contents: empty chip zone, eligible: all_players }]
      folded[player]             : Boolean      = false
      all_in[player]             : Boolean      = false
      committed_this_hand[player]: Integer      = 0   // bookkeeping for reconcile_pots; derivable from observation history
    }

    phase setup {
      shuffle deck
      dealer := dealer.left                            // rotate per hand

      // Antes
      for each player p:
        transfer ante_amount chips from stack[p] to pots[0].contents
        committed_this_hand[p] += ante_amount

      // Deal: two hole cards, then one door card, to each player.
      for each player p:
        deal 1 card from deck to hole[p]                 // visibility from zone: identity to p, count_only to others
        deal 1 card from deck to hole[p]
      for each player p:
        deal 1 card from deck to upcards[p]              // visibility from zone: identity to all
    }

    phase bring_in {
      // The player showing the lowest door card must post the bring-in.
      // Ties broken by suit (clubs < diamonds < hearts < spades, lowest acts).
      active_rules: [BringInMandatory]
      legal_moves:  [bring_in]

      let bringer = player with lowest door card (ties: lowest suit)
      offer action to bringer:
        bring_in:
          let amount = bring_in_amount
          transfer amount chips from stack[bringer] to pots[0].contents
          committed_this_hand[bringer] += amount

      // Action continues to bringer.left in betting_third.
    }

    phase betting_third {
      instantiate BettingRound (
        active_players  = players where not folded and not all_in,
        first_to_act    = bring_in player's left,
        opening_bet     = bring_in_amount,   // bring-in stands as the opening bet
        limit           = lower_limit,
        max_raises      = 3
      )
      reconcile_pots                          // creates side pots if anyone went all-in
    }

    phase deal_fourth_street {
      burn one card from deck to burn
      for each player p where not folded:
        deal 1 card from deck to upcards[p], visibility = public
    }

    phase betting_fourth {
      // Highest visible hand acts first. From fourth street onward,
      // the limit doubles if any player is showing an open pair.
      let limit = if any active player has open pair: upper_limit else lower_limit
      instantiate BettingRound (
        active_players  = players where not folded and not all_in,
        first_to_act    = player with highest visible poker hand from upcards,
        opening_bet     = 0,                  // round starts with no bet
        limit           = limit,
        max_raises      = 3
      )
      reconcile_pots
    }

    phase deal_fifth_street {
      burn one card from deck to burn
      for each player p where not folded:
        deal 1 card from deck to upcards[p], visibility = public
    }

    phase betting_fifth {
      instantiate BettingRound (
        active_players  = players where not folded and not all_in,
        first_to_act    = player with highest visible poker hand from upcards,
        opening_bet     = 0,
        limit           = upper_limit,        // upper limit from fifth street on
        max_raises      = 3
      )
      reconcile_pots
    }

    phase deal_sixth_street {
      burn one card from deck to burn
      for each player p where not folded:
        deal 1 card from deck to upcards[p], visibility = public
    }

    phase betting_sixth {
      instantiate BettingRound (
        active_players  = players where not folded and not all_in,
        first_to_act    = player with highest visible poker hand from upcards,
        opening_bet     = 0,
        limit           = upper_limit,
        max_raises      = 3
      )
      reconcile_pots
    }

    phase deal_seventh_street {
      burn one card from deck to burn
      // Seventh street is dealt face-down (private).
      for each player p where not folded:
        deal 1 card from deck to hole[p], visibility = private to p
    }

    phase betting_seventh {
      instantiate BettingRound (
        active_players  = players where not folded and not all_in,
        first_to_act    = player with highest visible poker hand from upcards,
        opening_bet     = 0,
        limit           = upper_limit,
        max_raises      = 3
      )
      reconcile_pots
    }

    phase showdown {
      // Reveal hole cards for non-folded players, in order of last
      // aggressive action (the player who made the final bet/raise
      // shows first; if everyone checked the last round, the player
      // closest to the dealer's left shows first).
      let show_order = ordered list of non-folded players by reveal-priority
      for each player p in show_order:
        reveal(all cards in hole[p], observers = all)

      // Evaluate and award each pot, in order (main pot first).
      for each pot in pots:
        let eligible = pot.eligible where not folded
        let best_hand_by_player[p] = best_five_card_hand(hole[p] ∪ upcards[p]) for p in eligible
        let winners = players in eligible with the max best_hand_by_player
        let total = pot.contents.count
        let share = total / |winners|
        for each w in winners:
          transfer share chips from pot.contents to stack[w]
        // Odd chips on a split pot go to the player closest to dealer's left
        // among the winners (standard poker convention).
        if total mod |winners| != 0:
          let odd_chips = total mod |winners|
          transfer odd_chips chips from pot.contents to stack[first winner clockwise from dealer.left]

      // Cards leave play; observers' memory persists.
      for each player p:
        muck all cards in hole[p]
        muck all cards in upcards[p]
    }
  }

  winner: per-hand only (no overall game winner; this is a cash game).
}

// === Types ===

type Pot = {
  contents : Zone<Resource<chip>> { composition: count_only to all }
  eligible : Set<Player>                                            // who can win this pot
}

type HandRank = {
  category   : HandCategory             // see below; totally ordered
  tiebreakers: List<Rank>               // descending; for comparing within a category
}
derived {
  // HandRank instances compare first by category, then lexicographically
  // by tiebreakers. Standard poker comparison.
}

type HandCategory =
    HighCard
  | OnePair
  | TwoPair
  | ThreeOfAKind
  | Straight
  | Flush
  | FullHouse
  | FourOfAKind
  | StraightFlush
// Totally ordered: HighCard < OnePair < ... < StraightFlush.

// === Mechanics ===

mechanic BettingRound (
  active_players  : List<Player>
  first_to_act    : Player
  opening_bet     : Integer
  limit           : Integer            // size of one bet or raise increment
  max_raises      : Integer
) {
  state {
    // Per-betting-round: lives for one BettingRound instance.
    bet_to_match      : Integer = opening_bet
    last_aggressor    : Player? = none
    has_acted[player] : Boolean = false
    raises_so_far     : Integer = 0
    bet_by[player]    : Integer = 0     // how much each player has put in THIS round
  }

  active_rules: [CheckLegalIfNothingToCall,
                 CallLegalIfBetToMatch,
                 BetLegalIfNoBetToMatch,
                 RaiseLegalIfBetExistsAndRaiseCapNotHit]
  legal_moves: [check, call, bet, raise, fold]

  // If only one active player remains, the round ends immediately.
  if |active_players| <= 1: return

  let actor = first_to_act
  repeat until betting_complete {

    if folded[actor] or all_in[actor]:
      actor := next_active_player(actor)
      continue

    offer action to actor:
      check:
        has_acted[actor] := true
      call:
        let amount = min(bet_to_match - bet_by[actor], stack[actor].count)
        transfer amount chips from stack[actor] to pots[0].contents
        bet_by[actor]              += amount
        committed_this_hand[actor] += amount
        if stack[actor].empty: all_in[actor] := true
        has_acted[actor] := true
      bet:
        let amount = min(limit, stack[actor].count)
        transfer amount chips from stack[actor] to pots[0].contents
        bet_by[actor]              += amount
        committed_this_hand[actor] += amount
        bet_to_match               := amount
        last_aggressor             := actor
        raises_so_far              := 1          // opening bet counts as first "raise" cap
        for each p in active_players: has_acted[p] := (p == actor)
        if stack[actor].empty: all_in[actor] := true
      raise:
        let amount = (bet_to_match - bet_by[actor]) + limit
        let actual = min(amount, stack[actor].count)
        transfer actual chips from stack[actor] to pots[0].contents
        bet_by[actor]              += actual
        committed_this_hand[actor] += actual
        bet_to_match               := bet_by[actor]
        last_aggressor             := actor
        raises_so_far              += 1
        for each p in active_players: has_acted[p] := (p == actor)
        if stack[actor].empty: all_in[actor] := true
      fold:
        folded[actor] := true
        muck all cards in upcards[actor]              // cards leave play; observers' memory persists
        // hole cards stay in hole[actor]; they'll be mucked in showdown.

    actor := next_active_player(actor)

    let betting_complete =
      |non-folded, non-all-in players who have not yet had has_acted = true| == 0
      and all non-folded, non-all-in players have bet_by[p] == bet_to_match
  }
}

// reconcile_pots is invoked after each BettingRound. It restructures
// the pot zones so all-in players are eligible only for the portion
// of the pot they could match.
//
// Algorithm: walk committed_this_hand[p] in ascending order. Each
// distinct commitment level creates a pot boundary. For each pot
// layer:
//   - eligible = { p | committed_this_hand[p] >= threshold and not folded[p] }
//   - amount   = (threshold - previous_threshold) × |contributors at this layer|
//                where contributors includes folded players who committed
//                at least up to this layer (their chips stay in the pot
//                they were committed to when they folded)
//
// The chip movement on restructuring: chip resources are redistributed
// among the pot zones so that each Pot's contents equals its computed
// amount. This is a zero-sum reshuffling of chips between pot zones;
// total chips across all pots is invariant.
//
// Correctness subtlety: folded players' contributions land in the
// *current* pot at the time of the fold. A player who folded before
// any all-in event contributes to the main pot; a player who folded
// after a side-pot boundary was established contributes to whichever
// layer was current when they folded. The algorithm above handles
// this correctly if `committed_this_hand` is tracked over time
// alongside fold events. This is a real algorithmic requirement of
// the reconcile_pots operation; the sketch above documents the
// structural form rather than the full implementation.
operation reconcile_pots {
  // (See above. The full implementation is standard poker side-pot
  // accounting; the sketch is the structural form.)
}

// === Rules ===

rule BringInMandatory {
  constrains: bring_in
  demands: actions where action.amount == bring_in_amount
  if_impossible: error("bring-in player must post the bring-in")
}

// BettingRound legality rules. Each reads BettingRound's
// mechanic-internal state via standard lexical scoping — these rules
// are only attached as `active_rules` inside BettingRound, so
// `state.bet_to_match`, `state.bet_by`, and `state.raises_so_far`
// resolve to the active instance's per-round state. See decisions.md
// "State scoping (lexical)".

rule CheckLegalIfNothingToCall {
  constrains: check
  applies_when: state.bet_to_match - state.bet_by[active_player] == 0
}

rule CallLegalIfBetToMatch {
  constrains: call
  applies_when: state.bet_to_match - state.bet_by[active_player] > 0
}

rule BetLegalIfNoBetToMatch {
  constrains: bet
  applies_when: state.bet_to_match == 0
}

rule RaiseLegalIfBetExistsAndRaiseCapNotHit {
  constrains: raise
  applies_when: state.bet_to_match > 0 and state.raises_so_far < max_raises
}

// `fold` has no applies_when — always legal for a non-folded,
// non-all-in active player. The mechanic body's `if folded[actor]
// or all_in[actor]: continue` keeps it from being offered when
// inapplicable.

// === Stdlib functions used ===

// best_five_card_hand(cards: Set<Card>) → HandRank
//   Standard poker hand evaluator. Given 7 cards, returns the best
//   5-card poker hand as a HandRank value. Stdlib because every poker
//   variant needs it. The implementation is standard and not
//   game-specific. Assumed; not defined here.

// next_active_player(p) → Player
//   Returns the next player clockwise from p who is not folded and
//   not all_in. Used by BettingRound's main loop.
```
