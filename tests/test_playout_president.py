"""President: combination-engine unit tests plus a random playout.

The combination engine is the heart of a climbing game, so it gets direct unit
tests: what a hand may lead (every rank x size held), which sets legally beat a
standing play (same size, strictly higher rank, 2 high), and the transparent
threes — a pure-threes set beats any equal-sized set and takes on the beaten
rank, so the chain after it compares against the absorbed rank, not the
threes'. The playout then checks the conservation census (52 cards, exactly
one player still holding at game end), that every hand's score delta is
exactly +2 and +1 to two distinct players (everyone else unchanged), that
cumulative scores never decrease, and termination at the 11-point target with
the highest total winning. A 40-seed exact-score golden is captured in a
PYTHONHASHSEED=0 subprocess (the repo's exact-score convention).
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime import reads, sidecar
from cardlang.runtime.driver import play_game
from cardlang.runtime.president import (
    _STRENGTH,
    ROW,
    Play,
    president_follows,
    president_lead_options,
    president_universe,
)
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

PRESIDENT = Path(__file__).parent.parent / "docs" / "games" / "president.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "president_scores.json"
REPO = Path(__file__).parent.parent

_SUIT = {"s": "spades", "h": "hearts", "c": "clubs", "d": "diamonds"}


def _hand(*specs: str) -> list[Card]:
    return [Card(r, _SUIT[s]) for r, s in (spec.split("@") for spec in specs)]


def _ctx() -> tuple[sidecar.EngineFacts, reads.GameReads]:
    """The value bundles a president query receives, built exactly as the
    engine builds them — rank_index from the driver's formula over the game's
    declared `ranking:`, which is the strength table live play uses."""
    from cardlang.ast import nodes as n

    game = check_source(PRESIDENT)
    decls = (
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
    )
    rs = RuntimeState(Seating(5), ZoneStore(decls, tuple(range(5))), random.Random(0))
    rs.rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    return sidecar.bind(rs, None, ROW)


def test_module_strength_table_matches_the_declared_ranking() -> None:
    # The universe enumeration uses the module table (no bundles); live
    # queries use the engine facts' rank_index from the game's `ranking:`.
    # Pin them together.
    ctx = _ctx()
    assert _STRENGTH == ctx[0].rank_index


def test_lead_options_cover_every_rank_and_size() -> None:
    ctx = _ctx()
    leads = president_lead_options(*ctx, _hand("7@s", "7@h", "7@c", "K@d", "3@s", "3@h"))
    shapes = {(p.cards[0].rank, p.size) for p in leads}
    assert shapes == {
        ("7", 1), ("7", 2), ("7", 3), ("K", 1), ("3", 1), ("3", 2),
    }
    # Every lead is a natural set: equal ranks, key = the rank's own strength.
    for p in leads:
        assert p.kind == "set" and len({c.rank for c in p.cards}) == 1
        assert p.key == ctx[0].rank_index[p.cards[0].rank]
    # A led set of threes is natural — the lowest key, not transparent.
    three_pair = next(p for p in leads if p.cards[0].rank == "3" and p.size == 2)
    assert three_pair.key == 0


def test_follows_are_same_size_and_strictly_higher() -> None:
    ctx = _ctx()
    strength = ctx[0].rank_index
    led_pair_9 = Play("set", 2, strength["9"], (Card("9", "spades"), Card("9", "hearts")))
    follows = president_follows(*ctx, _hand("9@c", "9@d", "K@s", "K@h", "A@c", "5@s", "5@h"), led_pair_9)
    ranks = {p.cards[0].rank for p in follows}
    # Equal rank does not beat; lower does not beat; a single ace is the wrong
    # size; the king pair does.
    assert ranks == {"K"}
    assert all(p.size == 2 for p in follows)
    # The 2 is the highest rank, the 3 the lowest.
    assert strength["2"] > strength["A"] > strength["4"] > strength["3"]
    # Nothing naturally beats a pair of 2s.
    led_pair_2 = Play("set", 2, strength["2"], (Card("2", "spades"), Card("2", "hearts")))
    assert president_follows(*ctx, _hand("A@s", "A@h", "K@c", "K@d"), led_pair_2) == []


def test_transparent_threes_beat_anything_and_absorb_the_rank() -> None:
    ctx = _ctx()
    strength = ctx[0].rank_index
    led_pair_k = Play("set", 2, strength["K"], (Card("K", "spades"), Card("K", "hearts")))
    follows = president_follows(*ctx, _hand("3@s", "3@h", "Q@c", "Q@d"), led_pair_k)
    # The queens cannot beat kings; the pure-threes pair can.
    threes = [p for p in follows if p.kind == "threes"]
    assert len(follows) == 1 and len(threes) == 1
    t = threes[0]
    assert {c.rank for c in t.cards} == {"3"} and t.size == 2
    # Transparency: the threes take on the beaten rank — the next follower
    # must beat kings, so aces beat, queens still do not.
    assert t.key == led_pair_k.key
    nxt = president_follows(*ctx, _hand("A@s", "A@h", "Q@s", "Q@h"), t)
    assert {p.cards[0].rank for p in nxt} == {"A"}
    # Threes also beat an effective rank of 2 (nothing else can) ...
    led_pair_two = Play("set", 2, strength["2"], (Card("2", "spades"), Card("2", "hearts")))
    over_two = president_follows(*ctx, _hand("3@c", "3@d", "A@s", "A@h"), led_pair_two)
    assert [p.kind for p in over_two] == ["threes"]
    # ... and beat a standing threes-as-X, absorbing X again.
    again = president_follows(*ctx, _hand("3@c", "3@d"), t)
    assert [p.kind for p in again] == ["threes"] and again[0].key == strength["K"]
    # A led (natural) threes set is beaten transparently too, absorbing the
    # threes' own lowest rank — so anything then beats it.
    led_three = Play("set", 1, strength["3"], (Card("3", "diamonds"),))
    over_three = president_follows(*ctx, _hand("3@c", "4@d"), led_three)
    assert {p.kind for p in over_three} == {"set", "threes"}
    # No bombs, no cross-size beating: a triple never answers a pair.
    follows_sizes = president_follows(*ctx, _hand("A@s", "A@h", "A@c"), led_pair_k)
    assert all(p.size == 2 for p in follows_sizes)


def test_universe_is_a_unique_superset_of_the_query_outputs() -> None:
    universe = president_universe()
    card_sets = {frozenset(p.cards) for p in universe}
    assert len(universe) == 195  # 13 ranks x (4 + 6 + 4 + 1) suit subsets
    assert len(card_sets) == 195, "combo card-sets must be unique"
    # Every play either query can emit over random hands is in the universe.
    ctx = _ctx()
    rng = random.Random(3)
    from cardlang.runtime.values import build_deck

    for _ in range(20):
        deck = build_deck("standard52")
        rng.shuffle(deck)
        hand = deck[:11]
        leads = president_lead_options(*ctx, hand)
        assert all(frozenset(p.cards) in card_sets for p in leads)
        for led in leads:
            for f in president_follows(*ctx, deck[11:22], led):
                assert frozenset(f.cards) in card_sets


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
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])
        assert max(result.scores.values()) >= 11, (
            f"seed {seed}: game ended below the 11-point target"
        )


# Exact-score golden: the repo's exact-score convention pins PYTHONHASHSEED=0
# in a subprocess (chooser candidate order elsewhere in the stack can be
# hash-dependent; the pinned environment makes the capture byte-stable).
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
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def test_per_seed_scores_match_golden() -> None:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    captured = json.loads(proc.stdout)
    expected = json.loads(GOLDEN.read_text())
    assert captured == expected
