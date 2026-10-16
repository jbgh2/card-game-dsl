"""Definition Contracts: a family library's `requires { }` row naming a move
type, a function or a procedure the importing GAME defines (decisions.md
"Family libraries").

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a Definition Contract row is answered by exactly the game's
                 own definition of its kind, at its parameters' positions and
                 exact type spellings and, for a function, a result its row's
                 result admits; every other answer is refused once, on the
                 game's `uses` line, with nothing reported in library text; and
                 every row shape no game could answer is refused to the
                 library's author before any game is consulted.
domain:          six axes. (1) The contractable kind — `_LIBRARY_DEF_KINDS`
                 restricted to the kinds whose namespace some slot a library's
                 own text holds can name — crossed with who answers the row:
                 the game's matching definition, nothing, the same name as
                 state, as a zone, as each other definition kind or as a
                 `primitives { }` entry, the name defined twice, another
                 library's definition, and the library itself, with the game
                 answering the row or not. (2) Each field a signature row compares, read off the
                 row nodes' own fields: arity both ways, a parameter's type and
                 its nullability, a parameter's name (accepted: positional), a
                 function's result (refused when it does not coerce; the
                 permissive top and the ordinary Integer-for-Player coercion
                 accepted). (3) The library's own rows: every word naming a
                 definition kind in a keyed row's type slot (each kind's
                 grammar keyword and its capitalised form, plus `Move`); every
                 type spelling a signature row's result can hold (the value
                 types with and without `?`, the zone types, the kind words,
                 an unknown name); the same spellings as a function row's and a
                 procedure row's parameter, each pinned EQUAL to the game
                 declaration it must agree with; every native call name and
                 round callback as a function row's name; a duplicate
                 parameter, a row named twice, a bare read, a call of a
                 procedure row and a run of a function row, a library procedure
                 running a procedure row; a library call disagreeing with its
                 own row; a call of the row from every library clause that
                 holds an expression (`n.Library`'s fields minus those with no
                 expression slot), against a game answering at the wrong
                 result; a dead row of each kind; a row name the library
                 also holds as provided state or as another definition, with
                 the game answering or not. (4) Two libraries and one name:
                 contracted at two signatures, as state and as a function,
                 at two results in both orders of the `uses` lines, and
                 contracted by one while the other brings it in. (5) What
                 crosses the splice: a call
                 cycle through the contract, a call-site pronoun inside an
                 answering definition, a hidden read through an answering
                 function. (6) The row's spelling at parse, including each
                 neighbouring row shape and definition header a designer
                 would copy. Rule is outside the kind axis by its derivation:
                 no library text can name a rule. A procedure row's name is
                 not crossed with the native names: a procedure is run, never
                 called, so no native function answers or shadows one.
registry:        kinds: `resolve._LIBRARY_DEF_KINDS` through
                 `contractable_kinds()` (the reachable-namespace walk of
                 tests/test_family_libraries.py), pinned equal to
                 `resolve.CONTRACT_KINDS`; keywords: the grammar, through
                 `tests.test_game_clause_guards._clause_keyword`; type
                 spellings: `typecheck.KNOWN_TYPE_NAMES`,
                 `stdlib.zones.LIBRARY_ZONE_TYPES`; native names:
                 `builtins.functions.BUILTIN_CALL_FUNCS`,
                 `PRIMITIVE_CALL_FUNCS`, `VALUE_NAMES`; compared fields:
                 `dataclasses.fields` of the row nodes; the whole-bag
                 rendering of a wrong result:
                 tests/rejections/contract_result_mismatch.expected; the
                 keyword-header twins: tests/rejections/libraries/; the
                 witness family: tests/test_smuggling_library.py; a hidden
                 read through an answer at every library position:
                 tests/test_contracted_hidden_reads.py.
does not prove:  that every member of a registry earns its exact sentence:
                 each cell reads its sentence by needle, through one host.
"""

from __future__ import annotations

import random
import re
import typing
from collections.abc import Iterator
from dataclasses import dataclass, fields

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    PRIMITIVE_CALL_FUNCS,
    VALUE_NAMES,
)
from cardlang.deckcheck import check_capacity
from cardlang.diagnostics import DiagnosticError
from cardlang.expand import expand
from cardlang.parse import parse_library, parse_text
from cardlang.resolve import _LIBRARY_DEF_KINDS, resolve
from cardlang.runtime.driver import play_game
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.typecheck import KNOWN_TYPE_NAMES, typecheck
from tests.test_family_libraries import _reachable_reference_namespaces
from tests.test_game_clause_guards import _clause_keyword

_LIB_FILE = "docs/libraries/contractlib.cardlang"
_GAME_FILE = "host.cardlang"


# --- the axes, derived ------------------------------------------------------


def _element_class(field: str) -> type:
    """The definition node a `n.Library` field holds (`functions` ->
    `n.FunctionDef`), read off the annotation."""
    hint = typing.get_type_hints(n.Library)[field]
    (element, _ellipsis) = typing.get_args(hint)
    assert isinstance(element, type)
    return element


def _production(cls: type) -> str:
    """`n.MoveTypeDef` -> `move_type_def`, the grammar production that writes
    one."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()


def _declared_namespace(field: str) -> str:
    """The namespace a definition of this kind declares its name into, from
    the reference-slot registry's declaration table."""
    from cardlang.resolve import _DECLARATION_SLOTS

    return _DECLARATION_SLOTS[(_element_class(field), "name")]


def contractable_kinds() -> tuple[tuple[str, str], ...]:
    """The definition kinds a library can contract for, derived independently
    of the implementation: `_LIBRARY_DEF_KINDS` restricted to the kinds whose
    reference namespace some slot a library's own text can hold issues. A kind
    no library text can name is a kind no library could use a contract for."""
    reachable = _reachable_reference_namespaces()
    return tuple(
        (field, noun)
        for field, noun in _LIBRARY_DEF_KINDS
        if _declared_namespace(field) in reachable
    )


