"""Skat's game-local runtime primitives.

The hand runs fully on the kernel (skat.cardlang): the Reizen call-and-response
is the auction form of `round` over a role-guarded two-participant ring, the
contract declaration a pair of `offer`s plus a one-draw suit round, the ten
tricks three single-actor filtered movements per trick, and the scoring plain
statements. What stays game-local: the 62-value bid ladder, the per-contract
follow-class legality and trick resolution (the four jacks and the trump suit
are one follow class in Suit and Grand; Null has no trumps and its own rank
order), matador counting, and the overbid arithmetic (a ceiling the expression
language lacks). The trick primitive also emits the play/trick_end/trick trace
events the playout harness recomputes winners from (tests/test_playout_skat.py).

The contract-dependent primitives read the declared contract from phase state
(`is_grand` / `is_null` / `trump_suit`) — the Stud/Cribbage precedent for
game-local primitives over live state.
"""

from __future__ import annotations

import math

from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# Non-jack strength for Suit/Grand (trump-suit cards and led-suit cards).
_SKAT_RANK = {"A": 7, "10": 6, "K": 5, "Q": 4, "9": 3, "8": 2, "7": 1}
# Null game ranking (no trumps).
_NULL_RANK = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
# Jack ordering (by suit): clubs > spades > hearts > diamonds.
_JACK_ORDER = {"clubs": 4, "spades": 3, "hearts": 2, "diamonds": 1}
# The legal Reizen bid sequence (reachable game values).
_BID_SEQUENCE = (
    18, 20, 22, 23, 24, 27, 30, 33, 35, 36, 40, 44, 45, 46, 48, 50,
    54, 55, 59, 60, 63, 66, 70, 72, 77, 80, 81, 84, 88, 90, 96, 99,
    100, 108, 110, 117, 120, 121, 126, 130, 132, 135, 140, 143, 144,
    150, 153, 156, 160, 162, 165, 168, 170, 176, 180, 187, 192, 198,
    204, 216, 240, 264,
)


def _contract(ctx: Ctx) -> tuple[str, str | None]:
    """The declared contract, read from phase state (the declaration move
    effects set it before any consumer runs)."""
    if ctx.rs.get("is_null"):
        return "null", None
    if ctx.rs.get("is_grand"):
        return "grand", None
    return "suit", ctx.rs.get("trump_suit")


def _is_trump(c: Card, game_type: str, trump_suit: str | None) -> bool:
    if game_type == "null":
        return False
    return c.rank == "J" or (game_type == "suit" and c.suit == trump_suit)


def _trump_strength(c: Card) -> int:
    return 100 + _JACK_ORDER[c.suit] if c.rank == "J" else _SKAT_RANK[c.rank]


def _follow_class(c: Card, game_type: str, trump_suit: str | None) -> str:
    return "trump" if _is_trump(c, game_type, trump_suit) else c.suit


def _trick_winner(
    played: list[tuple[Player, Card]],
    led_suit: str,
    game_type: str,
    trump_suit: str | None,
) -> Player:
    if game_type == "null":
        of_led = [(p, c) for p, c in played if c.suit == led_suit]
        return max(of_led, key=lambda pc: _NULL_RANK[pc[1].rank])[0]
    trumps = [(p, c) for p, c in played if _is_trump(c, game_type, trump_suit)]
    if trumps:
        return max(trumps, key=lambda pc: _trump_strength(pc[1]))[0]
    of_led = [
        (p, c)
        for p, c in played
        if c.suit == led_suit and not _is_trump(c, game_type, trump_suit)
    ]
    return max(of_led, key=lambda pc: _SKAT_RANK[pc[1].rank])[0]


def _trump_order(game_type: str, trump_suit: str | None) -> list[tuple[str, str]]:
    jacks = [("J", "clubs"), ("J", "spades"), ("J", "hearts"), ("J", "diamonds")]
    if game_type == "grand":
        return jacks
    assert trump_suit is not None
    return jacks + [(r, trump_suit) for r in ("A", "10", "K", "Q", "9", "8", "7")]


# --- the stdlib call surface -------------------------------------------------


def skat_next_bid(value: int) -> int:
    """The next Reizen ladder value above `value`, or 0 when the ladder is
    exhausted (the auction's `until` reads 0 as "the speaker cannot raise",
    ending the exchange with no draw, exactly like the reference)."""
    nexts = [x for x in _BID_SEQUENCE if x > value]
    return nexts[0] if nexts else 0


def skat_follow_ok(ctx: Ctx, p: Player, c: Card) -> bool:
    """Follow-class legality for the card `c` in `p`'s hand against the led
    card (`trick_pile[0]`): holding a card of the led class obliges playing
    one; void in the class, anything goes. No head/trump obligation."""
    game_type, trump_suit = _contract(ctx)
    led = ctx.rs.zones.single("trick_pile").cards[0]
    cls = _follow_class(led, game_type, trump_suit)
    hand = ctx.rs.zones.instance("hand", p).cards
    if any(_follow_class(x, game_type, trump_suit) == cls for x in hand):
        return _follow_class(c, game_type, trump_suit) == cls
    return True


def skat_trick_winner(ctx: Ctx, leader: Player) -> Player:
    """The completed three-card trick's winner (`trick_pile` holds the cards
    in seat order from the leader): the highest trump if any was played, else
    the highest card of the led suit — under Null, no trumps and the natural
    rank order. Emits the play/trick_end/trick traces the playout harness
    recomputes winners from."""
    game_type, trump_suit = _contract(ctx)
    cards = ctx.rs.zones.single("trick_pile").cards
    assert len(cards) == 3, f"skat trick pile holds {len(cards)} cards, expected 3"
    played = list(zip(ctx.rs.seating.turn_order_from(leader), cards))
    for q, c in played:
        ctx.trace("play", (q, c))
    winner = _trick_winner(played, cards[0].suit, game_type, trump_suit)
    ctx.trace("trick_end", {"game_type": game_type, "trump": trump_suit})
    ctx.trace("trick", (winner, list(cards)))
    return winner


def skat_matadors(ctx: Ctx, p: Player) -> int:
    """The matador count for `p`'s hand plus the skat under the declared
    trump structure: the length of the unbroken with/without run from the
    club Jack down the trump order. Undefined for Null (the game guards)."""
    game_type, trump_suit = _contract(ctx)
    cards = list(ctx.rs.zones.instance("hand", p).cards) + list(
        ctx.rs.zones.single("skat").cards
    )
    order = _trump_order(game_type, trump_suit)
    held = [any(c.rank == r and c.suit == s for c in cards) for (r, s) in order]
    want = held[0]  # "with" if holding the top trump (CJ), else "without"
    n = 0
    for h in held:
        if h == want:
            n += 1
        else:
            break
    return n


def skat_effective_loss(game_value: int, bid: int, base: int) -> int:
    """The loss base: the game value if it covered the bid, else the smallest
    multiple of the base value that meets the bid (the overbid penalty)."""
    if game_value >= bid:
        return game_value
    return base * math.ceil(bid / base)
