"""500 (4 players, partnerships) — OpenSpiel readiness, plus positive
confirmations of the two knowledge moments the game was added for: the
open-misère mid-phase reveal (the declarer's hand becomes public for every
observer identically, carried entirely by a movement into a PublicHand zone)
and the no-over-reveal converse (in a non-open contract the declarer's hand
stays a count to the defenders all hand).

Full `pyspiel.random_sim_test` measured 0.4s locally (random 500 games are
short — a failed high contract ends the game at -500 in one or two hands), so
the spec keeps the default full conformance sim. The greedy line terminates
in 55 steps, so `adapter_terminal_steps` walks it to the end and compares
terminal returns.

The auction-mask probes double as this change's misuse-probe rejection tests
in the runtime's currency (an illegal bid is an absent action, not a crash):
misère before any seven bid, a raise above 10NT, and the deck-derived
"joker" pseudo-strain as a bid or a nomination must all be masked out.
"""

from __future__ import annotations

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run
from cardlang.runtime.values import Card

from .harness import GAMES_DIR, GameSpec, ReadinessProofs

PATH = str(GAMES_DIR / "five-hundred.cardlang")

_RANK = {"A": 11, "K": 10, "Q": 9, "J": 8, "10": 7, "9": 6, "8": 5, "7": 4, "6": 3, "5": 2, "4": 1, "Joker": 100}


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_five_hundred",
        "five-hundred.cardlang",
        adapter_terminal_steps=400,  # greedy line measured 55 steps
    )


def _drive_open_misere(seed: int) -> tuple[list[int], Pause] | None:
    """Drive: dealer 1, opener P2 bids open misère, the rest pass; P2 takes
    the kitty (three greedy discard picks), declines the nomination, and
    trick 1 is steered to make the DECLARER LOSE it (he leads his lowest;
    the two active followers play their highest of the suit led), so the
    misère survives into trick 2 — where the exposure fires. Returns None
    when the steering fails for this seed (the declarer's lowest card still
    won the trick)."""
    _game, space = load(PATH)
    om = space.encode(("bid_open_misere", None))
    pa = space.encode(("pass", None))
    decline = space.encode("decline_nomination")
    declarer = 2

    hist: list[int] = [om, pa, pa, pa]
    r = run(PATH, seed, tuple(hist))
    assert isinstance(r, Pause)
    for _ in range(3):  # the three kitty discard picks
        hist.append(r.legal[0])
        r = run(PATH, seed, tuple(hist))
        assert isinstance(r, Pause)
    hist.append(decline)
    r = run(PATH, seed, tuple(hist))
    assert isinstance(r, Pause)

    led: str | None = None
    for _ in range(3):  # trick 1: three plays (the dead seat 0 is skipped)
        assert isinstance(r, Pause)
        cards = [(a, space.decode(a)) for a in r.legal]
        cards = [(a, c) for a, c in cards if isinstance(c, Card)]
        if r.player == declarer:
            aid, c = min(cards, key=lambda ac: _RANK[ac[1].rank])
            led = c.suit
        else:
            same = [(a, c) for a, c in cards if c.suit == led]
            aid, _ = max(same or cards, key=lambda ac: _RANK[ac[1].rank])
        hist.append(aid)
        nxt = run(PATH, seed, tuple(hist))
        if not isinstance(nxt, Pause):
            return None  # declarer won trick 1: game over, steering failed
        r = nxt
    return hist, r


def test_auction_masks_are_the_ladder_rules() -> None:
    """The bid guards in the runtime's currency: an illegal bid is an absent
    action. At the empty auction: misère is masked (no seven bid yet), open
    misère and every real strain are open, and the deck-derived "joker"
    pseudo-strain is masked. After ♠6-♠7, misère opens; above its rung it
    closes again."""
    _game, space = load(PATH)
    bid_s = space.encode(("submit_bid", "spades"))

    r = run(PATH, 3, ())
    assert isinstance(r, Pause)
    legal = {space.decode(a) for a in r.legal}
    assert ("bid_misere", None) not in legal, "misère before any seven bid"
    assert ("bid_open_misere", None) in legal
    assert ("submit_bid", "joker") not in legal, "the joker pseudo-strain"
    for strain in ("spades", "clubs", "diamonds", "hearts", None):
        assert ("submit_bid", strain) in legal

    # ♠6 then ♠7 (the cheapest spade raise): the standing bid is a seven
    # bid, so the NEXT seat may bid misère.
    r = run(PATH, 3, (bid_s, bid_s))
    assert isinstance(r, Pause)
    legal = {space.decode(a) for a in r.legal}
    assert ("bid_misere", None) in legal

    # Once the standing bid passes the misère rung it closes again.
    r = run(PATH, 3, (bid_s, bid_s, space.encode(("submit_bid", None))))  # 7NT? no: NT>7♠ -> 7NT
    assert isinstance(r, Pause)
    legal = {space.decode(a) for a in r.legal}
    assert ("bid_misere", None) in legal  # 7NT stands: still a seven bid
    r = run(PATH, 3, (bid_s, bid_s, space.encode(("submit_bid", None)), space.encode(("submit_bid", "spades"))))
    assert isinstance(r, Pause)
    legal = {space.decode(a) for a in r.legal}
    assert ("bid_misere", None) not in legal  # 8♠ stands: misère closed


