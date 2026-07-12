"""Runtime semantics of every aggregation form (closed-domain completeness,
decisions.md): the domain is the English register's aggregation surface —
`sum of … over cards in …`, `highest/lowest … over cards in … or <default>`,
and the counting card query `number of cards in … [where …]` — each arm
exercised here, including the empty and filtered-to-empty cases (the order
aggregators' grammar makes the `or <default>` clause mandatory, so an empty
zone yields the declared value, never a crash).

The retired spellings (`sum/count/max/min over … as x: …`, `==`/`!=`) must
NOT parse — pinned at the bottom so retirement cannot silently regress.
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

HEARTS_A = Card("A", "hearts")
HEARTS_2 = Card("2", "hearts")
CLUBS_K = Card("K", "clubs")


def _expr(expr_src: str) -> tuple[n.Game, n.Expr]:
    src = f"""
game Mini {{
  players: 1
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    let probe = {expr_src}
  }}
  winner: highest score
}}
"""
    game = check_dsl(src, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.LetStmt)
    return game, stmt.value


def _unused_chooser(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("aggregator evaluation makes no decision")


def _ctx(game: n.Game, pile_cards: list[Card]) -> Ctx:
    rs = RuntimeState(Seating(1), ZoneStore(game.zones, (0,)), random.Random(0))
    rs.zones.single("pile").add_all(pile_cards)
    return Ctx(rs=rs, chooser=_unused_chooser).acting_as(0)


# --- sum ---


def test_sum_aggregates_the_body_over_every_card() -> None:
    game, e = _expr("sum of (if card.suit is hearts then 1 else 0) over cards in pile")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


def test_sum_with_a_where_filter_aggregates_the_matching_cards_only() -> None:
    game, e = _expr("sum of 1 over cards in pile where card.suit is hearts")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


def test_sum_over_an_empty_collection_is_zero() -> None:
    game, e = _expr("sum of 1 over cards in pile")
    assert evaluate(e, _ctx(game, [])) == 0


# --- counting (the card query) ---


def test_bare_count_is_the_zone_size() -> None:
    game, e = _expr("number of cards in pile")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 3
    assert evaluate(e, _ctx(game, [])) == 0


def test_filtered_count_counts_the_matches() -> None:
    game, e = _expr("number of cards in pile where card.suit is hearts")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


# --- highest / lowest ---


def test_highest_returns_the_largest_body_value() -> None:
    game, e = _expr(
        "highest (if card.suit is hearts then 9 else 1) over cards in pile or -1"
    )
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 9


def test_lowest_returns_the_smallest_body_value() -> None:
    game, e = _expr(
        "lowest (if card.suit is hearts then 9 else 1) over cards in pile or -1"
    )
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 1


def test_order_aggregators_respect_the_where_filter() -> None:
    game, e = _expr("highest 5 over cards in pile where card.suit is hearts or -1")
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 5


@pytest.mark.parametrize("agg", ["highest", "lowest"])
def test_order_aggregators_yield_the_default_on_an_empty_zone(agg: str) -> None:
    game, e = _expr(f"{agg} 5 over cards in pile or -1")
    assert evaluate(e, _ctx(game, [])) == -1


@pytest.mark.parametrize("agg", ["highest", "lowest"])
def test_order_aggregators_yield_the_default_when_the_filter_empties(agg: str) -> None:
    game, e = _expr(f"{agg} 5 over cards in pile where card.suit is spades or 42")
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 42


# --- the retired spellings must not come back ---


@pytest.mark.parametrize(
    "src",
    [
        "sum over pile as c: 1",
        "count over pile as c: true",
        "max over pile as c: 1",
        "min over pile as c: 1",
        "any player p: score[p] >= 1",
    ],
)
def test_retired_aggregator_and_binder_spellings_do_not_parse(src: str) -> None:
    with pytest.raises(DiagnosticError, match="syntax error"):
        _expr(src)


def test_retired_equality_symbols_are_rejected_with_the_word_form() -> None:
    with pytest.raises(DiagnosticError, match="write `is`"):
        _expr("1 == 1")
    with pytest.raises(DiagnosticError, match="write `is not`"):
        _expr("1 != 1")
