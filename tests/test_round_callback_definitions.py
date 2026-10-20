"""A definition may not take a name a round slot reads.

property:   a game `function` named after a callback one of the game's own
            round slots names is refused at check time, at the function's
            line, naming that slot: the slot always runs the language's
            callback and never calls the function. A function no slot of the
            game names is called like any other. A family library's
            `function` and `requires` function row, which cannot know which
            game's rounds name what, are refused for every slot callback
            name, each with one refusal. A `primitives { }` entry is refused
            for every slot callback name.
domain:     slot callback name x callable-introducing position. The name
            axis is `_ROUND_QUERY_NAMES`, each name with the slot whose
            registry holds it. The position axis is every AST node that
            introduces a callable's name -- a game or library `FunctionDef`,
            a `PrimitiveDecl`, a `FunctionContract` -- partitioned against
            every node that carries parameters; the run-never-called kinds
            (move types, procedures, rules, procedure rows) and every
            value-holding introduction (state, zones, `let`, binders)
            never stand where a slot or a call means them, so sharing a
            spelling changes nothing a round does. Each game cell's host is
            the first corpus game whose rounds name the cell's name, and the
            boundary cell is a game whose rounds name none of it. A name that
            is also a callable native keeps the native-shadow refusal, whose
            sentence the game and library cells assert in its place.
registry:   names: `cardlang.resolve._ROUND_QUERY_NAMES` and
            `_ROUND_QUERY_REGISTRIES`; slot spellings:
            `cardlang.resolve._ROUND_QUERY_SLOT_SPELLINGS`; callable natives:
            `cardlang.builtins.functions.CALL_FUNCS`; parameter-bearing
            nodes: `cardlang.ast.nodes`; hosts: `docs/games/*.cardlang`;
            slot axis against the reference-slot table:
            tests/test_library_round_slot_primitives.py::test_the_slot_axis_is_every_round_query_slot;
            the `requires` row position:
            tests/test_definition_contracts.py::test_a_function_row_named_like_a_native_function.
does not prove:  that a slot runs the native it names: the round resolver
            and the runtime own that (tests/test_round_resolve.py).
"""

from __future__ import annotations

import dataclasses
import inspect
from itertools import combinations
from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.functions import CALL_FUNCS
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import (
    _ROUND_QUERY_NAMES,
    _ROUND_QUERY_REGISTRIES,
    _ROUND_QUERY_SLOT_SPELLINGS,
    _walk,
    slot_strings,
)

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
      winner highest_trump_or_led_suit
    score[0] := 1
  }}
  winner: highest score
}}
{definitions}
"""

_LIBRARY = "docs/libraries/lib.cardlang"
_GAMES = Path("docs/games")

NAMES = sorted(_ROUND_QUERY_NAMES)

# The nodes introducing a name a call or a slot could mean, and the nodes
# that carry parameters but are run, never called.
_CALLABLE_INTRODUCERS = {n.FunctionDef, n.PrimitiveDecl, n.FunctionContract}
_RUN_NEVER_CALLED = {n.MoveTypeDef, n.ProcedureDef, n.RuleDef, n.ProcedureContract}


def _host(*, uses: str = "", primitives: str = "", definitions: str = "") -> str:
    return _HOST.format(uses=uses, primitives=primitives, definitions=definitions)


def _errors(exc: DiagnosticError) -> list[str]:
    """Every error the stage reported: the notes carry the whole bag when it
    holds more than one, the leading diagnostic among them."""
    notes = getattr(exc, "__notes__", [])
    lines = "\n".join(notes).splitlines() if notes else [str(exc)]
    return [line for line in lines if ": error: " in line or line.startswith("error: ")]


def _slot_of(name: str) -> str:
    key = next(key for key, names in _ROUND_QUERY_REGISTRIES.items() if name in names)
    return _ROUND_QUERY_SLOT_SPELLINGS[key].format(name=name)


def _slot_names(text: str, source: str) -> frozenset[str]:
    """Every name the game's rounds write in a query slot."""
    return frozenset(
        name
        for nd in _walk(parse_text(text, source))
        for form, field_name in _ROUND_QUERY_REGISTRIES
        if isinstance(nd, form)
        for name in slot_strings(nd, field_name)
    )


def _corpus_host(name: str) -> Path:
    hosts = [
        p
        for p in sorted(_GAMES.glob("*.cardlang"))
        if name in _slot_names(p.read_text(), str(p))
    ]
    assert hosts, f"no corpus game's round names `{name}`, so its cell has no host"
    return hosts[0]


