"""A `Positive` procedure parameter takes a whole number of 1 or more.

property:   an argument bound to a `Positive` parameter at a `run` is accepted
            exactly when it is a written number of 1 or more; a written 0 or
            negative number, and every computed argument, is refused at check
            time at the argument, naming the parameter and the procedure.
            Inside the body the parameter is an Integer, and a run plays at
            the number written.
domain:     argument form x run-site host x parameter position.
            The argument axis is the guard's own partition: a written number
            (`n.IntLit`, whose sign the parser folds in, so `-1` is one) split
            at 1, and every other expression. The non-literal arm does not
            branch on the expression's kind, so its cells are witnesses of one
            arm rather than an enumeration of `n.Expr`; they are the most
            plausible computed sizes (a state read, arithmetic, a conditional,
            a count, a function call) and a Boolean.
            The host axis is every definition a `run` can bind: a game phase
            running a game procedure, a game phase running a library
            procedure, a library move type's effect running the library's own
            procedure, and one running a procedure a `requires` row
            contracts. A procedure body never holds a `run` (resolve refuses
            it). The statement position a game's `run` stands at (a nested
            block, a move effect, a Hosted Poll body) is outside this axis:
            the guard reads every `RunStmt` the generic tree walk reaches,
            with no arm per position.
            The position axis is first, middle and last among the parameters,
            and two `Positive` parameters of which one is wrong.
registry:   the domain word: `cardlang.typecheck.POSITIVE_PARAM_DOMAIN`, a
            member of `cardlang.resolve._PROCEDURE_PARAM_DOMAINS`; the guard:
            `cardlang.resolve._check_positive_arguments`; the word at every
            other type position (refused there):
            tests/test_type_name_positions.py's `Positive` column and
            tests/test_definition_contracts.py's signature-row spellings; the
            word reserved from position domains: tests/test_positions.py; the
            domain among the procedure domains: tests/test_procedures.py.
does not prove:  that every rulebook size is a written number. A procedure
            whose size its rules compute from play cannot take `Positive`
            and declares `Integer`, which admits 0 and negatives; the
            domain refuses what it cannot see rather than checking it at play.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from unittest import mock

import pytest

from cardlang import pipeline
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.libraries import library_names, load_library
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

GAME = """
game P {{
  players: 2
  max_length: 30
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0  tick : Integer = 2 }}
  phase p {{
    deal 1 cards from deck to each hand
{body}
  }}
  winner: highest score
}}
{procs}
"""

ADD = "procedure add(who : Player, size : Positive) { score[who] += size }"


def _check(body: str, procs: str = ADD) -> n.Game:
    return check_dsl(GAME.format(body=body, procs=procs), "positive")


def _refused(body: str, procs: str = ADD) -> str:
    with pytest.raises(DiagnosticError) as excinfo:
        _check(body, procs)
    return str(excinfo.value)


# --- argument form, at a game procedure -------------------------------------

ACCEPTED = ("1", "2", "10")
REFUSED_NUMBERS = ("0", "-1", "-10")
COMPUTED = (
    "tick",
    "tick + 1",
    "1 + 1",
    "if tick > 1 then 2 else 3",
    "number of cards in deck",
    "twice()",
    "true",
)
TWICE = "\nfunction twice() = 2"


@pytest.mark.parametrize("arg", ACCEPTED)
def test_a_written_number_of_one_or_more_is_accepted(arg: str) -> None:
    _check(f"    run add(0, {arg})")


@pytest.mark.parametrize("arg", REFUSED_NUMBERS)
def test_a_written_number_below_one_is_refused(arg: str) -> None:
    msg = _refused(f"    run add(0, {arg})")
    assert "`size`" in msg and "'add'" in msg
    assert f"{arg} is not one" in msg


@pytest.mark.parametrize("arg", COMPUTED)
def test_a_computed_argument_is_refused(arg: str) -> None:
    msg = _refused(f"    run add(0, {arg})", ADD + TWICE)
    assert "`size`" in msg and "'add'" in msg
    assert "write the number itself" in msg


def test_a_parenthesized_number_is_a_written_number() -> None:
    """The parser drops grouping, so `(2)` is the number 2 at the guard.
    red under: refuse every argument that is not a bare INT token."""
    _check("    run add(0, (2))")


# --- the body, and play ------------------------------------------------------


def test_the_body_reads_the_parameter_as_an_integer() -> None:
    msg = _refused(
        "    run flag(1)",
        "procedure flag(size : Positive) { if size { score[0] += 1 } }",
    )
    assert "Boolean" in msg


def test_a_run_plays_at_the_number_written() -> None:
    game = _check("    run add(1, 3)")
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 0, 1: 3}


# --- parameter position ------------------------------------------------------


@pytest.mark.parametrize(
    ("procs", "good", "bad", "name"),
    [
        (
            "procedure f(size : Positive, who : Player) { score[who] += size }",
            "run f(2, 0)", "run f(0, 0)", "size",
        ),
        (
            "procedure f(who : Player, size : Positive, more : Integer) "
            "{ score[who] += size + more }",
            "run f(0, 2, 0)", "run f(0, 0, 0)", "size",
        ),
        (
            "procedure f(small : Positive, big : Positive) { score[0] += small + big }",
            "run f(1, 2)", "run f(1, 0)", "big",
        ),
    ],
    ids=["first", "middle", "second-of-two"],
)
def test_the_refusal_names_the_parameter_it_binds(
    procs: str, good: str, bad: str, name: str
) -> None:
    _check(f"    {good}", procs)
    msg = _refused(f"    {bad}", procs)
    assert f"`{name}`" in msg
    assert msg.count("Positive number") == 1


def test_an_integer_parameter_beside_it_keeps_its_own_domain() -> None:
    """The guard reads the parameter's domain, not its neighbours': a 0 bound
    to an `Integer` beside a `Positive` stands."""
    _check(
        "    run f(0, 2, 0)",
        "procedure f(who : Player, size : Positive, more : Integer) "
        "{ score[who] += size + more }",
    )


def test_an_optional_positive_is_not_a_domain() -> None:
    msg = _refused(
        "    run f(1)", "procedure f(size : Positive?) { score[0] += 1 }"
    )
    assert "unsupported domain" in msg


# --- library hosts -----------------------------------------------------------

LIBRARY = """library sizes {{
  requires {{
    pot : Integer
    {contract}
  }}
  procedure grow(size : Positive) {{ pot := pot + size }}
  move_type raise_pot {{
    effect {{ {effect} }}
  }}
}}
"""

LIB_GAME = """
game L {{
  players: 2
  max_length: 30
  cards: standard52
  uses sizes
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ pot : Integer = 0  score[player] : Integer = 0 }}
  phase p {{
    deal 1 cards from deck to each hand
    {body}
    offer to 0 one of [raise_pot]
    score[0] := pot
  }}
  winner: highest score
}}
{procs}
"""


@pytest.fixture
def library() -> Iterator[dict[str, str]]:
    """The library text the test writes, loaded under the name `sizes`."""
    holder = {"contract": "", "effect": "pot := pot + 1"}

    def load(name: str) -> n.Library:
        if name != "sizes":
            return load_library(name)
        return parse_library(LIBRARY.format(**holder), "docs/libraries/sizes.cardlang")

    names = library_names() | {"sizes"}
    with mock.patch("cardlang.resolve.load_library", load), mock.patch(
        "cardlang.resolve.library_names", lambda: names
    ):
        pipeline._check.cache_clear()
        try:
            yield holder
        finally:
            pipeline._check.cache_clear()


def _lib_check(body: str, procs: str = "") -> n.Game:
    return check_dsl(LIB_GAME.format(body=body, procs=procs), "positive-lib")


@pytest.mark.parametrize(("arg", "accepted"), [("2", True), ("0", False), ("pot", False)])
def test_a_game_running_a_library_procedure(
    library: dict[str, str], arg: str, accepted: bool
) -> None:
    if accepted:
        _lib_check(f"run grow({arg})")
        return
    with pytest.raises(DiagnosticError) as excinfo:
        _lib_check(f"run grow({arg})")
    assert "`size`" in str(excinfo.value) and "'grow'" in str(excinfo.value)


@pytest.mark.parametrize(("arg", "accepted"), [("2", True), ("0", False), ("pot", False)])
def test_a_library_move_type_running_the_library_s_own_procedure(
    library: dict[str, str], arg: str, accepted: bool
) -> None:
    library["effect"] = f"run grow({arg})"
    if accepted:
        _lib_check("run grow(1)")
        return
    with pytest.raises(DiagnosticError) as excinfo:
        _lib_check("run grow(1)")
    assert "`size`" in str(excinfo.value) and "'grow'" in str(excinfo.value)


@pytest.mark.parametrize(("arg", "accepted"), [("2", True), ("0", False), ("pot", False)])
def test_a_library_move_type_running_a_contracted_procedure(
    library: dict[str, str], arg: str, accepted: bool
) -> None:
    library["contract"] = "bump(by : Positive) : Procedure"
    library["effect"] = f"run bump({arg})"
    procs = "procedure bump(by : Positive) { pot := pot + by }"
    if accepted:
        _lib_check("run grow(1)", procs)
        return
    with pytest.raises(DiagnosticError) as excinfo:
        _lib_check("run grow(1)", procs)
    assert "`by`" in str(excinfo.value) and "'bump'" in str(excinfo.value)
