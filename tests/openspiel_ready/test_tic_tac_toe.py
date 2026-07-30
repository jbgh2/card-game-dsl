"""Tic-tac-toe — OpenSpiel readiness (two-observer PERFECT information).

The board-topology walking skeleton, and the corpus's first perfect-information
two-player game. This module is the info-set acceptance evidence for the whole
rung: it proves, for BOTH observers, that every information set is a SINGLETON
and that nothing the observer is entitled to see is dropped nor anything hidden
leaked (there is nothing hidden).

What is proven here
-------------------
- Two-observer degeneracy (``test_indistinguishability_under_hidden_swap``):
  at a replayed mid-game pause, for EACH player no populated zone projects
  below identity (``hidden_cards == 0``) and all nine marks sit in
  identity-projected zones (``visible == 9``); every mark identity appears in
  the rendered information state; and both observers render the identical
  board (the common-knowledge hallmark of perfect information). The base
  proof's premise — a pair of worlds differing only in hidden content — is
  therefore unsatisfiable, so it is proven degenerate rather than skipped.
- Soundness on own view (``test_soundness_own_view_changes_the_state``):
  everything is "own view" here, so the override swaps a placed mark against a
  reserve mark of the OTHER side (distinct renderings) and requires BOTH
  observers' information states to move.
- The per-visible-fact matrix (inherited, the load-bearing proof for a
  perfect-information game): every zone x BOTH observers is identity-projected,
  so every content perturbation must move the state and none may be over-hidden.
- Event-level publicity (``test_placements_are_public_identity_events``): every
  board-directed ``move`` event carries full piece identity on both sides, and
  the two observers' board-directed subsequences are equal — placements are
  common knowledge at the event level.
- Seed degeneracy (``test_no_shuffle_means_seed_degeneracy``): a fixed action
  history renders byte-identical for both players across three seeds.

The singleton-partition argument (the "bulletproof" claim)
----------------------------------------------------------
Every populated zone projects identity to each observer, so the facts matrix's
"identity content shows through" direction gives: equal information state
implies equal visible content. With ``hidden_cards == 0`` there is no hidden
content to vary, so equal visible content forces equal state — the map
(world state -> information state) is injective, i.e. every information set is a
singleton. The marks are FUNGIBLE (all five X marks render ``mark:x``, all four
O marks ``mark:o``), so two arrangements differing only by permuting identical
marks are the SAME position: the partition is a singleton over DISTINCT
positions, not over piece labellings. Legal-action agreement is definitionally
trivial in a singleton partition (one world agrees with itself); it is
cross-checked NON-vacuously by the inherited adapter proof, whose per-step
``state.legal_actions() == r.legal`` compares against an independent pyspiel
re-simulation.

Inherited unchanged
-------------------
pyspiel conformance; the per-visible-fact matrix; seed/rng non-observability
(``vacuous_stock`` — no all-hidden populated stock exists, itself the
perfect-information fact); perfect recall; adapter agreement walked to Terminal
with the ``[+1, -1]`` / ``[0, 0]`` returns compared (the greedy ``legal[0]``
line wins in a measured, deterministic seven placements).

Honest caveats
--------------
- "Every zone identity to all" is precisely "every POPULATED zone": ``box`` is a
  ``Deck`` (count_only), but it is emptied at setup and thereafter renders
  ``box=#0`` identically for both observers, hiding nothing.
- Seed degeneracy is OVER-DETERMINED and its cause is not the absence of
  shuffle: it follows from fungible marks + attribute-based setup + sorted
  identity rendering (order never leaks). Adding a bare ``shuffle box`` is a
  DEMONSTRATED no-op (verified: three seeds stay byte-identical) precisely
  because of that. The firing red-under is ``shuffle box`` PLUS a position-based
  deal (``move 5 pieces from box to reserve[0]``): the x/o split then becomes
  seed-dependent (``reserve[0]=[o,o,o,x,x]`` under one seed, ``[o,x,x,x,x]``
  under another), and the sorted identity views diverge.
- The adapter's root chance node still samples a seed, but every branch is
  provably identical (the seed proof). Collapsing that degenerate node is the
  stage-3 chance workstream (roadmap residual "adapter root-chance collapse for
  chance-free games", added in the rung-1 docs promotion); it is not an
  info-set gap.
"""

from __future__ import annotations

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, _advance
from .partition import first_divergence, projection_for, record, zone_instances

PATH = str(GAMES_DIR / "tic-tac-toe.cardlang")

