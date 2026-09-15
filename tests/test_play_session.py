"""A person's seat at a game, played through `cardlang play`.

property:        Everything a person types at the table is carried out or
                 refused at every position a prompt can stand at: a number on
                 the menu is the pick, a control does what the prompt says it
                 does, and any other line, or the end of input, is refused or
                 leaves without a traceback. At each of the person's decisions
                 they are shown the text of the Seat View the line handed their
                 seat, the recent end of its log, and a menu numbering the legal
                 action ids by the adapter's own strings; the whole table is one
                 control away. Taking a pick back plays the line again without
                 the person's last pick, so they are asked again where they made
                 it, and a saved game resumes at the decision it was left at. A
                 saved file that is not a saved session, that another game or
                 another version of this one wrote, that a flag contradicts, or
                 whose picks do not replay is refused naming the file, before
                 anything is played, and so is a path no saved session can be
                 read from or written to; saving never replaces a file that is
                 not a saved session. A game that refuses mid-session reaches the
                 person as that refusal with the picks before it kept, and a game
                 whose decisions the action space cannot number is refused before
                 it is dealt.
domain:          Positions: `_WHERE`, one of each place a prompt can stand at
                 (the first decision, where nothing can be taken back; an inner
                 pick of a call for several; a decision the other seats played up
                 to; the end of the game). Inputs: the controls, derived from
                 `session.CONTROLS`, and `_OTHER_INPUT`, the other keystrokes a
                 person most plausibly gives. A pick taken back: one made in the
                 sitting, and one the line replayed (a game resumed from its
                 file, a second take-back in a row). The flags: every subset of
                 the `play` command's options, derived from the parser. Seats:
                 each side of the seat range, on a game of one seat and of two.
                 Saved files: `_BAD_SAVES`, each field of the format missing and
                 mistyped, a later format, JSON too large to read, another
                 game, an edited game, and picks that do not replay, beside the
                 controls that must resume (the file as saved, a renamed game,
                 a reformatted copy); each is also handed to `--save`. Paths:
                 `_FILE_KINDS`, each kind of path a person can hand an option
                 that names a file, crossed with those options, read off the
                 parser; and the command printed on leaving, run again, for
                 `_NAMES`, names as a person's folders and files come. The
                 shown text: every registered game's first decisions at seat
                 0. What a stopped session keeps: the file at every decision,
                 and after a person's interrupt, a game's refusal, an engine
                 failure and a save that cannot be written.
registry:        controls: `cardlang.play.session.CONTROLS`; commands and
                 options: `cardlang.cli.build_parser`, read through
                 tests/test_cli_surface.py's `_command_options`; games:
                 `cardlang.openspiel.registry.GAMES`; the line the session plays
                 and its refusals of recorded picks: tests/test_live_line.py; a
                 game's identity: tests/test_game_identity.py; the text of a Seat
                 View: `cardlang.play.view.render_view`, certified by
                 tests/test_play_view.py.
does not prove:  Which pick a person should make, or that the opponents are
                 any good: every other seat is the uniform opponent. The menu's
                 labels are the adapter's strings, and a label that says too
                 little (a bare number, a card set in rendering order) is shown
                 as it is (issue #682). A pick asked while another decision is being made (a
                 `choose` inside a move's effect) is shown as a decision of its
                 own, with nothing saying it belongs to the other (issue #605). A
                 choice from a zone the seat cannot see lists the cards it holds,
                 as the adapter's legal actions do (issue #281). A person seated
                 as a declarer is asked for the dummy's cards because a line asks
                 the Decider, which tests/test_live_line.py pins over the
                 registry; no cell here seats one.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shlex
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest

from cardlang.cli import build_parser, main
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, load
from cardlang.pipeline import check_source, game_identity
from cardlang.play.session import CONTROLS, RECENT_EVENTS, PersonSeat
from cardlang.play.view import render_view
from tests.test_cli_surface import _command_options

REPO = Path(__file__).parent.parent
GAMES_DIR = REPO / "docs" / "games"
FIXTURES = REPO / "tests" / "fixtures"

_SEED = 5


def _path(short_name: str) -> str:
    return str(GAMES_DIR / GAMES[short_name])


# The person makes one pick, and the game is over: the end of the game one
# pick from the start.
_ONE_PICK = """\
game OnePick {
  players: 2
  max_length: 4
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
  }
  state {
    score[player] : Integer = 0
  }
  phase setup {
    shuffle deck
    deal 2 cards from deck to each hand
  }
  phase play {
    as 0 { move chosen 1 card from hand to pile }
  }
  winner: highest score
}
"""

# A joint selection whose predicate is written inline: it plays, and the action
# space has no codec to number its subsets by.
_INLINE_JOINT = """\
game InlineJoint {
  players: 2
  max_length: 10
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
  }
  state {
    score[player] : Integer = 0
  }
  phase setup {
    shuffle deck
    deal 3 cards from deck to each hand
  }
  phase play {
    as 0 {
      move chosen 2 cards from hand where jointly (number of cards in cards) is 2 to pile
    }
  }
  winner: highest score
}
"""

_FIXTURE_TEXTS = {"one_pick": _ONE_PICK, "inline_joint": _INLINE_JOINT}


def _game_path(name: str, tmp_path: Path) -> str:
    if name in GAMES:
        return _path(name)
    path = tmp_path / f"{name}.cardlang"
    path.write_text(_FIXTURE_TEXTS[name])
    return str(path)


@dataclass(frozen=True)
class _Ask:
    view: SeatView
    legal: tuple[int, ...]


@dataclass(frozen=True)
class _Sitting:
    """One scripted session: how it ended, what it printed, and every position
    the person was asked at, in order."""

    code: int
    out: str
    err: str
    asks: list[_Ask]


_Sit = Callable[[list[str], str], _Sitting]

# A line holding only this is the person pressing Ctrl-C at the prompt.
_INTERRUPT = "\x03"


class _Keyboard:
    """What a person types, one line at a time."""

    def __init__(self, typed: str) -> None:
        self.lines = io.StringIO(typed)

    def readline(self) -> str:
        line = self.lines.readline()
        if line.rstrip("\n") == _INTERRUPT:
            raise KeyboardInterrupt
        return line


@pytest.fixture
def sit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> _Sit:
    asks: list[_Ask] = []
    person = PersonSeat.__call__

    def recording(self: PersonSeat, view: SeatView, legal: Sequence[int]) -> int:
        asks.append(_Ask(view, tuple(legal)))
        return person(self, view, legal)

    monkeypatch.setattr(PersonSeat, "__call__", recording)

    def run(argv: list[str], typed: str) -> _Sitting:
        asks.clear()
        monkeypatch.setattr(sys, "stdin", _Keyboard(typed))
        code = main(["play", *argv])
        captured = capsys.readouterr()
        return _Sitting(code, captured.out, captured.err, list(asks))

    return run


class _Stopped(Exception):
    pass


def _replayed(path: str, seed: int, history: list[int]) -> LiveLine:
    """The line `history` names, played no further than the history reaches."""
    game, _ = load(path)

    def stop(view: SeatView, legal: Sequence[int]) -> int:
        raise _Stopped

    line = LiveLine(path, seed, history)
    try:
        line.play({seat: stop for seat in range(game.players.low)})
    except _Stopped:
        pass
    return line


def _saved(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text())
    return loaded


# ---------------------------------------------------------------------------
# What a person types, at each place a prompt stands.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Where:
    game: str
    seat: int
    picks_before: int
    at_end: bool


_WHERE: dict[str, _Where] = {
    "the first decision": _Where("one_pick", 0, 0, False),
    # Hearts' pass takes three cards in one call.
    "an inner pick of one call": _Where("cardlang_hearts", 0, 1, False),
    # Seat 0's fourth decision comes after the other seats' passes.
    "a decision the other seats played up to": _Where("cardlang_hearts", 0, 3, False),
    "the end of the game": _Where("one_pick", 0, 1, True),
}

# The keystrokes a person most plausibly gives besides a control.
_OTHER_INPUT: dict[str, str | None] = {
    "a number on the menu": "1",
    "a number with a leading zero": "01",
    "a number past the menu": "99",
    "a number too long to read": "9" * 5000,
    "a word that is not a control": "x",
    "an empty line": "",
    "an interrupt": _INTERRUPT,
    "the end of input": None,
}


def _inputs() -> dict[str, str | None]:
    return {**{word: word for word in CONTROLS}, **_OTHER_INPUT}


_EXPECTED: dict[tuple[str, str], str] = {
    ("u", "the first decision"): "nothing to take back",
    ("u", "an inner pick of one call"): "takes back",
    ("u", "a decision the other seats played up to"): "takes back",
    ("u", "the end of the game"): "takes back",
    ("?", "the first decision"): "shows the whole table",
    ("?", "an inner pick of one call"): "shows the whole table",
    ("?", "a decision the other seats played up to"): "shows the whole table",
    ("?", "the end of the game"): "shows the whole table",
    ("q", "the first decision"): "leaves",
    ("q", "an inner pick of one call"): "leaves",
    ("q", "a decision the other seats played up to"): "leaves",
    ("q", "the end of the game"): "leaves",
    ("a number on the menu", "the first decision"): "picks",
    ("a number on the menu", "an inner pick of one call"): "picks",
    ("a number on the menu", "a decision the other seats played up to"): "picks",
    ("a number on the menu", "the end of the game"): "refuses the input",
    ("a number with a leading zero", "the first decision"): "picks",
    ("a number with a leading zero", "an inner pick of one call"): "picks",
    ("a number with a leading zero", "a decision the other seats played up to"): "picks",
    ("a number with a leading zero", "the end of the game"): "refuses the input",
    ("a number too long to read", "the first decision"): "refuses the input",
    ("a number too long to read", "an inner pick of one call"): "refuses the input",
    ("a number too long to read", "a decision the other seats played up to"): "refuses the input",
    ("a number too long to read", "the end of the game"): "refuses the input",
    ("a number past the menu", "the first decision"): "refuses the input",
    ("a number past the menu", "an inner pick of one call"): "refuses the input",
    ("a number past the menu", "a decision the other seats played up to"): "refuses the input",
    ("a number past the menu", "the end of the game"): "refuses the input",
    ("a word that is not a control", "the first decision"): "refuses the input",
    ("a word that is not a control", "an inner pick of one call"): "refuses the input",
    ("a word that is not a control", "a decision the other seats played up to"): "refuses the input",
    ("a word that is not a control", "the end of the game"): "refuses the input",
    ("an empty line", "the first decision"): "refuses the input",
    ("an empty line", "an inner pick of one call"): "refuses the input",
    ("an empty line", "a decision the other seats played up to"): "refuses the input",
    ("an empty line", "the end of the game"): "refuses the input",
    ("an interrupt", "the first decision"): "leaves",
    ("an interrupt", "an inner pick of one call"): "leaves",
    ("an interrupt", "a decision the other seats played up to"): "leaves",
    ("an interrupt", "the end of the game"): "leaves",
    ("the end of input", "the first decision"): "leaves",
    ("the end of input", "an inner pick of one call"): "leaves",
    ("the end of input", "a decision the other seats played up to"): "leaves",
    ("the end of input", "the end of the game"): "leaves",
}


def test_every_input_at_every_position_is_authored() -> None:
    derived = {(typed, where) for typed in _inputs() for where in _WHERE}
    assert derived == set(_EXPECTED), (
        "the controls, the other inputs and the positions have drifted from the "
        "authored outcomes; decide what each new cell does"
    )


@pytest.mark.parametrize(("typed", "where"), sorted(_EXPECTED))
def test_what_a_person_types_at_each_position(typed: str, where: str, tmp_path: Path, sit: _Sit) -> None:
    """red under, for an interrupt at the end of the game: let `_Prompt.read`
    pass the interrupt on; for a number with a leading zero: look the number
    up as it was typed."""
    place = _WHERE[where]
    path = _game_path(place.game, tmp_path)
    game, _ = load(path)
    saved = tmp_path / "saved.json"
    keys = _inputs()[typed]
    script = "1\n" * place.picks_before + ("" if keys is None else f"{keys}\nq\n")
    sitting = sit(
        [path, "--seat", str(place.seat), "--seed", str(_SEED), "--save", str(saved)], script
    )
    assert "Traceback" not in sitting.err
    assert sitting.code == 0, sitting.err
    reached = place.picks_before + (0 if place.at_end else 1)
    history = [int(aid) for aid in _saved(saved)["history"]]
    outcome = _EXPECTED[(typed, where)]
    controls = "one of: " + " ".join(CONTROLS)

    if outcome == "leaves":
        assert len(sitting.asks) == reached
    elif outcome == "nothing to take back":
        assert "nothing to take back" in sitting.out
        assert len(sitting.asks) == reached + 1
        assert sitting.asks[-1] == sitting.asks[-2]
    elif outcome == "takes back":
        assert len(sitting.asks) == reached + 1
        assert sitting.asks[-1] == sitting.asks[place.picks_before - 1]
    elif outcome == "shows the whole table":
        assert len(sitting.asks) == reached
        if place.at_end:
            end = _replayed(path, _SEED, history)
            assert end.deciders.count(place.seat) == place.picks_before
            view = LiveLine(path, _SEED, history).play({}).views[place.seat]
            whole = render_view(game, view)
            windowed = render_view(game, view, recent=RECENT_EVENTS)
        else:
            view = sitting.asks[-1].view
            whole = render_view(game, view, your_turn=True)
            windowed = render_view(game, view, your_turn=True, recent=RECENT_EVENTS)
        assert sitting.out.count(whole) == (whole == windowed) + 1
    elif outcome == "refuses the input":
        assert len(sitting.asks) == reached
        assert controls in sitting.out
        if not place.at_end:
            assert f"a number from 1 to {len(sitting.asks[-1].legal)}" in sitting.out
    else:
        assert outcome == "picks"
        line = _replayed(path, _SEED, history)
        assert line.deciders.count(place.seat) == place.picks_before + 1


@pytest.mark.parametrize("route", ["a game resumed from its file", "a second take-back in a row"])
def test_a_pick_the_line_replayed_is_taken_back_where_it_was_made(
    route: str, tmp_path: Path, sit: _Sit
) -> None:
    """red under: leave the seat of a replayed pick out of `ReplayChooser.deciders`."""
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    played = sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n1\n1\nq\n")
    made = _saved(saved)["history"]
    if route == "a game resumed from its file":
        sitting = sit([path, "--resume", str(saved)], "u\nq\n")
        asked, kept = [played.asks[3], played.asks[2]], 2
    else:
        sitting = sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n1\n1\nu\nu\nq\n")
        asked, kept = [*played.asks, played.asks[2], played.asks[1]], 1
    assert sitting.code == 0, sitting.err
    assert sitting.asks == asked
    assert _saved(saved)["history"] == made[:kept]


# ---------------------------------------------------------------------------
# What a person is shown.
# ---------------------------------------------------------------------------

# Enough of each game's start to reach several of the person's decisions.
_PICKS = 20


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_each_decision_shows_the_seat_its_view_and_the_menu(short_name: str, sit: _Sit) -> None:
    path = _path(short_name)
    game, space = load(path)
    sitting = sit([path, "--seed", str(_SEED)], "1\n" * _PICKS)
    assert "Traceback" not in sitting.err
    assert sitting.code == 0, sitting.err
    assert sitting.asks, f"{short_name}: seat 0 was never asked"
    for ask in sitting.asks:
        assert ask.view.player == 0
        assert render_view(game, ask.view, your_turn=True, recent=RECENT_EVENTS) in sitting.out
        assert f"choose 1 of {len(ask.legal)}" in sitting.out
    last = sitting.asks[-1]
    for number, aid in enumerate(last.legal, start=1):
        label = re.escape(space.to_string(aid))
        assert re.search(rf"(?:^|\s){number}  {label}(?:\s|$)", sitting.out, re.MULTILINE), (
            f"{short_name}: menu entry {number} does not name {space.to_string(aid)}"
        )


@pytest.mark.parametrize("number", [1, 7, 13])
def test_a_number_picks_the_id_the_menu_lists_under_it(number: int, tmp_path: Path, sit: _Sit) -> None:
    """red under: `return legal[int(word) % len(legal)]` in `PersonSeat.__call__`."""
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    sitting = sit([path, "--seed", str(_SEED), "--save", str(saved)], f"{number}\nq\n")
    _, space = load(path)
    first = sitting.asks[0]
    assert len(first.legal) == 13, "Hearts' first pass pick offers a whole hand"
    picked = _saved(saved)["history"][0]
    assert picked == first.legal[number - 1]
    assert re.search(
        rf"(?:^|\s){number}  {re.escape(space.to_string(picked))}(?:\s|$)", sitting.out, re.MULTILINE
    )


def test_the_file_holds_the_line_whenever_the_person_is_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """What a session that dies at a prompt, with no chance to save, still has.

    red under: drop the save from `Session._ask`."""
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    held: list[list[int]] = []
    asked = PersonSeat.__call__

    def reading(self: PersonSeat, view: SeatView, legal: Sequence[int]) -> int:
        held.append(_saved(saved)["history"])
        return asked(self, view, legal)

    monkeypatch.setattr(PersonSeat, "__call__", reading)
    sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n1\n1\n1\nq\n")
    lines = [_replayed(path, _SEED, history) for history in held]
    assert [line.deciders.count(0) for line in lines] == [0, 1, 2, 3, 4]
    assert all(line.history == history for line, history in zip(lines, held))


def test_an_interrupt_while_the_other_seats_pick_leaves_and_keeps_the_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """red under: catch `Leave` alone in `Session.run`."""
    from cardlang.openspiel.seat_policy import UniformSeatPolicy

    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    drawn = UniformSeatPolicy.__call__
    calls: list[int] = []

    def interrupted(self: UniformSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        calls.append(view.player)
        if len(calls) > 4:
            raise KeyboardInterrupt
        return drawn(self, view, legal)

    monkeypatch.setattr(UniformSeatPolicy, "__call__", interrupted)
    sitting = sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n1\n1\n")
    assert sitting.code == 0, sitting.err
    assert "you left the table" in sitting.out
    assert len(_saved(saved)["history"]) == 3 + 4


def test_an_engine_failure_mid_session_keeps_the_picks_before_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """An exception outside the rendered channels keeps its traceback, and the
    person's game survives it.

    red under: re-raise it in `Session.run` without keeping the line."""
    from cardlang.openspiel.seat_policy import UniformSeatPolicy

    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    drawn = UniformSeatPolicy.__call__
    calls: list[int] = []

    def failing(self: UniformSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        calls.append(view.player)
        if len(calls) > 4:
            raise AssertionError("an engine assertion")
        return drawn(self, view, legal)

    monkeypatch.setattr(UniformSeatPolicy, "__call__", failing)
    with pytest.raises(AssertionError, match="an engine assertion"):
        sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n1\n1\n")
    assert len(_saved(saved)["history"]) == 3 + 4


class _LockingKeyboard(_Keyboard):
    """A keyboard that makes `folder` unwritable once it has read `lines`
    lines."""

    def __init__(self, typed: str, folder: Path, lines: int) -> None:
        super().__init__(typed)
        self.folder = folder
        self.unread = lines

    def readline(self) -> str:
        line = super().readline()
        self.unread -= 1
        if self.unread == 0:
            self.folder.chmod(0o500)
        return line


@pytest.mark.parametrize("kept", [0, 1])
def test_a_save_that_fails_mid_session_is_refused_with_the_last_save_kept(
    kept: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The folder locks after the person's pick `kept + 1`, so the save
    before their next decision fails and the file keeps the one before it.

    red under: let `Session.save` pass the operating system's error on."""
    folder = tmp_path / "saves"
    folder.mkdir()
    saved = folder / "saved.json"
    monkeypatch.setattr(sys, "stdin", _LockingKeyboard("1\n1\n1\n", folder, lines=kept + 1))
    try:
        code = main(["play", _path("cardlang_hearts"), "--seed", str(_SEED), "--save", str(saved)])
    finally:
        folder.chmod(0o700)
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert code == 2, err
    assert f"cannot save to {saved}: Permission denied" in err
    assert len(_saved(saved)["history"]) == kept


