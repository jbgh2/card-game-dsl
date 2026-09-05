"""Registering a game file with OpenSpiel, from the corpus and from a path.

property:        Every way a `.cardlang` file reaches `pyspiel.register_game`
                 goes through one function, so a file registered by path is
                 classified, checked and named exactly as a corpus game is;
                 and every state a path or an entry can be in yields either a
                 registration or a refusal naming what is wrong — never a
                 short name `pyspiel.load_game` cannot reach, and never a
                 silent replacement of a game already registered. An
                 operation that offers SEVERAL files registers all of them or
                 none: the refusal arrives with pyspiel untouched, so a
                 corrected offer meets a registry holding nothing the refused
                 one put there.
domain:          Three crossings, each total over its axes. The first crosses
                 the registration SOURCE with the state of the file or entry
                 it offers; the second crosses the same sources with the state
                 of the short name that file derives — a state that spans BOTH
                 registries a name can be spoken for in, the adapter's own map
                 of the files it registered and the process-global one pyspiel
                 keeps, since a name held only by the second is one no file of
                 this process's own naming can be produced for. They factor
                 because a name binds only after the check passes — a file the
                 checker refuses never reaches `pyspiel.register_game`, so it
                 cannot take a name;
                 `test_a_refused_file_leaves_its_short_name_free`
                 is the cell that holds the factorization, and without it the
                 halving would be a convenience rather than a fact.

                 The third crosses each file-offering OPERATION with the stage
                 at which one of its files is refused, and asks what became of
                 the files planned before it. Operations rather than sources,
                 because the environment performs two that strand different
                 files: its entry list is one, and each directory entry it
                 names is globbed into another. The batch guarantee is
                 per-operation and stated that way — the corpus is registered
                 before the variable is read, so a refused variable leaves a
                 pyspiel holding exactly the corpus, which is what
                 `_register_env_var` says and what makes a corrected variable
                 safe to offer in a FRESH process. In the same one it is not:
                 the refusal takes the adapter's map with it and leaves those
                 corpus names held with no file to match them to, so
                 re-importing meets the `registered_outside` refusal on the
                 first of them —
                 `test_a_refused_import_leaves_the_corpus_names_held`, which
                 needs its own interpreter for the state and not the property.

                 Inside the domain: the OpenSpiel short name and its character
                 set, the collision rule across every pair of sources, the
                 entry vocabulary `CARDLANG_GAMES` accepts, that variable's own
                 value classes, and both halves of `check_source`'s suffix
                 dispatch — a path source names one file, so it may name a
                 Markdown one, while a directory is globbed for `.cardlang` as
                 the corpus directory is and a directory of rulebooks is
                 therefore an empty one. Outside it, each with the site that
                 owns it instead: what the CHECKER decides about a game is
                 `cardlang.pipeline`'s, exercised here only far enough to tell
                 an accepted file from a refused one; whether a path's bytes
                 decode as text is `check_source`'s unguarded read, whose whole
                 failure class the command line owns and pins
                 (tests/test_cli_surface.py); and what the adapter derives from
                 a game's header once registered is the adapter's, unchanged by
                 which source offered the file — with one header fact that this
                 surface newly puts within a designer's reach, a `players:`
                 range silently read as its low bound, recorded as issue #570.

                 The proof battery is corpus-bound: a game registered by path
                 gets the adapter's derived information states and no readiness
                 proof, which is issue #25 and states itself at the function.
                 This module runs only where the `openspiel` extra is
                 installed; two cells additionally need a fresh interpreter,
                 both for what adapter IMPORT does rather than for what a
                 refusal is, because `CARDLANG_GAMES` is read once at that
                 import and `pyspiel.register_game` has no inverse. The grids'
                 own environment cells drive `_register_env_var` in this
                 process instead.
registry:        sources and file/entry states: `_SOURCES` and `_FILE_STATES`
                 below, crossed into `_FILE_EXPECTED`; name states:
                 `_NAME_STATES`, crossed into `_NAME_EXPECTED`, over both
                 registries a short name can be taken in; batches and
                 refusal stages: `_BATCHES` and `_PREFLIGHT_STAGES`, crossed
                 into `_BATCH_EXPECTED`, with the batch axis tied to
                 `_SOURCES` by `test_every_source_performs_a_batch` and the
                 stage axis derived against the two authored columns by
                 `test_every_refusal_belongs_to_a_preflight_stage`; the
                 adapter's own map: `cardlang.openspiel.game._REGISTERED`; the
                 process-global registry the name and batch cells read:
                 `pyspiel.registered_names`; the entry
                 vocabulary: `cardlang.openspiel.game.ENTRY_KINDS`, held in
                 step with the env dispatch by
                 `test_the_entry_kinds_and_the_dispatch_agree`; the short-name
                 rule and its character set:
                 `cardlang.openspiel.registry._short_name` and
                 `cardlang.openspiel.registry.SHORT_NAME_CHARS`; the one
                 registration site:
                 `test_one_registration_site_in_the_package` scrapes it;
                 module collection without the extra:
                 tests/test_optional_pyspiel.py::test_every_test_module_imports_without_pyspiel;
                 the failure type's position in the taxonomy:
                 tests/test_failure_taxonomy.py.
does not prove:  A green here says nothing about whether a registered game's
                 information states are sound — that a game LOADS and steps is
                 all these cells watch, and soundness is the readiness
                 battery's claim over the corpus. Nor does it establish that
                 the short-name character set admits every name OpenSpiel can
                 load: it is a subset chosen so a refusal precedes the
                 irreversible `pyspiel.register_game`, so names outside it are
                 refused whether or not OpenSpiel would have taken them. Nor
                 does it make the process-global registry safe against a
                 CONCURRENT writer: the names a batch treats as taken are read
                 once, before its first commit, and pyspiel offers no
                 register-if-absent to close the window, so a name another
                 component registers between a plan and its commit is replaced
                 as it was before. A designed constraint of that API, not a
                 deferral — there is no primitive to build the alternative on.
"""

