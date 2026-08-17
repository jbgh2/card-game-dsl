from __future__ import annotations

import cardlang.ast.nodes as n
from cardlang.parse import parse_text

# A phase declares a variant outcome type in its header, mirroring `define`'s
# `-> { ... }` but with the `outcome` keyword.
SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { trump_suit : Suit? = none }
  phase round {
    phase declare_trump -> outcome { trump_declared(Suit) | bid_abandoned } {
      produce bid_abandoned
    }
    declare_trump produces:
      trump_declared(t) { trump_suit := t }
      bid_abandoned     { trump_suit := none }
  }
  winner: highest score
}
"""


def _find_phase(phase: n.Phase, name: str) -> n.Phase | None:
    if phase.name == name:
        return phase
    for item in phase.items:
        if isinstance(item, n.Phase):
            found = _find_phase(item, name)
            if found is not None:
                return found
    return None


def test_phase_parses_with_outcome_cases() -> None:
    game = parse_text(SRC, "g.cardlang")
    declare = None
    for top in game.phases:
        declare = _find_phase(top, "declare_trump")
        if declare is not None:
            break
    assert declare is not None
    assert [(c.tag, c.payload_types) for c in declare.outcome_cases] == [
        ("trump_declared", ("Suit",)),
        ("bid_abandoned", ()),
    ]


def test_phase_without_outcome_has_empty_cases() -> None:
    game = parse_text(SRC, "g.cardlang")
    top = game.phases[0]  # `round` — no outcome declared
    assert top.outcome_cases == ()


OPTIONAL_SRC = """
game G {
  players: 4
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { trump_suit : Suit? = none }
  phase rubber {
    phase auction -> outcome { contract_finalized(Player, Integer, Suit?) | all_pass } {
      produce all_pass
    }
    auction produces:
      contract_finalized(d, level, strain) { trump_suit := strain }
      all_pass { skip to next hand }
  }
  winner: highest score
}
"""


def test_variant_payload_type_can_be_optional() -> None:
    game = parse_text(OPTIONAL_SRC, "g.cardlang")
    auction = _find_phase(game.phases[0], "auction")
    assert auction is not None
    cases = {c.tag: c.payload_types for c in auction.outcome_cases}
    assert cases["contract_finalized"] == ("Player", "Integer", "Suit?")
    assert cases["all_pass"] == ()


CONTROL_SRC = """
game G {
  players: 4
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  phase rubber {
    phase auction -> outcome { made | all_pass } { produce made }
    auction produces:
      made     { continue to play }
      all_pass { skip to next hand }
    phase play { }
  }
  winner: highest score
}
"""


def test_arm_bodies_parse_continue_to_and_skip_to_next_hand() -> None:
    import cardlang.ast.nodes as n

    game = parse_text(CONTROL_SRC, "g.cardlang")
    rubber = game.phases[0]
    produces = next(i for i in rubber.items if isinstance(i, n.Produces))
    arms = {a.tag: a.body for a in produces.arms}
    assert len(arms["made"]) == 1
    assert isinstance(arms["made"][0], n.ContinueTo)
    assert arms["made"][0].phase == "play"
    assert len(arms["all_pass"]) == 1
    assert isinstance(arms["all_pass"][0], n.SkipToNextHand)
