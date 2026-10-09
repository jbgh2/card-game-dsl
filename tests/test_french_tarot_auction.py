"""French Tarot's four-level auction on the kernel round, both outcome arms
pinned independently of RNG luck.

The byte-identical characterization golden exercises both arms across its random
seeds, but that coverage rests on the seed set. These drive the two arms
deterministically with an injected chooser:

- every seat passes -> the hand is thrown in (re-dealt, no taker);
- the opener bids petite -> he is the taker at level 1.
"""

from __future__ import annotations

import random
from pathlib import Path
import re
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

TAROT = (
    Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"
).read_text()

# dealer starts 0; before_each advances it counterclockwise (offset_by right) to
# 3, so the opener (dealer's right, the first bidder) is seat 2.
FIRST_OPENER = 2


def _auction_move(candidates: list[Any], name: str) -> Any | None:
    for c in candidates:
        if isinstance(c, tuple) and c[0] == name:
            return c
    return None


def _capture_contracts(game: Any, want_first_bid: str | None) -> list[dict[str, Any]]:
    """Play one game, choosing `want_first_bid` (a move name) at the very first
    auction turn and passing at every later auction turn; non-auction decisions
    (chien discard, trick cards) take the first `n` candidates. Returns the
    contracts the auctions settled, re-derived from the announcements."""
    contracts: list[dict[str, Any]] = []
    bid_done = [False]

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        if candidates and isinstance(candidates[0], tuple):  # an auction turn
            if want_first_bid is not None and not bid_done[0]:
                pick = _auction_move(candidates, want_first_bid)
                if pick is not None:
                    bid_done[0] = True
                    return [pick]
            passit = _auction_move(candidates, "pass")
            return [passit if passit is not None else candidates[0]]
        return list(candidates[:n])

    # Two streams, kept in order: what seat 0 hears announced, and where the
    # chien goes. The chien's destination is the game's own consequence of
    # the `produce`d outcome — `move all cards from chien to hand[taker]` on
    # `taken`, back to the deck on `thrown_in` — so a contract re-derived from
    # the bids is held against what the game then did with it, not only
    # against the chooser's own inputs.
    heard: list[tuple[str, int | str, str]] = []

    def observer(player: int, event: tuple[Any, ...]) -> None:
        if player != 0:
            return
        if event[0] == "announce":
            heard.append(("announce", int(event[1]), str(event[2])))
        elif event[0] == "move" and event[1] == "chien":
            heard.append(("chien", str(event[3]), ""))

    play_game(game, random.Random(0), chooser=chooser, observer=observer)
    # Each auction is a run of bid-vocabulary announcements; its contract is
    # the last bid heard, or a thrown-in hand when nobody bid, and the chien
    # movement that follows says where the game sent the chien.
    levels = {"bid_petite": 1, "bid_garde": 2, "bid_garde_sans": 3, "bid_garde_contre": 4}
    in_auction = False
    taker: tuple[int, int] | None = None

    def close(chien_to: str) -> None:
        seat = re.fullmatch(r"hand\[(\d+)\]", chien_to)
        contracts.append(
            {"thrown_in": True, "chien_to": chien_to} if taker is None
            else {
                "thrown_in": False,
                "taker": taker[0],
                "level": taker[1],
                "chien_to": int(seat.group(1)) if seat else chien_to,
            }
        )

    for kind, actor, text in heard:
        if kind == "announce" and (text in levels or text == "pass"):
            in_auction = True
            if text in levels:
                assert isinstance(actor, int)
                taker = (actor, levels[text])
        elif kind == "chien" and in_auction:
            assert isinstance(actor, str)
            close(actor)
            in_auction, taker = False, None
    if in_auction:
        # The game ended inside the last auction: on an all-pass final hand
        # there is no next deal to gather the chien, so no movement follows.
        assert taker is None, "a taken auction closed with no chien movement"
        contracts.append({"thrown_in": True, "chien_to": None})
    return contracts


def test_all_pass_throws_the_hand_in() -> None:
    """red under: `produce taken(0, 1)` on the all-pass arm — the chien goes
    to a hand instead of back to the deck."""
    game = check_dsl(TAROT, "french-tarot.cardlang")
    contracts = _capture_contracts(game, want_first_bid=None)
    assert contracts, "no auction ran"
    assert contracts[0] == {"thrown_in": True, "chien_to": "deck"}


def test_opening_petite_makes_the_opener_taker_at_level_one() -> None:
    """The taker the bids name is the seat the game then hands the chien to.
    The level has no observation of its own: its witness is the per-seed
    scores golden (tests/test_migration_characterization.py), where a wrong
    multiplier moves every taken hand's score.

    red under: `produce taken(lead_taker offset_by left, current_level)` —
    the chien goes to the wrong hand."""
    game = check_dsl(TAROT, "french-tarot.cardlang")
    contracts = _capture_contracts(game, want_first_bid="bid_petite")
    assert contracts, "no auction ran"
    assert contracts[0] == {
        "thrown_in": False,
        "taker": FIRST_OPENER,
        "level": 1,
        "chien_to": FIRST_OPENER,
    }
