"""Pinochle's runtime support: the meld evaluator.

The ascending auction, the trump declaration, and the twelve strict [[trick]]s
all run in the DSL (docs/games/pinochle.cardlang) — trump declaration as a
one-draw `round offering [declare_trump_suit]`, strict-trick legality as the
`MustFollowSuit`/`MustHeadTrick`/`MustTrumpIfVoid`/`MustOverTrump` [[rule]]
cascade. This module holds only what is not expressible there: `pinochle_meld`
— the pure, RNG-free Counter-based meld tally (runs, marriages, dix, pinochle,
and the four-around sets; doubles score the published double values; the only
intra-class overlap handled is the trump run subsuming its own marriage) — and
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

ROW = reads.row("cardlang/runtime/pinochle.py", "pinochle.cardlang")


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
