# Spades

The companion formal file is [spades.cardlang](spades.cardlang); this is the
readable twin. Spades is a four-player partnership trick-taking game (partners
sit across) with spades always trump. Each player bids the number of tricks
they expect to take (a bid of zero is *nil*); the partnership's contract is the
sum of its non-nil bids. After thirteen tricks the hand is scored and the deal
rotates. The game runs until a team reaches +500 (a win) or −200 (a loss).

Scoring (the variant formalized here — Spades has several; this one is kept
internally consistent so each hand's score reconciles):

- **Contract.** Make the contract (team tricks ≥ contract): +10 per bid trick,
  plus one *bag* per overtrick. Miss it: −10 per bid trick, no bags.
- **Nil.** A nil bidder who takes no tricks scores +100; one who takes any
  scores −100. Nil is scored per player, independently of the contract.
- **Bag overflow.** Every 10 accumulated bags costs 100 points and drops the
  bag counter by 10.

This file folds scoring into the `scoring` phase (as Hearts does) rather than
using separate `scoring_component` blocks; the first-trick "no spades" ban from
some rulebooks is omitted because "no leading spades until broken" already
forbids leading a spade on the first trick.

```
game Spades {

  players: 4
  partnerships: [[0, 2], [1, 3]]   // partners sit across the four-hand ring
  direction: clockwise
  max_length: 2000

  cards: standard52
  ranking: aces high
  trump: spades

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
  }

  state {
    // Game-level: persist across hands.
    score[team] : Integer = 0
    bags[team]  : Integer = 0
  }

  phase hand_sequence repeat until (any team where score[team] >= 500 or score[team] <= 0 - 200) {
    state {
      // Per-hand, reset each hand by before_each.
      dealer             : Player  = 0
      leader             : Player? = none
      bid[player]        : Integer = 0
      tricks_won[player] : Integer = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 13 cards from deck to each hand
      dealer := dealer offset_by left          // rotate the deal each hand
      leader := dealer offset_by left          // eldest hand leads the first trick
      for each player p: bid[p] := 0
      for each player p: tricks_won[p] := 0
    }

    phase bidding {
      legal_moves: [submit_bid]
      // Each player names a number 0..13; 0 is a nil bid.
      for each player p: bid[p] := choose integer in 0 .. 13
    }

    phase play {
      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      phase spades_not_broken {
        active_rules: [+ NoLeadingSuitUntilBroken(spades)]
        transition_to: spades_broken when play_to_trick where action.card.suit is spades
      }

      phase spades_broken {
        // inherits the parent's MustFollowSuit only
      }

      repeat until (all players where hand[player] is empty) {
        round play_to_trick from leader over all players source hand into trick_pile
              winner highest_trump_or_led_suit
        move all cards from trick_pile to captured[team_of(winner)]
        tricks_won[winner] += 1
        leader := winner
      }
    }

    phase scoring {
      state {
        team_bid[team]    : Integer = 0
        team_tricks[team] : Integer = 0
      }

      for each player p: team_bid[team_of(p)] += (if bid[p] is 0 then 0 else bid[p])
      for each player p: team_tricks[team_of(p)] += tricks_won[p]

      for each team t:
        if team_tricks[t] >= team_bid[t] {
          score[t] += contract_score(t) + overtricks(t)
          bags[t]  += overtricks(t)
        } else {
          score[t] -= contract_score(t)
        }

      for each player p:
        if bid[p] is 0 {
          if tricks_won[p] is 0 { score[team_of(p)] += 100 }
          else { score[team_of(p)] -= 100 }
        }

      repeat until (all teams where bags[team] < 10) {
        for each team t:
          if bags[t] >= 10 { score[t] -= 100  bags[t] -= 10 }
      }
    }
  }

  winner: highest score
}

// MustFollowSuit and NoLeadingSuitUntilBroken(spades) are standard-library
// rules (library.md "Rules"): activated by name above, defined once in
// cardlang/stdlib/rules.cardlang.

// Per-team contract aggregates, named so the make and miss branches score the
// contract from one place: its value (10 per bid) and the overtricks beyond it.
function contract_score(t : Team) = 10 * team_bid[t]
function overtricks(t : Team)     = team_tricks[t] - team_bid[t]
```
