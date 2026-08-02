"""Klondike — OpenSpiel readiness.

The corpus's first 1-player game. Hidden information here is CHANCE-hidden
(the shuffle), not opponent-hidden: the sole player's information set must
track exactly the exposed cards (flipped tableau cards, the waste, the
foundations) plus counts and their own observation history, and face-down
card identities must be non-observable until flipped.

Two shared proofs assume opponent hands and are overridden with their
1-player analogues (the per-game caveat convention — rationale lives here):

- ``test_indistinguishability_under_hidden_swap``: with no opponent, the
  swap pairs two zones hidden from the sole player — a face-down tableau
  stack against the undrawn stock. ``on_first_decision`` fires before the
  replayed prefix, and the greedy prefix (12 stock draws — `draw_stock`
  sorts first in the names block) exposes only the stock's first 12 cards,
  so the swap pool is read off the PAUSED deck (exactly the undrawn,
  still-hidden remainder). Byte-identical information states +
  legal-action agreement prove the chance-hidden partition.
- ``test_soundness_own_view_changes_the_state``: the base probe swaps
  between the player's hand and an opponent's; here the sole player's "own
  view" is the face-up layout, so the probe perturbs a visible cascade top
  against a hidden stock card and requires the state to CHANGE.

The rest inherit: the per-visible-fact matrix enumerates the position-
indexed families through the same `zone_observer_key` ownership column the
runtime uses (positions are unowned — every observer projects `others`);
the rng proof reverses the all-hidden stocks (deck + the seven
`tableau_down` stacks); adapter agreement walks the greedy line, which
cycles draw/redeal forever, so `adapter_terminal_steps` stays None (the
returns surface is exercised by the conformance sim, which reaches resign
under random action choice).

The dedicated tests below pin the game's own epistemic claims: the flip IS
a derived observation event (count from the hidden side, identity at the
open side), and at the first decision every face-down identity is absent
from the information state while every exposed card is present.
"""

from __future__ import annotations

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run

from .harness import (
    SWAP_PAIRS_PER_SEED,
    SWAP_SEEDS,
    GAMES_DIR,
    GameSpec,
    ReadinessProofs,
    _swap_fn,
    action_strings,
)
from .partition import first_divergence, record

PATH = str(GAMES_DIR / "klondike.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_klondike",
        "klondike.cardlang",
        hidden_zone="tableau_down",
        stock_zone="deck",
        depth=12,
        swap_axis="any",  # no public observation depends on hidden identities
        adapter_terminal_steps=None,  # greedy line cycles draw_stock/redeal forever
    )

    @pytest.mark.parametrize("seed", SWAP_SEEDS)
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        """1-player analogue of the base proof (which requires an opponent
        hand): swap a face-down tableau card with an undrawn stock card —
        both chance-hidden from the sole player throughout the replayed
        prefix — and require byte-identical information states and identical
        legal actions.

        Overriding the shared proof replaces its decorator too, so the
        manifest is re-applied here explicitly: the seeds and the pair cap are
        `harness`'s, not this module's, and a game whose analogue silently
        stayed at one seed while the manifest grew is exactly the reading the
        coverage record must not permit."""
        spec = self.spec
        history, pause_a = _advance_greedy(seed, spec.depth)
        p = pause_a.player
        assert p == 0  # the sole player

        down = pause_a.rs.zones.instance("tableau_down", 7).cards
        # The paused deck holds exactly the UNDRAWN stock — every card in it
        # stayed hidden through the whole replayed prefix (the drawn ones are
        # in the waste by now), and the same identities sit at the back of
        # the first-decision deck the swap actually mutates.
        stock = pause_a.rs.zones.single("deck").cards
        candidates = [(x, y) for x in down for y in stock if x != y]
        assert candidates, "no hidden swap pair available; adjust the depth"

        _, space = load(PATH)
        info_a = information_state(p, pause_a.rs, pause_a.obs_logs[p])
        proved: list[str] = []
        for x, y in candidates[:SWAP_PAIRS_PER_SEED]:
            pause_b = run(
                PATH,
                seed,
                tuple(history),
                on_first_decision=_swap_fn(("tableau_down", 7), ("deck", None), x, y),
            )
            assert isinstance(pause_b, Pause)
            info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
            assert info_a == info_b, (
                f"cardlang_klondike: swapping chance-hidden {x}<->{y} CHANGED the "
                f"player's information state — the info-set leaks.\n"
                f"witness: {first_divergence(info_a, info_b)}"
            )
            assert pause_b.player == p
            assert pause_b.legal == pause_a.legal, (
                "same information set, different legal actions — the offer leaks "
                "chance-hidden content"
            )
            # ...and the same offer must READ the same. Backstop; the wall is
            # `test_action_strings.py` (see `harness.action_strings`).
            assert action_strings(space, pause_b.legal) == action_strings(
                space, pause_a.legal
            ), (
                "same legal actions, different rendered text — the action strings "
                "the prompt shows are a leak channel"
            )
            proved.append(f"{x}<->{y}")
        record(
            spec.short_name,
            "swap",
            seed=seed,
            depth=len(history),
            axis="chance-hidden (tableau_down[7] <-> undrawn stock)",
            pairs=";".join(proved),
            pairs_proved=len(proved),
            pairs_cap=SWAP_PAIRS_PER_SEED,
            candidates=len(candidates),
            legal_agreement=True,
            string_agreement=True,
        )

    def test_soundness_own_view_changes_the_state(self) -> None:
        """1-player analogue: the sole player's own view is the face-up
        layout, so swapping a VISIBLE cascade top for a hidden stock card
        must change their information state."""
        r0 = run(PATH, 5, ())
        assert isinstance(r0, Pause)
        p = r0.player
        up = r0.rs.zones.instance("tableau_up", 1).cards
        stock = r0.rs.zones.single("deck").cards
        assert up and stock
        x, y = up[0], stock[-1]
        info_a = information_state(p, r0.rs, r0.obs_logs[p])
        r1 = run(
            PATH, 5, (), on_first_decision=_swap_fn(("tableau_up", 1), ("deck", None), x, y)
        )
        assert isinstance(r1, Pause)
        info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
        assert r1.player == p and info_a != info_b, (
            "cardlang_klondike: the info-state is insensitive to the exposed layout"
        )


