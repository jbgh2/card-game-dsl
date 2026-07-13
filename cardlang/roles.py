"""The closed iteration-role registry.

`for each <role> <binder>` and `any`/`all <role> <binder>` quantifiers range
over one of four roles: the seat roles (`player`, `team`) or the deck's value
domains (`suit`, `rank`). This is the one place that four-name set is
spelled:

- `resolve.py` validates a `ForEach`'s role against `ROLES` (`_ITERATION_ROLES`).
- `typecheck.py` derives a `for each`/quantifier binder's `Type` from
  `role_type` (`_role_type`).
- `runtime/evaluate.py`'s `_role_domain` derives the actual runtime domain
  (players/teams/suits/ranks) per role, and `runtime/execute.py` imports that
  one function rather than re-deriving suit/rank domains itself.

A leaf module (depends only on `cardlang.types`) so all three layers — parse
front end, checker, and runtime — can import it without a cycle. Previously
the four sites hand-duplicated the same role set with nothing pinning them
equal; `tests/test_role_registry.py` pins the sync.

Distinct from resolve's `_KNOWN_ROLES` (`{"player", "team"}`), the closed set
of roles a *zone* may be indexed/owned by — a different, smaller domain this
registry does not cover.
"""

from __future__ import annotations

from cardlang.types import TAny, TEnum, TPlayer, TTeam, Type

# The closed set of roles `for each <role>`/`any <role>` may range over: the
# seat roles plus the deck's value domains. Grows only alongside the seating
# model or a new value domain the language exposes to quantifiers.
ROLES: frozenset[str] = frozenset({"player", "team", "suit", "rank"})

# Per-role binder type, used by typecheck to type a `for each`/quantifier
# binder inside its body. Covers exactly `ROLES` — pinned by
# tests/test_role_registry.py.
ROLE_TYPES: dict[str, Type] = {
    "player": TPlayer(),
    "team": TTeam(),
    "suit": TEnum("Suit"),
    "rank": TEnum("Rank"),
}


def role_type(role: str) -> Type:
    """The type a `for each <role>` / `any <role>` binder carries. `ROLES` is
    closed and resolve rejects anything outside it; the `TAny` fallback is a
    backstop for the permissive walks that run before that rejection."""
    return ROLE_TYPES.get(role, TAny())