def _kind_keyword(field: str) -> str:
    """The declaration keyword of a definition kind, from the grammar."""
    return _clause_keyword(_production(_element_class(field)))


# --- the host ----------------------------------------------------------------
#
# One library and one game, each completed per cell. The library contracts for
# exactly one definition of the kind under test and uses it once; the game
# answers it (or does not). Every other name either side needs is fixed, so a
# cell's outcome is the contract's and nothing else's.

_LIBRARY = """
library contractlib {{
  requires {{
    acted[player] : Boolean
    {rows}
  }}
  procedure ask(first : Player) {{
    turns t from first over players where not acted[player]
          until (number of players where not acted[player]) is 0 {{
      offer to t one of [{offering}]
    }}
  }}
  move_type stay {{ effect {{ {use} acted[actor] := true }} }}
  {extra}
}}
"""

_HOST = """
game Host {{
  uses contractlib
  {uses_more}
  players: 2
  cards: kuhn3
  max_length: 100
  {primitives}
  zones {{ deck : Deck {zones} }}
  state {{ acted[player] : Boolean = false {state} }}
  phase play {{ run ask(0) }}
  winner: highest acted
}}
{defs}
"""


@dataclass(frozen=True)
class Kind:
    """One contractable kind as the host writes it: the row, the offering the
    library's street presents, the library's use of the name inside `stay`,
    and the game's matching definition."""

    name: str
    row: str
    offering: str
    use: str
    answer: str


# Keyed by the derived axis; `test_every_contractable_kind_has_a_host` fails
# when `contractable_kinds()` gains a member this table does not write.
_KIND: dict[str, Kind] = {
    "move_types": Kind(
        name="fold",
        row="fold : Move",
        offering="stay, fold",
        use="",
        answer="move_type fold { effect { acted[actor] := true } }",
    ),
    "functions": Kind(
        name="ready",
        row="ready(p : Player) : Boolean",
        offering="stay",
        use="if ready(actor) { acted[actor] := true }",
        answer="function ready(p : Player) = not acted[p]",
    ),
    "procedures": Kind(
        name="settle",
        row="settle(p : Player) : Procedure",
        offering="stay",
        use="run settle(actor)",
        answer="procedure settle(p : Player) { acted[p] := true }",
    ),
}


def _library(
    kind: str,
    *,
    rows: str | None = None,
    use: str | None = None,
    extra: str = "",
    name: str = "contractlib",
) -> n.Library:
    k = _KIND[kind]
    text = _LIBRARY.format(
        rows=k.row if rows is None else rows,
        offering=k.offering,
        use=k.use if use is None else use,
        extra=extra,
    ).replace("library contractlib", f"library {name}")
    return parse_library(text, f"docs/libraries/{name}.cardlang")


def _host(
    *,
    defs: str = "",
    state: str = "",
    zones: str = "",
    primitives: str = "",
    uses_more: str = "",
) -> str:
    return _HOST.format(
        defs=defs, state=state, zones=zones, primitives=primitives, uses_more=uses_more
    )


def _patch(monkeypatch: pytest.MonkeyPatch, *libraries: n.Library) -> None:
    table = {lib.name: lib for lib in libraries}
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset(table))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: table[name])


def _check(text: str) -> n.Game:
    """The post-parse pipeline, unmemoized: `pipeline.check_dsl` caches on the
    parsed tree while the libraries are patched per cell, so one cell's result
    could answer another's."""
    game = resolve(parse_text(text, _GAME_FILE))
    return check_capacity(expand(typecheck(game)))


def _rendered(exc: DiagnosticError) -> list[str]:
    """Every diagnostic a stage raised, one rendered line each. A stage that
    collected more than one attaches the whole bag as a note."""
    notes = getattr(exc, "__notes__", [])
    return notes[0].splitlines() if notes else [str(exc)]


def _bag(text: str) -> list[str]:
    """Every rendered diagnostic the pipeline raises for `text`, or [] when it
    accepts."""
    try:
        _check(text)
    except DiagnosticError as exc:
        return _rendered(exc)
    return []


def _outcome(
    monkeypatch: pytest.MonkeyPatch,
    libraries: typing.Callable[[], tuple[n.Library, ...]],
    text: str,
) -> list[str]:
    """The whole bag a cell earns: the libraries' own parse first (a refusal
    there is the library author's), then the game through the pipeline."""
    try:
        built = libraries()
    except DiagnosticError as exc:
        return _rendered(exc)
    _patch(monkeypatch, *built)
    return _bag(text)


ACCEPT = None


@dataclass(frozen=True)
class Reject:
    """A refusal: every sentence lands in `where` (the file of the Author who
    can act), one of them says every needle, and — `alone` — it is the only
    sentence in the bag."""

    where: str
    needles: tuple[str, ...]
    alone: bool = True


GAME = _GAME_FILE
LIBRARY = _LIB_FILE


def _assert(bag: list[str], expected: Reject | None) -> None:
    if expected is None:
        assert bag == [], "expected the cell to be accepted, got:\n" + "\n".join(bag)
        return
    assert bag, "expected a refusal, but the cell was accepted"
    assert all(line.startswith(expected.where) for line in bag), (
        f"every sentence should be reported in {expected.where}:\n" + "\n".join(bag)
    )
    assert any(all(needle in line for needle in expected.needles) for line in bag), (
        f"no sentence says {expected.needles}:\n" + "\n".join(bag)
    )
    if expected.alone:
        assert len(bag) == 1, "expected exactly one sentence:\n" + "\n".join(bag)


# --- Axis 1: who answers the row, per contractable kind ----------------------
#
# The answer column: the game's own matching definition, nothing, the same name
# declared as each OTHER thing a game can declare (the two keyed blocks and
# every definition kind and a `primitives { }` entry), the name defined twice,
# another library's definition, and the library defining it itself — with the
# game answering the row or not. Reported on the game's `uses` line, except the
# last two, which are the library's own contradiction, told once whatever the
# game did.

