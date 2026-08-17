"""Reusable native-oracle differential for ALTERNATING perfect-information games.

A paired walker that drives a cardlang game (through the seed/history replay
adapter) and an OpenSpiel NATIVE game side by side under one policy, asserting
they present the same decision tree in a mapped action space. It is the second
external cross-implementation check in the corpus, after the GOPS differential.

Scope — alternating, perfect information only. At every one of our decisions
the walker asserts the native state is NOT a chance node and NOT simultaneous;
a game that violates either cannot be walked here:

- GOPS stays bespoke (`tests/test_differential_gops.py`, unchanged): its moves
  are SIMULTANEOUS (both bids resolve at once) and its prize order arrives as a
  stream of native CHANCE nodes that must be driven to follow our realized
  shuffle. Both are outside this walker's contract; folding them in would drown
  the alternating path in branches no board game needs.
- Backgammon is the planned extension point: its per-move dice roll is a native
  chance node interleaved with the alternating turns. Teaching this walker to
  FOLLOW a native chance outcome (the mechanism GOPS already has bespoke) is the
  one addition its rung of the board-topology ladder will require; until a game
  forces it, a chance node is a loud guard, not a silent skip.

Contract:
- Assumes: the native game named by `native_game` starts at
  `expected_first_player` with no chance node, and our adapter's DecisionNode player
  and mapped legal-action set match native's at every node reachable under the
  shared policy. `to_native` maps a decoded cardlang action to the native
  action id denoting the same move.
- Establishes: on return, both implementations walked to a terminal through the
  identical mapped decision tree; the two returns vectors are handed back for
  the caller to compare (exactly, or by `assert_outcomes_agree`'s
  scale-agnostic win/loss/draw classification).
- Divergence is loud: any mismatch raises AssertionError carrying the walk
  label, the ply index, and the decoded-action history (a complete board
  reconstruction for a placement game), never a silent skip or a papered-over
  disagreement.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.replay import DecisionNode, TerminalNode, load, run


def assert_node_agrees(
    native: Any,
    ours: DecisionNode,
    to_native: Callable[[Any], int],
    space: ActionSpace,
    *,
    label: str,
    step: int,
    history: list[Any] | None = None,
) -> list[int]:
    """Assert our DecisionNode and the native state pose the SAME decision, and return
    native's sorted legal-action list. The reusable per-node heart shared by the
    trajectory walker and any exhaustive/scripted paired walk built on it.

    Loud on every divergence a wrong game tree or a wrong `to_native` can
    produce here: a native chance/simultaneous node, a player disagreement, or a
    mapped legal-action SET that differs from native's. The witness names the
    walk (`label`), the ply (`step`), and the decoded-action history so far."""
    where = f"{label} step {step}"
    board = f" board={history}" if history is not None else ""
    assert not native.is_chance_node(), (
        f"{where}: native is at a chance node — this walker is perfect-"
        f"information only (backgammon's dice are the planned extension){board}"
    )
    assert not native.is_terminal(), (
        f"{where}: native is already terminal while our game still offers a "
        f"decision{board}"
    )
    current = native.current_player()
    assert current != pyspiel.PlayerId.SIMULTANEOUS, (
        f"{where}: native is at a simultaneous node — this walker is "
        f"alternating only{board}"
    )
    assert current == ours.player, (
        f"{where}: current player diverges — ours P{ours.player} native "
        f"P{current}{board}"
    )
    mapped = sorted(to_native(space.decode(a)) for a in ours.legal)
    native_legal = sorted(native.legal_actions())
    assert mapped == native_legal, (
        f"{where}: legal actions diverge — ours(mapped)={mapped} "
        f"native={native_legal}{board}"
    )
    return native_legal


def walk_paired_alternating(
    dsl_path: str,
    native_game: str,
    to_native: Callable[[Any], int],
    seed: int,
    policy_seed: int,
    *,
    expected_first_player: int = 0,
) -> tuple[list[float], list[float]]:
    """Walk our game (seed-replayed) and a fresh native game in lockstep under
    one seeded uniform policy in the MAPPED action space; return (our_returns,
    native_returns).

    At every one of our Pauses: native is not chance/simultaneous, the current
    players agree, and the mapped legal-action sets agree exactly (so "uniform
    over ours" equals "uniform over native's"). One policy-chosen action is
    applied to BOTH. At our TerminalNode, native must be terminal too."""
    _, space = load(dsl_path)
    native = pyspiel.load_game(native_game).new_initial_state()
    policy = random.Random(policy_seed)
    label = f"seed {seed}/policy {policy_seed}"

    history: list[int] = []
    decoded: list[Any] = []
    ours = run(dsl_path, seed, ())
    first = True
    while isinstance(ours, DecisionNode):
        if first:
            assert ours.player == expected_first_player, (
                f"{label}: first mover is P{ours.player}, expected "
                f"P{expected_first_player}"
            )
            first = False
        assert_node_agrees(
            native, ours, to_native, space,
            label=label, step=len(history), history=decoded,
        )
        action = policy.choice(ours.legal)
        chosen = space.decode(action)
        native.apply_action(to_native(chosen))
        history.append(action)
        decoded.append(chosen)
        ours = run(dsl_path, seed, tuple(history))

    assert isinstance(ours, TerminalNode)
    assert native.is_terminal(), (
        f"{label} step {len(history)}: our game is terminal but native is not "
        f"— board={decoded}"
    )
    return ours.returns, list(native.returns())


def classify(returns: list[float]) -> str:
    """The win/loss/draw outcome a 2-player returns vector induces, by the sign
    of the return difference — scale-agnostic (a [+1,-1] convention and a
    [+10,-10] one classify identically). A loud guard on any other player count:
    the whole alternating-perfect-information rung ladder (tic-tac-toe through
    draughts, and backgammon) is 2-player, so a wider game is a new design, not
    a silent mis-classification."""
    assert len(returns) == 2, (
        f"classify is defined for 2-player games; got {len(returns)} returns"
    )
    if returns[0] > returns[1]:
        return "p0"
    if returns[1] > returns[0]:
        return "p1"
    return "draw"


def assert_outcomes_agree(ours: list[float], native: list[float]) -> None:
    """Assert both returns vectors induce the SAME win/loss/draw outcome. The
    scale-agnostic comparison: a DSL scoring convention and a native one may
    legitimately differ in magnitude, so a per-game differential asserts this
    always and exact numeric equality only when the conventions were designed to
    match (tic-tac-toe's `result` is +1/0/-1, native's returns too)."""
    assert classify(ours) == classify(native), (
        f"outcome classification diverges — ours {ours} -> {classify(ours)}, "
        f"native {native} -> {classify(native)}"
    )
