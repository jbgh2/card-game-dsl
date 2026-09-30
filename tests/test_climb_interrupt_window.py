"""The climb form's Interrupt Window, crossed over every climb engine and
every step kind a climb decision can take.

property:        after every step of a climb trick, the window the engine
                 asks is the one its registry row and the rules owe: for an
                 engine that declares an interrupt decline, every seat still
                 holding cards, from the seat after the actor round to the
                 actor itself, after each ordinary turn (a play that does not
                 end the trick, a pass, a taken interrupt, and the
                 announcement a play opens, which the play's window follows)
                 and none after a play that ends the trick or the round; for
                 an engine that declares none, no window after any step.
domain:          every lead query in `PRIMITIVE_CLIMB_LEADS`, each run through
                 the corpus game that names it, crossed with the step kinds
                 that engine's row admits: the pass and the play for every
                 engine; the announcement where `climb_announcements` names
                 tokens; and, where `climb_interrupt_decline` names a decline,
                 the pass split by whether it returns the ring to the last
                 player, the play split by the two things that close a trick
                 (the play's `ends_trick`, the round's `until`), and the taken
                 interrupt split by the `until`. A decline opens nothing: it
                 is walked inside every window, so each opener's row holds
                 it. Every `ClimbPlay` member is classified below as a step
                 kind it splits or as read by no window schedule, and the
                 classification is pinned whole against the protocol.
registry:        engines: `cardlang.builtins.functions.PRIMITIVE_CLIMB_LEADS`;
                 engine rows: `primitives.climb_interrupt_decline`,
                 `primitives.climb_announcements`; play members:
                 `primitives.ClimbPlay`; the engine's corpus game: the
                 `combinations` slot of `docs/games/*.cardlang`; the decline
                 engine's oracle: tests/test_tichu_bombs.py::_Driven.
does not prove:  that a trick ends when the rules say it must: the oracle
                 owes no window after a play it reads as ending the trick or
                 the round, so an engine that keeps such a trick open reaches
                 a ring decision this module does not object to; nor that the
                 windowless engines' playouts reach every shape their own
                 rules allow — they are uniform over a few seeds.
"""

from __future__ import annotations

import functools
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import pytest

from cardlang.builtins.functions import PRIMITIVE_CLIMB_LEADS
from cardlang.pipeline import check_source
from cardlang.runtime import primitives
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Player
from tests import test_tichu_bombs as tb

GAMES = Path(__file__).parent.parent / "docs" / "games"

# Every member of `primitives.ClimbPlay`, and what the window schedule makes
# of it: the step kind it splits, or why no schedule reads it.
PLAY_MEMBERS: dict[str, str] = {
    "kind": "identity only",
    "cards": "identity only",
    "wild": "announced beside the movement; who is asked never reads it",
    "compelled": "binds on turn only, never in the window",
    "ends_trick": tb.PLAY_ENDING_THE_TRICK,
    "interrupt": tb.INTERRUPT,
    "announce": tb.ANNOUNCEMENT,
}

# The restated window oracle of each engine that declares a decline, keyed by
# its lead query: its driven playouts' step kinds, failures per step kind,
# and liveness totals.
WINDOW_ORACLES: dict[str, Callable[[], tuple[Counter[str], dict[str, list[str]], Counter[str]]]] = {
    "tichu_lead_options": tb.driven_tichu_run,
}


def _engine_games() -> dict[str, str]:
    """Each climb lead query and the corpus game whose `round climb` names
    it in its `combinations` slot."""
    out: dict[str, str] = {}
    for path in sorted(GAMES.glob("*.cardlang")):
        for name in re.findall(r"combinations\s+(\w+)", path.read_text()):
            if name in PRIMITIVE_CLIMB_LEADS:
                out.setdefault(name, path.stem)
    return out


def _kinds(engine: str) -> list[str]:
    kinds = [tb.PASS, tb.PLAY]
    if primitives.climb_announcements(engine):
        kinds.append(tb.ANNOUNCEMENT)
    if primitives.climb_interrupt_decline(engine) is not None:
        kinds += [
            tb.CLOSING_PASS,
            tb.PLAY_ENDING_THE_TRICK,
            tb.PLAY_ENDING_THE_ROUND,
            tb.INTERRUPT,
            tb.INTERRUPT_ENDING_THE_ROUND,
        ]
    return kinds


