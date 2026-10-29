"""President: the declared plays on hands built for each case, plus a random playout.

The catalogue and its follows function are the heart of a climbing game, so
they get direct tests: what a hand may lead (every rank x size held), which
sets legally beat a standing play (same size, strictly higher rank, 2 high),
and the transparent threes — a pure-threes set beats any equal-sized set and
takes on the beaten rank, so the chain after it compares against the absorbed
rank, not the threes'. The playout then checks the conservation census (52
cards, exactly one player still holding at game end), that every hand's score
delta is exactly +2 and +1 to two distinct players (everyone else unchanged),
that cumulative scores never decrease, and termination at the 11-point target
with the highest total winning. A 40-seed exact-score golden is captured in a
subprocess for interpreter isolation; the scores do not depend on
PYTHONHASHSEED, which test_migration_characterization.py's
`test_a_playout_is_hash_seed_independent` pins for this game directly.
"""

from __future__ import annotations

import itertools
import json
import random
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.resolve import _walk
from cardlang.runtime import declared
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Combination, build_deck
from tests import climb_asks

PRESIDENT = Path(__file__).parent.parent / "docs" / "games" / "president.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "president_scores.json"
REPO = Path(__file__).parent.parent

_SUIT = {"s": "spades", "h": "hearts", "c": "clubs", "d": "diamonds"}
_ORDER = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]


def _hand(*specs: str) -> list[Card]:
    return [Card(r, _SUIT[s]) for r, s in (spec.split("@") for spec in specs)]


@cache
def _ask() -> climb_asks.Ask:
    return climb_asks.asker(PRESIDENT)


def _set(*specs: str) -> Combination:
    """The set the given cards are, as the catalogue names it."""
    cards = _hand(*specs)
    (play,) = [p for p in _ask()(cards, None, ()) if len(p.cards) == len(cards)]
    return play


def _universe() -> list[Combination]:
    game = check_source(str(PRESIDENT))
    (engine,) = {nd.engine for nd in _walk(game) if isinstance(nd, n.ClimbRound)}
    assert isinstance(engine, n.DeclaredEngine)
    return list(declared.game_universe(game, engine).plays)


def test_lead_options_cover_every_rank_and_size() -> None:
    leads = _ask()(_hand("7@s", "7@h", "7@c", "K@d", "3@s", "3@h"), None, ())
    shapes = {(p.cards[0].rank, len(p.cards)) for p in leads}
    assert shapes == {
        ("7", 1), ("7", 2), ("7", 3), ("K", 1), ("3", 1), ("3", 2),
    }
    # Every lead is a natural set: equal ranks.
    for p in leads:
        assert len({c.rank for c in p.cards}) == 1


def test_follows_are_same_size_and_strictly_higher() -> None:
    led_pair_9 = _set("9@s", "9@h")
    follows = _ask()(_hand("9@c", "9@d", "K@s", "K@h", "A@c", "5@s", "5@h"), led_pair_9, led_pair_9.cards)
    ranks = {p.cards[0].rank for p in follows}
    # Equal rank does not beat; lower does not beat; a single ace is the wrong
    # size; the king pair does.
    assert ranks == {"K"}
    assert all(len(p.cards) == 2 for p in follows)
    # Nothing naturally beats a pair of 2s.
    led_pair_2 = _set("2@s", "2@h")
    assert _ask()(_hand("A@s", "A@h", "K@c", "K@d"), led_pair_2, led_pair_2.cards) == []


def test_transparent_threes_beat_anything_and_absorb_the_rank() -> None:
    ask = _ask()
    led_pair_k = _set("K@s", "K@h")
    follows = ask(_hand("3@s", "3@h", "Q@c", "Q@d"), led_pair_k, led_pair_k.cards)
    # The queens cannot beat kings; the pure-threes pair can.
    assert len(follows) == 1
    (t,) = follows
    assert {c.rank for c in t.cards} == {"3"} and len(t.cards) == 2
    # Transparency: the threes take on the beaten rank — the next follower
    # must beat kings, so aces beat, queens still do not.
    pile = (*led_pair_k.cards, *t.cards)
    nxt = ask(_hand("A@s", "A@h", "Q@s", "Q@h"), t, pile)
    assert {p.cards[0].rank for p in nxt} == {"A"}
    # Threes also beat a pair of 2s (nothing else can) ...
    led_pair_two = _set("2@s", "2@h")
    over_two = ask(_hand("3@c", "3@d", "A@s", "A@h"), led_pair_two, led_pair_two.cards)
    assert [{c.rank for c in p.cards} for p in over_two] == [{"3"}]
    # ... and beat a standing threes-as-K.
    again = ask(_hand("3@c", "3@d"), t, pile)
    assert [{c.rank for c in p.cards} for p in again] == [{"3"}]
    # A led threes set is beaten by any set its size, threes among them.
    led_three = _set("3@d")
    over_three = ask(_hand("3@c", "4@d"), led_three, led_three.cards)
    assert {p.cards[0].rank for p in over_three} == {"3", "4"}
    # No bombs, no cross-size beating: a triple never answers a pair.
    follows_sizes = ask(_hand("A@s", "A@h", "A@c"), led_pair_k, led_pair_k.cards)
    assert all(len(p.cards) == 2 for p in follows_sizes)


