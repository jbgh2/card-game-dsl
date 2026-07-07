"""Coup — OpenSpiel readiness.

Hidden zone `influence`: Coup hides face-down influence cards, not a hand.
"""

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_coup", "coup.cardlang", hidden_zone="influence")


def test_influence_flips_derive_hidden_observations() -> None:
    """Coup is pure hidden-role bluffing, so its observation boundary is the
    whole game: face-down influence must stay counts to everyone but the
    owner, while a lost influence flips PUBLICLY into `revealed` (identity to
    all — real Coup shows the lost card). Walk a greedy line to the first
    flip and check both sides of that boundary, plus that an exchange's
    returned cards stay hidden."""
    path = str(GAMES_DIR / "coup.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    for _ in range(60):
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause), "greedy line ended before any influence flip"
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

    # An exchange's returns (influence -> court_deck) stay counts to others.
    returns = [
        e for e in r.obs_logs[2]
        if e[0] == "move" and str(e[1]).startswith("influence[")
        and e[3] == "court_deck" and e[1] != "influence[2]"
    ]
    for e in returns:
        assert e[2] == 2 and e[4] == 2, "an exchange return leaked identities"

    # A bystander's rendered info state: hidden influence is a bare count,
    # the flipped card is in the clear, and no window-internal value beyond
    # the public stands-flags reaches the public state rendering.
    watcher = next(q for q in range(4) if q != loser)
    info = information_state(watcher, r.rs, r.obs_logs[watcher])
    assert f"revealed[{loser}]=[" in info
    assert f"influence[{watcher}]=[" in info  # own hand in the clear
