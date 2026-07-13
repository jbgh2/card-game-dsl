"""Domain completion: the audited gaps in admitted constructs, each cell total
(docs/design-notes/lexical-cleanup.md §2, "What landed, and where it lives").

- negative Integer literals (`-200`, retiring the `0 - 200` workaround);
- name-form rank literals resolving bare (`card.rank == K`, `Duke`), with the
  enum-comparison wall steering the numeric ranks ("10", "21" — bare numbers
  are Integers) to the validated string spelling and rejecting every
  silently-false shape;
- `any`/`all`/`for each` over the suit and rank domains;
- membership `in` over zones and `[…]` list literals.
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating, deck_ranks


def _game(body: str, deck: str = "standard52", ranking: str = "ranking: A K Q J 10 9 8 7 6 5 4 3 2") -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: {deck}
  {ranking}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    {body}
  }}
  winner: highest score
}}
"""


def _checked_expr(expr_src: str, **kw: str) -> tuple[n.Game, n.Expr]:
    game = check_dsl(_game(f"let probe = {expr_src}", **kw), "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.LetStmt)
    return game, stmt.value


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


def _unused_chooser(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("expression evaluation makes no decision")


def _ctx(game: n.Game, pile_cards: list[Card]) -> Ctx:
    rs = RuntimeState(Seating(2), ZoneStore(game.zones, (0, 1)), random.Random(0))
    rs.zones.single("pile").add_all(pile_cards)
    rs.suits = ("clubs", "diamonds", "hearts", "spades")
    rs.ranks = ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")
    return Ctx(rs=rs, chooser=_unused_chooser).acting_as(0)


# --- negative Integer literals ---


def test_negative_int_literal_parses_and_evaluates() -> None:
    game, e = _checked_expr("-200")
    assert isinstance(e, n.IntLit) and e.value == -200
    assert evaluate(e, _ctx(game, [])) == -200


def test_binary_minus_is_still_subtraction() -> None:
    game, e = _checked_expr("5 - 2")
    assert isinstance(e, n.BinOp) and e.op == "-"
    assert evaluate(e, _ctx(game, [])) == 3


# --- name-form rank literals ---


def test_bare_rank_resolves_as_a_rank_value() -> None:
    game, e = _checked_expr("if 1 is 1 then K else Q")
    assert evaluate(e, _ctx(game, [])) == "K"


def test_ranks_come_from_the_deck_not_the_ranking_declaration() -> None:
    # Coup declares no `ranking:`; its characters are the coup15 deck's ranks.
    assert "Duke" in deck_ranks("coup15")
    src = _game("let probe = if 1 is 1 then Duke else Contessa", deck="coup15", ranking="")
    check_dsl(src, "mini.cardlang")


# --- the enum-comparison wall (every silently-false shape is loud) ---


def test_rejects_rank_compared_with_integer() -> None:
    _rejects(
        _game("let probe = number of cards in pile where card.rank is 10"),
        "numeric ranks are written as strings",
    )


def test_rejects_a_name_form_rank_written_as_a_string() -> None:
    _rejects(
        _game('let probe = number of cards in pile where card.rank is "K"'),
        "write the Rank value bare",
    )


def test_rejects_a_string_that_is_not_a_rank_of_the_deck() -> None:
    _rejects(
        _game('let probe = number of cards in pile where card.rank is "Kx"'),
        "not a Rank value of this deck",
    )


def test_accepts_a_numeric_rank_as_a_string() -> None:
    _checked_expr('number of cards in pile where card.rank is "10"')


def test_rejects_cross_enum_comparison() -> None:
    _rejects(
        _game("let probe = number of cards in pile where card.rank is hearts"),
        "comparing Rank with Suit",
    )


def test_rejects_an_unknown_card_field() -> None:
    _rejects(
        _game("let probe = number of cards in pile where card.value is 3"),
        "Card has no field 'value'",
    )


# --- suit and rank iteration domains ---


def test_any_suit_quantifier_evaluates_over_the_deck_suits() -> None:
    game, e = _checked_expr(
        "any suit where (number of cards in pile where card.suit is suit) >= 2"
    )
    two_hearts = [Card("A", "hearts"), Card("2", "hearts"), Card("K", "clubs")]
    assert evaluate(e, _ctx(game, two_hearts)) is True
    assert evaluate(e, _ctx(game, two_hearts[1:])) is False


def test_all_rank_quantifier_evaluates_over_the_ranking() -> None:
    game, e = _checked_expr(
        "all ranks where (number of cards in pile where card.rank is rank) <= 1"
    )
    assert evaluate(e, _ctx(game, [Card("A", "hearts"), Card("A", "clubs")])) is False
    assert evaluate(e, _ctx(game, [Card("A", "hearts"), Card("K", "clubs")])) is True


def test_for_each_suit_runs_the_body_once_per_deck_suit() -> None:
    from cardlang.runtime.execute import execute

    game = check_dsl(_game("for each suit s: score[0] += 1"), "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.ForEach) and stmt.role == "suit"
    ctx = _ctx(game, [])
    ctx.rs.push_frame()
    ctx.rs.declare("score", indexed=True, value={0: 0, 1: 0})
    execute(stmt, ctx)
    assert ctx.rs.get("score")[0] == 4  # one pass per suit of standard52


def test_the_explicit_binder_quantifier_spelling_does_not_parse() -> None:
    # Quantifier roles are fixed by their grammar productions now; the retired
    # explicit-binder spelling is grammatically inexpressible.
    _rejects(_game("let probe = any color x: 1 is 1"), "syntax error")


def test_rejects_an_unknown_for_each_role() -> None:
    _rejects(_game("for each color x: score[0] += 1"), "unknown `for each` role")


def test_rejects_each_simultaneous_over_a_value_domain() -> None:
    _rejects(
        _game("each suit simultaneously: score[0] += 1"),
        "simultaneous moves are per player",
    )


# --- membership ---


def test_card_membership_in_a_zone() -> None:
    game, e = _checked_expr("Q of spades in pile")
    assert evaluate(e, _ctx(game, [Card("Q", "spades")])) is True
    assert evaluate(e, _ctx(game, [Card("Q", "hearts")])) is False


def test_value_membership_in_a_list_literal() -> None:
    game, e = _checked_expr(
        "number of cards in pile where card.suit in [hearts, spades]"
    )
    cards = [Card("A", "hearts"), Card("K", "clubs"), Card("2", "spades")]
    assert evaluate(e, _ctx(game, cards)) == 2


def test_mixed_rank_list_membership_evaluates() -> None:
    # Doppelkopf's fat-trick check: name-form ranks bare, numeric as string.
    game, e = _checked_expr('number of cards in pile where card.rank in [A, "10"]')
    cards = [Card("A", "hearts"), Card("10", "clubs"), Card("K", "spades")]
    assert evaluate(e, _ctx(game, cards)) == 2


def test_rejects_membership_in_a_non_collection() -> None:
    _rejects(
        _game("let probe = 3 in score[0]"),
        "must be a collection",
    )


def test_rejects_a_bogus_rank_string_inside_a_membership_list() -> None:
    _rejects(
        _game('let probe = number of cards in pile where card.rank in [A, "Kx"]'),
        "not a Rank value of this deck",
    )
