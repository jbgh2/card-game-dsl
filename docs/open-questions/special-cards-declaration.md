# Special cards declaration

**Tier 4 — low impact, defer until forced.**

Tichu's deck has four cards that don't fit the standard `(suit, rank)`
shape: Mahjong, Dog, Phoenix, Dragon. They have unique identities and
unique behaviors. The provisional declaration:

```
cards: {
  suits:    [S, H, D, C]
  ranks:    [2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A]
  specials: [Mahjong, Dog, Phoenix, Dragon]
}
```

Two design questions tangled together:

**1. Declaration mechanism.** Is `specials:` a real header, or should
specials be modelled as sentinel rank values (e.g.
`ranks: [Mahjong, 2..A, Dragon]`), or as a separate type altogether
(`specials: [...]` with their own object model)?

**2. Contextual rank.** Phoenix's rank when played as a single is
*half a rank above the last play* (1.5 if led, 8.5 over an 8). The
rank isn't intrinsic to the card; it's resolved at play time against
trick context. The provisional encoding `PhoenixRank(base_rank: Rank?)`
captures this but is awkward. Other modelling options: a per-play
`computed_rank` callback on the move, a stdlib `JumpUp` rank operator,
or just an inline case in `MustBeatPreviousCombination`.

These two questions sit together because Phoenix is one of the four
specials and the declaration mechanism determines how to express its
contextual-rank behavior.

**Tier 4 because** Tichu is currently the only game with non-suit/rank
cards. A second game (UNO would be the obvious one if commercial
games come into scope) would clarify whether `specials:` generalizes
or whether a one-off Tichu encoding is fine.
