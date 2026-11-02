"""The installed OpenSpiel `nine_mens_morris` slides a man onto point 0.

Point 0 is a7 on the World Mind Sports board; its neighbours are 1 (d7) and
9 (a4). open_spiel releases before 2.0 place at point 0 and slide from it but
never slide onto it, so a differential walked against one of them compares a
correct game with a board whose corner is dead. The `openspiel` extra's floor
in `pyproject.toml` is the one site declaring which wheel is installed, and a
floor cannot see whether a wheel carries the fix; this pin can.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        with point 0 empty, the installed oracle offers White's
                 slide 1 -> 0 and Black's slide 9 -> 0.
domain:          the two constructed positions: `_POSITION` after its
                 eighteen mill-free placements (White to move), and the
                 same after one quiet White slide (Black to move). Each
                 sits in the sliding phase with a7 empty and the slide's
                 man on its neighbour.
registry:        the `openspiel` extra's `open_spiel` floor, `pyproject.toml`.
held by:         Born-Green Pin. The oracle is an external binary; the floor
                 in `pyproject.toml` declares the wheel but cannot see its
                 rules, so the fact is pinned only by executing the wheel.
                 red under: `pip install open_spiel==1.6.15` -- both
                 slides onto point 0 report illegal.
does not prove:  that the installed oracle agrees with OpenSpiel's master
                 rules anywhere else on the board. The morris differential
                 (issue #978) is the walk that asks that.
"""

from __future__ import annotations

from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

# Placements alternate White, Black: White on 1 (d7), Black on 9 (a4), point
# 0 never placed.
_POSITION = (1, 9, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 16, 15, 17, 19)


def _game() -> Any:
    return pyspiel.load_game("nine_mens_morris")


def _placed() -> Any:
    state = _game().new_initial_state()
    for point in _POSITION:
        mover = state.current_player()
        state.apply_action(point)
        assert state.current_player() != mover, f"placing {point} closes a mill"
    return state


def _action(state: Any, text: str) -> int:
    matches = [
        a
        for a in range(state.get_game().num_distinct_actions())
        if state.action_to_string(state.current_player(), a) == text
    ]
    assert len(matches) == 1, f"{text!r} names {matches}"
    return matches[0]


def _assert_sliding(state: Any) -> None:
    offered = [state.action_to_string(state.current_player(), a) for a in state.legal_actions()]
    assert offered and all(s.startswith("Move ") for s in offered), offered


def test_white_slides_onto_point_0() -> None:
    state = _placed()
    assert state.current_player() == 0
    _assert_sliding(state)
    assert _action(state, "Move 1 -> 0") in state.legal_actions()


def test_black_slides_onto_point_0() -> None:
    state = _placed()
    quiet = _action(state, "Move 13 -> 20")
    assert quiet in state.legal_actions()
    state.apply_action(quiet)
    assert state.current_player() == 1, "Move 13 -> 20 closes a mill"
    _assert_sliding(state)
    assert _action(state, "Move 9 -> 0") in state.legal_actions()
