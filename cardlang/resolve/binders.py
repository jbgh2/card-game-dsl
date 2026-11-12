"""The binders a node introduces, and the fields they scope.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  the binders each node kind introduces (``_node_binders``,
              ``_introduced_binders``), and the fields each binder scopes
              (``_BINDER_SCOPE_FIELDS``).
"""

from __future__ import annotations

from typing import assert_never, cast, get_args
from cardlang.ast import nodes as n
from cardlang.runtime.values import content_noun
from cardlang.types import Flavor


# The Node union's members, for the runtime gate below. `get_args` reads the
# union itself, and tests/test_node_registry.py pins that union to the module's
# actual dataclasses — so this tuple cannot silently miss a node kind.
_NODE_KINDS: tuple[type, ...] = get_args(n.Node)


def _introduced_binders(node: object, flavor: Flavor = "card") -> tuple[str, ...]:
    """The single registry of "which node kinds bind names, and which names":
    every other place that needs to know (`_template_binders`'s collision
    check, `_check_functions`'s allowed-reference set, `_rewrite`'s lexical
    scoping via `_BINDER_SCOPE_FIELDS`) reads this instead of re-enumerating
    the node-kind match itself — separate copies of that match would drift out
    of sync, the `Transfer`/`EpistemicOp` filter arm being especially easy to
    miss.

    `flavor` sets the ONE binder that varies with content kind — the
    movement/reveal filter candidate, `card` vs `piece` (`content_noun`); every
    other binder is user-chosen or a card-only construct's fixed name. The
    scoping site passes the game's flavor so `piece` resolves in a piece game's
    filter; the collision/reserved sweeps default `card` (the fixed nouns are
    never reserved and a movement can only occur where the game's own flavor
    already governs).

    Walks feed this every field value they meet, so non-node values (a `str`
    name, a `Span`, an `int`) answer "nothing" here; every actual node kind is
    dispatched exhaustively in `_node_binders`."""
    if not isinstance(node, _NODE_KINDS):
        return ()
    return _node_binders(cast(n.Node, node), flavor)


def _node_binders(node: n.Node, flavor: Flavor = "card") -> tuple[str, ...]:
    """Exhaustive over `Node` — deliberately. A `case _: return ()` catch-all
    answers "no binders" for a node kind nobody has thought about, without
    anyone having decided that; exhaustive, a new node kind is a mypy error
    here until someone files it under binding or non-binding by hand.

    `LetStmt` returns both `name` and `index` (when present) — every name it
    binds *somewhere*, which is what a collision check needs. The two differ
    in WHERE they're visible (`index` scopes only its own `value`; `name`
    scopes to later statements in the same tuple), which is a lexical-scoping
    fact `_rewrite` must handle itself, not this registry (see the `LetStmt`
    branch in `_rewrite` and the sequential fold in `_rewrite_value`).

    Parameter-bearing declarations (`MoveTypeDef`, `RuleDef`, `FunctionDef`,
    `ProcedureDef`) are non-binding HERE by design, not by omission: their
    parameters scope to their own guard/effect/body only, which `_rewrite`
    implements in per-declaration arms, and `_check_reserved_params` sweeps
    them for reserved words. This registry answers for nodes a body walk can
    encounter, where the binder scopes within the walked tree itself.

    A movement/reveal filter binds the CONTENT noun (`card` for a card game,
    `piece` for a piece game — `content_noun`); the card-query and aggregation
    binders stay `card` because those forms are card-only (rejected in a piece
    game), so the noun they bind is fixed."""
    match node:
        case (
            n.Comprehension() | n.Quantifier() | n.ForEach() | n.Turns() | n.HostedPoll()
            | n.DomainQuery() | n.SubsetQuery()
        ):
            return (node.binder,)
        case n.EachSimultaneous():
            return (node.role,)
        case n.PlayerQuery():
            return ("player",)
        case n.CardQuery():
            return ("card",)
        case n.Transfer() if node.where is not None:
            # `where jointly` binds the candidate SET; a per-card `where`
            # binds each candidate (decisions.md "Joint-predicate selection").
            return (content_noun(flavor, plural=node.joint),)
        case n.EpistemicOp() if node.where is not None:
            return (content_noun(flavor, plural=False),)
        case n.LetStmt():
            return (node.name, node.index) if node.index is not None else (node.name,)
        case n.ProduceArm():
            # A `produces:` arm's payload binders (`Doubled(by, level) { … }`) are
            # user-chosen names bound in the arm body, and `_rewrite_produce_arm`
            # scopes them exactly like any other binder. Without this arm,
            # `_check_reserved_binders` never swept them, so an arm binder named
            # `actor` silently hijacked the pronoun (the body's bare `actor`
            # classified as that `local` instead), and `_check_functions` /
            # `_check_procedures` mistook a legitimately-bound arm name for an
            # unbound reference. Both fall out of the registry being complete.
            return node.binders
        # A filter-less Transfer/EpistemicOp falls through its guarded arm above:
        # no candidate set, so no `card` binder.
        case n.Transfer() | n.EpistemicOp():
            return ()
        # Declarations and game/phase structure. (The parameter-bearing ones are
        # covered by `_rewrite` + `_check_reserved_params` — see the docstring.)
        case (
            n.Game() | n.PlayersSpec() | n.Winner() | n.Loser() | n.StopResult()
            # The import nodes bind nothing: `uses` and `requires` name state and
            # definitions that already live in flat, game-wide namespaces, and a
            # `Library` is gone by the end of `_apply_uses` — its definitions are
            # spliced into the Game and reached through the arms below. A
            # signature row's parameters are its own reading and scope no body,
            # and a contract stamp or an origin stamp holds spellings, never a name.
            | n.Library() | n.UsesDecl() | n.RequireDecl()
            | n.MoveContract() | n.FunctionContract() | n.ProcedureContract()
            | n.ContractStamp() | n.LibraryOrigin()
            | n.MoveTypeDef() | n.Parameter() | n.RuleDef() | n.RuleRef()
            # A `primitives { }` entry's parameters name the arguments its
            # Python receives and key its `reads` binders; no DSL body is
            # scoped by them, so the entry introduces no name into any scope
            # (`_check_reserved_params` covers them via `_PARAM_BEARING`).
            | n.PrimitivesBlock() | n.PrimitiveDecl() | n.PrimitiveRead()
            | n.AppliesWhen() | n.Demands()
            | n.FunctionDef() | n.ProcedureDef() | n.OutcomeCase()
            | n.ZoneDecl() | n.TypeRef() | n.TypeArg()
            | n.CardPointsEntry() | n.LoweredSpelling() | n.SuitRanking()
            # A catalogue's row labels are declarations in the game's namespace
            # (refused where they collide), never binders a body scopes.
            | n.RankSequence() | n.ShapePart() | n.ShapeRow() | n.CombinationCatalogue()
            | n.StateBlock() | n.StateDecl() | n.PositionDecl() | n.BoardDecl()
            | n.Phase() | n.PhaseQualifier() | n.BeforeEach() | n.AfterEach()
            | n.ActiveRules() | n.LegalMoves() | n.Mode() | n.TransitionTo() | n.MoveEvent()
        ):
            # `StateDecl` in particular: state variables are a flat, game-wide
            # declaration namespace (`_categories`'s `state_vars`), not a binder
            # any construct introduces.
            return ()
        # Statements that bind nothing. `AsBlock` rebinds the ACTING player, not a
        # named binder — its player is an expression, not a NAME — so it introduces
        # no name into scope; its body is an ordinary block (see `_BINDER_SCOPE_FIELDS`).
        case (
            n.RotateStmt() | n.RepeatUntil() | n.IfStmt() | n.AsBlock() | n.AssignStmt()
            | n.Offer() | n.TrickRound() | n.ClimbRound()
            | n.RegisteredEngine() | n.DeclaredEngine()
            | n.Produce() | n.Produces()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt() | n.Block()
        ):
            return ()
        # Expressions that bind nothing.
        case (
            n.NameRef() | n.IntLit() | n.StrLit() | n.ListLit() | n.CardLiteral()
            | n.AllPlayers() | n.Member() | n.Subscript()
            | n.Call() | n.BinOp() | n.Not()
            | n.IsCheck() | n.IfExpr() | n.Choose()
        ):
            return ()
        case _:
            assert_never(node)


