"""Breakthrough — OpenSpiel readiness (two-observer PERFECT information).

The board-topology movement rung, and the corpus's first game whose pieces
travel. Tic-tac-toe proved the perfect-information shape for PLACEMENT; this
module proves it survives MOVEMENT and CAPTURE — the two new event kinds — for
BOTH observers: every information set is a singleton, nothing an observer is
entitled to see is dropped, and nothing hidden leaks (there is nothing hidden).

What is proven here
-------------------
- Two-observer degeneracy (``test_indistinguishability_under_hidden_swap``):
  at a replayed mid-game pause, for EACH player no populated zone projects
  below identity (``hidden_cards == 0``) and all thirty-two men sit in
  identity-projected zones (``visible == 32``) — on the board and in the
  captured piles; every populated zone is rendered under its own label with
  its occupant, so the observer sees WHERE each man is, not merely that men
  exist; and both observers render the identical board (the common-knowledge
  hallmark of perfect information). The base proof's premise — a pair of
  worlds differing only in hidden content — is therefore unsatisfiable, so it
  is proven degenerate rather than skipped.
- Soundness on own view (``test_soundness_own_view_changes_the_state``):
  everything is "own view" here, so the override perturbs a BOARD man and a
  CAPTURED man (each swapped against a man of the other side, so the
  renderings genuinely differ) and requires BOTH observers' information states
  to move under each. The captured pile is perturbed explicitly because it is
  the rung's new zone: a capture that vanished from the record would leave
  this the only proof that notices.
- The per-visible-fact matrix (inherited, the load-bearing proof for a
  perfect-information game): every zone x BOTH observers is identity-projected,
  so every content perturbation must move the state and none may be over-hidden.
- Event-level publicity (``test_moves_and_captures_are_public_identity_events``):
  every board-directed ``move`` event — placements at setup, steps, and the
  displacement half of a capture — carries full piece identity on both sides,
  and the two observers' board-directed subsequences are EQUAL. The pause is
  chosen so captures have happened, and their presence is asserted, so the
  capture half cannot go vacuous.
- Seed degeneracy (``test_no_shuffle_means_seed_degeneracy``): a fixed action
  history renders byte-identically for both players across three seeds.

The singleton-partition argument (the "bulletproof" claim)
----------------------------------------------------------
Every populated zone projects identity to each observer, so the facts matrix's
"identity content shows through" direction gives: equal information state
implies equal visible content. With ``hidden_cards == 0`` there is no hidden
content to vary, so equal visible content forces equal state — the map
(world state -> information state) is injective, i.e. every information set is
a singleton. The men are FUNGIBLE (all sixteen light men render ``man:light``,
all sixteen dark ``man:dark``), so two positions differing only by permuting
same-side men are the SAME position: the partition is a singleton over DISTINCT
positions, not over piece labellings. That is why the degeneracy proof checks
zone-by-zone occupancy rather than counting distinct labels — WHERE the men are
is the whole of the information. Legal-action agreement is definitionally
trivial in a singleton partition (one world agrees with itself); it is
cross-checked NON-vacuously by the inherited adapter proof, whose per-step
``state.legal_actions() == r.legal`` compares against an independent pyspiel
re-simulation.

Inherited unchanged
-------------------
pyspiel conformance (the full ``random_sim_test``); the per-visible-fact
matrix; seed/rng non-observability (``vacuous_stock`` — no all-hidden populated
stock exists, itself the perfect-information fact); perfect recall; adapter
agreement walked to Terminal with the ``[+1, -1]`` returns compared (the greedy
``legal[0]`` line wins in a measured, deterministic thirty steps).

Honest caveats
--------------
- "Every zone identity to all" is precisely "every POPULATED zone": ``box`` is
  a ``Deck`` (count_only), but it is emptied at setup and thereafter renders
  ``box=#0`` identically for both observers, hiding nothing. The two
  ``reserve`` piles are identity-projected and empty after setup — the army
  fills the home ranks exactly — so they conceal nothing either.
- Seed degeneracy is OVER-DETERMINED and its cause is not the absence of
  shuffle: it follows from fungible men + attribute-based setup + sorted
  identity rendering (order never leaks). Adding a bare ``shuffle box`` is a
  DEMONSTRATED no-op (verified: three seeds stay byte-identical) precisely
  because of that. The firing red-under is ``shuffle box`` PLUS a
  position-based deal (``move 16 pieces from box to reserve[0]``): the
  light/dark split then becomes seed-dependent and the sorted identity views
  diverge (verified: the very first pause differs between seeds 1 and 5).
- The adapter's root chance node still samples a seed, but every branch is
  provably identical (the seed proof). Collapsing that degenerate node is the
  stage-3 chance workstream (roadmap residual "adapter root-chance collapse for
  chance-free games"); it is not an info-set gap.
- A decider holding men with every step blocked is not modelled (the DSL would
  raise where the oracle returns an empty action list). It did not arise in 400
  random games and no machinery is built for it — issue #124. Nothing in this
  module depends on it.
"""

