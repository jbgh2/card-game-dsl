"""Cheat — OpenSpiel readiness, and the corpus's compound hidden-function probe.

Cheat's challenge is a PUBLIC Boolean function of HIDDEN content (do all the
face-down played cards match the public claimed rank?), answered by flipping
exactly those cards — the mechanic structural-infoset-proofs.md was blocked
on, because it defeats any simple per-card swap axis: whether a hidden card
may move depends on the LINE (was it played? flipped? picked up?), not on any
attribute of the card. So this module carries two layers beyond the shared
proofs:

- **Paired-history channel tests** (`test_face_down_play_...`,
  `test_challenge_verdict_...`, `test_unchallenged_play_...`): two lines
  differing only in a hidden played card are indistinguishable to every
  other player up to the exact moment of a challenge — the window decision
  is provably made under uncertainty — then distinguishable to everyone the
  instant the flip fires (identity + verdict + pile routing), and never
  distinguishable if no one calls. Together: exactly the declared function
  of hidden content leaks, and nothing else.
- **The constructive world generator** (`worlds.py`, built for this game):
  instead of sampling swaps and hoping the replay stays legal and
  unobserved, it derives the pinned set from the line itself (decode pins +
  observer log pins + identity-projection pins) and permutes the entire
  remaining hidden set across hands — validity by construction, asserted
  per observer, plus one discriminating probe per pin class proving the
  analysis is load-bearing (a decode-pin violation trips the replay wall; a
  log-pin violation replays legally but visibly differs — the exact
  "legally-replayed but distinguishable" world the swap harness could not
  rule out).

Coverage manifest. The constructive certificate runs at every seed in
`CONSTRUCTIVE_SEEDS` (= `harness.SWAP_SEEDS`), four observers and two rotations
each; the shared swap proof runs the same manifest. The paired-history probes
below are pinned to seed 5 deliberately: each names the exact cards of that
deal (A♠ against 3♥ under an Aces claim), which is what lets them assert the
channel's identity and routing rather than only its agreement — the deal is
part of the probe, not a sample of it. What generalizes across seeds is the
constructive certificate, and that is what got parametrized.

Shared-proof configuration: `hidden_zone="hand"`; depth 13 pauses the greedy
line (which never challenges: `allow` sorts below `call_cheat`) on player 2's
window decision over seat 1's play, with `d0=0`, so the swap probes pair
hands {1, 3} — both untouched by the replayed prefix, so `swap_axis="any"` is
sound here: on this game a hidden pair either replays legally (neither card
was chosen) and is then genuinely unobserved — every emission that reads
hidden content (the flip) names the cards it read, so unchosen means unseen —
or trips the replay wall and is skipped. The constructive tests above carry
the burden the sampled swap cannot: lines where the hidden-function channel
actually fired. Greedy play_four (lowest vocab id) sheds seat 0's hand in
four unchallenged turns, so the greedy line terminates at 101 steps and the
adapter proof compares terminal returns. The full O(n^2) random_sim_test is
prohibitively long at Cheat's random-line lengths (p95 ~2500 decisions), so
conformance uses the sanctioned bounded walk.
"""

from __future__ import annotations

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, build_deck

from .harness import (
    SWAP_SEEDS,
    GAMES_DIR,
    GameSpec,
    ReadinessProofs,
    action_strings,
    manifest,
)
from .partition import first_divergence, record
from .worlds import permuted_replay, plan_worlds

PATH = str(GAMES_DIR / "cheat.cardlang")

# The constructive certificate's COVERAGE MANIFEST. The same seeds the shared
# swap proof runs (`harness.SWAP_SEEDS`), because both were chosen against both
# proofs' preconditions at once and one manifest is one thing to keep true. Each
# seed deals different hands and drives a different challenge-rich line, so the
# five certificates cover five distinct flip/pickup patterns — the point of more
# than one seed here, since the pins this generator derives (which cards a line
# names, which the observer's log names) are exactly what changes with the line.
CONSTRUCTIVE_SEEDS = SWAP_SEEDS


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_cheat",
        "cheat.cardlang",
        hidden_zone="hand",
        depth=13,
        swap_axis="any",
        conformance_steps=400,
        adapter_terminal_steps=160,  # greedy line measured at 101 steps
    )


