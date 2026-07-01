"""The Big Two hand mechanic (four-player climbing/shedding game; concrete).

The corpus's second climbing game (after Tichu) and the partner instance that —
together with Tichu — shapes the kernel `climb` construct. Built, like Tichu, as
one concrete mechanic dispatched by `instantiate BigTwoHand`: the climbing trick
(lead a combination, then beat it with a higher one of the *same size* or pass;
the trick ends when action returns to the last player who played), the four
combination sizes (single / pair / triple / five-card), the five-card hierarchy
(straight < flush < full house < quads < straight flush), and the shedding finish
(the hand ends the instant a player empties their hand; the others score penalty
points for the cards they still hold). Lowest cumulative penalty wins the match.

The top half of this module is the **combination engine** — RNG-free, ported into
stdlib-query shape — split into two parts only Big Two has but Tichu does not:
suit *always* breaks ties (a single 52-card deck, so 7♠ > 7♥), and the five-card
group includes flushes and quads-plus-kicker. Two rank orders coexist: 2 is the
highest rank for singles/pairs/triples/quads/full-houses (and a flush's top card),
while straights and straight flushes run in *natural* order (A high in 10-J-Q-K-A,
low in the A-2-3-4-5 wheel; no wrap-around). This is the part the `climb` migration
(docs/kernel-migration.md, Workstream 3) will call as queries, kept game-local
beside Tichu's `combinations.py` until a third instance justifies merging them.

Scope reductions (random play; see docs/games/big-two.md): pairs/triples are
offered as the single strongest representative per rank (highest suits), and each
five-card type as its strongest representative (the top-5 of a suit for a flush,
the highest top-card for a straight); these never change which combinations a hand
can *legally beat*. Match-doubling surcharges (for 2s or a 13-card blitz) are
omitted — the basic 1/2/3-per-card penalty only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import Chooser, Ctx, Zone
from cardlang.runtime.values import Card, Player

# Big Two rank order for singles / pairs / triples / quads / full houses and a
# flush's top card: the 2 is the highest rank, the 3 the lowest.
_RANK = {"3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
         "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15}
# Natural order for straights / straight flushes: the ace is high in 10-J-Q-K-A
# and low in the A-2-3-4-5 wheel; the 2 is an ordinary low card here, never high.
_NAT = {"3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
        "J": 11, "Q": 12, "K": 13, "A": 14, "2": 2}
# Suit order, high to low: spades > hearts > clubs > diamonds (breaks every tie).
_SUIT = {"diamonds": 0, "clubs": 1, "hearts": 2, "spades": 3}

# Five-card type ranks: a higher type beats every lower one regardless of cards.
_STRAIGHT, _FLUSH, _FULLHOUSE, _QUADS, _STRAIGHTFLUSH = 0, 1, 2, 3, 4

# The ten straight rank-windows, each ordered low-to-high so the last element is
# the top card. The wheel (A-2-3-4-5) is lowest; 10-J-Q-K-A is highest.
_STRAIGHTS: tuple[tuple[str, ...], ...] = (
    ("A", "2", "3", "4", "5"),
    ("2", "3", "4", "5", "6"),
    ("3", "4", "5", "6", "7"),
    ("4", "5", "6", "7", "8"),
    ("5", "6", "7", "8", "9"),
    ("6", "7", "8", "9", "10"),
    ("7", "8", "9", "10", "J"),
    ("8", "9", "10", "J", "Q"),
    ("9", "10", "J", "Q", "K"),
    ("10", "J", "Q", "K", "A"),
)


@dataclass(frozen=True)
class Play:
    """A playable combination. `key` is a tuple comparing plays *of the same
    size*; for five-card plays its first element is the type rank, so a stronger
    type sorts above a weaker one before the within-type strength is consulted."""

    kind: str            # single|pair|triple|straight|flush|fullhouse|quads|straightflush
    size: int            # 1 | 2 | 3 | 5
    key: tuple[Any, ...]
    cards: tuple[Card, ...]


def _by_rank(hand: list[Card]) -> dict[str, list[Card]]:
    """Group a hand by rank, each rank's cards sorted highest suit first."""
    groups: dict[str, list[Card]] = {}
    for c in hand:
        groups.setdefault(c.rank, []).append(c)
    for cs in groups.values():
        cs.sort(key=lambda c: _SUIT[c.suit], reverse=True)
    return groups


