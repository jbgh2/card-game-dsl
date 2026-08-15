from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def test_accepts_exhaustive_typed_outcome() -> None:
    src = """
define settle -> { won(Integer) | lost } { produce won(7) }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""
    check_dsl(src, "g.cardlang")  # no raise


def test_rejects_non_exhaustive_match() -> None:
    src = """
define settle -> { won(Integer) | lost } { produce lost }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "exhaustive" in str(ei.value) or "lost" in str(ei.value)


def test_rejects_unknown_variant_in_match() -> None:
    src = """
define settle -> { won(Integer) | lost } { produce lost }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
        drew        { points[p] += 1 }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "drew" in str(ei.value) or "unknown variant" in str(ei.value)


def test_rejects_wrong_payload_type_in_produce() -> None:
    # `produce won(hearts)` — a Suit where the case declares Integer.
    src = """
define settle -> { won(Integer) | lost } { produce won(hearts) }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "won" in str(ei.value) or "Integer" in str(ei.value)


def test_rejects_wrong_binder_type_use() -> None:
    # `amount` binds an Integer; passing it to `player_holding` (which expects a
    # Card) errors via the existing native-arg check — proving the binder is
    # typed (not TAny) inside the arm body.
    src = """
define settle -> { won(Integer) | lost } { produce won(7) }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0  dealer : Player = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { dealer := player_holding(amount) }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "player_holding" in str(ei.value)
