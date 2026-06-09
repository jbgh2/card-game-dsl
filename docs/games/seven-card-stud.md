# Seven-Card Stud

The companion formal file is
[seven-card-stud.cardlang](seven-card-stud.cardlang); this is the readable twin.
Fixed-limit Seven-Card Stud — the corpus's first **betting** game. Source:
[Pagat](https://www.pagat.com/poker/variants/7stud.html).

Each hand:

1. Every player antes; deal two hole cards and one upcard each.
2. The lowest upcard (ties by suit) **brings in**.
3. Five betting streets — 3rd through 7th — interleaved with a dealt card each
   (an upcard on 4th/5th/6th, a face-down card on 7th, a burn before each). On
   each street a player may check, bet, call, raise (capped), or fold; the
   highest visible board acts first from 4th street on. The lower limit applies
   on 3rd/4th, the upper limit from 5th.
4. **Showdown** — the best five-card poker hand from each remaining player's seven
   cards wins the pot, with side pots when players are all-in.

The `.md` source is a cash game with no overall winner; to give the runtime a
terminal, the executable plays until one player holds **all** the chips and names
that player the winner. Chips are modelled as an integer `stack` per player (not
a resource-zone subsystem); the total is invariant. The hand engine — antes,
bring-in, betting, and showdown with side-pot distribution — runs in the built-in
`StudHand` mechanic; the poker evaluator is unit-tested. The 4th-street open-pair
limit doubling is simplified out.

```
game SevenCardStud {

  players: 4
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck            : Deck
    hole[player]    : Hand<player>           // face-down cards
    upcards[player] : PublicHand<player>     // face-up cards
    muck            : Muck                   // folded / spent cards
    burn            : Burn                   // one burned card per street
  }

  state {
    // Chips as integers; total is invariant. The winner holds them all.
    stack[player] : Integer = 100
  }

  phase hand_sequence repeats until (number of players where stack[player] > 0) <= 1 {
    state {
      dealer : Player = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      dealer := dealer offset_by left
    }

    phase play {
      legal_moves: [bring_in, check, call, bet, raise, fold]
      instantiate StudHand(dealer = dealer)
    }
  }

  winner: highest stack
}
```
