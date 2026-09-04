# Breakthrough

The companion formal file is [breakthrough.cardlang](breakthrough.cardlang);
this is the readable twin. Breakthrough (Dan Troyka, 2000) is the movement rung
of the board-game axis: the first corpus game whose pieces *travel* rather than
being placed once. **Variant pinned here: 2 players on an 8x8 board, 16 men
each; light (player 0) moves first; a man steps one square straight or
diagonally forward onto an empty square, or diagonally forward onto an enemy
man, removing it; a straight step never captures, and no step ever lands on a
man of your own side; you win by landing a man on the opponent's back row or by
capturing the opponent's last man.** There is no draw. Rules are common
knowledge, and the differential oracle is OpenSpiel's native `breakthrough`.

Setup and play:

- **The board.** An 8x8 grid of sixty-four cells, named by file (`a` to `h`
  from the left) and rank (`1` to `8` from the bottom): `a1` is the
  bottom-left corner, `h8` the top-right.
- **The armies.** Light fills ranks 1 and 2 (sixteen men), dark fills ranks 7
  and 8. Every man is the same; only its side matters. Nothing else is on the
  board.
- **Forward.** Light advances toward rank 8, dark toward rank 1 — each side's
  "forward" is its own, on the one shared board.
- **A turn.** Light moves first, then the players alternate. You must move; on
  your turn you pick one of your men and step it one square forward: straight
  ahead, or diagonally forward-left or forward-right.
- **The empty square.** Any of those three steps is legal onto an empty
  square. A step off the edge of the board is not a move.
- **Capture.** Only the two diagonal steps may capture. Stepping diagonally
  onto a square holding an enemy man removes that man from the board and puts
  yours in its place. A straight step onto an occupied square is illegal, and
  no step may land on a man of your own side. There is no jumping, no chain
  capture, and captured men never return.
- **Winning.** You win the moment one of your men stands on the opponent's
  back row — rank 8 for light, rank 1 for dark. You also win if you capture
  the opponent's last man. Nothing else ends the game, and it can never be
  drawn: every move either advances a man or removes one, so no line repeats.

How the DSL says it (decisions.md "Boards and cells"): `board: grid(8, 8)`
mints the position domain `cell` whose sixty-four members are the squares, and
`square[cell] : Cell<cell>` is the sixty-four-instance family of one-man
holding zones (a `Cell` has capacity one, so a step onto an occupied square
would hit the capacity Owner Guard — the guard is what keeps that from arising). The
same grid family also mints the movement-direction domain `dir`, whose three
members `ahead`, `ahead_left` and `ahead_right` are read in the *actor's*
frame: the grid carries a per-seat frame, so one shared board serves two
opposed armies without either side's rules being written twice.
`pieces: breakthrough_men` selects the thirty-two-man component set with a
`side` axis (`light` / `dark`) in place of a suit.

Setup is a region walk: `home(player)` is the grid family's name for a seat's
back two ranks, so `for each cell c: if c in home(0) { move one piece from
reserve[0] to square[c] }` lays out one army with no cell named individually,
and the mirror line lays out the other. `far_row(player)` is the Shadow Guard — the
rank at the far edge of that seat's frame, which is the opponent's back row and
the reach goal.

The move is `step(from : cell, along : dir)`: a *direction*, not a destination.
The parameter pair enumerates sixty-four cells times three directions, which is
one-to-one with what the game can actually do; a `(from, to)` pair would
declare four thousand actions of which a few hundred are ever legal. The guard
does the whole legality grid in one short-circuiting chain — the source square
holds one of my men, `has_step` says the step stays on the board, and the
destination is either empty or (diagonally only) an enemy. The ordering is
load-bearing: `has_step` gates every `neighbor` read, and the emptiness test
gates every `top_of`, so no query is ever asked about a square that is not
there.

The effect is two ordinary kernel movements. When the destination holds an
enemy, that man moves to `captured[foe]` — a public pile, one per side, holding
the men captured *from* that side — and then the mover moves from `square[from]`
to the destination. Both movements announce themselves at the existing
observation sites; nothing about a capture is concealed. `pieces_left[player]`
tracks each side's men on the board and is decremented as they are taken, so the
`until` predicate can name both termini exactly as the oracle's does: someone
has won (`result[player] is 1`) or someone has nothing left
(`pieces_left[player] is 0`). The outcome is written into `result[player]` as +1
(win) / -1 (loss) and `winner: highest result` reads it, making the OpenSpiel
returns `[+1,-1]` — zero-sum, never a draw. `max_length: 500` is a
non-termination Shadow Guard rather than a rule; the longest measured game is 108
plies. Everything is public — every populated zone projects identity to both
players — so each information set is a singleton and no hidden-information
machinery is engaged.