# --- the paired-history channel tests -------------------------------------
#
# Seed 5 deals seat 0: 3♠ 3♥ 6♠ 7♦ A♠ A♥ A♦ J♠ J♣ K♠ K♣ Q♠ Q♥. The first
# play must be called as Aces, so playing A♠ is a true claim and 3♥ a lie —
# one hidden card apart, every public emission identical until a flip.


def _ids() -> tuple[int, int, int, int, int]:
    _, space = load(PATH)
    return (
        space.encode(("play_one", None)),
        space.encode(("call_cheat", None)),
        space.encode(("allow", None)),
        space.encode(Card("A", "spades")),
        space.encode(Card("3", "hearts")),
    )


def test_face_down_play_is_uninformative_until_flipped() -> None:
    """Two worlds one hidden played card apart pause byte-identically for
    every other player at the window decision — the call/allow choice is
    provably made under uncertainty (same information state AND same legal
    actions), while the claimant's own state differs (they chose the card)."""
    play_one, _, _, ace, three = _ids()
    _, space = load(PATH)
    ra = run(PATH, 5, (play_one, ace))
    rb = run(PATH, 5, (play_one, three))
    assert isinstance(ra, DecisionNode) and isinstance(rb, DecisionNode)
    assert ra.player == rb.player == 1  # the claimant's left neighbour responds first
    assert ra.legal == rb.legal
    assert action_strings(space, ra.legal) == action_strings(space, rb.legal)
    for q in (1, 2, 3):
        info_a = information_state(q, ra.rs, ra.obs_logs[q])
        info_b = information_state(q, rb.rs, rb.obs_logs[q])
        assert info_a == info_b, (
            f"P{q} can tell A♠ from 3♥ under a face-down play:\n"
            f"witness: {first_divergence(info_a, info_b)}"
        )
    own_a = information_state(0, ra.rs, ra.obs_logs[0])
    own_b = information_state(0, rb.rs, rb.obs_logs[0])
    assert own_a != own_b, "the claimant's own choice is absent from their state"


def test_challenge_verdict_is_a_public_function_of_hidden_content() -> None:
    """The call flips the played card for the whole table and the verdict
    routes the pile: A♠ (true claim) sends the flip + pile to the WRONG
    CHALLENGER's hand, 3♥ (a lie) back to the LIAR's — the public Boolean of
    hidden content, now in every observer's log and information state."""
    play_one, call, _, ace, three = _ids()
    ra = run(PATH, 5, (play_one, ace, call))
    rb = run(PATH, 5, (play_one, three, call))
    assert isinstance(ra, DecisionNode) and isinstance(rb, DecisionNode)

    def flip_and_route(r: DecisionNode, q: int) -> tuple[tuple[object, ...], tuple[object, ...]]:
        flip = next(
            e for e in r.obs_logs[q] if e[0] == "move" and e[3] == "flipped"
        )
        route = next(
            e for e in r.obs_logs[q] if e[0] == "move" and e[1] == "flipped"
        )
        return flip, route

    for q in range(4):
        flip_a, route_a = flip_and_route(ra, q)
        flip_b, route_b = flip_and_route(rb, q)
        assert flip_a[4] == ("A♠",), f"P{q} did not see the true flip identity"
        assert flip_b[4] == ("3♥",), f"P{q} did not see the lying flip identity"
        assert route_a[3] == "hand[1]", "a true claim must cost the challenger"
        assert route_b[3] == "hand[0]", "a caught lie must cost the liar"
        info_a = information_state(q, ra.rs, ra.obs_logs[q])
        info_b = information_state(q, rb.rs, rb.obs_logs[q])
        assert info_a != info_b, f"P{q} cannot see the challenge outcome"

    # The claim cycle is public state and advances either way.
    assert ra.rs.get("claim_rank") == rb.rs.get("claim_rank") == "2"


def test_unchallenged_play_leaks_nothing() -> None:
    """If every responder allows, the play joins the face-down pile and the
    two worlds stay byte-identical for every player but the claimant, through
    the merge and into the next turn — nothing beyond the declared function
    of hidden content ever leaks, because the function was never evaluated."""
    play_one, _, allow, ace, three = _ids()
    _, space = load(PATH)
    ra = run(PATH, 5, (play_one, ace, allow, allow, allow))
    rb = run(PATH, 5, (play_one, three, allow, allow, allow))
    assert isinstance(ra, DecisionNode) and isinstance(rb, DecisionNode)
    assert ra.player == rb.player == 1  # the next turn's play offer
    assert ra.legal == rb.legal
    assert action_strings(space, ra.legal) == action_strings(space, rb.legal)
    for q in (1, 2, 3):
        info_a = information_state(q, ra.rs, ra.obs_logs[q])
        info_b = information_state(q, rb.rs, rb.obs_logs[q])
        assert info_a == info_b, (
            f"P{q} learned something from an unchallenged face-down play:\n"
            f"witness: {first_divergence(info_a, info_b)}"
        )


