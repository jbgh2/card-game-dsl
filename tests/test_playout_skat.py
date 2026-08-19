"""Random-playout harness for Skat.

Skat has three trump structures: Suit (four jacks + the trump suit), Grand (four
jacks only), and Null (no trumps, a distinct A-K-Q-J-10-9-8-7 order). The
falsifiable check recomputes every trick's winner, and every follow decision,
from the cards played and the contract the declarer announced -- so a wrong
jack-ordering, trump structure, or rank order turns it red. Plus deck integrity
(32 cards / 120 card points) and a fixed 36-hand game with the highest score
winning.

Observation-derived, not trace-derived (the schnapsen and Doppelkopf
precedent). Every fact it consumes rides observer 0's stream: plays are the
`move` events into `trick_pile`, winners are the `trick_pile -> captured[w]`
drains, and the CONTRACT is the declarer's `announce` events -- a public
decision every seat hears, which is what makes the contract a fact of the
table rather than of the engine. The `play` / `trick` / `trick_end` TRACE
events this used to read were emitted by the game-local winner Primitive,
which the Trick Order retired; deriving from observations instead is strictly
stronger, because a divergence between what the engine recorded and what
observers saw would now BREAK this oracle rather than being invisible to it.

Non-vacuity is asserted, not hoped for. When the winner Primitive stopped
emitting its traces, the trace-fed lists went empty and every recomputation
loop in this module iterated zero times -- a green run proving nothing (the
empty-input-set class, decisions.md "Closed-domain completeness"). So the
trick count is now pinned against the announcements (ten tricks per hand that
was not thrown in), and `test_the_three_contracts_are_all_reached` pins that
all three trump structures actually occur across the sweep: without it, the
Null branch of the recomputation -- the one order that is not the game's
`ranking:` -- could go unexercised and unnoticed.

The recomputation stays INDEPENDENT of the construct under test: it never
calls `follows_lead`, `highest_by_trick_order` or `card_strength`, and
re-implements the three orders in Python below.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Player

SKAT = Path(__file__).parent.parent / "docs" / "games" / "skat.cardlang"

HANDS = 36
TRICKS_PER_HAND = 10

_SKAT_RANK = {"A": 7, "10": 6, "K": 5, "Q": 4, "9": 3, "8": 2, "7": 1}
_NULL_RANK = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
_JACK = {"clubs": 4, "spades": 3, "hearts": 2, "diamonds": 1}

# A rendered card back to a Card. The observation stream carries the printed
# text -- what a seat at the table reads off the pile -- never an engine value.
_SUITS = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}


def _parse(card_str: str) -> Card:
    return Card(card_str[:-1], _SUITS[card_str[-1]])


def _skat() -> Any:
    return check_source(SKAT)


def _is_trump(c: Card, gt: str, trump: str | None) -> bool:
    return gt != "null" and (c.rank == "J" or (gt == "suit" and c.suit == trump))


def _follow_class(c: Card, gt: str, trump: str | None) -> str:
    """The class a card follows as: trumps are ONE class whatever suit they are
    printed, every other card its own suit."""
    return "trump" if _is_trump(c, gt, trump) else c.suit


def _winner(group: list[tuple[Player, Card]], gt: str, trump: str | None) -> Player:
    led = group[0][1].suit
    if gt == "null":
        of_led = [(p, c) for p, c in group if c.suit == led]
        return max(of_led, key=lambda pc: _NULL_RANK[pc[1].rank])[0]
    trumps = [(p, c) for p, c in group if _is_trump(c, gt, trump)]
    if trumps:
        return max(
            trumps,
            key=lambda pc: 100 + _JACK[pc[1].suit] if pc[1].rank == "J" else _SKAT_RANK[pc[1].rank],
        )[0]
    of_led = [(p, c) for p, c in group if c.suit == led and not _is_trump(c, gt, trump)]
    return max(of_led, key=lambda pc: _SKAT_RANK[pc[1].rank])[0]


# The declaration vocabulary, as it is announced. `declare_hand` / `pick_up_skat`
# is the first offer of the hand's declaration and so marks a fresh contract;
# `throw_in` ends the hand before any trick.
_HAND_OPENERS = frozenset({"declare_hand", "pick_up_skat"})


class _Table:
    """What a seat at the table writes down: the plays, the trick winners, the
    contract each trick was played under, and how many hands were thrown in."""

    def __init__(self) -> None:
        self.plays: list[tuple[Player, Card]] = []
        self.tricks: list[tuple[Player, list[Card]]] = []
        self.contracts: list[tuple[str, str | None]] = []
        self.hand_starts: list[int] = []
        self.thrown = 0
        self._pending: list[tuple[Player, Card]] = []
        self._gt = "suit"
        self._trump: str | None = None

    def observe(self, player: Player, event: tuple[Any, ...]) -> None:
        # Observer 0's stream only: the trick pile and the capture piles project
        # identity to every observer and an announcement is heard by every seat,
        # so seat 0 sees exactly what every other seat does.
        if player != 0:
            return
        if event[0] == "announce":
            self._announced(str(event[2]))
        elif event[0] == "move":
            self._moved(event)

    def _announced(self, said: str) -> None:
        if said in _HAND_OPENERS:
            self.hand_starts.append(len(self.tricks))
            self._gt, self._trump = "suit", None
        elif said == "throw_in":
            self.thrown += 1
        elif said == "declare_grand":
            self._gt, self._trump = "grand", None
        elif said == "declare_null":
            self._gt, self._trump = "null", None
        elif said.startswith("declare_suit("):
            self._gt = "suit"
            self._trump = said[len("declare_suit(") : -1]

    def _moved(self, event: tuple[Any, ...]) -> None:
        _, src, _src_view, dst, dst_view = event
        if dst == "trick_pile" and isinstance(src, str) and src.startswith("hand["):
            (card_str,) = dst_view  # one card per play
            play = (Player(int(src[len("hand[") : -1])), _parse(card_str))
            self.plays.append(play)
            self._pending.append(play)
        elif src == "trick_pile" and isinstance(dst, str) and dst.startswith("captured["):
            self.tricks.append(
                (Player(int(dst[len("captured[") : -1])), [c for _, c in self._pending])
            )
            self.contracts.append((self._gt, self._trump))
            self._pending.clear()


def _play(game: Any, seed: int) -> tuple[_Table, dict[str, int], int, Any]:
    table = _Table()
    census: dict[str, int] = {}
    hand_ends = 0

    def tracer(event: str, data: Any) -> None:
        nonlocal hand_ends
        if event == "hand_end":
            hand_ends += 1
        elif event == "game_end":
            census.update(data)

    rng = random.Random(seed)
    result = play_game(game, rng, tracer, random_chooser(rng), observer=table.observe)
    return table, census, hand_ends, result


def _check_seed(game: Any, seed: int) -> Counter[str]:
    table, census, hand_ends, result = _play(game, seed)

    assert hand_ends == HANDS  # fixed 36-hand game
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])

    # Deck integrity.
    assert census["total"] == 32, f"seed {seed}: {census}"
    assert census["total_value"] == 120, f"seed {seed}: {census}"

    # Non-vacuity, pinned against the announcements rather than against itself:
    # every hand not thrown in plays exactly ten tricks, so an oracle whose
    # observation stream went empty fails here instead of iterating nothing.
    # This floor comes FIRST because the three counts below are each `0 == 0`
    # when every hand is thrown in -- the non-vacuity guard passing vacuously,
    # the same class it exists to close. It is a floor, not a live constraint:
    # thrown-in hands run 2..8 of 36 across seeds 0..49 (measured 2026-08-17).
    assert table.thrown < HANDS, (
        f"seed {seed}: every hand was thrown in, so the three counts below "
        f"would each read 0 == 0 and this non-vacuity block would prove nothing"
    )
    played_hands = HANDS - table.thrown
    assert len(table.hand_starts) == played_hands, f"seed {seed}"
    assert len(table.tricks) == played_hands * TRICKS_PER_HAND, f"seed {seed}"
    assert len(table.plays) == 3 * len(table.tricks), f"seed {seed}"

    contracts: Counter[str] = Counter()
    for h, first in enumerate(table.hand_starts):
        h_tricks = table.tricks[first : first + TRICKS_PER_HAND]
        h_plays = table.plays[3 * first : 3 * (first + TRICKS_PER_HAND)]
        gt, trump = table.contracts[first]
        contracts[gt] += 1

        # The deal reconstructs from the plays: ten cards each, and the union is
        # thirty of the thirty-two (the skat holds the other two).
        dealt: dict[Player, list[Card]] = {}
        for p, c in h_plays:
            dealt.setdefault(p, []).append(c)
        assert sorted(dealt) == [0, 1, 2], f"seed {seed} hand {h}"
        assert all(len(cs) == TRICKS_PER_HAND for cs in dealt.values()), f"seed {seed} hand {h}"
        assert len({(c.rank, c.suit) for _, c in h_plays}) == 30, f"seed {seed} hand {h}"

        remaining = {p: {(c.rank, c.suit) for c in cs} for p, cs in dealt.items()}
        for t, (winner, cards) in enumerate(h_tricks):
            group = h_plays[3 * t : 3 * t + 3]
            assert {p for p, _ in group} == {0, 1, 2}, f"seed {seed} hand {h} trick {t}"
            assert [c for _, c in group] == cards, f"seed {seed} hand {h} trick {t}"
            # The contract holds for the whole hand.
            assert table.contracts[first + t] == (gt, trump), f"seed {seed} hand {h}"
            # Routing: the winner leads the next trick.
            if t + 1 < TRICKS_PER_HAND:
                assert h_plays[3 * (t + 1)][0] == winner, f"seed {seed} hand {h} trick {t}"
            # The winner recomputes under the announced contract's order.
            assert winner == _winner(group, gt, trump), f"seed {seed} hand {h} trick {t} ({gt})"

            # Follow legality: a holder of the led class must play in it.
            led_class = _follow_class(group[0][1], gt, trump)
            for idx, (p, c) in enumerate(group):
                if idx > 0:
                    holds = any(
                        _follow_class(Card(r, s), gt, trump) == led_class
                        for (r, s) in remaining[p]
                    )
                    if holds:
                        assert _follow_class(c, gt, trump) == led_class, (
                            f"seed {seed} hand {h} trick {t}: {p} broke follow "
                            f"({gt}, led {led_class})"
                        )
                remaining[p].discard((c.rank, c.suit))
    return contracts


def test_50_random_games_satisfy_invariants() -> None:
    game = _skat()
    for seed in range(50):
        _check_seed(game, seed)


def test_the_three_contracts_are_all_reached() -> None:
    """The recomputation branches on the contract, and Null's order is the one
    the game's `ranking:` does not give -- so a sweep that never declared Null
    would leave that branch, and the Trick Order row that selects it, entirely
    unchecked while every assertion above stayed green."""
    game = _skat()
    contracts: Counter[str] = Counter()
    for seed in range(10):
        contracts += _check_seed(game, seed)
    assert contracts["null"] > 0, contracts
    assert contracts["grand"] > 0, contracts
    assert contracts["suit"] > 0, contracts
