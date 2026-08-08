"""Expression evaluator.

`evaluate(expr, ctx)` walks an `n.Expr` and returns a runtime value. The key
move is `NameRef` dispatch on the `ref_kind` the resolver assigned — that is
exactly what the deep-resolution pass exists to make possible.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, assert_never

from cardlang.ast import nodes as n
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.domains import require_role, role_members
from cardlang.runtime import builtins, observe, primitives, reads
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.state import Ctx, Move, StructValue, elements
from cardlang.runtime.values import Card
from cardlang.stdlib.round_state import ROUND_STATE_FIELDS


def native_call(name: str, args: list[Any], ctx: Ctx) -> Any:
    """Dispatch `name` into native code: the Builtins half first (generic
    functions the language ships), the Primitives half second (sanctioned
    game-local Python), and a loud refusal from the second if neither claims
    it.

    The chain lives here rather than in either half so that neither half
    depends on the other — `builtins.py`'s and `primitives.py`'s arm counts
    are then independently readable, which is what makes the Primitive count
    usable as the elimination metric. Arguments are coerced ONCE, before the
    chain, because `deep_freeze` dominates playout cost.
    """
    sig = CALL_SIGS.get(name)
    if sig is not None:
        args = reads.coerce_args(sig, args)
    result = builtins.call(name, args, ctx)
    if result is builtins.NOT_A_BUILTIN:
        return primitives.call(name, args, ctx)
    return result


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
            return native_call(e.func, [evaluate(_pos(a), ctx) for a in e.args], ctx)
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
        case n.DomainQuery():
            return _domain_query(e, ctx)
        case n.Choose():
            return _choose(e, ctx)
        case _ as unreachable:
            assert_never(unreachable)


def _choose(e: n.Choose, ctx: Ctx) -> Any:
    assert e.domain == "integer"  # `choose integer` is the grammar's only choose form
    lo = int(evaluate(e.lo, ctx))
    hi = int(evaluate(e.hi, ctx))
    # Guard the live *range*, not just the drawn value: a range that escapes its
    # declared `0 .. ceiling` domain would offer a legal action with no OpenSpiel
    # id, and a value-only check passes whenever the chooser happens to draw
    # inside the reserved block. `static_ceiling` is non-None (resolve enforced).
    ceiling = n.static_ceiling(e)
    assert ceiling is not None  # resolve rejects a choose with no static ceiling
    if lo < 0 or hi > ceiling:
        raise OwnerGuardError(
            f"`choose integer in {lo} .. {hi}` escaped its declared domain "
            f"0 .. {ceiling}: every legal value must have an OpenSpiel action id "
            f"within the ceiling reserved up front (raise the `up to` bound "
            f"or fix the range)"
        )
    candidates = list(range(lo, hi + 1))
    if not candidates:
        raise OwnerGuardError(
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
    the shared game/phase state. Hermeticity for `actor`/`action`/`winner` is
    enforced at compile time (resolve rejects those pronouns in a body), so the
    `winner`/`action` clears here are belt-and-suspenders. `current_player` is
    *inherited*, not cleared: a body may read a bare per-player zone (e.g.
    `cards in hand where card.suit is spades`), whose family instance resolves
    through the acting player the caller set."""
    values = [evaluate(_pos(a), ctx) for a in args]
    body_ctx = replace(
        ctx,
        locals={p.name: v for p, v in zip(fn.params, values)},
        winner=None,
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
                # Shadow Guard behind resolve's `_check_position_family_refs`
                # Owner Guard: a bare position-family read has no per-player
                # instance to sugar to, and `instance(name, seat)` would
                # key-error far from the cause.
                if ctx.rs.zones.zone_index[e.name] in ctx.rs.position_domains:
                    raise ShadowGuardError(
                        "resolve._check_position_family_refs",
                        f"'{e.name}' is a position-indexed zone family and "
                        f"must be subscripted — it has no per-player "
                        f"instances",
                    )
                if ctx.current_player is None:
                    # The bare-family actor sugar (`hand` = the acting
                    # player's hand) read outside any acting context — a phase
                    # body has no actor. User-reachable (`shuffle hand` in a
                    # phase body checks clean today), so it fails as an
                    # Owner Guard with the fix named, not a bare assert. A static Owner Guard needs statement-position
                    # context (which construct encloses this read) that no
                    # pass threads today.
                    raise OwnerGuardError(
                        f"'{e.name}' is a per-player zone family read with no "
                        f"acting player — subscript it (`{e.name}[p]`) or use "
                        f"it where an actor is bound (a move effect, a `for "
                        f"each player` body)"
                    )
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
            return primitives.value_function(e.name)
        case _:
            raise AssertionError(f"name '{e.name}' was not resolved (ref_kind=None)")


def _pronoun(name: str, ctx: Ctx) -> Any:
    match name:
        case "state":
            # Inside a round, `state` is the live accumulator; once a round has
            # returned, the surrounding body sees that round's terminal state.
            # Reading `state` with neither active — a body that reads `state.x`
            # before any round has run — is a game-description error (the
            # checker validates the field, not the read's position in time),
            # so it fails as an Owner Guard, not a stale/empty frame.
            if ctx.rs.mech_state:
                return ctx.rs.mech_state[-1]
            if ctx.rs.last_round_state is None:
                raise OwnerGuardError(
                    "`state` read with no active or just-completed round — "
                    "`state.` is defined only inside a `round` or directly "
                    "after one returns"
                )
            return ctx.rs.last_round_state
        case "winner":
            return ctx.winner
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
    if isinstance(obj, Card):
        # A content item's axis field -> its `Card` attribute: identity for a
        # card deck ("suit"->"suit"), the piece set's map for a piece
        # ("side"->"suit", "kind"->"rank"). One source (rs.axis_attr, set by the
        # driver) so member access matches the flavor-keyed field table.
        return getattr(obj, ctx.rs.axis_attr.get(e.field, e.field))
    return _member(obj, e.field)


def _member(obj: Any, field: str) -> Any:
    # `Card` is handled in `_member_eval` (it needs the flavor axis map); this
    # sees Move / StructValue / dict / the deliberately-loose fallbacks.
    if isinstance(obj, Move):
        return getattr(obj, field)
    if isinstance(obj, StructValue):
        return obj.fields[field]
    if isinstance(obj, dict):
        if field not in obj:
            # REACHABLE from checked DSL, and deliberately so: the checker validates
            # `state.<field>` against the UNION of every form's published set, because
            # a reference is not statically attached to a form (a library rule is
            # activated in context). So a trick game CAN name a climb-published field
            # and reach here. That makes this a game-description error — the currency
            # the runtime uses for "the description asked for something impossible at
            # play time" — not a compiler bug, and not a bare KeyError.
            #
            # The message lists only what this form PUBLISHES, never the raw
            # accumulator: the accumulator also holds the form's working memory
            # (`idx`, `order`, …), and naming those here would advertise, in the
            # engine's own voice, the exact spellings the checker rejects.
            published = sorted(k for k in obj if k in ROUND_STATE_FIELDS)
            raise OwnerGuardError(
                f"this round publishes no `{field}` — it publishes "
                f"{', '.join(f'`{k}`' for k in published) or 'nothing'}. "
                f"`state.` reads the round that is actually running, and the checker "
                f"can only validate the field against every form's published set"
            )
        return obj[field]
    # Reachable when a value the checker deliberately leaves loose (an
    # `outcome` payload, an unregistered action field — TAny) is dereferenced
    # at play time: a game-description error, refused by its Owner Guard.
    raise OwnerGuardError(
        f"cannot read field '{field}' of {obj!r} — the checker leaves this "
        f"value's type open, so the read is checked here"
    )


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
        case "is":
            return left == right
        case "is_not":
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
            return left in elements(right)
        case _:
            raise AssertionError(f"unknown operator '{e.op}'")


def _is_check(e: n.IsCheck, ctx: Ctx) -> bool:
    value = evaluate(e.operand, ctx)
    match e.kind:
        case "none":
            return value is None
        case "not_none":
            return value is not None
        case "empty" | "not_empty":
            # typecheck's `_check_is_check` rejects a concrete non-collection
            # operand statically, but a `TAny`-typed operand (a pronoun
            # member, an unrefined query result) reaches here unchecked — a
            # Zone (a singleton/family instance) and a plain `list` (a
            # CardQuery/PlayerQuery `set` result, a `[...]` literal) are both
            # legitimate sized collections, so fold `len()` over any of them
            # rather than assert one shape. A genuinely non-collection value
            # is a typed runtime error, never a bare assert.
            if not hasattr(value, "__len__"):
                neg = "not " if e.kind == "not_empty" else ""
                raise OwnerGuardError(
                    f"`is {neg}empty` expects a zone or collection, got "
                    f"{value!r} — this value's type is left open by the "
                    "checker, so the read is checked here"
                )
            empty = len(value) == 0
            return not empty if e.kind == "not_empty" else empty
        case _:
            raise AssertionError(f"unknown is-check '{e.kind}'")


def _quantifier(e: n.Quantifier, ctx: Ctx) -> bool:
    # `role_members` (cardlang/domains.py) is the ONE runtime member enumerator
    # for the quantifiable-domain registry: the players/teams/suits/ranks a
    # quantifier binds over, in the registry's iteration order. A quantifier
    # never rebinds the actor (the `binds_actor` column is `for each`'s
    # concern) — `any player where …` asks a question about each seat, it does
    # not make a decision as that seat.
    domain = role_members(require_role(e.role, "quantifier role"), ctx)
    results = (evaluate(e.body, ctx.with_local(e.binder, x)) for x in domain)
    return any(results) if e.kind == "any" else all(results)


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
            if len(matches) != 1:
                # A runtime DATA condition, not a compiler invariant: whether
                # the predicate picks out exactly one player depends on live
                # state the checker cannot see. Typed error, not an assert —
                # the game author wrote a `the player where …` whose premise
                # failed, and they should hear that in the runtime's failure
                # currency.
                raise OwnerGuardError(
                    f"`the player where …` matched {len(matches)} players, "
                    f"expected exactly 1"
                )
            return matches[0]
        case _:
            raise AssertionError(f"unknown player-query kind '{e.kind}'")


def _card_query(e: n.CardQuery, ctx: Ctx) -> Any:
    source = evaluate(e.source, ctx)
    cards = list(elements(source))
    if e.pred is None:  # the bare `number of cards in <zone>` size idiom
        assert e.kind == "count"  # parse builds a pred-less query only for that idiom
        return len(cards)
    # `any`/`all` short-circuit over the same card order the eager `set`/
    # `count` kinds use — predicates are side-effect-free, so stopping early
    # is semantics-preserving and matters a lot here: library rules like
    # MustFollowSuit route `any card in hand[p] where …` through this on
    # every `legal_cards` call.
    if e.kind == "any":
        return any(evaluate(e.pred, ctx.with_local("card", c)) for c in cards)
    if e.kind == "all":
        return all(evaluate(e.pred, ctx.with_local("card", c)) for c in cards)
    results = [bool(evaluate(e.pred, ctx.with_local("card", c))) for c in cards]
    match e.kind:
        case "set":
            return [c for c, ok in zip(cards, results) if ok]
        case "count":
            return sum(results)
        case _:
            raise AssertionError(f"unknown card-query kind '{e.kind}'")


def _domain_query(e: n.DomainQuery, ctx: Ctx) -> Any:
    """The positional quantifier register (decisions.md "Boards and cells").
    A BARE form (`source is None`) enumerates a declared position domain in
    its ordered members (`rs.position_domains[binder]` -- the board's cells,
    an integer domain's range); a COLLECTION form iterates the evaluated
    `line`/`cell` collection. `any`/`all` fold Boolean, short-circuiting like
    the card queries; `count` returns how many members satisfy the predicate.
    Resolve/typecheck have already validated the noun and the source kind, so
    this arm reads uniformly over both member kinds."""
    if e.source is None:
        members: Any = ctx.rs.position_domains[e.binder]
    else:
        members = elements(evaluate(e.source, ctx))
    results = (evaluate(e.pred, ctx.with_local(e.binder, m)) for m in members)
    match e.kind:
        case "any":
            return any(results)
        case "all":
            return all(results)
        case "count":
            return sum(1 for ok in results if ok)
        case _:
            raise AssertionError(f"unknown domain-query kind '{e.kind}'")


def _if_expr(e: n.IfExpr, ctx: Ctx) -> Any:
    if evaluate(e.cond, ctx):
        return evaluate(e.then, ctx)
    for cond, then in e.elifs:
        if evaluate(cond, ctx):
            return evaluate(then, ctx)
    return evaluate(e.otherwise, ctx)


def _comprehension(e: n.Comprehension, ctx: Ctx) -> Any:
    source = evaluate(e.source, ctx)
    items = list(elements(source))
    if e.filter is not None:
        items = [
            x
            for x in items
            if evaluate(e.filter, ctx.with_local(e.binder, x))
        ]
    values = [evaluate(e.body, ctx.with_local(e.binder, x)) for x in items]
    match e.agg:
        case "sum":
            return sum(values)
        case "highest":
            if not values:
                assert e.default is not None, "grammar makes `or <default>` mandatory"
                return evaluate(e.default, ctx)
            return max(values)
        case "lowest":
            if not values:
                assert e.default is not None, "grammar makes `or <default>` mandatory"
                return evaluate(e.default, ctx)
            return min(values)
        case _:
            raise AssertionError(f"unknown aggregator '{e.agg}'")
