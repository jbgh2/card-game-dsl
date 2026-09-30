"""Bombs out of turn, held to their rules by driven playouts.

Rules (Fata Morgana English edition, its FAQ): "the proper chain of events"
is that after every ordinary turn — a combination played, or a pass — every
player, the one who just acted included and asked last, may bomb before the
next ordinary turn ("A plays … B can play a bomb or not / C … / D … / A can
play a bomb or not / B can play a (ordinary) combination or pass"); "you are
allowed to bomb your own trick"; after three passes any player may bomb
before the trick is gathered; the Dog cannot be bombed; a bomb played out of
turn need not fulfil the wish.

The window is the climb form's interrupt regime (`mechanics.ClimbForm`).
Nothing of it is visible from a score, so the checks read the live world
inside the chooser — the test's own reading of who must be asked next, of
what a window may offer, and of where the ring resumes after a taken bomb —
and hold the sequence of asks to it. Every window is attributed to the step
that opened it, so a wrong window reddens the step kind that owed it
(tests/test_climb_interrupt_window.py crosses those kinds with the climb
engines). The policy is aimed (P10): a seat asked in the window bombs
whenever it can, so taken windows, over-bombed windows, own-play bombs and
closing windows are all reached.

What a green here does not prove: nothing about whether bombing is wise,
and nothing at the OpenSpiel seam beyond what
tests/openspiel_ready/test_tichu.py certifies.
"""

from __future__ import annotations

import functools
import random
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.tichu_combinations import (
    INTERRUPT_DECLINE,
    WISH_TOKENS,
    Play,
    _combos,
    _legal_follows,
)
from cardlang.runtime.values import Player
from tests.test_playout_tichu import tichu_reference_policy

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"

# The step kinds a Tichu climb decision's choice is classified into — the
# rows of the grid's decline-engine column.
PASS = "pass"
CLOSING_PASS = "pass returning the ring to the last player"
PLAY = "play"
PLAY_ENDING_THE_TRICK = "play ending the trick"
PLAY_ENDING_THE_ROUND = "play ending the round"
INTERRUPT = "interrupt"
INTERRUPT_ENDING_THE_ROUND = "interrupt ending the round"
ANNOUNCEMENT = "announcement"

# The window policy's tempers, one per seed in turn.
EAGER = "eager"
OWN_PLAY = "over its own play"
LAST_CARDS = "with its last cards"
TEMPERS = (EAGER, OWN_PLAY, LAST_CARDS)


