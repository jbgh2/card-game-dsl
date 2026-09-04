"""The command-line surface: every command crossed with every option, and the
value classes a caller can supply.

property:        Every option the parser declares is accepted by exactly the
                 commands that declare it and refused by the rest, each
                 refusal loud in argparse's usage channel; every value class
                 a caller can supply to `--seed` or `--info-state` is either
                 carried out or refused with a message naming what is valid;
                 and the two invocation forms — the console script and
                 `python -m cardlang` — reach the same front end.
domain:          The commands and options are whatever `cardlang.cli`'s
                 parser declares, derived from the parser itself; the value
                 classes are the integer/non-integer and in-range/out-of-range
                 splits of the two options that take a value. The path
                 argument's whole failure class is here — a name that is
                 nothing, a name that is a directory, a file that will not
                 decode as text — because the command line owns that argument
                 and no earlier layer sees it. The failures it RENDERS are the
                 two the runtime types as catchable, `GameDescriptionError`
                 and `InstallationError`; an `IllegalMove` escaping a playout
                 is typed as neither and keeps its traceback while issue #554
                 settles what it means to a caller. Which file shapes exist is
                 `pipeline.check_source`'s question, answered in the pipeline
                 suite: `.cardlang` is raw DSL and every other suffix routes
                 to the Markdown extractor. What the checker decides about a
                 game and what a playout scores belong to those suites, and
                 are exercised here only far enough to tell an accepted
                 invocation from a refused one.
registry:        commands and options: `cardlang.cli.build_parser` via
                 `_command_options` below; seat bound: `game.players.low`, the
                 same value `cardlang.runtime.driver.play_game` seats;
                 diagnostic rendering shared with the checker:
                 tests/test_rejections.py; the runtime failure hierarchy this
                 module renders: tests/test_failure_taxonomy.py; the file-shape
                 dispatch: tests/test_pipeline_cardlang.py.
does not prove:  A green here says nothing about whether a playout's REPORTED
                 outcome is the right one — the returns and the decision count
                 are read back from the driver's and the adapter's own
                 derivations, and their correctness is those suites' claim,
                 not this module's. It equally says nothing about which games
                 a uniform-random line can finish: `play` renders that refusal
                 the same way whether the game or the policy is the reason,
                 and the corpus measurement is issue #553.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cardlang.cli import COMMANDS, build_parser, main
from cardlang.pipeline import check_source
from cardlang.runtime.errors import InstallationError

REPO = Path(__file__).parent.parent
HEARTS = REPO / "docs" / "games" / "hearts.cardlang"
KUHN = REPO / "docs" / "games" / "kuhn-poker.cardlang"
# Checks clean, then exceeds its declared `max_length` on every seed — the
# runtime half of the failure rendering, reached without tying the test to one
# corpus game's random line.
OVERRUNS = REPO / "tests" / "fixtures" / "exceeds_max_length.cardlang"


# ---------------------------------------------------------------------------
# The axes, derived from the parser rather than listed beside it.
# ---------------------------------------------------------------------------


def _command_options() -> dict[str, frozenset[str]]:
    """Each command the parser declares, and the long options it accepts.

    Walks the built parser so a command or option added to `cli.build_parser`
    arrives here as a new cell. `--help` is every parser's and carries no
    per-command decision, so it is not part of the cross.
    """
    out: dict[str, frozenset[str]] = {}
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                out[name] = frozenset(
                    opt
                    for sub_action in sub._actions
                    for opt in sub_action.option_strings
                    if opt.startswith("--") and opt != "--help"
                )
    return out


def _option_universe() -> tuple[str, ...]:
    return tuple(sorted({o for opts in _command_options().values() for o in opts}))


# A representative legal value per option, so a cell tests the option's
# acceptance and not an unrelated value refusal.
_SAMPLE_VALUE: dict[str, list[str]] = {
    "--emit-ir": [],
    "--seed": ["7"],
    "--info-state": ["0"],
}

# The authored expected column. Written as decisions, never derived from the
# parser: a grid whose expectations come from the same object it measures
# reports that the parser agrees with itself. A command or option the parser
# gains and this table lacks fails `test_every_cell_is_authored` rather than
# passing unexamined.
_EXPECTED: dict[tuple[str, str], str] = {
    ("check", "--emit-ir"): "accepted",
    ("check", "--seed"): "refused",
    ("check", "--info-state"): "refused",
    ("play", "--emit-ir"): "refused",
    ("play", "--seed"): "accepted",
    ("play", "--info-state"): "accepted",
}


def test_every_cell_is_authored() -> None:
    """The derived cross and the authored column name the same cells."""
    derived = {
        (command, option)
        for command in _command_options()
        for option in _option_universe()
    }
    assert derived == set(_EXPECTED), (
        "the parser's commands x options and the authored expectations have "
        "drifted; decide the new cells rather than letting them ride"
    )
    assert set(_command_options()) == set(COMMANDS), (
        "`cli.COMMANDS` and the parser's subcommands disagree — the dispatch "
        "reads the tuple and the grid reads the parser"
    )


@pytest.mark.parametrize(("command", "option"), sorted(_EXPECTED))
def test_command_option_cell(command: str, option: str, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [command, str(KUHN), option, *_SAMPLE_VALUE[option]]
    if _EXPECTED[(command, option)] == "accepted":
        assert main(argv) == 0
        return
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert option in err, f"the refusal must name {option}"
    assert "usage:" in err, "the refusal must show what the command accepts"


# ---------------------------------------------------------------------------
# Misuse probes: the first token, and the value classes of the two options
# that take one. Each must be loud in the layer that owns it.
# ---------------------------------------------------------------------------


def test_bare_file_still_checks() -> None:
    """The form the README documents keeps working, command name omitted."""
    assert main([str(HEARTS)]) == 0


def test_bare_file_with_emit_ir_still_checks(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(HEARTS), "--emit-ir"]) == 0
    assert capsys.readouterr().out.startswith("{")


def test_explicit_check_matches_the_bare_form(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(HEARTS), "--emit-ir"]) == 0
    bare = capsys.readouterr().out
    assert main(["check", str(HEARTS), "--emit-ir"]) == 0
    assert capsys.readouterr().out == bare


def test_unknown_first_token_names_the_commands(capsys: pytest.CaptureFixture[str]) -> None:
    """A bare word that is neither a command nor a file is answered on both
    readings, since the token stood where either could."""
    assert main(["frobnicate"]) == 2
    err = capsys.readouterr().err
    assert "no such file" in err
    for command in COMMANDS:
        assert command in err


def test_missing_file_under_an_explicit_command(capsys: pytest.CaptureFixture[str]) -> None:
    """No command hint, because the caller already named the command."""
    assert main(["play", "/no/such/file.cardlang"]) == 2
    err = capsys.readouterr().err
    assert "no such file" in err
    assert "if you meant a command" not in err


def test_a_directory_is_refused_as_a_path(capsys: pytest.CaptureFixture[str]) -> None:
    """A directory exists, so an existence test admits it and the read that
    follows raises with nobody named. Shell completion produces directory
    paths constantly, which is what puts this in the same class as the
    missing file rather than beside it."""
    assert main(["check", str(REPO / "docs" / "games")]) == 2
    assert "not a file" in capsys.readouterr().err


def test_a_file_that_is_not_text_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The third member of the path argument's failure class."""
    binary = tmp_path / "game.cardlang"
    binary.write_bytes(b"\xff\xfe\x00\x01 not text")
    assert main(["check", str(binary)]) == 2
    assert "decode" in capsys.readouterr().err


