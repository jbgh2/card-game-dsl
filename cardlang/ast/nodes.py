"""AST node definitions for the Card Game DSL.

Nodes are frozen dataclasses forming a closed :data:`Node` union. Every
consumer dispatches with structural ``match`` ending in
``typing.assert_never``; under ``mypy --strict`` that makes adding a node
without handling it everywhere a type error rather than a silent gap
(docs/building.md, "Typed-AST discipline").

This covers the Hearts construct set: the game header and its blocks, phases,
the statement vocabulary, rules, and the expression sublanguage. It grows one
construct at a time as more of the corpus is formalized.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from cardlang.diagnostics import Span

# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NameRef:
    """A bare identifier. ``ref_kind`` is filled by the resolver, classifying
    the name as one of: ``local`` (a binder/let), ``state_var``, ``zone``,
    ``enum_value``, ``function``, or a ``pronoun`` (`state`/`action`/`outcome`/
    `active_rules`). ``None`` until resolved."""

    name: str
    span: Span | None = None
    ref_kind: str | None = None


@dataclass(frozen=True, slots=True)
class IntLit:
    value: int
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class StrLit:
    value: str  # without surrounding quotes
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class CardLiteral:
    """A standard card written `<rank> of <suit>` (`2 of clubs`, `Q of spades`).
    Rank is kept as text; the resolver checks it against the deck's ranks."""

    rank: str
    suit: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class AllPlayers:
    """The `all players` collection literal."""

    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Member:
    """Field access, e.g. `card.suit`, `state.led_suit`, `action.card`."""

    obj: Expr
    field: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Subscript:
    """Indexing, e.g. `hand[player]`, `cumulative_score[p]`."""

    obj: Expr
    index: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Call:
    """A function call, e.g. `player_holding(2 of clubs)`."""

    func: str
    args: tuple[Arg, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class MethodCall:
    """A method call on a value, e.g. `hand.where(c => …)`."""

    obj: Expr
    method: str
    args: tuple[Arg, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class NamedArg:
    """A `name = value` argument (instantiate args, named call args)."""

    name: str
    value: Expr | Movement
    span: Span | None = None


# A call/method argument is either positional (an expression) or named.
Arg: TypeAlias = "Expr | NamedArg"


@dataclass(frozen=True, slots=True)
class BinOp:
    """A binary operator: `or`, `and`, comparison (`==`…), `+`, `-`,
    `offset_by`. The operator is kept as its surface token."""

    op: str
    left: Expr
    right: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Not:
    operand: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class IsCheck:
    """A postfix predicate: `x is none`, `x is not none`, `x is empty`."""

    operand: Expr
    kind: str  # "none" | "not_none" | "empty"
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Lambda:
    """`param => body` — a one-argument function value (zone-query filters)."""

    param: str
    body: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Quantifier:
    """`any <role> <binder>: body` / `all <role> <binder>: body`."""

    kind: str  # "any" | "all"
    role: str
    binder: str
    body: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class IfExpr:
    """`if c then a (elif c then a)* else b`."""

    cond: Expr
    then: Expr
    elifs: tuple[tuple[Expr, Expr], ...]
    otherwise: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Comprehension:
    """`<agg> over <source> as <binder>: body`, e.g. `sum over captured[p] as
    card: …`."""

    agg: str  # sum | count | max | min
    source: Expr
    binder: str
    body: Expr
    span: Span | None = None


Expr = (
    NameRef
    | IntLit
    | StrLit
    | CardLiteral
    | AllPlayers
    | Member
    | Subscript
    | Call
    | MethodCall
    | BinOp
    | Not
    | IsCheck
    | Lambda
    | Quantifier
    | IfExpr
    | Comprehension
)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Movement:
    """A movement operation (`deal`/`transfer`/`move`/`burn`/`muck`/`draw`).
    ``amount`` is ``"all"``, ``"one"``, or an :data:`Expr` count. ``dest`` is
    ``None`` for the `in <zone>` form where the verb implies the destination."""

    verb: str
    mode: str | None  # "chosen" | "random" | None
    amount: str | Expr  # "all" | "one" | count expression
    item: str  # the item noun: "cards", "coins", …
    source: Expr  # a zone reference
    dest: Expr | None
    dest_each: bool
    visibility: Expr | None = None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class EpistemicOp:
    """A prose epistemic operation, currently `shuffle <zone>`."""

    op: str
    target: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RotateStmt:
    """`rotate <var> through [<values>]` — a state-cycle."""

    var: str
    values: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class EachSimultaneous:
    """`each <role> simultaneously: <stmt>`."""

    role: str
    body: Stmt
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class ForEach:
    """`for each <role> <binder>: <stmt>`."""

    role: str
    binder: str
    body: Stmt
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RepeatUntil:
    """`repeat until <cond> { <stmt>* }`."""

    cond: Expr
    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Instantiate:
    """`instantiate <mechanic> ( <named_arg>* )`."""

    mechanic: str
    args: tuple[NamedArg, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class LetStmt:
    """`let <name>[<index>]? = <expr>`."""

    name: str
    index: str | None
    value: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class AssignStmt:
    """`<name>[<index>]? := / += / -= <expr>`."""

    name: str
    index: Expr | None
    op: str
    value: Expr
    span: Span | None = None


Stmt = (
    Movement
    | EpistemicOp
    | RotateStmt
    | EachSimultaneous
    | ForEach
    | RepeatUntil
    | Instantiate
    | LetStmt
    | AssignStmt
)


# ---------------------------------------------------------------------------
# Phases and the phase-item blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TypeArg:
    """One argument inside ``<>`` (an ordinary type name or a value in
    type-parameter position, e.g. `player` in `Hand<player>`)."""

    name: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class TypeRef:
    name: str
    args: tuple[TypeArg, ...] = ()
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class ZoneDecl:
    name: str
    index: str | None
    type_ref: TypeRef
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class StateDecl:
    """`<name>[<index>]? : <type>['?'] = <default>`."""

    name: str
    index: str | None
    type_name: str
    optional: bool
    default: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class StateBlock:
    decls: tuple[StateDecl, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RuleRef:
    """An entry in an `active_rules:` list, with its delta operator."""

    name: str
    op: str  # "plain" | "add" | "remove" | "override"
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class ActiveRules:
    refs: tuple[RuleRef, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class LegalMoves:
    names: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class MoveEvent:
    """A move-type event with an optional predicate over the move (`action`)."""

    move_type: str
    where: Expr | None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class TransitionTo:
    target: str
    event: MoveEvent
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class PhaseQualifier:
    """`repeats until <expr>` or `when <expr>` on a phase header."""

    kind: str  # "repeats" | "when"
    expr: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Phase:
    name: str
    qualifier: PhaseQualifier | None
    items: tuple[PhaseItem, ...]
    span: Span | None = None


# A phase body holds blocks, nested phases, and statements.
PhaseItem: TypeAlias = "StateBlock | ActiveRules | LegalMoves | TransitionTo | Phase | Stmt"


# ---------------------------------------------------------------------------
# Rules (top-level)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AppliesWhen:
    """`applies_when:` — ``always`` (the wildcard) or a state predicate."""

    always: bool
    pred: Expr | None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Demands:
    """`demands:` — a candidate-card set (kind="cards") or a move predicate
    (kind="actions", an `actions where …` clause)."""

    kind: str  # "cards" | "actions"
    expr: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RuleDef:
    name: str
    constrains: str | None
    applies_when: AppliesWhen | None
    demands: Demands | None
    if_impossible: Expr | None
    span: Span | None = None


# ---------------------------------------------------------------------------
# Game-level
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlayersSpec:
    low: int
    high: int | None = None  # None means a fixed count equal to ``low``
    span: Span | None = None

    @property
    def is_range(self) -> bool:
        return self.high is not None


@dataclass(frozen=True, slots=True)
class Winner:
    """`winner: lowest/highest <target>`."""

    rank_dir: str
    target: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Game:
    """A whole game plus the rules defined alongside it."""

    name: str
    players: PlayersSpec
    deck: str
    zones: tuple[ZoneDecl, ...]
    direction: str | None = None
    ranking: tuple[str, ...] = ()
    state: StateBlock | None = None
    phases: tuple[Phase, ...] = ()
    winner: Winner | None = None
    rules: tuple[RuleDef, ...] = ()
    span: Span | None = None


# The closed union. Consumers should match exhaustively over this.
Node = (
    Game
    | PlayersSpec
    | Winner
    | ZoneDecl
    | TypeRef
    | TypeArg
    | StateBlock
    | StateDecl
    | Phase
    | PhaseQualifier
    | ActiveRules
    | RuleRef
    | LegalMoves
    | TransitionTo
    | MoveEvent
    | RuleDef
    | AppliesWhen
    | Demands
    | Movement
    | EpistemicOp
    | RotateStmt
    | EachSimultaneous
    | ForEach
    | RepeatUntil
    | Instantiate
    | LetStmt
    | AssignStmt
    | NamedArg
    | NameRef
    | IntLit
    | StrLit
    | CardLiteral
    | AllPlayers
    | Member
    | Subscript
    | Call
    | MethodCall
    | BinOp
    | Not
    | IsCheck
    | Lambda
    | Quantifier
    | IfExpr
    | Comprehension
)
