"""Axis derivation for the team-question grid.

Separate from the grid module so the review can replay the HEAD-derived cell
list against the merge base without the base tree re-deriving its own.

A sentence asks about teams in one of two ways, each with its own registry:

  * it ranges a binder over a role -- every AST node carrying a `role` field,
    found by walking `cardlang.ast.nodes`, with `team` in that field;
  * it calls a Builtin whose signature takes or yields a `Team` -- every
    `CALL_SIGS` entry whose types mention `TTeam`, at any depth.

Each derived member needs a sentence to be written at all, and those
sentences are tables below, pinned against the derivation so a new member
reddens the grid instead of dropping out of it.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Iterator

from cardlang.ast import nodes as n
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.types import TTeam


def role_nodes() -> frozenset[str]:
    """Every AST node class with a `role` field."""
    return frozenset(
        cls.__name__
        for _, cls in inspect.getmembers(n, inspect.isclass)
        if dataclasses.is_dataclass(cls)
        and cls.__module__ == n.__name__
        and "role" in {f.name for f in dataclasses.fields(cls)}
    )


def _mentions_team(value: object) -> bool:
    if isinstance(value, TTeam):
        return True
    if isinstance(value, tuple):
        return any(_mentions_team(v) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return any(_mentions_team(getattr(value, f.name)) for f in dataclasses.fields(value))
    return False


def team_builtins() -> frozenset[str]:
    """Every Builtin whose signature takes or yields a `Team`."""
    return frozenset(name for name, sig in CALL_SIGS.items() if _mentions_team(sig))


# One statement per role-ranging node, ranging over teams. `Quantifier` has
# two kinds, and both are written.
ROLE_SENTENCES: dict[str, tuple[str, ...]] = {
    "Quantifier": (
        "if (any team where true) { shuffle deck }",
        "if (all teams where false) { shuffle deck }",
    ),
    "ForEach": ("for each team t: shuffle deck",),
    "EachSimultaneous": ("each team simultaneously: shuffle deck",),
}

# One call per team-typed Builtin, written where an expression is read.
BUILTIN_CALLS: dict[str, str] = {
    "team_of": "team_of(0)",
}


@dataclasses.dataclass(frozen=True)
class Cell:
    id: str
    member: str
    phase_body: str
    state: str
    functions: str


def cells() -> Iterator[Cell]:
    """Each role sentence as a phase statement; each Builtin call at three
    expression positions -- a statement's condition, a function body, and a
    `let` binding."""
    for node in sorted(ROLE_SENTENCES):
        for i, sentence in enumerate(ROLE_SENTENCES[node]):
            yield Cell(f"{node}-{i}", node, sentence, "", "")
    for name in sorted(BUILTIN_CALLS):
        call = BUILTIN_CALLS[name]
        yield Cell(f"{name}-condition", name, f"if ({call} is {call}) {{ shuffle deck }}", "", "")
        yield Cell(
            f"{name}-function",
            name,
            "if (asks()) { shuffle deck }",
            "",
            f"function asks() = {call} is {call}",
        )
        yield Cell(f"{name}-let", name, f"let t = {call}  shuffle deck", "", "")