# --- the constructive world generator -------------------------------------


def _challenge_rich_line(seed: int) -> tuple[int, ...]:
    """A deterministic line that exercises the hidden-function channel: P2
    calls "Cheat!" at every window it is offered, everyone else plays the
    lowest legal action. Extended past 60 steps to the next window pause, so
    the paused decision is the same [allow, call_cheat] shape for every
    generated world. Guarded non-vacuous where used: the line must contain
    flips and pile pickups, or the constructive certificate would quietly
    cover a challenge-free line."""
    _, space = load(PATH)
    call = space.encode(("call_cheat", None))
    history: list[int] = []
    r = run(PATH, seed, ())
    step = 0
    while step < 60 or (isinstance(r, DecisionNode) and call not in r.legal):
        assert isinstance(r, DecisionNode), "the challenge-rich line ended prematurely"
        a = call if (call in r.legal and r.player == 2) else r.legal[0]
        history.append(a)
        r = run(PATH, seed, tuple(history))
        step += 1
    return tuple(history)


@pytest.mark.parametrize("seed", manifest(CONSTRUCTIVE_SEEDS))
def test_constructive_worlds_are_indistinguishable(seed: int) -> None:
    """The generator's certificate, per observer: derive the pinned set from
    the line (decode + log + projection pins), permute EVERY remaining hidden
    card across the other players' deal-time hands, replay the same 60+ step
    challenge-rich line, and require a byte-identical information state, the
    same paused player, and — when the observer is the one to move — the same
    legal actions and the same rendered action text. Two rotations per
    observer: two maximally-distant worlds, not one lucky pair. The line is
    asserted channel-active first (flips and pile pickups occurred), so the
    certificate covers a line where the public Boolean of hidden content
    actually fired — the case the sampled swap harness structurally avoids (a
    swap only replays if it dodges the channel).

    Run over `CONSTRUCTIVE_SEEDS`, the module's coverage manifest: each seed
    deals a different hand and drives a different challenge-rich line, so five
    of them exercise five distinct flip/pickup patterns rather than one."""
    hist = _challenge_rich_line(seed)
    probe = run(PATH, seed, hist)
    assert isinstance(probe, DecisionNode)
    flips = [e for e in probe.obs_logs[0] if e[0] == "move" and e[3] == "flipped"]
    pickups = [
        e
        for e in probe.obs_logs[0]
        if e[0] == "move" and e[1] == "pile" and str(e[3]).startswith("hand[")
    ]
    assert len(flips) >= 2, "the line never exercised the flip channel"
    assert pickups, "the line never exercised a pile pickup"

    _, space = load(PATH)
    total_free = 0
    for observer in range(4):
        pause_a, plan = plan_worlds(PATH, seed, hist, observer, "hand")
        info_a = information_state(observer, pause_a.rs, pause_a.obs_logs[observer])
        free = plan.free_cards
        assert len(free) >= 12, (
            f"observer {observer}: only {len(free)} permutable cards — the "
            f"certificate has quietly shrunk; re-derive the line"
        )
        total_free += len(free)
        for rotation in (1, 2):
            pause_b = permuted_replay(PATH, seed, hist, plan, "hand", rotation=rotation)
            info_b = information_state(observer, pause_b.rs, pause_b.obs_logs[observer])
            assert pause_b.player == pause_a.player, (
                f"observer {observer} rotation {rotation}: the permutation "
                f"moved the turn — control flow read hidden content"
            )
            assert info_a == info_b, (
                f"observer {observer} rotation {rotation}: a constructed "
                f"hidden permutation is distinguishable — a pin class is "
                f"missing from the entitlement analysis\n"
                f"witness: {first_divergence(info_a, info_b)}"
            )
            if pause_a.player == observer:
                assert pause_b.legal == pause_a.legal, (
                    f"observer {observer}: same information set, different "
                    f"legal actions under the constructed world"
                )
                # ...and the same offer must READ the same. Backstop; the wall
                # is `test_action_strings.py` (see `harness.action_strings`).
                assert action_strings(space, pause_b.legal) == action_strings(
                    space, pause_a.legal
                ), (
                    f"observer {observer}: same legal actions, different "
                    f"rendered text under the constructed world — the strings "
                    f"a prompt shows are a leak channel"
                )
    record(
        "cardlang_cheat",
        "constructive",
        seed=seed,
        steps=len(hist),
        observers=4,
        rotations=2,
        flips_on_line=len(flips),
        pile_pickups_on_line=len(pickups),
        free_cards_total=total_free,
        legal_agreement=True,
        string_agreement=True,
    )


