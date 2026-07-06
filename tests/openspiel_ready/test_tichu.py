"""Tichu — OpenSpiel readiness.

Bounded conformance walk: Tichu runs to 1000 points (~15-25 hands x ~100-200
climb decisions plus the 12-pick push), thousands of actions — the same
O(n^2) full-sim wall as Stud and French Tarot (`pyspiel.random_sim_test`
re-simulates the whole (seed, history) state after every action).
"""

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_tichu", "tichu.cardlang", conformance_steps=120)


def test_push_derives_hidden_observations() -> None:
    """The push is where hidden cards change hands without ever becoming
    public: each giver picks three cards in ONE chooser draw (decomposed to
    three card actions by the replay chooser), and pick i goes to the i-th
    other player in seat order, giver-major. Per the zone projections (hand
    and gift are both owner-visible), the giver alone sees their picks, each
    receiver sees exactly the card that landed in their hand AND which giver's
    pile it came from (real Tichu: you know who passed you what), and a
    bystander sees counts on both sides. The score goldens can't witness any
    of this — the observation stream is the only proof the push derives
    per-observer."""
    path = str(GAMES_DIR / "tichu.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    while len(history) < 12:  # the full push: 4 givers x 3 decomposed picks
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt

    # The giver's three picks are the giver's alone (identity in their log).
    chose0 = [e[1] for e in r.obs_logs[0] if e[0] == "chose"]
    assert len(chose0) == 3

    def gift_moves(log: list[tuple[Any, ...]], src: str, dst: str) -> list[tuple[Any, ...]]:
        return [e for e in log if e[0] == "move" and e[1] == src and e[3] == dst]

    # The giver's outgoing pile: identity to the giver, counts to everyone else.
    (own_push,) = gift_moves(r.obs_logs[0], "hand[0]", "gift[0]")
    assert isinstance(own_push[2], tuple) and set(own_push[4]) == set(chose0)
    (other_push,) = gift_moves(r.obs_logs[2], "hand[0]", "gift[0]")
    assert other_push[2] == 3 and other_push[4] == 3, "a bystander saw the picks"

    # Giver-major routing witnessed by the receiver: p0's FIRST pick lands in
    # hand[1] (the lowest-numbered other seat), and p1 sees its identity plus
    # the source pile — but the source side collapses to a count.
    (recv,) = gift_moves(r.obs_logs[1], "gift[0]", "hand[1]")
    assert recv[4] == (chose0[0],), "the receiver must see exactly what landed"
    assert recv[2] == 1

    # A bystander sees the same transfer as counts on both sides, and never
    # observes another giver's picks.
    (bystander,) = gift_moves(r.obs_logs[3], "gift[0]", "hand[1]")
    assert bystander[2] == 1 and bystander[4] == 1, "a bystander saw a gift identity"
    leaked = [e for e in r.obs_logs[3] if e[0] == "chose" and e[1] in chose0]
    assert not leaked, f"P3 observed another giver's picks: {leaked}"

    # The pause after the push is the first climbing lead: the Mahjong holder.
    # Their rendered info state shows their own (post-push) hand as identities
    # and every other hand as a bare count.
    leader = r.player
    info = information_state(leader, r.rs, r.obs_logs[leader])
    assert f"hand[{leader}]=[" in info
    for q in range(4):
        if q != leader:
            assert f"hand[{q}]=#14" in info, "an opponent hand rendered as identities"
