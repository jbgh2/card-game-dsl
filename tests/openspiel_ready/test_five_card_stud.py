"""Five-Card Stud — OpenSpiel readiness.

Hidden zone `hole`: Stud's hidden card lives in `hole` (its `upcards` are
public); everyone else in the corpus hides a `hand`.

`swap_axis="any"`: the recorded actions are betting vocabulary — none names a
card — so ANY hole swap replays legally. The reason is the vocabulary alone,
not a starved pool: a one-card hole and a deck still holding most of a suit
would feed the harness's default same-suit filter perfectly well. What the
default would test is a strictly narrower claim than the game supports.

Bounded conformance walk: full `pyspiel.random_sim_test` re-simulates the whole
(seed, history) state after every action — O(n^2) in game length (issue #139) —
and a Five-Card Stud session runs until one player holds all 600 chips.

`conformance_steps=400` is MEASURED, and it is bought for more than the verb
claim. On the pinned `Random(7)` line every declared verb is applied by step 7
and the walk reaches TerminalNode at step 368 (measured 2026-09-06; a walk at
500 stops at the same 368). A bound sized to the verb claim alone would sit near
7 and never see a terminal state. This game is the only session-length poker
game in the corpus whose random line ends inside an affordable bound — the
greedy `legal[0]` line does not, on any manifest seed within 4000 steps
(measured), which is why `adapter_terminal_steps` stays unset and the returns
surface has nowhere else to be checked. So the bound is set past the terminal
rather than past the last verb, and
`test_the_bound_reaches_the_terminal_state_it_is_bought_for` below asserts it
lands there — without that assertion the extra steps would be a cost with a
claim that cannot fail.
"""

from __future__ import annotations

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, bounded_walk


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_five_card_stud",
        "five-card-stud.cardlang",
        hidden_zone="hole",
        conformance_steps=400,
        swap_axis="any",
    )


def test_the_bound_reaches_the_terminal_state_it_is_bought_for() -> None:
    """The half of `conformance_steps=400` the bounds grid cannot see.

    `test_conformance_bounds.py` asks only that the bound cover every declared
    verb, and this game's verbs are all applied by step 7 — so that grid stays
    green at any bound above single digits, including one that stops short of
    the terminal state this one is sized for. The bounded walk checks terminal
    returns only `if reached`, so a bound that quietly stopped reaching one
    would lose the check with nothing going red. This is that red.

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
        f"the walk consumed its whole budget ({walk.steps} steps) — `terminal` "
        f"is true only because the last step happened to land there, and the "
        f"bound carries no margin"
    )
