from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play {
    for each player p: offer to p one of [take_one, take_two]
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
"""


def test_resolves_clean() -> None:
    game = check_dsl(SRC, "g.cardlang")  # raises if any name is unresolved
    assert {m.name for m in game.move_types} == {"take_one", "take_two"}


def test_actor_classified_as_pronoun() -> None:
    game = check_dsl(SRC, "g.cardlang")
    # `actor` inside a move-type effect must resolve to the pronoun namespace.
    take_one = next(m for m in game.move_types if m.name == "take_one")
    assign = take_one.effect[0]
    assert isinstance(assign, n.AssignStmt)
    actor_ref = assign.index
    assert isinstance(actor_ref, n.NameRef)
    assert actor_ref.name == "actor" and actor_ref.ref_kind == "pronoun"


def test_offer_unknown_move_type_errors() -> None:
    bad = SRC.replace("[take_one, take_two]", "[take_one, nope]")
    try:
        check_dsl(bad, "g.cardlang")
        assert False, "expected a resolve error for unknown move type"
    except Exception as exc:  # DiagnosticError
        assert "nope" in str(exc)
