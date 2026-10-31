"""Every registered game ends by its rules under its reference playout policy,
with headroom under its `max_length`; the corpus's legal Length Stops are
asserted as stops; and `max_game_length` is a promise every registered game
keeps (docs/decisions.md, "Game length as a declared contract").

A game that reaches its bound ends there as a tie, flagged, and nothing
refuses it. So what a looping `until` in a corpus game would have been
refused for, this module measures instead: a registered game whose
reference-policy line stops by length, or runs within its dial of the bound,
is red here.

Completeness ledger
-------------------
property:        every registered game, on every seed of the manifest,
                 under its reference playout policy, ends by its rules
                 (`ended_by == rules`) after fewer than `max_length / dial`
                 picks; its lowest-id line reaches a terminal at or before
                 its bound; Coup under `first` and Tichu under the uniform
                 Chooser end by length, as ties.
domain:          the games this process registers at import, the corpus
                 (`registry.GAMES`) and every file `CARDLANG_GAMES` names,
                 crossed with the coverage manifest. A game registered later
                 by `register_game_file` is outside it, as it is outside the
                 readiness battery (issue #25).
registry:        games: `cardlang.openspiel.registry.GAMES` and
                 `cardlang.openspiel.game._entry_files`; policies:
                 `tests.playout_policy.REFERENCE_POLICIES`; seeds:
                 `tests.openspiel_ready.harness.SWAP_SEEDS`; dials: `HEADROOM`
                 below, reconciled by
                 `test_every_table_row_names_a_registered_game`.
held by:         Born-Green Pin: whether a game's lines end by its rules is a
                 fact about its runs, which no type holds and the engine
                 cannot decide.
does not prove:  that a line no policy in the table walks ends by its rules:
                 a designer's game under play the policy never makes may
                 still meet its bound, and ends there as a tie.

red under: register tests/test_length_stop.py's `bounded_tic_tac_toe()`
(tic-tac-toe at `max_length: 5`) through `CARDLANG_GAMES`; a uniform line that
places five marks without a win stops by length.
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
    "tichu": (
        3,
        "measured 2026-10-31 under the reference policy over the manifest: "
        "11960 picks at most, 3.3x under 40000 (issue #1005)",
    ),
}

# The walks the lowest-id line takes to its terminal, by short name; a game
# missing here is walked.
NOT_WALKED: dict[str, str] = {}


def _stem(path: Path) -> str:
    return path.stem


_RED = pytest.mark.xfail(
    strict=True,
    raises=(OwnerGuardError, AssertionError, ValueError, TypeError),
    reason="a run carries no `ended_by` on this tree",
)


def _ended_by(thing: object) -> object:
    return getattr(getattr(thing, "ended_by", None), "value", None)


def test_every_table_row_names_a_registered_game() -> None:
    """red under: rename `tichu` in `REFERENCE_POLICIES`."""
    stems = {_stem(p) for p in REGISTERED.values()}
    assert set(REFERENCE_POLICIES) <= stems
    assert set(HEADROOM) <= stems
    assert set(NOT_WALKED) <= set(REGISTERED)


@_RED
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
    dial, _why = HEADROOM.get(_stem(path), (DIAL, ""))
    assert picks * dial < game.max_length, (
        f"{short_name} seed {seed}: {picks} picks is within {dial}x of max_length "
        f"({game.max_length}); a finding about the game's length, never a reason "
        f"to raise the bound unmeasured"
    )


@_RED
@pytest.mark.parametrize("short_name", sorted(REGISTERED))
def test_the_lowest_id_line_reaches_a_terminal_within_the_advertised_length(short_name: str) -> None:
    """`max_game_length` is the declared `max_length`, and the lowest-id line
    a greedy OpenSpiel consumer walks ends at or before it."""
    if short_name in NOT_WALKED:
        pytest.skip(NOT_WALKED[short_name])
    path = REGISTERED[short_name]
    game = check_source(path)
    assert game.max_length is not None
    line, returns, ended_by = greedy_line(str(path), SWAP_SEEDS[0], game.max_length)  # type: ignore[misc]
    assert returns is not None
    assert len(line) <= game.max_length
    assert getattr(ended_by, "value", None) in ("rules", "length")


@_RED
def test_coup_under_first_is_a_length_stop() -> None:
    """A table whose every seat takes the first pick repeats one exchange:
    Coup's lines are legally unbounded, and this one ends by length, a tie."""
    path = str(_GAMES_DIR / "coup.cardlang")
    line = LiveLine(path, 1)
    end = line.play({seat: FirstSeatPolicy() for seat in range(4)})
    assert _ended_by(end) == "length"
    assert len(line.history) == 500
    assert end.returns == [0.0, 0.0, 0.0, 0.0]


@_RED
def test_tichu_under_the_uniform_chooser_is_a_length_stop() -> None:
    """A uniform Chooser calls tichu at about half of every offer and the race
    to 1000 diverges: seed 0 reaches the bound."""
    game = check_source(_GAMES_DIR / "tichu.cardlang")
    world: list[RuntimeState] = []
    result = play_game(game, random.Random(0), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert world[0].decisions_made == game.max_length
    assert result.winners == frozenset(range(4))
