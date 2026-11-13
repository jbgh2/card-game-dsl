"""A slip on the command line is told what was slipped: the command word, a
command-line option, a word after the file, the file itself, or the game
file's extension.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a first word that is no command and names nothing on disk,
                 standing where a command goes, is refused as a command that
                 does not exist and a file that does not exist, naming the
                 commands, with the commands it nearly spells offered as Near
                 Misses; a first word that names something on disk is read
                 as that file whatever it resembles, and one whose name
                 begins with a dash is told the spelling that names it; a
                 game file whose extension is not one the checker reads is
                 refused naming the extensions it reads, with the ones it
                 nearly spells offered, before its text is read and through
                 every consumer that reads a game file by its path; a
                 Markdown file with no fenced block is told the game file
                 beside it with its stem, or else the extension that reads
                 the DSL itself; a word that is no command-line option of the
                 command is refused naming it, with the commands that take
                 every word of the line, or else, offering nothing, what the
                 command declaring every option of the line refuses in it, or
                 the commands each option is an option of when none declares
                 them all, or else the command's own options it nearly
                 spells, or else where they are listed; a word after the file
                 is refused as one too many, or, when it is a command, with
                 the order that takes every word, or else what that command
                 refuses, or the commands each option is an option of; a line naming no
                 file, or an empty one, is refused for that; every refusal of
                 the line's words speaks as the command typed, or as
                 `cardlang` when none was, says when it read the line as
                 `check`, and every word it says was typed was, the path it
                 cannot read included; each refusal keeps the CLI's exit
                 status and failure channel, which every cell states; and
                 every offer, applied as the refusal prints it, gets the line
                 past that refusal.
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
                 with the extension it capitalizes offered. The words after
                 the command: every command and no command, crossed with
                 every command-line option any command declares that the
                 command does not (spaced from its value and joined to it
                 with `=`), with each of its own options slipped (the last
                 two letters swapped, the second letter of the name
                 dropped), and with words no parser declares (`-v`,
                 `--version`) first, before the file and after it; two
                 command-line options after the file, under every command
                 and under none, every option the command does not take
                 crossed with every other option; each command after the
                 file, alone, after each option and after a second file; a
                 second file, alone and beside every option the command does
                 not take; a file whose name begins
                 with a dash; no file, an empty file, an empty first word; a
                 value on an option or on help that takes none; a path
                 missing, spelled with `./`; argparse's own refusal of a
                 missing value under each command that takes one; and the
                 corpus's rulebook twins, the Markdown files of
                 `docs/games/` with a game file beside them. The offer a slip
                 of an option is told is authored by hand at the anchors,
                 `_ANCHORS`, where no offer is right as well as where one is;
                 the anchors the measure answers otherwise are marked for
                 issue #1098. Every proper prefix of every option a command
                 declares, derived from the parser's own table, is refused
                 under that command as typed, never read as the option it
                 begins. `-h` after any
                 line prints that command's help and refuses nothing. The
                 property reads every line above, the command-word grid's
                 included; a game file's own refusals name its path as
                 Python spells it, which is issue #1099's, marked below.
registry:        commands: `cardlang.cli.COMMANDS`, derived from
                 `cardlang.cli._COMMAND_TABLE`; options per command and
                 whether each takes a value: `cardlang.cli.build_parser`,
                 walked by `_declared` below; extensions:
                 `cardlang.pipeline.GAME_FILE_SHAPES`; the resemblance
                 measure and the `did you mean` wording:
                 `cardlang.diagnostics.near_misses` and
                 `cardlang.diagnostics.Diagnostic.format`; consumers of a game
                 file by path: `cardlang.pipeline.check_source`, each command
                 of `cardlang.cli.main`, and
                 `cardlang.openspiel.game.register_game_file`.
held by:         Derived and Pinned. The command word, the options, the
                 extension and the line's other words are strings a person
                 types, so no union holds them; each set has one owner, the
                 refusals read it, and the axes here are derived from it, so
                 a command, an option or an extension gained arrives as new
                 cells. The voice of a refusal has one owner,
                 `cardlang.cli._refuse`, which every refusal of the line's
                 words reaches.
does not prove:  that a slip outside the generated shapes and the anchors is
                 offered its command, option or extension, which is the
                 measure's claim (tests/test_near_misses.py); nor that the
                 reading of a first word that both names a file and
                 resembles a command is the one a designer meant. The
                 property reads a refusal's subjects by the sentence shapes
                 `_SUBJECTS` and `_ARGUMENT` name, and the offers by the
                 shapes `_offered_lines` and `_printed_words` read, so a
                 refusal worded in a new shape is read for its voice alone
                 until a shape names it; a cell whose refusal names no
                 subject it can read fails unless the cell says it names
                 none.
"""

