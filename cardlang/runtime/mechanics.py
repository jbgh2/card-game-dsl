"""Mechanic runtime: the kernel `round` and the per-game hand engines.

`run_decision_round` is the one parameterized per-step decision loop behind every
kernel `round` form (§4 of docs/design-notes/kernel-extensibility.md). The three
sequential forms are hook bundles over it — `TrickForm` (one turn-order pass, each
participant plays a legal card, an outcome function picks the winner), `AuctionForm`
(a continuous ring/priority vocabulary over a threaded bid history, serving *both*
the auction and betting forms), and `ClimbForm` (one combination-climbing trick over
game-local engine queries). `build_form` selects the bundle by field-presence and
`execute.py` dispatches on the returned Outcome union. `instantiate` dispatches the
remaining per-game hand engines (Skat, Tichu, Coup) not yet lifted
into the DSL.
"""

from __future__ import annotations

from typing import Any, Protocol

from cardlang.ast import nodes as n
from cardlang.runtime import observe, phases, rules
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, Move
from cardlang.runtime.values import SUITS, Player


def instantiate(stmt: n.Instantiate, ctx: Ctx) -> Player:
    if stmt.mechanic == "SkatHand":
        from cardlang.runtime.skat import run_skat_hand

        return run_skat_hand(stmt, ctx)
    if stmt.mechanic == "TichuHand":
        from cardlang.runtime.tichu import run_tichu_hand

        return run_tichu_hand(stmt, ctx)
    if stmt.mechanic == "CoupGame":
        from cardlang.runtime.coup import run_coup_game

        return run_coup_game(stmt, ctx)
    raise NotImplementedError(f"mechanic '{stmt.mechanic}' not supported yet")


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

State = dict[str, Any]
Outcome = Player | tuple[str, list[Any]] | None


class DecisionForm(Protocol):
    """The six pluggable slots of one kernel `round` form."""

    def init(self, state: State, ctx: Ctx) -> State:
        """Seed the accumulator and cursor into `state`, returning it."""

    def next_actor(self, state: State, ctx: Ctx) -> Player | None:
        """Who acts next, or `None` when the actor sequence is structurally spent."""

    def candidates(self, actor: Player, state: State, ctx: Ctx) -> list[Any]:
        """The finite, canonically-ordered action set for `actor`. Non-emptiness is
        the form's own contract — it raises its own malformed-game error, so the
        messages stay form-specific (see the draw site in `run_decision_round`)."""

    def terminated(self, state: State, ctx: Ctx) -> bool:
        """The predicate end, checked at the top of the loop."""

    def apply(self, actor: Player, choice: Any, state: State, ctx: Ctx) -> State:
        """Enact the chosen action — thread the accumulator, emit any domain trace
        events — and return `state`."""

    def outcome(self, state: State, ctx: Ctx) -> Outcome:
        """The round's result: a winning `Player`, a typed `(tag, payloads)`
        variant, or `None` (a betting round mutated shared state and just closes)."""


def run_decision_round(form: DecisionForm, state: State, ctx: Ctx) -> Outcome:
    """The one per-step decision loop behind every kernel `round` form (§4 of
    docs/design-notes/kernel-extensibility.md). `form` supplies the six slots; this
    skeleton is fixed. Exactly one `ctx.chooser` draw happens per step — the sole
    source of nondeterminism, and what the OpenSpiel one-node-per-turn compilation
    rests on."""
    state = form.init(state, ctx)
    while True:
        if form.terminated(state, ctx):  # until / early / shed-out
            break
        actor = form.next_actor(state, ctx)  # ring / priority / came-back-to-last
        if actor is None:  # the actor sequence is structurally spent
            break
        candidates = form.candidates(actor, state, ctx)
        # A decision node must be non-empty. That contract lives in each form's
        # `candidates` (which raises the form-specific malformed-game error), not
        # here: the messages stay byte-identical and the climbing form keeps its
        # original empty-lead behaviour rather than a reshaped guard.
        choice = ctx.chooser(actor, candidates, 1)[0]  # the single per-step draw
        ctx.trace("decision", (actor, choice))  # the canonical decision event (§4)
        observe.choice(ctx, actor, choice)
        state = form.apply(actor, choice, state, ctx)
    return form.outcome(state, ctx)