def _is_straight_ranks(ranks: frozenset[str]) -> bool:
    return any(ranks == frozenset(seq) for seq in _STRAIGHTS)


def _five_card_combos(hand: list[Card], by_rank: dict[str, list[Card]]) -> list[Play]:
    out: list[Play] = []
    suit_cards: dict[str, list[Card]] = {}
    for c in hand:
        suit_cards.setdefault(c.suit, []).append(c)

    # Straights and straight flushes, window by window.
    for seq in _STRAIGHTS:
        if not all(r in by_rank for r in seq):
            continue
        top_nat = _NAT[seq[-1]]
        # Straight flushes: any suit that covers all five ranks of the window.
        for suit in ("spades", "hearts", "clubs", "diamonds"):
            if all(any(c.suit == suit for c in by_rank[r]) for r in seq):
                cards = tuple(next(c for c in by_rank[r] if c.suit == suit) for r in seq)
                out.append(Play("straightflush", 5, (_STRAIGHTFLUSH, top_nat, _SUIT[suit]), cards))
        # A plain (mixed-suit) straight: top card the highest suit available at
        # the top rank, the rest any card, forced off-suit somewhere so it is not
        # secretly a flush (if it can only be monochrome it is a straight flush,
        # already emitted above).
        top_card = by_rank[seq[-1]][0]
        chosen = [top_card]
        mixed = False
        for r in seq[:-1]:
            alt = next((c for c in by_rank[r] if c.suit != top_card.suit), None)
            if alt is not None:
                chosen.append(alt)
                mixed = True
            else:
                chosen.append(by_rank[r][0])
        if mixed:
            out.append(Play("straight", 5, (_STRAIGHT, top_nat, _SUIT[top_card.suit]), tuple(chosen)))

    # Flushes: the five highest cards of any suit with five or more (unless those
    # five are consecutive — that is a straight flush, already emitted).
    for suit, cs in suit_cards.items():
        if len(cs) >= 5:
            top5 = sorted(cs, key=lambda c: _RANK[c.rank], reverse=True)[:5]
            if not _is_straight_ranks(frozenset(c.rank for c in top5)):
                out.append(Play("flush", 5, (_FLUSH, _SUIT[suit], _RANK[top5[0].rank]), tuple(top5)))

    # Full houses: a triple rank plus any different pair rank (triple rank ranks it).
    triple_ranks = [r for r, cs in by_rank.items() if len(cs) >= 3]
    pair_ranks = [r for r, cs in by_rank.items() if len(cs) >= 2]
    for tr in triple_ranks:
        pr = next((p for p in pair_ranks if p != tr), None)
        if pr is not None:
            out.append(Play("fullhouse", 5, (_FULLHOUSE, _RANK[tr]),
                            tuple(by_rank[tr][:3] + by_rank[pr][:2])))

    # Quads: four of a rank plus the lowest spare card as the mandatory kicker.
    for r, cs in by_rank.items():
        if len(cs) == 4:
            others = [c for c in hand if c.rank != r]
            if others:
                kicker = min(others, key=lambda c: (_RANK[c.rank], _SUIT[c.suit]))
                out.append(Play("quads", 5, (_QUADS, _RANK[r]), tuple(cs + [kicker])))
    return out


def _combos(hand: list[Card]) -> list[Play]:
    """Every combination a hand can play, as the strongest representative of each
    rank/type (see the module scope note). Sizes 1, 2, 3, and 5 — Big Two has no
    four-card play, and quads are a five-card group (four plus a kicker)."""
    by_rank = _by_rank(hand)
    out: list[Play] = [
        Play("single", 1, (_RANK[c.rank], _SUIT[c.suit]), (c,)) for c in hand
    ]
    for r, cs in by_rank.items():
        if len(cs) >= 2:
            out.append(Play("pair", 2, (_RANK[r], _SUIT[cs[0].suit]), tuple(cs[:2])))
        if len(cs) >= 3:
            out.append(Play("triple", 3, (_RANK[r],), tuple(cs[:3])))
    out.extend(_five_card_combos(hand, by_rank))
    return out


