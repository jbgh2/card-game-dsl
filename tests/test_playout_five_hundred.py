"""Random-playout harness for 500, plus a characterization pin.

500 has three trick structures: suit contracts (joker + right bower + left
bower head the trump suit, and the left bower changes effective suit),
no-trumps (the joker suitless or nominated into a suit), and the misères
(three-handed — the declarer's partner sits out — with inverse scoring).
The falsifiable check recomputes every trick's winner from the cards played
and the contract recorded in the trace, so a wrong bower ordering, a missed
effective-suit remap, a wrong joker rule, or a wrong misère seat-skip turns
it red. Plus deck integrity (43 cards), the champion invariant (the game
ends only on a contract win crossing +500 or a side out backwards at -500),
and misère's three-card tricks.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

FIVE_HUNDRED = Path(__file__).parent.parent / "docs" / "games" / "five-hundred.cardlang"

_RANK = {"A": 11, "K": 10, "Q": 9, "J": 8, "10": 7, "9": 6, "8": 5, "7": 4, "6": 3, "5": 2, "4": 1}
_MATE = {"spades": "clubs", "clubs": "spades", "hearts": "diamonds", "diamonds": "hearts"}


def _is_trump(c: Card, trump: str) -> bool:
    return c.suit == "joker" or c.suit == trump or (c.rank == "J" and c.suit == _MATE[trump])


def _cls(c: Card, trump: str | None, joker_suit: str | None) -> str:
    if trump is not None:
        return "trump" if _is_trump(c, trump) else c.suit
    if c.suit == "joker":
        return joker_suit if joker_suit is not None else "joker"
    return c.suit


def _winner(group: list[tuple[int, Card]], trump: str | None, joker_suit: str | None) -> int:
    led = _cls(group[0][1], trump, joker_suit)
    if trump is not None:
        trumps = [(p, c) for p, c in group if _is_trump(c, trump)]
        if trumps:
            def strength(c: Card) -> int:
                if c.suit == "joker":
                    return 1000
                if c.rank == "J" and c.suit == trump:
                    return 999
                if c.rank == "J" and c.suit == _MATE[trump]:
                    return 998
                return _RANK[c.rank]
            return max(trumps, key=lambda pc: strength(pc[1]))[0]
        of_led = [(p, c) for p, c in group if c.suit == led]
        return max(of_led, key=lambda pc: _RANK[pc[1].rank])[0]
    jokers = [(p, c) for p, c in group if c.suit == "joker"]
    if jokers and joker_suit is None:
        return jokers[0][0]
    of_led = [(p, c) for p, c in group if _cls(c, trump, joker_suit) == led]
    return max(of_led, key=lambda pc: 100 if pc[1].suit == "joker" else _RANK[pc[1].rank])[0]


def _run(seed: int) -> dict[str, Any]:
    game = check_source(FIVE_HUNDRED)
    plays: list[tuple[int, Card]] = []
    tricks: list[tuple[int, list[Card]]] = []
    contracts: list[dict[str, Any]] = []
    hand_scores: list[dict[int, int]] = []
    rs_box: list[Any] = []
    census: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "play":
            plays.append(data)
        elif event == "trick":
            tricks.append(data)
        elif event == "trick_end":
            contracts.append(data)
        elif event == "hand_end" and rs_box:
            hand_scores.append(dict(rs_box[0].get("score")))
        elif event == "game_end":
            census.clear()
            census.update(data)

    result = play_game(
        game, random.Random(seed), tracer, on_first_decision=lambda rs: rs_box.append(rs)
    )
    return {
        "result": result,
        "plays": plays,
        "tricks": tricks,
        "contracts": contracts,
        "hand_scores": hand_scores,
        "census": census,
    }


def test_40_random_games_satisfy_invariants() -> None:
    misere_seen = 0
    for seed in range(40):
        out = _run(seed)
        result, census = out["result"], out["census"]
        assert census["total"] == 43, f"seed {seed}: {census}"

        # Exactly one champion, fixed by the scoring rules: a contract win
        # crossing +500, or the other side out backwards at -500.
        final = out["hand_scores"][-1]
        assert result.winner is not None
        loser = 1 - result.winner
        assert final[result.winner] >= 500 or final[loser] <= -500, f"seed {seed}: {final}"

        # Trick shape: three cards under a misère (the declarer's partner
        # sits out — three DISTINCT seats), four otherwise; each trick's
        # winner recomputed independently from the played cards and the
        # traced contract.
        i = 0
        for (winner, cards), meta in zip(out["tricks"], out["contracts"]):
            size = 3 if meta["misere"] else 4
            group = out["plays"][i : i + size]
            i += size
            assert [c for _, c in group] == list(cards), f"seed {seed}"
            assert len({p for p, _ in group}) == size, f"seed {seed}: {group}"
            assert winner == _winner(group, meta["trump"], meta["joker_suit"]), (
                f"seed {seed} trick {meta}: {group}"
            )
            if meta["misere"]:
                misere_seen += 1
        assert i == len(out["plays"])
    # The misère family is reachable under random bidding (seeds 10/22/29
    # hit it today); a vanishing count means the auction guards broke.
    assert misere_seen > 0


def test_seed0_characterization() -> None:
    # Byte-identity pin for a whole game: any change to the constructs'
    # decision sequence (auction ring order, guard-filtered candidate order,
    # chosen-movement pool order, offer order) moves this vector. Measured
    # hash-independent (identical under PYTHONHASHSEED 0/1/7): every
    # collection on the decision path is ordered (seating rings, hand-order
    # pools, the declaration-order action space). The vector also depends on
    # the canonical gather order (`move all cards to deck` collects zones in
    # sorted-name order), which feeds the pre-shuffle deck permutation.
    out = _run(0)
    assert out["result"].winner == 1
    assert out["hand_scores"] == [{0: -520, 1: 70}]
    assert len(out["tricks"]) == 10
    meta = out["contracts"][0]
    assert (meta["trump"], meta["misere"], meta["joker_suit"]) == (None, False, None)
