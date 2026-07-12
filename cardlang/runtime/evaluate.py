"""Expression evaluator.

`evaluate(expr, ctx)` walks an `n.Expr` and returns a runtime value. The key
move is `NameRef` dispatch on the `ref_kind` the resolver assigned — that is
exactly what the deep-resolution pass exists to make possible.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, assert_never

from cardlang.ast import nodes as n
from cardlang.runtime import observe, stdlib
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
        case n.ListLit():
            return [evaluate(item, ctx) for item in e.elements]
        case n.Member():
            return _member_eval(e, ctx)
        case n.StructLit():
            return StructValue(
                e.type_name, {fi.name: evaluate(fi.value, ctx) for fi in e.fields}
            )
        case n.Subscript():
            return _subscript(e, ctx)
        case n.Call():
            fn = ctx.rs.function_index.get(e.func)
            if fn is not None:
                return _user_function(fn, e.args, ctx)
            return stdlib.call(e.func, [evaluate(_pos(a), ctx) for a in e.args], ctx)
        case n.BinOp():
            return _binop(e, ctx)
        case n.Not():
            return not evaluate(e.operand, ctx)
        case n.IsCheck():
            return _is_check(e, ctx)
        case n.Quantifier():
            return _quantifier(e, ctx)
        case n.IfExpr():
            return _if_expr(e, ctx)
        case n.Comprehension():
            return _comprehension(e, ctx)
        case n.PlayerQuery():
            return _player_query(e, ctx)
        case n.CardQuery():
            return _card_query(e, ctx)
        case n.Choose():
            return _choose(e, ctx)
        case _ as unreachable:
            assert_never(unreachable)


def _choose(e: n.Choose, ctx: Ctx) -> Any:
    assert e.domain == "integer"
    lo = int(evaluate(e.lo, ctx))
    hi = int(evaluate(e.hi, ctx))
    # Guard the live *range*, not just the drawn value: a range that escapes its
    # declared `0 .. ceiling` domain would offer a legal action with no OpenSpiel
    # id, and a value-only check passes whenever the chooser happens to draw
    # inside the reserved block. `static_ceiling` is non-None (resolve enforced).
    ceiling = n.static_ceiling(e)
    assert ceiling is not None
    if lo < 0 or hi > ceiling:
        raise RuntimeError(
            f"`choose integer in {lo} .. {hi}` escaped its declared domain "
            f"0 .. {ceiling}: every legal value must have an OpenSpiel action id "
            f"within the ceiling reserved up front (raise the `up to` bound "
            f"or fix the range)"
        )
    candidates = list(range(lo, hi + 1))
    if not candidates:
        raise RuntimeError(
            f"`choose integer in {lo} .. {hi}` has no value to choose (empty range): "
            f"a choice must offer at least one candidate"
        )
    actor = ctx.require_actor("a `choose`")
    value = ctx.chooser(actor, candidates, 1)[0]
    observe.choice(ctx, actor, value)
    observe.announce(ctx, actor, value)
    return value


def _pos(arg: n.Arg) -> n.Expr:
    if isinstance(arg, n.NamedArg):
        raise NotImplementedError("named call arguments not used by Hearts")
    return arg


def _user_function(fn: n.FunctionDef, args: tuple[n.Arg, ...], ctx: Ctx) -> Any:
    """Evaluate a user function hermetically: the arguments evaluate in the caller's
    context, then the body runs in a fresh scope holding only the parameters, over
    the shared game/phase state. Hermeticity for `actor`/`action`/`outcome` is
    enforced at compile time (resolve rejects those pronouns in a body), so the
    `outcome`/`action` clears here are belt-and-suspenders. `current_player` is
    *inherited*, not cleared: a body may read a bare per-player zone (e.g.
    `hand.cards_of_suit(...)`), whose family instance resolves through the acting
    player the caller set."""
    values = [evaluate(_pos(a), ctx) for a in args]
    body_ctx = replace(
        ctx,
        locals={p.name: v for p, v in zip(fn.params, values)},
        outcome=None,
        action=None,
    )
    return evaluate(fn.body, body_ctx)


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
        case "in":
            container = right.cards if isinstance(right, Zone) else right
            return left in container
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


def _quantifier(e: n.Quantifier, ctx: Ctx) -> bool:
    domain = _role_domain(e.role, ctx)
    results = (evaluate(e.body, ctx.with_local(e.binder, x)) for x in domain)
    return any(results) if e.kind == "any" else all(results)


def _role_domain(role: str, ctx: Ctx) -> list[Any]:
    if role == "player":
        return list(ctx.rs.seating.players)
    if role == "team":
        return list(ctx.rs.teams)
    if role == "suit":
        return list(ctx.rs.suits)
    if role == "rank":
        return list(ctx.rs.ranks)
    raise AssertionError(f"unknown quantifier role '{role}' (resolve rejects these)")


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


def _card_query(e: n.CardQuery, ctx: Ctx) -> Any:
    source = evaluate(e.source, ctx)
    cards = source.cards if isinstance(source, Zone) else list(source)
    if e.pred is None:  # the bare `number of cards in <zone>` size idiom
        assert e.kind == "count"
        return len(cards)
    results = [bool(evaluate(e.pred, ctx.with_local("card", c))) for c in cards]
    match e.kind:
        case "set":
            return [c for c, ok in zip(cards, results) if ok]
        case "count":
            return sum(results)
        case "any":
            return any(results)
        case "all":
            return all(results)
        case _:
            raise AssertionError(f"unknown card-query kind '{e.kind}'")


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
    if e.filter is not None:
        elements = [
            x
            for x in elements
            if evaluate(e.filter, ctx.with_local(e.binder, x))
        ]
    values = [evaluate(e.body, ctx.with_local(e.binder, x)) for x in elements]
    match e.agg:
        case "sum":
            return sum(values)
        case "max":
            if not values:
                assert e.default is not None, "grammar makes `or <default>` mandatory"
                return evaluate(e.default, ctx)
            return max(values)
        case "min":
            if not values:
                assert e.default is not None, "grammar makes `or <default>` mandatory"
                return evaluate(e.default, ctx)
            return min(values)
        case _:
            raise AssertionError(f"unknown aggregator '{e.agg}'")
