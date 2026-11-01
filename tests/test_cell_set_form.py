"""The position register's set form: `cells where <pred>`.

`<noun>s where <pred>` names the members of a declared position domain that
satisfy a predicate, in the domain's order, as a value: `Collection<Cell>`
for a board's `cell`, `Collection<Integer>` for an integer `positions { }`
name (decisions.md "Boards and cells"). It is the fourth fold of the bare
positional quantifier register (`any`, `all`, `number of`), the twin of
`players where <pred>` and `cards in <zone> where <pred>`. Its noun ranges
over the declared position domains alone: the board direction domain the
other three folds admit is refused by name. The collection twin `cells in
<expr> where <pred>` is not the language; the Diagnostic Grammar refuses it
naming the set form.

The grid, axis by axis, each read from where the language defines it:

  * GRID U -- the noun universe. For every game shape (a board, an integer
    domain, an integer domain named `cell`, boardless and positionless), the
    nouns are that game's own position domains
    (`board_domains.position_domains_of`), the direction domain's name
    (`DIRECTION_DOMAIN`), the collection nouns (`resolve._COLLECTION_NOUNS`)
    and one unknown spelling. A position domain is admitted; every other
    noun is refused naming the position domains alone.
  * GRID H -- the host: the set form at every expression host of the
    direction lift's grid (`tests/test_direction_lift.py::HOSTS`), each
    pinned to the AST field the query lands in.
  * GRID C -- the consumer: every slot is held to the answer a region
    verb's `Collection<Cell>` gets in the same slot (`home(0)`), admitted
    where it is admitted and refused with its message where it is refused,
    so the expected column is the region verb's, read live.
  * GRID R -- the runtime value: a tuple in the domain's order, equal by
    value to a region verb holding the same members and unequal to one that
    does not, empty when nothing matches, ascending over an integer domain,
    and its binder shadowing an outer one.
  * The grammar rows -- the set form parses once; the unparenthesized
    membership `x in cells where ...`, the `the`-led spelling and the fused
    spellings stay refused; the double-`where` sentence is an ambiguity the
    player register has too.
  * The twin rows -- the collection twin's shapes reach the ruled message,
    and the sentences it must not capture keep the main parser's error.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   `<noun>s where <pred>` over a declared position domain checks in
            every expression host, evaluates to the tuple of members
            satisfying the predicate in the domain's order, and meets every
            consumer slot exactly as a region verb's collection does; over
            any other noun it is refused naming the position domains; the
            collection twin led by `cells` is refused naming the set form,
            and no other sentence reaches that refusal.
domain:     {game shape} x {noun: the game's position domains, the
            direction domain, the collection nouns, one unknown} (GRID U);
            {host: tests/test_direction_lift.py::HOSTS} (GRID H); {consumer
            slot} x {the set form, the region verb} (GRID C); the runtime
            cells (GRID R); the grammar and twin rows. The set form takes
            the bare noun only: `cells in <expr> where` is not the
            language, and the twin is its one refusal, cut as the word its
            message names, so `columns in <expr> where` keeps the main
            parser's syntax error. The `connected` argument waits on the
            Builtin, issue #971.
registry:   nouns: cardlang/board_domains.py::position_domains_of,
            DIRECTION_DOMAIN, BOARD_DOMAIN; collection nouns:
            cardlang/resolve.py::_COLLECTION_NOUNS; hosts:
            tests/test_direction_lift.py::HOSTS; folds:
            cardlang/ast/nodes.py::DOMAIN_QUERY_KINDS; the phrase table:
            tests/test_cell_queries.py::test_the_phrase_table_is_the_kind_literal;
            corpus zero-ambiguity:
            tests/test_grammar_ambiguity.py::test_corpus_game_parses_with_zero_ambiguity;
            fused spellings: tests/keyword_fusion_sweep.py.
held by:    the fold axis is Unrepresentable: `DomainQueryKind`, matched
            with `assert_never` in the evaluator, the type checker and the
            IR. The noun universe is Derived and Pinned: a noun is a
            designer's string until resolve classifies it against
            `game.positions`, which no union the type checker sees can hold.
            The consumer slots are Unrepresentable in the type layer: the
            value is a `TCollection` like a region verb's, so each slot
            answers it by its existing rule. The tuple shape and the domain
            order are Born-Green Pins (GRID R), each naming its mutation.
does not prove:  that the consumer axis is every slot a collection can
            reach. It is the slots a designer writes a cell set into,
            authored rather than derived from the AST; what carries the rest
            is that the value's type is the region verbs' own, so a slot
            outside GRID C meets it as it meets `home(p)`.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from importlib import resources

import pytest
from lark import Lark, Tree
from lark.exceptions import LarkError

import cardlang.resolve as resolve_module
from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN, DIRECTION_DOMAIN, position_domains_of
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import IRDict, emit
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.resolve import _COLLECTION_NOUNS
from cardlang.runtime.driver import play_game
from cardlang.runtime.evaluate import evaluate
from cardlang.stdlib.boards import board_entry
from tests import test_direction_lift as lift
from tests.test_cell_queries import (
    NINE_CELLS,
    _board_ctx,
    _checked_board_expr,
    _checked_fc_expr,
    _count_ambig,
    _fc_ctx,
    _snippet,
    board_game,
    card_game,
)

# Every cell that writes the set form is refused at parse until the
# production lands. Each mark names the designed red: an acceptance cell
# raises the parse refusal, a message cell fails its assertion.
RED_ACCEPT = pytest.mark.xfail(
    strict=True, raises=DiagnosticError, reason="issue #972: the set form is not in the grammar yet"
)
RED_MESSAGE = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="issue #972: the set form is not in the grammar yet"
)

TWIN_MESSAGE = (
    "cells live on the board, not in a zone: the set form is `cells where <pred>`, "
    "with the membership in the predicate"
)
DIRECTION_REFUSAL = f"`{DIRECTION_DOMAIN}` is the board direction domain, not a position domain"
SYNTAX_ERROR = "syntax error: unexpected `where`"


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "set.cardlang")
    parts = [exc.value.diagnostic.message]
    parts.extend(getattr(exc.value, "__notes__", []) or [])
    return "\n".join(parts)


def _outcome(source: str) -> str | None:
    """None when the source checks, else the first refusal's message."""
    try:
        check_dsl(source, "set.cardlang")
    except DiagnosticError as exc:
        return exc.diagnostic.message
    return None


