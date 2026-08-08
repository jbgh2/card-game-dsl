"""AST node definitions for the Card Game DSL.

Nodes are frozen dataclasses forming a closed :data:`Node` union. Every
consumer dispatches with structural ``match`` ending in
``typing.assert_never``; under ``mypy --strict`` that makes adding a node
without handling it everywhere a type error rather than a silent gap
(docs/building.md, "Typed-AST discipline").

This covers the Hearts construct set: the game header and its blocks, phases,
the statement forms, rules, and the expression sublanguage. It grows one
construct at a time as more of the corpus is formalized.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from cardlang.diagnostics import Span
from cardlang.types import Flavor

# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NameRef:
    """A bare identifier. ``ref_kind`` is filled by the resolver, classifying
    the name as one of: ``local`` (a binder/let), ``state_var``, ``zone``,
    ``enum_value``, ``function``, ``null`` (the absence literal `none`), or a
    ``pronoun`` (``resolve._PRONOUNS`` — the context namespaces, `actor` among
    them). ``None`` until resolved."""

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
class ListLit:
    """A literal collection, `[hearts, spades]` — the right-hand side of a
    membership test. Never empty (the grammar requires one element)."""

    elements: tuple[Expr, ...]
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
class NamedArg:
    """A `name = value` argument (named call args)."""

    name: str
    value: Expr | Movement
    span: Span | None = None


# A call/method argument is either positional (an expression) or named.
Arg: TypeAlias = "Expr | NamedArg"


@dataclass(frozen=True, slots=True)
class BinOp:
    """A binary operator: `or`, `and`, comparisons, membership `in`, `+`,
    `-`, `*`, `offset_by`. Equality keeps the internal op tokens `==`/`!=`
    (built by the surface `is` / `is not`)."""

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
    """An aggregation over a card zone, binder implicitly `card`:
    `sum of <body> over cards in <source> [where <filter>]` and
    `highest/lowest <body> over cards in <source> [where <filter>]
    or <default>`.

    `filter` narrows the elements before `body` is aggregated; `default` is
    the order aggregators' empty-set value, mandatory in their grammar."""

    agg: str  # sum | max | min
    source: Expr
    binder: str
    body: Expr
    filter: Expr | None = None
    default: Expr | None = None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class CardQuery:
    """A query over a card zone, `pred` evaluated per card with `card` bound
    to the candidate (the card mirror of `PlayerQuery`):

    - `cards in <zone> where <pred>`             -> the matching cards (`set`)
    - `number of cards in <zone> [where <pred>]` -> how many match (`count`)
    - `any card in <zone> where <pred>`          -> does one match (`any`)
    - `all cards in <zone> where <pred>`         -> do all match (`all`)
    """

    kind: str  # "set" | "count" | "any" | "all"
    source: Expr
    pred: Expr | None  # None only for the bare `count` (zone size)
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class DomainQuery:
    """The generic position-domain / collection quantifier register
    (decisions.md "Boards and cells"), the positional twin of the fixed
    `Quantifier` forms. Five surface spellings, one node:

    - BARE, over a declared position domain (`source is None`):
      `any <domain> where <pred>`      (kind "any")
      `all <domain>s where <pred>`     (kind "all")
      `number of <domain>s where <pred>` (kind "count")
      -- `binder` is the singular domain noun, bound per member of the
      domain's ordered members (`cell` for a board, an integer `positions {}`
      name like `column`).

    - COLLECTION, over an evaluated collection (`source` present):
      `any line in <source> where <pred>`  (noun `line`, binds each line)
      `all cells in <source> where <pred>` (noun `cell`, binds each cell)
      -- `binder` is the singular noun (`line` / `cell`), fixed at rung 1.

    `spelled` is the noun exactly as written (plural for `all`/`count`),
    kept only so resolve's plural-mismatch diagnostic can quote it; `binder`
    is the derived singular (the scoped name and, for bare forms, the domain
    to enumerate)."""

    kind: str  # "any" | "all" | "count"
    binder: str  # the singular noun: binder name + (bare) domain to enumerate
    spelled: str  # the noun as written (for the plural diagnostic)
    source: Expr | None  # None for bare forms; the iterated collection for `in`
    pred: Expr
    span: Span | None = None


