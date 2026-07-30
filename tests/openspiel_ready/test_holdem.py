"""Texas Hold'em — OpenSpiel readiness.

Hidden zone `hole`: Hold'em's hidden cards live in `hole`; the community `board`
is a `Discard` (identity to all), so it is public by declaration and holds
nothing to perturb. That split is the point of the game for this harness — the
board is read by every contender's hand evaluation yet leaks nothing, because
its visibility is a property of its zone type rather than of any rule.

`swap_axis="any"`: Hold'em's recorded actions are betting vocabulary — none
names a card — so ANY hole swap replays legally. Its two-card holes rarely share
a suit, so the harness's default same-suit filter would starve the pool.

`depth=11` rather than the default 12, for two measured reasons at once.

The swap proof needs two observers who are neither the paused player nor the
first decider, which in a 3-player game means the depth pause must land on the
first decider itself; Hold'em's priority ring visits seats in a fixed cycle from
a fixed opener, so only every third depth qualifies (5, 8, 11, 14, ...). And the
swap is applied at the FIRST decision while its card pair is chosen at the depth
pause, so the depth must stay inside the SAME hand — Hold'em's `fold` mucks hole
cards and every hand re-deals, so a depth past the boundary names cards that are
not in those zones when the swap fires (depth 14 is hand 2: the board is back to
empty and all six hole cards are different).

11 is the deepest depth meeting both, and it is the strongest one available: all
five community cards are out, so the swap is checked with the public board
complete — the configuration this game was added to exercise.

Bounded conformance walk: full `pyspiel.random_sim_test` re-simulates the whole
(seed, history) state after every action — O(n^2) in game length (issue #139) —
and a Hold'em game runs until one player holds all 300 chips: ~60-110 hands.
Measured, the greedy line does not reach Terminal inside ten minutes through the
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

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_holdem",
        "holdem.cardlang",
        hidden_zone="hole",
        depth=11,
        conformance_steps=120,
        swap_axis="any",
        conformance_verbs_unreached=(
            (
                "<card>",
                ("STRUCTURAL, not a depth shortfall, on two legs. The encoding "
                 "reserves the card block for EVERY game unconditionally "
                 "(`ActionSpace.verbs` seeds its result with `CARD_VERB`), and "
                 "Hold'em offers nothing into it: its whole vocabulary is "
                 "check/bet/call/raise/fold, every one nullary, so no state can "
                 "ever make a card-valued decision. Measured unapplied at 60, "
                 "120 and 200 steps, where every betting verb is applied by "
                 "step 7. Issue #157 owns deriving the block away — Stud "
                 "reserves it for the same reason"),
            ),
        ),
    )
