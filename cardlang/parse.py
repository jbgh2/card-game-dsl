"""Parse stage: Lark + Transformer -> typed AST.

The grammar is read at runtime from ``grammar/cardlang.lark`` on the Earley
parser (so ambiguity surfaces as an error during development). A
:class:`_Builder` transformer shapes the parse tree into the frozen
dataclasses in :mod:`cardlang.ast.nodes`, attaching a :class:`Span` to every
node. Positions reported by Lark are 1-based within the DSL text; a
``line_offset`` lifts them back to the original Markdown file.

A handful of private marker dataclasses (``_Deck``, ``_Direction``, …) carry
intermediate results whose Lark rule produces a value the parent rule must
pick out by type — they never escape this module.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      raw DSL text (Markdown extraction already applied).
Establishes:  a syntactically valid frozen AST; every node carries a
              :class:`Span`. No semantic claims — names carry no
              [[ref-kind]] yet (``NameRef.ref_kind`` is ``None``) and
              nothing is typed. A `<...>` type spelling reaches the AST from
              a `primitives { }` entry's two slots alone, single-element,
              un-nested and un-optional; every other type position and the
              phrase form meet a span-carrying rejection naming the entry.
Now illegal:  ill-formed syntax; it cannot reach any later pass. A
              ``Collection<`` spelling on any :class:`~cardlang.ast.nodes.Parameter`
              outside a :class:`~cardlang.ast.nodes.PrimitiveDecl`, or in any
              ``StateDecl`` / ``StructField`` / ``OutcomeCase``. Also
              MUTATING A RETURNED AST: ``parse_text`` is memoized, so two
              callers parsing the same ``(text, source_name, line_offset)``
              receive the SAME object, and one writer would be visible to
              every other holder. A pass that wants to change a node builds a
              new one with ``dataclasses.replace``.

              Four [[owner-guard]]s hold that, each closing a different route, all
              enumerated in tests/test_node_registry.py: ``frozen=True``
              refuses every ordinary ``setattr`` (CPython's frozen
              ``__setattr__`` raises for ANY name on a direct instance, not
              only declared fields); ``slots=True`` additionally refuses
              ``object.__setattr__`` of a NEW name and ``__dict__``/``vars()``
              writes, which a frozen non-slots node would accept; a scrape
              refuses ``object.__setattr__`` of a DECLARED field, the one
              route neither of the others can — it is the same call frozen's
              own ``__init__`` uses, so it is guarded by not appearing at all;
              and a field-type check refuses mutable containers, since a
              ``list`` field would be writable THROUGH the node with no
              ``setattr`` for the other three to catch.

              Sharing itself is not new — ``openspiel/replay.py``'s ``load()``
              has been cached since 2026-06-07. Memoizing here makes it the
              default rather than opt-in, which is what turns those four from
              properties the code happens to have into Owner Guards.
Verified by:  the grammar-ambiguity check (tests/test_grammar_ambiguity.py)
              and the per-construct parse tests; the memo's own liveness and
              key correctness by tests/test_parse.py's caching pins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import cache, lru_cache
from importlib import resources
from typing import cast

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput, VisitError
from lark.tree import Meta
from lark.visitors import Transformer, v_args

from cardlang.ast import nodes as n
from cardlang.builtins.functions import TRICK_ORDER_ROW_KEYS
from cardlang.diagnostics import (
    Diagnostic,
    DiagnosticBag,
    DiagnosticError,
    Severity,
    Span,
)
from cardlang.extract import FencedBlock

# --- private intermediate markers (never leave this module) ---


@dataclass(frozen=True, slots=True)
class _Deck:
    name: str
    span: Span


@dataclass(frozen=True, slots=True)
class _Pieces:
    name: str
    span: Span


@dataclass(frozen=True, slots=True)
class _Direction:
    value: str
    span: Span


@dataclass(frozen=True, slots=True)
class _Ranking:
    ranks: tuple[str, ...]
    span: Span
    # A `RANKING_CONVENTIONS` key ("aces high", …) when the convention form
    # was written; the parse-level XOR guarantees `ranks` is empty then.
    convention: str | None = None


@dataclass(frozen=True, slots=True)
class _CardPointsElse:
    """The `else:` row of a `card_points { }` block, distinguished from the
    rank rows so the table callback can lift it into
    `CardPointsTable.else_value`."""

    value: int


@dataclass(frozen=True, slots=True)
class _Trump:
    suit: str
    span: Span


@dataclass(frozen=True, slots=True)
class _PrimitiveArrowDecl:
    """A `primitives` entry written with the arrow return spelling, carried
    only far enough for the reject callback to name the offending entry at its
    own span."""

    decl: n.PrimitiveDecl
    span: Span


@dataclass(frozen=True, slots=True)
class _PrimitiveDefaultDecl:
    """A `primitives` entry written with a `= <expr>` default, carried the same
    way and for the same reason as `_PrimitiveArrowDecl`."""

    decl: n.PrimitiveDecl
    span: Span


@dataclass(frozen=True, slots=True)
class _TrickOrderEqRow:
    """An assignment-shaped Trick Order row (`trump = ...` / `trump := ...`),
    carried only far enough for the reject callback to name the offending key
    and operator at its own span."""

    key: str
    op: str
    span: Span


@dataclass(frozen=True, slots=True)
class _Teams:
    teams: tuple[tuple[int, ...], ...]
    span: Span


@dataclass(frozen=True, slots=True)
class _MaxLength:
    value: int
    span: Span


@dataclass(frozen=True, slots=True)
class _Zones:
    zones: tuple[n.ZoneDecl, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class _Requires:
    decls: tuple[n.RequireDecl, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class _Positions:
    positions: tuple[n.PositionDecl, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class _TypeName:
    name: str
    optional: bool


@dataclass(frozen=True, slots=True)
class _Selection:
    mode: str | None
    amount: str | object  # "all" | "one" | Expr
    item: str


@dataclass(frozen=True, slots=True)
class _Dest:
    each: bool
    zone: object  # Expr


@dataclass(frozen=True, slots=True)
class _Vis:
    expr: object  # Expr


@dataclass(frozen=True, slots=True)
class _Lvalue:
    name: str
    index: object | None  # Expr | None


@dataclass(frozen=True, slots=True)
class _Constrains:
    move_type: str


@dataclass(frozen=True, slots=True)
class _IfImpossible:
    expr: object  # Expr


@dataclass(frozen=True, slots=True)
class _Exempts:
    expr: object  # Expr


@dataclass(frozen=True, slots=True)
class _Always:
    pass


@dataclass(frozen=True, slots=True)
class _ActionsWhere:
    expr: object  # Expr


@dataclass(frozen=True, slots=True)
class _Elif:
    cond: object  # Expr
    then: object  # Expr


@dataclass(frozen=True, slots=True)
class _ElseBlock:
    body: tuple[object, ...]  # tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class _Dist:
    mode: str


@dataclass(frozen=True, slots=True)
class _Where:
    expr: object  # Expr
    joint: bool = False  # `where jointly <pred>` — binds `cards`, not `card`


@dataclass(frozen=True, slots=True)
class _SelectMode:
    mode: str


@dataclass(frozen=True, slots=True)
class _MoveWhen:
    pred: object  # _Always | Expr


@dataclass(frozen=True, slots=True)
class _MoveEffect:
    body: tuple[object, ...]


@lru_cache(maxsize=1)
def _parser() -> Lark:
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    return Lark(
        grammar,
        parser="earley",
        propagate_positions=True,
        maybe_placeholders=True,
        # `start` is a game file; `stdlib_rules` is the stdlib rules fragment
        # (rule definitions with no enclosing game); `library` is a family
        # library (decisions.md "Family libraries").
        start=["start", "stdlib_rules", "library"],
    )


# The grammar's RANK_DIR terminal (`cardlang.lark`, "lowest" | "highest"),
# mapped to the Comprehension `agg` spelling it lowers to. Exhaustive by
# construction: `agg_order` below raises loudly on any key not present here,
# and `test_rank_dir_set_is_pinned` (test_comprehension_aggregators.py)
# reconciles this set against the grammar terminal so a new RANK_DIR token
# cannot land uncovered.
# The order aggregators, spelled exactly as the surface spells them — the
# grammar's RANK_DIR terminal. `Comprehension.agg` stores the token verbatim,
# as `Winner.rank_dir` already did; before, one token had two storage
# conventions depending on which node received it.
RANK_DIRECTIONS: frozenset[str] = frozenset({"highest", "lowest"})


@v_args(meta=True)
class _Builder(Transformer[Token, n.Game]):
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

    # --- game-level items ---

    def players_fixed(self, meta: Meta, c: list[Token]) -> n.PlayersSpec:
        return n.PlayersSpec(low=int(c[0]), high=None, span=self._span(meta))

    def players_range(self, meta: Meta, c: list[Token]) -> n.PlayersSpec:
        return n.PlayersSpec(low=int(c[0]), high=int(c[1]), span=self._span(meta))

    def players(self, meta: Meta, c: list[n.PlayersSpec]) -> n.PlayersSpec:
        # Re-span over the whole clause (`players: …`), not just the spec —
        # the duplicate-clause diagnostic points here.
        return replace(c[0], span=self._span(meta))

    def direction(self, meta: Meta, c: list[Token]) -> _Direction:
        return _Direction(str(c[0]), span=self._span(meta))

    def cards(self, meta: Meta, c: list[Token]) -> _Deck:
        return _Deck(str(c[0]), span=self._span(meta))

    def pieces(self, meta: Meta, c: list[Token]) -> _Pieces:
        return _Pieces(str(c[0]), span=self._span(meta))

    def ranking(self, meta: Meta, c: list[object]) -> _Ranking:
        # The convention forms: `ace-ten` arrives as the RANK_CONV terminal
        # (its hyphen has no enumeration derivation); the space forms
        # (`aces high`, …) arrive as ordinary card_rank NAMEs and are
        # recognized HERE by exact spelling — a grammar alternative would be
        # a real Earley ambiguity against `card_rank+` (see the grammar's
        # `ranking` comment). This reserves the registry keys' spellings in
        # ranking position: an enumeration can never consist of ranks that
        # space-join to a convention name.
        from cardlang.runtime.values import RANKING_CONVENTIONS

        span = self._span(meta)
        if len(c) == 1 and isinstance(c[0], Token) and c[0].type == "RANK_CONV":
            return _Ranking(ranks=(), span=span, convention=str(c[0]))
        words = tuple(str(r) for r in c)
        if " ".join(words) in RANKING_CONVENTIONS:
            return _Ranking(ranks=(), span=span, convention=" ".join(words))
        return _Ranking(words, span=span)

    def card_rank(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    # --- the card-point table (`card_points { }`) ---

    def card_points_key(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def cp_value(self, meta: Meta, c: list[Token]) -> int:
        return int(c[0])

    def cp_neg_value(self, meta: Meta, c: list[Token]) -> int:
        return -int(c[0])

    def card_points_entry(self, meta: Meta, c: list[object]) -> n.CardPointsEntry:
        assert isinstance(c[0], str) and isinstance(c[1], int)
        return n.CardPointsEntry(rank=c[0], value=c[1], span=self._span(meta))

    def card_points_else(self, meta: Meta, c: list[object]) -> _CardPointsElse:
        assert isinstance(c[0], int)
        return _CardPointsElse(c[0])

    def card_points_table(self, meta: Meta, c: list[object]) -> n.CardPointsTable:
        # Children: the rank rows, then the optional else row (None when
        # absent — the grammar's `[card_points_else]` placeholder).
        entries = tuple(x for x in c if isinstance(x, n.CardPointsEntry))
        else_rows = [x for x in c if isinstance(x, _CardPointsElse)]
        return n.CardPointsTable(
            entries=entries,
            else_value=else_rows[0].value if else_rows else None,
            span=self._span(meta),
        )

    def card_points_colon_reject(self, meta: Meta, c: list[object]) -> None:
        # A retired shape, not a clause: the block clauses take no colon, and
        # the colon habit is the most plausible wrong sentence (every scalar
        # clause a designer has met takes one). The `==`/`!=` mechanism: the
        # grammar owns the shape so the rejection can name the fix.
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "`card_points` is a block clause and takes no colon — write "
                "`card_points { A: 1 ... }`",
                self._span(meta),
            )
        )

    def card_values_reject(self, meta: Meta, c: list[object]) -> None:
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "`card_values` is not a clause — the card-point table is "
                "declared `card_points { A: 1 ... }`, and the Builtin reading "
                "it is `card_points(card)`",
                self._span(meta),
            )
        )

    # --- the primitives block (design-notes/primitive-sidecars.md section 2) ---
    #
    # An entry's NAME is validated nowhere here: which names may be declared is
    # a question about the game's own namespaces and the implementation index,
    # both of which resolve holds. What this layer owns is the SHAPE — the
    # colon row, and the three wrong spellings a designer reaches for.

    def primitive_read(self, meta: Meta, c: list[object]) -> n.PrimitiveRead:
        binder = c[1]
        phase = c[2]
        assert binder is None or isinstance(binder, str)
        assert phase is None or isinstance(phase, str)
        return n.PrimitiveRead(
            name=str(c[0]),
            binder=binder,
            phase=None if phase is None else str(phase),
            span=self._span(meta),
        )

    def primitive_read_transposed_reject(
        self, meta: Meta, c: list[object]
    ) -> n.PrimitiveRead:
        """`X in P[b]` — the binder written on the phase instead of on the
        variable. The replacement is exact, so the designer reads the sentence
        they meant rather than a shape error."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"a `reads` binder rides the variable, not the phase — write "
                f"`{c[0]}[{c[2]}] in {c[1]}`",
                self._span(meta),
            )
        )

    def primitive_reads(
        self, meta: Meta, c: list[n.PrimitiveRead]
    ) -> tuple[n.PrimitiveRead, ...]:
        return tuple(c)

    def primitive_plain_type(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def primitive_optional_type(self, meta: Meta, c: list[Token]) -> str:
        # A nullable entry type keeps its `?` in the name string, exactly as a
        # payload type does; the decomposition strips it.
        return str(c[0]) + "?"

    def primitive_collection_type(self, meta: Meta, c: list[Token]) -> str:
        # The bracket rides in the string too, so a Primitive's parameters and
        # a move type's stay one node shape. `primitives_block.decompose_type`
        # is the ONE reader of it.
        return f"{c[0]}<{c[1]}>"

    def collection_type_reject(self, meta: Meta, c: list[Token]) -> str:
        """A collection type written where the entry's slots are not.

        The spelling is real, so this names WHERE it belongs rather than
        calling the word unknown or dying at the bracket — the placement is the
        designer's mistake, and the entry is the answer."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "a collection type (`Collection<Card>`) is spellable in a "
                "`primitives { }` entry only — everywhere else a set of cards "
                "is a zone, and `move chosen some cards ... where jointly` is "
                "how a game picks one",
                self._span(meta),
            )
        )

    def collection_optional_reject(self, meta: Meta, c: list[Token]) -> str:
        """A `?` on the collection itself. Designed, not deferred.

        The runtime reason is `coerce_args`: its dispatch is on the declared
        `TCollection`, so an optional wrapper would pass the argument raw and
        die at the boundary. The designer's reason is the one the message
        carries — a set that might not be there has no rulebook reading, and
        an empty one is what they mean."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "a collection is never optional — `is empty` is its absence; "
                "write `Collection<Card>`",
                self._span(meta),
            )
        )

    def collection_arity_reject(self, meta: Meta, c: list[Token]) -> str:
        """A second element type. The keyed shape a designer reaches for here
        is the index bracket's, and a second spelling of one concept is the
        defect class this refuses into."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "a collection takes ONE element type — write `Collection<Card>`",
                self._span(meta),
            )
        )

    def collection_nested_reject(self, meta: Meta, c: list[Token]) -> str:
        """A collection of collections, at any depth.

        The game that wants one is a melding game, and the answer it is owed
        is a name for a group rather than a generic instantiation — so the
        message says the shape has no spelling and names where that is
        tracked, instead of teaching a form the language will not grow."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "a collection's element is a single type name — a collection "
                "of collections has no spelling here (issue #254 tracks the "
                "melds that would need one)",
                self._span(meta),
            )
        )

    def collection_optional_element_reject(self, meta: Meta, c: list[Token]) -> str:
        """A `?` on the element. An absence INSIDE a set has no rulebook
        reading; the operation the designer wants is a filter."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "an element is never optional — filter the collection "
                "instead; write `Collection<Card>`",
                self._span(meta),
            )
        )

    def collection_phrase_reject(self, meta: Meta, c: list[Token]) -> str:
        """The phrase form, taught back as the ruled one.

        No declaration in this language spells a type as a phrase, and `of`
        already carries three senses in expressions — so the sentence a reader
        of the design note writes first earns a replacement, not a life."""
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"a `primitives` entry spells a collection with angle "
                f"brackets, not a phrase — write `Collection<{c[1]}>` in place "
                f"of `{c[0]} of {c[1]}`",
                self._span(meta),
            )
        )

    def primitive_param(self, meta: Meta, c: list[object]) -> n.Parameter:
        # The entry's own parameter production. One NODE with a move type's,
        # because a Primitive's parameters and a move type's are one shape;
        # one PRODUCTION of its own, because the shared type productions carry
        # the teaching twin and a shared derivation would be ambiguous here.
        return n.Parameter(
            name=str(c[0]), type_name=str(c[1]), span=self._span(meta)
        )

    def _primitive_decl(self, meta: Meta, c: list[object]) -> n.PrimitiveDecl:
        """The shared body of the entry and its two reject twins, so the three
        productions cannot drift in what they read out of the same slots."""
        params = tuple(x for x in c if isinstance(x, n.Parameter))
        # The return type is the one bare string among the children: a
        # `payload_type` builds one, and `parameter` has already consumed its
        # own. The reads clause arrives as a tuple, absent as None.
        types = [x for x in c[1:] if isinstance(x, str)]
        reads = next((x for x in c if isinstance(x, tuple)), ())
        return n.PrimitiveDecl(
            name=str(c[0]),
            params=params,
            return_type=types[-1],
            reads=reads,
            span=self._span(meta),
        )

    def primitive_decl(self, meta: Meta, c: list[object]) -> n.PrimitiveDecl:
        return self._primitive_decl(meta, c)

    def primitive_arrow_decl(self, meta: Meta, c: list[object]) -> _PrimitiveArrowDecl:
        return _PrimitiveArrowDecl(
            decl=self._primitive_decl(meta, c), span=self._span(meta)
        )

    def primitive_default_decl(
        self, meta: Meta, c: list[object]
    ) -> _PrimitiveDefaultDecl:
        return _PrimitiveDefaultDecl(
            decl=self._primitive_decl(meta, c), span=self._span(meta)
        )

    def primitives_block(self, meta: Meta, c: list[object]) -> n.PrimitivesBlock:
        decls = tuple(x for x in c if isinstance(x, n.PrimitiveDecl))
        return n.PrimitivesBlock(decls=decls, span=self._span(meta))

    def primitives_colon_reject(self, meta: Meta, c: list[object]) -> n.PrimitivesBlock:
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "`primitives` is a block clause and takes no colon — write "
                "`primitives { name(p : Player) : Integer reads hand[p] }`",
                self._span(meta),
            )
        )

    def primitives_arrow_reject(self, meta: Meta, c: list[object]) -> n.PrimitivesBlock:
        bad = next(x for x in c if isinstance(x, _PrimitiveArrowDecl))
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"a `primitives` entry names its return type after a colon, "
                f"not an arrow — write `{bad.decl.name}(...) : "
                f"{bad.decl.return_type}`",
                bad.span,
            )
        )

    def primitives_default_reject(
        self, meta: Meta, c: list[object]
    ) -> n.PrimitivesBlock:
        bad = next(x for x in c if isinstance(x, _PrimitiveDefaultDecl))
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"a `primitives` entry declares a signature, never a value — "
                f"`{bad.decl.name}(...) : {bad.decl.return_type} = ...` gives it "
                f"a default the implementation would never see; drop the `=`",
                bad.span,
            )
        )

    # --- the Trick Order block (decisions.md "Trick Order"; issue #250) ------
    #
    # The row set is `TRICK_ORDER_ROWS`, and it is stated there ONLY: the
    # grammar's key terminal matches any identifier, and these callbacks
    # validate against the registry. That is what keeps a row added to the
    # language from needing a grammar edit, and what lets a wrong key be
    # refused by NAMING the rows rather than dying as a bare syntax error.

    def trick_order_row(self, meta: Meta, c: list[object]) -> n.TrickOrderRow:
        key = str(c[0])
        assert isinstance(c[1], n.Expr)
        if key not in TRICK_ORDER_ROW_KEYS:
            raise DiagnosticError(
                Diagnostic(
                    Severity.ERROR,
                    f"`{key}:` is not a row of `trick_order` — the rows are "
                    + ", ".join(f"`{k}:`" for k in TRICK_ORDER_ROW_KEYS),
                    self._span(meta),
                )
            )
        return n.TrickOrderRow(
            key=cast(n.TrickOrderRowKey, key), body=c[1], span=self._span(meta)
        )

    def trick_order(self, meta: Meta, c: list[object]) -> n.TrickOrder:
        rows = tuple(x for x in c if isinstance(x, n.TrickOrderRow))
        seen: set[str] = set()
        for row in rows:
            if row.key in seen:
                # A repeat would silently replace the first — the
                # accepted-but-ignored class, refused at its own row's span.
                raise DiagnosticError(
                    Diagnostic(
                        Severity.ERROR,
                        f"`trick_order` declares one `{row.key}:` row — the "
                        f"repeat would silently replace the first; keep one",
                        row.span,
                    )
                )
            seen.add(row.key)
        if "trump" not in seen:
            # Required, both counsels and the operator's ruling: every Trick
            # Order names its trumps, and a game with none says so rather than
            # leaving the reader to infer it from an absence.
            raise DiagnosticError(
                Diagnostic(
                    Severity.ERROR,
                    "`trick_order` declares no `trump:` row — every Trick "
                    "Order names its trumps; write `trump: false` for one "
                    "with none",
                    self._span(meta),
                )
            )
        return n.TrickOrder(rows=rows, span=self._span(meta))

    def trick_order_colon_reject(self, meta: Meta, c: list[object]) -> None:
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "`trick_order` is a block clause and takes no colon — write "
                "`trick_order { trump: ... }`",
                self._span(meta),
            )
        )

    def trick_order_comma_reject(self, meta: Meta, c: list[object]) -> None:
        first, second = TRICK_ORDER_ROW_KEYS[0], TRICK_ORDER_ROW_KEYS[1]
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"`trick_order` rows are whitespace-separated, never "
                f"comma-separated — write `trick_order {{ {first}: ...  "
                f"{second}: ... }}`",
                self._span(meta),
            )
        )

    def trick_order_eq_row(self, meta: Meta, c: list[object]) -> _TrickOrderEqRow:
        return _TrickOrderEqRow(str(c[0]), str(c[1]), span=self._span(meta))

    def trick_order_eq_reject(self, meta: Meta, c: list[object]) -> None:
        # The first assignment-shaped row speaks, so a block mixing one wrong
        # row among colon rows is refused at the row that is wrong.
        bad = next(x for x in c if isinstance(x, _TrickOrderEqRow))
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"a `trick_order` row is `{bad.key}: <expr>`, not "
                f"`{bad.key} {bad.op} <expr>` — write `{bad.key}: ...`",
                bad.span,
            )
        )

    def trump(self, meta: Meta, c: list[Token]) -> _Trump:
        return _Trump(str(c[0]), span=self._span(meta))

    def trump_int_reject(self, meta: Meta, c: list[Token]) -> None:
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "`trump:` names a suit of the declared deck by its bare name "
                "(`trump: spades`), not a number",
                self._span(meta),
            )
        )

    def trump_string_reject(self, meta: Meta, c: list[Token]) -> None:
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                "`trump:` names a suit of the declared deck by its bare name "
                "(`trump: spades`), not a quoted string — write the suit "
                "unquoted",
                self._span(meta),
            )
        )

    def team_spec(self, meta: Meta, c: list[Token]) -> tuple[int, ...]:
        return tuple(int(x) for x in c)

    def teams(self, meta: Meta, c: list[object]) -> _Teams:
        teams = tuple(t for t in c if isinstance(t, tuple))
        return _Teams(teams, span=self._span(meta))

    def max_length(self, meta: Meta, c: list[Token]) -> _MaxLength:
        return _MaxLength(int(c[0]), span=self._span(meta))

    def winner(self, meta: Meta, c: list[Token]) -> n.Winner:
        return n.Winner(rank_dir=str(c[0]), state_var=str(c[1]), span=self._span(meta))

    def loser(self, meta: Meta, c: list[object]) -> n.Loser:
        return n.Loser(selection=_as_expr(c[0]), span=self._span(meta))

    def rank_dir(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    # --- zones ---

    def index(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def type_arg(self, meta: Meta, c: list[Token]) -> n.TypeArg:
        return n.TypeArg(name=str(c[0]), span=self._span(meta))

    def type_args(self, meta: Meta, c: list[n.TypeArg]) -> tuple[n.TypeArg, ...]:
        return tuple(c)

    def type_ref(self, meta: Meta, c: list[object]) -> n.TypeRef:
        name = str(c[0])
        args: tuple[n.TypeArg, ...] = ()
        if len(c) > 1 and c[1] is not None:
            assert isinstance(c[1], tuple)
            args = c[1]
        return n.TypeRef(name=name, args=args, span=self._span(meta))

    def zone_decl(self, meta: Meta, c: list[object]) -> n.ZoneDecl:
        index = c[1]
        assert index is None or isinstance(index, str)
        assert isinstance(c[2], n.TypeRef)
        return n.ZoneDecl(
            name=str(c[0]), index=index, type_ref=c[2], span=self._span(meta)
        )

    def zones(self, meta: Meta, c: list[n.ZoneDecl]) -> _Zones:
        return _Zones(tuple(c), span=self._span(meta))

    # --- positions ---

    def position_decl(self, meta: Meta, c: list[Token]) -> n.PositionDecl:
        return n.PositionDecl(
            name=str(c[0]), lo=int(c[1]), hi=int(c[2]), span=self._span(meta)
        )

    def positions(self, meta: Meta, c: list[n.PositionDecl]) -> _Positions:
        return _Positions(tuple(c), span=self._span(meta))

    # --- board ---

    def board(self, meta: Meta, c: list[Token]) -> n.BoardDecl:
        # `c[0]` is the family NAME; the parenthesized INT args (if any)
        # follow (the "(", ",", ")" literals are filtered by lark). An omitted
        # arg list arrives as one None placeholder (`maybe_placeholders`) --
        # filtered here, so `board: grid` reaches resolve as zero args and
        # `board_entry`'s arity diagnostic, not an int(None) crash. Family/arg
        # validity is a resolve diagnostic via `board_entry` -- parse only
        # shapes the declaration.
        return n.BoardDecl(
            family=str(c[0]),
            args=tuple(int(x) for x in c[1:] if x is not None),
            span=self._span(meta),
        )

    # --- state ---

    def optional_type(self, meta: Meta, c: list[Token]) -> _TypeName:
        return _TypeName(str(c[0]), optional=True)

    def plain_type(self, meta: Meta, c: list[Token]) -> _TypeName:
        return _TypeName(str(c[0]), optional=False)

    def state_decl(self, meta: Meta, c: list[object]) -> n.StateDecl:
        name = str(c[0])
        index = c[1]
        assert index is None or isinstance(index, str)
        assert isinstance(c[2], _TypeName)
        return n.StateDecl(
            name=name,
            index=index,
            type_name=c[2].name,
            optional=c[2].optional,
            default=_as_expr(c[3]),
            span=self._span(meta),
        )

    def state_block(self, meta: Meta, c: list[n.StateDecl]) -> n.StateBlock:
        return n.StateBlock(decls=tuple(c), span=self._span(meta))

    # --- family libraries ---

    def uses_decl(self, meta: Meta, c: list[Token]) -> n.UsesDecl:
        return n.UsesDecl(name=str(c[0]), span=self._span(meta))

    def _require_decl(
        self, meta: Meta, c: list[object], *, optional: bool
    ) -> n.RequireDecl:
        index = c[1]
        assert index is None or isinstance(index, str)
        args: tuple[n.TypeArg, ...] = ()
        if len(c) > 3 and c[3] is not None:
            assert isinstance(c[3], tuple)
            args = c[3]
        return n.RequireDecl(
            name=str(c[0]),
            index=index,
            type_name=str(c[2]),
            type_args=args,
            optional=optional,
            span=self._span(meta),
        )

    def require_plain(self, meta: Meta, c: list[object]) -> n.RequireDecl:
        return self._require_decl(meta, c, optional=False)

    def require_optional(self, meta: Meta, c: list[object]) -> n.RequireDecl:
        return self._require_decl(meta, c, optional=True)

    def requires_block(self, meta: Meta, c: list[n.RequireDecl]) -> _Requires:
        return _Requires(tuple(c), span=self._span(meta))

    def library(self, meta: Meta, c: list[object]) -> n.Library:
        # ONE dispatch over the children, not a filter per field: independent
        # filters have no residue, so an item no filter matches is dropped
        # without a word — the accepted-but-ignored defect class, at the
        # granularity of a whole clause. `game()` below is the sibling this
        # mirrors, down to the `else` arm's channel.
        requires: tuple[n.RequireDecl, ...] = ()
        seen_requires = False
        state: n.StateBlock | None = None
        rules: list[n.RuleDef] = []
        move_types: list[n.MoveTypeDef] = []
        types: list[n.TypeDef] = []
        defines: list[n.DefineDef] = []
        functions: list[n.FunctionDef] = []
        procedures: list[n.ProcedureDef] = []
        for item in c[1:]:
            if isinstance(item, _Requires):
                # `library_item*` accepts repeats of the single-valued `requires`
                # block the same way `game_item*` does for the scalar game
                # clauses; keeping the last would silently discard the first
                # (decisions.md "Surface totality").
                if seen_requires:
                    raise DiagnosticError(
                        Diagnostic(
                            Severity.ERROR,
                            "a library declares one `requires` block — merge the "
                            "declarations into it",
                            item.span,
                        )
                    )
                seen_requires = True
                requires = item.decls
            elif isinstance(item, n.StateBlock):
                # Single-valued for the same reason `requires` is, and for the
                # same reason a GAME declares one `state { }`: keeping the last
                # would silently discard the first.
                if state is not None:
                    raise DiagnosticError(
                        Diagnostic(
                            Severity.ERROR,
                            "a library declares one `state` block — merge the "
                            "declarations into it",
                            item.span,
                        )
                    )
                state = item
            elif isinstance(item, n.RuleDef):
                rules.append(item)
            elif isinstance(item, n.MoveTypeDef):
                move_types.append(item)
            elif isinstance(item, n.TypeDef):
                types.append(item)
            elif isinstance(item, n.DefineDef):
                defines.append(item)
            elif isinstance(item, n.FunctionDef):
                functions.append(item)
            elif isinstance(item, n.ProcedureDef):
                procedures.append(item)
            else:
                # An `?library_item` alternative with no arm above. Compiler-bug
                # channel, exactly as in `game()`: a grammar alternative nobody
                # taught the builder about is a defect in this package, not a
                # sentence the designer got wrong, so it may not be reported as
                # an author-facing diagnostic. Pinned by
                # tests/test_family_libraries.py::test_an_unhandled_library_item_is_loud.
                raise AssertionError(f"unexpected library item: {item!r}")
        return n.Library(
            name=str(c[0]),
            requires=requires,
            state=state,
            rules=tuple(rules),
            move_types=tuple(move_types),
            types=tuple(types),
            defines=tuple(defines),
            functions=tuple(functions),
            procedures=tuple(procedures),
            span=self._span(meta),
        )

    # --- user-defined types ---

    def struct_field(self, meta: Meta, c: list[object]) -> n.StructField:
        assert isinstance(c[1], _TypeName)
        return n.StructField(
            name=str(c[0]),
            type_name=c[1].name,
            optional=c[1].optional,
            span=self._span(meta),
        )

    def derived_field(self, meta: Meta, c: list[object]) -> n.DerivedField:
        return n.DerivedField(
            name=str(c[0]), value=_as_expr(c[1]), span=self._span(meta)
        )

    def derived_block(
        self, meta: Meta, c: list[n.DerivedField]
    ) -> tuple[n.DerivedField, ...]:
        return tuple(c)

    def type_def(self, meta: Meta, c: list[object]) -> n.TypeDef:
        name = str(c[0])
        fields = tuple(x for x in c if isinstance(x, n.StructField))
        derived = next((x for x in c if isinstance(x, tuple)), ())
        return n.TypeDef(
            name=name, fields=fields, derived=derived, span=self._span(meta)
        )

    # --- phases ---

    def phase_repeats(self, meta: Meta, c: list[object]) -> n.PhaseQualifier:
        return n.PhaseQualifier("repeat_until", _as_expr(c[0]), span=self._span(meta))

    def phase_when(self, meta: Meta, c: list[object]) -> n.PhaseQualifier:
        return n.PhaseQualifier("when", _as_expr(c[0]), span=self._span(meta))

    def phase_outcome(self, meta: Meta, c: list[object]) -> tuple[n.OutcomeCase, ...]:
        # `-> outcome { ... }`: unwrap to the outcome_set tuple.
        return next(x for x in c if isinstance(x, tuple))

    def phase(self, meta: Meta, c: list[object]) -> n.Phase:
        # c: NAME, optional outcome (a tuple), optional qualifier, then items —
        # the two optionals leave None placeholders, so scan by type rather than
        # by position.
        name = str(c[0])
        qualifier = next((x for x in c if isinstance(x, n.PhaseQualifier)), None)
        outcome_cases = next((x for x in c if isinstance(x, tuple)), ())
        items = tuple(
            x
            for x in c[1:]
            if x is not None and not isinstance(x, (n.PhaseQualifier, tuple))
        )
        return n.Phase(
            name=name,
            qualifier=qualifier,
            outcome_cases=outcome_cases,
            items=items,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def mode_def(self, meta: Meta, c: list[object]) -> n.Mode:
        # `?mode_item` admits exactly two alternatives, so the body splits by
        # type with no residue — the grammar, not this builder, is what makes
        # anything else impossible here.
        return n.Mode(
            name=str(c[0]),
            active_rules=tuple(x for x in c[1:] if isinstance(x, n.ActiveRules)),
            transitions=tuple(x for x in c[1:] if isinstance(x, n.TransitionTo)),
            span=self._span(meta),
        )

    def active_rules(self, meta: Meta, c: list[object]) -> n.ActiveRules:
        refs = tuple(r for r in c if isinstance(r, n.RuleRef))
        return n.ActiveRules(refs=refs, span=self._span(meta))

    def rule_args(self, meta: Meta, c: list[object]) -> tuple[object, ...]:
        return tuple(_as_expr(x) for x in c)

    def rule_plain(self, meta: Meta, c: list[object]) -> n.RuleRef:
        args = c[1] if len(c) > 1 and isinstance(c[1], tuple) else ()
        return n.RuleRef(str(c[0]), "plain", args=args, span=self._span(meta))

    def rule_add(self, meta: Meta, c: list[object]) -> n.RuleRef:
        args = c[1] if len(c) > 1 and isinstance(c[1], tuple) else ()
        return n.RuleRef(str(c[0]), "add", args=args, span=self._span(meta))

    def rule_remove(self, meta: Meta, c: list[Token]) -> n.RuleRef:
        return n.RuleRef(str(c[0]), "remove", span=self._span(meta))

    def rule_override(self, meta: Meta, c: list[Token]) -> n.RuleRef:
        return n.RuleRef(str(c[0]), "override", span=self._span(meta))

    def legal_moves(self, meta: Meta, c: list[object]) -> n.LegalMoves:
        names = tuple(str(x) for x in c if x is not None)
        return n.LegalMoves(move_types=names, span=self._span(meta))

    def before_each(self, meta: Meta, c: list[object]) -> n.BeforeEach:
        return n.BeforeEach(body=tuple(_as_stmt(s) for s in c), span=self._span(meta))

    def after_each(self, meta: Meta, c: list[object]) -> n.AfterEach:
        return n.AfterEach(body=tuple(_as_stmt(s) for s in c), span=self._span(meta))

    def transition_to(self, meta: Meta, c: list[object]) -> n.TransitionTo:
        assert isinstance(c[1], n.MoveEvent)
        return n.TransitionTo(mode=str(c[0]), event=c[1], span=self._span(meta))

    def move_event(self, meta: Meta, c: list[object]) -> n.MoveEvent:
        where = _as_expr(c[1]) if len(c) > 1 and c[1] is not None else None
        return n.MoveEvent(move_type=str(c[0]), where=where, span=self._span(meta))

    # --- statements ---

    def sel_chosen(self, meta: Meta, c: list[object]) -> _SelectMode:
        return _SelectMode("chosen")

    def sel_random(self, meta: Meta, c: list[object]) -> _SelectMode:
        return _SelectMode("random")

    def amt_all(self, meta: Meta, c: list[object]) -> str:
        return "all"

    def amt_one(self, meta: Meta, c: list[object]) -> str:
        return "one"

    def amt_some(self, meta: Meta, c: list[object]) -> str:
        return "some"

    def amt_count(self, meta: Meta, c: list[object]) -> object:
        return _as_expr(c[0])

    def selection(self, meta: Meta, c: list[object]) -> _Selection:
        mode = c[0].mode if isinstance(c[0], _SelectMode) else None
        return _Selection(mode=mode, amount=c[1], item=str(c[2]))

    def dest_each(self, meta: Meta, c: list[object]) -> _Dest:
        return _Dest(each=True, zone=_as_expr(c[0]))

    def dest_one(self, meta: Meta, c: list[object]) -> _Dest:
        return _Dest(each=False, zone=_as_expr(c[0]))

    def vis_clause(self, meta: Meta, c: list[object]) -> _Vis:
        return _Vis(_as_expr(c[0]))

    def move_from(self, meta: Meta, c: list[object]) -> n.Transfer:
        sel = next(x for x in c if isinstance(x, _Selection))
        dest = next(x for x in c if isinstance(x, _Dest))
        vis = next((x.expr for x in c if isinstance(x, _Vis)), None)
        dist = next((x.mode for x in c if isinstance(x, _Dist)), None)
        where = next((x for x in c if isinstance(x, _Where)), None)
        return n.Transfer(
            verb=str(c[0]),
            selection_mode=sel.mode,
            amount=sel.amount,  # type: ignore[arg-type]
            item=sel.item,
            source=_as_expr(c[2]),  # zone_expr is the 3rd positional child
            dest=dest.zone,  # type: ignore[arg-type]
            dest_each=dest.each,
            distribution=dist,
            where=where.expr if where is not None else None,  # type: ignore[arg-type]
            joint=where.joint if where is not None else False,
            visibility=vis,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def dist_equally(self, meta: Meta, c: list[object]) -> _Dist:
        return _Dist("as_equally_as_possible")

    def where_each(self, meta: Meta, c: list[object]) -> _Where:
        return _Where(_as_expr(c[0]))

    def where_jointly(self, meta: Meta, c: list[object]) -> _Where:
        return _Where(_as_expr(c[0]), joint=True)

    def move_gather(self, meta: Meta, c: list[object]) -> n.Transfer:
        assert isinstance(c[1], _Selection) and isinstance(c[2], _Dest)
        vis = c[3].expr if len(c) > 3 and isinstance(c[3], _Vis) else None
        return n.Transfer(
            verb=str(c[0]),
            selection_mode=c[1].mode,
            amount=c[1].amount,  # type: ignore[arg-type]
            item=c[1].item,
            source=None,
            dest=c[2].zone,  # type: ignore[arg-type]
            dest_each=c[2].each,
            visibility=vis,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def move_in(self, meta: Meta, c: list[object]) -> n.Transfer:
        assert isinstance(c[1], _Selection)
        vis = c[3].expr if len(c) > 3 and isinstance(c[3], _Vis) else None
        return n.Transfer(
            verb=str(c[0]),
            selection_mode=c[1].mode,
            amount=c[1].amount,  # type: ignore[arg-type]
            item=c[1].item,
            source=_as_expr(c[2]),
            dest=None,
            dest_each=False,
            visibility=vis,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def shuffle_op(self, meta: Meta, c: list[object]) -> n.EpistemicOp:
        return n.EpistemicOp(op="shuffle", zone=_as_expr(c[0]), span=self._span(meta))

    def reveal_op(self, meta: Meta, c: list[object]) -> n.EpistemicOp:
        # The filter is an ordinary predicate with `card` bound per candidate
        # (a lambda during the register transition).
        filt = _as_expr(c[1]) if len(c) > 1 and c[1] is not None else None
        return n.EpistemicOp(
            op="reveal", zone=_as_expr(c[0]), where=filt, span=self._span(meta)
        )

    def name_list(self, meta: Meta, c: list[Token]) -> tuple[str, ...]:
        return tuple(str(x) for x in c)

    def rotate_stmt(self, meta: Meta, c: list[object]) -> n.RotateStmt:
        assert isinstance(c[1], tuple)
        return n.RotateStmt(
            target=n.NameRef(name=str(c[0]), span=self._span(meta)),
            values=c[1],
            span=self._span(meta),
        )

    def each_simultaneous(self, meta: Meta, c: list[object]) -> n.EachSimultaneous:
        return n.EachSimultaneous(
            role=str(c[0]), body=_as_stmt(c[1]), span=self._span(meta)
        )

    def for_each(self, meta: Meta, c: list[object]) -> n.ForEach:
        return n.ForEach(
            role=str(c[0]), binder=str(c[1]), body=_as_stmt(c[2]), span=self._span(meta)
        )

    def repeat_until(self, meta: Meta, c: list[object]) -> n.RepeatUntil:
        cond = _as_expr(c[0])
        body = tuple(_as_stmt(s) for s in c[1:])
        return n.RepeatUntil(until=cond, body=body, span=self._span(meta))

    def else_block(self, meta: Meta, c: list[object]) -> _ElseBlock:
        return _ElseBlock(body=tuple(_as_stmt(s) for s in c))

    def if_stmt(self, meta: Meta, c: list[object]) -> n.IfStmt:
        cond = _as_expr(c[0])
        last = c[-1]
        else_body = last.body if isinstance(last, _ElseBlock) else None
        then_body = tuple(_as_stmt(s) for s in c[1:-1])
        return n.IfStmt(
            cond=cond,
            then_body=then_body,
            else_body=else_body,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def as_block(self, meta: Meta, c: list[object]) -> n.AsBlock:
        # `_AS_KW` is auto-filtered (leading underscore), so c[0] is the player
        # expression and c[1:] are the braced body statements.
        player = _as_expr(c[0])
        body = tuple(_as_stmt(s) for s in c[1:])
        return n.AsBlock(player=player, body=body, span=self._span(meta))

    def turns_stmt(self, meta: Meta, c: list[object]) -> n.Turns:
        # c: [NAME(binder), expr(leader), expr(participants), expr(until),
        #     NAME(again)|None, statement*] — with maybe_placeholders=True the
        #     optional `again` NAME is None when the clause is absent.
        return n.Turns(
            binder=str(c[0]),
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            until=_as_expr(c[3]),
            again=str(c[4]) if c[4] is not None else None,
            body=tuple(_as_stmt(s) for s in c[5:]),
            span=self._span(meta),
        )

    def named_arg(self, meta: Meta, c: list[object]) -> n.NamedArg:
        return n.NamedArg(name=str(c[0]), value=c[1], span=self._span(meta))  # type: ignore[arg-type]

    def offer(self, meta: Meta, c: list[object]) -> n.Offer:
        player = _as_expr(c[0])
        names = tuple(str(x) for x in c[1:])
        return n.Offer(player=player, offering=names, span=self._span(meta))

    def round_stmt(self, meta: Meta, c: list[object]) -> n.TrickRound:
        # c: [NAME(move_type), expr(leader), expr(participants), NAME(source),
        #     NAME(into), NAME(winner), expr(trump)?, NAME(early)?]
        # With maybe_placeholders=True, len(c)==8 always; c[6]/c[7] are None when absent.
        trump = _as_expr(c[6]) if c[6] is not None else None
        early = str(c[7]) if c[7] is not None else None
        return n.TrickRound(
            move_type=str(c[0]),
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            source_zone=str(c[3]),
            play_zone=str(c[4]),
            winner_fn=str(c[5]),
            trump=trump,
            early_termination=early,
            span=self._span(meta),
        )

    def auction_moves(self, meta: Meta, c: list[object]) -> tuple[str, ...]:
        return tuple(str(x) for x in c)

    def auction_stmt(self, meta: Meta, c: list[object]) -> n.AuctionRound:
        # c: [tuple(move_types), expr(leader), expr(participants), NAME(order)?,
        #     expr(termination), NAME(outcome)?]. Both the `order` clause (c[3],
        #     default ring) and `outcome` (c[5], betting omits it) are None
        #     placeholders when absent.
        offering = c[0]
        assert isinstance(offering, tuple)
        return n.AuctionRound(
            offering=offering,
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            until=_as_expr(c[4]),
            order_mode=str(c[3]) if c[3] is not None else None,
            outcome_fn=str(c[5]) if c[5] is not None else None,
            span=self._span(meta),
        )

    def climb_stmt(self, meta: Meta, c: list[object]) -> n.ClimbRound:
        # c: [NAME(move_type), expr(leader), expr(participants), NAME(source),
        #     NAME(into), NAME(combinations), NAME(follows), expr(termination)].
        # The climbing form keeps the trick zones (source/into) but names the
        # combination-engine queries instead of a winner function; the winner is
        # the loop's last player.
        return n.ClimbRound(
            move_type=str(c[0]),
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            source_zone=str(c[3]),
            play_zone=str(c[4]),
            combos_fn=str(c[5]),
            follows_fn=str(c[6]),
            until=_as_expr(c[7]),
            span=self._span(meta),
        )

    def let_stmt(self, meta: Meta, c: list[object]) -> n.LetStmt:
        index = c[1] if isinstance(c[1], str) else None
        return n.LetStmt(
            name=str(c[0]), index=index, value=_as_expr(c[2]), span=self._span(meta)
        )

    def lvalue(self, meta: Meta, c: list[object]) -> _Lvalue:
        index = _as_expr(c[1]) if len(c) > 1 and c[1] is not None else None
        return _Lvalue(name=str(c[0]), index=index)

    def assign_op(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def assign_stmt(self, meta: Meta, c: list[object]) -> n.AssignStmt:
        assert isinstance(c[0], _Lvalue)
        return n.AssignStmt(
            target=n.NameRef(name=c[0].name, span=self._span(meta)),
            index=c[0].index,  # type: ignore[arg-type]
            op=str(c[1]),
            value=_as_expr(c[2]),
            span=self._span(meta),
        )

    # --- rules ---

    def constrains(self, meta: Meta, c: list[Token]) -> _Constrains:
        return _Constrains(str(c[0]))

    def always(self, meta: Meta, c: list[object]) -> _Always:
        return _Always()

    def applies_when(self, meta: Meta, c: list[object]) -> n.AppliesWhen:
        if isinstance(c[0], _Always):
            return n.AppliesWhen(always=True, pred=None, span=self._span(meta))
        return n.AppliesWhen(always=False, pred=_as_expr(c[0]), span=self._span(meta))

    def actions_where(self, meta: Meta, c: list[object]) -> _ActionsWhere:
        return _ActionsWhere(_as_expr(c[0]))

    def demands(self, meta: Meta, c: list[object]) -> n.Demands:
        if isinstance(c[0], _ActionsWhere):
            return n.Demands(kind="actions", expr=c[0].expr, span=self._span(meta))  # type: ignore[arg-type]
        return n.Demands(kind="cards", expr=_as_expr(c[0]), span=self._span(meta))

    def if_impossible(self, meta: Meta, c: list[object]) -> _IfImpossible:
        return _IfImpossible(_as_expr(c[0]))

    def exempts(self, meta: Meta, c: list[object]) -> _Exempts:
        return _Exempts(_as_expr(c[0]))

    def rule_params(self, meta: Meta, c: list[n.Parameter]) -> tuple[n.Parameter, ...]:
        return tuple(c)

    def rule_def(self, meta: Meta, c: list[object]) -> n.RuleDef:
        name = str(c[0])
        # The optional rule_params group leaves a None placeholder when absent.
        params = c[1] if isinstance(c[1], tuple) else ()
        constrains: str | None = None
        applies: n.AppliesWhen | None = None
        demands: n.Demands | None = None
        if_imp: object | None = None
        exempts_expr: object | None = None
        for clause in c[2:]:
            if isinstance(clause, _Constrains):
                constrains = clause.move_type
            elif isinstance(clause, n.AppliesWhen):
                applies = clause
            elif isinstance(clause, n.Demands):
                demands = clause
            elif isinstance(clause, _IfImpossible):
                if_imp = clause.expr
            elif isinstance(clause, _Exempts):
                exempts_expr = clause.expr
            else:
                raise AssertionError(f"unexpected rule clause: {clause!r}")
        return n.RuleDef(
            name=name,
            constrains=constrains,
            applies_when=applies,
            demands=demands,
            if_impossible=if_imp,  # type: ignore[arg-type]
            exempts=exempts_expr,  # type: ignore[arg-type]
            params=params,
            span=self._span(meta),
        )

    def stdlib_rules(self, meta: Meta, c: list[object]) -> tuple[n.RuleDef, ...]:
        return tuple(x for x in c if isinstance(x, n.RuleDef))

    # --- expressions ---

    def _implicit_quantifier(self, kind: str, role: str, meta: Meta, c: list[object]) -> n.Quantifier:
        # The implicit-binder spelling: the role noun is also the binder.
        return n.Quantifier(kind, role, role, _as_expr(c[0]), span=self._span(meta))

    def q_any_player(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("any", "player", meta, c)

    def q_all_player(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("all", "player", meta, c)

    def q_any_team(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("any", "team", meta, c)

    def q_all_team(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("all", "team", meta, c)

    def q_any_suit(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("any", "suit", meta, c)

    def q_all_suit(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("all", "suit", meta, c)

    def q_any_rank(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("any", "rank", meta, c)

    def q_all_rank(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return self._implicit_quantifier("all", "rank", meta, c)

    def _domain_query(
        self, kind: str, meta: Meta, noun: object, source: object, pred: object
    ) -> n.DomainQuery:
        # The plural convention is fixed by kind: `any` takes the singular
        # noun, `all`/`number of` the plural. The binder (the scoped name, and
        # for a bare form the domain to enumerate) is the singular, derived by
        # stripping a trailing `s` from a plural spelling; `spelled` keeps the
        # raw noun so resolve can quote it in the plural-mismatch diagnostic.
        # Whether the plural was actually well-formed is resolve's Owner Guard —
        # this only recovers the intended singular so the body's binder resolves.
        spelled = str(noun)
        binder = spelled[:-1] if kind != "any" and spelled.endswith("s") else spelled
        return n.DomainQuery(
            kind=kind,
            binder=binder,
            spelled=spelled,
            source=_as_expr(source) if source is not None else None,
            where=_as_expr(pred),
            span=self._span(meta),
        )

    def q_any_domain(self, meta: Meta, c: list[object]) -> n.DomainQuery:
        return self._domain_query("any", meta, c[0], None, c[1])

    def q_all_domain(self, meta: Meta, c: list[object]) -> n.DomainQuery:
        return self._domain_query("all", meta, c[0], None, c[1])

    def q_count_domain(self, meta: Meta, c: list[object]) -> n.DomainQuery:
        return self._domain_query("count", meta, c[0], None, c[1])

    def q_any_in(self, meta: Meta, c: list[object]) -> n.DomainQuery:
        return self._domain_query("any", meta, c[0], c[1], c[2])

    def q_all_in(self, meta: Meta, c: list[object]) -> n.DomainQuery:
        return self._domain_query("all", meta, c[0], c[1], c[2])

    def cq_set(self, meta: Meta, c: list[object]) -> n.CardQuery:
        return n.CardQuery(
            kind="set", source=_as_expr(c[0]), where=_as_expr(c[1]), span=self._span(meta)
        )

    def cq_count(self, meta: Meta, c: list[object]) -> n.CardQuery:
        where = _as_expr(c[1]) if len(c) > 1 and c[1] is not None else None
        return n.CardQuery(
            kind="count", source=_as_expr(c[0]), where=where, span=self._span(meta)
        )

    def cq_any(self, meta: Meta, c: list[object]) -> n.CardQuery:
        return n.CardQuery(
            kind="any", source=_as_expr(c[0]), where=_as_expr(c[1]), span=self._span(meta)
        )

    def cq_all(self, meta: Meta, c: list[object]) -> n.CardQuery:
        return n.CardQuery(
            kind="all", source=_as_expr(c[0]), where=_as_expr(c[1]), span=self._span(meta)
        )

    def agg_sum(self, meta: Meta, c: list[object]) -> n.Comprehension:
        # c: [body, zone_expr, where?]
        filt = _as_expr(c[2]) if len(c) > 2 and c[2] is not None else None
        return n.Comprehension(
            agg="sum",
            source=_as_expr(c[1]),
            binder="card",
            body=_as_expr(c[0]),
            where=filt,
            span=self._span(meta),
        )

    def agg_order(self, meta: Meta, c: list[object]) -> n.Comprehension:
        # c: [RANK_DIR, body, zone_expr, where?, default]
        filt = _as_expr(c[3]) if c[3] is not None else None
        direction = str(c[0])
        if direction not in RANK_DIRECTIONS:
            # Internal invariant, not a user diagnostic: the grammar's
            # RANK_DIR terminal and this set are out of sync.
            raise AssertionError(
                f"agg_order: unhandled RANK_DIR token {direction!r} — add it to "
                "RANK_DIRECTIONS"
            )
        return n.Comprehension(
            agg=direction,
            source=_as_expr(c[2]),
            binder="card",
            body=_as_expr(c[1]),
            where=filt,
            default=_as_expr(c[4]),
            span=self._span(meta),
        )

    def elif_clause(self, meta: Meta, c: list[object]) -> _Elif:
        return _Elif(_as_expr(c[0]), _as_expr(c[1]))

    def if_expr(self, meta: Meta, c: list[object]) -> n.IfExpr:
        elifs = tuple((e.cond, e.then) for e in c if isinstance(e, _Elif))
        exprs = [x for x in c if not isinstance(x, _Elif)]
        return n.IfExpr(
            cond=_as_expr(exprs[0]),
            then=_as_expr(exprs[1]),
            elifs=elifs,  # type: ignore[arg-type]
            otherwise=_as_expr(exprs[2]),
            span=self._span(meta),
        )

    def or_op(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("or", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def and_op(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("and", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def logical_not(self, meta: Meta, c: list[object]) -> n.Not:
        return n.Not(_as_expr(c[0]), span=self._span(meta))

    # The right-hand keywords of `is` / `is not` are a closed set: `none` and
    # `empty` dispatch to the absence/emptiness checks; anything else is
    # ordinary equality (BinOp, the same node `==` used to build).

    def compare_is(self, meta: Meta, c: list[object]) -> n.IsCheck | n.BinOp:
        rhs = c[1]
        if isinstance(rhs, n.NameRef) and rhs.name in ("none", "empty"):
            kind = "none" if rhs.name == "none" else "empty"
            return n.IsCheck(_as_expr(c[0]), kind, span=self._span(meta))
        return n.BinOp("is", _as_expr(c[0]), _as_expr(rhs), span=self._span(meta))

    def compare_is_not(self, meta: Meta, c: list[object]) -> n.IsCheck | n.BinOp:
        rhs = c[1]
        if isinstance(rhs, n.NameRef) and rhs.name in ("none", "empty"):
            kind = "not_none" if rhs.name == "none" else "not_empty"
            return n.IsCheck(_as_expr(c[0]), kind, span=self._span(meta))
        return n.BinOp("is_not", _as_expr(c[0]), _as_expr(rhs), span=self._span(meta))

    def players_where(self, meta: Meta, c: list[object]) -> n.PlayerQuery:
        return n.PlayerQuery(kind="set", where=_as_expr(c[0]), span=self._span(meta))

    def the_player_where(self, meta: Meta, c: list[object]) -> n.PlayerQuery:
        return n.PlayerQuery(kind="pick", where=_as_expr(c[0]), span=self._span(meta))

    def the_first_player_from_where(
        self, meta: Meta, c: list[object]
    ) -> n.PlayerQuery:
        # c: [start (sum-level), where]. The ring search: one inclusive lap
        # from `start` in the game's direction (nodes.PlayerQuery docstring).
        return n.PlayerQuery(
            kind="first_from",
            where=_as_expr(c[1]),
            start=_as_expr(c[0]),
            span=self._span(meta),
        )

    def number_players_where(self, meta: Meta, c: list[object]) -> n.PlayerQuery:
        return n.PlayerQuery(kind="count", where=_as_expr(c[0]), span=self._span(meta))

    def comp_op(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def compare(self, meta: Meta, c: list[object]) -> n.BinOp:
        op = str(c[1])
        if op in ("==", "!="):
            # Retired spellings (decisions.md "The expression register"): the
            # lexer still owns the tokens so the rejection can name the fix.
            word = "is" if op == "==" else "is not"
            raise DiagnosticError(
                Diagnostic(
                    Severity.ERROR,
                    f"`{op}` is not an operator in this language — equality "
                    f"is the word form: write `{word}`",
                    self._span(meta),
                )
            )
        return n.BinOp(op, _as_expr(c[0]), _as_expr(c[2]), span=self._span(meta))

    def membership(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("in", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def add(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("+", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def sub(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("-", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def mul(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("*", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def offset_by(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp(
            "offset_by", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta)
        )

    def divided_by_rounded_up(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp(
            "divided_by_rounded_up",
            _as_expr(c[0]),
            _as_expr(c[1]),
            span=self._span(meta),
        )

    def divided_by_rounded_down(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp(
            "divided_by_rounded_down",
            _as_expr(c[0]),
            _as_expr(c[1]),
            span=self._span(meta),
        )

    def div_symbol(self, meta: Meta, c: list[object]) -> n.BinOp:
        # Retired spellings (decisions.md "The expression register"): the
        # lexer still owns the tokens so the rejection can name the fix.
        # `//` is absent by necessity, not oversight — it introduces a
        # comment, so no builder can ever see it (the grammar's factor
        # comment and tests/test_divided_by.py's characterization).
        symbol = str(c[1])
        if symbol == "/":
            hint = (
                "division names its rounding: write "
                "`a divided by b rounded down` (floor) or "
                "`a divided by b rounded up` (ceiling)"
            )
        else:  # "%"
            hint = (
                "there is no remainder form; write "
                "`a - (a divided by b rounded down) * b`"
            )
        raise DiagnosticError(
            Diagnostic(
                Severity.ERROR,
                f"`{symbol}` is not an operator in this language — {hint}",
                self._span(meta),
            )
        )

    def arg_list(self, meta: Meta, c: list[object]) -> tuple[object, ...]:
        return tuple(c)

    def member(self, meta: Meta, c: list[object]) -> n.Member:
        return n.Member(obj=_as_expr(c[0]), field=str(c[1]), span=self._span(meta))

    def subscript(self, meta: Meta, c: list[object]) -> n.Subscript:
        return n.Subscript(
            obj=_as_expr(c[0]), index=_as_expr(c[1]), span=self._span(meta)
        )

    def field_init(self, meta: Meta, c: list[object]) -> n.FieldInit:
        return n.FieldInit(name=str(c[0]), value=_as_expr(c[1]), span=self._span(meta))

    def struct_lit(self, meta: Meta, c: list[object]) -> n.StructLit:
        return n.StructLit(
            type_name=str(c[0]),
            fields=tuple(x for x in c[1:] if isinstance(x, n.FieldInit)),
            span=self._span(meta),
        )

    def card_literal(self, meta: Meta, c: list[object]) -> n.CardLiteral:
        return n.CardLiteral(rank=str(c[0]), suit=str(c[1]), span=self._span(meta))

    def all_players(self, meta: Meta, c: list[object]) -> n.AllPlayers:
        return n.AllPlayers(span=self._span(meta))

    def choose_integer(self, meta: Meta, c: list[object]) -> n.Choose:
        # `up to N` and `excluding e` are optional; with maybe_placeholders
        # each group always fills its slot (c[2] the INT token, c[3] the
        # exclusion expression, None when absent), so a plain None-check does
        # it — matching the unconditional-index convention at `round_stmt`.
        ceiling: int | None = None
        if c[2] is not None:
            assert isinstance(c[2], Token)
            ceiling = int(c[2])
        return n.Choose(
            domain="integer",
            lo=_as_expr(c[0]),
            hi=_as_expr(c[1]),
            ceiling=ceiling,
            excluding=None if c[3] is None else _as_expr(c[3]),
            span=self._span(meta),
        )

    def call(self, meta: Meta, c: list[object]) -> n.Call:
        args = c[1] if len(c) > 1 and c[1] is not None else ()
        assert isinstance(args, tuple)
        return n.Call(func=str(c[0]), args=args, span=self._span(meta))

    def int_lit(self, meta: Meta, c: list[Token]) -> n.IntLit:
        return n.IntLit(int(c[0]), span=self._span(meta))

    def neg_int_lit(self, meta: Meta, c: list[Token]) -> n.IntLit:
        return n.IntLit(-int(c[0]), span=self._span(meta))

    def list_lit(self, meta: Meta, c: list[object]) -> n.ListLit:
        return n.ListLit(
            elements=tuple(_as_expr(x) for x in c), span=self._span(meta)
        )

    def str_lit(self, meta: Meta, c: list[Token]) -> n.StrLit:
        return n.StrLit(str(c[0])[1:-1], span=self._span(meta))

    def name_ref(self, meta: Meta, c: list[Token]) -> n.NameRef:
        return n.NameRef(str(c[0]), span=self._span(meta))

    def index_expr(self, meta: Meta, c: list[object]) -> object:
        return _as_expr(c[0])

    def zone_expr(self, meta: Meta, c: list[object]) -> object:
        base: object = n.NameRef(str(c[0]), span=self._span(meta))
        if len(c) > 1 and c[1] is not None:
            return n.Subscript(obj=base, index=_as_expr(c[1]), span=self._span(meta))  # type: ignore[arg-type]
        return base

    # --- top level ---

    def game(self, meta: Meta, c: list[object]) -> n.Game:
        name = str(c[0])
        players: n.PlayersSpec | None = None
        deck: _Deck | None = None
        pieces: _Pieces | None = None
        direction: str | None = None
        ranking: tuple[str, ...] = ()
        ranking_convention: str | None = None
        card_points: n.CardPointsTable | None = None
        trick_order: n.TrickOrder | None = None
        primitives: n.PrimitivesBlock | None = None
        trump: str | None = None
        teams: tuple[tuple[int, ...], ...] = ()
        max_length: int | None = None
        positions: tuple[n.PositionDecl, ...] = ()
        board: n.BoardDecl | None = None
        zones: tuple[n.ZoneDecl, ...] = ()
        state: n.StateBlock | None = None
        phases: list[n.Phase] = []
        uses: list[n.UsesDecl] = []
        winner: n.Winner | None = None
        loser: n.Loser | None = None

        # Every game clause except `phase` is single-valued; the grammar
        # (`game_item*`) accepts repeats, so keeping the last one would
        # silently discard the first (decisions.md "Surface totality"):
        # reject at the repeated clause. `merge_hint` distinguishes the
        # block clauses (whose declarations merge) from the scalar ones.
        seen: set[str] = set()

        # `span` is Optional only because AST nodes type it so; every node
        # this builder constructs carries one.
        def once(clause: str, span: Span | None, merge_hint: bool = False) -> None:
            if clause in seen:
                what, fix = (
                    (f"`{clause}` block", "merge the declarations into it")
                    if merge_hint
                    else (
                        f"`{clause}`",
                        "the repeat would silently replace the first; keep one",
                    )
                )
                raise DiagnosticError(
                    Diagnostic(
                        Severity.ERROR,
                        f"a game declares one {what} — {fix}",
                        span,
                    )
                )
            seen.add(clause)

        for item in c[1:]:
            if isinstance(item, n.PlayersSpec):
                once("players:", item.span)
                players = item
            elif isinstance(item, _Deck):
                once("cards:", item.span)
                deck = item
            elif isinstance(item, _Pieces):
                once("pieces:", item.span)
                pieces = item
            elif isinstance(item, _Direction):
                once("direction:", item.span)
                direction = item.value
            elif isinstance(item, _Ranking):
                once("ranking:", item.span)
                ranking = item.ranks
                ranking_convention = item.convention
            elif isinstance(item, n.CardPointsTable):
                once("card_points { }", item.span, merge_hint=True)
                card_points = item
            elif isinstance(item, n.TrickOrder):
                once("trick_order { }", item.span, merge_hint=True)
                trick_order = item
            elif isinstance(item, n.PrimitivesBlock):
                once("primitives { }", item.span, merge_hint=True)
                primitives = item
            elif isinstance(item, _Trump):
                once("trump:", item.span)
                trump = item.suit
            elif isinstance(item, _Teams):
                once("teams:", item.span)
                teams = item.teams
            elif isinstance(item, _MaxLength):
                once("max_length:", item.span)
                max_length = item.value
            elif isinstance(item, _Positions):
                once("positions { }", item.span, merge_hint=True)
                positions = item.positions
            elif isinstance(item, n.BoardDecl):
                once("board:", item.span)
                board = item
            elif isinstance(item, _Zones):
                once("zones { }", item.span, merge_hint=True)
                zones = item.zones
            elif isinstance(item, n.StateBlock):
                once("state { }", item.span, merge_hint=True)
                state = item
            elif isinstance(item, n.UsesDecl):
                # No `once`: a game uses as many libraries as it draws on. A
                # REPEATED name is still a defect (the second import is a no-op),
                # and is guarded in resolve, where the library names are known.
                uses.append(item)
            elif isinstance(item, n.Phase):
                phases.append(item)
            elif isinstance(item, n.Winner):
                once("winner:", item.span)
                winner = item
            elif isinstance(item, n.Loser):
                once("loser:", item.span)
                loser = item
            else:
                raise AssertionError(f"unexpected game item: {item!r}")

        # `players:` and a content clause (`cards:`/`pieces:`) are the
        # clauses the AST itself makes mandatory (`Game.players` /
        # `Game.deck` are non-optional), so this builder is the last layer
        # where their absence exists to report — the optionally-representable
        # mandatory clauses (`max_length:`, `winner:`/`loser:`) are guarded in
        # resolve instead. Bag-first so a game missing both hears about both
        # at once (resolve's `_raise_if_errors` idiom).
        bag = DiagnosticBag()
        game_span = self._span(meta)
        if players is None:
            bag.error(
                f"game '{name}' must declare `players: <n>` (or `players: "
                f"<lo> .. <hi>`) — the seat count that sizes every per-player "
                f"zone and the turn ring",
                game_span,
            )
        if deck is not None and pieces is not None:
            # Span on whichever clause appears later, as `once()` points at
            # the repeat.
            bag.error(
                "a game declares `cards:` or `pieces:`, not both — no game "
                "has witnessed needing both",
                pieces.span if pieces.span.start > deck.span.start else deck.span,
            )
        elif deck is None and pieces is None:
            bag.error(
                f"game '{name}' must declare `cards: <deck>` or `pieces: "
                f"<set>` — the components it is played with (e.g. `cards: "
                f"standard52`)",
                game_span,
            )
        if bag.has_errors:
            error = DiagnosticError(bag.items[0])
            if len(bag.items) > 1:
                error.add_note(bag.format())
            raise error
        # Shadow Guard for mypy narrowing only: the bag raise above is the
        # Owner Guard (players present, and exactly one content clause).
        assert players is not None
        content: _Deck | _Pieces | None = deck if deck is not None else pieces
        assert content is not None
        return n.Game(
            name=name,
            players=players,
            deck=content.name,
            content_flavor="card" if isinstance(content, _Deck) else "piece",
            zones=zones,
            direction=direction,
            ranking=ranking,
            ranking_convention=ranking_convention,
            card_points=card_points,
            trick_order=trick_order,
            primitives=primitives,
            trump=trump,
            teams=teams,
            positions=positions,
            board=board,
            max_length=max_length,
            state=state,
            phases=tuple(phases),
            winner=winner,
            loser=loser,
            rules=(),
            uses=tuple(uses),
            span=self._span(meta),
        )

    def parameter(self, meta: Meta, c: list[object]) -> n.Parameter:
        # c: NAME(param), payload_type string (carries a trailing `?` if nullable).
        # One builder for all four parameter-bearing constructs — move types,
        # functions, procedures, rules — because the grammar now has one
        # production for them. Per-construct type constraints stay in each
        # construct's own Owner Guard, not here.
        return n.Parameter(
            name=str(c[0]), type_name=str(c[1]), span=self._span(meta)
        )

    def move_when(self, meta: Meta, c: list[object]) -> _MoveWhen:
        return _MoveWhen(c[0])

    def move_effect(self, meta: Meta, c: list[object]) -> _MoveEffect:
        return _MoveEffect(tuple(_as_stmt(s) for s in c))

    def payload_plain(self, meta: Meta, c: list[object]) -> str:
        return str(c[0])

    def payload_optional(self, meta: Meta, c: list[object]) -> str:
        # A nullable payload type keeps its `?` in the name string; the type
        # registry strips it and resolves the inner type as optional.
        return str(c[0]) + "?"

    def outcome_case(self, meta: Meta, c: list[object]) -> n.OutcomeCase:
        # c: NAME(tag), then 0+ payload-type strings (a None placeholder stands in
        # for the absent optional group — filter to the real payload strings).
        payloads = tuple(x for x in c[1:] if isinstance(x, str) and not isinstance(x, Token))
        return n.OutcomeCase(tag=str(c[0]), payload_types=payloads, span=self._span(meta))

    def outcome_set(
        self, meta: Meta, c: list[n.OutcomeCase]
    ) -> tuple[n.OutcomeCase, ...]:
        return tuple(c)

    def define_def(self, meta: Meta, c: list[object]) -> n.DefineDef:
        name = str(c[0])
        cases = next(x for x in c if isinstance(x, tuple))
        body = tuple(
            _as_stmt(s)
            for s in c[1:]
            if s is not None and not isinstance(s, (str, tuple, Token))
        )
        return n.DefineDef(name=name, cases=cases, body=body, span=self._span(meta))

    def produce_stmt(self, meta: Meta, c: list[object]) -> n.Produce:
        # The optional payload group may leave a None placeholder; drop it.
        payloads = tuple(_as_expr(x) for x in c[1:] if x is not None)
        return n.Produce(tag=str(c[0]), payloads=payloads, span=self._span(meta))

    def produce_arm(self, meta: Meta, c: list[object]) -> n.ProduceArm:
        # c: NAME(tag), 0+ NAME binder tokens (or a None placeholder), then 0+
        # lowered statements. Binders are Tokens; body statements are nodes.
        tag = str(c[0])
        binders = tuple(str(x) for x in c[1:] if isinstance(x, Token))
        body = tuple(
            _as_stmt(s) for s in c[1:] if s is not None and not isinstance(s, Token)
        )
        return n.ProduceArm(tag=tag, binders=binders, body=body, span=self._span(meta))

    def produces_stmt(self, meta: Meta, c: list[object]) -> n.Produces:
        return n.Produces(
            define=str(c[0]),
            arms=tuple(x for x in c[1:] if isinstance(x, n.ProduceArm)),
            span=self._span(meta),
        )

    def continue_to(self, meta: Meta, c: list[object]) -> n.ContinueTo:
        return n.ContinueTo(phase=str(c[0]), span=self._span(meta))

    def skip_stmt(self, meta: Meta, c: list[object]) -> n.SkipToNextHand:
        return n.SkipToNextHand(span=self._span(meta))

    def move_type_def(self, meta: Meta, c: list[object]) -> n.MoveTypeDef:
        name = str(c[0])
        when_pred: object | None = None
        effect: tuple[object, ...] = ()
        for item in c[1:]:
            if isinstance(item, _MoveWhen):
                when_pred = None if isinstance(item.pred, _Always) else _as_expr(item.pred)
            elif isinstance(item, _MoveEffect):
                effect = item.body
        params = tuple(x for x in c if isinstance(x, n.Parameter))
        return n.MoveTypeDef(
            name=name,
            when=when_pred,  # type: ignore[arg-type]
            effect=effect,  # type: ignore[arg-type]
            params=params,
            span=self._span(meta),
        )

    def function_def(self, meta: Meta, c: list[object]) -> n.FunctionDef:
        # c: NAME, parameter* (n.Parameter), expr(body). The body is the last child.
        name = str(c[0])
        params = tuple(x for x in c if isinstance(x, n.Parameter))
        return n.FunctionDef(
            name=name, params=params, body=_as_expr(c[-1]), span=self._span(meta)
        )

    def procedure_def(self, meta: Meta, c: list[object]) -> n.ProcedureDef:
        # c: NAME, move_param* (n.Parameter), statement*. `maybe_placeholders`
        # leaves a None for an absent optional group; `_as_stmt` never sees it
        # because the params filter is by type and the body filter drops it.
        name = str(c[0])
        params = tuple(x for x in c if isinstance(x, n.Parameter))
        body = tuple(
            _as_stmt(s)
            for s in c[1:]
            if s is not None and not isinstance(s, n.Parameter)
        )
        return n.ProcedureDef(
            name=name, params=params, body=body, span=self._span(meta)
        )

    def run_stmt(self, meta: Meta, c: list[object]) -> n.RunStmt:
        name = str(c[0])
        args = tuple(_as_expr(a) for a in c[1:] if a is not None)
        return n.RunStmt(name=name, args=args, span=self._span(meta))

    def start(self, meta: Meta, c: list[object]) -> n.Game:
        # `start: top_item+` accepts any mix of definitions, so game-count
        # errors are reachable from source: without these Owner Guards a source
        # with no game would fail as an index error rather than a diagnostic,
        # and a second game would be silently discarded (decisions.md "Surface
        # totality"). One game per source.
        games = [x for x in c if isinstance(x, n.Game)]
        if not games:
            raise DiagnosticError(
                Diagnostic(
                    Severity.ERROR,
                    "source declares no `game { }` block — a cardlang source "
                    "is one game plus its supporting definitions",
                    self._span(meta),
                )
            )
        if len(games) > 1:
            raise DiagnosticError(
                Diagnostic(
                    Severity.ERROR,
                    f"source declares {len(games)} `game {{ }}` blocks — a "
                    "cardlang source is one game; move the others to their "
                    "own files",
                    games[1].span,
                )
            )
        game = games[0]
        rules = tuple(x for x in c if isinstance(x, n.RuleDef))
        move_types = tuple(x for x in c if isinstance(x, n.MoveTypeDef))
        types = tuple(x for x in c if isinstance(x, n.TypeDef))
        defines = tuple(x for x in c if isinstance(x, n.DefineDef))
        functions = tuple(x for x in c if isinstance(x, n.FunctionDef))
        procedures = tuple(x for x in c if isinstance(x, n.ProcedureDef))
        return replace(
            game,
            rules=rules,
            move_types=move_types,
            types=types,
            defines=defines,
            functions=functions,
            procedures=procedures,
        )


def _as_expr(value: object) -> n.Expr:
    """Assert a transformer child is an expression node (helps mypy + catches
    transform gaps loudly)."""
    assert not isinstance(value, (Tree, Token)), f"unlowered node: {value!r}"
    return value  # type: ignore[return-value]


def _as_stmt(value: object) -> n.Stmt:
    assert not isinstance(value, (Tree, Token)), f"unlowered node: {value!r}"
    return value  # type: ignore[return-value]


# A clause that is legal SOMEWHERE but not where it was written can only be
# reported by the parser as "no terminal matches", which names neither the
# mistake nor the fix. Keyed by the first word of the offending line, since
# that is what the designer has their cursor on.
#
# The hint states WHERE THE CLAUSE BELONGS. It deliberately does not say where
# the author currently is, because it cannot know: the parser reports a line,
# not an enclosing construct, so the same entry fires for a misplaced clause
# and for a clause in the right place with a bad argument list. An earlier
# wording asserted the container ("belongs to a `mode`, not a `phase`") and so
# told a designer already inside a phase to move the clause into a phase. Every
# entry must therefore read as true wherever it fires — a reminder of the
# clause's home, never a diagnosis of the author's position.
#: A clause keyword mapped to (the parse entry point whose text the hint's
#: sentence is TRUE of, or None for every one; the hint itself).
#:
#: The scope column is what keeps a hint from being read as a diagnosis of
#: something it cannot observe: the `primitives` sentence says a LIBRARY may
#: not declare the block, which is a fact about library text and false advice
#: appended to a game's own syntax error. A hint whose sentence holds
#: everywhere carries None and fires everywhere.
_PARSE_HINTS: dict[str, tuple[str | None, str]] = {
    "transition_to": (
        None,
        " — `transition_to:` is a mode clause: it declares an exit from a "
        "`mode NAME { }`, and its target is a sibling mode",
    ),
    "legal_moves": (
        None,
        " — `legal_moves:` is a phase clause: a mode toggles rules, never the "
        "move menu, so a mode body takes `active_rules:`/`transition_to:` only",
    ),
    "primitives": (
        "library",
        " — `primitives { }` is a game clause: a Primitive's meaning belongs "
        "to ONE game, so a library — which several games import — may not "
        "declare one; write the block in the game",
    ),
}


def _parse_hint(text: str, line: int, column: int, start: str) -> str:
    """Two probes, because Lark points at either end of the offending clause.

    A clause on its own line fails at the clause keyword itself; one written
    inline after `{` fails a few characters in. So try the identifier AT the
    reported column first, then fall back to the line's leading word.

    `start` is the entry point the text was parsed under, and a hint scoped to
    another one is withheld rather than qualified: a sentence a reader cannot
    act on is worse than no sentence.
    """
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return ""

    def hint_for(keyword: str) -> str | None:
        row = _PARSE_HINTS.get(keyword)
        if row is None:
            return None
        scope, hint = row
        return hint if scope is None or scope == start else ""

    source = lines[line - 1]
    at_column = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[max(0, column - 1) :])
    if at_column:
        found = hint_for(at_column.group())
        if found is not None:
            return found
    head = source.strip().split(":")[0].split()
    return (hint_for(head[0]) or "") if head else ""


def parse_to_tree(
    text: str, source_name: str, line_offset: int = 0, start: str = "start"
) -> Tree[Token]:
    """Parse DSL ``text`` to a raw Lark tree, raising a span-located diagnostic
    on a syntax error. The grammar-acceptance entry point."""
    try:
        tree = _parser().parse(text, start=start)
    except UnexpectedInput as exc:
        line = getattr(exc, "line", 1) + line_offset
        column = getattr(exc, "column", 1)
        span = Span(source_name, 0, 0, line, column)
        message = f"syntax error: {exc!s}".splitlines()[0]
        hint = _parse_hint(text, getattr(exc, "line", 1), column, start)
        raise DiagnosticError(
            Diagnostic(Severity.ERROR, f"{message}{hint}", span)
        ) from exc
    assert isinstance(tree, Tree)
    return tree


def _transform(builder: _Builder, tree: Tree[Token]) -> object:
    """Run ``builder`` over ``tree``, unwrapping Lark's ``VisitError`` so a
    builder-raised diagnostic (e.g. a duplicate `state { }` block, or the
    `==`-rejection) surfaces as itself rather than as an opaque wrapper."""
    try:
        return builder.transform(tree)
    except VisitError as exc:
        if isinstance(exc.orig_exc, DiagnosticError):
            raise exc.orig_exc from None
        raise


def parse_stdlib_rules(text: str, source_name: str) -> tuple[n.RuleDef, ...]:
    """Parse a standard-library rules fragment (rule definitions with no
    enclosing game) into RuleDef nodes, spans mapped to ``source_name``."""
    tree = parse_to_tree(text, source_name, start="stdlib_rules")
    result = _transform(_Builder(source_name, 0), tree)
    assert isinstance(result, tuple)
    assert all(isinstance(r, n.RuleDef) for r in result)
    return result


def parse_library(text: str, source_name: str) -> n.Library:
    """Parse a family-library file (`library <name> { ... }`, no enclosing game)
    into a Library node, spans mapped to ``source_name`` — so a diagnostic raised
    inside library text names the library file, not the game that used it."""
    tree = parse_to_tree(text, source_name, start="library")
    result = _transform(_Builder(source_name, 0), tree)
    assert isinstance(result, n.Library)
    return result


@cache
def _parse_text_cached(text: str, source_name: str, line_offset: int) -> n.Game:
    """The memoized body of :func:`parse_text`. Takes ``line_offset``
    positionally and without a default so one call site cannot miss another's
    entry over an argument spelling (``lru_cache`` keys on the call shape).

    Unbounded deliberately: a corpus game is re-parsed dozens of times across
    a suite run, interleaved with far more one-shot snippets from the
    rejection and typecheck-error tests, so any small bound would let that
    churn evict exactly the entries worth keeping. That trade suits every
    caller this has today — suite, CLI, harnesses — because all are
    short-lived. It would NOT suit a long-lived one: a caller that re-parses
    edited text (an editor session, a watch mode) mints a fresh entry per
    edit and never reuses it, so it must bound or clear this cache."""
    tree = parse_to_tree(text, source_name, line_offset)
    result = _transform(_Builder(source_name, line_offset), tree)
    assert isinstance(result, n.Game)
    return result


def parse_text(text: str, source_name: str, line_offset: int = 0) -> n.Game:
    """Parse DSL ``text`` into a :class:`~cardlang.ast.nodes.Game` AST."""
    return _parse_text_cached(text, source_name, line_offset)


def parse_block(block: FencedBlock) -> n.Game:
    """Parse a :class:`FencedBlock`, mapping spans back to its file."""
    return parse_text(block.text, block.source_name, line_offset=block.start_line - 1)
