"""A callback name is read only in the slot that takes it.

property:   a trick-winner name written anywhere an
            expression stands is refused at check time, located at the name,
            naming the slot that takes it -- never classified as a value, so
            no function object reaches a state variable or a playout
domain:     callback name (`VALUE_NAMES`, exactly `TRICK_WINNER_NAMES`) x
            expression position {an
            assignment's value, a state default, a `let`, an `if` condition,
            a function body, `loser:`}
registry:   `cardlang.builtins.functions.VALUE_NAMES`; the slot is the
            `str`-typed field `TrickRound.winner_fn`, which a bare name never
            reaches through an expression
does not prove:  anything about the slots themselves: a name in its own slot
            is the round resolver's (`tests/test_round_resolve.py`).
"""

from __future__ import annotations

import pytest

from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    TRICK_WINNER_NAMES,
    VALUE_NAMES,
)
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

_STATE = "seen[player] : Integer = 0  s : Integer = 0"

POSITIONS: dict[str, tuple[str, str, str, str]] = {
    # position -> (state block, phase body, definitions, result clause)
    "assignment": (_STATE, "seen[0] := {name}", "", "winner: highest seen"),
    "state default": (
        _STATE + "  d : Integer = {name}", "seen[0] := 1", "", "winner: highest seen"
    ),
    "let": (_STATE, "let x = {name}\n    seen[0] := 1", "", "winner: highest seen"),
    "if condition": (
        _STATE, "if {name} is 0 {{ seen[0] := 1 }}", "", "winner: highest seen"
    ),
    "function body": (
        _STATE,
        "seen[0] := f()",
        "function f() = {name}",
        "winner: highest seen",
    ),
    "loser": (_STATE, "seen[0] := 1", "", "loser: {name}"),
}


def _game(position: str, name: str) -> str:
    state, body, defs, result = (
        part.format(name=name) for part in POSITIONS[position]
    )
    return f"""game G {{
  players: 2
  max_length: 50
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ {state} }}
  phase play {{
    {body}
  }}
  {result}
}}
{defs}
"""


def _slot(name: str) -> str:
    assert name in TRICK_WINNER_NAMES, name
    return "trick round's `winner`"


def test_the_names_partition_into_the_two_slots() -> None:
    """Every callback name has exactly one slot the refusal can name.

    red under: add a name to `VALUE_NAMES` in cardlang/builtins/functions.py
    outside `TRICK_WINNER_NAMES`."""
    assert VALUE_NAMES == TRICK_WINNER_NAMES
    assert VALUE_NAMES


CELLS = [
    pytest.param(position, name, id=f"{position}-{name}")
    for position in POSITIONS
    for name in sorted(VALUE_NAMES)
]


@pytest.mark.parametrize(("position", "name"), CELLS)
def test_a_bare_callback_name_is_refused_naming_its_slot(position: str, name: str) -> None:
    src = _game(position, name)
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    msg = str(ei.value)
    assert f"`{name}`" in msg and _slot(name) in msg, msg
    span = ei.value.diagnostic.span
    assert span is not None
    line = src.splitlines()[span.line - 1]
    assert line[span.column - 1 :].startswith(name), (line, span)


@pytest.mark.parametrize("name", sorted(VALUE_NAMES - BUILTIN_CALL_FUNCS))
def test_a_callback_name_called_like_a_function_names_its_slot(name: str) -> None:
    """`highest_of_led_suit()` is the same mistake with parentheses. A name
    that is also a callable Builtin (an Arrival Record call) is a real call,
    judged by its own signature."""
    src = _game("assignment", name).replace(f"seen[0] := {name}", f"seen[0] := {name}()")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert _slot(name) in str(ei.value), str(ei.value)
