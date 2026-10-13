"""A library body naming something it may not reach is told what the name IS.

property:   every name a family library's body writes where the library
            cannot reach it is refused, located in the library file, with a
            message whose claim about the name is true whichever game imports
            the library. A CALL is answered from the library and then the
            language: the library's own definition, a contracted or kernel
            name, a type or a direction value is named as what it is, a
            Primitive gets the rule that keeps it out of a library and a fix
            that checks clean, a walled Primitive gets the slot its label
            names, and a trick winner gets the round slot that takes it. A
            BARE READ is answered from the library alone: its own definition
            or contracted move type is named as what it is, and every other
            name -- a language spelling, a deck spelling, anything else --
            keeps the missing-contract advice, because an importing game may
            declare state under that spelling, and the end-to-end rows run
            that fix clean for every such category.
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
            encapsulation Owner Guard (a deck spelling's first member outside
            500's deck, where the end-to-end rows run); the two full-width
            sweeps run every identifier-spelled member of those registries,
            one per position. An empty walled namespace contributes no cell,
            having no member a body could write. The `check_dsl` rows run
            through 500: the Primitive refusal beside the fix it names, and
            the contract fix for a bare read of each category that is not
            the library's own.
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
            sentence at a call -- the call sweep asserts only the absence of
            the unknown-name claim, and exact call wording runs on one
            representative per category. Nor that the contract fix runs
            clean for every member: it runs for one representative per
            category, through one importer. Nor anything about the
            bare-string slots a library names (`_slot_leaks`), whose wording
            is `_NAMESPACE_NOUN` x `_NAMESPACE_ADVICE`.
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

# The deck of the importing game the end-to-end rows run through: a deck
# spelling stands for a state name only in a game whose deck does not hold it.
_HOST_DECK = "five_hundred43"


def _deck_names(of: str, *, outside: str | None = None) -> frozenset[str]:
    names = suit_names if of == "suit" else rank_names
    held = names(outside) if outside is not None else frozenset()
    return frozenset(
        x for deck in DECKS for x in names(deck) if x.isidentifier() and x not in held
    )


_WALLED = frozenset().union(*WALLED_NAMESPACES.values())

# category -> (representative, extra library source, the noun a refusal names
# it by: None where the cell's sentence is its own).
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
    "suit": (min(_deck_names("suit", outside=_HOST_DECK)), "", None),
    "rank": (min(_deck_names("rank", outside=_HOST_DECK) - _deck_names("suit")), "", None),
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

# The categories the library itself holds -- the same whichever game imports
# it. Every other category is a spelling an importing game may also declare
# as state, so a bare read of it may be a missing contract entry.
_LIBRARY_OWN = frozenset(c for c in _CATEGORIES if c.startswith(("own ", "contracted ")))

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


def _primitive_rule(name: str) -> str:
    return (
        f"library '{_LIB}' calls '{name}', which is a Primitive — a Primitive "
        f"belongs to the one game that declares it, so a library that several "
        f"games import may not call one: compute the value in the game and pass "
        f"it to the library's function as an argument, or keep the definition "
        f"that needs it in the game"
    )


def _missing_contract(name: str) -> str:
    return (
        f"library '{_LIB}' reads '{name}', which is neither in its `requires` "
        f"contract nor defined in the library — add it to `requires {{ }}` if "
        f"the including game must declare it, or move the definition that "
        f"needs it into the game"
    )


def _unknown_call(name: str) -> str:
    return (
        f"library '{_LIB}' calls '{name}', which is neither defined in the "
        f"library nor a native function — a library's definitions may not "
        f"reach into the game that imports them"
    )


def _expected(category: str, position: str) -> str | None:
    """The one message each cell yields, or None for a clean cell."""
    name, _, noun = _CATEGORIES[category]
    if position == "read":
        if category in _READ_CLEAN:
            return None
        if category not in _LIBRARY_OWN:
            return _missing_contract(name)
        call_it = f" — call it: `{name}(...)`" if category == "own functions" else ""
        return f"library '{_LIB}' reads '{name}', which is a {noun}, not a value{call_it}"
    if category in ("own functions", "builtin call", "callable trick winner"):
        return None
    if category == "trick winner":
        return _callback_outside_slot(name)
    if category == "primitive":
        return _primitive_rule(name)
    if category in ("unknown", "suit", "rank"):
        return _unknown_call(name)
    phrase = category.removeprefix("walled: ") if category.startswith("walled: ") else f"a {noun}"
    return f"library '{_LIB}' calls '{name}', which is {phrase}, not a function"


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


# Every identifier-spelled name the language holds, at the full width of each
# registry the category axis samples. Directions are absent: a library body
# holds them as values.
_LANGUAGE_NAMES = frozenset(
    CALL_FUNCS
    | VALUE_NAMES
    | _WALLED
    | KNOWN_TYPE_NAMES
    | frozenset(LIBRARY_ZONE_TYPES)
    | LIBRARY_MOVE_TYPES
    | frozenset(stdlib_rules())
)


def test_no_language_name_is_called_unknown_at_a_library_call() -> None:
    """Every language name called in a library body is told what it is: none
    is told it is neither defined nor native."""
    wrong = {
        name: message
        for name in sorted(_LANGUAGE_NAMES)
        for message in _messages(f"library {_LIB} {{ {_POSITIONS['call'].format(name=name)} }}")
        if "nor a native function" in message
    }
    assert not wrong, wrong


def test_every_spelling_an_importer_may_declare_keeps_the_contract_advice_when_read() -> None:
    """Every language name and every deck spelling, read bare in a library
    body, is answered as the missing contract entry it may be, and nothing
    else is claimed about it."""
    spellings = _LANGUAGE_NAMES | _deck_names("suit") | _deck_names("rank")
    wrong = {
        name: got
        for name in sorted(spellings)
        if (got := _messages(f"library {_LIB} {{ {_POSITIONS['read'].format(name=name)} }}"))
        != [_missing_contract(name)]
    }
    assert not wrong, wrong


# --- end to end through 500: the refusal, and each fix it names --------------

_FIVE_HUNDRED = Path(__file__).resolve().parent.parent / "docs" / "games" / "five-hundred.cardlang"
_LIBRARY_FILE = f"docs/libraries/{_LIB}.cardlang"
_BID_VALUE = "let value = five_hundred_bid_value(bid_rank)"
_STATE_ANCHOR = "    trump_suit     : Suit?   = none"


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
    assert diagnostic.message == _primitive_rule("five_hundred_bid_value")
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


@pytest.mark.parametrize(
    "category", sorted(set(_CATEGORIES) - _LIBRARY_OWN - _READ_CLEAN - {"unknown"})
)
def test_a_bare_read_of_a_language_or_deck_spelling_is_fixed_by_the_contract(
    category: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why a bare read keeps the contract advice: the library contracts for the
    spelling, an importer declares state under it, and the game checks clean.
    red under: splicing only the game's own definitions in `_apply_uses`
    (no `from_libraries`)."""
    name, _, _ = _CATEGORIES[category]
    _five_hundred_with(
        f"library {_LIB} {{ requires {{ {name} : Integer }} function bump() = {name} + 1 }}",
        {
            _STATE_ANCHOR: f"    {name} : Integer = 0\n{_STATE_ANCHOR}",
            _BID_VALUE: "let value = five_hundred_bid_value(bid_rank) + bump()",
        },
        monkeypatch,
    )
