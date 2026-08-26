"""Mechanic runtime: the kernel [[round]] and its three [[form]]s.

`run_decision_round` is the one parameterized per-step decision loop behind every
kernel `round` form (§4 of docs/design-notes/kernel-extensibility.md). The three
sequential forms are hook bundles over it — `TrickForm` (one turn-order pass, each
participant plays a legal card, a [[winner]] function picks the winner),
`AuctionForm` (a continuous ring over an [[offering]], threading a bid history,
serving *both* the auction and betting forms), and `ClimbForm` (one
combination-climbing trick over game-local engine queries). `build_form` selects
the bundle by field-presence and `execute.py` dispatches on the returned Outcome
union.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Any, Protocol

from cardlang.ast import nodes as n
from cardlang.builtins.functions import TRICK_ORDER_GATED_WINNERS
from cardlang.domains import DomainSources, enumerate_domain
from cardlang.runtime import active_rules, delegation, narrowing, observe, reads, rules
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, Move
from cardlang.runtime.values import Player
from cardlang.stdlib.moves import RULE_ENFORCED_MOVE_TYPE

# ---------------------------------------------------------------------------
# The parameterized decision interpreter
# ---------------------------------------------------------------------------
#
# `run_trick`, `run_auction` (which serves *both* the auction and betting forms),
# and `run_climb` were the same per-step decision loop written three times. The
# interpreter is what remains after the varying slots are lifted out: a fixed
# loop that *calls* six pluggable hooks, with each kernel `round` form supplied
# as a hook bundle (§4 of docs/design-notes/kernel-extensibility.md). Order and
# participants are *functions* of the threaded `state`, never enums — the loop
# cursors that were Python locals (the auction ring pointer, the climb index, the
# trick's turn-order position and `led_suit`) live in `state`, so every hook is a
# pure function of `(…, state, ctx)`.

# The Round State (docs/glossary.md): the accumulator a running round threads
# through its hooks, and — for the forms that publish one — what the `state.`
# pronoun reads. `stdlib/round_state.py` names the same concept from the other
# side, declaring which of its keys each form publishes.
RoundState = dict[str, Any]
Outcome = Player | tuple[str, list[Any]] | None


class DecisionForm(Protocol):
    """The six pluggable slots of one kernel `round` [[form]]."""

    def init(self, state: RoundState, ctx: Ctx) -> RoundState:
        """Seed the accumulator and cursor into `state`, returning it."""

    def next_actor(self, state: RoundState, ctx: Ctx) -> Player | None:
        """Who acts next, or `None` when the actor sequence is structurally spent."""

    def candidates(self, actor: Player, state: RoundState, ctx: Ctx) -> list[Any]:
        """The finite, canonically-ordered action set for `actor`. Non-emptiness is
        the form's own contract — it raises its own malformed-game error, so the
        messages stay form-specific (see the draw site in `run_decision_round`)."""

    def terminated(self, state: RoundState, ctx: Ctx) -> bool:
        """The predicate end, checked at the top of the loop."""

    def apply(self, actor: Player, choice: Any, state: RoundState, ctx: Ctx) -> RoundState:
        """Enact the chosen action — thread the accumulator, emit any domain trace
        events — and return `state`."""

    def outcome(self, state: RoundState, ctx: Ctx) -> Outcome:
        """The round's result: a winning `Player`, a typed `(tag, payloads)`
        outcome, or `None` (a betting round mutated shared state and just closes)."""


def run_decision_round(form: DecisionForm, state: RoundState, ctx: Ctx) -> Outcome:
    """The one per-step decision loop behind every kernel `round` form (§4 of
    docs/design-notes/kernel-extensibility.md). `form` supplies the six slots; this
    skeleton is fixed. Exactly one `ctx.chooser` draw happens per step — the sole
    source of nondeterminism, and what the OpenSpiel one-node-per-turn compilation
    rests on.

    The round-state frame's lifetime is exactly this call. Whether there IS one is
    the form's choice — `init` pushes it, and the auction form deliberately
    publishes nothing — but ending it belongs here, so `outcome` computes a result
    and does nothing else. Popping back to the depth `init` was handed keeps push
    and pop symmetric without the protocol carrying a "do I publish?" slot."""
    depth = len(ctx.rs.mech_state)
    state = form.init(state, ctx)
    published = len(ctx.rs.mech_state) > depth
    while True:
        if form.terminated(state, ctx):  # until / early / shed-out
            break
        actor = form.next_actor(state, ctx)  # ring / came-back-to-last
        if actor is None:  # the actor sequence is structurally spent
            break
        candidates = form.candidates(actor, state, ctx)
        # A decision node must be non-empty. That contract lives in each form's
        # `candidates` (which raises the form-specific malformed-game error), not
        # here: the messages stay byte-identical and the climbing form keeps its
        # original empty-lead behaviour rather than a reshaped guard.
        # Delegated Play (decisions.md "Delegated play"): the decider makes
        # the draw and holds its recall; the trace and the apply stay the
        # actor's, so attribution is untouched. Consulted only for the routed
        # forms — delegation.ROUTED_FORMS names which and why — and the
        # decider equals the actor in every game defining no helper.
        decider = (
            delegation.decider_for(ctx, actor)
            if type(form).__name__ in delegation.ROUTED_FORMS
            else actor
        )
        if decider != actor:
            # The visibility Owner Guard: a delegated draw is offered only
            # from a pool the decider can SEE — legal actions must be a
            # function of the decider's own information state, or two worlds
            # the decider cannot tell apart would offer different moves.
            # Runtime rather than resolve because whether a seat's pool is
            # delegated depends on both helpers' values at the same seat,
            # which two opaque expression bodies do not statically reveal.
            delegation.check_decider_sees(ctx, decider, actor, form)
        choice = ctx.chooser(decider, candidates, 1)[0]  # the single per-step draw
        ctx.trace("decision", (actor, choice))  # the canonical decision event (§4)
        observe.choice(ctx, decider, choice)
        state = form.apply(actor, choice, state, replace(ctx, decider=decider))
    result = form.outcome(state, ctx)
    # After `outcome`, never before: the winner function runs as a primitive, and
    # `EngineFacts.round_state` hands it `mech_state[-1]` while a frame is live.
    # Popping first would silently feed it `last_round_state` instead.
    if published:
        ctx.rs.last_round_state = ctx.rs.mech_state.pop()
    return result


class TrickForm:
    """The [[trick]] form: one turn-order pass from the leader, each participant
    playing one legal card, until every participant has played (`next_actor` ⇒
    `None`) or an `early` predicate ends the pass; the winner function then picks
    the winner. Alone among the forms it exposes its [[round-state]] to the
    surrounding body — `init` pushes the accumulator onto `mech_state` (the
    `state.` pronoun), which `run_decision_round` pops into `last_round_state`
    once the round closes, so the body can still read
    `state.trick_terminated_early` afterward."""

    def __init__(self, stmt: n.TrickRound, ctx: Ctx) -> None:
        from cardlang.runtime import primitives

        # `winner_fn` / `early_termination` are bare native value-function names
        # on the node, validated at resolve time. Nothing is asserted about them
        # or about the card zones: the node's own field types say they are
        # present, which is what the split bought.
        self.participants: list[Player] = list(evaluate(stmt.participants, ctx))
        self.leader: Player = evaluate(stmt.leader, ctx)
        self.source_family = stmt.source_zone
        self.play_zone = stmt.play_zone
        self.winner_fn_name = stmt.winner_fn
        self.winner_fn = primitives.value_function(stmt.winner_fn)
        self.early_term = (
            primitives.value_function(stmt.early_termination)
            if stmt.early_termination is not None
            else None
        )
        # A Trick Order game declares no trump anywhere — the block's `trump:`
        # row is the trump, and resolve's presence partition refuses both the
        # game clause (R1) and the round's (R2) beside a block.
        self.trump: str | None = (
            evaluate(stmt.trump, ctx) if stmt.trump is not None else ctx.rs.trump
        )
        # Constant for the pass: the active rules, as a rules-bearing ctx. The
        # phase is kept rather than its transition list — which of its modes
        # still hold is re-read per play, since a play inside THIS trick is
        # what deactivates one.
        self.trick_ctx = ctx.with_rules(
            active_rules.compute_active_rules(ctx.current_phase, ctx.rs)
        )
        self.transition_phase = ctx.current_phase

    def init(self, state: RoundState, ctx: Ctx) -> RoundState:
        state["led_suit"] = None
        state["trick_terminated_early"] = False
        state["trump"] = self.trump
        state["played"] = []
        # The turn-order pass, materialized so `next_actor` is a pure function of
        # the cursor `idx` (seating is fixed within a round).
        state["order"] = list(ctx.rs.seating.turn_order_from(self.leader))
        state["idx"] = 0
        ctx.rs.mech_state.append(state)
        return state

    def terminated(self, state: RoundState, ctx: Ctx) -> bool:
        return bool(state["trick_terminated_early"])

    def next_actor(self, state: RoundState, ctx: Ctx) -> Player | None:
        order: list[Player] = state["order"]
        while state["idx"] < len(order):
            player = order[state["idx"]]
            state["idx"] += 1
            if player in self.participants:
                return player
        return None  # turn order ran out: every participant has played

    def candidates(self, actor: Player, state: RoundState, ctx: Ctx) -> list[Any]:
        # The acting seat's effective source: routed by `play_source_for`
        # when defined, else the declared family's instance — the ONE pool
        # candidates, rule bodies, and the removal in `apply` all read
        # (issue #457's class: two reads, one answer).
        src = delegation.source_for(
            self.trick_ctx, actor, ctx.rs.zones.instance(self.source_family, actor)
        )
        candidates = rules.legal_cards(
            actor,
            RULE_ENFORCED_MOVE_TYPE,
            replace(self.trick_ctx, round_source=(self.source_family, src)),
        )
        if not candidates:
            # No implicit pass: a player on turn must have a legal play. An empty
            # set means a rule filtered every card with no `if_impossible` fallback,
            # or the player's hand is exhausted — both malformed for a trick.
            raise OwnerGuardError(
                f"player {actor} has no legal play in the trick; a constraining "
                f"rule needs an `if_impossible` clause, or the participants are wrong"
            )
        return candidates

    def apply(self, actor: Player, choice: Any, state: RoundState, ctx: Ctx) -> RoundState:
        src = delegation.source_for(
            ctx, actor, ctx.rs.zones.instance(self.source_family, actor)
        )
        src.remove(choice)
        src_addr = ctx.rs.zones.locate(src)
        # Arrival.actor is the DECIDING seat and the source address carries
        # the owning seat — "two facts, deliberately" (decisions.md "The
        # Arrival Record"); winner paths pair cards with the owner.
        ctx.rs.zones.single(self.play_zone).add(
            choice, ctx.decider if ctx.decider is not None else actor, src_addr
        )
        observe.movement(ctx, src_addr, (self.play_zone, None), [choice])
        state["played"].append((actor, choice))
        ctx.trace("play", (actor, choice))
        if state["led_suit"] is None:
            state["led_suit"] = choice.suit
        _fire_transitions(self.transition_phase, Move(choice, actor), self.trick_ctx)
        # An `early` predicate ends the trick mid-pass; the winner function
        # picks from the plays so far (Getaway: a void player's off-led-suit
        # play, with the winner then picking up the pile).
        if self.early_term is not None and self.early_term(choice, state["led_suit"]):
            state["trick_terminated_early"] = True
        return state

    def outcome(self, state: RoundState, ctx: Ctx) -> Outcome:
        ctx.trace(
            "trick_end", {"early": state["trick_terminated_early"], "trump": self.trump}
        )
        # The winner callback answers one of TWO contracts, keyed by
        # `TRICK_ORDER_GATED_WINNERS` and dispatched by the one
        # `primitives.value_function`: the registry selects which call shape to
        # make, and the callable that dispatcher returned is what runs, either
        # way.
        if self.winner_fn_name in TRICK_ORDER_GATED_WINNERS:
            # The Trick Order contract. Its trumps, follow classes and
            # strengths are the GAME's declared rows, so it takes the plays and
            # a ctx to evaluate them under — never the round's led suit or
            # trump, which a block game does not have (R1/R2).
            winner = self.winner_fn(reads.deep_freeze(state["played"]), ctx)
        else:
            # The uniform contract: reads its plays and rank strengths as
            # arguments, not through a bundle, so the live `played` list and
            # `rank_index` dict are frozen here — the direct-call-site
            # analogue of `reads.coerce_args`.
            winner = self.winner_fn(
                reads.deep_freeze(state["played"]),
                state["led_suit"],
                self.trump,
                reads.deep_freeze(ctx.rs.rank_index),
            )
        # shadow guard: resolve admits only the trick-winner namespace (both
        # homes) into this slot, and every member returns a seat
        assert isinstance(winner, int)
        ctx.trace("trick", (winner, [c for _, c in state["played"]]))
        return winner


def param_domain(p: n.Parameter, actor: Player, ctx: Ctx) -> list[Any]:
    """One parameter's value-domain for the acting player. `Card` is the actor's
    live hand, in hand order — the state-dependent outlier, handled here ahead of
    the domain table (cardlang/domains.py) rather than as a row in it. Every
    other admitted spelling is a table lookup: `enumerate_domain` reads the
    registry row for the declared type and enumerates it from the runtime
    `DomainSources` built below.

    The sources are the LIVE runtime state, never module constants: `rs.suits`
    (set at driver setup from the game's deck) so a non-standard-suit deck
    (Coup's `coup15`, whose only suit is `"court"`) enumerates its own suits
    rather than the French four, and `rs.rank_index` for the declared ranking.

    `rank_index` is passed as a plain `list(...)` over the dict, never a sort:
    `driver.py` builds it by `enumerate(game.ranking)` in order, and a Python
    dict preserves insertion order, so its keys already walk the declared
    `ranking:` order. Sorting ascending by strength value (the dict's values)
    would walk it BACKWARDS for a high-to-low declaration (`ranking: A K Q ... 2`
    maps A to the highest strength number), which contradicts decisions.md
    "Declared parameter domains" ("Rank enumerates the game's declared
    ranking:") and the encoding.py comment asserting this runtime source and the
    static `list(game.ranking)` one are identical by construction. Note this is
    a DIFFERENT source from the `rank` role's runtime members (`rs.ranks`, which
    falls back to deck order when no `ranking:` is declared) — the deliberate
    divergence the domains module documents."""
    if p.type_name == "Card":
        return list(ctx.rs.zones.instance("hand", actor).cards)
    return enumerate_domain(
        p.type_name,
        DomainSources(
            suits=ctx.rs.suits,
            ranks=list(ctx.rs.rank_index),
            players=list(ctx.rs.seating.players),
            positions=ctx.rs.position_domains,
            directions=ctx.rs.direction_domains,
        ),
    )


def _pack(combo: tuple[Any, ...]) -> Any:
    """A candidate's value: None (nullary), the bare value (arity 1), or the
    tuple (arity >= 2). Arity 1 stays bare so existing offering keys are unchanged."""
    if not combo:
        return None
    return combo[0] if len(combo) == 1 else combo


def bind_params(ctx: Ctx, params: tuple[n.Parameter, ...], value: Any) -> Ctx:
    """Bind a candidate's value(s) as locals for the guard/effect that reads
    them. Arity comes from `params`, never guessed from `value`: a `Suit?`
    domain's `None` (no-trump) is a legitimate arity-1 VALUE, distinct from a
    nullary candidate's `None` (`_pack` collapses both to bare `None`, so only
    `params` can disambiguate). Branching on `value is None` instead would
    silently drop the binding for a `None`-valued arity-1 candidate, and any
    guard/effect read of that parameter would then raise `KeyError`."""
    if not params:
        return ctx
    combo = (value,) if len(params) == 1 else tuple(value)
    for p, v in zip(params, combo):
        ctx = ctx.with_local(p.name, v)
    return ctx


def concrete_moves(mt: n.MoveTypeDef, actor: Player, ctx: Ctx) -> list[tuple[str, Any]]:
    """The guard-filtered candidate list for one move type: the cross-product of
    its parameters' domains, in declaration order, each combo guard-checked with
    all parameters bound. Nullary is the empty-product case (one empty combo).

    `ctx` must already be bound to `actor` (`ctx.acting_as(actor)`) — a decision
    offering several move types (`AuctionForm.candidates`, `execute._offer`)
    hoists that binding once, outside its per-move-type loop, rather than have
    every move type in the offering redundantly recompute the same rebind."""
    domains = [param_domain(p, actor, ctx) for p in mt.params]
    out: list[tuple[str, Any]] = []
    for combo in itertools.product(*domains):
        value = _pack(combo)
        vctx = bind_params(ctx, mt.params, value)
        if mt.when is None or bool(evaluate(mt.when, vctx)):
            out.append((mt.name, value))
    return out


class AuctionForm:
    """The auction/betting form: a continuous ring over an [[offering]], looping
    until the termination predicate holds.

    Each turn the acting player chooses one of the legal *concrete* moves — every
    parameterized move expanded over its value-domain and guard-filtered, plus the
    nullary moves — as a single flat candidate list (one chooser draw, matching
    OpenSpiel's one-decision-node-per-turn action set). The chosen move's effect
    runs with `actor` (and the move parameter) bound, threading the bid history.

    One axis varies here, as a *value* on a hook rather than a new slot; the
    other the form carries is settled at one value, and the pair is worth reading
    together because it is what the axes-not-slots claim rests on:

    - **outcome (optional).** An auction supplies `outcome <fn>` and `outcome`
      produces the phase's typed outcome `(tag, payloads)` from the bid history when
      the ring closes. A betting round omits it (`outcome` returns `None`): the move
      effects have already mutated the shared chip/fold state, so the ring just
      closes and the surrounding body deals the next street or settles.
    - **order.** `next_actor` is the order axis refunctionalized, and one
      traversal stands: `ring` (equivalently, no `order` clause) advances the
      pointer each turn, so a seat that has acted is offered again only when the
      ring wraps. That is also poker's continuation order, three mechanisms
      jointly: the advancing pointer reaches the seats behind the aggressor
      next; the participants filter, re-evaluated each turn, brings the seats a
      bet re-opened back when the ring returns to them; and `until`, checked
      before every draw, closes the round mid-lap the moment nobody is pending. The participants clause and
      the termination predicate must agree, so an empty ring with `until` still
      false is malformed, raised rather than silently ended.
    """

    def __init__(self, stmt: n.AuctionRound, ctx: Ctx) -> None:
        # The OWNER GUARD for "the order axis holds no row this form cannot walk".
        # It shadows nothing: resolve owns whether a DECLARED mode is in the
        # registry, and no guard anywhere owns whether the registry has outgrown
        # its consumer — which is the condition here, and the reason the remedy is
        # a reconciliation rather than a check on the statement (decisions.md,
        # "Allow-list, never deny-list"). An assert is the channel because no game
        # description can reach it: the trigger is an edit to `ROUND_ORDER_MODES`,
        # so the reader it addresses is the engine maintainer making that edit.
        # It sits on the form rather than at module import, unlike its siblings,
        # because the row it pins is this form's — `next_actor`'s traversal — and
        # a tree with no auction round has no such row to be wrong about.
        assert n.ROUND_ORDER_MODES == {n.ROUND_ORDER_RING}, (
            f"the auction form implements the ring row only, and the order axis "
            f"now holds {sorted(n.ROUND_ORDER_MODES)} — a mode added to "
            f"`ROUND_ORDER_MODES` reaches this form as ring unless `next_actor` "
            f"gains its traversal"
        )
        self.stmt = stmt
        self.until: n.Expr = stmt.until
        self.order: list[Player] = ctx.rs.seating.turn_order_from(
            evaluate(stmt.leader, ctx)
        )
        self.move_defs = [ctx.rs.move_type_index[name] for name in stmt.offering]

    def init(self, state: RoundState, ctx: Ctx) -> RoundState:
        # This form publishes nothing to `state.` — it never pushes onto
        # `mech_state` (AUCTION_PUBLISHED is empty, and deliberately so). Clearing
        # `last_round_state` is what makes that honest: without it, `state.led_suit`
        # read during or after an auction found `mech_state` empty, fell through to
        # the fallback, and silently returned the state of whatever trick ran LAST
        # — a stale frame from a different form. `_pronoun`'s "fail loudly, don't
        # return a stale or empty frame" is only true because of this line.
        ctx.rs.last_round_state = None
        state["i"] = 0  # the ring pointer
        state["guard"] = 0
        state["history"] = []
        return state

    def terminated(self, state: RoundState, ctx: Ctx) -> bool:
        return bool(evaluate(self.until, ctx))

    def next_actor(self, state: RoundState, ctx: Ctx) -> Player | None:
        order = self.order
        # The participants ring is re-evaluated each step (the participant-filter
        # axis): a player the predicate drops mid-ring — a standing high bidder, a
        # player who has passed for good — is skipped with no chooser draw. The
        # ascending auctions (Pinochle, Tarot, Skat) and Stud's betting state the
        # shrinking ring this way; a static ring (Bridge's `all players`) is the
        # invariant case (decisions.md "The auction form of `round`"). Membership
        # is set-tested, so `order` stays the single source of sequencing.
        while True:
            state["guard"] += 1
            if state["guard"] > 1000:  # ring steps, not productive turns
                raise OwnerGuardError(
                    "auction did not terminate within 1000 ring steps — a fixed "
                    "engine limit, not the game's `max_length`, so raising that "
                    "declaration will not help: the `until` predicate and the "
                    "participants clause must between them end the ring"
                )
            participants = set(evaluate(self.stmt.participants, ctx))
            if not participants:
                # Nobody is in the ring and `until` is still false — `terminated`
                # runs before this method, so reaching here means the predicate
                # said the round goes on. Named for what it is rather than left
                # to spin out the step limit above, which reports a runaway loop
                # for what is a disagreement between two clauses.
                raise OwnerGuardError(
                    "auction: no participant is pending but the `until` predicate "
                    "is unsatisfied (the termination and participants clauses "
                    "disagree)"
                )
            pointer: int = state["i"]
            state["i"] = pointer + 1
            player = order[pointer % len(order)]
            if player in participants:
                return player
            # A non-participant in ring mode is skipped with no draw; loop on (the
            # skip mutates nothing, so the top-of-loop `terminated` cannot flip).

    def candidates(self, actor: Player, state: RoundState, ctx: Ctx) -> list[Any]:
        # Every move type's guard-filtered cross product (`concrete_moves`),
        # concatenated in offering order — one flat candidate list, matching
        # OpenSpiel's one-decision-node-per-turn action set. The Card domain
        # (state-dependent: the actor's live hand, in hand order) and the
        # Suit/Suit?/Rank/Player domains (deck/seating-sourced) are both handled
        # inside `concrete_moves`/`param_domain`. `acting_as` is bound once here
        # (not once per move type inside `concrete_moves`) since every move type
        # in the offering shares the same actor for this decision.
        pctx = ctx.acting_as(actor)
        candidates: list[tuple[str, Any]] = []
        for mt in self.move_defs:
            candidates.extend(concrete_moves(mt, actor, pctx))
        if not candidates:
            # A participant offered a turn must have a legal move — the
            # finite-action invariant of a decision node. The engine does NOT
            # silently skip a player with nothing to do: who is still in the ring
            # is for the game to state (the participants clause, `over … [where …]`),
            # and "all but one has passed" is its `until` predicate — not an engine
            # default (decisions.md "The auction form of `round`"). So an empty
            # candidate set is a malformed game: a missing always-legal move (give
            # `pass` no `when:`), or a participants filter that should have dropped
            # this player.
            raise OwnerGuardError(
                f"auction: participant {actor} has no legal move. Give an "
                f"always-legal move (e.g. an unguarded `pass`) or exclude "
                f"dropped-out players from the participants clause "
                f"(offering {list(self.stmt.offering or ())})"
            )
        return candidates

    def apply(self, actor: Player, choice: Any, state: RoundState, ctx: Ctx) -> RoundState:
        from cardlang.runtime.execute import run_body

        observe.announce(ctx, actor, choice)
        name, value = choice
        mt = ctx.rs.move_type_index[name]
        pctx = ctx.acting_as(actor)
        eff_ctx = bind_params(pctx, mt.params, value)
        run_body(mt.effect, eff_ctx)
        state["history"].append((actor, name, value))
        return state

    def outcome(self, state: RoundState, ctx: Ctx) -> Outcome:
        if self.stmt.outcome_fn is None:
            return None  # betting: the shared chip/fold state is already settled
        from cardlang.runtime import primitives

        return primitives.auction_outcome_function(self.stmt.outcome_fn)(
            state["history"], ctx
        )


class ClimbForm:
    """The climbing form: one combination-climbing trick. The leader leads a
    combination from the `combinations` lead query; then each participant beats the
    standing play (from the `follows` query) or passes. A pass does **not** drop a
    player — the trick ends when action returns to the last player who played
    (everyone else passed one full lap, `next_actor` ⇒ `None`), or when the `until`
    predicate holds (a player has shed out, ending the hand mid-trick). The last
    player to play is the [[winner]], bound as `winner` for the surrounding body,
    which routes the pile and sets the next lead. The combination engine is
    game-local, so this depends only on the queries' interface: each returns a list
    of plays, and a play exposes the cards it moves as a `.cards` tuple — plus,
    optionally, an `ends_trick` marker (Tichu's Dog): a lead so marked ends the
    trick at once, its followers drawing nothing. Players
    already shed out (Tichu) are skipped with no chooser draw — INCLUDING the
    named leader, who in a continue-after-going-out game may have shed their
    last card on the play that won them the lead; the lead then falls to the
    first participant at or after them in turn order. Big Two ends the
    trick the instant a player sheds, so its participants all hold cards throughout.

    Like the trick form, the climbing form exposes its state to the surrounding
    body: `init` pushes the accumulator onto `mech_state` and `run_decision_round`
    pops it into `last_round_state`, so the body reads `state.lead_ended_trick` (did a
    trick-ending lead close it?) and `state.shed_first` / `state.shed_second`
    (the first two players who played their last cards this trick, in play
    order — finishing order is score-bearing in Tichu). Big Two reads none of
    these; its goldens gate the no-change.
    """

    def __init__(self, stmt: n.ClimbRound, ctx: Ctx) -> None:
        from cardlang.runtime import primitives

        self.until: n.Expr = stmt.until
        self.leader: Player = evaluate(stmt.leader, ctx)
        self.lead_query = primitives.climb_lead_function(stmt.combos_fn)
        self.follow_query = primitives.climb_follow_function(stmt.follows_fn)
        self.climb_row = primitives.climb_row(stmt.combos_fn)
        self.hands = ctx.rs.zones.families[stmt.source_zone]
        self.pile = ctx.rs.zones.single(stmt.play_zone)
        self.source_name: str = stmt.source_zone
        self.pile_name: str = stmt.play_zone
        # The participant ring in seating order from the leader. `from` and
        # `over` are independent game expressions, so the leader need not be a
        # participant: in a game where going out does NOT end the hand, the
        # trick winner can shed their last card on the winning play and still
        # be the named leader. That is a normal state, not a malformed game —
        # the ring simply starts at the first participant at or after them,
        # which is what the trick, auction and `turns` paths already do with
        # the same clause pair.
        participants = set(evaluate(stmt.participants, ctx))
        self.ring: list[Player] = [
            p for p in ctx.rs.seating.turn_order_from(self.leader) if p in participants
        ]
        if not self.ring:
            # Runtime DATA, not a compiler invariant: nobody satisfies `over`,
            # so there is no one to lead and no one to follow. Report it
            # about the participants — the leader is not the problem.
            raise OwnerGuardError(
                f"round climb: no participant to lead — the `over` set is "
                f"empty, so the round has no actor (leader was "
                f"{self.leader}); make `until` cover this state"
            )
        # Lead from the first surviving seat. Rebinding `leader` (rather than
        # only the ring) keeps `init`'s `state["last"]` — the lap-completion
        # sentinel `next_actor` compares against — pointing at a player who is
        # actually in the ring.
        self.leader = self.ring[0]

    def init(self, state: RoundState, ctx: Ctx) -> RoundState:
        state["current"] = None  # the standing play; None until the leader leads
        state["last"] = self.leader  # the last player to play
        state["idx"] = 0  # the ring cursor
        state["guard"] = 0
        state["lead_ended_trick"] = False  # a Dog-style lead closed the trick
        state["shed_first"] = None  # first two sheds this trick, in play order
        state["shed_second"] = None
        ctx.rs.mech_state.append(state)
        return state

    def terminated(self, state: RoundState, ctx: Ctx) -> bool:
        # Gated on `current is not None`: the shed-out predicate is checked only
        # *after* a play (never before the leader leads), so the leader always gets
        # to lead even if a player is already shed out. Evaluating it at the top of
        # every step (including after passes) is safe — a pass sheds nothing, so the
        # predicate cannot flip, and it draws no card.
        if state["current"] is not None and state["lead_ended_trick"]:
            return True  # a trick-ending lead: the followers draw nothing
        return state["current"] is not None and bool(evaluate(self.until, ctx))

    def next_actor(self, state: RoundState, ctx: Ctx) -> Player | None:
        ring = self.ring
        while True:
            state["guard"] += 1
            if state["guard"] > 5000:
                raise OwnerGuardError(
                    "climb trick exceeded 5000 plays without resolving — a "
                    "fixed engine limit, not the game's `max_length`, so "
                    "raising that declaration will not help: make the `until` "
                    "predicate reachable, or drop players who can never play "
                    "from the `over` clause"
                )
            pointer: int = state["idx"]
            turn = ring[pointer % len(ring)]
            if state["current"] is not None and turn == state["last"]:
                return None  # action returned to the last player: the trick is spent
            if not self.hands[turn].cards:  # already shed out (Tichu): skip, no draw
                state["idx"] = pointer + 1
                continue
            return turn

    def candidates(self, actor: Player, state: RoundState, ctx: Ctx) -> list[Any]:
        # The climb engines are game-local, so they get the same value
        # bundles every other primitive does rather than the live ctx — and
        # their hand argument is deep_frozen for the same reason `call()`
        # freezes collection args: it is `self.hands[actor].cards`, a live
        # zone list a query could otherwise mutate.
        facts, gr = narrowing.bind(ctx.rs, ctx.current_player, self.climb_row)
        hand = reads.deep_freeze(self.hands[actor].cards)
        if state["current"] is None:  # the leader must lead
            return self.lead_query(facts, gr, hand)
        # `state["current"]` is the live standing `Play` in the round
        # accumulator; freeze it too, or a follow query could object.__setattr__
        # its key/kind/cards and corrupt the engine's standing play.
        standing = reads.deep_freeze(state["current"])
        return [*self.follow_query(facts, gr, hand, standing), "pass"]

    def apply(self, actor: Player, choice: Any, state: RoundState, ctx: Ctx) -> RoundState:
        if choice == "pass":
            observe.announce(ctx, actor, "pass")
            state["idx"] += 1
            return state
        play = choice
        for c in play.cards:
            self.hands[actor].remove(c)
        self.pile.add_all(play.cards, actor, (self.source_name, actor))
        observe.movement(ctx, (self.source_name, actor), (self.pile_name, None), play.cards)
        state["current"], state["last"] = play, actor
        state["idx"] += 1
        if not self.hands[actor].cards:  # played their last cards: record the shed
            if state["shed_first"] is None:
                state["shed_first"] = actor
            elif state["shed_second"] is None:
                state["shed_second"] = actor
        if getattr(play, "ends_trick", False):
            state["lead_ended_trick"] = True
        return state

    def outcome(self, state: RoundState, ctx: Ctx) -> Outcome:
        last: Player = state["last"]
        return last


def build_form(stmt: n.TrickRound | n.AuctionRound | n.ClimbRound, ctx: Ctx) -> DecisionForm:
    """Select the hook bundle for a `round` by which form it is.

    Dispatch on type, so the arms are disjoint and their ORDER carries no
    meaning. It used to: this cascade tested `combos_fn` before `offering`
    while resolve's tested `offering` before `combos_fn`, and the two agreed
    only because the parser never set both. A node that had would have
    validated as an auction and run as a climb."""
    match stmt:
        case n.ClimbRound():
            return ClimbForm(stmt, ctx)
        case n.AuctionRound():
            return AuctionForm(stmt, ctx)
        case n.TrickRound():
            return TrickForm(stmt, ctx)


def _fire_transitions(phase: n.Phase | None, move: Move, ctx: Ctx) -> None:
    """Evaluate each play-triggered transition's predicate against the move just
    played; a satisfied one marks its target as reached for this iteration.

    Only the transitions of modes that STILL HOLD are evaluated: an exit
    belongs to its condition, so once that condition has ended its remaining
    exits are gone with it. That has to be enforced twice over, because a
    condition can end on this very play as well as on an earlier one: the
    grouping filters modes deactivated before now, and the `break` stops a
    mode's remaining exits the instant one of them fires. Two exits of one
    mode that a SINGLE play satisfies — two unconditional ones, or any pair of
    overlapping predicates — would otherwise both reach their targets inside
    this loop. Independent modes keep being evaluated; only the fired one's
    siblings stop."""
    for _mode, exits in active_rules.active_mode_exits(phase, ctx.rs):
        for t in exits:
            # Shadow Guard. The Owner Guard is `resolve._resolve_transition`,
            # which rejects any event move type but `play_to_trick`, so no
            # other kind reaches here. Kept because this loop fires effects:
            # were the Owner Guard ever relaxed, silently treating an unknown event
            # as a trick play is the worse failure.
            if t.event.move_type != "play_to_trick":
                continue
            pred = t.event.where
            if pred is None or bool(evaluate(pred, ctx.with_action(move))):
                ctx.rs.fired_transitions.add(t.mode)
                break
