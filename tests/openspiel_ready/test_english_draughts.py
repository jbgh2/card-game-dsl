"""English draughts -- OpenSpiel readiness (two-observer PERFECT information).

The first corpus game whose turn offers captures or steps by whether a
capture exists anywhere, whose one move can take several jumps, and whose
pieces change kind on the board. Breakthrough proved the perfect-information
shape survives movement and capture; this module proves it holds for the
continuing capture, the crowning swap and the state a move leaves for the
next, for BOTH observers: every information set is a singleton, nothing an
observer is entitled to see is dropped, and nothing hidden leaks (there is
nothing hidden).

What is proven here
-------------------
- Two-observer degeneracy (``test_indistinguishability_under_hidden_swap``):
  at a replayed pause in the middle of a capture, for EACH player no
  populated zone projects below identity (``hidden_cards == 0``) and all
  forty-eight pieces sit in identity-projected zones -- on the squares, in
  the reserves, in the king supplies and in the captured piles; every
  populated zone is rendered under its own label with its occupant; both
  observers render the identical board; and both render the square the
  capture goes on from (``chain_from``), the same square, which is the one
  piece the turn may move.
- Soundness on own view (``test_soundness_own_view_changes_the_state``):
  the override perturbs a piece on a square and a captured piece, each
  swapped against one of the other side, and a man on a square swapped
  against a king of its own side from the supply, the swap that only a
  piece's kind tells apart; then the state the move leaves for the next,
  ``chain_from`` moved to another square and the forty-move count moved by
  one. BOTH observers' information states must move under each.
- The per-visible-fact matrix (inherited): every zone x BOTH observers is
  identity-projected, so every content perturbation must move the state.
- Event-level publicity (``test_moves_captures_and_crownings_are_public_identity_events``):
  every square-, reserve- and captured-directed ``move`` event carries full
  piece identity on both sides, and the two observers' subsequences are
  EQUAL; captures and both halves of a crowning (the man from its square to
  the reserve, a king from the supply to the square) are asserted present.
- Chance-freeness is proven over the corpus registry in
  ``tests/test_chance_free.py``.

The singleton-partition argument is breakthrough's (``test_breakthrough.py``):
every populated zone projects identity to each observer and no content is
hidden, so equal information state forces equal position. Pieces of one side
and kind are fungible, so the partition is a singleton over distinct
positions, not over piece labellings. The state variables, ``chain_from`` and
``quiet`` among them, are rendered whole to every seat.

Inherited unchanged
-------------------
pyspiel conformance (the full ``random_sim_test``, a uniform game the rules
end); the per-visible-fact matrix; seed/rng non-observability
(``vacuous_stock``); perfect recall; adapter agreement walked to TerminalNode
with the ``[+1, -1]`` returns compared (the greedy ``legal[0]`` line wins in
a deterministic forty-nine steps).

Honest caveats
--------------
- The greedy line crowns no man, so the crowning rows read a uniform line's
  pause instead (``CROWNING_SEED``).
- ``box`` is a ``Deck`` (count_only), emptied at setup; it renders ``box=#0``
  identically for both observers and hides nothing. The two reserves are
  identity-projected and empty until a man is crowned.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, run

from .harness import ONE_SEED, GAMES_DIR, GameSpec, ReadinessProofs, _advance
from .partition import (
    first_divergence,
    projection_for,
    record,
    unshown_occupants,
    zone_instances,
)

PATH = str(GAMES_DIR / "english-draughts.cardlang")

TOTAL_PIECES = 48  # twelve men and twelve kings a side, all in identity zones

# Deep enough that the greedy line has captured on both sides (its decisions 4
# to 7 are jumps), shallow enough that the inherited replays stay cheap. The
# line is the same for every seed: the game draws nothing.
DEPTH = 12

# The greedy line's first continuing capture: its decision 24 is a jump the
# same piece goes on with, so decision 25 is mid-capture. The two overridden
# proofs pause there.
CHAIN_DEPTH = 25

# A uniform line that crowns a man early: the crowning rows' pause follows it.
CROWNING_SEED = 0


def _zone_render(info: str) -> str:
    """The zone-projection portion of an information state (between the
    ``P<n>|`` prefix and ``|state:``)."""
    return info.split("|", 1)[1].split("|state:", 1)[0]


def _state_render(info: str) -> str:
    """The state-variable portion of an information state."""
    return info.split("|state:", 1)[1].split("|obs:", 1)[0]


class _Crowned(Exception):
    """A man has been crowned and the next decision reached."""


def _crowning_pause() -> DecisionNode:
    """The paused node one decision after the first crowning of the uniform
    line `CROWNING_SEED` makes."""
    rng = random.Random(CROWNING_SEED)
    world: list[Any] = []
    history: list[int] = []

    def beyond(player: int, legal: list[int]) -> int:
        kings = sum(len(world[0].zones.instance("kings", p).cards) for p in (0, 1))
        if kings < TOTAL_PIECES // 2:
            raise _Crowned
        action = rng.choice(legal)
        history.append(action)
        return action

    with pytest.raises(_Crowned):
        run(PATH, 0, (), on_first_decision=world.append, beyond=beyond)
    pause = run(PATH, 0, tuple(history))
    assert isinstance(pause, DecisionNode)
    return pause


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_english_draughts",
        "english-draughts.cardlang",
        hidden_zone="captured",  # unused: no zone hides content, both hand-assuming proofs overridden
        depth=DEPTH,
        swap_axis="any",  # no public card/rank observation to preserve
        adapter_terminal_steps=53,  # greedy legal[0] line wins in 49 (deterministic); +4 slack
    )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        """Perfect information, two observers: prove the DEGENERACY directly.
        At a replayed pause mid-capture, for EACH player: no populated zone
        projects below identity, all forty-eight pieces sit in
        identity-projected zones, and every populated zone is rendered under
        its own label with its occupant. Both observers render the identical
        board and the identical state, the square the capture goes on from
        included.

        red under: make ``_zone_line`` (cardlang/openspiel/infostate.py)
        render a ``square[...]`` zone's pieces as a count; the information
        state stops showing the pieces on the squares and the ``missing``
        assertion fails."""
        _, pause = _advance(PATH, seed, CHAIN_DEPTH)
        assert isinstance(pause, DecisionNode)
        captured = sum(
            len(z.cards) for name, _, z in zone_instances(pause.rs) if name == "captured"
        )
        assert captured, "no piece has been captured by this depth; deepen the spec"
        chain = pause.rs.get("chain_from")
        assert chain is not None, "the pause is not mid-capture; re-measure CHAIN_DEPTH"
        renders: list[str] = []
        states: list[str] = []
        for p in range(len(pause.obs_logs)):
            visible = 0
            hidden = 0
            for name, key, zone in zone_instances(pause.rs):
                if not zone.cards:
                    continue
                if projection_for(pause.rs, name, key, p) == "identity":
                    visible += len(zone.cards)
                else:
                    hidden += len(zone.cards)
            assert hidden == 0, (
                f"cardlang_english_draughts: P{p} has {hidden} pieces in non-identity "
                f"zones -- the perfect-information premise is broken"
            )
            assert visible == TOTAL_PIECES, (
                f"cardlang_english_draughts: P{p} sees {visible} of {TOTAL_PIECES} "
                f"pieces in identity zones -- a piece is over-hidden"
            )
            info = information_state(p, pause.rs, pause.obs_logs[p])
            missing = unshown_occupants(pause.rs, info)
            assert not missing, (
                f"cardlang_english_draughts: P{p}'s info state does not show the "
                f"pieces on {missing}"
            )
            renders.append(_zone_render(info))
            states.append(_state_render(info))
            assert f"chain_from={chain}" in states[-1], (
                f"cardlang_english_draughts: P{p}'s info state does not show the "
                f"capture going on from {chain}"
            )
        assert renders[0] == renders[1], (
            "cardlang_english_draughts: the two observers render different boards -- "
            f"perfect information is broken\nwitness: {first_divergence(renders[0], renders[1])}"
        )
        assert states[0] == states[1], (
            "cardlang_english_draughts: the two observers render different state\n"
            f"witness: {first_divergence(states[0], states[1])}"
        )
        record(
            "cardlang_english_draughts",
            "swap",
            degenerate="perfect information -- no hidden pair exists for either observer",
            hidden_cards=0,
            visible_pieces=TOTAL_PIECES,
            captured=captured,
            chain_from=str(chain),
            observers=len(pause.obs_logs),
            legal_agreement="trivial (singleton); adapter proof cross-checks vs pyspiel re-sim",
        )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_soundness_own_view_changes_the_state(self, seed: int) -> None:
        """Perturb what each observer sees -- a piece on a square and a
        captured piece, each swapped against one of the other side; a man on
        a square swapped against a king of its own side from the supply; the
        square the capture goes on from; and the forty-move count. BOTH
        observers' information states must move under each.

        red under: make ``_zone_line`` render a card by its ``suit`` alone;
        the man-for-king swap, which keeps the side, stops moving the states.
        And: make ``render_state_variable`` spell every ``str`` value alike;
        moving ``chain_from`` to another square stops moving them."""
        _, pause = _advance(PATH, seed, CHAIN_DEPTH)
        assert isinstance(pause, DecisionNode)
        rs = pause.rs
        squares = [z for name, _, z in zone_instances(rs) if name == "square" and z.cards]
        piles = [z for name, _, z in zone_instances(rs) if name == "captured" and z.cards]
        assert len(squares) >= 2 and piles, "the pause offers nothing to perturb"

        red = next(z for z in squares if z.cards[0].suit == "red")
        white = next(z for z in squares if z.cards[0].suit == "white")
        pile = piles[0]
        other = next(z for z in squares if z.cards[0].suit != pile.cards[0].suit)
        man = next(z for z in squares if z.cards[0].rank == "man" and z.cards[0].suit == "red")
        supply = rs.zones.instance("kings", 0)
        assert supply.cards and supply.cards[0].rank == "king"

        def states() -> list[str]:
            return [information_state(q, rs, pause.obs_logs[q]) for q in range(len(pause.obs_logs))]

        for label, a, b in (
            ("square <-> square", red, white),
            ("captured <-> square", pile, other),
            ("man <-> king", man, supply),
        ):
            before = states()
            a.cards[0], b.cards[0] = b.cards[0], a.cards[0]
            try:
                for q, after in enumerate(states()):
                    assert after != before[q], (
                        f"cardlang_english_draughts: P{q}'s info state is insensitive "
                        f"to a visible {label} swap"
                    )
            finally:
                a.cards[0], b.cards[0] = b.cards[0], a.cards[0]

        chain = rs.get("chain_from")
        elsewhere = next(c for c in rs.position_domains["cell"] if c != chain)
        for name, value in (("chain_from", elsewhere), ("quiet", int(rs.get("quiet")) + 1)):
            before = states()
            kept = rs.get(name)
            rs.set(name, value)
            try:
                for q, after in enumerate(states()):
                    assert after != before[q], (
                        f"cardlang_english_draughts: P{q}'s info state is insensitive "
                        f"to {name} moving to {value}"
                    )
            finally:
                rs.set(name, kept)


def _board_moves(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The ``move`` events to or from a square, or into a captured pile --
    setup's placements, steps, captures and both halves of a crowning -- in
    game order."""
    return [
        e
        for e in log
        if e[0] == "move"
        and (str(e[1]).startswith("square[") or str(e[3]).startswith(("square[", "captured[")))
    ]


