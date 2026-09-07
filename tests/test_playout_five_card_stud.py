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
from cardlang.runtime.stud import _best_showing

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


def test_a_street_is_anchored_on_the_best_board_even_when_it_cannot_act() -> None:
    """An ALL-IN seat keeps taking exposed cards, so it can hold the best board
    while having no chips to bet with. The rules anchor the street on the best
    board wherever it sits; the action then falls to the first seat clockwise
    from it that can act. Selecting the best board among only the seats that CAN
    act would name a different seat, and so a different ring order.

    Only a played session reaches this: a seat goes all-in and survives to a
    later street solely through the chips and the deal, so no hand-built state
    would put the game in the configuration the claim is about. The sweep is
    wide because the cell is incidental rather than aimed at — the assertion
    reports how many openings it actually found, so a line that stopped reaching
    them fails as loudly as a wrong order would. Measured 2026-09-06: 49 such
    openings across these seeds, and the floor below is set to notice a collapse
    rather than drift.
    """
    game = check_source(STUD)
    openings = 0

    for seed in range(60):
        held: dict[str, Any] = {}
        pick = random.Random(seed + 99)

        def capture(rs: Any) -> None:
            held["rs"] = rs

        def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
            nonlocal openings
            rs = held["rs"]

            def read(name: str) -> Any:
                for frame in reversed(rs.frames):
                    if name in frame:
                        return frame[name]
                raise AssertionError(f"{name} is in no live frame")

            folded, stack = read("folded"), read("stack")
            seats = list(range(3))
            boards = {q: list(rs.zones.instance("upcards", q).cards) for q in seats}
            showing = [q for q in seats if not folded[q] and boards[q]]
            able = [q for q in showing if stack[q] > 0]
            # A street's FIRST decision, read off the betting bookkeeping rather
            # than off the cards: `open_street` zeroes every `bet_by` and clears
            # every `acted`, and nothing else leaves both in that state — a
            # re-open clears `acted`, but only after a wager moved a `bet_by`.
            # Reading the cards instead would misfire, because a fold takes a
            # board out of `upcards` mid-street. The FIRST street never matches,
            # which is right: its bring-in posts before the round, and it is
            # anchored on the poster rather than on a board.
            acted, bet_by = read("acted"), read("bet_by")
            if not any(acted.values()) and not any(bet_by.values()):
                if able and set(showing) != set(able):
                    openings += 1
                    anchor = _best_showing(showing, boards)
                    want = next(
                        q for q in (anchor, (anchor + 1) % 3, (anchor + 2) % 3) if q in able
                    )
                    assert player == want, (
                        f"seed {seed}: boards showing {showing}, of which {able} can "
                        f"act; the best board is seat {anchor}, so the street opens "
                        f"on seat {want} — the game asked seat {player}"
                    )
            return [pick.choice(candidates)]

        play_game(game, random.Random(seed), chooser=chooser, on_first_decision=capture)

    assert openings > 25, (
        f"only {openings} street openings had an all-in seat still showing cards, "
        f"so this line barely reaches the configuration the claim is about"
    )
