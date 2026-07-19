"""Random-playout harness for FreeCell.

FreeCell is the perfect-information half of the positional-zone pair
(decisions.md "Position domains and positional zones"): the same position
machinery as Klondike with no hidden zone anywhere. Its falsifiable
invariants, checked at EVERY decision point of a resign-averse playout:

- every free cell holds at most one card (only `to_cell` fills one, guarded
  on emptiness);
- the deck is empty after the deal (all 52 face up — the perfect-information
  premise the proof module builds on);
- foundations ascend contiguously from the ace in their fixed suit;
- conservation — 52 cards across cascades/cells/foundations.

Cascades are NOT run-checked here, deliberately: unlike Klondike, a FreeCell
cascade's dealt base is arbitrary (7 face-up cards in any order), so only
the cards ADDED by builds obey descending/alternating — which the build
guards enforce per move and the foundation progress test exercises.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

FREECELL = Path(__file__).parent.parent / "docs" / "games" / "freecell.cardlang"

_FOUNDATION_SUIT = {1: "clubs", 2: "diamonds", 3: "hearts", 4: "spades"}
_RANKV = {r: i for i, r in enumerate(["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"])}


def _freecell() -> n.Game:
    return check_source(FREECELL)


def test_freecell_checks_clean() -> None:
    _freecell()  # parse -> resolve -> typecheck -> deck-capacity; must not raise


def _check_invariants(rs: RuntimeState) -> None:
    assert not rs.zones.single("deck").cards, "the deal must empty the deck"
    total = 0
    for c in range(1, 9):
        total += len(rs.zones.instance("cascade", c).cards)
    for s in range(1, 5):
        cell = rs.zones.instance("cells", s).cards
        assert len(cell) <= 1, f"cell {s} holds {len(cell)} cards"
        total += len(cell)
    for f in range(1, 5):
        pile = rs.zones.instance("foundation", f).cards
        total += len(pile)
        for i, card in enumerate(pile):
            assert card.suit == _FOUNDATION_SUIT[f], f"foundation {f} holds {card}"
            assert _RANKV[card.rank] == i, f"foundation {f} out of order: {pile}"
    assert total == 52, f"conservation broken: {total} cards"


def _resign_averse_playout(seed: int, budget: int = 400) -> int:
    game = _freecell()
    rng = random.Random(seed)
    decisions = [0]
    rs_ref: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        if "rs" in rs_ref:
            _check_invariants(rs_ref["rs"])
        decisions[0] += k
        live = [c for c in candidates if not (isinstance(c, tuple) and c[0] == "resign")]
        if decisions[0] > budget or not live:
            resigns = [c for c in candidates if isinstance(c, tuple) and c[0] == "resign"]
            assert resigns, "resign must always be offered"
            return [resigns[0]]
        return [rng.choice(live)]

    result = play_game(
        game,
        rng,
        chooser=chooser,
        on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
    )
    _check_invariants(rs_ref["rs"])
    assert result.loser is None
    assert result.winner == 0
    assert set(result.scores) == {0}
    assert 0 <= result.scores[0] <= 52
    return result.scores[0]


@pytest.mark.parametrize("seed", range(15))
def test_freecell_deep_playout_invariants(seed: int) -> None:
    _resign_averse_playout(seed)


@pytest.mark.parametrize("seed", range(15))
def test_freecell_plays_to_completion_under_pure_random(seed: int) -> None:
    game = _freecell()
    census: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            census.update(data)

    result = play_game(game, random.Random(seed), tracer)
    assert census["total"] == 52
    assert result.winner == 0 and result.loser is None
    assert 0 <= result.scores[0] <= 52


def test_freecell_random_play_reaches_real_progress() -> None:
    """Not vacuous: some seed sends several cards home under random play (a
    guard bug outlawing foundation moves would zero this)."""
    best = max(_resign_averse_playout(seed) for seed in range(10))
    assert best >= 4, f"best score over 10 seeds was only {best}"
