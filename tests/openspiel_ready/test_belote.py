"""Belote (4 players, fixed partnerships) — OpenSpiel readiness.

Depth 12 (the default): seed 5's greedy line takes the turn-up at step 0,
plays out trick 1 (steps 1-4), declines the Belote-Rebelote window (step 5 —
the trick held both trump royals, played by different seats, so the offered
player holds no partner card and the only legal move is the public
`no_belote`), declines the declaration poll four times (steps 6-9), and is
two plays into trick 2 at the pause — real decisions and movements on both
sides of the poll, with the declaration state all-zero on this line, so a
same-suit hidden swap between the two non-pausing opponents replays cleanly
through the poll (a declined declaration is legal in every world).

`swap_axis="suit"` (the default): a follow-suit trick game — a same-suit
swap preserves each hand's suit distribution, so follow/trump-class
legality of every replayed play is unchanged; rank-sensitive over-trump
demands can still reject a pair, which the harness skips.

`conformance_steps=150`: a full game to 1000 runs past 400 decisions, the
O(n^2) re-simulation wall of the score-target class (Bridge, Skat, Tichu).

`adapter_terminal_steps=500`: the seed-5 greedy line reaches Terminal at a
measured 418 steps.

Per-game caveats (recorded, not hidden):

- The generic hidden-swap proof pauses on a line where nobody declared, so
  it certifies indistinguishability around a *declined* poll. Worlds with a
  standing announcement are covered by the dedicated declaration-line test
  below OBSERVATIONALLY (the announced content is byte-identical in every
  log, the entitled side's cards are revealed, the losing declarer's hand
  still renders count-only) — not by a swap enumeration, because a hand
  that announced "tierce to the ace" is logically pinned to hold it, the
  same announcement-constrained class as Doppelkopf's said-Re ♣Q; the
  constructive world generator that would perturb *within* that class is
  the standing residual of
  docs/open-questions/structural-infoset-proofs.md.
- Phase-level state (the declaration bookkeeping among it) is not part of
  the paused information-state rendering (phase frames unwind at a pause).
  That is WHY Belote's announcements carry their whole content in the move
  name and Rank parameter: the announce event in each observer's log is
  the derivation channel, and the declaration-line test pins it.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs

PATH = str(GAMES_DIR / "belote.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_belote",
        "belote.cardlang",
        conformance_steps=150,
        adapter_terminal_steps=500,
    )


def _drive(
    seed: int, stop: Any, cap: int, rng_seed: int = 1234
) -> Pause:
    """Drive a deterministic line: prefer `say_belote`, then any
    `declare_*`, else a seeded-random legal action, pausing at the first
    decision where `stop(log0)` holds. Fails loudly if the line never gets
    there (the deal changed — re-pin the seed)."""
    _, space = load(PATH)
    rng = random.Random(rng_seed)
    hist: list[int] = []
    r = run(PATH, seed, ())
    for _ in range(cap):
        assert isinstance(r, Pause), "the game ended before the probed event"
        if stop(r.obs_logs[0]):
            return r
        names = {space.to_string(a): a for a in r.legal}
        if "say_belote" in names:
            action = names["say_belote"]
        else:
            action = next(
                (a for s, a in names.items() if s.startswith("declare_")), None
            ) or rng.choice(r.legal)
        hist.append(action)
        r = run(PATH, seed, tuple(hist))
    raise AssertionError(
        f"seed {seed}: the probed event did not occur within {cap} steps — "
        f"the line changed; re-pin the seed for this test"
    )


def _announces(log: list[tuple[Any, ...]], prefixes: tuple[str, ...]) -> list[tuple[Any, ...]]:
    return [
        e
        for e in log
        if e[0] == "announce" and isinstance(e[2], str) and e[2].startswith(prefixes)
    ]


def test_declaration_line_derives_announced_content_and_showing() -> None:
    """The declaration poll's information flow, end to end, on the pinned
    seed-1 line (three declarers, both teams, a trump/plain tie at the top):

    - every observer's log carries the SAME four poll announcements, each
      naming its content (kind + trump status in the move name, the top
      card as the parameter) — the announced facts are common knowledge;
    - the entitled side's declared cards (both partners': the trump tierce
      to the ace wins the comparison for its team) are publicly revealed,
      card by card, and match the announced combinations exactly;
    - the LOSING declarer's announcement is public but their cards are
      not: no reveal touches their hand, which still renders count-only —
      the info sets hold exactly what was announced and nothing more."""
    poll_names = ("declare_", "no_declaration")
    r = _drive(
        1,
        stop=lambda log: len(_announces(log, poll_names)) >= 4,
        cap=80,
    )

    # The pinned line, in poll order from the trick-1 leader (p3, counter-
    # clockwise): p3's trump tierce to the ace beats p1's plain tierce to
    # the ace (the trump bit breaks the tie) and p0's tierce to the 9; p2
    # declined. Entitled: team 1 = {1, 3}, both partners show.
    expected_polls = [
        (3, "declare_tierce_trump(A)"),
        (2, "no_declaration"),
        (1, "declare_tierce(A)"),
        (0, "declare_tierce(9)"),
    ]
    polls0 = [(e[1], e[2]) for e in _announces(r.obs_logs[0], poll_names)]
    assert polls0 == expected_polls, (
        f"the pinned seed-1 declaration line changed: {polls0} — re-pin"
    )
    expected_reveals = [
        ("reveal", "hand[1]", "A♣"),
        ("reveal", "hand[1]", "K♣"),
        ("reveal", "hand[1]", "Q♣"),
        ("reveal", "hand[3]", "A♥"),
        ("reveal", "hand[3]", "K♥"),
        ("reveal", "hand[3]", "Q♥"),
    ]
    for q, log in r.obs_logs.items():
        # Announced content: identical in every observer's log.
        assert [(e[1], e[2]) for e in _announces(log, poll_names)] == expected_polls, (
            f"player {q} heard different announcements"
        )
        # The showing: both entitled partners' tierces, revealed to everyone,
        # matching the announced kind and height (a natural run to the ace in
        # one suit each — the trump one from hand[3]).
        assert [e for e in log if e[0] == "reveal"] == expected_reveals, (
            f"player {q} saw different reveals"
        )
        # Nothing more: the losing declarer's (p0) and the silent player's
        # (p2) cards are in no reveal — checked by the exact lists above.

    # The losing declarer's hand renders count-only to every OTHER observer:
    # their announcement is public, their cards are not.
    n0 = len(r.rs.zones.instance("hand", 0).cards)
    for q in (1, 2, 3):
        info = information_state(q, r.rs, r.obs_logs[q])
        assert f"hand[0]=#{n0}" in info, (
            f"player {q} sees more of the losing declarer's hand than a count"
        )
    # ... while their own recall of their own decision is intact.
    assert any(e[0] == "chose" for e in r.obs_logs[0])


def test_belote_rebelote_reveals_exactly_the_partner_card() -> None:
    """The Belote-Rebelote announcement's information flow on the pinned
    seed-0 line: the sayer (p2) plays the first trump royal (the K♦) into
    the public trick, says belote at the window, and the partner card
    (the Q♦, still in hand) is publicly revealed — so after the
    announcement every observer holds exactly 'p2 had the K and Q of
    trumps': the played royal via the trick's move event, the held one via
    the reveal, and nothing else of p2's hand (still count-only)."""
    r = _drive(
        0,
        stop=lambda log: any(
            e[0] == "announce" and e[2] == "say_belote" for e in log
        ),
        cap=60,
    )
    for q, log in r.obs_logs.items():
        idx = next(
            i for i, e in enumerate(log)
            if e[0] == "announce" and e[2] == "say_belote"
        )
        sayer = log[idx][1]
        assert sayer == 2, "the pinned seed-0 belote line changed — re-pin"
        # No reveal from the sayer's hand before the announcement.
        assert not any(
            e[0] == "reveal" and e[1] == "hand[2]" for e in log[:idx]
        ), f"player {q}: a reveal preceded the announcement"
        # The reveal right after it names the partner royal, in hand.
        reveal = next(e for e in log[idx:] if e[0] == "reveal")
        assert reveal == ("reveal", "hand[2]", "Q♦"), (
            f"player {q}: expected the partner royal, got {reveal}"
        )
        # The played royal reached the public trick before the window: the
        # same suit's OTHER royal, from the sayer's hand, identity to all.
        played_royals = [
            e
            for e in log[:idx]
            if e[0] == "move"
            and e[1] == "hand[2]"
            and e[3] == "trick_pile"
            and isinstance(e[4], tuple)
            and "K♦" in e[4]
        ]
        assert played_royals, f"player {q} never saw the K♦ played by the sayer"

    # Beyond the pair, the sayer's hand is still just a count to others.
    n2 = len(r.rs.zones.instance("hand", 2).cards)
    for q in (0, 1, 3):
        info = information_state(q, r.rs, r.obs_logs[q])
        assert f"hand[2]=#{n2}" in info


def test_declined_window_reveals_nothing() -> None:
    """The window's decline arm: on the seed-5 greedy line trick 1 contains
    both trump royals, played by DIFFERENT seats — the offered player holds
    no partner card, so the only legal move is `no_belote`. The decline is
    a public announcement in every log (chosen and forced declines are the
    same observable fact), and no reveal ever fires."""
    hist: list[int] = []
    r = run(PATH, 5, ())
    for _ in range(12):
        assert isinstance(r, Pause)
        hist.append(r.legal[0])
        r = run(PATH, 5, tuple(hist))
    assert isinstance(r, Pause)
    for q, log in r.obs_logs.items():
        assert any(
            e[0] == "announce" and e[2] == "no_belote" for e in log
        ), f"player {q} did not observe the declined window"
        assert not any(e[0] == "reveal" for e in log), (
            f"player {q} saw a reveal on a fully-declined line"
        )
