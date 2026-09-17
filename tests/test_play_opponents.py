"""Who plays the seats a person does not take: `cardlang play --vs`.

property:        Every `--vs` value is read as WHO=OPPONENT, WHO a seat number
                 as the table numbers seats, `all` or `rest`, and OPPONENT a
                 name in the opponent table, or it is refused as a usage error
                 saying what an item is. The items together seat one opponent at
                 each seat that is not the person's, or they are refused before
                 anything is dealt, naming what to add or take away. With no
                 `--vs`, a game with other seats is refused naming those seats,
                 a command that seats them and every opponent, and a game of one
                 seat is played. Each seated opponent answers its own seat's
                 decisions, as the header names it and the saved game records
                 it. A resumed game seats the opponents its file records, and a
                 `--vs` beside it that names others is refused, naming what the
                 file records. `first` answers as a person picking the first item
                 on the menu does. `all=random` plays the line that a uniform
                 draw at every other seat plays on the same seed. Each opponent
                 answers a legal id as a function of its seed and the view it
                 is handed.
domain:          Values: `_WHO` crossed with the opponent spellings (the table's
                 names and `_MISNAMED`), the bare values `_BARE` and the table's
                 names, and `_ARGPARSE_READINGS`, the invocations argparse reads
                 before any value reaches the grammar. Compositions: `_SHAPES` on
                 one game for each number of seats a registered game seats
                 (`_TABLES`, checked against the registry), with the person at
                 the first seat and the last. Beside `--resume`: `_RESUMED`, and
                 a game of one seat. Refusal order: `_PRECEDENCE`, one pair for
                 each place a `--vs` refusal meets another. The refusal of a
                 missing `--vs`: its text, a partial composition, and the command
                 it prints run again under names that need quoting. What a person
                 is shown: `_HEADERS`, and who picked when a game refuses. Row
                 properties: each opponent at every seat of each registered game.
                 The `first` oracle: each registered game, skipping a game of
                 one seat, where no seat is left for `first`. The `random`
                 regression: `_UNIFORM_LINES`.
registry:        opponents: `cardlang.openspiel.seat_policy.OPPONENTS`; games:
                 `cardlang.openspiel.registry.GAMES`; the saved `opponents`
                 field's values: tests/test_play_session.py's `_BAD_SAVES`; the
                 seat a line asks, Delegated Play included:
                 tests/test_live_line.py.
does not prove:  That an opponent plays well. That a table ends: when every seat
                 keeps taking the first item, some games run into their
                 `max_length`, and the refusal names the game as at fault (issue
                 #698). That `first` and `random` are the opponents a designer
                 needs; only `seat_policy.OPPONENTS` says which exist. An
                 opponent that takes an argument. The table has no column for
                 one, by decision: no opponent takes an argument, and a column
                 nothing reads could not fail. So `name:argument` is read as a
                 whole name, and refused.
"""

from __future__ import annotations

import contextlib
import json
import re
import shlex
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from cardlang.cli import main
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, load
from cardlang.openspiel.seat_policy import (
    OPPONENTS,
    FirstSeatPolicy,
    SeatBinding,
    UniformSeatPolicy,
)
from tests.test_play_session import (
    FIXTURES,
    _a_save,
    _path,
    _replayed,
    _saved,
    _Sit,
    seat_a_person,
)

_SEED = 5


@pytest.fixture
def sit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> _Sit:
    return seat_a_person(monkeypatch, capsys)


def _vs(items: Sequence[str]) -> list[str]:
    return [word for item in items for word in ("--vs", item)]


class _Stopped(Exception):
    pass


# ---------------------------------------------------------------------------
# The opponent table.
# ---------------------------------------------------------------------------


def test_each_opponent_is_a_word_named_by_its_key() -> None:
    """A name is the one word a person types after `=`, and never the selector
    written before it.

    red under: add a row named `rest` to `OPPONENTS`."""
    assert OPPONENTS, "the table seats nobody"
    for name, row in OPPONENTS.items():
        assert row.name == name
        assert name not in ("all", "rest"), f"{name} is a selector a `--vs` item writes before `=`"
        assert re.fullmatch(r"[a-z][a-z0-9-]*", name), f"{name!r} is not one word a person types"
        assert row.description and "\n" not in row.description, f"{name} has no one-line description"


# Decisions each opponent is asked at before its line stops.
_ASKED = 40


