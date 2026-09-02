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
somebody must miss. Bidding starts left of the dealer and goes round, so the
dealer bids last with every other bid already heard, and that is what makes the
constraint land on them: the rulebook forbids the dealer, at the moment they
choose, the one number that would make the bids total the hand size. The
dealer's bid says exactly that — `excluding hand_size - total_bid` removes the
forbidden number from the dealer's range as the bid is chosen — so the bid
every player hears is the bid the game scores. When the other three have
already bid past the hand size, no number is forbidden and the dealer bids
freely, as at the table.

```
game OhHell {

  players: 4
  direction: clockwise
  max_length: 3000

  cards: standard52
  ranking: aces high

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

  phase hand_sequence repeat until hand_index >= 19 {
    state {
      hand_index         : Integer = 0      // 0..18 across the 19 hands
      hand_size          : Integer = 0      // tricks this hand
      dealer             : Player  = 0
      leader             : Player? = none
      bid[player]        : Integer = 0
      tricks_won[player] : Integer = 0
      trump_suit         : Suit?   = none
      total_bid          : Integer = 0
      has_bid[player]    : Boolean = false
    }

    before_each {
      move all cards to deck
      shuffle deck
      // Hand size: 10, 9, ..., 1, 2, ..., 10.
      hand_size := if hand_index <= 9 then 10 - hand_index else hand_index - 8
      deal hand_size cards from deck to each hand
      deal 1 card from deck to trump_indicator    // turn up the trump card
      trump_suit := suit_of(trump_indicator)
      dealer := dealer offset_by left
      leader := dealer offset_by left             // eldest hand leads
      for each player p: bid[p] := 0
      for each player p: has_bid[p] := false
      total_bid := 0
      for each player p: tricks_won[p] := 0
    }

    phase bidding {
      legal_moves: [submit_bid]
      // Bidding starts left of the dealer and goes round, so the dealer bids
      // last with every other bid heard. Bid up to the tricks in hand:
      // `hand_size` varies per hand, so the range's upper bound is runtime
      // state; `up to 10` declares the static ceiling (the largest hand) the
      // OpenSpiel action space reserves for the bid.
      turns t from dealer offset_by left over players where not has_bid[player]
            until (number of players where not has_bid[player]) is 0 {
        if t is dealer {
          // The hook: the dealer may not bid the number that would make the
          // bids total the hand size. When the others have already bid past
          // it, no number is forbidden and the exclusion is a no-op.
          bid[t] := choose integer in 0 .. hand_size up to 10
                    excluding hand_size - total_bid
        } else {
          bid[t] := choose integer in 0 .. hand_size up to 10
        }
        total_bid += bid[t]
        has_bid[t] := true
      }
    }

    phase play {
      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      repeat until (all players where hand[player] is empty) {
        round play_to_trick from leader over all players source hand into trick_pile
              winner highest_trump_or_led_suit trump trump_suit
        move all cards from trick_pile to captured[winner]
        tricks_won[winner] += 1
        leader := winner
      }
    }

    phase scoring {
      // +1 per trick taken, +10 for hitting the bid exactly (never negative).
      for each player p:
        if tricks_won[p] is bid[p] { score[p] += tricks_won[p] + 10 }
        else { score[p] += tricks_won[p] }
    }

    after_each {
      hand_index += 1
    }
  }

  winner: highest score
}

// MustFollowSuit is a standard-library rule (library.md "Rules"): activated
// by name above, defined once in cardlang/stdlib/rules.cardlang.
```
