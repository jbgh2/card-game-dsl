"""Known-value tests for Pinochle's meld scoring (`pinochle_meld`).

The kernel migration (docs/kernel-migration.md) leaves melding a pure Python
computation — `pinochle_meld_value`, a game-local stdlib primitive like Stud's
`pot_share` — since it is forced (a rational player melds everything), not a
choice. The playout invariants (conservation, per-trick winner correctness;
tests/test_playout_pinochle.py) cannot catch a misvalued combination, so these
pin the published point values directly (issue #83).
"""

from __future__ import annotations

from cardlang.runtime.pinochle import pinochle_meld
from cardlang.runtime.values import Card

_SUITS = ("clubs", "diamonds", "hearts", "spades")


def _cards(*rank_suit: tuple[str, str]) -> list[Card]:
    return [Card(rank, suit) for rank, suit in rank_suit]


def _around(rank: str, copies: int = 1) -> list[Card]:
    return _cards(*((rank, s) for s in _SUITS)) * copies


def test_empty_hand_scores_zero() -> None:
    assert pinochle_meld([], "spades") == 0


def test_single_trump_run_scores_150() -> None:
    run = _cards(("A", "spades"), ("10", "spades"), ("K", "spades"), ("Q", "spades"), ("J", "spades"))
    assert pinochle_meld(run, "spades") == 150


def test_double_trump_run_scores_1500_not_double_150() -> None:
    run = _cards(("A", "spades"), ("10", "spades"), ("K", "spades"), ("Q", "spades"), ("J", "spades"))
    assert pinochle_meld(run * 2, "spades") == 1500


def test_run_does_not_also_count_its_own_marriage() -> None:
    # The run's own K-Q is consumed by the run — no extra 40 on top of 150.
    run = _cards(("A", "spades"), ("10", "spades"), ("K", "spades"), ("Q", "spades"), ("J", "spades"))
    assert pinochle_meld(run, "spades") == 150


def test_a_second_marriage_beyond_the_run_still_counts() -> None:
    # One complete run plus a spare K-Q of trump (not part of any run): the
    # spare marriage is not subsumed, so it scores its own 40 on top of 150.
    run = _cards(("A", "spades"), ("10", "spades"), ("K", "spades"), ("Q", "spades"), ("J", "spades"))
    spare_marriage = _cards(("K", "spades"), ("Q", "spades"))
    assert pinochle_meld(run + spare_marriage, "spades") == 150 + 40


def test_trump_marriage_scores_40_plain_suit_marriage_scores_20() -> None:
    trump_marriage = _cards(("K", "spades"), ("Q", "spades"))
    plain_marriage = _cards(("K", "hearts"), ("Q", "hearts"))
    assert pinochle_meld(trump_marriage, "spades") == 40
    assert pinochle_meld(plain_marriage, "spades") == 20


def test_dix_scores_10_per_copy() -> None:
    assert pinochle_meld(_cards(("9", "spades")), "spades") == 10
    assert pinochle_meld(_cards(("9", "spades"), ("9", "spades")), "spades") == 20


def test_pinochle_scores_40_single_300_double() -> None:
    single = _cards(("Q", "spades"), ("J", "diamonds"))
    double = single * 2
    assert pinochle_meld(single, "clubs") == 40
    assert pinochle_meld(double, "clubs") == 300


def test_aces_around_scores_100_single_1000_double() -> None:
    assert pinochle_meld(_around("A"), "clubs") == 100
    assert pinochle_meld(_around("A", copies=2), "clubs") == 1000


def test_kings_around_scores_80_single_800_double() -> None:
    assert pinochle_meld(_around("K"), "clubs") == 80
    assert pinochle_meld(_around("K", copies=2), "clubs") == 800


def test_queens_around_scores_60_single_600_double() -> None:
    assert pinochle_meld(_around("Q"), "clubs") == 60
    assert pinochle_meld(_around("Q", copies=2), "clubs") == 600


def test_jacks_around_scores_40_single_400_double() -> None:
    assert pinochle_meld(_around("J"), "clubs") == 40
    assert pinochle_meld(_around("J", copies=2), "clubs") == 400
