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
the game draws, and at which sites; and, for a game that draws, a generator
whose draws are exactly the `DRAW_KINDS` its drawing constructs reach, each
scriptable, and which under an empty Draw Script deals as `random.Random(seed)`.
Illegal after this: reading a game's chance-freeness by scanning its source
for `shuffle`; drawing from a drawing game's generator through any method
but its draw kinds; or handling an `EpistemicOp` or `Transfer` selection
mode this module's tables do not name —
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
from collections.abc import Callable, Iterator
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


# Raised in full at each site rather than built by a helper: the guard-role
# census (tests/test_guard_role_sites.py) reads the raise statement, and an
# exception returned from a helper hides its class from the scraper.
_LEAKED_GUARD = "cardlang.runtime.chance.chance_sites"
_DREW = (
    "a game classified Chance-Free drew from its generator — the enumeration in "
    "cardlang/runtime/chance.py is missing the construct that drew, and this "
    "game's OpenSpiel tree would have dropped a real chance node"
)


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

    def random(self) -> float:
        raise ShadowGuardError(_LEAKED_GUARD, _DREW)

    def getrandbits(self, k: int) -> int:
        raise ShadowGuardError(_LEAKED_GUARD, _DREW)


# What one draw's outcome is, as positions in the draw's input: for a shuffle,
# the permutation (output position k holds input position `outcome[k]`); for a
# random selection, the positions picked, in the order they are taken.
Outcome = tuple[int, ...]

# The generator method each drawing construct reaches, keyed as `Draw.kind`.
# The drawing arms of `EPISTEMIC_OP_DRAWS` and `SELECTION_MODE_DRAWS`, spelled
# as `ScriptedRandom` overrides them; tests/test_scripted_random.py derives the
# drawing arms from those two tables and holds this tuple to them.
DRAW_KINDS: tuple[str, ...] = ("shuffle", "sample")

_UNSCRIPTED = (
    "a game drew from its generator outside `shuffle` and `sample`, the two "
    "methods its drawing constructs reach — the enumeration in "
    "cardlang/runtime/chance.py is missing the construct that drew, and a "
    "Constructed World could not script it"
)


def _restore(
    cls: type[ScriptedRandom],
    stream: Any,
    script: tuple[Outcome, ...],
    draws: int,
    on_draw: Callable[[Draw], None] | None,
    construct: Callable[[int, str, list[Any]], Outcome | None] | None,
) -> ScriptedRandom:
    rng = cls(0, script, on_draw, construct)
    rng.setstate(stream)
    rng.draws = draws
    return rng


@dataclasses.dataclass(frozen=True)
class Draw:
    """One draw as it happened: its index among the run's draws, its kind, the
    items it drew over, and what it produced."""

    index: int
    kind: str
    before: tuple[Any, ...]
    after: tuple[Any, ...]


class ScriptedRandom(random.Random):
    """The generator installed as `rs.rng` for a game that draws.

    A run's draws are numbered in the order they happen. Draw `i` takes its
    outcome from `outcome_for(i, kind, items)`, which answers from `script`
    while it lasts; past it, and wherever `outcome_for` answers None, the draw
    is `random.Random(seed)`'s own, consuming that stream exactly as the plain
    generator would. An empty Draw Script is therefore the plain generator: same
    seed, same outcomes.

    The Draw Script is what lets a world exist that no seed deals — the one
    `cardlang.openspiel.resample` constructs, holding what an observer has seen
    in place while redealing the rest. A scripted draw consumes no randomness,
    so the draws after the Draw Script are the seed's from its first bit.

    Drawing anywhere but `shuffle` and `sample` is refused, which makes
    `chance_sites`'s enumeration falsifiable here as `RefusingRandom` makes the
    Chance-Free classification falsifiable: a drawing construct the tables miss
    stops the run where it draws, instead of drawing outcomes no script can
    name.
    """

    def __init__(
        self,
        seed: int,
        script: tuple[Outcome, ...] = (),
        on_draw: Callable[[Draw], None] | None = None,
        construct: Callable[[int, str, list[Any]], Outcome | None] | None = None,
    ) -> None:
        self._inside = True
        super().__init__(seed)
        self._inside = False
        self.script = script
        self.on_draw = on_draw
        self.construct = construct
        self.draws = 0

    def __reduce__(self) -> tuple[Any, ...]:
        """Copy and pickle as the generator it is, mid-run: its stream, its
        script, its hooks and how many draws it has made. `random.Random`'s
        own reduction rebuilds the class with no arguments and keeps only the
        stream, which would drop the script and restart the draw count."""
        return (
            _restore,
            (type(self), self.getstate(), self.script, self.draws, self.on_draw, self.construct),
        )

    def outcome_for(self, index: int, kind: str, items: list[Any]) -> Outcome | None:
        """The outcome draw `index` takes, or None to draw from the seed:
        the script's while it lasts, then `construct`'s answer where one is
        given."""
        if index < len(self.script):
            return self.script[index]
        return None if self.construct is None else self.construct(index, kind, items)

    def shuffle(self, x: Any) -> None:
        index, before = self._begin(), list(x)
        outcome = self.outcome_for(index, "shuffle", before)
        if outcome is None:
            self._inside = True
            try:
                super().shuffle(x)
            finally:
                self._inside = False
        else:
            if sorted(outcome) != list(range(len(before))):
                raise ValueError(
                    f"draw {index} shuffles {len(before)} items, and its scripted "
                    f"outcome {outcome} is not a permutation of their positions"
                )
            x[:] = [before[j] for j in outcome]
        self._end(index, "shuffle", before, list(x))

    def sample(self, population: Any, k: int, *, counts: Any = None) -> list[Any]:
        if counts is not None:
            raise ShadowGuardError(_LEAKED_GUARD, _UNSCRIPTED)
        index, before = self._begin(), list(population)
        outcome = self.outcome_for(index, "sample", before)
        if outcome is None:
            self._inside = True
            try:
                chosen = super().sample(before, k)
            finally:
                self._inside = False
        else:
            if len(outcome) != k or len(set(outcome)) != k or not all(
                0 <= j < len(before) for j in outcome
            ):
                raise ValueError(
                    f"draw {index} selects {k} of {len(before)} items, and its "
                    f"scripted outcome {outcome} is not {k} distinct positions"
                )
            chosen = [before[j] for j in outcome]
        self._end(index, "sample", before, chosen)
        return chosen

    def _begin(self) -> int:
        index = self.draws
        self.draws += 1
        return index

    def _end(self, index: int, kind: str, before: list[Any], after: list[Any]) -> None:
        if self.on_draw is not None:
            self.on_draw(Draw(index, kind, tuple(before), tuple(after)))

    def random(self) -> float:
        if not self._inside:
            raise ShadowGuardError(_LEAKED_GUARD, _UNSCRIPTED)
        return super().random()

    def getrandbits(self, k: int) -> int:
        if not self._inside:
            raise ShadowGuardError(_LEAKED_GUARD, _UNSCRIPTED)
        return super().getrandbits(k)
