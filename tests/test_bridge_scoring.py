"""Independent recompute of Bridge scoring, driving the real bridge.cardlang.

Bridge's scoring lives in the DSL, so this drives actual games and recomputes
every hand's score from the contract and the trick winners, mirroring the
scoring rules in Python, then asserts the recomputed running totals match the
traced `hand_end` totals after every hand, and the final totals — after
Pagat's unfinished-rubber bonuses when play stops at the twelfth deal — match
the game's result. The contract is itself recomputed,
from the auction's announcements as every seat hears them: the standing bid,
its strain, the doubling, the closing passes and the declarer — the first
seat of the declaring side to name the final strain — are re-derived here from
the bids, and the declarer is held against the seat the game then exposes as
dummy (the declarer's partner), so the game's own bidding bookkeeping is held
to the rules too (red under: drop `and first_<strain>[side] is none` from
`submit_bid`'s effect — the last bidder becomes declarer and the wrong hand
is laid down).

Two choosers drive it. A uniform draw exercises the redoubled-undertrick tier
(x4 -> 400/200) heavily and ends almost every rubber at the deal bound. A uniform
bidder almost never MAKES a slam, so an aimed chooser — one that reads every
hand, bids the stronger side's longest suit to a set level, and has the
defenders throw their tricks — makes small and grand slams, vulnerable and
not, so both slam arms are executed and their bonuses held to Pagat's figures
(red under: restore a `when:` level cap below 6 on `submit_bid`, or change a
slam bonus). Aimed at one-level contracts it leaves part scores and single
games standing when play stops, which reaches both unfinished-rubber bonuses,
and it finishes rubbers at their second game. The aimed chooser is an
instrument for reaching those arms, not a Playout Policy: it reads hands no
seat can see.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, Player

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"
TEAM = {0: 0, 2: 0, 1: 1, 3: 1}  # teams [[0, 2], [1, 3]]
STRAIN_INDEX = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3, None: 4}
AUCTION_WORDS = {"pass", "double", "redouble", "submit_bid"}
SUITS = ("clubs", "diamonds", "hearts", "spades")
DEAL_BOUND = 12  # the rubber stops after twelve deals if it is unfinished


def _per_trick(strain: str | None) -> int:
    if strain is None:
        return 30  # no-trump
    return 20 if strain in ("clubs", "diamonds") else 30


class _Auction:
    """The bidding, re-derived from announcements: the cheapest level that
    beats the standing bid in a strain, doubling, and the closing passes."""

    def __init__(self) -> None:
        self.level = 0
        self.strain: str | None = None
        self.high: int | None = None
        self.doubled = 1
        self.passes = 0
        self.made_bid = False
        self.first_namer: dict[tuple[int, str | None], int] = {}

    def hear(self, actor: int, text: str) -> None:
        m = re.fullmatch(r"submit_bid(?:\((\w+)\))?", text)
        if m:
            strain = m.group(1)
            if self.level == 0:
                level = 1
            elif STRAIN_INDEX[strain] > STRAIN_INDEX[self.strain]:
                level = self.level
            else:
                level = self.level + 1
            self.level, self.strain, self.high = level, strain, actor
            self.doubled, self.made_bid, self.passes = 1, True, 0
            self.first_namer.setdefault((TEAM[actor], strain), actor)
        elif text == "double":
            self.doubled, self.passes = 2, 0
        elif text == "redouble":
            self.doubled, self.passes = 4, 0
        elif text == "pass":
            self.passes += 1

    @property
    def closed(self) -> bool:
        return (self.made_bid and self.passes >= 3) or (not self.made_bid and self.passes >= 4)

    def contract(self) -> dict[str, Any]:
        if not self.made_bid:
            return {"all_pass": True}
        assert self.high is not None
        return {
            "all_pass": False,
            "declarer_team": TEAM[self.high],
            "declarer": self.first_namer[(TEAM[self.high], self.strain)],
            "level": self.level,
            "strain": self.strain,
            "doubled_mult": self.doubled,
        }


def _recompute(
    game: Any,
    seed: int,
    chooser: Any = None,
    on_first_decision: Any = None,
    tap: Any = None,
) -> Counter[Any]:
    """Play one rubber and hold every hand's totals, and the final result, to
    the independent recompute. Returns the census of scoring arms reached."""
    census: Counter[Any] = Counter()
    events: list[tuple[str, Any]] = []

    def tracer(event: str, data: Any) -> None:
        if tap is not None:
            tap(event, data)
        if event in ("trick", "hand_end"):
            events.append((event, data))

    def observer(player: int, event: tuple[Any, ...]) -> None:
        # Seat 0 hears every announcement; the auction's are the ones in
        # its vocabulary (a card play announces a card, never a bid word).
        if player != 0:
            return
        if event[0] == "announce":
            text = str(event[2])
            if text.split("(")[0] in AUCTION_WORDS:
                events.append(("bid", (int(event[1]), text)))
        elif event[0] == "move" and str(event[3]).startswith("dummy_hand["):
            # The dummy lays their hand down: the game's own statement of
            # who declares, since dummy is the declarer's partner.
            laid = re.fullmatch(r"hand\[(\d)\]", str(event[1]))
            assert laid is not None, event
            events.append(("dummy", int(laid.group(1))))

    result = play_game(
        game, random.Random(seed), tracer, chooser=chooser,
        observer=observer, on_first_decision=on_first_decision,
    )

    games_won = {0: 0, 1: 0}
    below = {0: 0, 1: 0}
    total = {0: 0, 1: 0}
    contract: dict[str, Any] | None = None
    tricks = {0: 0, 1: 0}
    auction: _Auction | None = None
    deals = 0

    for kind, data in events:
        if kind == "bid":
            if auction is None or auction.closed:
                auction = _Auction()
                contract = None
            auction.hear(*data)
            if auction.closed:
                contract = auction.contract()
                tricks = {0: 0, 1: 0}
        elif kind == "dummy":
            assert contract is not None and not contract["all_pass"]
            assert (data + 2) % 4 == contract["declarer"], (
                f"seed {seed}: dummy is seat {data}, so the game's declarer is "
                f"{(data + 2) % 4}, but the first seat of the declaring side "
                f"to name {contract['strain']} was {contract['declarer']}"
            )
        elif kind == "trick":
            tricks[TEAM[data[0]]] += 1
        elif kind == "hand_end":
            assert contract is not None
            assert max(games_won.values()) < 2, f"seed {seed}: a deal after the rubber ended"
            deals += 1
            if not contract["all_pass"]:
                dt = contract["declarer_team"]
                ot = 1 - dt
                level, dm, strain = contract["level"], contract["doubled_mult"], contract["strain"]
                assert 1 <= level <= 7, f"seed {seed}: a level-{level} contract"
                required = 6 + level
                actual = tricks[dt]
                vuln = games_won[dt] >= 1
                pt = _per_trick(strain)
                if actual >= required:
                    nt_bonus = 10 if strain is None else 0
                    b = (pt * level + nt_bonus) * dm
                    total[dt] += b
                    below[dt] += b
                    over = actual - required
                    ov = pt if dm == 1 else (200 if vuln else 100) if dm == 2 else (400 if vuln else 200)
                    total[dt] += ov * over
                    if level == 6:
                        total[dt] += 750 if vuln else 500
                        census[("small slam", vuln)] += 1
                    if level == 7:
                        total[dt] += 1500 if vuln else 1000
                        census[("grand slam", vuln)] += 1
                    if below[dt] >= 100:
                        total[dt] += 500 if vuln else 300
                        games_won[dt] += 1
                        below[dt] = 0
                        below[ot] = 0
                        if games_won[dt] >= 2:
                            total[dt] += 700 if games_won[ot] == 0 else 500
                else:
                    under = required - actual
                    pu = (100 if vuln else 50) if dm == 1 else (200 if vuln else 100) if dm == 2 else (400 if vuln else 200)
                    total[ot] += pu * under
                    if dm == 4:
                        census["redoubled down"] += 1
            # The traced hand_end carries the runtime's total_score per team.
            assert data == total, f"seed {seed}: recompute {total} != runtime {data}"
            contract = None

    # The rubber ends at its second game, or play stops at the deal bound
    # with the rubber unfinished: a side with a game scores 300, a side with a
    # part score toward the uncompleted game 100.
    if max(games_won.values()) >= 2:
        census["rubber finished"] += 1
        assert deals <= DEAL_BOUND, f"seed {seed}: {deals} deals"
    else:
        assert deals == DEAL_BOUND, f"seed {seed}: unfinished after {deals} deals"
        for t in (0, 1):
            if games_won[t] == 1:
                total[t] += 300
                census["unfinished: game"] += 1
            if below[t] > 0:
                total[t] += 100
                census["unfinished: part score"] += 1
    assert result.scores == total, f"seed {seed}: recompute {total} != result {result.scores}"
    return census


def test_bridge_scoring_matches_independent_recompute() -> None:
    game = check_source(BRIDGE)
    census: Counter[Any] = Counter()
    for seed in range(25):
        census += _recompute(game, seed)
    # The redoubled-undertrick tier is genuinely exercised (not a vacuous pass).
    assert census["redoubled down"] > 0, census


def _beats(card: Card, best: Card, trump: str | None) -> bool:
    if card.suit == best.suit:
        return card.rank_order > best.rank_order
    return card.suit == trump


class _SlamAimer:
    """Bids the stronger side's longest suit to `level` and plays it out with
    the defenders throwing their tricks.

    Each deal, the side with more high-card points declares in the suit the
    side holds most of: its seats bid that suit each turn until the standing
    bid reaches `level`, and every other call is a pass. In play the declaring
    side wins each trick as cheaply as it can and leads its best card, trumps
    first; the defenders play their lowest card, keeping their trumps.
    """

    HCP = {"A": 4, "K": 3, "Q": 2, "J": 1}

    def __init__(self, level: int) -> None:
        self.level = level
        self.rs: RuntimeState | None = None
        self.plan: tuple[int, str] | None = None
        self.trick: list[tuple[Player, Card]] = []

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def tap(self, event: str, data: Any) -> None:
        if event == "play":
            self.trick.append(data)
        elif event == "trick":
            self.trick = []
        elif event == "hand_end":
            self.plan = None

    def _hand(self, seat: int) -> list[Card]:
        assert self.rs is not None
        return self.rs.zones.instance("hand", seat).cards

    def _plan(self) -> tuple[int, str]:
        def points(team: int) -> int:
            return sum(self.HCP.get(c.rank, 0) for s in (team, team + 2) for c in self._hand(s))

        team = max((0, 1), key=points)
        strain = max(
            SUITS,
            key=lambda s: sum(1 for p in (team, team + 2) for c in self._hand(p) if c.suit == s),
        )
        return team, strain

    def __call__(self, player: Player, candidates: list[Any], n: int) -> list[Any]:
        assert n == 1 and self.rs is not None
        if isinstance(candidates[0], tuple):
            if self.plan is None:
                self.plan = self._plan()
            team, strain = self.plan
            bid = ("submit_bid", strain)
            if TEAM[player] == team and bid in candidates and self.rs.get("cur_level") < self.level:
                return [bid]
            return [("pass", None)]
        assert self.plan is not None
        return [self._card(player, candidates, *self.plan)]

    def _card(self, player: Player, candidates: list[Card], team: int, trump: str) -> Card:
        def cheapest(cards: list[Card]) -> Card:
            return min(cards, key=lambda c: (c.suit == trump, c.rank_order))

        if TEAM[player] != team:
            return cheapest(candidates)
        if not self.trick:
            return max(candidates, key=lambda c: (c.suit == trump, c.rank_order))
        winner, best = self.trick[0]
        for seat, card in self.trick[1:]:
            if _beats(card, best, trump):
                winner, best = seat, card
        if TEAM[winner] == team:
            return cheapest(candidates)
        taking = [c for c in candidates if _beats(c, best, trump)]
        return cheapest(taking or candidates)


def test_aimed_slams_score_as_pagat_states() -> None:
    game = check_source(BRIDGE)
    census: Counter[Any] = Counter()
    for level in (1, 6, 7):
        for seed in range(12):
            aimer = _SlamAimer(level)
            census += _recompute(
                game, seed, chooser=aimer, on_first_decision=aimer.attach, tap=aimer.tap
            )
    for slam in ("small slam", "grand slam"):
        for vuln in (False, True):
            assert census[(slam, vuln)] > 0, f"no {slam} made {'' if vuln else 'non-'}vulnerable: {census}"
    # Both ways a rubber stops are reached, and both unfinished-rubber bonuses.
    for cell in ("rubber finished", "unfinished: game", "unfinished: part score"):
        assert census[cell] > 0, f"{cell!r} never reached: {census}"