@pytest.mark.parametrize(("name", "short_name"), [(n, g) for n in sorted(OPPONENTS) for g in sorted(GAMES)])
def test_each_opponent_answers_a_legal_id_as_a_function_of_its_seed_and_view(name: str, short_name: str) -> None:
    """What take-back and resume rest on: asked again, or made again from the
    same seed, an opponent answers a view the way it answered it.

    red under: a `random` row whose policy draws from one `random.Random(seed)`
    stream."""
    path = _path(short_name)
    game, space = load(path)
    row = OPPONENTS[name]
    asked = 0

    def seated(policy: Callable[[SeatView, Sequence[int]], int]) -> Callable[[SeatView, Sequence[int]], int]:
        def answer(view: SeatView, legal: Sequence[int]) -> int:
            nonlocal asked
            picked = policy(view, legal)
            assert picked in legal, f"{name} answered {picked}, which is not legal"
            assert policy(view, legal) == picked, f"{name}, asked again, answers otherwise"
            made = row.make(SeatBinding(game, space, view.player, _SEED))
            assert made(view, legal) == picked, f"{name}, made again, answers otherwise"
            asked += 1
            if asked == _ASKED:
                raise _Stopped
            return picked

        return answer

    with contextlib.suppress(_Stopped):
        LiveLine(path, _SEED).play(
            {
                seat: seated(row.make(SeatBinding(game, space, seat, _SEED)))
                for seat in range(game.players.low)
            }
        )
    assert asked, f"{short_name}: nobody was asked"


# ---------------------------------------------------------------------------
# One `--vs` value.
# ---------------------------------------------------------------------------

_NOT_A_SEAT = "is not a seat number, all or rest"
_NO_OPPONENT = "there is no opponent"
_NOT_AN_ITEM = "is not WHO=OPPONENT"

# WHO as a person might write it: None where it names seats.
_WHO: dict[str, str | None] = {
    "0": None,
    "1": None,
    "all": None,
    "rest": None,
    "": _NOT_A_SEAT,
    "01": _NOT_A_SEAT,
    "+1": _NOT_A_SEAT,
    "-1": _NOT_A_SEAT,
    " 1": _NOT_A_SEAT,
    "1 ": _NOT_A_SEAT,
    "1.0": _NOT_A_SEAT,
    "one": _NOT_A_SEAT,
    "P1": _NOT_A_SEAT,
    "ALL": _NOT_A_SEAT,
    "Rest": _NOT_A_SEAT,
    # ARABIC-INDIC DIGIT ONE, which `str.isdigit` and `int` both accept.
    "\u0661": _NOT_A_SEAT,
}

# Opponents as a person might misname one.
_MISNAMED: tuple[str, ...] = (
    "",
    "randon",
    "Random",
    " random",
    "random ",
    "all",
    "rest",
    "random:3",
    "uniform",
    "random=first",
)

# Values with no `=`, beside each opponent's bare name.
_BARE: tuple[str, ...] = ("", "randon", "1", "all", "rest", "P1")


def _item_cells() -> dict[str, str]:
    """Each value's expected reading: "read", or the refusal it carries. WHO is
    read before OPPONENT, so a value wrong in both is refused for its WHO."""
    spellings: dict[str, str | None] = {**{name: None for name in OPPONENTS}, **dict.fromkeys(_MISNAMED, _NO_OPPONENT)}
    cells = {
        f"{who}={opponent}": who_refusal or opponent_refusal or "read"
        for who, who_refusal in _WHO.items()
        for opponent, opponent_refusal in spellings.items()
    }
    cells.update({name: f"--vs all={name}" for name in OPPONENTS})
    cells.update(dict.fromkeys(_BARE, _NOT_AN_ITEM))
    return cells


_ITEM_CELLS = _item_cells()


def test_the_value_axes_are_disjoint() -> None:
    assert not set(_MISNAMED) & set(OPPONENTS), "a misnaming is an opponent's name"
    assert not set(_BARE) & set(OPPONENTS), "a bare value is an opponent's name"
    assert len(_ITEM_CELLS) == len(_WHO) * (len(OPPONENTS) + len(_MISNAMED)) + len(OPPONENTS) + len(_BARE)


