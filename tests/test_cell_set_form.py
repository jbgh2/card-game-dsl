"""The position register's Set Form: `cells where <pred>`.

`<noun>s where <pred>` names the members of a declared Position Domain that
satisfy a predicate, in the Position Domain's member order, as a collection:
`Collection<Cell>` for a board's `cell`, `Collection<Integer>` for an
integer `positions { }` name (decisions.md "Boards and cells"). It is the
fourth query kind of the bare positional quantifier register (`any`, `all`,
`number of`), the twin of `players where <pred>` and `cards in <zone> where
<pred>`. Its noun is a Position Domain alone: the board direction domain the
other three query kinds admit is refused by name. The collection twin
`cells in <expr> where <pred>` is not the language; the Diagnostic Grammar
refuses it naming the Set Form.

The grid, axis by axis, each read from where the language defines it:

  * GRID U -- the noun. For every game shape, the nouns are that game's
    Position Domains (`board_domains.position_domains_of`), the direction
    domain's name, the collection nouns, one unknown spelling, and one name
    of every kind resolve knows: its name categories (`resolve._categories`),
    its definitions as written, its reserved words (`resolve._RESERVED_WHY`)
    and the binders the language fixes. A Position Domain is admitted;
    every other noun is refused saying what it is, with the sentence that
    checks where the kind has one.
  * GRID H -- the host: the Set Form at every expression host of the
    direction lift's grid (`tests/test_direction_lift.py::HOSTS`), each
    pinned to the AST field the query lands in.
  * GRID P -- the position: the Set Form at every AST field an expression
    stands in (`resolve.HIDDEN_READ_POSITIONS`' keys), each with its
    authored outcome.
  * GRID C -- the operator consumer: the expression operators and the
    query sources a cell set meets, each held to the answer a Region
    Verb's `Collection<Cell>` gets in the same slot (`home(0)`), read live.
  * GRID R -- the runtime value: a tuple in the Position Domain's order,
    equal by member to a Region Verb holding the same members and unequal
    to one that does not, empty when nothing matches, ascending over an
    integer domain, and its binder shadowing an outer one.
  * The grammar rows -- the Set Form parses once; the unparenthesized
    membership `x in cells where ...`, the `the`-led spelling and the fused
    spellings stay refused; the double-`where` sentence is an ambiguity the
    player register has too; the query-kind tables are the compiled
    grammar's.
  * The twin rows -- on a board game the twin's words hold; the sentences
    it must not capture keep the main parser's error; and the three games
    where its words are false are strict xfails citing the operator's
    question on #972.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   `<noun>s where <pred>` over a declared Position Domain checks
            wherever an expression is a collection's place, evaluates to the
            tuple of members satisfying the predicate in the Position
            Domain's order, and meets every other position and operator in
            its typed channel, as a Region Verb's collection does; over any
            other noun it is refused saying what the name is; the collection
            twin led by `cells` is refused naming the Set Form, and no other
            sentence reaches that refusal.
domain:     {game shape} x {noun: GRID U's derived axis} (GRID U); {host:
            tests/test_direction_lift.py::HOSTS} (GRID H); {position:
            `HIDDEN_READ_POSITIONS`} (GRID P); {operator and source slot} x
            {the Set Form, the Region Verb} (GRID C); the runtime cells
            (GRID R); the grammar and twin rows. The Set Form takes the bare
            noun only: `cells in <expr> where` is not the language, and the
            twin is its one refusal, cut as the word its message names, so a
            collection twin over another noun keeps the main parser's syntax
            error.
registry:   nouns: cardlang/board_domains.py::position_domains_of,
            DIRECTION_DOMAIN, BOARD_DOMAIN; cardlang/resolve.py::_categories,
            _RESERVED_WHY, _COLLECTION_NOUNS; positions:
            cardlang/resolve.py::HIDDEN_READ_POSITIONS, pinned total by
            tests/test_hidden_reads.py::test_every_expression_position_is_bucketed;
            hosts: tests/test_direction_lift.py::HOSTS; query kinds:
            cardlang/ast/nodes.py::DOMAIN_QUERY_KINDS; the phrase table:
            tests/test_cell_queries.py::test_the_phrase_table_is_the_kind_literal;
            corpus zero-ambiguity:
            tests/test_grammar_ambiguity.py::test_corpus_game_parses_with_zero_ambiguity;
            fused spellings: tests/keyword_fusion_sweep.py.
held by:    the query-kind axis is Unrepresentable: `DomainQueryKind`, matched
            with `assert_never` in the evaluator, the type checker and the
            IR; `COLLECTION_QUERY_KINDS` is Derived and Pinned against the
            compiled grammar both ways. The noun universe is Derived and
            Pinned: a noun is a designer's string until resolve classifies
            it, which no union the type checker sees can hold. The positions
            are Unrepresentable in the type layer: the value is a
            `TCollection` like a Region Verb's, so each position answers it
            by its existing rule. The tuple shape and the member order are
            Born-Green Pins (GRID R), each naming its mutation.
does not prove:  that GRID C's operator slots are every operator a
            collection can meet: no registry lists the expression operators,
            so the slots are authored; what carries the rest is that the
            value's type is the Region Verbs' own.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from importlib import resources
from pathlib import Path
from typing import assert_never

import pytest
from lark import Lark, Tree

import cardlang.resolve as resolve_module
from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN, DIRECTION_DOMAIN, position_domains_of
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import IRDict, emit
from cardlang.parse import _diagnostic_parser, _parser as _main_parser, parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _COLLECTION_NOUNS
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.evaluate import evaluate
from cardlang.stdlib.boards import board_entry
from tests import test_direction_lift as lift
from tests.test_orphaned_surface_retired import _game as _trick_game
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


# A function and a procedure ride the board shape, and the trick game holds
# a rule, so every definition kind has a name to be written as a noun.
_TRICK_RULE = (
    "rule R {\n  constrains: play_to_trick\n"
    "  demands: cards in hand where card.suit is hearts\n  if_impossible: hand\n}\n"
)
SHAPES: dict[str, str] = {
    "board": board_game(
        moves=(
            "move_type place(at : cell) {\n"
            "  when: square[at] is empty\n"
            "  effect { move one piece from reserve[actor] to square[at] }\n"
            "}\n"
            "move_type stop { effect { run tidy() } }\n"
            "function helper(p : Player) = 1\n"
            "procedure tidy() { done := true }\n"
        )
    ),
    "integer domain": _integer_game("column"),
    "integer domain named cell": _integer_game(BOARD_DOMAIN),
    "boardless and positionless": card_game(body=""),
    "trick game": _trick_game(top=_TRICK_RULE),
}

UNKNOWN_NOUN = "cellz"

# What a refusal says each kind of name is. The kinds are resolve's own (its
# name categories, its definitions, its reserved words, the binders the
# language fixes); the names of each kind come from the game (`_noun_axis`).
KIND_WORDS: dict[str, str] = {
    "zone": "is a zone",
    "zone family": "is a zone family",
    "state variable": "is a state variable",
    "rank": "is a rank",
    "suit": "is a suit",
    "enum value": "is an enum value",
    "function": "is a function",
    "procedure": "is a procedure",
    "move type": "is a move type",
    "rule": "is a rule",
    "phase": "is a phase",
    "reserved word": "is a reserved word",
    "subset binder": "is the subset binder",
    "seat": "is a player's place in the turn ring",
    "piece binder": "is the piece binder",
}


def _declared(shape: str) -> list[str]:
    return sorted(position_domains_of(check_dsl(SHAPES[shape], "shape.cardlang")))


def _noun_axis(shape: str) -> dict[str, str]:
    """Every noun a bare query can be written over in `shape`, by its kind:
    the game's position domains, the direction domain's name, the collection
    nouns, one unknown spelling, and one name of every kind resolve knows
    (`resolve._categories`, the definitions, `resolve._RESERVED_WHY`, the
    fixed binders), each the first such name the game holds."""
    game = check_dsl(SHAPES[shape], "shape.cardlang")
    cats = resolve_module._categories(game)
    axis: dict[str, str] = {d: "position domain" for d in _declared(shape)}

    def first(names: object, kind: str) -> None:
        spellable = sorted(x for x in names if isinstance(x, str) and x.isidentifier())  # type: ignore[attr-defined]
        if spellable:
            axis.setdefault(spellable[0], kind)

    axis.setdefault(DIRECTION_DOMAIN, "direction domain")
    for noun in sorted(_COLLECTION_NOUNS):
        axis.setdefault(noun, "collection noun")
    axis.setdefault(UNKNOWN_NOUN, "unknown")
    first([z.name for z in game.zones if z.index is None], "zone")
    first([z.name for z in game.zones if z.index is not None], "zone family")
    first(cats.state_vars, "state variable")
    if game.content_flavor == "card":
        first(cats.ranks, "rank")
        first(cats.suits, "suit")
        first(cats.enums - cats.ranks - cats.suits, "enum value")
    else:
        first(cats.enums | cats.ranks | cats.suits, "enum value")
    # The definitions as written: a checked game has spliced its procedures.
    written = parse_text(SHAPES[shape], "shape.cardlang")
    for kind, defs in (
        ("function", written.functions),
        ("procedure", written.procedures),
        ("move type", written.move_types),
        ("rule", written.rules),
        ("phase", written.phases),
    ):
        first([d.name for d in defs], kind)
    for word in sorted(resolve_module._RESERVED_WHY):
        axis.setdefault(word, "reserved word")
    axis.setdefault(n.SUBSET_BINDER, "subset binder" if game.content_flavor == "card" else "unknown")
    axis.setdefault("seat", "seat")
    axis.setdefault("piece", "piece binder" if game.content_flavor == "piece" else "unknown")
    return axis


def _universe_cells() -> list[object]:
    return [
        pytest.param(shape, noun, kind, id=f"{shape}-{noun}")
        for shape in sorted(SHAPES)
        for noun, kind in sorted(_noun_axis(shape).items())
    ]


def _universe_phrase(declared: list[str]) -> str:
    if not declared:
        return "this game declares no position domains"
    return f"declared position domains: {', '.join(declared)}"


def _zone_fix(shape: str, zone: str) -> str:
    """The card query `cards in <zone> where` a zone noun's refusal offers,
    indexed by the zone family's first instance."""
    game = check_dsl(SHAPES[shape], "shape.cardlang")
    decl = next(z for z in game.zones if z.name == zone)
    if decl.index is None:
        return zone
    if decl.index == "player":
        return f"{zone}[0]"
    return f"{zone}[{position_domains_of(game)[decl.index][0]}]"


