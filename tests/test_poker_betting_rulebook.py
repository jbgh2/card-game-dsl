"""The rulebooks' own worked examples, driven through `poker_betting`.

property:        for each arithmetic example PRINTED in a poker rulebook, the
                 library offers the seat what the book says it may do, and a
                 wager costs what the book says it costs.
domain:          every worked example in the two authorities this repo names
                 (CLAUDE.md, "Rule references") that turns on the arithmetic of
                 an incomplete wager: Robert's Rules of Poker, "Betting and
                 Raising" 5 and "Rules of Seven-Card Stud" 3; Pagat's all-in
                 betting page. Not a crossed product — the domain is what the
                 books happen to print, and it grows one case at a time.
registry:        `CASES` below, each row carrying its source and its quote; the
                 library under test is `docs/libraries/poker_betting.cardlang`
                 via `libraries.load_library`.
does not prove:  nothing about positions the books do not illustrate. This
                 module is narrow ON PURPOSE and its narrowness is the point:
                 it is the ONLY oracle in this suite that is SPECIFIED rather
                 than DERIVED. Every other betting test — the offers grid, the
                 transition grid, the invariants — reads its expected column out
                 of the same rulebook by the same pair of eyes, so a MISREADING
                 survives all of them together. It cannot survive a printed
                 number. That asymmetry is why a case here outranks a cell
                 anywhere else in the suite, and why the standing rule is that
                 every betting finding which turns out to be a misreading closes
                 by adding its example here (docs/plans/2026-08-26-betting-rules-oracles.md).

The books are quoted rather than paraphrased because a paraphrase is already a
reading, and a reading is the thing this module exists to check.
"""

from __future__ import annotations

import random
from typing import Any, NamedTuple

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

ROBERTS = "Robert's Rules of Poker (pagat.com/docs/RobsPkrRulesHome.pdf)"
PAGAT = "Pagat, All-in betting (pagat.com/poker/rules/betting.html)"


class Case(NamedTuple):
    """One printed example, and what the book says happens in it."""

    name: str
    cite: str
    quote: str
    limit: int
    stacks: tuple[int, ...]
    opening_bet: int
    """A forced post standing when the round opens, or 0 for a clean street.

    The bring-in is a forced post and takes no turn to place, which is what
    lets a book's stud example start mid-street. Seat 0 posts it.
    """
    first: int
    """The seat the round starts from — 1 where seat 0 posted, since a book
    that says "the next player" means the seat after the poster."""
    script: tuple[str, ...]
    """Moves played in order, one per decision, before the seat under test."""
    offered: frozenset[str] | None
    """Exactly what the book says that seat may do, or None if it does not say."""
    standing_after_raise: int | None
    """What the bet stands at once that seat raises, or None if not printed."""
    raises_after_raise: int | None
    """Aggressions counted once that seat raises, or None if not printed."""


CASES: tuple[Case, ...] = (
    Case(
        name="pagat-completes-the-raise-over-a-short-all-in",
        cite=PAGAT,
        quote=(
            "In a $5 betting round with five players, player A checks, player B "
            "bets $5, player C calls for $5 and player D goes all-in for $6. "
            "Player E has the option to fold, to call for $6 or to complete the "
            "raise for $10."
        ),
        # D's $6 is a raise of $1 on a $5 street — under half, so it neither
        # counts nor reopens. The completion is $10, which is the LAST FULL
        # WAGER plus the street's size, and not the standing $6 plus it.
        limit=5,
        stacks=(20, 20, 20, 6, 20),
        opening_bet=0,
        first=0,
        script=("check", "bet", "call", "raise"),
        offered=frozenset({"call", "raise"}),
        standing_after_raise=10,
        raises_after_raise=None,
    ),
    Case(
        name="roberts-full-raise-over-an-all-in-of-half-a-bet-or-more",
        cite=f"{ROBERTS}, Betting and Raising 5",
        quote=(
            "An all-in wager of a half a bet or more is treated as a full bet, "
            "and a player may fold, call, or make a full raise. (An example of "
            "a full raise is on a $20 betting round, raising a $15 all-in bet "
            "to $35)."
        ),
        # The other arm: $15 on a $20 street IS half a bet or more, so it is
        # treated as a full bet and BECOMES the level a raise measures from.
        # $35 is $15 plus the street, so the all-in moved the level and the
        # short one in the case above did not.
        limit=20,
        stacks=(15, 40, 40),
        opening_bet=0,
        first=0,
        script=("bet",),
        offered=frozenset({"call", "raise"}),
        standing_after_raise=35,
        raises_after_raise=None,
    ),
    Case(
        name="roberts-stud-completion-is-not-a-raise",
        cite=f"{ROBERTS}, Rules of Seven-Card Stud 3",
        quote=(
            "Increasing the amount wagered by the opening forced bet up to a "
            "full bet does not count as a raise, but merely as a completion of "
            "the bet. For example: In $15-$30 stud, the lowcard opens for $5. "
            "If the next player increases the bet to $15 (completes the bet), "
            "up to three raises are then allowed when using a three-raise limit."
        ),
        # The completion brings the bet to the street's size and is the street's
        # OPENING BET, not a raise on top of one — so with `raise_cap` counting
        # aggressions including the opening bet, it leaves the cap at one, and
        # the three raises the book allows still fit underneath.
        limit=15,
        stacks=(60, 60, 60),
        opening_bet=5,
        first=1,
        script=(),
        offered=None,
        standing_after_raise=15,
        raises_after_raise=1,
    ),
)


