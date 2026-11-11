## Boards and cells

A game with a spatial board declares it with a `board: <family>(<args>)`
clause: it selects a [Board Family](../glossary/board-family.md) from the
closed `BOARDS` registry ([library.md](../library.md), "Built-in boards") and
gives its integer arguments. A family that takes none is named bare.

```text
board: grid(3, 3)
board: morris9
board: hex_rhombus(11)
board: draughts(8, 8)
```

The `grid` family builds a rectangular board, `morris9` the fixed
twenty-four-point nine men's morris board, `hex_rhombus` an n-by-n
rhombus of hexagons, and `draughts` the playable squares of a draughts
board; unknown family, wrong arity (`morris9(3)`, a bare `grid`,
`hex_rhombus(3, 3)`), or out-of-bounds arguments are resolve diagnostics
naming the argument and its bounds (the registry declares each family's
arguments, each with its own bounds). A `board:` clause **requires
`pieces:`** — a board holds pieces, not cards — so `board:` in a card
game is rejected, and the board-plus-`cards:` combination waits on a
witnessed need.

**The board mints one named-member position domain, `cell`.** It rides
the same substrate declared position domains do ("Position domains and
positional zones"): the minted domain is injected alongside any
`positions { }` block and flows through every surface an integer
position domain flows through — zone-family index, move-parameter
domain, the unowned projection, the action space, the IR — under the
same collision guard, the same 256-member cap, and the same
"always subscripted" rule. What differs is the member kind: a board's
members are **string cell names** (`a1`, `b1`, …, row-major from `a1`;
the file letter is the column from the left, the number the row from the
bottom — `grid(3, 3)`'s nine cells are `a1 b1 c1 a2 b2 c2 a3 b3 c3`),
not an integer range. The names and their order are the board entry's,
fixed in the registry.

```text
zones {
  square[cell]    : Cell<cell>          // nine one-card cells, keyed a1..c3
  reserve[player] : PlayerPile<player>
}
move_type place(at : cell) { when: square[at] is empty  effect { … } }
```

**Cells type as `TCell`, distinct from `TInteger`.** A parameter, `let`
binder, or subscript key over the `cell` domain carries `TCell`; a zone
family indexed by a named-member domain (`square[cell] : Cell<cell>`)
subscripts only with `TCell`-typed expressions (`square[at]`, never
`square[7]`), while an integer-keyed family keeps the `TInteger` rule
(`cascade[3]`) — one mechanism, both member kinds, each rejecting the
other's key. Two cells compare by equality (`at is at2`); a cell against
an integer (`at is 3`), cell ordering (`at < at2`), and cell arithmetic
(`at + 1`) are type errors — a cell name is an opaque member, with no
order, successor, or arithmetic (adjacency, where a game needs it,
arrives as declared board data, not an algebra on cell names —
[design-notes/positional-zones.md](../design-notes/positional-zones.md),
"Adjacency"). `place(at : cell)` enumerates one placement action per
cell, in member order, exactly as an integer position parameter
enumerates its range.

**The cell/line query register.** The bare quantifier forms range a
binder over any declared position domain ("Position domains and
positional zones") and, but for the set, over the board's direction
domain (below); the board adds two collection forms and the
`lines(k)` call that feeds them. A bare form's noun is the domain name,
validated against the game's declared domains (a board's `cell`, an
integer `positions { }` name) and the board's direction domain `dir`,
with `any` taking the singular noun and `all`, `number of` and the set
the plural:

```text
any cell where square[cell] is empty
all cells where square[cell] is not empty
number of cells where <pred>
cells where <pred>
```

The last is the register's Set Form, the twin of `players where
<pred>`: the members of the domain satisfying the predicate, in the
Position Domain's member order, as a collection — `Collection<Cell>` over
a board's `cell`, `Collection<Integer>` over an integer domain (`columns
where <pred>`). It compares by value with a Region Verb's collection
(`(cells where cell in home(0)) is home(0)`) and meets every other
consumer as one does. The Set Form gathers positions, so `dirs where` is
refused naming the direction domain.

```cardlang-fragment cell_set
function stones_of(p : Player) = cells where holds(cell, p)
```

An unknown noun is a diagnostic naming the declared domains, and a noun
naming a name of another kind (a zone, a state variable, a definition, a
reserved word) is refused saying what the name is, with the sentence that
checks where the kind has one. A bare `line` on a board is guided to the
collection form.

Every query kind has a collection form too, as the card register has every
one over `in <zone>`: `any`, `all`, `number of` and the set, each over `in
<collection>`, the noun one of the game's position domains or the board's
`line`. ADR-0017 records the ruling and the twin refusing the collection
set that it replaced.

```text
any cell in home(p) where square[cell] is empty
number of cells in line where square[cell] is empty
cells in home(p) where holds(cell, p)
number of lines in lines(3) where <pred>
```

The collection set is the members of its source satisfying the predicate,
in the source's order; the collection count is how many of them do, and
its `where` is mandatory (with it optional, `number of cells in cells
where P` would read two ways). A collection form's source is a collection
of its noun's members: a collection of cells or a line for `cell`, of
lines for `line` (a collection noun only where the game has a board), of
the domain's Integers for an integer domain, whose type every Integer
shares, so a source holding a non-member, or `none`, is refused at play,
at the query. A card zone is no such source, and a zone named under a noun that
is no position domain is refused naming `cards in <zone> where <pred>`. A
membership's right side sits below the query forms, so `at in cells where
<pred>` reads as the collection set over `at`; where `at` names a value
in scope, it is refused naming the sentence that checks: the
parenthesized membership, `at in (cells where <pred>)`, where the source
is a query's own noun, and the membership joined with `and`, `at in
mine and <pred>`, elsewhere. A library's collection form names no
position domain of the game it is used by, as its bare form names none.
`lines(k)` is the native call the board's declared length-`k` lines are
read through — on a grid every straight run of `k` cells along a row,
column, or diagonal, on a family with declared adjacency every straight
run of `k` points along it within one file or rank — returning a
collection of `TLine`, each an ordered tuple of cells; `grid(3, 3)`'s
`lines(3)` is the eight tic-tac-toe lines, and `morris9`'s the sixteen
mills. A family declares the lengths it answers (a grid every `k` up to
its longer side, `morris9` only `3`), and a literal `k` it does not
declare is a resolve error; a family that declares no lines
(`hex_rhombus`, `draughts`) refuses the call; `lines(...)` in a boardless
game is rejected naming `board:`.

```text
any line in lines(3) where all cells in line where square[cell] is not empty
```

Tic-tac-toe is the corpus witness
([games/tic-tac-toe.md](../games/tic-tac-toe.md)): `board: grid(3, 3)`,
`pieces: xo_marks`, the nine `square[cell]` cells, `place(at : cell)`,
and the win test `any line in lines(3) where all cells in line where …`.

### Transfer: directions, frames, and the class-1 verbs

Where tic-tac-toe only *places* pieces, a game whose pieces *move*
declares a move parameterized by a **movement direction** as well as a
cell. A board with a movement frame mints a second named-member domain,
`dir`, whose members are the frame's seat-relative directions: on a grid
the forward directions `ahead`, `ahead_left` and `ahead_right`, on a
draughts board the four diagonals `ahead_left`, `ahead_right`,
`back_left` and `back_right`:

```text
move_type step(from : cell, along : dir) { when: … effect { … } }
```

`dir` is a separate source from the `positions { }` union. A direction
is not a position, so `dir` never reaches the zone index or `for each`;
it is a closed domain, so the bare quantifier family and the declared-type
positions admit it, typed `TDir`: a move parameter, `any dir where`,
`all dirs where` and `number of dirs where`, and the type of a function
parameter or an outcome payload. The Set Form gathers positions, so
`dirs where` is refused naming the direction domain. A game with no `board:` mints no `dir`,
and neither does a board whose family has no movement frame (`morris9`,
`hex_rhombus`); naming it at any of those positions is refused naming
`board:`, or the family and how a move on its board names a cell. Beside a
frameless board, `positions { dir : ... }` is an ordinary declared
position domain; beside a framed one it collides with the minted one.
`TDir` is distinct from `TCell`: `along is a1` (direction against cell),
`along is 3`, `along < along2`, and `along[…]` are all type errors, and a
direction member is not expression-nameable — naming `ahead` in an
expression is an unknown name, exactly as a cell name is (the meaning of
a direction is read through the verbs below, never a literal).
`step(from : cell, along : dir)` enumerates one action per (cell,
direction) pair, in member order, and a bare quantifier over `dir` reads
the same members in the same order.

```text
function can_jump(p : Player) =
  any cell where mine(cell, p) and (any dir where jump_ok(cell, dir, p))
```

**Per-player frames.** A frame's directions are seat-relative: `ahead` is
one player's forward and the other's backward, because the second seat's
frame is the 180-degree rotation of the first's — one shared board, a
declared per-player transform, never a second board. The transform is
folded into the class-1 verbs, which take the acting player and resolve
the direction in that player's frame. The closed Builtin verbs below read
the board's movement frame (`BOARD_VERB_NEEDS` in
`cardlang/builtins/functions.py` maps each board verb to the part it
reads), rejected in a boardless game naming `board:`, the `lines(k)`
Shadow Guards, and on a board with no frame naming its family:

- `neighbor(from, along, player)` — the cell one step along `along` in
  `player`'s frame, a `TCell`. It is **total**: an off-board step is a
  guarded contract, not a return value, so a guard demands `has_step`
  before reading `neighbor` (`and` short-circuits, so `neighbor` is never
  evaluated off the board).
- `has_step(from, along, player)` — whether that step stays on the board.
- `is_diagonal(along)` — whether a step along `along` changes file (the
  capturing directions on a grid, where straight steps do not capture).
- `is_forward(along)` - whether a step along `along` advances toward the
  far rank: true of every grid direction and of a draughts board's two
  `ahead_*` members, so a man's step and a king's are told apart by it.
  It reads no seat: each seat's frame faces its own far rank.
- `home(player)` and `far_row(player)` - a player's setup region, the
  cells of its back ranks (two on a grid, three on a draughts board), and
  the cells of the opposite edge (a reach-to-win goal, or the king-row),
  each a `Collection<Cell>` the cell membership and quantifier forms
  consume.

**`for each cell` and cell membership.** Setup that fills a region
iterates it: `for each cell c: <stmt>` runs the body once per board cell,
binding `c` as a `TCell`, and a membership guard narrows it to a region.
This lifts the `for each <position>` gap for a board's named-member
domain only — an integer `positions { }` domain (`for each column`) stays
guarded, the split being named-member versus integer:

```text
for each cell c: if c in home(0) { move one piece from reserve[0] to square[c] }
```

**Displacement capture and reach.** Capture is two ordinary kernel
transfers — the captured piece to a `captured[player]` pile, then the
mover — so it emits through the existing observation sites with no new
machinery. A reach-to-win test reads the just-moved piece's destination
against `far_row(actor)`; a wipe-out win reads the opponent's piece
count. **The opponent of the actor is a game `function`, e.g.
`function opponent_of(p : Player) = if p is 0 then 1 else 0`, not a `for
each player p: if p is not actor` guard: inside a `for each player` body
the acting player IS the bound seat `p`, so `p is not actor` compares the
actor against a second name for the actor** — refused at resolve as an
always-false comparison ("Naming the acting player twice"), which is why a
"the other seats" idiom names a seat directly (`opponent_of`) or captures
the actor first (`let w = actor`, tic-tac-toe's spelling). Breakthrough is the corpus witness
([games/breakthrough.md](../games/breakthrough.md)): 8x8, sixteen pieces a
side, `step` with diagonal-only capture, and the two termini its oracle
names.

**Guards stated as behavior.** A bare cell name in an expression (`a1`),
or a direction name (`ahead`), is an unknown name, not a literal —
named only through a parameter or a quantifier binder; naming a specific
cell in a setup or rule waits on its witness (issue #111).
A position domain is not a state index, the direction domain `dir` is
not a `state` type, and an integer position domain is not a `for each`
role.
The remaining board-topology surface — the `HiddenCell` and `Point`
zone-type rows, double-indexed families, `roll` chance, probes,
`region`, in-file boards — is guarded per rung of the board-topology
ladder ([design-notes/board-topology.md](../design-notes/board-topology.md);
issue #124).

### Declared adjacency, and which family answers which verb

A family whose points are not a grid declares its topology as data on
its registry entry rather than as geometry. `board: morris9` mints `cell`
with the twenty-four points of the mill board, named in the WMD notation
and ordered row-major from `a1`; its declared adjacency joins three
concentric squares at their side midpoints ([library.md](../library.md),
"Built-in boards"). `neighbors(c)` returns the points joined to `c`, in
board order, as a `Collection<Cell>` — the `home(p)` shape — so the
membership form and a quantifier narrowed by membership consume it:

```text
move_type slide(from : cell, to : cell) {
  when: (point[from] is not empty) and (point[to] is empty) and (to in neighbors(from))
  effect { move one piece from point[from] to point[to] }
}
function can_slide_from(c : cell) = any cell where (cell in neighbors(c)) and (point[cell] is empty)
```

The collection form reads the same fact without the membership,
`any cell in neighbors(c) where point[cell] is empty`.

`board: hex_rhombus(n)` mints `cell` with the n-by-n hexagons of a Hex
board, named and ordered as the grid names its cells (`a1` row-major to
`k11` at n = 11), and declares their six-neighbour adjacency: a hexagon
touches the cells beside it along its rank, above and below it in its
file, and the up-left and down-right diagonal (`b1` touches `a2`; `a1`
does not touch `b2`), so `neighbors(c)` reads it. It also declares each
seat's two **borders**, the board edges a connection game joins:
`near_edge(p)` and `far_edge(p)`, each a `Collection<Cell>` in board order.
Seat 0 joins rank 1 (`near_edge(0)`) to the last rank (`far_edge(0)`), and
seat 1 file `a` to the last file; each corner hexagon belongs to both of
its edges, so the two near borders share `a1` and the two far borders the
opposite corner. It declares no lines and no movement frame.

`board: draughts(width, height)` mints `cell` with the playable squares of
a draughts board: the square at the top-left corner is never played, so at
8x8 `a1` is, and the thirty-two dark squares are the cells. The playable
region is the family's entry data, its cell list, never a guard over the
whole rectangle, so no light square reserves an action id. Its movement
frame has the four diagonals, two of them backward, and a step from a cell
lands on a cell or off the board; its homes are each seat's back three
ranks and its `far_row` the king-row. It declares no lines and no
adjacency.

**A board verb is answered by the families that declare what it reads.**
Each verb reads one part of its board's entry: `lines` the line lengths
the family declares, `neighbors` and `connected` its declared adjacency,
`neighbor`, `has_step`, `is_diagonal`, `is_forward`, `home` and `far_row`
its movement frame -- as does the direction domain `dir` -- and
`near_edge` and `far_edge` each seat's borders. A family declares only the
parts it has:

| family        | `lines(k)`                | `neighbors`, `connected` | the frame verbs and `dir` | `near_edge`, `far_edge` |
|---------------|---------------------------|--------------------------|---------------------------|-------------------------|
| `grid`        | `k` up to its longer side | refused                  | answered                  | refused                 |
| `morris9`     | `k = 3`, the mills        | answered                 | refused                   | refused                 |
| `hex_rhombus` | refused                   | answered                 | refused                   | answered                |
| `draughts`    | refused                   | refused                  | answered                  | refused                 |

A call on a family that does not declare its verb's part is refused at
the call, naming the board and the verbs it answers; reached through a
family library, it is refused on the game's `uses` line. A verb taking a
seat (`neighbor`, `has_step`, `home`, `far_row`, `near_edge`, `far_edge`)
reads the board from one of its two seats, so a game calling one declares
`players: 2`. The mills are
never a second list beside the adjacency: an adjacency family's lines are
the straight runs along its edges, so a line off the edges cannot be
written.

**Whether two cell sets join is a Builtin that owns its loop.** The
expression register has no loop and no recursion, so reachability is the
verb `connected(from, to, via) : Boolean`, each argument a
`Collection<Cell>`: true exactly when some cell of `from` reaches some cell
of `to` along the board's declared adjacency with every cell of the path,
both ends included, in `via`. A game writes no fixed point of its own;
Hex's win is one sentence over a predicate naming a seat's stones:

```cardlang-fragment connected
function joined(p : Player) = connected(near_edge(p), far_edge(p), cells where holds(cell, p))
```

The search is breadth first, seeded with `from`'s cells in `via` in
`from`'s order and taking each cell's neighbours in board order, and it
expands each cell at most once, so it ends within the board's cell count by
construction. It reads only the declared adjacency and its three
arguments, never a zone or a draw: the zones a game asks about are read by
the argument expressions, which the Hidden Read Owner Guard judges where
they are written. An empty `via`, or a `from` with no cell in `via`, is
false; a cell in all three is true. The connectivity is the family's
declaration, never a call-site argument, so a family that declares no
adjacency refuses the verb as it refuses `neighbors`. An optional set of
cells checks where a set of cells does, and a none argument, or a none
inside one, is refused at play; so is a value reaching the verb through the
Permissive Top that is not a collection of the board's cells. A set-valued sibling (`region`) is not the
language: it waits for the game that needs a region as a value.

Hex is the corpus witness ([games/hex.md](../games/hex.md)) for the hex
family, its borders, the Set Form and the fixed point together:
`board: hex_rhombus(11)`, `pieces: hex_stones`, the 121 `tile[cell]`
cells, `place(at : cell)`, and the win test `connected(near_edge(actor),
far_edge(actor), cells where holds(cell, actor))`, asked once per
placement.
