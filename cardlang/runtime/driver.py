"""The game driver: run the phase tree to play a game end to end.

`play_game` sets up the [[world]], runs the top-level phases, and reads the
[[winner]]. `run_phase` handles a phase's state block and its qualifier (`when`
guard / `repeat until` loop); `run_body` runs the items — modes are
configuration, read by `active_rules.compute_active_rules` rather than
executed — and threads `let` bindings.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.board_domains import directions_of, position_domains_of
from cardlang.domains import require_role, role_members
from cardlang.primitives_block import (
    PRIMITIVE_IMPLEMENTATIONS,
    InvocationContract,
    ReadKind,
    classify_read,
)
from cardlang.runtime import active_rules, primitives, reads
from cardlang.typecheck import declared_primitive_sigs
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.evaluate import evaluate, row_context
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
from cardlang.runtime.trick_order import TrickOrderTable
from cardlang.runtime.values import (
    Card,
    Player,
    Seating,
    axis_attributes,
    build_deck,
    deck_ranks,
    deck_suits,
    rank_strength,
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


def declared_card_points(game: n.Game) -> dict[str, int]:
    """The game's card-point table, materialized over the deck's ranks: the
    `card_points { }` rows verbatim, every unlisted rank at the `else:` value
    (or 0 with no else row). Materializing here — the one load site — is what
    keeps the table's two consumers (the `card_points(card)` Builtin and the
    card-point census below) reading identical values by construction: neither
    re-applies a default. Empty for a game declaring no clause (resolve's
    clause-required guard refuses the Builtin call there, and the census sums
    to 0, the pre-clause behavior)."""
    if game.card_points is None:
        return {}
    declared = {e.rank: e.value for e in game.card_points.entries}
    default = game.card_points.else_value or 0
    return {r: declared.get(r, default) for r in deck_ranks(game.deck)}


def declared_primitives(game: n.Game) -> dict[str, primitives.Declared] | None:
    """The game's `primitives { }` block, materialized: one dispatch entry per
    declared [[primitive]]. None for a game declaring no block, which is what
    leaves it on the legacy `PRIMITIVE_CALL_FUNCS` dispatch.

    Every fact a call needs is resolved HERE, at the one load site, the
    `declared_trick_order` precedent above: the implementation is imported from
    the names-only index, the declared reads become the primitive's own row,
    and each indexed read is paired with the parameter that keys it. No caller
    re-derives any of them, which is what keeps the bundle a primitive receives
    and the entry a designer wrote from being two readings of the same text.

    Resolve has already refused a declaration naming no implementation, an
    undeclarable contract, and an unclassifiable read, so the lookups below are
    total by the time this runs. It has also established the
    [[phase-scoped-read]]'s containment rule — every call of an entry with an
    `in <phase>` tail sits where that phase's frame stands — so a scoped read
    materializes through the SAME `rs.get` walk as a game-level one and there
    is nothing here to branch on: the tail rides into `classify_read` and
    decides the kind, and no arm below asks whether a read is scoped."""
    if game.primitives is None:
        return None
    game_file = Path(game.span.source_name).name if game.span is not None else ""
    sigs = declared_primitive_sigs(game)
    table: dict[str, primitives.Declared] = {}
    for decl in game.primitives.decls:
        impl_ref = PRIMITIVE_IMPLEMENTATIONS[decl.name]
        module = import_module(impl_ref.module)
        params = [p.name for p in decl.params]
        kinds = {
            read.name: classify_read(game, read.name, read.phase)
            for read in decl.reads
        }
        table[decl.name] = primitives.Declared(
            name=decl.name,
            impl=getattr(module, impl_ref.attribute),
            row=reads.PrimitiveReads(
                module=impl_ref.module.replace(".", "/") + ".py",
                game_file=game_file,
                state_vars=frozenset(
                    r.name
                    for r in decl.reads
                    if kinds[r.name]
                    in (ReadKind.STATE_VAR, ReadKind.INDEXED_STATE_VAR)
                ),
                zone_families=frozenset(
                    r.name for r in decl.reads if kinds[r.name] is ReadKind.ZONE_FAMILY
                ),
                single_zones=frozenset(
                    r.name for r in decl.reads if kinds[r.name] is ReadKind.SINGLE_ZONE
                ),
            ),
            binders=tuple(
                (r.name, params.index(r.binder))
                for r in decl.reads
                if r.binder is not None
            ),
            bundled=impl_ref.contract is InvocationContract.BUNDLED,
            scopes=tuple(
                (r.name, r.phase) for r in decl.reads if r.phase is not None
            ),
        )
    # A declared table keyed by exactly the block's entries: `sigs` is built
    # from the same decls, so a mismatch means one of the two walks skipped an
    # entry (this raise is its Shadow Guard; the Owner Guard is resolve's
    # duplicate-entry check, which is what makes the two counts comparable).
    assert set(table) == set(sigs), "declared table and signature table disagree"
    return table


def declared_trick_order(game: n.Game) -> TrickOrderTable | None:
    """The game's [[trick-order]], materialized: one callable per row, with the
    two DEFAULTS applied here and nowhere else. None for a game declaring no
    block (resolve's presence partition admits no reader of one there).

    Applying the defaults at this single load site is what keeps every consumer
    — the three readers, the winner, `follows_lead` — reading identical facts
    by construction, the `declared_card_points` precedent above: no reader
    re-derives what an omitted row means.

    The two defaults (decisions.md "Trick Order"):

    * `follow_class:` omitted — a card follows as its printed suit, the
      ordinary trick-taking rule. A game needs the row only when some card
      follows as something else (a class-remapped trump) or as nothing (the
      Excuse).
    * `card_strength:` omitted — `rank_value(card)`, the game's declared
      `ranking:`. typecheck's T2 refuses that combination in a game with no
      `ranking:`, so an empty order reaching the closure is an engine gap, not
      a bad game, and says so in the [[shadow-guard]]'s voice.

    A row's body evaluates under the hermetic row context
    (`evaluate.row_context`): only `card` is bound and no pronoun of any
    namespace is readable, which is what makes the answer a fact of the card
    and public state rather than of whoever happened to be asking."""
    if game.trick_order is None:
        return None

    def row_callable(body: n.Expr) -> Callable[[Card, Ctx], Any]:
        def read(card: Card, ctx: Ctx) -> Any:
            return evaluate(body, row_context(ctx, card))

        return read

    def default_class(card: Card, ctx: Ctx) -> str:
        return card.suit

    def default_strength(card: Card, ctx: Ctx) -> int:
        if not ctx.rs.rank_index:
            raise ShadowGuardError(
                "typecheck._check_trick_order (T2)",
                "a `trick_order { }` with no `card_strength:` row defaults to "
                "`rank_value(card)`, but the game declares no `ranking:` — T2 "
                "admits no defaulted strength without one",
            )
        return rank_strength(ctx.rs.rank_index, card.rank, "card_strength")

    rows = {r.key: r.body for r in game.trick_order.rows}
    trump_body = rows.get("trump")
    # shadow guard: parse requires the `trump:` row (P8), so a block that
    # reached here always has one
    assert trump_body is not None, "a `trick_order { }` with no `trump:` row"
    return TrickOrderTable(
        is_trump=row_callable(trump_body),
        follow_class=(
            row_callable(rows["follow_class"])
            if "follow_class" in rows
            else default_class
        ),
        card_strength=(
            row_callable(rows["card_strength"])
            if "card_strength" in rows
            else default_strength
        ),
    )


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
    # resolve()'s Owner Guard confines `direction:` to GAME_DIRECTIONS; None
    # means clockwise.
    seating = Seating(game.players.low, clockwise=game.direction != "counterclockwise")
    teams = tuple(range(len(game.teams)))
    team_of = {
        p: ti for ti, members in enumerate(game.teams) for p in members
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
    # deck ranks correctly without a hardcoded order. Card points come from the
    # game's own `card_points { }` clause — the ONE source; the deck registry
    # carries no point table (empty for games that score by other means).
    rs.rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    rs.card_points = declared_card_points(game)
    rs.trick_order = declared_trick_order(game)
    rs.declared_primitives = declared_primitives(game)
    rs.declared_sigs = declared_primitive_sigs(game)
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
        rs.score_var = game.winner.state_var  # loser games have no score var
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
            raise OwnerGuardError(
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
        # Shadow Guard behind resolve's `_check_winner_target`: a target that
        # is not a per-member score dies here on a raw `TypeError` rather than
        # ranking something meaningless.
        scores = dict(rs.get(game.winner.state_var))
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
        # winner is None here, so resolve's winner-or-loser Owner Guard leaves a loser
        assert game.loser is not None
        selected = evaluate(game.loser.selection, ctx)
        if not isinstance(selected, int):
            # `loser:` takes any expression and the checker leaves its type
            # open, so the player-ness of the result is checked here — a
            # game-description error, refused by its Owner Guard.
            raise OwnerGuardError(
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
    # Total card points across every zone — a deck-integrity check for
    # point-trick games (e.g. Schnapsen's 120). Zero when the game declares no
    # `card_points { }` clause. The table is materialized over the deck's
    # ranks (`declared_card_points`), so the `.get` default only serves the
    # clause-less empty table.
    total_value = sum(
        rs.card_points.get(c.rank, 0) for z in all_zones for c in z.cards
    )
    hands = rs.zones.families.get("hand", {})
    with_cards = sum(1 for z in hands.values() if z.cards)
    return {"total": total, "hands_with_cards": with_cards, "total_value": total_value}


class _HandCounter:
    """Counts executions of phases literally named `scoring`, reported as
    `hands_played`, for diagnostics / invariant checks. That is a PROXY for the
    [[hand-loop]]'s passes, not a count of them: a game whose scoring phase is
    named otherwise reports zero (→ F-6)."""

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
    # The ORDER below is load-bearing beyond this function: resolve's
    # `_check_scoped_read_containment` admits a [[phase-scoped-read]]'s call
    # from anywhere in the phase's subtree — the qualifier and both hooks
    # included — because the frame is pushed and the state declared before any
    # of them runs and popped in the outer `finally` after all of them. A
    # reordering that moved either hook outside that window would make that
    # guard silently unsound. The pop is also what makes an entry naming two
    # phases that do NOT nest a designed refusal rather than a deferral: a
    # phase's frame does not outlive the phase, so no position runs both.
    # `tests/test_phase_scoped_reads.py::test_a_phases_frame_does_not_outlive_
    # the_phase` pins it — the depth is unchanged across this call.
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
        if q is not None and q.kind == "repeat_until":
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
                # Owner Guard.
                guard += 1
                if guard > ctx.rs.max_length:
                    raise OwnerGuardError(
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
    """Run a phase's body. An outcome-declaring phase captures the outcome it
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
                    | n.Mode()
                    | n.BeforeEach()
                    | n.AfterEach()
                ):
                    pass  # config / lifecycle hooks, handled by run_phase
                case n.Phase():
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
                raise OwnerGuardError(
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
            # ran as a per-player store until resolve's Owner Guard rejected it.
            keys = role_members(
                require_role(decl.index, "state-variable index role"), ctx
            )
            value: dict[int, Any] = {k: evaluate(decl.default, ctx) for k in keys}
            ctx.rs.declare(decl.name, True, value)
