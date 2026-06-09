"""Typecheck stage.

Infers a :class:`~cardlang.types.Type` for every expression (`infer` over a
`TypeEnv` built from declared state vars, zone contents, and the deck/stdlib
enum values) and validates: sensible player counts, assignment compatibility,
stdlib argument types, subscripting only collections, and Boolean conditions
(`if` / `repeat until` / phase qualifiers). It accepts the whole corpus and
rejects real type errors.

Pragmatic by design: unrefined positions (pronoun member access, lambda values,
the `Resource`/`ChipStack` query API) infer the permissive `TAny`, which
propagates without error. Deferred to later stages: variant outcome types and
exhaustiveness (`TVariant`), user-defined `type` declarations (`TStruct`), full
`ZoneContents`/`Resource` typing, and payload-type narrowing.

Like :mod:`cardlang.resolve`, this annotates rather than rewrites: the
(unchanged) :class:`Game` flows on, and the IR stays at the resolved-AST level.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterator, Mapping, assert_never

from cardlang.ast import nodes as n
from cardlang.ast.nodes import Game
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.signatures import CALL_SIGS, METHOD_SIGS, ZONE_CONTENT
from cardlang.stdlib.values import DIRECTION_VALUES, deck_suits
from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TNull,
    TOptional,
    TPlayer,
    TString,
    TTeam,
    Type,
    assignable,
    subscriptable,
    unify,
)

# Declared scalar type names → their Type. Enum names (`Suit`/`Rank`/`Direction`)
# and unknown names (user-defined types, deferred) are handled separately.
_SCALAR_TYPES: dict[str, type] = {
    "Integer": TInteger,
    "Boolean": TBoolean,
    "String": TString,
    "Player": TPlayer,
    "Team": TTeam,
    "Card": TCard,
}
_ENUM_TYPES = frozenset({"Suit", "Rank", "Direction"})


def type_from_name(name: str, optional: bool) -> Type:
    """Map a declared type name (a `StateDecl` `type_name`) to a `Type`.

    Unknown names — user-defined types, deferred to a later stage — resolve to
    the permissive `TAny`. ``optional`` wraps the result in `TOptional`.
    """
    base: Type
    if name in _SCALAR_TYPES:
        base = _SCALAR_TYPES[name]()
    elif name in _ENUM_TYPES:
        base = TEnum(name)
    else:
        base = TAny()
    return TOptional(base) if optional else base


def value_enum_map(game: Game) -> dict[str, TEnum]:
    """Map each deck/stdlib enum *value* to its enum type.

    `resolve` collapses suits, ranks, and directions into one `enum_value`
    ref_kind; the type checker re-derives which enum each value belongs to so a
    `Suit` is not confused with an `Integer` or a `Direction`.
    """
    m: dict[str, TEnum] = {}
    for suit in deck_suits(game.deck):
        m[suit] = TEnum("Suit")
    for rank in game.ranking:
        m[rank] = TEnum("Rank")
    for direction in DIRECTION_VALUES:
        m[direction] = TEnum("Direction")
    return m


@dataclass(frozen=True)
class TypeEnv:
    """The types a bare name resolves against during inference: declared state
    vars, zone contents, deck/stdlib enum values, and scoped local binders."""

    state_vars: Mapping[str, Type] = field(default_factory=dict)
    zones: Mapping[str, Type] = field(default_factory=dict)
    value_enums: Mapping[str, TEnum] = field(default_factory=dict)
    locals: Mapping[str, Type] = field(default_factory=dict)

    def with_local(self, name: str, t: Type) -> "TypeEnv":
        return replace(self, locals={**self.locals, name: t})


def infer(e: n.Expr, env: TypeEnv) -> Type:
    """Infer the type of an expression. Unrefined arms return `TAny` (the
    permissive top); precision is added construct by construct."""
    match e:
        case n.IntLit():
            return TInteger()
        case n.StrLit():
            return TString()
        case n.CardLiteral():
            return TCard()
        case n.AllPlayers():
            return TCollection(TPlayer())
        case n.NameRef():
            return _name_type(e, env)
        case n.Subscript():
            obj = infer(e.obj, env)
            return obj.element if isinstance(obj, TCollection) else TAny()
        case n.Call():
            sig = CALL_SIGS.get(e.func)
            return sig.ret if sig is not None else TAny()
        case n.MethodCall():
            msig = METHOD_SIGS.get(e.method)
            if msig is None:
                return TAny()
            if msig.returns_receiver:
                return infer(e.obj, env)
            return msig.ret if msig.ret is not None else TAny()
        case n.BinOp():
            if e.op in ("==", "!=", "<", ">", "<=", ">=", "and", "or"):
                return TBoolean()
            if e.op in ("+", "-", "*"):
                return TInteger()
            return TAny()  # offset_by and any future operators
        case n.Not() | n.IsCheck() | n.Quantifier():
            return TBoolean()
        case n.Choose():
            return TInteger()
        case n.Comprehension():
            return TInteger() if e.agg in ("sum", "count") else TAny()
        case n.PlayerQuery():
            match e.kind:
                case "set":
                    return TCollection(TPlayer())
                case "count":
                    return TInteger()
                case _:  # "pick"
                    return TPlayer()
        case n.IfExpr():
            return _ifexpr_type(e, env)
        case n.Member() | n.Lambda():
            return TAny()  # member access (pronouns/sugar) and lambda values: deferred
        case _ as unreachable:
            assert_never(unreachable)


def _ifexpr_type(e: n.IfExpr, env: TypeEnv) -> Type:
    result = infer(e.then, env)
    for _cond, branch in e.elifs:
        merged = unify(result, infer(branch, env))
        result = merged if merged is not None else TAny()
    merged = unify(result, infer(e.otherwise, env))
    return merged if merged is not None else TAny()


def _name_type(e: n.NameRef, env: TypeEnv) -> Type:
    match e.ref_kind:
        case "local":
            return env.locals.get(e.name, TAny())
        case "state_var":
            return env.state_vars.get(e.name, TAny())
        case "zone":
            return env.zones.get(e.name, TAny())
        case "enum_value":
            return env.value_enums.get(e.name, TAny())
        case "bool":
            return TBoolean()
        case "null":
            return TNull()  # the `none` literal — assignable only to optionals
        case _:
            return TAny()  # pronoun / function / routing / unresolved


def _type_name(t: Type) -> str:
    if isinstance(t, TNull):
        return "none"
    if isinstance(t, TOptional):
        return f"{_type_name(t.inner)}?"
    if isinstance(t, TCollection):
        return f"Collection<{_type_name(t.element)}>"
    if isinstance(t, TEnum):
        return t.name
    return type(t).__name__[1:]  # TInteger -> "Integer", TPlayer -> "Player", …


def _state_blocks(game: Game) -> list[n.StateBlock]:
    blocks: list[n.StateBlock] = []
    if game.state is not None:
        blocks.append(game.state)

    def rec(phase: n.Phase) -> None:
        for item in phase.items:
            if isinstance(item, n.StateBlock):
                blocks.append(item)
            elif isinstance(item, n.Phase):
                rec(item)

    for phase in game.phases:
        rec(phase)
    return blocks


def env_from_game(game: Game) -> TypeEnv:
    """Build the top-level type environment: declared state vars (value types),
    zone contents, and the deck/stdlib enum value map."""
    state_vars: dict[str, Type] = {}
    for block in _state_blocks(game):
        for decl in block.decls:
            t = type_from_name(decl.type_name, decl.optional)
            # An indexed state var (`score[player] : Integer`) is a per-key map —
            # a collection whose subscript yields the declared value type.
            state_vars[decl.name] = TCollection(t) if decl.index is not None else t
    zones: dict[str, Type] = {
        z.name: ZONE_CONTENT.get(z.type_ref.name, TCollection(TAny()))
        for z in game.zones
    }
    return TypeEnv(state_vars=state_vars, zones=zones, value_enums=value_enum_map(game))


def _stmt_tree(s: n.Stmt) -> Iterator[n.Stmt]:
    yield s
    if isinstance(s, (n.ForEach, n.EachSimultaneous)):
        yield from _stmt_tree(s.body)
    elif isinstance(s, n.RepeatUntil):
        for x in s.body:
            yield from _stmt_tree(x)
    elif isinstance(s, n.IfStmt):
        for x in s.then_body:
            yield from _stmt_tree(x)
        for x in s.else_body or ():
            yield from _stmt_tree(x)


def _phase_statements(phase: n.Phase) -> Iterator[n.Stmt]:
    for item in phase.items:
        if isinstance(item, n.Phase):
            yield from _phase_statements(item)
        elif isinstance(item, (n.BeforeEach, n.AfterEach)):
            for s in item.body:
                yield from _stmt_tree(s)
        elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo)):
            pass
        else:
            yield from _stmt_tree(item)


def _all_statements(game: Game) -> Iterator[n.Stmt]:
    for routing in game.routings:
        for s in routing.body:
            yield from _stmt_tree(s)
    for move_type in game.move_types:
        for s in move_type.effect:
            yield from _stmt_tree(s)
    for phase in game.phases:
        yield from _phase_statements(phase)


def _arg_exprs(args: tuple[n.Arg, ...]) -> list[n.Expr]:
    """The positional expression arguments of a call (named args are not used by
    the stdlib functions/methods being checked)."""
    return [a for a in args if not isinstance(a, n.NamedArg)]


def _child_exprs(e: n.Expr) -> list[n.Expr]:
    if isinstance(e, n.Member):
        return [e.obj]
    if isinstance(e, n.Subscript):
        return [e.obj, e.index]
    if isinstance(e, n.Call):
        return _arg_exprs(e.args)
    if isinstance(e, n.MethodCall):
        return [e.obj, *_arg_exprs(e.args)]
    if isinstance(e, n.BinOp):
        return [e.left, e.right]
    if isinstance(e, (n.Not, n.IsCheck)):
        return [e.operand]
    if isinstance(e, (n.Lambda, n.Quantifier)):
        return [e.body]
    if isinstance(e, n.Comprehension):
        return [e.source, e.body]
    if isinstance(e, n.Choose):
        return [e.lo, e.hi]
    if isinstance(e, n.PlayerQuery):
        return [e.pred]
    if isinstance(e, n.IfExpr):
        out = [e.cond, e.then]
        for cond, branch in e.elifs:
            out += [cond, branch]
        out.append(e.otherwise)
        return out
    return []  # leaves: NameRef, IntLit, StrLit, CardLiteral, AllPlayers


def _check_expr(e: n.Expr, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Recursively validate a single expression: stdlib argument types and
    subscript legality. Types of unrefined sub-parts are `TAny` (permissive)."""
    for child in _child_exprs(e):
        _check_expr(child, env, bag)
    if isinstance(e, n.Call):
        sig = CALL_SIGS.get(e.func)
        if sig is not None:
            args = _arg_exprs(e.args)
            if len(args) != len(sig.params):
                bag.error(
                    f"{e.func}() expects {len(sig.params)} argument(s), got {len(args)}",
                    e.span,
                )
            else:
                for arg, param in zip(args, sig.params):
                    got = infer(arg, env)
                    if not assignable(got, param):
                        bag.error(
                            f"{e.func}() expects {_type_name(param)}, got {_type_name(got)}",
                            e.span,
                        )
    elif isinstance(e, n.MethodCall):
        msig = METHOD_SIGS.get(e.method)
        if msig is not None and not msig.lambda_arg:
            args = _arg_exprs(e.args)
            if len(args) != len(msig.params):
                bag.error(
                    f".{e.method}() expects {len(msig.params)} argument(s), got {len(args)}",
                    e.span,
                )
            else:
                for arg, param in zip(args, msig.params):
                    got = infer(arg, env)
                    if not assignable(got, param):
                        bag.error(
                            f".{e.method}() expects {_type_name(param)}, got {_type_name(got)}",
                            e.span,
                        )
    elif isinstance(e, n.Subscript):
        obj = infer(e.obj, env)
        if not subscriptable(obj):
            bag.error(f"cannot index {_type_name(obj)} (not a collection)", e.span)