@pytest.mark.parametrize(("shape", "noun", "kind"), _universe_cells())
def test_a_bare_nouns_refusal_says_what_the_name_is(shape: str, noun: str, kind: str) -> None:
    """A position domain is admitted. Every other noun is refused saying what
    it is: the direction domain by name, a collection noun or an unknown
    noun as an unknown position domain naming the declared ones, and a name
    of any other kind as that kind, with the sentence that checks where one
    exists. No refusal speaks of a binder the designer did not write, offers
    `in <collection>` (the Set Form has no collection twin) or offers the
    direction domain as a universe member."""
    source = SHAPES[shape] + f"function probe_set(p : Player) = {noun}s where true\n"
    if kind == "position domain":
        check_dsl(source, "set.cardlang")
        return
    message = _reject(source)
    universe = _universe_phrase(_declared(shape))
    assert "pick another name" not in message, message
    assert "in <collection>" not in message, message
    assert "direction domain:" not in message, message
    if kind == "direction domain":
        assert DIRECTION_REFUSAL in message, message
    elif kind in ("collection noun", "unknown"):
        assert f"unknown position domain '{noun}' -- {universe}" in message, message
    else:
        assert f"`{noun}` {KIND_WORDS[kind]}" in message, message
    if kind in ("zone", "zone family") and "pieces" not in SHAPES[shape]:
        ref = noun if kind == "zone" else f"{noun}[…]"
        assert f"`cards in {ref} where <pred>`" in message, message
        check_dsl(
            SHAPES[shape] + f"function probe_fix(p : Player) = cards in {_zone_fix(shape, noun)} where true\n",
            "set.cardlang",
        )
    elif kind == "seat":
        assert "`players where <pred>`" in message, message
        check_dsl(SHAPES[shape] + "function probe_fix(p : Player) = players where true\n", "set.cardlang")
    elif kind == "subset binder":
        assert "`number of subsets of <n> [or more] cards in <zone> where <pred>`" in message, message
    elif kind in ("zone", "zone family", "piece binder"):
        assert "a movement" in message or "movement's" in message, message
    else:
        assert universe in message, message


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
def test_the_set_form_checks_in_every_host(host: str) -> None:
    """Each host's Boolean compares the set with itself over a call-free
    predicate, since a state default refuses every call."""
    build, field = lift.HOSTS[host]
    query = "(cells where true)"
    game = check_dsl(build(f"({query} is {query})"), "set.cardlang")
    assert list(_set_query_hosts(game)) == [field, field]


