"""Combination validity beyond the movement production (decisions.md, "Surface
totality"): grammar surface the runtime would silently drop — a duplicate
`state { }` block, a lifecycle hook on a non-repeating phase, an `override`
rule delta, a transition keyed on a non-trick move, a trick round naming a
move type its form cannot run — is rejected at parse/resolve time instead.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

_RULE = """
  rule PassRule {
    constrains: transfer_between_hands
    demands: actions where action.card_count == 3
  }
"""


def _game(body: str, rules: str = "", extra_game_items: str = "") -> str:
    # Rule definitions are top-level items, siblings of the game block.
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0  ldr : Player = 0 }}
  {extra_game_items}
  phase root {{
    {body}
  }}
  winner: highest score
}}
{rules}
"""


def _rejects(src: str, *needles: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    msg = str(ei.value)
    assert any(needle in msg for needle in needles), msg


# --- duplicate state blocks: the runtime keeps one; a silent drop is a bug ---


def test_rejects_a_second_game_level_state_block() -> None:
    # The parser would otherwise keep only the LAST block, silently discarding
    # the first's declarations.
    _rejects(
        _game(
            "for each player q: score[q] := 1",
            extra_game_items="state { bags[player] : Integer = 0 }",
        ),
        "one `state { }` block",
    )


def test_rejects_a_second_phase_level_state_block() -> None:
    # The driver declares only a phase's FIRST block; reads of the second's
    # vars would KeyError at play time.
    _rejects(
        _game("state { a : Integer = 1 }\n    state { b : Integer = 2 }\n    for each player q: score[q] := a"),
        "more than one `state { }` block",
    )


# --- lifecycle hooks belong to `repeats until` phases ---


def test_rejects_before_each_on_a_non_repeating_phase() -> None:
    _rejects(
        _game("before_each { shuffle deck }\n    for each player q: score[q] := 1"),
        "has no iteration",
    )


def test_rejects_after_each_on_a_non_repeating_phase() -> None:
    _rejects(
        _game("after_each { shuffle deck }\n    for each player q: score[q] := 1"),
        "has no iteration",
    )


# --- `override` rule deltas are deferred surface ---


def test_rejects_override_in_active_rules() -> None:
    _rejects(
        _game("active_rules: [override PassRule]\n    for each player q: score[q] := 1", rules=_RULE),
        "not yet supported",
    )


# --- transitions fire from trick plays only ---


def test_rejects_a_transition_on_a_non_trick_event() -> None:
    body = """
    phase a {
      for each player q: score[q] := 1
      transition_to: b when transfer_between_hands where action.card_count == 3
    }
    phase b { for each player q: score[q] := 2 }
    """
    _rejects(_game(body), "must be `play_to_trick`")


# --- the trick round form runs `play_to_trick` only ---


def test_rejects_a_trick_round_naming_another_move_type() -> None:
    body = (
        "round transfer_between_hands from ldr over all players "
        "source hand into pile outcome highest_of_led_suit"
    )
    _rejects(_game(body), "is not runnable on it")


# --- `count over` ignores its body: only the literal `true` is honest ---


def test_rejects_a_count_comprehension_with_a_predicate_body() -> None:
    # The evaluator's `count` arm returns the element count and discards the
    # body — a predicate here would be silently misread as the zone size.
    _rejects(
        _game(
            "let n = count over pile as c: c.suit == hearts\n"
            "    for each player q: score[q] := n"
        ),
        "would silently ignore this body",
    )


def test_accepts_the_count_true_size_idiom() -> None:
    check_dsl(
        _game(
            "let n = count over pile as c: true\n"
            "    for each player q: score[q] := n"
        ),
        "mini.cardlang",
    )


# --- the accepted shapes stay accepted ---


def test_accepts_hooks_on_a_repeats_until_phase() -> None:
    body = """
    phase loop repeats until (any player p: score[p] >= 1) {
      before_each { shuffle deck }
      after_each { shuffle deck }
      phase inner { for each player q: score[q] := 1 }
    }
    """
    check_dsl(_game(body), "mini.cardlang")


def test_accepts_a_play_to_trick_transition_and_plain_rule_refs() -> None:
    body = """
    phase a {
      active_rules: [PassRule]
      for each player q: score[q] := 1
      transition_to: b when play_to_trick where action.card_count == 3
    }
    phase b { for each player q: score[q] := 2 }
    """
    check_dsl(_game(body, rules=_RULE), "mini.cardlang")