def test_a_broken_checkout_is_reported_to_whoever_installed_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`InstallationError` is deliberately not a `GameDescriptionError`
    (`cardlang/runtime/errors.py`): no game is at fault, so the rendering must
    not tell the game author to change their file.

    A game with a `uses` line reaches the family-library loader while
    resolving, which is where a partial checkout surfaces. The pipeline memo
    is cleared around the probe: it is keyed on the parsed tree, so a game
    another test already checked would answer from the cache and never reach
    the loader this monkeypatches.
    """
    from cardlang import libraries, pipeline

    def missing() -> Path:
        raise InstallationError("the family library directory is not in this checkout")

    monkeypatch.setattr(libraries, "_libraries_dir", missing)
    libraries.library_names.cache_clear()
    pipeline._check.cache_clear()
    try:
        assert main(["check", str(KUHN)]) == 2
        err = capsys.readouterr().err
        assert "checkout" in err
        assert "reinstall" in err
    finally:
        libraries.library_names.cache_clear()
        pipeline._check.cache_clear()


def test_no_arguments_names_the_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2
    assert "COMMAND" in capsys.readouterr().err


@pytest.mark.parametrize("seat", ["2", "-1"])
def test_seat_outside_the_table_is_refused(seat: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Kuhn seats two. A seat it does not seat is refused before the playout,
    with the range named — nothing downstream of here would notice: a bad seat
    projects zones through the wrong observer and renders a plausible string.
    """
    assert main(["play", str(KUHN), "--info-state", seat]) == 2
    err = capsys.readouterr().err
    assert "seat" in err
    assert "0..1" in err, "the refusal must name the seats this game seats"


def test_non_integer_seat_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["play", str(KUHN), "--info-state", "north"])
    assert exit_info.value.code == 2
    assert "--info-state" in capsys.readouterr().err


def test_non_integer_seed_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["play", str(KUHN), "--seed", "lucky"])
    assert exit_info.value.code == 2
    assert "--seed" in capsys.readouterr().err


def test_negative_seed_plays() -> None:
    """A seed is an arbitrary integer; nothing about it is a count."""
    assert main(["play", str(KUHN), "--seed", "-3"]) == 0


