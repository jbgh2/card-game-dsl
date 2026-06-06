"""Deep name resolution: every bare name is classified, and names/calls/
card-literals that resolve to nothing are caught.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.resolve import _walk, resolve

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def test_hearts_name_classifications() -> None:
    game = resolve(parse_text(HEARTS.read_text(), str(HEARTS)))
    kinds: dict[str, str] = {}
    for nd in _walk(game):
        if isinstance(nd, n.NameRef) and nd.ref_kind is not None:
            kinds.setdefault(nd.name, nd.ref_kind)
    assert kinds["leader"] == "state_var"
    assert kinds["cumulative_score"] == "state_var"
    assert kinds["deck"] == "zone"
    assert kinds["captured"] == "zone"
    assert kinds["hearts"] == "enum_value"
    assert kinds["hold"] == "enum_value"  # the no-pass Direction value
    assert kinds["none"] == "null"  # the universal absence literal
    assert kinds["state"] == "pronoun"
    assert kinds["action"] == "pronoun"
    assert kinds["outcome"] == "pronoun"
    assert kinds["highest_of_led_suit"] == "function"
    assert kinds["c"] == "local"
    assert kinds["card"] == "local"


def _game(state_default: str, type_name: str = "Integer") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state {\n"
        f"    x : {type_name} = {state_default}\n"
        "  }\n"
        "}\n"
    )


def test_unresolved_name_errors() -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("bogusname"), "t.cardlang"))
    assert "unresolved name 'bogusname'" in e.value.diagnostic.message


def test_unknown_zone_method_errors() -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("hand.bogus(hand)"), "t.cardlang"))
    assert "unknown zone method 'bogus'" in e.value.diagnostic.message


def test_bad_card_suit_errors() -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("Q of sphades", type_name="Card"), "t.cardlang"))
    assert "unknown suit 'sphades'" in e.value.diagnostic.message


def test_known_enum_value_resolves() -> None:
    # `hearts` is a deck suit; resolves as an enum value, not an error.
    resolve(parse_text(_game("hearts", type_name="Suit"), "t.cardlang"))