# --- GRID C: the consumer, held to the Region Verb's answer --------------------

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
    "equality with a Region Verb": _in_when("(@SET@ is home(1)) or true"),
    "inequality with a Region Verb": _in_when("(@SET@ is not home(1)) or true"),
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


def _channel(message: str | None) -> str | None:
    """A refusal as the slot gives it. A checker message names types, never
    the operand's text, so it compares whole; a parse refusal's expected-token
    list depends on the operand's first token, so it compares by channel."""
    if message is not None and message.startswith("syntax error"):
        return "syntax error"
    return message


@pytest.mark.parametrize("slot", sorted(CONSUMERS))
def test_a_consumer_answers_the_set_as_it_answers_a_region_verb(slot: str) -> None:
    """The Region Verb's outcome in the slot, read live, is the Set Form's."""
    template = CONSUMERS[slot]
    region = _channel(_outcome(template.replace("@SET@", REGION)))
    assert _channel(_outcome(template.replace("@SET@", SET_FORM))) == region, (slot, region)


def test_the_consumer_axis_commands_both_outcomes() -> None:
    """The consumer slots must hold both an admitted and a refused cell, or
    GRID C's equality would hold vacuously for a slot set the Region Verb
    meets one way."""
    outcomes = {slot: _outcome(t.replace("@SET@", REGION)) for slot, t in CONSUMERS.items()}
    assert any(o is None for o in outcomes.values()), outcomes
    assert any(o is not None for o in outcomes.values()), outcomes


