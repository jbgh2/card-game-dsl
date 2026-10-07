"""A per-player map is refused where a collection of cards is read.

property:   a keyed collection -- an indexed `let`, a per-seat state variable --
            written where the language reads a collection's elements is
            refused at check time, naming the key, because the runtime holds
            it as a map and reading its elements reads the keys (the seat ids)
            instead of any card
domain:     element-reading position {a Builtin's collection parameter, a
            declared Primitive's collection parameter, an aggregation's
            `over cards in` source, an `is empty` test, a turn ring's
            participants} x argument {a zone, an unkeyed `[...]`
            list bound by a `let`, an indexed `let` keyed by Player}
registry:   positions: the callers of `typecheck._refuse_keyed_elements` (the
            Call arm, `_check_card_source`, `_check_is_check`,
            `_check_participants`)
does not prove:  a keyed map reached through the permissive top (an `if`
            whose branches do not join), whose shape the checker cannot see
            (issue #116). The `in` membership position refuses a keyed map for
            its own reason (keys or values?) beside `_check_membership_operands`.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

_PRIMITIVE = "gin_valid_meld(cards : Collection<Card>) : Boolean"

POSITIONS: dict[str, tuple[str | None, str]] = {
    "builtin parameter": (None, "if top_of({x}) is A of spades {{ score[0] := 1 }}"),
    "primitive parameter": (
        _PRIMITIVE,
        "score[0] := if gin_valid_meld({x}) then 1 else 0",
    ),
    "aggregation source": (None, "score[0] := sum of 1 over cards in {x}"),
    "emptiness": (None, "if {x} is empty {{ score[0] := 1 }}"),
}

# The participants of a turn ring read a collection of players; a per-seat map
# would be iterated by its keys, so a team-keyed one skips the other seats.
PARTICIPANTS: dict[str, tuple[str, bool]] = {
    "all players": ("all players", True),
    "player list": ("[0, 1]", True),
    "seat-keyed map": ("score", False),
}

ARGUMENTS: dict[str, tuple[str, bool]] = {
    "zone": ("hand[0]", True),
    "list": ("pair", True),
    "keyed let": ("probe", False),
}


def _game(block: str | None, stmt: str) -> str:
    clause = "" if block is None else f"  primitives {{ {block} }}\n"
    return f"""game G {{
  players: 2
  max_length: 50
  cards: standard52
{clause}  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    shuffle deck
    deal 2 cards from deck to each hand
    let probe[p] = A of spades
    let pair = [A of spades, K of hearts]
    {stmt}
  }}
  winner: highest score
}}"""


CELLS = [
    pytest.param(pos, arg, id=f"{pos}-{arg}") for pos in POSITIONS for arg in ARGUMENTS
]


@pytest.mark.parametrize(("position", "argument"), CELLS)
def test_a_keyed_map_is_refused_where_elements_are_read(
    position: str, argument: str
) -> None:
    block, template = POSITIONS[position]
    spelling, accepted = ARGUMENTS[argument]
    src = _game(block, template.format(x=spelling))
    if accepted:
        check_dsl(src, "g.cardlang")
        return
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    msg = str(ei.value)
    assert "keyed by Player" in msg and "the keys" in msg, msg


@pytest.mark.parametrize("argument", list(PARTICIPANTS))
def test_a_turn_ring_takes_its_players_from_an_unkeyed_collection(argument: str) -> None:
    spelling, accepted = PARTICIPANTS[argument]
    src = _game(
        None,
        f"turns t from 0 over {spelling} until score[0] >= 1 {{ score[0] += 1 }}",
    )
    if accepted:
        check_dsl(src, "g.cardlang")
        return
    with pytest.raises(DiagnosticError, match="keyed by Player"):
        check_dsl(src, "g.cardlang")
