"""The information state's rendered FORM, pinned byte-for-byte.

property:        Every corpus game's first decision renders, for every seat,
                 the exact string this module's golden holds — so a change to
                 how the information state is assembled is visible as a diff
                 rather than as a suite that stays green because it only ever
                 asked questions the new form also answers.
domain:          Every game in the adapter registry (`GAMES`, derived from
                 `docs/games/*.cardlang` by glob), at seed 0, at the first
                 decision `replay.run` reaches, crossed with every seat that
                 game seats. The first decision is the position chosen because
                 it is the one every game has: a game whose whole line is
                 chance-driven still pauses there, and a later position would
                 be reachable for some games and not others, which would make
                 the domain the games' shapes rather than the registry.
registry:        games: `cardlang.openspiel.registry.GAMES`; the golden:
                 `tests/golden/infostate_format.json`, regenerated with
                 `CARDLANG_UPDATE_INFOSTATE_GOLDEN=1`; the projection
                 semantics this form renders, and the value-shape dispatch it
                 leans on:
                 tests/test_openspiel_infostate.py::test_render_covers_the_declared_value_shapes_and_refuses_the_rest.
does not prove:  Nothing about whether the form is the RIGHT one. Every string
                 here was captured from the tree rather than designed, so a
                 form that is wrong in the same way for every game is pinned
                 exactly as faithfully as a correct one. What a green means is
                 that the form has not MOVED. It equally says nothing about
                 positions past the first decision: a change that altered only
                 how a later position renders would not be seen here, and the
                 per-observer proofs under `tests/openspiel_ready/` are where
                 mid-line information states are exercised.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import DecisionNode, TerminalNode, run

REPO = Path(__file__).parent.parent
GAMES_DIR = REPO / "docs" / "games"
GOLDEN = REPO / "tests" / "golden" / "infostate_format.json"

# The seed every capture uses. One seed, because the claim is about the FORM
# and not about any game's line: a second seed would multiply the golden
# without crossing a new branch of the renderer.
SEED = 0


def _capture() -> dict[str, list[str]]:
    """Every registered game's first decision, as each seat sees it."""
    out: dict[str, list[str]] = {}
    for short_name, file_name in sorted(GAMES.items()):
        node = run(str(GAMES_DIR / file_name), SEED, ())
        if isinstance(node, TerminalNode):
            # A game that reaches its end with nobody asked to choose has no
            # decision to render, and says so here rather than being absent
            # from the golden — an absent key and a game that stopped being
            # captured are the same silence.
            out[short_name] = []
            continue
        assert isinstance(node, DecisionNode)
        out[short_name] = [
            information_state(seat, node.rs, node.obs_logs[seat])
            for seat in sorted(node.obs_logs)
        ]
    return out


def test_the_rendered_information_state_has_not_moved() -> None:
    """The golden is a characterization vector: it says what the form IS, and
    a diff here is a change to the form, never on its own a defect.

    Regenerate deliberately, with the reason in the commit message:

        CARDLANG_UPDATE_INFOSTATE_GOLDEN=1 pytest tests/test_infostate_format.py

    red under: change any separator in
    `cardlang.openspiel.infostate.information_state` — the `|` between
    segments, the `;` between zones, or the `=` in a zone label.
    """
    captured = _capture()
    if os.environ.get("CARDLANG_UPDATE_INFOSTATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(captured, indent=2, sort_keys=True) + "\n")
        pytest.skip("golden regenerated")
    expected = json.loads(GOLDEN.read_text())
    assert captured == expected


def test_the_golden_covers_every_registered_game() -> None:
    """The golden's keys and the registry's name the same games, so a game
    added to the corpus arrives as a missing key rather than as a game the
    format pin silently stopped covering."""
    expected = json.loads(GOLDEN.read_text())
    assert set(expected) == set(GAMES), (
        "the adapter registry and this golden have drifted; regenerate with "
        "CARDLANG_UPDATE_INFOSTATE_GOLDEN=1 and review the new game's strings"
    )


def test_the_renderer_needs_no_world() -> None:
    """The information state is a function of derived facts, and this is the
    test that would stop being writable if it were not.

    It constructs the seat's facts directly and renders them, touching no
    `RuntimeState` at all. A renderer that reached back into the live world
    for anything — a zone it was not handed, a state variable, the seating —
    could not be called from here, so this fails to import or fails to run
    rather than failing an assertion.

    red under: give `render_information_state` a parameter it can only get
    from the world, or read one inside it.
    """
    from cardlang.openspiel.infostate import SeatView, render_information_state

    view = SeatView(
        player=1,
        zones=(("hand[1]", ("5 of clubs",)), ("hand[0]", 3), ("muck", None)),
        state=(("score", {0: 10, 1: 20}),),
        obs_log=(("chose", ("5 of clubs",)),),
    )
    rendered = render_information_state(view)
    assert rendered.startswith("P1|")
    assert "hand[1]=[5 of clubs]" in rendered
    assert "hand[0]=#3" in rendered
    assert "muck=?" in rendered
    assert "state:score={0:10,1:20}" in rendered
    assert "obs:" in rendered
