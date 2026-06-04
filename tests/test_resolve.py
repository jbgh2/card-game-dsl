"""Resolver tests: Hearts hangs together, and the structural-reference checks
catch undefined rules, move types, mechanics, and bad transition targets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.resolve import resolve

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def _resolve(dsl: str) -> None:
    resolve(parse_text(dsl, "test.cardlang"))


def test_hearts_resolves_clean() -> None:
    resolve(parse_text(HEARTS.read_text(), str(HEARTS)))


def _game(body: str, rules: str = "") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        f"{body}\n"
        "}\n"
        f"{rules}\n"
    )


def test_undefined_rule_in_active_rules() -> None:
    dsl = _game("  phase p { active_rules: [Nonexistent] }")
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "undefined rule 'Nonexistent'" in e.value.diagnostic.message


def test_unknown_move_type_in_legal_moves() -> None:
    dsl = _game("  phase p { legal_moves: [bogus_move] }")
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "unknown move type 'bogus_move'" in e.value.diagnostic.message


def test_transition_target_must_be_sibling() -> None:
    dsl = _game(
        "  phase play {\n"
        "    phase a { transition_to: nowhere when play_to_trick }\n"
        "    phase b { }\n"
        "  }"
    )
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "transition_to target 'nowhere'" in e.value.diagnostic.message


def test_transition_to_real_sibling_resolves() -> None:
    dsl = _game(
        "  phase play {\n"
        "    phase a { transition_to: b when play_to_trick }\n"
        "    phase b { }\n"
        "  }"
    )
    _resolve(dsl)  # no error


def test_unknown_mechanic() -> None:
    dsl = _game("  phase p { instantiate Bogus ( ) }")
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "unknown mechanic 'Bogus'" in e.value.diagnostic.message


def test_rule_constrains_unknown_move_type() -> None:
    dsl = _game("  phase p { }", rules="rule R { constrains: bogus }")
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "unknown move type 'bogus'" in e.value.diagnostic.message