def _advance_greedy(seed: int, depth: int) -> tuple[list[int], Pause]:
    history: list[int] = []
    r = run(PATH, seed, ())
    assert isinstance(r, Pause)
    while len(history) < depth:
        history.append(r.legal[0])
        nxt = run(PATH, seed, tuple(history))
        assert isinstance(nxt, Pause), "greedy Klondike line ended unexpectedly"
        r = nxt
    return history, r


def test_face_down_identities_are_non_observable_until_flipped() -> None:
    """At the first decision: every face-down card's identity (the 21 under
    the tableau plus the 24-card stock) is absent from the player's derived
    information state, and every exposed card (the seven setup flips) is
    present. This is the chance-hidden partition stated directly on the
    rendered state."""
    r = run(PATH, 5, ())
    assert isinstance(r, Pause)
    info = information_state(0, r.rs, r.obs_logs[0])

    hidden = list(r.rs.zones.single("deck").cards)
    for c in range(1, 8):
        hidden.extend(r.rs.zones.instance("tableau_down", c).cards)
    exposed = [r.rs.zones.instance("tableau_up", c).cards[0] for c in range(1, 8)]
    assert len(hidden) == 45 and len(exposed) == 7

    leaked = [str(c) for c in hidden if str(c) in info]
    assert not leaked, f"hidden card identities leak into the info state: {leaked}"
    missing = [str(c) for c in exposed if str(c) not in info]
    assert not missing, f"exposed cards absent from the info state: {missing}"


def test_the_flip_is_a_derived_observation_event() -> None:
    """The seven setup flips are ordinary kernel movements from a
    HiddenStack to a Cascade: each emits ('move', tableau_down[c], COUNT,
    tableau_up[c], IDENTITY) — the count side proves the source stayed
    projection-hidden, the identity side IS the reveal — and the flipped
    card's identity appears in no earlier event of the player's log."""
    r = run(PATH, 5, ())
    assert isinstance(r, Pause)
    log = r.obs_logs[0]
    flips = [
        (i, e)
        for i, e in enumerate(log)
        if e[0] == "move"
        and str(e[1]).startswith("tableau_down[")
        and str(e[3]).startswith("tableau_up[")
    ]
    assert len(flips) == 7, f"expected the seven setup flips, got {len(flips)}"
    for i, e in flips:
        assert e[2] == 1, f"flip source view must be the COUNT 1, got {e[2]!r}"
        assert isinstance(e[4], tuple) and len(e[4]) == 1, (
            f"flip destination view must be one card identity, got {e[4]!r}"
        )
        card = e[4][0]
        earlier = ";".join(repr(ev) for ev in log[:i])
        assert card not in earlier, (
            f"{card} was observable before its flip event"
        )


def test_stock_draws_reveal_identity_at_the_waste_only() -> None:
    """A stock draw's event carries a count at the deck side and the card's
    identity at the waste side — the deal-1 rule's epistemic content,
    derived from the two declared projections (Deck: count_only; Discard:
    identity)."""
    seed = 5
    history: list[int] = []
    r = run(PATH, seed, ())
    assert isinstance(r, Pause)
    for _ in range(3):
        history.append(r.legal[0])  # greedy = draw_stock
        nxt = run(PATH, seed, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
    draws = [
        e
        for e in r.obs_logs[0]
        if e[0] == "move" and e[1] == "deck" and e[3] == "waste"
    ]
    assert len(draws) == 3
    for e in draws:
        assert e[2] == 1, "deck side must be a bare count"
        assert isinstance(e[4], tuple) and len(e[4]) == 1, (
            "waste side must be the drawn card's identity"
        )
