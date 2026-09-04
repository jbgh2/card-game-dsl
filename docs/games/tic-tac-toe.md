# Tic-tac-toe

The companion formal file is [tic-tac-toe.cardlang](tic-tac-toe.cardlang); this
is the readable twin. Tic-tac-toe is the walking skeleton of the board-game
axis: two players, a 3x3 grid, and nine marks (five X, four O). **Variant
pinned here: X (player 0) moves first; players alternate placing one mark on an
empty cell; three of your own marks in a line — row, column, or diagonal — wins
the instant the line completes; a full board with no line is a draw.** Rules are
common knowledge, and the differential oracle is OpenSpiel's native
`tic_tac_toe`.

Setup and play:

- **The board.** A 3x3 grid of nine cells, named by file (`a`, `b`, `c` from
  the left) and rank (`1`, `2`, `3` from the bottom): `a1` is the bottom-left
  corner, `c3` the top-right. Every cell starts empty.
- **The marks.** X holds five marks, O holds four — enough for either side to
  fill its half of a nine-cell board. They sit in each player's reserve until
  placed.
- **Goal.** Be the first to place three of your own marks in a straight line:
  any of the three rows, three columns, or two diagonals.
- **A turn.** On your turn you place one mark on any empty cell. You cannot
  pass, and you cannot play on an occupied cell.
- **Winning.** The moment your placement completes a line of three of your
  marks, you win and the game ends — even if cells remain empty.
- **The draw.** If all nine cells fill with no line completed, the game is a
  draw.

How the DSL says it (decisions.md "Boards and cells"): `board: grid(3, 3)`
mints a position domain named `cell` whose nine members are the grid squares,
and `square[cell] : Cell<cell>` is the nine-instance family of one-card holding
zones, one per square (a `Cell` has capacity one, so a placement onto an
occupied square would hit the capacity Owner Guard — the `when: square[at] is empty`
guard keeps that from arising). `pieces: xo_marks` selects the nine-mark
component set — the piece flavor of the same content model that backs a card
deck — with a `side` axis (`x` / `o`) in place of a suit. Placement is ordinary
kernel movement: `place(at : cell)` moves one mark from the actor's reserve to
`square[at]`, and the parameter `at` ranges over the nine cells, so the move
enumerates nine placement actions. The win test reads the board through the
line-query register: `any line in lines(3) where all cells in line where ...` is
true exactly when some declared length-3 line is filled by one side. Because the
just-placed mark's side is the actor's by construction, the line predicate
compares each cell's occupant to `top_of(square[at]).side` — the mark that was
just placed — so no player-to-side mapping is needed. The outcome is written into
`result[player]` as +1 (win) / -1 (loss), left at 0 for a draw, and
`winner: highest result` reads it; the encoding makes the OpenSpiel returns
`[+1,-1]` / `[0,0]`, so a draw is properly better than a loss. Everything is
public — every zone projects identity to both players — so each information set
is a singleton and no hidden-information machinery is engaged.
