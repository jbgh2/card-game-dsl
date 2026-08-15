"""Standard-library [[rule]]s, as parsed definitions.

The bodies live in ``rules.cardlang`` (real DSL, so the library and the games
speak one language); this module parses them once and exposes the registry the
resolver [[splice]]s from. A game activates a library rule by name in
``active_rules:`` without defining it; defining a rule under a library name is
rejected (the local copy would drift from the shared body silently).
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from cardlang.ast import nodes as n
from cardlang.parse import parse_stdlib_rules

_SOURCE_NAME = "cardlang/stdlib/rules.cardlang"


@lru_cache(maxsize=1)
def stdlib_rules() -> dict[str, n.RuleDef]:
    """Rule name -> parsed definition (templates keep their ``params``)."""
    text = resources.files("cardlang.stdlib").joinpath("rules.cardlang").read_text()
    rules = parse_stdlib_rules(text, _SOURCE_NAME)
    return {r.name: r for r in rules}
