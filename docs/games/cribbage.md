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

The hand engine — discard, cut, pegging, and the show — runs in the built-in
`CribbageHand` mechanic, which updates `score` directly and stops at 121. The
combination scorers are unit-tested against known hands (the 29-hand, runs with
multiplicity, flushes, his nob). The cardlang holds the deal and termination.

```
game Cribbage {

  players: 2
  direction: clockwise   // irrelevant with two players; kept for uniformity

  cards: standard52
  ranking: A 2 3 4 5 6 7 8 9 10 J Q K   // A low; J/Q/K worth 10 for pegging

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    crib           : FaceDownPile          // owned by the dealer, fed by both
    starter        : Discard               // one face-up card, shared
    play_pile      : TrickPile             // the current pegging round
    played[player] : PlayerPile<player>    // pegged cards
  }

  state {
    score[player] : Integer = 0
  }

  phase hand_sequence repeats until (any player p: score[p] >= 121) {
    state {
      dealer : Player = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 6 cards from deck to each hand
      dealer := the player where player != dealer   // the deal alternates
    }

    phase play {
      legal_moves: [discard_to_crib, play_card, declare_go]
      instantiate CribbageHand(dealer = dealer)
    }
  }

  winner: highest score
}
```
