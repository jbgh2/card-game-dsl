"""Tichu's game-local runtime primitives.

The hand runs fully on the kernel (tichu.cardlang): the Tichu/Grand-Tichu
calls and the push are plain statements (a `for each player` of one chosen
3-card movement, then a draw-free giver-major distribution), each climbing
trick is one `round climb` over the combination engine's queries, and the
finishing/scoring flow is statement control flow over the round's terminal
state (`state.lead_ended_trick`, `state.shed_first` / `state.shed_second`).
What stays game-local: the combination engine itself (`combinations.py`,
shared with nothing — Big Two's differs), the two non-chooser RNG sites the
monolith drew (the call-rate gates and the Dragon's trick going to a random
opponent — reproduced draw-for-draw at the same sites), partnership lookups,
and the card-point table.

The state-reading primitives (`tichu_double_victory`, `tichu_first_out`) read
the finishing order from phase state via `ctx.rs.get` — the Stud/Cribbage/Skat
precedent for game-local primitives over live state. `tichu_dragon_won` reads
the completed round's standing play from `last_round_state` (the same terminal
frame the body reads as `state.x`).
"""

from __future__ import annotations

from cardlang.runtime.combinations import Play, _combos, _legal_follows, _points
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player


# --- the climb queries (the monolith's candidate lists, verbatim) ---


def tichu_lead_options(hand: list[Card], ctx: Ctx) -> list[Play]:
    """Every combination the leader may lead: the engine's combos, then the
    three specials as lead singles in hand order (Dragon highest at 15, the
    Phoenix at 1.5, the Dog as its own trick-ending kind). `ctx` is unused —
    Tichu leads depend only on the hand — but the climb round passes it
    uniformly with the follows query."""
    leads = _combos(hand)
    for c in hand:
        if c.rank == "Dragon":
            leads.append(Play("single", 1, 15, (c,)))
        elif c.rank == "Phoenix":
            leads.append(Play("single", 1, 1.5, (c,)))
        elif c.rank == "Dog":
            leads.append(Play("dog", 1, 0, (c,)))
    return leads


def tichu_follows(hand: list[Card], current: Play, ctx: Ctx) -> list[Play]:
    """The combinations that legally beat the standing play (same kind and
    length, higher key; any bomb; the Dragon/Phoenix single answers). `ctx` is
    unused, passed uniformly with the lead query."""
    return _legal_follows(hand, current)


# --- the two non-chooser RNG sites (the monolith's, draw-for-draw) ---


def tichu_call_roll(ctx: Ctx) -> int:
    """One player's Tichu/Grand-Tichu gate: 200 at 4%, else 100 at 8%, else 0.
    The second draw happens only when the first misses (short-circuit), so the
    rng consumption matches the monolith exactly."""
    rng = ctx.rs.rng
    if rng.random() < 0.04:
        return 200
    if rng.random() < 0.08:
        return 100
    return 0


def tichu_dragon_recipient(ctx: Ctx, winner: Player) -> Player:
    """The opponent the Dragon-winner gives the trick to (a random pick — the
    migrated scope plays randomly; a real choice would be a chooser draw)."""
    opponents = [
        p for p in ctx.rs.seating.players
        if ctx.rs.team_of[p] != ctx.rs.team_of[winner]
    ]
    return ctx.rs.rng.choice(opponents)


# --- zone / seating / state reads (pure) ---


def tichu_mahjong_holder(ctx: Ctx) -> Player:
    """Who leads the first trick: the Mahjong holder (post-push hands; the
    full deal guarantees one exists)."""
    hands = ctx.rs.zones.families["hand"]
    return next(
        p for p in ctx.rs.seating.players
        if any(c.rank == "Mahjong" for c in hands[p].cards)
    )


def tichu_players_holding(ctx: Ctx) -> int:
    """How many players still hold cards (the hand ends at <= 1)."""
    hands = ctx.rs.zones.families["hand"]
    return sum(1 for p in ctx.rs.seating.players if hands[p].cards)


def tichu_double_victory(ctx: Ctx) -> bool:
    """Both recorded finishers are teammates (ends the hand early, +200)."""
    first, second = ctx.rs.get("out_first"), ctx.rs.get("out_second")
    return (
        first is not None
        and second is not None
        and ctx.rs.team_of[first] == ctx.rs.team_of[second]
    )


def tichu_partner(ctx: Ctx, p: Player) -> Player:
    """The teammate (partners sit across)."""
    return next(
        q for q in ctx.rs.seating.players
        if q != p and ctx.rs.team_of[q] == ctx.rs.team_of[p]
    )


def tichu_next_holder(ctx: Ctx, p: Player) -> Player:
    """`p` if they still hold cards, else the next holder counterclockwise —
    the monolith's post-trick leader advance. Returns `p` unchanged when
    everyone is out (the hand is over; the value is never read)."""
    hands = ctx.rs.zones.families["hand"]
    players = list(ctx.rs.seating.players)
    if not any(hands[q].cards for q in players):
        return p
    q = p
    while not hands[q].cards:
        q = (q - 1) % len(players)
    return q


def tichu_dragon_won(ctx: Ctx) -> bool:
    """Did the Dragon capture the trick just completed? Reads the standing
    play from the round's terminal state: the Dragon appears in a pile only as
    a played single, and only a bomb can beat it — so the check is exactly the
    monolith's (the final play is one card and it is the Dragon)."""
    st = ctx.rs.last_round_state
    cur = None if st is None else st.get("current")
    return (
        cur is not None and len(cur.cards) == 1 and cur.cards[0].rank == "Dragon"
    )


def tichu_opponent_team(ctx: Ctx, p: Player) -> int:
    """The team `p` does not belong to (two-team game)."""
    return next(t for t in ctx.rs.teams if t != ctx.rs.team_of[p])


def tichu_first_out(ctx: Ctx) -> Player:
    """The first player to shed out, defaulting to player 0 when nobody is
    recorded (the monolith's fallback; unreachable in a completed hand)."""
    first = ctx.rs.get("out_first")
    return 0 if first is None else int(first)


def tichu_card_points(ctx: Ctx, c: Card) -> int:
    """The card-point table (K and 10 score 10, 5 scores 5, Dragon +25,
    Phoenix -25; 100 points per hand)."""
    return _points(c)


def tichu_hand_summary(ctx: Ctx) -> int:
    """Emit the hand's `tichu_hand` trace — the double-victory flag and the
    card points sitting in the two captured piles after routing — and return
    the card points. The playout harness asserts every non-double-victory hand
    distributes exactly 100 (tests/test_playout_tichu.py)."""
    captured = ctx.rs.zones.families["captured"]
    pts = sum(_points(c) for t in ctx.rs.teams for c in captured[t].cards)
    ctx.trace(
        "tichu_hand",
        {"double_victory": tichu_double_victory(ctx), "card_points": pts},
    )
    return pts
