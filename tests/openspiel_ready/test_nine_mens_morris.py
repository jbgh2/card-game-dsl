"""Nine men's morris — OpenSpiel readiness (two-observer PERFECT information).

The first corpus game on a board that is not a grid, and the first whose turn
holds two decisions: the move, then the removal a mill earns. Breakthrough
proved the perfect-information shape survives movement and capture; this
module proves it holds for placement from a reserve, movement along declared
adjacency, flying, and removal into a captured pile, for BOTH observers: every
information set is a singleton, nothing an observer is entitled to see is
dropped, and nothing hidden leaks (there is nothing hidden).

What is proven here
-------------------
- Two-observer degeneracy (``test_indistinguishability_under_hidden_swap``):
  at a replayed pause after a removal, for EACH player no populated zone
  projects below identity (``hidden_cards == 0``) and all eighteen men sit in
  identity-projected zones (``visible == 18``) — on the points, in the
  reserves and in the captured piles; every populated zone is rendered under
  its own label with its occupant, so the observer sees WHERE each man is; and
  both observers render the identical board. The base proof's premise — a pair
  of worlds differing only in hidden content — is unsatisfiable, so it is
  proven degenerate rather than skipped.
- Soundness on own view (``test_soundness_own_view_changes_the_state``): the
  override perturbs a man on a point and a captured man, each swapped against
  a man of the other side, and requires BOTH observers' information states to
  move under each.
- The per-visible-fact matrix (inherited): every zone x BOTH observers is
  identity-projected, so every content perturbation must move the state.
- Event-level publicity (``test_moves_and_removals_are_public_identity_events``):
  every point- or captured-directed ``move`` event — placements, slides and
  removals — carries full piece identity on both sides, and the two observers'
  subsequences are EQUAL; removals are asserted present.
- Adapter returns on a rules-ended line
  (``test_adapter_returns_agree_on_a_rules_ended_line``): a uniform line
  walked through the pyspiel adapter to a terminal the rules reach, its
  returns equal to the DSL's on the same history.
- Chance-freeness is proven over the corpus registry in
  ``tests/test_chance_free.py``.

The singleton-partition argument is breakthrough's
(``test_breakthrough.py``): every populated zone projects identity to each
observer and no content is hidden, so equal information state forces equal
position. The men are fungible, so the partition is a singleton over distinct
positions, not over piece labellings.

Inherited unchanged
-------------------
pyspiel conformance (the full ``random_sim_test``: a uniform game ends by its
rules in a few hundred actions); the per-visible-fact matrix; seed/rng
non-observability (``vacuous_stock``); perfect recall; adapter agreement
over ``depth`` steps of the greedy line, information states and action
strings compared at every step.

Honest caveats
--------------
- ``adapter_terminal_steps`` is None. The greedy ``legal[0]`` line places
  without a mill, removes twice, then shuttles one man between two points and
  never ends by the rules: it reaches the Length Stop at all 6000 picks of
  ``max_length``, scored a tie (measured 2026-11-01; 81s for one native walk,
  `tests/test_length_registry_pin.py`'s ``LOWEST_ID_ENDS`` row). The game draws
  nothing, so every manifest seed walks that same line, and the stop's zeros
  are not a returns comparison worth five walks. The returns surface is
  compared instead on a rules-ended uniform line, above.
- ``box`` is a ``Deck`` (count_only), emptied at setup; it renders ``box=#0``
  identically for both observers and hides nothing. The two reserves are
  identity-projected.
"""

from __future__ import annotations

import random
from typing import Any

import pyspiel
import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, TerminalNode, run

from .harness import ONE_SEED, GAMES_DIR, GameSpec, ReadinessProofs, _advance
from .partition import first_divergence, projection_for, record, zone_instances

PATH = str(GAMES_DIR / "nine-mens-morris.cardlang")

TOTAL_MEN = 18  # nine a side; all eighteen live in identity-projected zones

