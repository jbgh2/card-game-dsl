"""Pins `cardlang.ast.nodes.Node` — the closed union of all AST node kinds — to
the module's actual dataclass contents, by derivation rather than by list.

`Node` is the registry other completeness arguments cite (test_binder_registry.py
names it as its domain), and exhaustive `match` dispatches over it are what make
a new node kind loud in every consumer. But the union itself was a hand-written
list that nothing checked, and it drifted: four members (`ContinueTo`,
`FunctionDef`, `ListLit`, `SkipToNextHand`) were silently absent. A registry that
can drift silently transmits that silence to everything derived from it — an
"exhaustive" match over an incomplete union is exhaustive over the wrong domain,
and mypy cannot know.

property:   `Node` contains exactly the dataclasses defined in
            `cardlang.ast.nodes` — no more, no fewer
domain:     every dataclass whose `__module__` is `cardlang.ast.nodes`
registry:   the module itself (introspected), which is the one source that
            cannot be out of date
covered:    the full membership equation, both directions, plus the
            every-member-is-frozen invariant the module docstring claims
sampled:    none
residual:   none
"""

from __future__ import annotations

import dataclasses
import typing

import cardlang.ast.nodes as n


def _module_dataclasses() -> set[type]:
    return {
        obj
        for name in dir(n)
        if isinstance(obj := getattr(n, name), type)
        and dataclasses.is_dataclass(obj)
        and obj.__module__ == n.__name__
    }


def test_node_union_is_exactly_the_modules_dataclasses() -> None:
    union = set(typing.get_args(n.Node))
    module = _module_dataclasses()
    missing = sorted(c.__name__ for c in module - union)
    extra = sorted(c.__name__ for c in union - module)
    assert not missing, (
        f"dataclasses defined in nodes.py but absent from the Node union: {missing} — "
        "every consumer that matches Node exhaustively is blind to these"
    )
    assert not extra, (
        f"Node union members not defined in nodes.py: {extra} — the union names "
        "node kinds that do not exist"
    )


def test_every_node_kind_is_frozen() -> None:
    """The module docstring's other structural claim: nodes are immutable, which
    is what lets passes rebuild trees with `dataclasses.replace` and share
    subtrees without defensive copies."""
    unfrozen = sorted(
        cls.__name__
        for cls in _module_dataclasses()
        if not cls.__dataclass_params__.frozen  # type: ignore[attr-defined]
    )
    assert not unfrozen, f"AST dataclasses not frozen: {unfrozen}"
