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
    )


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
