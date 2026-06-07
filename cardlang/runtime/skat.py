"""The Skat hand mechanic (three-player, DSkV rules; concrete).

Skat is built as one concrete mechanic, like Schnapsen/Pinochle: the Reizen
call-and-response auction, the declarer's contract choice (Suit / Grand / Null,
hand vs. picking up the skat), ten tricks under the contract's trump structure
(the four jacks are permanent trumps in Suit and Grand; Null has none and a
distinct rank order), and base x multiplier scoring with matadors, hand,
Schneider, Schwarz and the overbid rule. The random chooser bids, declares, and
plays uniformly; only the rules are modelled, not strategy. The cardlang holds
the deal, the score var, hand counting, and termination.

Out of scope (matching skat.md): announced Schneider/Schwarz/Ouvert, Null Ouvert,
Ramsch, four-player rotation, tournament conversions.
"""

from __future__ import annotations

import math
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# Non-jack strength for Suit/Grand (trump-suit cards and led-suit cards).
_SKAT_RANK = {"A": 7, "10": 6, "K": 5, "Q": 4, "9": 3, "8": 2, "7": 1}
# Null game ranking (no trumps).
_NULL_RANK = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
# Jack ordering (by suit): clubs > spades > hearts > diamonds.
_JACK_ORDER = {"clubs": 4, "spades": 3, "hearts": 2, "diamonds": 1}
_CARD_VALUE = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0}
_SUIT_BASE = {"diamonds": 9, "hearts": 10, "spades": 11, "clubs": 12}
# The legal Reizen bid sequence (reachable game values).
_BID_SEQUENCE = (
    18, 20, 22, 23, 24, 27, 30, 33, 35, 36, 40, 44, 45, 46, 48, 50,
    54, 55, 59, 60, 63, 66, 70, 72, 77, 80, 81, 84, 88, 90, 96, 99,
    100, 108, 110, 117, 120, 121, 126, 130, 132, 135, 140, 143, 144,
    150, 153, 156, 160, 162, 165, 168, 170, 176, 180, 187, 192, 198,
    204, 216, 240, 264,
)


def _is_trump(c: Card, game_type: str, trump_suit: str | None) -> bool:
    if game_type == "null":
        return False
    return c.rank == "J" or (game_type == "suit" and c.suit == trump_suit)


def _trump_strength(c: Card) -> int:
    return 100 + _JACK_ORDER[c.suit] if c.rank == "J" else _SKAT_RANK[c.rank]


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
    of_led = [(p, c) for p, c in played if c.suit == led_suit and not _is_trump(c, game_type, trump_suit)]
    return max(of_led, key=lambda pc: _SKAT_RANK[pc[1].rank])[0]


def _follow_class(c: Card, game_type: str, trump_suit: str | None) -> str:
    return "trump" if _is_trump(c, game_type, trump_suit) else c.suit


def _legal_follow(
    hand: list[Card], led: Card, game_type: str, trump_suit: str | None
) -> list[Card]:
    cls = _follow_class(led, game_type, trump_suit)
    same = [c for c in hand if _follow_class(c, game_type, trump_suit) == cls]
    return same or list(hand)


def _trump_order(game_type: str, trump_suit: str | None) -> list[tuple[str, str]]:
    jacks = [("J", "clubs"), ("J", "spades"), ("J", "hearts"), ("J", "diamonds")]
    if game_type == "grand":
        return jacks
    assert trump_suit is not None
    return jacks + [(r, trump_suit) for r in ("A", "10", "K", "Q", "9", "8", "7")]


def _matadors(cards: list[Card], game_type: str, trump_suit: str | None) -> int:
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


