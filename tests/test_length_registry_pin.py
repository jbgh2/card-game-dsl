"""Every registered game ends by its rules under its reference playout policy,
with headroom under its `max_length`; the corpus's legal Length Stops are
asserted as stops; and `max_game_length` is a promise every registered game
keeps (docs/decisions.md, "Game length as a declared contract").

A game that reaches its bound ends there, flagged, scored by its Stop
Result, and nothing refuses it. So what a looping `until` in a corpus game would have been
refused for, this module measures instead: a registered game whose
reference-policy line stops by length, or runs within its dial of the bound,
is red here.

Completeness ledger
-------------------
property:        every registered game, on every seed of the manifest,
                 under its reference playout policy, ends by its rules
                 (`ended_by == rules`) after fewer than `max_length / dial`
                 picks, or, for a game whose bound is its rules' own
                 (`RULES_BOUND`), at or before it; its lowest-id line,
                 walked natively, reaches a terminal at or before its
                 bound, ended the way
                 `LOWEST_ID_ENDS` names; Coup under `first` and Tichu under
                 the uniform Chooser end by length, each scored as it stands
                 as its file declares.
domain:          the games this process registers at import, the corpus
                 (`registry.GAMES`) and every file `CARDLANG_GAMES` names,
                 crossed with the coverage manifest. A game registered later
                 by `register_game_file` is outside it, as it is outside the
                 readiness battery (issue #25).
registry:        games: `cardlang.openspiel.registry.GAMES` and
                 `cardlang.openspiel.game._entry_files`; policies:
                 `tests.playout_policy.REFERENCE_POLICIES`; seeds:
                 `tests.openspiel_ready.harness.SWAP_SEEDS`; dials: `HEADROOM`
                 below, the rules-bound games: `RULES_BOUND`, and the
                 lowest-id line's ends: `LOWEST_ID_ENDS`, all reconciled by
                 `test_every_table_row_names_a_registered_game`.
held by:         Born-Green Pin: whether a game's lines end by its rules is a
                 fact about its runs, which no type holds and the engine
                 cannot decide.
does not prove:  that a line no policy in the table walks ends by its rules:
                 a designer's game under play the policy never makes may
                 still meet its bound, and ends there by its Stop Result.

red under: register tests/test_length_stop.py's `bounded_tic_tac_toe()`
(tic-tac-toe at `max_length: 5`) through `CARDLANG_GAMES`; a uniform line that
places five marks without a win stops by length. And: make `chooser.decide`'s
`admit` admit every pick; no line stops at its bound, and every game in
`LOWEST_ID_ENDS` walks past it. And: delete `RULES_BOUND`'s `hex` row; every
Hex manifest line falls within 4x of its 121. A dial-1 `HEADROOM` row in its
place stays green on the manifest, whose Hex lines stop short of the board,
and refuses seed 4's full-board line at 121 picks.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import pytest

pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # noqa: E402  (registers on import)
from cardlang.openspiel.registry import GAMES, _GAMES_DIR  # noqa: E402
from cardlang.openspiel.replay import LiveLine  # noqa: E402
from cardlang.openspiel.seat_policy import FirstSeatPolicy  # noqa: E402
from cardlang.pipeline import check_source  # noqa: E402
from cardlang.runtime.chooser import random_chooser  # noqa: E402
from cardlang.runtime.driver import play_game  # noqa: E402
from cardlang.runtime.errors import OwnerGuardError  # noqa: E402
from cardlang.runtime.state import RuntimeState  # noqa: E402
from tests.openspiel_ready.harness import SWAP_SEEDS, greedy_line, manifest  # noqa: E402
from tests.playout_policy import REFERENCE_POLICIES, reference_policy_for  # noqa: E402


def _registered() -> dict[str, Path]:
    """Short name -> file, for every game this process registers at import."""
    games = {short: _GAMES_DIR / filename for short, filename in GAMES.items()}
    value = os.environ.get(ogame.GAMES_ENV_VAR, "")
    if value.strip():
        for entry in value.split(os.pathsep):
            for path in ogame._entry_files(entry):
                short, resolved = ogame._pair(path)
                games[short] = Path(resolved)
    return games


REGISTERED = _registered()

# The multiple of a game's longest reference-policy line its `max_length`
# must exceed: Breakthrough's dial unless a row here says otherwise, each row
# with its measurement.
DIAL = 4
HEADROOM: dict[str, tuple[int, str]] = {
    "tic-tac-toe": (
        3,
        "bounded by its rules at nine placements; the bound of 30 is 3.3x the "
        "most any line can make",
    ),
    "pinochle": (
        2,
        "measured 2026-09-21 under the reference policy over 250 seeds: 3517 "
        "picks at most (tests/test_playout_pinochle.py), 2.8x under 10000 "
        "(issue #1005)",
    ),
    "tichu": (
        3,
        "measured 2026-10-31 under the reference policy over the manifest: "
        "11960 picks at most, 3.3x under 40000 (issue #1005)",
    ),
}


# The games whose `max_length` is the bound their rules put on every line,
# not an allowance over measured play: a line may end by its rules exactly at
# it, so no dial applies, and `ended_by == rules` is the whole check. Each row
# with the rule that bounds the line.
RULES_BOUND: dict[str, str] = {
    "hex": (
        "one stone per pick on 121 cells, and on a full board exactly one side "
        "has joined its edges, so the 121st placement decides "
        "(tests/test_playout_hex.py witnesses lines that fill the board)"
    ),
}


# How the lowest-id line of seed `SWAP_SEEDS[0]` ends, for the games whose
# line their rules never end (measured 2026-10-31; nine-mens-morris
# 2026-11-01): a table taking the first pick at every decision loops, and the
# line ends at the bound. Every other registered game's ends by its rules.
LOWEST_ID_ENDS: dict[str, str] = {
    "belote": "length",
    "coup": "length",
    "gin-rummy": "length",
    "klondike": "length",
    "nine-mens-morris": "length",
    "tichu": "length",
}


def _stem(path: Path) -> str:
    return path.stem


def _ended_by(thing: object) -> object:
    return getattr(getattr(thing, "ended_by", None), "value", None)


def test_every_table_row_names_a_registered_game() -> None:
    """red under: rename `tichu` in `REFERENCE_POLICIES`."""
    stems = {_stem(p) for p in REGISTERED.values()}
    assert set(REFERENCE_POLICIES) <= stems
    assert set(HEADROOM) <= stems
    assert set(RULES_BOUND) <= stems
    assert not set(HEADROOM) & set(RULES_BOUND)
    assert set(LOWEST_ID_ENDS) <= stems


@pytest.mark.parametrize("seed", manifest())
@pytest.mark.parametrize("short_name", sorted(REGISTERED))
def test_a_registered_game_ends_by_its_rules_with_headroom(short_name: str, seed: int) -> None:
    path = REGISTERED[short_name]
    game = check_source(path)
    assert game.max_length is not None
    rng = random.Random(seed)
    chooser = reference_policy_for(_stem(path), rng) or random_chooser(rng)
    world: list[RuntimeState] = []
    result = play_game(game, rng, chooser=chooser, on_first_decision=world.append)
    picks = world[0].decisions_made if world else 0
    assert _ended_by(result) == "rules", (
        f"{short_name} seed {seed}: the reference policy's line reached max_length "
        f"({game.max_length}) without the rules ending it"
    )
    if _stem(path) in RULES_BOUND:
        return
    dial, _why = HEADROOM.get(_stem(path), (DIAL, ""))
    assert picks * dial < game.max_length, (
        f"{short_name} seed {seed}: {picks} picks is within {dial}x of max_length "
        f"({game.max_length}); a finding about the game's length, never a reason "
        f"to raise the bound unmeasured"
    )


@pytest.mark.parametrize("short_name", sorted(REGISTERED))
def test_the_lowest_id_line_reaches_a_terminal_within_the_advertised_length(short_name: str) -> None:
    """The lowest-id line, walked natively through `play_game` (the line a
    greedy OpenSpiel consumer takes, without the adapter's replay cost), ends
    at or before the declared `max_length` the adapter advertises as
    `max_game_length`, and ends the way `LOWEST_ID_ENDS` says, for every
    registered game: the longest of these walks, Tichu's, measured 25s
    (2026-10-31)."""
    path = REGISTERED[short_name]
    game = check_source(path)
    assert game.max_length is not None
    line, returns, ended_by = greedy_line(str(path), SWAP_SEEDS[0], game.max_length)
    assert returns is not None, f"{short_name}: the line ran past its bound"
    assert len(line) <= game.max_length
    expected = LOWEST_ID_ENDS.get(_stem(path), "rules")
    assert ended_by is not None and ended_by.value == expected, (
        f"{short_name}: the lowest-id line ended by {ended_by}, not {expected}"
    )
    if expected == "length":
        assert len(line) == game.max_length


def test_coup_under_first_is_a_length_stop() -> None:
    """A table whose every seat takes the first pick repeats one exchange:
    Coup's lines are legally unbounded, and this one ends by length, scored
    as it stands: no seat has been exiled, so every seat's `alive` pays 1."""
    path = str(_GAMES_DIR / "coup.cardlang")
    line = LiveLine(path, 1)
    end = line.play({seat: FirstSeatPolicy() for seat in range(4)})
    assert _ended_by(end) == "length"
    assert len(line.history) == 500
    assert end.returns == [1.0, 1.0, 1.0, 1.0]


def test_tichu_under_the_uniform_chooser_is_a_length_stop() -> None:
    """A uniform Chooser calls tichu at about half of every offer and the race
    to 1000 diverges: seed 0 reaches the bound, scored as it stands, and the
    team standing higher on `score` wins."""
    game = check_source(_GAMES_DIR / "tichu.cardlang")
    world: list[RuntimeState] = []
    result = play_game(game, random.Random(0), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert world[0].decisions_made == game.max_length
    assert result.scores == {0: -12505, 1: -9095}
    assert result.winners == frozenset({1, 3})
