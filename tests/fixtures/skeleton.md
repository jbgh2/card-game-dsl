# Skeleton

A minimal synthetic game that exercises every pipeline stage end to end:
the game header, a player count, a deck, and two zones — one singleton, one
owner-parameterized. It is not a real game; it is the walking skeleton.

```
game Skeleton {
  players: 2
  max_length: 1000
  cards: standard52
  zones {
    deck         : Deck
    hand[player] : Hand<player>
  }
}
```