# The keyword phrase each DomainQuery kind spells in a diagnostic. Owned here
# beside the node so resolve and typecheck read one table, not two.
DOMAIN_QUERY_KIND_PHRASE: dict[str, str] = {"any": "any", "all": "all", "count": "number of"}


@dataclass(frozen=True, slots=True)
class Choose:
    """`choose integer in <lo> .. <hi> [up to <ceiling>]` — a decision that
    resolves to a value via the chooser (e.g. a bid). ``domain`` names the
    candidate space; the only one so far is ``"integer"``, an inclusive range
    from ``lo`` to ``hi``.

    ``ceiling`` is the declared static upper bound (`up to N`): the width the
    OpenSpiel action space reserves for this choose, independent of the live
    ``hi``. It is required when ``hi`` is not itself a static literal, and is
    ``None`` when the ceiling derives from a literal ``hi`` — see
    ``static_ceiling`` and decisions.md "Declared parameter domains"."""

    domain: str  # "integer"
    lo: Expr
    hi: Expr
    ceiling: int | None = None
    span: Span | None = None


def simultaneous_body_error(body: Stmt) -> str | None:
    """Why `body` cannot be the body of `each <role> simultaneously:`, or None if it
    can. THE single statement of that requirement.

    The form runs one chosen movement per player: it must snapshot every player's
    selection against the state as it was at block entry, and only then apply them
    all — that is what makes the pass atomic (in Hearts, nobody sees a passed card
    before choosing their own). A snapshot is only defined for a chosen movement with
    a source to draw from, a destination to deliver to, and a countable amount.

    This exists as one function, and not as a check in the resolver mirroring a set of
    asserts in the executor, because the mirroring is exactly what went wrong: the
    resolver's Owner Guard was written by hand against the FIRST of the executor's
    five requirements, so `move chosen one card …` (a keyword amount, not a countable
    expression) passed the checker and then hit a bare assert at play time. One
    predicate cannot drift from itself — `runtime/execute.py`'s `_pass_selection`
    asserts against this, and `resolve` rejects with it."""
    if not isinstance(body, Movement):
        return "it must be a movement"
    if body.selection_mode != "chosen":
        return "the movement must be `chosen` — each player picks their own cards"
    if body.source is None:
        return "the movement needs a source zone to draw from (`from <zone>`)"
    if body.dest is None:
        return "the movement needs a destination zone (`to <zone>`)"
    if isinstance(body.amount, str):
        return (
            f"the amount must be a countable number, not `{body.amount}` — every "
            f"player's selection is drawn at the same size before any is applied"
        )
    return None


