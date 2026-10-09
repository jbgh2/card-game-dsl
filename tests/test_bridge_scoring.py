"""Independent recompute of Bridge scoring, driving the real bridge.cardlang.

Bridge's scoring lives in the DSL, so this drives actual games and recomputes
every hand's score from the contract and the trick winners, mirroring the
scoring rules in Python, then asserts the recomputed running totals match the
traced `hand_end` totals after every hand. The contract is itself recomputed,
from the auction's announcements as every seat hears them: the standing bid,
its strain, the doubling, the closing passes and the declarer — the first
seat of the declaring side to name the final strain — are re-derived here from
the bids, and the declarer is held against the seat the game then exposes as
dummy (the declarer's partner), so the game's own bidding bookkeeping is held
to the rules too (red under: drop `and first_<strain>[side] is none` from
`submit_bid`'s effect — the last bidder becomes declarer and the wrong hand
is laid down). This
pins the whole scoring system — in particular the redoubled-undertrick tier
(x4 -> 400/200), which random play exercises heavily — so a regression in any
branch makes the recompute diverge and the test fail.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"
TEAM = {0: 0, 2: 0, 1: 1, 3: 1}  # teams [[0, 2], [1, 3]]
STRAIN_INDEX = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3, None: 4}
AUCTION_WORDS = {"pass", "double", "redouble", "submit_bid"}


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


def test_bridge_scoring_matches_independent_recompute() -> None:
    game = check_source(BRIDGE)
    redoubled_down = 0
    for seed in range(25):
        events: list[tuple[str, Any]] = []

        def tracer(event: str, data: Any) -> None:
            if event in ("trick", "hand_end"):
                events.append((event, data))  # noqa: B023 -- consumed before the loop advances

        def observer(player: int, event: tuple[Any, ...]) -> None:
            # Seat 0 hears every announcement; the auction's are the ones in
            # its vocabulary (a card play announces a card, never a bid word).
            if player != 0:
                return
            if event[0] == "announce":
                text = str(event[2])
                if text.split("(")[0] in AUCTION_WORDS:
                    events.append(("bid", (int(event[1]), text)))  # noqa: B023
            elif event[0] == "move" and str(event[3]).startswith("dummy_hand["):
                # The dummy lays their hand down: the game's own statement of
                # who declares, since dummy is the declarer's partner.
                laid = re.fullmatch(r"hand\[(\d)\]", str(event[1]))
                assert laid is not None, event
                events.append(("dummy", int(laid.group(1))))  # noqa: B023

        play_game(game, random.Random(seed), tracer, observer=observer)

        games_won = {0: 0, 1: 0}
        below = {0: 0, 1: 0}
        total = {0: 0, 1: 0}
        contract: dict[str, Any] | None = None
        tricks = {0: 0, 1: 0}
        auction: _Auction | None = None

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
                if not contract["all_pass"]:
                    dt = contract["declarer_team"]
                    ot = 1 - dt
                    level, dm, strain = contract["level"], contract["doubled_mult"], contract["strain"]
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
                        if level == 7:
                            total[dt] += 1500 if vuln else 1000
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
                            redoubled_down += 1
                # The traced hand_end carries the runtime's total_score per team.
                assert data == total, f"seed {seed}: recompute {total} != runtime {data}"
                contract = None

    # The redoubled-undertrick tier is genuinely exercised (not a vacuous pass).
    assert redoubled_down > 0
