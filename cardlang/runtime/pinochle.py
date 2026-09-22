"""Pinochle's runtime support: the meld evaluator.

The ascending auction, the trump declaration, and the twelve strict [[trick]]s
all run in the DSL (docs/games/pinochle.cardlang) — trump declaration as a
one-draw `round offering [declare_trump_suit]`, strict-trick legality as the
`MustFollowSuit`/`MustHeadTrick`/`MustTrumpIfVoid`/`MustOverTrump` [[rule]]
cascade. This module holds only what is not expressible there: `pinochle_meld`
— the pure, RNG-free Counter-based meld tally (runs, marriages, dix, pinochle,
and the four-around sets; doubles score the published double values; a trump run
absorbs its own K-Q, and a spare trump king or queen beside it is priced as a
card, which is the rules source's main account rather than its Variations
table) — and
`pinochle_meld_value`, the declared-reads native-call wrapper the DSL's `for each
player p: meld_score[team_of(p)] += pinochle_meld_value(p)` calls. Melding is
forced (a rational player melds everything), so it is a pure computation, not
a choice.
"""

from __future__ import annotations

from collections import Counter

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import SUITS, Card, Player

def pinochle_meld(cards: list[Card], trump: str) -> int:
    """Standard single-pack Pinochle meld value of a hand given the trump suit.
    Doubles (two copies) score the published double values. A trump run absorbs
    its own K-Q, and a spare trump king or queen beside it scores 40 as a card
    (the rules source's main account: 190 for a run with either, 230 with
    both)."""
    cnt = Counter((c.rank, c.suit) for c in cards)
    doubles = {0: 0, 1: 1, 2: 2}  # copies present, capped at 2 (pack has two)
    score = 0

    run_cards = [("A", trump), ("10", trump), ("K", trump), ("Q", trump), ("J", trump)]
    n_run = min(cnt[m] for m in run_cards)
    score += {0: 0, 1: 150, 2: 1500}[doubles[min(n_run, 2)]]
    score += 10 * cnt[("9", trump)]  # dix

    for s in SUITS:
        marr = min(cnt[("K", s)], cnt[("Q", s)])
        if s != trump:
            score += 20 * marr
        elif n_run:
            # With a run on the table the main account prices the SPARE CARD,
            # not a second marriage: a run with an extra king is 190, with an
            # extra queen 190, and with both 230. Counting spare marriages
            # instead (`40 * max(0, marr - n_run)`) is the Variations table,
            # which scores the first two at 150.
            score += 40 * (max(0, cnt[("K", s)] - n_run) + max(0, cnt[("Q", s)] - n_run))
        else:
            score += 40 * marr  # royal marriages, with no run to absorb them

    n_pin = min(cnt[("Q", "spades")], cnt[("J", "diamonds")])
    score += {0: 0, 1: 40, 2: 300}[min(n_pin, 2)]

    for rank, single, double in (("A", 100, 1000), ("K", 80, 800), ("Q", 60, 600), ("J", 40, 400)):
        n = min(cnt[(rank, s)] for s in SUITS)
        score += {0: 0, 1: single, 2: double}[min(n, 2)]
    return score


# The pack's rank order, low to high, so the cards a seat lays down come out in
# one order whatever a hand's own order is. A reveal sequence that depended on
# the deal would put the same meld into different observation logs.
_SHOW_ORDER = ("9", "J", "Q", "K", "10", "A")


def pinochle_meld_cards(cards: list[Card], trump: str) -> list[Card]:
    """The cards a seat lays face up to show its meld.

    Pagat: "Each player places face-up on the table only those cards necessary
    to show the value of their meld." A card may belong to several pieces of
    DIFFERENT types and is laid down once, so the count shown of each card is
    the largest any one piece needs — not the sum, which would show a queen of
    spades twice for a pinochle and a queens-around.

    Keyed to `pinochle_meld` above piece by piece: a holding that scores here
    shows its cards, and a holding that scores nothing shows none, which is
    what `test_pinochle_meld.py` holds the two to.
    """
    cnt = Counter((c.rank, c.suit) for c in cards)
    need: Counter[tuple[str, str]] = Counter()

    def want(rank: str, suit: str, copies: int) -> None:
        if copies > 0:
            need[(rank, suit)] = max(need[(rank, suit)], min(copies, cnt[(rank, suit)]))

    run_cards = [("A", trump), ("10", trump), ("K", trump), ("Q", trump), ("J", trump)]
    n_run = min(cnt[m] for m in run_cards)
    for rank, suit in run_cards:
        want(rank, suit, n_run)
    want("9", trump, cnt[("9", trump)])  # every dix scores

    for suit in SUITS:
        marr = min(cnt[("K", suit)], cnt[("Q", suit)])
        if suit != trump:
            want("K", suit, marr)
            want("Q", suit, marr)
        elif n_run:
            # The run's own K-Q plus any spare that the main account prices.
            want("K", suit, cnt[("K", suit)])
            want("Q", suit, cnt[("Q", suit)])
        else:
            want("K", suit, marr)
            want("Q", suit, marr)

    n_pin = min(cnt[("Q", "spades")], cnt[("J", "diamonds")])
    want("Q", "spades", n_pin)
    want("J", "diamonds", n_pin)

    for rank in ("A", "K", "Q", "J"):
        around = min(cnt[(rank, suit)] for suit in SUITS)
        for suit in SUITS:
            want(rank, suit, around)

    return [
        Card(rank, suit)
        for suit in SUITS
        for rank in _SHOW_ORDER
        for _ in range(need[(rank, suit)])
    ]


def pinochle_meld_value(
    facts: EngineFacts, gr: reads.GameReads, player: Player
) -> int:
    """The meld points `player`'s hand is worth under this hand's declared
    trump — a pure read of the live `hand` zone and the `trump_suit` state (no
    RNG, no mutation); the DSL statement `meld_score[team_of(p)] +=
    pinochle_meld_value(p)` is what actually credits it to the team."""
    hand = gr.families["hand"][player]
    trump = gr.state["trump_suit"]
    if not isinstance(trump, str):
        # Whether trump has been declared yet is live game state, so scoring
        # meld before it is the description's error, so this raise is its Owner Guard.
        raise OwnerGuardError(
            "pinochle_meld_value: meld is scored only after `trump_suit` is "
            "declared"
        )
    return pinochle_meld(list(hand), trump)


def _shown(gr: reads.GameReads, player: Player) -> list[Card]:
    """The cards `player` lays face up, under this hand's declared trump.

    Shares `pinochle_meld_value`'s Owner Guard rather than restating it: reading
    a meld before trump is named is the description's error either way, and one
    raise keeps the two answers from disagreeing about when they may be asked.
    """
    trump = gr.state["trump_suit"]
    if not isinstance(trump, str):
        raise OwnerGuardError(
            "pinochle meld: the cards a seat shows are known only after "
            "`trump_suit` is declared"
        )
    return pinochle_meld_cards(list(gr.families["hand"][player]), trump)


def pinochle_meld_size(
    facts: EngineFacts, gr: reads.GameReads, player: Player
) -> int:
    """How many cards `player` lays face up. The showing walks k = 0..size-1."""
    return len(_shown(gr, player))


def pinochle_meld_slot(
    facts: EngineFacts, gr: reads.GameReads, player: Player, k: int, c: Card
) -> bool:
    """Is `c` the `k`-th card `player` lays face up? Belote's declaration shows
    its combination the same way."""
    shown = _shown(gr, player)
    return 0 <= k < len(shown) and shown[k] == c
