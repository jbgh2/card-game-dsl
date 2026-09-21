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

    Measured 2026-09-20: every one of these seeds reaches a bring-in street with
    a post standing, so the floor below is the seed count rather than a token
    non-vacuity guard — a line that stopped reaching the branch fails here as
    loudly as a wrong standing bet would.
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

    assert seen >= 30, (
        f"only {seen} of 30 seeds reached a bring-in street with a post "
        f"standing, so this line barely reaches the branch the claim is about"
    )


GAME = Path(__file__).parent.parent / "docs" / "games" / "seven-card-stud.cardlang"


def _three_seats_two_chips() -> Any:
    """Seven-Card Stud at a table where the bring-in post busts its poster.

    Derived from the corpus file by substitution rather than copied, so it
    cannot drift from the game the way a hand-written fixture can: three seats
    with two chips each, so the one-chip ante leaves one chip and the bring-in
    of `min(2, 1)` takes it. Three seats can ante; two can act once the post
    is made.
    """
    src = GAME.read_text()
    swapped = src.replace("  players: 4\n", "  players: 3\n", 1).replace(
        "stack[player] : Integer = 100", "stack[player] : Integer = 2", 1
    )
    assert swapped != src and "players: 3" in swapped, "the substitution missed"
    return check_source_text(swapped)


def check_source_text(text: str) -> Any:
    from cardlang.pipeline import check_dsl

    return check_dsl(text, "seven-card-stud.cardlang")


def test_the_cap_counts_the_seats_that_can_act_after_the_forced_post() -> None:
    """Pagat caps a street that began with "more than two active players", and
    the start of the betting round is AFTER the bring-in: the post is forced,
    not a turn, so a poster it leaves with nothing is not one of the seats the
    cap protects.

    Counting before the post reads three seats where two will act, and caps a
    street the rules leave uncapped. The 50-seed golden never reaches this
    state, so nothing else in the suite would notice the count moving back.

    Does NOT cover Five-Card Stud, which carries the same ordering and the same
    fix. Its bring-in is 4 on a 10-chip street, so the busting table is a
    different substitution, and it has no per-seed golden either — that game's
    half of this correction is unpinned.

    red under, run: move `raise_cap := …` above `let bringer =
    bring_in_seat()` in `docs/games/seven-card-stud.cardlang`'s third street —
    the cap reads 4 here instead of the uncapped bound, and this fails naming
    both numbers.
    """
    game = _three_seats_two_chips()
    seen: list[tuple[int, int]] = []
    box: list[Any] = []

    def on_first(rs: Any) -> None:
        box.append(rs)

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        rs = box[0]
        if not seen:
            stacks = rs.get("stack")
            seen.append((rs.get("raise_cap"), sum(1 for v in stacks.values() if v > 0)))
        return list(candidates[:1])

    for seed in range(4):
        seen.clear()
        box.clear()
        try:
            play_game(game, random.Random(seed), None, chooser, None, on_first)
        except Exception:
            pass  # the session need not finish; the first decision is the claim
        assert seen, f"seed {seed}: no decision was reached"
        cap, can_act = seen[0]
        assert can_act == 2, f"seed {seed}: the post left {can_act} able to act, wanted 2"
        assert cap > 4, (
            f"seed {seed}: two seats can act and the cap is {cap} — the count was "
            f"taken before the forced post, where the rules take it after"
        )