# Deep enough that the greedy line has removed a man (its first removal is
# decision 20, measured 2026-11-01), shallow enough to be before its second.
DEPTH = 24


def _zone_render(info: str) -> str:
    """The zone-projection portion of an information state (between the
    ``P<n>|`` prefix and ``|state:``)."""
    return info.split("|", 1)[1].split("|state:", 1)[0]


def _occupied(rs: Any) -> list[tuple[str, Any]]:
    """(label, first occupant) for every populated zone instance."""
    return [
        (name if key is None else f"{name}[{key}]", zone.cards[0])
        for name, key, zone in zone_instances(rs)
        if zone.cards
    ]


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_nine_mens_morris",
        "nine-mens-morris.cardlang",
        hidden_zone="captured",  # unused: no zone hides content, both hand-assuming proofs overridden
        depth=DEPTH,
        swap_axis="any",  # no public card/rank observation to preserve
        adapter_terminal_steps=None,  # the greedy line ends by its Length Stop; see the caveats
    )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        """Perfect information, two observers: prove the DEGENERACY directly.
        At a replayed pause, for EACH player: no populated zone projects below
        identity, all eighteen men sit in identity-projected zones, and every
        populated zone is rendered under its own label with a man in it. Both
        observers render the identical board.

        red under: flipping ``Cell``'s projection to ``count_only`` in
        ``ZONE_PROJECTIONS`` leaves the men on the points in non-identity
        zones and the ``hidden == 0`` assertion fails."""
        _, pause = _advance(PATH, seed, self.spec.depth)
        assert isinstance(pause, DecisionNode)
        captured = sum(
            len(z.cards) for name, _, z in zone_instances(pause.rs) if name == "captured"
        )
        assert captured, (
            "no man has been removed by this depth — the captured pile would be "
            "an untested zone; deepen the spec"
        )
        renders: list[str] = []
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
                f"cardlang_nine_mens_morris: P{p} has {hidden} men in non-identity "
                f"zones — the perfect-information premise is broken"
            )
            assert visible == TOTAL_MEN, (
                f"cardlang_nine_mens_morris: P{p} sees {visible} of {TOTAL_MEN} men "
                f"in identity zones — a man is over-hidden"
            )
            info = information_state(p, pause.rs, pause.obs_logs[p])
            missing = [
                label
                for label, occupant in _occupied(pause.rs)
                if f"{label}=[{occupant}" not in info
            ]
            assert not missing, (
                f"cardlang_nine_mens_morris: P{p}'s info state does not show the "
                f"men on {missing}"
            )
            renders.append(_zone_render(info))
        assert renders[0] == renders[1], (
            "cardlang_nine_mens_morris: the two observers render different boards — "
            f"perfect information is broken\nwitness: {first_divergence(renders[0], renders[1])}"
        )
        record(
            "cardlang_nine_mens_morris",
            "swap",
            degenerate="perfect information — no hidden pair exists for either observer",
            hidden_cards=0,
            visible_men=TOTAL_MEN,
            captured=captured,
            observers=len(pause.obs_logs),
            legal_agreement="trivial (singleton); adapter proof cross-checks vs pyspiel re-sim",
        )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_soundness_own_view_changes_the_state(self, seed: int) -> None:
        """Perturb the two kinds of visible man — one on a point, one already
        removed into a captured pile — by swapping each against a man of the
        OTHER side. BOTH observers' information states must move under each.

        red under: flipping ``Cell``'s projection to ``count_only`` makes a
        white-for-black swap between points count-preserving, so the states
        stop moving and the point swap fails."""
        _, pause = _advance(PATH, seed, self.spec.depth)
        assert isinstance(pause, DecisionNode)
        points = [z for name, _, z in zone_instances(pause.rs) if name == "point" and z.cards]
        piles = [z for name, _, z in zone_instances(pause.rs) if name == "captured" and z.cards]
        assert len(points) >= 2 and piles, "the pause offers nothing to perturb"

        white = next(z for z in points if z.cards[0].suit == "white")
        black = next(z for z in points if z.cards[0].suit == "black")
        pile = piles[0]
        other = next(z for z in points if z.cards[0].suit != pile.cards[0].suit)

        for label, a, b in (("point <-> point", white, black), ("captured <-> point", pile, other)):
            before = {
                q: information_state(q, pause.rs, pause.obs_logs[q])
                for q in range(len(pause.obs_logs))
            }
            a.cards[0], b.cards[0] = b.cards[0], a.cards[0]
            try:
                for q in range(len(pause.obs_logs)):
                    after = information_state(q, pause.rs, pause.obs_logs[q])
                    assert after != before[q], (
                        f"cardlang_nine_mens_morris: P{q}'s info state is insensitive "
                        f"to a visible {label} swap"
                    )
            finally:
                a.cards[0], b.cards[0] = b.cards[0], a.cards[0]