@pytest.mark.parametrize("text", sorted(_ITEM_CELLS))
def test_each_vs_value_is_read_or_refused_as_a_usage_error(
    text: str, capsys: pytest.CaptureFixture[str], sit: _Sit
) -> None:
    """red under: accept any WHO whose digits `int()` reads, sign and spaces
    included."""
    argv = [_path("cardlang_kuhn_poker"), "--seed", str(_SEED), f"--vs={text}"]
    expected = _ITEM_CELLS[text]
    if expected == "read":
        sitting = sit(argv, "q\n")
        assert "Traceback" not in sitting.err
        assert "usage:" not in sitting.err
        assert not any(refusal in sitting.err for refusal in (_NOT_A_SEAT, _NO_OPPONENT, _NOT_AN_ITEM))
        return
    with pytest.raises(SystemExit) as exit_info:
        sit(argv, "q\n")
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "usage:" in err and "argument --vs:" in err, err
    assert expected in err, err
    if expected == _NO_OPPONENT:
        assert all(f"{name} ({row.description})" in err for name, row in OPPONENTS.items()), err


# What argparse makes of an invocation before any value reaches the grammar.
_ARGPARSE_READINGS: dict[str, tuple[list[str], str]] = {
    "a seat written with a dash, after a space": (["--vs", "-1=first"], "expected one argument"),
    "a second item without its flag": (["--vs", "1=first", "2=random"], "unrecognized arguments: 2=random"),
    "the flag with nothing after it": (["--vs"], "expected one argument"),
}


@pytest.mark.parametrize("reading", sorted(_ARGPARSE_READINGS))
def test_what_argparse_reads_before_the_grammar_is_a_usage_error(
    reading: str, capsys: pytest.CaptureFixture[str], sit: _Sit
) -> None:
    words, says = _ARGPARSE_READINGS[reading]
    with pytest.raises(SystemExit) as exit_info:
        sit([_path("cardlang_kuhn_poker"), *words], "q\n")
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "usage:" in err and says in err, err


def test_the_help_names_the_item_and_every_opponent(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["play", "--help"])
    shown = " ".join(capsys.readouterr().out.split())
    assert "--vs WHO=OPPONENT" in shown
    for name, row in OPPONENTS.items():
        assert f"{name} ({row.description})" in shown, f"the help does not name {name}"


# ---------------------------------------------------------------------------
# The items together, at a table of each size.
# ---------------------------------------------------------------------------

# One registered game for each number of seats the registry's games seat.
_TABLES: dict[int, str] = {
    1: "cardlang_freecell",
    2: "cardlang_kuhn_poker",
    3: "cardlang_holdem",
    4: "cardlang_hearts",
    5: "cardlang_president",
}


def test_a_table_of_each_size_the_registry_seats_is_named() -> None:
    seats = {short_name: load(_path(short_name))[0].players.low for short_name in GAMES}
    assert set(seats.values()) == set(_TABLES), "a registered game seats a number no table here does"
    assert all(seats[short_name] == size for size, short_name in _TABLES.items())


# (the other seats, the person's seat, the seats at the table) -> the items, or
# None where the shape needs more seats than the table has.
_Shape = Callable[[Sequence[int], int, int], list[str] | None]

_SHAPES: dict[str, _Shape] = {
    "no --vs": lambda others, person, seats: [],
    "all=random": lambda others, person, seats: ["all=random"],
    "all=first": lambda others, person, seats: ["all=first"],
    "each other seat numbered": lambda others, person, seats: (
        [f"{seat}={('first', 'random')[at % 2]}" for at, seat in enumerate(others)] if others else None
    ),
    "a numbered seat, and rest": lambda others, person, seats: (
        [f"{others[0]}=first", "rest=random"] if others else None
    ),
    "rest, and a numbered seat": lambda others, person, seats: (
        ["rest=random", f"{others[0]}=first"] if others else None
    ),
    "a seat left unnamed": lambda others, person, seats: (
        [f"{seat}=first" for seat in others[1:]] if len(others) > 1 else None
    ),
    "rest alone": lambda others, person, seats: ["rest=random"],
    "every other seat numbered, and rest": lambda others, person, seats: (
        [*(f"{seat}=first" for seat in others), "rest=random"] if others else None
    ),
    "rest twice": lambda others, person, seats: (
        [f"{others[0]}=first", "rest=random", "rest=first"] if others else None
    ),
    "all beside a numbered seat": lambda others, person, seats: (
        ["all=random", f"{others[0]}=first"] if others else None
    ),
    "all twice": lambda others, person, seats: ["all=random", "all=first"],
    "a seat named twice": lambda others, person, seats: (
        [f"{others[0]}=first", f"{others[0]}=random", *(f"{seat}=random" for seat in others[1:])]
        if others
        else None
    ),
    "the person's own seat": lambda others, person, seats: [f"{person}=first", "rest=random"],
    "a seat past the table": lambda others, person, seats: [f"{seats}=first", "rest=random"],
    "a seat number too long to read": lambda others, person, seats: ["9" * 5000 + "=first", "rest=random"],
}

