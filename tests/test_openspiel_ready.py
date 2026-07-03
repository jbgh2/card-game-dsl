"""The OpenSpiel-readiness proof, per fully-kernel game (SP1 spec, "The proof"):

1. pyspiel API conformance (random_sim_test, or a bounded random API walk for
   games whose full sim is prohibitively long — see CONFORMANCE_STEPS).
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
from cardlang.openspiel.replay import Pause, load, run  # noqa: E402

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"
KERNEL_GAMES = sorted(ogame.GAMES.items())  # (short_name, filename), deterministic order

# The zone family hiding each player's cards — what the swap tests perturb.
# Stud's hidden cards live in `hole` (its `upcards` are public); everyone else
# hides a `hand`.
HIDDEN_ZONE = {"cardlang_seven_card_stud": "hole"}


def _hidden(short_name: str) -> str:
    return HIDDEN_ZONE.get(short_name, "hand")

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

# Full `pyspiel.random_sim_test` re-simulates the whole (seed, history) state
# after every action — O(n^2) in game length — and a Stud game runs until one
# player holds all 400 chips: ~486 hands x ~21 decisions ~ 10k actions, which
# extrapolates to a ~15-minute median full sim. Games in this map instead get
# a bounded random API walk (the sanctioned SP1 bridge-fallback precedent):
# CONFORMANCE_STEPS random legal actions checking current_player/legal-actions
# consistency, info-state string non-crash, chance-node handling, and terminal
# handling if reached. The other games keep the full random_sim_test.
CONFORMANCE_STEPS = {"cardlang_seven_card_stud": 120}


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_pyspiel_conformance(short_name: str, filename: str) -> None:
    game = pyspiel.load_game(short_name)
    steps = CONFORMANCE_STEPS.get(short_name)
    if steps is None:
        pyspiel.random_sim_test(game, num_sims=1, serialize=False, verbose=False)
        return
    rng = random.Random(7)
    state = game.new_initial_state()
    for _ in range(steps):
        if state.is_terminal():
            assert len(state.returns()) == game.num_players()
            break
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            assert abs(sum(p for _, p in outcomes) - 1.0) < 1e-9
            action = rng.choice([a for a, _ in outcomes])
        else:
            player = state.current_player()
            assert 0 <= player < game.num_players()
            legal = state.legal_actions(player)
            assert legal, "a decision node must offer at least one action"
            assert legal == sorted(set(legal)), "legal actions must be sorted, unique"
            assert all(0 <= a < game.num_distinct_actions() for a in legal)
            assert state.information_state_string(player)  # derives, non-crash
            action = rng.choice(legal)
        state.apply_action(action)


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


def _swap_fn(zone: str, opp1: int, opp2: int, x: Any, y: Any) -> Any:
    def swap(rs: Any) -> None:
        h1, h2 = rs.zones.instance(zone, opp1), rs.zones.instance(zone, opp2)
        h1.remove(x)
        h2.remove(y)
        h1.add(y)
        h2.add(x)

    return swap


def _swap_pairs(short_name: str, hand1: list[Any], hand2: list[Any]) -> list[Any]:
    """Swappable hidden-card pairs. Games whose recorded actions are cards (or
    card combos) need same-suit swaps so every recorded action stays legal in
    the swapped world; Stud's recorded actions are betting vocabulary — none
    names a card — so ANY hole swap replays legally (and its two-card holes
    rarely share a suit, so a same-suit filter would starve the pool)."""
    if short_name == "cardlang_seven_card_stud":
        return [(x, y) for x in hand1 for y in hand2 if x != y]
    three_d = ("3", "diamonds")
    return [
        (x, y)
        for x in hand1
        for y in hand2
        if x.suit == y.suit
        and x != y
        # keep the 3♦ fixed: Big Two's opening filter keys on that exact card
        and (x.rank, x.suit) != three_d
        and (y.rank, y.suit) != three_d
    ]


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_indistinguishability_under_hidden_swap(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 5
    depth = DEPTH.get(short_name, DEFAULT_DEPTH)
    hz = _hidden(short_name)
    history, pause_a = _advance(path, seed, depth)
    p = pause_a.player
    first = run(path, seed, ())
    assert isinstance(first, Pause)
    d0 = first.player  # the swap must not touch the first decider (stale candidates)

    others = [q for q in range(len(pause_a.obs_logs)) if q not in (p, d0)]
    assert len(others) >= 2, "harness needs two swappable opponents"
    opp1, opp2 = others[0], others[1]

    # Skip pairs the replay rejects (a rule keyed on the specific card).
    hand1 = pause_a.rs.zones.instance(hz, opp1).cards
    hand2 = pause_a.rs.zones.instance(hz, opp2).cards
    candidates = _swap_pairs(short_name, hand1, hand2)
    assert candidates, "no swap pair available; lower DEPTH for this game"

    info_a = information_state(p, pause_a.rs, pause_a.obs_logs[p])
    last_err: ValueError | None = None
    for x, y in candidates:
        try:
            pause_b = run(path, seed, tuple(history), on_first_decision=_swap_fn(hz, opp1, opp2, x, y))
        except ValueError as e:
            # this pair made a recorded action illegal (ActionSpace.match's
            # "not among the live candidates", or a zone .remove failure);
            # try the next pair, but remember why in case none work.
            last_err = e
            continue
        assert isinstance(pause_b, Pause)
        info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
        assert info_a == info_b, (
            f"{short_name}: swapping hidden {x}<->{y} (players {opp1},{opp2}) "
            f"CHANGED P{p}'s information state — the info-set leaks"
        )
        return  # one successful controlled swap proves the property
    pytest.fail(f"{short_name}: no swap pair produced a legal replay; last replay error: {last_err!r}")


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_soundness_own_view_changes_the_state(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    hz = _hidden(short_name)
    r0 = run(path, 5, ())
    assert isinstance(r0, Pause)
    p = r0.player
    opp = next(q for q in range(len(r0.obs_logs)) if q != p)
    own = r0.rs.zones.instance(hz, p).cards
    theirs = r0.rs.zones.instance(hz, opp).cards
    x, y = next(iter(_swap_pairs(short_name, own, theirs)))
    info_a = information_state(p, r0.rs, r0.obs_logs[p])
    r1 = run(path, 5, (), on_first_decision=_swap_fn(hz, p, opp, x, y))
    assert isinstance(r1, Pause)
    info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
    # The pause player is the same (no actions replayed); their own hand changed.
    assert r1.player == p and info_a != info_b, (
        f"{short_name}: the info-state is insensitive to the player's own hand"
    )


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
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


def _is_stud_reveal_event(e: tuple[Any, ...]) -> bool:
    """A Stud showdown reveal (the park-then-flip `hole[p] -> upcards[p]`
    movement in seven-card-stud.cardlang's showdown block) as any NON-owner
    sees it: `hole[p]` collapses to a count (the owner's own view of the same
    event is a 7-card identity tuple, filtered out here) while `upcards[p]` —
    a PublicHand — stays identity for every observer, all seven merged cards
    landing in the clear at once."""
    return bool(
        e[0] == "move"
        and isinstance(e[1], str) and e[1].startswith("hole[")
        and isinstance(e[2], int)
        and isinstance(e[3], str) and e[3].startswith("upcards[")
        and isinstance(e[4], tuple) and len(e[4]) == 7
    )


def test_stud_showdown_reveals_contenders_holes_to_others() -> None:
    """The showdown block is the one place a Stud hand's hidden hole cards
    become public — and it is exactly what the score goldens can't see (the
    scores are provably insensitive to the reveal) and what this file's own
    proofs above never reach (their swaps pause pre-showdown, `DEFAULT_DEPTH`
    / stud's own comment above). This drives an actual hand past it and
    inspects the emitted events directly: a non-owner learns all seven of a
    contender's cards at once (count-only source, full-identity dest); a
    folded entrant's still-hidden hole cards muck count-only, with no
    identity leak to anyone else.

    The policy is `legal[0]` (check/call, the betting vocabulary's id order
    52..56) throughout, which alone reaches a contested 4-entrant showdown —
    nobody ever folds under it, since call and fold share a guard
    (`bet_to_match > bet_by[actor]`) and call's id sorts lower — except the
    first time `fold` itself is offered, where it is taken once, on purpose,
    to also exercise the folded-entrant guard in the same hand.
    """
    path = str(GAMES_DIR / "seven-card-stud.cardlang")
    game, space = load(path)
    seed = 3

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    folded_player: int | None = None
    reveal: dict[int, tuple[Any, ...]] = {}  # contender -> a non-owner's view of their reveal
    for _ in range(40):
        names = [space.to_string(a) for a in r.legal]
        if folded_player is None and "fold" in names:
            folded_player = r.player
            aid = r.legal[names.index("fold")]
        else:
            aid = r.legal[0]
        history.append(aid)
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause), "the hand ended before a showdown reveal was observed"
        r = nxt
        for log in r.obs_logs.values():
            for e in log:
                if _is_stud_reveal_event(e):
                    reveal[int(e[3][len("upcards["):-1])] = e
        if reveal:
            break
    else:
        pytest.fail("no contested stud showdown reveal within 40 steps")
    assert folded_player is not None, "the drive never saw a legal fold to take"

    contenders = set(reveal)
    assert len(contenders) > 1, "need a CONTESTED showdown (more than one contender)"
    assert contenders == set(range(game.players.low)) - {folded_player}

    # Every contender's reveal is visible to a NON-contender observer (the
    # folded entrant): source count-only over the merged 7-card hand, dest
    # identity with all seven card names.
    folded_log = r.obs_logs[folded_player]
    for p in contenders:
        src, dst = f"hole[{p}]", f"upcards[{p}]"
        matches = [
            e for e in folded_log if _is_stud_reveal_event(e) and e[1] == src and e[3] == dst
        ]
        assert matches, f"P{folded_player} never observed contender {p}'s reveal"
        event = matches[0]
        assert event[2] == 7, "the source view must be count-only over all seven cards"
        assert len(event[4]) == 7 and all(isinstance(c, str) for c in event[4])

    # Converse guard: the folded entrant's own hole cards were never
    # revealed. Their eventual hole -> muck event must stay count-only
    # (trivial dest) in every OTHER player's log — only the owner's own log
    # may show identity, and that isn't a leak.
    saw_fold_muck = False
    for q, log in r.obs_logs.items():
        if q == folded_player:
            continue
        for e in log:
            if e[0] == "move" and e[1] == f"hole[{folded_player}]" and e[3] == "muck":
                saw_fold_muck = True
                assert isinstance(e[2], int), (
                    f"P{q} saw the folded entrant's hole-card identity leak into the muck"
                )
                assert e[4] is None
    assert saw_fold_muck, "the folded entrant's hole cards were never observed mucking"


def test_playtest_report_shape() -> None:
    from cardlang.openspiel.report import playtest_report

    rep = playtest_report("cardlang_getaway", num_games=2, seed=1)
    assert rep["num_games"] == 2
    assert rep["mean_length"] > 0 and rep["mean_branching"] >= 1
    assert len(rep["mean_returns"]) == 4
    assert sum(rep["best_seat_counts"]) == 2