def static_ceiling(choose: Choose) -> int | None:
    """The choose's static upper bound: its declared ``up to N`` ceiling if
    present, else the value of a literal ``hi``. ``None`` when neither yields a
    static integer — a choose the resolver rejects (surface totality) and that
    can never be sized into the OpenSpiel action space."""
    if choose.ceiling is not None:
        return choose.ceiling
    if isinstance(choose.hi, IntLit):
        return choose.hi.value
    return None


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
    | ListLit
    | Member
    | Subscript
    | StructLit
    | Call
    | BinOp
    | Not
    | IsCheck
    | Quantifier
    | IfExpr
    | Comprehension
    | Choose
    | PlayerQuery
    | CardQuery
    | DomainQuery
)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Movement:
    """A movement operation (`deal`/`transfer`/`move`/`burn`/`muck`/`draw`).
    ``amount`` is ``"all"``, ``"one"``, or an :data:`Expr` count. ``dest`` is
    ``None`` for the `in <zone>` form where the verb implies the destination.
    ``filter`` (the `from <zone> where <lambda> to <zone>` form only) narrows
    the source pool to the matching cards, in source order, before the
    selection draws from it — `chosen`/`random` draw from the narrowed pool,
    the default (dealt) form takes the pool's first `count` (first match, not
    top-of-source), and `all` takes every matching card, leaving the rest."""

    verb: str
    # Qualified, like `Round.order_mode`: the bare word names the designer's
    # `mode { }` construct (`Mode`), and no engine field may shadow it.
    selection_mode: str | None  # "chosen" | "random" | None
    amount: str | Expr  # "all" | "one" | "some" | count expression
    item: str  # the item noun: "cards", "coins", …
    source: Expr | None  # a zone reference; None for a gather (collect-from-all)
    dest: Expr | None
    dest_each: bool
    distribution: str | None = None  # "as_equally_as_possible" for a round-robin deal
    filter: Expr | None = None  # a `where <lambda>` predicate narrowing the source pool
    # `where jointly <pred>`: the filter binds `cards` (the candidate SET) and
    # the selection is over the source's satisfying subsets — one decision,
    # not per-card filtering (decisions.md "Joint-predicate selection").
    joint: bool = False
    visibility: Expr | None = None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class EpistemicOp:
    """A prose epistemic operation: `shuffle <zone>` or `reveal one card from
    <zone> [where <pred>]`. `filter` is meaningful only for `reveal` (all
    cards are eligible when it is `None`; the predicate binds `card` per
    candidate); `shuffle` never sets it."""

    op: str
    target: Expr
    filter: Expr | None = None
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RotateStmt:
    """`rotate <target> through [<values>]` — a state-cycle.

    `target` is a `NameRef` for the same reason `AssignStmt.target` is: `rotate` writes
    persistent state, so it is a write target and must be classified like one. `values`
    stays a tuple of strings — those are deck/stdlib enum values validated against a
    registry, and they are not scope participants (nothing can shadow them into meaning
    something else)."""

    target: NameRef
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
class AsBlock:
    """`as <player> { <stmt>* }` — bind the acting player to one evaluated
    player for a braced body. The player expression is evaluated in the OUTER
    context (before the rebind), so it cannot be captured; the body runs once as
    a block scope. The first-class single-actor binder (decisions.md
    "Single-actor decisions: the `as` block")."""

    player: Expr
    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Turns:
    """`turns <binder> from <leader> over <participants> until <pred>
    [again <var>] { <stmt>* }` — the turn loop beneath the round forms.
    The binder names the current player, who is also the acting player
    (`for each`'s binding semantics, one player at a time); rotation and
    termination are owned by the form (decisions.md "The `turns` form").
    `again` names a declared Boolean state variable the body's effects
    write; a turn ending with it true repeats the same player."""

    binder: str
    leader: Expr
    participants: Expr
    termination: Expr
    again: str | None
    body: tuple[Stmt, ...]
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
    """`<target>[<index>]? := / += / -= <expr>`.

    `target` is a `NameRef`, not a bare string, and that is load-bearing. A name in
    this language can denote a lexical binder, a state variable, a zone, a deck
    value, a pronoun or a function, and `resolve._classify` decides which — by a
    fixed precedence, binders first. Every READ goes through that. Were a write
    target a bare `str`, it would go through NOTHING: invisible to name
    classification, to validation, and to `substitute`.

    Three defects would follow, and all three dissolve once the target is an ordinary
    name. A typo (`totaly_score := 1`) would reach the runtime, which requires every
    name it writes to have been declared, because nothing ever checked it existed. A binder shadowing a state
    variable would make one name mean two things — a read of `x` finding the binder
    while `x := 1` went to the state variable, silently. And procedure expansion, which
    rewrites `NameRef`s, would rewrite every read of a parameter and leave the write
    pointing at a global of the same name.

    With a `NameRef` the target is classified like any other name, so "you cannot
    assign to a binder" is one uniform rule instead of three bespoke guards, and
    substitution can see write positions."""

    target: NameRef
    index: Expr | None
    op: str
    value: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Produce:
    """`produce TAG[(expr, …)]` — terminal in a define body; sets the outcome
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
    """`NAME produces: <arm>+` — invoke a define and match its outcome result."""

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
    continue the enclosing `repeat until` hand loop's next iteration."""

    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Offer:
    """`offer to <player> one of [<move_type>, ...]` — the acting player chooses
    one legal move-type; its effect runs with `actor` bound to that player."""

    player: Expr
    offering: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Round:
    """The kernel decision round, in one of two forms.

    *Trick form* — `round <move_type> from <leader> over <participants> source
    <zone> into <zone> winner <fn> [trump <expr>] [early <predicate>]`: a single
    turn-order pass where each participant makes one card play (filtered by the
    active rules), then the winner function picks the winner, bound as `winner`.
    Routing is left to the surrounding body; an optional `early` predicate ends
    the pass before every participant has played (Getaway's tochoo). The winner
    function is carried in `outcome_fn`, the field shared with the auction form
    below — where the name is correct; the field splits with the node (issue #210).

    *Auction/betting form* — `round offering [<move_type>, …] from <leader> over
    <participants> until <pred> [outcome <fn>]`: a continuous ring over a
    heterogeneous offering (bids/passes/bets), looping until the
    termination predicate holds. The `outcome_fn` is optional: an auction supplies
    one and the function produces the typed outcome when the ring closes; a betting
    round omits it (`outcome_fn is None`) — each action mutates shared chip/fold
    state directly, so the closed ring returns and play moves to the next street.
    The trick-specific fields (`move_type`, `source_zone`, `play_zone`) are absent;
    `offering` and `termination` are present (decisions.md "Interactive
    decisions": the same kernel round along the offering/termination axes).

    *Climbing form* — `round climb <move_type> from <leader> over <participants>
    source <zone> into <zone> combinations <fn> follows <fn> until <pred>`: one
    combination-climbing trick (Big Two, Tichu). The leader leads a combination
    from the engine, then each participant beats the standing play or passes; the
    trick ends when action returns to the last player who played, or `termination`
    holds (a player has shed out). `combos_fn` / `follows_fn` name the game-local
    combination-engine queries (the engines differ across games, so the construct
    depends only on their interface). The last player to play is bound as `winner`;
    there is no winner *function*. Distinguished by `combos_fn is not None`.
    """

    move_type: str | None
    leader: Expr
    participants: Expr
    source_zone: str | None
    play_zone: str | None
    outcome_fn: str | None
    trump: Expr | None
    early_termination: str | None = None
    offering: tuple[str, ...] | None = None
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


