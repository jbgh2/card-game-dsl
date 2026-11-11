"""Library crossings: the definitions a name reaches, and the route a refusal carries."""

from __future__ import annotations

from dataclasses import dataclass
from cardlang.ast import nodes as n
from cardlang.attribution import cite_named, cite_origin
from cardlang.diagnostics import LibraryCitation, Route, Said, Span
from cardlang.resolve.walk import _walk
from cardlang.resolve.slots import _NAMING_SLOTS_BY_TYPE, slot_namespace, slot_strings


def _definition_closure(
    roots: list[object], pools: dict[str, dict[str, object]]
) -> dict[tuple[str, str], tuple[object, tuple[str, str] | None]]:
    """The definitions reachable from `roots` by name, through the pools
    given, as a fixpoint: each reached definition's own body is walked in
    turn. Keyed by (namespace, name); the value is the definition and the key
    of the definition that first named it (None for a root). Which slots NAME
    a definition is read off `slot_namespace`, so an invoking construct added
    to `_REFERENCE_SLOTS` reaches every caller of this walk."""
    reached: dict[tuple[str, str], tuple[object, tuple[str, str] | None]] = {}
    frontier: list[tuple[object, tuple[str, str] | None]] = [(r, None) for r in roots]
    while frontier:
        root, via = frontier.pop()
        for node in _walk(root):
            for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
                namespace = slot_namespace(node, field_name)
                if namespace is None:
                    continue
                pool = pools.get(namespace)
                if pool is None:
                    continue
                for name in slot_strings(node, field_name):
                    key = (namespace, name)
                    target = pool.get(name)
                    if target is None or key in reached:
                        continue
                    reached[key] = (target, via)
                    frontier.append((target, key))
    return reached


@dataclass(frozen=True)
class _LibraryEntry:
    """Where a route from the game's text last entered a library's: the game
    text naming the library definition (a call, a `run`, an offer), that
    definition's origin, how many definitions deep the entry stands, and the
    definition's own text."""

    span: Span | None
    origin: n.LibraryOrigin
    depth: int
    name: str
    definition: Span | None = None

    @property
    def through(self) -> LibraryCitation:
        """The entered definition, in the game's author's words."""
        return cite_origin(self.origin, self.definition)


_DEFINITION_POOLS: dict[str, str] = {
    "function": "functions", "procedure": "procedures", "move_type": "move_types", "rule": "rules",
}


def _cite_in(game: n.Game, namespace: str, name: str, words: str) -> Said:
    """`words` naming `name` of `namespace`: a citation of the definition the
    game holds by that name, and the bare words where it holds none (a
    Primitive, a Builtin, an engine's own name)."""
    found = next((d for d in getattr(game, _DEFINITION_POOLS[namespace]) if d.name == name), None)
    return words if found is None else cite_named(found, words)


def _entry_route(kind: str, entry: _LibraryEntry, fallback: Span | None) -> Route:
    """The crossing `entry` names, of `kind`, at the game's text naming the
    library definition (`fallback` where no text spans it)."""
    return Route(kind, entry.span or fallback, entry.origin.library, entry.name)
