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
    if stmt.mechanic == "SchnapsenHand":
        return run_schnapsen_hand(stmt, ctx)
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
    outcome = outcome_fn(played, state["led_suit"], trump, ctx.rs.rank_index)
    assert isinstance(outcome, int)
    ctx.trace("trick", (outcome, [c for _, c in played]))
    run_body(routing_body, trick_ctx.with_outcome(outcome))  # route the played cards
    ctx.rs.mech_state.pop()
    return outcome


# ---------------------------------------------------------------------------
# Schnapsen hand mechanic
# ---------------------------------------------------------------------------
#
# Schnapsen's hand is its own engine: the leader picks among heterogeneous
# moves (lead a card, declare a marriage, exchange the trump jack, close the
# talon), the two players play a trick, the winner then the loser draw from the
# talon, and play flips to strict follow-suit once the talon is closed or
# exhausted. This is built concretely for Schnapsen (corpus-first: abstract at
# the *second* instance of action-selection, not the first). The random chooser
# picks among legal moves uniformly; the only strategy baked in is claiming 66
# the moment a player reaches it (which exercises the win-by-claim settlement).
# All five move types, marriages (pending until the declarer wins a trick), the
# Viennese closing snapshot, and the strict endgame are implemented; the cardlang
# holds the deal, the settlement tiers, and termination.


def _strict_legal(
    hand: list[Card], led: Card, trump: str | None, rank: dict[str, int]
) -> list[Card]:
    """Endgame legality: follow suit and head if you can; else trump if void;
    else anything. Schnapsen has no over-trump obligation."""
    same = [c for c in hand if c.suit == led.suit]
    if same:
        higher = [c for c in same if rank[c.rank] > rank[led.rank]]
        return higher or same
    trumps = [c for c in hand if c.suit == trump]
    return trumps or list(hand)


def run_schnapsen_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    from cardlang.runtime import stdlib

    rs = ctx.rs
    args = {a.name: a.value for a in stmt.args}
    leader: Player = evaluate(_expr(args["leader"]), ctx)
    trump: str = evaluate(_expr(args["trump"]), ctx)
    rank = rs.rank_index
    values = rs.card_values
    players = list(rs.seating.players)
    hands = rs.zones.families["hand"]
    captured = rs.zones.families["captured"]
    talon = rs.zones.single("talon")
    indicator = rs.zones.single("trump_indicator")
    card_points = rs.get("card_points")
    tricks_won = rs.get("tricks_won")

    def other(p: Player) -> Player:
        return players[1] if p == players[0] else players[0]

    def stock_empty() -> bool:
        return not talon.cards and not indicator.cards

    pending: dict[Player, int] = {p: 0 for p in players}
    closed = False
    closed_by: Player | None = None
    closer_opp_cp = 0
    closer_opp_tr = 0
    claimer: Player | None = None
    last_winner = leader

    while hands[players[0]].cards and hands[players[1]].cards:
        endgame = closed or stock_empty()

        # The leader takes free actions (exchange / close), then leads a card.
        led: Card | None = None
        while led is None:
            lh = hands[leader].cards
            cands: list[tuple[Any, ...]] = [("play", c) for c in lh]
            for s in {c.suit for c in lh}:
                ranks_s = {c.rank for c in lh if c.suit == s}
                if "K" in ranks_s and "Q" in ranks_s:
                    cands.append(("marriage", s))
            if not closed and not stock_empty():
                if indicator.cards and any(
                    c.rank == "J" and c.suit == trump for c in lh
                ):
                    cands.append(("exchange",))
                if talon.cards:
                    cands.append(("close",))
            action = ctx.chooser(leader, cands, 1)[0]
            if action[0] == "exchange":
                jack = next(c for c in lh if c.rank == "J" and c.suit == trump)
                ind = indicator.cards[0]
                hands[leader].remove(jack)
                indicator.remove(ind)
                indicator.add(jack)
                hands[leader].add(ind)
            elif action[0] == "close":
                closed = True
                closed_by = leader
                closer_opp_cp = card_points[other(leader)]
                closer_opp_tr = tricks_won[other(leader)]
            elif action[0] == "marriage":
                suit = action[1]
                worth = 40 if suit == trump else 20
                if tricks_won[leader] > 0:
                    card_points[leader] += worth
                else:
                    pending[leader] += worth
                queen = next(c for c in lh if c.rank == "Q" and c.suit == suit)
                hands[leader].remove(queen)
                led = queen
            else:  # ("play", card)
                hands[leader].remove(action[1])
                led = action[1]

        follower = other(leader)
        legal = (
            _strict_legal(hands[follower].cards, led, trump, rank)
            if endgame
            else list(hands[follower].cards)
        )
        fcard = ctx.chooser(follower, legal, 1)[0]
        hands[follower].remove(fcard)

        played = [(leader, led), (follower, fcard)]
        ctx.trace("play", (leader, led))
        ctx.trace("play", (follower, fcard))
        winner = stdlib.highest_trump_or_led_suit(played, led.suit, trump, rank)
        ctx.trace("trick_end", {"trump": trump})
        ctx.trace("trick", (winner, [led, fcard]))
        captured[winner].add(led)
        captured[winner].add(fcard)
        card_points[winner] += values[led.rank] + values[fcard.rank]
        tricks_won[winner] += 1
        if pending[winner] > 0:
            card_points[winner] += pending[winner]
            pending[winner] = 0
        last_winner = winner

        for p in (winner, other(winner)):  # claim the instant a player reaches 66
            if card_points[p] >= 66:
                claimer = p
                break
        if claimer is not None:
            break

        if not closed and not stock_empty():
            for p in (winner, other(winner)):  # winner draws first
                if talon.cards:
                    hands[p].add(talon.cards.pop(0))
                elif indicator.cards:
                    hands[p].add(indicator.cards.pop(0))
        leader = winner

    rs.set("talon_closed_by", closed_by)
    rs.set("claimer", claimer)
    rs.set("closer_opp_card_points", closer_opp_cp)
    rs.set("closer_opp_tricks", closer_opp_tr)
    rs.set("last_trick_winner", last_winner)
    return last_winner


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
