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
    # (Outcome functions like highest_of_led_suit are now `round` string fields,
    # not bare-name NameRefs, so Hearts no longer carries a "function" ref_kind.)
    assert kinds["p"] == "local"  # the `let base[p]` / `for each player p` binder
    assert kinds["card"] == "local"  # the card-query/comprehension binder
    assert kinds["player"] == "local"  # the `any player where ...` binder


def _game(state_default: str, type_name: str = "Integer") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state {\n"
        f"    x : {type_name} = {state_default}\n"
        "  }\n"
        "  loser: 0\n"
        "}\n"
    )


def test_unresolved_name_errors() -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("bogusname"), "t.cardlang"))
    assert "unresolved name 'bogusname'" in e.value.diagnostic.message


def test_unknown_function_call_errors() -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("bogus(hand)"), "t.cardlang"))
    assert "call to unknown function 'bogus'" in e.value.diagnostic.message


def test_bad_card_suit_errors() -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("Q of sphades", type_name="Card"), "t.cardlang"))
    assert "unknown suit 'sphades'" in e.value.diagnostic.message


def test_known_enum_value_resolves() -> None:
    # `hearts` is a deck suit; resolves as an enum value, not an error.
    resolve(parse_text(_game("hearts", type_name="Suit"), "t.cardlang"))


def test_misspelled_declared_type_errors() -> None:
    # Closed-domain completeness: a declared type name outside the closed set
    # (scalars + enums + the game's structs) is a diagnostic, never a silent
    # TAny that exempts the variable from all further type checking.
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("0", type_name="Integar"), "t.cardlang"))
    assert "unknown type 'Integar' in declaration of 'x'" in e.value.diagnostic.message


def test_declared_struct_type_is_accepted() -> None:
    src = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state { deal : Contract? = none }\n"
        "  loser: 0\n"
        "}\n"
        "type Contract = { level : Integer }\n"
    )
    resolve(parse_text(src, "t.cardlang"))  # no diagnostics


def test_named_call_arguments_are_rejected() -> None:
    # The grammar admits f(x = 1); typecheck skipped the value expression and
    # the runtime crashed with NotImplementedError. Statically rejected until
    # a game needs the surface (Surface totality; recorded in roadmap.md).
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game("team_of(x = 1)"), "t.cardlang"))
    assert "named call arguments are not supported" in e.value.diagnostic.message


def test_unknown_deck_is_a_diagnostic_not_a_crash() -> None:
    # The suit registry derives from the runtime deck table, which raises
    # loudly for unknown names — right at playout time, wrong mid-resolve. A
    # typo'd `cards:` line must surface as a diagnostic naming the known decks.
    src = _game("0").replace("cards: standard52", "cards: standart52")
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(src, "t.cardlang"))
    assert "unknown deck 'standart52'" in e.value.diagnostic.message
    assert "standard52" in e.value.diagnostic.message  # the known-decks hint


@pytest.mark.parametrize(
    ("kind", "src_tail"),
    [
        ("zone", None),  # zones handled via the fixture below
        ("move_type", "move_type m { effect { } }\nmove_type m { effect { } }"),
        ("type", "type T = { a : Integer }\ntype T = { b : Integer }"),
        ("function", "function f(a : Integer) = a\nfunction f(a : Integer) = a"),
    ],
)
def test_duplicate_declarations_are_rejected(kind: str, src_tail: str | None) -> None:
    # Every declaration namespace enforces uniqueness: a duplicate would
    # silently shadow, last-wins — accepted-but-ignored at declaration level.
    if kind == "zone":
        src = _game("0").replace(
            "zones { hand[player] : Hand<player> }",
            "zones { hand[player] : Hand<player>\n    hand[player] : Hand<player> }",
        )
    else:
        src = _game("0") + (src_tail or "")
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(src, "t.cardlang"))
    assert "duplicate" in e.value.diagnostic.message
    assert "silently shadow" in e.value.diagnostic.message


def test_duplicate_state_var_is_rejected() -> None:
    src = _game("0").replace(
        "x : Integer = 0",
        "x : Integer = 0\n    x : Integer = 1",
    )
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(src, "t.cardlang"))
    assert "duplicate state variable 'x'" in e.value.diagnostic.message
