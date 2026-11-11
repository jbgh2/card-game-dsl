## Component sets: cards and pieces

A game's individuated zone content is declared with exactly one head
clause — `cards: <deck>` (a card deck) or `pieces: <set>` (a piece set)
— naming one entry of the closed component-set registry
([library.md](../library.md), "Built-in component sets"). The two are
mutually exclusive and one is required; a game declaring both, or
neither, is rejected (no game has witnessed needing both).

The individuated content kind is the **Piece**: an identity of two
enumerable axes (with per-set declared names) times multiplicities, plus
the per-game attributes and optional facing of the typed object model
("Typed object model"; "Knowledge, visibility, and the projection
model"). A **Card is the deck specialization of a Piece** — a component
set whose two axes are named `suit` and `rank` and which carries the
card-only conventions (`ranking:`, the follow/trump rule family,
hand-order enumeration, the `Card` move-parameter domain). A piece set
names its own two axes and carries none of them; `xo_marks`
(tic-tac-toe's marks) names them `side` (`x`/`o`) and `kind` (`mark`).

The axes bind positionally: a piece's first axis occupies the slot a
card's `suit` occupies, its second the `rank` slot. Field access types
against the game's declared axis names — `card.suit`/`card.rank` in a
card game, `piece.side`/`piece.kind` in a piece game — each axis a
distinct enum, so a cross-axis comparison (`piece.side is mark`) is
rejected exactly as `card.rank is spades` is. The axis values (`x`, `o`,
`mark`) enter the enum-value namespace exactly as a deck's suits and
ranks do.

**Noun/content agreement is a typecheck Owner Guard.** Every surface that
spells card-content vocabulary demands the deck flavor and, in a piece
game, is rejected with a diagnostic naming the game's declared kind
("this game declares pieces ('xo_marks')") — and symmetrically the
`piece`/`pieces` noun is rejected in a card game. The guarded surfaces
are the transfer/reveal item noun, the filter binder, `.suit`/`.rank`
field access, the card-query and aggregation forms, the `ranking:`
and `card_points { }` clauses, an answer to a card fact's Kernel
Definition Contract, the `suit`/`rank` quantifier and
iteration roles, the `Card`/`Suit`/`Suit?`/`Rank` move-parameter domains,
the deck-reading native calls, and card literals. Each rejection sits at the layer that
owns the operand-kind class (the typechecker), naming the kind rather
than parsing the construct and silently giving it card meaning — the
"accepted-but-ignored" failure this guard exists to prevent.

```text
pieces: xo_marks                        // axes: side = [x, o], kind = [mark]; 5 x + 4 o
move all pieces from box where piece.side is x to reserve[0]
```

**Seeding reuses the Deck-typed-zone rule** — the one existing "initial
contents" concept, one spelling per concept. A game's `Deck`-typed zone
is seeded with its component set at game start; tic-tac-toe names that
zone `box` and drains it in setup. A piece game with no `shuffle`
consumes no randomness — every seed yields the identical game.

The acceptance property for `Card`-as-a-specialization-of-`Piece` is
that **the card corpus cannot tell**: every card game keeps `cards:`,
its card queries, and byte-identical behavior. Piece Shadow Guards of the
card-query and aggregation forms are deliberately absent from the
grammar (a piece game counts and aggregates through the generic
collection surfaces a card game shares); the deferred declaration-site
and rule-system guards are recorded in issue #114.