TOTAL_MARKS = 9  # five X + four O; all nine live in identity-projected zones


def _zone_render(info: str) -> str:
    """The zone-projection portion of an information state (between the
    ``P<n>|`` prefix and ``|state:``) — identical between observers exactly
    when every zone projects identity to both."""
    return info.split("|", 1)[1].split("|state:", 1)[0]


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_tic_tac_toe",
        "tic-tac-toe.cardlang",
        hidden_zone="reserve",  # unused: no zone hides content, both hand-assuming proofs overridden
        depth=4,
        swap_axis="any",  # no public card/rank observation to preserve
        adapter_terminal_steps=9,  # greedy legal[0] line wins in 7 (measured, deterministic); +2 slack
    )

    def test_indistinguishability_under_hidden_swap(self) -> None:
        """Perfect information, two observers: prove the DEGENERACY directly
        rather than vacuously skip. At a replayed pause, for EACH player: no
        populated zone projects below identity (so no hidden pair exists for the
        base proof to swap), all nine marks sit in identity-projected zones, and
        every mark identity appears in the rendered information state. Both
        observers render the identical board — common knowledge — the hallmark
        of a singleton partition under perfect information."""
        _, pause = _advance(PATH, 5, self.spec.depth)
        assert isinstance(pause, Pause)
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
                f"cardlang_tic_tac_toe: P{p} has {hidden} cards in non-identity "
                f"zones — the perfect-information premise is broken"
            )
            assert visible == TOTAL_MARKS, (
                f"cardlang_tic_tac_toe: P{p} sees {visible} of {TOTAL_MARKS} marks "
                f"in identity zones — a mark is over-hidden"
            )
            info = information_state(p, pause.rs, pause.obs_logs[p])
            missing = [
                str(c)
                for _, _, zone in zone_instances(pause.rs)
                for c in zone.cards
                if str(c) not in info
            ]
            assert not missing, (
                f"cardlang_tic_tac_toe: marks absent from P{p}'s info state: {missing}"
            )
            renders.append(_zone_render(info))
        assert renders[0] == renders[1], (
            "cardlang_tic_tac_toe: the two observers render different boards — "
            f"perfect information is broken\nwitness: {first_divergence(renders[0], renders[1])}"
        )
        record(
            "cardlang_tic_tac_toe",
            "swap",
            degenerate="perfect information — no hidden pair exists for either observer",
            hidden_cards=0,
            visible_marks=TOTAL_MARKS,
            observers=len(pause.obs_logs),
            legal_agreement="trivial (singleton); adapter proof cross-checks vs pyspiel re-sim",
        )

    def test_soundness_own_view_changes_the_state(self) -> None:
        """Everything is own view under perfect information. Swap a placed mark
        against a reserve mark of the OTHER side (guaranteed distinct
        renderings, x vs o) at a mid-game pause; BOTH observers' information
        states must move, since every zone is identity-projected to both."""
        _, pause = _advance(PATH, 5, self.spec.depth)
        assert isinstance(pause, Pause)
        square = next(
            (z for name, _, z in zone_instances(pause.rs) if name == "square" and z.cards),
            None,
        )
        assert square is not None and len(square.cards) == 1
        placed = square.cards[0]
        other = pause.rs.zones.instance("reserve", 1 if placed.suit == "x" else 0)
        assert other.cards, "the other side's reserve is empty at this pause"
        mate = other.cards[0]
        assert placed != mate, "placed mark and its swap mate must be distinct sides"

        before = {
            q: information_state(q, pause.rs, pause.obs_logs[q])
            for q in range(len(pause.obs_logs))
        }
        square.cards[0], other.cards[0] = mate, placed
        try:
            for q in range(len(pause.obs_logs)):
                after = information_state(q, pause.rs, pause.obs_logs[q])
                assert after != before[q], (
                    f"cardlang_tic_tac_toe: P{q}'s info state is insensitive to a "
                    f"visible {placed}<->{mate} swap (square <-> other reserve)"
                )
        finally:
            square.cards[0], other.cards[0] = placed, mate