# --- GRID U: the noun universe ------------------------------------------------


def _integer_game(domain: str) -> str:
    """A boardless one-seat card game with one integer position domain."""
    return (
        "game IntegerSet {\n"
        "  players: 1\n"
        "  max_length: 30\n"
        "  cards: standard52\n"
        f"  positions {{ {domain} : 1..4 }}\n"
        f"  zones {{ deck : Deck  pile[{domain}] : Cascade<{domain}> }}\n"
        "  state { done : Boolean = false  score[player] : Integer = 0 }\n"
        "  phase p {\n"
        "    move all cards from deck to pile[1]\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
    )


SHAPES: dict[str, str] = {
    "board": board_game(),
    "integer domain": _integer_game("column"),
    "integer domain named cell": _integer_game(BOARD_DOMAIN),
    "boardless and positionless": card_game(body=""),
}

UNKNOWN_NOUN = "cellz"


def _declared(shape: str) -> list[str]:
    return sorted(position_domains_of(check_dsl(SHAPES[shape], "shape.cardlang")))


def _universe_cells() -> list[object]:
    cells: list[object] = []
    for shape in sorted(SHAPES):
        declared = _declared(shape)
        for noun in sorted({*declared, DIRECTION_DOMAIN, *_COLLECTION_NOUNS, UNKNOWN_NOUN}):
            admitted = noun in declared
            cells.append(
                pytest.param(
                    shape,
                    noun,
                    admitted,
                    id=f"{shape}-{noun}",
                    marks=RED_ACCEPT if admitted else RED_MESSAGE,
                )
            )
    return cells