_REFUSALS: dict[str, str] = {
    "one seat": "seats one player",
    "unnamed": "name who plays the other seats",
    "rest fills none": "fills no seat",
    "rest beside none": "and none is named",
    "rest twice": "give rest once",
    "all alone": "stands alone",
    "a seat twice": "name each seat once",
    "own seat": "your own seat",
    "no seat": "names no seat at this table",
}

_ONE_SEAT = {
    ("no --vs", 1): "seated",
    ("all=random", 1): "one seat",
    ("all=first", 1): "one seat",
    ("rest alone", 1): "one seat",
    ("all twice", 1): "one seat",
    ("the person's own seat", 1): "one seat",
    ("a seat past the table", 1): "one seat",
    ("a seat number too long to read", 1): "one seat",
}

_TWO_SEATS = {
    ("no --vs", 2): "unnamed",
    ("all=random", 2): "seated",
    ("all=first", 2): "seated",
    ("each other seat numbered", 2): "seated",
    ("a numbered seat, and rest", 2): "rest fills none",
    ("rest, and a numbered seat", 2): "rest fills none",
    ("rest alone", 2): "rest beside none",
    ("every other seat numbered, and rest", 2): "rest fills none",
    ("rest twice", 2): "rest twice",
    ("all beside a numbered seat", 2): "all alone",
    ("all twice", 2): "all alone",
    ("a seat named twice", 2): "a seat twice",
    ("the person's own seat", 2): "own seat",
    ("a seat past the table", 2): "no seat",
    ("a seat number too long to read", 2): "no seat",
}


def _several(seats: int) -> dict[tuple[str, int], str]:
    return {
        ("no --vs", seats): "unnamed",
        ("all=random", seats): "seated",
        ("all=first", seats): "seated",
        ("each other seat numbered", seats): "seated",
        ("a numbered seat, and rest", seats): "seated",
        ("rest, and a numbered seat", seats): "seated",
        ("a seat left unnamed", seats): "unnamed",
        ("rest alone", seats): "rest beside none",
        ("every other seat numbered, and rest", seats): "rest fills none",
        ("rest twice", seats): "rest twice",
        ("all beside a numbered seat", seats): "all alone",
        ("all twice", seats): "all alone",
        ("a seat named twice", seats): "a seat twice",
        ("the person's own seat", seats): "own seat",
        ("a seat past the table", seats): "no seat",
        ("a seat number too long to read", seats): "no seat",
    }


_COMPOSED: dict[tuple[str, int], str] = {**_ONE_SEAT, **_TWO_SEATS, **_several(3), **_several(4), **_several(5)}


def test_every_shape_at_every_table_is_authored() -> None:
    derived = {
        (shape, seats)
        for shape, build in _SHAPES.items()
        for seats in _TABLES
        if build(list(range(1, seats)), 0, seats) is not None
    }
    assert derived == set(_COMPOSED), "decide what each new composition does at each table"


def _meant(items: Sequence[str], others: Sequence[int]) -> dict[int, str]:
    """The opponent each other seat gets from a composition that seats them."""
    read = [item.partition("=") for item in items]
    numbered = {int(who): opponent for who, _, opponent in read if who.isdecimal()}
    fill = next((opponent for who, _, opponent in read if who in ("all", "rest")), None)
    return {seat: numbered.get(seat, fill or "") for seat in others}


def _composition_cells() -> list[tuple[str, int, int]]:
    return [(shape, seats, person) for shape, seats in sorted(_COMPOSED) for person in sorted({0, seats - 1})]


