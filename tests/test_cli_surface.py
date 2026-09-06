"""The command-line surface: every command crossed with every option, and the
value classes a caller can supply.

property:        Every option the parser declares is accepted by exactly the
                 commands that declare it and refused by the rest, each
                 refusal loud in argparse's usage channel; every COMBINATION
                 of the `play` command's options is either carried out or
                 refused in the command's own words; every value class a
                 caller can supply to `--seed`, `--info-state` or `--at` is
                 either carried out or refused with a message naming what is
                 valid; and the two invocation forms — the console script and
                 `python -m cardlang` — reach the same front end.
domain:          The commands and options are whatever `cardlang.cli`'s
                 parser declares, derived from the parser itself, and the
                 combination cross is the power set of the `play` command's
                 own options, derived the same way. That cross varies an
                 option's PRESENCE and holds one representative value; the
                 value classes — the integer/non-integer and
                 in-range/out-of-range splits of the three options that take
                 one — are crossed separately, in the probes below. `--at`
                 numbers the
                 playout's decisions — one Chooser call, one moment a seat is
                 asked — so every index names a position with a view of its
                 own; the summary's `decisions` line counts the picks those
                 calls consume, which is the unit `max_length` bounds, and a
                 game choosing several cards at once makes the two numbers
                 differ (Hearts' pass, pinned below). The path
                 argument's whole failure class is here — a name that is
                 nothing, a name that is a directory, a file that will not
                 decode as text — because the command line owns that argument
                 and no earlier layer sees it. The failures it RENDERS are the
                 two the runtime types as catchable, `GameDescriptionError`
                 and `InstallationError`; an `IllegalMove` escaping a playout
                 is typed as neither and keeps its traceback while issue #554
                 settles what it means to a caller. `--decisions` renders
                 every candidate offered rather than only the one chosen, so
                 it reaches `runtime.observe.render` over a wider set than a
                 plain playout does; a shape outside that function's declared
                 renderings raises there, in the engine maintainer's channel,
                 which is why the rendering happens only for a line that will
                 be shown. Which file shapes exist is
                 `pipeline.check_source`'s question, answered in the pipeline
                 suite: `.cardlang` is raw DSL and every other suffix routes
                 to the Markdown extractor. What the checker decides about a
                 game and what a playout scores belong to those suites, and
                 are exercised here only far enough to tell an accepted
                 invocation from a refused one.
registry:        commands and options: `cardlang.cli.build_parser` via
                 `_command_options` below; the combination cross:
                 `_play_option_subsets` below, over the same parser; seat
                 bound: `game.players.low`, the same value
                 `cardlang.runtime.driver.play_game` seats; the decision
                 value rendering `--decisions` shares with the observation
                 log: `cardlang.runtime.observe.render`;
                 diagnostic rendering shared with the checker:
                 tests/test_rejections.py; the runtime failure hierarchy this
                 module renders: tests/test_failure_taxonomy.py; the file-shape
                 dispatch: tests/test_pipeline_cardlang.py; the append-only
                 observation log a mid-hand view is projected from:
                 tests/openspiel_ready/harness.py.
does not prove:  A green here says nothing about whether a playout's REPORTED
                 outcome is the right one — the returns and the decision count
                 are read back from the driver's and the adapter's own
                 derivations, and their correctness is those suites' claim,
                 not this module's. It equally says nothing about which games
                 a uniform-random line can finish: `play` renders that refusal
                 the same way whether the game or the policy is the reason,
                 and the corpus measurement is issue #553. Nor does it compare
                 the string `--at` renders against the one `pyspiel` renders
                 at the same decision: the two routes derive a seat's own
                 decision from different observation logs (issue #592), and
                 no cell here runs both.
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from itertools import combinations
from pathlib import Path

import pytest

from cardlang.cli import COMMANDS, build_parser, main
from cardlang.openspiel.replay import returns_for
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import InstallationError

REPO = Path(__file__).parent.parent
HEARTS = REPO / "docs" / "games" / "hearts.cardlang"
KUHN = REPO / "docs" / "games" / "kuhn-poker.cardlang"
# A game whose zones empty on the way to the end: the hole cards are the
# seat's own by identity while the hand is live and are mucked at the finish,
# so it is where a mid-hand view differs from the terminal one.
HOLDEM = REPO / "docs" / "games" / "holdem-heads-up.cardlang"
# Checks clean, then exceeds its declared `max_length` on every seed — the
# runtime half of the failure rendering, reached without tying the test to one
# corpus game's random line.
OVERRUNS = REPO / "tests" / "fixtures" / "exceeds_max_length.cardlang"
# A Markdown game file, its DSL in one fenced block: the shape `play` must
# route to the extractor. The corpus rulebooks link to their `.cardlang` rather
# than embedding one (docs/maintaining.md, "The rulebook twin"), so a fixture
# is what carries the shape.
MARKDOWN = REPO / "tests" / "fixtures" / "skeleton.md"


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


def _play_option_subsets() -> tuple[tuple[str, ...], ...]:
    """Every subset of the `play` command's own options, derived from the
    parser rather than listed beside it.

    The per-option cells above measure one option at a time, and an option
    that is accepted and then quietly does nothing passes every one of them.
    The presence/absence cross is where that shows: `--at` names WHICH
    decision to look at and carries no meaning without a `--info-state` to
    say whose view, so the combination is the unit the decision lives in.
    """
    options = sorted(_command_options()["play"])
    return tuple(
        tuple(subset)
        for size in range(len(options) + 1)
        for subset in combinations(options, size)
    )


# A representative legal value per option, so a cell tests the option's
# acceptance and not an unrelated value refusal. Kuhn asks twice, so `--at 0`
# names a decision it reaches on every seed.
_SAMPLE_VALUE: dict[str, list[str]] = {
    "--emit-ir": [],
    "--seed": ["7"],
    "--info-state": ["0"],
    "--at": ["0"],
    "--decisions": [],
}

# What an option needs beside it to be carried out at all, so a per-option
# cell measures the COMMAND's answer and not a companion's absence. `--at`
# without `--info-state` is refused by design, and `_at_alone` below is the
# probe that names it; supplying the companion here keeps the two questions
# apart.
_COMPANION: dict[str, list[str]] = {"--at": ["--info-state", "0"]}

# The authored expected column. Written as decisions, never derived from the
# parser: a grid whose expectations come from the same object it measures
# reports that the parser agrees with itself. A command or option the parser
# gains and this table lacks fails `test_every_cell_is_authored` rather than
# passing unexamined.
_EXPECTED: dict[tuple[str, str], str] = {
    ("check", "--emit-ir"): "accepted",
    ("check", "--seed"): "refused",
    ("check", "--info-state"): "refused",
    ("check", "--at"): "refused",
    ("check", "--decisions"): "refused",
    ("play", "--emit-ir"): "refused",
    ("play", "--seed"): "accepted",
    ("play", "--info-state"): "accepted",
    ("play", "--at"): "accepted",
    ("play", "--decisions"): "accepted",
}

# The authored expected column for the combination cross. `--at` is refused
# exactly when no `--info-state` says whose view to render; every other
# combination is carried out.
_COMBINATION_EXPECTED: dict[tuple[str, ...], str] = {
    (): "accepted",
    ("--at",): "refused",
    ("--decisions",): "accepted",
    ("--info-state",): "accepted",
    ("--seed",): "accepted",
    ("--at", "--decisions"): "refused",
    ("--at", "--info-state"): "accepted",
    ("--at", "--seed"): "refused",
    ("--decisions", "--info-state"): "accepted",
    ("--decisions", "--seed"): "accepted",
    ("--info-state", "--seed"): "accepted",
    ("--at", "--decisions", "--info-state"): "accepted",
    ("--at", "--decisions", "--seed"): "refused",
    ("--at", "--info-state", "--seed"): "accepted",
    ("--decisions", "--info-state", "--seed"): "accepted",
    ("--at", "--decisions", "--info-state", "--seed"): "accepted",
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


def test_every_combination_is_authored() -> None:
    """The derived subsets of `play`'s options and the authored column name
    the same cells, so an option added to `play` arrives as a doubled cross
    to decide rather than as combinations nobody looked at."""
    assert set(_play_option_subsets()) == set(_COMBINATION_EXPECTED), (
        "the `play` command's options and the authored combination "
        "expectations have drifted; decide what each new combination means"
    )


@pytest.mark.parametrize(("command", "option"), sorted(_EXPECTED))
def test_command_option_cell(command: str, option: str, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        command,
        str(KUHN),
        option,
        *_SAMPLE_VALUE[option],
        *_COMPANION.get(option, []),
    ]
    if _EXPECTED[(command, option)] == "accepted":
        assert main(argv) == 0
        return
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert option in err, f"the refusal must name {option}"
    assert "usage:" in err, "the refusal must show what the command accepts"


@pytest.mark.parametrize("subset", sorted(_COMBINATION_EXPECTED))
def test_play_option_combination_cell(
    subset: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    """Each combination of `play`'s options is carried out or refused, and a
    refusal reaches the caller in the command's own words rather than
    argparse's — the parser accepts every one of these sentences, so what
    decides them is `_play`."""
    argv = ["play", str(KUHN)]
    for option in subset:
        argv += [option, *_SAMPLE_VALUE[option]]
    if _COMBINATION_EXPECTED[subset] == "accepted":
        assert main(argv) == 0
        return
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert "--at" in err, "the refusal must name the option that needs a companion"
    assert "--info-state" in err, "the refusal must name what to add"


# ---------------------------------------------------------------------------
# Misuse probes: the first token, and the value classes of the two options
# that take one. Each must be loud in the layer that owns it.
# ---------------------------------------------------------------------------


def test_bare_file_still_checks() -> None:
    """The command name is omissible: a bare file is read as `check`."""
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
    err = capsys.readouterr().err
    for command in COMMANDS:
        assert command in err


def test_a_command_in_the_wrong_slot_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """The plausible wrong sentence: the file first and the command after it.
    The bare form's rewrite makes that a `check` with a stray positional, so
    the refusal has to reach the caller rather than the file being checked and
    the command quietly dropped."""
    with pytest.raises(SystemExit) as exit_info:
        main([str(HEARTS), "play"])
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "play" in err
    for command in COMMANDS:
        assert command in err, "the usage line must name where a command goes"


def test_a_command_with_no_file_names_the_missing_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["check"])
    assert exit_info.value.code == 2
    assert "file" in capsys.readouterr().err


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_each_command_has_its_own_help(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--help` after a command reaches that command's parser, so the options
    a caller is shown are the ones that command accepts."""
    with pytest.raises(SystemExit) as exit_info:
        main([command, "--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert f"cardlang {command}" in out
    for option in sorted(_command_options()[command]):
        assert option in out


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


# ---------------------------------------------------------------------------
# `--at`: the value classes of a decision index, and the two flags' pairing.
# The first two refusals need no playout to decide and are taken beside the
# seat check; the third needs the count only the playout produces.
# ---------------------------------------------------------------------------


def _listing_of(rendered: str) -> tuple[str, list[str]]:
    """The `--decisions` listing's header and its rows.

    The summary indents its own lines too, so the rows are taken from the
    block the header opens rather than by indentation — a filter that reads
    `  returns  P0 0` as a decision would pass on output that has no listing
    in it at all.
    """
    head, _, rest = rendered.partition("; --at takes")
    header = head.rsplit("\n\n", 1)[1] + "; --at takes" + rest.split("\n", 1)[0]
    rows = []
    for line in rest.split("\n", 1)[1].splitlines():
        if not line.startswith("  ") or not line.split()[0].isdigit():
            break
        rows.append(line)
    return header, rows


def test_at_alone_says_whose_view_is_missing(capsys: pytest.CaptureFixture[str]) -> None:
    """`--at` picks which decision and `--info-state` picks whose view. Neither
    answers the other's question, so the sentence is refused rather than
    carried out against a seat nobody named."""
    assert main(["play", str(KUHN), "--at", "0"]) == 2
    err = capsys.readouterr().err
    assert "--at" in err
    assert "--info-state" in err, "the refusal must name what to add"


def test_a_negative_decision_index_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """A negative index is not a decision. `--seed -3` is legal, so a caller
    has every reason to think a leading minus is fine here too; and Python
    would read this one as counting from the end."""
    assert main(["play", str(KUHN), "--info-state", "0", "--at", "-1"]) == 2
    err = capsys.readouterr().err
    assert "--at -1" in err
    assert "start at 0" in err, "the refusal must name where a playout's decisions start"


def test_non_integer_at_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["play", str(KUHN), "--info-state", "0", "--at", "last"])
    assert exit_info.value.code == 2
    assert "--at" in capsys.readouterr().err


def test_a_decision_index_past_the_last_names_the_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The count is the playout's, so this refusal comes after the summary —
    and it names the range rather than clamping to the last decision, which
    would answer a question nobody asked."""
    assert main(["play", str(KUHN), "--seed", "7", "--info-state", "0", "--at", "99"]) == 2
    err = capsys.readouterr().err
    assert "--at 99" in err
    assert "0.." in err, "the refusal must name the decisions this playout has"


def test_at_on_a_game_with_no_decisions_says_there_are_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The skeleton deals and scores without asking anyone to choose, so there
    is no decision for `--at` to name — a different answer from an index past
    the last, and the designer of an early skeleton meets this one first.

    Both indices take that answer. The range refusal would spell an empty
    playout `0..-1`, so the order of the two is what keeps that off the
    screen, and only the higher index would reach it.
    """
    for index in ("0", "5"):
        argv = ["play", str(MARKDOWN), "--seed", "5", "--info-state", "0", "--at", index]
        assert main(argv) == 2
        err = capsys.readouterr().err
        assert "without a decision" in err
        assert "0..-1" not in err, "an empty playout has no range to name"


def test_the_last_decision_index_is_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    """The boundary the range refusal is drawn against."""
    assert main(["play", str(KUHN), "--seed", "7", "--decisions"]) == 0
    _, rows = _listing_of(capsys.readouterr().out)
    last = int(rows[-1].split()[0])
    assert main(
        ["play", str(KUHN), "--seed", "7", "--info-state", "0", "--at", str(last)]
    ) == 0
    assert f"at decision {last}" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# `--at`: what the view at a named decision actually shows.
# ---------------------------------------------------------------------------


def test_at_reaches_a_card_the_terminal_position_has_mucked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The whole point of naming a decision: a hole card is the seat's own, by
    identity, while the hand is live, and gone from every zone once the hand
    mucks it. The terminal view can only ever show the second, which is why a
    seat's view part-way through is a question the command line has to be able
    to answer.
    """
    assert main(["play", str(HOLDEM), "--seed", "7", "--info-state", "0", "--at", "0"]) == 0
    mid_hand = capsys.readouterr().out
    assert main(["play", str(HOLDEM), "--seed", "7", "--info-state", "0"]) == 0
    terminal = capsys.readouterr().out

    def hole(rendered: str) -> str:
        state = rendered.rsplit("P0|", 1)[1]
        return next(z for z in state.split("|")[0].split(";") if z.startswith("hole[0]="))

    assert hole(mid_hand) != "hole[0]=[]", "the seat's own cards are its view mid-hand"
    assert hole(terminal) == "hole[0]=[]", "the terminal position has mucked them"


def test_at_shows_a_seat_that_is_not_the_actor(capsys: pytest.CaptureFixture[str]) -> None:
    """Asking what the OPPONENT knows at your decision is the question a bluff
    turns on, so the seat and the decision's actor are independent."""
    assert main(["play", str(HOLDEM), "--seed", "7", "--decisions"]) == 0
    _, rows = _listing_of(capsys.readouterr().out)
    index = next(
        int(row.split()[0]) for row in rows if row.split()[1] == "P1"
    )
    assert main(
        ["play", str(HOLDEM), "--seed", "7", "--info-state", "0", "--at", str(index)]
    ) == 0
    out = capsys.readouterr().out
    assert "P0|" in out, "the view is the seat's, not the actor's"
    assert f"at decision {index}" in out


def test_at_indexes_the_moment_not_the_pick(capsys: pytest.CaptureFixture[str]) -> None:
    """Hearts' pass chooses three cards in one decision, so the playout's
    decisions and the picks the summary counts are different numbers. Every
    index names a distinct position; the listing states both counts so the two
    are never read as one."""
    assert main(["play", str(HEARTS), "--seed", "7", "--decisions"]) == 0
    out = capsys.readouterr().out
    picks = int(out.split("decisions", 1)[1].split()[0])
    header, rows = _listing_of(out)
    total = int(header.split()[0])
    assert total == len(rows), "every decision the header counts is on the list"
    assert total < picks, "Hearts' pass takes three cards in one decision"
    assert str(picks) in header, "the listing reconciles its count with the summary's"
    assert f"0..{total - 1}" in header, "the header names the range --at takes"


def test_a_long_candidate_pool_trails_off(capsys: pytest.CaptureFixture[str]) -> None:
    """A line names enough candidates to recognize the decision, not the whole
    pool — and says so, because the ellipsis is the only sign a designer gets
    that the pool runs on. Hearts' pass offers a full hand.

    red under: drop the `shown.append("...")` arm from `cardlang.cli._decision`.
    """
    assert main(["play", str(HEARTS), "--seed", "7", "--decisions"]) == 0
    _, rows = _listing_of(capsys.readouterr().out)
    long_pools = [row for row in rows if int(row.split(" of ")[1].split(":")[0]) > 6]
    assert long_pools, "the pin needs a decision offering more than a line names"
    for row in long_pools:
        assert row.endswith("..."), "a pool a line cannot hold must trail off"
    assert not any(row.endswith("...") for row in rows if row not in long_pools), (
        "a pool a line holds whole must not claim it was cut"
    )


def test_the_listing_numbers_every_decision(capsys: pytest.CaptureFixture[str]) -> None:
    """Every decision the playout made is on the list, numbered from zero and
    naming its actor — the listing is what makes an index discoverable."""
    assert main(["play", str(HOLDEM), "--seed", "7", "--decisions"]) == 0
    _, rows = _listing_of(capsys.readouterr().out)
    assert [int(row.split()[0]) for row in rows] == list(range(len(rows)))
    for row in rows:
        assert row.split()[1].startswith("P"), "each decision names who makes it"
        assert "chooses" in row, "each decision names what is being chosen from"


def test_numbering_a_playout_does_not_move_it(capsys: pytest.CaptureFixture[str]) -> None:
    """Reading a playout must not change it.

    `play` supplies its own Chooser at every invocation, to number the
    decisions and to reach a named one. `play_game` builds the uniform-random
    Chooser from the generator it is handed when a caller supplies none, so
    the command must build its own from that same generator: a second
    `random.Random` splits the shuffle and the policy into separate streams,
    and the seed a designer reproduces from would name a different game.

    The comparison is against the driver playing for itself, because the two
    command invocations both install the Chooser — a plant that moves the
    playout moves both of them together, and they would go on agreeing.

    red under: build the Chooser from `random.Random(drawn)` in
    `cardlang.cli._play` rather than from the generator handed to `play_game`.
    """
    game = check_source(HEARTS)
    played = play_game(game, random.Random(7))

    assert main(["play", str(HEARTS), "--seed", "7", "--decisions"]) == 0
    out = capsys.readouterr().out
    reported = out.split("returns", 1)[1].split("\n")[0].strip()
    expected = ", ".join(
        f"P{player} {int(value)}"
        for player, value in enumerate(returns_for(game, played))
    )
    assert reported == expected, (
        "the command's playout and the driver's own have diverged"
    )
    assert f"across {played.hands_played} hands" in out


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
    """A Markdown game file carries its DSL in a fenced block, and `play`
    dispatches on the suffix through the same `check_source` the checker does,
    so the file a designer is reading is the file they can run."""
    assert main(["play", str(MARKDOWN), "--seed", "5"]) == 0
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
