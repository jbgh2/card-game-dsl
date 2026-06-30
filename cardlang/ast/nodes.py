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
    ``enum_value``, ``function``, ``null`` (the absence literal `none`), or a
    ``pronoun`` (`state`/`action`/`outcome`/`active_rules`). ``None`` until
    resolved."""

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
class FieldInit:
    """One `name: value` pair in a struct literal."""

    name: str
    value: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class StructLit:
    """`TypeName { field: expr, … }` — constructs a user-defined struct value."""

    type_name: str
    fields: tuple[FieldInit, ...]
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
    """A postfix predicate: `x is none`, `x is not none`, `x is empty`,
    `x is not empty`."""

    operand: Expr
    kind: str  # "none" | "not_none" | "empty" | "not_empty"
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


@dataclass(frozen=True, slots=True)
class Choose:
    """`choose integer in <lo> .. <hi>` — a decision that resolves to a value
    via the chooser (e.g. a bid). ``domain`` names the candidate space; the only
    one so far is ``"integer"``, an inclusive range from ``lo`` to ``hi``."""

    domain: str  # "integer"
    lo: Expr
    hi: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class PlayerQuery:
    """A query over the player ring, whose `pred` is evaluated per player with
    `player` bound to the candidate:

    - `players where <pred>`           -> the set of matching players (`set`)
    - `the player where <pred>`        -> the unique matching player (`pick`)
    - `number of players where <pred>` -> how many match (`count`)
    """

    kind: str  # "set" | "pick" | "count"
    pred: Expr
    span: Span | None = None


Expr = (
    NameRef
    | IntLit
    | StrLit
    | CardLiteral
    | AllPlayers
    | Member
    | Subscript
    | StructLit
    | Call
    | MethodCall
    | BinOp
    | Not
    | IsCheck
    | Lambda
    | Quantifier
    | IfExpr
    | Comprehension
    | Choose
    | PlayerQuery
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
    source: Expr | None  # a zone reference; None for a gather (collect-from-all)
    dest: Expr | None
    dest_each: bool
    distribution: str | None = None  # "as_equally_as_possible" for a round-robin deal
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
class IfStmt:
    """`if <cond> { <stmt>* } [else { <stmt>* }]` — a conditional statement,
    distinct from the `if … then … else …` expression (`IfExpr`)."""

    cond: Expr
    then_body: tuple[Stmt, ...]
    else_body: tuple[Stmt, ...] | None
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


@dataclass(frozen=True, slots=True)
class Produce:
    """`produce TAG[(expr, …)]` — terminal in a define body; sets the variant
    result and unwinds the body."""

    tag: str
    payloads: tuple[Expr, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class ProduceArm:
    """One arm of a `produces:` block: a tag, payload binders, and a body."""

    tag: str
    binders: tuple[str, ...]
    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Produces:
    """`NAME produces: <arm>+` — invoke a define and match its variant result."""

    define: str
    arms: tuple[ProduceArm, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class ContinueTo:
    """`continue to <phase>` — in a `produces:` arm, resume the phase sequence at
    a named later sibling phase, skipping any phases between."""

    target: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class SkipToNextHand:
    """`skip to next hand` — in a `produces:` arm, abort the rest of this hand and
    continue the enclosing `repeats until` hand loop's next iteration."""

    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Offer:
    """`offer to <player> one of [<move_type>, ...]` — the acting player chooses
    one legal move-type; its effect runs with `actor` bound to that player."""

    player: Expr
    move_types: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Round:
    """The kernel decision round, in one of two forms.

    *Trick form* — `round <move_type> from <leader> over <participants> source
    <zone> into <zone> outcome <fn> [trump <expr>] [early <predicate>]`: a single
    turn-order pass where each participant makes one card play (filtered by the
    active rules), then the outcome function picks the winner, bound as `outcome`.
    Routing is left to the surrounding body; an optional `early` predicate ends
    the pass before every participant has played (Getaway's tochoo).

    *Auction/betting form* — `round offering [<move_type>, …] from <leader> over
    <participants> until <pred> [outcome <fn>]`: a continuous ring over a
    heterogeneous move vocabulary (bids/passes/bets), looping until the
    termination predicate holds. The `outcome_fn` is optional: an auction supplies
    one and the function produces the typed variant when the ring closes; a betting
    round omits it (`outcome_fn is None`) — each action mutates shared chip/fold
    state directly, so the closed ring returns and play moves to the next street.
    The trick-specific fields (`move_type`, `source_zone`, `play_zone`) are absent;
    `move_types` and `termination` are present (decisions.md "Interactive
    decisions": the same kernel round along the move-vocabulary/termination axes).

    *Climbing form* — `round climb <move_type> from <leader> over <participants>
    source <zone> into <zone> combinations <fn> follows <fn> until <pred>`: one
    combination-climbing trick (Big Two, Tichu). The leader leads a combination
    from the engine, then each participant beats the standing play or passes; the
    trick ends when action returns to the last player who played, or `termination`
    holds (a player has shed out). `combos_fn` / `follows_fn` name the game-local
    combination-engine queries (the engines differ across games, so the construct
    depends only on their interface). The last player to play is bound as `outcome`;
    there is no outcome *function*. Distinguished by `combos_fn is not None`.
    """

    move_type: str | None
    leader: Expr
    participants: Expr
    source_zone: str | None
    play_zone: str | None
    outcome_fn: str | None
    trump: Expr | None
    early_termination: str | None = None
    move_types: tuple[str, ...] | None = None
    termination: Expr | None = None
    # The order axis for the continuous-ring form: None / "ring" walks the ring
    # (pointer advances each turn); "priority" re-scans from the leader each turn
    # and offers the first still-pending participant (betting, response windows).
    order_mode: str | None = None
    # The climbing form's combination-engine queries: the lead-options query and
    # the legal-follows query. Both present (and `combos_fn is not None`) marks the
    # climb form; absent in the trick and auction forms.
    combos_fn: str | None = None
    follows_fn: str | None = None
    span: Span | None = None


