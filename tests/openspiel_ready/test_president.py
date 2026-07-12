"""President — OpenSpiel readiness.

`swap_axis="rank"`: suits never matter in President — no tie-breaks, no
flushes, no follow-suit — so two worlds differing only by a same-rank
suit swap between hidden hands are the exact indistinguishability class
(a cross-rank swap would change the swapped players' legal sets and what
their recorded plays reveal).

Bounded conformance walk (the Tichu/Doppelkopf shape): a game runs to the
11-point target over ~10-16 hands, thousands of actions — the same O(n^2)
full-sim wall; full-game-to-Terminal coverage through the replay engine
lives in `test_openspiel_replay.py`'s KERNEL_GAMES list.

The dedicated derivation test drives the greedy line across the first
hand boundary into the between-hands exchange — the one moment hidden
cards change hands (the Scum's forced give, the President's chosen
return) — and asserts each observer learns exactly what the projections
entitle them to: identity on their own side of each transfer, a bare
one-card count for bystanders.
"""

from __future__ import annotations

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_president",
        "president.cardlang",
        swap_axis="rank",
        conformance_steps=120,
    )


def _hand_to_hand(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The exchange transfers: the only hand->hand movements in the game."""
    return [
        e
        for e in log
        if e[0] == "move" and e[1].startswith("hand[") and e[3].startswith("hand[")
    ]


def test_exchange_derives_private_observations() -> None:
    """Drive the greedy line through hand 1 into hand 2's exchange. At the
    pause on the President's return decision the Scum's forced give has
    already emitted: the Scum saw the identity of the card they gave (their
    side of the transfer), the President the identity of the card received,
    and every bystander a bare one-card count on both sides. Stepping the
    return once more, the reverse transfer projects the same way — and the
    return, unlike the give, is the President's own chooser draw. Throughout,
    every hidden hand still renders as a count to every non-owner."""
    path = str(GAMES_DIR / "president.cardlang")
    seed = 5
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    for _ in range(400):
        if any(_hand_to_hand(log) for log in r.obs_logs.values()):
            break
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause), "the game ended before any exchange"
        r = nxt
    else:
        raise AssertionError("no exchange within 400 greedy steps")

    # The give's public shape: exactly one hand->hand transfer so far, from
    # the Scum's hand to the President's, one card.
    (give,) = _hand_to_hand(r.obs_logs[0])
    scum = int(give[1].removeprefix("hand[").removesuffix("]"))
    president = int(give[3].removeprefix("hand[").removesuffix("]"))
    assert scum != president

    # The pause is the President's return decision (the give itself was
    # forced — no chooser draw — so the first decision after the hand
    # boundary belongs to the President).
    assert r.player == president

    for q in range(5):
        (e,) = _hand_to_hand(r.obs_logs[q])
        if q == scum:
            assert isinstance(e[2], tuple) and len(e[2]) == 1, "the giver sees their card"
            assert e[4] == 1
        elif q == president:
            assert e[2] == 1
            assert isinstance(e[4], tuple) and len(e[4]) == 1, "the receiver sees the card"
        else:
            assert e[2] == 1 and e[4] == 1, f"bystander P{q} saw the give's identity"

    # Step the President's return: the reverse transfer projects the same
    # way, and the President's own log gains the chooser draw.
    history.append(r.legal[0])
    nxt = run(path, seed, tuple(history))
    assert isinstance(nxt, Pause)
    r = nxt
    for q in range(5):
        back = [e for e in _hand_to_hand(r.obs_logs[q]) if e[1] == f"hand[{president}]"]
        (e,) = back
        if q == president:
            assert isinstance(e[2], tuple) and len(e[2]) == 1
        elif q == scum:
            assert isinstance(e[4], tuple) and len(e[4]) == 1
        else:
            assert e[2] == 1 and e[4] == 1, f"bystander P{q} saw the return's identity"
    assert any(e[0] == "chose" for e in r.obs_logs[president]), (
        "the return must be the President's own recorded decision"
    )

    # Hidden hands stay counts: every non-owner's rendered information state
    # shows every other hand as a bare count, never identities.
    for q in range(5):
        info = information_state(q, r.rs, r.obs_logs[q])
        for other in range(5):
            if other != q:
                n = len(r.rs.zones.instance("hand", other).cards)
                assert f"hand[{other}]=#{n}" in info, (
                    f"P{q} sees more than a count of hand[{other}] after the exchange"
                )


def test_plays_are_public_and_hands_are_counts_early() -> None:
    """After a few opening plays: the trick pile renders publicly (identity
    to every observer — a played set is on the table), and every hidden hand
    renders as a bare count to every non-owner."""
    path = str(GAMES_DIR / "president.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    for _ in range(8):
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt

    pile = sorted(str(c) for c in r.rs.zones.single("trick_pile").cards)
    for q in range(5):
        info = information_state(q, r.rs, r.obs_logs[q])
        if pile:
            assert "trick_pile=[" + ",".join(pile) + "]" in info, (
                f"P{q} does not see the standing trick publicly"
            )
        for other in range(5):
            if other != q:
                n = len(r.rs.zones.instance("hand", other).cards)
                assert f"hand[{other}]=#{n}" in info, (
                    f"P{q} sees more than a count of hand[{other}]"
                )
