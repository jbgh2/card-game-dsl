"""A seat's view as text, pinned byte for byte.

property:        Every registered game's first decision renders, for every seat,
                 the exact text this module's golden holds, so a change to how
                 the text is arranged shows as a diff rather than as a suite
                 that stays green because it only asks whether each fact is
                 present.
domain:          Every game in the adapter registry (`GAMES`), at seed 0, at
                 the first decision `replay.run` reaches, for every seat that
                 game seats, with the turn line on the seat that decides there.
                 The first decision is the one position every game has.
registry:        games: `cardlang.openspiel.registry.GAMES`; the golden:
                 `tests/golden/play_view_format.json`, regenerated with
                 `CARDLANG_UPDATE_PLAY_VIEW_GOLDEN=1`; what the text must show:
                 tests/test_play_view.py.
does not prove:  That the arrangement is the right one: every text here was
                 captured from the tree, so an arrangement wrong the same way
                 for every game is pinned as faithfully as a good one. Nothing
                 past the first decision is pinned, and the position is the
                 adapter's decision node, whose world has unwound past every
                 phase frame, so a phase-local state variable never appears in
                 these texts (issue #612) — tests/test_play_view.py probes the
                 text where those variables stand.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cardlang.openspiel.infostate import derive
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import DecisionNode, TerminalNode, load, run
from cardlang.play.view import render_view

REPO = Path(__file__).parent.parent
GAMES_DIR = REPO / "docs" / "games"
GOLDEN = REPO / "tests" / "golden" / "play_view_format.json"

SEED = 0


def _capture() -> dict[str, list[str]]:
    """Every registered game's first decision, as each seat reads it."""
    out: dict[str, list[str]] = {}
    for short_name, file_name in sorted(GAMES.items()):
        path = str(GAMES_DIR / file_name)
        node = run(path, SEED, ())
        if isinstance(node, TerminalNode):
            out[short_name] = []
            continue
        assert isinstance(node, DecisionNode)
        game, _ = load(path)
        out[short_name] = [
            render_view(
                game,
                derive(seat, node.rs, node.obs_logs[seat]),
                your_turn=seat == node.player,
            )
            for seat in sorted(node.obs_logs)
        ]
    return out


def test_the_rendered_view_has_not_moved() -> None:
    """A characterization vector: a diff here is a change to the text, never
    on its own a defect. Regenerate deliberately, with the reason in the
    commit message:

        CARDLANG_UPDATE_PLAY_VIEW_GOLDEN=1 pytest tests/test_play_view_format.py
    """
    captured = _capture()
    if os.environ.get("CARDLANG_UPDATE_PLAY_VIEW_GOLDEN"):
        GOLDEN.write_text(json.dumps(captured, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        pytest.skip("golden regenerated")
    assert captured == json.loads(GOLDEN.read_text())


def test_the_golden_covers_every_registered_game() -> None:
    assert set(json.loads(GOLDEN.read_text())) == set(GAMES), (
        "the adapter registry and this golden have drifted; regenerate with "
        "CARDLANG_UPDATE_PLAY_VIEW_GOLDEN=1 and read the new game's texts"
    )
