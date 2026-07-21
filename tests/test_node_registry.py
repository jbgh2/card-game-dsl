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

This module also owns the IMMUTABILITY invariant the memo in `cardlang/parse.py`
rests on (its Contract block cites the walls below by name). Sharing checked
trees is not new — `openspiel/replay.py`'s `load()` has been `lru_cache`d since
2026-06-07 — but it was opt-in, one cache one caller reached deliberately.
Memoizing `parse_text`/`_check` makes it the DEFAULT for every caller, which is
why these invariants stop being properties the vocabulary happens to have and
become walls.

property:   (1) `Node` contains exactly the dataclasses defined in
            `cardlang.ast.nodes` — no more, no fewer; (2) a shared AST cannot
            be mutated
domain:     (1) every dataclass whose `__module__` is `cardlang.ast.nodes`;
            (2) the four routes to mutating one — ordinary `setattr`,
            `object.__setattr__`, `__dict__`/`vars()` writes, and reaching
            THROUGH a field into a mutable object it points at
registry:   the module itself (introspected), which is the one source that
            cannot be out of date
covered:    the full membership equation, both directions; and all four
            routes — `frozen=True` refuses ordinary `setattr` (for ANY name on
            a direct instance, not only declared fields); `slots=True` refuses
            `object.__setattr__` of a new name and `__dict__` writes; a scrape
            over `cardlang/` refuses `object.__setattr__` of a declared field,
            the one route the language cannot close since it is the call
            frozen's own `__init__` uses; and a field-type check refuses
            mutable containers, which no `setattr` wall can see. `Span` is
            pinned separately: every node carries one, so it is reachable from
            every shared tree, but it lives outside this module's `__module__`
            filter.
sampled:    none
residual:   two. The `object.__setattr__` scrape covers `cardlang/` only — a
            test or downstream consumer could still mutate a shared tree. And
            the field-type check is a denylist of mutable BUILTINS, so a
            custom mutable type held by a field would pass it.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import typing

import cardlang.ast.nodes as n
from cardlang.diagnostics import Span


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


def test_every_param_bearing_node_kind_is_reserved_swept() -> None:
    """`resolve._PARAM_BEARING` — the table `_check_reserved_params` walks — must
    cover exactly the node kinds that carry a `params` field, derived from the
    Node union rather than remembered. With the four collections spelled as a
    hand-written tuple inside the function, a new parameterized declaration
    form (procedures were one, once) would join the reserved-word sweep only if
    someone remembered it exists."""
    from cardlang.resolve import _PARAM_BEARING

    with_params = {
        cls
        for cls in typing.get_args(n.Node)
        if any(f.name == "params" for f in dataclasses.fields(cls))
    }
    assert with_params == set(_PARAM_BEARING), (
        f"node kinds with a `params` field: {sorted(c.__name__ for c in with_params)}; "
        f"kinds the reserved-word sweep covers: "
        f"{sorted(c.__name__ for c in _PARAM_BEARING)} — every parameterized "
        "declaration form must have a _PARAM_BEARING row"
    )
    # And each row's `Game` collection must actually hold that node kind, so a
    # row cannot point the sweep at the wrong list.
    for cls, (attr, _kind, _reserved) in _PARAM_BEARING.items():
        game_field = next(f for f in dataclasses.fields(n.Game) if f.name == attr)
        assert cls.__name__ in str(game_field.type), (
            f"_PARAM_BEARING maps {cls.__name__} to Game.{attr}, "
            f"which is typed {game_field.type}"
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


def test_every_node_kind_has_slots() -> None:
    """`slots=True` on top of `frozen=True`, load-bearing since `parse_text`
    and `_check` are memoized (cardlang/parse.py, Contract) and callers share
    one tree.

    What it does NOT buy: blocking plain attribute attachment. CPython's frozen
    `__setattr__` is `if type(self) is cls or name in fields: raise`, so
    `frozen=True` ALONE already raises `FrozenInstanceError` for any name on a
    direct instance, declared field or not.

    What it does buy, and nothing else does: closing the deliberate-bypass
    routes — `object.__setattr__(node, <new name>, v)` and `node.__dict__[...]`
    / `vars(node)`, all of which SUCCEED on a frozen non-slots dataclass and
    would be visible to every other holder of a shared tree. (The remaining
    route, `object.__setattr__` on a DECLARED field, is closed by
    `test_no_setattr_bypass_on_shared_asts` below, not by slots.) It is also
    what keeps the memo's retained-tree footprint affordable.

    `"__slots__" in cls.__dict__`, not `hasattr`: `hasattr` searches the MRO, so
    a node subclassing a slotted base without declaring `slots=True` itself
    would pass while its instances still carry a live `__dict__`."""
    slotless = sorted(
        cls.__name__
        for cls in _module_dataclasses()
        if "__slots__" not in cls.__dict__
    )
    assert not slotless, f"AST dataclasses without their own __slots__: {slotless}"


# Mutable builtins, spelled as they appear in an annotation. A denylist, not an
# allowlist: the allowlist would have to name every node type and drift with the
# union. The residual that costs is in the module ledger.
_MUTABLE_CONTAINERS = ("list[", "dict[", "set[", "bytearray")


def test_no_node_field_holds_a_mutable_container() -> None:
    """`frozen` and `slots` protect the node OBJECT; neither protects what a
    field POINTS AT. One `list[...]` field and a shared tree is mutable again
    through it — `game.zones.append(...)` needs no `setattr` at all, so every
    other wall here would still pass.

    Nothing enforced this before; it held because the vocabulary happens to be
    scalars, tuples, and nodes. That is the definition of a convention, and the
    memo makes it load-bearing, so it is walled here."""
    offenders = sorted(
        f"{cls.__name__}.{f.name}: {f.type}"
        for cls in _module_dataclasses()
        for f in dataclasses.fields(cls)
        if any(k in str(f.type) for k in _MUTABLE_CONTAINERS)
    )
    assert not offenders, (
        "AST field holding a mutable container — a memoized tree is shared, so "
        f"this is writable by every holder; use a tuple: {offenders}"
    )


def test_the_span_type_is_frozen_and_slotted_too() -> None:
    """`Span` lives in `cardlang.diagnostics`, so the `__module__` filter in
    `_module_dataclasses()` excludes it — but every node carries one, which
    makes it reachable from every memo-shared tree and part of the same hazard
    domain. The wall above enumerates the nodes; this pins the one non-node
    type they all hold."""
    assert Span.__dataclass_params__.frozen, "Span must be frozen"  # type: ignore[attr-defined]
    assert "__slots__" in Span.__dict__, "Span must declare its own __slots__"


# The one mutation route `frozen` + `slots` do NOT close, walled here instead.
# Matched over the parsed AST, not the text: `cardlang/parse.py`'s own Contract
# block names both spellings in prose, and a text scrape flags its own
# documentation.
def _bypass_sites(tree: ast.AST) -> list[int]:
    hits: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(f := node.func, ast.Attribute)
            and f.attr == "__setattr__"
            and isinstance(f.value, ast.Name)
            and f.value.id == "object"
        ):
            hits.append(node.lineno)
        # `x.__dict__[k] = v` / `del x.__dict__[k]` — a write, not a read.
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.Delete)):
            targets = (
                node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            )
            for t in targets:
                if (
                    isinstance(t, ast.Subscript)
                    and isinstance(v := t.value, ast.Attribute)
                    and v.attr == "__dict__"
                ):
                    hits.append(t.lineno)
    return hits


