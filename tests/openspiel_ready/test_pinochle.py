"""Pinochle — OpenSpiel readiness (harness defaults), plus a positive
confirmation of the declaration's and opening lead's observation shapes."""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_pinochle",
        "pinochle.cardlang",
        # The greedy line does not terminate, which puts Pinochle with the
        # other multi-hand score-target games. `throw_in` sorts below
        # `play_on`, so `legal[0]` concedes every hand: no side ever takes a
        # trick point, the declaring side is set by its bid each hand, and the
        # declarer alternates with the deal, so both scores fall without bound
        # and neither reaches the target. Measured 2026-09-21: 900 greedy
        # steps over 32 hands on seed 3, still not terminal. The conformance
        # walk draws randomly, not greedily, so it still reaches the tricks.
        adapter_terminal_steps=None,
    )


def test_declaration_and_lead_derive_observations() -> None:
    """Pinochle's trump declaration and its twelve strict tricks are the first
    time this game's decisions run through the kernel's decision/movement sites
    (docs/kernel-migration.md) rather than a Python mechanic that called
    `ctx.trace` only — a total info-set leak (no observer calls at all), not
    just an incomplete one. This drives a hand past the declaration and its
    opening lead and inspects the actual observation tuples, rather than
    relying only on the harness's swap-based leak-closure proof (which shows
    hidden cards don't change the information state, but never positively
    confirms an event's *shape*).

    Policy: `legal[0]`, with one named exception. `submit_bid` sorts before
    `pass` (ids 52 < 53), so the auction always runs the full 16 bids to the
    cap and settles deterministically on seat 1 (docs/games/pinochle.cardlang;
    tests/test_pinochle_auction.py pins the same ring-rotation fact), and the
    declaration takes the lowest-id enumerated Suit candidate. Between the
    declaration and the lead the partner passes four cards across and the
    declarer passes four back, all of them greedy. The exception is the
    declarer's concession: `throw_in` sorts below `play_on`, so a greedy pick
    there settles the hand without a trick, and this walk names `play_on` at
    that one node because an opening lead is what it is here to inspect.
    """
    path = str(GAMES_DIR / "pinochle.cardlang")
    _game, space = load(path)
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    declarer: int | None = None
    declared: str | None = None
    while declared is None:
        names = [space.to_string(a) for a in r.legal]
        if declarer is None and any(n.startswith("declare_trump_suit") for n in names):
            declarer = r.player
        aid = r.legal[0]
        chosen = space.to_string(aid)
        if declarer is not None and chosen.startswith("declare_trump_suit"):
            declared = chosen
        history.append(aid)
        assert len(history) < 30, "trump was never declared within 30 steps"
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "the hand ended before trump was declared"
        r = nxt
    assert declarer is not None

    # The declaration is a public announcement: every player's log hears it
    # (state variables are public — `trump_suit` is no exception).
    for p, log in r.obs_logs.items():
        assert ("announce", declarer, declared) in log, (
            f"P{p} never observed the trump declaration"
        )

    # The exchange and the concession decision stand between the declaration
    # and the lead. Walk them greedily, except at the concession.
    while True:
        names = [space.to_string(a) for a in r.legal]
        conceding = "play_on" in names
        history.append(r.legal[names.index("play_on")] if conceding else r.legal[0])
        assert len(history) < 60, "the opening lead was never reached"
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "the hand ended before the opening lead"
        r = nxt
        if conceding:
            break

    # The declarer leads the first trick; one more action plays their card.
    assert r.player == declarer, "the declarer leads the first trick"
    history.append(r.legal[0])
    r2 = run(path, seed, tuple(history))
    assert isinstance(r2, DecisionNode), "the hand ended on the opening lead"

    # A non-owner sees the leader's hand shrink count-only (never which card
    # left), while the public `trick_pile` destination is identity to
    # everyone — a follower sees WHAT was led, never what remains unplayed.
    non_owner = next(p for p in r2.obs_logs if p != declarer)
    plays = [
        e
        for e in r2.obs_logs[non_owner]
        if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == "trick_pile"
    ]
    assert plays, f"P{non_owner} never observed P{declarer}'s card leaving their hand"
    event = plays[0]
    assert isinstance(event[2], int), "a non-owner must see the source hand count-only"
    assert event[3] == "trick_pile"
    assert isinstance(event[4], tuple) and len(event[4]) == 1

    # The converse: the owner's own log shows identity leaving their own hand.
    own_plays = [
        e
        for e in r2.obs_logs[declarer]
        if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == "trick_pile"
    ]
    assert own_plays and isinstance(own_plays[0][2], tuple), (
        f"P{declarer} should see their own card's identity leaving their hand"
    )

    # And the non-owner's full information state renders every OTHER hand
    # (including the ones that haven't played yet) as counts, never identity.
    info = information_state(non_owner, r2.rs, r2.obs_logs[non_owner])
    for q in r2.obs_logs:
        if q == non_owner:
            continue
        n = len(r2.rs.zones.instance("hand", q).cards)
        assert f"hand[{q}]=#{n}" in info, f"P{non_owner} sees P{q}'s hand as more than a count"