def _check_bool(e: n.Expr, env: TypeEnv, bag: DiagnosticBag, where: str) -> None:
    t = infer(e, env)
    if not isinstance(t, (TBoolean, TAny)):
        bag.error(f"{where} must be Boolean, got {_type_name(t)}", e.span)


def _stmt_exprs(s: n.Stmt) -> list[n.Expr]:
    """The expressions held directly by a statement (its child *statements* are
    visited separately by the statement walk)."""
    if isinstance(s, n.AssignStmt):
        return [s.value] + ([s.index] if s.index is not None else [])
    if isinstance(s, n.LetStmt):
        return [s.value]
    if isinstance(s, n.Movement):
        out: list[n.Expr] = []
        if not isinstance(s.amount, str):
            out.append(s.amount)
        for opt in (s.source, s.dest, s.visibility):
            if opt is not None:
                out.append(opt)
        return out
    if isinstance(s, n.EpistemicOp):
        return [s.target]
    if isinstance(s, n.Offer):
        return [s.player]
    if isinstance(s, n.Round):
        return [s.leader, s.participants] + ([s.trump] if s.trump is not None else [])
    if isinstance(s, n.Instantiate):
        return [a.value for a in s.args if not isinstance(a.value, n.Movement)]
    if isinstance(s, (n.IfStmt, n.RepeatUntil)):
        return [s.cond]
    return []  # ForEach / EachSimultaneous / RotateStmt: no direct value expressions


