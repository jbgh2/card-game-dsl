"""Random-playout harness for Go Fish.

Go Fish is the corpus witness for declared move-parameter domains: `ask(target:
Player, rank: Rank)` is offered via a plain `offer`, enumerating the
guard-filtered Player x Rank cross-product
(docs/decisions.md "Declared parameter domains") rather than the
nullary-move-type explosion an earlier stress-branch skeleton was forced into.
Its falsifiable invariants are conservation (52 cards, always somewhere across
deck/hand/book) and termination (every hand empties or the stock runs out, and
the player with the most books wins).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GO_FISH = Path(__file__).parent.parent / "docs" / "games" / "go-fish.cardlang"


def _go_fish() -> n.Game:
    return check_source(GO_FISH)


def test_go_fish_checks_clean() -> None:
    _go_fish()  # parse -> resolve -> typecheck -> deck-capacity; must not raise


@pytest.mark.parametrize("seed", range(30))
def test_go_fish_plays_to_completion(seed: int) -> None:
    game = _go_fish()
    census: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            census.update(data)

    result = play_game(game, random.Random(seed), tracer)

    # A "most books wins" game: a winner, never an elimination loser.
    assert result.loser is None
    assert result.winner is not None
    assert set(result.scores) == set(range(game.players.low))
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])

    # Card conservation: every one of the 52 cards is still somewhere (stock,
    # a hand, or a shown-and-set-aside book) — none lost or duplicated.
    assert census["total"] == 52, f"seed {seed}: {census}"

    # At most 13 books can ever be completed (one per rank; a rank's four
    # cards can be split across hands/deck without ever completing a book).
    assert sum(result.scores.values()) <= 13, f"seed {seed}: {result.scores}"


def test_asks_actually_complete_books() -> None:
    # Termination and card conservation alone would hold even if `ask`'s
    # give-all-matching / go-fish-and-match branches were both dead (e.g. a
    # guard bug that always missed) — the game would still empty a hand or
    # drain the stock with zero books ever formed. Prove the mechanic this
    # game exists to witness actually fires: aggregate books formed across a
    # seed sweep (not a single seed, which can legitimately end at 0 on a
    # short game — seed 0 does) is reliably positive.
    game = _go_fish()
    total_books = sum(
        sum(play_game(game, random.Random(seed)).scores.values())
        for seed in range(30)
    )
    assert total_books > 0