def _integer_participants_game() -> str:
    """Two seats taking turns over an integer domain's set, whose members
    run past the seat count."""
    return (
        "game IntegerTurns {\n"
        "  players: 2\n"
        "  max_length: 30\n"
        "  cards: standard52\n"
        "  positions { column : 1..4 }\n"
        "  zones { deck : Deck  pile[column] : Cascade<column> }\n"
        "  state { done : Boolean = false  k : Integer = 0  score[player] : Integer = 0 }\n"
        "  phase p {\n"
        "    turns t from 0 over (columns where true) until done {\n"
        "      offer to t one of [tick]\n"
        "    }\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        "move_type tick { effect {\n"
        "  k := k + 1\n"
        "  if k > 5 { done := true }\n"
        "} }\n"
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #824: a computed non-seat in a turn's participants is dropped silently",
)
def test_an_integer_set_naming_no_seat_is_refused_as_participants() -> None:
    """An integer set coerces to a participants collection as an integer
    list does; a member naming no seat is a typed refusal at play, as the
    leader slot's is."""
    game = check_dsl(_integer_participants_game(), "set.cardlang")
    try:
        play_game(game, random.Random(0))
    except GameDescriptionError:
        return
    raise AssertionError("the members naming no seat were dropped from the ring")


@pytest.mark.xfail(strict=True, raises=DiagnosticError, reason="issue #971: `connected` is not a Builtin yet")
def test_the_set_is_a_connected_argument() -> None:
    check_dsl(
        _in_when("connected(home(0), far_row(0), cells where square[cell] is empty)"),
        "set.cardlang",
    )


# --- GRID P: every expression position ---------------------------------------
#
# The positions are `resolve.HIDDEN_READ_POSITIONS`' keys, the registry of
# every AST field an expression stands in (pinned total against the AST by
# tests/test_hidden_reads.py::test_every_expression_position_is_bucketed).
# Each position holds the Set Form once, in a board game over `cell` or a
# trick game over an integer `column`, and its expected outcome is authored.

BOARD_SET = "(cells where square[cell] is empty)"
COLUMN_SET = "(columns where column > 1)"
_LIFT_TURN = "offer to t one of [pick, stop]"


def _column_game(statement: str = "", top: str = "") -> str:
    return _trick_game(statement=statement, top=top).replace(
        "  ranking:", "  positions { column : 1..4 }\n  ranking:", 1
    )


def _column_rule(clauses: str) -> str:
    return _column_game(top="rule R {\n  constrains: play_to_trick\n" + clauses + "\n}")


def _moded(replace_where: str = "action.card.suit is spades", rule_arg: str | None = None) -> str:
    source = (REJECTIONS / "hidden_read_transition.cardlang").read_text().replace(
        "  ranking: aces high", "  ranking: aces high\n  positions { column : 1..4 }"
    )
    source = source.replace("where any card in hand[0] where card.suit is spades", f"where {replace_where}")
    if rule_arg is not None:
        source = source.replace(
            "    mode closed {\n",
            f"    mode closed {{\n      active_rules: [+ NoLeadingSuitUntilBroken({rule_arg})]\n",
        )
    return source


REJECTIONS = Path(__file__).parent / "rejections"
CHECKS = "checks"
B = lift.board_game

# position -> (the game with `@SET@` at the position, the expected outcome:
# `CHECKS`, or a needle the refusal holds).
POSITION_SLOTS: dict[tuple[str, str], tuple[str, str]] = {
    ("PhaseQualifier", "expr"): (B(phase_qualifier=" repeat until @SET@"), "condition must be Boolean, got Collection<Cell>"),
    ("MoveTypeDef", "when"): (B(when="@SET@"), "guard must be Boolean, got Collection<Cell>"),
    ("Transfer", "amount"): (
        B(effect="move @SET@ pieces from reserve[actor] to square[at]\n    done := true"),
        "expected an Integer, got Collection<Cell>",
    ),
    ("Transfer", "source"): (B(effect="move one piece from @SET@ to square[at]"), "syntax error"),
    ("Transfer", "where"): (
        B(setup="    move all pieces from reserve[0] where @SET@ to box\n"),
        "filter must be Boolean, got Collection<Cell>",
    ),
    ("Transfer", "dest"): (B(effect="move one piece from reserve[actor] to @SET@"), "syntax error"),
    ("Transfer", "visibility"): (
        B(effect="move one piece from reserve[actor] to square[at], visibility = @SET@"),
        "per-movement visibility overrides are not yet honored",
    ),
    ("LetStmt", "value"): (B(effect="let s = @SET@\n    done := true"), CHECKS),
    ("FunctionDef", "body"): (B(extra="function f(p : Player) = @SET@\n"), CHECKS),
    ("RunStmt", "args"): (
        B(effect="run bump(@SET@)", extra="procedure bump(k : Integer) { done := true }\n"),
        "expects Integer, got Collection<Cell>",
    ),
    ("AssignStmt", "value"): (B(state="    k : Integer = 0\n", effect="k := @SET@"), "cannot assign Collection<Cell>"),
    ("AssignStmt", "index"): (B(state="    k[player] : Integer = 0\n", effect="k[@SET@] := 1"), "got Collection<Cell>"),
    ("AssignStmt", "target"): (B(effect="@SET@ := 1"), "syntax error"),
    ("RotateStmt", "target"): (B(effect="rotate @SET@ through [a, b]"), "syntax error"),
    ("StateDecl", "default"): (B(state="    k : Integer = @SET@\n"), "its default has type Collection<Cell>"),
    ("IfStmt", "cond"): (B(effect="if @SET@ { done := true }"), "must be Boolean, got Collection<Cell>"),
    ("RepeatUntil", "until"): (B(effect="repeat until @SET@ { done := true }"), "must be Boolean, got Collection<Cell>"),
    ("AsBlock", "player"): (B(effect="as @SET@ { done := true }"), "must be a Player, got Collection<Cell>"),
    ("Offer", "player"): (
        B().replace(_LIFT_TURN, "offer to @SET@ one of [pick, stop]"),
        "expected a Player, got Collection<Cell>",
    ),
    ("Turns", "leader"): (
        B().replace("turns t from 0 over", "turns t from @SET@ over"),
        "expected a Player, got Collection<Cell>",
    ),
    ("Turns", "participants"): (
        B().replace("over all players until", "over @SET@ until"),
        "expected a collection of players, got Collection<Cell>",
    ),
    ("Turns", "until"): (B(until="@SET@"), "must be Boolean, got Collection<Cell>"),
    ("Loser", "selection"): (B(result="  loser: @SET@\n"), "expected a Player, got Collection<Cell>"),
    ("Choose", "lo"): (
        B(effect="let b = choose integer in @SET@ .. 3\n    done := true"),
        "expects an Integer lower bound, got Collection<Cell>",
    ),
    ("Choose", "hi"): (
        B(effect="let b = choose integer in 1 .. @SET@ up to 9\n    done := true"),
        "expects an Integer upper bound, got Collection<Cell>",
    ),
    ("Choose", "excluding"): (
        B(effect="let b = choose integer in 1 .. 3 excluding @SET@\n    done := true"),
        "expects an Integer `excluding` value, got Collection<Cell>",
    ),
    ("AppliesWhen", "pred"): (
        _column_rule("  applies_when: @SET@\n  demands: cards in hand where card.suit is hearts\n  if_impossible: hand"),
        "must be Boolean, got Collection<Integer>",
    ),
    ("Demands", "expr"): (_column_rule("  demands: @SET@\n  if_impossible: hand"), "got Collection<Integer>"),
    ("RuleDef", "if_impossible"): (
        _column_rule("  demands: cards in hand where card.suit is hearts\n  if_impossible: @SET@"),
        "got Collection<Integer>",
    ),
    ("RuleDef", "exempts"): (_column_rule("  exempts: @SET@"), "got Collection<Integer>"),
    ("RuleRef", "args"): (_moded(rule_arg="@SET@"), "must be a suit literal"),
    ("MoveEvent", "where"): (_moded(replace_where="@SET@"), "must be Boolean, got Collection<Integer>"),
    ("TrickRound", "leader"): (
        _column_game().replace("round play_to_trick from 0", "round play_to_trick from @SET@"),
        "expected a Player, got Collection<Integer>",
    ),
    ("TrickRound", "participants"): (
        _column_game().replace("from 0 over all players source", "from 0 over @SET@ source"),
        CHECKS,
    ),
    ("TrickRound", "trump"): (
        _column_game().replace(
            "winner highest_of_led_suit", "winner highest_trump_or_led_suit trump @SET@"
        ),
        "got Collection<Integer>",
    ),
    ("EpistemicOp", "zone"): (_column_game(statement="shuffle @SET@"), "syntax error"),
    ("EpistemicOp", "where"): (
        _column_game(statement="reveal one card from deck where @SET@"),
        "filter must be Boolean, got Collection<Integer>",
    ),
}

# A position no slot above holds, with the mark's reason (R4: each is typed
# by the check named, which the Set Form meets as any collection does).
UNHELD_POSITIONS: dict[tuple[str, str], str] = {
    ("ClimbRound", "leader"): "a climbing round needs a combination catalogue; untemplated here",
    ("ClimbRound", "participants"): "a climbing round needs a combination catalogue; untemplated here",
    ("ClimbRound", "until"): "a climbing round needs a combination catalogue; untemplated here",
    ("Produce", "payloads"): "a phase outcome needs a `produces:` arm to bind it; untemplated here",
}

# A slot whose outcome today is wrong, with the issue that holds it.
WRONG_TODAY: dict[tuple[str, str], str] = {
    ("Demands", "expr"): "issue #626: `demands:` accepts any value and enforces nothing",
    ("RuleDef", "exempts"): "issue #626: `exempts:` accepts any value and enforces nothing",
}


def test_the_position_axis_is_the_expression_position_registry() -> None:
    """Every key of `HIDDEN_READ_POSITIONS` is a slot or a recorded unheld
    position, and nothing else is. Red under: a position added to the
    registry with neither."""
    registry = {(node.__name__, field) for node, field in resolve_module.HIDDEN_READ_POSITIONS}
    assert set(POSITION_SLOTS).isdisjoint(UNHELD_POSITIONS)
    assert set(POSITION_SLOTS) | set(UNHELD_POSITIONS) == registry


def _position_cells() -> list[object]:
    cells: list[object] = []
    for key in sorted(POSITION_SLOTS):
        marks: list[pytest.MarkDecorator] = []
        if key in WRONG_TODAY:
            marks.append(pytest.mark.xfail(strict=True, raises=AssertionError, reason=WRONG_TODAY[key]))
        cells.append(pytest.param(key, id=".".join(key), marks=marks))
    for key, why in sorted(UNHELD_POSITIONS.items()):
        cells.append(pytest.param(key, id=".".join(key), marks=pytest.mark.skip(reason=why)))
    return cells


@pytest.mark.parametrize("key", _position_cells())
def test_the_set_form_at_every_expression_position(key: tuple[str, str]) -> None:
    """The Set Form at each position: admitted where a collection is a
    value (a `let`, a function body), refused in the typed channel naming
    `Collection<…>` where the position wants a Boolean, a seat, a number or
    a card set, and a syntax error where the position takes a name."""
    template, expected = POSITION_SLOTS[key]
    set_form = COLUMN_SET if "positions { column" in template else BOARD_SET
    source = template.replace("@SET@", set_form)
    outcome = _outcome(source)
    if expected == CHECKS:
        assert outcome is None, outcome
        hosts = [h for h in _all_set_hosts(check_dsl(source, "set.cardlang"))]
        assert key in hosts, hosts
    else:
        assert outcome is not None and expected in outcome, outcome


def _all_set_hosts(node: object, host: tuple[str, str] | None = None) -> Iterator[tuple[str, str]]:
    """The (node type, field) hosting every bare Set Form in `node`."""
    if isinstance(node, (tuple, list)):
        for item in node:
            yield from _all_set_hosts(item, host)
        return
    if not is_dataclass(node) or isinstance(node, type):
        return
    if isinstance(node, n.DomainQuery) and node.kind == "set":
        assert host is not None
        yield host
    for f in fields(node):
        child_host = host if type(node) in lift._EXPR_TYPES else (type(node).__name__, f.name)
        yield from _all_set_hosts(getattr(node, f.name), child_host)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #824: a computed non-seat in a round's participants crashes the round",
)
def test_an_integer_set_naming_no_seat_is_refused_as_a_rounds_participants() -> None:
    """The trick round over an integer set naming no seat: a typed refusal
    at play, as the turns ring's is to be."""
    template, _ = POSITION_SLOTS[("TrickRound", "participants")]
    game = check_dsl(template.replace("@SET@", COLUMN_SET), "set.cardlang")
    try:
        play_game(game, random.Random(0))
    except GameDescriptionError:
        return
    except Exception as exc:  # the defect's channel: a raw Python error
        raise AssertionError(f"the round crashed outside the typed channel: {exc!r}") from exc
    raise AssertionError("the members naming no seat were dropped from the round")


# --- the kind tables, from the compiled grammar ------------------------------


def _bare_query_kinds() -> tuple[set[str], set[str]]:
    """The kinds the grammar's `quantifier` rule builds over `QNOUN`, read
    from lark's compiled rules: each alternative's leading keywords, spelled
    by their terminals' patterns, are a kind's phrase; `_IN_KW` after the
    noun marks a collection form."""
    parser = _main_parser()
    words = {t.name: t.pattern.value.split("(?!")[0] for t in parser.terminals}
    by_phrase = {phrase: kind for kind, phrase in n.DOMAIN_QUERY_KIND_PHRASE.items()}
    bare: set[str] = set()
    collection: set[str] = set()
    for rule in parser.rules:
        if rule.origin.name != "quantifier":
            continue
        names = [sym.name for sym in rule.expansion]
        if "QNOUN" not in names:
            continue
        at = names.index("QNOUN")
        phrase = " ".join(words[name] for name in names[:at])
        kind = by_phrase[phrase]
        (collection if names[at + 1 : at + 2] == ["_IN_KW"] else bare).add(kind)
    return bare, collection


def test_the_kind_tables_are_the_grammars() -> None:
    """Both ways: every bare `QNOUN` alternative is a kind of the Literal and
    every kind has one; the kinds with a collection form are exactly
    `COLLECTION_QUERY_KINDS`. Red under: a `q_count_in` alternative added to
    `quantifier` (the collection set grows past the table)."""
    bare, collection = _bare_query_kinds()
    assert bare == set(n.DOMAIN_QUERY_KINDS)
    assert collection == set(n.COLLECTION_QUERY_KINDS)


# --- GRID R: the runtime value ------------------------------------------------


def _home(player: int) -> tuple[str, ...]:
    return board_entry("grid", (3, 3)).home(player)


def test_the_set_is_a_tuple_in_the_domains_order() -> None:
    """Red under: `evaluate._domain_query`'s set arm returning a list."""
    game, expr = _checked_board_expr("cells where true")
    value = evaluate(expr, _board_ctx(game, {}))
    assert isinstance(value, tuple)
    assert value == NINE_CELLS


def test_the_set_holds_the_satisfying_members_in_order() -> None:
    game, expr = _checked_board_expr("cells where square[cell] is not empty")
    assert evaluate(expr, _board_ctx(game, {"c3": "x", "a1": "o", "b2": "x"})) == ("a1", "b2", "c3")


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
def test_equality_with_a_region_verb_is_by_value(source: str, expected: bool) -> None:
    """Both truth values against the Region Verb. Red under: the set arm
    returning a list, which no Region Verb's tuple equals (the `same
    members` and `is not` cells). The control reads the Region Verb's own
    members. A bracket list against either is the same mismatch, issue
    #1023."""
    assert set(_home(0)) != set(_home(1))
    game, expr = _checked_board_expr(source)
    assert evaluate(expr, _board_ctx(game, {})) is expected


def test_the_inner_binder_shadows_the_outer() -> None:
    """The outer `cell` stands on the membership's left; the inner set binds
    its own. Every outer cell inside home(0) counts once."""
    game, expr = _checked_board_expr("number of cells where cell in (cells where cell in home(0))")
    assert evaluate(expr, _board_ctx(game, {})) == len(_home(0))


def test_an_integer_domains_set_ascends() -> None:
    game, expr = _checked_fc_expr("columns where cascade[column] is empty")
    assert evaluate(expr, _fc_ctx(game, {2: 1, 4: 3})) == (1, 3)


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


def test_the_ir_names_the_set_form() -> None:
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


def test_a_hidden_read_in_the_body_is_judged_as_the_other_query_kinds_are() -> None:
    """The set's body is judged at its enclosing clause, the When Clause:
    the same read under `any column where` gets the same verdict."""
    verdict = _outcome(_hidden_game(f"any column where {HIDDEN_READ}"))
    assert verdict is not None, "the control read must be refused at a deciding seat"
    assert _outcome(_hidden_game(f"c in (columns where {HIDDEN_READ})")) == verdict


_LIB = "probe_set_lib"


def test_a_library_naming_cells_is_refused_in_its_own_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A library names no board-minted domain; its Set Form is refused in
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
    `at in cells where P` is the parse refusal `x in players where P` gets,
    whose words name no fix for any register (issue #1024); `the cells
    where` is not the Set Form; a fused spelling is not a word. Red under,
    per cell: the Set Form placed in `?primary` (the two membership cells);
    `_THE_KW QNOUN _WHERE_KW expr` added to `quantifier` (the `the`-led
    cell); `_WHERE_KW` without its lookahead (the fused body)."""
    message = _reject(source)
    assert message.startswith("syntax error"), message
    assert TWIN_MESSAGE not in message, message


def test_the_double_where_sentence_is_ambiguous_on_the_player_register(explicit_parser: Lark) -> None:
    """Recorded, not fixed: a collection quantifier whose source is a bare
    Set Form and whose predicate is a bare name derives two ways. The
    player register's `players where` has it in the same place; no corpus
    sentence writes it (the corpus sweep's pin)."""
    tree = explicit_parser.parse(_snippet("    if any cell in players where players where (n is 0) { n := 1 }\n"))
    assert isinstance(tree, Tree)
    assert _count_ambig(tree) == 1


def test_the_double_where_sentence_is_ambiguous_on_the_position_register(explicit_parser: Lark) -> None:
    """The same class on the Set Form, recorded beside its player twin."""
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
    ],
)
def test_the_collection_twin_names_the_set_form(source: str) -> None:
    """On a board game the twin's words hold: cells live on the board, and
    the Set Form it names checks there."""
    assert TWIN_MESSAGE in _reject(source)
    check_dsl(_in_effect("let s = cells where square[cell] is empty"), "set.cardlang")


OPERATOR_QUESTION = "https://github.com/jbgh2/card-game-dsl/issues/972#issuecomment-6566773771"


def _twin_false(says: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=f"the twin says {says}; its shape is the operator's question on #972 ({OPERATOR_QUESTION})",
    )


@pytest.mark.parametrize(
    ("twin", "fix"),
    [
        pytest.param(
            card_game(body="    let s = cells in hand[0] where true\n"),
            card_game(body="    let s = cells where true\n"),
            id="boardless card game",
            marks=_twin_false("cells live on the board in a game with no board, and its fix is refused"),
        ),
        pytest.param(
            _integer_game("column") + "function f(p : Player) = cells in [1, 2] where cell > 1\n",
            _integer_game("column") + "function f(p : Player) = cells where cell > 1\n",
            id="integer domain column",
            marks=_twin_false("cells live on the board in a game with no board, and its fix is refused"),
        ),
        pytest.param(
            _integer_game(BOARD_DOMAIN) + "function f(p : Player) = cells in [1, 2] where cell > 1\n",
            _integer_game(BOARD_DOMAIN) + "function f(p : Player) = cells where cell > 1\n",
            id="integer domain named cell",
            marks=_twin_false("cells live on the board in a game with no board"),
        ),
    ],
)
def test_the_twins_words_hold_in_the_game_it_refuses(twin: str, fix: str) -> None:
    """Wherever the twin refuses, what it says is true of the game: it speaks
    of the board only where a `board:` mints `cell`, and the Set Form it
    names checks there. The three games here have no board."""
    message = _reject(twin)
    assert "on the board" not in message, message
    check_dsl(fix, "set.cardlang")


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
    right side is a bare Set Form keeps the main parser's syntax error (its
    words are issue #1024), and so does a collection twin over another noun
    (its words are issue #111). Red under: the twin led by `QNOUN` (every
    cell); led by any plural noun (`plural local`, `integer noun`,
    `lines`)."""
    message = _reject(source)
    assert message.startswith("syntax error"), message
    assert TWIN_MESSAGE not in message, message


def test_the_twins_word_is_the_boards_noun() -> None:
    """The twin's lead word is the plural of the noun a `board:` mints, the
    word its message names. Red under: the terminal spelled `cell`."""
    terminals = {t.name: t for t in _diagnostic_parser().terminals}
    pattern = re.compile(terminals["_SET_TWIN_CELLS_KW"].pattern.to_regexp())
    assert pattern.fullmatch(BOARD_DOMAIN + "s")
    assert not pattern.match(BOARD_DOMAIN + "sx")


def _as_boolean(kind: n.DomainQueryKind, query: str) -> str:
    match kind:
        case "any" | "all":
            return f"({query})"
        case "count":
            return f"(({query}) > 0)"
        case "set":
            return f"(({query}) is ({query}))"
        case unreachable:
            assert_never(unreachable)


@pytest.mark.parametrize("kind", n.DOMAIN_QUERY_KINDS)
def test_a_collection_nouns_hint_offers_only_a_form_the_query_kind_has(kind: n.DomainQueryKind) -> None:
    """A bare collection noun on a board is refused; the hint offers
    `<query kind's phrase> <noun> in <collection> where` only to a query kind with a collection
    form (the grammar's `q_any_in` / `q_all_in`), and the form it offers
    checks. Red under: the hint's `n.COLLECTION_QUERY_KINDS` gate removed (the
    `count` and `set` cells)."""
    phrase = n.DOMAIN_QUERY_KIND_PHRASE[kind]
    spelled = "line" if kind == "any" else "lines"
    message = _reject(_in_when(_as_boolean(kind, f"{phrase} {spelled} where true".strip())))
    assert "unknown position domain 'line'" in message, message
    if kind in n.COLLECTION_QUERY_KINDS:
        assert f"`{phrase} {spelled} in <collection> where ...`" in message, message
        check_dsl(_in_when(f"{phrase} {spelled} in lines(3) where true"), "set.cardlang")
    else:
        assert "in <collection>" not in message, message
