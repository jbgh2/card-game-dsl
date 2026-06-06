"""The Trick mechanic runtime (the main deferred runtime-primitive).

`instantiate` dispatches `instantiate Trick(...)`; `run_trick` plays one trick:
each participant in turn order from the leader plays a legal card, the lead sets
`led_suit`, then `outcome` selects a player and `routing` relocates the played
cards. Returns the next leader.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime import phases, rules
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, Move
from cardlang.runtime.values import SUITS, Card, Player


def instantiate(stmt: n.Instantiate, ctx: Ctx) -> Player:
    if stmt.mechanic == "SchnapsenHand":
        return run_schnapsen_hand(stmt, ctx)
    if stmt.mechanic == "PinochleHand":
        return run_pinochle_hand(stmt, ctx)
    if stmt.mechanic == "BridgeAuction":
        return run_bridge_auction(stmt, ctx)
    if stmt.mechanic == "SkatHand":
        from cardlang.runtime.skat import run_skat_hand

        return run_skat_hand(stmt, ctx)
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


# ---------------------------------------------------------------------------
# Pinochle hand mechanic
# ---------------------------------------------------------------------------
#
# Pinochle's hand is, like Schnapsen's, built concretely: an ascending auction,
# the high bidder's trump declaration (he must hold a marriage in the suit, else
# he abandons the bid), deterministic meld scoring, then twelve strict tricks.
# Auctions differ in shape across the corpus (Bridge double/redouble, Skat's
# Reizen, Tarot's four levels), so this is not generalized yet; nor are the
# strict-trick legality rules, which recur (Schnapsen endgame, here, and the
# coming trump games) and are flagged in IMPLEMENTATION_LOG.md as the surface to
# lift into the rule DSL. The random chooser bids/passes and plays uniformly;
# melding is forced (a rational player melds everything), so it is a pure
# computation, not a choice.


def pinochle_meld(cards: list[Card], trump: str) -> int:
    """Standard single-pack Pinochle meld value of a hand given the trump suit.
    Doubles (two copies) score the published double values. The only intra-class
    overlap handled is the trump run subsuming its own marriage."""
    cnt = Counter((c.rank, c.suit) for c in cards)
    doubles = {0: 0, 1: 1, 2: 2}  # copies present, capped at 2 (pack has two)
    score = 0

    run_cards = [("A", trump), ("10", trump), ("K", trump), ("Q", trump), ("J", trump)]
    n_run = min(cnt[m] for m in run_cards)
    score += {0: 0, 1: 150, 2: 1500}[doubles[min(n_run, 2)]]
    score += 10 * cnt[("9", trump)]  # dix

    for s in SUITS:
        marr = min(cnt[("K", s)], cnt[("Q", s)])
        if s == trump:
            score += 40 * max(0, marr - n_run)  # K-Q used by the run don't recount
        else:
            score += 20 * marr

    n_pin = min(cnt[("Q", "spades")], cnt[("J", "diamonds")])
    score += {0: 0, 1: 40, 2: 300}[min(n_pin, 2)]

    for rank, single, double in (("A", 100, 1000), ("K", 80, 800), ("Q", 60, 600), ("J", 40, 400)):
        n = min(cnt[(rank, s)] for s in SUITS)
        score += {0: 0, 1: single, 2: double}[min(n, 2)]
    return score


def _pinochle_legal(
    hand: list[Card],
    trick: list[tuple[Player, Card]],
    led_suit: str,
    trump: str,
    rank: dict[str, int],
) -> list[Card]:
    """A follower's legal cards: follow suit and head the led suit if able; else
    trump and over-trump if able; else anything."""
    same = [c for c in hand if c.suit == led_suit]
    if same:
        led_in_trick = [c for _, c in trick if c.suit == led_suit]
        best = max(led_in_trick, key=lambda c: rank[c.rank])
        higher = [c for c in same if rank[c.rank] > rank[best.rank]]
        return higher or same
    trumps = [c for c in hand if c.suit == trump]
    if trumps:
        trump_in_trick = [c for _, c in trick if c.suit == trump]
        if trump_in_trick:
            best_t = max(trump_in_trick, key=lambda c: rank[c.rank])
            over = [c for c in trumps if rank[c.rank] > rank[best_t.rank]]
            return over or trumps
        return trumps
    return list(hand)


def run_pinochle_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    from cardlang.runtime import stdlib

    rs = ctx.rs
    args = {a.name: a.value for a in stmt.args}
    opener: Player = evaluate(_expr(args["opener"]), ctx)
    players = list(rs.seating.players)
    hands = rs.zones.families["hand"]
    captured = rs.zones.families["captured"]
    rank = rs.rank_index

    # --- ascending auction ---
    order = rs.seating.turn_order_from(opener)
    passed: dict[Player, bool] = {p: False for p in players}
    current_bid = 0
    high_bidder: Player | None = None
    opening, increment, cap, max_bids = 50, 10, 250, 16
    bids = 0
    i = 0
    while sum(not passed[p] for p in players) > 1 and bids < max_bids:
        p = order[i % len(order)]
        i += 1
        if passed[p] or p == high_bidder:
            continue
        next_bid = current_bid + increment if current_bid else opening
        if next_bid > cap:
            passed[p] = True
            continue
        if ctx.chooser(p, ["bid", "pass"], 1)[0] == "bid":
            current_bid = next_bid
            high_bidder = p
            bids += 1
        else:
            passed[p] = True
    if high_bidder is None:
        high_bidder, current_bid = opener, opening
    rs.set("high_bidder", high_bidder)
    rs.set("current_bid", current_bid)

    # --- trump declaration (needs a marriage in the chosen suit) ---
    hb = hands[high_bidder].cards
    marriage_suits = [
        s
        for s in SUITS
        if any(c.rank == "K" and c.suit == s for c in hb)
        and any(c.rank == "Q" and c.suit == s for c in hb)
    ]
    if not marriage_suits:
        rs.set("bid_abandoned", True)
        return high_bidder
    rs.set("bid_abandoned", False)
    trump = ctx.chooser(high_bidder, marriage_suits, 1)[0]
    rs.set("trump_suit", trump)

    # --- meld (forced; a pure computation) ---
    meld_score = rs.get("meld_score")
    for p in players:
        meld_score[rs.team_of[p]] += pinochle_meld(hands[p].cards, trump)

    # --- twelve strict tricks ---
    trick_score = rs.get("trick_score")
    counters = {"A": 10, "10": 10, "K": 10}
    leader = high_bidder
    last_winner = leader
    for _ in range(12):
        trick: list[tuple[Player, Card]] = []
        for q in rs.seating.turn_order_from(leader):
            hand = hands[q].cards
            legal = (
                list(hand)
                if not trick
                else _pinochle_legal(hand, trick, trick[0][1].suit, trump, rank)
            )
            card = ctx.chooser(q, legal, 1)[0]
            hands[q].remove(card)
            trick.append((q, card))
            ctx.trace("play", (q, card))
        led_suit = trick[0][1].suit
        winner = stdlib.highest_trump_or_led_suit(trick, led_suit, trump, rank)
        ctx.trace("trick_end", {"trump": trump})
        ctx.trace("trick", (winner, [c for _, c in trick]))
        team = rs.team_of[winner]
        for _, c in trick:
            captured[team].add(c)
            trick_score[team] += counters.get(c.rank, 0)
        last_winner = winner
        leader = winner
    trick_score[rs.team_of[last_winner]] += 10  # ten for the last trick

    ctx.trace(
        "pinochle_hand",
        {"meld": dict(meld_score), "trick": dict(trick_score), "abandoned": False},
    )
    return high_bidder


# ---------------------------------------------------------------------------
# Bridge auction mechanic
# ---------------------------------------------------------------------------
#
# Bridge trick play needs only follow-suit (no head/trump obligation), so the
# DSL drives the thirteen tricks with the ordinary `Trick` mechanic (NT maps to
# trump = none). Only the auction is special, and it is built concretely here:
# ascending bids over the strain order C D H S NT, with double and redouble, the
# auction ending after three passes follow a call. Random bidders raise
# minimally (pick a strain; take the lowest level that beats the standing bid),
# which keeps contracts low enough to be made sometimes — so games and the rubber
# actually complete under random play. Doubling/redoubling and declarer
# determination (first of the partnership to name the final strain) are faithful;
# conventions and strategy are out of scope for a random playout.

_STRAINS: tuple[str | None, ...] = ("clubs", "diamonds", "hearts", "spades", None)


def run_bridge_auction(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    args = {a.name: a.value for a in stmt.args}
    opener: Player = evaluate(_expr(args["opener"]), ctx)
    order = rs.seating.turn_order_from(opener)
    team_of = rs.team_of

    cur_level = 0
    cur_strain = -1  # -1 = no bid yet
    high_team: int | None = None
    doubled = 1  # 1 undoubled, 2 doubled, 4 redoubled
    strain_first: dict[tuple[int, int], Player] = {}  # (team, strain) -> first to name it
    passes = 0
    made_bid = False
    i = 0
    guard = 0

    while True:
        guard += 1
        if guard > 500:  # safety net; minimal-ascent bids bound this far lower
            break
        p = order[i % len(order)]
        i += 1
        actions: list[tuple[Any, ...]] = [("pass",)]
        for st in range(5):  # minimal level that beats the standing bid in strain st
            lvl = 1 if cur_level == 0 else (cur_level if st > cur_strain else cur_level + 1)
            # Cap random bids at level 3: a random declarer almost never makes a
            # high contract, so without a cap a rubber takes hundreds of failed
            # hands to crawl to two games. Partscores (1-3) are made often enough
            # that games accumulate in a realistic ~dozens of hands. Game-level
            # and slam contracts are thus unreachable under random play (their
            # scoring is implemented but unexercised, like Spades' +500 branch).
            if lvl <= 3:
                actions.append(("bid", lvl, st))
        if made_bid and team_of[p] != high_team and doubled == 1:
            actions.append(("double",))
        if made_bid and doubled == 2 and team_of[p] == high_team:
            actions.append(("redouble",))

        choice = ctx.chooser(p, actions, 1)[0]
        kind = choice[0]
        if kind == "pass":
            passes += 1
            if (made_bid and passes >= 3) or (not made_bid and passes >= 4):
                break
        elif kind == "bid":
            cur_level, cur_strain = choice[1], choice[2]
            high_team = team_of[p]
            strain_first.setdefault((high_team, cur_strain), p)
            doubled = 1
            made_bid = True
            passes = 0
        elif kind == "double":
            doubled = 2
            passes = 0
        else:  # redouble
            doubled = 4
            passes = 0

    if not made_bid:
        rs.set("all_pass", True)
        return opener
    assert high_team is not None
    declarer = strain_first[(high_team, cur_strain)]
    rs.set("all_pass", False)
    rs.set("declarer", declarer)
    rs.set("contract_level", cur_level)
    rs.set("trump_suit", _STRAINS[cur_strain])
    rs.set("doubled_mult", doubled)
    return declarer


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
