"""A slip on the command line is told what was slipped: the command word, or
the game file's extension.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a first word that is no command and names nothing on disk,
                 standing where a command goes, is refused as a command that
                 does not exist and a file that does not exist, naming the
                 commands, with the commands it nearly spells offered as Near
                 Misses; a first word that names something on disk is read
                 as that file whatever it resembles; a game file whose
                 extension is not one the checker reads is refused naming the
                 extensions it reads, with the ones it nearly spells offered,
                 before its text is read and through every consumer that
                 reads a game file by its path; and an offered word, put in
                 place of the slip, gets the line past that refusal.
domain:          the commands, crossed with the slips generated from each
                 (two letters swapped, a letter dropped, a capital), crossed
                 with what follows the first word (a file, nothing, an
                 option) and with whether a file of the slip's name exists;
                 the words no command resembles, path-shaped and bare, under
                 the same crossing; `<command>.md`, which resembles its
                 command and is a plausible file name, existing and not; and
                 the extensions the checker reads, crossed with the slips
                 generated from each (a capital, two letters swapped, a
                 letter dropped, a backup extension after it), with each
                 extension inside another's name, with a name that is only
                 an extension, and with no extension, an unrelated one and a
                 trailing dot. Extensions are compared exactly as typed, on
                 every platform, as every glob that collects game files
                 compares them: a capitalized extension is a slip, refused
                 with the extension it capitalizes offered. A first word
                 beginning with a dash is read as an option of `check`, and
                 an empty first word as the current directory; what each is
                 told is issue #1084's, marked below. Option prefixes are
                 issue #624's.
registry:        commands: `cardlang.cli.COMMANDS`, derived from
                 `cardlang.cli._COMMAND_TABLE`; extensions:
                 `cardlang.pipeline.GAME_FILE_SHAPES`; the resemblance
                 measure and the `did you mean` wording:
                 `cardlang.diagnostics.near_misses` and
                 `cardlang.diagnostics.Diagnostic.format`; consumers of a game
                 file by path: `cardlang.pipeline.check_source`, each command
                 of `cardlang.cli.main`, and
                 `cardlang.openspiel.game.register_game_file`.
held by:         Derived and Pinned. The command word and the extension are
                 strings a person types, so no union holds them; each set has
                 one owner, the refusals read it, and the axes here are
                 derived from it, so a command or an extension gained arrives
                 as new cells.
does not prove:  that a slip outside the three generated shapes is offered
                 its command or extension, which is the measure's claim
                 (tests/test_near_misses.py); nor that the reading of a first
                 word that both names a file and resembles a command is the
                 one a designer meant.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang.cli import COMMANDS, main
from cardlang.diagnostics import DiagnosticError, near_misses
from cardlang.pipeline import GAME_FILE_SHAPES, check_source, extensions_read

REPO = Path(__file__).parent.parent
HEARTS = REPO / "docs" / "games" / "hearts.cardlang"
KUHN = REPO / "docs" / "games" / "kuhn-poker.cardlang"
MARKDOWN = REPO / "tests" / "fixtures" / "skeleton.md"
# A game file of each shape, to copy under a name.
_CONTENT: dict[str, Path] = {".cardlang": KUHN, ".md": MARKDOWN}


def test_every_extension_has_a_game_of_its_shape() -> None:
    """red under: add a `.txt` row to `GAME_FILE_SHAPES`."""
    assert set(_CONTENT) == set(GAME_FILE_SHAPES)


# ---------------------------------------------------------------------------
# The command word.
# ---------------------------------------------------------------------------


def _command_slips(command: str) -> dict[str, str]:
    return {
        "swapped": command[:-2] + command[-1] + command[-2],
        "dropped": command[:2] + command[3:],
        "capital": command.capitalize(),
    }


_SLIPS: list[tuple[str, str, str]] = [
    (command, shape, slip)
    for command in COMMANDS
    for shape, slip in _command_slips(command).items()
]

# What follows the first word.
_FOLLOWS: dict[str, list[str]] = {
    "a file": [str(KUHN)],
    "nothing": [],
    "an option": ["--emit-ir"],
}

# Words no command resembles: one a person might type for a command, one
# shaped like a path.
_UNLIKE: tuple[str, ...] = ("frobnicate", "missing-game.cardlang")


@dataclass(frozen=True)
class _Said:
    code: int
    err: str


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> _Said:
    try:
        code = main(argv)
    except SystemExit as exit_info:
        assert isinstance(exit_info.code, int)
        code = exit_info.code
    return _Said(code, capsys.readouterr().err)


def _refused_as_a_command(said: _Said, word: str) -> None:
    assert said.code == 2, said.err
    assert f"{word} is not a command, and no file has that name" in said.err, said.err
    assert f"the commands are: {', '.join(COMMANDS)}" in said.err
    assert said.err.startswith("usage: cardlang"), "the usage line leads, as argparse's refusals do"


def test_every_generated_slip_resembles_its_command() -> None:
    """The slips stand for their command: the measure offers it.

    red under: raise `diagnostics.NEAR_MISS_CUTOFF` to 0.95."""
    for command, _shape, slip in _SLIPS:
        assert slip not in COMMANDS
        assert command in near_misses(slip, COMMANDS), (command, slip)
    for word in _UNLIKE:
        assert near_misses(word, COMMANDS) == ()


@pytest.mark.parametrize("follows", sorted(_FOLLOWS))
@pytest.mark.parametrize(("command", "shape", "slip"), _SLIPS)
def test_a_slipped_command_naming_no_file_is_refused_as_a_command(
    command: str,
    shape: str,
    slip: str,
    follows: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    said = _run([slip, *_FOLLOWS[follows]], capsys)
    _refused_as_a_command(said, slip)
    assert f"; did you mean `{command}`?" in said.err


@pytest.mark.parametrize("follows", sorted(_FOLLOWS))
@pytest.mark.parametrize(("command", "shape", "slip"), _SLIPS)
def test_the_offered_command_gets_past_the_refusal(
    command: str,
    shape: str,
    slip: str,
    follows: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The offer is a claim: the line with the command in place of the slip
    meets some other answer, or none.

    red under: drop `argv[0] in COMMANDS` from `cli._normalize`'s
    pass-through."""
    monkeypatch.chdir(tmp_path)
    said = _run([command, *_FOLLOWS[follows]], capsys)
    assert "is not a command" not in said.err, said.err
    if follows == "a file" and command == "check":
        assert said.code == 0, said.err


