"""The native-call dispatch has two homes, and the two homes partition it.

property:   every name the checker registers as a native call dispatches from
            exactly one runtime home -- `runtime/builtins.py` (Builtins:
            generic native functions the language ships) or
            `runtime/primitives.py` (Primitives: sanctioned game-local
            Python) -- with nothing in both and nothing in neither, and every
            name-keyed dispatcher lives in the home its kind belongs to
domain:     CALL_FUNCS (the whole registry) x {builtins, primitives};
            every name-keyed dispatcher in either home x its home; the
            retired `runtime/stdlib.py` x {exists, imported}
registry:   `cardlang/builtins/functions.py` for BOTH name axes --
            `BUILTIN_CALL_FUNCS` / `PRIMITIVE_CALL_FUNCS` give the expected
            home and `CALL_FUNCS` their derived union; each home module's OWN
            `call` match AST for the actual home (scraped from the source,
            never hand-listed); each home module's module-level `match name:`
            functions for the dispatcher axis
covered:    the grid -- `test_call_arm_home[<name>]`, one row per registry
            member, crossed against the scraped home;
            `test_homes_partition_the_call_registry` (scraped union ==
            CALL_FUNCS, scraped intersection == empty, and each scraped home
            == its declared set both ways);
            `test_dispatcher_home[<dispatcher>]`, one row per scraped
            dispatcher, plus `test_every_scraped_dispatcher_is_accounted_for`
            so a NEW dispatcher cannot land unplaced (the dispatcher column
            is the dispatcher's FILE; the classification of the slot
            callbacks a dispatcher keys is the registries' statement, and
            `value_function` keys both homes' winners from primitives.py by
            design — see DISPATCHER_HOMES);
            `test_retired_module_is_gone`;
            `test_nothing_imports_the_retired_module`
sampled:    that each arm still computes the right answer is not this grid's
            property -- the full suite and byte-identical goldens carry it.
            This grid pins WHERE a name dispatches, not WHAT it returns.
residual:   the `climb_universe_function` / `climb_codec_function` /
            `joint_codec_function` key sets are not registries -- they exist
            only inside their own match -- so each carries a home row but no
            membership row. Their joint coverage of PRIMITIVE_CLIMB_LEADS is
            tests/test_signatures.py's property, not this grid's. R4, and
            this ledger owns the record: the two codec dispatchers return
            None on a miss by design, and the absence is guarded loudly where
            it matters (`ActionSpace.for_game`).

            Not a residual, recorded because it was one until issue #202:
            the expected-home column is now DERIVED from the declaration
            side, so this grid crosses two independent statements of where a
            name lives instead of checking the implementation against a copy
            of itself. A name declared in neither half is not in CALL_FUNCS
            and resolve refuses it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import cardlang
from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    CALL_FUNCS,
    PRIMITIVE_CALL_FUNCS,
)

_PACKAGE = Path(cardlang.__file__).parent
_BUILTINS = _PACKAGE / "runtime" / "builtins.py"
_PRIMITIVES = _PACKAGE / "runtime" / "primitives.py"
_RETIRED = _PACKAGE / "runtime" / "stdlib.py"

# The name-keyed dispatchers and the home each belongs to. `call` is the only
# one with a Builtins half; every other dispatcher keys slot callbacks (a
# winner function, a climb query, an auction outcome, a codec) and lives in
# primitives.py as ONE match statement per slot. This column is the
# DISPATCHER's file, not the CLASSIFICATION of the names it keys:
# `value_function` dispatches both the Builtin winners
# (`BUILTIN_TRICK_WINNERS`, reached through the neutral `runtime/winners.py`)
# and the Primitive ones (game-local modules) — one match, one file. Splitting
# it by home would mint a second dispatcher for two names and put nothing in
# the right place that is not already there; the classification of what it
# keys is `cardlang/builtins/functions.py`'s statement, pinned by
# tests/test_native_classification_prose.py, and the elimination metric is
# `PRIMITIVE_CALL_FUNCS` (the call arms below) plus the epic scoreboard,
# neither of which the winner reclassification touched.
DISPATCHER_HOMES: dict[str, str] = {
    "call": "both",
    "value_function": "primitives",
    "climb_row": "primitives",
    "climb_lead_function": "primitives",
    "climb_follow_function": "primitives",
    "climb_universe_function": "primitives",
    "joint_codec_function": "primitives",
    "climb_codec_function": "primitives",
    "auction_outcome_function": "primitives",
}


def _module_ast(path: Path) -> ast.Module | None:
    """The module's AST, or None when the file does not exist yet. A missing
    home is reported by the row's own assertion (an absent name), never by an
    ImportError escaping the grid -- a harness crash is not design-red."""
    if not path.exists():
        return None
    return ast.parse(path.read_text())


def _name_dispatchers(path: Path) -> dict[str, frozenset[str]]:
    """Every module-level function in `path` that dispatches on a `name`
    parameter, mapped to its literal case keys. Derived from the source, so a
    dispatcher moved between homes shows up here without anyone updating a
    list."""
    tree = _module_ast(path)
    if tree is None:
        return {}
    found: dict[str, frozenset[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        match_stmt = next(
            (
                s
                for s in node.body
                if isinstance(s, ast.Match)
                and isinstance(s.subject, ast.Name)
                and s.subject.id == "name"
            ),
            None,
        )
        if match_stmt is None:
            continue
        keys: set[str] = set()
        for case in match_stmt.cases:
            for pattern in (
                case.pattern.patterns
                if isinstance(case.pattern, ast.MatchOr)
                else [case.pattern]
            ):
                if isinstance(pattern, ast.MatchValue) and isinstance(
                    pattern.value, ast.Constant
                ):
                    keys.add(str(pattern.value.value))
        found[node.name] = frozenset(keys)
    return found


def _call_arms(path: Path) -> frozenset[str]:
    return _name_dispatchers(path).get("call", frozenset())


def _expected_home(name: str) -> str:
    """From the DECLARATION side, so this grid crosses two independent
    statements of the same fact rather than checking the implementation
    against a copy of itself."""
    return "builtins" if name in BUILTIN_CALL_FUNCS else "primitives"


def _actual_homes(name: str) -> list[str]:
    homes = []
    if name in _call_arms(_BUILTINS):
        homes.append("builtins")
    if name in _call_arms(_PRIMITIVES):
        homes.append("primitives")
    return homes


@pytest.mark.parametrize("name", sorted(CALL_FUNCS))
def test_call_arm_home(name: str) -> None:
    """Each registered call dispatches from exactly the home its kind says."""
    assert _actual_homes(name) == [_expected_home(name)], (
        f"{name!r} should dispatch from {_expected_home(name)}.py, but its "
        f"`call` arm was found in {_actual_homes(name) or 'neither home'}"
    )


def test_homes_partition_the_call_registry() -> None:
    """The two homes cover the registry exactly. Stated over the SCRAPED arm
    sets rather than by subtraction, so an arm in neither home (or in both)
    fails here by name rather than being absorbed into a complement."""
    builtins_arms, primitives_arms = _call_arms(_BUILTINS), _call_arms(_PRIMITIVES)
    assert builtins_arms | primitives_arms == CALL_FUNCS, (
        f"unhomed: {sorted(CALL_FUNCS - builtins_arms - primitives_arms)}; "
        f"unregistered: {sorted((builtins_arms | primitives_arms) - CALL_FUNCS)}"
    )
    assert builtins_arms.isdisjoint(primitives_arms), (
        f"dispatched from both homes: {sorted(builtins_arms & primitives_arms)}"
    )
    assert builtins_arms == BUILTIN_CALL_FUNCS
    assert primitives_arms == PRIMITIVE_CALL_FUNCS


@pytest.mark.parametrize("dispatcher", sorted(DISPATCHER_HOMES))
def test_dispatcher_home(dispatcher: str) -> None:
    """Every name-keyed dispatcher lives in the home its kind belongs to. Only
    `call` has a Builtins half; a game-local callback dispatcher appearing in
    `builtins.py` would put game knowledge in the generic layer."""
    in_builtins = dispatcher in _name_dispatchers(_BUILTINS)
    in_primitives = dispatcher in _name_dispatchers(_PRIMITIVES)
    expected = DISPATCHER_HOMES[dispatcher]
    assert (in_builtins, in_primitives) == (expected in ("builtins", "both"), True), (
        f"{dispatcher} should live in {expected}, found "
        f"builtins={in_builtins} primitives={in_primitives}"
    )


def test_every_scraped_dispatcher_is_accounted_for() -> None:
    """The dispatcher axis is derived, so a NEW dispatcher added to either home
    fails here until this grid records which home it belongs to."""
    scraped = set(_name_dispatchers(_BUILTINS)) | set(_name_dispatchers(_PRIMITIVES))
    assert scraped == set(DISPATCHER_HOMES), (
        f"unrecorded dispatchers: {sorted(scraped - set(DISPATCHER_HOMES))}; "
        f"recorded but absent: {sorted(set(DISPATCHER_HOMES) - scraped)}"
    )


def test_retired_module_is_gone() -> None:
    """`runtime/stdlib.py` was the game-primitive dispatch layer wearing the
    stdlib's name; the stdlib is the layer written in the language, and its
    package is `cardlang/stdlib/`."""
    assert not _RETIRED.exists(), (
        f"{_RETIRED} still exists -- the runtime's native dispatch lives in "
        f"builtins.py and primitives.py"
    )


def test_nothing_imports_the_retired_module() -> None:
    """Scraped over the whole package, so a leftover importer anywhere fails
    here rather than at whatever playout first reaches it."""
    retired = "cardlang.runtime.stdlib"
    offenders = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                hit = node.module == retired or (
                    node.module == "cardlang.runtime"
                    and any(a.name == "stdlib" for a in node.names)
                )
            elif isinstance(node, ast.Import):
                hit = any(a.name == retired for a in node.names)
            else:
                continue
            if hit:
                offenders.append(f"{path.relative_to(_PACKAGE)}:{node.lineno}")
    assert offenders == [], f"still importing the retired module: {offenders}"
