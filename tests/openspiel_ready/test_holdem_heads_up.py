"""Heads-up fixed-limit Texas Hold'em — OpenSpiel readiness.

Hidden zone `hole`: the hidden cards live in `hole`; the community `board` is a
`Discard` (identity to all), so it is public by declaration and holds nothing to
perturb. Three-handed Hold'em added that split to the corpus; this game inherits
it at two players, where the swap proof runs its 2-player branch (the opponent's
hole cards against the undealt stock) rather than the multi-observer one.

`swap_axis="any"`: the recorded actions are betting vocabulary — none names a
card — so ANY hole swap replays legally. Two-card holes rarely share a suit, so
the harness's default same-suit filter would starve the pool.

`depth=7`. The 2-player swap branch pauses on the FIRST decider, so the depth
must land on a P0 decision; the greedy `legal[0]` line
(`call, check, check, check, check, check, check, check`) puts P0 at depths 0,
3, 5 and 7. 7 is the deepest and the strongest: all five community cards are
out, so the swap is checked with the public board COMPLETE — the configuration
the community-board games exist to exercise — and 39 cards still sit undealt in
the deck to pair the opponent's hole cards against.

Unlike three-handed Hold'em, the depth cannot fall out of the hand: this game is
ONE hand, so there is no later hand whose re-deal would leave the depth naming
cards no longer in those zones. That is the whole of what the single-hand shape
buys the harness here.

`adapter_terminal_steps=12`: the greedy line reaches TerminalNode in 8 steps on
every seed of the manifest (measured, not estimated — the line is
seed-independent because a check-heavy line never consults a card), so 12
carries a 4-step margin.

`conformance_steps` is deliberately UNSET, so this game plays a full
`pyspiel.random_sim_test`. Three-handed Hold'em must bound its walk because it
runs until one player holds all 300 chips (~60-110 hands) and the sim's
whole-state re-simulation after every action is O(n^2) in game length (issue
#139). One hand is at most 32 decisions, so the same sim is affordable here and
the game gets the stronger check rather than a budget with a coverage claim
attached. No `conformance_verbs_unreached` follows from that: the complement pin
is only meaningful with a bound.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_holdem_heads_up",
        "holdem-heads-up.cardlang",
        hidden_zone="hole",
        depth=7,
        swap_axis="any",
        adapter_terminal_steps=12,
    )
