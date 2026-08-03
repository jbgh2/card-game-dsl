"""Reserved-word pins for the `is` / `not` / `number` grammar narrowing
(docs/decisions.md, "The expression register" — "The word/symbol line").

These three words are excluded from the NAME terminal (cardlang/grammar/
cardlang.lark) because each also opens a fixed grammar production
(`is`/`is not` equality, `not` negation, `number of … where` the card-query
count form) at a position where a bare NAME is otherwise reachable. Without
the exclusion, the corpus-wide Earley ambiguity budget
(tests/test_grammar_ambiguity.py) regresses: the parser can no longer tell
whether `number of cards in pile` is the count query or the card literal
`number of cards` followed by a dangling `in pile`.

`is` and `not` additionally get anchored terminals (`_IS_KW`, `_NOT_KW`)
rather than staying bare string literals, because an unanchored literal can
match as a *prefix* of a longer identifier even once the identifier's exact
text is excluded from NAME (`is_re` lexing as `is` + `_re`). This module pins
both halves of that fix: the reserved bare words are rejected, and
identifiers merely prefixed by a reserved word still parse as themselves.

Anchoring is no longer these three words' own property — every keyword in the
grammar carries it, stated as one rule over the whole terminal table in
tests/test_keyword_anchoring.py. Reservation (exclusion from NAME) stays the
smaller, separate set this module is about: a word that may not name a value.
"""

from __future__ import annotations

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text


def _game(body: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state {\n"
        f"    {body}\n"
        "  }\n"
        "}\n"
    )


def _rejects_as_syntax_error(src: str) -> None:
    with pytest.raises(DiagnosticError, match="syntax error"):
        parse_text(src, "t.cardlang")


# --- bare reserved words are not identifiers -------------------------------


@pytest.mark.parametrize("word", ["is", "not", "number"])
def test_reserved_word_rejected_as_state_var_name(word: str) -> None:
    _rejects_as_syntax_error(_game(f"{word} : Integer = 0"))


def test_reserved_word_rejected_as_let_binder_name() -> None:
    # The exact example named in the reservation: `let number = 3`.
    _rejects_as_syntax_error(_game("x : Integer = 0\n  }\n  phase p {\n    let number = 3"))


@pytest.mark.parametrize("word", ["is", "not", "number"])
def test_reserved_word_rejected_as_zone_name(word: str) -> None:
    src = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        f"  zones {{ {word} : Deck }}\n"
        "}\n"
    )
    _rejects_as_syntax_error(src)


@pytest.mark.parametrize("word", ["is", "not", "number"])
def test_reserved_word_rejected_as_function_name(word: str) -> None:
    src = _game("x : Integer = 0") + f"function {word}(a : Integer) = a\n"
    _rejects_as_syntax_error(src)


# --- prefixed identifiers are unaffected ------------------------------------


def test_is_prefixed_function_name_still_parses() -> None:
    # `is_re` is not the bare word `is`: the anchored _IS_KW terminal requires
    # a non-word character right after "is", so it never matches here and the
    # dynamic lexer has only one reading — the whole identifier as NAME.
    src = _game("x : Integer = 0") + "function is_re(a : Integer) = a\n"
    game = parse_text(src, "t.cardlang")
    assert any(d.name == "is_re" for d in game.functions)


def test_not_prefixed_function_name_still_parses() -> None:
    src = _game("x : Integer = 0") + "function not_yet(a : Integer) = a\n"
    game = parse_text(src, "t.cardlang")
    assert any(d.name == "not_yet" for d in game.functions)


def test_number_prefixed_state_var_name_still_parses() -> None:
    game = parse_text(_game("number_of_tricks : Integer = 0"), "t.cardlang")
    assert game.state is not None
    assert any(decl.name == "number_of_tricks" for decl in game.state.decls)


def test_is_prefixed_call_still_parses() -> None:
    # The exact shape named in the reservation: an `is_re(...)` call.
    src = _game("x : Integer = 0\n  }\n  phase p {\n    let probe = is_re(x)")
    src += "function is_re(a : Integer) = a\n"
    game = parse_text(src, "t.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.LetStmt)
    assert isinstance(stmt.value, n.Call)
    assert stmt.value.func == "is_re"


# --- the "is not_ready" identifier-split case -------------------------------
#
# `not` also sits as a bare string literal directly after `is` in the
# `compare_is_not` production (`sum "is" "not" sum`). That inline literal has
# exactly the same prefix-split hazard as the standalone `not_expr` site: for
# `sum is not_ready`, an unanchored "not" can match as a 3-character prefix of
# the identifier `not_ready`, leaving `_ready` as a second, competing parse of
# the trailing operand. No corpus game happens to use an operand starting
# with `not`, so tests/test_grammar_ambiguity.py's corpus sweep does not catch
# this; it was found by hand while verifying the `is`/`not`/`number` fix and
# closed by giving `compare_is_not` the same `_NOT_KW` anchored terminal the
# standalone `not_expr` production already uses.


def test_is_not_prefixed_identifier_parses_as_equality_not_negation() -> None:
    # `x is not_ready` must read as `x is (not_ready)` — plain equality
    # against the value `not_ready` — never as `x is not (ready)`. Since
    # `not_ready` is not one of the closed `none`/`empty` keywords, `compare_is`
    # lowers it to the ordinary equality BinOp (internal op token `==`).
    src = _game("x : Integer = 0\n  }\n  phase p {\n    let probe = x is not_ready")
    game = parse_text(src, "t.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.LetStmt)
    value = stmt.value
    assert isinstance(value, n.BinOp)
    assert value.op == "=="
    assert isinstance(value.right, n.NameRef) and value.right.name == "not_ready"


def test_is_not_none_and_is_not_empty_still_parse_as_the_closed_forms() -> None:
    # The fix must not disturb the two closed right-hand keywords that ride
    # the same "is not" production.
    src = _game(
        "x : Integer? = none\n"
        "  }\n"
        "  phase p {\n"
        "    let a = x is not none\n"
        "    let b = hand[0] is not empty"
    )
    game = parse_text(src, "t.cardlang")
    a, b = game.phases[0].items[-2], game.phases[0].items[-1]
    assert isinstance(a, n.LetStmt)
    assert isinstance(a.value, n.IsCheck) and a.value.kind == "not_none"
    assert isinstance(b, n.LetStmt)
    assert isinstance(b.value, n.IsCheck) and b.value.kind == "not_empty"