class TrickForm:
    """The trick form: one turn-order pass from the leader, each participant
    playing one legal card, until every participant has played (`next_actor` ⇒
    `None`) or an `early` predicate ends the pass; the outcome function then picks
    the winner. Alone among the forms it exposes its `state` to the surrounding
    body — `init` pushes the accumulator onto `mech_state` (the `state.` pronoun),
    and `outcome` pops it into `last_round_state` as the winner is returned."""

    def __init__(self, stmt: n.Round, ctx: Ctx) -> None:
        from cardlang.runtime import stdlib

        # `outcome_fn` / `early_termination` are bare stdlib value-function names on
        # the Round node (validated at resolve time). Only the betting form omits
        # `outcome_fn`, and it never selects this bundle.
        assert stmt.outcome_fn is not None, "the trick form requires an outcome function"
        # The trick form carries card zones; the auction form has none.
        assert (
            stmt.source_zone is not None and stmt.play_zone is not None
        ), "the trick form of `round` carries source/into card zones"
        self.participants: list[Player] = list(evaluate(stmt.participants, ctx))
        self.leader: Player = evaluate(stmt.leader, ctx)
        self.source_family = stmt.source_zone
        self.play_zone = stmt.play_zone
        self.outcome_fn = stdlib.value_function(stmt.outcome_fn)
        self.early_term = (
            stdlib.value_function(stmt.early_termination)
            if stmt.early_termination is not None
            else None
        )
        self.trump: str | None = (
            evaluate(stmt.trump, ctx) if stmt.trump is not None else ctx.rs.trump
        )
        # Constant for the pass: the active rules (as a rules-bearing ctx) and the
        # play-triggered transitions the leader/followers may fire.
        self.trick_ctx = ctx.with_rules(
            phases.compute_active_rules(ctx.current_phase, ctx.rs)
        )
        self.transitions = phases.phase_transitions(ctx.current_phase)

    def init(self, state: State, ctx: Ctx) -> State:
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

    def terminated(self, state: State, ctx: Ctx) -> bool:
        return bool(state["trick_terminated_early"])

    def next_actor(self, state: State, ctx: Ctx) -> Player | None:
        order: list[Player] = state["order"]
        while state["idx"] < len(order):
            player = order[state["idx"]]
            state["idx"] += 1
            if player in self.participants:
                return player
        return None  # turn order ran out: every participant has played

    def candidates(self, actor: Player, state: State, ctx: Ctx) -> list[Any]:
        candidates = rules.legal_cards(actor, "play_to_trick", self.trick_ctx)
        if not candidates:
            # No implicit pass: a player on turn must have a legal play. An empty
            # set means a rule filtered every card with no `if_impossible` fallback,
            # or the player's hand is exhausted — both malformed for a trick.
            raise RuntimeError(
                f"player {actor} has no legal play in the trick; a constraining "
                f"rule needs an `if_impossible` clause, or the participants are wrong"
            )
        return candidates

    def apply(self, actor: Player, choice: Any, state: State, ctx: Ctx) -> State:
        ctx.rs.zones.instance(self.source_family, actor).remove(choice)
        ctx.rs.zones.single(self.play_zone).add(choice)
        observe.movement(ctx, (self.source_family, actor), (self.play_zone, None), [choice])
        state["played"].append((actor, choice))
        ctx.trace("play", (actor, choice))
        if state["led_suit"] is None:
            state["led_suit"] = choice.suit
        _fire_transitions(self.transitions, Move(choice, actor), self.trick_ctx)
        # A tochoo (off-suit play, only possible when void) ends the trick: the
        # highest led-suit card so far becomes the outcome and picks up the pile.
        if self.early_term is not None and self.early_term(choice, state["led_suit"]):
            state["trick_terminated_early"] = True
        return state

    def outcome(self, state: State, ctx: Ctx) -> Outcome:
        ctx.trace(
            "trick_end", {"early": state["trick_terminated_early"], "trump": self.trump}
        )
        outcome = self.outcome_fn(
            state["played"], state["led_suit"], self.trump, ctx.rs.rank_index
        )
        assert isinstance(outcome, int)
        ctx.trace("trick", (outcome, [c for _, c in state["played"]]))
        # Stash the terminal state as we pop, so the surrounding body (which does
        # the routing) can still read `state.trick_terminated_early` afterward.
        ctx.rs.last_round_state = ctx.rs.mech_state.pop()
        return outcome