def test_the_recent_end_of_the_log_is_the_whole_text_with_the_earlier_lines_folded() -> None:
    path = _path("cardlang_hearts")
    game, _ = load(path)
    views: list[SeatView] = []

    def keep(view: SeatView, legal: Sequence[int]) -> int:
        views.append(view)
        if len(view.obs_log) > RECENT_EVENTS + 5:
            raise _Stopped
        return legal[0]

    with pytest.raises(_Stopped):
        LiveLine(path, _SEED).play({seat: keep for seat in range(4)})
    view = views[-1]
    whole = render_view(game, view).splitlines()
    windowed = render_view(game, view, recent=RECENT_EVENTS).splitlines()
    start = whole.index("observation log") + 1
    folded = len(view.obs_log) - RECENT_EVENTS
    assert windowed[:start] == whole[:start]
    assert windowed[start + 1 :] == whole[start + folded :]
    assert str(folded) in windowed[start]
    short = views[0]
    assert render_view(game, short, recent=RECENT_EVENTS) == render_view(game, short)


@pytest.mark.parametrize(
    ("short_name", "seat", "others"),
    [
        ("cardlang_kuhn_poker", 0, "P1 picks uniformly at random"),
        ("cardlang_hearts", 2, "P0, P1 and P3 each pick uniformly at random"),
        ("cardlang_freecell", 0, None),
    ],
)
def test_the_header_names_the_seat_the_seed_and_who_picks_at_random(
    short_name: str, seat: int, others: str | None, sit: _Sit
) -> None:
    path = _path(short_name)
    sitting = sit([path, "--seat", str(seat), "--seed", "11"], "")
    head = sitting.out.split("\n\n", 1)[0]
    assert f"P{seat}" in head and "seed 11" in head
    if others is None:
        assert "random" not in head
    else:
        assert others in head


