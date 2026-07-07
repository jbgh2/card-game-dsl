"""`max_length:` — the per-game declared bound (docs/decisions.md, "Game
length as a declared contract"). Missing/non-positive declarations are
covered in test_resolve.py alongside the resolver's other structural
checks; this file covers the grammar round-trip, the runtime's two
non-termination guards (statement-level `repeat until`, phase-level
`repeats until`), and the OpenSpiel adapter's `max_game_length` wiring.
"""

from __future__ import annotations

import random

import pytest

from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


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
    with pytest.raises(RuntimeError) as e:
        play_game(game, random.Random(0))
    assert "max_length (5)" in str(e.value)


def test_phase_level_repeats_until_respects_declared_max_length() -> None:
    dsl = _non_terminating_game("  phase p repeats until false {\n  }\n")
    game = check_dsl(dsl, "test.cardlang")
    with pytest.raises(RuntimeError) as e:
        play_game(game, random.Random(0))
    assert "max_length (5)" in str(e.value)


def test_openspiel_adapter_reports_the_declared_max_length() -> None:
    pytest.importorskip("pyspiel")
    import pyspiel

    import cardlang.openspiel.game  # noqa: F401  (registers on import)
    from cardlang.pipeline import check_source
    from cardlang.openspiel.game import GAMES, _GAMES_DIR

    for short_name, filename in GAMES.items():
        game_ast = check_source(_GAMES_DIR / filename)
        game = pyspiel.load_game(short_name)
        assert game.max_game_length() == game_ast.max_length, short_name
