"""Skat's game-local runtime [[primitive]]s.

The hand runs fully on the kernel (skat.cardlang): the Reizen call-and-response
is the auction [[form]] of `round` over a role-guarded two-participant ring, the
contract declaration a pair of `offer`s plus a one-draw suit round, the ten
tricks three single-actor filtered [[transfer]]s per trick, and the scoring plain
statements. What stays game-local: the 62-value bid ladder, the per-contract
follow-class legality and trick resolution (the four jacks and the trump suit
are one follow class in Suit and Grand; Null has no trumps and its own rank
order), matador counting, and the overbid arithmetic (a ceiling the expression
language lacks). The trick primitive also emits the play/trick_end/trick
[[trace-event]]s the playout harness recomputes winners from
(tests/test_playout_skat.py).

The contract-dependent primitives read the declared contract from phase state
(`is_grand` / `is_null` / `trump_suit`) — the Stud/Cribbage precedent for
game-local primitives over live state.
"""

from __future__ import annotations

import math

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.narrowing import EngineFacts, TraceEvent
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/skat.py", "skat.cardlang")

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


def _contract(gr: reads.GameReads) -> tuple[str, str | None]:
    """The declared contract, read from phase state (the declaration move
    effects set it before any consumer runs)."""
    if gr.state["is_null"]:
        return "null", None
    if gr.state["is_grand"]:
        return "grand", None
    return "suit", gr.state["trump_suit"]


def _is_trump(c: Card, game_type: str, trump_suit: str | None) -> bool:
    if game_type == "null":
        return False
    # Not a role: `game_type` is a Skat contract kind ("suit"/"grand"/"null"),
    # unrelated to the domain table.
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
    if trump_suit is None:
        # The contract is live game state (Null names no trump suit, and the
        # docstrings of the consumers say the game guards for it), so being
        # called without one is the description's error, in the runtime's
        # channel.
        raise OwnerGuardError(
            f"skat trump order consulted for a {game_type!r} contract with no "
            f"trump suit declared"
        )
    return jacks + [(r, trump_suit) for r in ("A", "10", "K", "Q", "9", "8", "7")]


# --- the stdlib call surface -------------------------------------------------


def skat_next_bid(value: int) -> int:
    """The next Reizen ladder value above `value`, or 0 when the ladder is
    exhausted (the auction's `until` reads 0 as "the speaker cannot raise",
    ending the exchange with no draw, exactly like the reference)."""
    nexts = [x for x in _BID_SEQUENCE if x > value]
    return nexts[0] if nexts else 0


def skat_follow_ok(
    facts: EngineFacts, gr: reads.GameReads, p: Player, c: Card
) -> bool:
    """Follow-class legality for the card `c` in `p`'s hand against the led
    card (`trick_pile[0]`): holding a card of the led class obliges playing
    one; void in the class, anything goes. No head/trump obligation."""
    game_type, trump_suit = _contract(gr)
    led = gr.singles["trick_pile"][0]
    cls = _follow_class(led, game_type, trump_suit)
    hand = gr.families["hand"][p]
    if any(_follow_class(x, game_type, trump_suit) == cls for x in hand):
        return _follow_class(c, game_type, trump_suit) == cls
    return True


def skat_trick_winner(
    facts: EngineFacts, gr: reads.GameReads, leader: Player
) -> tuple[Player, tuple[TraceEvent, ...]]:
    """The completed three-card trick's winner (`trick_pile` holds the cards
    in seat order from the leader): the highest trump if any was played, else
    the highest card of the led suit — under Null, no trumps and the natural
    rank order. Emits the play/trick_end/trick traces the playout harness
    recomputes winners from."""
    game_type, trump_suit = _contract(gr)
    cards = gr.singles["trick_pile"]
    if len(cards) != 3:
        # The pile's live size is the hosting game's runtime data, so a wrong
        # call site is the description's error, so this raise is its Owner Guard.
        raise OwnerGuardError(
            f"skat_trick_winner: trick pile holds {len(cards)} cards, expected "
            f"a completed 3-card trick"
        )
    played = list(zip(facts.seating.turn_order_from(leader), cards))
    events: list[TraceEvent] = [("play", (q, c)) for q, c in played]
    winner = _trick_winner(played, cards[0].suit, game_type, trump_suit)
    events.append(("trick_end", {"game_type": game_type, "trump": trump_suit}))
    events.append(("trick", (winner, list(cards))))
    return winner, tuple(events)


def skat_matadors(facts: EngineFacts, gr: reads.GameReads, p: Player) -> int:
    """The matador count for `p`'s hand plus the skat under the declared
    trump structure: the length of the unbroken with/without run from the
    club Jack down the trump order. Undefined for Null (the game guards)."""
    game_type, trump_suit = _contract(gr)
    cards = list(gr.families["hand"][p]) + list(gr.singles["skat"])
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