def test_an_unseeded_game_reports_the_seed_it_drew(sit: _Sit) -> None:
    sitting = sit([_path("cardlang_kuhn_poker")], "")
    assert re.search(r"seed -?\d+", sitting.out)


# ---------------------------------------------------------------------------
# The seat, and the flags beside it.
# ---------------------------------------------------------------------------

_SEAT_EXPECTED: dict[tuple[str, int], str] = {
    ("cardlang_kuhn_poker", -1): "refused",
    ("cardlang_kuhn_poker", 0): "seated",
    ("cardlang_kuhn_poker", 1): "seated",
    ("cardlang_kuhn_poker", 2): "refused",
    ("cardlang_freecell", -1): "refused",
    ("cardlang_freecell", 0): "seated",
    ("cardlang_freecell", 1): "refused",
}


@pytest.mark.parametrize(("short_name", "seat"), sorted(_SEAT_EXPECTED))
def test_a_seat_is_taken_or_refused_naming_the_seats(short_name: str, seat: int, sit: _Sit) -> None:
    path = _path(short_name)
    game, _ = load(path)
    sitting = sit([path, "--seat", str(seat), "--seed", "3"], "")
    if _SEAT_EXPECTED[(short_name, seat)] == "seated":
        assert sitting.code == 0, sitting.err
        assert sitting.asks and sitting.asks[0].view.player == seat
        return
    assert sitting.code == 2
    assert not sitting.asks
    assert f"seats 0..{game.players.low - 1}" in sitting.err
    assert f"--seat {seat}" in sitting.err


