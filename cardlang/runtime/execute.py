"""Statement executor.

`execute(stmt, ctx)` runs one statement, mutating `ctx.rs`. A statement may
introduce a binding for the rest of its body (a `let`), so `execute` returns
the (possibly extended) context the caller threads into subsequent statements.
"""

from __future__ import annotations

from typing import Any, assert_never

from cardlang.ast import nodes as n
from cardlang.runtime import mechanics
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, Zone, _ContinueTo, _ProduceSignal, _SkipHand
from cardlang.runtime.values import Card, Player


def execute(stmt: n.Stmt, ctx: Ctx) -> Ctx:
    match stmt:
        case n.Movement():
            _movement(stmt, ctx)
            return ctx
        case n.EpistemicOp():
            _epistemic(stmt, ctx)
            return ctx
        case n.RotateStmt():
            _rotate(stmt, ctx)
            return ctx
        case n.LetStmt():
            return _let(stmt, ctx)
        case n.AssignStmt():
            _assign(stmt, ctx)
            return ctx
        case n.ForEach():
            _for_each(stmt, ctx)
            return ctx
        case n.EachSimultaneous():
            _each_simultaneous(stmt, ctx)
            return ctx
        case n.RepeatUntil():
            _repeat_until(stmt, ctx)
            return ctx
        case n.IfStmt():
            if evaluate(stmt.cond, ctx):
                run_body(stmt.then_body, ctx)
            elif stmt.else_body is not None:
                run_body(stmt.else_body, ctx)
            return ctx
        case n.Instantiate():
            # The mechanic's result binds `outcome` for the rest of the body
            # (e.g. `instantiate BridgeAuction(...)` then reading `outcome`).
            return ctx.with_outcome(mechanics.instantiate(stmt, ctx))
        case n.Offer():
            _offer(stmt, ctx)
            return ctx
        case n.Round():
            return ctx.with_outcome(mechanics.run_round(stmt, ctx))
        case n.Produce():
            raise _ProduceSignal(stmt.tag, [evaluate(p, ctx) for p in stmt.payloads])
        case n.Produces():
            _produces(stmt, ctx)
            return ctx
        case n.ContinueTo():
            raise _ContinueTo(stmt.target)
        case n.SkipToNextHand():
            raise _SkipHand()
        case _ as unreachable:
            assert_never(unreachable)


def run_body(stmts: tuple[n.Stmt, ...], ctx: Ctx) -> None:
    """Run a statement sequence, threading `let` bindings forward."""
    for stmt in stmts:
        ctx = execute(stmt, ctx)


# --- movement ---


def _movement(stmt: n.Movement, ctx: Ctx) -> None:
    if stmt.source is None:
        _gather(stmt, ctx)  # `move all cards to <zone>` — collect from everywhere
        return
    source = evaluate(stmt.source, ctx)
    assert isinstance(source, Zone)
    if stmt.dest_each:
        assert isinstance(stmt.dest, n.NameRef)
        if stmt.distribution == "as_equally_as_possible":
            _deal_round_robin(source, stmt.dest.name, ctx)
        else:
            for player in ctx.rs.seating.players:
                cards = _select(source, stmt, ctx, player)
                ctx.rs.zones.instance(stmt.dest.name, player).add_all(cards)
    else:
        assert stmt.dest is not None
        dest = evaluate(stmt.dest, ctx)
        assert isinstance(dest, Zone)
        player = ctx.current_player if ctx.current_player is not None else 0
        dest.add_all(_select(source, stmt, ctx, player))


def _deal_round_robin(source: Zone, dest_family: str, ctx: Ctx) -> None:
    """Deal the source one card at a time around the players, so an indivisible
    deck is spread as equally as possible (the first players get the remainder)."""
    players = list(ctx.rs.seating.players)
    i = 0
    while source.cards:
        ctx.rs.zones.instance(dest_family, players[i % len(players)]).add(
            source.cards.pop(0)
        )
        i += 1


