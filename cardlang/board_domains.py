"""The one seam that reads a game's position domains as name -> members.

A game's quantifiable position domains are the union of its declared
`positions { }` block (integer members) and its `board:` clause (the minted
`cell` domain, string members) -- decisions.md "Boards and cells". Resolve
appends the board-minted domain into `Game.positions` as a named-member
`PositionDecl` (`_resolve_board`), so on a RESOLVED game the union is exactly
`Game.positions`.

Both consumers that build a `DomainSources.positions` -- `runtime/driver.py`
(the live candidate enumeration) and `openspiel/encoding.py` (the static
action space) -- call this one function rather than each writing the
`{p.name: p.members ...}` comprehension, so the runtime and the advertised
action space cannot diverge. A leaf module (it imports only the AST) so both
the runtime and the OpenSpiel front end read it without a cycle.
"""

from __future__ import annotations

from typing import Mapping

from cardlang.ast import nodes as n

# The name of the position domain a `board:` clause mints. Fixed (no game
# names its board's domain); the collision walls in resolve keep it from
# clashing with a declared `positions { }` name or a built-in spelling.
BOARD_DOMAIN = "cell"


def position_domains_of(game: n.Game) -> Mapping[str, tuple[int, ...] | tuple[str, ...]]:
    """A resolved game's position domains: name -> ordered members. Integer
    domains (`positions { }`) carry their inclusive range; the board-minted
    `cell` domain carries its cell names. `PositionDecl.members` returns the
    right member kind for each, so this reads uniformly over the union resolve
    already assembled in `game.positions`."""
    return {p.name: p.members for p in game.positions}