def enumerate_domain(type_name: str) -> list[Any]:
    """The *static* value-domain a parameterized move ranges over, in a fixed
    order so the flattened candidate list is deterministic. `Suit` is the deck's
    suits; `Suit?` appends `none` (the no-trump strain), which ranks last.

    `Card` is deliberately absent: a Card-parameterized move's domain is
    state-dependent — the actor's live hand, enumerated by
    `AuctionForm.candidates` — and its OpenSpiel actions are the shared card
    block (`encoding.ActionSpace`), so no static enumeration exists. The
    supported domains are closed at resolve time (a round vocabulary rejects any
    other parameter type), so this dispatch is total over what reaches it."""
    base = type_name.rstrip("?")
    if base == "Suit":
        values: list[Any] = list(SUITS)
        if type_name.endswith("?"):
            values.append(None)
        return values
    raise NotImplementedError(f"move parameter domain '{type_name}' not supported yet")


class AuctionForm:
    """The auction/betting form: a continuous ring over a move vocabulary, looping
    until the termination predicate holds.

    Each turn the acting player chooses one of the legal *concrete* moves — every
    parameterized move expanded over its value-domain and guard-filtered, plus the
    nullary moves — as a single flat candidate list (one chooser draw, matching
    OpenSpiel's one-decision-node-per-turn action set). The chosen move's effect
    runs with `actor` (and the move parameter) bound, threading the bid history.

    Two axes vary, both as *values* on the hooks rather than new slots:

    - **outcome (optional).** An auction supplies `outcome <fn>` and `outcome`
      produces the phase's typed variant `(tag, payloads)` from the bid history when
      the ring closes. A betting round omits it (`outcome` returns `None`): the move
      effects have already mutated the shared chip/fold state, so the ring just
      closes and the surrounding body deals the next street or settles.
    - **order.** `next_actor` is the order axis refunctionalized. `ring` (the
      default) advances the pointer each turn, so a seat that has acted is offered
      again only when the ring wraps. `priority` re-scans the seat order from the
      leader every turn and offers the first still-pending participant, so after an
      aggression re-opens earlier seats action returns to the earliest of them
      (betting, response windows); the pointer does not advance. In priority mode
      `until` is the sole terminator — the participants clause and the termination
      predicate must agree, so an empty ring with `until` still false is malformed,
      raised rather than silently ended.
    """

    def __init__(self, stmt: n.Round, ctx: Ctx) -> None:
        assert stmt.move_types is not None and stmt.termination is not None
        self.stmt = stmt
        self.termination: n.Expr = stmt.termination
        self.order: list[Player] = ctx.rs.seating.turn_order_from(
            evaluate(stmt.leader, ctx)
        )
        self.move_defs = [ctx.rs.move_type_index[name] for name in stmt.move_types]

    def init(self, state: State, ctx: Ctx) -> State:
        state["i"] = 0  # the ring pointer (ring mode)
        state["guard"] = 0
        state["history"] = []
        return state

    def terminated(self, state: State, ctx: Ctx) -> bool:
        return bool(evaluate(self.termination, ctx))

    def next_actor(self, state: State, ctx: Ctx) -> Player | None:
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
                raise RuntimeError("auction did not terminate within 1000 ring steps")
            participants = set(evaluate(self.stmt.participants, ctx))
            if self.stmt.order_mode == n.ROUND_ORDER_PRIORITY:
                player = next((p for p in order if p in participants), None)
                if player is None:
                    raise RuntimeError(
                        "priority round: no participant is pending but the `until` "
                        "predicate is unsatisfied (the termination and participants "
                        "clauses disagree)"
                    )
                return player
            pointer: int = state["i"]
            state["i"] = pointer + 1
            player = order[pointer % len(order)]
            if player in participants:
                return player
            # A non-participant in ring mode is skipped with no draw; loop on (the
            # skip mutates nothing, so the top-of-loop `terminated` cannot flip).

    def candidates(self, actor: Player, state: State, ctx: Ctx) -> list[Any]:
        pctx = ctx.acting_as(actor)
        candidates: list[tuple[str, Any]] = []
        for mt in self.move_defs:
            if mt.param is None:
                if mt.guard is None or bool(evaluate(mt.guard, pctx)):
                    candidates.append((mt.name, None))
            else:
                if mt.param.type_name == "Card":
                    # The Card domain is state-dependent: the actor's LIVE HAND,
                    # in hand order. A static deck-order enumeration filtered to
                    # the hand would reorder the candidates and shift the chooser
                    # draw — card plays are offered in hand order, like every
                    # other card-play form. The OpenSpiel action space never
                    # enumerates this domain; a Card-parameterized move's actions
                    # are the shared card block (encoding.ActionSpace).
                    domain: list[Any] = list(
                        pctx.rs.zones.instance("hand", actor).cards
                    )
                else:
                    domain = enumerate_domain(mt.param.type_name)
                for value in domain:
                    vctx = pctx.with_local(mt.param.name, value)
                    if mt.guard is None or bool(evaluate(mt.guard, vctx)):
                        candidates.append((mt.name, value))
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
            raise RuntimeError(
                f"auction: participant {actor} has no legal move. Give an "
                f"always-legal move (e.g. an unguarded `pass`) or exclude "
                f"dropped-out players from the participants clause "
                f"(vocabulary {list(self.stmt.move_types or ())})"
            )
        return candidates

    def apply(self, actor: Player, choice: Any, state: State, ctx: Ctx) -> State:
        from cardlang.runtime.execute import run_body

        observe.announce(ctx, actor, choice)
        name, value = choice
        mt = ctx.rs.move_type_index[name]
        pctx = ctx.acting_as(actor)
        eff_ctx = pctx.with_local(mt.param.name, value) if mt.param is not None else pctx
        run_body(mt.effect, eff_ctx)
        state["history"].append((actor, name, value))
        return state

    def outcome(self, state: State, ctx: Ctx) -> Outcome:
        if self.stmt.outcome_fn is None:
            return None  # betting: the shared chip/fold state is already settled
        from cardlang.runtime import stdlib

        return stdlib.auction_outcome_function(self.stmt.outcome_fn)(
            state["history"], ctx
        )