from __future__ import annotations

import ast
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang
from cardlang.diagnostics import DiagnosticError
from cardlang.openspiel.game import (
    ENTRY_KINDS,
    GAMES_ENV_VAR,
    _register_all,
    _register_env_var,
    _REGISTERED,
    register_game_file,
)
from cardlang.openspiel.registry import _derive_games, _short_name
from cardlang.runtime.errors import GameRegistrationError, InstallationError

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "docs" / "games"
# A small, fast, chance-bearing corpus game, copied wherever a cell needs a
# file the checker accepts. Copying beats authoring a fixture game: the cell is
# about registration, and a hand-written stub would drift from what the checker
# accepts the first time the language moves.
GREEN_SOURCE = CORPUS / "kuhn-poker.cardlang"


# ---------------------------------------------------------------------------
# The axes.
# ---------------------------------------------------------------------------

# How a file reaches the one registration function. `corpus` is the glob over
# `docs/games/`; `call` is `register_game_file`; `environment` is an entry in
# `CARDLANG_GAMES`. `test_one_registration_site_in_the_package` is what keeps
# this list total: a fourth source cannot register a game without going through
# the site that scrape pins.
_SOURCES: tuple[str, ...] = ("corpus", "call", "environment")

# What the source offers. `empty_entry` is the empty string a separator pair
# leaves behind (`a::b`, or a trailing separator); `bad_stem_file` is a file the
# checker accepts whose stem cannot render a short name `pyspiel.load_game` can
# reach.
_FILE_STATES: tuple[str, ...] = (
    "green_file",
    "diagnostic_file",
    "markdown_with_block",
    "markdown_without_block",
    "missing",
    "directory_of_games",
    "empty_directory",
    "empty_entry",
    "bad_stem_file",
)

# The state of the short name the offered file derives, with the file itself
# held green. `corpus_name` is the reachable collision — a designer's own
# `hearts.cardlang` against the corpus one. `registered_outside` is the state
# only the process-global registry can report: pyspiel holds the name and the
# adapter's map has no file for it, so the refusal has a name to state and no
# file to name.
_NAME_STATES: tuple[str, ...] = (
    "fresh",
    "same_path",
    "prior_call_other_path",
    "corpus_name",
    "registered_outside",
)

# Every operation that offers files to the one registration function, named for
# the source that performs it. A source appears once per operation, so the
# environment appears twice: its entry list is one batch, and each directory
# entry in that list is globbed into another. Those are different positions —
# a refusal between two entries and a refusal inside one entry's glob strand
# different files — and `test_every_source_performs_a_batch` ties the axis
# back to `_SOURCES`, so a source whose operations nobody enumerated fails.
_BATCHES: tuple[str, ...] = (
    "call",
    "corpus_glob",
    "environment_directory",
    "environment_entries",
)

_BATCH_SOURCE: dict[str, str] = {
    "call": "call",
    "corpus_glob": "corpus",
    "environment_directory": "environment",
    "environment_entries": "environment",
}

# The stage at which a file a batch offers is refused. `entry_shape` is whether
# what the batch names is a game file at all; `stem` is the short name the
# filename renders; `checker` is the front end over the file's text;
# `collision` is that short name against the names already spoken for — in the
# adapter's own map, in the batch being planned, and in pyspiel's process-global
# registry alike, which is one stage because one comparison answers all three.
# `test_every_refusal_belongs_to_a_preflight_stage` derives this axis's
# totality from the two authored columns above rather than asserting it.
_PREFLIGHT_STAGES: tuple[str, ...] = ("entry_shape", "stem", "checker", "collision")

# Which stage refuses each refusing cell of the two grids above. Written
# against those columns rather than listed from the implementation, so a
# refusal state added to either grid arrives here as an unmapped cell and its
# author has to say which stage catches it.
_STAGE_OF_REFUSAL: dict[tuple[str, str], str] = {
    ("corpus", "diagnostic_file"): "checker",
    ("corpus", "empty_directory"): "entry_shape",
    ("corpus", "bad_stem_file"): "stem",
    ("corpus", "corpus_name"): "collision",
    ("corpus", "registered_outside"): "collision",
    ("call", "diagnostic_file"): "checker",
    ("call", "markdown_without_block"): "checker",
    ("call", "missing"): "entry_shape",
    ("call", "directory_of_games"): "entry_shape",
    ("call", "empty_directory"): "entry_shape",
    ("call", "empty_entry"): "entry_shape",
    ("call", "bad_stem_file"): "stem",
    ("call", "prior_call_other_path"): "collision",
    ("call", "corpus_name"): "collision",
    ("call", "registered_outside"): "collision",
    ("environment", "diagnostic_file"): "checker",
    ("environment", "markdown_without_block"): "checker",
    ("environment", "missing"): "entry_shape",
    ("environment", "empty_directory"): "entry_shape",
    ("environment", "empty_entry"): "entry_shape",
    ("environment", "bad_stem_file"): "stem",
    ("environment", "prior_call_other_path"): "collision",
    ("environment", "corpus_name"): "collision",
    ("environment", "registered_outside"): "collision",
}

# The outcome vocabulary. `inexpressible` is surface totality's third state:
# the source cannot put a file in that state at all. `atomic` is the batch
# guarantee: a refusal leaves the batch's EARLIER files unregistered.
_REGISTERS = "registers"
_INEXPRESSIBLE = "inexpressible"
_ATOMIC = "atomic"

