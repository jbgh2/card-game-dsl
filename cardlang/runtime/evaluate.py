"""Expression evaluator.

`evaluate(expr, ctx)` walks an `n.Expr` and returns a runtime value. The key
move is `NameRef` dispatch on the `ref_kind` the resolver assigned — that is
exactly what the deep-resolution pass exists to make possible.
"""

from __future__ import annotations

from typing import Any, assert_never

from cardlang.ast import nodes as n
from cardlang.runtime import stdlib
from cardlang.runtime.state import Ctx, Move, StructValue, Zone
from cardlang.runtime.values import Card


def evaluate(e: n.Expr, ctx: Ctx) -> Any:
    match e:
        case n.NameRef():
            return _name(e, ctx)
        case n.IntLit():
            return e.value
        case n.StrLit():
            return e.value
        case n.CardLiteral():
            return Card(e.rank, e.suit)
        case n.AllPlayers():
            return list(ctx.rs.seating.players)
        case n.Member():
            return _member_eval(e, ctx)
        case n.StructLit():
            return StructValue(
                e.type_name, {fi.name: evaluate(fi.value, ctx) for fi in e.fields}
            )
        case n.Subscript():
            return _subscript(e, ctx)
        case n.Call():
            return stdlib.call(e.func, [evaluate(_pos(a), ctx) for a in e.args], ctx)
        case n.MethodCall():
            return _method(e, ctx)
        case n.BinOp():
            return _binop(e, ctx)
        case n.Not():
            return not evaluate(e.operand, ctx)
        case n.IsCheck():
            return _is_check(e, ctx)
        case n.Lambda():
            return _closure(e, ctx)
        case n.Quantifier():
            return _quantifier(e, ctx)
        case n.IfExpr():
            return _if_expr(e, ctx)
        case n.Comprehension():
            return _comprehension(e, ctx)
        case n.PlayerQuery():
            return _player_query(e, ctx)
        case n.Choose():
            return _choose(e, ctx)
        case _ as unreachable:
            assert_never(unreachable)


def _choose(e: n.Choose, ctx: Ctx) -> Any:
    assert e.domain == "integer"
    lo = int(evaluate(e.lo, ctx))
    hi = int(evaluate(e.hi, ctx))
    candidates = list(range(lo, hi + 1))
    player = ctx.current_player if ctx.current_player is not None else 0
    return ctx.chooser(player, candidates, 1)[0]


def _pos(arg: n.Arg) -> n.Expr:
    if isinstance(arg, n.NamedArg):
        raise NotImplementedError("named call arguments not used by Hearts")
    return arg


def _name(e: n.NameRef, ctx: Ctx) -> Any:
    match e.ref_kind:
        case "local":
            return ctx.locals[e.name]
        case "state_var":
            return ctx.rs.get(e.name)
        case "zone":
            if ctx.rs.zones.is_family(e.name):
                assert ctx.current_player is not None
                return ctx.rs.zones.instance(e.name, ctx.current_player)
            return ctx.rs.zones.single(e.name)
        case "null":
            return None  # the absence literal `none`
        case "bool":
            return e.name == "true"
        case "enum_value":
            return e.name  # suits/directions are their own string value
        case "pronoun":
            return _pronoun(e.name, ctx)
        case "function":
            return stdlib.value_function(e.name)
        case _:
            raise AssertionError(f"name '{e.name}' was not resolved (ref_kind=None)")


def _pronoun(name: str, ctx: Ctx) -> Any:
    match name:
        case "state":
            # Inside a round, `state` is the live accumulator; once a round has
            # returned, the surrounding body sees that round's terminal state.
            # Reading `state` with neither active is a bug (e.g. a body that reads
            # `state.x` before any round has run) — fail loudly, don't return a
            # stale or empty frame.
            if ctx.rs.mech_state:
                return ctx.rs.mech_state[-1]
            if ctx.rs.last_round_state is None:
                raise AssertionError(
                    "`state` read with no active or just-completed round"
                )
            return ctx.rs.last_round_state
        case "outcome":
            return ctx.outcome
        case "action":
            return ctx.action
        case "active_rules":
            return ctx.active_rules
        case "actor":
            return ctx.current_player
        case _:
            raise AssertionError(f"unknown pronoun '{name}'")


def _member_eval(e: n.Member, ctx: Ctx) -> Any:
    obj = evaluate(e.obj, ctx)
    if isinstance(obj, StructValue) and e.field not in obj.fields:
        # A derived field: compute its expression with the struct's declared
        # fields bound as locals (the scoped resolve pass classified those bare
        # field references as `"local"`).
        tdef = ctx.rs.type_index[obj.type_name]
        derived = next(d for d in tdef.derived if d.name == e.field)
        dctx = ctx
        for k, v in obj.fields.items():
            dctx = dctx.with_local(k, v)
        return evaluate(derived.value, dctx)
    return _member(obj, e.field)


