"""No implicit actions: kernel decision points fail loudly when nothing is legal.

These pin the "no implicit actions" contract (decisions.md "No implicit actions"):
a decision with no legal move is a malformed game, reported as an error — never a
silent skip or an implicit default. A regression that restored the old silent
no-op would make one of these tests fail.
"""

from __future__ import annotations

import random
from dataclasses import fields, is_dataclass

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError, Span
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


def _run(src: str) -> None:
    play_game(check_dsl(src, "t.cardlang"), random.Random(0))


OFFER_NO_LEGAL = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play { for each player p: offer to p one of [never] }
  winner: highest coins
}
move_type never { when: false  effect { coins[actor] += 1 } }
"""


def test_offer_with_no_legal_move_raises() -> None:
    # The only move's guard is always false, so the player has nothing legal —
    # the offer must raise, not silently no-op.
    with pytest.raises(RuntimeError, match="none of.*is legal"):
        _run(OFFER_NO_LEGAL)


CHOOSE_EMPTY_RANGE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { x[player] : Integer = 0 }
  phase play { for each player p: x[p] := choose integer in 5 .. 2 }
  winner: highest x
}
"""


def test_choose_over_empty_range_raises() -> None:
    # An inverted range offers no candidate — `choose` must raise, not pick a
    # silent default.
    with pytest.raises(RuntimeError, match="empty range"):
        _run(CHOOSE_EMPTY_RANGE)


RULE_WITHOUT_IF_IMPOSSIBLE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { x[player] : Integer = 0 }
  phase play { }
  winner: highest x
}
rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
}
"""


def test_card_set_demand_without_if_impossible_is_rejected() -> None:
    # A card-set demand can filter the legal set to empty; the rule must declare
    # its `if_impossible` fallback at compile time rather than rely on a silent
    # default. This catches the gap statically, not only when a void state runs.
    with pytest.raises(DiagnosticError, match="no `if_impossible`"):
        check_dsl(RULE_WITHOUT_IF_IMPOSSIBLE, "t.cardlang")


TRICK_ROUND_WITH_AUCTION_OUTCOME = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { leader : Player? = none }
  phase play {
    leader := 0
    round play_to_trick from leader over all players source hand into trick_pile
          outcome bridge_auction_outcome
  }
  winner: highest leader
}
"""


AUCTION_ROUND_WITH_TRICK_OUTCOME = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { passes : Integer = 0 }
  phase bid {
    round offering [pass] from 0 over all players until (passes >= 2)
          outcome highest_trump_or_led_suit
  }
  winner: highest passes
}
move_type pass { effect { passes += 1 } }
"""


def test_trick_round_rejects_an_auction_outcome() -> None:
    # A trick round whose outcome names an auction-form callback resolves to the
    # wrong dispatcher at runtime — reject it at compile time, by form-specific
    # outcome namespace, not with a late AssertionError.
    with pytest.raises(DiagnosticError, match="not a trick outcome function"):
        check_dsl(TRICK_ROUND_WITH_AUCTION_OUTCOME, "t.cardlang")


def test_auction_round_rejects_a_trick_outcome() -> None:
    with pytest.raises(DiagnosticError, match="not an auction outcome function"):
        check_dsl(AUCTION_ROUND_WITH_TRICK_OUTCOME, "t.cardlang")


AUCTION_NON_BOOLEAN_UNTIL = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { passes : Integer = 0 }
  phase bid {
    round offering [pass] from 0 over all players until 1
          outcome bridge_auction_outcome
  }
  winner: highest passes
}
move_type pass { effect { passes += 1 } }
"""


def test_auction_until_must_be_boolean() -> None:
    # The `until` termination is a predicate; a non-Boolean (here Integer `1`)
    # would silently fall back to Python truthiness at runtime, so it is a
    # type error.
    with pytest.raises(DiagnosticError, match="`until` condition must be Boolean"):
        check_dsl(AUCTION_NON_BOOLEAN_UNTIL, "t.cardlang")


PARAM_NAME_COLLIDES_WITH_STATE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { strain : Suit? = none  picked[player] : Suit? = none  score[player] : Integer = 0 }
  phase play {
    for each player p: picked[p] := strain
  }
  winner: highest score
}
move_type bid(strain : Suit?) { when: always  effect { picked[actor] := strain } }
"""


def _name_refs(node: object) -> list[n.NameRef]:
    """Every NameRef under `node` (a tiny AST walk for ref_kind assertions);
    accepts a node, a tuple of nodes, or any nested mix."""
    out: list[n.NameRef] = []
    if isinstance(node, n.NameRef):
        out.append(node)
    if isinstance(node, tuple):
        for item in node:
            out.extend(_name_refs(item))
    elif is_dataclass(node) and not isinstance(node, Span):
        for f in fields(node):
            out.extend(_name_refs(getattr(node, f.name)))
    return out


def test_move_param_scopes_to_its_move_both_directions() -> None:
    # A move parameter binds only in its own guard/effect; it must not leak into
    # the game-wide local set. Both directions of that scoping are pinned: a
    # same-named state var read OUTSIDE the move resolves as state (not the move's
    # local, which would read an empty ctx.locals -> KeyError at runtime), while
    # the param read INSIDE the move resolves as the local.
    game = check_dsl(PARAM_NAME_COLLIDES_WITH_STATE, "t.cardlang")

    # Direction A (the dangerous one): the game runs — the outside `strain` read is
    # state, not an unbound local.
    assert play_game(game, random.Random(0)).winner in (0, 1)

    # Direction B: inside the move's effect, `strain` is the parameter (local).
    bid = next(m for m in game.move_types if m.name == "bid")
    strain_refs = [r for r in _name_refs(bid.effect) if r.name == "strain"]
    assert strain_refs and all(r.ref_kind == "local" for r in strain_refs)

    # ...and the outside read classified as a state var.
    phase = game.phases[0]
    outside = [r for r in _name_refs(phase.items) if r.name == "strain"]
    assert outside and all(r.ref_kind == "state_var" for r in outside)


AUCTION_NO_LEGAL_MOVE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { passes : Integer = 0 }
  phase bid {
    round offering [never] from 0 over all players until (passes >= 99)
          outcome bridge_auction_outcome
  }
  winner: highest passes
}
move_type never { when: false  effect { passes += 1 } }
"""


def test_auction_with_no_legal_move_raises() -> None:
    # An auction participant offered a turn with nothing legal must raise — the
    # same fail-loud contract as `offer`, but in run_auction's ring (no silent
    # skip). Distinct code path from test_offer_with_no_legal_move_raises.
    with pytest.raises(RuntimeError, match="has no legal move"):
        _run(AUCTION_NO_LEGAL_MOVE)


OFFER_OF_PARAMETERIZED_MOVE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { picked[player] : Suit? = none }
  phase play { for each player p: offer to p one of [pick] }
  winner: highest picked
}
move_type pick(strain : Suit?) { effect { picked[actor] := strain } }
"""


def test_offer_of_parameterized_move_is_rejected() -> None:
    # `offer` picks a move by name and can't supply a parameter; a parameterized
    # move belongs in an auction `round offering`, which enumerates its domain.
    # Caught at resolve, not as an opaque runtime KeyError on the unbound param.
    with pytest.raises(DiagnosticError, match="parameterized move type"):
        check_dsl(OFFER_OF_PARAMETERIZED_MOVE, "t.cardlang")