def _universe_phrase(declared: list[str]) -> str:
    if not declared:
        return "this game declares no position domains"
    return f"declared position domains: {', '.join(declared)}"


@pytest.mark.parametrize(("shape", "noun", "admitted"), _universe_cells())
def test_the_set_forms_noun_is_a_position_domain(shape: str, noun: str, admitted: bool) -> None:
    """A position domain is admitted. The direction domain is refused by
    name; a collection noun and an unknown noun are refused naming the
    position domains. No refusal offers `in <collection>` (the set form has
    no collection twin) or the direction domain as a universe member."""
    source = SHAPES[shape] + f"function probe_set(p : Player) = {noun}s where true\n"
    if admitted:
        check_dsl(source, "set.cardlang")
        return
    message = _reject(source)
    universe = _universe_phrase(_declared(shape))
    if noun == DIRECTION_DOMAIN:
        assert DIRECTION_REFUSAL in message, message
    else:
        assert f"unknown position domain '{noun}' -- {universe}" in message, message
    assert universe in message, message
    assert "in <collection>" not in message, message
    assert "direction domain:" not in message, message


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        pytest.param(
            board_game() + "function probe_set(p : Player) = cell where true\n",
            "`cell where` needs the plural noun -- write `cells where`",
            id="board-cell",
        ),
        pytest.param(
            _integer_game("column") + "function probe_set(p : Player) = column where true\n",
            "`column where` needs the plural noun -- write `columns where`",
            id="integer-column",
        ),
    ],
)
@RED_MESSAGE
def test_a_singular_noun_is_guided_to_the_plural(source: str, needle: str) -> None:
    assert needle in _reject(source)


# --- GRID H: the host ---------------------------------------------------------


def _set_query_hosts(node: object, host: tuple[str, str] | None = None) -> Iterator[tuple[str, str]]:
    """For every set-form query in `node`, the (node type, field) of its
    nearest enclosing node that is not an expression."""
    if isinstance(node, (tuple, list)):
        for item in node:
            yield from _set_query_hosts(item, host)
        return
    if not is_dataclass(node) or isinstance(node, type):
        return
    if isinstance(node, n.DomainQuery) and node.source is None and node.binder == BOARD_DOMAIN:
        assert host is not None
        yield host
    for f in fields(node):
        child_host = host if type(node) in lift._EXPR_TYPES else (type(node).__name__, f.name)
        yield from _set_query_hosts(getattr(node, f.name), child_host)


@pytest.mark.parametrize("host", sorted(lift.HOSTS))
@RED_ACCEPT
def test_the_set_form_checks_in_every_host(host: str) -> None:
    """Each host's Boolean compares the set with itself over a call-free
    predicate, since a state default refuses every call."""
    build, field = lift.HOSTS[host]
    query = "(cells where true)"
    game = check_dsl(build(f"({query} is {query})"), "set.cardlang")
    assert list(_set_query_hosts(game)) == [field]


# --- GRID C: the consumer, held to the region verb's answer --------------------

# slot -> a board game writing `@SET@` in that slot. Every slot sits where `at`,
# `actor` and `t` are bound, so a refusal is the slot's own.
REGION = "home(0)"
SET_FORM = "(cells where square[cell] is empty)"


