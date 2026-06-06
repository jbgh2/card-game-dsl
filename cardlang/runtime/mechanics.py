"""The Trick mechanic runtime (the main deferred runtime-primitive).

`instantiate` dispatches `instantiate Trick(...)`; `run_trick` plays one trick:
each participant in turn order from the leader plays a legal card, the lead sets
`led_suit`, then `outcome` selects a player and `routing` relocates the played
cards. Returns the next leader.
"""

from __future__ import annotations

from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime import phases, rules
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, Move
from cardlang.runtime.values import Card, Player


def instantiate(stmt: n.Instantiate, ctx: Ctx) -> Player:
    if stmt.mechanic != "Trick":
        raise NotImplementedError(f"mechanic '{stmt.mechanic}' not supported yet")
    args = {a.name: a.value for a in stmt.args}
    participants = evaluate(_expr(args["participants"]), ctx)
    leader = evaluate(_expr(args["leader"]), ctx)
    source_zone = args["source_zone"]
    assert isinstance(source_zone, n.NameRef)
    play_zone = args["play_zone"]
    assert isinstance(play_zone, n.NameRef)
    outcome_fn = evaluate(_expr(args["outcome"]), ctx)
    routing_body = _routing_body(args["routing"], ctx)
    early_term = (
        evaluate(_expr(args["early_termination"]), ctx)
        if "early_termination" in args
        else None
    )
    # The trump suit for this trick: an explicit `trump =` arg when it varies by
    # hand (Oh Hell turns one up each deal), else the game-level `trump:` decl.
    trump = (
        evaluate(_expr(args["trump"]), ctx) if "trump" in args else ctx.rs.trump
    )
    # `play_rules = active_rules` -> the current phase's active rules, recomputed
    # each trick so the hearts-broken transition takes effect.
    play_rules = phases.compute_active_rules(ctx.current_phase, ctx.rs)
    return run_trick(
        participants=list(participants),
        leader=leader,
        source_family=source_zone.name,
        play_zone=play_zone.name,
        play_rules=play_rules,
        outcome_fn=outcome_fn,
        routing_body=routing_body,
        early_term=early_term,
        trump=trump,
        ctx=ctx,
    )


def _routing_body(value: n.Expr | n.Movement, ctx: Ctx) -> tuple[n.Stmt, ...]:
    """The Trick `routing =` arg is either an inline movement or the name of a
    `routing` definition; both reduce to a statement body run with `outcome`
    bound."""
    if isinstance(value, n.Movement):
        return (value,)
    if isinstance(value, n.NameRef) and value.ref_kind == "routing":
        return ctx.rs.routing_index[value.name].body
    raise AssertionError(f"unsupported routing argument: {value!r}")


def _expr(value: n.Expr | n.Movement) -> n.Expr:
    assert not isinstance(value, n.Movement)
    return value


def run_trick(
    participants: list[Player],
    leader: Player,
    source_family: str,
    play_zone: str,
    play_rules: tuple[n.RuleDef, ...],
    outcome_fn: Any,
    routing_body: tuple[n.Stmt, ...],
    early_term: Any,
    trump: str | None,
    ctx: Ctx,
) -> Player:
    from cardlang.runtime.execute import run_body  # lazy: breaks the import cycle

    state: dict[str, Any] = {
        "led_suit": None,
        "trick_terminated_early": False,
        "trump": trump,
    }
    ctx.rs.mech_state.append(state)
    trick_ctx = ctx.with_rules(play_rules)
    transitions = phases.phase_transitions(ctx.current_phase)
    played: list[tuple[Player, Card]] = []

    for player in ctx.rs.seating.turn_order_from(leader):
        if player not in participants:
            continue
        candidates = rules.legal_cards(player, "play_to_trick", trick_ctx)
        choice = ctx.chooser(player, candidates, 1)[0]
        ctx.rs.zones.instance(source_family, player).remove(choice)
        ctx.rs.zones.single(play_zone).add(choice)
        played.append((player, choice))
        ctx.trace("play", (player, choice))
        if state["led_suit"] is None:
            state["led_suit"] = choice.suit
        _fire_transitions(transitions, Move(choice, player), trick_ctx)
        # A tochoo (off-suit play, only possible when void) ends the trick: the
        # highest led-suit card so far becomes the outcome and picks up the pile.
        if early_term is not None and early_term(choice, state["led_suit"]):
            state["trick_terminated_early"] = True
            break

    ctx.trace("trick_end", {"early": state["trick_terminated_early"], "trump": trump})
    outcome = outcome_fn(played, state["led_suit"], trump)
    assert isinstance(outcome, int)
    ctx.trace("trick", (outcome, [c for _, c in played]))
    run_body(routing_body, trick_ctx.with_outcome(outcome))  # route the played cards
    ctx.rs.mech_state.pop()
    return outcome


def _fire_transitions(
    transitions: list[n.TransitionTo], move: Move, ctx: Ctx
) -> None:
    """Evaluate each play-triggered transition's predicate against the move just
    played; a satisfied one marks its target as reached for this iteration."""
    for t in transitions:
        if t.event.move_type != "play_to_trick":
            continue
        pred = t.event.where
        if pred is None or bool(evaluate(pred, ctx.with_action(move))):
            ctx.rs.fired_transitions.add(t.target)
