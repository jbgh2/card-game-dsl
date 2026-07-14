"""The `reveal` epistemic op: `reveal one card from <zone> [where <lambda>]`
publicly identifies one matching card without moving it — the card stays in
its zone, and the event reaches every player's log regardless of the zone's
declared visibility (unlike a movement, which projects through it). Semantics:
docs/superpowers/specs/2026-07-10-ws5-coup-interactive-windows-design.md,
"The `reveal` epistemic op".
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.ir import emit
from cardlang.openspiel.infostate import information_state
from cardlang.pipeline import check_dsl
from cardlang.runtime.execute import execute
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

QUEEN_SPADES = Card("Q", "spades")
KING_CLUBS = Card("K", "clubs")

SRC = """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase p {
    reveal one card from hand[0] where card.rank is Q
  }
  winner: highest score
}
"""

# The `where` clause is optional (`["where" lambda]` in the grammar) — every
# card in the zone is eligible when it is omitted.
SRC_NO_FILTER = """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase p {
    reveal one card from hand[0]
  }
  winner: highest score
}
"""

# Task 3's Coup usage filters on a state variable (`where card.rank is
# claim`), not a literal — the same `evaluate(filter, ctx)` closure path as a
# movement filter, but worth pinning directly since this is the branch that
# usage depends on.
SRC_STATE_FILTER = """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  // `claim` is a Rank, not a String holding a rank name: comparing `card.rank`
  // to a String is always false, and the checker rejects it (the same fix Coup
  // needed for its `block_claim`).
  state { score[player] : Integer = 0  claim : Rank = Q }
  phase p {
    reveal one card from hand[0] where card.rank is claim
  }
  winner: highest score
}
"""


def _reveal_stmt(game: n.Game) -> n.EpistemicOp:
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.EpistemicOp)
    return stmt


def test_reveal_parses_to_an_epistemic_op_with_a_filter() -> None:
    stmt = _reveal_stmt(check_dsl(SRC, "mini.cardlang"))
    assert stmt.op == "reveal"
    assert isinstance(stmt.filter, n.BinOp) and stmt.filter.op == "=="


def test_reveal_without_a_where_clause_parses_with_no_filter() -> None:
    stmt = _reveal_stmt(check_dsl(SRC_NO_FILTER, "mini.cardlang"))
    assert stmt.op == "reveal"
    assert stmt.filter is None


def _setup(
    hand0_cards: list[Card], src: str = SRC
) -> tuple[Ctx, dict[int, list[tuple[Any, ...]]], n.EpistemicOp]:
    game = check_dsl(src, "mini.cardlang")
    stmt = _reveal_stmt(game)
    players = (0, 1)
    rs = RuntimeState(Seating(2), ZoneStore(game.zones, players), random.Random(0))
    rs.zones.instance("hand", 0).add_all(hand0_cards)
    if src == SRC_STATE_FILTER:
        rs.push_frame()
        rs.declare("claim", False, "Q")
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in players}
    ctx = Ctx(
        rs=rs,
        chooser=lambda p, c, k: list(c[:k]),
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    return ctx, logs, stmt


def test_reveal_emits_to_every_player_and_leaves_the_card_in_place() -> None:
    ctx, logs, stmt = _setup([KING_CLUBS, QUEEN_SPADES])
    execute(stmt, ctx)

    expected = ("reveal", "hand[0]", "Q♠")
    for player in (0, 1):
        assert expected in logs[player], f"player {player} did not observe the reveal"
    # The revealed card is untouched — a reveal is not a movement.
    assert ctx.rs.zones.instance("hand", 0).cards == [KING_CLUBS, QUEEN_SPADES]
    # Player 1 owns no stake in hand[0] (Hand<player> normally shows non-owners
    # only a count through the movement projection); reveal bypasses that
    # projection entirely and gives every player the identity.
    assert logs[1] == [("reveal", "hand[0]", "Q♠")]


def test_reveal_reaches_the_derived_information_state() -> None:
    ctx, logs, stmt = _setup([QUEEN_SPADES])
    execute(stmt, ctx)

    expected_repr = repr(("reveal", "hand[0]", "Q♠"))
    for player in (0, 1):
        info = information_state(player, ctx.rs, logs[player])
        assert expected_repr in info


def test_reveal_fails_loudly_when_the_filter_matches_nothing() -> None:
    ctx, _logs, stmt = _setup([KING_CLUBS])  # no queen in the zone
    with pytest.raises(RuntimeError, match="reveal"):
        execute(stmt, ctx)


def test_reveal_fails_loudly_on_an_empty_zone() -> None:
    ctx, _logs, stmt = _setup([])
    with pytest.raises(RuntimeError, match="reveal"):
        execute(stmt, ctx)


def test_reveal_without_a_filter_takes_the_first_card_and_leaves_the_zone_alone() -> None:
    ctx, logs, stmt = _setup([KING_CLUBS, QUEEN_SPADES], src=SRC_NO_FILTER)
    execute(stmt, ctx)

    expected = ("reveal", "hand[0]", "K♣")  # every card eligible: the first in the zone
    for player in (0, 1):
        assert expected in logs[player]
    assert ctx.rs.zones.instance("hand", 0).cards == [KING_CLUBS, QUEEN_SPADES]


def test_reveal_without_a_filter_fails_loudly_on_an_empty_zone() -> None:
    ctx, _logs, stmt = _setup([], src=SRC_NO_FILTER)
    with pytest.raises(RuntimeError, match="reveal"):
        execute(stmt, ctx)


def test_reveal_filter_can_reference_state() -> None:
    ctx, logs, stmt = _setup([KING_CLUBS, QUEEN_SPADES], src=SRC_STATE_FILTER)
    execute(stmt, ctx)

    expected = ("reveal", "hand[0]", "Q♠")
    for player in (0, 1):
        assert expected in logs[player]


def test_reveal_ir_emits_filter_key_only_when_present() -> None:
    filtered_ir: Any = emit(check_dsl(SRC, "mini.cardlang"))
    plain_ir: Any = emit(check_dsl(SRC_NO_FILTER, "mini.cardlang"))
    filtered_op = filtered_ir["phases"][0]["items"][0]
    plain_op = plain_ir["phases"][0]["items"][0]
    assert filtered_op["kind"] == "epistemic_op" and filtered_op["op"] == "reveal"
    assert plain_op["kind"] == "epistemic_op" and plain_op["op"] == "reveal"

    assert "filter" in filtered_op
    assert filtered_op["filter"]["kind"] == "binop"
    # The whole point (mirrors the movement `where` filter's IR convention):
    # an unfiltered reveal carries NO "filter" key at all.
    assert "filter" not in plain_op
