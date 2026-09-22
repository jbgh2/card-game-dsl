"""Pinochle — OpenSpiel readiness (harness defaults), plus a positive
confirmation of the declaration's and opening lead's observation shapes."""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, greedy_pick


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_pinochle",
        "pinochle.cardlang",
        # A plain `legal[0]` line plays a game nobody plays and never ends it.
        # `submit_bid` sorts below both ways out, so every seat bids until the
        # ladder hits its ceiling and the contract is 1500 — unmakeable, so the
        # declaring side is set every hand; and `throw_in` sorts below
        # `play_on`, so the hands that are played are conceded instead. Either
        # way no side takes a trick point, and with the declarer rotating on
        # the deal both scores fall without bound.
        #
        # Both preferences are needed and neither is enough (measured
        # 2026-09-21, 30,000-step cap, all five manifest seeds): with neither,
        # with `play_on` alone, and with a way out alone, no line terminates;
        # with both, every line does, in 693 to 2,772 steps. The line then
        # walks the auction, the exchange, the meld and all twelve tricks of
        # every hand to a result.
        greedy_prefers=("pass", "play_on"),
        # The greedy line's length puts Pinochle with the other multi-hand
        # score-target games. With both preferences it DOES reach a result —
        # 693 to 2,772 steps over the manifest, measured 2026-09-21 — but the
        # adapter walk re-simulates per applied action, and the corpus's
        # longest affordable line is Belote's 500. Without them it does not
        # terminate at all within 30,000.
        adapter_terminal_steps=None,
        # A full game under a uniform draw runs past the declared length, so
        # the API conformance proof takes the bounded walk. Every verb the
        # action space declares is applied by step 235 (`throw_in`, the last),
        # measured 2026-09-21.
        conformance_steps=400,
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

    Policy: the spec's own greedy line — `legal[0]`, with `pass` and `play_on`
    preferred where a node offers them. Bare `legal[0]` would bid the ladder to
    its ceiling and reach no declaration at all, which is why the spec declares
    those preferences and why this walk reads them from the spec rather than
    naming its own. The declaration takes the lowest-id enumerated Suit
    candidate; between it and the lead the partner passes four cards across and
    the declarer passes four back.
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
        aid = greedy_pick(space, list(r.legal), TestReadiness.spec.greedy_prefers)
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
        history.append(
            r.legal[names.index("play_on")]
            if conceding
            else greedy_pick(space, list(r.legal), TestReadiness.spec.greedy_prefers)
        )
        assert len(history) < 60, "the opening lead was never reached"
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "the hand ended before the opening lead"
        r = nxt
        if conceding:
            break

    # The declarer leads the first trick; one more action plays their card.
    assert r.player == declarer, "the declarer leads the first trick"
    history.append(greedy_pick(space, list(r.legal), TestReadiness.spec.greedy_prefers))
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
        aid = greedy_pick(space, list(r.legal), TestReadiness.spec.greedy_prefers)
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
        history.append(greedy_pick(space, list(r.legal), TestReadiness.spec.greedy_prefers))
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
