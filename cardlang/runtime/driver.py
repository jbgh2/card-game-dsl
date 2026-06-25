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
from cardlang.runtime.state import (
    Chooser,
    ChooserAbort,
    Ctx,
    RuntimeState,
    ZoneStore,
    _ContinueTo,
    _ProduceSignal,
    _SkipHand,
)
from cardlang.runtime.values import DECKS, Player, Seating, build_deck


@dataclass(frozen=True, slots=True)
class GameResult:
    scores: dict[Player, int]  # empty for games with no score var (loser games)
    winner: Player | None
    loser: Player | None
    hands_played: int


def play_game(
    game: n.Game,
    rng: random.Random,
    tracer: Callable[[str, Any], None] | None = None,
    chooser: Chooser | None = None,
) -> GameResult:
    assert game.winner is not None or game.loser is not None, (
        "a game must declare a winner or a loser"
    )
    seating = Seating(game.players.low, clockwise=game.direction != "counterclockwise")
    teams = tuple(range(len(game.partnerships)))
    team_of = {
        p: ti for ti, members in enumerate(game.partnerships) for p in members
    }
    zones = ZoneStore(game.zones, seating.players, teams)
    rs = RuntimeState(seating, zones, rng)
    rs.trump = game.trump
    rs.teams = teams
    rs.team_of = team_of
    # Rank strength is read from the game's `ranking:` (high to low), so every
    # deck ranks correctly without a hardcoded order. Card values come from the
    # deck table (empty for games that score by other means).
    rs.rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    rs.card_values = dict(DECKS[game.deck].values)
    rs.rule_index = {r.name: r for r in game.rules}
    rs.move_type_index = {m.name: m for m in game.move_types}
    rs.type_index = {t.name: t for t in game.types}
    rs.define_index = {d.name: d for d in game.defines}
    rs.deck_zone = next(z.name for z in game.zones if z.type_ref.name == "Deck")
    rs.zones.single(rs.deck_zone).add_all(build_deck(game.deck))
    if game.winner is not None:
        rs.score_var = game.winner.target  # loser games have no score var
    ctx = Ctx(rs=rs, chooser=chooser or random_chooser(rng), tracer=tracer)

    rs.push_frame()  # game-level state (cumulative_score, …)
    if game.state is not None:
        _declare_state(game.state, ctx)

    hands = _HandCounter()
    try:
        for phase in game.phases:
            run_phase(phase, ctx, hands)
    except ChooserAbort as abort:
        # A chooser suspended the playout (steppable adapter). Surface the live
        # world so the caller can inspect the paused decision point.
        abort.rs = rs
        raise

    ctx.trace("game_end", _final_card_census(rs))

    # Compute the result against the final state, before unwinding the frame.
    scores: dict[Player, int] = {}
    winner: Player | None = None
    loser: Player | None = None
    if game.winner is not None:
        scores = dict(rs.get(game.winner.target))
        pick = min if game.winner.rank_dir == "lowest" else max
        winner = pick(scores, key=lambda p: scores[p])
    else:
        assert game.loser is not None
        selected = evaluate(game.loser.selection, ctx)
        assert isinstance(selected, int)  # a Player
        loser = selected
    rs.pop_frame()
    return GameResult(
        scores=scores, winner=winner, loser=loser, hands_played=hands.value
    )


def _final_card_census(rs: RuntimeState) -> dict[str, int]:
    """Total cards across every zone (conservation check) and how many `hand`
    zones still hold cards (the survivor count for an elimination game)."""
    all_zones = list(rs.zones.singles.values())
    for family in rs.zones.families.values():
        all_zones.extend(family.values())
    total = sum(len(z.cards) for z in all_zones)
    # Total card-point value across every zone — a deck-integrity check for
    # point-trick games (e.g. Schnapsen's 120). Zero when the deck has no values.
    total_value = sum(
        rs.card_values.get(c.rank, 0) for z in all_zones for c in z.cards
    )
    hands = rs.zones.families.get("hand", {})
    with_cards = sum(1 for z in hands.values() if z.cards)
    return {"total": total, "hands_with_cards": with_cards, "total_value": total_value}


class _HandCounter:
    """Counts scoring phases run, for diagnostics / invariant checks."""

    def __init__(self) -> None:
        self.value = 0


def _subtree_outcome_names(phase: n.Phase) -> set[str]:
    """Names of every outcome-declaring phase in `phase`'s subtree (inclusive)."""
    names: set[str] = set()

    def rec(p: n.Phase) -> None:
        if p.outcome_cases:
            names.add(p.name)
        for item in p.items:
            if isinstance(item, n.Phase):
                rec(item)

    rec(phase)
    return names


