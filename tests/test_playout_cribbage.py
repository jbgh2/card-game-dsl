"""Cribbage: the show's known hands through the game's own functions, the
pegging scorers against known counts, plus a random playout.

A counting game has no card-conservation point total, so the strongest
falsifiable check is the show against hands whose values are famous or
hand-derivable (the 29-hand, runs with multiplicity, flushes, his nob). The
show is written in the language, so the probe carries the game file's OWN
`card_points { }` clause and `function` block, read from cribbage.cardlang --
a copy here would be a second scorer that could drift. The playout then checks
termination, that exactly one player crosses 121, and that the winner is that
player.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.cribbage import peg_pairs, peg_run
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, expand_ranking_convention

CRIBBAGE = Path(__file__).parent.parent / "docs" / "games" / "cribbage.cardlang"

# The declared `ranking: aces low`'s rank_index, derived through the same
# expansion the resolver uses (never a private copy of the order).
_ORDER = {
    r: i
    for i, r in enumerate(reversed(expand_ranking_convention("aces low", "standard52")))
}


def _c(spec: str) -> Card:
    rank, suit = spec[:-1], {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[spec[-1]]
    return Card(rank, suit)


def _pick(specs: str) -> str:
    def one(c: Card) -> str:
        rank = f'"{c.rank}"' if c.rank.isdigit() else c.rank
        return f"(card.rank is {rank} and card.suit is {c.suit})"
    return " or ".join(one(_c(x)) for x in specs.split())


def _show_probe(hand: str, starter: str, is_crib: bool) -> str:
    """A game holding the given four cards (in `played[0]`, or in `crib`) and
    the starter, scoring them with cribbage.cardlang's own clause and
    functions."""
    text = CRIBBAGE.read_text()
    clause = re.search(r"card_points \{[^}]*\}", text)
    assert clause is not None
    functions = text[text.index("\nfunction ") :]
    target = "crib" if is_crib else "played[0]"
    return (
        "game ShowProbe {\n"
        "  players: 2\n  max_length: 100\n  cards: standard52\n  ranking: aces low\n"
        f"  {clause.group(0)}\n"
        "  zones { deck : Deck  starter : Discard  crib : FaceDownPile"
        "  hand[player] : Hand<player>  played[player] : PlayerPile<player> }\n"
        "  state { score[player] : Integer = 0 }\n  winner: highest score\n"
        "  phase p {\n    move all cards to deck\n"
        f"    move all cards from deck where {_pick(hand)} to {target}\n"
        f"    move all cards from deck where {_pick(starter)} to starter\n"
        "    score[0] := show_value(0)\n    score[1] := crib_value()\n  }\n}\n"
        f"{functions}"
    )


# (label, the four cards, the starter, scored as the crib?, the show's value)
_KNOWN_HANDS = [
    ("the perfect 29", "5C 5D 5S JH", "5H", False, 29),
    ("run of five + two fifteens", "4C 5D 6S 7H", "8C", False, 9),
    ("double run of three, a pair and three fifteens", "4C 5D 5S 6H", "9C", False, 14),
    ("four-flush, starter off-suit", "2C 5C 8C JC", "9D", False, 8),
    ("five-flush", "2C 5C 8C JC", "9C", False, 10),
    ("a four-flush in the crib scores nothing", "2C 5C 8C JC", "9D", True, 4),
    ("a five-flush in the crib", "2C 5C 8C JC", "9C", True, 10),
    ("his nob", "JC 2D 3S 4H", "9C", False, 8),
    ("the same hand, no nob", "JC 2D 3S 4H", "9D", False, 7),
    ("one fifteen (A+6+8)", "AC 3H 6S 8C", "KH", False, 2),
    ("A-2-3 runs: aces low", "AC 2H 3S 9C", "KH", False, 7),
    ("Q-K-A does not wrap", "QC KH AS 5C", "9H", False, 6),
]


@pytest.mark.parametrize("label,hand,starter,is_crib,expected", _KNOWN_HANDS,
                         ids=[h[0] for h in _KNOWN_HANDS])
def test_the_show_scores_known_hands(
    label: str, hand: str, starter: str, is_crib: bool, expected: int
) -> None:
    result = play_game(check_dsl(_show_probe(hand, starter, is_crib), "show.cardlang"),
                       rng=random.Random(0))
    assert result.scores[1 if is_crib else 0] == expected, label


def test_pegging_scorers() -> None:
    assert peg_pairs([_c("7C"), _c("7D")]) == 2  # a pair
    assert peg_pairs([_c("7C"), _c("7D"), _c("7S")]) == 6  # pair royal
    assert peg_run([_c("4C"), _c("6D"), _c("5S")], _ORDER) == 3  # run regardless of order
    assert peg_run([_c("9C"), _c("4D"), _c("6S"), _c("5H")], _ORDER) == 3  # only the suffix


def test_50_random_games_satisfy_invariants() -> None:
    game = check_source(CRIBBAGE)
    for seed in range(50):
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        crossed = [p for p, s in result.scores.items() if s >= 121]
        assert len(crossed) == 1, f"seed {seed}: {result.scores}"  # exactly one winner
        assert result.winner == crossed[0]
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])
        assert census["total"] == 52, f"seed {seed}: {census}"