def run_skat_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    args = {a.name: a.value for a in stmt.args}
    forehand: Player = evaluate(args["forehand"], ctx)  # type: ignore[arg-type]
    choose = ctx.chooser
    middlehand = rs.seating.offset_by(forehand, "left")
    rearhand = rs.seating.offset_by(middlehand, "left")
    hands = rs.zones.families["hand"]
    captured = rs.zones.families["captured"]
    skat = rs.zones.single("skat")

    # --- Reizen auction ---
    bid = {"value": 0}

    def exchange(speaker: Player, responder: Player) -> Player:
        while True:
            nexts = [v for v in _BID_SEQUENCE if v > bid["value"]]
            if nexts and choose(speaker, ["bid", "pass"], 1)[0] == "bid":
                bid["value"] = nexts[0]
                if choose(responder, ["yes", "pass"], 1)[0] == "pass":
                    return speaker
            else:
                return responder

    w1 = exchange(middlehand, forehand)
    declarer = exchange(rearhand, w1)
    if bid["value"] == 0:
        if choose(forehand, ["play18", "throwin"], 1)[0] == "play18":
            declarer, bid["value"] = forehand, 18
        else:
            return forehand  # all pass — hand thrown in, no score
    final_bid = bid["value"]

    # --- contract declaration ---
    hand_mode = choose(declarer, ["pickup", "hand"], 1)[0] == "hand"
    if not hand_mode:
        hands[declarer].add_all(skat.take_all())
        discards = choose(declarer, list(hands[declarer].cards), 2)
        for c in discards:
            hands[declarer].remove(c)
            skat.add(c)
    game_type = choose(declarer, ["suit", "grand", "null"], 1)[0]
    trump_suit: str | None = None
    if game_type == "suit":
        trump_suit = choose(declarer, ["clubs", "diamonds", "hearts", "spades"], 1)[0]

    matador_cards = list(hands[declarer].cards) + list(skat.cards)  # before play

    # --- ten tricks ---
    leader = forehand
    declarer_tricks = 0
    for _ in range(10):
        trick: list[tuple[Player, Card]] = []
        for q in rs.seating.turn_order_from(leader):
            hand = hands[q].cards
            legal = (
                list(hand)
                if not trick
                else _legal_follow(hand, trick[0][1], game_type, trump_suit)
            )
            card = choose(q, legal, 1)[0]
            hands[q].remove(card)
            trick.append((q, card))
            ctx.trace("play", (q, card))
        led_suit = trick[0][1].suit
        winner = _trick_winner(trick, led_suit, game_type, trump_suit)
        ctx.trace("trick_end", {"game_type": game_type, "trump": trump_suit})
        ctx.trace("trick", (winner, [c for _, c in trick]))
        for _, c in trick:
            captured[winner].add(c)
        if winner == declarer:
            declarer_tricks += 1
        leader = winner

    # --- scoring ---
    score = rs.get("score")
    if game_type == "null":
        declarer_won = declarer_tricks == 0
        game_value = 35 if hand_mode else 23
        if declarer_won and game_value >= final_bid:
            score[declarer] += game_value
        else:
            score[declarer] -= 2 * _effective_loss(game_value, final_bid, game_value)
    else:
        declarer_points = sum(_CARD_VALUE[c.rank] for c in captured[declarer].cards)
        declarer_points += sum(_CARD_VALUE[c.rank] for c in skat.cards)
        base = 24 if game_type == "grand" else _SUIT_BASE[trump_suit]  # type: ignore[index]
        matadors = _matadors(matador_cards, game_type, trump_suit)
        schneider = 1 if (declarer_points >= 90 or declarer_points <= 30) else 0
        schwarz = 1 if (declarer_tricks == 10 or declarer_tricks == 0) else 0
        multiplier = matadors + 1 + (1 if hand_mode else 0) + schneider + schwarz
        game_value = base * multiplier
        if declarer_points >= 61 and game_value >= final_bid:
            score[declarer] += game_value
        else:
            score[declarer] -= 2 * _effective_loss(game_value, final_bid, base)

    ctx.trace(
        "skat_hand",
        {"declarer": declarer, "game_type": game_type, "bid": final_bid},
    )
    return declarer


def _effective_loss(game_value: int, bid: int, base: int) -> int:
    """The loss base: the game value if it covered the bid, else the smallest
    multiple of the base value that meets the bid (the overbid penalty)."""
    if game_value >= bid:
        return game_value
    return base * math.ceil(bid / base)
