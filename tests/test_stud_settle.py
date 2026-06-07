"""Known-value tests for Stud side-pot distribution (`_settle`).

The chip-conservation invariant in the playout can't catch a *misallocated*
side pot — the leftover sweep rebalances the total regardless. These tests pin
the exact per-player payouts for the side-pot cases: a short all-in that can only
win the main pot, a tie with an odd chip, and a folded player's contribution
landing in a pot others win.
"""

from __future__ import annotations

from cardlang.runtime.state import Zone
from cardlang.runtime.stud import _settle
from cardlang.runtime.values import Card

_SUIT = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}


def _hand(*specs: str) -> Zone:
    return Zone([Card(s[:-1], _SUIT[s[-1]]) for s in specs])


# Distinct seven-card hands of known strength (each evaluated independently, so
# cards may repeat across players).
_STRAIGHT_FLUSH = _hand("AS", "KS", "QS", "JS", "10S", "2D", "3C")  # beats all
_QUADS = _hand("9C", "9D", "9H", "9S", "2C", "3D", "4H")
_HIGH_CARD = _hand("AD", "JH", "8C", "5S", "3D", "2H", "7C")


def _settle_deltas(
    in_hand: list[int],
    committed: dict[int, int],
    folded: dict[int, bool],
    hands: dict[int, Zone],
) -> dict[int, int]:
    stack = {p: 0 for p in in_hand}
    hole = {p: hands[p] for p in in_hand}
    upcards = {p: Zone() for p in in_hand}
    _settle(in_hand, committed, folded, stack, hole, upcards)
    return stack


def test_short_all_in_wins_only_main_pot() -> None:
    # P0 all-in for 10 with the best hand; P1/P2 contest the 80-chip side pot.
    deltas = _settle_deltas(
        [0, 1, 2],
        committed={0: 10, 1: 50, 2: 50},
        folded={0: False, 1: False, 2: False},
        hands={0: _STRAIGHT_FLUSH, 1: _QUADS, 2: _HIGH_CARD},
    )
    # Main pot 10*3 = 30 -> P0 (best). Side pot (50-10)*2 = 80 -> P1 (> P2).
    assert deltas == {0: 30, 1: 80, 2: 0}
    assert sum(deltas.values()) == 110  # whole pot distributed


def test_tie_splits_with_odd_chip_to_first_and_folded_contribution_counts() -> None:
    # P2 folded but contributed 1; P0 and P1 tie. Odd chip goes to the first
    # winner (lowest index in in_hand order).
    deltas = _settle_deltas(
        [0, 1, 2],
        committed={0: 5, 1: 5, 2: 1},
        folded={0: False, 1: False, 2: True},
        hands={0: _QUADS, 1: _QUADS, 2: _HIGH_CARD},
    )
    # Layer 1 (3 contributors): 3 chips, tie -> P0 gets 2 (incl. odd), P1 gets 1.
    # Layer 5 (P0,P1): 8 chips, tie -> 4 each. P0=6, P1=5, P2=0.
    assert deltas == {0: 6, 1: 5, 2: 0}
    assert sum(deltas.values()) == 11


def test_all_but_one_folded_takes_whole_pot() -> None:
    deltas = _settle_deltas(
        [0, 1],
        committed={0: 10, 1: 10},
        folded={0: False, 1: True},
        hands={0: _HIGH_CARD, 1: _STRAIGHT_FLUSH},  # P1 folded despite better cards
    )
    assert deltas == {0: 20, 1: 0}
