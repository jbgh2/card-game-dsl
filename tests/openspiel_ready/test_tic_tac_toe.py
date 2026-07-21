"""Tic-tac-toe — OpenSpiel readiness (minimal; Task 10 completes this).

The board-topology walking skeleton, and the first PERFECT-INFORMATION
two-player game: every populated zone (the nine `Cell` squares, both
`PlayerPile` reserves) projects identity to both players, and the `Deck` box
empties at setup — so each information set is a singleton and there is no
hidden pair to swap.

Only ``test_indistinguishability_under_hidden_swap`` is overridden: its base
form needs an opponent hand paired against an un-dealt stock, and TTT has
neither (no `deck` zone, the `box` empties). The override proves the
degeneracy directly for BOTH observers — no populated zone sits below
identity, so the base proof's premise (a pair of worlds differing only in
hidden content) is unsatisfiable. Every other proof inherits: the
per-visible-fact matrix (the load-bearing one here — every zone x both
observers at identity, every content perturbation must move the state),
soundness on own view, seed/rng non-observability (no shuffle: `vacuous_stock`
and reseed-invariant), perfect recall, adapter agreement walked to Terminal
with the [+1,-1]/[0,0] returns compared, and pyspiel conformance.

Task 10 extends this with the two-observer dedicated tests (placement events
as public identity; seed degeneracy across the adapter's root chance).
"""

from __future__ import annotations

from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, _advance
from .partition import projection_for, record, zone_instances

PATH = str(GAMES_DIR / "tic-tac-toe.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_tic_tac_toe",
        "tic-tac-toe.cardlang",
        hidden_zone="reserve",  # unused: no zone actually hides content
        depth=4,
        swap_axis="any",  # no public card/rank observation to preserve
        adapter_terminal_steps=9,  # greedy line terminates by a full board
    )

    def test_indistinguishability_under_hidden_swap(self) -> None:
        """Perfect information, two observers: prove the DEGENERACY rather
        than vacuously skip. At a replayed pause, for EACH player no populated
        zone projects below identity, so no hidden pair exists for the base
        proof to swap — every information set is a singleton."""
        _, pause = _advance(PATH, 5, self.spec.depth)
        assert isinstance(pause, Pause)
        for p in range(len(pause.obs_logs)):
            hidden = sum(
                len(zone.cards)
                for name, key, zone in zone_instances(pause.rs)
                if zone.cards and projection_for(pause.rs, name, key, p) != "identity"
            )
            assert hidden == 0, (
                f"cardlang_tic_tac_toe: P{p} has {hidden} cards in non-identity "
                f"zones — the perfect-information premise is broken"
            )
        record(
            "cardlang_tic_tac_toe",
            "swap",
            degenerate="perfect information — no hidden pair exists for either observer",
            hidden_cards=0,
            observers=len(pause.obs_logs),
        )
