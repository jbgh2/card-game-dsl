"""Differential validation: cardlang GOPS against OpenSpiel's NATIVE goofspiel.

The corpus's first external cross-implementation check. Our gops.cardlang is
configured to mirror `goofspiel(players=2,num_cards=13,points_order=random)`:
13 point cards, random prize order, and the native tie rule — a tied bid
DISCARDS the prize (goofspiel.h: "the point card is given to the highest
bidder or discarded if the bids are equal"). Pagat's *main* GOPS text instead
carries a tied prize over to the next round (the accumulating-prize rule) and
records the discard rule as a variant; the game file deliberately implements
the variant so this trajectory-level comparison is exact. That is a
configuration choice, not a divergence — any genuine rules disagreement this
test finds must FAIL the walk with its witness, never be papered over.

The pairing. Both implementations are walked side by side under a shared
uniform policy in the MAPPED action space:

- Bids: our action ids are card ids of the bidder's own suit; a card of rank
  r maps to the native bid id `value(r) - 1` (A=1 .. K=13, so A->0, K->12).
  At every decision the mapped legal-action sets must agree exactly, which
  makes "uniform over ours" identical to "uniform over native's".
- Chance: our prize order is realized by our seeded shuffle at setup;
  native's arrives one chance node per round. The native chance nodes are
  driven to FOLLOW our realized order: at each of our round-opening pauses,
  the exposed prize card maps to the native point-card outcome `value - 1`,
  which must be among native's legal chance outcomes — and the whole native
  outcome set must equal our remaining prize pool, mapped.
- Terminal: native is loaded with `returns_type=total_points`, so its returns
  ARE the per-player prize totals — compared exactly against our returns
  (our adapter returns raw `prize_points`, same scale), plus the win/draw
  classification derived from both.

Native fast-forwards the forced 13th round (goofspiel.cc auto-plays the last
turn without recording it in the tree), so after our 24th action native is
already terminal while we still hold two single-option decisions; the walk
plays them out and asserts they are exactly the cards/prize native forced.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.replay import Pause, Terminal, load, run  # noqa: E402
from cardlang.runtime.values import Card  # noqa: E402

PATH = str(Path(__file__).parent.parent / "docs" / "games" / "gops.cardlang")
NATIVE = "goofspiel(players=2,num_cards=13,points_order=random,returns_type=total_points)"

# Card value under GOPS (A low .. K high); native ids are value - 1.
VALUE = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
         "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}


def _to_native(card: Card) -> int:
    """The native goofspiel action/outcome id a card denotes (rank only:
    native has no suits — bid ids and point-card ids share the 0..12 space)."""
    return VALUE[card.rank] - 1


def walk_paired(seed: int) -> tuple[list[float], list[float]]:
    """Walk our game (seed-replayed) and a fresh native goofspiel state in
    lockstep under one uniform policy, asserting mapped legal-action and
    chance agreement at every node; returns (our_returns, native_returns).

    Reusable shape for a second differential consumer: the GOPS-specific
    parts are `_to_native` (the action/chance mapper) and the round
    structure (P0 then P1 per round, chance at each round opening)."""
    _, space = load(PATH)
    native = pyspiel.load_game(NATIVE).new_initial_state()
    policy = random.Random(10_000 + seed)

    history: list[int] = []
    ours = run(PATH, seed, ())
    pending_bids: dict[int, int] = {}  # our round's bids, as native ids
    played: dict[int, set[int]] = {0: set(), 1: set()}  # native bid ids used
    dealt: set[int] = set()  # native point-card ids dealt

    while isinstance(ours, Pause):
        p = ours.player
        if native.is_terminal():
            # Native auto-played the forced 13th round; our remaining
            # decisions must be exactly the cards native forced.
            assert len(history) >= 24, f"seed {seed}: native terminal too early"
            assert len(ours.legal) == 1, (
                f"seed {seed}: past native's end our decision is not forced"
            )
            forced = _to_native(space.decode(ours.legal[0]))
            assert {forced} == set(range(13)) - played[p], (
                f"seed {seed}: forced 13th-round bid {forced} for P{p} is not "
                f"the one unplayed card"
            )
            history.append(ours.legal[0])
            ours = run(PATH, seed, tuple(history))
            continue

        if p == 0:
            # A round opens on P0's bid; native must sit at the round's
            # chance node. Drive it to follow our realized prize order.
            assert native.is_chance_node(), (
                f"seed {seed} step {len(history)}: native not at a chance node "
                f"at our round opening"
            )
            prize_zone = ours.rs.zones.single("prize").cards
            assert len(prize_zone) == 1, f"seed {seed}: {len(prize_zone)} prizes on offer"
            outcome = _to_native(prize_zone[0])
            native_outcomes = sorted(a for a, _ in native.chance_outcomes())
            remaining = sorted(
                {_to_native(c) for c in ours.rs.zones.single("prize_deck").cards}
                | {outcome}
            )
            assert native_outcomes == remaining, (
                f"seed {seed}: native chance outcomes {native_outcomes} != our "
                f"remaining prize pool {remaining}"
            )
            native.apply_action(outcome)
            dealt.add(outcome)

        assert native.current_player() == pyspiel.PlayerId.SIMULTANEOUS
        mapped_legal = sorted(_to_native(space.decode(a)) for a in ours.legal)
        native_legal = sorted(native.legal_actions(p))
        assert mapped_legal == native_legal, (
            f"seed {seed} step {len(history)}: P{p} legal actions diverge — "
            f"ours(mapped)={mapped_legal} native={native_legal}"
        )

        action = policy.choice(ours.legal)
        pending_bids[p] = _to_native(space.decode(action))
        played[p].add(pending_bids[p])
        history.append(action)
        if p == 1:
            native.apply_actions([pending_bids[0], pending_bids[1]])
            pending_bids.clear()
        ours = run(PATH, seed, tuple(history))

    assert isinstance(ours, Terminal)
    assert native.is_terminal(), f"seed {seed}: we are terminal, native is not"
    assert len(dealt) == 12, (
        f"seed {seed}: {len(dealt)} native chance nodes driven (12 expected — "
        f"the 13th is native-forced)"
    )
    return ours.returns, list(native.returns())


def _classify(returns: list[float]) -> str:
    if returns[0] > returns[1]:
        return "p0"
    if returns[1] > returns[0]:
        return "p1"
    return "draw"


def test_paired_trajectories_agree_with_native_goofspiel() -> None:
    """30 paired trajectories: mapped legal actions agree at every decision
    node, native's chance nodes accept and follow our realized prize order,
    and the terminal point totals (and the win/draw classification) agree
    exactly."""
    outcomes = {"p0": 0, "p1": 0, "draw": 0}
    tied_games = 0
    for seed in range(30):
        ours, native = walk_paired(seed)
        assert ours == native, (
            f"seed {seed}: terminal totals diverge — ours {ours} != native {native}"
        )
        assert _classify(ours) == _classify(native)
        outcomes[_classify(ours)] += 1
        if sum(ours) < 91:
            tied_games += 1  # a shortfall from 91 is a discarded (tied) prize
    # The comparison saw real games, not one degenerate branch — and the tie
    # rule (the variant chosen to mirror native) was actually exercised.
    assert outcomes["p0"] > 0 and outcomes["p1"] > 0, outcomes
    assert tied_games > 0, "no tied round arose in 30 seeds — tie rule untested"