@pytest.mark.parametrize("follows", sorted(_FOLLOWS))
@pytest.mark.parametrize(("command", "shape", "slip"), _SLIPS)
def test_a_slipped_command_that_names_a_file_is_read_as_the_file(
    command: str,
    shape: str,
    slip: str,
    follows: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The file wins: a designer may name a game `chek`. With no extension,
    the file is then refused for its name, which says the word was read as a
    file.

    red under: drop the `Path(word).exists()` arm from `cli._normalize`."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / slip).write_text(KUHN.read_text())
    said = _run([slip, *_FOLLOWS[follows]], capsys)
    assert "is not a command" not in said.err, said.err
    if follows == "a file":
        assert said.code == 2 and "unrecognized arguments" in said.err, said.err
    else:
        assert said.code == 1, said.err
        assert f"{slip} has no extension" in said.err, said.err


@pytest.mark.parametrize("follows", sorted(_FOLLOWS))
@pytest.mark.parametrize("word", _UNLIKE)
def test_a_word_resembling_no_command(
    word: str,
    follows: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Alone or before options, the word may be the file: both readings are
    answered. Before another word, it stands where a command goes.

    red under: drop the options-only arm from `cli._normalize`."""
    monkeypatch.chdir(tmp_path)
    said = _run([word, *_FOLLOWS[follows]], capsys)
    assert said.code == 2, said.err
    if follows == "a file":
        _refused_as_a_command(said, word)
        assert "did you mean" not in said.err
    else:
        assert f"cannot read {word}: no such file" in said.err
        assert f"if you meant a command, they are: {', '.join(COMMANDS)}" in said.err


@pytest.mark.parametrize("command", COMMANDS)
def test_a_markdown_file_named_for_a_command(
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`check.md` resembles `check`: missing, it is refused on both readings
    with the command offered; present, it is checked."""
    monkeypatch.chdir(tmp_path)
    name = f"{command}.md"
    assert command in near_misses(name, COMMANDS)
    said = _run([name], capsys)
    _refused_as_a_command(said, name)
    assert f"; did you mean `{command}`?" in said.err
    shutil.copy(MARKDOWN, tmp_path / name)
    assert _run([name], capsys).code == 0


@pytest.mark.parametrize("follows", ["nothing", "an option"])
def test_the_bare_form_checks_a_file(
    follows: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`cardlang FILE [--emit-ir]`, as the module docstring has it.

    red under: have `cli._normalize` leave the bare line without `check`."""
    assert _run([str(KUHN), *_FOLLOWS[follows]], capsys).code == 0


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1084")
@pytest.mark.parametrize("word", ["-v", "--version"])
def test_a_first_word_with_a_dash_is_not_told_about_a_command_never_typed(
    word: str, capsys: pytest.CaptureFixture[str]
) -> None:
    said = _run([word], capsys)
    assert said.code == 2
    assert "cardlang check" not in said.err, said.err


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1084")
def test_an_empty_first_word_is_not_told_about_a_path_never_typed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    said = _run([""], capsys)
    assert said.code == 2
    assert "cannot read ." not in said.err, said.err


# ---------------------------------------------------------------------------
# The extension.
# ---------------------------------------------------------------------------


def _extension_slips(ext: str) -> dict[str, str]:
    return {
        "capital": ext.upper(),
        "swapped": ext[:-2] + ext[-1] + ext[-2],
        "dropped": ext[:-1],
    }


_EXT_SLIPS: list[tuple[str, str, str]] = [
    (ext, shape, slip)
    for ext in GAME_FILE_SHAPES
    for shape, slip in _extension_slips(ext).items()
]


def _copy(tmp_path: Path, ext: str, name: str) -> Path:
    path = tmp_path / name
    shutil.copy(_CONTENT[ext], path)
    return path


def _refusal(path: Path) -> DiagnosticError:
    with pytest.raises(DiagnosticError) as refused:
        check_source(path)
    return refused.value


def _names_what_is_read(error: DiagnosticError, path: Path) -> None:
    message = error.diagnostic.message
    assert str(path) in message, message
    assert extensions_read() in message, message
    assert error.diagnostic.span is None, "the file's name is refused, not a place in its text"


@pytest.mark.parametrize("ext", sorted(GAME_FILE_SHAPES))
def test_each_extension_read_is_checked(ext: str, tmp_path: Path) -> None:
    """red under: map `.cardlang` to `check_markdown` in `GAME_FILE_SHAPES`."""
    assert check_source(_copy(tmp_path, ext, f"game{ext}")).players.count >= 1


@pytest.mark.parametrize(("ext", "shape", "slip"), _EXT_SLIPS)
def test_a_slipped_extension_is_refused_with_the_extension_offered(
    ext: str, shape: str, slip: str, tmp_path: Path
) -> None:
    path = _copy(tmp_path, ext, f"game{slip}")
    refused = _refusal(path)
    _names_what_is_read(refused, path)
    assert f"{path} ends in {slip}" in refused.diagnostic.message
    assert ext in refused.diagnostic.near_misses


@pytest.mark.parametrize(("ext", "shape", "slip"), _EXT_SLIPS)
def test_the_offered_extension_gets_past_the_refusal(
    ext: str, shape: str, slip: str, tmp_path: Path
) -> None:
    path = _copy(tmp_path, ext, f"game{slip}")
    offered = _refusal(path).diagnostic.near_misses
    assert offered, "nothing offered"
    assert check_source(path.rename(path.with_suffix(offered[0]))).players.count >= 1


@pytest.mark.parametrize("ext", sorted(GAME_FILE_SHAPES))
def test_a_backup_extension_after_a_game_extension_is_refused(ext: str, tmp_path: Path) -> None:
    path = _copy(tmp_path, ext, f"game{ext}.bak")
    refused = _refusal(path)
    _names_what_is_read(refused, path)
    assert refused.diagnostic.near_misses == ()


@pytest.mark.parametrize("inner", sorted(GAME_FILE_SHAPES))
@pytest.mark.parametrize("outer", sorted(GAME_FILE_SHAPES))
def test_the_last_extension_names_the_shape(inner: str, outer: str, tmp_path: Path) -> None:
    """red under: have `check_source` dispatch on `p.suffixes[0]`."""
    assert check_source(_copy(tmp_path, outer, f"game{inner}{outer}")).players.count >= 1


_NO_EXTENSION: dict[str, str] = {
    "no extension": "game",
    "a trailing dot": "game.cardlang.",
    **{f"only {ext}": ext for ext in GAME_FILE_SHAPES},
}


@pytest.mark.parametrize("case", sorted(_NO_EXTENSION))
def test_a_name_with_no_extension_is_refused(case: str, tmp_path: Path) -> None:
    path = _copy(tmp_path, ".cardlang", _NO_EXTENSION[case])
    refused = _refusal(path)
    _names_what_is_read(refused, path)
    assert f"{path} has no extension" in refused.diagnostic.message
    assert refused.diagnostic.near_misses == ()


@pytest.mark.parametrize("unrelated", [".txt", ".markdown", ".dsl"])
def test_an_unrelated_extension_is_refused_with_nothing_offered(
    unrelated: str, tmp_path: Path
) -> None:
    path = _copy(tmp_path, ".cardlang", f"game{unrelated}")
    refused = _refusal(path)
    _names_what_is_read(refused, path)
    assert refused.diagnostic.near_misses == ()


def test_the_extension_is_refused_before_the_file_is_read(tmp_path: Path) -> None:
    """Text the front end cannot decode is never read for a name it refuses."""
    path = tmp_path / "game.cardlnag"
    path.write_bytes(b"\xff\xfe\x00\x01 not text")
    _names_what_is_read(_refusal(path), path)


# What a command cannot be run without, beside its file.
_REQUIRED: dict[str, list[str]] = {"query": ["--at", "1:1"]}


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_tells_a_slipped_extension(
    command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _copy(tmp_path, ".cardlang", "hearts.cardlnag")
    said = _run([command, str(path), *_REQUIRED.get(command, [])], capsys)
    assert said.code == 1, said.err
    assert said.err.startswith(f"error: {path} ends in .cardlnag"), said.err
    assert "; did you mean `.cardlang`?" in said.err


def test_registering_a_slipped_extension_by_path_is_refused(tmp_path: Path) -> None:
    pytest.importorskip("pyspiel")
    from cardlang.openspiel.game import register_game_file

    path = _copy(tmp_path, ".cardlang", "slipped_extension.cardlnag")
    with pytest.raises(DiagnosticError) as refused:
        register_game_file(path)
    assert refused.value.diagnostic.near_misses == (".cardlang",)


# ---------------------------------------------------------------------------
# The two witnesses, as each issue states it.
# ---------------------------------------------------------------------------


def test_hearts_with_its_extension_slipped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Issue #1060."""
    path = tmp_path / "hearts.cardlnag"
    shutil.copy(HEARTS, path)
    said = _run(["check", str(path)], capsys)
    assert said.code == 1
    assert "fenced code block" not in said.err, said.err
    assert said.err == (
        f"error: {path} ends in .cardlnag, and a game file's name ends in "
        f"{extensions_read()}; did you mean `.cardlang`?\n"
    )


def test_hearts_checked_with_the_command_slipped(capsys: pytest.CaptureFixture[str]) -> None:
    """Issue #1061."""
    said = _run(["chekc", str(HEARTS)], capsys)
    assert "unrecognized arguments" not in said.err, said.err
    _refused_as_a_command(said, "chekc")
    assert said.err.endswith("; did you mean `check`?\n"), said.err