def _gather(stmt: n.Movement, ctx: Ctx) -> None:
    """`move all cards to <zone>`: collect every card from all other zones."""
    assert stmt.amount == "all" and isinstance(stmt.dest, n.NameRef)
    dest = evaluate(stmt.dest, ctx)
    assert isinstance(dest, Zone)
    zones = ctx.rs.zones
    for name, zone in zones.singles.items():
        if zone is not dest:
            dest.add_all(zone.take_all())
    for family in zones.families.values():
        for zone in family.values():
            dest.add_all(zone.take_all())


def _select(source: Zone, stmt: n.Movement, ctx: Ctx, player: Player) -> list[Card]:
    amount = stmt.amount
    if amount == "all":
        return source.take_all()
    if amount == "one":
        count = 1
    else:
        assert not isinstance(amount, str)
        count = int(evaluate(amount, ctx))
    if stmt.mode == "chosen":
        chosen = ctx.chooser(player, list(source.cards), count)
        for card in chosen:
            source.remove(card)
        return chosen
    if stmt.mode == "random":
        chosen = ctx.rs.rng.sample(list(source.cards), count)
        for card in chosen:
            source.remove(card)
        return chosen
    if count > len(source.cards):  # fail loudly like the chosen/random branches
        raise ValueError(
            f"cannot deal {count} cards from a source holding {len(source.cards)}"
        )
    taken = source.cards[:count]  # deal off the top
    del source.cards[:count]
    return taken


def _epistemic(stmt: n.EpistemicOp, ctx: Ctx) -> None:
    assert stmt.op == "shuffle"
    zone = evaluate(stmt.target, ctx)
    assert isinstance(zone, Zone)
    ctx.rs.rng.shuffle(zone.cards)


def _rotate(stmt: n.RotateStmt, ctx: Ctx) -> None:
    # Advance the variable to the next value in the cycle. Loop state persists
    # across iterations and `before_each` rotates each hand, so the cycle
    # advances hand to hand (see decisions.md "Loop lifecycle").
    current = ctx.rs.get(stmt.var)
    values = list(stmt.values)
    idx = values.index(current) if current in values else -1
    ctx.rs.set(stmt.var, values[(idx + 1) % len(values)])


def _let(stmt: n.LetStmt, ctx: Ctx) -> Ctx:
    if stmt.index is None:
        return ctx.with_local(stmt.name, evaluate(stmt.value, ctx))
    # Indexed let: `base[p] = E` -> a per-player map.
    value: dict[Player, Any] = {
        p: evaluate(stmt.value, ctx.with_local(stmt.index, p))
        for p in ctx.rs.seating.players
    }
    return ctx.with_local(stmt.name, value)


def _assign(stmt: n.AssignStmt, ctx: Ctx) -> None:
    rhs = evaluate(stmt.value, ctx)
    if stmt.index is None:
        new = rhs if stmt.op == ":=" else _apply(stmt.op, ctx.rs.get(stmt.name), rhs)
        ctx.rs.set(stmt.name, new)
    else:
        key = evaluate(stmt.index, ctx)
        target = ctx.rs.get(stmt.name)  # the per-player map
        target[key] = rhs if stmt.op == ":=" else _apply(stmt.op, target[key], rhs)


def _apply(op: str, current: Any, rhs: Any) -> Any:
    if op == "+=":
        return current + rhs
    if op == "-=":
        return current - rhs
    raise AssertionError(f"unknown assignment operator '{op}'")


def _for_each(stmt: n.ForEach, ctx: Ctx) -> None:
    if stmt.role == "team":
        for team in ctx.rs.teams:
            execute(stmt.body, ctx.with_local(stmt.binder, team))
        return
    assert stmt.role == "player"
    # The bound player is also the acting player for the body, so a decision
    # made inside (e.g. `bid[p] := choose …`) knows who is choosing.
    for player in ctx.rs.seating.players:
        execute(stmt.body, ctx.with_local(stmt.binder, player).acting_as(player))


def _offer(stmt: n.Offer, ctx: Ctx) -> None:
    player = evaluate(stmt.player, ctx)
    pctx = ctx.acting_as(player)
    legal = [
        name
        for name in stmt.move_types
        if _move_legal(ctx.rs.move_type_index[name], pctx)
    ]
    if not legal:
        return  # no legal move: the offer is a no-op
    chosen = ctx.chooser(player, legal, 1)[0]
    run_body(ctx.rs.move_type_index[chosen].effect, pctx)


