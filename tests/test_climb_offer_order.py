"""An enumerated climb engine offers its candidates in action-id order.

property:        At every ask of a climbing round whose engine serves an
                 enumerated play universe, the plays offered are in strictly
                 increasing combo-block id order, with the pass after them,
                 and each moves its cards in card-id order. The
                 random chooser samples the candidate list, so the per-seed
                 goldens pin this order; holding it to the ids makes a
                 candidate list a function of the plays it holds, never of how
                 an engine generated them.
domain:          Every climb engine in `PRIMITIVE_CLIMB_ENGINES` whose
                 `climb_codec_function` is None, each played in the corpus game
                 whose round names its lead query, at every ask of the seeds
                 below.
registry:        `cardlang.builtins.functions.PRIMITIVE_CLIMB_ENGINES`;
                 `cardlang.runtime.primitives.climb_codec_function`.
held by:         a single owner of the order, `primitives.action_order`, which
                 the encoder numbers the universe by and each enumerated engine
                 sorts its candidates by (`primitives.action_rank`); this module
                 is a Pin over the engines' use of it, and of
                 `primitives.in_card_order`. Reddening mutation: drop
                 `_in_action_order` from either query of either engine.
does not prove:  Anything about a codec engine (Tichu), whose candidates keep
                 the engine's own order; nor that the offered plays are the
                 legal ones (tests/test_bigtwo_combinations.py,
                 tests/test_playout_president.py).
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

import pytest

from cardlang.builtins.functions import PRIMITIVE_CLIMB_ENGINES
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_source
from cardlang.runtime import driver, mechanics, primitives

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
_SLOT = re.compile(r"combinations\s+(\w+)\s+follows\s+(\w+)")
_SEEDS = range(3)

ENUMERATED = sorted(
    lead for lead in PRIMITIVE_CLIMB_ENGINES if primitives.climb_codec_function(lead) is None
)


def _game_for(lead: str) -> Path:
    for path in sorted(GAMES.glob("*.cardlang")):
        m = _SLOT.search(path.read_text())
        if m and m.group(1) == lead:
            return path
    raise AssertionError(f"no corpus game names climb lead query {lead!r}")


def test_the_domain_is_not_empty() -> None:
    """The enumerated engines exist, so the parametrized pin below asks
    something."""
    assert ENUMERATED


@pytest.mark.parametrize("lead", ENUMERATED)
def test_an_enumerated_engine_offers_its_plays_in_action_id_order(
    lead: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = check_source(str(_game_for(lead)))
    space = ActionSpace.for_game(game)
    orig = mechanics.ClimbForm.candidates
    asks = 0

    def candidates(self: mechanics.ClimbForm, actor: Any, state: Any, ctx: Any) -> list[Any]:
        nonlocal asks
        offered = orig(self, actor, state, ctx)
        plays = [c for c in offered if c != primitives.CLIMB_PASS]
        assert offered[: len(plays)] == plays, offered
        ids = [space.encode(p) for p in plays]
        assert ids == sorted(set(ids)), (lead, ids)
        for p in plays:
            assert tuple(p.cards) == primitives.in_card_order(p.cards), (lead, p)
        asks += 1
        return offered

    monkeypatch.setattr(mechanics.ClimbForm, "candidates", candidates)
    for seed in _SEEDS:
        driver.play_game(game, random.Random(seed))
    assert asks > 0
