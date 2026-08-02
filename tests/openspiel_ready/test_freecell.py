"""FreeCell — OpenSpiel readiness.

The perfect-information half of the positional-zone pair: one player, every
zone identity-visible, the deck empty after the deal. Its proof obligations
are deliberately near-trivial — that is the point (the positional design
collapses cleanly to the no-hidden-information case) — and two shared
proofs degenerate and are overridden with the honest degenerate statements
(the per-game caveat convention):

- ``test_indistinguishability_under_hidden_swap``: there is NO hidden card
  to swap — every populated zone projects identity to the sole player, so
  each information set is a singleton and the base proof's premise (a pair
  of worlds differing only in hidden content) is unsatisfiable. The
  override proves the degeneracy directly: no zone instance holds a card
  the player is not entitled to see, and every card's identity is present
  in the derived information state.
- ``test_soundness_own_view_changes_the_state``: the base probe needs an
  opponent hand; the override perturbs a visible cascade (everything is
  "own view" here) and requires the state to change.

The rest inherit. The per-visible-fact matrix is the load-bearing proof for
this game — every zone x the sole observer is identity-projected, so every
content perturbation must move the state. The rng proof records
``vacuous_stock=True`` (there is no all-hidden populated stock to reverse —
itself the perfect-information fact) while still pinning generator
non-observability. The greedy line resigns immediately (``resign`` is the
game's only bare-name action, so it takes the lowest non-card id), which
makes the adapter proof walk to Terminal and ASSERT the DSL and pyspiel
returns agree — the 1-player returns surface, proven end to end.
"""

from __future__ import annotations

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import ONE_SEED, GAMES_DIR, GameSpec, ReadinessProofs, _swap_fn
from .partition import first_divergence, projection_for, record, zone_instances

PATH = str(GAMES_DIR / "freecell.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_freecell",
        "freecell.cardlang",
        hidden_zone="cascade",  # unused: both hand-assuming proofs are overridden
        depth=6,  # the greedy line resigns at once; _advance backs off to the deal
        swap_axis="any",
        adapter_terminal_steps=4,  # greedy = resign: Terminal on the first action
    )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        """Perfect information: prove the DEGENERACY rather than vacuously
        skip. At the first decision, (a) no populated zone projects less than
        identity to the sole player, so there exists no hidden pair for the
        base proof to swap — every information set is a singleton; (b) every
        one of the 52 card identities appears in the derived information
        state. Legal-action agreement is trivial (a singleton set)."""
        r = run(PATH, seed, ())
        assert isinstance(r, Pause)
        p = r.player
        assert p == 0

        hidden_cards = 0
        for name, key, zone in zone_instances(r.rs):
            proj = projection_for(r.rs, name, key, p)
            if proj != "identity" and zone.cards:
                hidden_cards += len(zone.cards)
        assert hidden_cards == 0, (
            f"cardlang_freecell: {hidden_cards} cards sit in non-identity "
            f"zones — the perfect-information premise is broken"
        )

        info = information_state(p, r.rs, r.obs_logs[p])
        missing = [
            str(c)
            for _, _, zone in zone_instances(r.rs)
            for c in zone.cards
            if str(c) not in info
        ]
        assert not missing, f"cards absent from the info state: {missing}"
        record(
            "cardlang_freecell",
            "swap",
            degenerate="perfect information — no hidden pair exists",
            hidden_cards=0,
            cards_in_state=52,
        )

    def test_soundness_own_view_changes_the_state(self) -> None:
        """Everything is the sole player's own view: swapping two visible
        cascade cards must change the information state."""
        r0 = run(PATH, 5, ())
        assert isinstance(r0, Pause)
        p = r0.player
        c1 = r0.rs.zones.instance("cascade", 1).cards
        c2 = r0.rs.zones.instance("cascade", 2).cards
        assert c1 and c2
        x, y = c1[-1], c2[-1]
        info_a = information_state(p, r0.rs, r0.obs_logs[p])
        r1 = run(
            PATH, 5, (), on_first_decision=_swap_fn(("cascade", 1), ("cascade", 2), x, y)
        )
        assert isinstance(r1, Pause)
        info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
        assert r1.player == p and info_a != info_b, (
            "cardlang_freecell: the info-state is insensitive to the visible "
            f"layout\nwitness: {first_divergence(info_a, info_b)}"
        )


def test_deal_events_carry_full_identity() -> None:
    """The deal's observation events already carry every card's identity
    (Deck -> Cascade: the destination side is identity), so the sole
    player's knowledge is complete from the first event on — no visibility
    machinery is engaged at any point."""
    r = run(PATH, 5, ())
    assert isinstance(r, Pause)
    deals = [
        e
        for e in r.obs_logs[0]
        if e[0] == "move" and e[1] == "deck" and str(e[3]).startswith("cascade[")
    ]
    assert len(deals) == 8, f"expected eight column deals, got {len(deals)}"
    dealt = [c for e in deals for c in e[4]]
    assert len(dealt) == 52 and len(set(dealt)) == 52, (
        "the eight deal events must carry all 52 distinct identities"
    )
    for e in deals[:4]:
        assert len(e[4]) == 7
    for e in deals[4:]:
        assert len(e[4]) == 6
