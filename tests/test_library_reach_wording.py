"""A library body naming something it may not reach is told what the name IS.

property:   every name a family library's body writes where the library
            cannot reach it is refused, located in the library file, with a
            message whose claim about the name is true -- a Primitive is
            called a Primitive, with the rule that keeps it out of a library
            and a fix that checks clean; a walled Primitive gets the slot its
            label names; a trick winner gets the round slot that takes it; a
            suit or rank gets the reason a library names none, with a fix
            that checks clean; the library's own definition, a contracted or
            kernel name, a type or a direction value is named as what it is;
            and only a name that is none of these is told it is neither
            defined in the library nor native code.
domain:     name category x position. The category axis: every native-name
            registry (`BUILTIN_CALL_FUNCS`, `VALUE_NAMES` split by
            callability, `PRIMITIVE_CALL_FUNCS`, each non-empty member of
            `WALLED_NAMESPACES`); every library definition kind
            (`_LIBRARY_DEF_KINDS`); every contract kind a library body names
            (state, zone, move type); the closed tables a body names without
            a contract (`SEAT_DIRECTION_VALUES`, `KNOWN_TYPE_NAMES`,
            `LIBRARY_ZONE_TYPES`, `LIBRARY_MOVE_TYPES`, the stdlib rules);
            every card deck's suits and ranks (`DECKS`); and a name that is
            none of these, which is where a name only the importing game
            declares, a pronoun, a binder and a misspelling all land. The
            position axis is the two expression positions a body names a
            thing in: a call `name(...)` and a bare name. Each category is
            probed through its alphabetically first member against the
            encapsulation Owner Guard; the full-width sweep runs every
            identifier-spelled member of those registries in both positions.
            An empty walled namespace contributes no cell, having no member a
            body could write. Four `check_dsl` rows run two cells end to
            end through 500, the corpus game whose own text holds both
            shapes: the Primitive refusal and the suit refusal, each beside
            the fix it names, checking clean.
registry:   native names: `cardlang.builtins.functions` (`BUILTIN_CALL_FUNCS`,
            `PRIMITIVE_CALL_FUNCS`, `VALUE_NAMES`) and
            `cardlang.primitives_block.WALLED_NAMESPACES`; definition kinds:
            `cardlang.resolve._LIBRARY_DEF_KINDS`; closed tables:
            `cardlang.stdlib.enums.SEAT_DIRECTION_VALUES`,
            `cardlang.typecheck.KNOWN_TYPE_NAMES`,
            `cardlang.stdlib.zones.LIBRARY_ZONE_TYPES`,
            `cardlang.stdlib.moves.LIBRARY_MOVE_TYPES`,
            `cardlang.stdlib.rules.stdlib_rules`; decks:
            `cardlang.runtime.values.DECKS`; the trick-winner sentence:
            `cardlang.resolve._callback_outside_slot`, pinned for game
            positions at tests/test_bare_callback_names.py.
does not prove:  that each member of a registry earns its category's exact
            sentence -- the full-width sweep asserts only the absence of
            the false claims, and exact wording runs on one representative
            per category. Nor anything about the bare-string slots a library
            names (`_slot_leaks`), whose wording is `_NAMESPACE_NOUN` x
            `_NAMESPACE_ADVICE`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    CALL_FUNCS,
    PRIMITIVE_CALL_FUNCS,
    VALUE_NAMES,
)
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import WALLED_NAMESPACES
from cardlang.resolve import (
    _LIBRARY_DEF_KINDS,
    _callback_outside_slot,
    _check_library_encapsulation,
)
from cardlang.runtime.values import DECKS
from cardlang.stdlib.enums import SEAT_DIRECTION_VALUES, rank_names, suit_names
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import stdlib_rules
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.typecheck import KNOWN_TYPE_NAMES

_LIB = "probelib"

# A definition of each kind, spelled under the probe's target name.
_DEF_SOURCE: dict[str, str] = {
    "rules": "rule {name} {{ }}",
    "move_types": "move_type {name} {{ effect {{ }} }}",
    "functions": "function {name}() = 1",
    "procedures": "procedure {name}() {{ }}",
}

# Each contract kind, naming the probe's target.
_REQUIRES_SOURCE: dict[str, tuple[str, str]] = {
    # kind -> (contract source, the noun the refusal names it by)
    "state": ("requires {{ {name} : Integer }}", "state variable"),
    "zone": ("requires {{ {name} : Discard }}", "zone"),
    "move type": ("requires {{ {name} : Move }}", "move type"),
}

_POSITIONS: dict[str, str] = {
    "call": "function probe(p : Player) = {name}(p)",
    "read": "function probe(p : Player) = {name}",
}

_UNKNOWN = "frobnicate"


def _deck_names(of: str) -> frozenset[str]:
    names = suit_names if of == "suit" else rank_names
    return frozenset(x for deck in DECKS for x in names(deck) if x.isidentifier())


_WALLED = frozenset().union(*WALLED_NAMESPACES.values())

# category -> (representative, extra library source, the noun a refusal
# names it by: None where the cell's sentence is its own).
_CATEGORIES: dict[str, tuple[str, str, str | None]] = {
    **{
        f"own {field}": ("target", _DEF_SOURCE[field].format(name="target"), f"{noun} the library defines")
        for field, noun in _LIBRARY_DEF_KINDS
    },
    **{
        f"contracted {kind}": ("target", source.format(name="target"), noun)
        for kind, (source, noun) in _REQUIRES_SOURCE.items()
    },
    "direction value": (min(SEAT_DIRECTION_VALUES), "", "direction value"),
    "type": (min(KNOWN_TYPE_NAMES), "", "type"),
    "zone type": (min(LIBRARY_ZONE_TYPES), "", "type"),
    "kernel move type": (min(LIBRARY_MOVE_TYPES), "", "move type"),
    "stdlib rule": (min(stdlib_rules()), "", "rule"),
    "suit": (min(_deck_names("suit")), "", None),
    "rank": (min(_deck_names("rank") - _deck_names("suit")), "", None),
    "builtin call": (min(BUILTIN_CALL_FUNCS - VALUE_NAMES), "", None),
    "callable trick winner": (min(BUILTIN_CALL_FUNCS & VALUE_NAMES), "", None),
    "trick winner": (min(VALUE_NAMES - BUILTIN_CALL_FUNCS), "", None),
    **{
        f"walled: {label}": (min(names), "", None)
        for label, names in WALLED_NAMESPACES.items()
        if names
    },
    "primitive": (min(PRIMITIVE_CALL_FUNCS), "", None),
    "unknown": (_UNKNOWN, "", None),
}

# The reads that resolve: a contracted state variable or zone, and a direction
# value, are values a library body holds.
_READ_CLEAN = frozenset({"contracted state", "contracted zone", "direction value"})


def _messages(library_text: str) -> list[str]:
    bag = DiagnosticBag()
    _check_library_encapsulation(parse_library(library_text, f"{_LIB}.cardlang"), bag)
    return [d.message for d in bag.items]


def _probe(category: str, position: str) -> list[str]:
    name, extra, _ = _CATEGORIES[category]
    return _messages(f"library {_LIB} {{ {extra}\n {_POSITIONS[position].format(name=name)} }}")


def _primitive_rule(name: str, verb: str) -> str:
    return (
        f"library '{_LIB}' {verb} '{name}', which is a Primitive — a Primitive "
        f"belongs to the one game that declares it, so a library that several "
        f"games import may not call one: compute the value in the game and pass "
        f"it to the library's function as an argument, or keep the definition "
        f"that needs it in the game"
    )


def _deck_rule(name: str, noun: str) -> str:
    return (
        f"library '{_LIB}' reads '{name}', which is a {noun}, but a family "
        f"library is deck-agnostic — its members do not share a deck: take the "
        f"{noun} as a parameter, or keep the definition that needs it in the game"
    )


def _expected(category: str, position: str) -> str | None:
    """The one message each cell yields, or None for a clean cell."""
    name, _, noun = _CATEGORIES[category]
    call = position == "call"
    verb = "calls" if call else "reads"
    if category in ("own functions", "builtin call", "callable trick winner") and call:
        return None
    if category in _READ_CLEAN and not call:
        return None
    if category in ("trick winner", "callable trick winner"):
        return _callback_outside_slot(name)
    if category == "primitive":
        return _primitive_rule(name, verb)
    if category in ("suit", "rank") and not call:
        return _deck_rule(name, category)
    if category == "unknown":
        if call:
            return (
                f"library '{_LIB}' calls '{name}', which is neither defined in the "
                f"library nor a native function — a library's definitions may not "
                f"reach into the game that imports them"
            )
        return (
            f"library '{_LIB}' reads '{name}', which is neither in its `requires` "
            f"contract nor defined in the library — add it to `requires {{ }}` if "
            f"the including game must declare it, or move the definition that "
            f"needs it into the game"
        )
    if category.startswith("walled: "):
        phrase = category.removeprefix("walled: ")
    elif category in ("suit", "rank"):
        phrase = f"a {category}"
    elif category == "builtin call":
        phrase = "a function"
    else:
        assert noun is not None, category
        phrase = f"a {noun}"
    tail = "not a function" if call else "not a value"
    if not call and category in ("own functions", "builtin call"):
        tail += f" — call it: `{name}(...)`"
    return f"library '{_LIB}' {verb} '{name}', which is {phrase}, {tail}"


@pytest.mark.parametrize(
    "category,position",
    [pytest.param(c, p, id=f"{c}|{p}") for c in _CATEGORIES for p in _POSITIONS],
)
def test_a_library_is_told_what_the_name_it_cannot_reach_is(category: str, position: str) -> None:
    expected = _expected(category, position)
    assert _probe(category, position) == ([] if expected is None else [expected])


def test_the_probe_library_is_otherwise_clean() -> None:
    """The control: the probe frame alone raises nothing, so every refusal a
    cell sees is its target's."""
    assert _messages(f"library {_LIB} {{ function probe(p : Player) = p }}") == []


