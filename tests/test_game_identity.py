"""A game's identity: what a file replayed against a game proves it belongs to.

property:        `pipeline.game_identity` names a checked game by its program, not
                 by the bytes of its file: a copy reformatted and moved keeps the
                 identity, and an edit that reaches the checked program moves it,
                 an edit to a library the game uses included. Every registered
                 game has an identity of its own.
domain:          The registry, for distinctness and shape. The edits: `_EDITS`, one
                 per place a change to a game can come from (a declared number in
                 the file, the game's name, a statement of a phase, a definition
                 spliced from a `uses` library, the IR's own version), each
                 against the unedited game as its control, beside the reformatted
                 and moved copy that must not move.
registry:        games: `cardlang.openspiel.registry.GAMES`; the checked program:
                 `cardlang.ir.emit`; libraries: `cardlang.libraries`.
does not prove:  That every edit which changes play moves the identity. The
                 identity is taken from the IR, and a fact of the checked tree the
                 emitter leaves out of the IR is invisible to it; the engine's own
                 code, a Primitive's implementation included, is outside it
                 altogether.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from cardlang import ir, libraries, pipeline
from cardlang.openspiel.registry import GAMES
from cardlang.pipeline import check_source, game_identity

REPO = Path(__file__).parent.parent
GAMES_DIR = REPO / "docs" / "games"
LIBRARIES_DIR = REPO / "docs" / "libraries"


@pytest.fixture
def fresh_caches() -> Iterator[None]:
    """The check memo is keyed on the parsed tree and a library is loaded once,
    so a probe that edits either must start and end with both emptied."""

    def clear() -> None:
        libraries.library_names.cache_clear()
        libraries.load_library.cache_clear()
        pipeline._check.cache_clear()

    clear()
    yield
    clear()


def test_every_registered_game_has_an_identity_of_its_own() -> None:
    identities = {
        short_name: game_identity(check_source(GAMES_DIR / file_name))
        for short_name, file_name in GAMES.items()
    }
    for short_name, identity in identities.items():
        assert re.fullmatch(r"[0-9a-f]{64}", identity), f"{short_name}: {identity!r}"
    assert len(set(identities.values())) == len(identities)


def test_a_reformatted_copy_somewhere_else_keeps_its_identity(tmp_path: Path) -> None:
    """The known-positive control for every edit below."""
    source = (GAMES_DIR / "hearts.cardlang").read_text()
    lines = source.splitlines()
    reformatted = "\n".join(["// a copy kept elsewhere", "", *lines[:5], "", "", *lines[5:]]) + "\n"
    copy = tmp_path / "renamed-copy.cardlang"
    copy.write_text(reformatted)
    assert game_identity(check_source(copy)) == game_identity(check_source(GAMES_DIR / "hearts.cardlang"))


def _edit_file(game_file: str, old: str, new: str) -> Callable[[Path, pytest.MonkeyPatch], Path]:
    def edit(tmp_path: Path, _monkeypatch: pytest.MonkeyPatch) -> Path:
        source = (GAMES_DIR / game_file).read_text()
        assert source.count(old) == 1, f"the edit's anchor must occur once in {game_file}"
        edited = tmp_path / game_file
        edited.write_text(source.replace(old, new))
        return edited

    return edit


def _edit_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    copied = tmp_path / "libraries"
    shutil.copytree(LIBRARIES_DIR, copied)
    library = copied / "poker_betting.cardlang"
    old = "not folded[p] and stack[p] > 0"
    source = library.read_text()
    assert source.count(old) == 1
    library.write_text(source.replace(old, "not folded[p] and stack[p] > 1"))
    monkeypatch.setattr(libraries, "_libraries_dir", lambda: copied)
    libraries.library_names.cache_clear()
    libraries.load_library.cache_clear()
    pipeline._check.cache_clear()
    return GAMES_DIR / "five-card-draw.cardlang"


def _bump_ir_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ir, "IR_VERSION", ir.IR_VERSION + 1)
    return GAMES_DIR / "hearts.cardlang"


# Each edit, and the unedited game it is measured against.
_EDITS: dict[str, tuple[str, Callable[[Path, pytest.MonkeyPatch], Path]]] = {
    "a declared number": ("hearts.cardlang", _edit_file("hearts.cardlang", "max_length: 5000", "max_length: 5001")),
    "the game's name": ("hearts.cardlang", _edit_file("hearts.cardlang", "game Hearts {", "game HeartsCopy {")),
    "a statement of a phase": (
        "hearts.cardlang",
        _edit_file("hearts.cardlang", "elif card is Q of spades     then 13", "elif card is Q of spades     then 12"),
    ),
    "a definition a library splices in": ("five-card-draw.cardlang", _edit_library),
    "the IR's own version": ("hearts.cardlang", _bump_ir_version),
}


@pytest.mark.parametrize("edit", sorted(_EDITS))
def test_an_edit_that_reaches_the_checked_program_moves_the_identity(
    edit: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_caches: None
) -> None:
    game_file, apply = _EDITS[edit]
    before = game_identity(check_source(GAMES_DIR / game_file))
    after = game_identity(check_source(apply(tmp_path, monkeypatch)))
    assert after != before
