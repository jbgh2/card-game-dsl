"""A write fits the shape of the variable it writes.

property:   an assignment or a `rotate` whose target cannot take it is
            refused at check time, naming the spelling that fits: `+=` and
            `-=` need an Integer (an `Integer?` is admitted; adding to its
            `none` is refused at play); an index needs a keyed variable, and
            a keyed variable needs an index to take `+=` or `-=`; `rotate`
            cycles a variable holding one value through values it can hold.
            Every write that fits checks clean.
domain:     write statement x declared type x optional x keyed x index
            form. Statements: the grammar's `ASSIGN_OP` alternatives and
            `rotate`; types: `typecheck.KNOWN_TYPE_NAMES`, each with and
            without `?`; shape: one value, or one per player; index: bare,
            or `[0]` (`rotate` takes no index in the grammar). The written
            value is always one of the target's own type, so a refusal is
            the shape's, never the value's; a mismatched value is
            `_check_assign`'s `cannot assign` cell, pinned elsewhere.
registry:   operators: `cardlang.parse._parser()`'s `ASSIGN_OP` terminal;
            types: `cardlang.typecheck.KNOWN_TYPE_NAMES`; values per type:
            `_VALUES` below, pinned to that registry.
does not prove:  a computed value's shape: the value is a literal of the
            target's type here.
"""

from __future__ import annotations

import random
import re

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _parser
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.typecheck import KNOWN_TYPE_NAMES


def _assign_ops() -> tuple[str, ...]:
    (term,) = [t for t in _parser().terminals if t.name == "ASSIGN_OP"]
    regexp = term.pattern.to_regexp()
    match = re.fullmatch(r"\(\?:(.*)\)", regexp)
    assert match is not None, regexp
    return tuple(alt.replace("\\", "") for alt in match.group(1).split("|"))


OPS = _assign_ops()
STATEMENTS = (*OPS, "rotate")

# type -> (a default, a second value of the type, and, for an enum, two of
# its values to rotate through)
_VALUES: dict[str, tuple[str, str]] = {
    "Integer": ("0", "1"),
    "Boolean": ("false", "true"),
    "Player": ("0", "1"),
    "Team": ("0", "1"),
    "Suit": ("hearts", "spades"),
    "Rank": ("Q", "K"),
    "SeatDirection": ("left", "right"),
    "String": ('"a"', '"b"'),
    "Card": ("A of spades", "K of hearts"),
}
_ENUMS = frozenset({"Suit", "Rank", "SeatDirection"})


def test_every_declarable_type_has_values() -> None:
    """red under: add a name to `KNOWN_TYPE_NAMES`."""
    assert set(_VALUES) == KNOWN_TYPE_NAMES
    assert set(OPS) == {":=", "+=", "-="}


_HOST = """game G {{
  players: 2
  max_length: 20
  cards: standard52
  ranking: aces high
  teams: [[0], [1]]
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0  {decl} }}
  phase play {{
    {stmt}
  }}
  winner: highest score
}}
"""


def _source(type_name: str, optional: bool, keyed: bool, stmt: str, indexed: bool) -> str:
    default, value = _VALUES[type_name]
    declared = type_name + ("?" if optional else "")
    decl = f"x{'[player]' if keyed else ''} : {declared} = {'none' if optional else default}"
    if stmt == "rotate":
        through = (default, value) if type_name in _ENUMS else _VALUES["SeatDirection"]
        line = f"rotate x through [{through[0]}, {through[1]}]"
    else:
        line = f"x{'[0]' if indexed else ''} {stmt} {'1' if stmt != ':=' else value}"
    return _HOST.format(decl=decl, stmt=line)


def _expected(type_name: str, optional: bool, keyed: bool, stmt: str, indexed: bool) -> str | None:
    """None: checks clean. Otherwise a phrase of the refusal ("" when another
    check owns it)."""
    if stmt == "rotate":
        if keyed:
            return "holds one per player"
        return None if type_name in _ENUMS else "cannot hold"
    if indexed and not keyed:
        return "takes no index"
    if keyed and not indexed:
        return "" if stmt == ":=" else "needs one of them"
    if stmt in ("+=", "-=") and type_name != "Integer":
        return "needs an Integer"
    return None


CELLS = [
    pytest.param(t, opt, keyed, stmt, idx, id=f"{t}{'?' if opt else ''}-{'keyed' if keyed else 'one'}-{stmt}-{'indexed' if idx else 'bare'}")
    for t in sorted(KNOWN_TYPE_NAMES)
    for opt in (False, True)
    for keyed in (False, True)
    for stmt in STATEMENTS
    for idx in ((False,) if stmt == "rotate" else (False, True))
]


@pytest.mark.parametrize(("type_name", "optional", "keyed", "stmt", "indexed"), CELLS)
def test_a_write_fits_its_target(
    type_name: str, optional: bool, keyed: bool, stmt: str, indexed: bool
) -> None:
    src = _source(type_name, optional, keyed, stmt, indexed)
    expected = _expected(type_name, optional, keyed, stmt, indexed)
    if expected is None:
        check_dsl(src, "g.cardlang")
        return
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "g.cardlang")
    assert expected in str(exc.value), str(exc.value)


@pytest.mark.parametrize(
    ("line", "fix"),
    [
        pytest.param("x += 1", "`x := true`", id="boolean"),
        pytest.param("p += 1", "offset_by", id="player"),
        pytest.param("score += 1", "`score[<player>] += ", id="keyed"),
        pytest.param("x[0] := true", "`x := ", id="unkeyed-index"),
    ],
)
def test_each_refusal_names_the_spelling_that_fits(line: str, fix: str) -> None:
    src = _HOST.format(decl="x : Boolean = false  p : Player = 0", stmt=line)
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "g.cardlang")
    assert fix in str(exc.value), str(exc.value)


def test_adding_to_none_is_refused_at_play() -> None:
    """An `Integer?` target is admitted: whether it holds `none` is runtime
    data, so the add is refused at play, naming the variable.

    red under: drop `_apply`'s `none` refusal."""
    src = _HOST.format(decl="x : Integer? = none", stmt="x += 1")
    with pytest.raises(OwnerGuardError, match="`x` holds `none`"):
        play_game(check_dsl(src, "g.cardlang"), random.Random(0))
