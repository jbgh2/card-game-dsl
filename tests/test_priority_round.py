"""The kernel's `priority` order value on the betting/auction round.

The auction form walks a *continuous ring* — `order[i % n]`, the pointer advancing
each turn. The `priority` order value instead re-scans the seat order from the
leader every turn and offers the first still-pending participant. So a seat that
stays pending is re-offered before later seats — the model Stud's betting uses
(and Coup's response windows will). This is a pre-designed value on the closed
order axis (turn-from-a-seat / priority / simultaneous), not a new axis.

The two orders are distinguished by a fixture where each seat must act twice:
priority drains seat 0 fully before seat 1 ([0,0,1,1,2,2]); the ring interleaves
([0,1,2,0,1,2]).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import play_game

# Each seat acts until its counter reaches 2; `step` is always the lone legal move.
SRC_PRIORITY = """
game G {
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck }
  state { acted_count[player] : Integer = 0 }
  phase run {
    round offering [step] from 0 over players where acted_count[player] < 2
          order priority
          until (number of players where acted_count[player] < 2) is 0
  }
  winner: highest acted_count
}
move_type step { effect { acted_count[actor] := acted_count[actor] + 1 } }
"""

SRC_RING = SRC_PRIORITY.replace("          order priority\n", "")


def _actor_sequence(src: str) -> list[int]:
    game = check_dsl(src, "order.cardlang")
    seq: list[int] = []

    def recording_chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        seq.append(player)
        return list(candidates[:count])

    play_game(game, random.Random(0), chooser=recording_chooser)
    return seq


def test_priority_order_drains_each_seat_before_advancing() -> None:
    assert _actor_sequence(SRC_PRIORITY) == [0, 0, 1, 1, 2, 2]


def test_continuous_ring_interleaves_the_seats() -> None:
    # The default (no `order` clause) is the continuous ring — the contrast.
    assert _actor_sequence(SRC_RING) == [0, 1, 2, 0, 1, 2]


# --- the corpus witness: poker's continuation order --------------------------
#
# The synthetic fixtures above separate the two traversals on a ring nobody
# re-opens. Poker re-opens one on every aggression, and that is where the order
# a corpus game actually gets is decided — so the witness drives a corpus game
# rather than a fixture, and its own source says nothing about the `order`
# clause. What it asserts is the property, not a spelling: after a seat bets,
# the seat BEHIND the aggressor decides before the checked seat in front of it.

HOLDEM = Path(__file__).parent.parent / "docs" / "games" / "holdem.cardlang"

# The line, one entry per decision. Three-handed Hold'em opens pre-flop with the
# blinds already posted, so the check-then-bet shape only arises on a street
# `open_street` has zeroed: the first three entries limp the pot to the flop, the
# next two are the flop's check and bet, and the decision AFTER them is the one
# under test.
LIMP_TO_THE_FLOP_THEN_CHECK_AND_BET = ("call", "call", "check", "check", "bet")


class _LineComplete(Exception):
    """Ends the playout once the decision after the flop bet has been offered.

    Hold'em plays until one seat holds every chip; nothing past this decision
    bears on the property, so the line stops rather than dealing out ~60 hands.
    """


def _seats_offered_along_the_line() -> list[int]:
    """The seats Hold'em offers along the scripted line, plus the one after it.

    The script is keyed by decision index, so it asserts at every step that the
    move it intends is on offer. A line that drifts — a street shape changed, a
    move's guard narrowed — then fails naming the decision it drifted at, rather
    than silently checking a different decision than the one it claims to.
    """
    game = check_source(HOLDEM)
    seats: list[int] = []

    def scripted(player: int, candidates: list[Any], count: int) -> list[Any]:
        seats.append(player)
        if len(seats) > len(LIMP_TO_THE_FLOP_THEN_CHECK_AND_BET):
            raise _LineComplete
        want = LIMP_TO_THE_FLOP_THEN_CHECK_AND_BET[len(seats) - 1]
        offered = [name for name, _ in candidates]
        assert want in offered, (
            f"decision {len(seats)} of the line wanted `{want}` and seat "
            f"{player} was offered {offered} — the line no longer reaches the "
            f"flop check-and-bet it is written to set up"
        )
        return [next(c for c in candidates if c[0] == want)]

    try:
        play_game(game, random.Random(0), chooser=scripted)
    except _LineComplete:
        pass
    return seats


def test_the_seat_behind_the_aggressor_decides_before_the_checked_seat() -> None:
    """After a bet re-opens a checked seat, the ring continues past the aggressor.

    The information-set property, and the only thing that can see it: the same
    seats commit the same chips under either traversal, so chip conservation,
    termination and the side-pot known-value tests are all blind to it. What
    differs is what the checked opener has WATCHED when it decides — under a
    re-scan from the leader it answers the bet without seeing the third seat's
    reply; under the ring it sees that reply first.
    """
    seats = _seats_offered_along_the_line()
    assert len(seats) == len(LIMP_TO_THE_FLOP_THEN_CHECK_AND_BET) + 1, (
        f"the line ended early at {seats} — the flop bet did not re-open the street"
    )
    entrants = set(seats[:3])
    assert len(entrants) == 3, f"the pre-flop street did not offer three seats: {seats}"
    opener, aggressor = seats[3], seats[4]
    (behind,) = entrants - {opener, aggressor}
    assert seats[5] == behind, (
        f"seat {opener} checked and seat {aggressor} bet; the next seat offered "
        f"was {seats[5]}, but poker continues round the ring from the aggressor, "
        f"so seat {behind} — which has not yet spoken this street — decides "
        f"first and seat {opener} answers knowing what it did"
    )