_OTHER_DECLARATIONS: dict[str, str] = {
    "state": "state",
    "zone": "a zone",
    **{field: f"a {noun}" for field, noun in _LIBRARY_DEF_KINDS},
    "primitive": "a Primitive",
}


def _as_other(other: str, name: str) -> dict[str, str]:
    """`name` declared as `other`, as the keyword arguments of `_host`."""
    if other == "state":
        return {"state": f"{name} : Boolean = false"}
    if other == "zone":
        return {"zones": f"{name} : Discard"}
    if other == "primitive":
        return {"primitives": f"primitives {{ {name}(p : Player) : Boolean }}"}
    return {"defs": _DEF_TEXT[other].format(name=name)}


# One minimal definition per kind, under a given name. The pin below holds its
# keys to `_LIBRARY_DEF_KINDS`.
_DEF_TEXT: dict[str, str] = {
    "rules": "rule {name} {{ }}",
    "move_types": "move_type {name} {{ effect {{ acted[actor] := true }} }}",
    "functions": "function {name}(p : Player) = true",
    "procedures": "procedure {name}(p : Player) {{ acted[p] := true }}",
}


def _answer_cells() -> Iterator[tuple[str, str]]:
    for field, _noun in contractable_kinds():
        yield field, "match"
        yield field, "absent"
        for other in _OTHER_DECLARATIONS:
            if other != field:
                yield field, f"as:{other}"
        yield field, "twice"
        yield field, "other_library"
        yield field, "library_defines_too"
        yield field, "library_defines_too_and_game_answers"


def _answer_expected(field: str, answer: str) -> Reject | None:
    k = _KIND[field]
    noun = dict(_LIBRARY_DEF_KINDS)[field]
    asks = f"library 'contractlib' requires {noun} `{k.name}"
    if answer == "match":
        return ACCEPT
    if answer == "absent":
        return Reject(GAME, (asks, "which game 'Host' does not define"))
    if answer.startswith("as:"):
        other = answer.removeprefix("as:")
        return Reject(GAME, (asks, f"declares as {_OTHER_DECLARATIONS[other]}"))
    if answer == "twice":
        return Reject(GAME, (asks, "defines 2 times"))
    if answer == "other_library":
        return Reject(GAME, (asks, "which library 'other' defines"))
    assert answer.startswith("library_defines_too")
    return Reject(LIBRARY, (f"both defines and requires {noun} '{k.name}'",))


def _answer_cell(field: str, answer: str) -> tuple[typing.Callable[[], tuple[n.Library, ...]], str]:
    k = _KIND[field]
    if answer == "match":
        return (lambda: (_library(field),)), _host(defs=k.answer)
    if answer == "absent":
        return (lambda: (_library(field),)), _host()
    if answer.startswith("as:"):
        return (lambda: (_library(field),)), _host(**_as_other(answer[3:], k.name))
    if answer == "twice":
        return (lambda: (_library(field),)), _host(defs=f"{k.answer}\n{k.answer}")
    if answer == "other_library":
        other = (
            "library other {{ requires {{ acted[player] : Boolean }} "
            + _DEF_TEXT[field].format(name=k.name)
            + " }}"
        ).replace("{{", "{").replace("}}", "}")
        return (
            lambda: (_library(field), parse_library(other, "docs/libraries/other.cardlang")),
            _host(uses_more="uses other"),
        )
    assert answer.startswith("library_defines_too")
    own = _DEF_TEXT[field].format(name=k.name).replace("{{", "{").replace("}}", "}")
    answered = k.answer if answer.endswith("game_answers") else ""
    return (lambda: (_library(field, extra=own),)), _host(defs=answered)


@pytest.mark.parametrize("field,answer", list(_answer_cells()))
def test_who_answers_a_definition_row(
    monkeypatch: pytest.MonkeyPatch, field: str, answer: str
) -> None:
    libraries, text = _answer_cell(field, answer)
    _assert(_outcome(monkeypatch, libraries, text), _answer_expected(field, answer))


