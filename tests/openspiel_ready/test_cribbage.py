"""Cribbage (2 players) — OpenSpiel readiness.

Depth 4: the deepest pause <= the harness default whose pauser is player 0
(probed at seed 5) — player 0 discards first (seat-order for-each) and
always leads pegging as the non-dealer (`dealer: Player = 0` flips to 1 in
the first before_each), so depth 4 (both players' two discard picks each,
decomposed to 4 sequential actions) is exactly player 0's first pegging
draw. With only 2 players, the swappable opponent is necessarily the same
seat throughout, so the pause must coincide with the first decider
(`p == d0`, seat 0 discards first too) — true here, and true at every
deeper p0 pause this seed reaches.

`stock_swap_skip=1`: how many leading stock cards to exclude from the swap
pool. This is defensive/redundant at the current depth-4 pause: the pool is
sourced from the paused (post-cut) deck, where the starter already sits in
the `starter` zone and `deck[0]` is an ordinary card, so the swap cannot
touch the starter regardless. (The starter stays identical across both swap
worlds structurally — the cut deals off the deck head while a swapped card
is appended to the tail.) Kept at 1 so a shallower, pre-cut pause could not
swap the imminent public starter.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_cribbage",
        "cribbage.cardlang",
        depth=4,
        stock_swap_skip=1,
        adapter_terminal_steps=210,  # greedy line measured at 156 steps
    )


def test_discard_and_pegging_derive_observations() -> None:
    """Cribbage's crib discard and pegging are the first time this game's
    decisions run through the kernel's decision/movement sites rather than a
    Python mechanic that traced only `cribbage_show` (dropped, no consumer) —
    a total info-set leak, not just an incomplete one (the Pinochle/Tarot
    precedent). Seed 5, greedy `legal[0]` throughout (the same seed and policy
    the spec's depth=4 is probed against, module docstring above): player 0
    discards first (seat-order for-each) and always leads pegging as the
    non-dealer.

    The crib's contents are never revealed even at the show (only the score
    delta signals it, matching the deleted monolith, which never moved the
    crib either) — a faithful table reveal is deferred fidelity work, not
    this migration.
    """
    path = str(GAMES_DIR / "cribbage.cardlang")
    _game, _space = load(path)
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    assert r.player == 0, "player 0 discards first"

    # Player 0's two discard picks (k=2 decomposes to 2 sequential actions).
    for _ in range(2):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode)
        r = nxt
    assert r.player == 1, "player 1 discards next"

    # P0's own discard: identity on the source (their own hand), COUNT-ONLY
    # into the crib even for the discarder's own view (FaceDownPile is
    # count-only to EVERYONE, not just opponents — the crib stays hidden from
    # the dealer too), plus the two per-pick "chose" events in P0's log only.
    own_log = r.obs_logs[0]
    own_discard = next(
        e for e in own_log if e[0] == "move" and e[1] == "hand[0]" and e[3] == "crib"
    )
    assert isinstance(own_discard[2], tuple) and len(own_discard[2]) == 2
    assert own_discard[4] == 2
    assert len([e for e in own_log if e[0] == "chose"]) == 2

    # P1's view of the same event: count-only on BOTH sides, no "chose"
    # leakage (P1 hasn't acted yet, so their log has none at all).
    opp_log = r.obs_logs[1]
    opp_view = next(
        e for e in opp_log if e[0] == "move" and e[1] == "hand[0]" and e[3] == "crib"
    )
    assert opp_view[2] == 2 and opp_view[4] == 2
    assert not any(e[0] == "chose" for e in opp_log)

    # Player 1's two discard picks.
    for _ in range(2):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode)
        r = nxt
    assert r.player == 0, "player 0 (the non-dealer) leads pegging"

    # The starter cut: identity to all (a genuinely public reveal).
    for log in r.obs_logs.values():
        starter_cut = next(
            e for e in log if e[0] == "move" and e[1] == "deck" and e[3] == "starter"
        )
        assert isinstance(starter_cut[4], tuple) and len(starter_cut[4]) == 1

    # Player 0's first pegging play.
    history.append(r.legal[0])
    r2 = run(path, seed, tuple(history))
    assert isinstance(r2, DecisionNode)
    assert r2.player == 1, "pegging alternates to player 1 next"

    # The non-actor (P1) sees the play count-only on the source, identity on
    # the public play_pile destination — WHAT was led, never what remains.
    non_actor_play = next(
        e for e in r2.obs_logs[1] if e[0] == "move" and e[1] == "hand[0]" and e[3] == "play_pile"
    )
    assert non_actor_play[2] == 1
    assert isinstance(non_actor_play[4], tuple) and len(non_actor_play[4]) == 1

    # The actor (P0) sees identity on both sides of their own play.
    actor_play = next(
        e for e in r2.obs_logs[0] if e[0] == "move" and e[1] == "hand[0]" and e[3] == "play_pile"
    )
    assert isinstance(actor_play[2], tuple) and len(actor_play[2]) == 1
    assert actor_play[2] == actor_play[4]

    # Belt-and-braces: P1's rendered info state shows P0's hand and the crib
    # as bare counts, never identity; P0's own hand renders as identity.
    info1 = information_state(1, r2.rs, r2.obs_logs[1])
    assert "crib=#4" in info1
    n0 = len(r2.rs.zones.instance("hand", 0).cards)
    assert f"hand[0]=#{n0}" in info1
    info0 = information_state(0, r2.rs, r2.obs_logs[0])
    assert "crib=#4" in info0  # count-only to everyone — `crib` has no owner index
    assert f"hand[0]=#{n0}" not in info0
    assert "hand[0]=[" in info0