def _in_when(expr: str) -> str:
    return board_game(
        moves=(
            "move_type place(at : cell) {\n"
            f"  when: {expr}\n"
            "  effect { move one piece from reserve[actor] to square[at] }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        )
    )


def _in_effect(stmt: str) -> str:
    return board_game(
        moves=(
            "move_type place(at : cell) {\n"
            "  when: square[at] is empty\n"
            f"  effect {{ {stmt} }}\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        )
    )


def _in_turns(clause: str, body: str = "offer to t one of [place, stop]") -> str:
    return board_game().replace(
        "    turns t from 0 over all players until done {\n      offer to t one of [place, stop]\n",
        f"    turns t from 0 {clause} {{\n      {body}\n",
    )


CONSUMERS: dict[str, str] = {
    "membership of the move's cell": _in_when("at in @SET@"),
    "membership of an integer": _in_when("1 in @SET@"),
    "equality with a region verb": _in_when("(@SET@ is home(1)) or true"),
    "inequality with a region verb": _in_when("(@SET@ is not home(1)) or true"),
    "ordering": _in_when("@SET@ < @SET@"),
    "arithmetic": _in_when("(@SET@ + 1) > 0"),
    "emptiness": _in_when("@SET@ is empty"),
    "a subscript": _in_when("@SET@[0] is at"),
    "a member read": _in_when("@SET@.size > 0"),
    "a Boolean position": _in_when("@SET@"),
    "a collection quantifier's cell source": _in_when("all cells in @SET@ where true"),
    "a collection quantifier's line source": _in_when("any line in @SET@ where true"),
    "a card count's zone": _in_when("(number of cards in @SET@) > 0"),
    "a movement's amount": _in_effect("move @SET@ pieces from reserve[actor] to square[at]"),
    "a let then membership": _in_effect("let s = @SET@\n    if at in s { done := true }"),
    "an effect condition": _in_effect("if @SET@ { done := true }"),
    "a turn's participants": _in_turns("over @SET@ until done"),
    "the offer's seat": _in_turns("over all players until done", "offer to @SET@ one of [place, stop]"),
}


@pytest.mark.parametrize("slot", sorted(CONSUMERS))
@RED_MESSAGE
def test_a_consumer_answers_the_set_as_it_answers_a_region_verb(slot: str) -> None:
    """The region verb's outcome in the slot, read live, is the set form's.
    A refusal message names types, never the operand's text, so the two
    messages are equal; the red is the set form's parse refusal."""
    template = CONSUMERS[slot]
    region = _outcome(template.replace("@SET@", REGION))
    assert _outcome(template.replace("@SET@", SET_FORM)) == region, (slot, region)


def test_the_consumer_axis_commands_both_outcomes() -> None:
    """The consumer slots must hold both an admitted and a refused cell, or
    GRID C's equality would hold vacuously for a slot set the region verb
    meets one way."""
    outcomes = {slot: _outcome(t.replace("@SET@", REGION)) for slot, t in CONSUMERS.items()}
    assert any(o is None for o in outcomes.values()), outcomes
    assert any(o is not None for o in outcomes.values()), outcomes


@pytest.mark.xfail(strict=True, raises=DiagnosticError, reason="issue #971: `connected` is not a Builtin yet")
def test_the_set_is_a_connected_argument() -> None:
    check_dsl(
        _in_when("connected(home(0), far_row(0), cells where square[cell] is empty)"),
        "set.cardlang",
    )


# --- GRID R: the runtime value ------------------------------------------------


def _home(player: int) -> tuple[str, ...]:
    return board_entry("grid", (3, 3)).home(player)


@RED_ACCEPT
def test_the_set_is_a_tuple_in_the_domains_order() -> None:
    """Red under: `evaluate._domain_query`'s set arm returning a list."""
    game, expr = _checked_board_expr("cells where true")
    value = evaluate(expr, _board_ctx(game, {}))
    assert isinstance(value, tuple)
    assert value == NINE_CELLS


@RED_ACCEPT
def test_the_set_holds_the_satisfying_members_in_order() -> None:
    game, expr = _checked_board_expr("cells where square[cell] is not empty")
    assert evaluate(expr, _board_ctx(game, {"c3": "x", "a1": "o", "b2": "x"})) == ("a1", "b2", "c3")


@RED_ACCEPT
def test_nothing_satisfying_is_the_empty_set() -> None:
    game, expr = _checked_board_expr("cells where false")
    assert evaluate(expr, _board_ctx(game, {})) == ()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("(cells where cell in home(0)) is home(0)", True, id="same members"),
        pytest.param("(cells where cell in home(1)) is home(0)", False, id="other members"),
        pytest.param("(cells where cell in home(0)) is not home(0)", False, id="is not, same"),
        pytest.param(
            "(cells where cell in home(0)) is (cells where cell in home(0))", True, id="two sets"
        ),
    ],
)
@RED_ACCEPT
def test_equality_with_a_region_verb_is_by_value(source: str, expected: bool) -> None:
    """Both truth values against the region verb. Red under: the set arm
    returning a list, which no region verb's tuple equals (the `same
    members` cell). The control reads the region verb's own members."""
    assert set(_home(0)) != set(_home(1))
    game, expr = _checked_board_expr(source)
    assert evaluate(expr, _board_ctx(game, {})) is expected