def test_the_matching_answer_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accepting is not running: each kind's accepting cell plays to the end,
    with the contracted definition reached from library text."""
    for field, _noun in contractable_kinds():
        libraries, text = _answer_cell(field, "match")
        _patch(monkeypatch, *libraries())
        play_game(_check(text), random.Random(0))


def test_every_contractable_kind_has_a_host() -> None:
    """The host tables are keyed by the derived axes, so a kind joining either
    registry is a red here rather than a kind no cell writes.

    red under: add a field to `n.Library` and a row to `_LIBRARY_DEF_KINDS`
    whose declaration namespace a library slot can reach."""
    assert set(_KIND) == {field for field, _ in contractable_kinds()}
    assert set(_DEF_TEXT) == {field for field, _ in _LIBRARY_DEF_KINDS}


def test_the_kind_words_are_the_grammars() -> None:
    """Every keyed-row word naming a definition kind, as resolve reads it, is
    one this module derives from the grammar's declaration keywords.

    red under: drop the capitalised forms from
    `resolve._DEFINITION_KIND_WORDS`."""
    from cardlang.resolve import _DEFINITION_KIND_WORDS

    assert set(_DEFINITION_KIND_WORDS) == {*_kind_words(), n.MOVE_CONTRACT_TYPE}


def test_the_contract_kind_registry_is_the_derived_one() -> None:
    """The implementation's registry of contractable kinds equals this module's
    independent derivation: a kind no library text can name (rule) is excluded
    by reachability, never by a list.

    red under: add `rules` to the registry by hand, or make a rule reachable
    from library text (a `RuleRef` slot under a library clause)."""
    from cardlang.resolve import CONTRACT_KINDS

    assert tuple((f, noun) for f, noun, _cls in CONTRACT_KINDS) == contractable_kinds()


# --- Axis 2: one cell per compared field of a signature row ------------------
#
# A row with a signature fixes its parameters by POSITION and type (the names
# are the row's own documentation: the library never names the game's
# binders), and a function row fixes its result. Each cell keeps the game's
# answer matching except in the one field it varies. The field axis is held to
# the contract nodes' own fields by the pin below.

# (kind, field) -> {variant: (the game's answer, expected)}
_FIELD_CELLS: dict[tuple[str, str], dict[str, tuple[str, Reject | None]]] = {
    ("functions", "params"): {
        "one_more": (
            "function ready(p : Player, q : Player) = not acted[p]",
            Reject(GAME, ("requires function `ready(p : Player) : Boolean`", "2 parameters")),
        ),
        "one_fewer": (
            "function ready() = true",
            Reject(GAME, ("requires function `ready(p : Player) : Boolean`", "0 parameters")),
        ),
        "type_differs": (
            "function ready(p : Team) = true",
            Reject(GAME, ("requires function `ready(p : Player) : Boolean`", "parameter 1 is `Team`")),
        ),
        "nullability_differs": (
            "function ready(p : Player?) = true",
            Reject(GAME, ("requires function `ready(p : Player) : Boolean`", "parameter 1 is `Player?`")),
        ),
        "name_differs": ("function ready(who : Player) = not acted[who]", ACCEPT),
    },
    ("functions", "result_type"): {
        "type_differs": (
            "function ready(p : Player) = 1",
            Reject(GAME, ("requires function `ready(p : Player) : Boolean`", "returning Integer")),
        ),
        # The permissive top fits every result, by the ordinary coercion rule
        # every other typed position applies.
        "permissive_top": ('function ready(p : Player) = error("never")', ACCEPT),
    },
    ("procedures", "params"): {
        "one_more": (
            "procedure settle(p : Player, q : Player) { acted[p] := true }",
            Reject(GAME, ("requires procedure `settle(p : Player) : Procedure`", "2 parameters")),
        ),
        "one_fewer": (
            "procedure settle() { acted[0] := true }",
            Reject(GAME, ("requires procedure `settle(p : Player) : Procedure`", "0 parameters")),
        ),
        "type_differs": (
            "procedure settle(p : Integer) { acted[p] := true }",
            Reject(GAME, ("requires procedure `settle(p : Player) : Procedure`", "parameter 1 is `Integer`")),
        ),
        "nullability_differs": (
            "procedure settle(p : Player?) { acted[0] := true }",
            Reject(GAME, ("requires procedure `settle(p : Player) : Procedure`", "parameter 1 is `Player?`")),
        ),
        "name_differs": ("procedure settle(who : Player) { acted[who] := true }", ACCEPT),
    },
}


def test_the_field_axis_is_every_compared_field() -> None:
    """Every field a signature row carries beyond its name and span is a
    dimension the game's answer can disagree on, so each has cells above.

    red under: add a field to `n.FunctionContract` or `n.ProcedureContract`
    without cells for it."""
    from cardlang.resolve import CONTRACT_KINDS

    expected = {
        (field, f.name)
        for field, _noun, cls in CONTRACT_KINDS
        for f in fields(cls)
        if f.name not in ("name", "span")
    }
    assert set(_FIELD_CELLS) == expected


@pytest.mark.parametrize(
    "field,compared,variant",
    [(k, c, v) for (k, c), cells in _FIELD_CELLS.items() for v in cells],
)
def test_a_signature_row_compares_each_field(
    monkeypatch: pytest.MonkeyPatch, field: str, compared: str, variant: str
) -> None:
    answer, expected = _FIELD_CELLS[(field, compared)][variant]
    bag = _outcome(monkeypatch, lambda: (_library(field),), _host(defs=answer))
    _assert(bag, expected)


def test_a_result_coerces_by_the_ordinary_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """An Integer answering a `Player` result is the coercion every typed
    position allows (`types.coercible`), not a mismatch."""
    bag = _outcome(
        monkeypatch,
        lambda: (
            _library(
                "functions",
                rows="ready(p : Player) : Player",
                use="if ready(actor) is actor { acted[actor] := true }",
            ),
        ),
        _host(defs="function ready(p : Player) = 0"),
    )
    _assert(bag, ACCEPT)


# --- Axis 3: the library's own rows, before any game is consulted ------------
#
# Every shape here is wrong in the library's own text, so no game could answer
# it and the library's author is told, in the library's file.


def _alone(library: typing.Callable[[], n.Library]) -> list[str]:
    """The library-alone verdict: its parse, then every property it holds by
    itself (`resolve.check_library_alone`)."""
    from cardlang.diagnostics import DiagnosticBag
    from cardlang.resolve import check_library_alone

    try:
        built = library()
    except DiagnosticError as exc:
        return _rendered(exc)
    bag = DiagnosticBag()
    check_library_alone(built, bag)
    return [d.format() for d in bag.items]


def _camel(word: str) -> str:
    return "".join(part.title() for part in word.split("_"))


def _kind_words() -> list[str]:
    """Every word that names a KIND of definition rather than a type: each
    kind's declaration keyword, from the grammar, and its capitalised form —
    the two spellings a designer reaches for in a type slot."""
    words: list[str] = []
    for field, _noun in _LIBRARY_DEF_KINDS:
        keyword = _kind_keyword(field)
        words += [keyword, _camel(keyword)]
    return words


def _keyed_word_expected(word: str) -> Reject | None:
    if word == "Move":
        return ACCEPT
    if word in ("move_type", "MoveType"):
        return Reject(LIBRARY, ("`x : Move`",))
    if word in ("function", "Function"):
        return Reject(LIBRARY, ("x : " + word, "signature", "`x(", ") : <result type>`"))
    if word in ("procedure", "Procedure"):
        return Reject(LIBRARY, ("x : " + word, "signature", ") : Procedure`"))
    assert word in ("rule", "Rule"), word
    return Reject(LIBRARY, ("x : " + word, "a rule cannot be contracted", "active_rules:"))


@pytest.mark.parametrize("word", ["Move", *_kind_words()])
def test_a_keyed_row_naming_a_definition_kind(word: str) -> None:
    """`x : Procedure`, `x : function`, `x : Rule`: a definition kind in a
    keyed row's type slot. Only `Move` is a row; every other spelling is told
    the row to write instead."""
    bag = _alone(
        lambda: parse_library(
            _LIBRARY.format(
                rows=f"x : {word}",
                offering="stay, x" if word == "Move" else "stay",
                use="",
                extra="",
            ),
            _LIB_FILE,
        )
    )
    _assert(bag, _keyed_word_expected(word))


def _type_spellings() -> list[str]:
    """Every spelling a signature row's type slot can hold that the language
    gives a meaning: the value types with and without `?`, the zone types, the
    kind words, and one name no registry holds."""
    return sorted(
        {*KNOWN_TYPE_NAMES, *(f"{t}?" for t in KNOWN_TYPE_NAMES), *LIBRARY_ZONE_TYPES,
         *_kind_words(), "Move", "Procedure?", "Widget"}
    )


def _result_expected(result: str) -> Reject | None:
    if result.removesuffix("?") in KNOWN_TYPE_NAMES or result == "Procedure":
        return ACCEPT
    if result in LIBRARY_ZONE_TYPES:
        return Reject(LIBRARY, ("ready(p : Player)", "is a zone type"))
    if result == "Move":
        return Reject(LIBRARY, ("ready(p : Player)", "`ready : Move`"))
    if result == "Procedure?":
        return Reject(LIBRARY, ("ready(p : Player)", "a procedure returns no value"))
    if result == "Widget":
        return Reject(LIBRARY, ("'Widget'",))
    return Reject(LIBRARY, ("ready(p : Player)", "names a kind of definition"))


@pytest.mark.parametrize("result", _type_spellings())
def test_a_signature_rows_result(result: str) -> None:
    bag = _alone(
        lambda: _library(
            "functions",
            rows=f"ready(p : Player) : {result}",
            # A procedure row the library never runs is refused on its own.
            use="run ready(actor)" if result == "Procedure" else "",
        )
    )
    _assert(bag, _result_expected(result))


def _game_refuses_parameter(definition: str) -> bool:
    """Whether a plain game refuses `definition` for its parameter's type —
    the declaration a contract row must agree with."""
    text = (
        "game G { players: 2 cards: kuhn3 max_length: 10 zones { deck : Deck } "
        "state { acted[player] : Boolean = false } "
        "phase play { run use_it() } winner: highest acted } "
        + definition
    )
    try:
        resolve(parse_text(text, "plain.cardlang"))
    except DiagnosticError as exc:
        return any(
            "unknown type" in line or "unsupported domain" in line
            for line in _rendered(exc)
        )
    return False


def _refuses_parameter(bag: list[str], spelling: str) -> bool:
    """Whether the library's verdict refuses the row's parameter by name. A
    verdict that is neither that refusal nor an acceptance (a parse failure, a
    refusal of something else) answers neither way, and fails the cell."""
    assert all(line.startswith(LIBRARY) for line in bag), bag
    if any(f"x : {spelling}" in line for line in bag):
        return True
    assert bag == [], f"refused for another reason:\n" + "\n".join(bag)
    return False


@pytest.mark.parametrize("spelling", _type_spellings())
def test_a_function_rows_parameter_is_refused_exactly_when_the_definition_would_be(
    spelling: str,
) -> None:
    """A row's parameter type and the game's function parameter are one
    position: a row admitting a type a `function` refuses would be a row no
    game could answer, and the reverse would refuse a row a game could.

    red under: let `resolve._check_contract_shapes` accept a zone type as a
    function row's parameter."""
    game_refuses = _game_refuses_parameter(
        f"procedure use_it() {{ acted[0] := f(0) }} function f(x : {spelling}) = true"
    )
    bag = _alone(lambda: _library("functions", rows=f"f(x : {spelling}) : Boolean", use=""))
    assert _refuses_parameter(bag, spelling) == game_refuses, bag