def _member(obj: Any, field: str) -> Any:
    if isinstance(obj, Card):
        return getattr(obj, field)
    if isinstance(obj, Move):
        return getattr(obj, field)
    if isinstance(obj, StructValue):
        return obj.fields[field]
    if isinstance(obj, dict):
        return obj[field]
    raise AssertionError(f"cannot read field '{field}' of {obj!r}")


def _subscript(e: n.Subscript, ctx: Ctx) -> Any:
    obj = e.obj
    index = evaluate(e.index, ctx)
    if isinstance(obj, n.NameRef) and obj.ref_kind == "zone":
        return ctx.rs.zones.instance(obj.name, index)
    return evaluate(obj, ctx)[index]


def _method(e: n.MethodCall, ctx: Ctx) -> Any:
    receiver = evaluate(e.obj, ctx)
    assert isinstance(receiver, Zone), f"method '{e.method}' on non-zone {receiver!r}"
    cards = receiver.cards
    match e.method:
        case "where":
            pred = evaluate(_pos(e.args[0]), ctx)
            return [c for c in cards if pred(c)]
        case "cards_of_suit":
            suit = evaluate(_pos(e.args[0]), ctx)
            return [c for c in cards if c.suit == suit]
        case _:
            raise AssertionError(f"unknown zone method '{e.method}'")


def _binop(e: n.BinOp, ctx: Ctx) -> Any:
    if e.op == "and":
        return bool(evaluate(e.left, ctx)) and bool(evaluate(e.right, ctx))
    if e.op == "or":
        return bool(evaluate(e.left, ctx)) or bool(evaluate(e.right, ctx))
    left = evaluate(e.left, ctx)
    right = evaluate(e.right, ctx)
    match e.op:
        case "+":
            return left + right
        case "-":
            return left - right
        case "*":
            return left * right
        case "==":
            return left == right
        case "!=":
            return left != right
        case ">=":
            return left >= right
        case "<=":
            return left <= right
        case ">":
            return left > right
        case "<":
            return left < right
        case "offset_by":
            return ctx.rs.seating.offset_by(left, right)
        case _:
            raise AssertionError(f"unknown operator '{e.op}'")


def _is_check(e: n.IsCheck, ctx: Ctx) -> bool:
    value = evaluate(e.operand, ctx)
    match e.kind:
        case "none":
            return value is None
        case "not_none":
            return value is not None
        case "empty":
            assert isinstance(value, Zone)
            return value.empty
        case "not_empty":
            assert isinstance(value, Zone)
            return not value.empty
        case _:
            raise AssertionError(f"unknown is-check '{e.kind}'")


def _closure(e: n.Lambda, ctx: Ctx):  # type: ignore[no-untyped-def]
    return lambda value: evaluate(e.body, ctx.with_local(e.param, value))


def _quantifier(e: n.Quantifier, ctx: Ctx) -> bool:
    domain = _role_domain(e.role, ctx)
    results = (evaluate(e.body, ctx.with_local(e.binder, x)) for x in domain)
    return any(results) if e.kind == "any" else all(results)


def _role_domain(role: str, ctx: Ctx) -> list[Any]:
    if role == "player":
        return list(ctx.rs.seating.players)
    if role == "team":
        return list(ctx.rs.teams)
    raise NotImplementedError(f"quantifier role '{role}' not supported yet")


def _player_query(e: n.PlayerQuery, ctx: Ctx) -> Any:
    matches = [
        p
        for p in ctx.rs.seating.players
        if evaluate(e.pred, ctx.with_local("player", p))
    ]
    match e.kind:
        case "set":
            return matches
        case "count":
            return len(matches)
        case "pick":
            assert len(matches) == 1, (
                f"`the player where …` matched {len(matches)} players, expected 1"
            )
            return matches[0]
        case _:
            raise AssertionError(f"unknown player-query kind '{e.kind}'")


def _if_expr(e: n.IfExpr, ctx: Ctx) -> Any:
    if evaluate(e.cond, ctx):
        return evaluate(e.then, ctx)
    for cond, then in e.elifs:
        if evaluate(cond, ctx):
            return evaluate(then, ctx)
    return evaluate(e.otherwise, ctx)


def _comprehension(e: n.Comprehension, ctx: Ctx) -> Any:
    source = evaluate(e.source, ctx)
    elements = source.cards if isinstance(source, Zone) else list(source)
    values = [evaluate(e.body, ctx.with_local(e.binder, x)) for x in elements]
    match e.agg:
        case "sum":
            return sum(values)
        case "count":
            return len(values)
        case "max":
            return max(values)
        case "min":
            return min(values)
        case _:
            raise AssertionError(f"unknown aggregator '{e.agg}'")