def _initial_hands(seed: int) -> dict[int, list[Card]]:
    captured: dict[int, list[Card]] = {}

    def capture(rs: RuntimeState) -> None:
        for p in range(4):
            captured[p] = list(rs.zones.instance("hand", p).cards)

    r0 = run(PATH, seed, (), on_first_decision=capture)
    assert isinstance(r0, DecisionNode)
    return captured


def test_decode_pin_violation_trips_the_replay_wall() -> None:
    """The discriminating probe for the decode-pin class: move a card the
    line PLAYED AND FLIPPED (the hidden-function channel's own cards) out of
    its deal-time hand, and the replay must refuse loudly — the recorded
    chosen-card action no longer matches a live candidate. This is what makes
    'legal replay' a real wall for the generator, not an assumption."""
    seed = 5
    hist = _challenge_rich_line(seed)
    pause_a, plan = plan_worlds(PATH, seed, hist, 0, "hand")
    initial = _initial_hands(seed)
    _, _space = load(PATH)
    by_render = {str(c): c for c in build_deck("standard52")}

    flipped = [
        by_render[s]
        for e in pause_a.obs_logs[0]
        if e[0] == "move" and e[3] == "flipped"
        for s in e[4]
    ]
    target = next(c for c in flipped if any(c in initial[p] for p in (1, 2, 3)))
    holder = next(p for p in (1, 2, 3) if target in initial[p])
    other = next(p for p in (1, 2, 3) if p != holder and plan.free[f"hand[{p}]"])
    partner = plan.free[f"hand[{other}]"][0]

    def violate(rs: RuntimeState) -> None:
        h1 = rs.zones.instance("hand", holder)
        h2 = rs.zones.instance("hand", other)
        h1.remove(target)
        h2.remove(partner)
        h1.add(partner)
        h2.add(target)

    with pytest.raises(ValueError, match="not among the live candidates"):
        run(PATH, seed, hist, on_first_decision=violate)


def test_log_pin_violation_replays_legally_but_is_distinguishable() -> None:
    """The discriminating probe for the log-pin class — and the proof that
    the generator's equality assert is not vacuous. Swap a card the observer
    was DEALT and never played (log-pinned: its identity is in their deal
    event; named by no recorded action) with a genuinely-free opponent card:
    the replay is perfectly legal, and the observer's information state MUST
    differ. A legally-replaying world is NOT automatically indistinguishable
    — exactly the gap swap-and-replay sampling cannot express, and the reason
    the entitlement analysis, not replay legality, defines the partition."""
    seed = 5
    hist = _challenge_rich_line(seed)
    observer = 0
    pause_a, plan = plan_worlds(PATH, seed, hist, observer, "hand")
    initial = _initial_hands(seed)

    own_unplayed = next(c for c in initial[observer] if c in plan.projection_pins)
    opp = next(p for p in (1, 2, 3) if plan.free[f"hand[{p}]"])
    opp_free = plan.free[f"hand[{opp}]"][0]

    def swap(rs: RuntimeState) -> None:
        h1 = rs.zones.instance("hand", observer)
        h2 = rs.zones.instance("hand", opp)
        h1.remove(own_unplayed)
        h2.remove(opp_free)
        h1.add(opp_free)
        h2.add(own_unplayed)

    pause_b = run(PATH, seed, hist, on_first_decision=swap)
    assert isinstance(pause_b, DecisionNode)
    assert pause_b.player == pause_a.player
    info_a = information_state(observer, pause_a.rs, pause_a.obs_logs[observer])
    info_b = information_state(observer, pause_b.rs, pause_b.obs_logs[observer])
    assert info_a != info_b, (
        "a world that moves the observer's own dealt card replayed legally "
        "AND rendered identically — the log-pin class is not load-bearing, "
        "so the constructive certificate would be vacuous"
    )
