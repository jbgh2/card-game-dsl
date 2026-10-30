"""Random-playout harness for Bridge (rubber, without honours).

Bridge reuses the ordinary Trick engine (its play needs only follow-suit) but
adds a real auction (ascending bids over C D H S NT, double/redouble) and rubber
scoring. Falsifiable invariants: card conservation, per-trick winner correctness
against the contract's trump (none for a no-trump contract), termination (the
rubber loop exits when a side reaches two games or at the twelfth deal), and the
winner being the side with the higher total.

The longest legal line is played too: every auction runs to seven no-trumps
redoubled with each call delayed as long as the rules allow, so the declared
`max_length` is held against the game's real ceiling rather than a sample of
uniform lines (red under: lower `max_length` below that line's length).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, Player

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"


def _bridge() -> Any:
    return check_source(BRIDGE)


def _expected_winner(group: list[tuple[int, Card]], trump: str | None) -> int:
    led = group[0][1].suit
    if trump is not None:
        trumps = [(p, c) for p, c in group if c.suit == trump]
        if trumps:
            return max(trumps, key=lambda pc: pc[1].rank_order)[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: pc[1].rank_order)[0]


def test_40_random_rubbers_satisfy_invariants() -> None:
    game = _bridge()
    for seed in range(40):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        trumps: list[str | None] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick_end":
                trumps.append(data["trump"])  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Terminated, won by the seats of the side with the higher total.
        top = max(result.scores.values())
        assert result.winners == {
            p for t, s in result.scores.items() if s == top for p in game.teams[t]
        }
        assert census["total"] == 52, f"seed {seed}: {census}"

        # Played hands are 13 tricks of four plays; all-pass hands add none.
        assert len(plays) == 4 * len(tricks)
        assert len(trumps) == len(tricks)
        assert len(tricks) % 13 == 0  # every played hand contributes exactly 13

        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _expected_winner(group, trumps[i]), f"seed {seed} trick {i}"


STRAIN_RANK = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3, None: 4}
# The longest auction: three passes before the opening bid; after each of the
# 35 bids from one club to seven no-trumps, two passes, a double, two passes,
# a redouble and two passes; then the third closing pass.
LONGEST_AUCTION = 3 + 35 * 9 + 1


def test_the_longest_legal_line_fits_max_length() -> None:
    game = _bridge()
    box: dict[str, RuntimeState] = {}

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if not isinstance(candidates[0], tuple):
            return [candidates[0]]
        rs = box["rs"]
        passes, made_bid = rs.get("passes"), rs.get("made_bid")
        if passes < (2 if made_bid else 3):
            return [("pass", None)]
        for call in (("double", None), ("redouble", None)):
            if call in candidates:
                return [call]
        level, strain = rs.get("cur_level"), rs.get("cur_strain")

        def cost(bid: tuple[str, str | None]) -> tuple[int, int]:
            rank = STRAIN_RANK[bid[1]]
            if level == 0:
                return (1, rank)
            return (level if rank > STRAIN_RANK[strain] else level + 1, rank)

        bids = [c for c in candidates if c[0] == "submit_bid"]
        return [min(bids, key=cost) if bids else ("pass", None)]

    def attach(rs: RuntimeState) -> None:
        box["rs"] = rs

    play_game(game, random.Random(0), chooser=chooser, on_first_decision=attach)
    decisions = box["rs"].decisions_made
    assert decisions == 12 * (LONGEST_AUCTION + 52), decisions
    assert game.max_length is not None and decisions <= game.max_length
