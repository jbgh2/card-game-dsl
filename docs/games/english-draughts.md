# English draughts

The companion formal file is [english-draughts.cardlang](english-draughts.cardlang);
this is the readable twin. English draughts (checkers) is the move-existence
rung of the board-game axis: the first corpus game in which what you may do
depends on whether a move of another kind exists anywhere on the board, and
the first whose one move can take several jumps. **Variant pinned here: 2
players on the thirty-two dark squares of an 8x8 board (`draughts(8, 8)`),
twelve men a side and a king for each (`draughts_men`); Red (player 0) moves
first; men step and capture diagonally forward, kings both ways; every capture
is compulsory, any capture may be chosen, and a capturing piece jumps on until
it cannot; a man reaching the far rank is crowned, and that ends its move; the
player left with no legal move loses; eighty plies in a row with no capture and
no uncrowned man moved draw the game.** Rules are common knowledge.

**Rules source.** The rules body is the World Checkers/Draughts Federation's
*Rules of Draughts*, served as a Word document at
<https://www.usacheckers.com/rulesofcheckers.php> (read 2026-11-02; the
WCDF's own <https://www.wcdf.net/rules.htm> serves its navigation and none of
the text). Section One, "Equipment and Rules for Play", is the part the file
plays. The executable tiebreaker is OpenSpiel's native `checkers`
([checkers.h](https://raw.githubusercontent.com/google-deepmind/open_spiel/master/open_spiel/games/checkers/checkers.h),
[checkers.cc](https://raw.githubusercontent.com/google-deepmind/open_spiel/master/open_spiel/games/checkers/checkers.cc)),
read the same day, at its defaults `rows=8` and `columns=8`.

**Two departures from the text, both named in the file's header.**

- **The forty-move rule is automatic.** The federation declares a game drawn
  when a player shows the referee that neither player has advanced an
  uncrowned man, and no piece has been removed, in either player's own
  previous forty moves. A game with no referee cannot hear a claim, so the
  file draws the game itself the moment the condition holds: eighty plies in a
  row (forty moves each) with no capture and no move of an uncrowned man. A
  man's move always advances it, since a man moves only forward.
- **No repetition claim.** The federation's other referee's draw, a player
  showing that their next move would make the same position for the third
  time, is not played (issue #953's ruling, question 2). Neither is a draw by
  agreement, a resignation, a forfeit or a clock.

## The board

The board is eight ranks by eight files, named by file (`a` to `h` from the
left as Red sits) and rank (`1` to `8` from Red's side). Only the dark squares
are played, and `a1`, Red's near-left corner, is one of them: the thirty-two
squares whose file, counted from `a` as 1, and rank add up to an even number,
`a1`, `c1`, `e1`, `g1`, `b2`, `d2` and so on up to `h8`.
The federation numbers the same squares 1 to 32 from Red's side, so Red's
squares 1 to 12 are its back three ranks and White's squares 21 to 32 are
White's.

## Play

- **The pieces.** Each player starts with twelve men, Red's on the dark
  squares of ranks 1 to 3 and White's on those of ranks 6 to 8. Every man of a
  side is the same; so is every king.
- **A turn.** Red moves first, then the players alternate. On your turn you
  move one piece, by a step or by a capture.
- **A man's step.** A man moves one square diagonally forward, left or right,
  onto an empty square. Forward is toward the opponent's side: up the ranks
  for Red, down for White.
- **A king's step.** A king moves one square diagonally forward or backward,
  onto an empty square.
- **A capture.** A piece captures by jumping over a diagonally adjacent enemy
  piece, man or king, onto the empty square just beyond it, and the jumped
  piece leaves the board. A man jumps forward only; a king jumps either way.
- **Capturing is compulsory.** If any of your pieces can capture, you must
  capture; you may not step. When several captures are open, you may choose
  any of them, not necessarily the one that takes the most.
- **The continuing capture.** If the piece that just jumped can jump again
  from the square it landed on, it must, and no other piece moves until it is
  done. The move ends when the jumping piece has no further jump. A piece is
  jumped only once in a move.
- **Crowning.** A man that reaches the far rank (rank 8 for Red, rank 1 for
  White) becomes a king, and that ends the move, even if it arrived by a jump
  and another jump would be open to the new king. It moves as a king from the
  player's next turn. A king that jumps onto the far rank is not crowned again
  and jumps on if it can.
- **Winning.** The federation's sentence is that the game "is won by the
  player who can make the last move": you win when your opponent, on their
  turn, has no legal move, every piece of theirs captured or every one
  blocked.
- **The draw.** The game is drawn after eighty plies in a row in which no
  piece was captured and no uncrowned man moved. A move that leaves the
  opponent with no legal move wins, even when it is the eightieth of those
  plies.

## How the DSL says it

`board: draughts(8, 8)` mints the position domain `cell` whose thirty-two
members are the dark squares, and its movement frame mints `dir`: the four
diagonals `ahead_left`, `ahead_right`, `back_left` and `back_right`, each
seat's own, the second seat's frame the first's turned half round
([decisions.md](../decisions.md), "Boards and cells"). `square[cell] :
Cell<cell>` holds the piece on each square. `pieces: draughts_men` is the
forty-eight pieces, a `side` axis of `red` and `white` and a `kind` axis of
`man` and `king`. Setup puts each side's kings in its `kings` supply and its
men in its `reserve`, then fills each side's `home`, its back three ranks.

`is_forward(along)` is true of the two `ahead_*` directions, so `may_go` is a
man forward and a king any way. `step_ok` and `jump_ok` are a step and a jump
from one square in one direction; `can_jump(p)` asks whether any of `p`'s
pieces has a jump in any direction (`any cell where any dir where ...`), and
`can_move(p)` whether it has a jump or a step.

**Compulsory capture is the rulebook's own sentence.** The turn is
`if can_jump(t) { offer to t one of [jump] } else { offer to t one of [step] }`:
if you can capture, the turn offers captures, and otherwise steps. No move
carries a "no capture elsewhere" clause.

**The continuing capture is the turn's go-again.** A jump that lands where the
same piece can jump again records that square in `chain_from` and sets
`jumping`, the turn's `again` flag, so the same player takes the next turn;
`jump`'s When Clause admits only the piece on `chain_from` while it is set.
`chain_from : cell? = none` is a state variable holding a square
([decisions.md](../decisions.md), "Boards and cells"), and it goes back to
`none` with every jump, so a jump that ends the move leaves it clear.

**Crowning is a swap from the supply.** A man arriving on `far_row(actor)`
goes back to its side's `reserve` and a king from `kings[actor]` takes its
square, so the board holds a real king, and every movement is a public
transfer. A crowning jump writes no `chain_from`, which is how crowning ends
the move.

**The count and the loss.** `quiet` counts the plies in a row with no capture
and no man moved: a man's step and every jump set it to 0, a king's step adds
one. The `until` ends the game when a player's `result` is 1 or `quiet`
reaches 80, and `winner: highest result` gives a drawn game, both results 0,
to nobody. The loss is written by the move that causes it: after a step, and
after a jump that ends the move, `can_move(foe)` asks whether the opponent has
any move, and if not the mover's `result` is +1 and the opponent's -1. Because
the move writes the win before the `until` reads `quiet`, a blockade on the
eightieth quiet ply is a win, which is the federation's "last move".

**Two readings of the rules the file settles.**

- **When a jumped piece leaves the board.** The federation says both that the
  captured piece is removed on completion of each jump and that all captured
  pieces are removed at the end of the capturing sequence. The file removes
  each piece as it is jumped. The two agree on every move: a jump moves a
  piece two squares diagonally, so every square it lands on in one move has
  the same file parity and rank parity as the square it started from, while
  every jumped square has the other parity; a jumped piece left standing could
  therefore never block a landing square, and it cannot be jumped again (a
  piece is jumped once in a move), so whether it stands until the move ends
  changes nothing. The differential's scripted multi-jump lines check this
  against OpenSpiel, which removes each piece as it is jumped.
- **The colours.** OpenSpiel calls its first mover White and draws it at the
  bottom of its board; the federation's first mover is Red. The differential
  maps the two by seat, player 0 to player 0, and the file's Red is seat 0.

Everything is public -- the board, both reserves, both king supplies and both
captured piles, `quiet` and `chain_from` -- so each information set is a
singleton and no hidden-information machinery is engaged.

`max_length` is the bound the engine stops a game at, not a rule of the game.
Every line of this game ends by its rules: a man's moves are finite, every
capture takes a piece, and between them the forty-move count ends the game,
so the bound is set far above the longest line the playout tests measure and
no line reaches it.

OpenSpiel's `checkers` also ends a game after forty plies with no capture,
counting every ply, man's moves and the hops of a capture alike, as a draw.
That is not a rule of this game, and the differential stops comparing at that
point.
