"""Every refusal `check`, `demo` and `play` tell, as a record and as text.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every refusal the command line tells once the line is read
                 exits with the status its author names -- the game's or a
                 library's 1, the invocation's, the installation's or a
                 registration's 2, the engine's 3, the highest of them where
                 one run tells several -- in the text and under `--json`
                 alike; under `--json` stdout holds exactly one Record
                 Envelope and nothing else, every refusal is a record with
                 its code and author, and nothing the text prints as a
                 transcript is lost: it goes to stderr word for word; and the
                 text a refusal prints is its record re-rendered in its
                 code's layout, so the record carries every line the text
                 prints, in the order printed.
domain:          the authors, crossed with the status each names; every
                 runtime refusal type, derived as tests/test_records.py
                 derives them, raised where a check, a playout, a table's
                 load and a table's session raise, and where a query's check
                 raises, crossed with the two
                 output forms; an exception outside the typed channels, raised
                 while the command is carried out (an `OSError` the path
                 probe meets before it is issue #1097's), under
                 every command, crossed with the two forms; and the command
                 lines `_LINES` lists, one or more per refusal the command
                 line composes, crossed with the two forms; three of those
                 refusals no input on disk reaches (a save failing at the
                 table, a resumed game's picks that no longer replay, a
                 decision a table cannot number), so their rows plant the
                 raise where it is met. The lines are
                 hand-written, and every Diagnostic Code `cardlang/cli.py`
                 names is either a code a row of `_LINES` tells, a refusal of
                 the line's words (`_LINE_REFUSALS`, refused before the line
                 is read and so text under `--json`, witnessed in
                 tests/test_command_line_slips.py), or `engine-gap`.
                 An engine failure's traceback goes to stderr in both forms;
                 its record carries the exception's message.
registry:        the authors -- `cardlang.diagnostics.Author`; the runtime
                 refusal types -- tests/test_records.py::_refusal_types; the
                 codes the command line names -- a scrape of `Code.` in
                 `cardlang/cli.py`; the commands -- `cardlang.cli.COMMANDS`;
                 every command taking `--json` --
                 tests/test_cli_surface.py::test_command_option_cell.
held by:         Unrepresentable for the status of an author: `cli._status`
                 is an exhaustive match ending in `assert_never`. Derived and
                 Pinned for the rest: a command line's outcome is no type.
does not prove:  that a layout's lines say what the refusal means; the
                 re-rendering proves the text and the record hold the same
                 words, not that the words are right.
"""

from __future__ import annotations

import ast
import io
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from cardlang import cli
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Author
from cardlang.pipeline import check_source, game_identity
from cardlang.play import session as play_session
from cardlang.records import read_envelope
from cardlang.runtime import errors
from cardlang.openspiel.replay import HistoryMismatch
from tests.test_records import EXPECTED as REFUSAL_EXPECTED
from tests.test_records import _refusal, _refusal_types

_ROOT = Path(__file__).resolve().parent.parent
KUHN = str(_ROOT / "docs" / "games" / "kuhn-poker.cardlang")
# Deals and scores without asking anyone to choose.
SKELETON = str(_ROOT / "tests" / "fixtures" / "skeleton.md")

# The status each author names: authored, never read off `cli._status`.
STATUS: dict[Author, int] = {
    Author.GAME: 1,
    Author.LIBRARY: 1,
    Author.INVOCATION: 2,
    Author.INSTALLATION: 2,
    Author.REGISTRATION: 2,
    Author.ENGINE: 3,
}


def test_every_author_has_its_status() -> None:
    assert set(STATUS) == set(Author)
    for author in Author:
        assert cli._status(author) == STATUS[author], author


@dataclass(frozen=True)
class _Ran:
    status: int
    out: str
    err: str


