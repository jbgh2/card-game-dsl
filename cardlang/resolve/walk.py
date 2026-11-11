"""The resolver's tree walk.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      an AST node for ``_walk``, which yields nothing for a tuple;
              a field value, tuple or node, for ``_child_nodes``.
Establishes:  every node beneath it, by its dataclass fields, spans
              skipped, and the one-level rebuilding descent (``_traverse``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import fields, is_dataclass, replace
from cardlang.diagnostics import Span


def _traverse(node: object, step: Callable[[str, object], object]) -> object:
    """The immutable one-level descent shared by every default-arm traversal
    in the resolve package (`substitute`'s default arm, `_rewrite`'s default arm, and
    `_rewrite`'s per-field binder-scoping dispatch below): every dataclass
    field — guarded against `Span`, a leaf the walk must not open — is handed
    to `step` along with its field name, and replaced only where `step`
    actually returns something different. `dataclasses.replace` is skipped
    entirely when nothing changed, so an untouched subtree keeps its identity.
    Non-dataclass nodes (a tuple, a leaf) pass through unchanged — tuple
    mapping and leaf handling are the callers' job (`_substitute_value` /
    `_rewrite_value`), since the two differ there: `_rewrite_value`'s tuple
    arm folds `let` bindings sequentially into later siblings, which
    `substitute` (fixed-mapping template substitution, not scope-sensitive)
    has no need of."""
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = step(f.name, value)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _walk(node: object) -> Iterator[object]:
    """Yield every AST node under (and including) ``node``, skipping spans."""
    if not is_dataclass(node) or isinstance(node, Span):
        return
    yield node
    for f in fields(node):
        value = getattr(node, f.name)
        yield from _child_nodes(value)


def _child_nodes(value: object) -> Iterator[object]:
    if is_dataclass(value) and not isinstance(value, Span):
        yield from _walk(value)
    elif isinstance(value, tuple):
        for item in value:
            yield from _child_nodes(item)