@RED_ACCEPT
def test_the_inner_binder_shadows_the_outer() -> None:
    """The outer `cell` stands on the membership's left; the inner set binds
    its own. Every outer cell inside home(0) counts once."""
    game, expr = _checked_board_expr("number of cells where cell in (cells where cell in home(0))")
    assert evaluate(expr, _board_ctx(game, {})) == len(_home(0))


@RED_ACCEPT
def test_an_integer_domains_set_ascends() -> None:
    game, expr = _checked_fc_expr("columns where cascade[column] is empty")
    assert evaluate(expr, _fc_ctx(game, {2: 1, 4: 3})) == (1, 3)


@RED_ACCEPT
def test_the_set_form_plays() -> None:
    """The execution witness: a move may be made only on a cell of the set,
    and a uniform playout reaches the end."""
    game = check_dsl(_in_when("at in (cells where square[cell] is empty)"), "set.cardlang")
    play_game(game, random.Random(0))


# --- the IR -------------------------------------------------------------------


def _domain_queries(ir: object) -> Iterator[IRDict]:
    if isinstance(ir, dict):
        if ir.get("kind") == "domain_query":
            yield ir
        for value in ir.values():
            yield from _domain_queries(value)
    elif isinstance(ir, list):
        for item in ir:
            yield from _domain_queries(item)


@RED_ACCEPT
def test_the_ir_names_the_set_fold() -> None:
    ir = emit(check_dsl(_in_when("at in (cells where square[cell] is empty)"), "set.cardlang"))
    assert [q["query"] for q in _domain_queries(ir)] == ["set"]


# --- information sets and library text ---------------------------------------


