"""Which decision sites share an ask, per registered game.

`legal_agreement` (coq/Kernel.v) holds for every program whose menus pass
the Hidden Read judgement, whatever its branches read, when the `asked`
event tells the program's decision sites apart. The engine's ask names the
phase, the construct, the count and the destination. Where two sites share
all four, the seat cannot tell them apart from its log, and the partition is
sound there only if no branch the seat cannot see chooses between them
(issue #755). This probe plays seeded uniform lines and lists, per game, the
ask payloads more than one site emits.

A site is the nearest designer-text node (one with a source span) on the
call stack of the ask. Run: python experiments/infoset_proofs/probe_ask_sites.py
"""

from __future__ import annotations

import inspect
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import run
from cardlang.runtime.state import Ctx

ROOT = Path(__file__).resolve().parents[2]
GAMES_DIR = ROOT / "docs" / "games"
WITNESS = ROOT / "tests" / "fixtures" / "blind_decisions" / "control_branch.cardlang"
LINES = 8

Site = tuple[str, int, int]
seen: dict[tuple[Any, ...], set[Site]] = defaultdict(set)
_original = Ctx.observe


def _site() -> Site | None:
    frame = inspect.currentframe()
    while frame is not None:
        for value in frame.f_locals.values():
            span = getattr(value, "span", None)
            if isinstance(value, n.Node) and span is not None and not isinstance(
                value, (n.Phase, n.Game)
            ):
                return (type(value).__name__, span.line, span.column)
        frame = frame.f_back
    return None


def _observe(self: Ctx, player: int, event: tuple[Any, ...]) -> None:
    if event and event[0] == "asked":
        site = _site()
        if site is not None:
            seen[event[1:]].add(site)
    _original(self, player, event)


def sweep(path: str) -> dict[tuple[Any, ...], set[Site]]:
    seen.clear()
    for line in range(LINES):
        rnd = random.Random(f"{path}:{line}")
        try:
            run(path, rnd.randrange(4096), (), beyond=lambda _d, legal: rnd.choice(legal))
        except Exception as error:  # a line the uniform policy cannot finish
            print(f"    line {line}: {type(error).__name__}: {str(error)[:120]}")
    return {ask: sites for ask, sites in seen.items() if len(sites) > 1}


def main(names: list[str]) -> None:
    setattr(Ctx, "observe", _observe)
    targets = [("witness_control_branch", str(WITNESS))] + [
        (short, str(GAMES_DIR / filename))
        for short, filename in sorted(GAMES.items())
        if not names or short.removeprefix("cardlang_") in names
    ]
    for short, path in targets:
        shared = sweep(path)
        print(f"{short}: {len(shared)} ask payload(s) emitted by more than one site", flush=True)
        for ask, sites in sorted(shared.items(), key=repr):
            where = ", ".join(f"{kind}@{line}:{col}" for kind, line, col in sorted(sites))
            print(f"    {ask!r}: {where}")


if __name__ == "__main__":
    main(sys.argv[1:])
