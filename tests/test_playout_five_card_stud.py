"""Five-Card Stud: the invariants a random session must satisfy, and the two
Pagat sentences about the bring-in that only a played hand can show.

Chip conservation is the falsifiable check for the betting and side-pot logic —
the total never moves, whatever the streets do — and card conservation is its
zone-level sibling. Both are asserted over a batch of seeds alongside
termination.

The bring-in tests are here rather than in the readiness proofs because they are
about the OPTION LIST the rules describe, not about information sets. The first
street's ring opens on the poster, so the poster's own turn is the round's first
decision, and what it is offered and what its choice does to the seats behind it
are the two halves of Pagat's paragraph on opening the betting.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

STUD = Path(__file__).parent.parent / "docs" / "games" / "five-card-stud.cardlang"

CHIPS = 600  # 3 players x 200 starting chips


def test_20_random_sessions_satisfy_invariants() -> None:
    game = check_source(STUD)
    start = time.monotonic()
    for seed in range(20):
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        assert sum(result.scores.values()) == CHIPS, f"seed {seed}: {result.scores}"
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1, f"seed {seed}: {result.scores}"
        assert result.winner == with_chips[0]
        assert result.scores[result.winner] == CHIPS
        assert census["total"] == 52, f"seed {seed}: {census}"
    assert time.monotonic() - start < 120  # stays comfortably fast


def _first_street(seed: int, poster_plays: str, steps: int) -> list[tuple[int, set[str], tuple[int, int, int]]]:
    """The first street's decisions: who is asked, what they are offered, and
    the standing bet / level / aggression count they face.

    The live `RuntimeState` arrives through `on_first_decision` and is read at
    each later decision, so the bookkeeping reported is the state the seat
    actually faces rather than one reconstructed afterwards.
    """
    rows: list[tuple[int, set[str], tuple[int, int, int]]] = []
    held: dict[str, Any] = {}
    pick = random.Random(seed)

    def capture(rs: Any) -> None:
        held["rs"] = rs

    def read(name: str) -> Any:
        for frame in reversed(held["rs"].frames):
            if name in frame:
                return frame[name]
        raise AssertionError(f"{name} is in no live frame")

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        if len(rows) < steps:
            rows.append(
                (player, {n for n, _ in candidates}, (read("bet_to_match"), read("level"), read("raises")))
            )
            if len(rows) == 1:
                chosen = [c for c in candidates if c[0] == poster_plays]
                assert chosen, (
                    f"seed {seed}: the street's FIRST decision goes to seat "
                    f"{player}, offered {sorted(n for n, _ in candidates)} — a "
                    f"seat facing the bring-in rather than the seat that posted "
                    f"it, so `{poster_plays}` is not on the table and the "
                    f"poster's option is not where the rules put it"
                )
                return chosen
        return [pick.choice(candidates)]

    play_game(check_source(STUD), random.Random(seed), chooser=chooser, on_first_decision=capture)
    return rows


def test_the_bring_in_poster_is_offered_the_full_small_bet() -> None:
    """Pagat: "The player who opens the betting has the option to place a full
    small bet ($5) instead of just the compulsory minimum $2."

    The post is already made when the poster's turn comes, so it owes nothing
    and cannot fold its own forced bet: the option list is exactly `check`
    (stand on the minimum) and `raise` (complete). Swept over seeds because
    which seat brings in is a fact about the deal, and the claim is about the
    poster whoever it is.

    red under: change the first street's `round ... from bringer` to
    `from bringer offset_by left` — the poster then acts last and the round's
    first decision belongs to a seat facing the bring-in.
    """
    for seed in range(20):
        player, offered, (bet, level, raises) = _first_street(seed, "check", 1)[0]
        assert offered == {"check", "raise"}, (
            f"seed {seed}: the bring-in poster (seat {player}) is offered "
            f"{sorted(offered)}, not its stand-or-complete option"
        )
        assert (bet, level, raises) == (4, 0, 0), (
            f"seed {seed}: the poster faces {(bet, level, raises)} — the post "
            f"should stand at 4 with the street's level and cap untouched"
        )


def test_the_posters_choice_is_what_the_seats_behind_it_face() -> None:
    """Pagat: "If the opener just places the minimum bring-in, subsequent
    players have the option to complete the bet to a small bet ($5), to call the
    bring-in ($2) or to fold. Only if someone completes the bet are later
    players allowed to raise. If the opener chooses to begin with a full bet
    ($5), subsequent players can raise."

    Both arms, on the same deal. Standing leaves the standing bet at the
    bring-in with the level at zero, so the next seat's `raise` is the
    COMPLETION and no aggression has been spent — Pagat's "A bring-in of less
    than a small bet does not count as a bet for this purpose - after it is
    completed there can be three raises". Completing takes the bet to the
    street's own size rather than adding one to the post, which is the
    difference between a ladder of 4 / 10 / 20 and one of 4 / 14 / 24.
    """
    stood = _first_street(3, "check", 2)
    completed = _first_street(3, "raise", 2)

    assert stood[1][2] == (4, 0, 0), (
        f"standing on the minimum should leave the seat behind facing the "
        f"bring-in with the level at zero, not {stood[1][2]}"
    )
    assert completed[1][2] == (10, 10, 1), (
        f"completing should take the standing bet to the street's own size and "
        f"spend the street's first aggression, not leave {completed[1][2]}"
    )
    # The seat behind faces the same option list either way; what differs is
    # what its `raise` costs, which the bookkeeping above already fixes.
    assert stood[1][1] == completed[1][1] == {"call", "fold", "raise"}