from __future__ import annotations

from typing import Any

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import ONE_SEED, GAMES_DIR, GameSpec, ReadinessProofs, _advance
from .partition import first_divergence, projection_for, record, zone_instances

PATH = str(GAMES_DIR / "breakthrough.cardlang")

TOTAL_MEN = 32  # sixteen a side; all thirty-two live in identity-projected zones

# Deep enough that steps AND captures have happened (measured: the greedy line
# has taken a man from each side by here), shallow enough to be far from the
# thirty-step terminal.
DEPTH = 12


def _zone_render(info: str) -> str:
    """The zone-projection portion of an information state (between the
    ``P<n>|`` prefix and ``|state:``) — identical between observers exactly
    when every zone projects identity to both."""
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
        "cardlang_breakthrough",
        "breakthrough.cardlang",
        hidden_zone="captured",  # unused: no zone hides content, both hand-assuming proofs overridden
        depth=DEPTH,
        swap_axis="any",  # no public card/rank observation to preserve
        adapter_terminal_steps=34,  # greedy legal[0] line wins in 30 (measured, deterministic); +4 slack
    )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        """Perfect information, two observers: prove the DEGENERACY directly
        rather than vacuously skip. At a replayed pause, for EACH player: no
        populated zone projects below identity (so no hidden pair exists for
        the base proof to swap), all thirty-two men sit in identity-projected
        zones, and every populated zone is rendered under its own label with a
        man in it — the men are fungible, so their POSITIONS are the whole of
        the information. Both observers render the identical board — common
        knowledge — the hallmark of a singleton partition under perfect
        information.

        red under (demonstrated out of band, reverted): flipping ``Cell``'s
        projection to ``count_only`` leaves thirty men in non-identity zones
        and the perfect-information assertion fails — the degeneracy is a
        measured fact, not a definition."""
        _, pause = _advance(PATH, seed, self.spec.depth)
        assert isinstance(pause, Pause)
        captured = sum(
            len(z.cards) for name, _, z in zone_instances(pause.rs) if name == "captured"
        )
        assert captured, (
            "no man has been captured by this depth — the captured pile would be "
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
                f"cardlang_breakthrough: P{p} has {hidden} men in non-identity "
                f"zones — the perfect-information premise is broken"
            )
            assert visible == TOTAL_MEN, (
                f"cardlang_breakthrough: P{p} sees {visible} of {TOTAL_MEN} men "
                f"in identity zones — a man is over-hidden"
            )
            info = information_state(p, pause.rs, pause.obs_logs[p])
            missing = [
                label
                for label, occupant in _occupied(pause.rs)
                if f"{label}=[{occupant}" not in info
            ]
            assert not missing, (
                f"cardlang_breakthrough: P{p}'s info state does not show the men "
                f"on {missing}"
            )
            renders.append(_zone_render(info))
        assert renders[0] == renders[1], (
            "cardlang_breakthrough: the two observers render different boards — "
            f"perfect information is broken\nwitness: {first_divergence(renders[0], renders[1])}"
        )
        record(
            "cardlang_breakthrough",
            "swap",
            degenerate="perfect information — no hidden pair exists for either observer",
            hidden_cards=0,
            visible_men=TOTAL_MEN,
            captured=captured,
            observers=len(pause.obs_logs),
            legal_agreement="trivial (singleton); adapter proof cross-checks vs pyspiel re-sim",
        )

    def test_soundness_own_view_changes_the_state(self) -> None:
        """Everything is own view under perfect information. Perturb the two
        kinds of visible man this rung has — one standing on a square, one
        already taken into a captured pile — by swapping each against a man of
        the OTHER side (guaranteed distinct renderings, light vs dark). BOTH
        observers' information states must move under each, since every zone is
        identity-projected to both.

        red under (demonstrated out of band, reverted): flipping ``Cell``'s
        projection to ``count_only`` makes a light-for-dark swap
        count-preserving, so P0's state stops moving and the square swap
        fails."""
        _, pause = _advance(PATH, 5, self.spec.depth)
        assert isinstance(pause, Pause)
        squares = [z for name, _, z in zone_instances(pause.rs) if name == "square" and z.cards]
        piles = [z for name, _, z in zone_instances(pause.rs) if name == "captured" and z.cards]
        assert len(squares) >= 2 and piles, "the pause offers nothing to perturb"

        light = next(z for z in squares if z.cards[0].suit == "light")
        dark = next(z for z in squares if z.cards[0].suit == "dark")
        pile = piles[0]
        other = next(z for z in squares if z.cards[0].suit != pile.cards[0].suit)

        for label, a, b in (("square <-> square", light, dark), ("captured <-> square", pile, other)):
            before = {
                q: information_state(q, pause.rs, pause.obs_logs[q])
                for q in range(len(pause.obs_logs))
            }
            a.cards[0], b.cards[0] = b.cards[0], a.cards[0]
            try:
                for q in range(len(pause.obs_logs)):
                    after = information_state(q, pause.rs, pause.obs_logs[q])
                    assert after != before[q], (
                        f"cardlang_breakthrough: P{q}'s info state is insensitive to a "
                        f"visible {label} swap"
                    )
            finally:
                a.cards[0], b.cards[0] = b.cards[0], a.cards[0]