# The values `Round.order_mode` may take (None is treated as the default, ring).
ROUND_ORDER_RING = "ring"
ROUND_ORDER_PRIORITY = "priority"
ROUND_ORDER_MODES = frozenset({ROUND_ORDER_RING, ROUND_ORDER_PRIORITY})


Stmt = (
    Movement
    | EpistemicOp
    | RotateStmt
    | EachSimultaneous
    | ForEach
    | RepeatUntil
    | IfStmt
    | Instantiate
    | LetStmt
    | AssignStmt
    | Offer
    | Round
    | Produce
    | Produces
    | ContinueTo
    | SkipToNextHand
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
class BeforeEach:
    """`before_each { … }` — runs at the start of every loop iteration."""

    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class AfterEach:
    """`after_each { … }` — runs at the end of every loop iteration, including
    one terminated mid-body by the loop's predicate."""

    body: tuple[Stmt, ...]
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
    # A phase that resolves more than one way declares its variant cases here
    # (`phase NAME -> outcome { ... }`); empty for the usual single-outcome phase.
    outcome_cases: tuple[VariantCase, ...] = ()
    span: Span | None = None


# A phase body holds blocks, lifecycle hooks, nested phases, and statements.
PhaseItem: TypeAlias = (
    "StateBlock | ActiveRules | LegalMoves | TransitionTo | BeforeEach | AfterEach"
    " | Phase | Stmt"
)


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


@dataclass(frozen=True, slots=True)
class MoveParam:
    """A `move_type`'s optional parameter: a name bound in the guard/effect and a
    type whose value-domain is enumerated (`submit_bid(strain : Suit?)`). The
    ``type_name`` keeps a trailing `?` for a nullable domain, like a payload type."""

    name: str
    type_name: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class MoveTypeDef:
    """`move_type NAME [(<param> : <type>)] { when: <pred> effect { <stmt>* } }` —
    a named, guarded action. ``guard`` is None when the move is always legal;
    ``param`` is None for a nullary move (the trick/offer form)."""

    name: str
    guard: Expr | None
    effect: tuple[Stmt, ...]
    param: MoveParam | None = None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class FunctionDef:
    """`function NAME(<param> : <type>, …) = <expr>` — a named, parameterized
    expression callable wherever an expression appears. The body is hermetic: it
    reads only its parameters (bound to the call arguments) and game/phase state
    (read at call time), never the caller's binders. Non-recursive."""

    name: str
    params: tuple[MoveParam, ...]
    body: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class VariantCase:
    """One case of a variant outcome: a tag with zero or more typed payloads."""

    tag: str
    payload_types: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class DefineDef:
    """`define NAME -> { case(T) | … } { <stmt>* }` — a param-light definition
    that produces one variant. Runs with the enclosing context bound."""

    name: str
    cases: tuple[VariantCase, ...]
    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class StructField:
    """A declared struct field: `name : Type['?']`."""

    name: str
    type_name: str
    optional: bool
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class DerivedField:
    """A computed struct field: `name = <expr>` over the declared fields."""

    name: str
    value: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class TypeDef:
    """`type Name = { field: T … } [derived { name = expr … }]` — a user-defined
    struct value type."""

    name: str
    fields: tuple[StructField, ...]
    derived: tuple[DerivedField, ...]
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
class Loser:
    """`loser: <selection>` — a player-valued expression naming the sole loser,
    evaluated against the final state. Unlike `winner:` (which ranks a score
    variable), an elimination game ends with one player selected directly."""

    selection: Expr
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
    trump: str | None = None
    partnerships: tuple[tuple[int, ...], ...] = ()
    state: StateBlock | None = None
    phases: tuple[Phase, ...] = ()
    winner: Winner | None = None
    loser: Loser | None = None
    rules: tuple[RuleDef, ...] = ()
    move_types: tuple[MoveTypeDef, ...] = ()
    types: tuple[TypeDef, ...] = ()
    defines: tuple[DefineDef, ...] = ()
    functions: tuple[FunctionDef, ...] = ()
    span: Span | None = None


# The closed union. Consumers should match exhaustively over this.
Node = (
    Game
    | PlayersSpec
    | Winner
    | Loser
    | MoveTypeDef
    | MoveParam
    | VariantCase
    | DefineDef
    | StructField
    | DerivedField
    | TypeDef
    | ZoneDecl
    | TypeRef
    | TypeArg
    | StateBlock
    | StateDecl
    | Phase
    | PhaseQualifier
    | BeforeEach
    | AfterEach
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
    | IfStmt
    | Instantiate
    | LetStmt
    | AssignStmt
    | Offer
    | Round
    | Produce
    | ProduceArm
    | Produces
    | NamedArg
    | NameRef
    | IntLit
    | StrLit
    | CardLiteral
    | AllPlayers
    | Member
    | Subscript
    | FieldInit
    | StructLit
    | Call
    | MethodCall
    | BinOp
    | Not
    | IsCheck
    | Lambda
    | Quantifier
    | IfExpr
    | Comprehension
    | Choose
    | PlayerQuery
)