def _hidden_game(when: str) -> str:
    return (
        "game HiddenSet {\n"
        "  players: 2\n"
        "  max_length: 30\n"
        "  cards: standard52\n"
        "  positions { column : 1..4 }\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { done : Boolean = false  score[player] : Integer = 0 }\n"
        "  phase p {\n"
        "    move all cards from deck where card.suit is hearts to hand[1]\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [pick]\n"
        "    }\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        "move_type pick(c : column) {\n"
        f"  when: {when}\n"
        "  effect { done := true }\n"
        "}\n"
    )


HIDDEN_READ = "(number of cards in hand[1] where card.rank is A) > 0"


@RED_MESSAGE
def test_a_hidden_read_in_the_body_is_judged_as_the_other_folds_are() -> None:
    """The set's body is judged at its enclosing clause, the When Clause:
    the same read under `any column where` gets the same verdict."""
    fold = _outcome(_hidden_game(f"any column where {HIDDEN_READ}"))
    assert fold is not None, "the control read must be refused at a deciding seat"
    assert _outcome(_hidden_game(f"c in (columns where {HIDDEN_READ})")) == fold


_LIB = "probe_set_lib"


@RED_ACCEPT
def test_a_library_naming_cells_is_refused_in_its_own_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A library names no board-minted domain; its set form is refused in
    its own file, as its `number of cells where` is."""
    body = "function lib_set(p : Player) = cells where true"
    library = parse_library(f"library {_LIB} {{\n{body}\n}}\n", f"docs/libraries/{_LIB}.cardlang")
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(board_game().replace("  players: 2\n", f"  uses {_LIB}\n  players: 2\n", 1), "set.cardlang")
    first = exc.value.diagnostic.format()
    assert first.startswith(f"docs/libraries/{_LIB}.cardlang:"), first
    assert "'cell'" in first, first


# --- the grammar --------------------------------------------------------------


@pytest.fixture(scope="module")
def explicit_parser() -> Lark:
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    return Lark(grammar, parser="earley", ambiguity="explicit", propagate_positions=True, maybe_placeholders=True)


H = "function holds(c : cell, p : Player) = (square[c] is not empty) and (top_of(square[c]).side is x)\n"


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(_in_when("at in cells where square[cell] is empty"), id="when membership"),
        pytest.param(
            _in_effect("if at in cells where square[cell] is empty { done := true }"),
            id="effect membership",
        ),
        pytest.param(board_game() + "function f(p : Player) = the cells where true\n", id="the-led"),
        pytest.param(board_game() + "function f(p : Player) = cellswhere true\n", id="fused noun"),
        pytest.param(board_game() + "function f(p : Player) = cells wheretrue\n", id="fused body"),
    ],
)
def test_a_sentence_beside_the_set_form_stays_a_syntax_error(source: str) -> None:
    """Membership's right side sits below the query forms, so
    `at in cells where P` is the parse refusal `x in players where P` gets;
    `the cells where` is not the set form; a fused spelling is not a word.
    Red under, per cell: the set form placed in `?primary` (the two
    membership cells); `_THE_KW QNOUN _WHERE_KW expr` added to `quantifier`
    (the `the`-led cell); `_WHERE_KW` without its lookahead (the fused
    body)."""
    message = _reject(source)
    assert message.startswith("syntax error"), message
    assert TWIN_MESSAGE not in message, message


def test_the_double_where_sentence_is_ambiguous_on_the_player_register(explicit_parser: Lark) -> None:
    """Recorded, not fixed: a collection quantifier whose source is a bare
    set form and whose predicate is a bare name derives two ways. The
    player register's `players where` has it in the same place; no corpus
    sentence writes it (the corpus sweep's pin)."""
    tree = explicit_parser.parse(_snippet("    if any cell in players where players where (n is 0) { n := 1 }\n"))
    assert isinstance(tree, Tree)
    assert _count_ambig(tree) == 1


@pytest.mark.xfail(strict=True, raises=LarkError, reason="issue #972: the set form is not in the grammar yet")
def test_the_double_where_sentence_is_ambiguous_on_the_position_register(explicit_parser: Lark) -> None:
    """The same class on the set form, recorded beside its player twin."""
    tree = explicit_parser.parse(_snippet("    if any cell in cells where mine where (n is 0) { n := 1 }\n"))
    assert isinstance(tree, Tree)
    assert _count_ambig(tree) == 1


# --- the collection twin -------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            _in_effect("let s = cells in home(actor) where square[cell] is empty"), id="let"
        ),
        pytest.param(
            _in_when("at in (cells in home(actor) where square[cell] is empty)"), id="parenthesized"
        ),
        pytest.param(
            _integer_game(BOARD_DOMAIN) + "function f(p : Player) = cells in [1, 2] where cell > 1\n",
            id="integer domain named cell",
        ),
    ],
)
@RED_MESSAGE
def test_the_collection_twin_names_the_set_form(source: str) -> None:
    assert TWIN_MESSAGE in _reject(source)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(_in_when("at in cells where square[cell] is empty"), id="cell membership"),
        pytest.param(
            _in_effect("if actor in players where player is 0 { done := true }"), id="player membership"
        ),
        pytest.param(
            _in_effect("let dests = home(actor)\n    if dests in cells where true { done := true }"),
            id="plural local",
        ),
        pytest.param(
            _integer_game("column") + "function f(p : Player) = columns in [1, 2] where column > 1\n",
            id="integer noun",
        ),
        pytest.param(board_game() + "function f(p : Player) = lines in lines(3) where true\n", id="lines"),
    ],
)
def test_the_twin_captures_no_other_sentence(source: str) -> None:
    """The twin is led by the word its message names, so a membership whose
    right side is a bare set form, and a collection twin over another noun,
    keep the main parser's syntax error. Red under: the twin led by
    `QNOUN` (every cell but `integer noun` and `lines`, which a plural-led
    twin also takes)."""
    message = _reject(source)
    assert message.startswith("syntax error"), message
    assert TWIN_MESSAGE not in message, message
