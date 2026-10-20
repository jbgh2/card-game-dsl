"""A definition may not take a name a round slot reads.

property:   a callable a designer introduces -- a game `function`, a game's
            `primitives { }` entry, a family library's `function`, a library
            `requires` function row -- whose name a round's query slot reads
            is refused at check time, at the line that introduces it, naming
            the name. The game's own function is told the slot that reads the
            name, because that slot always runs the native one and never
            calls the function.
domain:     slot callback name x callable-introducing position. The name
            axis is every member of every `_ROUND_QUERY_REGISTRIES` set, each
            with the slot whose registry holds it. The position axis is every
            place a designer introduces a name that a call or a slot could
            mean: the game's `function` and `primitives { }` entry and a
            library's `function` (this module), and a library's `requires`
            function row (the contract module's native-name cells). A name
            that is also a callable native keeps the native-shadow refusal,
            whose sentence the game and library cells assert in its place.
            Every other introduction -- state, zones, `let`, binders,
            parameters, procedures, move types, phases -- holds a value or is
            run, never called or named in a slot, so sharing a slot
            callback's spelling changes nothing a round does.
registry:   names: `cardlang.resolve._ROUND_QUERY_REGISTRIES`; slot
            spellings: `cardlang.resolve._ROUND_QUERY_SLOT_SPELLINGS`;
            callable natives: `cardlang.builtins.functions.CALL_FUNCS`;
            slot axis against the reference-slot table:
            tests/test_library_round_slot_primitives.py::test_the_slot_axis_is_every_round_query_slot;
            the `requires` row position:
            tests/test_definition_contracts.py::test_a_function_row_named_like_a_native_function.
does not prove:  that a slot runs the native it names: the round resolver
            and the runtime own that (tests/test_round_resolve.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.builtins.functions import CALL_FUNCS
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.resolve import _ROUND_QUERY_REGISTRIES, _ROUND_QUERY_SLOT_SPELLINGS

_HOST = """game H {{
  {uses}
  players: 2
  cards: standard52
  ranking: aces high
  max_length: 100
  {primitives}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    round play_to_trick from 0 over all players source hand into pile
      winner highest_of_led_suit
    score[0] := 1
  }}
  winner: highest score
}}
{definitions}
"""

_LIBRARY = "docs/libraries/lib.cardlang"

NAMES = sorted(frozenset().union(*_ROUND_QUERY_REGISTRIES.values()))


def _host(*, uses: str = "", primitives: str = "", definitions: str = "") -> str:
    return _HOST.format(uses=uses, primitives=primitives, definitions=definitions)


def _whole_bag(exc: DiagnosticError) -> str:
    return "\n".join([str(exc), *getattr(exc, "__notes__", [])])


def _slot_of(name: str) -> tuple[type, str]:
    return next(key for key, names in _ROUND_QUERY_REGISTRIES.items() if name in names)


def _refused_at(src: str, file: str, line_start: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, file)
    span = exc.value.diagnostic.span
    assert span is not None
    assert src.splitlines()[span.line - 1].lstrip().startswith(line_start), span
    return _whole_bag(exc.value)


def test_every_query_slot_has_a_spelling() -> None:
    """The refusal names the slot from this table, so a slot added to the
    registries without a spelling has no sentence to be told in.

    red under: delete a row from `_ROUND_QUERY_SLOT_SPELLINGS`."""
    assert set(_ROUND_QUERY_SLOT_SPELLINGS) == set(_ROUND_QUERY_REGISTRIES)
    assert NAMES


def test_the_host_checks_clean() -> None:
    """The control every cell leans on, with and without an empty
    `primitives { }` block.

    red under: name an unknown zone in the host's round."""
    check_dsl(_host(), "h.cardlang")
    check_dsl(_host(primitives="primitives { }"), "h.cardlang")


@pytest.mark.parametrize("name", NAMES)
def test_a_game_function_named_like_a_slot_callback_is_refused(name: str) -> None:
    src = _host(definitions=f"function {name}(p : Player) = 1")
    message = _refused_at(src, "h.cardlang", f"function {name}(")
    if name in CALL_FUNCS:
        assert f"function '{name}' shadows the native function" in message, message
    else:
        slot = _ROUND_QUERY_SLOT_SPELLINGS[_slot_of(name)].format(name=name)
        assert f"function '{name}'" in message and slot in message, message


@pytest.mark.parametrize("name", NAMES)
def test_a_primitives_entry_named_like_a_slot_callback_is_refused(name: str) -> None:
    """Born green: `_check_primitive_name` refuses every slot callback, by
    the Builtin, walled-namespace or unimplemented arm.

    red under: return early from `_check_primitive_name` when the name is in
    `_ROUND_QUERY_REGISTRIES`'s union."""
    src = _host(primitives=f"primitives {{ {name}(p : Player) : Integer }}")
    message = _refused_at(src, "h.cardlang", "primitives {")
    assert f"'{name}'" in message or f"`{name}`" in message, message


def _with_library(monkeypatch: pytest.MonkeyPatch, name: str, body: str) -> str:
    """Point resolve at one synthetic library and return its `uses` line. The
    checker memoizes on the game's tree, so each cell's library is named for
    its cell and the importing game differs with it."""
    library_name = f"lib_{name}"
    library = parse_library(f"library {library_name} {{ {body} }}", _LIBRARY)
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({library_name}))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda _: library)
    return f"uses {library_name}"


@pytest.mark.parametrize("name", NAMES)
def test_a_library_function_named_like_a_slot_callback_is_refused(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    uses = _with_library(monkeypatch, name, f"function {name}(p : Player) = 1")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_host(uses=uses), "h.cardlang")
    message = _whole_bag(exc.value)
    defines = f"library 'lib_{name}' defines function '{name}', which"
    if name in CALL_FUNCS:
        assert f"{defines} shadows the native function" in message, message
    else:
        slot = _ROUND_QUERY_SLOT_SPELLINGS[_slot_of(name)].format(name=name)
        assert defines in message and slot in message, message
    span = exc.value.diagnostic.span
    assert span is not None and span.source_name == _LIBRARY, span


def test_hearts_with_a_function_named_after_its_winner_is_refused() -> None:
    """The planted-fault witness: the corpus game whose trick round names
    `highest_of_led_suit`, with a function of that name appended.

    red under: drop the round-callback arm of `_check_functions`."""
    path = Path("docs/games/hearts.cardlang")
    src = path.read_text() + "\nfunction highest_of_led_suit(p : Player) = 1\n"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, str(path))
    assert "`winner` slot" in _whole_bag(exc.value), _whole_bag(exc.value)
