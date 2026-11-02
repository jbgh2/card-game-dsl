# Hex

The companion formal file is [hex.cardlang](hex.cardlang); this is the
readable twin. Hex is the connection rung of the board-game axis: the first
corpus game won by a *shape* on the board, a chain of stones joining two
edges, rather than by a line of fixed length or by reaching a row. **Variant
pinned here: 2 players on an 11x11 rhombus of hexagons, 61 black stones and
60 white; no swap rule; black (player 0) moves first; players alternate
placing one stone on an empty cell; the first player to join their two edges
with an unbroken chain of their own stones wins.** There is no draw.

Rules sources, read 2026-11-01:

- The rules body is Wikipedia's [Hex (board
  game)](https://en.wikipedia.org/wiki/Hex_(board_game)), "Rules": a stone per
  turn on an empty cell, stones never moved or removed, each player's goal a
  chain of their own stones linking their two opposite edges, the first to
  complete one the winner, and the corner hexagons belonging to both adjacent
  edges. The page describes the swap rule as the usual balance for the first
  player's advantage; this variant does not play it.
- The executable tiebreaker is OpenSpiel's native `hex`
  ([hex.h](https://raw.githubusercontent.com/google-deepmind/open_spiel/master/open_spiel/games/hex/hex.h),
  [hex.cc](https://raw.githubusercontent.com/google-deepmind/open_spiel/master/open_spiel/games/hex/hex.cc)),
  at its defaults `board_size=11` and `swap=false` ("Does not implement pie
  rule"). Black is its player 0 and moves first, black joins its first row to
  its last, white its first column to its last, and its cells name exactly as
  ours do.
- Pagat, the corpus's usual authority, covers card games and has no Hex page.

Setup and play:

- **The board.** An 11x11 rhombus of 121 hexagons, named like a chessboard:
  files `a` to `k` from the left, ranks `1` to `11` from the bottom, so `a1`
  is the corner at the bottom left and `k11` the corner at the top right.
  Each hexagon touches up to six others: the two beside it on its rank, the
  two above and below it on its file, and the two on the diagonal running up
  to the left and down to the right (`b1` touches `a2`; `a1` does not touch
  `b2`).
- **The edges.** Black owns the bottom edge (rank 1) and the top edge (rank
  11). White owns the left edge (file `a`) and the right edge (file `k`). Each
  corner hexagon lies on both of its edges, so `a1` is on black's bottom edge
  and white's left edge alike.
- **The stones.** Black holds 61 stones and white 60 — one for every cell,
  black holding the odd one because black moves first. Every stone of a colour
  is the same.
- **A turn.** Black moves first, then the players alternate. On your turn you
  place one of your stones on any empty cell. You cannot pass, and a stone,
  once placed, never moves and is never taken.
- **Winning.** You win the moment your stones form an unbroken chain of
  touching hexagons from one of your edges to the other. The chain may wind
  anywhere; only its ends must lie on your two edges.
- **No draw.** However the board fills, exactly one player has joined their
  two edges, so the game always ends with a winner, at the 121st stone at the
  latest (the hex theorem).

How the DSL says it (decisions.md "Boards and cells"): `board: hex_rhombus(11)`
mints the position domain `cell` whose 121 members are the hexagons, in the
same order as the grid's cells, and declares their six-neighbour adjacency and
each seat's two borders; `tile[cell] : Cell<cell>` is the 121-instance family
of one-stone holding zones. `pieces: hex_stones` selects the 121-stone
component set with a `side` axis (`black` / `white`) in place of a suit.
Placement is ordinary kernel movement: `place(at : cell)` moves one stone from
the actor's reserve to `tile[at]`, and `at` ranges over the 121 cells, so the
move enumerates 121 placement actions in board order.

The win is one sentence: `connected(near_edge(actor), far_edge(actor), cells
where holds(cell, actor))`. `near_edge(p)` and `far_edge(p)` are the two
borders the board declares for seat `p` (rank 1 and rank 11 for black, file
`a` and file `k` for white); `cells where holds(cell, actor)` is the Set Form,
the cells holding the actor's stones; and `connected` asks whether some cell
of the first set reaches some cell of the second through cells of the third
along the board's adjacency. It is a Builtin that owns its loop, so the game
writes no search of its own. Only the stone just placed can complete a chain,
so the test runs once per placement, for the player who placed it, and its
outcome is written into `result[player]` as +1 (win) / -1 (loss);
`winner: highest result` reads it, making the OpenSpiel returns `[+1,-1]` or
`[-1,+1]`.

`max_length: 121` is the board's own bound, not an allowance measured from
play: one stone goes down per turn, the board has 121 cells, and by the hex
theorem the 121st placement decides if nothing earlier has. So the `until`
names one arm, someone has won, and no "board full" arm is written: the
rulebook has no draw for it to score. Everything is public — every populated
zone projects identity to both players — so each information set is a
singleton and no hidden-information machinery is engaged.

The reference playout policy is uniform random over the offered placements.
