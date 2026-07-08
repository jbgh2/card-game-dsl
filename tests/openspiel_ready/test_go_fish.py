"""Go Fish — OpenSpiel readiness.

Four players, hidden `hand`. A public ask's transfer COUNT is observed
(`Hand` -> count_only to non-owners), so an indistinguishable world requires a
same-RANK swap (K♠↔K♥): it preserves every per-rank count and every ask's
legality, hence every public observation. Same-suit (the trick-game default)
is wrong in general: on any line where an observed transfer count depends on
a rank's composition, a same-suit swap changes that count. That's why "rank",
not "suit", is the correct axis for this game as a general property of the
mechanic — independent of whether any one test run happens to probe that
channel (see the caveat below: this particular run doesn't).

Depth 6: the greedy `legal[0]` policy always names the SMALLEST legal
(target, rank) pair, and Go Fish's `ask(target, rank)` guard never consults
the target's hand — only `target != actor` and "actor holds the rank" — so
the smallest legal target is always player 0 (for any actor != 0) or player 1
(for actor 0, since 0 can't target itself). Concretely: every non-zero actor
always asks player 0, and player 0 always asks player 1. Players 2 and 3 are
therefore NEVER named as an ask target under this policy, so their hands
never lose a card to a targeted transfer. At depth 6 the pause lands on
player 1 (p=1), so the harness swaps between hands {2, 3} — exactly the two
hands the greedy policy structurally never touches. This isn't a lucky
artifact of this seed's deal: it holds for any deal, since it follows from the
guard and the target-ordering alone, which is what makes a same-rank swap
between those two hands genuinely invisible to P1 (own hand untouched, and
the swapped hands are never observed as anything but counts, unaffected by a
same-rank swap, all the way through the replayed prefix).

HONESTY CAVEAT — what this test does and doesn't prove: because hands 2/3
are structurally never ask targets at this depth, P1 observes no
transfer-count event that mentions either hand — so this instance shows a
same-rank swap is SUFFICIENT for a valid indistinguishable world, not that it
is NECESSARY here. Checked directly: `swap_axis="suit"` and `"any"` ALSO pass
at this exact (seed=5, depth=6) configuration, because the one channel this
test exists to guard — the public transfer count — is never exercised on
this particular line. So this test does not itself exercise the
transfer-count derivation; it demonstrates a correct instance, not a
discriminating one. The direct semantic Go Fish was chosen to prove — that an
observer derives "the asker holds the named rank" from a public ask — is
instead proven by the dedicated observational test
`test_public_ask_derives_asker_holds_rank` (Task 9), not by this swap test.
The general limitation this reveals — a greedy swap-and-replay harness can
produce a legally-replayed swap that never exercises the adversarial channel
it's meant to probe — is documented in
`docs/open-questions/structural-infoset-proofs.md` ("World-generator gap
(Go Fish)").
"""

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_go_fish",
        "go-fish.cardlang",
        hidden_zone="hand",
        depth=6,
        swap_axis="rank",
    )


def test_public_ask_derives_asker_holds_rank() -> None:
    """An ask is public: naming (target, rank) reaches EVERY player's observation
    log and information state. Because a legal ask requires the asker to hold the
    named rank, that public announce is exactly the evidence from which every
    observer derives 'the asker holds this rank' — the info-set content Go Fish
    exists to prove derivable."""
    path = str(GAMES_DIR / "go-fish.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    for _ in range(40):
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause), "greedy line ended before any ask"
        r = nxt
        if any(e[0] == "announce" and str(e[2]).startswith("ask(") for e in r.obs_logs[0]):
            break

    def asks(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return [e for e in log if e[0] == "announce" and str(e[2]).startswith("ask(")]

    assert asks(r.obs_logs[0]), "no ask was announced on the greedy line"
    first = asks(r.obs_logs[0])[0]
    rendered = str(first[2])              # e.g. "ask(1,6)"

    # The ask is public: identical announce in every player's log.
    for q in range(4):
        assert first in asks(r.obs_logs[q]), f"P{q} did not observe the public ask"

    # And it reaches a bystander's derived information state verbatim.
    asker = int(first[1])
    watcher = next(q for q in range(4) if q != asker)
    info = information_state(watcher, r.rs, r.obs_logs[watcher])
    assert rendered in info, "the public ask is absent from a bystander's info state"


def test_public_ask_hit_transfer_is_a_public_count_not_identity() -> None:
    """A hit — the named rank's holder actually has it — moves ALL of it from
    hand[target] to hand[asker]. Every non-participant's Hand<player>
    projection reduces that transfer to a bare COUNT, never a card identity:
    combined with the ask's public (target, rank) announce, that public count
    is the exact evidence a bystander derives 'the asker now holds N more of
    rank R' from, without ever learning which cards they are. This is the
    transfer-count channel the four-proof indistinguishability test cannot
    exercise at its configured depth (see this module's TestReadiness
    docstring): here it is exercised directly."""
    path = str(GAMES_DIR / "go-fish.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    for _ in range(60):
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause), "greedy line ended before any hit transfer"
        r = nxt
        if any(
            e[0] == "move" and str(e[1]).startswith("hand[") and str(e[3]).startswith("hand[")
            for e in r.obs_logs[0]
        ):
            break

    def hand_moves(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return [
            e for e in log
            if e[0] == "move" and str(e[1]).startswith("hand[") and str(e[3]).startswith("hand[")
        ]

    assert hand_moves(r.obs_logs[0]), "no hand-to-hand transfer (hit) occurred on the greedy line"
    first = hand_moves(r.obs_logs[0])[0]
    target = int(str(first[1]).split("[")[1].rstrip("]"))
    asker = int(str(first[3]).split("[")[1].rstrip("]"))
    assert asker != target

    # Ground truth for how many cards actually transferred: the asker's own
    # log shows the received cards' identities (they own the destination side).
    identity = hand_moves(r.obs_logs[asker])[0][4]
    assert isinstance(identity, tuple) and len(identity) >= 1, (
        "the asker did not see the identity of the cards they received"
    )
    n_transferred = len(identity)

    # Every bystander (neither participant) sees ONLY the count, on BOTH
    # sides of the move — and it reaches their derived information state too.
    for bystander in (q for q in range(4) if q not in (asker, target)):
        seen = hand_moves(r.obs_logs[bystander])[0]
        assert seen[1] == first[1] and seen[3] == first[3]
        assert isinstance(seen[2], int) and seen[2] == n_transferred, (
            f"P{bystander} saw hand[{target}]'s card identities, not a count"
        )
        assert isinstance(seen[4], int) and seen[4] == n_transferred, (
            f"P{bystander} saw hand[{asker}]'s card identities, not a count"
        )
        info = information_state(bystander, r.rs, r.obs_logs[bystander])
        assert repr(seen) in info, (
            f"P{bystander}'s derived information state omits the public transfer count"
        )