@pytest.mark.parametrize("spelling", _type_spellings())
def test_a_procedure_rows_parameter_is_refused_exactly_when_the_definition_would_be(
    spelling: str,
) -> None:
    """The procedure leg of the same equality, against the procedure
    parameter domains (`resolve._PROCEDURE_PARAM_DOMAINS`).

    red under: let `resolve._check_contract_shapes` accept `Card` as a
    procedure row's parameter."""
    game_refuses = _game_refuses_parameter(
        f"procedure use_it() {{ acted[0] := true }} "
        f"procedure p(x : {spelling}) {{ acted[0] := true }}"
    )
    bag = _alone(
        lambda: _library(
            "procedures", rows=f"p(x : {spelling}) : Procedure", use="run p(0)"
        )
    )
    assert _refuses_parameter(bag, spelling) == game_refuses, bag


@pytest.mark.parametrize(
    "name", sorted(BUILTIN_CALL_FUNCS | PRIMITIVE_CALL_FUNCS | VALUE_NAMES)
)
def test_a_function_row_named_like_a_native_function(name: str) -> None:
    """A Builtin needs no contract — the library calls it directly — a
    Primitive belongs to the one game that declares it, and a round's callback
    is named in its slot, never called, so no row may take any of those
    spellings. That is also why a game's `primitives { }` entry never answers a
    function row."""
    bag = _alone(lambda: _library("functions", rows=f"{name}(p : Player) : Boolean", use=""))
    if name in VALUE_NAMES:
        needle = "callback"
    elif name in BUILTIN_CALL_FUNCS:
        needle = "call it directly"
    else:
        needle = "Primitive"
    _assert(bag, Reject(LIBRARY, (f"'{name}'", needle)))


