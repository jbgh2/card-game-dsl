"""Hearts as an OpenSpiel game: API conformance, a full rollout, and info-state
correctness (perfect recall, no leakage of hidden hands).

Skipped entirely when `pyspiel` (open_spiel) isn't installed.
"""

from __future__ import annotations

import random

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game  # noqa: E402  (registers the game on import)
from cardlang.openspiel.infostate import hearts_information_state  # noqa: E402
from cardlang.openspiel.replay import Pause, run  # noqa: E402


def test_random_sim_conformance() -> None:
    game = pyspiel.load_game("cardlang_hearts")
    assert game.num_distinct_actions() == 52
    # OpenSpiel's own API/consistency tester (legal_actions, apply, clone,
    # chance, terminal, returns, info-state). Small num_sims: re-sim is O(n²).
    pyspiel.random_sim_test(game, num_sims=2, serialize=False, verbose=False)


def test_full_rollout_is_zero_sum_and_terminates() -> None:
    game = pyspiel.load_game("cardlang_hearts")
    state = game.new_initial_state()
    rng = random.Random(2)
    steps = 0
    while not state.is_terminal():
        if state.is_chance_node():
            action = rng.choice([o for o, _ in state.chance_outcomes()])
        else:
            action = rng.choice(state.legal_actions())
        state.apply_action(action)
        steps += 1
        assert steps < 10000
    ret = state.returns()
    assert len(ret) == 4
    assert abs(sum(ret)) < 1e-6  # zero-sum (recentred Hearts scores)


def test_infostate_does_not_leak_hidden_hands() -> None:
    r = run(0, ())  # first decision: a player choosing a pass card
    assert isinstance(r, Pause)
    p = r.player
    info_p = hearts_information_state(p, r.rs, r.observed_log)
    for q in range(4):
        if q == p:
            continue
        for card in r.rs.zones.instance("hand", q).cards:
            assert str(card) not in info_p, f"leak: {card} (player {q}) in P{p} info-state"


def test_infostate_hides_other_players_pass_mid_simultaneous_pass() -> None:
    # Advance through the (simultaneous) pass until a *second* player is to act,
    # so the first passer has fully chosen — the exact node where the
    # "trick-play public / pass actor-private" filter must hide the first
    # passer's picks. (The history=() test above leaves that filter unexercised.)
    seed = 0
    history: list[int] = []
    r = run(seed, tuple(history))
    assert isinstance(r, Pause)
    first = r.player
    while isinstance(r, Pause) and r.player == first:
        history.append(r.legal[0])
        r = run(seed, tuple(history))
    assert isinstance(r, Pause) and r.player != first
    p2 = r.player
    # Still in the pass (no trick plays yet): p2's observable log must contain
    # only p2's own actions — the first passer's pass picks are filtered out.
    observable = [
        (pl, aid) for (pl, aid, kind) in r.observed_log if kind == "play" or pl == p2
    ]
    assert all(pl == p2 for (pl, _) in observable)
    assert any(pl == first and kind == "pass" for (pl, _, kind) in r.observed_log)
    # And the first passer's (un-transferred, hidden) hand never appears.
    info_p2 = hearts_information_state(p2, r.rs, r.observed_log)
    for card in r.rs.zones.instance("hand", first).cards:
        assert str(card) not in info_p2


def test_perfect_recall_no_duplicate_infostates_in_a_game() -> None:
    # Walk one full deterministic game; each player's own-decision info-states
    # must all be distinct (perfect recall).
    seed = 3
    history: list[int] = []
    seen: dict[int, set[str]] = {p: set() for p in range(4)}
    r = run(seed, tuple(history))
    steps = 0
    while isinstance(r, Pause):
        s = hearts_information_state(r.player, r.rs, r.observed_log)
        assert s not in seen[r.player], "duplicate info-state (perfect recall violated)"
        seen[r.player].add(s)
        history.append(r.legal[0])
        r = run(seed, tuple(history))
        steps += 1
        assert steps < 5000


def test_perfect_recall_distinguishes_own_actions() -> None:
    r0 = run(0, ())
    assert isinstance(r0, Pause)
    a, b = r0.legal[0], r0.legal[1]
    ra = run(0, (a,))
    rb = run(0, (b,))
    assert isinstance(ra, Pause) and isinstance(rb, Pause)
    ia = hearts_information_state(ra.player, ra.rs, ra.observed_log)
    ib = hearts_information_state(rb.player, rb.rs, rb.observed_log)
    assert ia != ib  # the player's own (different) action changes their info-state
