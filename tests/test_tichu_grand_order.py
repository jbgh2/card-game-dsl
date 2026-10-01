"""The order of grand tichu calls, held to the rules by playouts.

Rules (Fata Morgana English edition, its FAQ): "the winner of the previous
round shuffles … The dealer himself takes the top card. Now all in turn take
one card at a time"; grand tichu is called "before taking his ninth card",
and the FAQ fixes the order at the last card: "A nimmt seine 8te Karte (kann
ansagen) / C nimmt 8te Karte (kann ansagen) / A (sieht, das C nichts ansagt,
kann nun seinerseits ansagen) und nimmt seine 9te Karte / C (weiss nun, dass
A nicht ansagt, kann selbst ansagen) nimmt seine 9te Karte". The winner of
the previous round is read as the player who went out first in it, and seat
0 deals the first hand (the operator's ruling on issue #781).

The checks restate that order from the live world, never from the game
file's polls:

- every hand's grand tichu decisions on each card count begin with the
  dealer;
- every seat's last decision on eight cards — the one it takes the ninth
  card after — comes once every other seat has decided on eight cards.

red under: anchor tichu.cardlang's deal-time polls at a fixed seat — the
dealer counter reddens; close the eighth card's poll after one silent lap —
the final-decision counter reddens.

What a green here does not prove: nothing about the earlier counts beyond
who opens them (the next card is itself the next look), and nothing at the
OpenSpiel seam beyond what tests/openspiel_ready/test_tichu.py certifies.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Player
from tests.test_playout_tichu import tichu_reference_policy

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"
SEEDS = range(3)
GRAND = {"call_grand_tichu", "decline_grand"}


class _Order:
    """A chooser that plays the reference policy and records, per hand, the
    grand tichu decisions as (seat, cards held), the dealer the rules name,
    and the first seat out."""

    def __init__(self, seed: int) -> None:
        self.base = tichu_reference_policy(random.Random(seed))
        self.rs: RuntimeState | None = None
        self.hands: list[dict[str, Any]] = []

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def _held(self, seat: Player) -> int:
        assert self.rs is not None
        return len(self.rs.zones.instance("hand", seat).cards)

    def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
        names = {c[0] for c in candidates if isinstance(c, tuple) and c}
        seats = list(self.rs.seating.players) if self.rs is not None else []
        if names & GRAND:
            held = self._held(player)
            if held == 1 and (not self.hands or self.hands[-1]["asks"][-1][1] != 1):
                first_out = self.hands[-1]["first_out"] if self.hands else None
                self.hands.append(
                    {"dealer": first_out if first_out is not None else 0, "asks": [], "first_out": None}
                )
            self.hands[-1]["asks"].append((player, held))
        elif self.hands and self.hands[-1]["first_out"] is None and self.hands[-1]["asks"][-1][1] >= 8:
            empty = [p for p in seats if self._held(p) == 0]
            if len(empty) == 1:
                self.hands[-1]["first_out"] = empty[0]
        return self.base(player, candidates, n)


def _played() -> list[_Order]:
    game = check_source(TICHU)
    out = []
    for seed in SEEDS:
        rec = _Order(seed)
        play_game(game, random.Random(seed), None, rec, None, on_first_decision=rec.attach)
        out.append(rec)
    return out


def _violations(runs: list[_Order]) -> Counter[str]:
    found: Counter[str] = Counter()
    for rec in runs:
        for hand in rec.hands:
            asks = hand["asks"]
            for count in range(1, 9):
                at = [seat for seat, held in asks if held == count]
                found["grand.counts_reached"] += 1
                if not at or at[0] != hand["dealer"]:
                    found["grand.count_not_opened_by_the_dealer"] += 1
            eight = [seat for seat, held in asks if held == 8]
            seats = set(eight)
            for seat in seats:
                last = max(i for i, s in enumerate(eight) if s == seat)
                seen = {s for s in eight[:last] if s != seat}
                if seen != seats - {seat}:
                    found["grand.final_eighth_card_decision_before_the_others"] += 1
    return found


def test_grand_tichu_follows_the_faq_order() -> None:
    found = _violations(_played())
    assert found["grand.counts_reached"] > 0, found
    assert found["grand.count_not_opened_by_the_dealer"] == 0, found
    assert found["grand.final_eighth_card_decision_before_the_others"] == 0, found