# Misuses of the library's own text around a row, each told to the library's
# author. (rows, use, extra, needles)
_LIBRARY_MISUSE: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "duplicate_parameter": (
        "ready(p : Player, p : Player) : Boolean", "", "",
        ("ready", "more than one parameter named 'p'"),
    ),
    "row_twice": (
        "ready(p : Player) : Boolean\n    ready : Boolean", "", "",
        ("'ready'", "more than one row"),
    ),
    "bare_read_of_a_function_row": (
        "ready(p : Player) : Boolean", "if ready { acted[actor] := true }", "",
        ("reads 'ready'", "call it"),
    ),
    "call_of_a_procedure_row": (
        "settle(p : Player) : Procedure", "if settle(actor) { acted[actor] := true }",
        "move_type pay { effect { run settle(actor) } }",
        ("calls 'settle'", "procedure", "not a function"),
    ),
    "run_of_a_function_row": (
        "ready(p : Player) : Boolean", "run ready(actor)", "",
        ("'ready'", "function", "not a procedure"),
    ),
    # A result that is no value type: one sentence, and the row's `run` site
    # is not also told the row is a function.
    "procedure_result_with_question_mark": (
        "settle(p : Player) : Procedure?", "run settle(actor)", "",
        ("a procedure returns no value",),
    ),
    "unknown_result": (
        "settle(p : Player) : Void", "run settle(actor)", "",
        ("'Void'",),
    ),
    "library_procedure_runs_a_procedure_row": (
        "settle(p : Player) : Procedure", "run helper(actor)",
        "procedure helper(p : Player) { run settle(p) }",
        ("procedure 'helper' runs 'settle'", "a move type's effect"),
    ),
}


@pytest.mark.parametrize("case", sorted(_LIBRARY_MISUSE))
def test_a_library_misusing_its_own_row(case: str) -> None:
    rows, use, extra, needles = _LIBRARY_MISUSE[case]
    bag = _alone(lambda: _library("functions", rows=rows, use=use, extra=extra))
    _assert(bag, Reject(LIBRARY, needles))


# A library call disagreeing with its own row is typed against the row, so the
# library's author is told whatever the game answered.
_CALL_AGAINST_ROW: dict[str, tuple[str, str]] = {
    "arity": ("if ready(actor, actor) { acted[actor] := true }", "ready() expects 1 argument(s), got 2"),
    "argument_type": ("if ready(1 is 1) { acted[actor] := true }", "ready() expects Player, got Boolean"),
}


