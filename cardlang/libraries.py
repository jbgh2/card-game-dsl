"""Family libraries: the import tier between game-local and stdlib.

A library is a file of the definition forms a game already holds — move_types,
rules, functions, procedures, types, defines — plus a ``requires`` block naming
the state its including game must declare. A game names one with ``uses
<library>`` and resolution is flat and two-level: game, then the named
libraries, then the stdlib. See decisions.md "Family libraries".

This module owns only *finding and parsing* library files. The splice, the
collision walls, and the requires check live in ``resolve`` — they are name
resolution, and that is the pass whose contract owns names.

Where library files live
------------------------
``docs/libraries/<name>.cardlang``, beside the corpus in ``docs/games/`` and for
the same reason: a family library is maintained with the corpus, not with the
language (the stdlib is the part maintained with the language, which is exactly
the boundary design-notes/primitive-sidecars.md exists to defend). The lookup is
repo-relative and glob-derived, mirroring ``openspiel/registry.py`` — and it
inherits that module's packaging limitation unchanged: a wheel install ships
``cardlang*`` but not ``docs/``, so this directory would be absent. That is the
one already-recorded issue in roadmap.md, "Packaging the corpus for
distribution"; it is a project-level decision (ship both corpus and libraries as
package data, load via ``importlib.resources``) and is deliberately NOT patched
here, because patching one loader while ``docs/games/`` stays checkout-relative
would leave the two inconsistent.
"""

from __future__ import annotations

from functools import cache, lru_cache
from pathlib import Path

from cardlang.ast import nodes as n
from cardlang.parse import parse_library

_LIBRARIES_DIR = Path(__file__).resolve().parent.parent / "docs" / "libraries"


def _libraries_dir() -> Path:
    if not _LIBRARIES_DIR.is_dir():
        # Loud rather than "zero libraries available", which would degrade every
        # `uses` line into the unknown-library diagnostic and read as an author
        # typo instead of a missing checkout (registry.py takes the same line).
        raise RuntimeError(
            f"family-library directory not found: {_LIBRARIES_DIR}. Libraries "
            f"load from the checkout (see this module's docstring on packaging)."
        )
    return _LIBRARIES_DIR


@lru_cache(maxsize=1)
def library_names() -> frozenset[str]:
    """Every family library available to a `uses` line, glob-derived from the
    directory so adding a library is adding a file — never also editing a
    hand-maintained list that could drift out of step with it."""
    return frozenset(p.stem for p in _libraries_dir().glob("*.cardlang"))


@cache
def load_library(name: str) -> n.Library:
    """Parse the named family library. Callers check `name in library_names()`
    first: an unknown library is an author error carrying the game's `uses`
    span, which this module has no access to, so reaching here with an
    unregistered name is a caller bug and raises rather than diagnosing."""
    if name not in library_names():
        raise KeyError(f"no family library named '{name}'")
    path = _libraries_dir() / f"{name}.cardlang"
    source_name = f"docs/libraries/{name}.cardlang"
    library = parse_library(path.read_text(), source_name)
    if library.name != name:
        # The file name is what `uses` spells, so a mismatch would mean the
        # declared name is decorative — the accepted-but-ignored shape.
        raise ValueError(
            f"{source_name} declares `library {library.name}` but is named "
            f"'{name}.cardlang' — a library's declared name is what `uses` "
            f"spells, so the two must agree"
        )
    return library
