"""Doppelkopf — OpenSpiel readiness.

Bounded conformance walk (the Skat/Tichu shape): a four-hand session runs to
several hundred decisions, the same O(n^2) re-simulation guard; full-game-to-
TerminalNode coverage lives in `test_openspiel_replay.py`'s KERNEL_GAMES list.

Known swap caveat (the structural-infoset-proofs class): a ♣Q in the hand of
a player who has already announced Re is logically pinned — physically
unobserved, but publicly implied by the announcement's legality. The
harness's swap machinery only proposes pairs the replay accepts, so such
pinned cards are skipped rather than perturbed; the constructive world
generator that would cover them is the recorded residual of
docs/open-questions/structural-infoset-proofs.md.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs

_ANNOUNCE_NAMES = (
    "announce_re",
    "announce_kontra",
    "announce_re_no90",
    "announce_re_no60",
    "announce_re_no30",
    "announce_re_schwarz",
    "announce_kontra_no90",
    "announce_kontra_no60",
    "announce_kontra_no30",
    "announce_kontra_schwarz",
)


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_doppelkopf",
        "doppelkopf.cardlang",
        conformance_steps=120,
        provenance_zones=("trick_pile",),  # doko_trick_winner reads the record
    )


def _encode(space: object, name: str) -> int:
    """Move-name action id (nullary moves encode as the bare name in some
    vocabularies and as (name, None) in others — accept either)."""
    try:
        return space.encode(name)  # type: ignore[attr-defined, no-any-return]
    except (KeyError, ValueError):
        return space.encode((name, None))  # type: ignore[attr-defined, no-any-return]


def test_quiet_poll_lap_is_public_and_leaks_nothing() -> None:
    """The game opens on the announcement poll: four consecutive
    `no_announcement`s close the window and hand the pause to the leader's
    card decision. Every decline is a public announce event in EVERY log —
    a decline chosen and a decline forced are the same observable fact — and
    after the full lap every hidden hand still renders as a bare count."""
    path = str(GAMES_DIR / "doppelkopf.cardlang")
    _, space = load(path)
    na = _encode(space, "no_announcement")

    r = run(path, 7, ())
    assert isinstance(r, DecisionNode)
    leader = r.player
    assert na in r.legal, "the game must open on the announcement poll"

    pollers: list[int] = []
    history: list[int] = []
    for _ in range(4):
        assert isinstance(r, DecisionNode)
        pollers.append(r.player)
        history.append(na)
        nxt = run(path, 7, tuple(history))
        assert isinstance(nxt, DecisionNode)
        r = nxt

    # The poll ring walked one full lap from the leader; the pause after the
    # quiet lap is the leader's card decision over their whole 12-card hand.
    assert sorted(pollers) == [0, 1, 2, 3]
    assert pollers[0] == leader
    assert r.player == leader
    assert na not in r.legal
    # A lead offers every distinct card in hand: the double pack collapses
    # duplicate copies onto one action id, so distinct — not 12 — is the count.
    distinct = {(c.rank, c.suit) for c in r.rs.zones.instance("hand", leader).cards}
    assert len(r.legal) == len(distinct)

    for q in range(4):
        declines = [
            e for e in r.obs_logs[q] if e[0] == "announce" and e[2] == "no_announcement"
        ]
        assert len(declines) == 4, f"P{q} saw {len(declines)} declines, expected 4"
        info = information_state(q, r.rs, r.obs_logs[q])
        for other in range(4):
            if other != q:
                assert f"hand[{other}]=#12" in info, (
                    f"P{q} sees more than a count of hand[{other}] after the poll"
                )


def test_announcement_is_public_and_narrows_by_event_not_by_zone() -> None:
    """An announcement is a public declaration: the announce event reaches
    every player's log and rendered information state. What it teaches about
    the announcer's hand (♣Q or not) arrives through the EVENT — the hand
    zone itself still renders as a bare count to everyone else."""
    path = str(GAMES_DIR / "doppelkopf.cardlang")
    _, space = load(path)
    ann_ids = {_encode(space, name): name for name in _ANNOUNCE_NAMES}
    na = _encode(space, "no_announcement")

    history: list[int] = []
    r = run(path, 7, ())
    announcer: int | None = None
    announced: str | None = None
    for _ in range(60):
        assert isinstance(r, DecisionNode)
        pick = next((a for a in r.legal if a in ann_ids), None)
        if pick is None:
            pick = na if na in r.legal else r.legal[0]
        if pick in ann_ids:
            announcer, announced = r.player, ann_ids[pick]
        history.append(pick)
        nxt = run(path, 7, tuple(history))
        assert isinstance(nxt, DecisionNode), "line ended before any announcement"
        r = nxt
        if announcer is not None:
            break
    assert announcer is not None and announced is not None, (
        "no announcement became legal in 60 steps"
    )

    event = ("announce", announcer, announced)
    assert isinstance(r, DecisionNode)
    for q in range(4):
        assert event in r.obs_logs[q], f"P{q} did not observe the announcement"
        info = information_state(q, r.rs, r.obs_logs[q])
        assert repr(event) in info, f"P{q}'s info state omits the announcement"
        if q != announcer:
            assert f"hand[{announcer}]=#12" in info, (
                "the announcement revealed zone contents, not just the event"
            )
