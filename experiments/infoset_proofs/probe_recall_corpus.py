"""Perfect recall held against Constructed Worlds, over every registered game.

Perfect recall (Kuhn): every history in one information set of seat p carries
the same sequence of p's own earlier information states. The oracle: walk a
seeded uniform line; at sampled picks, construct a world p cannot tell from
the true one (`cardlang.openspiel.resample`, accepted by byte-identical
information state at the pause); replay both worlds' prefixes and compare p's
information state at each of p's earlier decisions. Any pair that differs is
a recall failure at the pause.

The witness `witnesses/state_recall.cardlang` runs first, to show the oracle
can redden.

Run: python experiments/infoset_proofs/probe_recall_corpus.py [game ...]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import DecisionNode, run
from cardlang.openspiel.resample import ResampleRefusal, resample
from cardlang.runtime.chance import Outcome

ROOT = Path(__file__).resolve().parents[2]
GAMES_DIR = ROOT / "docs" / "games"
WITNESS = Path(__file__).resolve().parent / "witnesses" / "state_recall.cardlang"
SAMPLE_AT = (1, 2, 3, 5, 8, 12, 20, 30)
LINES = 6


def earlier_states(
    path: str, seed: int, script: tuple[Outcome, ...], history: tuple[int, ...], seat: int
) -> list[str]:
    """`seat`'s information state at each pick before the pause it decided."""
    states: list[str] = []
    for j in range(len(history)):
        node = run(path, seed, history[:j], script=script)
        assert isinstance(node, DecisionNode)
        if node.player == seat:
            states.append(information_state(seat, node.rs, node.obs_logs[seat]))
    return states


def probe(path: str, line: int) -> tuple[int, list[str]]:
    rnd = random.Random(f"{path}:{line}")
    seed = rnd.randrange(4096)
    history: list[int] = []
    checked = 0
    failures: list[str] = []
    for pick in range(max(SAMPLE_AT) + 1):
        node = run(path, seed, tuple(history))
        if not isinstance(node, DecisionNode):
            break
        if pick in SAMPLE_AT:
            seat = node.player
            try:
                world = resample(path, seed, (), tuple(history), seat, rnd, 4096)
            except ResampleRefusal:
                history.append(rnd.choice(node.legal))
                continue
            mine = earlier_states(path, seed, (), tuple(history), seat)
            theirs = earlier_states(path, world.seed, world.script, world.history, seat)
            checked += 1
            if mine != theirs:
                at = next(
                    (i for i, (a, b) in enumerate(zip(mine, theirs)) if a != b),
                    min(len(mine), len(theirs)),
                )
                a = mine[at] if at < len(mine) else "<absent>"
                b = theirs[at] if at < len(theirs) else "<absent>"
                failures.append(
                    f"pick {pick}, seat {seat}: earlier decision #{at} differs\n"
                    f"      true : {a[:400]}\n      world: {b[:400]}"
                )
        history.append(rnd.choice(node.legal))
    return checked, failures


def main(names: list[str]) -> None:
    targets = [("witness_state_recall", str(WITNESS))]
    targets += [
        (short, str(GAMES_DIR / filename))
        for short, filename in sorted(GAMES.items())
        if not names or short in names or short.removeprefix("cardlang_") in names
    ]
    for short, path in targets:
        checked = 0
        failures: list[str] = []
        try:
            for line in range(LINES):
                c, f = probe(path, line)
                checked += c
                failures += f
        except ResampleRefusal as refusal:
            print(f"{short}: refused ({refusal.kind})", flush=True)
            continue
        verdict = "RECALL FAILS" if failures else "ok"
        print(f"{short}: {verdict} ({checked} constructed worlds compared)", flush=True)
        for failure in failures[:2]:
            print("    " + failure, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