from __future__ import annotations

import argparse
import io
import re
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang.cli import COMMANDS, build_parser, main
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
    raised: bool = False


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> _Said:
    try:
        code = main(argv)
    except SystemExit as exit_info:
        assert isinstance(exit_info.code, int)
        return _Said(exit_info.code, capsys.readouterr().err, raised=True)
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
    """The offer is a claim: the line with each command offered, as the
    refusal prints it, in place of the slip meets some other answer, or none.

    red under: drop `argv[0] in COMMANDS` from `cli._normalize`'s
    pass-through."""
    monkeypatch.chdir(tmp_path)
    offered = _printed_words(_run([slip, *_FOLLOWS[follows]], capsys).err)
    assert command in offered, offered
    for word in offered:
        said = _run([word, *_FOLLOWS[follows]], capsys)
        assert "is not a command" not in said.err, said.err
        if follows == "a file" and word == "check":
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
        assert said.code == 2 and f"so {KUHN} is one too many" in said.err, said.err
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
    for word in _printed_words(said.err):
        assert "is not a command" not in _run([word], capsys).err
    shutil.copy(MARKDOWN, tmp_path / name)
    assert _run([name], capsys).code == 0


@pytest.mark.parametrize("follows", ["nothing", "an option"])
def test_the_bare_form_checks_a_file(
    follows: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`cardlang FILE [--emit-ir]`, as the module docstring has it.

    red under: have `cli._normalize` leave the bare line without `check`."""
    assert _run([str(KUHN), *_FOLLOWS[follows]], capsys).code == 0


# ---------------------------------------------------------------------------
# The words after the command: command-line options, extra words, the file.
# ---------------------------------------------------------------------------

# The game file every line below names, relative to the repository, where
# each cell runs.
_F = "docs/games/kuhn-poker.cardlang"
_IMPLICIT = "no command is named, so the line is read as check"
_ANY_COMMAND_HINT = "cardlang -h lists the commands, and cardlang <command> -h the options each takes"


def _declared() -> dict[str, tuple[str, ...]]:
    """Each command and the option words its parser declares, `-h` and
    `--help` aside, walked from the built parser."""
    out: dict[str, tuple[str, ...]] = {}
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                out[name] = tuple(
                    opt
                    for sub_action in sub._actions
                    for opt in sub_action.option_strings
                    if opt not in ("-h", "--help")
                )
    return out


_DECLARED = _declared()
_EVERY_OPTION: tuple[str, ...] = tuple(sorted({o for opts in _DECLARED.values() for o in opts}))
_TAKES_VALUE: frozenset[str] = frozenset(
    opt
    for action in build_parser()._actions
    if isinstance(action, argparse._SubParsersAction)
    for sub in action.choices.values()
    for sub_action in sub._actions
    if sub_action.nargs != 0
    for opt in sub_action.option_strings
)
_VALUE: dict[str, str] = {"--vs": "all=random", "--save": "saved.json", "--resume": "saved.json"}
# The option pairs a command declares and refuses together (a mutually
# exclusive group), walked from the built parser.
_EXCLUSIVE: frozenset[frozenset[str]] = frozenset(
    frozenset(opt for a in group._group_actions for opt in a.option_strings)
    for action in build_parser()._actions
    if isinstance(action, argparse._SubParsersAction)
    for sub in action.choices.values()
    for group in sub._mutually_exclusive_groups
)


def _and(names: tuple[str, ...]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _or(names: tuple[str, ...]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def _owners(option: str) -> tuple[str, ...]:
    return tuple(c for c in COMMANDS if option in _DECLARED[c])


def _prefix_of_declared(word: str, command: str) -> bool:
    """Whether `word` begins an option `command` declares: a prefix, which
    `test_no_command_takes_an_option_by_a_prefix` refuses."""
    return any(opt.startswith(word) for opt in _DECLARED[command])


@dataclass(frozen=True)
class _Cell:
    """A line, and what it is told.

    `channel` is the CLI's contract for the refusal: `usage` is argparse's
    (`SystemExit` 2, the usage line leading, then the refusal under the
    voice of the command typed, or of `cardlang` when none was); `path` is
    the path argument's (returned 2, `cardlang: cannot read` leading); `game`
    is the game file's (returned 1, the diagnostic leading)."""

    argv: tuple[str, ...]
    code: int
    channel: str
    says: tuple[str, ...]
    # Whether the refusal names a word of the line; one refusing a line for
    # naming no file, or an empty one, names none.
    names: bool = True


def _usage(argv: list[str], *says: str) -> _Cell:
    return _Cell(tuple(argv), 2, "usage", says)


def _nameless(argv: list[str], *says: str) -> _Cell:
    return _Cell(tuple(argv), 2, "usage", says, names=False)


def _subject(command: str | None) -> str:
    return command if command is not None else f"{_IMPLICIT}, which"


def _lead(command: str | None) -> list[str]:
    return [] if command is None else [command]


_WHO: tuple[str | None, ...] = (*COMMANDS, None)


def _who(command: str | None) -> str:
    return "no command" if command is None else command


def _option_cells() -> dict[str, _Cell]:
    """An option of another command, after the file, under every command and
    under none, spaced from its value and joined to it."""
    cells: dict[str, _Cell] = {}
    for command in _WHO:
        here = "check" if command is None else command
        for option in _EVERY_OPTION:
            if option in _DECLARED[here]:
                continue
            owners = _owners(option)
            fix = (
                f"so name {_or(owners)} first"
                if command is None
                else f"so name {_or(owners)} in place of {command}"
            )
            said = f"{_subject(command)} takes no {option}; {option} is an option of {_and(owners)}, {fix}"
            value = [_VALUE.get(option, "1")] if option in _TAKES_VALUE else []
            cells[f"{_who(command)}: {option}, spaced"] = _usage(
                [*_lead(command), _F, option, *value], said
            )
            joined = f"{option}={_VALUE.get(option, '1')}"
            name = f"{_who(command)}: {option}, joined"
            if option in _TAKES_VALUE:
                cells[name] = _usage([*_lead(command), _F, joined], said)
            else:
                # An option that takes no value, given one: the command it
                # belongs to refuses the word too, in argparse's words.
                cells[name] = _usage(
                    [*_lead(command), _F, joined],
                    f"{_subject(command)} takes no {option}; {option} is an option of "
                    f"{_and(owners)}, and {owners[0]} refuses this line too: argument {option}:",
                )
    return cells


def _option_slips(option: str) -> dict[str, str]:
    return {
        "swapped": option[:-2] + option[-1] + option[-2],
        "dropped": option[:3] + option[4:],
    }


def _slipped_option_cells() -> dict[str, tuple[_Cell, str]]:
    """A command's own option, slipped, after the file: each with the option
    it slips. A slip that is a prefix of an option is the prefix grid's, and
    a slip that spells another declared option is that option."""
    cells: dict[str, tuple[_Cell, str]] = {}
    for command in _WHO:
        here = "check" if command is None else command
        for option in _DECLARED[here]:
            for shape, slip in _option_slips(option).items():
                if slip in _EVERY_OPTION or _prefix_of_declared(slip, here):
                    continue
                value = [_VALUE.get(option, "1")] if option in _TAKES_VALUE else []
                cells[f"{_who(command)}: {option} {shape}"] = (
                    _usage(
                        [*_lead(command), _F, slip, *value],
                        f"{_subject(command)} takes no {slip}; did you mean ",
                        f"`{option}`",
                    ),
                    option,
                )
    return cells


# Words no parser declares, which a designer reaches for.
_UNDECLARED: tuple[str, ...] = ("-v", "--version")


def _hint(command: str | None) -> str:
    return _ANY_COMMAND_HINT if command is None else f"cardlang {command} -h lists the options it takes"


def _undeclared_cells() -> dict[str, _Cell]:
    """A word no parser declares, first and after the file, under every
    command and under none. What each is offered is `_ANCHORS`'."""
    cells: dict[str, _Cell] = {}
    for command in _WHO:
        for word in _UNDECLARED:
            said = f"{_subject(command)} takes no {word}"
            cells[f"{_who(command)}: {word} alone"] = _usage([*_lead(command), word], said)
            cells[f"{_who(command)}: {word} after the file"] = _usage([*_lead(command), _F, word], said)
            cells[f"{_who(command)}: {word} before the file"] = _usage([*_lead(command), word, _F], said)
    return cells


def _value(option: str) -> list[str]:
    return [_VALUE.get(option, "1")] if option in _TAKES_VALUE else []


def _apart(options: tuple[str, ...]) -> str:
    """The commands each option is one of, as a refusal naming no command
    that takes them all says it."""
    return "; ".join(
        f"{o} is an option of {_and(_owners(o)) if _owners(o) else 'no command'}" for o in options
    )


def _pair_cells() -> dict[str, _Cell]:
    """Two command-line options after the file, under every command and
    under none: the first one the command does not take, the second any
    other. The offer is a command that takes both, or none."""
    cells: dict[str, _Cell] = {}
    for command in _WHO:
        here = "check" if command is None else command
        for first in _EVERY_OPTION:
            if first in _DECLARED[here]:
                continue
            for second in _EVERY_OPTION:
                if second == first:
                    continue
                takers = tuple(c for c in COMMANDS if first in _DECLARED[c] and second in _DECLARED[c])
                if takers and frozenset({first, second}) in _EXCLUSIVE:
                    said = (
                        f"{_subject(command)} takes no {first}; {first} is an option of "
                        f"{_and(_owners(first))}, and {takers[0]} refuses this line too: "
                        f"argument {second}: not allowed with argument {first}"
                    )
                elif takers:
                    where = "first" if command is None else f"in place of {command}"
                    said = (
                        f"{_subject(command)} takes no {first}; {first} is an option of "
                        f"{_and(_owners(first))}, so name {_or(takers)} {where}"
                    )
                else:
                    said = (
                        f"{_subject(command)} takes no {first}; no command takes every word "
                        f"of this line: {_apart((first, second))}"
                    )
                name = f"{_who(command)}: {first} with {second}"
                cells[name] = _usage(
                    [*_lead(command), _F, first, *_value(first), second, *_value(second)], said
                )
    return cells


def _order_cells() -> dict[str, _Cell]:
    """A command after the file, under no command, with each command-line
    option before it: the order offered takes every word, or none is."""
    cells: dict[str, _Cell] = {}
    for typed in COMMANDS:
        for option in _EVERY_OPTION:
            if option in _DECLARED[typed]:
                line = shlex.join(["cardlang", typed, _F, option, *_value(option)])
                said = f"{typed} comes after the file, and a command goes first: {line}"
            else:
                said = (
                    f"{typed} comes after the file, and a command goes first, but {typed} "
                    f"does not take every word of this line: {_apart((option,))}"
                )
            name = f"no command: {option}, then {typed} after the file"
            cells[name] = _usage([_F, option, *_value(option), typed], said)
    return cells


def _second_file_cells() -> dict[str, _Cell]:
    """A second file beside another command's option, under every command
    and under none, and before a command named after the file: the command
    that declares every option of the line refuses it too, and says why."""
    cells: dict[str, _Cell] = {}
    extra = "so other.cardlang is one too many"
    for command in _WHO:
        here = "check" if command is None else command
        for option in _EVERY_OPTION:
            if option in _DECLARED[here]:
                continue
            owners = _owners(option)
            name = f"{_who(command)}: {option} and a second file"
            cells[name] = _usage(
                [*_lead(command), _F, option, *_value(option), "other.cardlang"],
                f"{_subject(command)} takes no {option}; {option} is an option of {_and(owners)}, "
                f"and {owners[0]} refuses this line too: {owners[0]} reads one game file and no "
                f"other word, {extra}",
            )
    for typed in COMMANDS:
        name = f"no command: a second file, then {typed} after the file"
        cells[name] = _usage(
            [_F, "other.cardlang", typed],
            f"{typed} comes after the file, and a command goes first, but {typed} refuses this "
            f"line too: {typed} reads one game file and no other word, {extra}",
        )
    return cells


def _dash_cells() -> dict[str, _Cell]:
    """A file whose name begins with a dash, named as the file, under every
    command and under none."""
    said = (
        f"{_DASHED} begins with a dash, so it reads as a command-line option, not as the "
        f"file of that name; spell the file ./{_DASHED}"
    )
    cells = {
        f"{_who(command)}: a file whose name begins with a dash": _usage([*_lead(command), _DASHED], said)
        for command in _WHO
    }
    return cells


def _word_cells() -> dict[str, _Cell]:
    """A word after the file: a command, under none, and any other word."""
    cells: dict[str, _Cell] = {}
    for command in _WHO:
        cells[f"{_who(command)}: a second file"] = _usage(
            [*_lead(command), _F, "other.cardlang"],
            f"{_subject(command)} reads one game file and no other word, so other.cardlang is one too many",
        )
    for typed in COMMANDS:
        cells[f"no command: {typed} after the file"] = _usage(
            [_F, typed],
            f"{typed} comes after the file, and a command goes first: cardlang {typed} {_F}",
        )
        cells[f"{typed}: check after the file"] = _usage(
            [typed, _F, "check"],
            f"{typed} reads one game file and no other word, so check is one too many",
        )
    return cells


def _file_cells() -> dict[str, _Cell]:
    """No file, and an empty word for one, under every command and under
    none."""
    cells: dict[str, _Cell] = {}
    for command in COMMANDS:
        cells[f"{command}: no file"] = _nameless(
            [command], f"{command} needs a game file, its name ending in {extensions_read()}"
        )
        cells[f"{command}: an empty file"] = _nameless(
            [command, ""], "argument file: an empty name names no file"
        )
    cells["no command: only an option"] = _nameless(
        ["--emit-ir"], f"{_IMPLICIT}, which needs a game file, its name ending in {extensions_read()}"
    )
    cells["no command: an empty word"] = _nameless(
        [""], f"{_IMPLICIT}: argument file: an empty name names no file"
    )
    cells["no command: an empty word, then a word"] = _nameless(
        ["", "x"], f"{_IMPLICIT}: argument file: an empty name names no file"
    )
    cells["no command: a value on an option that takes none"] = _usage(
        [_F, "--emit-ir=x"], f"{_IMPLICIT}: argument --emit-ir:"
    )
    cells["no command: a value on help"] = _usage(["--help=x"], f"{_IMPLICIT}: argument -h/--help:")
    cells["no command: a path missing, as typed"] = _Cell(
        ("./missing.cardlang",), 2, "path", ("cannot read ./missing.cardlang: no such file",)
    )
    for command in COMMANDS:
        cells[f"{command}: a path missing, as typed"] = _Cell(
            (command, "./missing.cardlang"), 2, "path", ("cannot read ./missing.cardlang: no such file",)
        )
    return cells


def _argparse_cells() -> dict[str, _Cell]:
    """argparse's own refusal of a value, under the command typed: told in
    that command's voice, in argparse's words."""
    cells: dict[str, _Cell] = {}
    for command, options in _DECLARED.items():
        for option in options:
            if option in _TAKES_VALUE:
                cells[f"{command}: {option} with no value"] = _usage(
                    [command, _F, option], f"argument {option}"
                )
    return cells


# A game file whose name begins with a dash, which every table holds.
_DASHED = "-dash.cardlang"

_SLIPPED = _slipped_option_cells()
_CELLS: dict[str, _Cell] = {
    **_option_cells(),
    **{name: cell for name, (cell, _option) in _SLIPPED.items()},
    **_undeclared_cells(),
    **_word_cells(),
    **_file_cells(),
    **_pair_cells(),
    **_order_cells(),
    **_second_file_cells(),
    **_dash_cells(),
}
# The cells that keep what the tree already says.
_KEPT: dict[str, _Cell] = _argparse_cells()


@pytest.fixture
def table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where each line runs: a directory holding the game file the lines
    name, at the path they name it by, and a game file named with a dash. A
    line `play` carries out saves its game here."""
    (tmp_path / "docs" / "games").mkdir(parents=True)
    shutil.copy(KUHN, tmp_path / _F)
    shutil.copy(KUHN, tmp_path / _DASHED)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_at_table(argv: tuple[str, ...], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> _Said:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    return _run(list(argv), capsys)


def _typed_command(argv: tuple[str, ...]) -> str | None:
    return argv[0] if argv and argv[0] in COMMANDS else None


def _told(cell: _Cell, said: _Said) -> None:
    assert said.code == cell.code, said.err
    assert said.raised is (cell.channel == "usage"), said.err
    typed = _typed_command(cell.argv)
    if cell.channel == "usage":
        usage = "usage: cardlang [-h]" if typed is None else f"usage: cardlang {typed} [-h]"
        assert said.err.startswith(usage), said.err
        voice = "cardlang: error: " if typed is None else f"cardlang {typed}: error: "
        assert voice in said.err, said.err
    elif cell.channel == "path":
        assert said.err.startswith("cardlang: cannot read "), said.err
    for words in cell.says:
        assert words in " ".join(said.err.split()), said.err



@pytest.mark.parametrize("cell", sorted(_CELLS))
def test_each_line_is_told_what_it_typed_and_the_fix(
    cell: str, table: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _told(_CELLS[cell], _run_at_table(_CELLS[cell].argv, monkeypatch, capsys))


@pytest.mark.parametrize("cell", sorted(_KEPT))
def test_argparse_s_own_refusal_under_the_command_typed(
    cell: str, table: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """red under: have `cli._refuse` always speak as the top parser."""
    _told(_KEPT[cell], _run_at_table(_KEPT[cell].argv, monkeypatch, capsys))


# The voices a refusal speaks in, and the words it says were typed. Every
# other word in a refusal is an offer: a command or an option that would
# work, a `did you mean`, a line to type instead.
_VOICE = re.compile(r"^(?:usage: )?cardlang (\w+)", re.MULTILINE)
_SUBJECTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"takes no (\S+?)(?:;|$)", re.MULTILINE),
    re.compile(r"cannot read (.+?): ", re.MULTILINE),
    re.compile(r"so (\S+) is one too many"),
    re.compile(r"(\S+) comes after the file"),
    re.compile(r"^cardlang: error: (\S+) is not a command", re.MULTILINE),
    re.compile(r"^error: (\S+) ends in ", re.MULTILINE),
    re.compile(r"^error: (\S+) has no extension", re.MULTILINE),
    re.compile(r"error: (\S+) begins with a dash"),
)
# argparse names an option by every spelling it has, `-h/--help`.
_ARGUMENT = re.compile(r"argument (-\S+?): ")


def _command_word_lines() -> dict[str, tuple[str, ...]]:
    """The command-word grid's lines above, run where no file has a slip's
    name: each slipped command and each word resembling none, before each
    thing that may follow it, and `<command>.md`."""
    follows: dict[str, list[str]] = {**_FOLLOWS, "a file": [_F]}
    lines: dict[str, tuple[str, ...]] = {}
    for _command, shape, slip in _SLIPS:
        for after, words in follows.items():
            lines[f"the command word {slip} ({shape}), then {after}"] = (slip, *words)
    for word in _UNLIKE:
        for after, words in follows.items():
            lines[f"the word {word}, then {after}"] = (word, *words)
    for command in COMMANDS:
        lines[f"the word {command}.md"] = (f"{command}.md",)
    return lines


# Every line the property reads, and whether its refusal names a word of it.
_PROPERTY: dict[str, tuple[tuple[str, ...], bool]] = {
    **{name: (cell.argv, cell.names) for name, cell in {**_CELLS, **_KEPT}.items()},
    **{name: (argv, True) for name, argv in _command_word_lines().items()},
}


def _names_only_what_was_typed(argv: tuple[str, ...], said: _Said, names: bool) -> None:
    assert said.code != 0, said.err
    typed = _typed_command(argv)
    for spoken in _VOICE.findall(said.err):
        if spoken in COMMANDS:
            assert spoken == typed, said.err
    words = set(argv) | {w.split("=", 1)[0] for w in argv}
    found = [m for pattern in _SUBJECTS for m in pattern.findall(said.err)]
    spelled = _ARGUMENT.findall(said.err)
    assert bool(found or spelled) is names, f"the words named: {found + spelled}: {said.err}"
    for subject in found:
        assert subject in words, (subject, said.err)
    for subject in spelled:
        assert any(spelling in words for spelling in subject.split("/")), (subject, said.err)


@pytest.mark.parametrize("cell", sorted(_PROPERTY))
def test_no_refusal_names_a_word_never_typed(
    cell: str, table: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The property, over every line of the grid: the command a refusal
    speaks as is the one typed, and each word it says was typed was.

    red under: have `cli._unreadable` name `Path(word)` rather than the word;
    or have `cli._refuse` speak as `line.argv[0]`, the command parsed; or have
    `cli._normalize`'s refusal name `word.casefold()`."""
    argv, names = _PROPERTY[cell]
    _names_only_what_was_typed(argv, _run_at_table(argv, monkeypatch, capsys), names)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1099")
def test_a_slipped_extension_is_named_as_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`./game.cardlnag` is refused naming `./game.cardlnag`, the word typed."""
    monkeypatch.chdir(tmp_path)
    _copy(tmp_path, ".cardlang", "game.cardlnag")
    argv = ("check", "./game.cardlnag")
    _names_only_what_was_typed(argv, _run(list(argv), capsys), True)



# The offers a refusal prints: a whole line, commands to name first or in
# place of the one typed, a file's spelling, and words in place of the word
# it refused.
_OFFERED_LINE = re.compile(r"a command goes first: (.+)$", re.MULTILINE)
_OFFERED_COMMANDS = re.compile(r"so name (.+?) (first|in place of \S+)$", re.MULTILINE)
_OFFERED_SPELLING = re.compile(r"spell the file (\S+)$", re.MULTILINE)
_OFFERED_WORDS = re.compile(r"did you mean (.+)\?$", re.MULTILINE)


def _printed_words(err: str) -> tuple[str, ...]:
    """The words a refusal's `did you mean` offers, as printed."""
    return tuple(w for clause in _OFFERED_WORDS.findall(err) for w in re.findall(r"`([^`]+)`", clause))


def _subjects(err: str) -> list[str]:
    return [m for pattern in _SUBJECTS for m in pattern.findall(err)]


def _in_place(argv: tuple[str, ...], refused: str, offered: str) -> tuple[str, ...]:
    """`argv` with the word the refusal named replaced by the one offered,
    keeping a value joined to it."""
    return tuple(
        offered + w[len(refused):] if w == refused or w.startswith(refused + "=") else w for w in argv
    )


def _offered_lines(argv: tuple[str, ...], err: str) -> list[tuple[str, ...]]:
    """Every line a refusal offers whole, built from what it prints."""
    lines: list[tuple[str, ...]] = []
    for printed in _OFFERED_LINE.findall(err):
        words = shlex.split(printed)
        assert words[0] == "cardlang", printed
        lines.append(tuple(words[1:]))
    for names, where in _OFFERED_COMMANDS.findall(err):
        for name in re.split(r", | or ", names):
            lines.append((name, *argv) if where == "first" else (name, *argv[1:]))
    for spelling in _OFFERED_SPELLING.findall(err):
        lines.append(_in_place(argv, _subjects(err)[0], spelling))
    return lines


@pytest.mark.parametrize("cell", sorted({**_CELLS, **_KEPT}))
def test_every_offer_is_taken_as_printed(
    cell: str, table: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each offer, applied as the refusal prints it, gets past it: a line,
    a command or a file's spelling offered whole is a line every word of
    which is taken, and a word offered in place of the word refused is not
    refused itself.

    red under: have `cli._set_aside` print the order offered from `words`, the
    command word left in, while `_takes` judges `rest`; or have it offer
    every command an option belongs to, `takers = list(belongs)`."""
    argv = {**_CELLS, **_KEPT}[cell].argv
    refused = _run_at_table(argv, monkeypatch, capsys).err
    for line in _offered_lines(argv, refused):
        said = _run_at_table(line, monkeypatch, capsys)
        assert "usage:" not in said.err, (line, said.err)
    words = _printed_words(refused)
    if words:
        subject = _subjects(refused)[0]
        for word in words:
            said = _run_at_table(_in_place(argv, subject, word), monkeypatch, capsys)
            assert word not in _subjects(said.err), (word, said.err)


# The offer a slip is told, authored by hand: a command and the word typed
# after the file. An empty offer means the help is named instead.
_ANCHORS: dict[tuple[str | None, str], tuple[str, ...]] = {
    (None, "--emitir"): ("--emit-ir",),
    ("check", "--emitir"): ("--emit-ir",),
    ("demo", "--sed"): ("--seed",),
    ("demo", "--veiw"): ("--view",),
    ("demo", "--decisons"): ("--decisions",),
    ("play", "--resmue"): ("--resume",),
    ("play", "--sed"): ("--seed",),
    (None, "-v"): (),
    (None, "--version"): (),
    ("check", "-v"): (),
    ("check", "--version"): (),
    ("demo", "-v"): (),
    ("demo", "--version"): (),
    ("demo", "-x"): (),
    ("demo", "--emit"): (),
    ("play", "-v"): (),
    ("play", "--version"): (),
}
# The anchors the measure answers otherwise (issue #1098).
_MEASURE_ERRS: frozenset[tuple[str | None, str]] = frozenset(
    {
        ("play", "--sed"),
        ("demo", "--decisons"),
        ("demo", "--version"),
        ("demo", "--emit"),
        ("play", "-v"),
        ("play", "--version"),
        (None, "--version"),
        ("check", "--version"),
    }
)


@pytest.mark.parametrize(
    "anchor",
    [
        pytest.param(
            a,
            id=f"{_who(a[0])} {a[1]}",
            marks=[pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1098")]
            if a in _MEASURE_ERRS
            else [],
        )
        for a in _ANCHORS
    ],
)
def test_an_anchor_slip_is_offered_what_was_meant(
    anchor: tuple[str | None, str],
    table: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command, word = anchor
    said = _run_at_table((*_lead(command), _F, word), monkeypatch, capsys)
    assert f"takes no {word}" in said.err, said.err
    assert _printed_words(said.err) == _ANCHORS[anchor], said.err
    if not _ANCHORS[anchor]:
        assert _hint(command) in said.err, said.err


def _option_prefixes() -> list[tuple[str, str]]:
    """Every proper prefix of every option each command declares, from the
    parser's own table: `--` and at least one letter, short of the whole."""
    return sorted(
        {
            (command, option[:size])
            for command in COMMANDS
            for option in build_parser().commands[command].options()
            if option.startswith("--")
            for size in range(3, len(option))
        }
    )


@pytest.mark.parametrize("cell", _option_prefixes(), ids=lambda c: f"{c[0]} {c[1]}")
def test_no_command_takes_an_option_by_a_prefix(
    cell: tuple[str, str], table: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A prefix is a slip, refused naming it as typed, never read as the
    option it begins. red under: `allow_abbrev=False` dropped from the
    command parsers in `cli.build_parser`."""
    command, prefix = cell
    said = _run_at_table((command, _F, prefix), monkeypatch, capsys)
    assert (said.code, said.raised) == (2, True), said.err
    assert f"takes no {prefix}" in said.err, said.err


def test_every_generated_option_slip_resembles_its_option() -> None:
    """The slips stand for their option: the measure offers it.

    red under: raise `diagnostics.NEAR_MISS_CUTOFF` to 0.95."""
    assert _SLIPPED
    for line, option in _SLIPPED.values():
        slip = next(w for w in line.argv if w.startswith("-"))
        assert option in near_misses(slip, _DECLARED[_typed_command(line.argv) or "check"]), slip



# The corpus's Markdown files with a game file of the DSL itself beside them.
_TWINS: tuple[str, ...] = tuple(
    sorted(p.name for p in (REPO / "docs" / "games").glob("*.md") if p.with_suffix(".cardlang").exists())
)


@pytest.mark.parametrize("twin", _TWINS)
def test_a_rulebook_twin_is_told_the_game_file_beside_it(
    twin: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`check docs/games/hearts.md` names `docs/games/hearts.cardlang`, which
    checks, rather than advising a rename that would overwrite it."""
    monkeypatch.chdir(REPO)
    path = f"docs/games/{twin}"
    beside = path.removesuffix(".md") + ".cardlang"
    said = _run(["check", path], capsys)
    assert said.code == 1 and not said.raised, said.err
    assert said.err.startswith(
        f"{path}:1:1: error: no fenced code block found; {beside} stands beside it, "
        "named for the DSL itself: check that file instead"
    ), said.err
    found = re.search(r"found; (\S+) stands beside it", said.err)
    assert found is not None
    assert _run(["check", found.group(1)], capsys).code == 0


def test_the_corpus_has_rulebook_twins() -> None:
    assert _TWINS


def test_a_markdown_file_with_no_fence_is_told_the_dsl_may_stand_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `.md` file holding the DSL as it is: the refusal names the extension
    that reads the DSL itself."""
    path = tmp_path / "game.md"
    path.write_text(KUHN.read_text())
    said = _run(["check", str(path)], capsys)
    assert said.code == 1 and not said.raised, said.err
    assert said.err.startswith(f"{path}:1:1: error: no fenced code block found"), said.err
    others = [ext for ext in GAME_FILE_SHAPES if ext != ".md"]
    for ext in others:
        assert f"rename the file to end in {ext} if it holds {GAME_FILE_SHAPES[ext][0]}" in said.err, said.err


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
    """Each extension the refusal prints, put in place of the slip."""
    path = _copy(tmp_path, ext, f"game{slip}")
    offered = _printed_words(_refusal(path).diagnostic.format())
    assert ext in offered, offered
    for index, word in enumerate(offered):
        # Each in a directory of its own: a capital slip and its offer are
        # one file where names are compared without case.
        (tmp_path / f"offer{index}").mkdir()
        renamed = shutil.copy(path, tmp_path / f"offer{index}" / path.with_suffix(word).name)
        assert check_source(renamed).players.count >= 1


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
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _copy(tmp_path, ".cardlang", "hearts.cardlnag")
    said = _run([command, str(path), *_REQUIRED.get(command, [])], capsys)
    assert said.code == 1, said.err
    assert said.err.startswith(f"error: {path} ends in .cardlnag"), said.err
    assert "; did you mean `.cardlang`?" in said.err
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    for word in _printed_words(said.err):
        renamed = path.with_suffix(word)
        shutil.copy(path, renamed)
        assert "ends in" not in _run([command, str(renamed)], capsys).err


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
    (offered,) = _printed_words(said.err)
    assert _run(["check", str(path.rename(path.with_suffix(offered)))], capsys).code == 0


def test_hearts_checked_with_the_command_slipped(capsys: pytest.CaptureFixture[str]) -> None:
    """Issue #1061."""
    said = _run(["chekc", str(HEARTS)], capsys)
    assert "unrecognized arguments" not in said.err, said.err
    _refused_as_a_command(said, "chekc")
    assert said.err.endswith("; did you mean `check`?\n"), said.err
