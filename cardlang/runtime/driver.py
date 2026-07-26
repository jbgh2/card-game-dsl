"""The game driver: run the phase tree to play a game end to end.

`play_game` sets up the world, runs the top-level phases, and reads the winner.
`run_phase` handles a phase's state block and its qualifier (`when` guard /
`repeat until` loop); `run_body` runs the items, skipping rule-delta sub-phases
(handled by phases.compute_active_rules) and threading `let` bindings.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cardlang.ast import nodes as n
from cardlang.board_domains import directions_of, position_domains_of
from cardlang.domains import role_members
from cardlang.runtime import phases
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.execute import execute
from cardlang.runtime.execute import run_body as run_stmts
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
from cardlang.runtime.values import (
    Player,
    Seating,
    axis_attributes,
    build_deck,
    component_deck,
    deck_ranks,
    deck_suits,
)
from cardlang.stdlib.boards import board_entry


@dataclass(frozen=True, slots=True)
class GameResult:
    # `scores` is keyed by the `winner:` target's OWN index domain — by player
    # for `score[player]`, by TEAM for `score[team]` — so a key is not always a
    # seat, and `winner`, picked from it, is a team index in a team-scored game
    # (issue #154). A reader
    # deciding which it holds must consult the target's declaration, never the
    # key set: the two are indistinguishable whenever a game's team count equals
    # its player count (`openspiel/replay._winner_target_is_team_keyed`).
    scores: dict[Player, int]  # empty for games with no score var (loser games)
    winner: Player | None
    loser: Player | None
    hands_played: int


# The grammar's RANK_DIR terminal (`cardlang.lark`, "lowest" | "highest"),
# mapped to the builtin it picks the winner with. Exhaustive by construction:
# `play_game` below raises loudly on any key not present here, and
# `test_rank_dir_set_is_pinned` (tests/test_comprehension_aggregators.py)
# reconciles this set against the grammar terminal so a new RANK_DIR token
# cannot land uncovered here.
RANK_DIR_TO_PICK: dict[str, Callable[..., Player]] = {"highest": max, "lowest": min}


def play_game(
    game: n.Game,
    rng: random.Random,
    tracer: Callable[[str, Any], None] | None = None,
    chooser: Chooser | None = None,
    observer: Callable[[Player, tuple[Any, ...]], None] | None = None,
    on_first_decision: Callable[[RuntimeState], None] | None = None,
) -> GameResult:
    assert game.winner is not None or game.loser is not None, (
        "resolve() must reject a game with neither `winner:` nor `loser:`"
    )
    # resolve() walls `direction:` to GAME_DIRECTIONS; None means clockwise.
    seating = Seating(game.players.low, clockwise=game.direction != "counterclockwise")
    teams = tuple(range(len(game.partnerships)))
    team_of = {
        p: ti for ti, members in enumerate(game.partnerships) for p in members
    }
    positions = dict(position_domains_of(game))
    zones = ZoneStore(game.zones, seating.players, teams, positions=positions)
    rs = RuntimeState(seating, zones, rng)
    rs.trump = game.trump
    rs.teams = teams
    rs.team_of = team_of
    rs.position_domains = positions
    # The board-minted `dir` move-parameter domain (decisions.md "Boards and
    # cells"): built from the same `board:` clause as `cell`, via the seam the
    # OpenSpiel encoding also reads, so the live candidate enumeration and the
    # static action space cannot diverge. Empty for a boardless game.
    rs.direction_domains = dict(directions_of(game))
    # The instantiated board (cells + lines) for the cell/line query verbs;
    # `board_entry` is total on a resolved game (resolve validated it).
    rs.board = board_entry(game.board.family, game.board.args) if game.board is not None else None
    assert game.max_length is not None, "resolve() must reject a missing max_length"
    rs.max_length = game.max_length
    # Rank strength is read from the game's `ranking:` (high to low), so every
    # deck ranks correctly without a hardcoded order. Card values come from the
    # deck table (empty for games that score by other means).
    rs.rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    rs.card_values = dict(component_deck(game.deck).values)
    rs.content_flavor = game.content_flavor
    rs.axis_attr = axis_attributes(game.deck)
    rs.suits = deck_suits(game.deck)
    # Rank iteration order for `for each rank` / `any rank`: the declared
    # ranking when present, else the deck's first-appearance order.
    rs.ranks = game.ranking if game.ranking else deck_ranks(game.deck)
    rs.rule_index = {r.name: r for r in game.rules}
    rs.move_type_index = {m.name: m for m in game.move_types}
    rs.type_index = {t.name: t for t in game.types}
    rs.define_index = {d.name: d for d in game.defines}
    rs.function_index = {f.name: f for f in game.functions}
    rs.deck_zone = next(z.name for z in game.zones if z.type_ref.name == "Deck")
    rs.zones.single(rs.deck_zone).add_all(build_deck(game.deck))
    if game.winner is not None:
        rs.score_var = game.winner.target  # loser games have no score var
    base_chooser = chooser or random_chooser(rng)

    uncounted = base_chooser

    def _counted(player: Player, candidates: list[Any], n: int) -> list[Any]:
        # The declared max_length's other half (docs/decisions.md, "Game
        # length as a declared contract"): the loop guards below only bound
        # iteration counts, which can be far coarser than decisions (a single
        # `repeat until` iteration may make many chooser calls) — this counts
        # every decision itself, the unit max_length's corpus values are
        # actually sized against (measured per-game random-playout lengths),
        # so a structurally-terminating loop that makes unboundedly many
        # decisions per iteration is caught here, not silently under-bounded.
        rs.decisions_made += n
        if rs.decisions_made > rs.max_length:
            raise RuntimeError(
                f"the game made {rs.decisions_made} decisions, exceeding its "
                f"declared max_length ({rs.max_length}) — non-termination, or "
                "raise max_length if this game genuinely runs this long"
            )
        return uncounted(player, candidates, n)

    base_chooser = _counted
    if on_first_decision is not None:
        # The deal-injection seam (SP1 proof harness): fire once, inside the
        # first chooser call, before delegating. NOTE: the first decider's
        # candidates were computed before this fires — a mutation must not
        # touch the first decider's own zones if the caller will use the
        # pause's legal actions or replay further actions (those candidates
        # would go stale). A caller that only inspects the paused world may
        # mutate anyone's zones, including the first decider's own.
        inner = base_chooser
        hook = on_first_decision
        fired = False

        def hooked(player: Player, candidates: list[Any], n: int) -> list[Any]:
            nonlocal fired
            if not fired:
                fired = True
                hook(rs)
            return inner(player, candidates, n)

        base_chooser = hooked
    ctx = Ctx(rs=rs, chooser=base_chooser, tracer=tracer, observer=observer)

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
        if game.winner.rank_dir not in RANK_DIR_TO_PICK:
            # Internal invariant, not a user diagnostic: the grammar's
            # RANK_DIR terminal and this mapping are out of sync.
            raise AssertionError(
                f"winner: unhandled RANK_DIR value {game.winner.rank_dir!r} — add "
                "it to RANK_DIR_TO_PICK"
            )
        pick = RANK_DIR_TO_PICK[game.winner.rank_dir]
        winner = pick(scores, key=lambda p: scores[p])
    else:
        # winner is None here, so resolve's winner-or-loser wall leaves a loser
        assert game.loser is not None
        selected = evaluate(game.loser.selection, ctx)
        if not isinstance(selected, int):
            # `loser:` takes any expression and the checker leaves its type
            # open, so the player-ness of the result is checked here — a
            # game-description error in the runtime's currency.
            raise RuntimeError(
                f"`loser:` selected {selected!r} ({type(selected).__name__}), "
                f"not a player"
            )
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
                # A `repeat until` whose condition never holds (e.g. a win
                # threshold unreachable under random play) would otherwise hang
                # forever — fail loudly so non-termination surfaces as a test
                # failure, not a stuck process, against the game's declared
                # `max_length` (docs/decisions.md, "Game length as a declared
                # contract"). The statement-level `repeat until` has the same
                # backstop.
                guard += 1
                if guard > ctx.rs.max_length:
                    raise RuntimeError(
                        f"phase '{phase.name}' repeated {guard} times without its "
                        "`repeat until` condition holding, exceeding the game's "
                        f"declared max_length ({ctx.rs.max_length}) — non-termination, "
                        "or raise max_length if this game genuinely runs this long"
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
    produces (via DSL `produce` or a round's typed outcome) into `phase_outcomes`
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
            # The indexed var's key set is the index domain's runtime member
            # set — the same table cell `for each <role>` iterates. The old
            # `teams if index == "team" else players` silently keyed every
            # other role by players, which is exactly how `state { x[suit] }`
            # ran as a per-player store until resolve walled it.
            keys = role_members(decl.index, ctx)
            value: dict[int, Any] = {k: evaluate(decl.default, ctx) for k in keys}
            ctx.rs.declare(decl.name, True, value)