def test_a_seat_that_is_not_a_number_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["play", _path("cardlang_kuhn_poker"), "--seat", "one"])
    assert exit_info.value.code == 2
    assert "--seat" in capsys.readouterr().err


def _play_option_subsets() -> tuple[tuple[str, ...], ...]:
    options = sorted(_command_options()["play"])
    return tuple(
        tuple(subset) for size in range(len(options) + 1) for subset in combinations(options, size)
    )


# A saved game played at seat 1 with seed 9, beside flags naming seat 0 and
# seed 7: `--resume` beside either of those contradicts the file.
_PLAY_COMBINATION_EXPECTED: dict[tuple[str, ...], str] = {
    (): "accepted",
    ("--resume",): "accepted",
    ("--save",): "accepted",
    ("--seat",): "accepted",
    ("--seed",): "accepted",
    ("--resume", "--save"): "accepted",
    ("--resume", "--seat"): "refused",
    ("--resume", "--seed"): "refused",
    ("--save", "--seat"): "accepted",
    ("--save", "--seed"): "accepted",
    ("--seat", "--seed"): "accepted",
    ("--resume", "--save", "--seat"): "refused",
    ("--resume", "--save", "--seed"): "refused",
    ("--resume", "--seat", "--seed"): "refused",
    ("--save", "--seat", "--seed"): "accepted",
    ("--resume", "--save", "--seat", "--seed"): "refused",
}


