"""The game driver: run the phase tree to play a game end to end.

`play_game` sets up the world, runs the top-level phases, and reads the winner.
`run_phase` handles a phase's state block and its qualifier (`when` guard /
`repeats until` loop); `run_body` runs the items, skipping rule-delta sub-phases
(handled by phases.compute_active_rules) and threading `let` bindings.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable

from cardlang.ast import nodes as n
from cardlang.runtime import phases
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.execute import execute, run_body as run_stmts
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Player, Seating, build_deck


@dataclass(frozen=True, slots=True)
class GameResult:
    scores: dict[Player, int]
    winner: Player
    hands_played: int


def play_game(
    game: n.Game,
    rng: random.Random,
    tracer: Callable[[str, Any], None] | None = None,
) -> GameResult:
    seating = Seating(game.players.low)
    zones = ZoneStore(game.zones, seating.players)
    rs = RuntimeState(seating, zones, rng)
    rs.rule_index = {r.name: r for r in game.rules}
    rs.deck_zone = next(z.name for z in game.zones if z.type_ref.name == "Deck")
    rs.zones.single(rs.deck_zone).add_all(build_deck(game.deck))
    assert game.winner is not None
    rs.score_var = game.winner.target
    ctx = Ctx(rs=rs, chooser=random_chooser(rng), tracer=tracer)

    rs.push_frame()  # game-level state (cumulative_score, …)
    if game.state is not None:
        _declare_state(game.state, ctx)

    hands = _HandCounter()
    for phase in game.phases:
        run_phase(phase, ctx, hands)

    assert game.winner is not None
    scores: dict[Player, int] = dict(rs.get(game.winner.target))
    pick = min if game.winner.rank_dir == "lowest" else max
    winner = pick(scores, key=lambda p: scores[p])
    rs.pop_frame()
    return GameResult(scores=scores, winner=winner, hands_played=hands.value)


class _HandCounter:
    """Counts scoring phases run, for diagnostics / invariant checks."""

    def __init__(self) -> None:
        self.value = 0


def run_phase(phase: n.Phase, ctx: Ctx, hands: _HandCounter) -> None:
    ctx.rs.push_frame()
    ctx = ctx.in_phase(phase)
    state_block = next((i for i in phase.items if isinstance(i, n.StateBlock)), None)
    if state_block is not None:
        _declare_state(state_block, ctx)

    before = next((i for i in phase.items if isinstance(i, n.BeforeEach)), None)
    after = next((i for i in phase.items if isinstance(i, n.AfterEach)), None)

    q = phase.qualifier
    if q is not None and q.kind == "repeats":
        while not evaluate(q.expr, ctx):
            ctx.rs.fired_transitions.clear()  # transitions reset each iteration
            if before is not None:
                run_stmts(before.body, ctx)
            try:
                run_body(phase, ctx, hands)
            finally:
                if after is not None:  # guaranteed, even on mid-iteration exit
                    run_stmts(after.body, ctx)
            ctx.trace("hand_end", dict(ctx.rs.get(ctx.rs.score_var)))
    elif q is not None and q.kind == "when":
        if evaluate(q.expr, ctx):
            run_body(phase, ctx, hands)
    else:
        run_body(phase, ctx, hands)

    ctx.rs.pop_frame()


def run_body(phase: n.Phase, ctx: Ctx, hands: _HandCounter) -> None:
    if phase.name == "scoring":
        hands.value += 1
    for item in phase.items:
        match item:
            case (
                n.StateBlock()
                | n.ActiveRules()
                | n.LegalMoves()
                | n.TransitionTo()
                | n.BeforeEach()
                | n.AfterEach()
            ):
                pass  # config / lifecycle hooks, handled by run_phase
            case n.Phase():
                if not phases._is_rule_delta(item):
                    run_phase(item, ctx, hands)
            case _:
                ctx = execute(item, ctx)


def _declare_state(block: n.StateBlock, ctx: Ctx) -> None:
    for decl in block.decls:
        if decl.index is None:
            ctx.rs.declare(decl.name, False, evaluate(decl.default, ctx))
        else:
            value: dict[Player, Any] = {
                p: evaluate(decl.default, ctx) for p in ctx.rs.seating.players
            }
            ctx.rs.declare(decl.name, True, value)
