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
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        f"{body}\n"
        "  loser: 0\n"
        "}\n"
        f"{rules}\n"
    )


def test_missing_max_length_is_a_diagnostic() -> None:
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "}\n"
    )
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "must declare `max_length" in e.value.diagnostic.message


def test_missing_winner_and_loser_is_a_diagnostic() -> None:
    # Without this guard a game with neither would compile clean and die on a
    # driver assert before its first decision (write-time triage: the assert
    # is the guard's recorded Shadow Guard).
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "}\n"
    )
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "must declare `winner:" in e.value.diagnostic.message


def test_non_positive_max_length_is_a_diagnostic() -> None:
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 0\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "}\n"
    )
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "must be a positive integer" in e.value.diagnostic.message


# A phase's rules and modes stand beside a trick round that asks them: one no
# trick round asks is refused (tests/test_rules_reach_the_round.py).
_TRICK = (
    "    round play_to_trick from 0 over all players source hand into pile "
    "winner highest_of_led_suit\n"
)


def _tricked(dsl: str) -> str:
    return dsl.replace(
        "  zones { hand[player] : Hand<player> }\n",
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player>  pile : TrickPile }\n",
        1,
    )


def test_undefined_rule_in_active_rules() -> None:
    dsl = _tricked(_game("  phase p {\n    active_rules: [Nonexistent]\n" + _TRICK + "  }"))
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "undefined rule 'Nonexistent'" in e.value.diagnostic.message


def test_unknown_move_type_in_legal_moves() -> None:
    dsl = _game("  phase p { legal_moves: [bogus_move] }")
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "unknown move type 'bogus_move'" in e.value.diagnostic.message


def test_transition_target_must_be_sibling() -> None:
    dsl = _tricked(_game(
        "  phase play {\n"
        "    mode a { transition_to: nowhere when play_to_trick }\n" + _TRICK +
        "  }"
    ))
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "transition_to target 'nowhere'" in e.value.diagnostic.message


def test_transition_to_real_sibling_resolves() -> None:
    dsl = _tricked(_game(
        "  phase play {\n"
        "    mode a { transition_to: b when play_to_trick }\n"
        "    mode b { }\n" + _TRICK +
        "  }"
    ))
    _resolve(dsl)  # no error


def test_rule_constrains_unknown_move_type() -> None:
    dsl = _game("  phase p { }", rules="rule R { constrains: bogus }")
    with pytest.raises(DiagnosticError) as e:
        _resolve(dsl)
    assert "unknown move type 'bogus'" in e.value.diagnostic.message
