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

The Prefix Walk. `walk_paired_prefix` walks one line against an oracle that
may end it earlier than the game does, by a draw rule the game does not play
(a turn cap, a no-capture counter), and returns how the line ended as a Line
End (`LineEnd`): `Rules` or `Truncated`. It drives one live run of the game through
`replay.run`'s `beyond` continuation, so a line costs one run rather than one
replay per ply, and closes every line with one paused replay of its whole
history, which must end where the live run ended. `choose` picks each action
(`uniform` is the seeded policy; a caller's script is another), and `advance`
lets the caller's independent model follow the line when an action id needs
facts the decoded action does not carry.

Contract:
- Assumes: the native game named by `native_game` starts at
  `expected_first_player` with no chance node, and our adapter's DecisionNode player
  and mapped legal-action set match native's at every node reachable under the
  shared policy. `to_native` maps a decoded cardlang action to the native
  action id denoting the same move. A native state once terminal stays
  terminal (an external fact about OpenSpiel's states).
- Establishes: on return, both implementations walked to a terminal through the
  identical mapped decision tree; the two returns vectors are handed back for
  the caller to compare (exactly, or by `assert_outcomes_agree`'s
  scale-agnostic win/loss/draw classification). Held by: Born-Green Pin, the
  tic-tac-toe and breakthrough differentials, whose tripwires (a wrong
  direction map, a blind capture bit) redden it; why not higher: agreement is a
  fact about two implementations' runs, which no type carries.
- Divergence is loud: any mismatch raises AssertionError carrying the walk
  label, the ply index, and the decoded-action history (a complete board
  reconstruction for a placement game), never a silent skip or a papered-over
  disagreement. Held by: Born-Green Pin, the tripwires matching the failure's
  text; why not higher: a message is a string no type constrains.
- Assumes (Prefix Walk): `truncate_when` names the oracle's own draw rule,
  never one of the game's, as a predicate asked of a terminal native state.
- Establishes (Prefix Walk): every returned Line End is `Rules` (both sides
  terminal, ours by its rules, the outcomes agreeing) or `Truncated` (the
  oracle terminal at one of our decisions past the root, its end named by
  `truncate_when` and a draw). Held by: Unrepresentable, the closed union
  `LineEnd` that `tally_line_ends` dispatches over with `assert_never`.
  Every other meeting fails naming the ply, each held by Derived and Pinned
  (one check in the walker, and its row in the grid of
  `tests/test_native_oracle_prefix.py`): the oracle terminal at one of our
  decisions with its end unnamed (`assert_node_agrees`'s terminal check); a
  truncation that is decisive, or at our root; our terminal against a live
  oracle, a tie by the game's own rule said so; a Length Stop; a game terminal
  at its root; a wrong first mover; a paused replay ending elsewhere or
  refusing the history. `tally_line_ends` refuses a manifest with no `Rules`
  end, Derived and Pinned: the tally is the walker's own and the refusal
  reads it. Why not higher, for each: the fact is about the values one run
  produces (an untyped OpenSpiel state, a returns vector, a history), which
  no type the walker receives carries.
- Illegal after: comparing returns on a truncated line, held by
  Unrepresentable (`Truncated` carries no returns). Truncating a line the
  oracle still plays, held by Derived and Pinned: the walker asks
  `truncate_when` only behind `native.is_terminal()`, and the grid's
  live-oracle rows record any ask of a live oracle; why not higher: the
  OpenSpiel state is untyped, so no type separates a terminal state from a
  live one. The predicate is monotone along a line by that check and the
  terminal state assumed absorbing above.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, assert_never

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.replay import DecisionNode, HistoryMismatch, TerminalNode, load, run
from cardlang.runtime.driver import EndedBy
from cardlang.runtime.state import RuntimeState


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


@dataclass(frozen=True, slots=True)
class Rules:
    """A line both implementations ended by their rules, on agreeing outcomes."""

    ply: int
    ours: tuple[float, ...]
    native: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Truncated:
    """A line the oracle ended by its own draw rule while the game asks on."""

    ply: int


LineEnd = Rules | Truncated
ToNative = Callable[[Any], int]
Advance = Callable[[int, Any], None]
TruncateWhen = Callable[[Any], bool]
Choose = Callable[[list[int], ActionSpace], int]


def uniform(policy_seed: int) -> Choose:
    """The seeded uniform policy over the offered action ids."""
    policy = random.Random(policy_seed)

    def choose(legal: list[int], space: ActionSpace) -> int:
        return policy.choice(legal)

    return choose


def walk_paired_prefix(
    dsl_path: str,
    native_game: str,
    to_native: ToNative,
    truncate_when: TruncateWhen,
    seed: int,
    choose: Choose,
    *,
    label: str,
    advance: Advance | None = None,
    expected_first_player: int = 0,
) -> LineEnd:
    """Walk one line of our game and a fresh native game in lockstep, `choose`
    picking among our offered ids, and return how the line ended.

    At each of our decisions: a terminal oracle is a truncation when
    `truncate_when` names its end, and that end must be a draw; any other
    terminal oracle is a divergence. Otherwise `assert_node_agrees` compares
    the node, `choose` picks, the oracle applies the mapped id and `advance`
    follows. At our terminal the oracle must be terminal and the outcomes must
    agree; `truncate_when` is not asked there. An exception `choose` or
    `advance` raises ends the walk as that exception."""
    _, space = load(dsl_path)
    native = pyspiel.load_game(native_game).new_initial_state()
    world: list[RuntimeState] = []
    history: list[int] = []
    decoded: list[Any] = []
    asked: list[DecisionNode] = []

    def where() -> str:
        return f"{label} step {len(history)}"

    def beyond(player: int, legal: list[int]) -> int:
        asked[:] = [DecisionNode(player, legal, world[0], {})]
        if not history:
            assert player == expected_first_player, (
                f"{label}: first mover is P{player}, expected "
                f"P{expected_first_player}"
            )
        if native.is_terminal() and truncate_when(native):
            assert history, (
                f"{where()}: the oracle's root is terminal by the rule "
                f"truncate_when names, so the line compares nothing"
            )
            drawn = list(native.returns())
            assert classify(drawn) == "draw", (
                f"{where()}: truncate_when names a decisive oracle end {drawn}; "
                f"a truncation is the oracle's own draw; board={decoded}"
            )
            raise _OracleDrew
        assert_node_agrees(
            native, asked[0], to_native, space,
            label=label, step=len(history), history=decoded,
        )
        action = choose(legal, space)
        chosen = space.decode(action)
        native.apply_action(to_native(chosen))
        if advance is not None:
            advance(player, chosen)
        history.append(action)
        decoded.append(chosen)
        return action

    try:
        ours = run(dsl_path, seed, (), on_first_decision=world.append, beyond=beyond)
    except _OracleDrew:
        paused = _replay(dsl_path, seed, history, where())
        live = asked[0]
        assert (
            isinstance(paused, DecisionNode)
            and paused.player == live.player
            and paused.legal == live.legal
        ), (
            f"{where()}: the paused replay of the line ends at {_describe(paused)}, "
            f"not at the live run's {_describe(live)}"
        )
        return Truncated(len(history))

    assert isinstance(ours, TerminalNode)
    assert history, (
        f"{label}: our game ended before its first decision, so the line "
        f"compares nothing"
    )
    assert ours.ended_by is EndedBy.RULES, (
        f"{where()}: our game's Length Stop ended the line ({ours.returns}); a "
        f"compared line ends by the game's rules; board={decoded}"
    )
    if not native.is_terminal():
        assert classify(ours.returns) != "draw", (
            f"{where()}: our game ended in a tie by its own rule while the "
            f"oracle plays on; board={decoded}"
        )
        raise AssertionError(
            f"{where()}: our game is terminal ({ours.returns}) but native is "
            f"not; board={decoded}"
        )
    native_returns = list(native.returns())
    try:
        assert_outcomes_agree(ours.returns, native_returns)
    except AssertionError as diverged:
        raise AssertionError(f"{where()}: {diverged}; board={decoded}") from None
    paused = _replay(dsl_path, seed, history, where())
    assert (
        isinstance(paused, TerminalNode)
        and paused.returns == ours.returns
        and paused.ended_by is ours.ended_by
    ), (
        f"{where()}: the paused replay of the line ends at {_describe(paused)}, "
        f"not at the live run's {_describe(ours)}"
    )
    return Rules(len(history), tuple(ours.returns), tuple(native_returns))


class _OracleDrew(Exception):
    """The oracle ended the line by the rule `truncate_when` names."""


def _replay(
    dsl_path: str, seed: int, history: list[int], where: str
) -> DecisionNode | TerminalNode:
    """The paused adapter's node at the end of the line."""
    try:
        return run(dsl_path, seed, tuple(history))
    except HistoryMismatch as refused:
        raise AssertionError(
            f"{where}: the paused replay refuses the line's history: {refused}"
        ) from None


def _describe(node: DecisionNode | TerminalNode) -> str:
    if isinstance(node, DecisionNode):
        return f"a decision of P{node.player} offering {node.legal}"
    return f"a terminal ({node.ended_by.value}) with returns {node.returns}"


def tally_line_ends(ends: Iterable[LineEnd]) -> Counter[str]:
    """Count a manifest's line ends: each `Rules` end under the outcome class
    its returns induce, each `Truncated` end under `truncated`. A manifest
    with no `Rules` end compared no returns at all, and is refused."""
    tally: Counter[str] = Counter()
    for end in ends:
        if isinstance(end, Rules):
            tally[classify(list(end.ours))] += 1
        elif isinstance(end, Truncated):
            tally["truncated"] += 1
        else:
            assert_never(end)
    assert sum(n for kind, n in tally.items() if kind != "truncated"), (
        f"no line of the manifest reached a rules end ({dict(tally)}), so no "
        f"returns were compared"
    )
    return tally