@dataclass(frozen=True, slots=True)
class Block:
    """A statement sequence with its own binding scope, and nothing else — no
    condition, no iteration. SYNTHETIC: the grammar has no block form, so no source
    program can write one. `expand` creates them, as the shape a `run` becomes.

    It exists because an expansion needs both halves of what a block is: the body's
    `let`s must not leak into the caller's sequence, and the whole thing must be ONE
    statement so it fits a single-statement slot (`for each <role> <b>: <stmt>`).

    It is a real node rather than an `if true { … }`, and the difference is not
    cosmetic: an `IfStmt` tells every downstream pass that the body is CONDITIONAL.
    The deck-capacity gate believed it — it carries `max(then, else)` across a
    conditional — so a procedure that refilled the deck did not reset the gate's
    running total, and the very same program was accepted written inline and rejected
    written as a `run`. That is the one property the construct exists to guarantee."""

    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RunStmt:
    """`run NAME(<arg>, …)` — invoke a named procedure. A resolve-time construct
    only: `expand` splices the procedure's body in at this site (arguments
    substituted for parameters) and drops the node, so no `RunStmt` ever reaches
    the IR or the runtime. The consumers below it therefore carry loud
    Shadow Guards, not silent passes — a `RunStmt` surviving expansion is a
    compiler bug."""

    name: str
    args: tuple[Expr, ...]
    span: Span | None = None