def _legal_follows(hand: list[Card], led: Play) -> list[Play]:
    """Plays that legally beat `led`: the same number of cards and a higher key.
    Big Two has no cross-size beating and no bombs — a single follows a single, a
    five-card group a five-card group (where a stronger type already sorts above a
    weaker one inside the key)."""
    return [p for p in _combos(hand) if p.size == led.size and p.key > led.key]


def _penalty(cards_left: int) -> int:
    """Penalty points for the cards a non-winner still holds: one per card up to
    nine, two per card for ten–twelve, three per card for a full thirteen."""
    if cards_left <= 9:
        return cards_left
    if cards_left <= 12:
        return 2 * cards_left
    return 3 * cards_left


# ---------------------------------------------------------------------------
# The hand mechanic
# ---------------------------------------------------------------------------


def _play_trick(
    leader: Player,
    hands: dict[Player, Zone],
    discard: Zone,
    advance: Callable[[Player], Player],
    choose: Chooser,
    out: list[Player],
    must_include: Card | None,
) -> Player:
    """Play one climbing trick: the leader leads a combination, then each player
    in turn beats the standing play or passes (a pass does *not* drop you for the
    rest of the trick). The trick ends when action returns to the last player who
    played — everyone else has passed — and that player leads the next trick.
    Returns the next leader, or the player who just emptied their hand (which ends
    the whole hand: the caller sees `out` filled)."""
    current: Play | None = None
    last = leader
    turn = leader
    guard = 0
    while True:
        guard += 1
        if guard > 1000:
            raise RuntimeError("big two trick exceeded 1000 plays without resolving")
        if current is not None and turn == last:
            return last  # all others passed: `last` wins the trick and leads next
        if current is None:  # the leader must lead
            leads = _combos(hands[turn].cards)
            if must_include is not None:
                leads = [p for p in leads if must_include in p.cards]
            play = choose(turn, leads, 1)[0]
        else:
            choice = choose(turn, [*_legal_follows(hands[turn].cards, current), "pass"], 1)[0]
            if choice == "pass":
                turn = advance(turn)
                continue
            play = choice
        for c in play.cards:
            hands[turn].remove(c)
        discard.add_all(play.cards)
        current, last = play, turn
        if not hands[turn].cards:  # the player went out — the hand ends now
            out.append(turn)
            return turn
        turn = advance(turn)


def run_bigtwo_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    choose = ctx.chooser
    players = list(rs.seating.players)
    npl = len(players)
    hands = rs.zones.families["hand"]
    discard = rs.zones.single("discard")
    score = rs.get("score")
    step = 1 if rs.seating.clockwise else -1

    def advance(p: Player) -> Player:
        return (p + step) % npl

    # The 3♦ holder leads the first hand of the match and must include it in the
    # opening combination; thereafter the previous hand's winner leads (no 3♦
    # rule). `winner_seat` is game state — `none` until the first hand is scored.
    prev_winner = rs.get("winner_seat")
    if prev_winner is None:
        three = Card("3", "diamonds")
        leader = next(p for p in players if three in hands[p].cards)
        must_include: Card | None = three
    else:
        leader = prev_winner
        must_include = None

    out: list[Player] = []
    guard = 0
    while not out:
        guard += 1
        if guard > 1000:
            raise RuntimeError("big two hand exceeded 1000 tricks without resolving")
        leader = _play_trick(leader, hands, discard, advance, choose, out, must_include)
        must_include = None  # only the opening lead of the first hand is constrained

    first_out = out[0]
    for p in players:
        if p != first_out:
            score[p] += _penalty(len(hands[p].cards))
    rs.set("winner_seat", first_out)
    ctx.trace(
        "bigtwo_hand",
        {"winner": first_out, "cards_left": {p: len(hands[p].cards) for p in players}},
    )
    return first_out
