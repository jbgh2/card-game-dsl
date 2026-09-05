"""A native call reaches its Python by exactly one route, and which one is
its kind's.

property:   every name the checker registers as a native call reaches its
            Python by exactly one route -- a Builtin through the `call` match
            `runtime/builtins.py` holds, a Primitive through the table its
            game's own `primitives { }` block derives at load, which is why a
            Primitive has an arm in NEITHER runtime home; and every name-keyed
            dispatcher lives in the home its kind belongs to
domain:     CALL_FUNCS (the whole registry) x {builtins, declared}; every
            name-keyed dispatcher in either home x its home; the retired
            `runtime/stdlib.py` x {exists, imported}; the retired legacy
            dispatch seam x {the dispatcher, its callers, the set that
            classified it}
registry:   `cardlang/builtins/functions.py` for the name axis --
            `BUILTIN_CALL_FUNCS` / `PRIMITIVE_CALL_FUNCS` give the expected
            route and `CALL_FUNCS` their derived union; each home module's OWN
            `call` match AST for the actual home (scraped from the source,
            never hand-listed); each home module's module-level `match name:`
            functions for the dispatcher axis
covered:    the grid -- `test_call_arm_home[<name>]`, one row per registry
            member, crossed against the scraped home, including every
            Primitive row whose expected home is no arm at all;
            `test_homes_partition_the_call_registry` (scraped union ==
            CALL_FUNCS minus the Primitives, scraped intersection == empty,
            the Builtins' scraped arms == their declared set both ways, and
            the Primitives home's arm set empty);
            `test_dispatcher_home[<dispatcher>]`, one row per scraped
            dispatcher, plus `test_every_scraped_dispatcher_is_accounted_for`
            so a NEW dispatcher cannot land unplaced (the dispatcher column
            is the dispatcher's FILE; the classification of the slot
            callbacks a dispatcher keys is the registries' statement, and
            `value_function` keys both homes' winners from primitives.py by
            design — see DISPATCHER_HOMES);
            `test_the_legacy_dispatch_seam_is_gone` (the dispatcher, its
            callers and `DECLARED_ONLY_CALL_FUNCS`, each falsifiable alone);
            `test_retired_module_is_gone`;
            `test_nothing_imports_the_retired_module`
sampled:    that each arm still computes the right answer is not this grid's
            property -- the full suite and byte-identical goldens carry it.
            This grid pins WHERE a name dispatches, not WHAT it returns.
does not prove: that a Primitive's DECLARED route works. This grid says only
            that no arm dispatches one; that the table a block derives finds
            real Python and hands it the right shape is
            tests/test_primitives_block.py's and tests/test_signatures.py's,
            and a green here would survive the declared route being broken
            outright.
red under (the end state, authored before it held):
            the five cells that state the retirement were authored against the
            tree that still carried the seam, and four of the five were red
            there. Measured 2026-09-04, `.venv/bin/python -m pytest
            tests/test_native_dispatch_split.py::test_the_legacy_dispatch_seam_is_gone
            tests/test_permissive_top.py::test_call_signature_registry_covers_every_native_call_function
            tests/test_signatures.py::test_tables_reconcile_with_name_sets
            tests/test_primitives_block.py::test_the_index_is_where_a_primitive_signature_is_stated
            tests/test_primitives_block.py::test_every_authored_row_is_one_a_walled_binder_binds -q`
            -> `4 failed, 1 passed`. The fifth
            (`test_every_authored_row_is_one_a_walled_binder_binds`) was
            already true when it was written and carries its own reddening
            mutation instead.
            A red run stops at a cell's FIRST assertion, so that run credits
            only the first of each multi-assertion cell: the remaining
            assertions of `test_the_legacy_dispatch_seam_is_gone` and of
            `test_the_index_is_where_a_primitive_signature_is_stated` carry
            their own per-assertion mutations, listed at each.
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

# The name-keyed dispatchers and the home each belongs to. `call` is the
# Builtins' own; every other dispatcher keys slot callbacks (a winner
# function, a climb query, an auction outcome, a codec) and lives in
# primitives.py as ONE match statement per slot. This column is the
# DISPATCHER's file, not the CLASSIFICATION of the names it keys:
# `value_function` dispatches both the Builtin winners
# (`BUILTIN_TRICK_WINNERS`, reached through the neutral `runtime/winners.py`)
# and any game-local winner (`PRIMITIVE_TRICK_WINNERS`, whose members reach
# their own modules) — one match, one file. Splitting it by home would mint a
# second dispatcher per home and put nothing in the right place that is not
# already there; the classification of what it
# keys is `cardlang/builtins/functions.py`'s statement, pinned by
# tests/test_native_classification_prose.py, and the elimination metric is
# `PRIMITIVE_CALL_FUNCS` plus the epic scoreboard, neither of which the winner
# reclassification touched.
DISPATCHER_HOMES: dict[str, str] = {
    "call": "builtins",
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


def _legacy_dispatch_callers() -> list[str]:
    """Every site in the package that calls `primitives.call` through the
    module attribute — the form `runtime/evaluate.py` used. Derived from the
    AST rather than a text match, so a caller under a reformatted call still
    shows up. A caller reached through `from ... import call` is NOT matched,
    and does not need to be: the assertion above this one says no such
    function is defined to import."""
    offenders = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "call"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "primitives"
            ):
                offenders.append(f"{path.relative_to(_PACKAGE)}:{node.lineno}")
    return offenders


def test_the_legacy_dispatch_seam_is_gone() -> None:
    """A Primitive is reached by declaration and by nothing else.

    Three statements of the one end state, each falsifiable on its own — and
    each observed red on its own, because an assertion that never spoke is a
    check no one has seen fail. The dispatcher is not defined; nothing calls
    it; and the set that classified which Primitives it held no arm for is not
    there to classify anything. The third is asked of the module rather than by
    importing the name, so its reappearance is a red assertion here and not an
    ImportError somewhere else.

    red under, one mutation per assertion, each demonstrated and reverted
    2026-09-05: (1) restore a `def call(name, args, ctx)` with a
    `case "gin_deadwood"` arm to `runtime/primitives.py` — this cell's first
    assertion speaks, beside `test_call_arm_home[gin_deadwood]` and
    `test_homes_partition_the_call_registry`; (2) `return primitives.call(name, args, ctx)` in
    `native_call`'s Builtin-miss branch — "still dispatching through the
    retired seam: ['runtime/evaluate.py:50']"; (3)
    `DECLARED_ONLY_CALL_FUNCS = PRIMITIVE_CALL_FUNCS` in `builtins/functions.py`
    — "DECLARED_ONLY_CALL_FUNCS is back"."""
    import cardlang.builtins.functions as functions_mod

    assert "call" not in _name_dispatchers(_PRIMITIVES), (
        "cardlang/runtime/primitives.py defines a `call` dispatcher — a "
        "Primitive's only route to its Python is `call_declared` off its "
        "game's `primitives { }` block"
    )
    assert _legacy_dispatch_callers() == [], (
        f"still dispatching through the retired seam: "
        f"{_legacy_dispatch_callers()}"
    )
    assert not hasattr(functions_mod, "DECLARED_ONLY_CALL_FUNCS"), (
        "DECLARED_ONLY_CALL_FUNCS is back — every Primitive is reached by "
        "declaration, so the set that named the ones with no arm classifies "
        "nothing `PRIMITIVE_CALL_FUNCS` does not"
    )


def _expected_home(name: str) -> str:
    """From the DECLARATION side, so this grid crosses two independent
    statements of the same fact rather than checking the implementation
    against a copy of itself.

    Two values, because a name has exactly one route to its Python: a Builtin
    through the `call` match its home holds, a Primitive through the table a
    game's own `primitives { }` block derives at load
    (`runtime/primitives.py`, `Declared`). A Primitive has NO arm in either
    home, and expecting one would ask for an arm in the module whose Contract
    says there will never be one."""
    return "builtins" if name in BUILTIN_CALL_FUNCS else "declared"


def _actual_homes(name: str) -> list[str]:
    """Scraped over BOTH runtime homes, though only one holds a `call` match:
    a name dispatched from an arm the Primitives home grew back would be found
    here rather than absorbed into the Builtins' set."""
    homes = []
    if name in _call_arms(_BUILTINS):
        homes.append("builtins")
    if name in _call_arms(_PRIMITIVES):
        homes.append("primitives")
    return homes