class ClimbForm:
    """The climbing form: one combination-climbing trick. The leader leads a
    combination from the `combinations` lead query; then each participant beats the
    standing play (from the `follows` query) or passes. A pass does **not** drop a
    player — the trick ends when action returns to the last player who played
    (everyone else passed one full lap, `next_actor` ⇒ `None`), or when the `until`
    predicate holds (a player has shed out, ending the hand mid-trick). The last
    player to play is the outcome, bound as `outcome` for the surrounding body,
    which routes the pile and sets the next lead. The combination engine is
    game-local, so this depends only on the queries' interface: each returns a list
    of plays, and a play exposes the cards it moves as a `.cards` tuple. Players
    already shed out (Tichu) are skipped with no chooser draw; Big Two ends the
    trick the instant a player sheds, so its participants all hold cards throughout.
    """

    def __init__(self, stmt: n.Round, ctx: Ctx) -> None:
        from cardlang.runtime import stdlib

        assert (
            stmt.combos_fn is not None
            and stmt.follows_fn is not None
            and stmt.source_zone is not None
            and stmt.play_zone is not None
            and stmt.termination is not None
        ), "the climbing form of `round` carries combination queries and card zones"
        self.termination: n.Expr = stmt.termination
        self.leader: Player = evaluate(stmt.leader, ctx)
        self.lead_query = stdlib.climb_lead_function(stmt.combos_fn)
        self.follow_query = stdlib.climb_follow_function(stmt.follows_fn)
        self.hands = ctx.rs.zones.families[stmt.source_zone]
        self.pile = ctx.rs.zones.single(stmt.play_zone)
        self.source_name: str = stmt.source_zone
        self.pile_name: str = stmt.play_zone
        # The participant ring in seating order from the leader.
        participants = set(evaluate(stmt.participants, ctx))
        self.ring: list[Player] = [
            p for p in ctx.rs.seating.turn_order_from(self.leader) if p in participants
        ]
        assert self.ring and self.ring[0] == self.leader, "the leader must lead"

    def init(self, state: State, ctx: Ctx) -> State:
        state["current"] = None  # the standing play; None until the leader leads
        state["last"] = self.leader  # the last player to play
        state["idx"] = 0  # the ring cursor
        state["guard"] = 0
        return state

    def terminated(self, state: State, ctx: Ctx) -> bool:
        # Gated on `current is not None`: the shed-out predicate is checked only
        # *after* a play (never before the leader leads), so the leader always gets
        # to lead even if a player is already shed out. Evaluating it at the top of
        # every step (including after passes) is safe — a pass sheds nothing, so the
        # predicate cannot flip, and it draws no card.
        return state["current"] is not None and bool(evaluate(self.termination, ctx))

    def next_actor(self, state: State, ctx: Ctx) -> Player | None:
        ring = self.ring
        while True:
            state["guard"] += 1
            if state["guard"] > 5000:
                raise RuntimeError("climb trick exceeded 5000 plays without resolving")
            pointer: int = state["idx"]
            turn = ring[pointer % len(ring)]
            if state["current"] is not None and turn == state["last"]:
                return None  # action returned to the last player: the trick is spent
            if not self.hands[turn].cards:  # already shed out (Tichu): skip, no draw
                state["idx"] = pointer + 1
                continue
            return turn

    def candidates(self, actor: Player, state: State, ctx: Ctx) -> list[Any]:
        if state["current"] is None:  # the leader must lead
            return self.lead_query(self.hands[actor].cards, ctx)
        return [*self.follow_query(self.hands[actor].cards, state["current"], ctx), "pass"]

    def apply(self, actor: Player, choice: Any, state: State, ctx: Ctx) -> State:
        if choice == "pass":
            observe.announce(ctx, actor, "pass")
            state["idx"] += 1
            return state
        play = choice
        for c in play.cards:
            self.hands[actor].remove(c)
        self.pile.add_all(play.cards)
        observe.movement(ctx, (self.source_name, actor), (self.pile_name, None), play.cards)
        state["current"], state["last"] = play, actor
        state["idx"] += 1
        return state

    def outcome(self, state: State, ctx: Ctx) -> Outcome:
        last: Player = state["last"]
        return last


def build_form(stmt: n.Round, ctx: Ctx) -> DecisionForm:
    """Select the hook bundle for a `round` by field-presence: the climbing form
    carries the combination queries (`combos_fn`), the auction/betting form a move
    vocabulary (`move_types`), and the trick form neither. This is the sole
    field-presence discrimination among the forms — the interpreter and the Outcome
    union carry everything else — and it preserves the original cascade order
    (`combos_fn` before `move_types`)."""
    if stmt.combos_fn is not None:
        return ClimbForm(stmt, ctx)
    if stmt.move_types is not None:
        return AuctionForm(stmt, ctx)
    return TrickForm(stmt, ctx)


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
