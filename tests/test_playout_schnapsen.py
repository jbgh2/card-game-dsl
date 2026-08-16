"""Random-playout harness for Schnapsen.

Schnapsen is the first game with heterogeneous lead moves and a non-standard
deck (schnapsen20, A 10 K Q J). The invariants that would go red under a real
bug: card-point integrity (the deck holds exactly 120 points — catches a wrong
value table or a lost card), per-trick winner correctness against the
schnapsen20 rank order *and* trump (catches the rank-order landmine for a
non-standard deck), and that every hand awards game points (settlement fires).

Trick facts derive from the kernel's observation events, not trace events
(the `tests/playout_trace.py` pattern — Coup and Tichu precedents): the game
carries no game-local Python since issue #256 retired the schnapsen shell, so
plays are the observed movements into `trick_pile` (a TrickPile: identity to
every observer), winners are the observed `trick_pile -> captured[w]` drains,
and the trump is the observed deal into `trump_indicator` (a Discard). The
winner recomputation below is an independent oracle: the engine names its
winner through the `highest_trump_or_led_suit` call form over the Arrival
Record, and this harness re-derives the same winner from observation alone —
if the record ever diverged from what observers saw, the routing would
contradict the recomputation here.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Player

SCHNAPSEN = Path(__file__).parent.parent / "docs" / "games" / "schnapsen.cardlang"

# schnapsen20 strength, high to low: A 10 K Q J.
RANK = {r: i for i, r in enumerate(("J", "Q", "K", "10", "A"))}

_SUITS = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}


def _parse(card_str: str) -> tuple[str, str]:
    """(rank, suit) of a rendered card string (`K♣` -> (`K`, `clubs`))."""
    return card_str[:-1], _SUITS[card_str[-1]]


def _seat(label: str, family: str) -> int:
    """The instance key of a family zone label (`hand[1]` -> 1)."""
    return int(label[len(family) + 1 : -1])


class SchnapsenTricks:
    """Trick reconstruction from observer 0's stream.

    Every consumed fact rides a zone whose projection is identity for every
    observer (`trick_pile` a TrickPile, `captured` a PlayerPile,
    `trump_indicator` a Discard — cardlang/stdlib/zones.py ZONE_PROJECTIONS),
    so observer 0's `move` events carry full card identity at every consumed
    transfer, and the source labels carry the seats.
    """

    def __init__(self) -> None:
        self.trump: str | None = None
        self.pending: list[tuple[Player, tuple[str, str]]] = []
        # One reconstructed trick: (winner, plays-in-order, trump-then).
        self.tricks: list[tuple[Player, list[tuple[Player, tuple[str, str]]], str]] = []

    def observer(self, player: Player, event: tuple[Any, ...]) -> None:
        if player != 0 or event[0] != "move":
            return
        _, src, _src_view, dst, dst_view = event
        if dst == "trump_indicator" and src == "deck":
            # The turned-up trump card (the exchange arrival from a hand is
            # the trump JACK — same suit, deliberately not consumed).
            (card_str,) = dst_view
            self.trump = _parse(card_str)[1]
        elif dst == "trick_pile" and isinstance(src, str) and src.startswith("hand["):
            (card_str,) = dst_view  # one card per play
            self.pending.append((_seat(src, "hand"), _parse(card_str)))
        elif src == "trick_pile" and isinstance(dst, str) and dst.startswith("captured["):
            assert self.trump is not None, "a trick completed before any trump was turned"
            self.tricks.append(
                (_seat(dst, "captured"), list(self.pending), self.trump)
            )
            self.pending = []


def _expected_winner(
    group: list[tuple[Player, tuple[str, str]]], trump: str
) -> Player:
    led = group[0][1][1]
    trumps = [(p, c) for p, c in group if c[1] == trump]
    if trumps:
        return max(trumps, key=lambda pc: RANK[pc[1][0]])[0]
    of_led = [(p, c) for p, c in group if c[1] == led]
    return max(of_led, key=lambda pc: RANK[pc[1][0]])[0]


def _schnapsen() -> Any:
    return check_source(SCHNAPSEN)


def test_200_random_games_satisfy_invariants() -> None:
    game = _schnapsen()
    for seed in range(200):
        score_sums: list[int] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                score_sums.append(sum(data.values()))  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        recon = SchnapsenTricks()
        result = play_game(game, random.Random(seed), tracer, observer=recon.observer)

        # Terminates with a winner who reached 0 (or below); winner is lowest.
        assert result.winner == min(result.scores, key=lambda p: result.scores[p])
        assert result.scores[result.winner] <= 0

        # Deck integrity: 20 cards, exactly 120 card points, across all zones.
        assert census["total"] == 20, f"seed {seed}: {census}"
        assert census["total_value"] == 120, f"seed {seed}: {census}"

        # The reconstruction found real tricks (the vacuous-oracle guard:
        # an empty event stream must fail, never pass by iterating nothing).
        assert recon.tricks, f"seed {seed}: no tricks reconstructed"
        assert not recon.pending, f"seed {seed}: dangling plays outside a trick"

        # Two plays per trick; the engine's winner (the captured-pile
        # routing, fed by the Arrival Record) matches an independent
        # recomputation from the observed plays and trump.
        for i, (winner, group, trump) in enumerate(recon.tricks):
            assert len(group) == 2, f"seed {seed} trick {i}: {group}"
            assert winner == _expected_winner(group, trump), f"seed {seed} trick {i}"

        # Every hand settles to someone's cost: the total game score strictly
        # falls hand over hand (game points are always awarded).
        assert len(score_sums) == result.hands_played
        for a, b in zip([14, *score_sums], score_sums):  # 7 + 7 at the start
            assert b < a, f"seed {seed}: game score did not fall ({a} -> {b})"