@pytest.mark.parametrize(("shape", "seats", "person"), _composition_cells())
def test_each_composition_seats_every_other_seat_or_is_refused(
    shape: str, seats: int, person: int, tmp_path: Path, sit: _Sit
) -> None:
    """red under: let a later `--vs` naming a seat replace an earlier one."""
    path = _path(_TABLES[seats])
    others = [seat for seat in range(seats) if seat != person]
    items = _SHAPES[shape](others, person, seats)
    assert items is not None
    saved = tmp_path / "saved.json"
    argv = [path, "--seat", str(person), "--seed", str(_SEED), "--save", str(saved), *_vs(items)]
    sitting = sit(argv, "q\n")
    assert "Traceback" not in sitting.err
    expected = _COMPOSED[(shape, seats)]
    if expected == "seated":
        assert sitting.code == 0, sitting.err
        meant = _meant(items, others)
        assert _saved(saved)["opponents"] == {str(seat): name for seat, name in meant.items()}
        return
    assert sitting.code == 2, sitting.err
    assert sitting.out == ""
    assert not sitting.asks
    assert not saved.exists()
    assert _REFUSALS[expected] in sitting.err, sitting.err


def test_each_opponent_answers_the_seats_it_is_named_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """red under: seat the opponent `rest` names at every other seat."""
    answered: dict[str, set[int]] = {"first": set(), "random": set()}
    first, uniform = FirstSeatPolicy.__call__, UniformSeatPolicy.__call__

    def by_first(self: FirstSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        answered["first"].add(view.player)
        return first(self, view, legal)

    def by_uniform(self: UniformSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        answered["random"].add(view.player)
        return uniform(self, view, legal)

    monkeypatch.setattr(FirstSeatPolicy, "__call__", by_first)
    monkeypatch.setattr(UniformSeatPolicy, "__call__", by_uniform)
    path = _path("cardlang_hearts")
    sitting = sit([path, "--seed", str(_SEED), *_vs(["2=first", "rest=random"])], "1\n1\n1\n1\nq\n")
    assert sitting.code == 0, sitting.err
    assert answered == {"first": {2}, "random": {1, 3}}


# ---------------------------------------------------------------------------
# The refusal of a missing `--vs`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("short_name", "file_name", "unnamed"),
    [
        ("cardlang_hearts", "hearts.cardlang", "P1, P2 and P3 need an opponent"),
        ("cardlang_kuhn_poker", "kuhn.cardlang", "P1 needs an opponent"),
    ],
)
def test_no_vs_is_refused_naming_the_seats_a_command_and_the_opponents(
    short_name: str, file_name: str, unnamed: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    monkeypatch.chdir(tmp_path)
    Path(file_name).write_text(Path(_path(short_name)).read_text())
    sitting = sit([file_name], "q\n")
    listing = ", ".join(f"{name} ({row.description})" for name, row in OPPONENTS.items())
    assert sitting.code == 2
    assert sitting.out == ""
    assert sitting.err == (
        f"cardlang: name who plays the other seats: you are P0, and {unnamed}, for example\n"
        f"    cardlang play {file_name} --vs all=random\n"
        f"the opponents: {listing}\n"
    )


# Names as a person's folders and files come, and the options they gave.
_GIVEN: dict[str, tuple[str, str, str]] = {
    "plain names": ("games", "kuhn.cardlang", "saved.json"),
    "names with spaces": ("my games", "kuhn poker.cardlang", "my game.json"),
    "names a shell reads": ("$HOME", "kuhn $(date).cardlang", "it's $(date).json"),
    "names beginning with a dash": ("-games", "-kuhn.cardlang", "-saved.json"),
}


@pytest.mark.parametrize("names", sorted(_GIVEN))
def test_the_command_the_refusal_prints_carries_the_options_and_seats_the_game(
    names: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """red under: print the command with the game's path alone."""
    folder_name, game_name, save_name = _GIVEN[names]
    monkeypatch.chdir(tmp_path)
    Path(folder_name).mkdir()
    game = Path(folder_name) / game_name
    game.write_text(Path(_path("cardlang_kuhn_poker")).read_text())
    saved = Path(folder_name) / save_name
    refused = sit(["--seat", "1", "--seed", "3", f"--save={saved}", "--", str(game)], "q\n")
    assert refused.code == 2
    (command,) = [line.strip() for line in refused.err.splitlines() if line.strip().startswith("cardlang play")]
    argv = shlex.split(command)
    assert argv[:2] == ["cardlang", "play"] and Path(argv[2]) == game
    given = list(zip(argv[3::2], argv[4::2]))
    assert ("--seat", "1") in given and ("--seed", "3") in given
    assert ("--vs", "all=random") in given
    assert any(option == "--save" and Path(value) == saved for option, value in given)
    again = sit(argv[2:], "q\n")
    assert again.code == 0, again.err
    assert again.asks and again.asks[0].view.player == 1
    assert _saved(saved)["opponents"] == {"0": "random"}


def test_a_composition_that_leaves_seats_unnamed_is_refused_with_a_command_that_completes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("hearts.cardlang").write_text(Path(_path("cardlang_hearts")).read_text())
    refused = sit(["hearts.cardlang", "--seed", "3", *_vs(["1=first"])], "q\n")
    assert refused.code == 2
    assert "you are P0, and P2 and P3 need an opponent" in refused.err
    (command,) = [line.strip() for line in refused.err.splitlines() if line.strip().startswith("cardlang play")]
    argv = shlex.split(command)
    assert argv[argv.index("1=first") - 1] == "--vs" and argv[argv.index("rest=random") - 1] == "--vs"
    again = sit([*argv[2:], "--save", "saved.json"], "q\n")
    assert again.code == 0, again.err
    assert _saved(Path("saved.json"))["opponents"] == {"1": "first", "2": "random", "3": "random"}


# ---------------------------------------------------------------------------
# `--vs` beside `--resume`.
# ---------------------------------------------------------------------------

_RECORDED = {"0": "first", "1": "random", "3": "random"}
_DIFFERS = "does not name the same opponents"

# A Hearts game saved at seat 2 against `_RECORDED`, resumed beside these items.
_RESUMED: dict[str, tuple[list[str], str]] = {
    "no --vs": ([], "seated"),
    "the recorded opponents, by rest": (["0=first", "rest=random"], "seated"),
    "the recorded opponents, seat by seat": (["0=first", "1=random", "3=random"], "seated"),
    "the recorded opponents, rest first": (["rest=random", "3=random", "0=first"], "seated"),
    "all=random": (["all=random"], _DIFFERS),
    "all=first": (["all=first"], _DIFFERS),
    "one seat named otherwise": (["0=random", "rest=random"], _DIFFERS),
    "a seat left unnamed": (["0=first", "1=random"], _DIFFERS),
    "all beside a numbered seat": (["all=random", "0=first"], _REFUSALS["all alone"]),
    "the person's own seat": (["2=first", "rest=random"], _REFUSALS["own seat"]),
}


@pytest.mark.parametrize("case", sorted(_RESUMED))
def test_vs_beside_resume_agrees_with_the_saved_game_or_is_refused(case: str, tmp_path: Path, sit: _Sit) -> None:
    """red under: let `--vs` beside `--resume` replace the recorded opponents."""
    path = _path("cardlang_hearts")
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_a_save(path, seat=2, seed=_SEED, history=[], opponents=_RECORDED)))
    kept = resume.read_text()
    items, expected = _RESUMED[case]
    sitting = sit([path, "--resume", str(resume), *_vs(items)], "q\n")
    assert "Traceback" not in sitting.err
    if expected == "seated":
        assert sitting.code == 0, sitting.err
        assert sitting.asks and sitting.asks[0].view.player == 2
        assert _saved(resume)["opponents"] == _RECORDED
        return
    assert sitting.code == 2
    assert not sitting.asks
    assert str(resume) in sitting.err and expected in sitting.err, sitting.err
    assert resume.read_text() == kept
    if expected == _DIFFERS:
        assert "--vs 0=first --vs 1=random --vs 3=random" in sitting.err
        assert "leave --vs out" in sitting.err


def test_a_resumed_game_seats_the_opponents_its_file_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sit: _Sit
) -> None:
    """Hearts passes seat by seat, so P0 and P1 pass before P2 is asked.

    red under: seat `random` at every other seat of a resumed game."""
    answered: dict[int, str] = {}
    first, uniform = FirstSeatPolicy.__call__, UniformSeatPolicy.__call__

    def by_first(self: FirstSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        answered[view.player] = "first"
        return first(self, view, legal)

    def by_uniform(self: UniformSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        answered[view.player] = "random"
        return uniform(self, view, legal)

    monkeypatch.setattr(FirstSeatPolicy, "__call__", by_first)
    monkeypatch.setattr(UniformSeatPolicy, "__call__", by_uniform)
    path = _path("cardlang_hearts")
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_a_save(path, seat=2, seed=_SEED, history=[], opponents=_RECORDED)))
    sitting = sit([path, "--resume", str(resume)], "q\n")
    assert sitting.code == 0, sitting.err
    assert answered == {0: "first", 1: "random"}