# source x file/entry state. Authored as decisions, never read back from the
# implementation.
_FILE_EXPECTED: dict[tuple[str, str], str] = {
    # The corpus source is a glob over a directory this checkout controls.
    ("corpus", "green_file"): _REGISTERS,
    ("corpus", "diagnostic_file"): "DiagnosticError",
    # The corpus glob is `*.cardlang`, so a Markdown file in `docs/games/` —
    # the rulebook twin every game carries — is never a thing the corpus source
    # offers, whether or not it holds a block.
    ("corpus", "markdown_with_block"): _INEXPRESSIBLE,
    ("corpus", "markdown_without_block"): _INEXPRESSIBLE,
    # A glob yields only paths that exist, and yields files rather than the
    # directory holding them.
    ("corpus", "missing"): _INEXPRESSIBLE,
    ("corpus", "directory_of_games"): _REGISTERS,
    ("corpus", "empty_directory"): "InstallationError",
    # The corpus is a directory, not a list of entries; there is no separator
    # for an empty one to sit between.
    ("corpus", "empty_entry"): _INEXPRESSIBLE,
    ("corpus", "bad_stem_file"): "InstallationError",
    # A call names one file.
    ("call", "green_file"): _REGISTERS,
    ("call", "diagnostic_file"): "DiagnosticError",
    ("call", "markdown_with_block"): _REGISTERS,
    ("call", "markdown_without_block"): "DiagnosticError",
    ("call", "missing"): "GameRegistrationError",
    ("call", "directory_of_games"): "GameRegistrationError",
    ("call", "empty_directory"): "GameRegistrationError",
    ("call", "empty_entry"): "GameRegistrationError",
    ("call", "bad_stem_file"): "GameRegistrationError",
    # An entry is a file or a directory of files.
    ("environment", "green_file"): _REGISTERS,
    ("environment", "diagnostic_file"): "DiagnosticError",
    ("environment", "markdown_with_block"): _REGISTERS,
    ("environment", "markdown_without_block"): "DiagnosticError",
    ("environment", "missing"): "GameRegistrationError",
    ("environment", "directory_of_games"): _REGISTERS,
    ("environment", "empty_directory"): "GameRegistrationError",
    ("environment", "empty_entry"): "GameRegistrationError",
    ("environment", "bad_stem_file"): "GameRegistrationError",
}

# source x name state, the file held green.
_NAME_EXPECTED: dict[tuple[str, str], str] = {
    ("corpus", "fresh"): _REGISTERS,
    # The corpus derivation maps each short name once, so it never offers one
    # twice from the same file.
    ("corpus", "same_path"): _INEXPRESSIBLE,
    # The corpus loop runs at adapter import, before any call can have taken a
    # name.
    ("corpus", "prior_call_other_path"): _INEXPRESSIBLE,
    ("corpus", "corpus_name"): "InstallationError",
    # Live where `prior_call_other_path` is not, and the temporal argument
    # above is exactly why: taking a name through this adapter needs the
    # adapter imported, and calling `pyspiel.register_game` does not — so a
    # component that holds a corpus game's name before the corpus loop runs is
    # a process anyone can compose. It is also the cell that shows the union is
    # read where every batch passes rather than at the two entry points.
    ("corpus", "registered_outside"): "GameRegistrationError",
    ("call", "fresh"): _REGISTERS,
    ("call", "same_path"): "idempotent",
    ("call", "prior_call_other_path"): "GameRegistrationError",
    ("call", "corpus_name"): "GameRegistrationError",
    ("call", "registered_outside"): "GameRegistrationError",
    ("environment", "fresh"): _REGISTERS,
    ("environment", "same_path"): "idempotent",
    ("environment", "prior_call_other_path"): "GameRegistrationError",
    ("environment", "corpus_name"): "GameRegistrationError",
    ("environment", "registered_outside"): "GameRegistrationError",
}


# batch x the stage at which one of its files is refused. `atomic` is the
# claim: the batch's EARLIER files are not registered either. Authored as
# decisions, never read back from the implementation.
_BATCH_EXPECTED: dict[tuple[str, str], str] = {
    # A call names one file. No stage has an earlier file to strand, which is
    # what makes the other three batches the whole of this domain.
    ("call", "entry_shape"): _INEXPRESSIBLE,
    ("call", "stem"): _INEXPRESSIBLE,
    ("call", "checker"): _INEXPRESSIBLE,
    ("call", "collision"): _INEXPRESSIBLE,
    # `_derive_games` refuses an empty directory, an unrenderable stem and a
    # colliding pair while reading filenames, before the loop registers
    # anything — so the checker is the one stage a corpus batch reaches with
    # files already planned.
    ("corpus_glob", "entry_shape"): _INEXPRESSIBLE,
    ("corpus_glob", "stem"): _INEXPRESSIBLE,
    ("corpus_glob", "collision"): _INEXPRESSIBLE,
    ("corpus_glob", "checker"): _ATOMIC,
    # A directory entry is globbed for `*.cardlang`, so every path it yields
    # exists and is a file and the shape stage is settled by the glob itself.
    ("environment_directory", "entry_shape"): _INEXPRESSIBLE,
    ("environment_directory", "stem"): _ATOMIC,
    ("environment_directory", "checker"): _ATOMIC,
    ("environment_directory", "collision"): _ATOMIC,
    # The entry list: the batch whose files a refusal used to strand.
    ("environment_entries", "entry_shape"): _ATOMIC,
    ("environment_entries", "stem"): _ATOMIC,
    ("environment_entries", "checker"): _ATOMIC,
    ("environment_entries", "collision"): _ATOMIC,
}


def test_every_file_cell_is_authored() -> None:
    """The derived cross and the authored column name the same cells."""
    derived = {(s, f) for s in _SOURCES for f in _FILE_STATES}
    assert derived == set(_FILE_EXPECTED)


def test_every_name_cell_is_authored() -> None:
    derived = {(s, n) for s in _SOURCES for n in _NAME_STATES}
    assert derived == set(_NAME_EXPECTED)


def test_every_batch_cell_is_authored() -> None:
    derived = {(b, s) for b in _BATCHES for s in _PREFLIGHT_STAGES}
    assert derived == set(_BATCH_EXPECTED)


