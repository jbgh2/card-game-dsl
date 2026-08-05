"""Green Lane information-set proofs — the experiment-local counterpart of
tests/openspiel_ready/ (whose generic 2-player swap pairs a hand against the
un-dealt deck; Green Lane's deck is empty after setup, and its hidden
information is choice-generated, so the meaningful properties are proved
directly):

1. SHIPMENT INDISTINGUISHABILITY: two histories that differ only in which
   card the merchant secretly shipped give the OTHER player byte-identical
   information states and identical legal actions — while the merchant's own
   information states differ. Checked at every concealed ship decision along
   sampled playouts, for every pair of alternatives.
2. WAREHOUSE OPACITY: the ambiguity persists after resolution — wave both
   variant shipments through, play an identical continuation, and the other
   player's information state stays byte-identical for the rest of the game
   (stopping only where a later inspection could legitimately reveal the
   forked card: the merchant's forced last shipment).
3. PERFECT RECALL: every player's observation log is append-only along any
   playout.
4. SEED NON-OBSERVABILITY: the game makes no rng draws, so any two seeds
   yield byte-identical information states everywhere along any history.

Run:  python experiments/green-lane/proofs.py
"""

from __future__ import annotations

import itertools
import random
from typing import Any

import glcommon

from cardlang.openspiel import replay
from cardlang.openspiel.infostate import information_state

RESPONSE_LABELS = {"inspect", "wave"}


def random_history(path: str, seed: int, rng: random.Random) -> list[int]:
    history: list[int] = []
    while True:
        r = replay.run(path, seed, tuple(history))
        if isinstance(r, replay.TerminalNode):
            return history
        history.append(rng.choice(r.legal))


def infostate(path: str, history: tuple[int, ...], player: int) -> str:
    r = replay.run(path, 0, history)
    assert isinstance(r, replay.DecisionNode)
    return information_state(player, r.rs, r.obs_logs[player])


def labels_of(space: Any, legal: list[int]) -> list[str]:
    return [space.to_string(a) for a in legal]


def is_ship_node(space: Any, r: replay.DecisionNode) -> bool:
    return not any(lab in RESPONSE_LABELS for lab in labels_of(space, r.legal))


def wave_action(space: Any, r: replay.DecisionNode) -> int | None:
    for a in r.legal:
        if space.to_string(a) == "wave":
            return a
    return None


def check_shipment_indistinguishability(path: str) -> tuple[int, int]:
    """Fork every concealed ship decision: the next decider (a different
    player) must see identical information states and legal actions across
    the alternatives; the shipper's own states must all differ."""
    _, space = replay.load(path)
    rng = random.Random(11)
    checked = ship_nodes = 0
    for _ in range(40):
        history = random_history(path, 0, rng)
        for cut in range(len(history)):
            prefix = tuple(history[:cut])
            r = replay.run(path, 0, prefix)
            if not isinstance(r, replay.DecisionNode) or len(r.legal) < 2:
                continue
            if not is_ship_node(space, r):
                continue
            nxt = replay.run(path, 0, prefix + (r.legal[0],))
            if not isinstance(nxt, replay.DecisionNode) or nxt.player == r.player:
                continue
            ship_nodes += 1
            merchant, other = r.player, nxt.player
            for a, b in itertools.combinations(r.legal, 2):
                ia = infostate(path, prefix + (a,), other)
                ib = infostate(path, prefix + (b,), other)
                assert ia == ib, (
                    f"P{other} distinguishes concealed shipments "
                    f"{space.to_string(a)} vs {space.to_string(b)} after {prefix}:"
                    f"\n{ia}\nvs\n{ib}"
                )
                la = replay.run(path, 0, prefix + (a,))
                lb = replay.run(path, 0, prefix + (b,))
                assert isinstance(la, replay.DecisionNode) and isinstance(lb, replay.DecisionNode)
                assert la.legal == lb.legal, "legal-action agreement broken"
                ma = infostate(path, prefix + (a,), merchant)
                mb = infostate(path, prefix + (b,), merchant)
                assert ma != mb, (
                    "merchant cannot tell their own shipments apart: "
                    f"{space.to_string(a)} vs {space.to_string(b)}"
                )
                checked += 1
    return ship_nodes, checked


