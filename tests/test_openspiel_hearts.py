"""Hearts on the GENERAL OpenSpiel adapter: API conformance, a full rollout,
and the ported info-state regression tests (leakage, mid-pass hiding, perfect
recall, own-action distinction) — now against DERIVED observations."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game  # noqa: F401  (registers all six games on import)
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

HEARTS = str(Path(__file__).resolve().parent.parent / "docs" / "games" / "hearts.cardlang")


def test_random_sim_conformance() -> None:
    game = pyspiel.load_game("cardlang_hearts")
    assert game.num_distinct_actions() == 52
    pyspiel.random_sim_test(game, num_sims=2, serialize=False, verbose=False)


def test_full_rollout_returns_negated_scores() -> None:
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
    assert all(r <= 0 for r in ret)  # lowest-wins: returns are negated penalties
    assert min(ret) < 0  # 26 penalty points exist per hand; someone took some


def test_infostate_does_not_leak_hidden_hands() -> None:
    r = run(HEARTS, 0, ())
    assert isinstance(r, Pause)
    p = r.player
    info_p = information_state(p, r.rs, r.obs_logs[p])
    for q in range(4):
        if q == p:
            continue
        for card in r.rs.zones.instance("hand", q).cards:
            assert str(card) not in info_p, f"leak: {card} (player {q}) in P{p}"


def test_infostate_hides_other_players_pass_mid_simultaneous_pass() -> None:
    seed = 0
    history: list[int] = []
    r = run(HEARTS, seed, ())
    assert isinstance(r, Pause)
    first = r.player
    while isinstance(r, Pause) and r.player == first:
        history.append(r.legal[0])
        r = run(HEARTS, seed, tuple(history))
    assert isinstance(r, Pause) and r.player != first
    p2 = r.player
    # Step one pick into p2's own selection: the pause under test is mid-pass
    # AND mid-selection, where p2's log holds exactly their own single "chose"
    # event (at p2's first pick nothing has been drawn yet, so there would be
    # nothing to distinguish).
    history.append(r.legal[0])
    r = run(HEARTS, seed, tuple(history))
    assert isinstance(r, Pause) and r.player == p2
    info_p2 = information_state(p2, r.rs, r.obs_logs[p2])
    # Mid-pass, transfers have not applied: the first passer's picks are still
    # in their hand, so the hidden-hand check covers the picks themselves.
    for card in r.rs.zones.instance("hand", first).cards:
        assert str(card) not in info_p2
    # And p2 must have received zero "chose" events during the pass beyond
    # their own single selection ("chose" is actor-only by construction).
    assert sum(1 for e in r.obs_logs[p2] if e[0] == "chose") == 1


def test_perfect_recall_no_duplicate_infostates_in_a_game() -> None:
    seed = 3
    history: list[int] = []
    seen: dict[int, set[str]] = {p: set() for p in range(4)}
    r = run(HEARTS, seed, ())
    steps = 0
    while isinstance(r, Pause):
        s = information_state(r.player, r.rs, r.obs_logs[r.player])
        assert s not in seen[r.player], "duplicate info-state (perfect recall violated)"
        seen[r.player].add(s)
        history.append(r.legal[0])
        r = run(HEARTS, seed, tuple(history))
        steps += 1
        assert steps < 5000


def test_perfect_recall_distinguishes_own_actions() -> None:
    r0 = run(HEARTS, 0, ())
    assert isinstance(r0, Pause)
    a, b = r0.legal[0], r0.legal[1]
    ra = run(HEARTS, 0, (a,))
    rb = run(HEARTS, 0, (b,))
    assert isinstance(ra, Pause) and isinstance(rb, Pause)
    ia = information_state(ra.player, ra.rs, ra.obs_logs[ra.player])
    ib = information_state(rb.player, rb.rs, rb.obs_logs[rb.player])
    assert ia != ib
