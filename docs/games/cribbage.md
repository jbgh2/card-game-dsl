# Cribbage

The companion formal file is [cribbage.cardlang](cribbage.cardlang); this is the
readable twin. Two-player six-card Cribbage — the corpus's first **counting**
game (no tricks). First to 121 points, scored from two streams: *pegging* during
play, and the *show* afterwards. Source:
[Pagat](https://www.pagat.com/adders/crib6.html).

Each hand:

1. Deal six cards each; both players discard two to the dealer's **crib**.
2. Cut a **starter** card (the dealer scores 2 for *his heels* if it is a Jack).
3. **Pegging** — players alternate laying cards, calling the running total, which
   may not exceed 31. Score 2 for reaching fifteen or thirty-one, pairs (2/6/12
   for two/three/four of a kind in a row), runs (the run length for a run of 3+
   in the recent cards), and 1 for the last card of a round (a *go*).
4. **The show** — each player picks their four cards back up and counts, with the
   starter as a fifth card: fifteens (2 each), pairs (2 each), runs (length ×
   multiplicity), a flush (4, or 5 with the starter; the crib needs all five),
   and *his nob* (1 for the Jack of the starter's suit). The non-dealer counts
   first, then the dealer's hand, then the crib — and the count stops the instant
   a player reaches 121, so the first to 121 wins outright.

The whole hand — discard, cut, pegging, and the show — runs in the DSL. Both
players' discards and every pegging play are filtered card movements (`move
chosen … where …`); ordinary statement control flow (`repeat until`, `if`/`else`,
`skip to next hand`) reproduces the 121-point cutoff one scoring component at a
time. Pegging needs no `round` form of its own — no existing round fits its
per-play scoring plus forced-play flow — so the current sub-round's card
provenance (who played each `play_pile` card) is carried by two `Integer` state
variables (`seq_bits`/`seq_len`, public information: every player watched the
count) and decoded by the `peg_origin_of` stdlib primitive at each close, which
routes the pile into `played[dealer]` / `played[nondealer]`. The combination
scorers (fifteens, pairs, runs, flush, his nob) and the pegging-count scorers are
stdlib primitives, unit-tested against known hands (the 29-hand, runs with
multiplicity, flushes, his nob).

```
game Cribbage {

  players: 2
  direction: clockwise   // irrelevant with two players; kept for uniformity
  max_length: 1500

  cards: standard52
  ranking: A 2 3 4 5 6 7 8 9 10 J Q K   // A low; J/Q/K worth 10 for pegging

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    crib           : FaceDownPile          // the dealer's crib, hidden from BOTH players until the show
    starter        : Discard               // one face-up card, shared
    play_pile      : TrickPile             // the current pegging sub-round
    played[player] : PlayerPile<player>    // pegged cards, by whoever played them
  }

  state {
    // Game-level: persists across hands.
    score[player] : Integer = 0
  }

  phase hand_sequence repeat until (any player where score[player] >= 121) {
    state {
      dealer : Player = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 6 cards from deck to each hand
      dealer := the player where player is not dealer   // the deal alternates
    }

    phase play {
      state {
        total       : Integer = 0   // the running count of the current sub-round
        gos         : Integer = 0   // consecutive players unable to play
        seq_bits    : Integer = 0   // play-order of the count: 1-bit per play, MSB first, 1 = dealer
        seq_len     : Integer = 0   // plays in the current sub-round (= size of play_pile)
        last_played : Player  = 0   // only read after a play has set it
        active      : Player  = 0
      }

      // Both players discard two to the dealer's crib, in seat order.
      for each player p: move chosen 2 cards from hand[p] to crib

      // Cut the starter (top of the shuffled deck). His heels: a Jack scores the dealer 2.
      move one card from deck to starter
      if any card in starter where card.rank is J {
        score[dealer] += 2
      }
      if game_over() { skip to next hand }

      // Pegging: the non-dealer leads; forced play while able; a go is silent (no decision).
      active := the player where player is not dealer
      repeat until (all players where hand[player] is empty) {
        as active {
          if hand[active] is empty {
            active := the player where player is not active
          } else {
            if any card in hand[active] where total + peg_value(card) <= 31 {
              move chosen one card from hand[active] where total + peg_value(card) <= 31 to play_pile
              seq_bits := seq_bits * 2 + (if active is dealer then 1 else 0)
              seq_len := seq_len + 1
              total := sum of peg_value(card) over cards in play_pile
              last_played := active
              gos := 0
              if total is 15 or total is 31 { score[active] += 2 }
              if game_over() { skip to next hand }
              score[active] += peg_pair_points()
              if game_over() { skip to next hand }
              score[active] += peg_run_points()
              if game_over() { skip to next hand }
              if total is 31 {
                move all cards from play_pile where peg_origin_of(card) is dealer to played[dealer]
                move all cards from play_pile to played[the player where player is not dealer]
                total := 0
                seq_bits := 0
                seq_len := 0
              }
              active := the player where player is not active
            } else {
              gos := gos + 1
              if gos >= 2 {
                score[last_played] += 1          // the go point for the sub-round's last card
                move all cards from play_pile where peg_origin_of(card) is dealer to played[dealer]
                move all cards from play_pile to played[the player where player is not dealer]
                total := 0
                seq_bits := 0
                seq_len := 0
                gos := 0
                if game_over() { skip to next hand }
                active := the player where player is not last_played
              } else {
                active := the player where player is not active
              }
            }
          }
        }
      }
      // Final open sub-round: last card scores 1 (a 31 always closed inside the
      // loop, clearing the pile, so this close is never the scored-31 case).
      if play_pile is not empty {
        score[last_played] += 1
        move all cards from play_pile where peg_origin_of(card) is dealer to played[dealer]
        move all cards from play_pile to played[the player where player is not dealer]
        if game_over() { skip to next hand }
      }

      // The show: non-dealer's hand, dealer's hand, then the crib (to the
      // dealer), stopping the instant a player crosses 121.
      let nondealer = the player where player is not dealer
      score[nondealer] += cribbage_show_value(nondealer)
      if game_over() { skip to next hand }
      score[dealer] += cribbage_show_value(dealer)
      if game_over() { skip to next hand }
      score[dealer] += cribbage_crib_value()
    }
  }

  winner: highest score
}

// True the instant either player has reached the 121-point target — read at
// every scoring point inside `phase play` (mirroring the monolith's `add()`
// gate: once a component crosses 121, no later component in the same hand may
// score, and no further chooser draw may occur).
function game_over() = any player where score[player] >= 121
```
