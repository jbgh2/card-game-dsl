"""The opponent that plays by what a game declares: `--vs all=ranked`.

property:        `ranked` answers from its seat's view and the game's own
                 declarations, and states what it does with every block of
                 action ids the game's action space declares. At a card
                 decision it plays to take the trick with the cheapest card
                 that takes it, or sheds its cheapest, by the declared ranking
                 and the direction the game's `winner:` names; at a numeric
                 decision it answers near its hand's strength; at a
                 combination decision it spends the fewest cards; at every
                 other id it draws uniformly, which the table states rather
                 than leaves to be noticed. Where a position has a best line
                 it plays one. Seated at a table it reaches an outcome a
                 uniform draw does not: Spades' +500, which a uniform table
                 never scores.
domain:          Dispositions: every block `encoding.BLOCKS` declares, crossed
                 with what `ranked.DISPOSITIONS` says of it. The solved
                 position: `tests/fixtures/one_trick_known_best.cardlang`, its
                 whole game tree enumerated for the ranked seat over `_SEEDS`.
                 The measured claims: `_MEASURED`, one line per seed per game,
                 each against the uniform table over the same seeds. The
                 delegated block: an offering decision compared against the
                 uniform draw it delegates to. Legality and purity over every
                 registered game come from the row pins in
                 tests/test_play_opponents.py, which `ranked` joins as a row.
registry:        blocks: `cardlang.openspiel.encoding.BLOCKS`; opponents:
                 `cardlang.openspiel.seat_policy.OPPONENTS`; games:
                 `cardlang.openspiel.registry.GAMES`; the declarations it
                 reads: the checked `n.Game` (`ranking`, `trick_order`,
                 `trump`, `winner`), and `stdlib.zones.ZONE_PROJECTIONS` for
                 which of its own zones are private to it.
does not prove:  That `ranked` plays a game well. It reads no game's own
                 strategy: it ignores partners, position, what has already been
                 played, and every state variable, and it draws uniformly at
                 every offering — so a game whose decisions are offerings is
                 played as a uniform draw plays it, Tichu's calls included
                 (issue #703, and the wall issue #553 leaves standing). A game
                 that declares no ranking has nothing here to rank by, and the
                 disposition says so rather than pretending otherwise. Nothing
                 here measures it against a competent player; the claims are
                 all against a uniform draw.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from cardlang.openspiel.encoding import BLOCKS
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.ranked import DISPOSITIONS, RankedSeatPolicy
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, load
from cardlang.openspiel.seat_policy import OPPONENTS, FirstSeatPolicy, SeatBinding, UniformSeatPolicy
from cardlang.runtime.errors import GameDescriptionError
from tests.test_play_session import FIXTURES, _path

_SEED = 5
MINIATURE = str(FIXTURES / "one_trick_known_best.cardlang")


def _seated(path: str, name: str, seats: Sequence[int], seed: int) -> dict[int, object]:
    """`name` at each of `seats`, `random` at the rest."""
    game, space = load(path)
    rows = {seat: OPPONENTS[name if seat in seats else "random"] for seat in range(game.players.low)}
    return {
        seat: row.make(SeatBinding(game, space, seat, seed)) for seat, row in rows.items()
    }


# ---------------------------------------------------------------------------
# What it says it does.
# ---------------------------------------------------------------------------


def test_every_block_of_action_ids_has_a_disposition() -> None:
    """The closed domain is the action space's own blocks: a block with no
    disposition would be drawn uniformly with nobody having said so.

    red under: add a block to `encoding.BLOCKS` without a row here."""
    assert set(DISPOSITIONS) == set(BLOCKS), "decide what `ranked` does with each block"
    assert set(DISPOSITIONS.values()) <= {"ranked", "delegated"}


def test_the_opponent_names_no_game() -> None:
    """A ranker keyed on one game's move type is a per-game branch (CLAUDE.md).

    red under: rank `call_tichu` by name."""
    source = Path("cardlang/openspiel/ranked.py").read_text()
    for short_name, file_name in GAMES.items():
        stem = file_name.removesuffix(".cardlang")
        assert stem not in source and short_name not in source, f"{stem} is named in the source"
    assert "RuntimeState" not in source, "a Seat Policy reads the view, never the world"


# ---------------------------------------------------------------------------
# A position whose best line is computed, not assumed.
# ---------------------------------------------------------------------------

_SEEDS = tuple(range(24))


def _tricks(name: str, seed: int) -> float:
    """What `name` takes at seat 1 against `first` at seat 0, in one line."""
    game, space = load(MINIATURE)
    policy = OPPONENTS[name].make(SeatBinding(game, space, 1, seed))
    return LiveLine(MINIATURE, seed).play({0: FirstSeatPolicy(), 1: policy}).returns[1]


def test_the_ranked_seat_takes_more_tricks_than_either_baseline() -> None:
    """Three tricks, two seats, and the lead passing to whoever took the last:
    a position small enough that the trick logic is the only thing being
    measured, since no library decides anything here.

    The comparison is against the other opponents at the same seat over the
    same seeds, not against the best line the position allows: that best line
    is computed knowing the hidden hand, which no seat can know.

    red under: answer `legal[-1]` at a card decision, or read the direction as
    `lowest` whatever the game declares."""
    took = {name: sum(_tricks(name, seed) for seed in _SEEDS) for name in ("ranked", "first", "random")}
    assert took["ranked"] > took["first"] and took["ranked"] > took["random"], took
    assert took["first"] and took["random"], f"a baseline took nothing, so the cell compares little: {took}"


# ---------------------------------------------------------------------------
# What it reaches at a table.
# ---------------------------------------------------------------------------

# Games whose card play decides the score: the seeds each claim is measured
# over, and the floor it must clear. Measured 2026-09-15 on this branch: a
# ranked table reached Spades' +500 on 12 of 12 seeds and a uniform table on
# none; a ranked seat beat the uniform average at Hearts on 12 of 16.
_SPADES_SEEDS, _SPADES_FLOOR = 12, 8
_HEARTS_SEEDS, _HEARTS_FLOOR = 16, 10


def _line(path: str, name: str, seats: Sequence[int], seed: int) -> list[float] | None:
    line = LiveLine(path, seed)
    try:
        return list(line.play(_seated(path, name, seats, seed)).returns)  # type: ignore[arg-type]
    except GameDescriptionError:
        return None


def test_a_ranked_table_reaches_the_win_a_uniform_table_never_does() -> None:
    """Spades' +500 sits behind bidding a uniform draw overbids past, which is
    the witness `tests/test_playout_spades.py` holds at the chooser level.

    red under: answer a numeric decision uniformly."""
    path = _path("cardlang_spades")
    seeds = range(_SPADES_SEEDS)
    ranked = [_line(path, "ranked", range(4), seed) for seed in seeds]
    uniform = [_line(path, "random", [], seed) for seed in seeds]
    reached = sum(1 for returns in ranked if returns is not None and max(returns) >= 500)
    by_draw = sum(1 for returns in uniform if returns is not None and max(returns) >= 500)
    assert reached >= _SPADES_FLOOR, (
        f"a ranked table reached +500 on {reached} of {_SPADES_SEEDS} seeds"
    )
    assert by_draw == 0, "a uniform table now reaches +500 — the contrast is gone"


def test_a_ranked_seat_takes_fewer_penalties_than_the_uniform_seats_beside_it() -> None:
    """Hearts wants its score LOW, and the direction is the game's own
    `winner:` clause. One ranked seat against three uniform ones, so the
    comparison is inside a line rather than across two of them.

    red under: read the direction as `highest` whatever the game declares."""
    path = _path("cardlang_hearts")
    better = 0
    for seed in range(_HEARTS_SEEDS):
        returns = _line(path, "ranked", [0], seed)
        assert returns is not None, f"seed {seed}: hearts did not reach an end"
        # `winner: lowest cumulative_score`, so a return is better when higher:
        # the returns are the game's own, already signed by the winner clause.
        better += returns[0] > sum(returns[1:]) / 3
    assert better >= _HEARTS_FLOOR, (
        f"the ranked seat beat the uniform average on {better} of {_HEARTS_SEEDS} seeds"
    )


def test_an_offering_is_the_uniform_draw_the_table_says_it_is() -> None:
    """The delegated blocks are delegated to the draw, not to something else
    that happens to be uniform-looking.

    red under: delegate to a second `random.Random` stream."""
    path = _path("cardlang_kuhn_poker")
    game, space = load(path)
    binding = SeatBinding(game, space, 1, _SEED)
    ranked = RankedSeatPolicy(binding)
    uniform = UniformSeatPolicy(_SEED)
    asked = 0

    def compare(view: SeatView, legal: Sequence[int]) -> int:
        nonlocal asked
        picked = ranked(view, legal)
        if all(space.block_of(aid) in _delegated() for aid in legal):
            assert picked == uniform(view, legal), "a delegated decision answered otherwise"
            asked += 1
        return picked

    LiveLine(path, _SEED).play({0: FirstSeatPolicy(), 1: compare})
    assert asked, "no delegated decision was reached"


def _delegated() -> set[str]:
    return {block for block, disposition in DISPOSITIONS.items() if disposition == "delegated"}


def test_the_help_and_the_table_carry_the_new_row() -> None:
    """The row joins the table, so every listing renders it (tests/test_play_opponents.py)."""
    assert "ranked" in OPPONENTS
    assert re.fullmatch(r"[a-z][a-z0-9-]*", OPPONENTS["ranked"].name)
