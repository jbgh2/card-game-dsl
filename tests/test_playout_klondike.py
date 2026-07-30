"""Random-playout harness for Klondike.

Klondike is the corpus witness for position domains (decisions.md "Position
domains and positional zones"): seven tableau columns as position-indexed
zone families, each column a HiddenStack under a Cascade, with the flip an
ordinary kernel movement. Its falsifiable invariants are structural, checked
at EVERY decision point of a resign-averse playout:

- the run invariant — every face-up cascade is a strictly-descending,
  alternating-color sequence (what makes the rank-filter run move denote
  the suffix);
- the flip invariant — a column's face-up part is empty only when its
  face-down part is too (what makes `tableau_up[c] is empty` the whole
  emptiness test);
- foundations ascend contiguously from the ace in their fixed suit;
- conservation — 52 cards, always, across stock/waste/columns/foundations.

Plain random playouts terminate fast (resign is one of few candidates every
turn); the resign-averse chooser defers resigning until a decision budget is
spent, driving deep lines (hundreds of moves, redeals included) so the
invariants are exercised where they could actually break.
"""

from __future__ import annotations

import itertools
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

KLONDIKE = Path(__file__).parent.parent / "docs" / "games" / "klondike.cardlang"

_RED = {"hearts", "diamonds"}
_FOUNDATION_SUIT = {1: "clubs", 2: "diamonds", 3: "hearts", 4: "spades"}
# aces-low scale, matching the game's `ranking: aces low` (A=0 .. K=12).
_RANKV = {r: i for i, r in enumerate(["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"])}


def _klondike() -> n.Game:
    return check_source(KLONDIKE)


def test_klondike_checks_clean() -> None:
    _klondike()  # parse -> resolve -> typecheck -> deck-capacity; must not raise


def _check_invariants(rs: RuntimeState) -> None:
    total = len(rs.zones.single("deck").cards) + len(rs.zones.single("waste").cards)
    for c in range(1, 8):
        up = rs.zones.instance("tableau_up", c).cards
        down = rs.zones.instance("tableau_down", c).cards
        total += len(up) + len(down)
        if not up:
            assert not down, f"flip invariant broken at column {c}: {len(down)} face-down under an empty run"
        for a, b in itertools.pairwise(up):
            assert _RANKV[b.rank] == _RANKV[a.rank] - 1, f"run not descending at column {c}: {up}"
            assert (a.suit in _RED) != (b.suit in _RED), f"run not alternating at column {c}: {up}"
    for f in range(1, 5):
        pile = rs.zones.instance("foundation", f).cards
        total += len(pile)
        for i, card in enumerate(pile):
            assert card.suit == _FOUNDATION_SUIT[f], f"foundation {f} holds {card}"
            assert _RANKV[card.rank] == i, f"foundation {f} out of order: {pile}"
    assert total == 52, f"conservation broken: {total} cards"


def _resign_averse_playout(seed: int, budget: int = 400) -> int:
    """Play one game, checking every invariant at every decision point.
    Returns the final score (cards sent home)."""
    game = _klondike()
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
    assert result.winner == 0  # the sole player
    assert set(result.scores) == {0}
    assert 0 <= result.scores[0] <= 52
    return result.scores[0]


@pytest.mark.parametrize("seed", range(15))
def test_klondike_deep_playout_invariants(seed: int) -> None:
    _resign_averse_playout(seed)


@pytest.mark.parametrize("seed", range(15))
def test_klondike_plays_to_completion_under_pure_random(seed: int) -> None:
    """Plain random play (resign among the candidates): terminates well under
    max_length, conserves the deck, and produces the 1-player result shape."""
    game = _klondike()
    census: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            census.update(data)

    result = play_game(game, random.Random(seed), tracer)
    assert census["total"] == 52
    assert result.winner == 0 and result.loser is None
    assert 0 <= result.scores[0] <= 52


def test_klondike_random_play_reaches_real_progress() -> None:
    """Not vacuous: across seeds, the resign-averse line sends a meaningful
    number of cards home (a semantics bug that silently outlawed foundation
    moves would zero this)."""
    best = max(_resign_averse_playout(seed) for seed in range(10))
    assert best >= 10, f"best score over 10 seeds was only {best}"
