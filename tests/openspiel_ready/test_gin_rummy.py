"""Gin Rummy (2 players) — OpenSpiel readiness.

Depth 9: the deepest pause <= the harness default whose pauser is the FIRST
decider (the 2-player swap precondition, p == d0) — gin's first decider is
seat 1, the non-dealer, who gets the upcard ritual's first offer (probed at
seed 5: p1 pauses at depths 0/2/3/7/8/9, p0 at 1/4/5/6/10/11/12). With 2
players the swappable opponent is the same seat throughout.

`swap_axis="any"`: gin publishes card identity only for cards that have
LEFT the hidden zones (the upcard, open discards, takes from the discard
pile — all public zone traffic), so an opponent-hand/stock swap touches no
publicly-observed card, and the pauser's own legal actions (`gin_can_knock`
over their own hand; the candidate pools of their own chosen movements)
never read the swapped cards. The Stud precedent.

`adapter_terminal_steps=None`: the greedy (legal[0]) line never knocks well
and no-results indefinitely — the multi-hand score-target class (Bridge,
Hearts, Oh Hell, Stud, Skat, Tichu).

Per-game caveat (recorded, not hidden): the showdown's projections — the
face-down knock card staying count-only, shown melds becoming public, the
staging zone's invisibility — are exercised by the playout suite (every
knocked hand in tests/test_playout_gin_rummy.py routes through them) but
not by a replay-driven observation assertion, because the greedy replay
line never reaches a knock. The turn-cycle projections ARE asserted below.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_gin_rummy",
        "gin-rummy.cardlang",
        depth=9,
        swap_axis="any",
        # The full random_sim_test re-simulates the whole (seed, history)
        # state per action — measured ~8 minutes alone for gin's long
        # matches, which dominates the suite on the 2-vCPU CI runner. The
        # bounded random API walk is the sanctioned fallback for the
        # score-target class (harness.py, `conformance_steps`).
        conformance_steps=400,
        # The showdown cluster, the same surface the module caveat above
        # names: a random line knocks about as rarely as the greedy one does,
        # so every verb behind the knock stays unapplied within any affordable
        # bound. `test_knock_line_derives_showdown_observations` below drives a
        # knock deliberately, and tests/test_playout_gin_rummy.py routes every
        # knocked hand of a 30-seed sweep through the arrangement and lay-off
        # decisions.
        conformance_verbs_unreached=(
            ("end_knock", "the knock itself — see above"),
            ("finish_arranging", "post-knock: the knocker arranges melds"),
            ("finish_defense", "post-knock: the defender lays off"),
            ("declare_meld", "post-knock arrangement"),
            ("declare_meld_d", "post-knock defence arrangement"),
            ("lay_off_a", "post-knock lay-off"),
            ("lay_off_b", "post-knock lay-off"),
            ("lay_off_c", "post-knock lay-off"),
            ("<combo>", ("the joint meld-arrangement subsets, offered only "
                        "inside the post-knock arrangement")),
        ),
    )


def test_knock_line_derives_showdown_observations() -> None:
    """The showdown surface, which the greedy line never reaches (the module
    caveat): drive a knock at seed 3 by preferring `end_knock` whenever legal,
    then apply the first joint arrangement decision (a combo-block action)
    and assert its projections — the knocker's own `chose` + identity move,
    the defender's count-only source view, and the knock card's face-down
    count-only arrival on BOTH sides."""
    from cardlang.openspiel.replay import load

    path = str(GAMES_DIR / "gin-rummy.cardlang")
    _, space = load(path)
    seed = 3

    def is_combo(aid: int) -> bool:
        return space.to_string(aid).startswith(("set[", "run["))

    history: list[int] = []
    r = run(path, seed, ())
    combo_pause = None
    for _ in range(120):
        assert isinstance(r, Pause)
        combo = next((a for a in r.legal if is_combo(a)), None)
        if combo is not None:
            knocker = r.player
            history.append(combo)
            nxt = run(path, seed, tuple(history))
            assert isinstance(nxt, Pause)
            combo_pause = nxt
            break
        knock = next(
            (a for a in r.legal if space.to_string(a) == "end_knock"), None
        )
        history.append(knock if knock is not None else r.legal[0])
        r = run(path, seed, tuple(history))
    assert combo_pause is not None, "no joint arrangement decision within 120 steps"
    defender = 1 - knocker

    # The knocker's own log: the joint pick is a recorded decision (`chose`)
    # and the meld arrival is identity on both sides.
    k_log = combo_pause.obs_logs[knocker]
    assert any(e[0] == "chose" for e in k_log)
    own_meld = next(
        e
        for e in k_log
        if e[0] == "move"
        and str(e[1]).startswith("hand[")
        and str(e[3]).startswith("meld")
    )
    assert isinstance(own_meld[2], tuple) and isinstance(own_meld[4], tuple)

    # The defender's view of the same meld: count-only on the knocker's hand
    # (the source), identity on the public meld pile (the destination).
    d_log = combo_pause.obs_logs[defender]
    d_meld = next(
        e
        for e in d_log
        if e[0] == "move"
        and str(e[1]).startswith("hand[")
        and str(e[3]).startswith("meld")
    )
    assert isinstance(d_meld[2], int) and isinstance(d_meld[4], tuple)

    # The knock card reached `face_down` count-only for BOTH observers on the
    # destination side (the knocker's own source view stays identity — their
    # recall of their own hand).
    for p, log in combo_pause.obs_logs.items():
        fd = next(
            e
            for e in log
            if e[0] == "move" and e[3] == "face_down"
        )
        assert isinstance(fd[4], int), f"player {p} saw the knock card"


def test_turn_cycle_derives_observations() -> None:
    """The draw-discard cycle's projections, on the seed-5 greedy line: a
    stock draw is count-only to the opponent and identity to the drawer; an
    open discard's arrival on `discard_top` is identity to both; the
    rendered info states show the own hand as identity and the opponent's
    as a bare count."""
    path = str(GAMES_DIR / "gin-rummy.cardlang")
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    for _ in range(12):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
    assert r.player == 0  # the probed depth-12 pauser

    # A stock draw by some player p: identity to p, count-only to the other.
    draws = [
        (p, e)
        for p, log in r.obs_logs.items()
        for e in log
        if e[0] == "move" and e[1] == "deck" and str(e[3]).startswith("hand[")
    ]
    assert draws, "the greedy line drew from stock within 12 steps"
    for p, e in draws:
        drawer = int(str(e[3])[5:-1])
        if p == drawer:
            assert isinstance(e[4], tuple), "drawer sees the drawn card"
        else:
            assert isinstance(e[4], int), "opponent sees a count only"

    # An open discard's arrival: identity to both players (public zone).
    for p, log in r.obs_logs.items():
        arrivals = [
            e
            for e in log
            if e[0] == "move" and str(e[1]).startswith("hand[") and e[3] == "discard_top"
        ]
        assert arrivals, "someone discarded within 12 steps"
        for e in arrivals:
            assert isinstance(e[4], tuple) and len(e[4]) == 1

    # Rendered info states: own hand identity, opponent hand count-only.
    n1 = len(r.rs.zones.instance("hand", 1).cards)
    info0 = information_state(0, r.rs, r.obs_logs[0])
    assert "hand[0]=[" in info0
    assert f"hand[1]=#{n1}" in info0
    info1 = information_state(1, r.rs, r.obs_logs[1])
    assert "hand[1]=[" in info1
    assert f"hand[1]=#{n1}" not in info1
