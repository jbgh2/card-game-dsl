"""Axis derivation for the `winner:` target grid.

Split from the grid module for the same reason as `tests/teams_axes.py`: the
review replays the HEAD-derived cell list against the merge base, and a base
tree re-deriving its own list would silently drop the rows the change adds.

`winner: <rank-dir> <name>` ranks a game by a state variable. Resolve already
walls the name itself — an undeclared name, and a name declared inside a
phase rather than at game level, are both diagnostics. What remains
unconstrained is the DECLARATION the name resolves to, which has exactly two
free properties, and both are registry-defined:

  * its index — `StateDecl.index`, a role name, against `domains.Role`;
  * its declared type — `StateDecl.type_name`, against
    `typecheck.KNOWN_TYPE_NAMES`, in a plain or an optional form.

Neither axis is read off the guard's own coverage. The role axis crosses ALL
of `Role`, not the `ZONE_INDEX_ROLES` subset a state index may legally take,
so the day a role joins the indexable set the grid has a row for it already.
"""

from __future__ import annotations

from collections.abc import Iterator

from cardlang.domains import Role
from cardlang.typecheck import KNOWN_TYPE_NAMES

# --- axis: the target declaration's index -----------------------------------
# DERIVED from the `Role` enum — the definition site (`domains.Role`: "THE
# definition site: `Domain.id` is a `Role`, so the enum and the table cannot
# disagree"). `None` is the unindexed case, which is not a role and so has no
# member to derive: a scalar declaration is the absence of the whole clause.
INDEXES: tuple[str | None, ...] = (None,) + tuple(r.value for r in Role)


# --- axis: the target declaration's declared type ----------------------------
# DERIVED from `KNOWN_TYPE_NAMES`, the closed set of built-in declared-type
# names resolve validates every declaration against. A state declaration also
# admits a game's own struct names; those are carried as a separate cell
# rather than a whole sub-axis, because a struct's FIELDS do not vary the
# property under guard (a struct is unrankable whatever it holds).
#
# A default literal is needed to write the declaration at all, and there is
# no registry of them — so the table below is pinned against
# KNOWN_TYPE_NAMES rather than trusted: a new declared type reddens
# `test_default_table_covers_every_declared_type` instead of silently
# dropping its rows from the grid.
DEFAULTS: dict[str, str] = {
    "Integer": "0",
    "Boolean": "false",
    "String": '"x"',
    "Player": "0",
    "Team": "0",
    "Card": "none",  # no Card literal exists; only the optional form is writable
    "Suit": "hearts",
    "Rank": "A",
    "SeatDirection": "left",
}

# `Card` has no literal, so `Card = <default>` cannot be written at all: the
# plain form is unreachable through the grammar and only `Card?` (defaulting
# to `none`) is a real cell. Recorded here, and pinned by the grid's
# unreachable-cell row rather than left as a gap in the parametrization.
NO_PLAIN_LITERAL: frozenset[str] = frozenset({"Card"})

STRUCT_TYPE = "Pair"  # a game-declared struct, the non-builtin type cell


def type_cells() -> Iterator[tuple[str, str, bool]]:
    """(type name as written, default literal, is_optional) per declarable type.

    Crosses every `KNOWN_TYPE_NAMES` member with the plain and optional
    forms, skipping the plain forms that have no writable literal, and adds
    the game-declared struct type in both forms.
    """
    for name in sorted(KNOWN_TYPE_NAMES) + [STRUCT_TYPE]:
        default = DEFAULTS.get(name, f"{STRUCT_TYPE} {{ a: 0 }}")
        if name not in NO_PLAIN_LITERAL:
            yield name, default, False
        yield f"{name}?", "none", True


def cells() -> Iterator[tuple[str, str | None, str, str, bool]]:
    """(cell id, index role or None, type as written, default, is_optional)."""
    for index in INDEXES:
        for written, default, optional in type_cells():
            yield (
                f"{index or 'scalar'}__{written.replace('?', '_opt')}",
                index,
                written,
                default,
                optional,
            )
