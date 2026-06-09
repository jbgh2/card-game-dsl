"""Negative tests: the type checker must reject genuinely ill-typed games.

Each is driven RED-first (the pre-check skeleton accepts everything) and a
checking rule turns it GREEN.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _game(body_state: str, body_play: str) -> str:
    return f"""
game G {{
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ {body_state} }}
  phase play {{ {body_play} }}
  winner: highest score
}}
"""


def test_rejects_suit_assigned_to_integer_var() -> None:
    # `score[p] := hearts` assigns a Suit to an Integer state var.
    src = _game("score[player] : Integer = 0", "for each player p: score[p] := hearts")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "score" in str(ei.value) or "Suit" in str(ei.value) or "Integer" in str(ei.value)