def test_every_source_performs_a_batch() -> None:
    """The batch axis is the source axis, one row per file-offering operation.

    A fourth source cannot register a game without going through the site
    `test_one_registration_site_in_the_package` pins, so a source with no row
    here is a source whose operations nobody enumerated. The environment
    carries two rows because `"directory"` is an entry kind: one entry can
    name many files, and a refusal inside that glob strands different files
    from a refusal between two entries.
    """
    assert set(_BATCH_SOURCE) == set(_BATCHES)
    assert set(_BATCH_SOURCE.values()) == set(_SOURCES)
    assert "directory" in ENTRY_KINDS


def test_every_refusal_belongs_to_a_preflight_stage() -> None:
    """The stage axis is total over what the two grids above refuse.

    The batch grid asks what a refusal leaves behind, so its stage axis has to
    name every refusal there is. Derived against the authored columns rather
    than listed, so a refusal state added to either grid arrives here as an
    unmapped cell — and nobody can add one without saying which stage catches
    it, which is the question the batch grid then has to answer.

    Every stage is required to carry a refusal, too: a stage no grid cell
    reaches is a column the batch grid crosses for nothing.

    red under, both halves, both verified: add a refusing cell to
    `_FILE_EXPECTED` with no stage row (`test_every_file_cell_is_authored`
    reddens beside it, so the pair says which went missing); drop a stage from
    `_PREFLIGHT_STAGES` (`test_every_batch_cell_is_authored` reddens beside
    it). Born green — the map was written against grids that already existed,
    so neither half's red run happened on its own.
    """
    outcomes = {**_FILE_EXPECTED, **_NAME_EXPECTED}
    refusing = {
        cell
        for cell, outcome in outcomes.items()
        if outcome not in (_REGISTERS, _INEXPRESSIBLE, "idempotent")
    }
    assert set(_STAGE_OF_REFUSAL) == refusing
    assert set(_STAGE_OF_REFUSAL.values()) == set(_PREFLIGHT_STAGES)