class _Driven:
    """A window-bombing chooser that audits every climb decision against
    the FAQ's chain of events."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.base = tichu_reference_policy(self.rng)
        self.temper = TEMPERS[seed % len(TEMPERS)]
        self.rs: RuntimeState | None = None
        # Per step kind: how often it was taken, and what went wrong after it.
        self.kinds: Counter[str] = Counter()
        self.failures: dict[str, list[str]] = {}
        # The window the rules owe: the step kind that opened it and the
        # seats still to ask, in order; None while no window is owed.
        self.owed: tuple[str, list[Player]] | None = None
        # The kind of the step most recently taken.
        self.last_kind: str | None = None
        # After a taken window bomb: the seat the ring must resume at.
        self.resume_at: Player | None = None
        self.window_asks = 0
        self.window_bombs = 0
        self.over_bombs = 0
        self.own_play_bombs = 0
        self.resumes_checked = 0

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def _fail(self, kind: str | None, message: str) -> None:
        self.failures.setdefault(kind or "(before any step)", []).append(message)

    def _holds(self, p: Player) -> bool:
        rs = self.rs
        assert rs is not None
        return bool(rs.zones.families["hand"][p].cards)

    def _window_after(self, seat: Player) -> list[Player]:
        """The FAQ's chain: every seat still holding cards, from the one after
        `seat` round to `seat` itself, asked last."""
        rs = self.rs
        assert rs is not None
        order = rs.seating.turn_order_from(seat)
        return [p for p in [*order[1:], seat] if self._holds(p)]

    def _open(self, kind: str, seat: Player) -> None:
        self.owed = (kind, self._window_after(seat))

    def _ring_next(self, seat: Player, last: Player) -> Player | None:
        """Where the ring goes after `seat`: the first seat in turn order
        that is the last player (action returning to them ends the trick,
        cards or none) or still holds cards."""
        rs = self.rs
        assert rs is not None
        for p in rs.seating.turn_order_from(seat)[1:]:
            if p == last or self._holds(p):
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
        holders = sum(1 for q in range(4) if self._holds(q))
        if holders <= 2:
            return True
        out_first = rs.get("out_first")
        shed_first = rs.mech_state[-1]["shed_first"]
        first = out_first if out_first is not None else shed_first
        return first is not None and rs.team_of[first] == rs.team_of[player]

    def _owed_remaining(self) -> list[Player]:
        if self.owed is None:
            return []
        return [p for p in self.owed[1] if self._holds(p)]

    def _close_owed(self, where: str) -> None:
        """A decision outside the window: every seat owed must have been
        asked by now."""
        if self.owed is not None:
            rest = self._owed_remaining()
            if rest:
                self._fail(self.owed[0], f"{where} while {rest} were still owed a window")
        self.owed = None

    def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
        rs = self.rs
        assert rs is not None
        if candidates and all(isinstance(c, str) and c in WISH_TOKENS for c in candidates):
            # The Mahjong's wish: the window its play opened is asked after
            # the token, so it becomes the announcement's to answer for.
            self.kinds[ANNOUNCEMENT] += 1
            self.last_kind = ANNOUNCEMENT
            if self.owed is not None:
                self.owed = (ANNOUNCEMENT, self.owed[1])
            return [self.rng.choice(candidates)]
        plays = [c for c in candidates if isinstance(c, Play)]
        in_window = INTERRUPT_DECLINE in candidates
        if not plays and not in_window and "pass" not in candidates:
            self._close_owed(f"P{player} decided outside the trick")
            return self.base(player, candidates, n)
        frame = rs.mech_state[-1]
        standing = frame["current"]
        if in_window:
            self.window_asks += 1
            assert "pass" not in candidates
            # The right seat, in the right order.
            rest = self._owed_remaining()
            if self.owed is None:
                self._fail(self.last_kind, f"window asked P{player} with none owed")
            elif not rest or rest[0] != player:
                self._fail(self.owed[0], f"window asked P{player}; the rules ask {rest}")
                self.owed = None
            else:
                self.owed = (self.owed[0], rest[1:])
            # Exactly the beating bombs, out of the seat's own hand.
            hand = rs.zones.families["hand"][player].cards
            bombs = {(frozenset(p.cards), p.wild) for p in _legal_follows(list(hand), standing) if p.is_bomb}
            offered = {(frozenset(p.cards), p.wild) for p in plays}
            if offered != bombs:
                self._fail(self.owed[0] if self.owed else self.last_kind, f"P{player}'s window offered {offered ^ bombs}")
            # Aimed, in three tempers, one per seed: an eager table bombs
            # whenever it can, which reaches the bomb over a bomb; the other
            # two hold their bombs for one shape each — over the bomber's own
            # standing play, or with the bomber's last cards.
            wanted = {
                EAGER: True,
                OWN_PLAY: frame["last"] == player,
                LAST_CARDS: any(len(p.cards) == len(hand) for p in plays),
            }[self.temper]
            if plays and wanted:
                self.window_bombs += 1
                if standing.is_bomb:
                    self.over_bombs += 1
                if frame["last"] == player:
                    self.own_play_bombs += 1
                pick = plays[self.rng.randrange(len(plays))]
                if self._play_ends_the_hand(player, pick):
                    self.kinds[INTERRUPT_ENDING_THE_ROUND] += 1
                    self.last_kind = INTERRUPT_ENDING_THE_ROUND
                    self.owed = None
                    self.resume_at = None
                else:
                    self.kinds[INTERRUPT] += 1
                    self.last_kind = INTERRUPT
                    self._open(INTERRUPT, player)
                    # The owed window is recomputed against the hand the bomb
                    # leaves, which it has not left yet: drop the bomber if
                    # the bomb is their last cards.
                    if len(hand) == len(pick.cards):
                        assert self.owed is not None
                        self.owed = (INTERRUPT, [p for p in self.owed[1] if p != player])
                    # The ring resumes after the bomber.
                    nxt = self._ring_next(player, player)
                    self.resume_at = None if nxt == player else nxt
                return [pick]
            return [INTERRUPT_DECLINE]
        # A ring decision: every window owed was walked to its end first,
        # and after a taken bomb the ring resumes right after the bomber.
        self._close_owed(f"P{player} asked on turn")
        if self.resume_at is not None:
            if player != self.resume_at:
                self._fail(INTERRUPT, f"the ring resumed at P{player}, not after the bomber (P{self.resume_at})")
            self.resumes_checked += 1
            self.resume_at = None
        # Aimed: on turn a table that holds its bombs keeps them whole where
        # it has another choice, so a bomb outlives the seat's own plays and
        # a hand whittles down to one.
        hand = rs.zones.families["hand"][player].cards
        kept = {c for p in _combos(list(hand)) if p.is_bomb for c in p.cards} if self.temper != EAGER else set()
        spare = [c for c in candidates if not (isinstance(c, Play) and kept & set(c.cards))]
        picked = [self.rng.choice(spare)] if kept and spare else self.base(player, candidates, n)
        chosen = picked[0]
        if isinstance(chosen, Play):
            if chosen.kind == "dog":
                kind = PLAY_ENDING_THE_TRICK  # the Dog cannot be bombed
            elif self._play_ends_the_hand(player, chosen):
                kind = PLAY_ENDING_THE_ROUND
            else:
                kind = PLAY
                self.owed = (
                    PLAY,
                    [p for p in self._window_after(player) if p != player or len(hand) != len(chosen.cards)],
                )
        else:
            last = frame["last"]
            kind = CLOSING_PASS if self._ring_next(player, last) == last else PASS
            self._open(kind, player)
        self.kinds[kind] += 1
        self.last_kind = kind
        return picked


@functools.lru_cache(maxsize=None)
def driven_tichu_run(seeds: int = 10) -> tuple[Counter[str], dict[str, list[str]], Counter[str]]:
    """The driven playouts over `seeds` seeds: the step kinds taken, the
    failures attributed to each, and the liveness totals."""
    game = check_source(TICHU)
    kinds: Counter[str] = Counter()
    failures: dict[str, list[str]] = {}
    totals: Counter[str] = Counter()
    for seed in range(seeds):
        driven = _Driven(seed)
        play_game(game, random.Random(seed), None, driven, on_first_decision=driven.attach)
        kinds.update(driven.kinds)
        for kind, messages in driven.failures.items():
            failures.setdefault(kind, []).extend(f"seed {seed}: {m}" for m in messages)
        totals.update(
            {
                "asks": driven.window_asks,
                "bombs": driven.window_bombs,
                "over": driven.over_bombs,
                "own": driven.own_play_bombs,
                "resumes": driven.resumes_checked,
            }
        )
    return kinds, failures, totals


def test_the_window_follows_the_faq_chain_after_every_ordinary_turn() -> None:
    kinds, failures, totals = driven_tichu_run()
    assert not failures, {k: v[:5] for k, v in failures.items()}
    # Live, not vacuously green: windows were asked after plays and passes
    # and at the close, bombs were taken out of turn (over-bombed, and over
    # the bomber's own standing play), the ring resumed after the bomber,
    # and the Dog's no-window rule was exercised.
    assert totals["asks"] > 1000, totals
    assert totals["bombs"] > 20, totals
    assert totals["over"] > 0, totals
    assert totals["own"] > 0, totals
    assert totals["resumes"] > 20, totals
    assert kinds[CLOSING_PASS] > 100, kinds
    assert kinds[PLAY_ENDING_THE_TRICK] > 0, kinds