def test_no_setattr_bypass_on_shared_asts() -> None:
    """`object.__setattr__(node, <declared field>, v)` mutates a frozen slotted
    node in place — it is the same call frozen's own `__init__` uses, so
    neither `frozen` nor `slots` can refuse it. Since `parse_text`/`_check` are
    memoized, one such write is visible to every other holder of that tree.

    Nothing in the language can prevent it, so the guarantee is that the call
    does not appear at all. That was true by accident before this was written;
    this makes it true by construction, which is the difference between a
    convention and a wall (decisions.md "Closed-domain completeness"). A pass
    that genuinely needs to change a node builds a new one with
    `dataclasses.replace`."""
    root = pathlib.Path(__file__).parent.parent / "cardlang"
    scanned = 0
    offenders = []
    for path in sorted(root.rglob("*.py")):
        scanned += 1
        for line in _bypass_sites(ast.parse(path.read_text())):
            offenders.append(f"{path.relative_to(root.parent)}:{line}")
    assert scanned > 0, "the scrape found no cardlang/ modules — check the path"
    assert not offenders, (
        "in-place AST mutation bypass in cardlang/ — a memoized tree is shared, "
        f"so this is visible to every holder; use dataclasses.replace: {offenders}"
    )


def test_probe_the_bypass_scrape_actually_matches() -> None:
    """Guards the wall above against becoming vacuous: a matcher that silently
    stopped matching would report zero offenders and read as a clean bill of
    health. Also pins that a mention in PROSE is not a hit — `parse.py`'s
    Contract block names both spellings, and a text scrape flagged it."""
    assert _bypass_sites(ast.parse("object.__setattr__(node, 'name', v)")) == [1]
    assert _bypass_sites(ast.parse("node.__dict__['x'] = v")) == [1]
    assert _bypass_sites(ast.parse("game = dataclasses.replace(game, name=v)")) == []
    assert _bypass_sites(ast.parse("v = node.__dict__['x']")) == []  # a read
    assert _bypass_sites(ast.parse("'''docs naming object.__setattr__ in prose'''")) == []