# Every identifier-spelled name the language holds that a library body might
# write: the full width of each registry the category axis samples.
_HELD_NAMES = sorted(
    CALL_FUNCS
    | VALUE_NAMES
    | _WALLED
    | SEAT_DIRECTION_VALUES
    | KNOWN_TYPE_NAMES
    | frozenset(LIBRARY_ZONE_TYPES)
    | LIBRARY_MOVE_TYPES
    | frozenset(stdlib_rules())
    | _deck_names("suit")
    | _deck_names("rank")
)

# The claims the unknown-name sentences make, false of every held name.
_FALSE_OF_A_HELD_NAME = ("nor a native function", "nor defined in the library", "add it to `requires { }`")


@pytest.mark.parametrize("position", sorted(_POSITIONS))
def test_no_name_the_language_holds_is_called_unknown_in_a_library(position: str) -> None:
    """Every held name, in both positions: none is told it is neither defined
    nor native, and none is sent to the `requires` contract."""
    wrong = {
        name: message
        for name in _HELD_NAMES
        for message in _messages(f"library {_LIB} {{ {_POSITIONS[position].format(name=name)} }}")
        if any(claim in message for claim in _FALSE_OF_A_HELD_NAME)
    }
    assert not wrong, wrong


# --- end to end through 500: each refusal, and the fix it names --------------

