"""Pinochle — OpenSpiel readiness (harness defaults), plus a positive
confirmation of the declaration's and opening lead's observation shapes."""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_pinochle",
        "pinochle.cardlang",
        adapter_terminal_steps=100,  # greedy line measured at 65 steps
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

    Policy: `legal[0]` throughout. `submit_bid` sorts before `pass` (ids
    52 < 53), so the auction always runs the full 16 bids to the cap and
    settles deterministically on seat 1 (docs/games/pinochle.cardlang;
    tests/test_pinochle_auction.py pins the same ring-rotation fact); seed 5
    gives seat 1 a marriage, so `declare_trump_suit` is offered and its
    lowest-id enumerated Suit candidate (clubs) is taken.
    """
    path = str(GAMES_DIR / "pinochle.cardlang")
    game, space = load(path)
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
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
        assert isinstance(nxt, Pause), "the hand ended before trump was declared"
        r = nxt
    assert declarer is not None

    # The declaration is a public announcement: every player's log hears it
    # (state variables are public — `trump_suit` is no exception).
    for p, log in r.obs_logs.items():
        assert ("announce", declarer, declared) in log, (
            f"P{p} never observed the trump declaration"
        )

    # The declarer leads the first trick; one more action plays their card.
    assert r.player == declarer, "the declarer leads the first trick"
    history.append(r.legal[0])
    r2 = run(path, seed, tuple(history))
    assert isinstance(r2, Pause), "the hand ended on the opening lead"

    # A non-owner sees the leader's hand shrink count-only (never which card
    # left), while the public `trick_pile` destination is identity to
    # everyone — a follower sees WHAT was led, never what remains unplayed.
    non_owner = next(p for p in r2.obs_logs if p != declarer)
    plays = [
        e for e in r2.obs_logs[non_owner] if e[0] == "move" and e[1] == f"hand[{declarer}]"
    ]
    assert plays, f"P{non_owner} never observed P{declarer}'s card leaving their hand"
    event = plays[0]
    assert isinstance(event[2], int), "a non-owner must see the source hand count-only"
    assert event[3] == "trick_pile"
    assert isinstance(event[4], tuple) and len(event[4]) == 1

    # The converse: the owner's own log shows identity leaving their own hand.
    own_plays = [
        e for e in r2.obs_logs[declarer] if e[0] == "move" and e[1] == f"hand[{declarer}]"
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
