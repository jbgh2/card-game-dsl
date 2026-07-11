# Oh Hell

The companion formal file is [oh-hell.cardlang](oh-hell.cardlang); this is the
readable twin. Four-player Oh Hell (also Blackout, Up and Down the River,
Contract Whist). Each hand turns up a card to fix trump, every player bids the
*exact* number of tricks they expect, and the hand scores +1 per trick won plus
a +10 bonus for hitting the bid exactly (missing — over or under — costs only
the bonus, never goes negative). The hand-size sequence runs 10 down to 1, then
back up to 10 (sizes 2–10): 19 hands, after which the highest score wins. Source:
[Pagat](https://www.pagat.com/exact/ohhell.html).

Tricks are played via the kernel `round` construct. The trump suit changes every
hand, so it is passed as a `trump` argument (the per-hand `trump_suit` state
var) rather than the fixed game-level `trump:` declaration that Spades uses.

**The hook rule** — the total of all bids may not equal the hand size, so
somebody must miss. The rulebook constrains the dealer (who bids last) at choice
time; this file enforces the same observable effect by correcting the dealer's
bid after bids are in, since the language has no sequential-bidding /
`choose … excluding …` construct yet and a uniform-random playout models no
bidding strategy regardless.

```
game OhHell {

  players: 4
  direction: clockwise
  max_length: 3000

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trump_indicator  : Discard              // the face-up card that fixes trump
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }

  state {
    // Game-level: persists across hands.
    score[player] : Integer = 0
  }

  phase hand_sequence repeats until hand_index >= 19 {
    state {
      hand_index         : Integer = 0      // 0..18 across the 19 hands
      hand_size          : Integer = 0      // tricks this hand
      dealer             : Player  = 0
      leader             : Player? = none
      bid[player]        : Integer = 0
      tricks_won[player] : Integer = 0
      trump_suit         : Suit?   = none
      total_bid          : Integer = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      // Hand size: 10, 9, ..., 1, 2, ..., 10.
      hand_size := if hand_index <= 9 then 10 - hand_index else hand_index - 8
      deal hand_size cards from deck to each hand
      deal 1 cards from deck to trump_indicator   // turn up the trump card
      trump_suit := suit_of(trump_indicator)
      dealer := dealer offset_by left
      leader := dealer offset_by left             // eldest hand leads
      for each player p: bid[p] := 0
      for each player p: tricks_won[p] := 0
    }

    phase bidding {
      legal_moves: [submit_bid]
      for each player p: bid[p] := choose integer in 0 .. hand_size up to 10

      // Dealer hook: the bids may not total the hand size.
      total_bid := 0
      for each player p: total_bid += bid[p]
      if total_bid == hand_size {
        if bid[dealer] < hand_size { bid[dealer] := bid[dealer] + 1 }
        else { bid[dealer] := bid[dealer] - 1 }
      }
    }

    phase play {
      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      repeat until (all player p: hand[p] is empty) {
        round play_to_trick from leader over all players source hand into trick_pile
              outcome highest_trump_or_led_suit trump trump_suit
        move all cards from trick_pile to captured[outcome]
        tricks_won[outcome] += 1
        leader := outcome
      }
    }

    phase scoring {
      // +1 per trick taken, +10 for hitting the bid exactly (never negative).
      for each player p:
        if tricks_won[p] == bid[p] { score[p] += tricks_won[p] + 10 }
        else { score[p] += tricks_won[p] }
    }

    after_each {
      hand_index += 1
    }
  }

  winner: highest score
}

rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
  if_impossible: hand   // void in the led suit: play any card
}
```