def _board_moves(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The board-directed ``move`` events in an observation log — a man landing
    on a square (setup placements and steps) or being taken into a captured
    pile — in game order."""
    return [
        e
        for e in log
        if e[0] == "move" and str(e[3]).startswith(("square[", "captured["))
    ]


def test_moves_and_captures_are_public_identity_events() -> None:
    """Every board-directed ``move`` event carries full piece identity on BOTH
    sides (square, reserve and captured are all identity-projected), and the
    two observers' board-directed subsequences are EQUAL — steps and captures
    alike are common knowledge at the event level. Captures are asserted
    PRESENT, so the half of the claim this rung adds cannot go vacuous.

    red under (demonstrated out of band, reverted): flipping ``Cell``'s
    projection to ``count_only`` renders the square-destination view as an int
    count instead of the identity tuple, so the ``isinstance(dst_view, tuple)``
    assertion fails — the identity claim is not vacuous.
    """
    _, pause = _advance(PATH, 5, DEPTH)
    assert isinstance(pause, Pause)
    boards: dict[int, list[tuple[Any, ...]]] = {}
    for p in range(len(pause.obs_logs)):
        moves = _board_moves(pause.obs_logs[p])
        assert moves, f"P{p} logged no board-directed events"
        takes = [e for e in moves if str(e[3]).startswith("captured[")]
        assert takes, f"P{p} logged no capture events — the capture claim is vacuous here"
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
        "cardlang_breakthrough: the observers disagree on the board-directed "
        "events — movement is not common knowledge\n"
        f"only-in-P0={[e for e in boards[0] if e not in boards[1]]}\n"
        f"only-in-P1={[e for e in boards[1] if e not in boards[0]]}"
    )
    record(
        "cardlang_breakthrough",
        "movements",
        events=len(boards[0]),
        captures=len([e for e in boards[0] if str(e[3]).startswith("captured[")]),
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
    three seeds. The degeneracy is OVER-DETERMINED (fungible men +
    attribute-based setup + sorted identity rendering), not caused by the mere
    absence of shuffle.

    red under (demonstrated out of band, reverted): a bare ``shuffle box`` is a
    DEMONSTRATED no-op — three seeds stay byte-identical — because order never
    leaks and same-side men are fungible. The firing red-under is
    ``shuffle box`` PLUS a position-based deal (``move 16 pieces from box to
    reserve[0]`` in place of the ``where piece.side is light`` filter): the
    light/dark split becomes seed-dependent, mixed armies fill the home ranks,
    and the sorted identity views diverge at the very first pause.

    Honest caveat: the adapter's root chance node still samples the seed; every
    branch is provably identical (this proof), and collapsing that degenerate
    node is the stage-3 chance workstream (roadmap residual), not an info-set
    gap.
    """
    history, _ = _advance(PATH, 1, DEPTH)
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
                f"cardlang_breakthrough: seed {seed} renders differently from the "
                f"reference seed — the info state is seed-sensitive\n"
                f"witness (step {step}): {first_divergence(ref_cell, got_cell)}"
            )
    assert reference is not None
    record(
        "cardlang_breakthrough",
        "seed_degeneracy",
        seeds=3,
        steps=len(reference),
        over_determined=True,
    )
