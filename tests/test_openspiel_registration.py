"""Registering a game file with OpenSpiel, from the corpus and from a path.

property:        Every way a `.cardlang` file reaches `pyspiel.register_game`
                 goes through one function, so a file registered by path is
                 classified, checked and named exactly as a corpus game is;
                 and every state a path or an entry can be in yields either a
                 registration or a refusal naming what is wrong — never a
                 short name `pyspiel.load_game` cannot reach, and never a
                 silent replacement of a game already registered.
domain:          Two crossings, each total over its axes. The first crosses
                 the registration SOURCE with the state of the file or entry
                 it offers; the second crosses the same sources with the state
                 of the short name that file derives. They factor because a
                 name binds only after the check passes — a file the checker
                 refuses never reaches `pyspiel.register_game`, so it cannot
                 take a name; `test_a_refused_file_leaves_its_short_name_free`
                 is the cell that holds the factorization, and without it the
                 halving would be a convenience rather than a fact.

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
                 installed; the environment cells additionally need a
                 subprocess, because `CARDLANG_GAMES` is read once at adapter
                 import and `pyspiel.register_game` has no inverse.
registry:        sources and file/entry states: `_SOURCES` and `_FILE_STATES`
                 below, crossed into `_FILE_EXPECTED`; name states:
                 `_NAME_STATES`, crossed into `_NAME_EXPECTED`; the entry
                 vocabulary: `cardlang.openspiel.game.ENTRY_KINDS`, which the
                 env dispatch reads; the short-name rule and its character set:
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
                 refused whether or not OpenSpiel would have taken them.
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
    _register,
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
# `hearts.cardlang` against the corpus one.
_NAME_STATES: tuple[str, ...] = (
    "fresh",
    "same_path",
    "prior_call_other_path",
    "corpus_name",
)

# The outcome vocabulary. `inexpressible` is surface totality's third state:
# the source cannot put a file in that state at all.
_REGISTERS = "registers"
_INEXPRESSIBLE = "inexpressible"

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
    ("call", "fresh"): _REGISTERS,
    ("call", "same_path"): "idempotent",
    ("call", "prior_call_other_path"): "GameRegistrationError",
    ("call", "corpus_name"): "GameRegistrationError",
    ("environment", "fresh"): _REGISTERS,
    ("environment", "same_path"): "idempotent",
    ("environment", "prior_call_other_path"): "GameRegistrationError",
    ("environment", "corpus_name"): "GameRegistrationError",
}


def test_every_file_cell_is_authored() -> None:
    """The derived cross and the authored column name the same cells."""
    derived = {(s, f) for s in _SOURCES for f in _FILE_STATES}
    assert derived == set(_FILE_EXPECTED)


def test_every_name_cell_is_authored() -> None:
    derived = {(s, n) for s in _SOURCES for n in _NAME_STATES}
    assert derived == set(_NAME_EXPECTED)


def test_the_entry_vocabulary_is_what_the_dispatch_reads() -> None:
    """`ENTRY_KINDS` is the env dispatch's own vocabulary, and the file-state
    axis crosses every member of it: a kind the dispatch gains without a cell
    here fails this rather than riding unexercised."""
    assert set(ENTRY_KINDS) == {"file", "directory", "missing", "empty"}


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
            _register(short_name, str(tmp_path / filename))
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
    assert state == "corpus_name", state
    mine = _green_copy(tmp_path, "hearts")
    with pytest.raises(GameRegistrationError) as info:
        _env_registration(monkeypatch, str(mine))
    assert str(CORPUS / "hearts.cardlang") in str(info.value)
    assert str(mine) in str(info.value)


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

    The one cell that needs a fresh interpreter, and the reason the others do
    not: every refusal above is a property of `_register_env_var`, which this
    process can call, while "adapter import calls it" is a property of the
    import and nothing else. `pyspiel.register_game` has no inverse, so
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
