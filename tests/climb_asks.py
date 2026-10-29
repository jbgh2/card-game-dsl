"""A climbing game's Declared Engine, asked about hands a test builds, and
the smallest catalogue a probe game's climbing round can name.

`asker` plays the game file to its first climb ask and holds that ask's
engine and context, so a test asks the engine what it offers a hand against
a standing play it names, with the trick pile holding what the test lays
there: the live tables (the game's state, its `ranking:`, its follows
function) answer, never a copy of them.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime import driver, mechanics
from cardlang.runtime.values import Card, Combination

# A catalogue of singles and pairs that follow by size and rank strength, and
# the round slot naming it: what a probe game's climbing round plays when the
# probe is about the form, not about what its plays are. Appended after the
# probe's `game { }` block; it reads the probe's `ranking:`.
SETS_CATALOGUE = """
combinations sets {
  single: 1 card
  pair:   2 of a kind
}

function beats(play : Combination, standing : Combination?) =
  standing is none
  or ((number of cards in play) is (number of cards in standing)
      and (highest rank_value(card) over cards in play or 0)
          > (highest rank_value(card) over cards in standing or 0))
"""
SETS_SLOTS = "combinations sets follows beats"
# The catalogue for a probe spelled as a `str.format` template.
SETS_CATALOGUE_TEMPLATE = SETS_CATALOGUE.replace("{", "{{").replace("}", "}}")

Ask = Callable[[Sequence[Card], Combination | None, Sequence[Card]], list[Combination]]


class _Stop(Exception):
    pass


def asker(path: Path, **values: Any) -> Ask:
    """The engine's offer for a hand against a standing play (None at a
    lead) with the trick pile holding the given cards, each state variable
    named set as given."""
    found: list[tuple[mechanics.ClimbForm, Any]] = []
    orig = mechanics.ClimbForm.candidates

    def stop(self: mechanics.ClimbForm, actor: Any, state: Any, ctx: Any) -> list[Any]:
        found.append((self, ctx))
        raise _Stop

    mechanics.ClimbForm.candidates = stop  # type: ignore[method-assign]
    try:
        driver.play_game(check_source(str(path)), random.Random(0))
    except _Stop:
        pass
    finally:
        mechanics.ClimbForm.candidates = orig  # type: ignore[method-assign]
    (form, ctx), *_ = found
    engine = form.declared
    assert engine is not None, f"{path.name} plays no catalogue"
    for name, value in values.items():
        ctx.rs.set(name, value)

    def ask(hand: Sequence[Card], standing: Combination | None, pile: Sequence[Card] = ()) -> list[Combination]:
        form.pile.cards[:] = list(pile)
        return engine.candidates(hand, standing, ctx)

    return ask