def test_every_play_option_combination_is_authored() -> None:
    assert set(_play_option_subsets()) == set(_PLAY_COMBINATION_EXPECTED), (
        "the `play` command's options and the authored combinations have drifted; "
        "decide what each new combination means"
    )


def _a_save(path: str, *, seat: int, seed: int, history: list[Any]) -> dict[str, Any]:
    game = check_source(Path(path))
    return {
        "cardlang_session": 1,
        "game": game.name,
        "identity": game_identity(game),
        "seed": seed,
        "seat": seat,
        "history": history,
    }


@pytest.mark.parametrize("subset", sorted(_PLAY_COMBINATION_EXPECTED))
def test_play_option_combination_cell(subset: tuple[str, ...], tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_kuhn_poker")
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_a_save(path, seat=1, seed=9, history=[])))
    values = {
        "--seat": ["0"],
        "--seed": ["7"],
        "--save": [str(tmp_path / "save.json")],
        "--resume": [str(resume)],
    }
    argv = [path]
    for option in subset:
        argv += [option, *values[option]]
    sitting = sit(argv, "")
    if _PLAY_COMBINATION_EXPECTED[subset] == "accepted":
        assert sitting.code == 0, sitting.err
        assert sitting.asks
        seat = 1 if "--resume" in subset else 0
        assert sitting.asks[0].view.player == seat
        return
    assert sitting.code == 2
    assert not sitting.asks
    assert str(resume) in sitting.err
    assert any(option in sitting.err for option in ("--seat", "--seed") if option in subset)


def test_a_flag_that_agrees_with_the_saved_game_is_accepted(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_kuhn_poker")
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_a_save(path, seat=1, seed=9, history=[])))
    sitting = sit([path, "--resume", str(resume), "--seat", "1", "--seed", "9"], "")
    assert sitting.code == 0, sitting.err
    assert sitting.asks and sitting.asks[0].view.player == 1


# ---------------------------------------------------------------------------
# Saving and resuming.
# ---------------------------------------------------------------------------


