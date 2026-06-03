"""Parse stage: Lark + Transformer -> typed AST.

The grammar is read at runtime from ``grammar/cardlang.lark`` on the Earley
parser (so ambiguity surfaces as an error during development). A
:class:`_Builder` transformer shapes the parse tree into the frozen
dataclasses in :mod:`cardlang.ast.nodes`, attaching a :class:`Span` to every
node. Positions reported by Lark are 1-based within the DSL text; a
``line_offset`` lifts them back to the original Markdown file.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput
from lark.tree import Meta
from lark.visitors import Transformer, v_args

from cardlang.ast.nodes import Game, PlayersSpec, TypeArg, TypeRef, ZoneDecl
from cardlang.diagnostics import Diagnostic, DiagnosticError, Severity, Span
from cardlang.extract import FencedBlock


@dataclass(frozen=True, slots=True)
class _Deck:
    """Internal marker so the deck name is distinguishable from other strings
    while scanning a game's items by type."""

    name: str


@lru_cache(maxsize=1)
def _parser() -> Lark:
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    return Lark(
        grammar,
        parser="earley",
        propagate_positions=True,
        maybe_placeholders=True,
    )


@v_args(meta=True)
class _Builder(Transformer[Token, Game]):
    """Turns the Lark tree into AST nodes, threading source location through."""

    def __init__(self, source_name: str, line_offset: int) -> None:
        super().__init__()
        self._source_name = source_name
        self._line_offset = line_offset

    def _span(self, meta: Meta) -> Span:
        return Span(
            source_name=self._source_name,
            start=meta.start_pos,
            end=meta.end_pos,
            line=meta.line + self._line_offset,
            column=meta.column,
        )

    # --- leaves and small nodes ---

    def players_fixed(self, meta: Meta, children: list[Token]) -> PlayersSpec:
        (count,) = children
        return PlayersSpec(low=int(count), high=None, span=self._span(meta))

    def players_range(self, meta: Meta, children: list[Token]) -> PlayersSpec:
        low, high = children
        return PlayersSpec(low=int(low), high=int(high), span=self._span(meta))

    def players(self, meta: Meta, children: list[PlayersSpec]) -> PlayersSpec:
        (spec,) = children
        return spec

    def cards(self, meta: Meta, children: list[Token]) -> _Deck:
        (name,) = children
        return _Deck(str(name))

    def index(self, meta: Meta, children: list[Token]) -> str:
        (name,) = children
        return str(name)

    def type_arg(self, meta: Meta, children: list[Token]) -> TypeArg:
        (name,) = children
        return TypeArg(name=str(name), span=self._span(meta))

    def type_args(self, meta: Meta, children: list[TypeArg]) -> tuple[TypeArg, ...]:
        return tuple(children)

    def type_ref(
        self, meta: Meta, children: list[Token | tuple[TypeArg, ...]]
    ) -> TypeRef:
        name = children[0]
        args: tuple[TypeArg, ...] = ()
        if len(children) > 1 and children[1] is not None:
            assert isinstance(children[1], tuple)
            args = children[1]
        return TypeRef(name=str(name), args=args, span=self._span(meta))

    def zone_decl(
        self, meta: Meta, children: list[Token | str | TypeRef | None]
    ) -> ZoneDecl:
        name = children[0]
        index = children[1]  # str from `index`, or None via maybe_placeholders
        type_ref = children[2]
        assert isinstance(type_ref, TypeRef)
        assert index is None or isinstance(index, str)
        return ZoneDecl(
            name=str(name),
            index=index,
            type_ref=type_ref,
            span=self._span(meta),
        )

    def zones(self, meta: Meta, children: list[ZoneDecl]) -> tuple[ZoneDecl, ...]:
        return tuple(children)

    def game(self, meta: Meta, children: list[object]) -> Game:
        # The grammar admits game items in any order; locate the ones the
        # typed AST models. Items it does not yet model (direction, ranking,
        # state, phases, winner) are a deliberate not-implemented error — the
        # typed pipeline grows to cover them construct by construct, rather
        # than silently dropping them.
        name = str(children[0])
        players: PlayersSpec | None = None
        deck: _Deck | None = None
        zones: tuple[ZoneDecl, ...] | None = None
        for item in children[1:]:
            if isinstance(item, PlayersSpec):
                players = item
            elif isinstance(item, _Deck):
                deck = item
            elif isinstance(item, tuple):
                zones = item
            else:
                raise NotImplementedError(
                    f"game item not yet modeled by the typed AST: {item!r}"
                )
        assert players is not None and deck is not None and zones is not None
        return Game(
            name=name,
            players=players,
            deck=deck.name,
            zones=zones,
            span=self._span(meta),
        )

    def start(self, meta: Meta, children: list[Game]) -> Game:
        (game,) = children
        return game


def parse_to_tree(text: str, source_name: str, line_offset: int = 0) -> Tree[Token]:
    """Parse DSL ``text`` to a raw Lark tree, raising a span-located diagnostic
    on a syntax error.

    This is the grammar-acceptance entry point: it proves the grammar accepts a
    source without committing to a typed AST for every construct. The typed
    pipeline (:func:`parse_text`) grows to cover constructs one at a time.
    """
    try:
        tree = _parser().parse(text)
    except UnexpectedInput as exc:
        line = getattr(exc, "line", 1) + line_offset
        column = getattr(exc, "column", 1)
        span = Span(source_name, 0, 0, line, column)
        raise DiagnosticError(
            Diagnostic(Severity.ERROR, f"syntax error: {exc!s}".splitlines()[0], span)
        ) from exc
    assert isinstance(tree, Tree)
    return tree


def parse_text(text: str, source_name: str, line_offset: int = 0) -> Game:
    """Parse DSL ``text`` into a :class:`Game` AST.

    ``line_offset`` is added to Lark's 1-based line numbers so spans point at
    the original file (a Markdown block starting at file line N uses
    ``line_offset = N - 1``).
    """
    tree = parse_to_tree(text, source_name, line_offset)
    return _Builder(source_name, line_offset).transform(tree)


def parse_block(block: FencedBlock) -> Game:
    """Parse a :class:`FencedBlock`, mapping spans back to its file."""
    return parse_text(block.text, block.source_name, line_offset=block.start_line - 1)
