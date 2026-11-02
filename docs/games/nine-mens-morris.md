# Nine men's morris

The companion formal file is [nine-mens-morris.cardlang](nine-mens-morris.cardlang);
this is the readable twin. Nine men's morris (German *Mühle*) is the corpus's
first game on a board that is not a grid: twenty-four points joined by lines,
and two decisions in one turn — the move, then the removal a mill earns.
**Variant pinned here: 2 players, nine men each, on the standard
twenty-four-point board; White (player 0) moves first; the placing phase, then
the moving phase along the lines, and flying once a player is down to three
men; a mill earns one removal, one even when a single move closes two mills;
a man standing in a mill may be removed only when every enemy man on the board
stands in one; you lose when you are reduced to two men or have no legal move
on your turn. There is no move cap and no repetition rule.** Rules are common
knowledge. The native differential against OpenSpiel's `nine_mens_morris` is
`tests/test_differential_nine_mens_morris.py`: the two agree at every node it
walks, and it stops comparing at that implementation's turn cap
(`kMaxNumTurns`, 200 completed turns), which is not a rule of the game.

**Rules source.** The rules body is the Welt-Mühlespiel-Dachverband (WMD).
Its own pages did not resolve when the file was written (2026-11-01:
`muehlespiel.eu` serves unrelated content), and Pagat, the repo's usual
authority, does not cover the game (its alphabetical index, 2026-11-01). The
file follows the two restatements that do resolve, fetched live on
2026-11-01:

- English Wikipedia, [Nine men's morris](https://en.wikipedia.org/wiki/Nine_men%27s_morris):
  placing, moving to an adjacent point, flying at three men, the mill and its
  removal ("a piece in an opponent's mill … can be removed only if no other
  pieces are available"), and the two ways to win.
- German Wikipedia, [Mühle (Spiel)](https://de.wikipedia.org/wiki/M%C3%BChle_(Spiel)),
  its account of the WMD rules: the three phases, flying at three, the loss of
  a player who cannot move, the ban on taking a man from a mill, and the
  official exception that a man may be taken from a closed mill when the
  opponent has men only in closed mills.

Three points are settled outside those pages:

- **One removal for two mills.** Neither page says what a move that closes
  two mills at once earns. The file removes one man, as the operator's ruling
  on the boards rung says (issue #953).
- **White moves first.** English Wikipedia leaves the first player to the
  players; the variant pins White.
- **The in-mill restriction is the traditional one.** Rosenberger's
  *Mühle-Lehrbuch* (v1.9, read during planning on 2026-10-25 and not
  re-fetched) records that the WMD has since lifted the ban on taking from a
  mill altogether, so that any enemy man may be taken. That relaxation is a
  variant this file does not pin; the file plays the restriction with its
  every-man-in-a-mill exception, which both restatements above state.

## The board

Twenty-four points on three concentric squares, named in the WMD notation:
the file letter from the left (`a` to `g`), the rank from the bottom (`1` to
`7`). Lines join each square's corners to its side midpoints, and each side's
midpoint to the next square's:

    a7 ---------- d7 ---------- g7
    |             |             |
    |   b6 ------ d6 ------ f6  |
    |   |         |         |   |
    |   |   c5 -- d5 -- e5  |   |
    |   |   |           |   |   |
    a4 -b4 -c4          e4 -f4 -g4
    |   |   |           |   |   |
    |   |   c3 -- d3 -- e3  |   |
    |   |         |         |   |
    |   b2 ------ d2 ------ f2  |
    |             |             |
    a1 ---------- d1 ---------- g1

Two points are **adjacent** when a line joins them with no point between. A
**mill** is three men of one side on one straight line of three points: the
three points along each side of each square (twelve), and the four lines of
three crossing the squares at their midpoints (`d1 d2 d3`, `d5 d6 d7`,
`a4 b4 c4`, `e4 f4 g4`) — sixteen in all. `a4 b4 c4 e4 f4 g4` is not a line of
six: the middle of the board is empty, so `c4` and `e4` are not joined.

## Play

- **The men.** Each player has nine men, White's and Black's. Every man of a
  side is the same; only its side matters. The board starts empty.
- **A turn.** White moves first, then the players alternate. On your turn you
  make one move; if it closes a mill, you then remove one enemy man, in the
  same turn.
- **Placing.** While you have men left to place, your move is to put one of
  them on any vacant point. Each player places all nine before anyone moves a
  man on the board, so the placing phase lasts eighteen turns (removals do not
  shorten it: a man removed from the board is not placed again).
- **Moving.** Once you have placed all nine, your move is to slide one of
  your men along a line to an adjacent vacant point. There is no jumping.
- **Flying.** Once you are down to three men, your move is to take one of
  your men from its point to any vacant point on the board, adjacent or not.
  Your opponent, with more men, still slides.
- **Mills and removal.** A move that brings a man onto a point completing a
  mill of your side closes that mill — a placement, a slide or a fly alike.
  Moving a man out of a mill and back closes it again. Closing a mill earns
  one removal: take one of your opponent's men off the board, for good. A man
  standing in a mill of its own side may not be taken while any enemy man
  stands outside every mill; when every enemy man on the board stands in a
  mill, any of them may be taken. A move closing two mills at once still
  earns one removal.
- **Winning.** You win when your removal leaves your opponent with two men.
  Men not yet placed count: during the placing phase, a player's men are those
  on the board and those still to place. You also win when your opponent, on
  their turn, has no legal move — every man of theirs is blocked, with no
  vacant point beside it. A player who flies always has a move, and so does
  a player still placing.
- **No draw rule.** Nothing else ends the game: there is no limit on the
  number of moves and no rule about repeated positions. Between two careful
  players a game can go on forever; a line that never ends is drawn when the
  engine stops it at its bound.

## How the DSL says it

`board: morris9` mints the position domain `cell`, whose twenty-four members
are the points, and `point[cell] : Cell<cell>` is the family of one-man
holding zones ([decisions.md](../decisions.md), "Declared adjacency, and which
family answers which verb"). `neighbors(c)` reads the board's declared
adjacency, so a slide is legal where `to in neighbors(from)`; `lines(3)` is
the sixteen mills. `pieces: morris_men` is the eighteen men, a `side` axis of
`white` and `black`.

The phase is the offer's branch, so each move family is written once: `place`
behind "you have men in reserve", `slide` behind "you have more than three
men", `fly` otherwise. `place`, `slide` and `fly` each raise the `milled` flag
when the man lands in a mill (`in_mill`), and the turn then offers the same
player one `remove` — a second decision inside the turn. The in-mill
restriction is `remove`'s When Clause: the man is the enemy's, and either it
stands in no mill or every enemy man does (`all_in_mill`). `milled` is a flag,
not a count, which is how two mills earn one removal.

The blocked player is found in the turn body before any offer (`can_move`):
a turn whose player has no legal move decides nothing, writes the loss, and
the `until` ends the game at the turn's end. `men_left[player]` counts a
side's men in reserve and on the board; the one `remove` effect decrements it
beside the one movement to `captured`, and reaching two ends the game.
`result[player]` is +1 / -1 and `winner: highest result` reads it, so the
OpenSpiel returns are `[+1, -1]` or `[-1, +1]`.

`max_length` is the bound the engine stops a game at, not a rule of the game;
`at max_length: tie` says what a stopped game is worth — a draw, every return
0 — which is the honest reading of a line that repeats without end
([decisions.md](../decisions.md), "Game length as a declared contract"). The
playout tests measure the longest line under uniform play and hold the bound
well above it. Everything is public — the board, both reserves and both
captured piles — so each information set is a singleton and no
hidden-information machinery is engaged.
