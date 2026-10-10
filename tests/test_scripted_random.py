"""The generator a drawing game plays under: an empty script is the seed's
own generator, a script gives each draw its outcome, and a draw outside the
two methods the drawing constructs reach is refused.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        `ScriptedRandom` deals every draw kind exactly as
                 `random.Random(seed)` does under an empty script, gives each
                 scripted draw its outcome and draws past the script from the
                 seed's first bit, refuses a malformed outcome, and refuses any
                 draw that is not one of its draw kinds.
domain:          every draw kind in `DRAW_KINDS`, held equal to the drawing
                 arms of the two chance tables through `_METHOD`, crossed with
                 the behaviours above; the unnamed draws are every public
                 drawing method of `random.Random` that is not a draw kind.
registry:        drawing arms: `cardlang.runtime.chance.EPISTEMIC_OP_DRAWS`,
                 `cardlang.runtime.chance.SELECTION_MODE_DRAWS`; draw kinds:
                 `cardlang.runtime.chance.DRAW_KINDS`; the chance tables'
                 reconciliation with the grammar:
                 tests/test_chance_free.py::test_construct_axis_is_pinned_by_grammar.
does not prove:  that the engine reaches the generator only through these
                 methods for every game — the refusal fires where a run draws,
                 so it speaks for the lines that run; the corpus's own lines run
                 under it in every replay.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import pytest

from cardlang.openspiel import replay
from cardlang.openspiel.registry import _GAMES_DIR
from cardlang.runtime.chance import (
    DRAW_KINDS,
    EPISTEMIC_OP_DRAWS,
    SELECTION_MODE_DRAWS,
    Draw,
    ScriptedRandom,
)
from cardlang.runtime.errors import ShadowGuardError

# Each drawing arm of the chance tables, mapped to the generator method its
# construct reaches (`execute._epistemic` shuffles; a random selection samples).
_METHOD: dict[str | None, str] = {"shuffle": "shuffle", "random": "sample"}

_ITEMS = list(range(10))


def _draw(rng: random.Random, kind: str) -> list[int]:
    """One draw of `kind` over `_ITEMS`, as the engine makes it."""
    if kind == "shuffle":
        items = list(_ITEMS)
        rng.shuffle(items)
        return items
    assert kind == "sample", kind
    return rng.sample(list(_ITEMS), 4)


def test_the_draw_kinds_are_the_drawing_arms() -> None:
    arms = {op for op, draws in EPISTEMIC_OP_DRAWS.items() if draws} | {
        mode for mode, draws in SELECTION_MODE_DRAWS.items() if draws
    }
    assert set(_METHOD) == arms
    assert set(_METHOD.values()) == set(DRAW_KINDS)


@pytest.mark.parametrize("kind", DRAW_KINDS)
def test_an_empty_script_draws_as_the_seed(kind: str) -> None:
    plain, scripted = random.Random(7), ScriptedRandom(7)
    for _ in range(3):
        assert _draw(scripted, kind) == _draw(plain, kind)


@pytest.mark.parametrize("kind", DRAW_KINDS)
def test_a_script_gives_each_draw_its_outcome(kind: str) -> None:
    outcome = tuple(reversed(range(10))) if kind == "shuffle" else (9, 0, 5, 2)
    heard: list[Draw] = []
    rng = ScriptedRandom(7, (outcome,), on_draw=heard.append)
    assert _draw(rng, kind) == [_ITEMS[j] for j in outcome]
    # Past the script, the seed's stream from its first bit.
    assert _draw(rng, kind) == _draw(random.Random(7), kind)
    assert [(d.index, d.kind) for d in heard] == [(0, kind), (1, kind)]
    assert heard[0].before == tuple(_ITEMS)


@pytest.mark.parametrize("kind", DRAW_KINDS)
def test_a_construct_answers_the_draws_past_the_script(kind: str) -> None:
    outcome = tuple(range(10)) if kind == "shuffle" else (0, 1, 2, 3)
    asked: list[tuple[int, str]] = []

    def construct(index: int, k: str, items: list[Any]) -> tuple[int, ...]:
        asked.append((index, k))
        return outcome

    rng = ScriptedRandom(7, construct=construct)
    assert _draw(rng, kind) == [_ITEMS[j] for j in outcome]
    assert asked == [(0, kind)]


@pytest.mark.parametrize("kind", DRAW_KINDS)
def test_a_malformed_outcome_is_refused(kind: str) -> None:
    bad = (0, 0, 1, 2, 3, 4, 5, 6, 7, 8) if kind == "shuffle" else (0, 0, 1, 2)
    with pytest.raises(ValueError, match="scripted outcome"):
        _draw(ScriptedRandom(7, (bad,)), kind)


_UNNAMED: dict[str, Callable[[random.Random], object]] = {
    "betavariate": lambda r: r.betavariate(1, 1),
    "choice": lambda r: r.choice(_ITEMS),
    "choices": lambda r: r.choices(_ITEMS),
    "expovariate": lambda r: r.expovariate(1),
    "gammavariate": lambda r: r.gammavariate(1, 1),
    "gauss": lambda r: r.gauss(0, 1),
    "getrandbits": lambda r: r.getrandbits(8),
    "lognormvariate": lambda r: r.lognormvariate(0, 1),
    "normalvariate": lambda r: r.normalvariate(0, 1),
    "paretovariate": lambda r: r.paretovariate(1),
    "randbytes": lambda r: r.randbytes(2),
    "randint": lambda r: r.randint(0, 9),
    "random": lambda r: r.random(),
    "randrange": lambda r: r.randrange(10),
    "triangular": lambda r: r.triangular(),
    "uniform": lambda r: r.uniform(0, 1),
    "vonmisesvariate": lambda r: r.vonmisesvariate(0, 1),
    "weibullvariate": lambda r: r.weibullvariate(1, 1),
}


def test_the_unnamed_draws_are_every_other_drawing_method() -> None:
    """`_UNNAMED` is the public drawing surface of `random.Random` beyond the
    draw kinds, read off the class rather than listed from memory."""
    drawing = {
        name
        for name in dir(random.Random)
        if not name.startswith("_") and callable(getattr(random.Random, name))
    } - {"seed", "getstate", "setstate"} - set(DRAW_KINDS)
    assert drawing == set(_UNNAMED)


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize("name", sorted(_UNNAMED))
def test_a_draw_outside_the_draw_kinds_is_refused(name: str) -> None:
    """red under: return `super().getrandbits(k)` and `super().random()`
    without the `_inside` check — every row draws and none raises."""
    with pytest.raises(ShadowGuardError, match="outside `shuffle` and `sample`"):
        _UNNAMED[name](ScriptedRandom(7))


def test_a_script_for_a_game_that_draws_nothing_is_refused() -> None:
    path = str(_GAMES_DIR / "tic-tac-toe.cardlang")
    assert replay.chance_free(path)
    with pytest.raises(ValueError, match="draws nothing"):
        replay.generator_for(path, 0, ((0,),))


@pytest.mark.parametrize("kind", DRAW_KINDS)
def test_a_copy_mid_run_draws_on_as_the_original(kind: str) -> None:
    """A world is deep-copied mid-run by the proofs' probes, its generator
    with it. red under: drop `ScriptedRandom.__reduce__` — `random.Random`'s
    own rebuilds the class with no seed and the copy raises."""
    import copy
    import pickle

    outcome = tuple(range(10)) if kind == "shuffle" else (0, 1, 2, 3)
    rng = ScriptedRandom(7, (outcome, outcome))
    _draw(rng, kind)
    for twin in (copy.copy(rng), copy.deepcopy(rng), pickle.loads(pickle.dumps(rng))):
        assert twin.draws == rng.draws == 1
        assert _draw(twin, kind) == _draw(copy.deepcopy(rng), kind)
        assert _draw(twin, kind) == _draw(random.Random(7), kind)