def test_the_saved_file_carries_the_format_the_game_and_the_line(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    sit([path, "--seat", "0", "--seed", str(_SEED), "--save", str(saved)], "1\n1\nq\n")
    data = _saved(saved)
    game = check_source(Path(path))
    assert set(data) == {"cardlang_session", "game", "identity", "seed", "seat", "history"}
    assert data["cardlang_session"] == 1
    assert data["game"] == game.name
    assert data["identity"] == game_identity(game)
    assert (data["seed"], data["seat"]) == (_SEED, 0)
    assert _replayed(path, _SEED, data["history"]).deciders.count(0) == 2


def test_a_saved_game_resumes_at_the_decision_it_was_left_at(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    before = sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n1\n1\n1\nq\n")
    after = sit([path, "--resume", str(saved)], "q\n")
    assert after.code == 0, after.err
    assert after.asks == [before.asks[-1]]


def test_a_resumed_game_saves_back_to_its_own_file(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\nq\n")
    first = _saved(saved)["history"]
    sit([path, "--resume", str(saved)], "1\nq\n")
    second = _saved(saved)["history"]
    assert second[: len(first)] == first and len(second) > len(first)


def test_save_beside_resume_writes_the_other_file(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_hearts")
    saved = tmp_path / "saved.json"
    other = tmp_path / "other.json"
    sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\nq\n")
    kept = saved.read_text()
    sit([path, "--resume", str(saved), "--save", str(other)], "1\nq\n")
    assert saved.read_text() == kept
    assert len(_saved(other)["history"]) > len(json.loads(kept)["history"])


def test_a_game_saved_at_its_end_resumes_at_its_end(tmp_path: Path, sit: _Sit) -> None:
    path = _game_path("one_pick", tmp_path)
    saved = tmp_path / "saved.json"
    sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\nq\n")
    after = sit([path, "--resume", str(saved)], "q\n")
    assert after.code == 0, after.err
    assert not after.asks
    assert "the game is over" in after.out


def test_the_game_name_in_a_saved_file_is_never_checked(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_kuhn_poker")
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps({**_a_save(path, seat=0, seed=9, history=[]), "game": "Another"}))
    sitting = sit([path, "--resume", str(resume)], "")
    assert sitting.code == 0, sitting.err
    assert sitting.asks


def test_a_reformatted_copy_of_the_game_resumes_its_save(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_kuhn_poker")
    copy = tmp_path / "kuhn-copy.cardlang"
    copy.write_text("// a copy, reformatted\n\n" + Path(path).read_text())
    saved = tmp_path / "saved.json"
    sit([path, "--seed", "9", "--save", str(saved)], "1\nq\n")
    sitting = sit([str(copy), "--resume", str(saved)], "q\n")
    assert sitting.code == 0, sitting.err


def _edited_kuhn(tmp_path: Path) -> Path:
    text = Path(_path("cardlang_kuhn_poker")).read_text()
    edited, count = re.subn(
        r"max_length:\s*(\d+)", lambda m: f"max_length: {int(m.group(1)) + 1}", text, count=1
    )
    assert count == 1, "the edit reaches no line of the game"
    copy = tmp_path / "kuhn-edited.cardlang"
    copy.write_text(edited)
    return copy


def _with(**changes: Any) -> Callable[[dict[str, Any], Path], str]:
    return lambda good, tmp_path: json.dumps({**good, **changes})


def _without(field: str) -> Callable[[dict[str, Any], Path], str]:
    return lambda good, tmp_path: json.dumps({k: v for k, v in good.items() if k != field})


def _identity_of(path: Callable[[Path], str]) -> Callable[[dict[str, Any], Path], str]:
    return lambda good, tmp_path: json.dumps(
        {**good, "identity": game_identity(check_source(Path(path(tmp_path))))}
    )


# The files a person most plausibly hands `--resume` that are not this game's
# saved session, and what the refusal says of each.
_BAD_SAVES: dict[str, tuple[Callable[[dict[str, Any], Path], str], str]] = {
    "text that is not JSON": (lambda good, tmp_path: "{", "not a saved session"),
    "a number too long to read": (lambda good, tmp_path: '{"seed": ' + "9" * 5000 + "}", "not a saved session"),
    "nesting too deep to read": (lambda good, tmp_path: "[" * 200_000 + "]" * 200_000, "not a saved session"),
    "a JSON list": (lambda good, tmp_path: "[]", "not a saved session"),
    "no format": (_without("cardlang_session"), "not a saved session"),
    "no game": (_without("game"), "not a saved session"),
    "no identity": (_without("identity"), "not a saved session"),
    "no seed": (_without("seed"), "not a saved session"),
    "no seat": (_without("seat"), "not a saved session"),
    "no history": (_without("history"), "not a saved session"),
    "the format as text": (_with(cardlang_session="1"), "not a saved session"),
    "the identity as a number": (_with(identity=7), "not a saved session"),
    "the seed as text": (_with(seed="9"), "not a saved session"),
    "the seat as a flag": (_with(seat=True), "not a saved session"),
    "the history as a number": (_with(history=3), "not a saved session"),
    "a field the format does not have": (_with(opponents=["uniform"]), "not a saved session"),
    "a later format": (_with(cardlang_session=2), "format 2"),
    "another game": (_identity_of(lambda tmp_path: _path("cardlang_hearts")), "different game"),
    "an edited version of the game": (
        _identity_of(lambda tmp_path: str(_edited_kuhn(tmp_path))),
        "different game",
    ),
    "a seat the game does not seat": (_with(seat=2), "seats 0..1"),
    "a pick the game does not offer": (_with(history=[999]), "no longer replay"),
    "a flag for a pick": (_with(history=[True]), "no longer replay"),
}


@pytest.mark.parametrize("kind", sorted(_BAD_SAVES))
def test_a_file_that_is_not_this_games_saved_session_is_refused(
    kind: str, tmp_path: Path, sit: _Sit
) -> None:
    """red under, for the field the format does not have: skip the refusal of
    unknown fields in `read_saved`."""
    path = _path("cardlang_kuhn_poker")
    make, says = _BAD_SAVES[kind]
    resume = tmp_path / "resume.json"
    resume.write_text(make(_a_save(path, seat=0, seed=9, history=[]), tmp_path))
    kept = resume.read_text()
    sitting = sit([path, "--resume", str(resume)], "1\nq\n")
    assert sitting.code == 2
    assert "Traceback" not in sitting.err
    assert not sitting.asks
    assert str(resume) in sitting.err
    assert says in sitting.err
    assert resume.read_text() == kept, "a refused file must not be overwritten"


def _file_options() -> tuple[str, ...]:
    """The `play` options whose value names a file, read off the parser."""
    return tuple(
        sorted(
            option
            for action in build_parser()._actions
            if isinstance(action, argparse._SubParsersAction)
            for sub_action in action.choices["play"]._actions
            if sub_action.metavar == "FILE"
            for option in sub_action.option_strings
        )
    )


def _written(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def _a_saved_file(path: Path, game: Path) -> Path:
    return _written(path, json.dumps(_a_save(str(game), seat=0, seed=7, history=[])))


def _in_a_locked_directory(tmp_path: Path, game: Path) -> Path:
    locked = tmp_path / "locked"
    locked.mkdir()
    saved = _a_saved_file(locked / "saved.json", game)
    locked.chmod(0o500)
    assert not os.access(locked, os.W_OK), "this user writes to a directory it may not write to"
    return saved


def _unreadable(tmp_path: Path, game: Path) -> Path:
    saved = _a_saved_file(tmp_path / "saved.json", game)
    saved.chmod(0o200)
    assert not os.access(saved, os.R_OK), "this user reads a file it may not read"
    return saved


# Each kind of path a person can hand an option that names a file, made beside
# a copy of the game being played.
_FILE_KINDS: dict[str, Callable[[Path, Path], Path | str]] = {
    "a file that does not exist": lambda tmp_path, game: tmp_path / "new.json",
    "a saved session of this game": lambda tmp_path, game: _a_saved_file(tmp_path / "saved.json", game),
    "a saved session of another game": lambda tmp_path, game: _a_saved_file(
        tmp_path / "hearts.json", Path(_path("cardlang_hearts"))
    ),
    "the game file itself": lambda tmp_path, game: game,
    "a file that is not a saved session": lambda tmp_path, game: _written(tmp_path / "notes.txt", "notes\n"),
    "a directory": lambda tmp_path, game: tmp_path,
    "a file in a directory that does not exist": lambda tmp_path, game: tmp_path / "nowhere" / "saved.json",
    "a name longer than a folder allows": lambda tmp_path, game: tmp_path / ("x" * 300 + ".json"),
    "a saved session in a directory that cannot be written to": _in_a_locked_directory,
    "a saved session that cannot be read": _unreadable,
    "an empty name": lambda tmp_path, game: "",
}

# What each path does, and what a refusal says of it.
_NOT_A_SESSION = "cannot be read as a saved session"
_FILE_EXPECTED: dict[tuple[str, str], tuple[str, str]] = {
    ("--resume", "a directory"): ("refused", "Is a directory"),
    ("--resume", "a file in a directory that does not exist"): ("refused", "no such file"),
    ("--resume", "a file that does not exist"): ("refused", "no such file"),
    ("--resume", "a name longer than a folder allows"): ("refused", "File name too long"),
    ("--resume", "a file that is not a saved session"): ("refused", "not a saved session"),
    ("--resume", "a saved session in a directory that cannot be written to"): ("refused", "Permission denied"),
    ("--resume", "a saved session of another game"): ("refused", "different game"),
    ("--resume", "a saved session of this game"): ("plays", ""),
    ("--resume", "a saved session that cannot be read"): ("refused", "Permission denied"),
    ("--resume", "an empty name"): ("a usage error", "an empty name names no file"),
    ("--resume", "the game file itself"): ("refused", "not a saved session"),
    ("--save", "a directory"): ("refused", "it is a directory"),
    ("--save", "a file in a directory that does not exist"): ("refused", "there is no directory"),
    ("--save", "a file that does not exist"): ("plays", ""),
    ("--save", "a name longer than a folder allows"): ("refused", "File name too long"),
    ("--save", "a file that is not a saved session"): ("refused", _NOT_A_SESSION),
    ("--save", "a saved session in a directory that cannot be written to"): ("refused", "Permission denied"),
    ("--save", "a saved session of another game"): ("plays", ""),
    ("--save", "a saved session of this game"): ("plays", ""),
    ("--save", "a saved session that cannot be read"): ("refused", _NOT_A_SESSION),
    ("--save", "an empty name"): ("a usage error", "an empty name names no file"),
    ("--save", "the game file itself"): ("refused", _NOT_A_SESSION),
}


def test_every_file_option_and_kind_of_path_is_authored() -> None:
    derived = {(option, kind) for option in _file_options() for kind in _FILE_KINDS}
    assert derived == set(_FILE_EXPECTED), "decide what each new path does"


@pytest.mark.parametrize(("option", "kind"), sorted(_FILE_EXPECTED))
def test_each_kind_of_path_a_file_option_names(
    option: str,
    kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sit: _Sit,
) -> None:
    """red under: drop any one of `unwritable`'s refusals, or the parser's
    refusal of an empty name."""
    monkeypatch.chdir(tmp_path)
    game = _written(tmp_path / "kuhn.cardlang", Path(_path("cardlang_kuhn_poker")).read_text())
    named = str(_FILE_KINDS[kind](tmp_path, game))
    stamps = {path: path.stat() for path in tmp_path.rglob("*") if path.is_file()}
    outcome, says = _FILE_EXPECTED[(option, kind)]
    try:
        if outcome == "a usage error":
            with pytest.raises(SystemExit) as exit_info:
                sit([str(game), option, named], "q\n")
            assert exit_info.value.code == 2
            err = capsys.readouterr().err
            assert option in err and says in err
            return
        sitting = sit([str(game), option, named], "q\n")
        assert "Traceback" not in sitting.err
        if outcome == "plays":
            assert sitting.code == 0, sitting.err
            assert sitting.asks
            assert _saved(Path(named))["identity"] == game_identity(check_source(game))
            return
        assert outcome == "refused"
        assert sitting.code == 2
        assert not sitting.asks
        assert named in sitting.err and says in sitting.err
        after = {path: path.stat() for path in stamps}
        assert all(
            (after[path].st_ino, after[path].st_mtime_ns) == (stamp.st_ino, stamp.st_mtime_ns)
            for path, stamp in stamps.items()
        ), "a refused path must leave every file as it was"
        assert not list(tmp_path.rglob("*.tmp")), "a refused save must leave no temporary file"
    finally:
        for path in [tmp_path, *tmp_path.rglob("*")]:
            path.chmod(0o700 if path.is_dir() else 0o600)


# What saving over each of those files does: a file that reads as a saved
# session in the format resuming reads is replaced, whichever game it names, and
# any other is refused and kept.
_SAVE_OVER: dict[str, str] = {
    "text that is not JSON": "refused",
    "a number too long to read": "refused",
    "nesting too deep to read": "refused",
    "a JSON list": "refused",
    "no format": "refused",
    "no game": "refused",
    "no identity": "refused",
    "no seed": "refused",
    "no seat": "refused",
    "no history": "refused",
    "the format as text": "refused",
    "the identity as a number": "refused",
    "the seed as text": "refused",
    "the seat as a flag": "refused",
    "the history as a number": "refused",
    "a field the format does not have": "refused",
    "a later format": "refused",
    "another game": "replaced",
    "an edited version of the game": "replaced",
    "a seat the game does not seat": "replaced",
    "a pick the game does not offer": "replaced",
    "a flag for a pick": "replaced",
}


def test_saving_over_each_saved_file_kind_is_authored() -> None:
    assert set(_SAVE_OVER) == set(_BAD_SAVES), "decide what saving over each new kind does"


@pytest.mark.parametrize("kind", sorted(_SAVE_OVER))
def test_saving_over_a_file_replaces_only_a_saved_session(kind: str, tmp_path: Path, sit: _Sit) -> None:
    """red under: let `unwritable` replace any JSON object carrying a format
    number."""
    path = _path("cardlang_kuhn_poker")
    make, _ = _BAD_SAVES[kind]
    target = tmp_path / "saved.json"
    target.write_text(make(_a_save(path, seat=0, seed=9, history=[]), tmp_path))
    kept = target.read_text()
    sitting = sit([path, "--seed", "3", "--save", str(target)], "q\n")
    assert "Traceback" not in sitting.err
    if _SAVE_OVER[kind] == "replaced":
        assert sitting.code == 0, sitting.err
        assert _saved(target)["identity"] == game_identity(check_source(Path(path)))
        return
    assert sitting.code == 2
    assert not sitting.asks
    assert str(target) in sitting.err and _NOT_A_SESSION in sitting.err
    assert target.read_text() == kept, "a refused file must not be overwritten"


# Names as a person's folders and files come: plain, with spaces, with
# characters a shell reads, and beginning with a dash, which a parser reads as
# an option.
_NAMES: dict[str, tuple[str, str, str]] = {
    "plain names": ("games", "kuhn.cardlang", "saved.json"),
    "names with spaces": ("my games", "kuhn poker.cardlang", "my game.json"),
    "names a shell reads": ("$HOME", "kuhn $(date).cardlang", "it's $(date).json"),
    "names beginning with a dash": ("-games", "-kuhn.cardlang", "-saved.json"),
}


@pytest.mark.parametrize("names", sorted(_NAMES))
def test_leaving_prints_a_command_that_resumes_the_game(
    names: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """red under: print the paths into the command as they are, or quoted
    with a leading dash left to read as an option."""
    folder_name, game_name, save_name = _NAMES[names]
    monkeypatch.chdir(tmp_path)
    Path(folder_name).mkdir()
    game = _written(Path(folder_name) / game_name, Path(_path("cardlang_kuhn_poker")).read_text())
    saved = Path(folder_name) / save_name
    sitting = sit(["--seed", "3", f"--save={saved}", "--", str(game)], "q\n")
    assert sitting.code == 0, sitting.err
    (command,) = [line.strip() for line in sitting.out.splitlines() if line.strip().startswith("cardlang play")]
    argv = shlex.split(command)
    assert argv[:2] == ["cardlang", "play"] and argv[3] == "--resume"
    assert (Path(argv[2]), Path(argv[4])) == (game, saved)
    again = sit(argv[2:], "q\n")
    assert again.code == 0, again.err
    assert again.asks == sitting.asks


# ---------------------------------------------------------------------------
# Games that refuse.
# ---------------------------------------------------------------------------


def test_a_game_that_refuses_mid_session_keeps_the_picks_before_it(tmp_path: Path, sit: _Sit) -> None:
    path = str(FIXTURES / "empty_zone_choice.cardlang")
    saved = tmp_path / "saved.json"
    sitting = sit([path, "--seed", str(_SEED), "--save", str(saved)], "1\n")
    assert sitting.code == 1
    assert "Traceback" not in sitting.err
    assert "cannot choose 1 of 0 candidates" in sitting.err
    assert "P1 picked uniformly at random" in sitting.err
    assert "uniform-random self-play" not in sitting.err
    assert len(_saved(saved)["history"]) == 2


def test_a_game_that_overruns_its_length_mid_session_is_refused(sit: _Sit) -> None:
    sitting = sit([str(FIXTURES / "exceeds_max_length.cardlang"), "--seed", "1"], "1\n")
    assert sitting.code == 1
    assert "max_length" in sitting.err
    assert "Traceback" not in sitting.err


def test_a_games_own_error_before_any_decision_is_refused(sit: _Sit) -> None:
    sitting = sit([str(FIXTURES / "rule_refuses_every_card.cardlang"), "--seed", "1"], "")
    assert sitting.code == 1
    assert "the lead must be a spade" in sitting.err
    assert "Traceback" not in sitting.err
    assert not sitting.asks


def test_a_game_whose_decisions_cannot_be_numbered_is_refused_before_the_deal(
    tmp_path: Path, sit: _Sit
) -> None:
    sitting = sit([_game_path("inline_joint", tmp_path), "--seed", "1"], "1\nq\n")
    assert sitting.code == 2
    assert "Traceback" not in sitting.err
    assert not sitting.asks
    assert "cannot be played at a table" in sitting.err


# ---------------------------------------------------------------------------
# The seed.
# ---------------------------------------------------------------------------


def test_the_seed_reaches_the_other_seats_in_a_chance_free_game(tmp_path: Path, sit: _Sit) -> None:
    path = _path("cardlang_breakthrough")
    lines = []
    for seed in (1, 2):
        saved = tmp_path / f"saved-{seed}.json"
        sit([path, "--seed", str(seed), "--save", str(saved)], "1\n1\n1\nq\n")
        lines.append(_saved(saved)["history"])
    assert lines[0] != lines[1]
