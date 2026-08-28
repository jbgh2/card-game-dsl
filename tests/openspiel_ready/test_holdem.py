"""Texas Hold'em — OpenSpiel readiness.

Hidden zone `hole`: Hold'em's hidden cards live in `hole`; the community `board`
is a `Discard` (identity to all), so it is public by declaration and holds
nothing to perturb. That split is the point of the game for this harness — the
board is read by every contender's hand evaluation yet leaks nothing, because
its visibility is a property of its zone type rather than of any rule.

`swap_axis="any"`: Hold'em's recorded actions are betting vocabulary — none
names a card — so ANY hole swap replays legally. Its two-card holes rarely share
a suit, so the harness's default same-suit filter would starve the pool.

The depth is not the harness default, and it is DERIVED rather than chosen:
`test_the_depth_is_the_deepest_pause_the_swap_geometry_admits` below re-runs the
derivation on every seed of the manifest, so a change to the greedy line moves
the number by reddening rather than by going quietly unstated.

Two constraints bound it. The swap proof needs two observers who are neither the
paused player nor the first decider, which in a 3-player game means the depth
pause must land on the first decider itself. And the swap is applied at the FIRST
decision while its card pair is chosen at the depth pause, so the depth must stay
inside the SAME hand — Hold'em's `fold` mucks hole cards and every hand re-deals,
so a depth past the boundary names cards that are not in those zones when the
swap fires. The deepest depth meeting both is what the spec carries.

Of the depths meeting both, the deepest is also the strongest: all five community
cards are out, so the swap is checked with the public board complete — the
configuration this game was added to exercise. That the two coincide is the
second thing the derivation test pins; they need not, and if a future line
separates them the test says so rather than silently preferring one.

Bounded conformance walk: full `pyspiel.random_sim_test` re-simulates the whole
(seed, history) state after every action — O(n^2) in game length (issue #139) —
and a Hold'em game runs until one player holds all 300 chips: ~60-110 hands.
Measured, the greedy line does not reach TerminalNode inside ten minutes through the
adapter, which is why `adapter_terminal_steps` stays unset.

`conformance_steps=120` is INHERITED from Stud's number, not derived: on the
pinned `Random(7)` line every betting verb is applied by step 7 (measured, and
unchanged at 60/120/200 steps), so 120 carries a 113-step margin over the
smallest bound that covers this line. A future reader should treat it as
"Stud's precedent, comfortably sufficient here" rather than as a measured
worst-case across rngs — the harness's own recipe (worst last-new-verb over
several rngs, plus margin) was not run, because the margin already dwarfs any
plausible spread.
"""

from __future__ import annotations

import pytest

from cardlang.openspiel.replay import DecisionNode

from .harness import GameSpec, ReadinessProofs, _advance, manifest


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_holdem",
        "holdem.cardlang",
        hidden_zone="hole",
        depth=11,
        conformance_steps=120,
        swap_axis="any",
    )


def _first_hand(seed: int) -> list[tuple[int, int, int]]:
    """`(depth, paused player, board size)` for every depth inside the first hand.

    The hand boundary is read off the board rather than counted: within a hand
    the community grows and never shrinks, so the first depth whose board is
    SMALLER than the one before it is the first depth of the next deal. Reading
    it from the state keeps the walk independent of how many decisions a hand
    happens to take on the greedy line.
    """
    rows: list[tuple[int, int, int]] = []
    previous = -1
    for depth in range(200):
        _, pause = _advance(TestReadiness.spec.path, seed, depth)
        assert isinstance(pause, DecisionNode)
        board = len(pause.rs.zones.single("board").cards)
        if board < previous:
            return rows
        rows.append((depth, pause.player, board))
        previous = board
    raise AssertionError("the first hand did not end within 200 decisions")


@pytest.mark.parametrize("seed", manifest())
def test_the_depth_is_the_deepest_pause_the_swap_geometry_admits(seed: int) -> None:
    """The spec's depth is derived here, not chosen — and both its reasons run.

    Constraint one is the swap proof's own geometry: with three players it needs
    two observers who are neither the paused player nor the first decider, which
    leaves the pause no choice but to land ON the first decider. Constraint two is
    the hand boundary — the swapped pair is picked at the pause and applied at the
    first decision, so a pause in a later hand names cards that have since mucked
    and re-dealt.

    red under: set `depth` to any other value in the spec above. Lowering it
    reddens the board-complete assert as well, which is the second thing worth
    knowing: the deepest admissible pause is also the one with the whole
    community out.
    """
    rows = _first_hand(seed)
    first_decider = rows[0][1]
    admissible = [depth for depth, player, _ in rows if player == first_decider]
    assert admissible, (
        f"seed {seed}: no depth in the first hand pauses on the first decider"
    )
    assert TestReadiness.spec.depth == max(admissible), (
        f"seed {seed}: the deepest pause the swap geometry admits inside hand one "
        f"is {max(admissible)} (of {admissible}), not the spec's "
        f"{TestReadiness.spec.depth}"
    )
    board_at = {depth: board for depth, _, board in rows}
    # The hand-boundary walk reads the board's growth, so a first hand that never
    # dealt one would make the comparison below `0 == 0` — true, and about
    # nothing. Asserting the community grew is what keeps the board-complete half
    # of this pin from going quietly vacuous if the greedy line stops reaching a
    # flop.
    assert max(board_at.values()) > 0, (
        f"seed {seed}: the first hand dealt no community card, so the walk's "
        f"boundary never triggered and the board comparison below is vacuous"
    )
    assert board_at[TestReadiness.spec.depth] == max(board_at.values()), (
        f"seed {seed}: the deepest admissible pause no longer has the whole "
        f"community out — board {board_at[TestReadiness.spec.depth]} of "
        f"{max(board_at.values())}"
    )