# Binder-introducing node kinds `_rewrite` scopes to specific sub-fields only
# (lexical scoping): each maps to the field name(s) whose subtree sees the
# node's own binder(s) (from `_introduced_binders`) added to `cats.locals` —
# every other field of the node keeps the enclosing scope. A source/default
# field is deliberately absent from a comprehension's/card-query's entry: the
# source zone and the empty-set default are evaluated outside the element
# scope (mirrors typecheck.py `_check_expr`'s identical split). `LetStmt` is
# handled separately in `_rewrite` (its `index` scopes only its own `value`;
# its `name` scopes forward to later statements, not to any field of its own
# node — see the sequential fold in `_rewrite_value`'s tuple arm) and so has
# no entry here.
_BINDER_SCOPE_FIELDS: dict[type, tuple[str, ...]] = {
    n.Quantifier: ("body",),
    n.Comprehension: ("where", "body"),
    n.CardQuery: ("where",),
    # A PlayerQuery's binder scopes to its `where` only; the ring search's
    # `start` seat is evaluated in the enclosing scope (the same split as
    # every source field absent from this table), so `player` in a start
    # slot means an OUTER binder or nothing.
    n.PlayerQuery: ("where",),
    # A DomainQuery's binder scopes to its `where` only; the `in` source is
    # evaluated in the enclosing scope (mirrors Comprehension/CardQuery, whose
    # source field is likewise absent here).
    n.DomainQuery: ("where",),
    # A SubsetQuery's binder scopes to the fields that are folded over the
    # candidate set — its filter and, in the aggregation register, its body.
    # `count`, `source` and the order aggregators' `default` are absent for the
    # same reason every source/default field is: they are evaluated outside the
    # element scope, so `subset` in one of them means an OUTER binder or nothing.
    n.SubsetQuery: ("where", "body"),
    n.Transfer: ("where",),
    n.EpistemicOp: ("where",),
    n.ForEach: ("body",),
    n.EachSimultaneous: ("body",),
    # `turns`' binder scopes to the body only: leader/participants/termination
    # evaluate in the enclosing scope (the binder does not exist until a turn
    # is bound — decisions.md "The `turns` form").
    n.Turns: ("body",),
    # A Hosted Poll's binder is the seat about to be asked, bound for its body
    # alone; the climbing round's own clauses never see it.
    n.HostedPoll: ("body",),
}
