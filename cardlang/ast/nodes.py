"""AST node definitions for the Card Game DSL.

Nodes are frozen dataclasses forming a closed :data:`Node` union. Every
consumer dispatches with structural ``match`` ending in
``typing.assert_never``; under ``mypy --strict`` that makes adding a node
without handling it everywhere a type error rather than a silent gap
(docs/building.md, "Typed-AST discipline").

This is the walking-skeleton subset — game header, players, deck, and zone
declarations. It grows one construct at a time as the grammar does.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardlang.diagnostics import Span


@dataclass(frozen=True, slots=True)
class TypeArg:
    """One argument inside ``<>``.

    May be an ordinary type name (``Owner``) or a value in type-parameter
    position (``player`` in ``Hand<player>``) — the ``<>`` value-parameter
    deviation noted in principles.md. The parser cannot tell them apart by
    shape; ``resolve``/``typecheck`` decide using the referenced declaration.
    """

    name: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class TypeRef:
    """A reference to a (possibly parameterized) type, e.g. ``Hand<player>``."""

    name: str
    args: tuple[TypeArg, ...] = ()
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class PlayersSpec:
    """``players: 4`` (fixed) or ``players: 2..8`` (range)."""

    low: int
    high: int | None = None  # None means a fixed count equal to ``low``
    span: Span | None = None

    @property
    def is_range(self) -> bool:
        return self.high is not None


@dataclass(frozen=True, slots=True)
class ZoneDecl:
    """A zone declaration, optionally indexed by a role, e.g. ``hand[player]``."""

    name: str
    index: str | None  # the index role (``player``) or None for a singleton zone
    type_ref: TypeRef
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Game:
    """A whole game: the top-level AST node."""

    name: str
    players: PlayersSpec
    deck: str  # a deck name, e.g. ``standard52`` (custom decks land later)
    zones: tuple[ZoneDecl, ...]
    span: Span | None = None


# The closed union. Consumers should match exhaustively over this.
Node = Game | ZoneDecl | TypeRef | TypeArg | PlayersSpec
