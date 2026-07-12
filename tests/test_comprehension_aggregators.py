"""Runtime semantics of every comprehension aggregator arm (closed-domain
completeness, decisions.md): the domain is the grammar's `AGG` terminal —
`sum | count | max | min` — and every arm is exercised here, including the
empty-collection behavior of the order aggregators (a loud runtime error, not
a bare `ValueError` from `max()`/`min()`).

`count` accepts only the literal `true` as its body (resolve rejects anything
else — see `tests/test_construct_combination_validity.py`), so its runtime arm
is exercised through that one legal shape.
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

HEARTS_A = Card("A", "hearts")
HEARTS_2 = Card("2", "hearts")
CLUBS_K = Card("K", "clubs")

# Every aggregator the grammar admits; pinned so a new AGG token cannot land
# without extending this module's coverage.
GRAMMAR_AGGREGATORS = frozenset({"sum", "count", "max", "min"})


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


def test_grammar_agg_set_is_pinned() -> None:
    """The grammar's AGG terminal and this module's covered set must agree —
    a new aggregator arrives with its arm tests or not at all."""
    from importlib import resources

    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    (line,) = [ln for ln in grammar.splitlines() if ln.startswith("AGG:")]
    in_grammar = {tok.strip().strip('"') for tok in line.split(":", 1)[1].split("|")}
    assert in_grammar == GRAMMAR_AGGREGATORS


def test_sum_aggregates_the_body_values() -> None:
    game, e = _expr("sum over pile as c: if c.suit == hearts then 1 else 0")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


def test_sum_over_an_empty_collection_is_zero() -> None:
    game, e = _expr("sum over pile as c: if c.suit == hearts then 1 else 0")
    assert evaluate(e, _ctx(game, [])) == 0


def test_count_true_returns_the_element_count() -> None:
    game, e = _expr("count over pile as c: true")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 3
    assert evaluate(e, _ctx(game, [])) == 0


def test_max_returns_the_largest_body_value() -> None:
    game, e = _expr("max over pile as c: if c.suit == hearts then 9 else 1")
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 9


def test_min_returns_the_smallest_body_value() -> None:
    game, e = _expr("min over pile as c: if c.suit == hearts then 9 else 1")
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 1


@pytest.mark.parametrize("agg", ["max", "min"])
def test_order_aggregators_fail_loud_on_an_empty_collection(agg: str) -> None:
    # Not a bare ValueError out of the builtin: the message names the construct
    # and the guard, in the runtime's failure currency.
    game, e = _expr(f"{agg} over pile as c: if c.suit == hearts then 9 else 1")
    with pytest.raises(RuntimeError, match="empty collection has no value"):
        evaluate(e, _ctx(game, []))
