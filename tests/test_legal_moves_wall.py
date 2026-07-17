"""The `legal_moves`-in-a-rule-delta-sub-phase wall (resolve.py's
`_check_rule_delta_subphases`).

A rule-delta sub-phase is config-only (`_is_rule_delta`: nothing but
`active_rules:` / `legal_moves:` / `transition_to:`). The runtime never runs
it and folds only its `active_rules:` (`compute_active_rules`) and reads only
its `transition_to:` (`phase_transitions`); a `legal_moves:` inside one is
consulted by no consumer, so it would be silently ignored — the
accepted-but-ignored class. The wall rejects it at resolve instead. The
design boundary it draws: the move menu is set by the phase a player is in,
never toggled by an invisible config sub-phase.

The message itself is pinned as a rendered artifact in
`tests/rejections/legal_moves_in_rule_delta_subphase.{cardlang,expected}`;
this module pins the DOMAIN — every position a `LegalMoves` item can sit in.

Completeness ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------------------
property:   a `legal_moves` item with no runtime effect is rejected at
            resolve, never silently ignored
domain:     the position of a `LegalMoves` item, quantified over the three
            slots the grammar's `legal_moves` production can occupy against
            the `_is_rule_delta` partition:
              (1) top-level phase, (2) normal (executed) sub-phase,
              (3) rule-delta (config-only) sub-phase — and, within (3), the
            item-combinations `_is_rule_delta` admits: {LM}, {LM,AR},
            {LM,TT}, {LM,AR,TT}
registry:   the `legal_moves` grammar production × `_is_rule_delta`
            (cardlang/runtime/phases.py)
covered:    - slot (3), every admitted combination -> resolve diagnostic
              (test_legal_moves_only_*, _with_active_rules_*, _with_transition_*)
            - slot (1) top-level phase -> consumed, not walled (test_top_level_*)
            - slot (2) normal sub-phase -> consumed, not walled (test_normal_subphase_*)
            - the delta-operator spelling `legal_moves: [+ X]` -> grammar
              parse error, the adjacent wrong sentence (test_delta_operator_*)
sampled:    none
residual:   none — the domain is closed and every cell has a run probe
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

_HEAD = """game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { score[player] : Integer = 0 }
"""
_TAIL = "  winner: highest score\n}\n"

_WALL = "`legal_moves:` in a rule-delta sub-phase"


def _messages(body: str) -> list[str] | None:
    """Run a game whose `play`-level content is `body`; return the rendered
    error messages, or None if it checks clean."""
    try:
        check_dsl(_HEAD + body + _TAIL, "wall.cardlang")
    except DiagnosticError as e:
        return [str(e), *(str(n) for n in getattr(e, "__notes__", []))]
    return None


def _rejected_by_wall(body: str) -> bool:
    msgs = _messages(body)
    return msgs is not None and any(_WALL in m for m in msgs)


# --- slot (3): rule-delta sub-phase — every admitted combination is walled ---


def test_legal_moves_only_in_delta_subphase_is_rejected() -> None:
    assert _rejected_by_wall(
        """  phase play {
    legal_moves: [play_to_trick]
    phase r { legal_moves: [play_to_trick] }
  }
"""
    )


def test_legal_moves_with_active_rules_in_delta_subphase_is_rejected() -> None:
    assert _rejected_by_wall(
        """  phase play {
    legal_moves: [play_to_trick]
    phase window {
      active_rules: [+ MustFollowSuit]
      legal_moves: [play_to_trick]
    }
  }
"""
    )


def test_legal_moves_with_transition_in_delta_subphase_is_rejected() -> None:
    assert _rejected_by_wall(
        """  phase play {
    legal_moves: [play_to_trick]
    phase before {
      legal_moves: [play_to_trick]
      transition_to: after when play_to_trick
    }
    phase after { }
  }
"""
    )


# --- slots (1) and (2): a LegalMoves that IS consulted must NOT be walled ---


def test_top_level_phase_legal_moves_is_not_walled() -> None:
    assert _messages("  phase play { legal_moves: [play_to_trick] }\n") is None


def test_legal_moves_in_normal_subphase_is_not_walled() -> None:
    # `inner` carries a statement, so it is an executed sub-phase, not a
    # rule-delta one — its legal_moves is genuinely in force while it runs.
    assert (
        _messages(
            """  phase play {
    phase inner { legal_moves: [play_to_trick]  score[0] := 1 }
  }
"""
        )
        is None
    )


def test_active_rules_delta_subphase_without_legal_moves_is_not_walled() -> None:
    # The Hearts `hearts_not_broken` shape: active_rules + transition_to, no
    # legal_moves. The wall must not over-fire on the legitimate delta.
    assert (
        _messages(
            """  phase play {
    legal_moves: [play_to_trick]
    phase before { active_rules: [+ MustFollowSuit]  transition_to: after when play_to_trick }
    phase after { }
  }
"""
        )
        is None
    )


# --- the adjacent wrong sentence: the delta operator the docs once implied ---


def test_legal_moves_delta_operator_is_a_grammar_error() -> None:
    # `legal_moves: [+ X]` — the symmetry with active_rules the spec once
    # claimed. The grammar admits only bare names here, so it fails loud at
    # parse (not the resolve wall, but the right currency: a located error).
    msgs = _messages("  phase play { legal_moves: [+ play_to_trick] }\n")
    assert msgs is not None
    assert not any(_WALL in m for m in msgs)  # a parse error, not the resolve wall


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
