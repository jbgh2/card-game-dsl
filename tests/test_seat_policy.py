"""The Seat Policy type, and the uniform policy that fills a seat nobody takes.

property:        A Seat Policy is handed a Seat View and the legal action ids and
                 answers an action id, and nothing else is in its signature. The
                 uniform policy holds its seed and nothing else; it answers one of
                 the legal ids, the same one for the same seed and view whatever
                 the process's hash seed, spread over the ids rather than stuck on
                 one, and a different seed moves its answers even in a game that
                 deals nothing.
domain:          The signature: `SeatPolicy.__call__`. The answers: every ask of a
                 uniform line in every registered game up to `_LAST` picks. The
                 seed's reach: every Chance-Free Game in the registry, two seeds.
                 The hash seed: two interpreter processes over one game's line.
registry:        policies: `cardlang.openspiel.seat_policy`; games:
                 `cardlang.openspiel.registry.GAMES`, split by
                 `cardlang.openspiel.replay.chance_free`; the lines:
                 tests/test_live_line.py.
does not prove:  That a uniform answer is uniform. The draw is a hash of the seed
                 and the view's information state, so one seed answers one view
                 one way: a seeded pure strategy, varied by varying the seed.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import get_type_hints

import pytest

from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, chance_free, load
from cardlang.openspiel.seat_policy import SeatPolicy, UniformSeatPolicy
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.state import IllegalMove
from tests.test_migration_characterization import _HASHSEEDS, _capture_under_hashseed

REPO = Path(__file__).parent.parent
GAMES_DIR = REPO / "docs" / "games"

_LAST = 144


def _path(short_name: str) -> str:
    return str(GAMES_DIR / GAMES[short_name])


class _Enough(Exception):
    """The line has run as far as the cell needs."""


def _line(short_name: str, seed: int, last: int = _LAST) -> tuple[list[int], list[tuple[SeatView, tuple[int, ...], int]]]:
    """A uniform line of `short_name` under `seed`, and every ask it made."""
    path = _path(short_name)
    game, _ = load(path)
    line = LiveLine(path, seed)
    asks: list[tuple[SeatView, tuple[int, ...], int]] = []
    uniform = UniformSeatPolicy(seed)

    def ask(view: SeatView, legal: Sequence[int]) -> int:
        if len(line.history) > last:
            raise _Enough
        answer = uniform(view, legal)
        asks.append((view, tuple(legal), answer))
        return answer

    try:
        line.play({seat: ask for seat in range(game.players.count)})
    except (_Enough, GameDescriptionError, IllegalMove):
        pass
    return line.history, asks


def test_a_seat_policy_is_handed_a_seat_view_and_legal_ids_and_answers_an_id() -> None:
    """red under: widen `SeatPolicy.__call__` with a parameter a policy could
    read the World through."""
    assert get_type_hints(SeatPolicy.__call__) == {
        "view": SeatView,
        "legal": Sequence[int],
        "return": int,
    }


def test_the_uniform_policy_holds_its_seed_and_nothing_else() -> None:
    """A policy holding a random stream answers differently after an undo.

    red under: give `UniformSeatPolicy` a `random.Random` attribute."""
    assert vars(UniformSeatPolicy(3)) == {"seed": 3}


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_the_uniform_policy_answers_a_legal_id_the_same_way_for_the_same_view(short_name: str) -> None:
    _, asks = _line(short_name, 0)
    assert asks
    again = UniformSeatPolicy(0)
    for view, legal, answer in asks:
        assert answer in legal
        assert again(view, legal) == answer


def test_the_uniform_policy_spreads_its_answers_over_the_legal_ids() -> None:
    """red under: answer `legal[0]`."""
    _, asks = _line("cardlang_hearts", 0)
    choices = [(legal, answer) for _, legal, answer in asks if len(legal) > 1]
    assert len(choices) > 40
    firsts = sum(1 for legal, answer in choices if answer == legal[0])
    assert firsts < len(choices) // 2


@pytest.mark.parametrize(
    "short_name", sorted(name for name in GAMES if chance_free(_path(name)))
)
def test_a_different_seed_moves_the_uniform_line_of_a_game_that_deals_nothing(short_name: str) -> None:
    """A seed that reaches no shuffle still reaches the seats a uniform draw
    fills, so it is never a flag that changes nothing."""
    assert _line(short_name, 0)[0] != _line(short_name, 1)[0]


# Argument 1 is a registered game's short name, argument 2 how many picks the
# line takes; the line's picks are printed.
_LINE_SCRIPT = """
import sys
from pathlib import Path
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, load
from cardlang.openspiel.seat_policy import UniformSeatPolicy
path = str(Path("docs/games") / GAMES[sys.argv[1]])
last = int(sys.argv[2])
line = LiveLine(path, 3)
class Enough(Exception):
    pass
uniform = UniformSeatPolicy(3)
def ask(view, legal):
    if len(line.history) >= last:
        raise Enough
    return uniform(view, legal)
try:
    line.play({seat: ask for seat in range(load(path)[0].players.count)})
except Enough:
    pass
print(line.history)
"""


def test_a_uniform_line_is_the_same_under_every_hash_seed() -> None:
    """Python salts `hash` per process; a draw keyed on it would give a saved
    line other opponents when it is resumed. The two runs go through the one
    helper that may set the hash seed.

    red under: key the uniform draw on `hash` of the view's information state."""
    printed = [
        _capture_under_hashseed("cardlang_hearts", 40, hash_seed, _LINE_SCRIPT)
        for hash_seed in _HASHSEEDS
    ]
    assert printed[0] == printed[1] and printed[0].strip() != "[]"