def _board_moves(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The board-directed ``move`` events in an observation log (destination a
    square) — the placements, in game order."""
    return [e for e in log if e[0] == "move" and str(e[3]).startswith("square[")]


def test_placements_are_public_identity_events() -> None:
    """Every board-directed ``move`` event carries full piece identity on BOTH
    sides (reserve source and square destination are both identity-projected),
    and the two observers' board-directed subsequences are EQUAL — placements
    are common knowledge at the event level.

    red under (demonstrated out of band, reverted): flipping ``Cell``'s
    projection to ``count_only`` renders the square-destination view as an int
    count (``('move', 'reserve[0]', ('mark:x',), 'square[a1]', 1)``) instead of
    the identity tuple, so the ``isinstance(dst_view, tuple)`` assertion fails —
    the identity claim is not vacuous.
    """
    _, pause = _advance(PATH, 5, 4)
    assert isinstance(pause, Pause)
    boards: dict[int, list[tuple[Any, ...]]] = {}
    for p in range(len(pause.obs_logs)):
        moves = _board_moves(pause.obs_logs[p])
        assert moves, f"P{p} logged no board-directed placement events"
        for e in moves:
            src_view, dst_view = e[2], e[4]
            assert isinstance(dst_view, tuple) and dst_view and all(
                isinstance(c, str) for c in dst_view
            ), f"placement {e!r}: destination is not a full-identity view"
            assert isinstance(src_view, tuple) and src_view and all(
                isinstance(c, str) for c in src_view
            ), f"placement {e!r}: source is not a full-identity view"
        boards[p] = moves
    assert boards[0] == boards[1], (
        "cardlang_tic_tac_toe: the observers disagree on the board-directed "
        "events — placements are not common knowledge\n"
        f"only-in-P0={[e for e in boards[0] if e not in boards[1]]}\n"
        f"only-in-P1={[e for e in boards[1] if e not in boards[0]]}"
    )
    record(
        "cardlang_tic_tac_toe",
        "placements",
        placements=len(boards[0]),
        common_knowledge=True,
    )


def _first_step_divergence(
    reference: list[tuple[str, ...]], states: list[tuple[str, ...]]
) -> tuple[int, str, str]:
    """The first (step, reference-render, actual-render) where two per-step
    render lists differ, so the witness points at the real divergence rather
    than always at step 0."""
    for i in range(min(len(reference), len(states))):
        if states[i] != reference[i]:
            for q in range(min(len(reference[i]), len(states[i]))):
                if states[i][q] != reference[i][q]:
                    return i, reference[i][q], states[i][q]
            return i, str(reference[i]), str(states[i])
    return 0, str(reference), str(states)


def test_no_shuffle_means_seed_degeneracy() -> None:
    """A fixed action history renders byte-identically for both players across
    three seeds. The degeneracy is OVER-DETERMINED (fungible marks +
    attribute-based setup + sorted identity rendering), not caused by the mere
    absence of shuffle.

    red under (demonstrated out of band, reverted): a bare ``shuffle box`` is a
    DEMONSTRATED no-op — three seeds stay byte-identical — because order never
    leaks and same-side marks are fungible. The firing red-under is
    ``shuffle box`` PLUS a position-based deal (``move 5 pieces from box to
    reserve[0]``): the x/o split becomes seed-dependent
    (``reserve[0]=[mark:o,mark:o,mark:o,mark:x,mark:x]`` under seed 1 vs
    ``[mark:o,mark:x,mark:x,mark:x,mark:x]`` under seed 5), so the sorted
    identity views diverge and the cross-seed equality fails.

    Honest caveat: the adapter's root chance node still samples the seed; every
    branch is provably identical (this proof), and collapsing that degenerate
    node is the stage-3 chance workstream (roadmap residual), not an info-set
    gap.
    """
    history, _ = _advance(PATH, 1, 9)  # the deterministic greedy line, backed off before the win
    assert len(history) >= 4, "seed test needs a non-trivial replayed line"
    reference: list[tuple[str, ...]] | None = None
    for seed in (1, 5, 7):
        states: list[tuple[str, ...]] = []
        for i in range(len(history) + 1):
            r = run(PATH, seed, tuple(history[:i]))
            if not isinstance(r, Pause):
                break
            states.append(
                tuple(
                    information_state(q, r.rs, r.obs_logs[q])
                    for q in range(len(r.obs_logs))
                )
            )
        assert states, f"seed {seed} produced no pause states"
        if reference is None:
            reference = states
        else:
            step, ref_cell, got_cell = _first_step_divergence(reference, states)
            assert states == reference, (
                f"cardlang_tic_tac_toe: seed {seed} renders differently from the "
                f"reference seed — the info state is seed-sensitive\n"
                f"witness (step {step}): {first_divergence(ref_cell, got_cell)}"
            )
    assert reference is not None
    record(
        "cardlang_tic_tac_toe",
        "seed_degeneracy",
        seeds=3,
        steps=len(reference),
        over_determined=True,
    )