def _run(argv: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> _Ran:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    try:
        status = cli.main(argv)
    except SystemExit as exit_info:
        assert isinstance(exit_info.code, int)
        status = exit_info.code
    out, err = capsys.readouterr()
    return _Ran(status, out, err)


def _records(ran: _Ran) -> list[dict[str, object]]:
    """The one Record Envelope `--json` prints, its records; nothing else may
    stand on stdout."""
    document = json.loads(ran.out)
    read_envelope(document)
    records = document["diagnostics"]
    assert isinstance(records, list)
    return records


def _lines(record: dict[str, object]) -> list[str]:
    notes = record["notes"]
    assert isinstance(notes, list)
    return [n["message"] for n in notes]


def _located(record: dict[str, object]) -> str:
    span = record["span"]
    message = str(record["message"])
    if span is None:
        return f"  {message}"
    assert isinstance(span, dict)
    return f"{span['file']}:{span['line']}:{span['column']}: {record['severity']}: {message}"


def _as_a_line(record: dict[str, object]) -> str:
    """A refusal of the command's own: every line led by `cardlang: `."""
    return "".join(f"cardlang: {line}\n" for line in [str(record["message"]), *_lines(record)])


def _as_a_playout(record: dict[str, object]) -> str:
    """A refusal met loading or playing a game: the heading, the refusal at
    its sentence, then the lines told with it, indented."""
    heading, *rest = _lines(record)
    return f"cardlang: {heading}\n{_located(record)}\n" + "".join(f"  {line}\n" for line in rest)


# The layout each code's text takes, re-rendered from its record alone.
_LAYOUT: dict[str, Callable[[dict[str, object]], str]] = {
    Code.REFUSED_DURING_PLAY.slug: _as_a_playout,
    Code.GAME_ERROR_RAISED.slug: _as_a_playout,
    Code.ENGINE_GAP.slug: _as_a_playout,
    Code.INCOMPLETE_INSTALLATION.slug: _as_a_playout,
    Code.UNREGISTRABLE_GAME.slug: _as_a_line,
}


def _rendered(records: list[dict[str, object]]) -> str:
    return "".join(_LAYOUT.get(str(r["code"]), _as_a_line)(r) for r in records)


def _both(
    argv: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> tuple[_Ran, _Ran, list[dict[str, object]]]:
    text = _run(argv, capsys, monkeypatch)
    as_json = _run([*argv, "--json"], capsys, monkeypatch)
    return text, as_json, _records(as_json)


# --- the runtime's typed refusals, wherever a command meets one ---------------


def _raising(exc: BaseException) -> Callable[..., object]:
    def raised(*_args: object, **_kwargs: object) -> object:
        raise exc

    return raised


# Where each command meets a refusal, and the line that reaches it.
_WHERE: dict[str, tuple[Callable[[pytest.MonkeyPatch, BaseException], None], list[str]]] = {
    "check": (lambda mp, exc: mp.setattr(cli, "check_source", _raising(exc)), ["check", KUHN]),
    "demo": (lambda mp, exc: mp.setattr(cli, "play_game", _raising(exc)), ["demo", KUHN, "--seed", "1"]),
    "play, loading": (
        lambda mp, exc: mp.setattr(cli, "load", _raising(exc)),
        ["play", KUHN, "--seed", "1", "--vs", "all=random"],
    ),
    "play, at the table": (
        lambda mp, exc: mp.setattr(play_session.Session, "run", _raising(exc)),
        ["play", KUHN, "--seed", "1", "--vs", "all=random"],
    ),
    "query": (lambda mp, exc: mp.setattr(cli, "check_source", _raising(exc)), ["query", KUHN, "--at", "76:24"]),
}


@pytest.mark.parametrize("where", sorted(_WHERE))
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name,
            marks=[pytest.mark.expects_shadow_guard] if name == errors.ShadowGuardError.__name__ else [],
        )
        for name in sorted(REFUSAL_EXPECTED)
    ],
)
def test_a_runtime_refusal_is_its_record_in_both_forms(
    name: str, where: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (cls,) = (c for c in _refusal_types() if c.__name__ == name)
    patch, argv = _WHERE[where]
    exc = _refusal(cls)
    if isinstance(exc, errors.Located):
        exc.locate(phase="deal", zone="deck")
    patch(monkeypatch, exc)
    text, as_json, records = _both(argv, capsys, monkeypatch)
    code, author = REFUSAL_EXPECTED[name]
    (record,) = records
    assert (record["code"], record["author"]) == (code.slug, author.value)
    assert text.status == as_json.status == STATUS[author]
    assert text.out == as_json.err, "the transcript moves to stderr word for word"
    assert text.err == _rendered(records)
    assert ("in phase deal, moving from deck" in _lines(record)) is isinstance(exc, errors.Located)


# --- an exception outside the typed channels ---------------------------------


_CRASHING: dict[str, list[str]] = {
    "check": ["check", KUHN],
    "demo": ["demo", KUHN, "--seed", "1"],
    "play": ["play", KUHN, "--seed", "1", "--vs", "all=random"],
    "query": ["query", KUHN, "--at", "76:24"],
}


def test_every_command_meets_an_engine_failure() -> None:
    """red under: a fifth row in `cli._COMMAND_TABLE`."""
    assert set(_CRASHING) == set(cli.COMMANDS)


@pytest.mark.parametrize("command", sorted(_CRASHING))
def test_an_engine_failure_exits_3_and_keeps_its_traceback(
    command: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    crash = _raising(AssertionError("an engine invariant"))
    monkeypatch.setattr(cli, "check_source", crash)
    monkeypatch.setattr(cli, "load", crash)
    text = _run(_CRASHING[command], capsys, monkeypatch)
    as_json = _run([*_CRASHING[command], "--json"], capsys, monkeypatch)
    assert text.status == as_json.status == 3
    for ran in (text, as_json):
        assert "Traceback (most recent call last)" in ran.err
        assert ran.err.rstrip().endswith("AssertionError: an engine invariant")
    assert text.out == ""
    document = json.loads(as_json.out)
    read_envelope(document)
    (record,) = document["diagnostics"]
    assert (record["code"], record["author"], record["message"]) == (
        "engine-gap", "engine", "an engine invariant"
    )


# --- the command's own refusals ----------------------------------------------


def _saved(tmp: Path, **fields: object) -> str:
    game = check_source(Path(KUHN))
    record: dict[str, object] = {
        "cardlang_session": 2,
        "game": game.name,
        "identity": game_identity(game),
        "seed": 7,
        "seat": 0,
        "opponents": {"1": "random"},
        "history": [],
        **fields,
    }
    path = tmp / "saved.json"
    path.write_text(json.dumps(record))
    return str(path)


@dataclass(frozen=True)
class _Line:
    """A command line, the codes its refusals carry in order, and anything the
    line needs set up: files in `tmp`, or a raise planted where it is met."""

    argv: Callable[[Path], list[str]]
    codes: tuple[Code, ...]
    patch: Callable[[pytest.MonkeyPatch], None] = field(default=lambda _mp: None)


def _bounded(tmp: Path) -> str:
    from tests.test_length_stop import bounded_tic_tac_toe

    path = tmp / "bounded.cardlang"
    path.write_text(bounded_tic_tac_toe())
    return str(path)


# Seed 0 of the bounded game places five marks without a win (tests/test_cli_surface.py).
_STOPS = "0"

_LINES: dict[str, _Line] = {
    "demo: --info-state names no seat": _Line(lambda _t: ["demo", KUHN, "--info-state", "5"], (Code.OUT_OF_RANGE,)),
    "demo: --view names no seat": _Line(lambda _t: ["demo", KUHN, "--view", "9"], (Code.OUT_OF_RANGE,)),
    "demo: --at with no seat to show": _Line(lambda _t: ["demo", KUHN, "--at", "0"], (Code.COMMAND_LINE_USAGE,)),
    "demo: --at before the first decision": _Line(
        lambda _t: ["demo", KUHN, "--at", "-1", "--view", "0"], (Code.OUT_OF_RANGE,)
    ),
    "demo: --at past the last decision": _Line(
        lambda _t: ["demo", KUHN, "--seed", "1", "--at", "999", "--view", "0"], (Code.OUT_OF_RANGE,)
    ),
    "demo: a view of a playout with no decision": _Line(
        lambda _t: ["demo", SKELETON, "--seed", "5", "--view", "0"], (Code.SEAT_VIEW_NEEDS_A_DECISION,)
    ),
    "demo: random play reaches max_length": _Line(
        lambda t: ["demo", _bounded(t), "--seed", _STOPS], (Code.RANDOM_PLAY_REACHES_LENGTH_STOP,)
    ),
    "demo: max_length reached, then --at past the last decision": _Line(
        lambda t: ["demo", _bounded(t), "--seed", _STOPS, "--view", "0", "--at", "99"],
        (Code.RANDOM_PLAY_REACHES_LENGTH_STOP, Code.OUT_OF_RANGE),
    ),
    "play: --seat names no seat": _Line(
        lambda _t: ["play", KUHN, "--seat", "5", "--vs", "all=random"], (Code.OUT_OF_RANGE,)
    ),
    "play: no opponent named": _Line(lambda _t: ["play", KUHN], (Code.UNNAMED_OPPONENTS,)),
    "play: one seat named twice": _Line(
        lambda _t: ["play", KUHN, "--vs", "1=random", "--vs", "1=first"], (Code.OPPONENTS_SEATED_WRONGLY,)
    ),
    "play: --vs names the person's own seat": _Line(
        lambda _t: ["play", KUHN, "--vs", "0=random"], (Code.OPPONENTS_SEATED_WRONGLY,)
    ),
    "play: --vs names no seat": _Line(lambda _t: ["play", KUHN, "--vs", "7=random"], (Code.OPPONENTS_SEATED_WRONGLY,)),
    "play: resume a missing file": _Line(
        lambda t: ["play", KUHN, "--resume", str(t / "missing.json")], (Code.SAVED_GAME_NOT_RESUMABLE,)
    ),
    "play: resume a file that is no saved game": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t, cardlang_session=None)], (Code.SAVED_GAME_NOT_RESUMABLE,)
    ),
    "play: resume a game saved at a seat the table lacks": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t, seat=5)], (Code.SAVED_GAME_NOT_RESUMABLE,)
    ),
    "play: resume a game recording an opponent there is not": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t, opponents={"1": "nobody"})], (Code.SAVED_GAME_NOT_RESUMABLE,)
    ),
    "play: resume, its picks no longer replay": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t)],
        (Code.SAVED_GAME_NOT_RESUMABLE,),
        lambda mp: mp.setattr(play_session.Session, "run", _raising(HistoryMismatch("pick 3 is not offered"))),
    ),
    "play: resume at another seat": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t), "--seat", "1"], (Code.CONTRADICTS_SAVED_GAME,)
    ),
    "play: resume with another seed": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t), "--seed", "9"], (Code.CONTRADICTS_SAVED_GAME,)
    ),
    "play: resume against other opponents": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t), "--vs", "1=first"], (Code.CONTRADICTS_SAVED_GAME,)
    ),
    "play: resume, seating the opponents wrongly": _Line(
        lambda t: ["play", KUHN, "--resume", _saved(t), "--vs", "0=first"], (Code.OPPONENTS_SEATED_WRONGLY,)
    ),
    "play: save into a directory that is not there": _Line(
        lambda t: ["play", KUHN, "--vs", "all=random", "--save", str(t / "nodir" / "x.json")],
        (Code.UNWRITABLE_SAVE_FILE,),
    ),
    "play: a save failing at the table": _Line(
        lambda t: ["play", KUHN, "--vs", "all=random", "--save", str(t / "x.json")],
        (Code.UNWRITABLE_SAVE_FILE,),
        lambda mp: mp.setattr(play_session.Session, "run", _raising(play_session.SaveFailed("cannot save to x.json: disk full"))),
    ),
    "play: a decision a table cannot number": _Line(
        lambda _t: ["play", KUHN, "--vs", "all=random"],
        (Code.TABLE_CANNOT_NUMBER_A_DECISION,),
        lambda mp: mp.setattr(cli, "load", _raising(NotImplementedError("no numbering for a `choose integer`"))),
    ),
    "check: a path that names nothing": _Line(lambda t: ["check", str(t / "missing.cardlang")], (Code.UNREADABLE_FILE,)),
    "check, named by no command: a path that names nothing": _Line(
        lambda t: [str(t / "missing.cardlang")], (Code.UNREADABLE_FILE,)
    ),
    "demo: a path that names nothing": _Line(lambda t: ["demo", str(t / "missing.cardlang")], (Code.UNREADABLE_FILE,)),
    "play: a path that names nothing": _Line(lambda t: ["play", str(t / "missing.cardlang")], (Code.UNREADABLE_FILE,)),
}


