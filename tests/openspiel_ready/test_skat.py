"""Skat (3 players) — OpenSpiel readiness, plus a positive confirmation of
the Reizen's, pickup's, and discard's shapes.

Bounded conformance walk: the full `pyspiel.random_sim_test` measured 54s
locally (a Skat rubber plays multiple hands to a target score, hundreds of
actions — the same O(n^2) re-simulation cost as Stud/French Tarot/Tichu).
Full-game-to-TerminalNode coverage through the actual pyspiel `State` wrapper
(is_terminal/returns, not just this project's own replay engine) moves to
`test_openspiel_replay.py`'s KERNEL_GAMES list instead, so bounding this
walk drops no real coverage.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_skat",
        "skat.cardlang",
        conformance_steps=120,
        # provenance zones derive from PRIMITIVE_READS.arrival_zones (skat's row)
        provenance_depth=126,  # the greedy line first plays to the trick at 127

        conformance_verbs_unreached=(
            (
                "throw_in",
                ("the hand is thrown in only when all three players pass the "
                "Reizen, which the seed-7 line does not do (and no bound makes "
                "reliable — the outcome is a property of the deal, not of "
                "depth); the 50-seed sweep in tests/test_playout_skat.py plays "
                "enough deals to hit it"),
            ),
        ),
    )


def test_pickup_and_discard_derive_hidden_observations() -> None:
    """Skat's information structure, positively confirmed (the Tarot/Cribbage/
    Schnapsen precedent): the Reizen and every declaration are public
    announcements, the skat pickup is identity only into the declarer's own
    hand (a count to the defenders on both sides), the two-card discard's
    picks are the declarer's alone, and a defender's rendered info state shows
    the declarer's hand and the skat as bare counts.

    The auction roles are seating-derived, so the driven line is
    seed-independent: dealer rotates 0->1 before hand 1, forehand = 2 answers,
    middlehand = 0 speaks, rearhand = 1 speaks second. Both speakers pass, so
    forehand becomes declarer at 18 (play_at_eighteen), picks up the skat,
    discards two, and declares grand — no cards influence any legal set until
    the discard, whose picks we take from the live legal actions.
    """
    path = str(GAMES_DIR / "skat.cardlang")
    _game, space = load(path)
    seed = 3
    declarer, defenders = 2, (0, 1)

    aid = {name: space.encode(name) for name in
           ("play_at_eighteen", "pick_up_skat", "declare_grand")}
    vpass = space.encode(("pass", None))

    history: list[int] = [vpass, vpass, aid["play_at_eighteen"], aid["pick_up_skat"]]
    r = run(path, seed, tuple(history))
    assert isinstance(r, DecisionNode)
    assert r.player == declarer and all(a < 52 for a in r.legal), "the discard pause"
    history.append(r.legal[0])  # first discard pick
    r = run(path, seed, tuple(history))
    assert isinstance(r, DecisionNode)
    history.append(r.legal[0])  # second discard pick
    history.append(aid["declare_grand"])
    r = run(path, seed, tuple(history))
    assert isinstance(r, DecisionNode)
    assert r.player == 2, "forehand leads the first trick"

    # The auction and declarations are public: every log heard both passes and
    # each of the declarer's choices.
    for p, log in r.obs_logs.items():
        assert ("announce", 0, "pass") in log and ("announce", 1, "pass") in log
        for name in ("play_at_eighteen", "pick_up_skat", "declare_grand"):
            assert ("announce", declarer, name) in log, f"P{p} missed {name}"

    # The pickup (skat -> hand[declarer]): identity into the declarer's own
    # hand; the skat side is a count to everyone (FaceDownPile), and a
    # defender sees the hand side as a count too.
    own_pickup = next(
        e for e in r.obs_logs[declarer]
        if e[0] == "move" and e[1] == "skat" and e[3] == f"hand[{declarer}]"
    )
    assert own_pickup[2] == 2 and isinstance(own_pickup[4], tuple) and len(own_pickup[4]) == 2
    for d in defenders:
        seen = next(
            e for e in r.obs_logs[d]
            if e[0] == "move" and e[1] == "skat" and e[3] == f"hand[{declarer}]"
        )
        assert seen[2] == 2 and seen[4] == 2, f"P{d} saw more than counts of the pickup"

    # The discard (hand[declarer] -> skat): the declarer sees the two cards
    # leave; a defender sees counts on both sides; the two "chose" picks are
    # the declarer's alone.
    own_discard = next(
        e for e in r.obs_logs[declarer]
        if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == "skat"
    )
    assert isinstance(own_discard[2], tuple) and len(own_discard[2]) == 2
    discarded = set(own_discard[2])
    for d in defenders:
        seen = next(
            e for e in r.obs_logs[d]
            if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == "skat"
        )
        assert seen[2] == 2 and seen[4] == 2, f"P{d} saw the discard identities"
        leaked = [e for e in r.obs_logs[d] if e[0] == "chose" and e[1] in discarded]
        assert not leaked, f"P{d} observed the declarer's discard picks: {leaked}"

    # A defender's rendered info state: the declarer's hand and the skat are
    # bare counts; the declarer's own rendering shows the hand identities.
    # And no hidden-derived value reaches the public state rendering: the
    # matador count (a function of the declarer's hidden hand + the face-down
    # skat, computed at this point of the hand for the grand contract) must be
    # a local, never a state variable — state renders public to everyone.
    for d in defenders:
        info = information_state(d, r.rs, r.obs_logs[d])
        assert f"hand[{declarer}]=#10" in info
        assert "skat=#2" in info
        assert "matadors" not in info, "the matador count leaked into public state"
    own_info = information_state(declarer, r.rs, r.obs_logs[declarer])
    assert f"hand[{declarer}]=#10" not in own_info
    assert f"hand[{declarer}]=[" in own_info