def test_open_misere_reveal_reaches_every_observer_and_only_then() -> None:
    """The named knowledge event: BEFORE the reveal the declarer's hand is a
    count to everyone else (his kitty picks and buried discards included);
    once the first trick has been played, the exposure movement lands the
    identities in EVERY observer's log, and every information state renders
    the exposed hand in full — the opposing information sets genuinely
    contain the revealed cards. The declarer's sat-out partner (seat 0)
    never acts and his face-down hand stays a count throughout."""
    declarer, partner = 2, 0
    for seed in (3, 4, 5, 7, 8):
        out = _drive_open_misere(seed)
        if out is not None:
            break
    assert out is not None, "no driving seed kept the declarer losing trick 1"
    hist, r = out

    # Pre-reveal: replay to the first-trick pause and check the hand is a
    # count to a defender (10 after the three-card discard).
    pre = run(PATH, seed, tuple(hist[: len(hist) - 3]))
    assert isinstance(pre, Pause)
    for q in (1, 3):
        info = information_state(q, pre.rs, pre.obs_logs[q])
        assert f"hand[{declarer}]=#10" in info, f"P{q} pre-reveal"
        assert f"exposed[{declarer}]=[]" in info

    # Post-trick-1: the exposure fired. Everyone saw the movement WITH
    # identities (the PublicHand projection), and every rendering carries
    # the full exposed hand.
    exposed = [str(c) for c in r.rs.zones.instance("exposed", declarer).cards]
    assert len(exposed) == 9  # ten dealt, one played to trick 1
    for q in range(4):
        ev = next(
            e for e in r.obs_logs[q]
            if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == f"exposed[{declarer}]"
        )
        # (move, src, src_payload, dst, dst_payload): the PublicHand side
        # carries identities to EVERY observer.
        assert isinstance(ev[4], tuple) and len(ev[4]) == 9, f"P{q} saw only counts of the reveal"
        info = information_state(q, r.rs, r.obs_logs[q])
        assert f"exposed[{declarer}]=[" in info and f"exposed[{declarer}]=#" not in info
        for card in exposed:
            assert card in info, f"P{q} missing revealed {card}"
        # The sat-out partner's hand is still face down: a count to everyone
        # but its owner.
        expect = f"hand[{partner}]=[" if q == partner else f"hand[{partner}]=#10"
        assert expect in info

    # The sat-out partner took no part: no play ever left his hand.
    plays = [e for e in r.obs_logs[1] if e[0] == "move" and e[3] == "trick_pile"]
    assert plays and all(e[1] != f"hand[{partner}]" for e in plays)


def test_plain_misere_never_exposes_the_declarer() -> None:
    """The converse: in a NON-open misère nothing extra leaks — the
    declarer's hand stays a count to the defenders for the whole contract,
    and the exposed zone stays empty. Line: ♠6 (P2), ♠7 (P3), misère (P0),
    pass, pass, pass -> P0 declares misère; P2 (P0's partner) sits out."""
    _game, space = load(PATH)
    bid_s = space.encode(("submit_bid", "spades"))
    mis = space.encode(("bid_misere", None))
    pa = space.encode(("pass", None))
    declarer, _partner = 0, 2
    seed = 11

    hist = [bid_s, bid_s, mis, pa, pa, pa]
    r = run(PATH, seed, tuple(hist))
    assert isinstance(r, Pause)
    assert r.player == declarer, "the misère bidder takes the kitty"
    for _ in range(3):  # kitty discards
        hist.append(r.legal[0])
        r = run(PATH, seed, tuple(hist))
        assert isinstance(r, Pause)
    hist.append(space.encode("decline_nomination"))
    r = run(PATH, seed, tuple(hist))

    steps = 0
    while isinstance(r, Pause) and steps < 9:  # three tricks of three plays
        hist.append(r.legal[0])
        r = run(PATH, seed, tuple(hist))
        steps += 1
    if not isinstance(r, Pause):  # the declarer took a trick and play ended
        return
    for q in (1, 3):
        info = information_state(q, r.rs, r.obs_logs[q])
        assert f"hand[{declarer}]=" in info and f"hand[{declarer}]=[" not in info, f"P{q}"
        assert f"exposed[{declarer}]=[]" in info
    # No movement into any exposed zone ever happened.
    assert not any(
        e[0] == "move" and "exposed" in str(e[3]) for log in r.obs_logs.values() for e in log
    )


def test_joker_suit_is_never_nominable() -> None:
    """At the nomination offer the four real suits are offered (when the
    joker is held) and the deck-derived "joker" suit never is. Seed 3's
    declarer holds the joker (the driven reveal line relies on it), so the
    positive arm is exercised, not vacuous."""
    _game, space = load(PATH)
    om = space.encode(("bid_open_misere", None))
    pa = space.encode(("pass", None))
    seed = 3
    hist = [om, pa, pa, pa]
    r = run(PATH, seed, tuple(hist))
    assert isinstance(r, Pause)
    for _ in range(3):
        hist.append(r.legal[0])
        r = run(PATH, seed, tuple(hist))
        assert isinstance(r, Pause)
    decoded = {space.decode(a) for a in r.legal}
    assert "decline_nomination" in decoded
    assert ("nominate_joker_suit", "joker") not in decoded
    assert {("nominate_joker_suit", s) for s in ("clubs", "diamonds", "hearts", "spades")} <= decoded