def _board_moves(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The point- and captured-directed ``move`` events in an observation log —
    a man placed or moved onto a point, or removed into a captured pile — in
    game order."""
    return [
        e
        for e in log
        if e[0] == "move" and str(e[3]).startswith(("point[", "captured["))
    ]


def test_moves_and_removals_are_public_identity_events() -> None:
    """Every point- or captured-directed ``move`` event carries full piece
    identity on BOTH sides, and the two observers' subsequences are EQUAL —
    placements, slides and removals alike are common knowledge at the event
    level. Removals are asserted PRESENT.

    red under: flipping ``Cell``'s projection to ``count_only`` renders the
    point-destination view as a count instead of the identity tuple, so the
    ``isinstance(dst_view, tuple)`` assertion fails."""
    _, pause = _advance(PATH, ONE_SEED[0], DEPTH)
    assert isinstance(pause, DecisionNode)
    boards: dict[int, list[tuple[Any, ...]]] = {}
    for p in range(len(pause.obs_logs)):
        moves = _board_moves(pause.obs_logs[p])
        assert moves, f"P{p} logged no board-directed events"
        takes = [e for e in moves if str(e[3]).startswith("captured[")]
        assert takes, f"P{p} logged no removal events — the removal claim is vacuous here"
        slides = [e for e in moves if str(e[1]).startswith("point[")]
        assert slides, f"P{p} logged no slide events — the movement claim is vacuous here"
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
        "cardlang_nine_mens_morris: the observers disagree on the board-directed "
        "events — movement is not common knowledge\n"
        f"only-in-P0={[e for e in boards[0] if e not in boards[1]]}\n"
        f"only-in-P1={[e for e in boards[1] if e not in boards[0]]}"
    )
    record(
        "cardlang_nine_mens_morris",
        "movements",
        events=len(boards[0]),
        removals=len([e for e in boards[0] if str(e[3]).startswith("captured[")]),
        common_knowledge=True,
    )


def test_adapter_returns_agree_on_a_rules_ended_line() -> None:
    """A uniform line, walked through the pyspiel adapter to a terminal the
    rules reach, pays a win and a loss, and pays what the DSL pays on the same
    history: the returns surface the greedy line cannot reach, since it ends
    at the Length Stop. Both sides read one `returns_for`, so what this pins
    is the adapter's terminal, not the result mapping.

    red under: make `CardlangState.returns` (cardlang/openspiel/game.py)
    answer zeros at a terminal node."""
    game = pyspiel.load_game("cardlang_nine_mens_morris")
    state = game.new_initial_state()
    rng = random.Random(ONE_SEED[0])
    history: list[int] = []
    while not state.is_terminal():
        action = rng.choice(state.legal_actions())
        state.apply_action(action)
        history.append(action)
    end = run(PATH, ONE_SEED[0], tuple(history))
    assert isinstance(end, TerminalNode)
    assert end.ended_by.value == "rules", "the uniform line ended by its Length Stop"
    assert state.returns() == end.returns
    assert sorted(end.returns) == [-1.0, 1.0]
