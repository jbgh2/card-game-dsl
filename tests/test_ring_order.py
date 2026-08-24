"""The auction round's ring, and the one traversal its `order` clause names.

The auction form walks a *continuous ring* — `order[i % n]`, the pointer advancing
each turn — and `order ring` is the only value the axis holds, equal to writing no
clause at all. The clause survives its second value as the docking point a further
traversal arrives at; why it is kept, and what a further one owes, is
`docs/decisions.md`, "The auction form of `round`", under Order.

What is pinned here divides by who meets it. The ring's own stepping and poker's
continuation order are what a designer sees; the two refusals — a mode the axis
does not hold, and a ring that empties while `until` is still false — are what a
designer meets when the game description is wrong.
The clause's grid cells (parse, resolve, IR, execution, crossed against the
other optional clauses) live in tests/test_round_forms.py; this module holds
the behaviour that grid cannot state.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError

# Each seat acts until its counter reaches 2; `step` is always the lone legal
# move. Each seat needing TWO turns is what makes the trace discriminating: a
# traversal that drained a seat before advancing would read [0,0,1,1,2,2].
SRC_DEFAULT = """
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
{order}          until (number of players where acted_count[player] < 2) is 0
  }
  winner: highest acted_count
}
move_type step { effect { acted_count[actor] := acted_count[actor] + 1 } }
"""


def _source(order_clause: str = "") -> str:
    """The fixture, with the `order` clause written or left absent."""
    return SRC_DEFAULT.replace("{order}", order_clause)


def _actor_sequence(src: str) -> list[int]:
    game = check_dsl(src, "order.cardlang")
    seq: list[int] = []

    def recording_chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        seq.append(player)
        return list(candidates[:count])

    play_game(game, random.Random(0), chooser=recording_chooser)
    return seq


def test_continuous_ring_interleaves_the_seats() -> None:
    assert _actor_sequence(_source()) == [0, 1, 2, 0, 1, 2]


# The misuse probe: the grammar admits `order <NAME>`, so every wrong spelling a
# designer might reach for arrives at resolve, not at the parser. `priority` is
# the retired value and the one most likely to be typed — from an older game
# file, or from anywhere describing poker's betting.
#
# There is deliberately no companion pin that `order ring` and an absent clause
# play the same, though both are legal: nothing below resolve reads
# `order_mode`, so the two spellings are one code path and such a pin could not
# fail under any mutation of the traversal it claimed to watch. What the clause
# DOES prove is that it parses, resolves, emits and runs, and that is the round
# form grid's `order=ring` cells in tests/test_round_forms.py, whose ledger owns
# the record.
PROBE_SPELLINGS = ("priority", "simultaneous", "Ring", "rings")


def test_an_order_mode_the_axis_does_not_hold_is_refused() -> None:
    """Resolve names the legal set, so the message is the whole remedy.

    The expectation is derived from the registry rather than spelled: a value
    added to `ROUND_ORDER_MODES` changes what this test demands back, and the
    probe list is checked against the registry rather than filtered by it — a
    probe silently dropped because it became legal is the vacuously-green shape.
    The list's own non-emptiness is asserted for the same reason and not as
    ceremony: an emptied tuple satisfies the disjointness check and the loop
    alike, which is this repo's recorded empty-input-set defect wearing a
    probe's name.
    """
    assert PROBE_SPELLINGS, (
        "the probe list is empty, so this test exercises no refusal at all"
    )
    legal = set(n.ROUND_ORDER_MODES) & set(PROBE_SPELLINGS)
    assert not legal, (
        f"{sorted(legal)} is a legal order mode again, so it no longer probes "
        f"anything — choose a spelling the axis does not hold"
    )
    for spelling in PROBE_SPELLINGS:
        with pytest.raises(DiagnosticError) as excinfo:
            check_dsl(_source(f"          order {spelling}\n"), "order.cardlang")
        message = str(excinfo.value)
        assert f"round order '{spelling}' is unknown" in message, message
        assert str(sorted(n.ROUND_ORDER_MODES)) in message, message


EMPTY_RING = """
game G {
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck }
  state { acted_count[player] : Integer = 0 }
  phase run {
    round offering [step] from 0 over players where acted_count[player] < 0
          until false
  }
  winner: highest acted_count
}
move_type step { effect { acted_count[actor] := acted_count[actor] + 1 } }
"""


def test_an_empty_ring_with_until_unsatisfied_names_the_disagreement() -> None:
    """Nobody pending and `until` still false is a malformed game, said so.

    `until` is checked before every draw, so an empty ring is reached only when
    the termination predicate has just said the round goes on — two clauses
    contradicting each other, which is what the message must send the author to.
    The engine's step limit would also stop it, and that is the failure this
    guard exists to displace: a runaway-loop message for a game that is not
    looping but disagreeing with itself.

    red under: delete the `if not participants` raise from
    `AuctionForm.next_actor` — the round then spins to the 1000-step limit and
    reports a termination problem instead.
    """
    game = check_dsl(EMPTY_RING, "empty.cardlang")
    with pytest.raises(OwnerGuardError) as excinfo:
        play_game(game, random.Random(0))
    message = str(excinfo.value)
    assert "auction: no participant is pending" in message, message
    assert "termination and participants clauses disagree" in message, message
    assert "1000" not in message, message


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
