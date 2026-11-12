"""The resolve pass's step layout: the import direction between its modules.

`cardlang/resolve/` is one module per Resolve Step, called in a named
sequence by `resolve()` in the package root, plus the shared modules the
steps read. A check lives in the step that calls it, and a step reads
another step's code only by that code moving down into a shared module, in
a diff that shows it.

The grid crosses the kind of the importing module with the kind of the
imported one, each kind derived from the package: a cell the layout admits
must hold at least one import (so the derivation is seeing edges), and a
cell it refuses must hold none.

Completeness ledger
-------------------
property:        every module of the package is the root, a step, or a
                 shared module; the root imports steps and shared modules,
                 a step imports shared modules, a shared module imports
                 shared modules, and no other kind pair holds an import;
                 the package's internal import graph has no cycle; the root
                 defines no function but `resolve`.
domain:          the direct import statements between modules under
                 `cardlang.resolve`, function-local imports included, as
                 `grimp` builds them, crossed by kind: root, step, shared,
                 importer by imported. Python's implied parent edge
                 (importing a module under the package runs the root) is not a
                 statement and is outside the domain.
registry:        modules: `tests/resolver_package.py::resolver_modules`;
                 steps: `_step_modules`, the modules defining a function
                 `resolve()` calls; shared: every other module but the root.
held by:         Derived and Pinned. Python has no module-visibility
                 construct a type checker enforces, so the direction is a
                 property of the import graph and this pin is its rung.
does not prove:  a `getattr` or string reach across modules (not an import
                 statement); a transitive path that leaves the package and
                 comes back (a step imports `cardlang.attribution`, which
                 imports the root inside a function -- issue #991's edge to
                 rule, not this pin's); the ORDER of the sequence, which the
                 rejection snapshots under tests/rejections/ hold as report
                 order; that a check belongs to the step whose Contract
                 names it.
red under:       a step module importing a helper from a sibling step, e.g.
                 `from cardlang.resolve.references import _check_move_params`
                 in `cardlang/resolve/result.py` (executed 2026-11-11: the
                 `step-imports-step` cell fails naming
                 `cardlang.resolve.result -> cardlang.resolve.references`);
                 a shared module importing a step, e.g. that line in
                 `cardlang/resolve/walk.py` (executed 2026-11-11: the
                 `shared-imports-step` cell fails); a module of the package
                 importing its root, e.g. `from cardlang.resolve import
                 resolve` inside a function of `cardlang/resolve/walk.py`
                 (executed 2026-11-11: the `shared-imports-root` cell fails).
"""

from __future__ import annotations

import ast
import inspect
from functools import cache
from itertools import product
from typing import Literal

import grimp
import pytest

import cardlang.resolve as resolve_root
from tests.resolver_package import resolver_modules

_ROOT = resolve_root.__name__
Kind = Literal["root", "step", "shared"]
KINDS: tuple[Kind, ...] = ("root", "step", "shared")
# The kind pairs the layout admits; every other pair is refused.
ADMITTED: frozenset[tuple[Kind, Kind]] = frozenset(
    {("root", "step"), ("root", "shared"), ("step", "shared"), ("shared", "shared")}
)


@cache
def _graph() -> grimp.ImportGraph:
    return grimp.build_graph("cardlang")


def _package_modules() -> frozenset[str]:
    return frozenset(m.__name__ for m in resolver_modules())


def _step_modules() -> frozenset[str]:
    """The modules defining a function `resolve()` calls: as `step.entry(...)`
    on an imported step module, or as a bare name the root imported from one."""
    fn = ast.parse(inspect.getsource(resolve_root.resolve)).body[0]
    called: set[str] = set()
    for nd in ast.walk(fn):
        if not isinstance(nd, ast.Call):
            continue
        if isinstance(nd.func, ast.Attribute) and isinstance(nd.func.value, ast.Name):
            target = getattr(resolve_root, nd.func.value.id, None)
            if inspect.ismodule(target):
                called.add(target.__name__)
        elif isinstance(nd.func, ast.Name):
            target = getattr(resolve_root, nd.func.id, None)
            module = getattr(target, "__module__", None)
            if inspect.isfunction(target) and module and module.startswith(f"{_ROOT}."):
                called.add(module)
    return frozenset(called)


def _kind(module: str) -> Kind:
    if module == _ROOT:
        return "root"
    return "step" if module in _step_modules() else "shared"


def _internal_edges() -> list[tuple[str, str]]:
    graph = _graph()
    package = _package_modules()
    return sorted(
        (importer, imported)
        for importer in package
        for imported in graph.find_modules_directly_imported_by(importer)
        if imported in package and imported != importer
    )


def test_the_layout_is_derived_from_the_sequence() -> None:
    """Every kind has a member, and every module is in the graph, so the grid
    below is about real modules."""
    package = _package_modules()
    assert all(m in _graph().modules for m in package), "the graph is reading the wrong package"
    assert {_kind(m) for m in package} == set(KINDS), sorted((m, _kind(m)) for m in package)


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        pytest.param(a, b, id=f"{a}-imports-{b}")
        for a, b in product(KINDS, KINDS)
        if (a, b) != ("root", "root")
    ],
)
def test_imports_by_kind(importer: Kind, imported: Kind) -> None:
    edges = [f"{a} -> {b}" for a, b in _internal_edges() if (_kind(a), _kind(b)) == (importer, imported)]
    if (importer, imported) in ADMITTED:
        assert edges, f"no {importer} module imports a {imported} module: the grid sees no edges"
    else:
        assert not edges, (
            f"a {importer} module imports a {imported} module; a step reads another "
            f"step's code only once it moves down into a shared module: {edges}"
        )


def test_the_package_imports_form_no_cycle() -> None:
    edges: dict[str, set[str]] = {}
    for a, b in _internal_edges():
        edges.setdefault(a, set()).add(b)
    state: dict[str, int] = {}
    cycle: list[str] = []

    def visit(module: str, path: list[str]) -> None:
        state[module] = 1
        for nxt in sorted(edges.get(module, ())):
            if state.get(nxt) == 1 and not cycle:
                cycle.extend(path[path.index(nxt):] + [nxt])
            elif nxt not in state:
                visit(nxt, [*path, nxt])
        state[module] = 2

    for module in sorted(edges):
        if module not in state:
            visit(module, [module])
    assert not cycle, f"an import cycle inside the package: {' -> '.join(cycle)}"


def test_the_root_defines_only_the_sequence() -> None:
    """The root holds `resolve()` and nothing a step could own.

    red under: define any function in `cardlang/resolve/__init__.py`
    (executed 2026-11-11: `_plant` beside `resolve`)."""
    tree = ast.parse(inspect.getsource(resolve_root))
    defined = sorted(
        s.name for s in tree.body if isinstance(s, (ast.FunctionDef, ast.ClassDef))
    )
    assert defined == ["resolve"], defined
