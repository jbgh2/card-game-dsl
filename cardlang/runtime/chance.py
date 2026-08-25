"""Which games draw from the [[world]]'s generator, and the guard for those
that do not.

A **Chance-Free Game** consumes no randomness: nothing in its text permutes a
zone or picks by chance, so its whole trajectory is a function of the actions
taken. `docs/games/` holds such games — the boards, which seed their pieces by
attribute and then only move them.

Randomness enters a running game at exactly two constructs, and this module is
the enumeration of them:

- `shuffle <zone>`, which permutes;
- a movement whose selection mode is `random`, which picks.

`reveal` names a card its predicate already fixes; `chosen` defers to the
[[chooser]] seam, whose draws belong to the POLICY and not to the game — a
uniform-random playout is not a chance node, and treating it as one would
classify every game with a decision as chance-bearing. An absent selection mode
deals off the top.

Contract
--------
Assumes: a CHECKED game — `_apply_uses` has spliced every library definition
into the tree and `expand` has spliced every procedure body at its call site,
so a walk of this tree reads all the text that can run. Establishes: whether
the game draws, and at which sites. Illegal after this: reading a game's
chance-freeness by scanning its source for `shuffle`, or handling an
`EpistemicOp` or `Transfer` selection mode this module's tables do not name —
the tables are reconciled against the grammar productions that define them by
`tests/test_chance_free.py::test_construct_axis_is_pinned_by_grammar`, so a new
arm reddens there rather than reading here as drawing nothing.

The classification is a claim about a whole game; `RefusingRandom` is what
makes the claim falsifiable at run time. A consumer that acts on
`is_chance_free` installs it, and a site the enumeration missed then stops the
run where it draws instead of returning a value nothing checks.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Iterator
from typing import Any

from cardlang.ast import nodes as n
from cardlang.diagnostics import Span
from cardlang.runtime.errors import ShadowGuardError

# The grammar's `epistemic_op` arms, mapped to whether the op draws. An
# ALLOW-LIST: `chance_sites` raises on any op absent here rather than reading it
# as non-drawing, because the silent direction is the one that collapses a real
# chance node.
EPISTEMIC_OP_DRAWS: dict[str, bool] = {"shuffle": True, "reveal": False}

# The grammar's `select_mode` arms plus the absent mode its bracket admits,
# mapped the same way and refused the same way.
SELECTION_MODE_DRAWS: dict[str | None, bool] = {
    "random": True,
    "chosen": False,
    None: False,
}


def _walk(node: Any) -> Iterator[Any]:
    """Every dataclass node reachable from `node` (AST nodes hold only
    dataclasses, tuples, and leaves)."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in dataclasses.fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


def _where(span: Span | None) -> str:
    return "?" if span is None else f"line {span.line}"


def chance_sites(game: n.Game) -> list[str]:
    """Every site in `game` that draws from the generator, each rendered with
    its source line.

    A list rather than a flag because the sites are what a reader needs when
    the answer surprises them, and because the question a mid-game chance
    construct would ask is "which sites", not "any".
    """
    sites: list[str] = []
    for node in _walk(game):
        if isinstance(node, n.EpistemicOp):
            if node.op not in EPISTEMIC_OP_DRAWS:
                raise AssertionError(
                    f"chance_sites: unhandled epistemic op {node.op!r} at "
                    f"{_where(node.span)} — this module's EPISTEMIC_OP_DRAWS and the "
                    f"grammar's `epistemic_op` production are out of sync. Add the "
                    f"arm here, saying whether it draws; reading it as non-drawing "
                    f"would collapse the chance node of a game that uses it."
                )
            if EPISTEMIC_OP_DRAWS[node.op]:
                sites.append(f"{node.op} ({_where(node.span)})")
        elif isinstance(node, n.Transfer):
            if node.selection_mode not in SELECTION_MODE_DRAWS:
                raise AssertionError(
                    f"chance_sites: unhandled selection mode "
                    f"{node.selection_mode!r} at {_where(node.span)} — this module's "
                    f"SELECTION_MODE_DRAWS and the grammar's `select_mode` production "
                    f"are out of sync. Add the arm here, saying whether it draws."
                )
            if SELECTION_MODE_DRAWS[node.selection_mode]:
                sites.append(f"{node.verb} {node.selection_mode} ({_where(node.span)})")
    return sites


def is_chance_free(game: n.Game) -> bool:
    """Whether `game` consumes no randomness."""
    return not chance_sites(game)


class RefusingRandom(random.Random):
    """The generator installed as `rs.rng` for a Chance-Free Game.

    The Shadow Guard behind `chance_sites`: if the classification is right this
    never fires, and if it is wrong the run stops at the drawing site rather
    than producing a game tree that silently omits a real chance node.

    Refusing at `random()` and `getrandbits()` covers the class rather than a
    list of it — every other `random.Random` method is built on those two, so
    `sample`, `shuffle`, `choice`, `randint` and the rest are refused without
    being named here.
    """

    def _refuse(self) -> ShadowGuardError:
        return ShadowGuardError(
            "cardlang.runtime.chance.chance_sites",
            "a game classified Chance-Free drew from its generator — the "
            "enumeration in cardlang/runtime/chance.py is missing the construct "
            "that drew, and this game's OpenSpiel tree would have dropped a real "
            "chance node",
        )

    def random(self) -> float:
        raise self._refuse()

    def getrandbits(self, k: int) -> int:
        raise self._refuse()
