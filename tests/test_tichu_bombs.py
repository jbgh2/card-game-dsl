"""Bombs out of turn, held to their rules by driven playouts.

Rules (Fata Morgana English edition, its FAQ): bombs can be played at any
moment, out of turn included; after each ordinary combination every player
in turn may bomb before the next ordinary play; after three passes any
player may bomb before the trick is gathered; the Dog cannot be bombed; a
bomb played out of turn need not fulfil the wish.

The window is the climb form's interrupt regime (`mechanics.ClimbForm`):
after every play but a trick-ending one, and once more when the ring is
spent, every other seat still holding cards is asked in turn order from the
last player, offered its beating bombs beside the decline token. Nothing of
that is visible from a score, so the checks read the live world inside the
chooser — the test's own reading of who must be asked next, of what a
window may offer, and of where the ring resumes after a taken bomb — and
hold the sequence of asks to it. The policy is aimed (P10): a seat asked in
the window bombs whenever it can, so taken windows, over-bombed windows and
closing windows are all reached.

What a green here does not prove: nothing about whether bombing is wise,
and nothing at the OpenSpiel seam beyond what
tests/openspiel_ready/test_tichu.py certifies.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.tichu_combinations import (
    INTERRUPT_DECLINE,
    WISH_TOKENS,
    Play,
    _legal_follows,
)
from cardlang.runtime.values import Player
from tests.test_playout_tichu import tichu_reference_policy

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"


class _Driven:
    """A window-bombing chooser that audits every climb decision."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.base = tichu_reference_policy(self.rng)
        self.rs: RuntimeState | None = None
        self.failures: list[str] = []
        # The seats the rules say must be asked next, in order, before any
        # ring decision; None while no window is owed.
        self.expected_window: list[Player] | None = None
        # After a taken window bomb: the seat the ring must resume at.
        self.resume_at: Player | None = None
        self.window_asks = 0
        self.window_bombs = 0
        self.closing_windows = 0
        self.over_bombs = 0
        self.dog_leads = 0
        self.resumes_checked = 0

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def _holders_from(self, seat: Player, include_seat: bool) -> list[Player]:
        rs = self.rs
        assert rs is not None
        return [
            p for p in rs.seating.turn_order_from(seat)
            if (include_seat or p != seat) and rs.zones.families["hand"][p].cards
        ]

    def _ring_next(self, seat: Player, last: Player) -> Player | None:
        """Where the ring goes after `seat`: the first seat in turn order
        that is the last player (action returning to them ends the trick,
        cards or none) or still holds cards."""
        rs = self.rs
        assert rs is not None
        for p in rs.seating.turn_order_from(seat)[1:]:
            if p == last or rs.zones.families["hand"][p].cards:
                return p
        return None

    def _play_ends_the_hand(self, player: Player, play: Play) -> bool:
        """The game's own trick-ending condition for a play about to be
        made: it empties the hand and either only one other seat still holds
        cards or the shed completes a double victory."""
        rs = self.rs
        assert rs is not None
        hand = rs.zones.families["hand"][player].cards
        if len(hand) != len(play.cards):
            return False
        holders = sum(1 for q in range(4) if rs.zones.families["hand"][q].cards)
        if holders <= 2:
            return True
        out_first = rs.get("out_first")
        shed_first = rs.mech_state[-1]["shed_first"]
        first = out_first if out_first is not None else shed_first
        return first is not None and rs.team_of[first] == rs.team_of[player]

    def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
        rs = self.rs
        assert rs is not None
        if candidates and all(isinstance(c, str) and c in WISH_TOKENS for c in candidates):
            return [self.rng.choice(candidates)]
        plays = [c for c in candidates if isinstance(c, Play)]
        in_window = INTERRUPT_DECLINE in candidates
        if not plays and not in_window and "pass" not in candidates:
            return self.base(player, candidates, n)
        frame = rs.mech_state[-1]
        standing = frame["current"]
        if in_window:
            self.window_asks += 1
            assert "pass" not in candidates
            # The right seat, in the right order.
            if not self.expected_window or self.expected_window[0] != player:
                self.failures.append(f"window asked P{player}; the rules ask {self.expected_window}")
            else:
                self.expected_window.pop(0)
            # Exactly the beating bombs, out of the seat's own hand.
            hand = rs.zones.families["hand"][player].cards
            bombs = {(frozenset(p.cards), p.wild) for p in _legal_follows(list(hand), standing) if p.is_bomb}
            offered = {(frozenset(p.cards), p.wild) for p in plays}
            if offered != bombs:
                self.failures.append(f"P{player}'s window offered {offered ^ bombs}")
            if plays:
                self.window_bombs += 1
                if standing.is_bomb:
                    self.over_bombs += 1
                pick = plays[self.rng.randrange(len(plays))]
                if self._play_ends_the_hand(player, pick):
                    self.expected_window = None
                    self.resume_at = None
                else:
                    self.expected_window = self._holders_from(player, include_seat=False)
                    # The ring resumes after the bomber; if it comes straight
                    # back to the bomber, the closing window follows instead.
                    nxt = self._ring_next(player, player)
                    self.resume_at = None if nxt == player else nxt
                return [pick]
            return [INTERRUPT_DECLINE]
        # A ring decision: every window owed was walked to its end first,
        # and after a taken bomb the ring resumes right after the bomber.
        if self.expected_window:
            self.failures.append(f"P{player} asked on turn while {self.expected_window} were still owed a window")
        self.expected_window = None
        if self.resume_at is not None:
            if player != self.resume_at:
                self.failures.append(f"the ring resumed at P{player}, not after the bomber (P{self.resume_at})")
            self.resumes_checked += 1
            self.resume_at = None
        picked = self.base(player, candidates, n)
        chosen = picked[0]
        if isinstance(chosen, Play):
            if chosen.kind == "dog":
                self.dog_leads += 1
                self.expected_window = None  # the Dog cannot be bombed
            elif self._play_ends_the_hand(player, chosen):
                self.expected_window = None
            else:
                self.expected_window = self._holders_from(player, include_seat=False)
        else:
            # A pass. When the ring's next seat is the last player — cards
            # or none — the ring is spent and the closing window is owed.
            last = frame["last"]
            if self._ring_next(player, last) == last:
                self.closing_windows += 1
                self.expected_window = self._holders_from(last, include_seat=False)
        return picked


def test_the_window_asks_every_other_seat_in_turn_after_each_play() -> None:
    game = check_source(TICHU)
    totals = {"asks": 0, "bombs": 0, "over": 0, "dogs": 0, "closing": 0, "resumes": 0}
    for seed in range(10):
        driven = _Driven(seed)
        play_game(game, random.Random(seed), None, driven, on_first_decision=driven.attach)
        assert not driven.failures, driven.failures[:5]
        totals["asks"] += driven.window_asks
        totals["bombs"] += driven.window_bombs
        totals["over"] += driven.over_bombs
        totals["dogs"] += driven.dog_leads
        totals["closing"] += driven.closing_windows
        totals["resumes"] += driven.resumes_checked
    # Live, not vacuously green: windows were asked after plays and at the
    # close, bombs were taken out of turn (and over-bombed), the ring resumed
    # after the bomber, and the Dog's no-window rule was exercised.
    assert totals["asks"] > 1000, totals
    assert totals["bombs"] > 20, totals
    assert totals["over"] > 0, totals
    assert totals["closing"] > 100, totals
    assert totals["resumes"] > 20, totals
    assert totals["dogs"] > 0, totals