def test_moves_captures_and_crownings_are_public_identity_events() -> None:
    """Every ``move`` event to or from a square, or into a captured pile,
    carries full piece identity on BOTH sides, and the two observers' subsequences are
    EQUAL -- steps, captures and crownings alike are common knowledge at the
    event level. Captures and both movements of a crowning are asserted
    PRESENT.

    red under: make ``movement`` (cardlang/runtime/observe.py) emit a
    ``reserve``-directed destination as a count; the crowned man's
    destination view is no longer an identity tuple, so the
    ``isinstance(dst_view, tuple)`` assertion fails."""
    pause = _crowning_pause()
    boards: dict[int, list[tuple[Any, ...]]] = {}
    for p in range(len(pause.obs_logs)):
        moves = _board_moves(pause.obs_logs[p])
        takes = [e for e in moves if str(e[3]).startswith("captured[")]
        assert takes, f"P{p} logged no capture events -- the capture claim is vacuous here"
        uncrowned = [
            e for e in moves
            if str(e[1]).startswith("square[") and str(e[3]).startswith("reserve[")
        ]
        crowned = [
            e for e in moves
            if str(e[1]).startswith("kings[") and str(e[3]).startswith("square[")
        ]
        assert uncrowned and crowned, f"P{p} logged no crowning -- the crowning claim is vacuous here"
        for e in moves:
            src_view, dst_view = e[2], e[4]
            assert isinstance(dst_view, tuple) and dst_view and all(
                isinstance(c, str) for c in dst_view
            ), f"event {e!r}: destination is not a full-identity view"
            assert isinstance(src_view, tuple) and src_view and all(
                isinstance(c, str) for c in src_view
            ), f"event {e!r}: source is not a full-identity view"
        boards[p] = moves
    assert boards[0] == boards[1], (
        "cardlang_english_draughts: the observers disagree on the board-directed "
        "events -- movement is not common knowledge\n"
        f"only-in-P0={[e for e in boards[0] if e not in boards[1]]}\n"
        f"only-in-P1={[e for e in boards[1] if e not in boards[0]]}"
    )
    record(
        "cardlang_english_draughts",
        "movements",
        events=len(boards[0]),
        crownings=len([e for e in boards[0] if str(e[1]).startswith("kings[")]),
        common_knowledge=True,
    )

