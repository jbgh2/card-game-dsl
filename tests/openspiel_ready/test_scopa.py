"""Scopa (2 players) — OpenSpiel readiness.

Depth 6: the harness's 2-player swap pairs the opponent's hand against the
un-dealt deck, which needs the pause to coincide with the first decider
(p == d0). Scopa's first decider is the non-dealer, seat 1, and depth 6 is the
deepest of the shallow depths at which every harness seed pauses on that seat
(probed over the manifest's seeds: seat 1 pauses at depths 0, 3 and 6 on all of
them, and the seeds diverge from 9 on). Six decisions in, both seats have
played and captured while the deck still holds most of the pack to swap
against.

`swap_axis` stays the default: Scopa has no follow rule and publishes card
identity only for cards that have left a hand — the played card, the layout,
the capture piles — so the replayed prefix carries no public observation of an
un-played card at all.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_scopa",
        "scopa.cardlang",
        depth=6,
    )
