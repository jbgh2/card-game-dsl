"""500's game-local runtime primitives.

The hand runs fully on the kernel (five-hundred.cardlang): the ascending
auction is the drop-out ring form of `round` (the Pinochle shape), the kitty
pickup and discard are plain movements, the joker nomination an `offer`, and
the ten tricks single-actor filtered movements (the Skat/Doppelkopf shape).
What stays game-local: the 27-rung bid ladder with the misère insertions, the
per-contract follow/lead legality, and trick resolution — the joker and both
bowers behave in all respects as members of the trump suit (the Skat
jacks-as-a-follow-class precedent, plus an effective-suit remap for the left
bower), and in the no-trump family the joker is suitless (or, once nominated,
the highest card of its suit). The trick primitive also emits the
play/trick_end/trick trace events the playout harness recomputes winners from
(tests/test_playout_five_hundred.py).

The contract-dependent primitives read the declared contract from phase state
(`trump_suit` / `is_misere` / `is_open_misere` / `joker_suit` / `declarer`) —
the Skat/Stud precedent for game-local primitives over live state.

Contract ordinals: every bid is a rung on one strictly-ordered ladder,
encoded as an integer so the standing bid is one public state variable.
Suit/no-trump bids take 10*((level-6)*5 + strain) with strain ♠1 ♣2 ♦3 ♥4
NT5 (so 6♠=10 … 10NT=250); misère sits at 105 (above every seven bid, below
every eight bid) and open misère at 235 (above 10♦, below 10♥). Point values
are a separate table — misère (250) is worth MORE than 8♠ (240) but ranks
BELOW it; the ordinal and the value never share a scale.
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.sidecar import EngineFacts, TraceEvent
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/five_hundred.py", "five-hundred.cardlang")

# In-suit strength, aces high (the joker and the bowers are handled above
# this table; there is no 3 or 2 in the 43-card pack).
_PLAIN_RANK = {
    "A": 11, "K": 10, "Q": 9, "J": 8, "10": 7, "9": 6,
    "8": 5, "7": 4, "6": 3, "5": 2, "4": 1,
}
_SAME_COLOUR = {"spades": "clubs", "clubs": "spades", "hearts": "diamonds", "diamonds": "hearts"}

# Bidding order of the strains within a level: ♠ < ♣ < ♦ < ♥ < no-trump
# (None). The deck-derived Suit domain also contains "joker" (the joker's own
# suit); it is NOT a biddable or nominable strain — `five_hundred_next_bid`
# returns 0 for it and the game file's guards mask it, so the action exists
# in the fixed action space but is never legal.
_STRAIN_ORD: dict[str | None, int] = {"spades": 1, "clubs": 2, "diamonds": 3, "hearts": 4, None: 5}

_MISERE_ORD = 105
_OPEN_MISERE_ORD = 235
_SUIT_BID_ORDS = tuple(10 * n for n in range(1, 26))  # 6♠=10 .. 10NT=250


def _is_suit_bid_ord(rank: int) -> bool:
    return rank in _SUIT_BID_ORDS


def five_hundred_next_bid(standing: int, strain: str | None) -> int:
    """The ordinal of the cheapest bid in `strain` that beats the standing
    bid ordinal, or 0 when none exists (levels stop at ten) — also 0 for the
    joker pseudo-strain, which is never biddable. The auction's guard reads
    0 as "this strain cannot outbid", exactly like skat_next_bid's exhausted
    ladder."""
    so = _STRAIN_ORD.get(strain)
    if so is None:
        return 0  # the deck-derived "joker" suit: never a biddable strain
    nexts = [10 * ((lvl - 6) * 5 + so) for lvl in range(6, 11)]
    higher = [o for o in nexts if o > standing]
    return higher[0] if higher else 0


def five_hundred_bid_value(rank: int) -> int:
    """The score value of a contract ordinal: the Pagat table (6♠=40, +20 per
    strain, +100 per level, 10NT=520), misère 250, open misère 500. Any other
    integer is no contract — the ladder above is the whole domain, so a stray
    value is the description's error, in the runtime's currency."""
    if rank == _MISERE_ORD:
        return 250
    if rank == _OPEN_MISERE_ORD:
        return 500
    if not _is_suit_bid_ord(rank):
        raise OwnerGuardError(
            f"five_hundred_bid_value: {rank} is not a contract ordinal "
            f"(suit bids 10..250 by tens, misère 105, open misère 235)"
        )
    n = rank // 10 - 1
    level, strain = 6 + n // 5, n % 5 + 1
    return 40 + 20 * (strain - 1) + 100 * (level - 6)


def five_hundred_bid_level(rank: int) -> int:
    """The trick target (6..10) of a suit or no-trump contract ordinal.
    Misère ordinals have no trick target (the game scores them on
    `declarer_tricks is 0`, never through this) and anything off the ladder
    is no contract — both are the description's error, loud."""
    if not _is_suit_bid_ord(rank):
        raise OwnerGuardError(
            f"five_hundred_bid_level: {rank} is not a suit/no-trump contract "
            f"ordinal (misère contracts have no trick target)"
        )
    return 6 + (rank // 10 - 1) // 5


def _contract(gr: reads.GameReads) -> tuple[str | None, bool]:
    """(trump_suit, misère?) read from phase state. A misère contract is
    always no-trump; `trump_suit is None` alone means plain no-trumps."""
    trump = gr.state["trump_suit"]
    misere = bool(gr.state["is_misere"]) or bool(
        gr.state["is_open_misere"]
    )
    return trump, misere


def _is_trump(c: Card, trump: str | None) -> bool:
    if trump is None:
        return False
    return (
        c.suit == "joker"
        or c.suit == trump
        or (c.rank == "J" and c.suit == _SAME_COLOUR[trump])
    )


def _trump_strength(c: Card, trump: str) -> int:
    if c.suit == "joker":
        return 1000
    if c.rank == "J" and c.suit == trump:
        return 999  # right bower
    if c.rank == "J" and c.suit == _SAME_COLOUR[trump]:
        return 998  # left bower
    return _PLAIN_RANK[c.rank]


def _follow_class(c: Card, trump: str | None, joker_suit: str | None) -> str:
    """The suit a card follows as: under a trump contract the joker and both
    bowers are members of the trump suit "in all respects"; in the no-trump
    family the joker is its own class until nominated, then a member of the
    nominated suit."""
    if trump is not None:
        return "trump" if _is_trump(c, trump) else c.suit
    if c.suit == "joker":
        return joker_suit if joker_suit is not None else "joker"
    return c.suit


def _pool(gr: reads.GameReads, p: Player) -> list[Card]:
    """The cards `p` plays from: the hand, or — after an open misère
    exposure — the face-up `exposed` zone (exactly one is non-empty during
    play)."""
    return list(gr.families["hand"][p]) + list(gr.families["exposed"][p])


def follow_ok(
    pool: list[Card],
    led: Card,
    c: Card,
    trump: str | None,
    misere: bool,
    joker_suit: str | None,
) -> bool:
    """The pure follow rule: holding a card of the led class obliges playing
    one; void, anything goes (no obligation to trump) — except that in a
    misère contract a void holder of the un-nominated joker MUST play it
    (Pagat: "you must play the joker if you have no cards of the suit
    led")."""
    cls = _follow_class(led, trump, joker_suit)
    if any(_follow_class(x, trump, joker_suit) == cls for x in pool):
        return _follow_class(c, trump, joker_suit) == cls
    if misere and joker_suit is None and any(x.suit == "joker" for x in pool):
        return c.suit == "joker"  # void + un-nominated joker: forced in misère
    return True


def lead_ok(pool: list[Card], c: Card, trump: str | None, joker_suit: str | None) -> bool:
    """The pure lead rule: anything may be led, except that in the no-trump
    family an un-nominated joker may not be led before the holder's last
    card (the modelled form of Pagat's lead-nomination rule — see
    five-hundred.md, "Chosen ruleset"). Under a trump contract the joker is
    simply the top trump and leads freely; a nominated joker leads as the
    highest card of its suit."""
    if trump is not None or c.suit != "joker":
        return True
    return joker_suit is not None or len(pool) == 1


def trick_winner(
    played: list[tuple[Player, Card]],
    trump: str | None,
    joker_suit: str | None,
) -> Player:
    """The pure trick rule: the highest trump if any was played (joker >
    right bower > left bower > A..), else the highest card of the led class;
    in the no-trump family an un-nominated joker wins any trick it is played
    to, and a nominated joker is simply the highest card of its suit."""
    cards = [c for _, c in played]
    led_cls = _follow_class(cards[0], trump, joker_suit)
    if trump is not None:
        trumps = [(q, c) for q, c in played if _is_trump(c, trump)]
        if trumps:
            return max(trumps, key=lambda pc: _trump_strength(pc[1], trump))[0]
        of_led = [(q, c) for q, c in played if c.suit == led_cls]
        return max(of_led, key=lambda pc: _PLAIN_RANK[pc[1].rank])[0]
    joker = [(q, c) for q, c in played if c.suit == "joker"]
    if joker and joker_suit is None:
        return joker[0][0]  # the un-nominated joker: highest in the pack
    of_led = [(q, c) for q, c in played if _follow_class(c, trump, joker_suit) == led_cls]
    return max(
        of_led,
        key=lambda pc: 100 if pc[1].suit == "joker" else _PLAIN_RANK[pc[1].rank],
    )[0]


def five_hundred_follow_ok(
    facts: EngineFacts, gr: reads.GameReads, p: Player, c: Card
) -> bool:
    """`follow_ok` over live state: the led card is `trick_pile[0]`, the
    holder's pool his hand (or his exposed lay-down in an open misère)."""
    trump, misere = _contract(gr)
    joker_suit = gr.state["joker_suit"]
    led = gr.singles["trick_pile"][0]
    return follow_ok(_pool(gr, p), led, c, trump, misere, joker_suit)


def five_hundred_lead_ok(
    facts: EngineFacts, gr: reads.GameReads, p: Player, c: Card
) -> bool:
    """`lead_ok` over live state."""
    trump, _ = _contract(gr)
    joker_suit = gr.state["joker_suit"]
    return lead_ok(_pool(gr, p), c, trump, joker_suit)


def five_hundred_trick_winner(
    facts: EngineFacts, gr: reads.GameReads, leader: Player
) -> tuple[Player, tuple[TraceEvent, ...]]:
    """The completed trick's winner (`trick_pile` holds the cards in seat
    order from the leader — three cards in a misère contract, where the
    declarer's partner sits out, else four): the highest trump if any was
    played (joker > right bower > left bower > A..), else the highest card
    of the led class; in the no-trump family an un-nominated joker wins any
    trick it is played to, and a nominated joker is simply the highest card
    of its suit. Emits the play/trick_end/trick traces the playout harness
    recomputes winners from."""
    trump, misere = _contract(gr)
    joker_suit = gr.state["joker_suit"]
    cards = gr.singles["trick_pile"]
    order = facts.seating.turn_order_from(leader)
    if misere:
        declarer = gr.state["declarer"]
        dead = facts.seating.offset_by(declarer, "across")
        order = [q for q in order if q != dead]
    if len(cards) != len(order):
        # The pile's live size is the hosting game's runtime data, so a wrong
        # call site is the description's error, in the runtime's currency.
        raise OwnerGuardError(
            f"five_hundred_trick_winner: trick pile holds {len(cards)} cards, "
            f"expected a completed {len(order)}-card trick"
        )
    played = list(zip(order, cards))
    events: list[TraceEvent] = [("play", (q, c)) for q, c in played]
    winner = trick_winner(played, trump, joker_suit)
    events.append(
        ("trick_end", {"trump": trump, "misere": misere, "joker_suit": joker_suit})
    )
    events.append(("trick", (winner, list(cards))))
    return winner, tuple(events)
