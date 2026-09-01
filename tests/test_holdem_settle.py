"""Known-value tests for Hold'em side-pot distribution (`side_pot_payouts`).

The chip-conservation invariant in the playout can't catch a *misallocated*
side pot — the leftover sweep rebalances the total regardless. These tests pin
the exact per-player payouts for the side-pot cases, and — the part that is
Hold'em's and not Stud's — for the hand shapes a SHARED board creates: every
contender ranks against the same five community cards, so two players holding
nothing relevant can tie on the board alone, a case Stud's seven private-and-
upcard cards cannot produce.
"""

from __future__ import annotations

from cardlang.runtime.holdem import showdown_hands
from cardlang.runtime.poker import side_pot_payouts
from cardlang.runtime.values import Card

_SUIT = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}


def _cards(*specs: str) -> tuple[Card, ...]:
    """Cards as the binder delivers them: a plain tuple, not a live `Zone`
    (`side_pot_payouts` is values-in, so the fixture hands it the GameReads
    shape)."""
    return tuple(Card(s[:-1], _SUIT[s[-1]]) for s in specs)


# A board that helps nobody in particular: no pair, no flush, no straight.
_DRY_BOARD = _cards("2C", "7D", "9H", "JS", "4C")

_ACES = _cards("AD", "AH")        # + dry board -> pair of aces
_KINGS = _cards("KD", "KH")       # + dry board -> pair of kings
_DEUCE_TREY = _cards("2D", "3C")  # + dry board -> pair of twos (weakest here)


def _settle(
    in_hand: list[int],
    committed: dict[int, int],
    folded: dict[int, bool],
    private: dict[int, tuple[Card, ...]],
    board: tuple[Card, ...] = _DRY_BOARD,
) -> dict[int, int]:
    # Through Hold'em's own hand assembly, so this pins the composition the
    # runtime uses (hole + shown + the SHARED board) and not just the
    # family-wide layering. `shown` is empty here: the fixture puts each
    # contender's private cards in `hole`, which is where they sit for a lone
    # contender and, concatenated, is what makes the settlement insensitive to
    # the reveal move.
    hands = showdown_hands(in_hand, private, {p: () for p in in_hand}, board)
    return side_pot_payouts(in_hand, committed, folded, hands)


def test_short_all_in_wins_only_main_pot() -> None:
    # P0 all-in for 10 with the best hand; P1/P2 contest the 80-chip side pot.
    deltas = _settle(
        [0, 1, 2],
        committed={0: 10, 1: 50, 2: 50},
        folded={0: False, 1: False, 2: False},
        private={0: _ACES, 1: _KINGS, 2: _DEUCE_TREY},
    )
    # Main pot 10*3 = 30 -> P0 (aces). Side pot (50-10)*2 = 80 -> P1 (kings > twos).
    assert deltas == {0: 30, 1: 80, 2: 0}
    assert sum(deltas.values()) == 110  # whole pot distributed


def test_tie_splits_with_odd_chip_to_first_and_folded_contribution_counts() -> None:
    # P2 folded but contributed 1; P0 and P1 tie (identical hole ranks, same
    # board). Odd chip goes to the first winner in seat order.
    deltas = _settle(
        [0, 1, 2],
        committed={0: 5, 1: 5, 2: 1},
        folded={0: False, 1: False, 2: True},
        private={0: _cards("AD", "AH"), 1: _cards("AS", "AC"), 2: _DEUCE_TREY},
    )
    # Layer 1 (3 contributors): 3 chips, tie -> P0 gets 2 (incl. odd), P1 gets 1.
    # Layer 5 (P0,P1): 8 chips, tie -> 4 each. P0=6, P1=5, P2=0.
    assert deltas == {0: 6, 1: 5, 2: 0}
    assert sum(deltas.values()) == 11


def test_three_way_all_in_layers_each_side_pot_to_its_strongest_eligible() -> None:
    # Three all-ins at different amounts plus a caller — the case chip
    # conservation cannot catch (a misallocation across layers still sums right).
    deltas = _settle(
        [0, 1, 2, 3],
        committed={0: 10, 1: 50, 2: 100, 3: 100},
        folded={0: False, 1: False, 2: False, 3: False},
        private={
            0: _cards("2H", "2S"),   # + 2C on the board -> trip twos, best overall
            1: _ACES,                # pair of aces
            2: _KINGS,               # pair of kings
            3: _cards("3D", "5H"),   # nothing: jack high
        },
    )
    # Layer 10 (all four eligible): 10*4 = 40 -> P0 (trips, best overall, but
    #   eligible for this layer only — the short all-in).
    # Layer 50 (P1,P2,P3):          40*3 = 120 -> P1 (aces).
    # Layer 100 (P2,P3):            50*2 = 100 -> P2 (kings > jack high).
    assert deltas == {0: 40, 1: 120, 2: 100, 3: 0}
    assert sum(deltas.values()) == 260


def test_all_but_one_folded_takes_whole_pot() -> None:
    deltas = _settle(
        [0, 1],
        committed={0: 10, 1: 10},
        folded={0: False, 1: True},
        private={0: _DEUCE_TREY, 1: _ACES},  # P1 folded despite better cards
    )
    assert deltas == {0: 20, 1: 0}


# --- the shared board: hand shapes only a community game produces ------------


def test_playing_the_board_ties_and_splits() -> None:
    """Both contenders' best five ARE the five community cards, so neither hole
    card matters and the pot splits. Hold'em's own case: with a shared board a
    contender can reach the best available hand using NO private card, which is
    unreachable in Stud where every card in a ranking belongs to one player."""
    royal = _cards("AS", "KS", "QS", "JS", "10S")
    deltas = _settle(
        [0, 1],
        committed={0: 20, 1: 20},
        folded={0: False, 1: False},
        private={0: _cards("2D", "3C"), 1: _cards("4H", "5H")},
        board=royal,
    )
    assert deltas == {0: 20, 1: 20}  # 40-chip pot split evenly


def test_one_hole_card_plus_four_board_cards_wins() -> None:
    """The middle case of the three Hold'em hand shapes (two hole cards, one, or
    none): P0's single spade completes a royal flush out of four board cards,
    beating a pair of aces that uses both hole cards."""
    board = _cards("AS", "KS", "QS", "JS", "2D")
    deltas = _settle(
        [0, 1],
        committed={0: 20, 1: 20},
        folded={0: False, 1: False},
        private={0: _cards("10S", "3C"), 1: _cards("AD", "AH")},
        board=board,
    )
    assert deltas == {0: 40, 1: 0}
