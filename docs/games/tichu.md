# Tichu

The companion formal file is [tichu.cardlang](tichu.cardlang); this is the
readable twin. A four-player partnership **climbing** game on a 56-card deck (the
standard 52 plus four special cards: Mahjong, Dog, Phoenix, Dragon). First
partnership to **1000** wins. Rules: Fata Morgana English edition.

Each hand:

1. Deal 14 cards each; every player **pushes** one card to each other player.
2. The Mahjong holder leads. Players **climb**: each play must be a combination
   of the led *type and length* and **beat** the previous play in rank, or be a
   **bomb** (four of a kind, which beats any non-bomb), or **pass**. Three passes
   end the trick and the last player to play wins it and leads next.
   Combinations: singles, pairs, triples, full houses, straights (≥5),
   consecutive pairs (≥2), and bombs.
3. The special cards: the **Mahjong** is rank 1 (lowest) and leads first; the
   **Dog** is led alone and hands the lead to your partner (no capture); the
   **Phoenix** is a wildcard / a single worth half a rank above the last play
   (and −25 points); the **Dragon** is the highest single, worth +25, and its
   trick is given to an opponent.
4. As players empty their hands they go out in order. If both partners of a team
   go out first and second — a **double victory** — the hand ends for 200 points
   with no card counting. Otherwise the last player's remaining hand goes to the
   opponents and their captured tricks to the first player out, and each team
   scores its captured card points (K and 10 = 10, 5 = 5, Dragon +25, Phoenix
   −25; 100 in all). Finally, **Tichu** (±100) and **Grand Tichu** (±200) calls
   pay out by whether the caller went out first.

The hand engine runs in the built-in `TichuHand` mechanic. Scope reductions
(random play): the Mahjong wish, the Phoenix as a wildcard inside
straights/consecutive-pairs, straight-flush bombs, and out-of-turn bombs are
omitted; Tichu/Grand Tichu are called at a low random rate.

```
game Tichu {

  players: 4
  partnerships: [[0, 2], [1, 3]]   // partners sit across
  direction: counterclockwise

  cards: tichu56

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
    discard        : Discard          // the Dog goes here (no capture)
  }

  state {
    score[team] : Integer = 0
  }

  phase hand_sequence repeats until (any team t: score[t] >= 1000) {
    before_each {
      move all cards to deck
      shuffle deck
      deal 14 cards from deck to each hand
    }

    phase play {
      legal_moves: [play_combination, pass, call_tichu, call_grand_tichu, push_card]
      instantiate TichuHand(starting = 0)
    }
  }

  winner: highest score
}
```
