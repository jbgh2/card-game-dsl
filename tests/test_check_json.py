"""`cardlang check --json`: one Record Envelope on stdout, whatever the outcome.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        once the command line is read, `check --json` prints exactly
                 one Record Envelope on stdout and nothing on stderr but an
                 engine failure's traceback, exits with the code the text
                 output exits with, and exits 1 exactly when every error it
                 records is a game's or a library's to fix, 3 when one is the
                 engine's; `--json` beside `--emit-ir` is refused as a usage
                 error.
domain:          the outcomes of a check -- a game that checks clean, a
                 game refused, a file of an extension the checker does not
                 read, a path that cannot be read, every runtime refusal type
                 a check can raise -- crossed with the two output forms, text
                 and `--json`; the text of a runtime refusal and of an
                 unreadable first word is its record re-rendered. A command line
                 refused before it is read (a usage error, a first word that
                 names no command) is refused as text: `--json` is a word of
                 the line being refused.
registry:        the authors -- `cardlang.diagnostics.Author`; the runtime
                 refusal types -- tests/test_records.py::_refusal_types; `--json` on
                 every command -- tests/test_cli_surface.py::test_command_option_cell.
held by:         Derived and Pinned: the cells are command lines, which no
                 type sees.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cardlang import cli
from cardlang.records import read_envelope
from cardlang.runtime import errors
from cardlang.runtime.errors import GameRegistrationError
from tests.test_records import EXPECTED as REFUSAL_EXPECTED
from tests.test_records import _refusal, _refusal_types

_ROOT = Path(__file__).resolve().parent.parent
HEARTS = _ROOT / "docs" / "games" / "hearts.cardlang"

# The authors whose fix is in a file the check read: the text output's
# exit 1.
_FILE_AUTHORS = {"game", "library"}


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = cli.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def _typo(tmp_path: Path) -> Path:
    path = tmp_path / "hearts.cardlang"
    path.write_text(HEARTS.read_text().replace("from hand[player]", "from hnad[player]", 1))
    return path


def _cases(tmp_path: Path) -> dict[str, Path]:
    unread = tmp_path / "game.txt"
    unread.write_text("game g { }\n")
    return {
        "clean": HEARTS,
        "refused": _typo(tmp_path),
        "extension": unread,
        "unreadable": tmp_path / "missing.cardlang",
    }


@pytest.mark.parametrize("case", ["clean", "refused", "extension", "unreadable"])
def test_json_prints_one_envelope_and_exits_as_the_text_does(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = str(_cases(tmp_path)[case])
    text_exit, _out, _err = _run(["check", path], capsys)
    json_exit, out, err = _run(["check", path, "--json"], capsys)
    assert (json_exit, err) == (text_exit, "")
    document = json.loads(out)
    read_envelope(document)
    errors = [r for r in document["diagnostics"] if r["severity"] == "error"]
    assert (errors == []) == (json_exit == 0)
    if errors:
        assert (json_exit == 1) == all(r["author"] in _FILE_AUTHORS for r in errors)


def test_the_witness_a_typo_in_hearts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _exit, out, _err = _run(["check", str(_typo(tmp_path)), "--json"], capsys)
    (record,) = json.loads(out)["diagnostics"]
    assert (record["code"], record["author"], record["message"]) == (
        "unknown-name", "game", "unresolved name 'hnad'"
    )
    assert record["suggestions"] == [{"text": "hand", "applicability": "offered"}]


def test_json_beside_emit_ir_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """One JSON document on stdout: the IR or the Record Envelope, never both.
    `--json` on another command is a cell of tests/test_cli_surface.py."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["check", str(HEARTS), "--json", "--emit-ir"])
    out, err = capsys.readouterr()
    assert (excinfo.value.code, out) == (2, "")
    assert "not allowed with" in err


def test_a_registration_refusal_is_a_record_and_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refused(_path: object) -> None:
        raise GameRegistrationError("two files claim one short name")

    monkeypatch.setattr(cli, "check_source", refused)
    exit_code, out, err = _run(["check", str(HEARTS), "--json"], capsys)
    (record,) = json.loads(out)["diagnostics"]
    assert (exit_code, err) == (2, "")
    assert (record["code"], record["author"]) == ("unregistrable-game", "registration")


def test_an_engine_failure_prints_its_envelope_and_exits_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An exception outside the typed channels: the envelope tells the
    engine, the traceback goes to stderr, and the status is the engine's 3,
    never the 1 a game at fault gets."""

    def crashed(_path: object) -> None:
        raise AssertionError("an engine invariant")

    monkeypatch.setattr(cli, "check_source", crashed)
    exit_code, out, err = _run(["check", str(HEARTS), "--json"], capsys)
    (record,) = json.loads(out)["diagnostics"]
    assert (record["code"], record["author"], record["message"]) == (
        "engine-gap", "engine", "an engine invariant"
    )
    assert exit_code == 3
    assert "Traceback (most recent call last)" in err


def _as_text(record: dict[str, object]) -> str:
    """A record re-rendered as the text prints its code: a refusal met
    playing a game leads with its first line, prints the refusal at its
    sentence, then the rest indented; any other leads every line with
    `cardlang: `."""
    lines = [n["message"] for n in record["notes"]]  # type: ignore[attr-defined]
    message = str(record["message"])
    if record["code"] == "unregistrable-game":
        return "".join(f"cardlang: {line}\n" for line in [message, *lines])
    span = record["span"]
    located = (
        f"  {message}"
        if span is None
        else f"{span['file']}:{span['line']}:{span['column']}: {record['severity']}: {message}"  # type: ignore[index]
    )
    heading, *rest = lines
    return f"cardlang: {heading}\n{located}\n" + "".join(f"  {line}\n" for line in rest)


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
def test_a_runtime_refusal_s_record_carries_every_line_the_text_prints(
    name: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The text a check prints for a runtime refusal is its record
    re-rendered: the heading, the phase and zone, the advice, all of it.
    red under: `_with_lines` returning `told` unchanged."""
    (cls,) = (c for c in _refusal_types() if c.__name__ == name)
    exc = _refusal(cls)
    if isinstance(exc, errors.Located):
        exc.locate(phase="deal", zone="deck")

    def refused(_path: object) -> None:
        raise exc

    monkeypatch.setattr(cli, "check_source", refused)
    text_exit, _out, err = _run(["check", str(HEARTS)], capsys)
    json_exit, out, _err = _run(["check", str(HEARTS), "--json"], capsys)
    (record,) = json.loads(out)["diagnostics"]
    assert text_exit == json_exit
    assert err == _as_text(record)
    assert all(n["span"] is None for n in record["notes"])


def test_the_hint_beside_an_unreadable_first_word_is_in_its_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A first word that names nothing and stands where a command may: the
    record carries the commands the text names beside it."""
    missing = str(tmp_path / "missing.cardlang")
    _exit, _out, err = _run([missing], capsys)
    _exit, out, _err = _run([missing, "--json"], capsys)
    (record,) = json.loads(out)["diagnostics"]
    assert record["notes"] == [
        {"span": None, "message": f"if you meant a command, they are: {', '.join(cli.COMMANDS)}"}
    ]
    assert err == "".join(f"cardlang: {line}\n" for line in [record["message"], record["notes"][0]["message"]])