@pytest.mark.parametrize(
    ("opponents", "items", "expected"),
    [
        ({}, [], "seated"),
        ({}, ["all=random"], "seats one player"),
        ({"1": "random"}, [], "seats one player"),
    ],
)
def test_a_game_of_one_seat_resumes_with_no_opponent(
    opponents: dict[str, str], items: list[str], expected: str, tmp_path: Path, sit: _Sit
) -> None:
    path = _path("cardlang_freecell")
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_a_save(path, seat=0, seed=_SEED, history=[], opponents=opponents)))
    sitting = sit([path, "--resume", str(resume), *_vs(items)], "q\n")
    assert "Traceback" not in sitting.err
    if expected == "seated":
        assert sitting.code == 0, sitting.err
        return
    assert sitting.code == 2
    assert not sitting.asks
    assert expected in sitting.err, sitting.err


# ---------------------------------------------------------------------------
# Which refusal a person meets first.
# ---------------------------------------------------------------------------

# Each pair: the invocation, the refusal it meets, the refusal it does not, and
# whether argparse refuses it.
_PRECEDENCE: dict[str, tuple[Callable[[Path], list[str]], str, str, bool]] = {
    "a seat past the table, beside --vs naming it": (
        lambda tmp_path: [_path("cardlang_kuhn_poker"), "--seat", "9", *_vs(["9=first"])],
        "--seat 9 names no seat",
        "--vs 9=first",
        False,
    ),
    "no --vs, beside a save to a directory": (
        lambda tmp_path: [_path("cardlang_kuhn_poker"), "--save", str(tmp_path)],
        _REFUSALS["unnamed"],
        "it is a directory",
        False,
    ),
    "a saved game of another game, beside a composition refused": (
        lambda tmp_path: [
            _path("cardlang_kuhn_poker"),
            "--resume",
            str(_written_save(tmp_path, _path("cardlang_hearts"))),
            *_vs(["all=random", "1=first"]),
        ],
        "different game",
        _REFUSALS["all alone"],
        False,
    ),
    "a value refused, beside a game file that does not exist": (
        lambda tmp_path: [str(tmp_path / "missing.cardlang"), *_vs(["1=randon"])],
        _NO_OPPONENT,
        "no such file",
        True,
    ),
}


