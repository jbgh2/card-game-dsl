"""The resolve pass as a package, for tests that read or stub it.

The resolve pass is a package: a definition lives in one module and is read
under the same name by every module that imports it, the package root
included. Replacing the name on one module leaves the others reading the
original, so a test that stubs a resolver name stubs it wherever it is
bound (`patch_resolver`); a test that scrapes the resolver's source reads
every module of the package (`resolver_sources`). Both derive the modules
from the package at call time, never from a list.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

import cardlang.resolve as resolve_root


def resolver_modules() -> list[ModuleType]:
    """The package root and every module under it."""
    return [resolve_root] + [
        importlib.import_module(f"{resolve_root.__name__}.{info.name}")
        for info in pkgutil.iter_modules(resolve_root.__path__)
    ]


def resolver_sources() -> list[Path]:
    """The source file of every module of the resolve package."""
    return [Path(str(m.__file__)) for m in resolver_modules()]


def resolver_text() -> str:
    """The source text of the whole resolve package, module after module."""
    return "".join(path.read_text() for path in resolver_sources())


def resolver_tree() -> ast.Module:
    """One module node whose body is every top-level statement of every
    module of the resolve package, for a scrape that walks the whole pass."""
    body: list[ast.stmt] = []
    for path in resolver_sources():
        body.extend(ast.parse(path.read_text(), str(path)).body)
    return ast.Module(body=body, type_ignores=[])


def pass_tree(name: str) -> ast.Module:
    """The parsed source of the pass `name`: the module `cardlang/<name>.py`,
    or every module of the resolve package for `resolve`."""
    if name == "resolve":
        return resolver_tree()
    path = Path(resolve_root.__path__[0]).parent / f"{name}.py"
    return ast.parse(path.read_text(), str(path))


def patch_resolver(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> None:
    """Bind `name` to `value` in every resolver module that binds it.

    Refuses a name no module binds (a stub that would replace nothing) and a
    name two modules bind to different objects (a stub whose reach would be
    ambiguous)."""
    holders = [m for m in resolver_modules() if name in vars(m)]
    if not holders:
        raise AttributeError(f"no module of {resolve_root.__name__} binds {name!r}")
    if len({id(vars(m)[name]) for m in holders}) != 1:
        raise AssertionError(f"modules of {resolve_root.__name__} bind {name!r} to different objects")
    for module in holders:
        monkeypatch.setattr(module, name, value)