def check_warehouse_opacity(path: str) -> int:
    """Fork a ship decision, wave both variants through, then replay one
    random common continuation on both branches: the other player's
    information state must stay identical at every later pause. The walk
    stops where the merchant's FORCED last shipment (not an action, so not
    excluded by the common-action filter) could be inspected — the one place
    a divergent card can legitimately become public."""
    _, space = replay.load(path)
    rng = random.Random(23)
    persistent_checks = 0
    for _ in range(30):
        history = random_history(path, 0, rng)
        for cut in range(len(history)):
            prefix = tuple(history[:cut])
            r = replay.run(path, 0, prefix)
            if not isinstance(r, replay.DecisionNode) or len(r.legal) < 2:
                continue
            if not is_ship_node(space, r):
                continue
            merchant = r.player
            a, b = rng.sample(r.legal, 2)
            branches = [prefix + (a,), prefix + (b,)]
            # If the fork is answered by an inspect/wave decision, wave BOTH
            # branches so the variant shipment stays concealed.
            ra = replay.run(path, 0, branches[0])
            if isinstance(ra, replay.DecisionNode) and not is_ship_node(space, ra):
                w = wave_action(space, ra)
                assert w is not None
                branches = [h + (w,) for h in branches]

            while True:
                pa = replay.run(path, 0, branches[0])
                pb = replay.run(path, 0, branches[1])
                if isinstance(pa, replay.TerminalNode) or isinstance(pb, replay.TerminalNode):
                    break
                assert isinstance(pa, replay.DecisionNode) and isinstance(pb, replay.DecisionNode)
                if pa.player != merchant:
                    ia = infostate(path, branches[0], pa.player)
                    ib = infostate(path, branches[1], pb.player)
                    assert ia == ib, (
                        f"warehouse leaked: P{pa.player} distinguishes waved "
                        f"{space.to_string(a)} vs {space.to_string(b)}, "
                        f"{len(branches[0]) - len(prefix)} plies after the fork"
                    )
                    persistent_checks += 1
                # Stop before a response to the merchant's forced last ship:
                # with an empty merchant hand the standing shipment may be the
                # forked card itself, and inspecting it reveals the divergence.
                if not is_ship_node(space, pa):
                    hand = pa.rs.zones.instance("hand", merchant).cards
                    if len(hand) == 0:
                        break
                common = [x for x in pa.legal if x in pb.legal]
                if not common:
                    break
                step = rng.choice(common)  # ONE draw — both branches take the same action
                branches = [h + (step,) for h in branches]
            break  # one fork per playout; move on
    return persistent_checks


def check_perfect_recall(path: str) -> int:
    rng = random.Random(5)
    checked = 0
    for _ in range(10):
        history = random_history(path, 0, rng)
        prev: dict[int, list[tuple[Any, ...]]] = {}
        for cut in range(len(history) + 1):
            r = replay.run(path, 0, tuple(history[:cut]))
            if not isinstance(r, replay.DecisionNode):
                continue
            for p, log in r.obs_logs.items():
                if p in prev:
                    assert log[: len(prev[p])] == prev[p], (
                        f"observation log for P{p} rewrote history at ply {cut}"
                    )
                prev[p] = list(log)
                checked += 1
    return checked


def check_seed_non_observability(path: str) -> int:
    rng = random.Random(31)
    checked = 0
    for _ in range(5):
        history = random_history(path, 0, rng)
        for cut in range(len(history)):
            ra = replay.run(path, 0, tuple(history[:cut]))
            rb = replay.run(path, 99, tuple(history[:cut]))
            if not isinstance(ra, replay.DecisionNode):
                continue
            assert isinstance(rb, replay.DecisionNode)
            for p in range(2):
                assert information_state(p, ra.rs, ra.obs_logs[p]) == information_state(
                    p, rb.rs, rb.obs_logs[p]
                ), f"seed leaked into P{p}'s information state"
            checked += 1
    return checked


def main() -> None:
    import sys

    glcommon.install_replay_memo()
    files = sys.argv[1:] or [str(glcommon.HERE / f) for f in glcommon.GAMES.values()]
    for path in files:
        filename = path.rsplit("/", 1)[-1]
        print(f"== {filename} ==")
        nodes, pairs = check_shipment_indistinguishability(path)
        print(
            f"  shipment indistinguishability: {pairs} concealed-choice pairs "
            f"across {nodes} ship decisions — all agree"
        )
        persistent = check_warehouse_opacity(path)
        print(f"  warehouse opacity: {persistent} later-ply checks — no leak")
        recall = check_perfect_recall(path)
        print(f"  perfect recall: {recall} log-prefix checks — append-only")
        seeds = check_seed_non_observability(path)
        print(f"  seed non-observability: {seeds} paused states across seeds 0/99 — identical")
    print("all proofs passed")


if __name__ == "__main__":
    main()
