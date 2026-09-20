"""Regression: a Stud hand nobody can bet in must still be dealt out and settled.

Two players each enter with exactly one chip (= the ante), so after antes every
entrant is all-in: the bring-in is a post of nothing and no street can be
contested. What this pins is the whole hand REACHING the showdown from there —
the deal, the burns, the reveal and the side-pot layering all running with the
betting collapsed — and the chips arriving whole at one seat.

It does not pin the game's two-entrant gate on the bring-in phase. Under
card-based membership (`bring_in_seat` reads the boards) that gate protects
nothing a played hand can reach: every entrant holds a door card, so the
selector is total, and the round's own `pending` filter empties the ring when
nobody can act. Neutralising the gate leaves this module green — measured
2026-09-20 — which is why the claim above is the one written down.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

FIXTURE = Path(__file__).parent / "fixtures" / "stud_allin.cardlang"
PARTIAL = Path(__file__).parent / "fixtures" / "stud_partial_bringin.cardlang"


def test_ante_all_in_hand_settles_without_crashing() -> None:
    game = check_source(FIXTURE)
    for seed in range(30):
        census: dict[str, Any] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed))  # must not raise
        # Two chips total, always; the game ends with one player holding them.
        assert sum(result.scores.values()) == 2, f"seed {seed}: {result.scores}"
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1 and result.winner == with_chips[0]


def test_partial_bring_in_settles_and_conserves_chips() -> None:
    # Every player starts with two chips, so after the ante the bringer holds one
    # and posts a partial bring-in (min(2, 1) = 1, all-in) — the branch the 100-chip
    # golden never reaches. The hand must settle, conserving the six chips.
    game = check_source(PARTIAL)
    for seed in range(30):
        result = play_game(game, random.Random(seed))  # must not raise
        assert sum(result.scores.values()) == 6, f"seed {seed}: {result.scores}"
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1 and result.winner == with_chips[0]


def test_a_short_bring_in_leaves_the_standing_bet_at_what_was_posted() -> None:
    """The street's standing bet is what the bringer actually put in.

    Chips and the winner cannot see this: a bring-in short of its nominal size
    still settles and still conserves, whatever the seats behind were asked to
    match. What moves is the OBLIGATION — a seat facing a one-chip post owes one,
    not the two a full bring-in would have named — so the assertion reads
    `bet_to_match` at the street's first decision rather than the result.

    red under: restore the nominal post at the call site, `bet_to_match := 2` in
    tests/fixtures/stud_partial_bringin.cardlang — RUN, not predicted: every
    seed then reports a standing bet of 2 over a posted 1.
    """
    game = check_source(PARTIAL)
    seen = 0

    for seed in range(30):
        held: dict[str, Any] = {}

        def capture(rs: Any) -> None:
            held["rs"] = rs

        def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
            nonlocal seen
            rs = held["rs"]

            def read(name: str) -> Any:
                for frame in reversed(rs.frames):
                    if name in frame:
                        return frame[name]
                raise AssertionError(f"{name} is in no live frame")

            bet_by, to_match = read("bet_by"), read("bet_to_match")
            posted = max(bet_by.values())
            # The bring-in street's first decision: exactly one seat has put
            # chips in, and that is the post, since nobody has acted yet.
            if sum(1 for v in bet_by.values() if v > 0) == 1 and posted > 0:
                if to_match == posted:
                    seen += 1
                assert to_match == posted, (
                    f"seed {seed}: the bringer posted {posted}, so the street's "
                    f"standing bet is {posted} — the game asked for {to_match}"
                )
            return [candidates[0]]

        play_game(game, random.Random(seed), chooser=chooser, on_first_decision=capture)

    assert seen > 0, "no seed reached a bring-in street with a post standing"
