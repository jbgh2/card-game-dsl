"""Export differential trace fixtures from the ADAPTER (the rules authority)
and verify fast_sim replays every one of them exactly: same legal sets at
every step, same trick winners and tide cards, same terminal returns. Also
writes the fixtures to play/fixtures.json for the artifact's JS engine to
replay through the same bar.

Run:  python export_fixtures.py [n_traces]
"""

from __future__ import annotations

import json
import random
import sys

import fast_sim
import utcommon
from analyze_undertow import tricks_from_log

from cardlang.openspiel import replay


def export_trace(path: str, seed: int, rng: random.Random) -> dict:
    history: list[int] = []
    steps = []
    space = replay.load(path)[1]
    while True:
        r = replay.run(path, seed, tuple(history))
        if isinstance(r, replay.Terminal):
            returns = r.returns
            break
        legal_labels = [space.to_string(a) for a in r.legal]
        a = rng.choice(r.legal)
        steps.append(
            {"actor": r.player, "legal": legal_labels, "chosen": space.to_string(a)}
        )
        history.append(a)
    pause = replay.run(path, seed, tuple(history[:-1]))
    tricks = tricks_from_log(pause.obs_logs[0])
    return {
        "seed": seed,
        "steps": steps,
        "tricks": [
            {"winner": t["winner"], "tide": t["tide_card"], "plays": [
                [p, c] for p, c in t["plays"]]}
            for t in tricks if "winner" in t
        ],
        "returns": returns,
    }


def hands_from_steps(steps: list[dict]) -> list[list[int]]:
    hands: list[list[int]] = [[], [], [], []]
    for s in steps:
        hands[s["actor"]].append(fast_sim.parse_label(s["chosen"]))
    return hands


def replay_in_sim(trace: dict) -> None:
    hands = hands_from_steps(trace["steps"])
    sim = fast_sim.Sim(hands, leader=trace["steps"][0]["actor"])
    trick_idx = 0
    for i, s in enumerate(trace["steps"]):
        assert sim.to_play == s["actor"], f"step {i}: actor {sim.to_play} != {s['actor']}"
        want = sorted(s["legal"])
        got = sorted(fast_sim.label(c) for c in sim.legal())
        assert got == want, f"step {i}: legal {got} != {want}"
        before = len(sim.played) // 4
        sim.apply(fast_sim.parse_label(s["chosen"]))
        after = len(sim.played) // 4
        if after > before and trick_idx < len(trace["tricks"]):
            t = trace["tricks"][trick_idx]
            assert sim.leader == t["winner"], f"trick {trick_idx}: winner {sim.leader} != {t['winner']}"
            assert fast_sim.SUITS[sim.trump] == t["tide"][-1], (
                f"trick {trick_idx}: tide suit {fast_sim.SUITS[sim.trump]} != {t['tide']}"
            )
            trick_idx += 1
    assert sim.terminal()
    assert [float(x) for x in sim.tricks_won] == list(trace["returns"]), (
        f"returns {sim.tricks_won} != {trace['returns']}"
    )


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    path = utcommon.register(num_seeds=2048)
    rng = random.Random(99)
    traces = []
    for i in range(n):
        trace = export_trace(path, rng.randrange(2048), rng)
        replay_in_sim(trace)
        traces.append(trace)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{n} traces exported + replayed in fast_sim")
    out = utcommon.HERE / "play" / "fixtures.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"schema": 1, "game": "undertow", "traces": traces}))
    total_steps = sum(len(t["steps"]) for t in traces)
    print(f"fast_sim agrees with the adapter on {n} traces / {total_steps} steps")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
