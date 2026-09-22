"""Playout harness for Pinochle.

Pinochle is the corpus's first auction + melding game, on the 48-card double
pack (A 10 K Q J 9). Falsifiable invariants: card/value conservation (48 cards,
240 counter points), per-trick winner correctness against the pinochle rank
order and trump, and trick-point reconciliation — every hand that is actually
played out distributes exactly 250 trick points (240 in counters + 10 for the
last trick). A wrong rank order, value table, or last-trick award turns these red.

The playout drives the game through a REFERENCE POLICY, not the uniform
chooser. A uniform chooser bids jumps of any size up to the declared ceiling and
concedes about half the hands it could play, so both sides go set hand after
hand and their scores fall without bound: measured on this tree, 0 of 30 uniform
lines reach a result within 20,000 decisions (2026-09-21). That is not a defect
of the game — it is what a table of indiscriminate bidders would produce at a
real one — so the game text stays faithful (CLAUDE.md, "The game does not bend
to the harness") and the play-style assumption lives here.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Player

PINOCHLE = Path(__file__).parent.parent / "docs" / "games" / "pinochle.cardlang"

# pinochle48 strength, low to high: 9 J Q K 10 A.
RANK = {r: i for i, r in enumerate(("9", "J", "Q", "K", "10", "A"))}

# Pinochle's card-point table (A/10/K = 10; Q/J/9 = 0) — the same table
# `card_points(c)` reads at runtime (pinochle.cardlang's `card_points { }`
# clause). Duplicated here (not parsed out of the game file) so the recompute
# below is an independent oracle for the code it checks.
COUNTER_VALUE = {"A": 10, "10": 10, "K": 10}


# The play-style this harness assumes, and the whole of it. Each number is a
# rate per offer, not a read of the hand: a policy that judged hands would be a
# player, and what is wanted here is the smallest assumption that makes a game
# of Pinochle finish so the invariants above have lines to run on.
#
# - `BID_RATE`: a seat bids about three times in ten that it may. Real auctions
#   end near the minimum, because a contract is only worth taking on a hand
#   that can make it.
# - `JUMP_RATE` and `JUMP_RUNGS`: a bidder jumps about one bid in ten, by two to
#   five rungs (Pagat's jump is "at least 20 above the last"). Jumping to the
#   ceiling is legal and nobody does it, so a uniform draw over the remaining
#   range is the one thing that must not happen here.
# - `THROW_RATE`: a declarer concedes about one hand in fifty. Pagat gives the
#   throw-in to a declarer with "absolutely no chance", which is rare.
#
# Measured under exactly these rates, 250 seeds, 2026-09-21: every line
# finishes, median 952 decisions, p99 2,749, max 3,517, and no contract above
# 400. `max_length` in the game file is sized from that maximum.
BID_RATE = 0.30
JUMP_RATE = 0.10
JUMP_RUNGS = 4
THROW_RATE = 0.02


def pinochle_reference_policy(
    rng: random.Random,
) -> Callable[[Player, list[Any], int], list[Any]]:
    """The playout policy: uniform play except at the auction's three decisions
    and the declarer's concession, which are gated at the rates above.

    It reads nothing but the candidate list and its own rng — no hand, no
    score — so it cannot consult a seat's private zones even in principle, and
    the projection contract `tests/playout_policy.py` states for the shared
    policy holds here by construction rather than by inspection.
    """
    base = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        names = {c[0]: c for c in candidates if isinstance(c, tuple) and c}
        if "throw_in" in names:
            concede = rng.random() < THROW_RATE
            return [names["throw_in"] if concede else names["play_on"]]
        if "submit_bid" in names or "pass" in names:
            if "submit_bid" in names and rng.random() < BID_RATE:
                return [names["submit_bid"]]
            # Both ways out are the same to this policy; `pass_with_help` is a
            # signal to a partner it does not model. It is taken when the rung
            # is the top one, where `submit_bid` is withheld and `pass` may be
            # the only name present.
            return [names.get("pass") or names["pass_with_help"]]
        if n == 1 and candidates and isinstance(candidates[0], int):
            # The bid amount, in rungs above the standing bid.
            lowest = min(candidates)
            if rng.random() < JUMP_RATE:
                return [min(lowest + rng.randint(1, JUMP_RUNGS), max(candidates))]
            return [lowest]
        return base(player, candidates, n)

    return chooser


def _pinochle() -> Any:
    return check_source(PINOCHLE)


def _expected_winner(group: list[tuple[int, Card]], trump: str) -> int:
    led = group[0][1].suit
    trumps = [(p, c) for p, c in group if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: RANK[pc[1].rank])[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: RANK[pc[1].rank])[0]


def test_150_random_games_satisfy_invariants() -> None:
    game = _pinochle()
    for seed in range(150):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        trumps: list[str] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick_end":
                trumps.append(data["trump"])  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        rng = random.Random(seed)
        result = play_game(game, rng, tracer, chooser=pinochle_reference_policy(rng))

        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert max(result.scores.values()) >= 1500

        # Card and counter-value conservation.
        assert census["total"] == 48, f"seed {seed}: {census}"
        assert census["total_value"] == 240, f"seed {seed}: {census}"

        # Four plays per trick; winner correct against rank order and trump.
        assert len(plays) == 4 * len(tricks)
        assert len(trumps) == len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _expected_winner(group, trumps[i]), f"seed {seed} trick {i}"

        # Every played-out hand distributes exactly 250 trick points (240 in
        # counters + 10 for the last trick). Recomputed from the traced `trick`
        # events (winner + the 4 played cards) rather than a mechanic-local
        # trace, so the check survives trick play leaving `instantiate` for the
        # kernel (docs/kernel-migration.md). A played hand contributes exactly
        # 12 consecutive `trick` events and an abandoned one contributes none,
        # so the flat per-game sequence still divides evenly into hands; `team
        # = player % 2` follows from `teams: [[0, 2], [1, 3]]`, and each
        # trick's `winner` is independently pinned against `_expected_winner`
        # above.
        assert len(tricks) % 12 == 0, f"seed {seed}: {len(tricks)} tricks, not hand-aligned"
        for start in range(0, len(tricks), 12):
            hand_tricks = tricks[start : start + 12]
            trick_points = {0: 0, 1: 0}
            for winner, cards in hand_tricks:
                trick_points[winner % 2] += sum(COUNTER_VALUE.get(c.rank, 0) for c in cards)
            trick_points[hand_tricks[-1][0] % 2] += 10  # ten for the last trick
            assert sum(trick_points.values()) == 250, f"seed {seed} hand at trick {start}: {trick_points}"
