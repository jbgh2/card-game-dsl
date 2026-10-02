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
  card after — comes once every other seat has decided on eight cards;
- no seat decides on eight cards more than twice: a call in the last lap is
  not answered by a seat that has already taken its ninth card (the
  operator's ruling on issue #785). An aimed run reaches that case: in a
  game's first hands, a seat asked a second time on eight cards calls
  whenever the call is offered.

red under: anchor tichu.cardlang's deal-time polls at a fixed seat — the
dealer counter reddens; close the eighth card's poll after one silent lap —
the final-decision counter reddens; let a call re-open the eighth card's
poll — the aimed run's third-decision counter reddens.

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
# The aimed run calls on a second look only in a game's first hands: calling
# grand that eagerly every hand loses the race to 1000 for both teams, so the
# game never ends and its declared `max_length` stops it.
EAGER_HANDS = 2


class _Order:
    """A chooser that plays the reference policy and records, per hand, the
    grand tichu decisions as (seat, cards held), the dealer the rules name,
    and the first seat out."""

    def __init__(self, seed: int, eager_second: bool = False) -> None:
        self.base = tichu_reference_policy(random.Random(seed))
        self.eager_second = eager_second
        self.second_look_calls = 0
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
            looked = self.hands[-1]["asks"].count((player, 8))
            self.hands[-1]["asks"].append((player, held))
            call = next((c for c in candidates if c[0] == "call_grand_tichu"), None)
            aimed = self.eager_second and len(self.hands) <= EAGER_HANDS
            if aimed and held == 8 and looked == 1 and call is not None:
                self.second_look_calls += 1
                return [call]
        elif self.hands and self.hands[-1]["first_out"] is None and self.hands[-1]["asks"][-1][1] >= 8:
            empty = [p for p in seats if self._held(p) == 0]
            if len(empty) == 1:
                self.hands[-1]["first_out"] = empty[0]
        return self.base(player, candidates, n)


def _played(eager_second: bool = False) -> list[_Order]:
    game = check_source(TICHU)
    out = []
    for seed in SEEDS:
        rec = _Order(seed, eager_second)
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
                if eight.count(seat) > 2:
                    found["grand.decision_after_taking_the_ninth_card"] += 1
    return found


def test_grand_tichu_follows_the_faq_order() -> None:
    found = _violations(_played())
    assert found["grand.counts_reached"] > 0, found
    assert found["grand.count_not_opened_by_the_dealer"] == 0, found
    assert found["grand.final_eighth_card_decision_before_the_others"] == 0, found
    assert found["grand.decision_after_taking_the_ninth_card"] == 0, found


def test_a_call_on_the_last_lap_is_not_answered() -> None:
    runs = _played(eager_second=True)
    assert sum(r.second_look_calls for r in runs) > 0
    found = _violations(runs)
    assert found["grand.decision_after_taking_the_ninth_card"] == 0, found
    assert found["grand.count_not_opened_by_the_dealer"] == 0, found
