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
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput
from lark.tree import Meta
from lark.visitors import Transformer, v_args

from cardlang.ast import nodes as n
from cardlang.diagnostics import Diagnostic, DiagnosticError, Severity, Span
from cardlang.extract import FencedBlock


# --- private intermediate markers (never leave this module) ---


@dataclass(frozen=True, slots=True)
class _Deck:
    name: str


@dataclass(frozen=True, slots=True)
class _Direction:
    value: str


@dataclass(frozen=True, slots=True)
class _Ranking:
    ranks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Zones:
    zones: tuple[n.ZoneDecl, ...]


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
class _SelectMode:
    mode: str


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
        return c[0]

    def direction(self, meta: Meta, c: list[Token]) -> _Direction:
        return _Direction(str(c[0]))

    def cards(self, meta: Meta, c: list[Token]) -> _Deck:
        return _Deck(str(c[0]))

    def ranking(self, meta: Meta, c: list[object]) -> _Ranking:
        return _Ranking(tuple(str(r) for r in c))

    def card_rank(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def winner(self, meta: Meta, c: list[Token]) -> n.Winner:
        return n.Winner(rank_dir=str(c[0]), target=str(c[1]), span=self._span(meta))

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
        return _Zones(tuple(c))

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

    # --- phases ---

    def phase_repeats(self, meta: Meta, c: list[object]) -> n.PhaseQualifier:
        return n.PhaseQualifier("repeats", _as_expr(c[0]), span=self._span(meta))

    def phase_when(self, meta: Meta, c: list[object]) -> n.PhaseQualifier:
        return n.PhaseQualifier("when", _as_expr(c[0]), span=self._span(meta))

    def phase(self, meta: Meta, c: list[object]) -> n.Phase:
        name = str(c[0])
        qualifier = c[1] if isinstance(c[1], n.PhaseQualifier) else None
        items = tuple(c[2:])
        return n.Phase(name=name, qualifier=qualifier, items=items, span=self._span(meta))  # type: ignore[arg-type]

    def active_rules(self, meta: Meta, c: list[object]) -> n.ActiveRules:
        refs = tuple(r for r in c if isinstance(r, n.RuleRef))
        return n.ActiveRules(refs=refs, span=self._span(meta))

    def rule_plain(self, meta: Meta, c: list[Token]) -> n.RuleRef:
        return n.RuleRef(str(c[0]), "plain", span=self._span(meta))

    def rule_add(self, meta: Meta, c: list[Token]) -> n.RuleRef:
        return n.RuleRef(str(c[0]), "add", span=self._span(meta))

    def rule_remove(self, meta: Meta, c: list[Token]) -> n.RuleRef:
        return n.RuleRef(str(c[0]), "remove", span=self._span(meta))

    def rule_override(self, meta: Meta, c: list[Token]) -> n.RuleRef:
        return n.RuleRef(str(c[0]), "override", span=self._span(meta))

    def legal_moves(self, meta: Meta, c: list[object]) -> n.LegalMoves:
        names = tuple(str(x) for x in c if x is not None)
        return n.LegalMoves(names=names, span=self._span(meta))

    def transition_to(self, meta: Meta, c: list[object]) -> n.TransitionTo:
        assert isinstance(c[1], n.MoveEvent)
        return n.TransitionTo(target=str(c[0]), event=c[1], span=self._span(meta))

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

    def move_from(self, meta: Meta, c: list[object]) -> n.Movement:
        assert isinstance(c[1], _Selection) and isinstance(c[3], _Dest)
        vis = c[4].expr if len(c) > 4 and isinstance(c[4], _Vis) else None
        return n.Movement(
            verb=str(c[0]),
            mode=c[1].mode,
            amount=c[1].amount,  # type: ignore[arg-type]
            item=c[1].item,
            source=_as_expr(c[2]),
            dest=c[3].zone,  # type: ignore[arg-type]
            dest_each=c[3].each,
            visibility=vis,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def move_in(self, meta: Meta, c: list[object]) -> n.Movement:
        assert isinstance(c[1], _Selection)
        vis = c[3].expr if len(c) > 3 and isinstance(c[3], _Vis) else None
        return n.Movement(
            verb=str(c[0]),
            mode=c[1].mode,
            amount=c[1].amount,  # type: ignore[arg-type]
            item=c[1].item,
            source=_as_expr(c[2]),
            dest=None,
            dest_each=False,
            visibility=vis,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def shuffle_op(self, meta: Meta, c: list[object]) -> n.EpistemicOp:
        return n.EpistemicOp(op="shuffle", target=_as_expr(c[0]), span=self._span(meta))

    def name_list(self, meta: Meta, c: list[Token]) -> tuple[str, ...]:
        return tuple(str(x) for x in c)

    def rotate_stmt(self, meta: Meta, c: list[object]) -> n.RotateStmt:
        assert isinstance(c[1], tuple)
        return n.RotateStmt(var=str(c[0]), values=c[1], span=self._span(meta))

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
        return n.RepeatUntil(cond=cond, body=body, span=self._span(meta))

    def named_arg(self, meta: Meta, c: list[object]) -> n.NamedArg:
        return n.NamedArg(name=str(c[0]), value=c[1], span=self._span(meta))  # type: ignore[arg-type]

    def instantiate(self, meta: Meta, c: list[object]) -> n.Instantiate:
        args = tuple(a for a in c[1:] if isinstance(a, n.NamedArg))
        return n.Instantiate(mechanic=str(c[0]), args=args, span=self._span(meta))

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
            name=c[0].name,
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

    def rule_def(self, meta: Meta, c: list[object]) -> n.RuleDef:
        name = str(c[0])
        constrains: str | None = None
        applies: n.AppliesWhen | None = None
        demands: n.Demands | None = None
        if_imp: object | None = None
        for clause in c[1:]:
            if isinstance(clause, _Constrains):
                constrains = clause.move_type
            elif isinstance(clause, n.AppliesWhen):
                applies = clause
            elif isinstance(clause, n.Demands):
                demands = clause
            elif isinstance(clause, _IfImpossible):
                if_imp = clause.expr
            else:
                raise AssertionError(f"unexpected rule clause: {clause!r}")
        return n.RuleDef(
            name=name,
            constrains=constrains,
            applies_when=applies,
            demands=demands,
            if_impossible=if_imp,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    # --- expressions ---

    def exists(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return n.Quantifier(
            "any", str(c[0]), str(c[1]), _as_expr(c[2]), span=self._span(meta)
        )

    def forall(self, meta: Meta, c: list[object]) -> n.Quantifier:
        return n.Quantifier(
            "all", str(c[0]), str(c[1]), _as_expr(c[2]), span=self._span(meta)
        )

    def comprehension(self, meta: Meta, c: list[object]) -> n.Comprehension:
        return n.Comprehension(
            agg=str(c[0]),
            source=_as_expr(c[1]),
            binder=str(c[2]),
            body=_as_expr(c[3]),
            span=self._span(meta),
        )

    def lambda_expr(self, meta: Meta, c: list[object]) -> n.Lambda:
        return n.Lambda(param=str(c[0]), body=_as_expr(c[1]), span=self._span(meta))

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

    def is_none(self, meta: Meta, c: list[object]) -> n.IsCheck:
        return n.IsCheck(_as_expr(c[0]), "none", span=self._span(meta))

    def is_not_none(self, meta: Meta, c: list[object]) -> n.IsCheck:
        return n.IsCheck(_as_expr(c[0]), "not_none", span=self._span(meta))

    def is_empty(self, meta: Meta, c: list[object]) -> n.IsCheck:
        return n.IsCheck(_as_expr(c[0]), "empty", span=self._span(meta))

    def comp_op(self, meta: Meta, c: list[Token]) -> str:
        return str(c[0])

    def compare(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp(str(c[1]), _as_expr(c[0]), _as_expr(c[2]), span=self._span(meta))

    def add(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("+", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def sub(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp("-", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta))

    def offset_by(self, meta: Meta, c: list[object]) -> n.BinOp:
        return n.BinOp(
            "offset_by", _as_expr(c[0]), _as_expr(c[1]), span=self._span(meta)
        )

    def arg_list(self, meta: Meta, c: list[object]) -> tuple[object, ...]:
        return tuple(c)

    def method_call(self, meta: Meta, c: list[object]) -> n.MethodCall:
        args = c[2] if len(c) > 2 and c[2] is not None else ()
        assert isinstance(args, tuple)
        return n.MethodCall(
            obj=_as_expr(c[0]), method=str(c[1]), args=args, span=self._span(meta)
        )

    def member(self, meta: Meta, c: list[object]) -> n.Member:
        return n.Member(obj=_as_expr(c[0]), field=str(c[1]), span=self._span(meta))

    def subscript(self, meta: Meta, c: list[object]) -> n.Subscript:
        return n.Subscript(
            obj=_as_expr(c[0]), index=_as_expr(c[1]), span=self._span(meta)
        )

    def card_literal(self, meta: Meta, c: list[object]) -> n.CardLiteral:
        return n.CardLiteral(rank=str(c[0]), suit=str(c[1]), span=self._span(meta))

    def all_players(self, meta: Meta, c: list[object]) -> n.AllPlayers:
        return n.AllPlayers(span=self._span(meta))

    def call(self, meta: Meta, c: list[object]) -> n.Call:
        args = c[1] if len(c) > 1 and c[1] is not None else ()
        assert isinstance(args, tuple)
        return n.Call(func=str(c[0]), args=args, span=self._span(meta))

    def int_lit(self, meta: Meta, c: list[Token]) -> n.IntLit:
        return n.IntLit(int(c[0]), span=self._span(meta))

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
        deck: str | None = None
        direction: str | None = None
        ranking: tuple[str, ...] = ()
        zones: tuple[n.ZoneDecl, ...] = ()
        state: n.StateBlock | None = None
        phases: list[n.Phase] = []
        winner: n.Winner | None = None
        for item in c[1:]:
            if isinstance(item, n.PlayersSpec):
                players = item
            elif isinstance(item, _Deck):
                deck = item.name
            elif isinstance(item, _Direction):
                direction = item.value
            elif isinstance(item, _Ranking):
                ranking = item.ranks
            elif isinstance(item, _Zones):
                zones = item.zones
            elif isinstance(item, n.StateBlock):
                state = item
            elif isinstance(item, n.Phase):
                phases.append(item)
            elif isinstance(item, n.Winner):
                winner = item
            else:
                raise AssertionError(f"unexpected game item: {item!r}")
        assert players is not None and deck is not None
        return n.Game(
            name=name,
            players=players,
            deck=deck,
            zones=zones,
            direction=direction,
            ranking=ranking,
            state=state,
            phases=tuple(phases),
            winner=winner,
            rules=(),
            span=self._span(meta),
        )

    def start(self, meta: Meta, c: list[object]) -> n.Game:
        game = next(x for x in c if isinstance(x, n.Game))
        rules = tuple(x for x in c if isinstance(x, n.RuleDef))
        return replace(game, rules=rules)


def _as_expr(value: object) -> n.Expr:
    """Assert a transformer child is an expression node (helps mypy + catches
    transform gaps loudly)."""
    assert not isinstance(value, (Tree, Token)), f"unlowered node: {value!r}"
    return value  # type: ignore[return-value]


def _as_stmt(value: object) -> n.Stmt:
    assert not isinstance(value, (Tree, Token)), f"unlowered node: {value!r}"
    return value  # type: ignore[return-value]


def parse_to_tree(text: str, source_name: str, line_offset: int = 0) -> Tree[Token]:
    """Parse DSL ``text`` to a raw Lark tree, raising a span-located diagnostic
    on a syntax error. The grammar-acceptance entry point."""
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


def parse_text(text: str, source_name: str, line_offset: int = 0) -> n.Game:
    """Parse DSL ``text`` into a :class:`~cardlang.ast.nodes.Game` AST."""
    tree = parse_to_tree(text, source_name, line_offset)
    return _Builder(source_name, line_offset).transform(tree)


def parse_block(block: FencedBlock) -> n.Game:
    """Parse a :class:`FencedBlock`, mapping spans back to its file."""
    return parse_text(block.text, block.source_name, line_offset=block.start_line - 1)
