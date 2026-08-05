"""Negative tests: the type checker must reject genuinely ill-typed games.

Each is driven RED-first (the pre-check skeleton accepts everything) and a
checking rule turns it GREEN.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.types import Type


def _game(body_state: str, body_play: str) -> str:
    return f"""
game G {{
  players: 2
  max_length: 1000
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


def test_rejects_wrong_stdlib_arg_type() -> None:
    # `player_holding` expects a Card; `hearts` is a Suit.
    src = _game(
        "score[player] : Integer = 0  dealer : Player = 0",
        "dealer := player_holding(hearts)",
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "player_holding" in str(ei.value) or "Card" in str(ei.value)


def test_rejects_subscript_of_non_collection() -> None:
    # `total` is a bare Integer, not a collection; `total[p]` is illegal.
    src = _game(
        "score[player] : Integer = 0  total : Integer = 0",
        "for each player p: score[p] := total[p]",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "g.cardlang")


def test_rejects_none_assigned_to_non_optional() -> None:
    # `none` may only be assigned to an optional; `dealer` is a plain Player.
    src = _game(
        "score[player] : Integer = 0  dealer : Player = 0",
        "dealer := none",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "g.cardlang")


def test_rejects_wrong_call_arity() -> None:
    # `player_holding` takes one Card; two are given.
    src = _game(
        "score[player] : Integer = 0  dealer : Player = 0",
        "dealer := player_holding(2 of clubs, 3 of clubs)",
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "player_holding" in str(ei.value) or "argument" in str(ei.value)


def test_rejects_non_boolean_condition() -> None:
    # `if total { … }` where `total` is an Integer, not a Boolean.
    src = _game(
        "score[player] : Integer = 0  total : Integer = 0",
        "if total { score[0] := 1 }",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "g.cardlang")


def _typed_game(body_play: str) -> str:
    """Like `_game`, but prefixed with a `Contract` struct type so the body can
    construct struct literals. Struct literals are validated in statement
    position (the checker walks statements, not state defaults).

    `deal` is `Contract?` so its `= none` initial value is valid: a non-optional
    struct cannot be `none`, and the state-default type wall
    (`_check_state_default_type`) rightly rejects it — a `Contract = none` here
    would trip that wall before the body's struct-literal check, muddying every
    case below with a second, unrelated error."""
    return f"""
type Contract = {{ level : Integer  suit : Suit }}
game G {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0  deal : Contract? = none }}
  phase play {{ {body_play} }}
  winner: highest score
}}
"""


def test_rejects_struct_literal_missing_field() -> None:
    # `Contract { level: 1 }` omits the declared `suit` field.
    src = _typed_game("deal := Contract { level: 1 }")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "suit" in str(ei.value) or "field" in str(ei.value)


def test_rejects_struct_literal_wrong_field_type() -> None:
    # `level` is declared Integer; `hearts` is a Suit.
    src = _typed_game("deal := Contract { level: hearts, suit: hearts }")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "level" in str(ei.value) or "Integer" in str(ei.value)


def test_rejects_supplying_a_derived_field() -> None:
    # `surplus` is computed; supplying it would let a caller override the
    # derivation, so a struct literal may not provide a derived field.
    src = """
type HandResult = {
  tricks_required : Integer
  tricks_actual   : Integer
} derived {
  surplus = tricks_actual - tricks_required
}
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  result : HandResult = none }
  phase play {
    result := HandResult { tricks_required: 6, tricks_actual: 9, surplus: 999 }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "surplus" in str(ei.value) or "derived" in str(ei.value)


def test_rejects_produce_outside_define() -> None:
    # `produce` is only meaningful in a define body; elsewhere it raises an
    # uncaught signal at runtime, so it must be a compile error.
    src = _game("score[player] : Integer = 0", "produce won")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "produce" in str(ei.value) or "define" in str(ei.value)


def test_rejects_dot_form_on_a_player_receiver() -> None:
    # The dot form is object-member access only (Card, Move, struct fields).
    # `p.hand` — the once-documented zone sugar — was never implemented by the
    # runtime and no corpus game uses it, so it is statically rejected toward
    # the bracket form (decisions.md "Typed object model", access discipline;
    # settled by Doppelkopf, the predicted forcing game, whose relational
    # chains flattened to player-indexed state instead).
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0  d : Player = 0 }
  phase play {
    x := d.score + 1
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value) and "score[...]" in str(ei.value)


def test_rejects_dot_form_on_a_computed_player_receiver() -> None:
    # The complex-receiver case the settled question named: a relational
    # chain in subject position is rejected the same way, not silently
    # deferred — including when rooted at a loop binder the flat walk leaves
    # untyped (offset_by yields a seat regardless of its operand's type).
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0 }
  phase play {
    for each player p:
      x := (p offset_by left).score + 1
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value)


def test_rejects_dot_form_on_an_optional_player_receiver() -> None:
    # Optionals reject like their payload: the closed rejection domain
    # includes the optional wrappers of its members (sweep-the-class).
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0  d : Player? = none }
  phase play {
    x := d.score + 1
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value)


def test_rejects_dot_form_on_loop_and_quantifier_binders() -> None:
    # Binder-introducing constructs type their binders (for-each and
    # quantifier binders are seats/teams by their role), so the dot-form
    # rejection fires on binder-rooted receivers too — untyped, they would
    # infer TAny and only fail loud at runtime.
    header = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0  flag : Boolean = false }
  phase play {
    %s
  }
  winner: highest score
}
"""
    rejected = [
        "for each player p: x := p.score + 1",
        "flag := any player where player.score > 0",
        "x := (number of players where player.score > 0) + 1",
    ]
    for stmt in rejected:
        with pytest.raises(DiagnosticError) as ei:
            check_dsl(header % stmt, "g.cardlang")
        assert "object-member" in str(ei.value), stmt


def test_rejects_dot_form_on_a_team_binder() -> None:
    src = """
game G {
  players: 4
  teams: [[0, 2], [1, 3]]
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[team] : Integer = 0  x : Integer = 0 }
  phase play {
    for each team t: x := t.score + 1
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value) and "Team" in str(ei.value)


def test_rejects_dot_form_on_a_loop_binder_inside_a_produces_arm() -> None:
    # The produces-arm sub-walk threads loop binders exactly like the main
    # walk — an arm body is not a TAny loophole for the dot-form rejection.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0 }
  phase round {
    phase declare -> outcome { done(Player) | skipped } {
      produce skipped
    }
    declare produces:
      done(w) { for each player q: x := q.score + 1 }
      skipped { x := 0 }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value)


def test_rejects_dot_form_on_an_each_simultaneously_binder() -> None:
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  pile : Discard }
  state { score[player] : Integer = 0  x : Integer = 0 }
  phase play {
    // The body is a chosen movement (the only shape this form runs); the point
    // under test is the dot-form on the binder, in its `where` filter.
    each player simultaneously:
      move chosen 1 cards from hand[player] where player.score > 0 to pile
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value)


def test_comprehension_binder_is_card_typed_over_a_zone() -> None:
    # Negative control for the binder typing: a comprehension binder over a
    # card zone is a Card, so its legitimate members stay accepted.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0 }
  phase play {
    x := sum of (if card.suit is hearts then 1 else 0) over cards in deck
  }
  winner: highest score
}
"""
    check_dsl(src, "g.cardlang")  # no raise


# --- The Member arm's coverage of the Type union, DERIVED ---------------------


def test_every_type_union_member_is_classified_by_the_member_arm() -> None:
    """Every `Type` the checker can infer earns a dot-form arm, and the domain
    is read from `get_args(Type)` rather than restated here -- so a newly
    declared type fails THIS test rather than silently reaching no arm and
    inferring `TAny`. That silent fall-through is the permissive-top gap the
    fieldless sweep closed for six types at once; a hand-listed wall would
    reopen it the day someone adds a seventh, which is exactly what this pin
    prevents. The reject classes are IMPORTED from the checker, not copied, so
    the arm and this pin cannot drift apart.

    Adding a type means putting it in one bucket below: give it its own
    field-checking arm (like `TStruct`/`TCard`), classify it as a reject, or
    justify it as structural/permissive.

    red under: delete any member from `_FIELDLESS_RECEIVERS` (or add a member
    to the `Type` union without classifying it here) -- run and observed, both
    directions.
    """
    from typing import get_args

    from cardlang.typecheck import _FIELDLESS_RECEIVERS, _INDEXABLE_RECEIVERS

    declared = {t.__name__ for t in get_args(Type)}

    # Types carrying user-accessible fields: each has its own arm that checks
    # the field name against the declared set.
    fielded = {"TStruct", "TCard"}
    # Its own arm, with an aggregate-instead message.
    collection = {"TCollection"}
    # Structural: unwrapped to its payload before the chain, so a bare
    # TOptional never reaches an arm -- its payload is classified instead.
    structural = {"TOptional"}
    # The permissive top, by design (docs: the deferred parts of the typed
    # object model propagate through it without error).
    permissive = {"TAny"}
    rejected = {t.__name__ for t in _INDEXABLE_RECEIVERS + _FIELDLESS_RECEIVERS}

    buckets = [fielded, collection, structural, permissive, rejected]
    classified: set[str] = set().union(*buckets)

    unclassified = declared - classified
    assert not unclassified, (
        f"Type member(s) {sorted(unclassified)} reach the dot-form (Member) arm "
        "with no case, so `<expr>.field` on one infers TAny with NO diagnostic. "
        "Classify each in tests/test_typecheck_errors.py and give it an arm in "
        "cardlang/typecheck.py::_check_expr."
    )
    assert not classified - declared, (
        f"classified name(s) {sorted(classified - declared)} are not in the Type "
        "union -- a stale entry outliving the type it named."
    )
    # Exactly one bucket each: a type in two classes would take whichever arm
    # the chain reaches first, making the other silently dead.
    for i, bucket in enumerate(buckets):
        for other in buckets[i + 1 :]:
            assert not bucket & other, f"classified twice: {sorted(bucket & other)}"


# --- The fieldless value types: dot-form rejection swept across the class -----
# TCell/TDir/TLine/TEnum/TString have no user-accessible fields, so a dot form on
# one otherwise reaches no Member arm and infers TAny with no diagnostic (the
# permissive-top gap a `cell`/`dir` binder or a movement verb's TCell return
# could slip through). The whole class is walled at the Member arm, at the layer
# that owns operand kinds, not per producer (decisions.md "Closed-domain
# completeness"; the TCard/struct/collection positives above are the negative
# controls that fielded receivers still work). Each cell below is red before the
# sweep -- the dot form checked clean, silently TAny -- and green after.
# TNull is in the swept isinstance defensively: `none` is a comparison-only
# operand, not a bare primary, so `none.foo` does not parse -- unreachable from
# user syntax, covered by the same arm, not independently probed.


def _board_member_probe(move: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        "  board: grid(3, 3)\n"
        "  pieces: xo_marks\n"
        "  zones { box : Deck  square[cell] : Cell<cell>  reserve[player] : PlayerPile<player> }\n"
        "  state { n : Integer = 0 }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        "  }\n"
        "  phase play { turns t from 0 over all players until (n is 1) { offer to t one of [m] } }\n"
        "  winner: highest n\n"
        "}\n"
        + move
    )


def test_rejects_dot_form_on_a_cell_binder() -> None:
    src = _board_member_probe(
        "move_type m(at : cell) { when: at.file is 1 effect { n := 1 } }\n"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value) and "Cell" in str(ei.value)


def test_rejects_dot_form_on_a_dir_binder() -> None:
    src = _board_member_probe(
        "move_type m(along : dir) { when: along.name is 1 effect { n := 1 } }\n"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value) and "Dir" in str(ei.value)


def test_rejects_dot_form_on_a_line_binder() -> None:
    src = _board_member_probe(
        "move_type m(at : cell) {\n"
        "  when: any line in lines(3) where line.file is 1\n"
        "  effect { n := 1 }\n"
        "}\n"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value) and "Line" in str(ei.value)


def test_rejects_dot_form_on_an_enum_value() -> None:
    # `card.suit` is TEnum("Suit"); a dot on it (`card.suit.name`) is fieldless.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0 }
  phase play {
    x := sum of (if card.suit.name is 1 then 1 else 0) over cards in deck
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value)


def test_rejects_dot_form_on_a_string_literal() -> None:
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  x : Integer = 0 }
  phase play {
    x := (if "y".size is 1 then 1 else 0)
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "object-member" in str(ei.value) and "String" in str(ei.value)
