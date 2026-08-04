"""Every exception class the engine defines declares where it sits, and does not move.

`cardlang/runtime/errors.py` encodes a guard's ROLE as its TYPE (glossary
section 5): `OwnerGuardError` and `ShadowGuardError` under a shared
`GameDescriptionError`, so a harness can catch "this game is illegal" while the
suite holds the stronger line that a Shadow Guard firing is an ENGINE gap. That
design is carried entirely by four `issubclass` relations, and every one of them
is a single-word edit away from silently ceasing to hold:

* re-parent `GameDescriptionError` to `RuntimeError` and all nine
  `PrimitiveReadError` sites — whose Author is the primitive-module maintainer,
  not the game author — become catchable as game-description failures;
* let `IllegalMove` into the tree and a game working AS WRITTEN (the author
  wrote `error(...)`; the refusal IS the rule) reads as a defect;
* let a control-flow signal in and `produce` unwinding becomes a game fault;
* drop the `GameDescriptionError` base from `ShadowGuardError` and every
  harness that catches the base stops stopping for engine gaps.

None of those edits fails a behavioural test — the wrong class is still an
exception, still propagates, still matches a broad `except`. So the containment
relations are pinned here directly, and the class axis is DERIVED (every
exception class defined anywhere in `cardlang/`, found by import) rather than
listed: a new exception class cannot join the engine without this module
demanding to know where it sits.

Contract
--------
Assumes: `cardlang` imports cleanly. Establishes: the failure taxonomy's shape
is what `errors.py` documents. Illegal after this: adding an exception class to
`cardlang/` without recording its position, or moving an existing one.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every exception class the engine defines sits where the taxonomy
           says, and the two disjointness guarantees `errors.py` names
           (`PrimitiveReadError` outside; `IllegalMove` outside) hold
           structurally rather than by accident.
domain:    every class defined in the `cardlang` package that is a
           `BaseException` subclass, crossed with the containment predicates
           that carry a design decision — membership in the
           `GameDescriptionError` tree, and `RuntimeError`-ness (the relation
           that keeps `PrimitiveReadError` disjoint for free).
registry:  the class axis derives by importing every module of the package and
           reading back the `BaseException` subclasses whose `__module__` is
           `cardlang.*` (`_engine_exception_classes`) — a new class is in
           domain the day it is defined, and `test_every_engine_exception_is_placed`
           fails until it is placed. The predicate axis is `_PREDICATES`.
covered:   the full cross product, as `test_containment` — every derived class
           against every predicate, expected values in `_EXPECTED`.
sampled:   none. The cross product is total over both axes.
residual:  stdlib exception classes raised directly by the engine
           (`ValueError`, `KeyError`, ...) are not classes the engine DEFINES,
           so they have no position to pin here; that they are raised at all
           where a role type belongs is the census's property, not this
           module's (`tests/test_guard_role_sites.py`). `BaseException`
           subclasses that are not `Exception` subclasses would be a new
           design question (nothing in the engine defines one); the derivation
           catches one arriving, since it quantifies over `BaseException`.

red under: two, one per disjointness guarantee, both verified by making the
edit and watching the named cells — and only those — go red.
  * give `IllegalMove` (cardlang/runtime/state.py) the base
    `GameDescriptionError`: fails the `IllegalMove` /
    `in_game_description_tree` cell alone.
  * re-parent `GameDescriptionError` to `RuntimeError`: fails the
    `is_runtime_error` cell for all three tree classes. This is the edit the
    module exists for — it is one word, it breaks no behavioural test, and it
    would quietly make every `PrimitiveReadError` catchable as a
    game-description failure.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Mapping
from functools import cache

import pytest

import cardlang
from cardlang.runtime.errors import (
    GameDescriptionError,
    OwnerGuardError,
    ShadowGuardError,
)

# The predicates that carry a design decision. Each is a relation `errors.py`
# argues for in prose; the point of the module is that the prose and the class
# statement cannot drift apart.
_PREDICATES: dict[str, Callable[[type[BaseException]], bool]] = {
    # Catchable as "this game description is illegal".
    "in_game_description_tree": lambda c: issubclass(c, GameDescriptionError),
    # The relation that keeps `PrimitiveReadError` disjoint from the tree
    # without anyone maintaining a list: it roots at `RuntimeError`, and
    # `GameDescriptionError` deliberately does not.
    "is_runtime_error": lambda c: issubclass(c, RuntimeError),
}

# class qualname -> {predicate name: expected}. Authored from the decisions
# recorded in `cardlang/runtime/errors.py`; a row here is a claim about WHO
# must act on that failure, not a restatement of the class statement.
_EXPECTED: dict[str, dict[str, bool]] = {
    # --- the role-bearing tree (Author: the game author) -------------------
    "GameDescriptionError": {"in_game_description_tree": True, "is_runtime_error": False},
    "OwnerGuardError": {"in_game_description_tree": True, "is_runtime_error": False},
    "ShadowGuardError": {"in_game_description_tree": True, "is_runtime_error": False},
    # --- Author: the primitive-module maintainer ---------------------------
    # Disjoint from the tree BY ROOT, not by a list anyone maintains.
    "PrimitiveReadError": {"in_game_description_tree": False, "is_runtime_error": True},
    # --- Author: whoever installed or checked the package out --------------
    # A sibling, never a child: a harness catching `GameDescriptionError` to
    # report an illegal game must not swallow a missing corpus directory and
    # carry on with an empty game list.
    "InstallationError": {"in_game_description_tree": False, "is_runtime_error": False},
    # --- not a defect at all: the game is working as written ---------------
    # The author wrote `error(...)`; refusing the move IS the rule.
    "IllegalMove": {"in_game_description_tree": False, "is_runtime_error": False},
    # --- control flow, not failure -----------------------------------------
    "_ProduceSignal": {"in_game_description_tree": False, "is_runtime_error": False},
    "_ContinueTo": {"in_game_description_tree": False, "is_runtime_error": False},
    "_SkipHand": {"in_game_description_tree": False, "is_runtime_error": False},
    "ChooserAbort": {"in_game_description_tree": False, "is_runtime_error": False},
    # --- the compile passes' own channel -----------------------------------
    # Diagnostics are bag-collected and carry spans; a compile failure is never
    # a play-time refusal, and catching one as a game-description failure would
    # cross two currencies.
    "DiagnosticError": {"in_game_description_tree": False, "is_runtime_error": False},
}


@cache
def _engine_exception_classes() -> Mapping[str, type[BaseException]]:
    """Every exception class DEFINED in the `cardlang` package, by qualname.

    Derived, not listed: import every module the package walk yields, then read
    back the classes whose `__module__` is inside the package. Filtering on
    `__module__` is what makes it "defined here" rather than "imported here" —
    `errors.py`'s names are visible from a dozen modules and would otherwise
    multiply-count.

    The walk's own module list is the domain, deliberately NOT `sys.modules`:
    the global table holds whatever a prior test happened to import, so reading
    it would make this axis depend on what else ran and on the order it ran in.
    A solo run and a full-suite run must derive the same set.
    """
    found: dict[str, type[BaseException]] = {}
    walked = ["cardlang", *(i.name for i in pkgutil.walk_packages(cardlang.__path__, prefix="cardlang."))]
    for mod_name in walked:
        for obj in vars(importlib.import_module(mod_name)).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseException)
                and getattr(obj, "__module__", "").startswith("cardlang")
            ):
                found[obj.__name__] = obj
    return found


def test_every_engine_exception_is_placed() -> None:
    """A new exception class must declare its position before it can ship.

    This is the totality half: `test_containment` only checks the classes
    `_EXPECTED` names, so without this a class added to the engine would sit
    unpinned and the suite would stay green.
    """
    derived = set(_engine_exception_classes())
    recorded = set(_EXPECTED)
    unplaced = sorted(derived - recorded)
    stale = sorted(recorded - derived)
    assert not unplaced, (
        f"{len(unplaced)} exception class(es) defined in cardlang/ with no "
        f"recorded position in the failure taxonomy: {unplaced}. Decide WHO "
        f"must act on it (game author / primitive maintainer / engine "
        f"maintainer / installer), then add a row to _EXPECTED. If it belongs "
        f"in the role-bearing tree, it subclasses OwnerGuardError or "
        f"ShadowGuardError, not GameDescriptionError directly."
    )
    assert not stale, (
        f"_EXPECTED names {stale}, which no longer exist in cardlang/ — a "
        f"deleted or renamed exception class leaves its row behind."
    )


@pytest.mark.parametrize("predicate", sorted(_PREDICATES))
@pytest.mark.parametrize("cls_name", sorted(_EXPECTED))
def test_containment(cls_name: str, predicate: str) -> None:
    """The cross product: every engine exception against every relation that
    carries a decision."""
    cls = _engine_exception_classes()[cls_name]
    assert _PREDICATES[predicate](cls) is _EXPECTED[cls_name][predicate], (
        f"{cls_name} is on the wrong side of {predicate!r}. This relation is a "
        f"design decision recorded in cardlang/runtime/errors.py, not an "
        f"implementation detail — if the move is intended, the argument in that "
        f"module's docstring changes in the same commit as this row."
    )


@pytest.mark.expects_shadow_guard
def test_shadow_guard_leads_with_the_leaked_guard() -> None:
    """`ShadowGuardError`'s rendered message names the Owner Guard first.

    The type says "engine gap"; the message has to say WHICH guard leaked, or
    the maintainer who must act cannot act. Pinned because the ordering is the
    whole reason the constructor takes two arguments instead of one.
    """
    exc = ShadowGuardError("resolve._check_board_call", "grid(0) is not a board")
    assert str(exc).startswith("resolve._check_board_call should have refused")
    assert exc.leaked == "resolve._check_board_call"


def test_owner_guard_is_not_catchable_as_a_shadow_guard() -> None:
    """The two roles are siblings, not a chain.

    A harness catching `ShadowGuardError` to escalate an engine gap must not
    also swallow ordinary bad-game refusals, and `except OwnerGuardError` must
    not catch the engine's own leak. Sibling-ness is what makes both true, and
    it is exactly what a well-meaning "ShadowGuardError is a special
    OwnerGuardError" refactor would destroy.
    """
    assert not issubclass(ShadowGuardError, OwnerGuardError)
    assert not issubclass(OwnerGuardError, ShadowGuardError)
