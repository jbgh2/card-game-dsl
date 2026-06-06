"""Named top-level routing functions — introduced by Getaway.

Hearts routes inline (`routing = move all cards from trick_pile to waste`).
Getaway needs a *named* routing with branching logic
(`routing = GetawayRouting`). A named routing is a reusable routing body that
runs with the same trick context bound as an inline routing — the `outcome` and
`state` pronouns — so it takes no parameter list.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from lark import Lark, Tree

from cardlang.ast import nodes as n
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

ROUTING_GAME = """
game T {
  players: 4
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {
    hand[player] : Hand<player>
    trick_pile   : TrickPile
    waste        : Discard
  }
  phase p {
    state { leader : Player? = none }
    instantiate Trick (
      participants = all players,
      leader = leader,
      source_zone = hand,
      play_zone = trick_pile,
      play_rules = active_rules,
      outcome = highest_of_led_suit,
      routing = GetawayRouting
    )
  }
  loser: the player where hand[player] is not empty
}

routing GetawayRouting {
  if state.trick_terminated_early { move all cards from trick_pile to hand[outcome] }
  else { move all cards from trick_pile to waste }
}
"""


def test_routing_def_parses_and_attaches_to_game() -> None:
    game = parse_text(ROUTING_GAME, "t.dsl")
    assert len(game.routings) == 1
    routing = game.routings[0]
    assert routing.name == "GetawayRouting"
    assert len(routing.body) == 1
    assert isinstance(routing.body[0], n.IfStmt)


def test_routing_name_resolves_in_instantiate_arg() -> None:
    # The bare `routing = GetawayRouting` reference classifies as a routing.
    game = check_dsl(ROUTING_GAME, "t.dsl")
    inst = next(it for it in game.phases[0].items if isinstance(it, n.Instantiate))
    routing_arg = next(a for a in inst.args if a.name == "routing")
    assert isinstance(routing_arg.value, n.NameRef)
    assert routing_arg.value.ref_kind == "routing"


def test_routing_def_zero_ambiguity() -> None:
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    explicit = Lark(grammar, parser="earley", ambiguity="explicit",
                    propagate_positions=True, maybe_placeholders=True)
    tree = explicit.parse(ROUTING_GAME)
    assert isinstance(tree, Tree)
    ambig = sum(1 for nd in tree.iter_subtrees() if nd.data == "_ambig")
    assert ambig == 0, f"routing_def introduced {ambig} ambiguity site(s)"