@pytest.mark.parametrize("name", sorted(_LINES))
def test_a_command_s_own_refusal_is_its_record_in_both_forms(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    line = _LINES[name]
    line.patch(monkeypatch)
    text, as_json, records = _both(line.argv(tmp_path), capsys, monkeypatch)
    assert tuple(r["code"] for r in records) == tuple(c.slug for c in line.codes)
    statuses = [STATUS[Author(r["author"])] for r in records if r["severity"] == "error"]
    assert text.status == as_json.status == max(statuses)
    if Code.RANDOM_PLAY_REACHES_LENGTH_STOP in line.codes:
        # The Length Stop's line leads the transcript; the record carries it.
        stop, *rest = records
        assert text.out.splitlines()[0] == stop["message"]
        assert (stop["author"], _lines(stop)) == ("game", [])
        records = rest
    assert text.out == as_json.err, "the transcript moves to stderr word for word"
    assert text.err == _rendered(records)


def test_the_hint_beside_an_unreadable_first_word_is_a_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _text, _as_json, records = _both([str(tmp_path / "missing.cardlang")], capsys, monkeypatch)
    (record,) = records
    assert _lines(record) == [f"if you meant a command, they are: {', '.join(cli.COMMANDS)}"]
    assert record["notes"] == [{"span": None, "message": _lines(record)[0]}]


# The refusals of the line's words: told before the line is read, so text
# under `--json` as well.
_LINE_REFUSALS: frozenset[Code] = frozenset(
    {
        Code.UNKNOWN_COMMAND,
        Code.COMMAND_GOES_FIRST,
        Code.UNKNOWN_COMMAND_LINE_OPTION,
        Code.COMMAND_LINE_OPTION_OF_ANOTHER_COMMAND,
        Code.FILE_NAME_READS_AS_COMMAND_LINE_OPTION,
        Code.EXTRA_WORD,
        Code.MISSING_GAME_FILE,
    }
)


def _codes_named_in_cli() -> set[Code]:
    tree = ast.parse(Path(cli.__file__).read_text())
    return {
        Code[node.attr]
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "Code"
    }


def test_every_code_the_command_line_names_has_a_line() -> None:
    """red under: `_play`'s numbering refusal coded `Code.NOT_YET_SUPPORTED`,
    a code no row of `_LINES` tells."""
    told = {c for line in _LINES.values() for c in line.codes}
    assert _codes_named_in_cli() - _LINE_REFUSALS - {Code.ENGINE_GAP} <= told
    assert not _LINE_REFUSALS & told


# --- the most plausible wrong lines a tool writes with `--json` --------------


@pytest.mark.parametrize(
    "argv",
    [
        ["play", "--json"],
        ["demo", KUHN, "--json", "--emit-ir"],
        ["play", KUHN, "--json", "--decisions"],
        ["check", KUHN, "--json", "--seed", "1"],
    ],
    ids=lambda argv: " ".join(a for a in argv if a != KUHN),
)
def test_a_line_refused_before_it_is_read_stays_text_under_json(
    argv: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """red under: `_refuse` printing the usage line on stdout."""
    ran = _run(argv, capsys, monkeypatch)
    assert (ran.status, ran.out) == (2, "")
    assert "usage:" in ran.err


def test_the_bare_form_takes_json(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """red under: `main` building `_Telling(args.json and not implicit)`."""
    ran = _run([KUHN, "--json"], capsys, monkeypatch)
    assert (ran.status, ran.err, _records(ran)) == (0, "", [])


@pytest.mark.parametrize("argv", [["demo", KUHN, "--seed", "1", "--decisions", "--view", "1"],
                                  ["play", KUHN, "--seed", "1", "--vs", "all=random"]],
                         ids=["demo", "play"])
def test_a_clean_run_under_json_is_an_empty_envelope_and_its_transcript(
    argv: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    text = _run(argv, capsys, monkeypatch)
    as_json = _run([*argv, "--json"], capsys, monkeypatch)
    assert (text.status, as_json.status, _records(as_json)) == (0, 0, [])
    assert (text.err, as_json.err) == ("", text.out)
