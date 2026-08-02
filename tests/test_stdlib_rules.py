"""Standard-library rules: splice, instantiation, and every rejection cell.

A game activates a library rule (`cardlang/stdlib/rules.cardlang`) by name in
`active_rules:` without defining it; a parameterized rule (library or local)
is instantiated by passing arguments. The mismatch cells are all loud
(decisions.md "Surface totality"): shadowing a library name, args on a
parameter-free rule, a bare reference to a parameterized rule, arity/domain
mismatches, conflicting instantiations, and a never-instantiated template.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_stdlib_rules
from cardlang.pipeline import check_dsl
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import stdlib_rules


def _game(active: str, rules: str = "") -> str:
    return f"""
game Mini {{
  players: 4
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ score[player] : Integer = 0  leader : Player? = none }}
  phase play {{
    active_rules: [{active}]
    legal_moves: [play_to_trick]
    leader := 0
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit
  }}
  winner: highest score
}}
{rules}
"""


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


# --- the library registry itself stays well-formed ---


def test_stdlib_rules_parse_and_constrain_known_move_types() -> None:
    lib = stdlib_rules()
    assert {"MustFollowSuit", "NoLeadingSuitUntilBroken"} <= set(lib)
    for rule in lib.values():
        assert rule.constrains in LIBRARY_MOVE_TYPES
        # Every card-set demand carries its impossibility fallback, the same
        # obligation game-local rules are held to.
        if rule.demands is not None and rule.demands.kind == "cards":
            assert rule.if_impossible is not None
        for p in rule.params:
            assert p.type_name == "Suit"  # the one supported template domain


def test_parse_stdlib_rules_surfaces_a_builder_diagnostic_not_a_visit_error() -> None:
    # A rules fragment is transformed by the same _Builder as a full game; a
    # builder-raised diagnostic (here, the `==`-rejection) must surface as a
    # located DiagnosticError, not leak as lark's opaque VisitError wrapper.
    src = """
rule BadRule {
  constrains: play_to_trick
  applies_when: state.led_suit == none
  demands: cards in hand where card.suit is state.led_suit
  if_impossible: hand
}
"""
    with pytest.raises(DiagnosticError) as ei:
        parse_stdlib_rules(src, "frag.cardlang")
    message = str(ei.value)
    assert "write `is`" in message
    diag = ei.value.diagnostic
    assert diag.span is not None
    assert diag.span.source_name == "frag.cardlang"


# --- splice and instantiation ---


def test_a_game_activates_a_library_rule_without_defining_it() -> None:
    g = check_dsl(_game("MustFollowSuit"), "mini.cardlang")
    follow = next(r for r in g.rules if r.name == "MustFollowSuit")
    assert follow.demands is not None and follow.demands.kind == "cards"
    assert follow.params == ()


def test_a_parameterized_library_rule_instantiates_with_a_suit() -> None:
    g = check_dsl(_game("NoLeadingSuitUntilBroken(spades)"), "mini.cardlang")
    inst = next(r for r in g.rules if r.name == "NoLeadingSuitUntilBroken")
    assert inst.params == ()
    # The suit argument was substituted into the demand body.
    assert "spades" in repr(inst.demands)


def test_a_game_local_template_instantiates_too() -> None:
    local = """
rule NoTrumpLead(suit: Suit) {
  constrains: play_to_trick
  applies_when: state.led_suit is none
  demands: cards in hand where card.suit is not suit
  if_impossible: hand
}
"""
    g = check_dsl(_game("NoTrumpLead(clubs)", rules=local), "mini.cardlang")
    inst = next(r for r in g.rules if r.name == "NoTrumpLead")
    assert inst.params == () and "clubs" in repr(inst.demands)


def test_same_instantiation_twice_is_deduplicated() -> None:
    src = _game("NoLeadingSuitUntilBroken(hearts), NoLeadingSuitUntilBroken(hearts)")
    g = check_dsl(src, "mini.cardlang")
    assert [r.name for r in g.rules].count("NoLeadingSuitUntilBroken") == 1


# --- the rejection cells ---


def test_rejects_a_local_definition_under_a_library_name() -> None:
    local = """
rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: cards in hand where card.suit is state.led_suit
  if_impossible: hand
}
"""
    _rejects(_game("MustFollowSuit", rules=local), "shadows the standard-library rule")


def test_rejects_arguments_on_a_parameter_free_rule() -> None:
    _rejects(_game("MustFollowSuit(hearts)"), "takes no parameters")


def test_rejects_a_bare_reference_to_a_parameterized_rule() -> None:
    _rejects(_game("NoLeadingSuitUntilBroken"), "is parameterized")


def test_rejects_an_arity_mismatch() -> None:
    _rejects(
        _game("NoLeadingSuitUntilBroken(hearts, spades)"),
        "takes 1 argument(s), got 2",
    )


def test_rejects_a_non_suit_argument() -> None:
    _rejects(_game("NoLeadingSuitUntilBroken(7)"), "must be a suit literal")
    _rejects(_game("NoLeadingSuitUntilBroken(leader)"), "must be a suit literal")


def test_rejects_two_instantiations_with_different_arguments() -> None:
    src = _game("NoLeadingSuitUntilBroken(hearts), NoLeadingSuitUntilBroken(spades)")
    _rejects(src, "instantiated with different arguments")


def test_rejects_a_never_instantiated_local_template() -> None:
    local = """
rule Unused(suit: Suit) {
  constrains: play_to_trick
  demands: cards in hand where card.suit is not suit
  if_impossible: hand
}
"""
    _rejects(_game("MustFollowSuit", rules=local), "never instantiated")


def test_rejects_a_non_suit_template_domain() -> None:
    local = """
rule ByPlayer(p: Player) {
  constrains: play_to_trick
  demands: cards in hand where card.suit is not hearts
  if_impossible: hand
}
"""
    _rejects(_game("ByPlayer(0)", rules=local), "support Suit only")


def test_rejects_a_template_binder_capturing_its_parameter() -> None:
    # The suit quantifier binds `suit` implicitly, which would capture the
    # template parameter of the same name instead of substituting it.
    local = """
rule Capture(suit: Suit) {
  constrains: play_to_trick
  applies_when: any suit where suit is hearts
  demands: cards in hand where card.suit is not hearts
  if_impossible: hand
}
"""
    _rejects(_game("Capture(hearts)", rules=local), "shadowing its own parameter")
