"""The Mahjong's wish, held to its rules by driven playouts.

Rules (Fata Morgana English edition): whoever plays the Mahjong may wish for
a rank; the next player who holds a card of that rank and can lawfully play
it must (a bomb holding it counts; the Phoenix does not count as the rank);
the wish stays in force until someone fulfils it.

The wish is a second decision of the same seat right after the Mahjong's
play (the climb form's announcement regime, `mechanics.ClimbForm`), and the
compulsion is the form offering the compelled plays alone. Neither can be
seen from a score, so every check here reads the live world inside the
chooser — an independent re-derivation of the standing wish from the trick's
own event record and the carried `wish` — and holds the candidate list to
it. The policy is aimed (P10): it always wishes, and it keeps the Mahjong to
the last, so the wish node and the hand-ending Mahjong play are both reached.

What a green here does not prove: nothing about which rank a seat ought to
wish for, and nothing at the OpenSpiel seam beyond what
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
    WISH_TOKENS,
    WISH_VALUES,
    Play,
)
from cardlang.runtime.values import Card, Player
from tests.test_playout_tichu import tichu_reference_policy

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"
_RANKVAL = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
            "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}


def _standing_wish(rs: RuntimeState) -> int | None:
    """The wish in force at a live decision, re-derived here from the game's
    carried `wish` and the running trick's events — the test's own reading
    of the rule, never `tichu.standing_wish`."""
    carried = rs.get("wish")
    wish: int | None = carried or None
    frame = rs.mech_state[-1] if rs.mech_state else None
    for kind, _seat, value in (frame["events"] if frame is not None else ()):
        if kind == "announce":
            wish = WISH_VALUES.get(value) if value in WISH_VALUES else (None if value == "no_wish" else wish)
        elif kind == "play" and wish is not None:
            if any(_RANKVAL.get(c.rank) == wish for c in value.cards):
                wish = None
    return wish


class _Driven:
    """A wishing, Mahjong-hoarding chooser that audits every climb decision."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.base = tichu_reference_policy(self.rng)
        self.rs: RuntimeState | None = None
        self.wish_nodes = 0
        self.compelled_nodes = 0
        self.free_nodes = 0
        self.failures: list[str] = []
        self.awaiting_wish: Player | None = None
        self.mahjong_ended_hand = 0

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
        rs = self.rs
        assert rs is not None
        if candidates and all(isinstance(c, str) and c in WISH_TOKENS for c in candidates):
            # The announcement regime: the wisher, asked once more, right
            # after the Mahjong's play.
            if self.awaiting_wish != player:
                self.failures.append(f"wish offered to P{player}, expected P{self.awaiting_wish}")
            self.awaiting_wish = None
            self.wish_nodes += 1
            assert set(candidates) == set(WISH_TOKENS)
            wished = [t for t in candidates if t != "no_wish"]
            return [self.rng.choice(wished)]
        if self.awaiting_wish is not None:
            self.failures.append(f"P{self.awaiting_wish} played the Mahjong and was not asked to wish")
            self.awaiting_wish = None
        plays = [c for c in candidates if isinstance(c, Play)]
        if not plays and "pass" not in candidates:
            return self.base(player, candidates, n)
        # A climb decision. What the rules compel, from the test's own reading.
        wish = _standing_wish(rs)
        holding = [p for p in plays if any(_RANKVAL.get(c.rank) == wish for c in p.cards)]
        if wish is not None and holding:
            self.compelled_nodes += 1
            if "pass" in candidates or len(plays) != len(holding):
                self.failures.append(
                    f"P{player} holds a legal play of the wished rank {wish} yet was offered "
                    f"{len(plays)} plays and pass={'pass' in candidates}"
                )
        else:
            self.free_nodes += 1
            leading = rs.mech_state[-1]["current"] is None
            if wish is not None and not holding and plays and not leading and "pass" not in candidates:
                self.failures.append(f"P{player} cannot fulfil {wish} and was offered no pass")
        # Keep the Mahjong to the last card, so the hand-ending Mahjong play
        # is reached; otherwise draw uniformly.
        hand = rs.zones.families["hand"][player].cards
        without = [p for p in plays if not any(c.rank == "Mahjong" for c in p.cards)]
        pool: list[Any] = list(without) + (["pass"] if "pass" in candidates else [])
        if not pool:
            pool = list(candidates)
        pick = pool[self.rng.randrange(len(pool))]
        if isinstance(pick, Play) and any(c.rank == "Mahjong" for c in pick.cards):
            if len(hand) == len(pick.cards) and self._play_ends_the_hand(player):
                # The Mahjong as the play that ends the hand — the third
                # player out, or a double victory completed: the round ends
                # here and the wish is void, so no announcement may follow.
                self.mahjong_ended_hand += 1
            else:
                self.awaiting_wish = player
        return [pick]

    def _play_ends_the_hand(self, player: Player) -> bool:
        """The game's own trick-ending condition, read for the play about
        to empty `player`'s hand: only one other seat still holds cards, or
        the shed completes a double victory."""
        rs = self.rs
        assert rs is not None
        holders = sum(1 for q in range(4) if rs.zones.families["hand"][q].cards)
        if holders <= 2:
            return True
        team_of = rs.team_of
        out_first = rs.get("out_first")
        shed_first = rs.mech_state[-1]["shed_first"]
        first = out_first if out_first is not None else shed_first
        return first is not None and team_of[first] == team_of[player]