Stmt = (
    Movement
    | EpistemicOp
    | RotateStmt
    | EachSimultaneous
    | ForEach
    | RepeatUntil
    | IfStmt
    | AsBlock
    | Turns
    | LetStmt
    | AssignStmt
    | Offer
    | Round
    | Produce
    | Produces
    | ContinueTo
    | SkipToNextHand
    | RunStmt
    | Block
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
class PositionDecl:
    """One entry of the `positions { }` block: a declared per-game position
    domain `<name> : <lo>..<hi>` (decisions.md "Position domains and
    positional zones"). Members are the inclusive integer range; the name is
    usable as a zone-family index and a move-parameter domain, and nowhere
    else (resolve rejects the rest of the role/type surface).

    A `board:` clause mints a NAMED-member domain by setting `members_named`
    (decisions.md "Boards and cells"): the members are then the given cell
    names (strings) rather than an integer range, and `lo`/`hi` are unread.
    Resolve is the only site that constructs the named form (from a validated
    `board_entry`); the `positions { }` grammar produces the integer form
    exclusively."""

    name: str
    lo: int
    hi: int
    members_named: tuple[str, ...] | None = None
    span: Span | None = None

    @property
    def members(self) -> tuple[int, ...] | tuple[str, ...]:
        if self.members_named is not None:
            return self.members_named
        return tuple(range(self.lo, self.hi + 1))


@dataclass(frozen=True, slots=True)
class BoardDecl:
    """The `board: <family>(<args>)` clause (decisions.md "Boards and cells").

    Records only the selection — the family name and its integer arguments.
    Resolve validates them against `BOARD_FAMILIES` (via `board_entry`) and
    mints the `cell` position domain, injecting a named-member `PositionDecl`
    into `Game.positions`; this node is retained on the resolved `Game` so the
    runtime can rebuild the `BoardEntry` (`rs.board`) for the cell/line query
    verbs. Not emitted to the IR: the board's IR representation is its minted
    `cell` position domain (the members), as `span`/`procedures` are likewise
    non-serialized."""

    family: str
    args: tuple[int, ...]
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
    """An entry in an `active_rules:` list, with its delta operator. ``args``
    instantiates a parameterized rule (library or game-local): the resolver
    substitutes them into the template body and splices the instance into
    ``game.rules`` under this reference's name."""

    name: str
    op: str  # "plain" | "add" | "remove" | "override"
    args: tuple[Expr, ...] = ()
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class ActiveRules:
    refs: tuple[RuleRef, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class LegalMoves:
    move_types: tuple[str, ...]
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
class Mode:
    """`mode NAME { }` — a condition the enclosing phase is in, existing to
    change which rules are active.

    Modes are INDEPENDENT conditions, not an exclusive state machine: a phase
    may hold several, all of their deltas stack, and each is the "before" side
    (it declares transitions) or the "after" side (a sibling names it) of
    exactly one condition. `active_rules` is the delta a mode contributes while
    it holds; `transitions` are the events that end it. Both tuples may be
    empty — an empty mode is the terminal side of some sibling's condition."""

    name: str
    active_rules: tuple[ActiveRules, ...]
    transitions: tuple[TransitionTo, ...]
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
    """`repeat until <expr>` or `when <expr>` on a phase header."""

    kind: str  # "repeats" | "when"
    expr: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Phase:
    name: str
    qualifier: PhaseQualifier | None
    items: tuple[PhaseItem, ...]
    # A phase that resolves more than one way declares its outcome cases here
    # (`phase NAME -> outcome { ... }`); empty for the usual single-outcome phase.
    outcome_cases: tuple[OutcomeCase, ...] = ()
    span: Span | None = None


# A phase body holds blocks, modes, lifecycle hooks, nested phases, and
# statements. `TransitionTo` is NOT a phase item: it lives only inside a mode.
PhaseItem: TypeAlias = (
    "StateBlock | ActiveRules | LegalMoves | Mode | BeforeEach | AfterEach | Phase | Stmt"
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


# The `demands:` clause's two forms, one per `demand_value` grammar
# alternative. A REGISTRY, not a comment: the enforcement Owner Guard is
# written as the complement of the enforced kind (`kind != DEMAND_KIND_CARDS`),
# so a third form added here is rejected on arrival rather than silently
# ignored — and the rule grid derives its axis from this set instead of
# hand-listing it.
DEMAND_KIND_CARDS = "cards"
DEMAND_KIND_ACTIONS = "actions"
DEMAND_KINDS: frozenset[str] = frozenset({DEMAND_KIND_CARDS, DEMAND_KIND_ACTIONS})


@dataclass(frozen=True, slots=True)
class Demands:
    """`demands:` — a candidate-card set (kind=`DEMAND_KIND_CARDS`) or a move
    predicate (kind=`DEMAND_KIND_ACTIONS`, an `actions where …` clause)."""

    kind: str  # a member of DEMAND_KINDS
    expr: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RuleDef:
    """... ``exempts`` (optional): a candidate-card expression (like a card-set
    `demands`) whose cards sit outside this rule's obligation entirely — never
    constrained by it, never counted toward satisfying it. When the rule
    `constrains` a move type, `rules.legal_cards` removes exempt cards from the
    demand cascade's working set and appends them after every other candidate,
    in hand order (Tarot's Excuse: always playable, offered last)."""

    name: str
    constrains: str | None
    applies_when: AppliesWhen | None
    demands: Demands | None
    if_impossible: Expr | None
    exempts: Expr | None = None
    # Declared parameters make this a template: never active itself, only
    # instantiated by an `active_rules` reference with arguments. The resolver
    # consumes templates — post-resolve, every rule in `game.rules` has
    # `params == ()`.
    params: tuple[MoveParam, ...] = ()
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
    """`move_type NAME [(<param> : <type>, …)] { when: <pred> effect { <stmt>* } }` —
    a named action, legal only where its predicate holds. ``when`` is None when the
    move is always legal — the field is named for the clause the designer writes;
    ``params`` is empty for a nullary move (the trick/offer form). Parameters
    enumerate in declaration order (leftmost outermost); see decisions.md
    "Declared parameter domains"."""

    name: str
    when: Expr | None
    effect: tuple[Stmt, ...]
    params: tuple[MoveParam, ...] = ()
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
class ProcedureDef:
    """`procedure NAME(<param> : <type>, …) { <stmt>* }` — a named, parameterized
    statement block. Reuse is *textual*: `expand` splices the body in at each
    `run` site after substituting arguments for parameters, so the statements a
    procedure contributes — and therefore the observation events they emit, and
    therefore the derived information sets — are exactly what inline text would
    emit. The body is hermetic: it reads only its parameters and game/phase state,
    never the caller's binders, and never the call-site pronouns (`actor` /
    `action` / `outcome`), which would make its meaning depend on where it is
    called from. The resolver consumes procedures — post-expansion,
    `Game.procedures` is empty."""

    name: str
    params: tuple[MoveParam, ...]
    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class OutcomeCase:
    """One case of a outcome outcome: a tag with zero or more typed payloads."""

    tag: str
    payload_types: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class DefineDef:
    """`define NAME -> { case(T) | … } { <stmt>* }` — a param-light definition
    that produces one outcome. Runs with the enclosing context bound."""

    name: str
    cases: tuple[OutcomeCase, ...]
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
class UsesDecl:
    """`uses <library>` — one family-library import. Carries its own span so the
    requires-contract failure lands on the line the author wrote, not inside the
    library text they did not write."""

    name: str
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class RequireDecl:
    """One entry of a library's `requires` block: the thing the including game
    must declare, with the shape the library's bodies read it at. A `StateDecl`
    minus the default, which the game owns — plus the zone types' `<owner>`
    argument, because an entry may name a `zones { }` declaration as well as a
    `state { }` one.

    The two shapes are exclusive and `resolve` enforces it: `type_args` is a
    zone spelling and `optional` a state one, so an entry carrying both names
    nothing a game can declare."""

    name: str
    index: str | None
    type_name: str
    type_args: tuple[TypeArg, ...]
    optional: bool
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Library:
    """A family library: the definition forms of a game, minus the game. Held
    only between parse and resolve — `resolve` splices each used library's
    definitions into the including `Game` and no `Library` survives into the IR,
    which is what makes imports pure name resolution with no runtime or
    information-set implication.

    ``state`` and ``requires`` are the two halves of a library's state surface
    and are not interchangeable. ``state`` is state the library OWNS: it carries
    defaults, splices into the game's own ``state { }``, and the including game
    may read it but not write it. ``requires`` is state the library CONTRACTS
    for: the game declares it, chooses its initial value, and writes it. A name
    may appear in one or the other, never both (``resolve._check_state_claims``).
    """

    name: str
    requires: tuple[RequireDecl, ...] = ()
    state: StateBlock | None = None
    rules: tuple[RuleDef, ...] = ()
    move_types: tuple[MoveTypeDef, ...] = ()
    types: tuple[TypeDef, ...] = ()
    defines: tuple[DefineDef, ...] = ()
    functions: tuple[FunctionDef, ...] = ()
    procedures: tuple[ProcedureDef, ...] = ()
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Game:
    """A whole game plus the rules defined alongside it."""

    name: str
    players: PlayersSpec
    # The selected component-set name, for both content flavors.
    deck: str
    zones: tuple[ZoneDecl, ...]
    # Which clause selected `deck` — "card" (`cards:`) or "piece" (`pieces:`),
    # stamped at parse; resolve rejects a cross-flavor name, so post-resolve
    # `component_set(deck).flavor == content_flavor`.
    content_flavor: Flavor = "card"
    direction: str | None = None
    ranking: tuple[str, ...] = ()
    # The convention keyword `ranking:` was written with (`"aces high"` etc.,
    # a `RANKING_CONVENTIONS` key), or None for an enumerated/absent ranking.
    # Parse guarantees the XOR (a convention parses with `ranking` empty);
    # resolve expands the convention into `ranking`, so post-resolve `ranking`
    # is always the operative strength order and this field only records the
    # source form (for `ir.emit`).
    ranking_convention: str | None = None
    trump: str | None = None
    teams: tuple[tuple[int, ...], ...] = ()
    # Declared position domains (`positions { column : 1..7 }`) — per-game
    # integer index/parameter domains (decisions.md "Position domains and
    # positional zones"). Empty for every game with no positional layout.
    # Resolve APPENDS the board-minted `cell` domain (a named-member
    # `PositionDecl`) here, so a post-resolve game's positions are the union of
    # the declared integer domains and the board's cells.
    positions: tuple[PositionDecl, ...] = ()
    # The `board:` clause (decisions.md "Boards and cells"), or None. Retained
    # through resolve for `rs.board`; the minted `cell` domain lives in
    # `positions`, so this field is not itself emitted to the IR.
    board: BoardDecl | None = None
    max_length: int | None = None
    state: StateBlock | None = None
    phases: tuple[Phase, ...] = ()
    winner: Winner | None = None
    loser: Loser | None = None
    rules: tuple[RuleDef, ...] = ()
    move_types: tuple[MoveTypeDef, ...] = ()
    types: tuple[TypeDef, ...] = ()
    defines: tuple[DefineDef, ...] = ()
    functions: tuple[FunctionDef, ...] = ()
    # Consumed by `expand`, which runs after typecheck: every `run` site is
    # replaced by the substituted body and this tuple is emptied. It must be
    # empty downstream — `openspiel.encoding` walks every dataclass field of the
    # `Game`, so a surviving procedure body would count its `offer`/`round`
    # decision sites a second time, on top of the copies spliced at the call
    # sites, and size the action space wrong.
    procedures: tuple[ProcedureDef, ...] = ()
    # Emptied by `resolve`, which splices each named library's definitions in:
    # like `procedures`, a surviving entry downstream would mean the import was
    # parsed and ignored. Order is source order, and resolution is flat and
    # two-level (game -> named libraries -> stdlib) with no library-imports-
    # library — see decisions.md "Family libraries".
    uses: tuple[UsesDecl, ...] = ()
    span: Span | None = None


# The closed union of EVERY dataclass in this module. Consumers dispatch over it
# exhaustively (`match` + `assert_never`), so membership is what makes a new node
# kind loud everywhere. The list is pinned to the module's actual contents by
# tests/test_node_registry.py — it drifted silently once (four members missing,
# nothing noticed, because the only consumer was a docstring).
Node = (
    Game
    | Library
    | UsesDecl
    | RequireDecl
    | PlayersSpec
    | Winner
    | Loser
    | MoveTypeDef
    | MoveParam
    | OutcomeCase
    | DefineDef
    | FunctionDef
    | StructField
    | DerivedField
    | TypeDef
    | ZoneDecl
    | TypeRef
    | TypeArg
    | StateBlock
    | StateDecl
    | PositionDecl
    | BoardDecl
    | Phase
    | PhaseQualifier
    | BeforeEach
    | AfterEach
    | ActiveRules
    | RuleRef
    | LegalMoves
    | Mode
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
    | AsBlock
    | Turns
    | LetStmt
    | AssignStmt
    | Offer
    | Round
    | Produce
    | ProduceArm
    | Produces
    | ContinueTo
    | SkipToNextHand
    | RunStmt
    | Block
    | ProcedureDef
    | NamedArg
    | NameRef
    | IntLit
    | StrLit
    | ListLit
    | CardLiteral
    | AllPlayers
    | Member
    | Subscript
    | FieldInit
    | StructLit
    | Call
    | BinOp
    | Not
    | IsCheck
    | Quantifier
    | IfExpr
    | Comprehension
    | Choose
    | PlayerQuery
    | CardQuery
    | DomainQuery
)


def state_blocks(game: Game) -> list[StateBlock]:
    """Every state block a game declares: the game-level one and every phase's,
    nested phases included.

    One walk, because "where can state be declared" is one fact: the typechecker
    builds its state-variable table from this, and `openspiel/replay` reads a
    `winner:` target's declaration through it to learn whether the target is
    keyed by team. A second copy of the walk would drift the day state becomes
    declarable somewhere new, and the two readers would disagree about what a
    game declares."""
    blocks: list[StateBlock] = []
    if game.state is not None:
        blocks.append(game.state)

    def rec(phase: Phase) -> None:
        for item in phase.items:
            if isinstance(item, StateBlock):
                blocks.append(item)
            elif isinstance(item, Phase):
                rec(item)

    for phase in game.phases:
        rec(phase)
    return blocks