def _all_phases(game: Game) -> Iterator[n.Phase]:
    def rec(phase: n.Phase) -> Iterator[n.Phase]:
        yield phase
        for item in phase.items:
            if isinstance(item, n.Phase):
                yield from rec(item)

    for phase in game.phases:
        yield from rec(phase)


def _check_assign(stmt: n.AssignStmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    target = env.state_vars.get(stmt.name)
    if target is None:
        return  # not a typed state var (a let-local, or unknown — left permissive)
    if stmt.index is not None and isinstance(target, TCollection):
        target = target.element  # an indexed assignment writes one element
    rhs = infer(stmt.value, env)
    if stmt.op in ("+=", "-="):
        if not assignable(rhs, TInteger()):
            bag.error(
                f"'{stmt.name}' {stmt.op} expects an Integer, got {_type_name(rhs)}",
                stmt.span,
            )
    elif not assignable(rhs, target):
        bag.error(
            f"cannot assign {_type_name(rhs)} to '{stmt.name}' ({_type_name(target)})",
            stmt.span,
        )


def typecheck(game: Game) -> Game:
    bag = DiagnosticBag()

    players = game.players
    if players.low < 1:
        bag.error(f"a game needs at least one player, got {players.low}", players.span)
    if players.high is not None and players.high < players.low:
        bag.error(
            f"player range upper bound {players.high} precedes lower bound {players.low}",
            players.span,
        )

    env = env_from_game(game)
    for stmt in _all_statements(game):
        for expr in _stmt_exprs(stmt):
            _check_expr(expr, env, bag)
        if isinstance(stmt, n.AssignStmt):
            _check_assign(stmt, env, bag)
        elif isinstance(stmt, n.IfStmt):
            _check_bool(stmt.cond, env, bag, "if condition")
        elif isinstance(stmt, n.RepeatUntil):
            _check_bool(stmt.cond, env, bag, "repeat-until condition")
    for phase in _all_phases(game):
        if phase.qualifier is not None:
            _check_expr(phase.qualifier.expr, env, bag)
            _check_bool(
                phase.qualifier.expr, env, bag, f"phase '{phase.name}' condition"
            )
    if game.loser is not None:
        _check_expr(game.loser.selection, env, bag)

    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game
