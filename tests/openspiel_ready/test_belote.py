"""Belote (4 players, fixed teams) — OpenSpiel readiness.

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
O(n^2) re-simulation guard of the score-target class (Bridge, Skat, Tichu).

`adapter_terminal_steps=500`: the seed-5 greedy line reaches TerminalNode at a
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

What Belote's information state PUBLISHES, and why that is entitled
-------------------------------------------------------------------
Scope decides publication: game-scoped state renders into the information
state where phase-scoped state does not. Belote's Trick Order rows read the
made trump, and a `trick_order` block is a game clause, so `trump_suit` is
game-level -- and therefore public -- where it used to be phase-level and
invisible. The soundness matrix's `state_vars` count is 8 against 4 before
(two game variables for each of four observers), and the new one is perturbed
and proven visible there.

The information-set PARTITION did not move. Half of that claim is EXECUTED
here and half is a recorded RESIDUAL, and the two are not mixed together:

* executed -- `test_the_published_trump_derives_from_each_observers_log`
  below. Every rendered value re-derives from the reading observer's OWN log,
  because the trump is what the trump-making ANNOUNCED: round one's `take`
  means the turn-up's suit, which is public identity (`turnup : Discard`,
  identity to every observer) and is exactly what lets a parameterless move
  name a suit; round two's `take_suit(s)` names its own. Both arms are
  asserted reached -- the greedy line takes the turn-up, and a driven line
  passes it round to reach `take_suit`.
* residual -- the base-to-head comparison. Measured while the migration
  landed (issue #250 PR 4): over 800 states (40 greedy-line nodes x 4
  observers x 5 manifest seeds) every observer's zone views and observation
  log were byte-identical to the PRE-migration tree, `trump_suit` the only
  key differing in the rendering, at every one of the 800. It cannot become a
  test in this tree -- it needs the pre-migration game file to compare
  against -- so it is a one-shot measurement whose provenance is the commit
  that made it, the same standing as `tests/test_trick_order_migration.py`'s
  own captures. R4, THIS LEDGER ROW owns the record.

So the one variable carries no fact an observer could not already compute,
and no observer's states merge or split. The pre/post byte-identity of PLAY
itself is `tests/test_trick_order_migration.py`, whose ledger delegates this
surface here.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs

PATH = str(GAMES_DIR / "belote.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_belote",
        "belote.cardlang",
        conformance_steps=150,
        adapter_terminal_steps=500,
        # The seed-7 conformance line takes the turn-up in the auction's first
        # round and declares nothing all game, so it never applies:
        conformance_verbs_unreached=(
            ("pass", "the auction's second round: no one passes on this line"),
            ("take_suit", "same — the turn-up suit was taken in round 1"),
            ("say_belote", ("driven deliberately by test_belote_rebelote_"
                           "reveals_exactly_the_partner_card below")),
            ("declare_carre", ("the declaration poll declines throughout this "
                              "line; the poll's announce arms are driven by "
                              "test_declaration_line_derives_announced_content"
                              "_and_showing below")),
            ("declare_quarte_trump", "as declare_carre"),
            ("declare_quinte", "as declare_carre"),
            ("declare_quinte_trump", "as declare_carre"),
            ("declare_tierce", "as declare_carre"),
            ("declare_tierce_trump", "as declare_carre"),
        ),
    )


def _drive(
    seed: int, stop: Any, cap: int, rng_seed: int = 1234
) -> DecisionNode:
    """Drive a deterministic line: prefer `say_belote`, then any
    `declare_*`, else a seeded-random legal action, pausing at the first
    decision where `stop(log0)` holds. Fails loudly if the line never gets
    there (the deal changed — re-pin the seed)."""
    _, space = load(PATH)
    rng = random.Random(rng_seed)
    hist: list[int] = []
    r = run(PATH, seed, ())
    for _ in range(cap):
        assert isinstance(r, DecisionNode), "the game ended before the probed event"
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
        assert isinstance(r, DecisionNode)
        hist.append(r.legal[0])
        r = run(PATH, 5, tuple(hist))
    assert isinstance(r, DecisionNode)
    for q, log in r.obs_logs.items():
        assert any(
            e[0] == "announce" and e[2] == "no_belote" for e in log
        ), f"player {q} did not observe the declined window"
        assert not any(e[0] == "reveal" for e in log), (
            f"player {q} saw a reveal on a fully-declined line"
        )


# --- the published trump, re-derived from each observer's own log ----------

_TAKE_SUIT = "take_suit("
_SUIT_GLYPH = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}


def _trump_from_log(log: list[tuple[Any, ...]]) -> tuple[str | None, str, int]:
    """The made trump as a seat at the table would write it down from what it
    HEARD, which arm named it, and which hand is running. A hand begins at its
    turn-up (`deck -> turnup`, one per hand and the only movement into that
    zone); `take` means that card's suit, and `take_suit(s)` names its own.
    Reads no engine state and no other seat's view -- that is the whole point.

    The hand INDEX is what makes the pre-take arm worth counting: a first
    hand's auction renders `none` with nothing behind it to be stale, so only
    a LATER hand's auction is the shape the phase's `trump_suit := none`
    protects."""
    trump: str | None = None
    arm = "none"
    turnup: str | None = None
    hand = -1
    for e in log:
        if e[0] == "move" and str(e[1]) == "deck" and str(e[3]) == "turnup":
            turnup = _SUIT_GLYPH[str(e[4][0])[-1]]
            trump, arm = None, "none"
            hand += 1
        elif e[0] == "announce":
            said = str(e[2])
            if said == "take":
                trump, arm = turnup, "take"
            elif said.startswith(_TAKE_SUIT):
                trump, arm = said[len(_TAKE_SUIT) : -1], "take_suit"
    return trump, arm, hand


def _check_line(
    seed: int, history: tuple[int, ...], limit: int, prefer: str | None = None
) -> Any:
    """Walk from `history`, comparing the published trump against each
    observer's own derivation at every node. Returns (facts checked, per-arm
    counts, failures).

    The line is greedy (`legal[0]`) unless `prefer` names an action string
    still on offer -- passing `"pass"` keeps an auction OPEN instead of
    ending it on the first take, which is how the pre-take arm is reached
    more than one node deep."""
    checked = 0
    arms: dict[str, int] = {}
    failures: list[str] = []
    hist = list(history)
    r = run(PATH, seed, tuple(hist))
    while isinstance(r, DecisionNode) and len(hist) - len(history) < limit:
        for q in sorted(r.obs_logs):
            rendered = dict(
                kv.split("=", 1)
                for kv in information_state(q, r.rs, r.obs_logs[q])
                .split("|", 3)[2]
                .split(";")
                if "=" in kv
            )
            trump, arm, hand = _trump_from_log(r.obs_logs[q])
            want = "None" if trump is None else trump
            checked += 1
            arms[arm] = arms.get(arm, 0) + 1
            if arm == "none" and hand > 0:
                arms["none_after_a_hand"] = arms.get("none_after_a_hand", 0) + 1
            if rendered.get("trump_suit") != want:
                failures.append(
                    f"seed {seed} step {len(hist)} P{q}: the state renders "
                    f"trump_suit={rendered.get('trump_suit')}, but P{q}'s own "
                    f"log derives {want} (via {arm})"
                )
        chosen = r.legal[0]
        if prefer is not None:
            _game, space = load(PATH)
            chosen = next(
                (a for a in r.legal if space.to_string(a) == prefer), chosen
            )
        hist.append(chosen)
        nxt = run(PATH, seed, tuple(hist))
        if not isinstance(nxt, DecisionNode):
            break
        r = nxt
    return checked, arms, failures


def _turnups(log: list[tuple[Any, ...]]) -> int:
    return sum(
        1
        for e in log
        if e[0] == "move" and str(e[1]) == "deck" and str(e[3]) == "turnup"
    )


def _drive_to_the_second_auction(seed: int, cap: int = 80) -> tuple[int, ...]:
    """The greedy line up to the SECOND hand's turn-up, then `pass` while it
    is legal — so the second auction runs several decisions deep instead of
    ending on its first `take`.

    That depth is the point. A first hand's auction renders `trump_suit=None`
    with nothing behind it to be stale, so the arm that witnesses `phase
    play`'s `trump_suit := none` is a LATER hand's auction — and on the greedy
    line that arm is one node wide, close enough to any depth cap that a deal
    shift would drop it silently."""
    _game, space = load(PATH)
    passing = space.encode(("pass", None))
    hist: list[int] = []
    r = run(PATH, seed, ())
    for _ in range(cap):
        assert isinstance(r, DecisionNode), "the game ended before the second deal"
        if _turnups(r.obs_logs[0]) >= 2:
            for _ in range(2):  # open the second auction, then let the walk pass
                if passing not in r.legal:
                    break
                hist.append(passing)
                nxt = run(PATH, seed, tuple(hist))
                if not isinstance(nxt, DecisionNode):
                    break
                r = nxt
            return tuple(hist)
        hist.append(r.legal[0])
        r = run(PATH, seed, tuple(hist))
    raise AssertionError(
        f"seed {seed}: no second hand within {cap} steps — re-pin the seed"
    )


def test_the_published_trump_derives_from_each_observers_log() -> None:
    """`trump_suit` is game-scoped and therefore RENDERS into every
    information state (module docstring). This is the entitlement half: the
    rendered value is a function of what that observer already heard, so
    publishing it merges and splits nothing.

    Both naming arms are asserted reached, and that guard is load-bearing in
    one direction: the greedy line takes the turn-up in round one on every
    manifest seed, so `take_suit` would be zero without the driven line below
    -- and a `take_suit` whose suit the log could not name would be exactly
    the leak this test exists to refuse. The `none` arm is the auction before
    anyone takes, which is where a stale trump from the previous hand would
    show."""
    checked = 0
    arms: dict[str, int] = {}
    failures: list[str] = []
    for seed in (3, 5, 14, 15, 18):
        c, a, f = _check_line(seed, (), 40)
        checked += c
        for k, v in a.items():
            arms[k] = arms.get(k, 0) + v
        failures += f

    # The driven second-round line: everyone passes the turn-up, then the
    # first speaker of round two names a suit.
    _game, space = load(PATH)
    hist = [space.encode(("pass", None))] * 4
    r = run(PATH, 3, tuple(hist))
    assert isinstance(r, DecisionNode)
    named = next(
        a for a in r.legal if space.to_string(a).startswith("take_suit(")
    )
    hist.append(named)
    c, a, f = _check_line(3, tuple(hist), 20)
    checked += c
    for k, v in a.items():
        arms[k] = arms.get(k, 0) + v
    failures += f

    # The driven SECOND-hand auction: the arm a stale trump would show in,
    # several decisions deep rather than the one node the greedy line reaches.
    for seed in (3, 5):
        c, a, f = _check_line(
            seed, _drive_to_the_second_auction(seed), 8, prefer="pass"
        )
        checked += c
        for k, v in a.items():
            arms[k] = arms.get(k, 0) + v
        failures += f

    assert not failures, "\n".join(failures[:6])
    assert checked > 0 and arms.get("take", 0) > 0, arms
    assert arms.get("take_suit", 0) > 0, (
        f"no state ever rendered a round-two named trump ({arms}) — the "
        f"driven line above stopped reaching `take_suit`, so that arm is "
        f"unproven"
    )
    assert arms.get("none_after_a_hand", 0) > 0, (
        f"no state was rendered during a LATER hand's auction ({arms}) — a "
        f"first hand's `none` has nothing behind it to be stale, so this "
        f"proof would no longer reach the shape `phase play`'s "
        f"`trump_suit := none` protects; deepen the walk"
    )
