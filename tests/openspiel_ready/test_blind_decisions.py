"""The swap proof's blind-decision comparison, held to reddening.

property:        The swap proof fails when a seat blind to both swapped cards
                 is offered different legal actions, or is asked in one world
                 and not the other, at any recorded pick before the pause or at
                 the pause itself, whether a phase gate, a rule, a chosen
                 movement's pool or a control branch read the hidden card.
domain:          Every recorded pick of the greedy line to the spec's depth
                 after the first Chooser call, whose candidates are computed
                 before the swap fires, for up to `SWAP_PAIRS_PER_SEED` pairs
                 taken in `spread_pairs` order. A seat is blind when neither
                 swap side projects card identity to it under the declared
                 projections at the pause (`harness.blind_seats`), so a swapped
                 card carried into a blind seat's sight by a movement nobody
                 chose fails the proof rather than dropping the pair. Every
                 witness game but `control_branch` reads a hidden card at a
                 position the wall on hidden reads covers (issue #281).
registry:        projections, `cardlang.stdlib.zones.ZONE_PROJECTIONS` through
                 `tests.openspiel_ready.partition.projection_for`; recorded
                 picks, `cardlang.openspiel.replay.RecordedPick`; the witness games,
                 `tests/fixtures/blind_decisions/`.
does not prove:  That a hidden read is caught once a seat that sees a swapped
                 card has diverged: a recorded pick world B does not offer to
                 such a seat drops the pair, and no later pick of it is
                 compared. Nor that a hidden read turning on one opponent card
                 is caught when no pair among the first `SWAP_PAIRS_PER_SEED`
                 flips it: the cap is load-bearing for that class, which every
                 rule witness below belongs to, and the seeds pinned here are
                 ones measured to redden. Nor that a blind seat other than the
                 paused one is TOLD the same thing before the pause: an earlier
                 pick is compared by its decider and its offer, and the
                 information state at the pause only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from cardlang.pipeline import check_source

from .harness import GameSpec, ReadinessProofs, spread_pairs

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "blind_decisions"

Axis = Literal["suit", "rank", "any"]


def _prove(fixture: str, depth: int, axis: Axis, seed: int) -> None:
    class Witness(ReadinessProofs):
        spec = GameSpec(
            f"witness_{fixture}",
            str(FIXTURES / f"{fixture}.cardlang"),
            depth=depth,
            swap_axis=axis,
        )

    Witness().test_indistinguishability_under_hidden_swap(seed)


# (fixture, depth, swap axis, seed, the failure the proof names). Each seed is
# one measured to redden at `SWAP_PAIRS_PER_SEED`.
WITNESSES: list[tuple[str, int, Axis, int, str]] = [
    ("gate_at_pause", 1, "suit", 3, "CHANGED P0's information state"),
    ("gate_in_prefix", 2, "suit", 3, "CHANGED P0's information state"),
    (
        "gate_reroutes",
        2,
        "suit",
        3,
        "same information, different offer at pick 1 for seat 0: world A asks seat 0 "
        "and world B asks seat 1",
    ),
    (
        "gate_reroutes",
        2,
        "suit",
        18,
        "same information, different offer at pick 1 for seat 0: world A asks seat 1 "
        "and world B asks seat 0",
    ),
    ("hidden_rule", 2, "suit", 3, "same information set, different legal actions"),
    (
        "hidden_rule_prefix",
        4,
        "suit",
        3,
        "same information, different offer at pick 2 for seat 0: only-in-A",
    ),
    (
        "blind_draw",
        2,
        "any",
        3,
        "same information, different offer at pick 1 for seat 0: only-in-A",
    ),
]


@pytest.mark.parametrize(
    ("fixture", "depth", "axis", "seed", "failure"),
    WITNESSES,
    ids=[f"{w[0]}-seed{w[3]}" for w in WITNESSES],
)
def test_a_hidden_read_reddens_the_swap_proof(
    fixture: str, depth: int, axis: Axis, seed: int, failure: str
) -> None:
    """red under: `harness.compare_blind_picks` skipping every pick -- the
    `gate_reroutes` rows and `hidden_rule_prefix` pass, and `blind_draw` fails
    at the pause instead. red under: `harness.spread_pairs` returning its
    input -- `gate_reroutes`, `hidden_rule` and `hidden_rule_prefix` at seed 3
    pass. red under: `compare_blind_picks` judging a pick blind by world A's
    decider alone -- `gate_reroutes` at seed 18 passes."""
    with pytest.raises(AssertionError, match=failure):
        _prove(fixture, depth, axis, seed)


@pytest.mark.parametrize(
    ("seed", "failure"),
    [
        (15, "only-in-A=\\[\\] only-in-B="),
        (3, "the recorded pick \\d+ is offered in world A and not in world B"),
    ],
    ids=["offer-differs", "recorded-pick-refused"],
)
def test_a_control_branch_on_a_hidden_card_reddens_the_swap_proof(
    seed: int, failure: str
) -> None:
    """An `if` on hand[1] picks which of two decisions seat 0 is asked; the
    two share phase, construct, count and destination and differ only in
    their `where`, so every asked observation agrees. At seed 15 world A takes
    the narrower branch, so the recorded pick is legal in both worlds and only
    the offer at pick 1 differs; at seed 3 world A takes the wider branch and
    its recorded pick is not offered in world B. The checker accepts the game:
    a control position is outside the wall on hidden reads (issue #755), so
    this is the proof's standing witness that its blind-pick comparison can
    fail, in both forms.

    red under: `harness.compare_blind_picks` skipping every pick -- the
    proof passes at both seeds, as a comparison at the pause alone does."""
    check_source(FIXTURES / "control_branch.cardlang")
    with pytest.raises(
        AssertionError,
        match="same information, different offer at pick 1 for seat 0: " + failure,
    ):
        _prove("control_branch", 2, "suit", seed)


def test_spread_pairs_reorders_and_keeps_every_pair() -> None:
    pairs = [(x, y) for x in "abc" for y in "pqrs"]
    spread = spread_pairs(pairs)
    assert sorted(spread) == sorted(pairs)
    assert [x for x, _ in spread[:3]] == ["a", "b", "c"]
    assert len({y for _, y in spread[:3]}) == 3