@pytest.mark.parametrize("case", sorted(_CALL_AGAINST_ROW))
def test_a_library_call_is_typed_against_its_own_row(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    use, needle = _CALL_AGAINST_ROW[case]
    bag = _outcome(
        monkeypatch,
        lambda: (_library("functions", use=use),),
        _host(defs=_KIND["functions"].answer),
    )
    _assert(bag, Reject(LIBRARY, (needle,)))


# A call of the function row from each library clause that can hold an
# expression, with the game answering at the wrong result. Keyed by the clause;
# `test_every_expression_bearing_clause_calls_a_row` holds the keys to
# `n.Library`'s fields minus the ones with no expression slot.
_CALL_SITE: dict[str, str] = {
    "rules": (
        "rule watch { constrains: play_to_trick applies_when: ready(actor) "
        "demands: cards in hand where card.suit is state.led_suit if_impossible: hand }"
    ),
    "move_types": "move_type pay { effect { if ready(actor) { acted[actor] := true } } }",
    "functions": "function gate(p : Player) = ready(p)",
    "procedures": (
        "procedure check(p : Player) { if ready(p) { acted[p] := true } } "
        "move_type runner { effect { run check(actor) } }"
    ),
    "state": "state { flag : Boolean = ready(0) }",
}


def test_every_expression_bearing_clause_calls_a_row() -> None:
    """red under: add an expression-bearing field to `n.Library` without a
    `_CALL_SITE` cell."""
    assert set(_CALL_SITE) == {f.name for f in fields(n.Library)} - {
        "name",
        "requires",
        "span",
    }


@pytest.mark.parametrize("site", sorted(_CALL_SITE))
def test_a_wrong_result_is_told_once_from_every_call_site(
    monkeypatch: pytest.MonkeyPatch, site: str
) -> None:
    """Every library call of a contracted function is typed against the row,
    so a game answering at the wrong result is told once, on its `uses` line,
    wherever the library calls it. A provided default is the exception by an
    earlier rule: a default may call nothing (`_check_state_default_scope`),
    so the library's author is told that instead, once, and the game's answer
    is never consulted.

    red under: leave a definition field out of
    `resolve._stamp_contracted_calls` — that site's call is typed against the
    game's Integer and earns a second sentence in the library's file."""
    text = _host(defs="function ready(p : Player) = 1")
    if site == "rules":
        # A library rule splices only where the game activates it, so the host
        # activates it, with the trick round a rule constrains.
        text = _host(
            defs="function ready(p : Player) = 1",
            zones="hand[player] : Hand<player>  pile : TrickPile",
        ).replace(
            "  max_length: 100\n", "  max_length: 100\n  ranking: K Q J\n"
        ).replace(
            "phase play { run ask(0) }",
            "phase play {\n    active_rules: [watch]\n"
            "    round play_to_trick from 0 over all players source hand into pile\n"
            "      winner highest_of_led_suit\n    run ask(0)\n  }",
        )
        assert "active_rules: [watch]" in text
    bag = _outcome(
        monkeypatch,
        lambda: (_library("functions", use="", extra=_CALL_SITE[site]),),
        text,
    )
    if site == "state":
        _assert(bag, Reject(LIBRARY, ("cannot call 'ready'",)))
    else:
        _assert(bag, Reject(GAME, ("requires function `ready(p : Player) : Boolean`", "returning Integer")))


def _unused(field: str) -> n.Library:
    k = _KIND[field]
    return parse_library(
        _LIBRARY.format(rows=k.row, offering="stay", use="", extra=""), _LIB_FILE
    )


@pytest.mark.parametrize("field", [f for f, _ in contractable_kinds()])
def test_a_row_the_library_never_reaches_is_dead(field: str) -> None:
    """Minimality, per kind: a row is reached by the library's use of it and
    by nothing else.

    red under: drop the kind's namespace from `resolve._LibraryReach`'s
    definition reads."""
    from cardlang.resolve import dead_contract_rows

    assert dead_contract_rows(_library(field)) == frozenset()
    assert dead_contract_rows(_unused(field)) == frozenset({_KIND[field].name})


# A dead row is a contract some games cannot meet: the game's move type would be
# refused as never offered, and its procedure as never run, so the library's
# author is told. A function the game defines and nothing calls is legal, so a
# dead function row is only the minimality pin's
# (tests/test_family_libraries.py::test_every_library_contracts_for_exactly_what_it_reaches).
_DEAD_ROW: dict[str, Reject | None] = {
    "move_types": Reject(LIBRARY, ("`fold : Move`", "never offers it")),
    "functions": ACCEPT,
    "procedures": Reject(LIBRARY, ("`settle(p : Player) : Procedure`", "never runs it")),
}


@pytest.mark.parametrize("field", [f for f, _ in contractable_kinds()])
def test_a_dead_row_no_game_could_answer_is_refused(field: str) -> None:
    _assert(_alone(lambda: _unused(field)), _DEAD_ROW[field])


# --- Axis 4: the same name contracted by two libraries -----------------------
#
# Each library's rows are checked against the game on that library's own `uses`
# line, so when two libraries disagree about one name the game can meet at most
# one of them, and the other's line is the one refused.

_SECOND = """
library second {{
  requires {{ acted[player] : Boolean  {row} }}
  move_type wait {{ effect {{ {use} acted[actor] := true }} }}
}}
"""


@pytest.mark.parametrize(
    "row,use,needles",
    [
        (
            "ready(p : Team) : Boolean",
            "if ready(0) { }",
            ("library 'second' requires function `ready(p : Team) : Boolean`", "parameter 1 is `Player`"),
        ),
        (
            "ready : Boolean",
            "if ready { }",
            ("library 'second' requires state `ready : Boolean`", "declares as a function"),
        ),
    ],
    ids=["two_signatures", "state_and_function"],
)
def test_two_libraries_contracting_one_name(
    monkeypatch: pytest.MonkeyPatch, row: str, use: str, needles: tuple[str, ...]
) -> None:
    second = _SECOND.format(row=row, use=use)
    bag = _outcome(
        monkeypatch,
        lambda: (_library("functions"), parse_library(second, "docs/libraries/second.cardlang")),
        _host(defs=_KIND["functions"].answer, uses_more="uses second"),
    )
    _assert(bag, Reject(GAME, needles))


@pytest.mark.parametrize("probe_first", [True, False], ids=["probe_first", "second_first"])
def test_two_libraries_reading_one_answer_at_different_results(
    monkeypatch: pytest.MonkeyPatch, probe_first: bool
) -> None:
    """Both libraries' rows are checked against the one answer, in either
    order of the `uses` lines: the answer carries every row it answers, so
    the library whose result it does not meet is the one refused.

    red under: let a later library's stamp replace an earlier one's in
    `resolve._apply_uses` — one order is accepted and plays with a Boolean
    where the second library reads an Integer."""
    second = _SECOND.format(row="ready(q : Player) : Integer", use="if ready(actor) is 1 { }")
    order = ("uses second", "") if not probe_first else ("", "uses second")
    text = _host(defs=_KIND["functions"].answer, uses_more=order[1])
    if not probe_first:
        text = text.replace("uses contractlib", "uses second\n  uses contractlib", 1)
    bag = _outcome(
        monkeypatch,
        lambda: (_library("functions"), parse_library(second, "docs/libraries/second.cardlang")),
        text,
    )
    _assert(
        bag,
        Reject(GAME, ("library 'second' requires function `ready(q : Player) : Integer`", "returning Boolean")),
    )


# A library forcing a name on the game through its contract, while another
# library brings in the same name: the game cannot rename its answer, so it is
# told the two libraries do not combine. (clash text in the second library)
_FORCED_CLASH: dict[str, str] = {
    "provided_state": "state {{ ready : Boolean = false }}",
    "move_type": "move_type ready {{ effect {{ acted[actor] := true }} }}",
}


@pytest.mark.parametrize("clash", sorted(_FORCED_CLASH))
def test_a_name_one_contract_forces_and_another_library_brings_in(
    monkeypatch: pytest.MonkeyPatch, clash: str
) -> None:
    second = (
        "library second {{ requires {{ acted[player] : Boolean }} "
        + _FORCED_CLASH[clash]
        + " }}"
    ).replace("{{", "{").replace("}}", "}")
    bag = _outcome(
        monkeypatch,
        lambda: (_library("functions"), parse_library(second, "docs/libraries/second.cardlang")),
        _host(defs=_KIND["functions"].answer, uses_more="uses second"),
    )
    _assert(
        bag,
        Reject(GAME, ("library 'second' brings in", "library 'contractlib' has this game define 'ready'", "drop one `uses` line")),
    )


# A library holding a name it also contracts for, told once to its author —
# whether or not the game answered the row. (the library's own text)
_OWN_CLASH: dict[str, str] = {
    "provided_state": "state { ready : Boolean = false }",
    "move_type": "move_type ready { effect { acted[actor] := true } }",
    "procedure": "procedure ready(p : Player) { acted[p] := true }",
}


@pytest.mark.parametrize("answered", [True, False], ids=["answered", "unanswered"])
@pytest.mark.parametrize("clash", sorted(_OWN_CLASH))
def test_a_library_holding_its_own_row_name_is_told_once(
    monkeypatch: pytest.MonkeyPatch, clash: str, answered: bool
) -> None:
    """The library's contradiction is its own; the game answering the row
    did what the row asked, so it earns no sentence of its own.

    red under: drop the contracted-name skip from
    `resolve._check_library_shadows_game` — the answered cells gain a second
    sentence in the game's file."""
    bag = _outcome(
        monkeypatch,
        lambda: (_library("functions", extra=_OWN_CLASH[clash]),),
        _host(defs=_KIND["functions"].answer if answered else ""),
    )
    if answered:
        _assert(bag, Reject(LIBRARY, ("requires 'ready' as a function and also holds",)))
    else:
        assert any("requires 'ready' as a function and also holds" in line for line in bag), bag
        assert not any(line.startswith(GAME) and "rename one" in line for line in bag), bag


# --- Axis 5: what crosses the splice -----------------------------------------


def test_a_call_cycle_through_the_contract_is_the_games_to_break(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library's function calls the game's, which calls back into the
    library's. Neither file alone is recursive; the game closed the cycle, so
    the game's author is told, at the game's function."""
    bag = _outcome(
        monkeypatch,
        lambda: (
            _library(
                "functions",
                use="if gate(actor) { acted[actor] := true }",
                extra="function gate(p : Player) = ready(p)",
            ),
        ),
        _host(defs="function ready(p : Player) = gate(p)"),
    )
    _assert(bag, Reject(GAME, ("function 'ready' is recursive", "library 'contractlib'")))


@pytest.mark.parametrize(
    "answer,needle",
    [
        (
            "procedure settle(p : Player) { acted[actor] := true }",
            "procedure 'settle' reads the call-site pronoun 'actor'",
        ),
        (
            "function ready(p : Player) = not acted[actor]",
            "function 'ready' reads the call-site pronoun 'actor'",
        ),
    ],
    ids=["procedure", "function"],
)
def test_a_contracted_definition_reading_a_pronoun_is_told_a_fix_it_can_take(
    monkeypatch: pytest.MonkeyPatch, answer: str, needle: str
) -> None:
    """A definition the library calls cannot be handed a new argument from the
    game's side: the call site is in library text. So the refusal sends the
    game's author to the parameter the row already passes, never to a `run` or
    a call they cannot edit. The remedy is the matching answer of
    `test_who_answers_a_definition_row`, which reads the parameter and plays."""
    field = "procedures" if answer.startswith("procedure") else "functions"
    bag = _outcome(monkeypatch, lambda: (_library(field),), _host(defs=answer))
    _assert(bag, Reject(GAME, (needle, "library 'contractlib'", "the parameter")))
    assert not any("run settle(actor)" in line or "pass the value in" in line for line in bag)


_PEEK_LIBRARY = """
library contractlib {
  requires {
    acted[player] : Boolean
    ready(p : Player) : Boolean
  }
  procedure ask(first : Player) {
    turns t from first over players where not acted[player]
          until (number of players where not acted[player]) is 0 {
      offer to t one of [stay]
    }
  }
  move_type stay { when: ready(actor) effect { acted[actor] := true } }
}
"""


def test_a_hidden_read_through_a_contracted_function_is_the_games(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bag = _outcome(
        monkeypatch,
        lambda: (parse_library(_PEEK_LIBRARY, _LIB_FILE),),
        _host(
            zones="secret[player] : HiddenPile<player>",
            defs="function ready(p : Player) = any card in secret[1] where true",
        ),
    )
    if not bag:
        raise RuntimeError("the hidden read was accepted")
    _assert(bag, Reject(GAME, ("ready",)))


# --- Axis 6: the row's own spelling, at parse --------------------------------

_SPELLING: dict[str, tuple[str, tuple[str, ...]]] = {
    "function_keyword": (
        "function ready(p : Player) : Boolean",
        ("`ready(p : Player) : Boolean`", "keyword"),
    ),
    "procedure_keyword": (
        "procedure settle(p : Player)",
        ("`settle(p : Player) : Procedure`", "keyword"),
    ),
    "procedure_keyword_with_result": (
        "procedure settle(p : Player) : Procedure",
        ("`settle(p : Player) : Procedure`", "keyword"),
    ),
    "whole_definition": ("function ready(p : Player) = true", ()),
    "colon_forgotten": ("ready(p : Player)", ()),
    "collection_result": ("ready(p : Player) : Collection<Card>", ("Collection<Card>",)),
    "collection_parameter": ("ready(c : Collection<Card>) : Boolean", ("Collection<Card>",)),
    "move_with_parentheses": ("fold() : Move", ("`fold : Move`",)),
    # Habits from the neighbouring row shapes and definition headers. Each is
    # a syntax error in the library's file; none parses as something else.
    "arrow_result": ("ready(p : Player) -> Boolean", ()),
    "default_body": ("ready(p : Player) : Boolean = true", ()),
    "procedure_body": ("settle(p : Player) : Procedure { acted[p] := true }", ()),
    "reads_clause": ("ready(p : Player) : Boolean reads acted", ()),
    "indexed_signature": ("ready[player](p : Player) : Boolean", ()),
    "type_only_parameter": ("ready(Player) : Boolean", ()),
    "reserved_parameter_name": ("ready(none : Player) : Boolean", ("'none'",)),
}


@pytest.mark.parametrize("case", sorted(_SPELLING))
def test_a_misspelled_row_is_told_the_row_to_write(case: str) -> None:
    row, needles = _SPELLING[case]
    bag = _alone(lambda: _library("functions", rows=row, use=""))
    _assert(bag, Reject(LIBRARY, needles))
