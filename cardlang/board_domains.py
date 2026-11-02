"""The one seam that reads a game's position domains as name -> members.

A game's quantifiable [[position-domain]]s are the union of its declared
`positions { }` block (integer members) and its `board:` clause (the minted
`cell` domain, string members) -- decisions.md "Boards and cells". Resolve
appends the board-minted domain into `Game.positions` as a named-member
`PositionDecl` (`_resolve_board`), so on a RESOLVED game the union is exactly
`Game.positions`.

Both consumers that build a `DomainSources.positions` -- `runtime/driver.py`
(the live [[candidate]] enumeration) and `openspiel/encoding.py` (the static
action space) -- call this one function rather than each writing the
`{p.name: p.members ...}` comprehension, so the runtime and the advertised
action space cannot diverge. A leaf module (it imports only the AST) so both
the runtime and the OpenSpiel front end read it without a cycle.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a resolved game, whose `board:` clause `board_entry` accepts.
Establishes:  a game's position domains and its direction domains, each
              read from one source; the `dir` domain exists exactly where
              the board's family has a movement frame.
Now illegal:  a `dir` member read from anywhere but the board entry's frame.
Held by:      Unrepresentable -- `BoardEntry.frame` is optional and
              `board_directions` is its one reader for `dir`, so a frameless
              board's direction source is empty by construction.
"""

from __future__ import annotations

from collections.abc import Mapping

from cardlang.ast import nodes as n
from cardlang.stdlib.boards import BoardEntry, board_entry

# The name of the position domain a `board:` clause mints. Fixed (no game
# names its board's domain); the collision Owner Guards in resolve keep it
# from clashing with a declared `positions { }` name or a built-in spelling.
BOARD_DOMAIN = "cell"

# The name of the SECOND domain a `board:` clause mints where its family has a
# movement frame -- the movement directions (decisions.md "Boards and cells",
# rung-2 movement). Unlike
# `cell`, `dir` is NOT injected into `game.positions`: it is a separate
# per-game source (`directions_of`), so the zone-index and `for each` Owner
# Guards, which read `game.positions`, reject `dir` for free -- a direction is
# not a position. It is a closed domain, so the move parameter, the bare
# quantifier and the declared types of function parameters and outcome
# payloads admit it (`resolve._minted_directions`). The collision Owner Guard in
# `_resolve_board` keeps it from clashing with a declared `positions { }`
# name (the `cell` twin); `direction` is a reserved clause keyword and the
# turn-order enum's tag, hence `dir`.
DIRECTION_DOMAIN = "dir"

# The noun the board's lines are quantified by in the collection forms
# (`any line in lines(3) where …`): no Position Domain, a collection noun
# alone (decisions.md "Boards and cells").
LINE_NOUN = "line"


def position_domains_of(game: n.Game) -> Mapping[str, tuple[int, ...] | tuple[str, ...]]:
    """A resolved game's position domains: name -> ordered members. Integer
    domains (`positions { }`) carry their inclusive range; the board-minted
    `cell` domain carries its cell names. `PositionDecl.members` returns the
    right member kind for each, so this reads uniformly over the union resolve
    already assembled in `game.positions`."""
    return {p.name: p.members for p in game.positions}


def directions_of(game: n.Game) -> Mapping[str, tuple[str, ...]]:
    """A resolved game's movement-direction domains: name -> ordered members.
    A `board:` clause whose family has a movement frame mints the single `dir`
    domain (its seat-relative forward directions); a boardless game, and a
    board with no frame (`morris9`), have none. The SIBLING of
    `position_domains_of` for the SEPARATE `dir` source (decisions.md "Boards
    and cells", rung-2 movement).

    Unlike `position_domains_of`, the members are NOT stored in the AST (`dir`
    is deliberately absent from `game.positions`), so this reads them off the
    board family entry -- the SAME `board_entry` the driver and the OpenSpiel
    encoding instantiate, so the runtime candidate enumeration and the static
    action space cannot diverge. `board_entry` is total on a resolved game
    (resolve validated the family/args).

    Held by: Unrepresentable. `BoardEntry.frame` is optional and
    `board_directions` is the one reader of it for `dir`, so a frameless
    board's direction source is empty by construction and every position
    admitting `dir` (`resolve._minted_directions`) refuses it."""
    if game.board is None:
        return {}
    return board_directions(board_entry(game.board.family, game.board.args))


def board_directions(entry: BoardEntry) -> Mapping[str, tuple[str, ...]]:
    """The direction domains a built board mints: `dir` with its frame's
    directions where the family has a movement frame, none where it has not.
    The one reader of `BoardEntry.frame` for `dir`, which `directions_of` and
    resolve's checks of a declared board both ask."""
    if entry.frame is None:
        return {}
    return {DIRECTION_DOMAIN: entry.directions()}