def run_phase(phase: n.Phase, ctx: Ctx, hands: _HandCounter) -> None:
    ctx.rs.push_frame()
    try:
        ctx = ctx.in_phase(phase)
        # Drop this phase's own stale outcome on entry, so a guarded-off or
        # non-producing run leaves no prior-pass result for a consumer to pop.
        # Scoped to this phase's name — other phases' pending outcomes survive.
        if phase.outcome_cases:
            ctx.rs.phase_outcomes.pop(phase.name, None)
        state_block = next(
            (i for i in phase.items if isinstance(i, n.StateBlock)), None
        )
        if state_block is not None:
            _declare_state(state_block, ctx)

        before = next((i for i in phase.items if isinstance(i, n.BeforeEach)), None)
        after = next((i for i in phase.items if isinstance(i, n.AfterEach)), None)

        q = phase.qualifier
        if q is not None and q.kind == "repeats":
            # Each new hand discards any outcome produced inside this loop's subtree
            # in the prior iteration (a producer skipped by `continue to`, or
            # guarded off). Scoped to descendants, so a sibling/ancestor outcome
            # pending across this loop is preserved.
            loop_outcomes = _subtree_outcome_names(phase)
            guard = 0
            while not evaluate(q.expr, ctx):
                # A `repeats until` whose condition never holds (e.g. a win
                # threshold unreachable under random play) would otherwise hang
                # forever — fail loudly so non-termination surfaces as a test
                # failure, not a stuck process. The statement-level `repeat
                # until` has the same backstop.
                guard += 1
                if guard > 10_000:
                    raise RuntimeError(
                        f"phase '{phase.name}' repeated 10000 times without its "
                        "`repeats until` condition holding (non-termination?)"
                    )
                ctx.rs.fired_transitions.clear()  # transitions reset each iteration
                for nm in loop_outcomes:
                    ctx.rs.phase_outcomes.pop(nm, None)
                if before is not None:
                    run_stmts(before.body, ctx)
                try:
                    _run_phase_body(phase, ctx, hands)
                except _SkipHand:
                    pass  # `skip to next hand`: abort the rest, run after_each
                finally:
                    if after is not None:  # guaranteed, even on mid-iteration exit
                        run_stmts(after.body, ctx)
                if ctx.rs.score_var is not None:  # loser games keep no per-hand score
                    ctx.trace("hand_end", dict(ctx.rs.get(ctx.rs.score_var)))
        elif q is not None and q.kind == "when":
            if evaluate(q.expr, ctx):
                _run_phase_body(phase, ctx, hands)
        else:
            _run_phase_body(phase, ctx, hands)
    finally:
        ctx.rs.pop_frame()  # always pop, even on _ContinueTo/_SkipHand unwind


def _run_phase_body(phase: n.Phase, ctx: Ctx, hands: _HandCounter) -> None:
    """Run a phase's body. An outcome-declaring phase captures the variant it
    produces (via DSL `produce` or an instantiated mechanic) into `phase_outcomes`
    for a later-sibling `produces:` consumer."""
    if not phase.outcome_cases:
        run_body(phase, ctx, hands)
        return
    try:
        run_body(phase, ctx, hands)
    except _ProduceSignal as produced:
        ctx.rs.phase_outcomes[phase.name] = (produced.tag, produced.payloads)


def run_body(phase: n.Phase, ctx: Ctx, hands: _HandCounter) -> None:
    if phase.name == "scoring":
        hands.value += 1
    items = phase.items
    i = 0
    while i < len(items):
        item = items[i]
        try:
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
        except _ContinueTo as jump:
            # `continue to <phase>`: resume at the named sibling, if it is one of
            # this body's phases; otherwise let an enclosing body handle it.
            target = next(
                (
                    j
                    for j, it in enumerate(items)
                    if isinstance(it, n.Phase) and it.name == jump.target
                ),
                None,
            )
            if target is None:
                raise
            if target <= i:
                # `continue to` is forward-only — a backward jump would re-run the
                # producer and loop forever. Fail loudly rather than hang.
                raise RuntimeError(
                    f"`continue to {jump.target}` is not a forward phase from "
                    f"'{phase.name}'"
                )
            i = target
            continue
        i += 1


def _declare_state(block: n.StateBlock, ctx: Ctx) -> None:
    for decl in block.decls:
        if decl.index is None:
            ctx.rs.declare(decl.name, False, evaluate(decl.default, ctx))
        else:
            keys = ctx.rs.teams if decl.index == "team" else ctx.rs.seating.players
            value: dict[int, Any] = {k: evaluate(decl.default, ctx) for k in keys}
            ctx.rs.declare(decl.name, True, value)