@pytest.mark.parametrize("name", sorted(CALL_FUNCS))
def test_call_arm_home(name: str) -> None:
    """Each registered call dispatches from exactly the home its kind says —
    and a Primitive from NEITHER, because its dispatch derives from the
    declaration rather than from an arm."""
    expected = [] if _expected_home(name) == "declared" else [_expected_home(name)]
    assert _actual_homes(name) == expected, (
        f"{name!r} should dispatch from {_expected_home(name)}, but its "
        f"`call` arm was found in {_actual_homes(name) or 'neither home'}"
    )


def test_homes_partition_the_call_registry() -> None:
    """The arm-dispatched registry is exactly the Builtins. Stated over the
    SCRAPED arm sets rather than by subtraction, so an arm that appeared in
    either home fails here by name rather than being absorbed into a
    complement. The Primitives are the registry's other part: they have no arm
    anywhere, and their route is the declaration."""
    builtins_arms, primitives_arms = _call_arms(_BUILTINS), _call_arms(_PRIMITIVES)
    assert builtins_arms | primitives_arms == CALL_FUNCS - PRIMITIVE_CALL_FUNCS, (
        f"unhomed: {sorted(CALL_FUNCS - PRIMITIVE_CALL_FUNCS - builtins_arms - primitives_arms)}; "
        f"unregistered: {sorted((builtins_arms | primitives_arms) - CALL_FUNCS)}"
    )
    assert builtins_arms.isdisjoint(primitives_arms), (
        f"dispatched from both homes: {sorted(builtins_arms & primitives_arms)}"
    )
    assert builtins_arms == BUILTIN_CALL_FUNCS
    assert primitives_arms == frozenset(), (
        f"the Primitives home dispatches by arm: {sorted(primitives_arms)}"
    )


@pytest.mark.parametrize("dispatcher", sorted(DISPATCHER_HOMES))
def test_dispatcher_home(dispatcher: str) -> None:
    """Every name-keyed dispatcher lives in the home its kind belongs to.
    `call` is the Builtins' own; a game-local callback dispatcher appearing in
    `builtins.py` would put game knowledge in the generic layer."""
    in_builtins = dispatcher in _name_dispatchers(_BUILTINS)
    in_primitives = dispatcher in _name_dispatchers(_PRIMITIVES)
    expected = DISPATCHER_HOMES[dispatcher]
    assert (in_builtins, in_primitives) == (
        expected in ("builtins", "both"),
        expected in ("primitives", "both"),
    ), (
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
