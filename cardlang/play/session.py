"""A person's seat at a game: the session `cardlang play` runs.

A session is a line of play, ``(seed, history)`` played on through
`replay.LiveLine`, with a person answering for one seat. The person is a
[[seat-policy]] like every other seat: handed their seat's [[seat-view]] and the
legal action ids, they are shown the view's text (`render_view`) and a menu that
numbers the ids by the adapter's own strings (`ActionSpace.to_string`), and they
answer with a number. Every other seat plays `UniformSeatPolicy` on the
session's seed.

The session holds OpenSpiel action ids outside the Interop package, and does so
deliberately: a saved session is a recorded history, and recorded picks have one
reader (`replay.ReplayChooser`), which also refuses a pick that does not replay.

A running game stops only by an exception unwinding it, so a person's controls
travel through their seat as one. Taking a pick back ends the line and plays it
again from the history before the person's last pick, which asks them again
where they made it; leaving ends it where it stands, and so does an interrupt.
A saved session is the history with the seed, the seat, the game's identity
(`pipeline.game_identity`) and a format number, written before each of the
person's decisions and whenever the session stops.

Contract
--------
Assumes: a checked game whose action space `ActionSpace.for_game` derives, and
a seat the game seats.
Establishes: the session's state is ``(seed, history)`` and nothing else; the
person is shown the Seat View their seat is handed and the legal action ids,
never a node or the World; a control ends the line only through the person's
seat; a saved session is read back only in its own format, and resumed only in
a game with the identity it carries.
Illegal after: rendering anything of a `DecisionNode`; a second reader of
recorded picks; reading a fact out of a label, an action string or a rendering.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from cardlang.ast import nodes as n
from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.replay import HistoryMismatch, LiveEnd, LiveLine
from cardlang.openspiel.seat_policy import SeatPolicy, UniformSeatPolicy
from cardlang.pipeline import game_identity
from cardlang.play.view import render_view

# What a person may type at a prompt besides a number on the menu.
CONTROLS: dict[str, str] = {
    "u": "take back your last pick",
    "?": "show the whole table",
    "q": "leave the table",
}

# How many of the log's latest events a decision shows; `?` shows them all.
RECENT_EVENTS = 12

# The saved-session format this module writes, and the only one it reads.
SESSION_FORMAT = 1

_FIELDS: dict[str, type] = {
    "cardlang_session": int,
    "game": str,
    "identity": str,
    "seed": int,
    "seat": int,
    "history": list,
}

# The width a menu's columns are laid out in.
_MENU_WIDTH = 78


class TakeBack(Exception):
    """The person takes back their last pick, ending the line so it can be
    played again without it."""


class Leave(Exception):
    """The person leaves the table, ending the line where it stands."""


def _controls() -> str:
    return ", ".join(f"{word} to {what}" for word, what in CONTROLS.items())


def _named(seats: Sequence[int]) -> str:
    names = [f"P{seat}" for seat in seats]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _menu(space: ActionSpace, legal: Sequence[int]) -> str:
    digits = len(str(len(legal)))
    cells = [
        f"{number:>{digits}}  {space.to_string(aid)}"
        for number, aid in enumerate(legal, start=1)
    ]
    width = max(len(cell) for cell in cells) + 3
    columns = max(1, min(len(cells), _MENU_WIDTH // width))
    rows = -(-len(cells) // columns)
    lines = [f"choose 1 of {len(legal)}"]
    for row in range(rows):
        taken = cells[row::rows][:columns]
        lines.append("  " + "".join(cell.ljust(width) for cell in taken).rstrip())
    return "\n".join(lines)


def _returns(returns: Sequence[float]) -> str:
    def trimmed(value: float) -> str:
        return str(int(value)) if value == int(value) else str(value)

    best = max(returns)
    return (
        "  returns      "
        + ", ".join(f"P{seat} {trimmed(value)}" for seat, value in enumerate(returns))
        + "\n  best return  "
        + ", ".join(f"P{seat}" for seat, value in enumerate(returns) if value == best)
    )


class _Prompt:
    """One reader and one writer, shared by every prompt a session shows."""

    def __init__(self, reader: TextIO, writer: TextIO) -> None:
        self.reader = reader
        self.writer = writer

    def say(self, text: str) -> None:
        self.writer.write(text + "\n")
        self.writer.flush()

    def read(self, prompt: str) -> str | None:
        """The line typed after `prompt`, stripped, or None at the end of input
        or an interrupt."""
        self.writer.write(prompt)
        self.writer.flush()
        try:
            line = self.reader.readline()
        except KeyboardInterrupt:
            return None
        return None if line == "" else line.strip()


class PersonSeat:
    """A person at a terminal, answering for one seat.

    Each decision shows the seat's view with the recent end of its log, then
    the menu; a number on the menu is the pick. `?` shows the whole view, `u`
    raises `TakeBack` and `q` raises `Leave`, and the end of input leaves."""

    def __init__(self, game: n.Game, space: ActionSpace, reader: TextIO, writer: TextIO) -> None:
        self.game = game
        self.space = space
        self.prompt = _Prompt(reader, writer)

    def __call__(self, view: SeatView, legal: Sequence[int], /) -> int:
        say = self.prompt.say
        say("")
        say(render_view(self.game, view, your_turn=True, recent=RECENT_EVENTS))
        say("")
        say(_menu(self.space, legal))
        while True:
            word = self.prompt.read(f"your pick (1 to {len(legal)}), or {_controls()}: ")
            if word is None or word == "q":
                raise Leave
            if re.fullmatch(r"[0-9]+", word) and 1 <= int(word) <= len(legal):
                return legal[int(word) - 1]
            if word == "u":
                raise TakeBack
            if word == "?":
                say(render_view(self.game, view, your_turn=True))
                say("")
                say(_menu(self.space, legal))
                continue
            say(f"type a number from 1 to {len(legal)}, or one of: {' '.join(CONTROLS)}")


@dataclass(frozen=True)
class Saved:
    """What a saved session holds besides its format and the game's identity.

    `history` is as the file holds it: the line's replay is what refuses a pick
    that is not an action id, or that the game does not offer."""

    seed: int
    seat: int
    history: list[Any]


def _record(path: Path) -> dict[str, Any] | str:
    """What the file at `path` holds when it is a saved session in the format
    this module reads, whichever game it was saved from, or why it is not
    one."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return "no such file"
    except OSError as exc:
        return exc.strerror or str(exc)
    except UnicodeDecodeError:
        return "not a saved session: not text"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return "not a saved session: not JSON"
    if not isinstance(data, dict):
        return "not a saved session: not a JSON object"
    version = data.get("cardlang_session")
    if type(version) is not int:
        return "not a saved session: no `cardlang_session` format number"
    if version != SESSION_FORMAT:
        return (
            f"saved in session format {version}, and this cardlang reads format "
            f"{SESSION_FORMAT}"
        )
    unknown = sorted(set(data) - set(_FIELDS))
    if unknown:
        return (
            f"not a saved session: it holds {', '.join(unknown)}, which the format "
            "does not"
        )
    for field, kind in _FIELDS.items():
        if field not in data:
            return f"not a saved session: no `{field}`"
        if type(data[field]) is not kind:
            return f"not a saved session: `{field}` is {data[field]!r}"
    return data


