"""Five-Card Stud — OpenSpiel readiness.

Hidden zone `hole`: Stud's hidden card lives in `hole` (its `upcards` are
public); everyone else in the corpus hides a `hand`.

This game reaches BOTH arms of the swap proof across one manifest, and the
reason is the game rather than the configuration: Stud's street opener is read
off the up cards, so whether the depth pause lands on the first decider varies
with the deal. Where it does, the harness swaps two opponents' hole cards;
where it does not, it swaps the one remaining observer's hole card against the
un-dealt stock.

`swap_axis="any"`: the recorded actions are betting vocabulary — none names a
card — so ANY hole swap replays legally. On the two-opponent arm that is not a
preference but the only workable setting: a one-card hole against a one-card
hole offers exactly ONE candidate pair, and two single cards share a suit under
a quarter of the time, so the harness's default same-suit filter would empty the
pool on most deals and trip its own `no swap pair available` guard. The stock
arm would survive the default, and would be proving a strictly narrower claim
than the game supports.

`depth=11` is DERIVED, not chosen, and
`test_the_depth_is_the_last_decision_of_the_first_hand` below re-runs the
derivation on every manifest seed so the number moves by reddening. Two things
bound it. The swapped pair is picked at the pause and applied at the FIRST
decision, so the depth must stay inside the same hand — every hand re-deals, and
a contested showdown empties `hole` into `upcards`, so a depth past either
boundary names cards that are not in those zones when the swap fires. Inside
that hand the deepest pause is the strongest: all four up cards are out, so the
hidden hole card is checked against a public board that is complete.

Bounded conformance walk: full `pyspiel.random_sim_test` re-simulates the whole
(seed, history) state after every action — O(n^2) in game length (issue #139) —
and a Five-Card Stud session runs until one player holds all 600 chips.

`conformance_steps=400` is MEASURED, and it is bought for more than the verb
claim. On the pinned `Random(7)` line every declared verb is applied by step 7
and the walk reaches TerminalNode at step 368 (measured 2026-09-06; a walk
budgeted 500 stops at the same 368). A bound sized to the verb claim alone would
sit near 7 and never see a terminal state. This is the only session-length poker
game in the corpus whose random line ends inside an affordable bound — its
greedy `legal[0]` line does not, on any manifest seed within 4000 steps
(measured), which is why `adapter_terminal_steps` stays unset and the terminal
returns have nowhere else to be checked. So the bound is set past the terminal
rather than past the last verb, and
`test_the_bound_reaches_the_terminal_state_it_is_bought_for` asserts it lands
there — without that assertion the extra steps would be a cost carrying a claim
that cannot fail.
"""

from __future__ import annotations

import pytest

from cardlang.openspiel.replay import DecisionNode

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, _advance, bounded_walk, manifest


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_five_card_stud",
        "five-card-stud.cardlang",
        hidden_zone="hole",
        depth=11,
        conformance_steps=400,
        swap_axis="any",
    )


def _first_hand(seed: int) -> list[int]:
    """Every depth of the greedy line still inside the first hand.

    The boundary is read off the deck rather than counted: within a hand the
    deck only shrinks, and `before_each` refills it, so the first depth whose
    deck is LARGER than the one before it is the first depth of the next deal.
    Reading it from the state keeps the walk independent of how many decisions
    a hand happens to take, which folding changes.
    """
    depths: list[int] = []
    previous = 53  # larger than any deck this game holds, so depth 0 always enters
    for depth in range(60):
        _, pause = _advance(TestReadiness.spec.path, seed, depth)
        if not isinstance(pause, DecisionNode):
            break
        deck = len(pause.rs.zones.single("deck").cards)
        if deck > previous:
            break
        previous = deck
        depths.append(depth)
    assert depths, f"seed {seed}: the first hand offered no decision"
    return depths


@pytest.mark.parametrize("seed", manifest())
def test_the_depth_is_the_last_decision_of_the_first_hand(seed: int) -> None:
    """The spec's depth is derived here, and both of its reasons run.

    The hand boundary is constraint one: the swap is applied at the first
    decision using cards read at the pause, so a pause in a later hand names
    cards that have since mucked and re-dealt. Constraint two is that the
    deepest such pause is the strongest — every up card is out, so the hidden
    hole card is checked against a complete public board.

    red under: set `depth` to any other value in the spec above.
    """
    depths = _first_hand(seed)
    assert TestReadiness.spec.depth == depths[-1], (
        f"seed {seed}: the first hand's last decision is at depth {depths[-1]}, "
        f"not the spec's {TestReadiness.spec.depth}"
    )
    _, pause = _advance(TestReadiness.spec.path, seed, TestReadiness.spec.depth)
    assert isinstance(pause, DecisionNode)
    holes = [len(pause.rs.zones.instance("hole", q).cards) for q in range(3)]
    assert min(holes) == 1, (
        f"seed {seed}: the pause at depth {TestReadiness.spec.depth} finds holes "
        f"{holes} — a seat with no hole card has nothing for the swap to move, "
        f"so the depth has crossed a showdown or a re-deal"
    )
    ups = [len(pause.rs.zones.instance("upcards", q).cards) for q in range(3)]
    assert max(ups) == 4, (
        f"seed {seed}: the deepest pause in hand one shows {ups} up cards, so "
        f"the swap is no longer checked against a complete public board"
    )


def test_the_bound_reaches_the_terminal_state_it_is_bought_for() -> None:
    """The half of `conformance_steps=400` the bounds grid cannot see.

    `test_conformance_bounds.py` asks only that the bound cover every declared
    verb, and this game's verbs are all applied by step 7 — so that grid stays
    green at any bound above single digits, including one stopping well short
    of the terminal state this bound is sized for. The bounded walk checks
    terminal returns only `if reached`, so a bound that quietly stopped reaching
    one would lose the check with nothing going red. This is that red.

    red under: lower `conformance_steps` below the terminal step recorded here.
    """
    spec = TestReadiness.spec
    assert spec.conformance_steps is not None
    walk = bounded_walk(spec.short_name, str(GAMES_DIR / spec.filename), spec.conformance_steps)
    assert walk.terminal, (
        f"the bounded walk no longer reaches TerminalNode within "
        f"conformance_steps={spec.conformance_steps} (it stopped at step "
        f"{walk.steps}) — this game's terminal returns are checked nowhere "
        f"else, so raise the bound rather than dropping the claim"
    )
    assert walk.steps < spec.conformance_steps, (
        f"the walk consumed its whole budget ({walk.steps} steps), so `terminal` "
        f"is true only because the last step happened to land there and the "
        f"bound carries no margin"
    )
