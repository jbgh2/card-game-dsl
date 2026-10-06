"""A position that counts demands an Integer.

property:   an operand written where the language counts -- how many cards a
            movement moves, how big a subset is, a `choose integer` bound or
            exclusion -- is refused at check time unless it types as an
            Integer, located at the line and naming what the position counts;
            a literal count below its floor is refused too (a movement moves 0
            or more, a subset holds 1 or more; the choose bounds' floor is
            `resolve._check_chooses`'); a non-Integer count reaching the
            executor through the permissive top is refused at play time
domain:     count position {movement amount, subset size, choose lower bound,
            choose upper bound, choose exclusion} x operand type {Integer
            literal, Integer variable, Boolean comparison, Boolean literal,
            Suit, Player}; an index is a position, not a count, and its
            demand is tests/test_positional_index.py's
registry:   positions: the Integer rows of
            `tests.test_typed_positions.TREATMENT`, pinned against
            `COUNT_POSITIONS` by `test_every_count_field_has_a_row`
does not prove:  a range on a computed count, which is a playout's to refuse
            (the executor's amount guard and the subset domain's size guard).
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from tests.test_typed_positions import TREATMENT


def _game(stmt: str) -> str:
    return f"""game G {{
  players: 2
  max_length: 100
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard }}
  state {{ m[player] : Integer = 0  k : Integer = 2  dealer : Player = 0 }}
  phase play {{
    shuffle deck
    {stmt}
  }}
  winner: highest m
}}"""


COUNT_POSITIONS: dict[tuple[type, str], str] = {
    (n.Transfer, "amount"): "deal {x} cards from deck to each hand",
    (n.SubsetQuery, "count"): (
        "deal 3 cards from deck to each hand\n"
        "    if any subset of {x} cards in hand[0] where 1 is 1 {{ m[0] := 1 }}"
    ),
    (n.Choose, "lo"): "for each player p: m[p] := choose integer in {x} .. 5",
    (n.Choose, "hi"): "for each player p: m[p] := choose integer in 0 .. {x} up to 5",
    (n.Choose, "excluding"): (
        "for each player p: m[p] := choose integer in 0 .. 5 excluding {x}"
    ),
}

# (spelling, accepted): an Integer is the only operand type a count takes.
OPERANDS: tuple[tuple[str, bool], ...] = (
    ("2", True),
    ("k", True),
    ("(13 > 2)", False),
    ("true", False),
    ("hearts", False),
    ("dealer", False),
)

# A literal upper bound IS the ceiling, so `up to` beside one is refused for
# that reason (tests/test_choose_ceiling.py); the cell would test the wrong arm.
_SKIP = {((n.Choose, "hi"), "2")}

CELLS = [
    pytest.param(pos, spelling, accepted, id=f"{pos[0].__name__}.{pos[1]}-{spelling}")
    for pos in COUNT_POSITIONS
    for spelling, accepted in OPERANDS
    if (pos, spelling) not in _SKIP
]


@pytest.mark.parametrize(("pos", "spelling", "accepted"), CELLS)
def test_a_count_position_takes_only_an_integer(
    pos: tuple[type, str], spelling: str, accepted: bool
) -> None:
    src = _game(COUNT_POSITIONS[pos].format(x=spelling))
    if accepted:
        check_dsl(src, "g.cardlang")
        return
    with pytest.raises(DiagnosticError, match="(expects|expected) an Integer"):
        check_dsl(src, "g.cardlang")


def test_every_count_field_has_a_row() -> None:
    """The registry pin: every position the typed-position table requires an
    Integer of has a row here, except a subscript's index, whose Integer
    demand holds on an unkeyed receiver only (tests/test_positional_index.py).

    red under: add a `("Turns", "until"): (GRADUAL, "Integer")` row to
    `TREATMENT` in place of its Boolean one."""
    derived = {
        position
        for position, (_, required) in TREATMENT.items()
        if required == "Integer"
    }
    assert derived == {(node.__name__, field) for node, field in COUNT_POSITIONS}


def test_a_comparison_as_a_deal_count_is_refused_at_its_line() -> None:
    """The issue's sentence on a corpus game: `deal (13 > 2) cards` dealt one
    card a hand and played on."""
    with open("docs/games/hearts.cardlang") as fh:
        src = fh.read().replace(
            "deal 13 cards from deck", "deal (13 > 2) cards from deck", 1
        )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "hearts.cardlang")
    assert "hearts.cardlang:53:" in str(ei.value)
    assert "how many cards to move" in str(ei.value)


@pytest.mark.parametrize(
    ("stmt", "needle"),
    [
        ("deal -1 cards from deck to each hand", "moves fewer than none"),
        (COUNT_POSITIONS[(n.SubsetQuery, "count")].format(x="0"), "holds at least one"),
        (COUNT_POSITIONS[(n.SubsetQuery, "count")].format(x="-2"), "holds at least one"),
    ],
)
def test_a_literal_count_below_its_floor_is_refused(stmt: str, needle: str) -> None:
    with pytest.raises(DiagnosticError, match=needle):
        check_dsl(_game(stmt), "g.cardlang")


def test_a_zero_movement_amount_is_accepted() -> None:
    check_dsl(_game("deal 0 cards from deck to each hand"), "g.cardlang")


def test_a_laundered_amount_is_refused_at_play() -> None:
    """The same wrongness behind the permissive top: the checker cannot see
    it, and the executor refuses it rather than dealing `true` as one card."""
    game = check_dsl(
        _game("deal (if true then (13 > 2) else 1) cards from deck to each hand"),
        "g.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="not an Integer"):
        play_game(game, random.Random(0))
