"""`Seating.turn_order_from` honours the game's direction.

`direction: clockwise` advances by increasing seat index; `counterclockwise`
advances by decreasing index. The kernel `round` ring (trick and auction) walks
`turn_order_from`, so a counterclockwise game (French Tarot) must cycle seats in
the opposite order — otherwise its auction would seat the bids on the wrong
players. `offset_by left`/`right` stay absolute (+1 / -1) regardless.
"""

from __future__ import annotations

from cardlang.runtime.values import Seating


def test_turn_order_clockwise_is_increasing_index() -> None:
    s = Seating(4)  # clockwise by default
    assert s.turn_order_from(0) == [0, 1, 2, 3]
    assert s.turn_order_from(2) == [2, 3, 0, 1]


def test_turn_order_counterclockwise_is_decreasing_index() -> None:
    s = Seating(4, clockwise=False)
    assert s.turn_order_from(0) == [0, 3, 2, 1]
    assert s.turn_order_from(2) == [2, 1, 0, 3]


def test_offset_by_is_absolute_regardless_of_direction() -> None:
    # left/right are +1/-1 in both rings; only the turn-order walk flips.
    for s in (Seating(4), Seating(4, clockwise=False)):
        assert s.offset_by(0, "left") == 1
        assert s.offset_by(0, "right") == 3
