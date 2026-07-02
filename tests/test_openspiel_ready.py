"""The OpenSpiel-readiness proof, per fully-kernel game (SP1 spec, "The proof"):

1. pyspiel API conformance (random_sim_test).
2. INDISTINGUISHABILITY: two worlds differing only in cards hidden from P
   yield byte-identical information states for P (the leak-closure proof).
3. Soundness converse: perturbing what P CAN see changes P's state.
4. Perfect recall: each player's observation log is append-only along a game.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # noqa: E402  (registers on import)
from cardlang.openspiel.infostate import information_state  # noqa: E402
from cardlang.openspiel.replay import Pause, run  # noqa: E402

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"
SIX = sorted(ogame.GAMES.items())  # (short_name, filename), deterministic order

# Steps to replay before the indistinguishability check. Deep enough that real
# decisions and movements happened; shallow enough that opponents still hold
# swappable cards. Getaway/Big Two shed cards fast, hence the smaller L.
# Bridge redeals the hand outright on a 4-pass "passed out" auction (real
# rule), and this harness's greedy `_advance` (always `legal[0]`) always picks
# "pass" first, so any depth >= 4 crosses into a *second* deal — a fresh
# shuffle unrelated to the hands `on_first_decision` mutates (that hook always
# fires at the game's very first-ever decision, i.e. deal #1). At depth >= 4
# the swap was confirmed (field-by-field diff, see task-10 report) to change
# ONLY P0's own re-shuffled `hand[0]` — hidden hands stayed `#13` in both
# worlds and no opponent card identity appeared in the obs log — i.e. an
# ill-posed experiment (mutated hands != examined hands), not a leak. Depth 3
# stays inside deal #1, where the mutated hands and the examined hands
# coincide, so the property is checked in the pre-play auction phase (this
# seed's greedy policy never reaches trick play for bridge).
DEPTH = {"cardlang_getaway": 8, "cardlang_big_two": 6, "cardlang_bridge": 3}
DEFAULT_DEPTH = 12


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_pyspiel_conformance(short_name: str, filename: str) -> None:
    game = pyspiel.load_game(short_name)
    pyspiel.random_sim_test(game, num_sims=1, serialize=False, verbose=False)


def _advance(path: str, seed: int, depth: int) -> tuple[list[int], Pause]:
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    while len(history) < depth:
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        if not isinstance(nxt, Pause):  # short game: back off one step
            history.pop()
            break
        r = nxt
    return history, r


def _swap_fn(opp1: int, opp2: int, x: Any, y: Any) -> Any:
    def swap(rs: Any) -> None:
        h1, h2 = rs.zones.instance("hand", opp1), rs.zones.instance("hand", opp2)
        h1.remove(x)
        h2.remove(y)
        h1.add(y)
        h2.add(x)

    return swap


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_indistinguishability_under_hidden_swap(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 5
    depth = DEPTH.get(short_name, DEFAULT_DEPTH)
    history, pause_a = _advance(path, seed, depth)
    p = pause_a.player
    first = run(path, seed, ())
    assert isinstance(first, Pause)
    d0 = first.player  # the swap must not touch the first decider (stale candidates)

    others = [q for q in range(len(pause_a.obs_logs)) if q not in (p, d0)]
    assert len(others) >= 2, "harness needs two swappable opponents"
    opp1, opp2 = others[0], others[1]

    # Same-suit swap keeps every recorded action legal in the swapped world;
    # skip pairs the replay rejects (a rule keyed on the specific card).
    hand1 = pause_a.rs.zones.instance("hand", opp1).cards
    hand2 = pause_a.rs.zones.instance("hand", opp2).cards
    three_d = ("3", "diamonds")
    candidates = [
        (x, y)
        for x in hand1
        for y in hand2
        if x.suit == y.suit
        and x != y
        # keep the 3♦ fixed: Big Two's opening filter keys on that exact card
        and (x.rank, x.suit) != three_d
        and (y.rank, y.suit) != three_d
    ]
    assert candidates, "no same-suit swap pair available; lower DEPTH for this game"

    info_a = information_state(p, pause_a.rs, pause_a.obs_logs[p])
    for x, y in candidates:
        try:
            pause_b = run(path, seed, tuple(history), on_first_decision=_swap_fn(opp1, opp2, x, y))
        except Exception:
            continue  # this pair made a recorded action illegal; try the next
        assert isinstance(pause_b, Pause)
        info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
        assert info_a == info_b, (
            f"{short_name}: swapping hidden {x}<->{y} (players {opp1},{opp2}) "
            f"CHANGED P{p}'s information state — the info-set leaks"
        )
        return  # one successful controlled swap proves the property
    pytest.fail(f"{short_name}: no swap pair produced a legal replay")


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_soundness_own_view_changes_the_state(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    r0 = run(path, 5, ())
    assert isinstance(r0, Pause)
    p = r0.player
    opp = next(q for q in range(len(r0.obs_logs)) if q != p)
    own = r0.rs.zones.instance("hand", p).cards
    theirs = r0.rs.zones.instance("hand", opp).cards
    x, y = next(
        (x, y) for x in own for y in theirs if x.suit == y.suit and x != y
    )
    info_a = information_state(p, r0.rs, r0.obs_logs[p])
    r1 = run(path, 5, (), on_first_decision=_swap_fn(p, opp, x, y))
    assert isinstance(r1, Pause)
    info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
    # The pause player is the same (no actions replayed); their own hand changed.
    assert r1.player == p and info_a != info_b, (
        f"{short_name}: the info-state is insensitive to the player's own hand"
    )


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_perfect_recall_logs_are_append_only(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 9
    history: list[int] = []
    r = run(path, seed, ())
    prev: dict[int, list[tuple[Any, ...]]] = {}
    steps = 0
    while isinstance(r, Pause) and steps < 40:
        for q, log in r.obs_logs.items():
            if q in prev:
                assert log[: len(prev[q])] == prev[q], (
                    f"{short_name}: P{q}'s observation log rewrote history"
                )
            prev[q] = list(log)
        history.append(r.legal[0])
        r = run(path, seed, tuple(history))
        steps += 1