def _written_save(tmp_path: Path, path: str) -> Path:
    saved = tmp_path / "other.json"
    saved.write_text(json.dumps(_a_save(path, seat=0, seed=_SEED, history=[])))
    return saved


@pytest.mark.parametrize("pair", sorted(_PRECEDENCE))
def test_each_vs_refusal_meets_its_neighbours_in_order(
    pair: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], sit: _Sit
) -> None:
    make, meets, not_met, usage = _PRECEDENCE[pair]
    if usage:
        with pytest.raises(SystemExit) as exit_info:
            sit(make(tmp_path), "q\n")
        assert exit_info.value.code == 2
        err = capsys.readouterr().err
    else:
        sitting = sit(make(tmp_path), "q\n")
        assert sitting.code == 2
        err = sitting.err
    assert meets in err and not_met not in err, err


# ---------------------------------------------------------------------------
# What a person is shown.
# ---------------------------------------------------------------------------

_HEADERS: dict[tuple[str, int, tuple[str, ...]], list[str]] = {
    ("cardlang_kuhn_poker", 0, ("all=random",)): ["P1: random (picks uniformly at random)"],
    ("cardlang_hearts", 0, ("all=first",)): ["P1, P2 and P3: first (always takes the first pick on the menu)"],
    ("cardlang_hearts", 2, ("0=first", "rest=random")): [
        "P0: first (always takes the first pick on the menu)",
        "P1 and P3: random (picks uniformly at random)",
    ],
    ("cardlang_freecell", 0, ()): [],
}


@pytest.mark.parametrize(("short_name", "seat", "items"), sorted(_HEADERS))
def test_the_header_names_each_other_seats_opponent(
    short_name: str, seat: int, items: tuple[str, ...], sit: _Sit
) -> None:
    """red under: give every other seat a line of its own."""
    path = _path(short_name)
    game, _ = load(path)
    sitting = sit([path, "--seat", str(seat), "--seed", "11", *_vs(items)], "q\n")
    assert sitting.code == 0, sitting.err
    head = sitting.out.split("\n\n", 1)[0].splitlines()
    assert head == [f"{game.name}: you are P{seat}, seed 11", *_HEADERS[(short_name, seat, items)]]


