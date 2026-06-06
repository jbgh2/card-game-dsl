from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 2
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


def test_resolves_clean():
    game = check_dsl(SRC, "g.cardlang")  # raises if any name is unresolved
    assert {m.name for m in game.move_types} == {"take_one", "take_two"}


def test_offer_unknown_move_type_errors():
    bad = SRC.replace("[take_one, take_two]", "[take_one, nope]")
    try:
        check_dsl(bad, "g.cardlang")
        assert False, "expected a resolve error for unknown move type"
    except Exception as exc:  # DiagnosticError
        assert "nope" in str(exc)
