"""Hex — OpenSpiel readiness (two-observer PERFECT information).

The board-topology connection rung. Tic-tac-toe proved the perfect-information
shape for placement on a grid; this module proves it for placement on a
declared-adjacency board whose win is a position-wide question, for BOTH
observers: every information set is a singleton, nothing an observer is
entitled to see is dropped, and nothing hidden leaks (there is nothing hidden).

What is proven here
-------------------
- Two-observer degeneracy (``test_indistinguishability_under_hidden_swap``):
  at a replayed mid-game pause, for EACH player no populated zone projects
  below identity (``hidden_cards == 0``) and all 121 stones sit in
  identity-projected zones (``visible == 121``); every populated zone renders
  under its own label with its occupant, so the observer sees WHERE each stone
  is, not merely that stones exist; and both observers render the identical
  board. That last equality holds by construction once every zone is at
  identity, so it guards the premise rather than adding to it. The base
  proof's premise — a pair of worlds differing only in hidden content — is
  therefore unsatisfiable, so it is proven degenerate rather than skipped.
- Soundness on own view (``test_soundness_own_view_changes_the_state``):
  everything is "own view" here, so the override swaps a placed stone against
  a reserve stone of the OTHER side (distinct renderings) and requires BOTH
  observers' information states to move.
- The per-visible-fact matrix (inherited, the load-bearing proof for a
  perfect-information game): every zone x BOTH observers is identity-projected,
  so every content perturbation must move the state and none may be over-hidden.
- Event-level publicity (``test_placements_are_public_identity_events``): every
  board-directed ``move`` event carries full piece identity on both sides, and
  the two observers' board-directed subsequences are equal — placements are
  common knowledge at the event level.
- Chance-freeness: nothing in the game draws, so the adapter gives it a tree
  with no root chance node and its generator refuses every draw
  (``cardlang.runtime.chance``). The property is proven over the corpus
  registry in ``tests/test_chance_free.py`` rather than restated per game here.

The singleton-partition argument (the "bulletproof" claim)
----------------------------------------------------------
Every populated zone projects identity to each observer, so the facts matrix's
"identity content shows through" direction gives: equal information state
implies equal visible content. With ``hidden_cards == 0`` there is no hidden
content to vary, so equal visible content forces equal state — the map
(world state -> information state) is injective, i.e. every information set is a
singleton. The stones are FUNGIBLE (all 61 black stones render alike, all 60
white alike), so two arrangements differing only by permuting same-side stones
are the SAME position: the partition is a singleton over DISTINCT positions,
not over piece labellings. Legal-action agreement is definitionally trivial in
a singleton partition (one world agrees with itself); it is cross-checked
NON-vacuously by the inherited adapter proof, whose per-step
``state.legal_actions() == r.legal`` compares against an independent pyspiel
run.

Inherited unchanged
-------------------
pyspiel conformance (the full ``random_sim_test``: one whole random game
through the adapter); the per-visible-fact matrix; seed/rng
non-observability (``vacuous_stock`` — no all-hidden populated stock exists,
itself the perfect-information fact); perfect recall; adapter agreement walked
to TerminalNode with the ``[+1, -1]`` returns compared (the greedy ``legal[0]``
line places in the first empty cell in board order on both sides and wins for
black in 111 placements, the line the native oracle's lowest id takes too;
measured 2026-11-01).

Honest caveats
--------------
- "Every zone identity to all" is precisely "every POPULATED zone": ``box`` is a
  ``Deck`` (count_only), but it is emptied at setup and thereafter renders
  ``box=#0`` identically for both observers, hiding nothing.
- Seed insensitivity here is OVER-DETERMINED, and no single cause carries it:
  the game draws nothing at all, AND fungible stones + attribute-based setup +
  sorted identity rendering would hide a permutation even if it did. A bare
  ``shuffle box`` added to this game is a no-op for the rendered views though
  it is not a no-op for the classification — it makes the game chance-bearing
  and restores its root chance node.
"""

from __future__ import annotations

from typing import Any

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode

from .harness import ONE_SEED, GAMES_DIR, GameSpec, ReadinessProofs, _advance
from .partition import (
    first_divergence,
    projection_for,
    record,
    unshown_occupants,
    zone_instances,
)

PATH = str(GAMES_DIR / "hex.cardlang")

TOTAL_STONES = 121  # 61 black + 60 white; all live in identity-projected zones