def read_saved(path: Path, identity: str) -> Saved | str:
    """The session saved at `path`, or why the game with `identity` cannot
    resume it."""
    data = _record(path)
    if isinstance(data, str):
        return data
    if data["identity"] != identity:
        return (
            "it was saved from a different game, or from another version of this "
            "one: its rules, or a library it uses, have changed. A saved session "
            "replays only in the game it was played in, so start a new game, or "
            "resume it in the game it was saved from"
        )
    return Saved(data["seed"], data["seat"], data["history"])


def unwritable(path: Path) -> str | None:
    """Why a session cannot be saved at `path`, or None when it can. Nothing
    is written to `path` itself, and a file already there is replaced only when
    it is a saved session."""
    if path.is_dir():
        return "it is a directory"
    if not path.parent.is_dir():
        return f"there is no directory {path.parent}"
    if path.exists() and isinstance(_record(path), str):
        return (
            "it holds something that cannot be read as a saved session, and saving "
            "would replace it; name another file"
        )
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent):
            pass
    except OSError as exc:
        return exc.strerror or str(exc)
    return None


class Session:
    """A person seated at a game, from the history they start at to the moment
    they leave.

    `run` returns when the person leaves. A refusal the game raises, or a
    history that does not replay, ends the session as that exception, with the
    picks made before it saved (a history that does not replay leaves the file
    as it was)."""

    def __init__(
        self,
        path: str,
        game: n.Game,
        space: ActionSpace,
        seat: int,
        seed: int,
        history: Sequence[Any],
        reader: TextIO,
        writer: TextIO,
        save_to: Path | None,
    ) -> None:
        self.path = path
        self.game = game
        self.seat = seat
        self.seed = seed
        self.history: list[Any] = list(history)
        self.save_to = save_to
        self.identity = game_identity(game)
        self.prompt = _Prompt(reader, writer)
        self.person = PersonSeat(game, space, reader, writer)
        self.others = [other for other in range(game.players.low) if other != seat]
        uniform = UniformSeatPolicy(seed)
        self.policies: Mapping[int, SeatPolicy] = {
            other: (self._ask if other == seat else uniform)
            for other in range(game.players.low)
        }
        self.line = LiveLine(path, seed, self.history)

    def who_played(self) -> str:
        """Who chose for each seat, as a refusal names them."""
        if not self.others:
            return f"P{self.seat} was you"
        verb = "picked" if len(self.others) == 1 else "each picked"
        return f"{_named(self.others)} {verb} uniformly at random, and P{self.seat} was you"

    def save(self) -> None:
        if self.save_to is None:
            return
        record = {
            "cardlang_session": SESSION_FORMAT,
            "game": self.game.name,
            "identity": self.identity,
            "seed": self.seed,
            "seat": self.seat,
            "history": self.history,
        }
        with tempfile.NamedTemporaryFile(
            "w", dir=self.save_to.parent, suffix=".tmp", delete=False
        ) as handle:
            handle.write(json.dumps(record) + "\n")
        os.replace(handle.name, self.save_to)

    def run(self) -> None:
        self.prompt.say(self._header())
        while True:
            self.line = line = LiveLine(self.path, self.seed, self.history)
            try:
                end = line.play(self.policies)
            except TakeBack:
                self.history = self._before_last_pick(line)
                continue
            except (Leave, KeyboardInterrupt):
                self._keep(line)
                self._left()
                return
            except HistoryMismatch:
                raise
            except BaseException:
                self._keep(line)
                raise
            self._keep(line)
            if not self._at_the_end(end):
                self._left()
                return
            self.history = self._before_last_pick(line)

    def _ask(self, view: SeatView, legal: Sequence[int]) -> int:
        self._keep(self.line)
        return self.person(view, legal)

    def _keep(self, line: LiveLine) -> None:
        self.history = list(line.history)
        self.save()

    def _header(self) -> str:
        lines = [f"{self.game.name}: you are P{self.seat}, seed {self.seed}"]
        if self.others:
            verb = "picks" if len(self.others) == 1 else "each pick"
            lines.append(
                f"{_named(self.others)} {verb} uniformly at random; choosing an "
                "opponent is not built yet"
            )
        if self.save_to is not None:
            lines.append(f"saving to {self.save_to} before each of your picks")
        return "\n".join(lines)

    def _before_last_pick(self, line: LiveLine) -> list[Any]:
        picks = [index for index, decider in enumerate(line.deciders) if decider == self.seat]
        if not picks:
            self.prompt.say("nothing to take back yet")
            return list(line.history)
        return list(line.history[: picks[-1]])

    def _at_the_end(self, end: LiveEnd) -> bool:
        """Shows the end of the game; True when the person takes a pick back."""
        say = self.prompt.say
        view = end.views.get(self.seat)
        say("")
        say("the game is over")
        if view is not None:
            say(render_view(self.game, view, recent=RECENT_EVENTS))
        say("")
        say(_returns(end.returns))
        while True:
            word = self.prompt.read(f"{_controls()}: ")
            if word is None or word == "q":
                return False
            if word == "u":
                return True
            if word == "?":
                say(
                    "nobody was asked to choose, so there is no view to show"
                    if view is None
                    else render_view(self.game, view)
                )
                continue
            say(f"type one of: {' '.join(CONTROLS)}")

    def _left(self) -> None:
        self.prompt.say("")
        self.prompt.say("you left the table")
        if self.save_to is not None:
            resume = shlex.join(["cardlang", "play", self.path, "--resume", str(self.save_to)])
            self.prompt.say(f"the game is saved in {self.save_to}; to go on with it:\n    {resume}")