_FIVE_HUNDRED = Path(__file__).resolve().parent.parent / "docs" / "games" / "five-hundred.cardlang"
_LIBRARY_FILE = f"docs/libraries/{_LIB}.cardlang"


def _five_hundred_with(
    library_text: str, edits: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    library = parse_library(library_text, _LIBRARY_FILE)
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: library)
    text = _FIVE_HUNDRED.read_text().replace("  players: 4", f"  uses {_LIB}\n  players: 4", 1)
    for old, new in edits.items():
        assert text.count(old) == 1, f"the probe's anchor {old!r} moved in five-hundred.cardlang"
        text = text.replace(old, new)
    check_dsl(text, "five-hundred.cardlang")


_BID_VALUE = "let value = five_hundred_bid_value(bid_rank)"
_SAME_COLOUR = (
    "function same_colour(s : Suit?) =\n"
    "  if s is spades then clubs elif s is clubs then spades\n"
    "  elif s is hearts then diamonds elif s is diamonds then hearts else joker\n"
)


def test_a_library_calling_a_primitive_its_importer_declares_is_told_the_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Through an importer whose `primitives { }` block DOES declare the
    Primitive the library calls: the refusal is the library's, not the
    importer's regime."""
    with pytest.raises(DiagnosticError) as exc:
        _five_hundred_with(
            f"library {_LIB} {{ function contract_value(rank : Integer) = five_hundred_bid_value(rank) }}",
            {_BID_VALUE: "let value = contract_value(bid_rank)"},
            monkeypatch,
        )
    diagnostic = exc.value.diagnostic
    assert diagnostic.message == _primitive_rule("five_hundred_bid_value", "calls")
    assert diagnostic.span is not None and diagnostic.span.source_name == _LIBRARY_FILE


def test_the_fix_the_primitive_refusal_names_checks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """The game computes the Primitive's value and passes it to the library's
    function as an argument. red under: splicing only the game's own
    definitions in `_apply_uses` (no `from_libraries`)."""
    _five_hundred_with(
        f"library {_LIB} {{ function contract_value(base : Integer) = base }}",
        {_BID_VALUE: "let value = contract_value(five_hundred_bid_value(bid_rank))"},
        monkeypatch,
    )


def test_a_library_naming_a_suit_is_told_it_is_deck_agnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    """500's own `same_colour`, moved into a library unchanged."""
    with pytest.raises(DiagnosticError) as exc:
        _five_hundred_with(f"library {_LIB} {{ {_SAME_COLOUR} }}", {_SAME_COLOUR: ""}, monkeypatch)
    diagnostic = exc.value.diagnostic
    assert diagnostic.message == _deck_rule("spades", "suit")
    assert diagnostic.span is not None and diagnostic.span.source_name == _LIBRARY_FILE


def test_the_fix_the_suit_refusal_names_checks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """The library takes the suits as parameters and the game passes its own.
    red under: splicing only the game's own definitions in
    `_apply_uses` (no `from_libraries`)."""
    _five_hundred_with(
        f"library {_LIB} {{ function colour_twin(s : Suit?, a : Suit, b : Suit, c : Suit, "
        f"d : Suit, other : Suit) = if s is a then b elif s is b then a elif s is c "
        f"then d elif s is d then c else other }}",
        {
            _SAME_COLOUR: "function same_colour(s : Suit?) =\n"
            "  colour_twin(s, spades, clubs, hearts, diamonds, joker)\n"
        },
        monkeypatch,
    )