def _zone_render(info: str) -> str:
    """The zone-projection portion of an information state (between the
    ``P<n>|`` prefix and ``|state:``) — identical between observers exactly
    when every zone projects identity to both."""
    return info.split("|", 1)[1].split("|state:", 1)[0]


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_hex",
        "hex.cardlang",
        hidden_zone="reserve",  # unused: no zone hides content, both hand-assuming proofs overridden
        depth=12,
        swap_axis="any",  # no public card/rank observation to preserve
        # The board's bound: every line ends by its rules within 121
        # placements. The greedy legal[0] line wins in 111 (measured 2026-11-01).
        adapter_terminal_steps=121,
    )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        """Perfect information, two observers: prove the DEGENERACY directly
        rather than vacuously skip. At a replayed pause, for EACH player: no
        populated zone projects below identity (so no hidden pair exists for the
        base proof to swap), all 121 stones sit in identity-projected zones, and
        every populated zone renders under its own label with its occupant.
        Both observers render the identical board, which holds by construction
        once every zone projects identity to both.

        red under: `reserve[player] : Hand<player>` in hex.cardlang ("P0 has 54
        cards in non-identity zones"); `_zone_line` rendering an identity zone
        as `f"{label}=#{len(view)}"` (the occupant check names every populated
        zone)."""
        _, pause = _advance(PATH, seed, self.spec.depth)
        assert isinstance(pause, DecisionNode)
        renders: list[str] = []
        for p in range(len(pause.obs_logs)):
            visible = 0
            hidden = 0
            for name, key, zone in zone_instances(pause.rs):
                if not zone.cards:
                    continue
                if projection_for(pause.rs, name, key, p) == "identity":
                    visible += len(zone.cards)
                else:
                    hidden += len(zone.cards)
            assert hidden == 0, (
                f"cardlang_hex: P{p} has {hidden} cards in non-identity "
                f"zones — the perfect-information premise is broken"
            )
            assert visible == TOTAL_STONES, (
                f"cardlang_hex: P{p} sees {visible} of {TOTAL_STONES} stones "
                f"in identity zones — a stone is over-hidden"
            )
            info = information_state(p, pause.rs, pause.obs_logs[p])
            missing = unshown_occupants(pause.rs, info)
            assert not missing, (
                f"cardlang_hex: P{p}'s info state does not show the stones "
                f"on {missing}"
            )
            renders.append(_zone_render(info))
        assert renders[0] == renders[1], (
            "cardlang_hex: the two observers render different boards — "
            f"perfect information is broken\nwitness: {first_divergence(renders[0], renders[1])}"
        )
        record(
            "cardlang_hex",
            "swap",
            degenerate="perfect information — no hidden pair exists for either observer",
            hidden_cards=0,
            visible_stones=TOTAL_STONES,
            observers=len(pause.obs_logs),
            legal_agreement="trivial (singleton); adapter proof cross-checks vs pyspiel re-sim",
        )

    @pytest.mark.parametrize("seed", ONE_SEED)
    def test_soundness_own_view_changes_the_state(self, seed: int) -> None:
        """Everything is own view under perfect information. Swap a placed stone
        against a reserve stone of the OTHER side (guaranteed distinct
        renderings, black vs white) at a mid-game pause; BOTH observers' information
        states must move, since every zone is identity-projected to both.

        red under: `_zone_line` rendering an identity zone as
        `f"{label}=#{len(view)}"` ("P0's info state is insensitive to a visible
        stone:black<->stone:white swap")."""
        _, pause = _advance(PATH, seed, self.spec.depth)
        assert isinstance(pause, DecisionNode)
        tile = next(
            (z for name, _, z in zone_instances(pause.rs) if name == "tile" and z.cards),
            None,
        )
        assert tile is not None and len(tile.cards) == 1
        placed = tile.cards[0]
        other = pause.rs.zones.instance("reserve", 1 if placed.suit == "black" else 0)
        assert other.cards, "the other side's reserve is empty at this pause"
        mate = other.cards[0]
        assert placed != mate, "placed stone and its swap mate must be distinct sides"

        before = {
            q: information_state(q, pause.rs, pause.obs_logs[q])
            for q in range(len(pause.obs_logs))
        }
        tile.cards[0], other.cards[0] = mate, placed
        try:
            for q in range(len(pause.obs_logs)):
                after = information_state(q, pause.rs, pause.obs_logs[q])
                assert after != before[q], (
                    f"cardlang_hex: P{q}'s info state is insensitive to a "
                    f"visible {placed}<->{mate} swap (tile <-> other reserve)"
                )
        finally:
            tile.cards[0], other.cards[0] = placed, mate


def _board_moves(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The board-directed ``move`` events in an observation log (destination a
    tile) — the placements, in game order."""
    return [e for e in log if e[0] == "move" and str(e[3]).startswith("tile[")]


def test_placements_are_public_identity_events() -> None:
    """Every board-directed ``move`` event carries full piece identity on BOTH
    sides (reserve source and tile destination are both identity-projected),
    and the two observers' board-directed subsequences are EQUAL — placements
    are common knowledge at the event level.

    red under: ``dst_view = len(cards)`` in ``observe.movement`` renders the
    tile-destination view as a count
    (``('move', 'reserve[0]', ('stone:black',), 'tile[a1]', 1)``) instead of
    the identity tuple, so the ``isinstance(dst_view, tuple)`` assertion fails.
    Flipping ``Cell``'s projection to ``count_only`` does not reach this pin:
    the checker's Hidden Read Owner Guard then refuses Breakthrough's
    ``when:``, which reads a square's top piece, and the corpus registry this
    module imports fails first.
    """
    _, pause = _advance(PATH, 5, 4)
    assert isinstance(pause, DecisionNode)
    boards: dict[int, list[tuple[Any, ...]]] = {}
    for p in range(len(pause.obs_logs)):
        moves = _board_moves(pause.obs_logs[p])
        assert moves, f"P{p} logged no board-directed placement events"
        for e in moves:
            src_view, dst_view = e[2], e[4]
            assert isinstance(dst_view, tuple) and dst_view and all(
                isinstance(c, str) for c in dst_view
            ), f"placement {e!r}: destination is not a full-identity view"
            assert isinstance(src_view, tuple) and src_view and all(
                isinstance(c, str) for c in src_view
            ), f"placement {e!r}: source is not a full-identity view"
        boards[p] = moves
    assert boards[0] == boards[1], (
        "cardlang_hex: the observers disagree on the board-directed "
        "events — placements are not common knowledge\n"
        f"only-in-P0={[e for e in boards[0] if e not in boards[1]]}\n"
        f"only-in-P1={[e for e in boards[1] if e not in boards[0]]}"
    )
    record(
        "cardlang_hex",
        "placements",
        placements=len(boards[0]),
        common_knowledge=True,
    )
