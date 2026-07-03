"""The movement `where` filter: `move/deal/transfer <sel> cards from <zone>
where <lambda> to <zone>` narrows the source pool to the matching cards (in
source order) before the selection draws from it.

This is the frontend half (grammar/AST/parse/IR/typecheck); the execution
semantics are in test_movement_filter_execute.py. The IR key is emitted ONLY
when a filter is present — the load-bearing property that keeps every
existing (unfiltered) movement's golden byte-identical (plan §2e/§4).
"""

from __future__ import annotations

from typing import Any

from cardlang.ast import nodes as n
from cardlang.ir import emit
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

FILTERED_SRC = """
game Mini {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase p {
    move chosen 2 cards from hand[0] where c => c.suit == hearts to pile
  }
  winner: highest score
}
"""

PLAIN_SRC = """
game Mini {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase p {
    move chosen 2 cards from hand[0] to pile
  }
  winner: highest score
}
"""


def _movement(game: n.Game) -> n.Movement:
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.Movement)
    return stmt


def test_where_filter_parses_as_a_lambda() -> None:
    mv = _movement(parse_text(FILTERED_SRC, "mini.cardlang"))
    assert isinstance(mv.filter, n.Lambda)
    assert mv.filter.param == "c"


def test_plain_movement_has_no_filter() -> None:
    mv = _movement(parse_text(PLAIN_SRC, "mini.cardlang"))
    assert mv.filter is None


def test_typecheck_accepts_the_where_predicate() -> None:
    game = check_dsl(FILTERED_SRC, "mini.cardlang")
    mv = _movement(game)
    assert isinstance(mv.filter, n.Lambda)
    # Resolve classified the lambda's own binder as a local, and the deck's
    # `hearts` suit as an enum value — both readable off the checked AST.
    body = mv.filter.body
    assert isinstance(body, n.BinOp) and body.op == "=="


def test_filter_ir_key_emitted_only_when_present() -> None:
    filtered_ir: Any = emit(check_dsl(FILTERED_SRC, "mini.cardlang"))
    plain_ir: Any = emit(check_dsl(PLAIN_SRC, "mini.cardlang"))
    filtered_mv = filtered_ir["phases"][0]["items"][0]
    plain_mv = plain_ir["phases"][0]["items"][0]
    assert filtered_mv["kind"] == "movement" and plain_mv["kind"] == "movement"

    assert "filter" in filtered_mv
    assert filtered_mv["filter"] == {
        "kind": "lambda",
        "param": "c",
        "body": {
            "kind": "binop",
            "op": "==",
            "left": {"kind": "member", "obj": {"kind": "name", "name": "c", "ref": "local"}, "field": "suit"},
            "right": {"kind": "name", "name": "hearts", "ref": "enum_value"},
        },
    }
    # The whole point: an unfiltered movement carries NO "filter" key at all
    # (not `"filter": null`) — this is what keeps every pre-existing IR golden
    # byte-identical after this change.
    assert "filter" not in plain_mv