# ---------------------------------------------------------------------------
# Playing through.
# ---------------------------------------------------------------------------


def test_play_reaches_a_terminal_position(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["play", str(HEARTS), "--seed", "7"]) == 0
    out = capsys.readouterr().out
    assert "returns" in out
    assert "decisions" in out
    assert "seed" in out and "7" in out


def test_play_reads_the_markdown_shape_too(capsys: pytest.CaptureFixture[str]) -> None:
    """Half the corpus ships its rules in a fenced block, and `play` dispatches
    on the suffix through the same `check_source` the checker does — so a
    designer reading a rulebook can run the file they are reading."""
    assert main(["play", str(REPO / "docs" / "games" / "gops.md"), "--seed", "5"]) == 0
    assert "returns" in capsys.readouterr().out


def test_the_same_seed_replays_the_same_game(capsys: pytest.CaptureFixture[str]) -> None:
    """Determinism as a property, not a captured string: pinning the exact
    output would redden whenever Hearts or the interpreter moves, in a change
    that touched neither."""
    assert main(["play", str(HEARTS), "--seed", "7"]) == 0
    first = capsys.readouterr().out
    assert main(["play", str(HEARTS), "--seed", "7"]) == 0
    assert capsys.readouterr().out == first


def test_an_unseeded_run_reports_the_seed_it_drew(capsys: pytest.CaptureFixture[str]) -> None:
    """The reported seed reproduces the run, which is the whole reason an
    omitted `--seed` still prints one."""
    assert main(["play", str(HEARTS)]) == 0
    drawn = capsys.readouterr().out
    seed = drawn.rsplit("seed", 1)[1].strip()
    assert main(["play", str(HEARTS), "--seed", seed]) == 0
    assert capsys.readouterr().out == drawn


def test_info_state_names_the_seat(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["play", str(HEARTS), "--seed", "7", "--info-state", "1"]) == 0
    out = capsys.readouterr().out
    assert "P1|" in out


def test_info_state_carries_the_state_variables() -> None:
    """The terminal snapshot is taken while the game-level frame still stands.

    `play_game` pops that frame before returning, so a snapshot taken after it
    returns renders `state:` empty and reads as a game that declared none —
    complete-looking and wrong. This is the pin on the one thing the snapshot
    site depends on beyond the trace event existing: WHERE it fires.
    """
    game = check_source(HEARTS)
    assert game.state is not None, "the pin needs a game that declares state"
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert main(["play", str(HEARTS), "--seed", "7", "--info-state", "1"]) == 0
    rendered = buffer.getvalue()
    segment = rendered.rsplit("|state:", 1)[1].split("|obs:")[0]
    assert segment, "the terminal information state lost its state variables"


# ---------------------------------------------------------------------------
# Failures, each rendered to its own author.
# ---------------------------------------------------------------------------


def test_a_static_failure_renders_as_check_renders_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`play` checks before it plays, so a compile diagnostic must reach the
    caller in the checker's own words — one rendering, not two."""
    bad = tmp_path / "bad.cardlang"
    bad.write_text(
        "game B {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  phase p { active_rules: [Ghost] }\n"
        "}\n"
    )
    assert main(["check", str(bad)]) == 1
    from_check = capsys.readouterr().err
    assert main(["play", str(bad)]) == 1
    assert capsys.readouterr().err == from_check


def test_a_runtime_failure_renders_without_a_traceback(
    capsys: pytest.CaptureFixture[str]
) -> None:
    """A game that is legal to the checker and illegal at play time is the
    game author's to fix, so it arrives as a message naming the layer and what
    they can do — never as a traceback, which addresses nobody who can act."""
    assert main(["play", str(OVERRUNS)]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "max_length" in err
    assert "playing" in err, "the message must say which layer refused"


# ---------------------------------------------------------------------------
# The two invocation forms.
# ---------------------------------------------------------------------------


def _module_form(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO), env.get("PYTHONPATH", "")])
    return subprocess.run(
        [sys.executable, "-m", "cardlang", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_python_m_cardlang_checks() -> None:
    """red under: delete `cardlang/__main__.py`."""
    done = _module_form([str(HEARTS)])
    assert done.returncode == 0, done.stderr


def test_python_m_cardlang_plays_the_same_game_as_the_console_script(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["play", str(HEARTS), "--seed", "7"]) == 0
    in_process = capsys.readouterr().out
    done = _module_form(["play", str(HEARTS), "--seed", "7"])
    assert done.returncode == 0, done.stderr
    assert done.stdout == in_process


def test_the_front_end_does_not_require_the_openspiel_extra() -> None:
    """`cardlang` is usable with the core install (README, Installation), so
    the command line must not drag in `pyspiel` by importing the adapter.

    red under: import `cardlang.openspiel.game` from `cardlang/cli.py`.
    """
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cardlang.cli, sys; print('pyspiel' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False"
