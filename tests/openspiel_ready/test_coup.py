"""Coup — OpenSpiel readiness.

Hidden zone `influence`: Coup hides face-down influence cards, not a hand.
"""

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    # No adapter_terminal_steps: interactive Coup's greedy (lowest-id) line
    # never terminates — it loops on the coin-neutral exchange and never
    # challenges, so no forced coup ever fires (the legally-unbounded-lines
    # finding, open-questions/unbounded-lines-and-max-length.md). The
    # adapter proof honestly records terminal=False for this game.
    spec = GameSpec(
        "cardlang_coup",
        "coup.cardlang",
        hidden_zone="influence",
    )


def test_influence_flips_derive_hidden_observations() -> None:
    """Coup is pure hidden-role bluffing, so its observation boundary is the
    whole game: face-down influence must stay counts to everyone but the
    owner, while a lost influence flips PUBLICLY into `revealed` (identity to
    all — real Coup shows the lost card). Greedy lowest-id play never
    challenges (it always answers a window with `allow`), so this walk seeks
    the flip instead: it picks `challenge` whenever a window offers it and
    the highest legal id otherwise (targeted actions over the exchange
    loop) — the first challenge's resolution flips somebody's influence,
    whichever way the proof goes. Then check both sides of the boundary."""
    path = str(GAMES_DIR / "coup.cardlang")
    _, space = load(path)
    challenge_id = space.encode(("challenge", None))
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, DecisionNode)
    for _ in range(60):
        history.append(challenge_id if challenge_id in r.legal else r.legal[-1])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, DecisionNode), "line ended before any influence flip"
        r = nxt
        if any(
            e[0] == "move" and str(e[3]).startswith("revealed[")
            for e in r.obs_logs[0]
        ):
            break

    def flips(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return [e for e in log if e[0] == "move" and str(e[3]).startswith("revealed[")]

    first = flips(r.obs_logs[0])[0]
    loser = int(str(first[1]).split("[")[1].rstrip("]"))
    # Every observer sees the flipped card's identity land in revealed[loser]...
    for q in range(4):
        seen = flips(r.obs_logs[q])[0]
        assert isinstance(seen[4], tuple) and len(seen[4]) == 1, (
            f"P{q} did not see the flip identity"
        )
        # ...but only the loser sees which card left their influence hand.
        if q == loser:
            assert isinstance(seen[2], tuple)
        else:
            assert seen[2] == 1, f"P{q} saw inside influence[{loser}]"

    # The initial deals: identity to the owner, counts to everyone else.
    own_deal = next(
        e for e in r.obs_logs[1]
        if e[0] == "move" and e[1] == "court_deck" and e[3] == "influence[1]"
    )
    assert isinstance(own_deal[4], tuple) and len(own_deal[4]) == 2
    other_deal = next(
        e for e in r.obs_logs[2]
        if e[0] == "move" and e[1] == "court_deck" and e[3] == "influence[1]"
    )
    assert other_deal[4] == 2, "a bystander saw a dealt influence identity"

    # Returns into the deck (influence -> court_deck) stay counts to others,
    # whichever kind: an exchange's two returned cards, or a proven
    # challenge's single returned card (whose identity reaches observers
    # only through the separate public `reveal` event, never the movement).
    returns = [
        e for e in r.obs_logs[2]
        if e[0] == "move" and str(e[1]).startswith("influence[")
        and e[3] == "court_deck" and e[1] != "influence[2]"
    ]
    for e in returns:
        assert isinstance(e[2], int) and isinstance(e[4], int) and e[2] == e[4] in (1, 2), (
            "a deck return leaked identities to a bystander"
        )

    # A bystander's rendered info state: hidden influence is a bare count,
    # the flipped card is in the clear, and no window-internal value beyond
    # the public stands-flags reaches the public state rendering.
    watcher = next(q for q in range(4) if q != loser)
    info = information_state(watcher, r.rs, r.obs_logs[watcher])
    assert f"revealed[{loser}]=[" in info
    assert f"influence[{watcher}]=[" in info  # own hand in the clear


def _challenge_seeking_walk(seed: int, steps: int) -> "DecisionNode":
    """Drive a line that challenges every window it meets (challenge when
    offered, else the highest legal id — targeted actions over the exchange
    loop) and return the pause after `steps` actions."""
    path = str(GAMES_DIR / "coup.cardlang")
    _, space = load(path)
    challenge_id = space.encode(("challenge", None))
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    for _ in range(steps):
        history.append(challenge_id if challenge_id in r.legal else r.legal[-1])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode), "line ended early"
        r = nxt
    return r


def test_challenge_decision_is_public() -> None:
    """A challenge is an announced decision: the (actor, "challenge") announce
    reaches EVERY player's observation log and a bystander's derived
    information state — the window decisions the WS5 upgrade added are in the
    partition, not rng invisible to it."""
    r = _challenge_seeking_walk(seed=0, steps=8)
    challenges = [
        e for e in r.obs_logs[0] if e[0] == "announce" and e[2] == "challenge"
    ]
    assert challenges, "no challenge was announced on the challenge-seeking line"
    first = challenges[0]
    for q in range(4):
        assert first in r.obs_logs[q], f"P{q} did not observe the public challenge"
    watcher = next(q for q in range(4) if q != int(first[1]))
    info = information_state(watcher, r.rs, r.obs_logs[watcher])
    assert repr(first) in info, "the challenge is absent from a bystander's info state"


def test_reveal_reaches_every_information_state() -> None:
    """A proven challenge `reveal`s the shown card publicly: the reveal event
    appears verbatim in every player's log and derived information state
    (seed 0's challenge-seeking line proves a claim within 8 steps)."""
    r = _challenge_seeking_walk(seed=0, steps=8)
    reveals = [e for e in r.obs_logs[0] if e[0] == "reveal"]
    assert reveals, "no proven challenge occurred on this line"
    first = reveals[0]
    assert str(first[1]).startswith("influence[")
    for q in range(4):
        assert first in r.obs_logs[q], f"P{q} did not observe the reveal"
        info = information_state(q, r.rs, r.obs_logs[q])
        assert repr(first) in info, f"P{q}'s information state omits the reveal"


def test_blocked_foreign_aid_moves_no_coins() -> None:
    """A blocked, unchallenged foreign aid transfers nothing: actor 0 takes
    foreign aid, player 1 claims the Duke, the block-challenge window (players
    2, 3, and the actor) all allow — the aid never resolves."""
    path = str(GAMES_DIR / "coup.cardlang")
    _, space = load(path)
    fa = space.encode(("foreign_aid", None))
    block = space.encode(("block_claiming_duke", None))
    allow = space.encode(("allow", None))
    r = run(path, 5, (fa, block, allow, allow, allow))
    assert isinstance(r, DecisionNode)
    # (Phase-local window state is unreadable here — the pause's unwind pops
    # phase frames — so the coin economy is the observable proof.)
    assert r.rs.get("coins")[0] == 2, "a blocked foreign aid still paid out"
    assert r.rs.get("treasury") == 42  # 50 - 4x2 setup, untouched since