def test_the_exchange_is_in_both_partners_information_sets() -> None:
    """The four cards a partner passes reach the declarer's information set and
    nobody else's.

    The exchange is the one movement in this game that carries identity from
    one hand to another, so it is the one place a leak would put a private card
    into three other information sets at once. The harness's swap proof shows
    that hidden cards do not change an information state; this confirms
    positively that the transfer IS in the two partners' states, which a leak
    proof alone cannot distinguish from an exchange that never happened.

    Policy: `legal[0]` to the declaration, then the partner's `pass_four` and
    its four card picks.
    """
    path = str(GAMES_DIR / "pinochle.cardlang")
    _game, space = load(path)
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    declarer: int | None = None
    while declarer is None:
        aid = r.legal[0]
        if space.to_string(aid).startswith("declare_trump_suit"):
            declarer = r.player
        history.append(aid)
        assert len(history) < 30, "trump was never declared within 30 steps"
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "the hand ended before trump was declared"
        r = nxt

    # The declarer's partner sits across, and passes first.
    passer = r.player
    assert passer != declarer, "the declarer's partner passes across, not the declarer"

    # `pass_four` itself, then its four single-card decisions.
    for _ in range(5):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "the hand ended inside the exchange"
        r = nxt

    src, dst = f"hand[{passer}]", f"hand[{declarer}]"
    seen = {
        q: [e for e in log if e[0] == "move" and e[1] == src and e[3] == dst]
        for q, log in r.obs_logs.items()
    }
    for q, events in seen.items():
        assert len(events) == 1, f"P{q} saw {len(events)} exchanges, not one"

    # The passer names what left; the declarer names what arrived; each sees
    # the other end as a bare count.
    assert isinstance(seen[passer][0][2], tuple) and len(seen[passer][0][2]) == 4
    assert seen[passer][0][4] == 4
    assert isinstance(seen[declarer][0][4], tuple) and len(seen[declarer][0][4]) == 4
    assert seen[declarer][0][2] == 4
    assert set(seen[passer][0][2]) == set(seen[declarer][0][4]), (
        "the cards the partner passed are not the ones the declarer received"
    )

    # The opponents see four cards cross the table and no identity at either
    # end. The event's shape is the whole statement of that: searching an
    # opponent's rendered information state for a passed card would find one
    # whenever they hold the other copy, since the pack holds two of every
    # card, and would pass for the wrong reason whenever they hold neither.
    for q in seen:
        if q in (passer, declarer):
            continue
        assert seen[q][0][2] == 4 and seen[q][0][4] == 4, (
            f"P{q} sees an identity in an exchange between the other two seats"
        )