_PROBE = """
game Rulebook {{
  uses poker_betting
  players: {seats}
  cards: standard52
  max_length: 200
  zones {{ deck : Deck }}
  state {{
    stack[player]     : Integer = 0
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 99
  }}
  phase play {{
    run open_street({limit})
{stacks}{post}    round offering [check, bet, call, raise] from {first}
          over players where pending(player)
          until false
  }}
  winner: highest stack
}}
"""


class _Reached(Exception):
    """Carries the seat-under-test's offer out of the probe."""

    def __init__(self, names: frozenset[str]) -> None:
        self.names = names


def _source(case: Case) -> str:
    stacks = "".join(
        f"    stack[{seat}] := {chips}\n" for seat, chips in enumerate(case.stacks)
    )
    # A forced post stands before the round begins and takes no turn to place,
    # which is what a book's stud example assumes when it starts at the bring-in.
    post = ""
    if case.opening_bet:
        post = (
            f"    bet_by[0] := {case.opening_bet}\n"
            f"    stack[0] := stack[0] - {case.opening_bet}\n"
            f"    committed[0] := committed[0] + {case.opening_bet}\n"
            f"    bet_to_match := {case.opening_bet}\n"
        )
    return _PROBE.format(
        seats=len(case.stacks),
        limit=case.limit,
        stacks=stacks,
        post=post,
        first=case.first,
    )


def _play(case: Case) -> tuple[frozenset[str], RuntimeState]:
    """Play the case's script, then stop at the seat the book speaks about."""
    game = check_dsl(_source(case), "rulebook.cardlang")
    box: list[RuntimeState] = []
    step = 0

    def on_first(state: RuntimeState) -> None:
        box.append(state)

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        nonlocal step
        names = frozenset(name for name, _ in candidates)
        if step == len(case.script):
            raise _Reached(names)
        want = case.script[step]
        step += 1
        for candidate in candidates:
            if candidate[0] == want:
                return [candidate]
        raise AssertionError(
            f"{case.name}: step {step - 1} wanted `{want}` and the library "
            f"offered {sorted(names)} — the book's line is not playable here"
        )

    try:
        play_game(game, random.Random(0), None, chooser, None, on_first)
    except _Reached as reached:
        return reached.names, box[0]
    raise AssertionError(f"{case.name}: the probe ran out of decisions")


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_the_library_plays_the_books_worked_example(case: Case) -> None:
    """A printed number is the one expected value in this suite nobody authored.

    red under: there is no plant to describe. Every assertion here is a figure
    lifted from a rulebook, so the way to redden a case is to change the
    library's arithmetic away from the book — which is the defect the case
    exists to catch, and is exactly the state these cases were authored in.
    """
    offered, state = _play(case)

    if case.offered is not None:
        # `fold` is game-local and outside the library, so the book's third
        # option is not the library's to offer; the rest of the set is.
        assert offered == case.offered, (
            f"{case.name}: the library offers {sorted(offered)} where\n"
            f"  {case.cite}\n  says {sorted(case.offered)}\n  {case.quote}"
        )

    if case.standing_after_raise is None:
        return

    assert "raise" in offered, (
        f"{case.name}: the book has this seat completing or raising, and the "
        f"library offers {sorted(offered)}"
    )
    _play_one_more(case, state)


def _play_one_more(case: Case, _seen: RuntimeState) -> None:
    """Replay with the raise appended, and read what the bet then stands at."""
    extended = case._replace(script=case.script + ("raise",))
    _, state = _play(extended)
    standing = state.get("bet_to_match")
    assert standing == case.standing_after_raise, (
        f"{case.name}: raising makes the bet {standing} where\n"
        f"  {case.cite}\n  says {case.standing_after_raise}\n  {case.quote}"
    )
    if case.raises_after_raise is not None:
        counted = state.get("raises")
        assert counted == case.raises_after_raise, (
            f"{case.name}: the library has counted {counted} aggressions where\n"
            f"  {case.cite}\n  allows the three raises that follow "
            f"{case.raises_after_raise}\n  {case.quote}"
        )


def test_every_case_carries_its_source_and_its_quote() -> None:
    """A case with no citation is an authored expectation wearing a book's name.

    The whole claim of this module is that its expected column came from print
    rather than from a reading, and a row without its quote cannot support that.

    red under: blank any `quote` or `cite` field in `CASES`.
    """
    for case in CASES:
        assert case.cite.strip(), f"{case.name}: no source"
        assert len(case.quote.split()) >= 12, (
            f"{case.name}: the quote is too short to carry the example — a "
            f"paraphrase is a reading, which is what this module cannot use"
        )
        assert case.cite in (PAGAT,) or case.cite.startswith(ROBERTS), (
            f"{case.name}: cites {case.cite!r}, which is not one of the two "
            f"authorities CLAUDE.md names"
        )