def test_the_entry_kinds_and_the_dispatch_agree() -> None:
    """`ENTRY_KINDS`, what `_entry_kind` returns, and what `_entry_files`
    dispatches on are one set — so the file-state axis crosses every kind the
    env source can produce, and a kind the dispatch gains without a cell here
    fails this rather than riding unexercised.

    Derived from those two functions' own source, because nothing at runtime
    reads the tuple: it declares a set two functions state in bare literals,
    and an equality against a literal set would pin only the tuple against
    itself. Measured before this derivation existed — dropping a member from
    `ENTRY_KINDS` reddened that equality and nothing else, the dispatch going
    on handling the dropped kind correctly.

    red under: drop a member from `ENTRY_KINDS`, or give `_entry_kind` a
    `return "symlink"` arm `_entry_files` does not answer. Verified.
    """
    root = pathlib.Path(str(cardlang.__file__)).parent
    tree = ast.parse((root / "openspiel" / "game.py").read_text())
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    returned = {
        node.value.value
        for node in ast.walk(functions["_entry_kind"])
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    dispatched = {
        operand.value
        for node in ast.walk(functions["_entry_files"])
        if isinstance(node, ast.Compare)
        for operand in node.comparators
        if isinstance(operand, ast.Constant) and isinstance(operand.value, str)
    }
    assert returned == set(ENTRY_KINDS), returned
    assert dispatched == set(ENTRY_KINDS), dispatched


# ---------------------------------------------------------------------------
# Fixtures: unique stems per cell. `pyspiel.register_game` is process-global
# and has no inverse, so no two cells may claim one short name and no cell may
# assume an empty registry.
# ---------------------------------------------------------------------------


def _green_copy(directory: Path, stem: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    dst = directory / f"{stem}.cardlang"
    shutil.copy(GREEN_SOURCE, dst)
    return dst


def _diagnostic_copy(directory: Path, stem: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    dst = directory / f"{stem}.cardlang"
    dst.write_text("game NotAGame {\n  players: 2\n}\n")
    return dst


def _markdown_copy(directory: Path, stem: str, *, with_block: bool) -> Path:
    """A game file whose suffix sends it to the Markdown extractor.

    `check_source` dispatches on the suffix — `.cardlang` is raw DSL, anything
    else is Markdown holding exactly one fenced block — so a path source can
    offer either shape. `with_block=False` is the corpus's own rulebook-twin
    shape, which links to its `.cardlang` rather than repeating it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    dst = directory / f"{stem}.md"
    body = f"# {stem}\n\nA rulebook.\n"
    if with_block:
        body += "\n```\n" + GREEN_SOURCE.read_text() + "```\n"
    dst.write_text(body)
    return dst


def _register_outside(short_name: str) -> str:
    """Give `short_name` to pyspiel directly, as another component does, and
    return the long name that identifies what it holds.

    Nothing here touches the adapter, which is the whole of the state being
    built: the name is spoken for in the process-global registry and the
    adapter's map has no entry for it. The long name is the discriminator a
    cell reads back — the adapter renders `Cardlang <game name>`, so one that
    cannot be that spelling tells the game pyspiel still answers with apart
    from a replacement.

    The game is a shell rather than a copy of a corpus one: what a cell asks
    of it is that it hold a name and load, and a shell that cannot step is the
    stronger fixture for the second half, since a cell that accidentally
    replaced it would then have to say so.
    """
    long_name = f"Outside cardlang, {short_name}"
    game_type = pyspiel.GameType(
        short_name=short_name,
        long_name=long_name,
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
        information=pyspiel.GameType.Information.PERFECT_INFORMATION,
        utility=pyspiel.GameType.Utility.ZERO_SUM,
        reward_model=pyspiel.GameType.RewardModel.TERMINAL,
        max_num_players=2,
        min_num_players=2,
        provides_information_state_string=False,
        provides_information_state_tensor=False,
        provides_observation_string=False,
        provides_observation_tensor=False,
        provides_factored_observation_string=False,
    )
    game_info = pyspiel.GameInfo(
        num_distinct_actions=1,
        max_chance_outcomes=0,
        num_players=2,
        min_utility=-1.0,
        max_utility=1.0,
        utility_sum=0.0,
        max_game_length=1,
    )

    # `pyspiel` reaches this module through `importorskip`, so it is a value
    # and not a name mypy can resolve a base class through — the adapter and
    # the experiment rigs `import pyspiel` and silence the untyped base as
    # `misc` instead.
    class _Outside(pyspiel.Game):  # type: ignore[name-defined,misc]
        def __init__(self, params: object = None) -> None:
            super().__init__(game_type, game_info, params or {})

        def new_initial_state(self) -> object:
            raise NotImplementedError

    pyspiel.register_game(game_type, _Outside)
    return long_name


def _env_registration(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    """Run the environment source over `value`, in this process.

    `_register_env_var` is the whole of what adapter import does with the
    variable, so driving it directly exercises the same parse, the same
    dispatch and the same refusals — and it does so in the failure channel the
    refusals actually use, rather than by scraping a subprocess's stderr for
    the name of an exception. That adapter import CALLS it is a separate claim
    with its own subprocess pin below; it is one property, so it is one
    subprocess rather than one per cell.
    """
    if value is None:
        monkeypatch.delenv(GAMES_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(GAMES_ENV_VAR, value)
    _register_env_var()


# ---------------------------------------------------------------------------
# Grid 1 — source x file/entry state.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("source", "state"), sorted(_FILE_EXPECTED))
def test_file_state_cell(
    source: str, state: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _FILE_EXPECTED[(source, state)]
    if expected == _INEXPRESSIBLE:
        pytest.skip(f"{source} cannot offer a {state}: see the authored column")
    stem = f"probe_{source}_{state}"
    if source == "corpus":
        _corpus_cell(state, stem, tmp_path)
    elif source == "call":
        _call_cell(state, stem, tmp_path)
    else:
        _environment_cell(state, stem, tmp_path, monkeypatch)


def _corpus_cell(state: str, stem: str, tmp_path: Path) -> None:
    """The corpus source is `_derive_games` over a directory, driven here on a
    temporary one so a cell can put the directory in a state the checkout's own
    `docs/games/` must never be in."""
    if state == "green_file":
        # The real corpus, registered at import: a game the glob found loads.
        assert pyspiel.load_game("cardlang_kuhn_poker").num_players() == 2
        return
    if state == "diagnostic_file":
        _diagnostic_copy(tmp_path, stem)
        # What the corpus loop does with what the derivation hands it — the
        # derivation itself reads filenames and never opens a game, so the
        # check runs here or nowhere.
        [(short_name, filename)] = _derive_games(tmp_path).items()
        with pytest.raises(DiagnosticError):
            _register_all([(short_name, str(tmp_path / filename))])
        return
    if state == "directory_of_games":
        _green_copy(tmp_path, f"{stem}_a")
        _green_copy(tmp_path, f"{stem}_b")
        assert sorted(_derive_games(tmp_path)) == [
            f"cardlang_{stem}_a",
            f"cardlang_{stem}_b",
        ]
        return
    if state == "empty_directory":
        with pytest.raises(InstallationError, match="no .cardlang games found"):
            _derive_games(tmp_path)
        return
    assert state == "bad_stem_file", state
    _green_copy(tmp_path, "corpus(paren)")
    with pytest.raises(InstallationError, match="pyspiel cannot load"):
        _derive_games(tmp_path)


def _call_cell(state: str, stem: str, tmp_path: Path) -> None:
    if state == "green_file":
        path = _green_copy(tmp_path, stem)
        name = register_game_file(path)
        assert name == f"cardlang_{stem}"
        game = pyspiel.load_game(name)
        assert game.get_type().short_name == name
        # A step through the pyspiel State, not just a load: the tree a
        # path-registered game gets is the corpus tree or it is nothing.
        opening = game.new_initial_state()
        assert opening.is_chance_node()
        opening.apply_action(opening.chance_outcomes()[0][0])
        assert opening.legal_actions()
        return
    if state == "diagnostic_file":
        path = _diagnostic_copy(tmp_path, stem)
        with pytest.raises(DiagnosticError):
            register_game_file(path)
        return
    if state == "markdown_with_block":
        path = _markdown_copy(tmp_path, stem, with_block=True)
        assert register_game_file(path) == f"cardlang_{stem}"
        assert pyspiel.load_game(f"cardlang_{stem}").num_players() == 2
        return
    if state == "markdown_without_block":
        path = _markdown_copy(tmp_path, stem, with_block=False)
        with pytest.raises(DiagnosticError, match="no fenced code block"):
            register_game_file(path)
        return
    if state == "missing":
        with pytest.raises(GameRegistrationError, match="no such file"):
            register_game_file(tmp_path / f"{stem}.cardlang")
        return
    if state == "directory_of_games":
        _green_copy(tmp_path, stem)
        with pytest.raises(GameRegistrationError, match="not a file"):
            register_game_file(tmp_path)
        return
    if state == "empty_directory":
        with pytest.raises(GameRegistrationError, match="not a file"):
            register_game_file(tmp_path)
        return
    if state == "empty_entry":
        with pytest.raises(GameRegistrationError, match="not a file"):
            register_game_file("")
        return
    assert state == "bad_stem_file", state
    # A stem unique to this cell, and a match on wording the collision refusal
    # does not share: both name the short name, so a matcher on that phrase
    # alone would read a collision as this refusal — and would, once a
    # neighbouring cell had registered the same stem.
    path = _green_copy(tmp_path, "call(paren)")
    with pytest.raises(GameRegistrationError, match="pyspiel cannot load"):
        register_game_file(path)


def _environment_cell(
    state: str, stem: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if state == "green_file":
        path = _green_copy(tmp_path, stem)
        _env_registration(monkeypatch, str(path))
        assert pyspiel.load_game(f"cardlang_{stem}").num_players() == 2
        return
    if state == "diagnostic_file":
        path = _diagnostic_copy(tmp_path, stem)
        with pytest.raises(DiagnosticError):
            _env_registration(monkeypatch, str(path))
        return
    if state == "markdown_with_block":
        path = _markdown_copy(tmp_path, stem, with_block=True)
        _env_registration(monkeypatch, str(path))
        assert pyspiel.load_game(f"cardlang_{stem}").num_players() == 2
        return
    if state == "markdown_without_block":
        path = _markdown_copy(tmp_path, stem, with_block=False)
        with pytest.raises(DiagnosticError, match="no fenced code block"):
            _env_registration(monkeypatch, str(path))
        return
    if state == "missing":
        with pytest.raises(GameRegistrationError, match="neither a file nor a directory"):
            _env_registration(monkeypatch, str(tmp_path / f"{stem}.cardlang"))
        return
    if state == "directory_of_games":
        _green_copy(tmp_path, f"{stem}_a")
        _green_copy(tmp_path, f"{stem}_b")
        _env_registration(monkeypatch, str(tmp_path))
        assert pyspiel.load_game(f"cardlang_{stem}_a").num_players() == 2
        assert pyspiel.load_game(f"cardlang_{stem}_b").num_players() == 2
        return
    if state == "empty_directory":
        tmp_path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(GameRegistrationError, match="holds no .cardlang games"):
            _env_registration(monkeypatch, str(tmp_path))
        return
    if state == "empty_entry":
        path = _green_copy(tmp_path, stem)
        with pytest.raises(GameRegistrationError, match="empty entry"):
            _env_registration(monkeypatch, f"{path}{os.pathsep}{os.pathsep}{path}")
        return
    assert state == "bad_stem_file", state
    _green_copy(tmp_path, "env(paren)")
    with pytest.raises(GameRegistrationError, match="pyspiel cannot load"):
        _env_registration(monkeypatch, str(tmp_path / "env(paren).cardlang"))


# ---------------------------------------------------------------------------
# Grid 2 — source x name state, the file held green.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("source", "state"), sorted(_NAME_EXPECTED))
def test_name_state_cell(
    source: str, state: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _NAME_EXPECTED[(source, state)]
    if expected == _INEXPRESSIBLE:
        pytest.skip(f"{source} cannot reach name state {state}: see the authored column")
    stem = f"probe_name_{source}_{state}"
    if source == "corpus":
        _corpus_name_cell(state, stem, tmp_path)
    elif source == "call":
        _call_name_cell(state, stem, tmp_path)
    else:
        _environment_name_cell(state, stem, tmp_path, monkeypatch)


def _corpus_name_cell(state: str, stem: str, tmp_path: Path) -> None:
    if state == "fresh":
        name = _short_name("kuhn-poker.cardlang")
        assert pyspiel.load_game(name).get_type().short_name == name
        return
    if state == "registered_outside":
        # The corpus loop over what the derivation hands it, on a temporary
        # directory — the same driving as `_corpus_cell`, because the state a
        # component builds before adapter import cannot be built against the
        # checkout's own `docs/games/` after it.
        long_name = _register_outside(f"cardlang_{stem}")
        _green_copy(tmp_path, stem)
        [(short_name, filename)] = _derive_games(tmp_path).items()
        with pytest.raises(GameRegistrationError, match="registered outside"):
            _register_all([(short_name, str(tmp_path / filename))])
        assert pyspiel.load_game(f"cardlang_{stem}").get_type().long_name == long_name
        return
    assert state == "corpus_name", state
    _green_copy(tmp_path, "a-b")
    _green_copy(tmp_path, "a_b")
    with pytest.raises(InstallationError, match="same OpenSpiel short name"):
        _derive_games(tmp_path)


def _call_name_cell(state: str, stem: str, tmp_path: Path) -> None:
    if state == "fresh":
        assert register_game_file(_green_copy(tmp_path, stem)) == f"cardlang_{stem}"
        return
    if state == "same_path":
        path = _green_copy(tmp_path, stem)
        (tmp_path / "sub").mkdir()
        first = register_game_file(path)
        # The same file, spelled differently. `Path` keeps a `..` component
        # rather than collapsing it, so the two strings genuinely differ and
        # the cell tests the resolved identity rather than string equality.
        detour = tmp_path / "sub" / ".." / f"{stem}.cardlang"
        assert str(detour) != str(path)
        assert register_game_file(detour) == first == f"cardlang_{stem}"
        return
    if state == "prior_call_other_path":
        register_game_file(_green_copy(tmp_path / "a", stem))
        other = _green_copy(tmp_path / "b", stem)
        with pytest.raises(GameRegistrationError) as info:
            register_game_file(other)
        message = str(info.value)
        assert str(tmp_path / "a" / f"{stem}.cardlang") in message
        assert str(other) in message
        return
    if state == "registered_outside":
        # Matched on wording neither collision refusal shares: both name the
        # short name and both say it is registered, so a matcher on either
        # phrase alone would read one as the other.
        long_name = _register_outside(f"cardlang_{stem}")
        mine = _green_copy(tmp_path, stem)
        with pytest.raises(GameRegistrationError, match="registered outside") as info:
            register_game_file(mine)
        assert str(mine) in str(info.value)
        assert pyspiel.load_game(f"cardlang_{stem}").get_type().long_name == long_name
        return
    assert state == "corpus_name", state
    mine = _green_copy(tmp_path, "hearts")
    with pytest.raises(GameRegistrationError) as info:
        register_game_file(mine)
    message = str(info.value)
    assert str(CORPUS / "hearts.cardlang") in message
    assert str(mine) in message


def _environment_name_cell(
    state: str, stem: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if state == "fresh":
        path = _green_copy(tmp_path, stem)
        _env_registration(monkeypatch, str(path))
        assert pyspiel.load_game(f"cardlang_{stem}").num_players() == 2
        return
    if state == "same_path":
        path = _green_copy(tmp_path, stem)
        _env_registration(monkeypatch, f"{path}{os.pathsep}{path}")
        assert pyspiel.load_game(f"cardlang_{stem}").num_players() == 2
        return
    if state == "prior_call_other_path":
        first = _green_copy(tmp_path / "a", stem)
        second = _green_copy(tmp_path / "b", stem)
        with pytest.raises(GameRegistrationError) as info:
            _env_registration(monkeypatch, f"{first}{os.pathsep}{second}")
        assert str(first) in str(info.value)
        assert str(second) in str(info.value)
        return
    if state == "registered_outside":
        long_name = _register_outside(f"cardlang_{stem}")
        mine = _green_copy(tmp_path, stem)
        with pytest.raises(GameRegistrationError, match="registered outside") as info:
            _env_registration(monkeypatch, str(mine))
        assert str(mine) in str(info.value)
        assert pyspiel.load_game(f"cardlang_{stem}").get_type().long_name == long_name
        return
    assert state == "corpus_name", state
    mine = _green_copy(tmp_path, "hearts")
    with pytest.raises(GameRegistrationError) as info:
        _env_registration(monkeypatch, str(mine))
    assert str(CORPUS / "hearts.cardlang") in str(info.value)
    assert str(mine) in str(info.value)


# ---------------------------------------------------------------------------
# Grid 3 — batch x the stage at which one of its files is refused.
# ---------------------------------------------------------------------------


def _assert_unregistered(*short_names: str) -> None:
    """Nothing took these names — read from pyspiel, not from bookkeeping.

    `_REGISTERED` is this module's own map and the commit pass is the only
    thing that writes it, so a cell reading it alone would be watching the
    bookkeeping rather than the registry the bookkeeping describes. The
    property is that the two agree, so both are read, and
    `pyspiel.registered_names` is the half with no inverse.
    """
    registered = set(pyspiel.registered_names())
    for short_name in short_names:
        assert short_name not in _REGISTERED, short_name
        assert short_name not in registered, short_name


@pytest.mark.parametrize(("batch", "stage"), sorted(_BATCH_EXPECTED))
def test_batch_atomicity_cell(
    batch: str, stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file refused at `stage` leaves its batch's earlier files unregistered.

    `pyspiel.register_game` is process-global and has no inverse, and the map
    that makes the collision refusal possible dies with the module when a
    refusal escapes adapter import. A batch that registered as it went would
    therefore leave names registered that no later run knows are taken — and
    the next registration under one of them would win silently, which is the
    refusal this surface exists to give.
    """
    expected = _BATCH_EXPECTED[(batch, stage)]
    if expected == _INEXPRESSIBLE:
        pytest.skip(f"{batch} cannot strand a file at {stage}: see the authored column")
    stem = f"probe_batch_{batch}_{stage}"
    if batch == "corpus_glob":
        _corpus_batch_cell(stem, tmp_path)
    elif batch == "environment_directory":
        _environment_directory_batch_cell(stage, stem, tmp_path, monkeypatch)
    else:
        _environment_entries_batch_cell(stage, stem, tmp_path, monkeypatch)


def _corpus_batch_cell(stem: str, tmp_path: Path) -> None:
    """The corpus loop over what `_derive_games` hands it, on a temporary
    directory — the checkout's own `docs/games/` must never hold a game the
    checker refuses, so the state this cell needs cannot be built there."""
    _green_copy(tmp_path, f"{stem}_a")
    _diagnostic_copy(tmp_path, f"{stem}_b")
    derived = _derive_games(tmp_path)
    assert list(derived) == [f"cardlang_{stem}_a", f"cardlang_{stem}_b"]
    with pytest.raises(DiagnosticError):
        _register_all((name, str(tmp_path / f)) for name, f in derived.items())
    _assert_unregistered(f"cardlang_{stem}_a")


def _environment_directory_batch_cell(
    stage: str, stem: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One directory entry, whose glob holds a green game and then a refused
    one. Filenames are chosen so the glob's sort puts the green game first —
    the cell has nothing to say if the refusal comes before anything to
    strand."""
    _green_copy(tmp_path, f"{stem}_a")
    protected = [f"cardlang_{stem}_a"]
    raises: type[Exception] = GameRegistrationError
    match: str | None
    if stage == "stem":
        _green_copy(tmp_path, f"{stem}_zz(paren)")
        match = "pyspiel cannot load"
    elif stage == "checker":
        _diagnostic_copy(tmp_path, f"{stem}_b")
        raises, match = DiagnosticError, None
    else:
        assert stage == "collision", stage
        # One stem in two spellings inside one directory: `-` sorts before
        # `_`, so the pair is planned after the green game above and the
        # second of them is what the glob refuses.
        _green_copy(tmp_path, f"{stem}-x")
        _green_copy(tmp_path, f"{stem}_x")
        protected.append(f"cardlang_{stem}_x")
        match = "claim the OpenSpiel short name"
    with pytest.raises(raises, match=match):
        _env_registration(monkeypatch, str(tmp_path))
    _assert_unregistered(*protected)


def _environment_entries_batch_cell(
    stage: str, stem: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two entries: a green file, then one refused at `stage`."""
    first = _green_copy(tmp_path / "first", stem)
    raises: type[Exception] = GameRegistrationError
    match: str | None
    if stage == "entry_shape":
        second = str(tmp_path / "nowhere.cardlang")
        match = "neither a file nor a directory"
    elif stage == "stem":
        second = str(_green_copy(tmp_path / "second", f"{stem}(paren)"))
        match = "pyspiel cannot load"
    elif stage == "checker":
        second = str(_diagnostic_copy(tmp_path / "second", f"{stem}_refused"))
        raises, match = DiagnosticError, None
    else:
        assert stage == "collision", stage
        second = str(_green_copy(tmp_path / "second", stem))
        match = "claim the OpenSpiel short name"
    with pytest.raises(raises, match=match):
        _env_registration(monkeypatch, f"{first}{os.pathsep}{second}")
    _assert_unregistered(f"cardlang_{stem}")


# ---------------------------------------------------------------------------
# The factorization, and the variable's own value classes.
# ---------------------------------------------------------------------------


def test_a_refused_file_leaves_its_short_name_free() -> None:
    """What lets the two grids factor: a name binds only after the check passes.

    Without this cell the name axis would be crossed with the green file state
    alone by convenience rather than by fact, and a refusal that registered the
    name anyway would sit in the gap between the two grids.
    """
    directory = Path(tempfile.mkdtemp())
    stem = "probe_factorization"
    bad = _diagnostic_copy(directory / "bad", stem)
    with pytest.raises(DiagnosticError):
        register_game_file(bad)
    good = _green_copy(directory / "good", stem)
    assert register_game_file(good) == f"cardlang_{stem}"


def test_the_corpus_directory_offered_again_registers_nothing_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CARDLANG_GAMES=docs/games` is a no-op, not thirty-one collisions.

    The first entry a designer reaches for, and the reason identity is the
    resolved path rather than the string: every file in that directory is
    already registered from the same file, so each offer is the same
    registration rather than a rival for the name.
    """
    before = dict(_REGISTERED)
    _env_registration(monkeypatch, str(CORPUS))
    assert _REGISTERED == before


@pytest.mark.parametrize("value", [None, "", "   "], ids=["unset", "empty", "whitespace"])
def test_the_variable_names_no_entry(
    value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every value `CARDLANG_GAMES` can carry that names no entry at all.

    An unset variable and one set to nothing mean the same thing: splitting an
    empty value leaves one empty entry, which would refuse a variable the
    caller effectively did not set.
    """
    before = dict(_REGISTERED)
    _env_registration(monkeypatch, value)
    assert _REGISTERED == before


_IMPORT_PROBE = """
import cardlang.openspiel.game as g
print("LOADED", " ".join(sorted(n for n in g._REGISTERED if n.startswith("cardlang_probe"))))
"""


def test_the_variable_is_read_at_adapter_import(tmp_path: Path) -> None:
    """Importing the adapter is what runs the environment source.

    One of the two cells that need a fresh interpreter, and the reason the
    others do not: every refusal above is a property of `_register_env_var`,
    which this process can call, while "adapter import calls it" is a property
    of the import and nothing else. `pyspiel.register_game` has no inverse, so
    re-importing here would re-register the corpus against a registry that
    cannot be rolled back.
    """
    path = _green_copy(tmp_path, "probe_import_time")
    env = dict(os.environ)
    env[GAMES_ENV_VAR] = str(path)
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(  # noqa: PLW1510 -- the returncode assert below carries proc.stderr
        [sys.executable, "-c", _IMPORT_PROBE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "cardlang_probe_import_time" in proc.stdout


_REIMPORT_PROBE = """
import os
os.environ["CARDLANG_GAMES"] = "/no/such/cardlang/entry.cardlang"
try:
    import cardlang.openspiel.game
except Exception as exc:
    print("FIRST", type(exc).__name__)
del os.environ["CARDLANG_GAMES"]
try:
    import cardlang.openspiel.game
    print("SECOND registered")
except Exception as exc:
    print("SECOND", type(exc).__name__, exc)
"""


def test_a_refused_import_leaves_the_corpus_names_held() -> None:
    """A corrected `CARDLANG_GAMES` is a fresh process, and says so.

    The other cell needing a fresh interpreter, for the state it needs rather
    than the property: a refusal escaping adapter import takes the map with it
    while the corpus games it already committed stay in pyspiel, and no
    process that imported the adapter successfully can be put back into that
    state. Re-importing there is the one place the corpus source meets names
    it holds no file for, so the refusal it earns is the same one a component
    registering outside earns — loud, rather than a second game quietly
    registered under each corpus name and answering `pyspiel.load_game`.

    red under: read `taken` from `_REGISTERED` alone. The second import then
    reports `SECOND registered`, having replaced all of them.
    """
    env = dict(os.environ)
    env.pop(GAMES_ENV_VAR, None)
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(  # noqa: PLW1510 -- the returncode assert below carries proc.stderr
        [sys.executable, "-c", _REIMPORT_PROBE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FIRST GameRegistrationError" in proc.stdout, proc.stdout
    assert "SECOND GameRegistrationError" in proc.stdout, proc.stdout
    assert "registered outside this module" in proc.stdout, proc.stdout


# ---------------------------------------------------------------------------
# Misuse probes, and the one-site pin.
# ---------------------------------------------------------------------------


def test_one_registration_site_in_the_package() -> None:
    """`pyspiel.register_game` is called from exactly one place in `cardlang/`.

    The contract's "one path, one classification read" is this, made
    structural: a second call site would give the collision rule and the
    chance-mode read a second definition, and neither would be visible in a
    green suite. The experiment rigs under `experiments/` register their own
    miniatures and are deliberately outside this scrape — they are not the
    adapter.

    red under: add a second `pyspiel.register_game(...)` call anywhere under
    `cardlang/`. Verified by doing so.
    """
    root = pathlib.Path(str(cardlang.__file__)).parent
    sites: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "register_game"
            ):
                sites.append(f"{path.relative_to(root.parent)}:{node.lineno}")
    assert len(sites) == 1, f"expected one registration site, found: {sites}"


def test_a_registered_path_game_is_not_in_the_corpus_registry() -> None:
    """`GAMES` stays the corpus, so every table keyed on it stays corpus-shaped.

    The readiness proofs, the projection sweep and the chance-free pin all
    parametrize over `GAMES`; a path-registered game appearing there would
    demand a proof module its author cannot write (issue #25).

    red under: have `register_game_file` write its result into
    `registry.GAMES` alongside `_REGISTERED`. Verified by doing so.
    """
    from cardlang.openspiel.registry import GAMES

    path = _green_copy(Path(tempfile.mkdtemp()), "probe_not_in_registry")
    name = register_game_file(path)
    assert name not in GAMES
    assert sorted(GAMES.values()) == sorted(p.name for p in CORPUS.glob("*.cardlang"))
