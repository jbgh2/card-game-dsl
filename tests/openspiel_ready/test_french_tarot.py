"""French Tarot — OpenSpiel readiness.

Depth 3: `pass` (action id 78) sorts below every bid (79-82), so the
harness's greedy `legal[0]` always passes, and this game's four-seat auction
ALWAYS throws the hand in at exactly 4 actions (re-dealing before-each next
hand) — the same crossed-into-a-second-deal shape as Bridge (see
test_bridge.py), confirmed directly: a field-by-field info-state diff at
depth 12 showed only the later re-dealt hands moved, via the
gather-then-shuffle the thrown-in hand's `before_each` runs. Depth 3 stays
inside the still-open first auction, before that reshuffle.

Bounded conformance walk: 36 hands x ~76 decision-picks/hand (~2,740 total)
measured at 436s for the full sim (`pyspiel.random_sim_test` is O(n^2) in
game length) — far past the ~60s keep-it threshold.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_french_tarot",
        "french-tarot.cardlang",
        depth=3,
        # The greedy line passes every hand into the throw-in, so the
        # provenance walk needs one bid to reach a trick at all (see
        # `GameSpec.provenance_opening`); the opener's `bid_petite` is legal
        # at the very first decision on every manifest seed. After it, greedy
        # takes three passes and the six discard picks and then leads.
        provenance_opening=(("bid_petite", None),),
        conformance_steps=120,
        conformance_verbs_unreached=(
            ("bid_garde", ("the auction's higher levels are legal only over a "
                          "standing lower bid, which the seed-7 line never "
                          "produces; the 40-seed sweep in "
                          "tests/test_playout_french_tarot.py bids the ladder")),
            ("bid_garde_sans", "as bid_garde"),
        ),
        adapter_terminal_steps=200,  # greedy line measured at 144 steps
    )


def test_discard_derives_hidden_observations() -> None:
    """French Tarot's chien discard is the fidelity stage's payoff: a
    genuinely HIDDEN reroute (`discard[player]`, not the public captured
    pile the byte-identical migration used). Drives a hand to a Petite
    contract — seat 2 (the opener) takes the ONLY bid (`bid_petite`, forced
    at the very first decision, since greedy `legal[0]` always picks `pass`
    first — the same reason `test_french_tarot_auction.py` and this module's
    depth-3 rationale both note); every later seat then passes under
    `legal[0]`, confirmed by direct probe — and inspects the chien merge and
    the discard directly, rather than relying only on the harness's
    swap-based leak-closure proof (which never positively confirms an
    event's *shape*, per the Pinochle/Stud precedent).
    """
    path = str(GAMES_DIR / "french-tarot.cardlang")
    _game, space = load(path)
    seed = 0

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    taker = r.player  # the opener; the only bidder under this driving policy
    bid_petite_aid = space.encode(("bid_petite", None))
    assert bid_petite_aid in r.legal, "bid_petite must be legal at the first turn"
    history.append(bid_petite_aid)
    r = run(path, seed, tuple(history))
    assert isinstance(r, DecisionNode)

    # Three remaining auction passes, then the six discard picks — nine more
    # `legal[0]` steps (verified by direct probe: `pass` has no guard and
    # always sorts first among the candidates, so every later seat passes).
    for _ in range(9):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "the hand ended before the discard completed"
        r = nxt
    assert r.player == taker, "the taker leads the first trick next"

    taker_log = r.obs_logs[taker]
    defender = next(p for p in r.obs_logs if p != taker)
    defender_log = r.obs_logs[defender]

    # The auction is public: every log hears the bid and every pass.
    for p, log in r.obs_logs.items():
        assert ("announce", taker, "bid_petite") in log, f"P{p} never heard the bid"
        for other in range(4):
            if other != taker:
                assert ("announce", other, "pass") in log, f"P{p} never heard P{other} pass"

    # The chien merge (`chien` -> `hand[taker]`): count-only to a defender on
    # BOTH sides (the chien's own projection is count-only to everyone), but
    # identity into the taker's own hand.
    chien_to_defender = next(e for e in defender_log if e[0] == "move" and e[1] == "chien")
    assert chien_to_defender[2] == 6 and chien_to_defender[4] == 6

    chien_to_taker = next(e for e in taker_log if e[0] == "move" and e[1] == "chien")
    assert isinstance(chien_to_taker[4], tuple) and len(chien_to_taker[4]) == 6

    # The six discard picks surface as six "chose" events in the taker's log
    # only (the choice values themselves must never appear as another
    # player's "chose" — perfect recall of one's own decisions only).
    discarded = {e[1] for e in taker_log if e[0] == "chose"} - {"bid_petite"}
    assert len(discarded) == 6, discarded
    for p, log in r.obs_logs.items():
        if p == taker:
            continue
        leaked = [e for e in log if e[0] == "chose" and e[1] in discarded]
        assert not leaked, f"P{p} observed the taker's private discard choice: {leaked}"

    # The discard movement itself (`hand[taker]` -> `discard[taker]`) — the
    # fidelity payoff — is count-only to a defender on BOTH sides, never the
    # old public-captured-pile leak.
    discard_to_defender = next(
        e for e in defender_log if e[0] == "move" and e[3] == f"discard[{taker}]"
    )
    assert discard_to_defender[1] == f"hand[{taker}]"
    assert discard_to_defender[2] == 6, "source (hand) must be count-only to a defender"
    assert discard_to_defender[4] == 6, "dest (discard) must be count-only to a defender"

    # The taker sees identity on both sides of their own discard, the same
    # six cards leaving one zone and landing in the other.
    discard_to_taker = next(
        e for e in taker_log if e[0] == "move" and e[3] == f"discard[{taker}]"
    )
    assert isinstance(discard_to_taker[2], tuple) and len(discard_to_taker[2]) == 6
    assert isinstance(discard_to_taker[4], tuple) and len(discard_to_taker[4]) == 6
    assert set(discard_to_taker[2]) == set(discard_to_taker[4]) == discarded

    # Info state: a defender's rendering is a bare count; the taker's shows
    # the six actual identities.
    defender_info = information_state(defender, r.rs, r.obs_logs[defender])
    assert f"discard[{taker}]=#6" in defender_info

    taker_info = information_state(taker, r.rs, r.obs_logs[taker])
    assert f"discard[{taker}]=#6" not in taker_info
    assert f"discard[{taker}]=[" in taker_info


def test_the_greedy_line_alone_never_reaches_the_trick_pile() -> None:
    """The measurement `GameSpec.provenance_opening` exists for, executed here
    rather than asserted in a comment.

    `pass` (action id 78) sorts below every bid (79-82), so `legal[0]` throws
    every hand in and the whole 36-hand match is 144 auction actions with no
    card ever played. The provenance proof's own vacuity guard
    (`entries_compared > 0`) is what reddens without the opening -- "the greedy
    line never put a card in ('trick_pile',) within 40 steps" (executed
    2026-08-19, with `provenance_opening` emptied) -- and this says WHY, so the
    next reader does not try to fix it by deepening the walk.

    Completeness of the knob (decisions.md "Closed-domain completeness"):
    property -- a declared opening is legal at every one of its turns and its
    line reaches the zone; domain -- the registered games x {opening, none};
    covered -- `harness._opening`'s two assertions run on every provenance run
    of a spec that declares one, `entries_compared > 0` runs on every spec with
    a provenance domain, and this test covers the one game that declares one;
    residual -- an opening declared where the greedy line already reached would
    change WHICH line is certified without weakening the certificate, since the
    walk certifies every node of whatever line it takes. R4, this ledger owns
    the record.
    """
    from cardlang.openspiel.replay import DecisionNode

    path = str(GAMES_DIR / "french-tarot.cardlang")
    history: list[int] = []
    r = run(path, 3, ())
    steps = 0
    while isinstance(r, DecisionNode) and steps < 400:
        assert not r.rs.zones.single("trick_pile").arrivals, (
            f"step {steps}: the greedy line reached a trick after all -- "
            f"`provenance_opening` is no longer needed for this game"
        )
        history.append(r.legal[0])
        r = run(path, 3, tuple(history))
        steps += 1
    assert steps == 144, f"the greedy line is {steps} actions, not 144"
