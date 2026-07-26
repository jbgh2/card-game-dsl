"""Canasta: random-playout invariants plus a characterization pin.

A partnership melding game with public melds and hidden hands: the strongest
falsifiable checks are conservation (all 108 cards somewhere every game),
the fixed four-deal match shape, and an INDEPENDENT re-derivation of the
final hand's score delta from the final table (the meld piles, red-three
rows, and hands are all still live at game end, so the pure scoring
functions can recompute what the DSL's scoring phase added). The meld-window
totality claim — an open meld attempt always closes legally, random play
included — is exercised implicitly by every completing seed: a wedged
window would raise the offer's loud no-legal-move error mid-playout.

What the sweep covers is ASSERTED, not measured once and written down: the
recompute's arms (a team that melded and one that never did, a completed
canasta, a go-out and a hand that ended without one, red threes on the row)
must each fire on `WITNESS_SEEDS` distinct seeds, so a seed count that stops
carrying an arm reddens by name. The rarer paths keep their own pinned
seeds: the black-three go-out meld (seed 30) and the no-stock decline
(seed 19), both below. The 90/120 initial-meld brackets are unreachable in a
four-deal random match (cumulative 1500+ before the last deal); they are
pinned at the table level in tests/test_canasta_primitives.py.
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.canasta import (
    canasta_bonus_for,
    card_points,
    is_red3,
    red3_bonus_for,
)
from cardlang.runtime.driver import play_game

CANASTA = Path(__file__).parent.parent / "docs" / "games" / "canasta.cardlang"

_MELD_FAMILIES = (
    "meldA", "meldK", "meldQ", "meldJ", "meld10", "meld9",
    "meld8", "meld7", "meld6", "meld5", "meld4", "meld3b",
)


@lru_cache(maxsize=None)
def _run(seed: int) -> tuple[Any, Any, list[dict[int, int]]]:
    game = check_source(CANASTA)
    rs_box: list[Any] = []
    hand_ends: list[dict[int, int]] = []

    def tracer(event: str, data: Any) -> None:
        if event == "hand_end":
            hand_ends.append(dict(data))

    result = play_game(
        game,
        random.Random(seed),
        tracer=tracer,
        on_first_decision=lambda rs: rs_box.append(rs),
    )
    return result, rs_box[0], hand_ends


# The arms of the per-seed assertions below — each a branch that would
# otherwise be checked vacuously (a recompute that never sees a go-out has
# not exercised the 100-point bonus; one that never sees an unmelded team has
# not exercised the hand-points penalty against a team with nothing down).
RECOMPUTE_ARMS = frozenset(
    {"team_melded", "team_never_melded", "canasta_completed",
     "went_out", "did_not_go_out", "red3_row_used"}
)

# Every arm on at least this many DISTINCT seeds: one witness is satisfiable
# by a single lucky deal, which is what makes a seed count unfalsifiable.
WITNESS_SEEDS = 3

# Derived from that, not chosen. Five of the six arms fire on seed 0; the
# binding one is `team_never_melded` (a partnership that never gets down),
# which lands on seeds 2, 3 and 4 — so five seeds is the minimum that
# witnesses every arm three times, and ten leaves headroom for a game change
# that shifts an arm off the early seeds. Each seed is a full four-deal
# match, the corpus's most expensive playout.
#
# red under: SEEDS = 4 (`team_never_melded` drops to two witness seeds).
SEEDS = 10


def test_random_matches_satisfy_invariants() -> None:
    witnesses: dict[str, set[int]] = {}
    for seed in range(SEEDS):
        _one_match(seed, witnesses)

    assert set(witnesses) == RECOMPUTE_ARMS, (
        f"the {SEEDS}-seed sweep no longer exercises "
        f"{sorted(RECOMPUTE_ARMS - set(witnesses))} — the recompute below "
        f"still passes, but it no longer checks those arms"
    )
    thin = {a: sorted(w) for a, w in witnesses.items() if len(w) < WITNESS_SEEDS}
    assert not thin, (
        f"{thin} fire on fewer than {WITNESS_SEEDS} of the {SEEDS} seeds — the "
        f"seed count no longer carries the arm it was derived from"
    )


def _one_match(seed: int, witnesses: dict[str, set[int]]) -> None:
    result, rs, hand_ends = _run(seed)

    def witness(arm: str) -> None:
        witnesses.setdefault(arm, set()).add(seed)

    # A fixed four-deal match: four scoring phases, team-keyed scores, and
    # the winner is the higher cumulative total.
    assert result.hands_played == 4 and len(hand_ends) == 4
    assert set(result.scores) == {0, 1}
    assert result.winner == max(result.scores, key=lambda t: result.scores[t])

    # Conservation: all 108 cards are somewhere (stock, hands, pile, stage,
    # melds, red-three rows).
    total = sum(len(z.cards) for z in rs.zones.singles.values()) + sum(
        len(z.cards) for fam in rs.zones.families.values() for z in fam.values()
    )
    assert total == 108, f"seed {seed}: {total}"

    # No meld attempt survives a hand: the stage zones are empty at the end.
    for z in rs.zones.families["stage"].values():
        assert not z.cards, f"seed {seed}: stage not empty"
    # Red threes never rest in hands or melds — only on the red3 rows.
    for name in ("hand", *_MELD_FAMILIES):
        for z in rs.zones.families[name].values():
            assert not any(is_red3(c) for c in z.cards), f"seed {seed}: {name}"

    # Independent re-derivation of the FINAL hand's score delta from the
    # final table, via the pure scoring functions: melded card points +
    # canasta bonuses + red-three bonus + 100 for going out - card points
    # left in the partners' hands. (A hand is empty only by going out, so
    # went-out is inferable from the final hands.)
    prev = hand_ends[2]
    for team in (0, 1):
        members = [p for p, t in rs.team_of.items() if t == team]
        melds = [
            list(rs.zones.instance(name, team).cards) for name in _MELD_FAMILIES
        ]
        melded = any(m for m in melds)
        witness("team_melded" if melded else "team_never_melded")
        if any(canasta_bonus_for(m) for m in melds):
            witness("canasta_completed")
        if rs.zones.instance("red3", team).cards:
            witness("red3_row_used")
        witness(
            "went_out"
            if any(not rs.zones.instance("hand", p).cards for p in members)
            else "did_not_go_out"
        )
        expected = (
            sum(card_points(c) for m in melds for c in m)
            + sum(canasta_bonus_for(m) for m in melds)
            + red3_bonus_for(len(rs.zones.instance("red3", team).cards), melded)
            + (100 if any(not rs.zones.instance("hand", p).cards for p in members) else 0)
            - sum(card_points(c) for p in members for c in rs.zones.instance("hand", p).cards)
        )
        got = result.scores[team] - prev[team]
        assert got == expected, f"seed {seed} team {team}: {got} != {expected}"


def test_seed0_characterization() -> None:
    # Byte-identity pin for the whole match: any change to the constructs'
    # decision sequence (turns rotation, offer order, chosen-movement pools,
    # the gather order feeding the shuffle) moves this vector. Measured
    # hash-independent (identical under PYTHONHASHSEED 0/7/12): every
    # collection on the decision path is ordered.
    result, _, hand_ends = _run(0)
    assert result.winner == 0
    assert result.scores == {0: 4500, 1: 2655}
    assert hand_ends == [
        {0: 1260, 1: 255},
        {0: 1795, 1: 590},
        {0: 2955, 1: 1795},
        {0: 4500, 1: 2655},
    ]


def test_black_three_go_out_meld_fires() -> None:
    # The go-out black-three group is the rarest legal action (a canasta on
    # the row, the hand exactly the group plus at most a final discard).
    # Seed 30 was found by a bounded search; the announce below pins that
    # the path stays reachable.
    game = check_source(CANASTA)
    announced: list[str] = []

    def obs(p: int, e: tuple[Any, ...]) -> None:
        if p == 0 and e[0] == "announce" and str(e[2]) == "meld_black3":
            announced.append(str(e[2]))

    play_game(game, random.Random(30), observer=obs)
    assert announced, "seed 30 no longer reaches the black-three go-out meld"


def test_no_stock_decline_ends_the_hand() -> None:
    # Seed 19 (found by searching 0..29) reaches the stock-exhaustion
    # endgame with a legal but unforced pile take, and declines it — the
    # `decline_pile` path that ends the hand.
    game = check_source(CANASTA)
    announced: list[str] = []

    def obs(p: int, e: tuple[Any, ...]) -> None:
        if p == 0 and e[0] == "announce" and str(e[2]) == "decline_pile":
            announced.append(str(e[2]))

    play_game(game, random.Random(19), observer=obs)
    assert announced, "seed 19 no longer reaches the no-stock decline"
