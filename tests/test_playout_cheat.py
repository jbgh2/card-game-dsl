"""Random-playout harness for Cheat.

Cheat is the corpus's claim-versus-content game in its purest form: every
play is face-down cards plus a public claim (the forced rank cycle + the
announced count), adjudicated — when anyone calls "Cheat!" — by flipping
exactly the played cards. Its falsifiable invariants are conservation (52
cards, always somewhere across deck/hands/played/pile/flipped), termination
(exactly one player sheds out and survives their final play's window), and
the winner reading (`winner: highest won` names the sole shed-out player).

The adjudication branches — challenger eats the pile on a true claim, liar
eats it on a lie, unchallenged plays merge face-down — are each proven to
actually fire (a guard bug that killed one branch would still conserve and
terminate); the observation-boundary proofs for the same mechanic live in
tests/openspiel_ready/test_cheat.py.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

CHEAT = Path(__file__).parent.parent / "docs" / "games" / "cheat.cardlang"


def _cheat() -> n.Game:
    return check_source(CHEAT)


def test_cheat_checks_clean() -> None:
    _cheat()  # parse -> resolve -> typecheck -> deck-capacity; must not raise


@pytest.mark.parametrize("seed", range(30))
def test_cheat_plays_to_completion(seed: int) -> None:
    game = _cheat()
    census: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            census.update(data)

    result = play_game(game, random.Random(seed), tracer)

    # Exactly one player shed out and survived their final window: the winner.
    assert result.loser is None
    assert result.winner is not None
    winners = [p for p, w in result.scores.items() if w]
    assert winners == [result.winner], f"seed {seed}: {result.scores}"

    # Card conservation: all 52 cards still somewhere (a hand or the face-down
    # pile; `played`/`flipped` empty out inside every adjudication).
    assert census["total"] == 52, f"seed {seed}: {census}"


def test_all_three_adjudication_branches_fire() -> None:
    """Aggregate across a seed sweep (one seed can legitimately miss a branch):
    a true claim challenged routes the flip + pile to the CHALLENGER's hand, a
    caught lie routes them to the claimant's, and an unchallenged play merges
    face-down into the pile. Counted from player 0's observation stream — the
    flip destination (`flipped`) and the two pickup routes are public events,
    so any observer's stream carries all three."""
    game = _cheat()
    flips_to_challenger = 0
    flips_to_claimant = 0
    pile_merges = 0

    for seed in range(6):
        events: list[tuple[Any, ...]] = []

        def observer(player: int, event: tuple[Any, ...]) -> None:
            if player == 0:
                events.append(event)  # noqa: B023 -- consumed before the loop advances

        play_game(game, random.Random(seed), observer=observer)

        claimant: int | None = None
        challenger: int | None = None
        for e in events:
            if e[0] == "announce" and str(e[2]).startswith("play_"):
                claimant = int(e[1])
            elif e[0] == "announce" and e[2] == "call_cheat":
                challenger = int(e[1])
            elif e[0] == "move" and e[1] == "played" and e[3] == "pile":
                pile_merges += 1
            elif e[0] == "move" and e[1] == "flipped" and str(e[3]).startswith("hand["):
                taker = int(str(e[3]).split("[")[1].rstrip("]"))
                assert challenger is not None and claimant is not None
                if taker == challenger:
                    flips_to_challenger += 1
                else:
                    assert taker == claimant, (
                        f"seed {seed}: a flip went to P{taker}, neither the "
                        f"claimant P{claimant} nor the challenger P{challenger}"
                    )
                    flips_to_claimant += 1

    assert flips_to_challenger > 0, "no true claim was ever challenged"
    assert flips_to_claimant > 0, "no lie was ever caught"
    assert pile_merges > 0, "no play ever went unchallenged"


def test_seed0_characterization() -> None:
    # Byte-identity pin for the whole game at seed 0: any change to the
    # decision sequence (turns rotation, window order, offer order, the
    # played-count range, the chosen-card pool order) moves this vector. Measured hash-independent
    # (identical under PYTHONHASHSEED 0, 1, 7, 42): every collection on the
    # decision path is ordered (source-order pools, offer lists, seating
    # rings), so the in-process pin is sound without a subprocess seed pin.
    game = _cheat()
    rs_box: list[Any] = []
    result = play_game(
        game, random.Random(0), on_first_decision=lambda rs: rs_box.append(rs)
    )
    assert result.winner == 3
    assert result.scores == {0: False, 1: False, 2: False, 3: True}
    assert rs_box[0].decisions_made == 151
