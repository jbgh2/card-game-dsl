"""The standard library's [[rule]]s: `library stdlib`, parsed and checked once.

The bodies live in ``rules.cardlang`` (real DSL, so the library and the games
speak one language), as a `library` file like any family library's: one parse
entry, one library-alone law. Two things set it apart, both pinned here. No
`uses` line names it — a game activates its rules by name in `active_rules:`
and `resolve._instantiate_rules` splices each one where it is named — so its
declared name is pinned against `STDLIB_NAME` rather than against a file a
`uses` line spells, and its contract must be empty: a `requires` row would have
no `uses` line to be reported at. Defining a rule under a library name is
rejected (the local copy would drift from the shared body silently).
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag
from cardlang.parse import parse_library

#: The standard library's declared name, and the one name a `uses` line may
#: never spell.
STDLIB_NAME = "stdlib"
STDLIB_SOURCE_NAME = "cardlang/stdlib/rules.cardlang"


def load_stdlib(text: str, source_name: str) -> n.Library:
    """Parse and check the standard library's text. A failure here is a
    defect in the language itself, raised at load and located in the stdlib
    file."""
    library = parse_library(text, source_name)
    if library.name != STDLIB_NAME:
        raise ValueError(
            f"{source_name} declares `library {library.name}`, but the standard "
            f"library is `library {STDLIB_NAME}` — no `uses` line spells it, so "
            f"its name is pinned here instead"
        )
    if library.requires:
        raise ValueError(
            f"{source_name} declares a `requires` contract, but the standard "
            f"library is switched on by `active_rules:` alone, with no `uses` "
            f"line to report an unmet contract at — its rules may read only "
            f"what every game has"
        )
    # Deferred: `resolve` imports this module for the rule index.
    from cardlang.attribution import raise_where_written
    from cardlang.resolve import check_library_alone

    bag = DiagnosticBag()
    check_library_alone(library, bag)
    raise_where_written(bag)
    return library


@lru_cache(maxsize=1)
def stdlib_library() -> n.Library:
    """`library stdlib`, loaded once."""
    text = resources.files("cardlang.stdlib").joinpath("rules.cardlang").read_text()
    return load_stdlib(text, STDLIB_SOURCE_NAME)


@lru_cache(maxsize=1)
def stdlib_rules() -> dict[str, n.RuleDef]:
    """Rule name -> parsed definition (templates keep their ``params``)."""
    return {r.name: r for r in stdlib_library().rules}
