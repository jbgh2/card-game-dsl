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
              :class:`Span`. No semantic claims — names are unclassified
              (``NameRef.ref_kind`` is ``None``) and nothing is typed.
Now illegal:  ill-formed syntax; it cannot reach any later pass.
Verified by:  the grammar-ambiguity check (tests/test_grammar_ambiguity.py)
              and the per-construct parse tests.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput, VisitError
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
class _Trump:
    suit: str


@dataclass(frozen=True, slots=True)
class _Partnerships:
    teams: tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class _MaxLength:
    value: int


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
        # `start` is a game file; `library_rules` is the stdlib rules fragment
        # (rule definitions with no enclosing game).
        start=["start", "library_rules"],
    )


# The grammar's RANK_DIR terminal (`cardlang.lark`, "lowest" | "highest"),
# mapped to the Comprehension `agg` spelling it lowers to. Exhaustive by
# construction: `agg_order` below raises loudly on any key not present here,
# and `test_rank_dir_set_is_pinned` (test_comprehension_aggregators.py)
# reconciles this set against the grammar terminal so a new RANK_DIR token
# cannot land uncovered.
RANK_DIR_TO_AGG: dict[str, str] = {"highest": "max", "lowest": "min"}


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

    def trump(self, meta: Meta, c: list[Token]) -> _Trump:
        return _Trump(str(c[0]))

    def team_spec(self, meta: Meta, c: list[Token]) -> tuple[int, ...]:
        return tuple(int(x) for x in c)

    def partnerships(self, meta: Meta, c: list[object]) -> _Partnerships:
        teams = tuple(t for t in c if isinstance(t, tuple))
        return _Partnerships(teams)

    def max_length(self, meta: Meta, c: list[Token]) -> _MaxLength:
        return _MaxLength(int(c[0]))

    def winner(self, meta: Meta, c: list[Token]) -> n.Winner:
        return n.Winner(rank_dir=str(c[0]), target=str(c[1]), span=self._span(meta))

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
        return n.PhaseQualifier("repeats", _as_expr(c[0]), span=self._span(meta))

    def phase_when(self, meta: Meta, c: list[object]) -> n.PhaseQualifier:
        return n.PhaseQualifier("when", _as_expr(c[0]), span=self._span(meta))

    def phase_outcome(self, meta: Meta, c: list[object]) -> tuple[n.VariantCase, ...]:
        # `-> outcome { ... }`: unwrap to the variant_set tuple.
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
        return n.LegalMoves(names=names, span=self._span(meta))

    def before_each(self, meta: Meta, c: list[object]) -> n.BeforeEach:
        return n.BeforeEach(body=tuple(_as_stmt(s) for s in c), span=self._span(meta))

    def after_each(self, meta: Meta, c: list[object]) -> n.AfterEach:
        return n.AfterEach(body=tuple(_as_stmt(s) for s in c), span=self._span(meta))

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
        sel = next(x for x in c if isinstance(x, _Selection))
        dest = next(x for x in c if isinstance(x, _Dest))
        vis = next((x.expr for x in c if isinstance(x, _Vis)), None)
        dist = next((x.mode for x in c if isinstance(x, _Dist)), None)
        filt = next((x.expr for x in c if isinstance(x, _Where)), None)
        return n.Movement(
            verb=str(c[0]),
            mode=sel.mode,
            amount=sel.amount,  # type: ignore[arg-type]
            item=sel.item,
            source=_as_expr(c[2]),  # zone_expr is the 3rd positional child
            dest=dest.zone,  # type: ignore[arg-type]
            dest_each=dest.each,
            distribution=dist,
            filter=filt,  # type: ignore[arg-type]
            visibility=vis,  # type: ignore[arg-type]
            span=self._span(meta),
        )

    def dist_equally(self, meta: Meta, c: list[object]) -> _Dist:
        return _Dist("as_equally_as_possible")

    def where_clause(self, meta: Meta, c: list[object]) -> _Where:
        return _Where(_as_expr(c[0]))

    def move_gather(self, meta: Meta, c: list[object]) -> n.Movement:
        assert isinstance(c[1], _Selection) and isinstance(c[2], _Dest)
        vis = c[3].expr if len(c) > 3 and isinstance(c[3], _Vis) else None
        return n.Movement(
            verb=str(c[0]),
            mode=c[1].mode,
            amount=c[1].amount,  # type: ignore[arg-type]
            item=c[1].item,
            source=None,
            dest=c[2].zone,  # type: ignore[arg-type]
            dest_each=c[2].each,
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

    def reveal_op(self, meta: Meta, c: list[object]) -> n.EpistemicOp:
        # The filter is an ordinary predicate with `card` bound per candidate
        # (a lambda during the register transition).
        filt = _as_expr(c[1]) if len(c) > 1 and c[1] is not None else None
        return n.EpistemicOp(
            op="reveal", target=_as_expr(c[0]), filter=filt, span=self._span(meta)
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
        return n.RepeatUntil(cond=cond, body=body, span=self._span(meta))

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

    def named_arg(self, meta: Meta, c: list[object]) -> n.NamedArg:
        return n.NamedArg(name=str(c[0]), value=c[1], span=self._span(meta))  # type: ignore[arg-type]

    def offer(self, meta: Meta, c: list[object]) -> n.Offer:
        player = _as_expr(c[0])
        names = tuple(str(x) for x in c[1:])
        return n.Offer(player=player, move_types=names, span=self._span(meta))

    def round_stmt(self, meta: Meta, c: list[object]) -> n.Round:
        # c: [NAME(move_type), expr(leader), expr(participants), NAME(source),
        #     NAME(into), NAME(outcome), expr(trump)?, NAME(early)?]
        # With maybe_placeholders=True, len(c)==8 always; c[6]/c[7] are None when absent.
        trump = _as_expr(c[6]) if c[6] is not None else None
        early = str(c[7]) if c[7] is not None else None
        return n.Round(
            move_type=str(c[0]),
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            source_zone=str(c[3]),
            play_zone=str(c[4]),
            outcome_fn=str(c[5]),
            trump=trump,
            early_termination=early,
            span=self._span(meta),
        )

    def auction_moves(self, meta: Meta, c: list[object]) -> tuple[str, ...]:
        return tuple(str(x) for x in c)

    def auction_stmt(self, meta: Meta, c: list[object]) -> n.Round:
        # c: [tuple(move_types), expr(leader), expr(participants), NAME(order)?,
        #     expr(termination), NAME(outcome)?]. The auction/betting form leaves the
        #     trick-specific fields None; both the `order` clause (c[3], default ring)
        #     and `outcome` (c[5], betting omits it) are None placeholders when absent.
        move_types = c[0]
        assert isinstance(move_types, tuple)
        return n.Round(
            move_type=None,
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            source_zone=None,
            play_zone=None,
            outcome_fn=str(c[5]) if c[5] is not None else None,
            trump=None,
            move_types=move_types,
            termination=_as_expr(c[4]),
            order_mode=str(c[3]) if c[3] is not None else None,
            span=self._span(meta),
        )

    def climb_stmt(self, meta: Meta, c: list[object]) -> n.Round:
        # c: [NAME(move_type), expr(leader), expr(participants), NAME(source),
        #     NAME(into), NAME(combinations), NAME(follows), expr(termination)].
        # The climbing form keeps the trick zones (source/into) but names the
        # combination-engine queries instead of an outcome function; the winner is
        # the loop's last player. `combos_fn is not None` marks the form.
        return n.Round(
            move_type=str(c[0]),
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            source_zone=str(c[3]),
            play_zone=str(c[4]),
            outcome_fn=None,
            trump=None,
            combos_fn=str(c[5]),
            follows_fn=str(c[6]),
            termination=_as_expr(c[7]),
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

    def rule_params(self, meta: Meta, c: list[n.MoveParam]) -> tuple[n.MoveParam, ...]:
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

    def library_rules(self, meta: Meta, c: list[object]) -> tuple[n.RuleDef, ...]:
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

    def cq_set(self, meta: Meta, c: list[object]) -> n.CardQuery:
        return n.CardQuery(
            kind="set", source=_as_expr(c[0]), pred=_as_expr(c[1]), span=self._span(meta)
        )

    def cq_count(self, meta: Meta, c: list[object]) -> n.CardQuery:
        pred = _as_expr(c[1]) if len(c) > 1 and c[1] is not None else None
        return n.CardQuery(
            kind="count", source=_as_expr(c[0]), pred=pred, span=self._span(meta)
        )

    def cq_any(self, meta: Meta, c: list[object]) -> n.CardQuery:
        return n.CardQuery(
            kind="any", source=_as_expr(c[0]), pred=_as_expr(c[1]), span=self._span(meta)
        )

    def cq_all(self, meta: Meta, c: list[object]) -> n.CardQuery:
        return n.CardQuery(
            kind="all", source=_as_expr(c[0]), pred=_as_expr(c[1]), span=self._span(meta)
        )

    def agg_sum(self, meta: Meta, c: list[object]) -> n.Comprehension:
        # c: [body, zone_expr, where?]
        filt = _as_expr(c[2]) if len(c) > 2 and c[2] is not None else None
        return n.Comprehension(
            agg="sum",
            source=_as_expr(c[1]),
            binder="card",
            body=_as_expr(c[0]),
            filter=filt,
            span=self._span(meta),
        )

    def agg_order(self, meta: Meta, c: list[object]) -> n.Comprehension:
        # c: [RANK_DIR, body, zone_expr, where?, default]
        filt = _as_expr(c[3]) if c[3] is not None else None
        direction = str(c[0])
        if direction not in RANK_DIR_TO_AGG:
            # Internal invariant, not a user diagnostic: the grammar's
            # RANK_DIR terminal and this mapping are out of sync.
            raise AssertionError(
                f"agg_order: unhandled RANK_DIR token {direction!r} — add it to "
                "RANK_DIR_TO_AGG"
            )
        return n.Comprehension(
            agg=RANK_DIR_TO_AGG[direction],
            source=_as_expr(c[2]),
            binder="card",
            body=_as_expr(c[1]),
            filter=filt,
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
        return n.BinOp("==", _as_expr(c[0]), _as_expr(rhs), span=self._span(meta))

    def compare_is_not(self, meta: Meta, c: list[object]) -> n.IsCheck | n.BinOp:
        rhs = c[1]
        if isinstance(rhs, n.NameRef) and rhs.name in ("none", "empty"):
            kind = "not_none" if rhs.name == "none" else "not_empty"
            return n.IsCheck(_as_expr(c[0]), kind, span=self._span(meta))
        return n.BinOp("!=", _as_expr(c[0]), _as_expr(rhs), span=self._span(meta))

    def players_where(self, meta: Meta, c: list[object]) -> n.PlayerQuery:
        return n.PlayerQuery(kind="set", pred=_as_expr(c[0]), span=self._span(meta))

    def the_player_where(self, meta: Meta, c: list[object]) -> n.PlayerQuery:
        return n.PlayerQuery(kind="pick", pred=_as_expr(c[0]), span=self._span(meta))

    def number_players_where(self, meta: Meta, c: list[object]) -> n.PlayerQuery:
        return n.PlayerQuery(kind="count", pred=_as_expr(c[0]), span=self._span(meta))

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
        # `up to N` is optional; with maybe_placeholders the group always fills
        # c[2] (the INT token, or None when absent), so a plain None-check does
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
        deck: str | None = None
        direction: str | None = None
        ranking: tuple[str, ...] = ()
        trump: str | None = None
        partnerships: tuple[tuple[int, ...], ...] = ()
        max_length: int | None = None
        zones: tuple[n.ZoneDecl, ...] = ()
        state: n.StateBlock | None = None
        phases: list[n.Phase] = []
        winner: n.Winner | None = None
        loser: n.Loser | None = None
        for item in c[1:]:
            if isinstance(item, n.PlayersSpec):
                players = item
            elif isinstance(item, _Deck):
                deck = item.name
            elif isinstance(item, _Direction):
                direction = item.value
            elif isinstance(item, _Ranking):
                ranking = item.ranks
            elif isinstance(item, _Trump):
                trump = item.suit
            elif isinstance(item, _Partnerships):
                partnerships = item.teams
            elif isinstance(item, _MaxLength):
                max_length = item.value
            elif isinstance(item, _Zones):
                zones = item.zones
            elif isinstance(item, n.StateBlock):
                if state is not None:
                    # Keeping the last block would silently discard the first's
                    # declarations (decisions.md "Surface totality"): reject.
                    raise DiagnosticError(
                        Diagnostic(
                            Severity.ERROR,
                            "a game declares one `state { }` block — merge the "
                            "declarations into it",
                            item.span,
                        )
                    )
                state = item
            elif isinstance(item, n.Phase):
                phases.append(item)
            elif isinstance(item, n.Winner):
                winner = item
            elif isinstance(item, n.Loser):
                loser = item
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
            trump=trump,
            partnerships=partnerships,
            max_length=max_length,
            state=state,
            phases=tuple(phases),
            winner=winner,
            loser=loser,
            rules=(),
            span=self._span(meta),
        )

    def move_param(self, meta: Meta, c: list[object]) -> n.MoveParam:
        # c: NAME(param), payload_type string (carries a trailing `?` if nullable).
        return n.MoveParam(
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

    def variant_case(self, meta: Meta, c: list[object]) -> n.VariantCase:
        # c: NAME(tag), then 0+ payload-type strings (a None placeholder stands in
        # for the absent optional group — filter to the real payload strings).
        payloads = tuple(x for x in c[1:] if isinstance(x, str) and not isinstance(x, Token))
        return n.VariantCase(tag=str(c[0]), payload_types=payloads, span=self._span(meta))

    def variant_set(
        self, meta: Meta, c: list[n.VariantCase]
    ) -> tuple[n.VariantCase, ...]:
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
        return n.ContinueTo(target=str(c[0]), span=self._span(meta))

    def skip_stmt(self, meta: Meta, c: list[object]) -> n.SkipToNextHand:
        return n.SkipToNextHand(span=self._span(meta))

    def move_type_def(self, meta: Meta, c: list[object]) -> n.MoveTypeDef:
        name = str(c[0])
        guard: object | None = None
        effect: tuple[object, ...] = ()
        for item in c[1:]:
            if isinstance(item, _MoveWhen):
                guard = None if isinstance(item.pred, _Always) else _as_expr(item.pred)
            elif isinstance(item, _MoveEffect):
                effect = item.body
        params = tuple(x for x in c if isinstance(x, n.MoveParam))
        return n.MoveTypeDef(
            name=name,
            guard=guard,  # type: ignore[arg-type]
            effect=effect,  # type: ignore[arg-type]
            params=params,
            span=self._span(meta),
        )

    def func_param(self, meta: Meta, c: list[object]) -> n.MoveParam:
        return n.MoveParam(name=str(c[0]), type_name=str(c[1]), span=self._span(meta))

    def function_def(self, meta: Meta, c: list[object]) -> n.FunctionDef:
        # c: NAME, func_param* (n.MoveParam), expr(body). The body is the last child.
        name = str(c[0])
        params = tuple(x for x in c if isinstance(x, n.MoveParam))
        return n.FunctionDef(
            name=name, params=params, body=_as_expr(c[-1]), span=self._span(meta)
        )

    def procedure_def(self, meta: Meta, c: list[object]) -> n.ProcedureDef:
        # c: NAME, move_param* (n.MoveParam), statement*. `maybe_placeholders`
        # leaves a None for an absent optional group; `_as_stmt` never sees it
        # because the params filter is by type and the body filter drops it.
        name = str(c[0])
        params = tuple(x for x in c if isinstance(x, n.MoveParam))
        body = tuple(
            _as_stmt(s)
            for s in c[1:]
            if s is not None and not isinstance(s, n.MoveParam)
        )
        return n.ProcedureDef(
            name=name, params=params, body=body, span=self._span(meta)
        )

    def run_stmt(self, meta: Meta, c: list[object]) -> n.RunStmt:
        name = str(c[0])
        args = tuple(_as_expr(a) for a in c[1:] if a is not None)
        return n.RunStmt(name=name, args=args, span=self._span(meta))

    def start(self, meta: Meta, c: list[object]) -> n.Game:
        game = next(x for x in c if isinstance(x, n.Game))
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
        raise DiagnosticError(
            Diagnostic(Severity.ERROR, f"syntax error: {exc!s}".splitlines()[0], span)
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


def parse_library_rules(text: str, source_name: str) -> tuple[n.RuleDef, ...]:
    """Parse a standard-library rules fragment (rule definitions with no
    enclosing game) into RuleDef nodes, spans mapped to ``source_name``."""
    tree = parse_to_tree(text, source_name, start="library_rules")
    result = _transform(_Builder(source_name, 0), tree)
    assert isinstance(result, tuple)
    assert all(isinstance(r, n.RuleDef) for r in result)
    return result


def parse_text(text: str, source_name: str, line_offset: int = 0) -> n.Game:
    """Parse DSL ``text`` into a :class:`~cardlang.ast.nodes.Game` AST."""
    tree = parse_to_tree(text, source_name, line_offset)
    result = _transform(_Builder(source_name, line_offset), tree)
    assert isinstance(result, n.Game)
    return result


def parse_block(block: FencedBlock) -> n.Game:
    """Parse a :class:`FencedBlock`, mapping spans back to its file."""
    return parse_text(block.text, block.source_name, line_offset=block.start_line - 1)