CELLS = [(engine, kind) for engine in sorted(PRIMITIVE_CLIMB_LEADS) for kind in _kinds(engine)]


class _Windowless:
    """A uniform chooser over an engine that declares no decline: tallies the
    step kinds taken and every climb decision over a standing play that is
    not a ring turn (a ring turn always offers the pass)."""

    def __init__(self, seed: int) -> None:
        self.base = random_chooser(random.Random(seed))
        self.kinds: Counter[str] = Counter()
        self.windows: list[str] = []
        self.rs: Any = None

    def attach(self, rs: Any) -> None:
        self.rs = rs

    def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
        # A climb decision is any the climb round asks while its frame is
        # the innermost: the form owns every decision inside its trick.
        frame = self.rs.mech_state[-1] if self.rs.mech_state else None
        if frame is None or not {"current", "last"} <= set(frame):
            return self.base(player, candidates, n)
        if frame["current"] is not None and primitives.CLIMB_PASS not in candidates:
            self.windows.append(f"P{player} asked off the ring over {frame['current']}: {candidates}")
        picked = self.base(player, candidates, n)
        self.kinds[tb.PASS if picked[0] == primitives.CLIMB_PASS else tb.PLAY] += 1
        return picked


@functools.lru_cache(maxsize=None)
def _windowless_run(game_name: str, seeds: int = 3) -> tuple[Counter[str], list[str]]:
    game = check_source(GAMES / f"{game_name}.cardlang")
    kinds: Counter[str] = Counter()
    windows: list[str] = []
    for seed in range(seeds):
        chooser = _Windowless(seed)
        play_game(game, random.Random(seed), None, chooser, on_first_decision=chooser.attach)
        kinds.update(chooser.kinds)
        windows += chooser.windows
    return kinds, windows


def test_every_climb_play_member_is_classified() -> None:
    """red under: add a member to `primitives.ClimbPlay`."""
    members = {n for n, v in vars(primitives.ClimbPlay).items() if isinstance(v, property)}
    assert members == set(PLAY_MEMBERS)


def test_every_climb_engine_has_a_corpus_game() -> None:
    """red under: name `bigtwo_lead_options` in the `combinations` slot of
    docs/games/president.cardlang."""
    assert set(_engine_games()) == PRIMITIVE_CLIMB_LEADS


@pytest.mark.parametrize(("engine", "kind"), CELLS, ids=[f"{e}-{k}" for e, k in CELLS])
def test_the_window_owed_after_each_step(engine: str, kind: str) -> None:
    """red under, for a decline engine's ordinary-turn cells (`pass`, the
    closing pass, `play`, `announcement`, `interrupt`): leave the actor out
    of `ClimbForm._window_after`; for the two pass cells, also: open no
    window in `apply`'s pass branch.
    red under, for each windowless engine's cells: fall back to a decline in
    `ClimbForm.__init__` (`climb_interrupt_decline(...) or "no_bomb"`).
    red under, for `play ending the trick`: drop `terminated`'s
    `lead_ended_trick` return and open the window in `apply`'s `ends_trick`
    branch.
    red under, for `play ending the round` and `interrupt ending the round`:
    have `ClimbForm.terminated` answer False while a window is queued."""
    game = _engine_games()[engine]
    if primitives.climb_interrupt_decline(engine) is None:
        kinds, windows = _windowless_run(game)
        assert kinds[kind] > 0, kinds
        assert not windows, windows[:5]
        return
    oracle = WINDOW_ORACLES.get(engine)
    if oracle is None:
        raise AssertionError(
            f"{engine} declares an interrupt decline and this module holds no "
            f"restated oracle for its game ({game}); write one beside "
            f"tests/test_tichu_bombs.py::_Driven and key it in WINDOW_ORACLES"
        )
    kinds, failures, _ = oracle()
    assert kinds[kind] > 0, kinds
    assert not failures.get(kind), failures[kind][:5]