def test_a_game_that_refuses_names_who_played_each_seat(sit: _Sit) -> None:
    sitting = sit([str(FIXTURES / "empty_zone_choice.cardlang"), "--seed", str(_SEED), *_vs(["all=first"])], "1\n")
    assert sitting.code == 1
    assert "Traceback" not in sitting.err
    assert "P1: first (always takes the first pick on the menu); P0 was you" in sitting.err


# ---------------------------------------------------------------------------
# What the opponents play.
# ---------------------------------------------------------------------------

# The picks the person makes, each the first item, before leaving.
_PERSON_PICKS = 8


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_first_answers_as_a_person_picking_the_first_item(short_name: str, tmp_path: Path, sit: _Sit) -> None:
    """The person at seat 0 with `first` at seat 1, and the person at seat 1
    with `first` at seat 0, play one line.

    red under: a `first` that answers `legal[-1]`."""
    path = _path(short_name)
    game, _ = load(path)
    if game.players.low == 1:
        pytest.skip("a game of one seat has no seat for an opponent")
    rest = ["rest=random"] if game.players.low > 2 else []
    lines = []
    for person, other in ((0, 1), (1, 0)):
        saved = tmp_path / f"seat-{person}.json"
        argv = [path, "--seat", str(person), "--seed", str(_SEED), "--save", str(saved), *_vs([f"{other}=first", *rest])]
        sitting = sit(argv, "1\n" * _PERSON_PICKS + "q\n")
        assert sitting.code == 0, sitting.err
        lines.append(list(_saved(saved)["history"]))
    shorter, longer = sorted(lines, key=len)
    assert longer[: len(shorter)] == shorter
    assert {0, 1} <= set(_replayed(path, _SEED, shorter).deciders), f"{short_name}: the line reached one seat"


# Each line on seed 5 with the person answering 1 six times and a uniform draw
# at every other seat, as the saved history holds it.
_UNIFORM_LINES: dict[tuple[str, int], list[int]] = {
    ("cardlang_kuhn_poker", 0): [0, 0],
    ("cardlang_holdem", 2): [2, 2, 0, 0, 0, 0, 0, 0, 1, 2, 2, 0, 0, 0, 2, 4, 2],
    ("cardlang_hearts", 0): [
        9, 11, 18, 17, 12, 34, 23, 6, 7, 3, 44, 41, 0,
        6, 3, 2, 22, 25, 21, 17, 40, 11, 45, 39, 13, 16,
    ],
    ("cardlang_hearts", 3): [
        36, 50, 27, 17, 12, 34, 23, 6, 7, 1, 3, 10, 0,
        6, 3, 4, 7, 1, 2, 8, 12, 15, 11, 28, 24,
    ],
    ("cardlang_president", 1): [
        193, 52, 52, 52, 52, 101, 52, 52, 67, 63, 90, 52, 93, 91, 52, 52,
        52, 52, 82, 104, 80, 52, 52, 79, 54, 52, 52, 52, 52, 100, 64,
    ],
}


def _line_against(opponent: str, short_name: str, seat: int, tmp_path: Path, sit: _Sit) -> list[int]:
    saved = tmp_path / "saved.json"
    argv = [_path(short_name), "--seat", str(seat), "--seed", str(_SEED), "--save", str(saved), *_vs([f"all={opponent}"])]
    sitting = sit(argv, "1\n" * 6 + "q\n")
    assert sitting.code == 0, sitting.err
    return list(_saved(saved)["history"])


@pytest.mark.parametrize(("short_name", "seat"), sorted(_UNIFORM_LINES))
def test_all_random_plays_the_line_a_uniform_draw_at_every_other_seat_plays(
    short_name: str, seat: int, tmp_path: Path, sit: _Sit
) -> None:
    """red under: seat `UniformSeatPolicy(seed + seat)` at each seat."""
    assert _line_against("random", short_name, seat, tmp_path, sit) == _UNIFORM_LINES[(short_name, seat)]


@pytest.mark.parametrize(
    ("short_name", "seat"), sorted(key for key, line in _UNIFORM_LINES.items() if len(line) > 2)
)
def test_all_first_plays_another_line(short_name: str, seat: int, tmp_path: Path, sit: _Sit) -> None:
    """The control for the lines above, on each line long enough for a draw to
    differ from the first item: a table that seated `random` whatever it was
    told would pass them.

    red under: read every `--vs` opponent as `random`."""
    assert _line_against("first", short_name, seat, tmp_path, sit) != _UNIFORM_LINES[(short_name, seat)]