def _move_legal(mt: n.MoveTypeDef, ctx: Ctx) -> bool:
    return mt.guard is None or bool(evaluate(mt.guard, ctx))


def _produces(stmt: n.Produces, ctx: Ctx) -> None:
    # Dispatch to the matching arm and bind the payloads as arm locals. No frame
    # is pushed; `let`-locals thread via the immutable
    # `Ctx`, and the signal unwind leaves no state to clean up. The produced
    # outcome comes from either an outcome-declaring phase that already ran (and
    # stashed it by name), or a `define` invoked here.
    if stmt.define in ctx.rs.phase_outcomes:
        tag, payloads = ctx.rs.phase_outcomes.pop(stmt.define)
    elif stmt.define in ctx.rs.define_index:
        tag, payloads = _run_define(stmt.define, ctx)
    else:
        raise AssertionError(
            f"phase '{stmt.define}' did not produce an outcome before its consumer"
        )
    arm = next((a for a in stmt.arms if a.tag == tag), None)
    if arm is None:
        raise AssertionError(
            f"'{stmt.define}' produced '{tag}', which no produces: arm matches"
        )
    arm_ctx = ctx
    for binder, value in zip(arm.binders, payloads):
        arm_ctx = arm_ctx.with_local(binder, value)
    run_body(arm.body, arm_ctx)


def _run_define(name: str, ctx: Ctx) -> tuple[str, list[Any]]:
    """Run a param-light define's body and capture the variant it produces."""
    define = ctx.rs.define_index[name]
    try:
        run_body(define.body, ctx)
    except _ProduceSignal as produced:
        return produced.tag, produced.payloads
    raise AssertionError(f"define '{name}' completed without producing")


def _each_simultaneous(stmt: n.EachSimultaneous, ctx: Ctx) -> None:
    # All players choose from their pre-block hands; effects applied atomically.
    # For Hearts' pass, the per-player bodies are independent transfers, and a
    # player's source hand isn't read by another's body, so sequential
    # execution with the chooser reading current hands is equivalent (see
    # decisions.md "Simultaneous moves").
    assert stmt.role == "player"
    # Snapshot every player's chosen cards against pre-block hands, then apply.
    selections: dict[Player, list[Card]] = {}
    for player in ctx.rs.seating.players:
        body_ctx = ctx.with_local(stmt.role, player).acting_as(player)
        selections[player] = _pass_selection(stmt.body, body_ctx)
    for player in ctx.rs.seating.players:
        body_ctx = ctx.with_local(stmt.role, player).acting_as(player)
        _apply_pass(stmt.body, body_ctx, selections)


def _pass_selection(body: n.Stmt, ctx: Ctx) -> list[Card]:
    assert isinstance(body, n.Movement) and body.mode == "chosen"
    assert body.source is not None
    source = evaluate(body.source, ctx)
    assert isinstance(source, Zone)
    assert not isinstance(body.amount, str)
    count = int(evaluate(body.amount, ctx))
    return ctx.chooser(ctx.current_player or 0, list(source.cards), count)


def _apply_pass(
    body: n.Stmt, ctx: Ctx, selections: dict[Player, list[Card]]
) -> None:
    assert isinstance(body, n.Movement)
    player = ctx.current_player
    assert player is not None and body.source is not None and body.dest is not None
    source = evaluate(body.source, ctx)
    dest = evaluate(body.dest, ctx)
    assert isinstance(source, Zone) and isinstance(dest, Zone)
    for card in selections[player]:
        source.remove(card)
        dest.add(card)


def _repeat_until(stmt: n.RepeatUntil, ctx: Ctx) -> None:
    guard = 0
    while not evaluate(stmt.cond, ctx):
        run_body(stmt.body, ctx)
        guard += 1
        if guard > 10_000:
            raise RuntimeError("repeat-until exceeded 10000 iterations (non-termination?)")
