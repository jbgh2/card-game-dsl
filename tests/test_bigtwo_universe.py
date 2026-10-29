"""The Big Two play universe: every play its catalogue names over the deck,
unique by card-set — the combination action space (SP1 spec, Pillar 2)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.resolve import _walk
from cardlang.runtime import declared
from cardlang.runtime.values import RANKS, SUITS, Card, Combination
from tests import climb_asks

GOLDEN = Path(__file__).resolve().parent / "golden" / "bigtwo_universe_count.json"
BIG_TWO = Path(__file__).resolve().parent.parent / "docs" / "games" / "big-two.cardlang"


def _universe() -> list[Combination]:
    game = check_source(str(BIG_TWO))
    (engine,) = {nd.engine for nd in _walk(game) if isinstance(nd, n.ClimbRound)}
    assert isinstance(engine, n.DeclaredEngine)
    return list(declared.game_universe(game, engine).plays)


def test_universe_size_is_pinned_and_card_sets_unique() -> None:
    plays = _universe()
    sets = {frozenset(p.cards) for p in plays}
    assert len(sets) == len(plays)  # card-set decodes to exactly one play
    expected = json.loads(GOLDEN.read_text())["count"]
    assert len(plays) == expected


def test_universe_composition_by_shape() -> None:
    by_shape: dict[str, int] = {}
    for p in _universe():
        by_shape[p.shape] = by_shape.get(p.shape, 0) + 1
    assert by_shape["single"] == 52
    assert by_shape["pair"] == 13 * 6
    assert by_shape["triple"] == 13 * 4
    assert by_shape["straight_flush"] == 10 * 4
    assert by_shape["straight"] == 10 * (4**5 - 4)
    assert by_shape["flush"] == 4 * (1287 - 10)
    assert by_shape["full_house"] == 13 * 12 * 4 * 6
    assert by_shape["quads"] == 13 * 48


def test_universe_covers_every_reachable_play() -> None:
    universe = {frozenset(p.cards): p.shape for p in _universe()}
    ask = climb_asks.asker(BIG_TWO, opened=True)
    deck = [Card(r, s) for s in SUITS for r in RANKS]
    rng = random.Random(0)
    for _ in range(300):
        hand = rng.sample(deck, 13)
        for play in ask(hand, None, ()):
            key = frozenset(play.cards)
            assert key in universe, f"unreachable in universe: {play}"
            assert universe[key] == play.shape
