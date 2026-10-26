"""A round-slot name written outside its slot is told which slot it belongs to.

property:        A name only a round slot reads — a walled Primitive (a climb
                 lead or follows query, an early-termination predicate, a
                 game-local trick winner) or a trick winner — written as a call,
                 a bare name, or the `winner:` clause's state variable is
                 refused with its
                 slot's sentence, the one the `primitives { }` block gives the
                 same name, never as an unknown function or variable.
domain:          The expression positions, a call and a bare name: every name
                 of every `WALLED_NAMESPACES` label crossed with both regimes, a
                 game writing a `primitives { }` block and a game writing none.
                 The `winner:` position: every walled name and every name in
                 `VALUE_NAMES`. A trick winner in an expression has its own
                 sentence and pin (tests/test_bare_callback_names.py). A
                 library's reference to these names is answered by the
                 library's own refusal (tests/test_library_round_slot_primitives.py).
registry:        names and labels: `cardlang.primitives_block.WALLED_NAMESPACES`,
                 `cardlang.builtins.functions.VALUE_NAMES`; regimes:
                 `cardlang.primitives_block.Regime`; the block-position
                 refusal: tests/test_primitives_block.py::test_a_walled_namespace_name_cannot_be_declared.
held by:         a single owner — resolve's `_slot_name_outside_slot` is the one
                 sentence every expression position and the `winner:` clause
                 ask, over `walled_namespace_of`, the lookup the block asks too;
                 this grid is a Pin over its consumers.
does not prove:  Anything about the slot positions themselves, which accept
                 these names (tests/test_round_forms.py and each round form's
                 own grids).
"""

from __future__ import annotations

import pytest

from cardlang.builtins.functions import VALUE_NAMES
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import WALLED_NAMESPACES, Regime, regime
from tests.test_primitives_block import _PINOCHLE_ENTRY, _game

_BLOCKS: dict[Regime, str | None] = {Regime.DECLARED: _PINOCHLE_ENTRY, Regime.LEGACY: None}

# The two expression positions a name can be written in, as the probe body.
_POSITIONS: dict[str, str] = {
    "call": "    score[0] := if {name}(0) then 1 else 0",
    "bare name": "    score[0] := if {name} then 1 else 0",
}

CELLS = [
    (label, name, mode, position)
    for label, names in WALLED_NAMESPACES.items()
    for name in sorted(names)
    for mode in Regime
    for position in _POSITIONS
]


def test_the_regimes_are_the_two_the_probe_writes() -> None:
    """The regime axis is `Regime` whole, and each probe lands in the regime
    it names."""
    for mode, block in _BLOCKS.items():
        assert regime(check_dsl(_game(block), "probe.cardlang")) is mode
    assert set(_BLOCKS) == set(Regime)


@pytest.mark.parametrize(("label", "name", "mode", "position"), CELLS)
def test_a_walled_name_in_an_expression_is_told_its_namespace(
    label: str, name: str, mode: Regime, position: str
) -> None:
    source = _game(_BLOCKS[mode], body=_POSITIONS[position].format(name=name))
    with pytest.raises(DiagnosticError) as err:
        check_dsl(source, "probe.cardlang")
    message = str(err.value)
    assert label in message, message
    assert "unknown function" not in message and "unresolved name" not in message, message


WINNER_CELLS = sorted(frozenset().union(*WALLED_NAMESPACES.values()) | VALUE_NAMES)


@pytest.mark.parametrize("name", WINNER_CELLS)
def test_a_slot_name_as_the_winner_clause_is_told_its_slot(name: str) -> None:
    source = _game(None).replace("winner: highest score", f"winner: highest {name}")
    assert f"winner: highest {name}" in source
    with pytest.raises(DiagnosticError) as err:
        check_dsl(source, "probe.cardlang")
    message = str(err.value)
    assert "slot" in message and f"`{name}`" in message, message
    assert "unknown variable" not in message, message
    assert "declared in" not in message, message
