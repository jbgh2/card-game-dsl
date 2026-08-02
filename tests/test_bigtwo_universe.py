"""The Big Two play universe: a superset of every reachable representative,
unique by card-set — the combination action space (SP1 spec, Pillar 2)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from cardlang.runtime.bigtwo import _combos, bigtwo_universe
from cardlang.runtime.primitives import climb_universe_function
from cardlang.runtime.values import RANKS, SUITS, Card

GOLDEN = Path(__file__).resolve().parent / "golden" / "bigtwo_universe_count.json"


def test_universe_size_is_pinned_and_card_sets_unique() -> None:
    plays = bigtwo_universe()
    sets = {frozenset(p.cards) for p in plays}
    assert len(sets) == len(plays)  # card-set decodes to exactly one play
    expected = json.loads(GOLDEN.read_text())["count"]
    assert len(plays) == expected


def test_universe_composition_by_kind() -> None:
    plays = bigtwo_universe()
    by_kind: dict[str, int] = {}
    for p in plays:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
    assert by_kind["single"] == 52
    assert by_kind["pair"] == 13 * 6
    assert by_kind["triple"] == 13 * 4
    assert by_kind["straightflush"] == 10 * 4
    assert by_kind["straight"] == 10 * (4**5 - 4)
    assert by_kind["flush"] == 4 * (1287 - 10)
    assert by_kind["fullhouse"] == 13 * 12 * 4 * 6
    assert by_kind["quads"] == 13 * 48


def test_universe_covers_every_reachable_representative() -> None:
    universe = {frozenset(p.cards): p.kind for p in bigtwo_universe()}
    deck = [Card(r, s) for s in SUITS for r in RANKS]
    rng = random.Random(0)
    for _ in range(300):
        hand = rng.sample(deck, 13)
        for play in _combos(hand):
            key = frozenset(play.cards)
            assert key in universe, f"unreachable in universe: {play}"
            assert universe[key] == play.kind


def test_stdlib_registry_resolves_by_combos_query_name() -> None:
    fn = climb_universe_function("bigtwo_lead_options")
    assert len(fn()) == len(bigtwo_universe())
