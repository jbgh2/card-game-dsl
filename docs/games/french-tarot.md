# French Tarot

The companion formal file is [french-tarot.cardlang](french-tarot.cardlang);
this is the readable twin. Four-player French Tarot (FFT rules) on the 78-card
Tarot deck — four 14-card suits (K Q Cavalier J 10…1), 21 atouts (trumps), and
the Excuse. One player (the *taker*) plays alone against the other three, trying
to take enough card points in tricks to beat a threshold set by how many *bouts*
(the 1 of atouts, the 21, and the Excuse) they capture. Thirty-six hands are
played; the highest score wins. Source:
[Pagat](https://www.pagat.com/tarot/frtarot.html).

Each hand:

1. Deal 18 cards to each player and 6 to the *chien* (kitty).
2. **Bid** — one ascending bid per player: Petite < Garde < Garde sans le chien
   < Garde contre le chien. The highest bidder is the taker; if all pass, the
   hand is thrown in.
3. **Chien** — at Petite/Garde the taker takes the chien and discards six (the
   discards count to the taker); at Garde sans the chien counts to the taker
   unseen; at Garde contre it counts to the opponents.
4. **Play** — eighteen tricks; atouts are trumps. Follow suit; if void you must
   trump, and you must over-trump if you can. The Excuse may be played at any
   time, never wins, and stays with its team (transferring a low card to the
   trick winner in compensation).
5. **Score** — the threshold is 36/41/51/56 card points for 3/2/1/0 bouts.
   `pt = taker points − threshold`; with the petit-au-bout bonus `pb` (±10 if the
   1 of atouts falls in the last trick) and the bid multiplier `mu`
   (1/2/4/6), each opponent pays `(25 + pt + pb) × mu` and the taker collects
   three times that (zero-sum).

The hand engine runs in the built-in `TarotHand` mechanic (card points kept in
doubled integer units; the 78 cards sum to 182). poignée and the Excuse
half-point IOU deferral are out of scope.

```
game FrenchTarot {

  players: 4
  direction: counterclockwise        // canonical for French Tarot

  cards: tarot78

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    chien            : FaceDownPile        // the six-card kitty
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }

  state {
    score[player] : Integer = 0
    hands_played  : Integer = 0
  }

  phase hand_sequence repeats until hands_played >= 36 {
    state {
      dealer : Player = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 18 cards from deck to each hand
      deal 6 cards from deck to chien
      dealer := dealer offset_by right        // counter-clockwise rotation
    }

    phase play {
      legal_moves: [submit_bid, pass, discard_to_chien, call_poignee, play_to_trick]
      instantiate TarotHand(starting = dealer offset_by right)
    }

    after_each {
      hands_played += 1
    }
  }

  winner: highest score
}
```
