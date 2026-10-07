"""A position in a collection is an Integer inside it.

property:   an index on a positional collection (one with no key: a `[...]`
            list, a board region, a query result) is refused at check time
            unless it is an Integer, refused when it is a negative literal,
            and refused when it is a literal at or past the collection's
            length where the sentence states that length; a zone is not
            addressed by position at all; a computed index the checker cannot
            bound is refused at play time in the runtime's typed channel,
            never read from the end, and a Boolean reaching any index, count
            or arithmetic through the permissive top never acts as 1
domain:     receiver {`[...]` list, `home(p)`, `far_row(p)`, `lines(k)`} x
            index {first, last, one past the last, far past, negative literal,
            Boolean, Player, String}; a zone receiver; a computed index at
            play; a laundered Boolean at an index, a key, an arithmetic operand
            and a compound assignment
registry:   the receivers whose length a sentence states:
            `resolve._REGION_CALL_FUNCS` (the board verbs returning an unkeyed
            collection, each a `BoardEntry` method, pinned below) and `n.ListLit`
does not prove:  a static range on a collection whose length the sentence
            does not state where it is indexed (a query result, a `let`-bound
            list, `all players`); that is the runtime guard's, executed in
            `test_a_computed_index_past_the_end_is_refused_at_play`.
"""

from __future__ import annotations

import random

import pytest

from cardlang import resolve
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.stdlib.boards import board_entry
from tests.test_movement_verbs import _board_game

# receiver spelling -> (its length on a grid(8, 8), the guard sentence reading
# one of its members at `{i}`)
RECEIVERS: dict[str, tuple[int, str]] = {
    "list": (2, "square[[from, from][{i}]] is empty"),
    "home": (16, "square[home(actor)[{i}]] is empty"),
    "far_row": (8, "square[far_row(actor)[{i}]] is empty"),
    "lines": (len(board_entry("grid", (8, 8)).lines(3)), "all cells in lines(3)[{i}] where square[cell] is empty"),
}


def _indexes(length: int) -> list[tuple[str, str, bool]]:
    return [
        ("first", "0", True),
        ("last", str(length - 1), True),
        ("one past", str(length), False),
        ("far past", str(length + 90), False),
        ("negative", "-1", False),
        ("boolean", "true", False),
        ("player", "actor", False),
        ("string", '"zz"', False),
    ]


CELLS = [
    pytest.param(receiver, spelling, accepted, id=f"{receiver}-{label}")
    for receiver, (length, _) in RECEIVERS.items()
    for label, spelling, accepted in _indexes(length)
]


@pytest.mark.parametrize(("receiver", "spelling", "accepted"), CELLS)
def test_a_positional_index_is_an_integer_inside_the_collection(
    receiver: str, spelling: str, accepted: bool
) -> None:
    src = _board_game(guard=RECEIVERS[receiver][1].format(i=spelling))
    if accepted:
        check_dsl(src, "board.cardlang")
        return
    with pytest.raises(DiagnosticError, match="position"):
        check_dsl(src, "board.cardlang")


def test_every_region_verb_is_a_board_method() -> None:
    """The lengths are read off the board by the verb's own name.

    red under: rename `BoardEntry.far_row` in cardlang/stdlib/boards.py."""
    assert resolve._REGION_CALL_FUNCS
    entry = board_entry("grid", (8, 8))
    for fn in resolve._REGION_CALL_FUNCS:
        assert callable(getattr(entry, fn, None)), fn


def test_a_computed_index_past_the_end_is_refused_at_play() -> None:
    """A computed position the checker cannot bound: refused by the runtime's
    Owner Guard rather than read from the end of the row."""
    src = _board_game(
        guard="square[far_row(actor)[k]] is empty",
    ).replace("score[player] : Integer = 0", "score[player] : Integer = 0  k : Integer = -1")
    game = check_dsl(src, "board.cardlang")
    with pytest.raises(OwnerGuardError, match="outside a collection"):
        play_game(game, random.Random(0))


@pytest.mark.parametrize("read", ["hand[0][0]", "z[0]"])
def test_a_zone_is_not_addressed_by_position(read: str) -> None:
    """A zone family member types as a card collection, but its cards are not
    addressed by position: refused at check time, naming the reads that are."""
    src = f"""game Z {{
  players: 2
  max_length: 50
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    deal 2 cards from deck to each hand
    let z = hand[0]
    if {read} is A of spades {{ score[0] := 1 }}
  }}
  winner: highest score
}}"""
    with pytest.raises(DiagnosticError, match="not addressed by position"):
        check_dsl(src, "z.cardlang")


_LAUNDERED = "(if true then (1 > 0) else 1)"


@pytest.mark.parametrize(
    "stmt",
    [
        f"score[0] := [10, 20, 30][0 + {_LAUNDERED}]",
        f"score[{_LAUNDERED}] += 5",
        f"score[0] += {_LAUNDERED}",
        f"deal (1 + {_LAUNDERED}) cards from deck to each hand",
    ],
)
def test_a_laundered_boolean_never_acts_as_one(stmt: str) -> None:
    """A Boolean the checker cannot see -- an `if` whose branches do not join
    types as the permissive top -- is refused where it would count, index or
    key as 1, in the runtime's typed channel."""
    src = f"""game L {{
  players: 2
  max_length: 50
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    shuffle deck
    {stmt}
  }}
  winner: highest score
}}"""
    game = check_dsl(src, "l.cardlang")
    with pytest.raises(OwnerGuardError):
        play_game(game, random.Random(0))


def test_an_invalid_board_is_reported_not_crashed_on() -> None:
    """A region read on a board the clause cannot mint: the static length has
    no board to count, and the board clause's own diagnostic is reported."""
    src = _board_game(guard="square[home(actor)[0]] is empty").replace(
        "board: grid(8, 8)", "board: grid(0, 8)"
    )
    assert "grid(0, 8)" in src
    with pytest.raises(DiagnosticError):
        check_dsl(src, "board.cardlang")


def test_a_position_typed_as_the_top_is_refused_at_its_line() -> None:
    """An unkeyed receiver's position must type exactly Integer."""
    src = _board_game(guard="square[home(actor)[(if true then (1 > 0) else 1)]] is empty")
    with pytest.raises(DiagnosticError, match="types as `Any`"):
        check_dsl(src, "board.cardlang")
