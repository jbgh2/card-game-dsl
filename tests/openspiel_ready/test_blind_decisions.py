"""The swap proof's blind-decision comparison, held to reddening.

property:        The swap proof fails when a seat that has seen neither
                 swapped card is offered different legal actions, or is asked
                 in one world and not the other, at any recorded pick before
                 the pause or at the pause itself, and does not fail at a pick
                 whose decider has seen one; and a game reading a hidden card
                 where the checker refuses as a Hidden Read never reaches the
                 proof.
domain:          Every recorded pick of the greedy line to the spec's depth
                 after the first Chooser call, whose candidates are computed
                 before the swap fires, for up to `SWAP_PAIRS_PER_SEED` pairs
                 taken in `spread_pairs` order. A decider is blind at a pick
                 unless its Seat Views there, recorded inside the Chooser call,
                 name a swapped card a different number of times in the two
                 worlds (`harness.mentions`): every field of the view is read,
                 so a zone it sees at identity, a State Variable and every
                 observation event kind make it sighted alike, however the
                 card reached it (`seen_before_pick`), and a seat holding the
                 other copy of a two-deck card in both worlds stays blind. The
                 witnesses that reach the proof read the hidden card at a
                 control position, which the checker's Hidden Read Owner
                 Guard does not judge (issue #755): a phase gate, a rule or a
                 chosen movement's pool that reads it is refused by the
                 checker before any proof runs, and each such witness is
                 held to that refusal here instead.
registry:        what a seat knows, `cardlang.openspiel.infostate.SeatView`;
                 event kinds, `cardlang.runtime.observe.EVENT_PAYLOADS`;
                 recorded picks, `cardlang.openspiel.replay.RecordedPick`; the
                 witness games, `tests/fixtures/blind_decisions/`.
does not prove:  That a hidden read is caught once a seat that sees a swapped
                 card has diverged: a recorded pick world B does not offer to
                 such a seat drops the pair, and no later pick of it is
                 compared. Nor that a hidden read turning on one opponent card
                 is caught when no pair among the first `SWAP_PAIRS_PER_SEED`
                 flips it: the cap is load-bearing for that class, which
                 `control_high_card` belongs to, and the seeds pinned here are
                 ones measured to redden. Nor that a blind seat other than the
                 paused one is TOLD the same thing before the pause: an earlier
                 pick is compared by its decider and its offer, and the
                 information state at the pause only. Nor that the pause seat
                 may see a swapped card: a pair it has seen (a public `reveal`
                 of it) fails the comparison at the pause, since the sampler
                 draws its pairs as hidden from that seat and a card its view
                 names cannot be dropped without excusing a leak that names
                 it. Nor that learning a property of a swapped card without
                 its identity (a transfer count, a challenge verdict) makes a
                 seat sighted: the game's swap axis keeps such pairs apart.
                 Nor that a leak naming a swapped card in a seat's view is
                 caught at that seat's earlier picks: such a view reads as
                 sighted there, and the leak is the pause comparison's to
                 catch at the pause seat.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_source

from .harness import SWAP_SEEDS, GameSpec, ReadinessProofs, spread_pairs
from .partition import RECORDS

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
    (
        "control_reroutes",
        2,
        "suit",
        3,
        "same information, different offer at pick 1 for seat 0: world A asks seat 0 "
        "and world B asks seat 1",
    ),
    (
        "control_reroutes",
        2,
        "suit",
        18,
        "same information, different offer at pick 1 for seat 0: world A asks seat 1 "
        "and world B asks seat 0",
    ),
    (
        "control_high_card",
        2,
        "suit",
        5,
        "same information, different offer at pick 1 for seat 0: the recorded pick "
        "\\d+ is offered in world A and not in world B",
    ),
    (
        "control_high_card",
        2,
        "suit",
        9,
        "same information, different offer at pick 1 for seat 0: only-in-A=",
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
    """red under: `harness.spread_pairs` returning its input --
    `control_high_card` at seeds 5 and 9 passes. red under:
    `harness._blind_decider` judging seats that differ between the worlds by
    world A's decider alone -- `control_reroutes` at seed 18 passes."""
    check_source(FIXTURES / f"{fixture}.cardlang")
    with pytest.raises(AssertionError, match=failure):
        _prove(fixture, depth, axis, seed)


# fixture -> what the checker's refusal names: a Hidden Read never reaches the
# proof.
REFUSED: dict[str, str] = {
    "gate_at_pause": "phase `high`'s `when` gate is a fact every seat can check",
    "gate_in_prefix": "phase `high`'s `when` gate is a fact every seat can check",
    "gate_reroutes": "phase `high`'s `when` gate is a fact every seat can check",
    "hidden_rule": "rule `HiddenHigh`'s `applies_when:` is decided by the acting seat",
    "hidden_rule_prefix": "rule `HiddenHigh`'s `applies_when:` is decided by the acting seat",
    "blind_draw": "needs a pick by position, which the language does not have yet (issue #756)",
}


@pytest.mark.parametrize("fixture", sorted(REFUSED))
def test_a_hidden_read_is_refused_before_the_proof(fixture: str) -> None:
    """Each game reads seat 1's concealed hand where a decision turns on it,
    and the checker refuses it, naming the announcement or the pick the
    designer is missing."""
    with pytest.raises(DiagnosticError) as exc:
        check_source(FIXTURES / f"{fixture}.cardlang")
    assert exc.value.diagnostic.span is not None
    assert REFUSED[fixture] in exc.value.diagnostic.message
    assert "`hand[1]`" in exc.value.diagnostic.message


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
    a control position is one the Hidden Read Owner Guard does not judge
    (issue #755), so
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


def test_a_seat_that_has_seen_the_swapped_card_is_not_held_to_the_other_world() -> None:
    """Seat 2's hand passes through seat 0's hand and back, so seat 0's second
    offer turns on cards it has held; seat 1 has seen only their count and
    its pick before the pause is compared. The proof passes at every manifest
    seed, and compared a blind pick at each.

    red under: `harness.mentions` returning 0 -- seat 0's pick is
    held to the other world and the proof fails at seed 3, "same
    information, different offer at pick 1 for seat 0". red under:
    `harness.compare_blind_picks` skipping every pick -- no blind pick is
    compared."""
    check_source(FIXTURES / "seen_before_pick.cardlang")
    for seed in SWAP_SEEDS:
        before = len(RECORDS)
        _prove("seen_before_pick", 3, "suit", seed)
        (row,) = RECORDS[before:]
        assert row.detail["blind_picks_compared"] > 0, row
        del RECORDS[before:]


def test_spread_pairs_reorders_and_keeps_every_pair() -> None:
    pairs = [(x, y) for x in "abc" for y in "pqrs"]
    spread = spread_pairs(pairs)
    assert sorted(spread) == sorted(pairs)
    assert [x for x, _ in spread[:3]] == ["a", "b", "c"]
    assert len({y for _, y in spread[:3]}) == 3