def test_every_set_a_hand_holds_is_offered_at_lead_and_follow() -> None:
    """The offers against an oracle written from Pagat ("any single card or
    any set of cards of equal rank"; a set "can only be beaten by a higher set
    containing the same number of cards"; transparent threes beat a set of
    the same size of any rank): every subset of the hand, classified without
    the game file, is offered exactly when the rules allow it, once, over a
    standing natural set led to the trick."""
    ask = _ask()
    rng = random.Random(962)
    deck = build_deck("standard52")
    universe = _universe()
    for _ in range(60):
        hand = rng.sample(deck, 11)
        subsets = [
            frozenset(s)
            for size in range(1, 5)
            for s in itertools.combinations(hand, size)
            if len({c.rank for c in s}) == 1
        ]
        offered = [frozenset(p.cards) for p in ask(hand, None, ())]
        assert len(offered) == len(set(offered)), "a set offered twice"
        assert set(offered) == set(subsets)
        rest = [c for c in deck if c not in hand]
        for _ in range(10):
            led = next(
                p for p in rng.sample(universe, len(universe))
                if not (frozenset(p.cards) - frozenset(rest))
            )
            power = _ORDER.index(led.cards[0].rank)
            expected = {
                s for s in subsets
                if len(s) == len(led.cards)
                and (_ORDER.index(next(iter(s)).rank) > power or next(iter(s)).rank == "3")
            }
            got = [frozenset(p.cards) for p in ask(hand, led, led.cards)]
            assert len(got) == len(set(got)), "a set offered twice"
            assert set(got) == expected, (led, set(got) ^ expected)


def test_the_universe_is_every_set_of_one_rank() -> None:
    universe = _universe()
    card_sets = {frozenset(p.cards) for p in universe}
    assert len(universe) == 195  # 13 ranks x (4 + 6 + 4 + 1) suit subsets
    assert len(card_sets) == 195, "combo card-sets must be unique"
    assert all(len({c.rank for c in s}) == 1 for s in card_sets)


def test_30_random_games_satisfy_invariants() -> None:
    game = check_source(PRESIDENT)
    for seed in range(30):
        census: dict[str, int] = {}
        hand_totals: list[dict[int, int]] = []

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                hand_totals.append(dict(data))  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        assert hand_totals, f"seed {seed}: no hand was played"
        prev = {p: 0 for p in range(5)}
        for cum in hand_totals:
            deltas = {p: cum[p] - prev[p] for p in cum}
            # Exactly one President (+2) and one Vice-President (+1) per hand,
            # two distinct players; everyone else exactly 0 (scores only grow).
            assert sorted(deltas.values()) == [0, 0, 0, 1, 2], (
                f"seed {seed}: bad per-hand deltas {deltas}"
            )
            prev = cum

        # Conservation: 52 cards, and exactly one player (the Scum) still
        # holds cards when the game ends.
        assert census["total"] == 52, f"seed {seed}: {census}"
        assert census["hands_with_cards"] == 1, f"seed {seed}: {census}"
        assert result.scores == hand_totals[-1], f"seed {seed}: final score mismatch"
        top = max(result.scores.values())
        assert result.winners == {p for p, s in result.scores.items() if s == top}
        assert max(result.scores.values()) >= 11, (
            f"seed {seed}: game ended below the 11-point target"
        )


# Exact-score golden, captured in a subprocess for interpreter isolation.
# President is one of the games test_migration_characterization.py's
# `test_a_playout_is_hash_seed_independent` captures under two hash seeds, so
# this vector reproduces under whatever seed a run draws.
_CAPTURE = """
import json, random
from pathlib import Path
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

game = check_source(Path("docs/games/president.cardlang"))
out = {}
for seed in range(40):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(p): s for p, s in sorted(r.scores.items())},
        "winners": sorted(r.winners),
    }
print(json.dumps(out))
"""


def test_per_seed_scores_match_golden() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    captured = json.loads(proc.stdout)
    expected = json.loads(GOLDEN.read_text())
    assert captured == expected
