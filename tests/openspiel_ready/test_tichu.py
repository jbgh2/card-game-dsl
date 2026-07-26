"""Tichu — OpenSpiel readiness.

Bounded conformance walk: Tichu runs to 1000 points (~15-25 hands x ~100-200
climb decisions plus the 12-pick push), thousands of actions — the same
O(n^2) full-sim wall as Stud and French Tarot (`pyspiel.random_sim_test`
re-simulates the whole (seed, history) state after every action).
"""

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_tichu",
        "tichu.cardlang",
        conformance_steps=120,
        conformance_verbs_unreached=(
            (
                "dragon_to_right",
                ("the mirror arm of the dragon gift: `dragon_to_left` IS applied "
                "within the bound, and which opponent the trick is given to is "
                "the same move with the other target. Reaching the right arm on "
                "this line costs 178 steps (measured), and the arms diverge "
                "wildly by rng (337 on seed 0, past 400 on seed 1) — depth buys "
                "a coin flip here, not coverage"),
            ),
        ),
    )


def _decline_ids(space: object) -> set[int]:
    """The action ids that wave a call window through (decline the grand,
    stay silent in a small-tichu poll)."""
    out = set()
    for name in ("decline_grand", "no_call"):
        try:
            out.add(space.encode(name))  # type: ignore[attr-defined]
        except (KeyError, ValueError):
            out.add(space.encode((name, None)))  # type: ignore[attr-defined]
    return out


def _walk_through_push(path: str, seed: int) -> Pause:
    """Advance past the grand-tichu offers and small-tichu polls (declining
    everything) and through the 12 push picks; return the pause after."""
    _, space = load(path)
    declines = _decline_ids(space)
    history: list[int] = []
    picks = 0
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    while picks < 12:
        quiet = [a for a in r.legal if a in declines]
        if quiet:
            history.append(quiet[0])
        else:
            history.append(r.legal[0])  # a push pick (card action)
            picks += 1
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
    # Clear the post-push poll too, so the pause is the first climbing lead.
    while any(a in declines for a in r.legal):
        history.append(next(a for a in r.legal if a in declines))
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
    return r


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
    per-observer. The walk declines the grand-tichu offers and small-tichu
    polls on the way (their publicity has its own test below)."""
    path = str(GAMES_DIR / "tichu.cardlang")
    r = _walk_through_push(path, 5)

    # The giver's three picks are the giver's alone (identity in their log).
    # The walk's declined windows are also "chose" events; the picks are the
    # card-valued remainder.
    chose0 = [
        e[1]
        for e in r.obs_logs[0]
        if e[0] == "chose" and str(e[1]) not in ("decline_grand", "no_call")
    ]
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


def test_call_windows_are_public_announced_decisions() -> None:
    """The WS5 upgrade's whole point: grand and small tichu are decisions in
    the observation stream, not rng. Drive player 0's grand call at the deal
    window and a small-tichu call at the first poll; both announce events
    must reach EVERY log and rendered information state, while the callers'
    hands stay bare counts to everyone else (the call teaches strategy, not
    contents)."""
    path = str(GAMES_DIR / "tichu.cardlang")
    _, space = load(path)
    declines = _decline_ids(space)

    def encode(name: str) -> int:
        try:
            return space.encode(name)
        except (KeyError, ValueError):
            return space.encode((name, None))

    grand = encode("call_grand_tichu")
    small = encode("call_tichu")

    r = run(path, 5, ())
    assert isinstance(r, Pause)
    grand_caller = r.player
    assert grand in r.legal, "the game must open on the grand-tichu window"
    history: list[int] = [grand]

    small_caller: int | None = None
    for _ in range(40):
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
        if small_caller is not None:
            break
        if small in r.legal:
            small_caller = r.player
            history.append(small)
        elif any(a in declines for a in r.legal):
            history.append(next(a for a in r.legal if a in declines))
        else:
            break  # deal chance/push reached without a small window (unexpected)
    assert small_caller is not None, "no small-tichu window offered a call"
    assert small_caller != grand_caller, "the grand caller must be barred from small"

    grand_ev = ("announce", grand_caller, "call_grand_tichu")
    small_ev = ("announce", small_caller, "call_tichu")
    assert isinstance(r, Pause)
    for q in range(4):
        assert grand_ev in r.obs_logs[q], f"P{q} missed the grand call"
        assert small_ev in r.obs_logs[q], f"P{q} missed the small call"
        info = information_state(q, r.rs, r.obs_logs[q])
        assert repr(grand_ev) in info and repr(small_ev) in info
        for caller in (grand_caller, small_caller):
            if q != caller:
                assert f"hand[{caller}]=[" not in info, (
                    f"P{q} sees inside hand[{caller}] after a call"
                )
