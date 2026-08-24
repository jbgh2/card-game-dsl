"""Random-playout harness for Spades.

Spades is the first team trump game on the runtime. Its invariants
exercise the seams Hearts/Getaway never touched: a value (integer-bid) decision,
a trump-aware trick winner, and team-indexed capture/scoring. The trump check is
the one that would go red under a wrong outcome function — it recomputes each
trick's winner from the cards played and compares against what the runtime chose.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.policy import PlayoutPolicy
from cardlang.runtime.values import Card

SPADES = Path(__file__).parent.parent / "docs" / "games" / "spades.cardlang"


def _spades() -> Any:
    return check_source(SPADES)


def _expected_winner(group: list[tuple[int, Card]]) -> int:
    """The trick winner under Spades rules: highest spade if any spade was
    played, otherwise the highest card of the led suit."""
    led = group[0][1].suit
    spades = [(p, c) for p, c in group if c.suit == "spades"]
    if spades:
        return max(spades, key=lambda pc: pc[1].rank_order)[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: pc[1].rank_order)[0]


def test_200_random_games_satisfy_invariants() -> None:
    game = _spades()
    for seed in range(200):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Terminates at a real threshold, and the winner is the top-scoring team.
        assert result.winner in (0, 1)
        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert max(result.scores.values()) >= 500 or min(result.scores.values()) <= -200

        # Conservation: all 52 cards still exist; no hand holds cards at the end.
        assert census["total"] == 52, f"seed {seed}: census {census}"
        assert census["hands_with_cards"] == 0

        # 13 tricks per hand, four plays per trick.
        assert len(tricks) == 13 * result.hands_played
        assert len(plays) == 4 * len(tricks)

        # Trump resolution: every trick was won by the right player.
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert len(group) == 4
            assert {p for p, _ in group} == {0, 1, 2, 3}  # all four play once
            assert winner == _expected_winner(group), f"seed {seed}, trick {i}"
            assert [c for _, c in group] == cards


# --- the +500 witness -----------------------------------------------------
#
# The assertion above — `max(...) >= 500 or min(...) <= -200` — is a
# disjunction only ever satisfied by its right arm: uniform-random bidding
# draws over 0..13, so both teams systematically overbid, miss their
# contracts, and sink to the -200 floor. Spades' +500 win is scored and never
# reached. What follows is the left arm, under a Playout Policy, with the
# uniform chooser measured over the same seeds as the contrast that makes it
# a witness rather than a number.

WITNESS_SEEDS = 30

# The floor, not the measurement: the policy reaches +500 on 27 of these 30
# seeds (2026-08-23), and this is set well below that so ordinary drift does
# not redden it while a policy that stopped steering would.
WITNESS_FLOOR = 20


def _termini(seeds: int, use_policy: bool) -> Counter[str]:
    """How each seed ended: the win, the collapse, or the declared bound.

    `max_length` is a counted outcome rather than an error. It is a per-game
    declared contract sized against measured random playouts, and a policy
    that keeps a team solvent plays more hands than a random one — so a few
    seeds spend the budget. The bucket is the record.
    """
    game = _spades()
    out: Counter[str] = Counter()
    for seed in range(seeds):
        rng = random.Random(seed)
        policy = PlayoutPolicy(rng) if use_policy else None
        try:
            result = (
                play_game(game, rng, chooser=policy, on_first_decision=policy.attach)
                if policy is not None
                else play_game(game, rng)
            )
        except OwnerGuardError:
            out["max_length"] += 1
            continue
        out["+500" if max(result.scores.values()) >= 500 else "-200"] += 1
    return out


def test_the_policy_reaches_the_500_win_the_random_chooser_never_does() -> None:
    """#105's witness: the skill-gated branch, executed.

    Both arms run over the same seeds, so the contrast is attributable to the
    chooser and nothing else. Asserting a COUNT rather than "at least one"
    is what makes it a regression gate: a policy that stopped steering the
    bidding would still hit +500 occasionally and would still redden here.
    """
    policy_termini = _termini(WITNESS_SEEDS, use_policy=True)
    random_termini = _termini(WITNESS_SEEDS, use_policy=False)

    assert policy_termini["+500"] >= WITNESS_FLOOR, (
        f"the Playout Policy reached +500 on only {policy_termini['+500']} of "
        f"{WITNESS_SEEDS} seeds: {dict(policy_termini)}"
    )
    assert random_termini["+500"] == 0, (
        "the uniform chooser now reaches +500 — the contrast this witness "
        f"rests on no longer holds: {dict(random_termini)}"
    )
    # Non-vacuity: both arms actually played every seed.
    assert sum(policy_termini.values()) == WITNESS_SEEDS
    assert sum(random_termini.values()) == WITNESS_SEEDS