def test_the_wish_is_asked_of_the_mahjong_player_and_compels_the_table() -> None:
    game = check_source(TICHU)
    total = _Driven(0)
    for seed in range(24):
        driven = _Driven(seed)
        rng = random.Random(seed)
        play_game(game, rng, None, driven, on_first_decision=driven.attach)
        assert not driven.failures, driven.failures[:5]
        total.wish_nodes += driven.wish_nodes
        total.compelled_nodes += driven.compelled_nodes
        total.free_nodes += driven.free_nodes
        total.mahjong_ended_hand += driven.mahjong_ended_hand
    # Live, not vacuously green: the wish was asked, seats were compelled,
    # and the void case — the Mahjong ending the hand — was reached and no
    # announcement followed it (a failure above would have named it).
    assert total.wish_nodes > 20, total.wish_nodes
    assert total.compelled_nodes > 10, total.compelled_nodes
    assert total.free_nodes > total.compelled_nodes
    assert total.mahjong_ended_hand > 0, "the hand-ending Mahjong play was never reached"


def test_the_wish_is_a_public_announcement_every_seat_records() -> None:
    game = check_source(TICHU)
    driven = _Driven(3)
    logs: dict[Player, list[tuple[Any, ...]]] = {p: [] for p in range(4)}

    def observer(player: Player, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    play_game(game, random.Random(3), None, driven, observer=observer, on_first_decision=driven.attach)
    wishes = [e for e in logs[0] if e[0] == "announce" and e[2] in WISH_VALUES]
    assert wishes, "no wish was announced"
    for q in range(1, 4):
        assert [e for e in logs[q] if e[0] == "announce" and e[2] in WISH_VALUES] == wishes


def test_a_wildcard_play_is_announced_and_two_histories_differ() -> None:
    """Two halves of one claim. The legal set of the next seat depends on
    the rank the Phoenix stands for: on one hand, against the two standing
    plays a gapless Phoenix straight can be, the follows differ. And the
    announce carries that rank to every seat: two lines from one seed that
    differ only in the assignment leave a bystander two different logs.
    The reddening edit for the second half: drop the wild-play announce in
    `mechanics.ClimbForm.apply` and the logs agree while the follows still
    differ — a legal set depending on a fact outside the information state."""
    from cardlang.runtime.tichu_combinations import _combos, _legal_follows

    phoenix = Card("Phoenix", "special")
    played = [Card("3", "clubs"), Card("4", "clubs"), Card("5", "hearts"), Card("6", "spades"), phoenix]
    two_to_six, three_to_seven = sorted(
        (p for p in _combos(played) if p.kind == "straight"), key=lambda p: p.key
    )
    assert (two_to_six.wild, three_to_seven.wild) == (2, 7)
    next_hand = [Card(r, "diamonds") for r in ("3", "4", "5", "6")] + [Card("7", "clubs")]
    beats_low = {p.key for p in _legal_follows(next_hand, two_to_six)}
    beats_high = {p.key for p in _legal_follows(next_hand, three_to_seven)}
    assert beats_low == {7} and beats_high == set()

    game = check_source(TICHU)

    class _Stop(Exception):
        pass

    class _Twins:
        def __init__(self, choose_high: bool) -> None:
            self.rng = random.Random(9)
            self.base = tichu_reference_policy(self.rng)
            self.choose_high = choose_high
            self.done = False
            self.log: list[tuple[Any, ...]] = []

        def observer(self, player: Player, event: tuple[Any, ...]) -> None:
            if player == 3 and event[0] == "announce":
                self.log.append(event)

        def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
            if self.done:
                raise _Stop
            plays = [c for c in candidates if isinstance(c, Play)]
            sets: dict[frozenset[Card], list[Play]] = {}
            for p in plays:
                sets.setdefault(frozenset(p.cards), []).append(p)
            twins = [ps for ps in sets.values() if len(ps) == 2 and ps[0].kind == "straight"]
            if twins:
                low, high = sorted(twins[0], key=lambda p: p.key)
                self.done = True
                return [high if self.choose_high else low]
            return self.base(player, candidates, n)

    logs: list[list[tuple[Any, ...]]] = []
    for high in (False, True):
        twins = _Twins(high)
        try:
            play_game(game, random.Random(9), None, twins, observer=twins.observer)
        except _Stop:
            pass
        assert twins.done, "no gapless Phoenix straight was offered on this line"
        logs.append(twins.log)
    assert logs[0][:-1] == logs[1][:-1], "the lines diverged before the twin play"
    assert logs[0][-1] != logs[1][-1], "the two assignments left a bystander's log identical"
    assert "@" in str(logs[0][-1][2]) and "@" in str(logs[1][-1][2])
