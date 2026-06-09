"""The steppable-adapter seam: play_game accepts an injected chooser, and a
chooser may raise ChooserAbort to suspend the playout (with the live state
attached). Default behavior (no chooser) is unchanged.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import ChooserAbort

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def test_chooser_abort_propagates_with_live_state() -> None:
    game = check_source(HEARTS)

    def aborting(player: int, candidates: list[Any], n: int) -> list[Any]:
        raise ChooserAbort(player, [c for c in candidates])

    with pytest.raises(ChooserAbort) as ei:
        play_game(game, random.Random(0), chooser=aborting)
    assert ei.value.rs is not None  # the driver attached the paused world
    assert ei.value.player in range(4)
    assert ei.value.legal  # the deciding player's candidates


def test_default_chooser_unchanged() -> None:
    game = check_source(HEARTS)
    result = play_game(game, random.Random(0))  # no chooser -> random_chooser
    assert result.winner in range(4)
