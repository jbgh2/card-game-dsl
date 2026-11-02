"""`max_length:` — the per-game declared bound (docs/decisions.md, "Game
length as a declared contract"). Missing/non-positive declarations are
covered in test_resolve.py alongside the resolver's other structural
checks; this file covers the grammar round-trip, the two `repeat until`
guards that refuse a loop making no decisions, the pick count that ends a
game at its bound (the unit corpus values are sized against), and the
OpenSpiel adapter's `max_game_length` wiring. The Length Stop's whole domain
is tests/test_length_stop.py.
"""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import pytest

from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import EndedBy, play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.errors import OwnerGuardError

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def test_declares_and_parses() -> None:
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 500\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "}\n"
    )
    game = parse_text(dsl, "test.cardlang")
    assert game.max_length == 500


def _non_terminating_game(phase: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 5\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { n[player] : Integer = 0 }\n"
        f"{phase}\n"
        "  winner: highest n\n"
        "}\n"
    )


def test_statement_level_repeat_until_respects_declared_max_length() -> None:
    dsl = _non_terminating_game(
        "  phase p {\n"
        "    repeat until false {\n"
        "    }\n"
        "  }\n"
    )
    game = check_dsl(dsl, "test.cardlang")
    with pytest.raises(OwnerGuardError) as e:
        play_game(game, random.Random(0))
    assert "max_length (5)" in str(e.value)


def test_phase_level_repeat_until_respects_declared_max_length() -> None:
    dsl = _non_terminating_game("  phase p repeat until false {\n  }\n")
    game = check_dsl(dsl, "test.cardlang")
    with pytest.raises(OwnerGuardError) as e:
        play_game(game, random.Random(0))
    assert "max_length (5)" in str(e.value)


def test_the_pick_count_ends_a_game_inside_its_first_loop_iteration() -> None:
    """A game can reach its bound before any loop completes an iteration:
    real Hearts, its max_length overridden down to a number its own deal
    passes in a handful of picks, ends at exactly that many picks, by length,
    with neither loop guard counting a boundary."""
    game = check_source(HEARTS)
    tiny = dataclasses.replace(game, max_length=5)
    world: list[RuntimeState] = []
    result = play_game(tiny, random.Random(0), on_first_decision=world.append)
    assert result.ended_by is EndedBy.LENGTH
    assert world[0].decisions_made == 5


def test_openspiel_adapter_reports_the_declared_max_length() -> None:
    pytest.importorskip("pyspiel")
    import pyspiel

    import cardlang.openspiel.game  # noqa: F401  (registers on import)
    from cardlang.openspiel.registry import GAMES, _GAMES_DIR
    from cardlang.pipeline import check_source

    for short_name, filename in GAMES.items():
        game_ast = check_source(_GAMES_DIR / filename)
        game = pyspiel.load_game(short_name)
        assert game.max_game_length() == game_ast.max_length, short_name
