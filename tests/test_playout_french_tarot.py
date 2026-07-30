"""Random-playout harness for French Tarot.

Tarot is the corpus's first non-uniform deck (78 cards: four 14-card suits, 21
atouts, the Excuse). Falsifiable invariants: card conservation (78 cards), a
fixed 36 hands, per-trick winner correctness (highest atout wins, else highest
of the led suit, and the Excuse never wins), and the zero-sum bouts/multiplier
settlement — recomputed independently per hand from the driver's own
`hand_end` cumulative-score snapshots (never a mechanic-internal trace): each
hand's delta is either all-zero (thrown in) or {+3x, -x, -x, -x} for some
taker and per-opponent amount x.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

TAROT = Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"
_SUIT_STR = {"K": 14, "Q": 13, "C": 12, "J": 11}


def _tarot() -> Any:
    return check_source(TAROT)


def _suit_strength(c: Card) -> int:
    return _SUIT_STR.get(c.rank, 0) or int(c.rank)


def _winner(group: list[tuple[int, Card]]) -> int:
    atouts = [(p, c) for p, c in group if c.suit == "atouts"]
    if atouts:
        return max(atouts, key=lambda pc: int(pc[1].rank))[0]
    led = next(c.suit for _, c in group if c.suit != "excuse")
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: _suit_strength(pc[1]))[0]


# What the sweep's own assertions BRANCH on. Each is a distinct arm some
# assertion below would otherwise check vacuously — an all-zero hand delta
# never seen means the thrown-in arm went unexercised, no Excuse ever played
# means "the Excuse never wins" proved nothing. Asserted exhaustively after
# the sweep, so the seed count is a claim rather than a habit.
SETTLEMENT_ARMS = frozenset(
    {"hand_thrown_in", "taker_made_it", "taker_missed",
     "trick_won_on_atout", "trick_won_on_led_suit", "excuse_played"}
)

# Every arm must fire on at least this many DISTINCT seeds. One witness would
# be satisfiable by a single lucky deal, which is what makes a seed count
# unfalsifiable — with three, the count is load-bearing and a cut reddens.
WITNESS_SEEDS = 3

# Derived from that: a 36-hand match saturates five of the six arms on its
# first seed, so the binding arm is `hand_thrown_in` (an all-pass auction),
# which lands in 15 of 40 seeds — here on seeds 0, 4, 5, 6 and 9. Six seeds is
# the minimum that witnesses it three times; ten leaves headroom for a game
# change that shifts one arm off the early seeds.
#
# red under: SEEDS = 5 (`hand_thrown_in` drops to two witness seeds).
SEEDS = 10


def test_random_games_satisfy_invariants() -> None:
    game = _tarot()
    witnesses: dict[str, set[int]] = {}
    for seed in range(SEEDS):
        arms: set[str] = set()
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        hand_ends = 0
        hand_end_scores: list[dict[int, int]] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            nonlocal hand_ends
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "hand_end":
                hand_ends += 1
                hand_end_scores.append(dict(data))  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        assert hand_ends == 36
        assert sum(result.scores.values()) == 0  # zero-sum
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])
        assert census["total"] == 78, f"seed {seed}: {census}"

        # Independent per-hand settlement recompute, from the driver's own
        # cumulative `hand_end` snapshots (dict(score) after each hand) — never
        # a mechanic-internal trace. Each hand's delta is either all-zero (a
        # thrown-in hand skips scoring entirely) or the zero-sum {3d, -d, -d,
        # -d} shape for some taker and per-opponent amount `d` — `d` may be
        # NEGATIVE (the taker misses the bid: the taker pays 3x and each
        # opponent collects x, sign-flipped from the taker-succeeds case), so
        # this does not presuppose which side gains.
        prev = {p: 0 for p in range(4)}
        for hand_no, snapshot in enumerate(hand_end_scores):
            delta = {p: snapshot[p] - prev[p] for p in range(4)}
            prev = snapshot
            if all(d == 0 for d in delta.values()):
                arms.add("hand_thrown_in")
                continue
            counts: dict[int, int] = {}
            for d in delta.values():
                counts[d] = counts.get(d, 0) + 1
            shared = [d for d, c in counts.items() if c == 3]
            assert len(shared) == 1, (seed, hand_no, delta)
            per_opp = shared[0]
            taker = next(p for p, d in delta.items() if d != per_opp)
            assert delta[taker] == -3 * per_opp, (seed, hand_no, delta)
            # `per_opp` is what each opponent's score MOVED by, so a negative
            # one is the taker collecting: both arms, never presupposed.
            arms.add("taker_made_it" if per_opp < 0 else "taker_missed")

        assert len(plays) == 4 * len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _winner(group), f"seed {seed} trick {i}"
            arms.add(
                "trick_won_on_atout"
                if any(c.suit == "atouts" for _, c in group)
                else "trick_won_on_led_suit"
            )
            # The Excuse never wins a trick — vacuous unless one was played,
            # which the arm below is what makes checkable.
            if any(c.suit == "excuse" for _, c in group):
                arms.add("excuse_played")
            won_card = next(c for p, c in group if p == winner)
            assert won_card.suit != "excuse"

        for arm in arms:
            witnesses.setdefault(arm, set()).add(seed)

    assert set(witnesses) == SETTLEMENT_ARMS, (
        f"the {SEEDS}-seed sweep no longer exercises "
        f"{sorted(SETTLEMENT_ARMS - set(witnesses))} — the assertions guarding "
        f"those arms are now vacuous. Raise SEEDS until they fire again, or, if "
        f"an arm has become unreachable, say why here rather than dropping it."
    )
    thin = {a: sorted(s) for a, s in witnesses.items() if len(s) < WITNESS_SEEDS}
    assert not thin, (
        f"{thin} fire on fewer than {WITNESS_SEEDS} of the {SEEDS} seeds — the "
        f"seed count no longer carries the arm it was derived from"
    )
