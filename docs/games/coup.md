# Coup

The companion formal file is [coup.cardlang](coup.cardlang); this is the
readable twin. Coup (base game, 3-6 players; the executable fixes four) — a
bluff-and-challenge game with a 15-card deck (five characters, three copies
each) and a coin economy. Each player holds two face-down *influence* cards and
some coins; on a turn the active player takes one action, others may challenge
or block it, and influence is lost by flipping a card permanently face-up. The
last player with influence wins. Rules: Tchanturia, 2012.

A turn's actions:

- **Income** — take 1 coin (uncontestable).
- **Foreign aid** — take 2 coins, unless someone claims the Duke to block it.
- **Coup** — pay 7, force a player to lose influence (uncontestable). Forced once
  you reach 10 coins.
- **Tax** (claim Duke) — take 3 coins.
- **Assassinate** (claim Assassin) — pay 3, a target loses influence unless they
  claim the Contessa to block.
- **Steal** (claim Captain) — take 2 coins from a target unless they claim
  Captain or Ambassador to block.
- **Exchange** (claim Ambassador) — draw 2 from the deck and return 2.

Any character claim (an action or a block) can be **challenged**: if the claimant
holds the character, the challenger loses influence and the claimant swaps the
proven card for a fresh one; if it was a bluff, the claimant loses influence and
the action fails. A player who loses their last influence is exiled and their
coins return to the bank.

The whole game — setup, the turn loop, the seven actions, the challenge/block
windows, and elimination — runs in the built-in `CoupGame` mechanic, which drives
`coins`, `treasury`, and `alive` directly. Coins are integers (always 50 in
total) and influence cards conserve to 15. `alive[p]` is 1 while a player is in
and 0 once exiled, so `winner: highest alive` names the survivor. Challenges and
blocks fire at a modest random rate; the forced Coup at 10 coins guarantees
elimination and termination.

```
game Coup {

  players: 4
  direction: clockwise

  cards: coup15

  zones {
    court_deck        : Deck                  // the face-down character pile
    influence[player] : Hand<player>          // face-down influence
    revealed[player]  : PlayerPile<player>    // lost influence, face-up
  }

  state {
    coins[player]  : Integer = 0      // dealt 2 each from the treasury at setup
    treasury       : Integer = 50     // the bank starts with all 50 coins
    alive[player]  : Integer = 1      // 1 while in the game, 0 once exiled
  }

  phase play {
    legal_moves: [income, foreign_aid, coup, tax, assassinate, steal, exchange, challenge, block]
    instantiate CoupGame()
  }

  winner: highest alive
}
```
