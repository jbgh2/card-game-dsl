"""Seven-Card Stud: poker-evaluator unit tests plus a random playout.

The strongest falsifiable checks for a betting game: the poker hand evaluator
against known orderings/tiebreakers, and chip conservation (total chips never
change — the test of the betting and side-pot logic). The playout also checks
card conservation and that the game terminates with one player holding all the
chips.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.poker import hand_rank
from cardlang.runtime.values import Card

STUD = Path(__file__).parent.parent / "docs" / "games" / "seven-card-stud.cardlang"


def _h(*specs: str) -> list[Card]:
    suit = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}
    return [Card(s[:-1], suit[s[-1]]) for s in specs]


def test_hand_evaluator_category_order() -> None:
    sf = hand_rank(_h("AS", "KS", "QS", "JS", "10S", "2D", "3C"))  # royal flush
    quads = hand_rank(_h("9S", "9D", "9H", "9C", "KS", "2D", "3C"))
    boat = hand_rank(_h("9S", "9D", "9H", "KC", "KS", "2D", "3C"))
    flush = hand_rank(_h("AS", "JS", "8S", "5S", "2S", "KD", "3C"))
    straight = hand_rank(_h("9S", "8D", "7H", "6C", "5S", "KD", "2C"))
    trips = hand_rank(_h("9S", "9D", "9H", "KC", "5S", "2D", "3C"))
    two_pair = hand_rank(_h("9S", "9D", "KH", "KC", "5S", "2D", "3C"))
    pair = hand_rank(_h("9S", "9D", "KH", "QC", "5S", "2D", "3C"))
    high = hand_rank(_h("AS", "JD", "9H", "7C", "5S", "3D", "2C"))
    ordered = [high, pair, two_pair, trips, straight, flush, boat, quads, sf]
    assert ordered == sorted(ordered)  # strictly increasing strength

    # The wheel A-2-3-4-5 is a straight (the five-high).
    wheel = hand_rank(_h("AS", "2D", "3H", "4C", "5S", "KD", "QC"))
    assert wheel[0] == 4 and wheel[1] == 5
    # Tiebreak: higher kicker wins within a category.
    assert hand_rank(_h("AS", "AD", "KH", "5C", "3S", "2D", "7C")) > hand_rank(
        _h("AS", "AD", "QH", "5C", "3S", "2D", "7C")
    )


def test_15_random_games_satisfy_invariants() -> None:
    game = check_source(STUD)
    start = time.monotonic()
    for seed in range(15):
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Chip conservation: 4 players × 100 starting chips, always.
        assert sum(result.scores.values()) == 400, f"seed {seed}: {result.scores}"
        # Terminates with one player holding chips, who wins holding them all.
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1, f"seed {seed}: {result.scores}"
        assert result.winners == frozenset(with_chips)
        assert result.scores[with_chips[0]] == 400
        # Card conservation.
        assert census["total"] == 52, f"seed {seed}: {census}"
    assert time.monotonic() - start < 60  # stays comfortably fast


class _Asked(Exception):
    """Stops a hand once the decision under test has been offered."""


def test_the_bring_in_poster_called_around_is_not_asked_again() -> None:
    """Pagat: "If the opener just places the minimum bring-in, subsequent
    players have the option to complete the bet to a small bet ($5), to call
    the bring-in ($2) or to fold. Only if someone completes the bet are later
    players allowed to raise."

    The poster decides once. It stands on the bring-in, every seat behind it
    calls, and the next decision is the 4th street's opener facing no bet —
    the poster is not asked again on 3rd street, because nobody completed.
    Swept over seeds because which seat brings in is a fact about the deal.
    The twin (`docs/games/seven-card-stud.md`) states the same rule.

    red under: drop `acted[actor] := true` from `check` in
    `docs/libraries/poker_betting.cardlang` — standing on the minimum then
    leaves the poster pending, and the ring asks it again over its own post.
    """
    game = check_source(STUD)
    seats = 4
    for seed in range(20):
        held: dict[str, Any] = {}
        rows: list[tuple[int, frozenset[str], int]] = []

        def capture(rs: Any) -> None:
            held["rs"] = rs  # noqa: B023 -- consumed before the loop advances

        def read(name: str) -> Any:
            for frame in reversed(held["rs"].frames):  # noqa: B023
                if name in frame:
                    return frame[name]
            raise AssertionError(f"{name} is in no live frame")

        def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
            offered = frozenset(name for name, _ in candidates)
            rows.append((player, offered, read("bet_to_match")))  # noqa: B023
            if len(rows) > seats:  # noqa: B023
                raise _Asked
            want = "check" if len(rows) == 1 else "call"  # noqa: B023
            return [c for c in candidates if c[0] == want]

        try:
            play_game(game, random.Random(seed), chooser=chooser, on_first_decision=capture)
        except _Asked:
            pass

        poster, offered, standing = rows[0]
        assert offered == {"check", "raise"} and standing == 2, (
            f"seed {seed}: the street's first decision is seat {poster} facing "
            f"{standing}, offered {sorted(offered)} — not the bring-in poster's "
            f"stand-or-complete choice"
        )
        callers = [player for player, _, _ in rows[1:seats]]
        assert poster not in callers and len(set(callers)) == seats - 1, (
            f"seed {seed}: 3rd street asks {[poster, *callers]} — the poster "
            f"once and each seat behind it once"
        )
        player, offered, standing = rows[seats]
        assert standing == 0 and "raise" not in offered, (
            f"seed {seed}: called around, the next decision is seat {player} "
            f"facing {standing}, offered {sorted(offered)} — the bring-in poster "
            f"is asked again on 3rd street, which no completion licensed"
        )