def test_the_slot_registries_and_spellings_agree() -> None:
    """Each slot has a spelling and owns its names alone, so a refusal names
    the one slot that reads the name.

    red under: delete a row from `_ROUND_QUERY_SLOT_SPELLINGS`, or add a
    trick winner to `PRIMITIVE_EARLY_PREDICATES`."""
    assert set(_ROUND_QUERY_SLOT_SPELLINGS) == set(_ROUND_QUERY_REGISTRIES)
    for a, b in combinations(_ROUND_QUERY_REGISTRIES.values(), 2):
        assert not a & b, a & b
    assert NAMES


def test_the_position_axis_partitions_every_parameter_bearing_node() -> None:
    """A new node kind that takes parameters joins one side or the other.

    red under: add a dataclass with a `params` field to `cardlang.ast.nodes`."""
    bearing = {
        cls
        for _, cls in inspect.getmembers(n, inspect.isclass)
        if dataclasses.is_dataclass(cls)
        and cls.__module__ == n.__name__
        and any(f.name == "params" for f in dataclasses.fields(cls))
    }
    assert bearing == _CALLABLE_INTRODUCERS | _RUN_NEVER_CALLED, bearing
    assert not _CALLABLE_INTRODUCERS & _RUN_NEVER_CALLED


def test_the_host_checks_clean_and_its_rounds_name_one_winner() -> None:
    """The control the library, primitives and boundary cells lean on.

    red under: name an unknown zone in the host's round."""
    check_dsl(_host(), "h.cardlang")
    check_dsl(_host(primitives="primitives { }"), "h.cardlang")
    assert _slot_names(_host(), "h.cardlang") == {"highest_trump_or_led_suit"}


@pytest.mark.parametrize("name", NAMES)
def test_a_function_named_after_its_games_slot_callback_is_refused(name: str) -> None:
    """The planted-fault witnesses: every corpus game's slot callback,
    redefined as a function beside the round that names it.

    red under: drop the round-callback arm of `_check_functions`; for a name
    in `CALL_FUNCS`, drop the native-shadow arm instead."""
    path = _corpus_host(name)
    src = path.read_text() + f"\nfunction {name}(p : Player) = 1\n"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, str(path))
    span = exc.value.diagnostic.span
    assert span is not None
    assert src.splitlines()[span.line - 1].startswith(f"function {name}("), span
    errors = _errors(exc.value)
    assert len(errors) == 1, errors
    if name in CALL_FUNCS:
        assert f"function '{name}' shadows the native function" in errors[0], errors
    else:
        assert f"function '{name}'" in errors[0] and _slot_of(name) in errors[0], errors


@pytest.mark.parametrize("name", sorted(_ROUND_QUERY_NAMES - CALL_FUNCS))
def test_a_function_no_slot_of_its_game_names_is_called(name: str) -> None:
    """The boundary: the game's rounds name another winner, so the function
    is the one meaning its name has here, and the call reaches it.

    red under: key the round-callback arm of `_check_functions` on
    `_ROUND_QUERY_NAMES` instead of the game's own slots."""
    check_dsl(
        _host(definitions=f"function {name}(k : Integer) = k + 1").replace(
            "score[0] := 1", f"score[0] := {name}(1)"
        ),
        "h.cardlang",
    )


@pytest.mark.parametrize("name", NAMES)
def test_a_primitives_entry_named_like_a_slot_callback_is_refused(name: str) -> None:
    """Born green: `_check_primitive_name` refuses every slot callback, by
    the Builtin, walled-namespace or unimplemented arm.

    red under: return early from `_check_primitive_name` when the name is in
    `_ROUND_QUERY_NAMES`."""
    src = _host(primitives=f"primitives {{ {name}(p : Player) : Integer }}")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "h.cardlang")
    span = exc.value.diagnostic.span
    assert span is not None
    assert src.splitlines()[span.line - 1].lstrip().startswith("primitives {"), span
    message = "\n".join(_errors(exc.value))
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
def test_a_library_function_named_like_a_slot_callback_is_refused_once(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """red under: drop the round-callback arm of `_check_library_collisions`
    (an `early` or climb name checks clean); drop the function skip in
    `_check_library_shadows_game` (a trick winner draws two refusals)."""
    uses = _with_library(monkeypatch, name, f"function {name}(p : Player) = 1")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_host(uses=uses), "h.cardlang")
    errors = _errors(exc.value)
    assert len(errors) == 1, errors
    span = exc.value.diagnostic.span
    assert span is not None and span.source_name == _LIBRARY, span
    defines = f"library 'lib_{name}' defines function '{name}', which"
    if name in CALL_FUNCS:
        assert f"{defines} shadows the native function" in errors[0], errors
    else:
        assert defines in errors[0] and _slot_of(name) in errors[0], errors
