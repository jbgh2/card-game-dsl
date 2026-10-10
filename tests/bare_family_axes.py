"""Axis derivation for the bare-family grid (`tests/test_bare_family_grid.py`).

Separate from the grid module so the review can replay the HEAD-derived cell
list against the merge base without the base tree re-deriving it.

A zone family named without a subscript means the acting player's instance:
the engine keys it by the acting SEAT. The grid crosses every index role a
family can be declared with against every position a family name can be
written bare, and each axis below reads the registry that defines it.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardlang.ast import nodes as n
from cardlang.builtins.functions import BUILTIN_IMPLICIT_READS
from cardlang.domains import ZONE_INDEX_ROLES, Role
from cardlang.resolve import _REFERENCE_SLOTS

# --- axis: the index role of the named family -------------------------------
# DERIVED: the registry's zone-indexable roles (`ZONE_INDEX_ROLES`), plus the
# game-declared position domain and the unindexed single zone. The board's
# `cell` domain is a position domain in a piece game; the grid's corpus sweep
# reaches it through the board games rather than this card template.
POSITION_ROLE = "position"
SINGLE = "single"

# role -> the `zones { }` line declaring the family `won` with that index.
_ROLE_DECLS: dict[str, str] = {
    Role.PLAYER.value: "won[player] : PlayerPile<player>",
    Role.TEAM.value: "won[team] : TeamPile<team>",
    POSITION_ROLE: "won[column] : Cascade<column>",
    SINGLE: "won : Discard",
}
assert {r.value for r in ZONE_INDEX_ROLES} | {POSITION_ROLE, SINGLE} == set(_ROLE_DECLS), (
    "ZONE_INDEX_ROLES changed: give the new zone-index role a declaration row"
)
ROLES: tuple[str, ...] = tuple(_ROLE_DECLS)

# The role whose bare name means the acting player's instance: the one row
# whose domain binds the actor.
ADMITTED_ROLE = Role.PLAYER.value

# The concealed twin of the team row: a team zone only its own side sees.
CONCEALED_TEAM_DECL = "won[team] : Hand<team>"


def role_decl(role: str) -> str:
    return _ROLE_DECLS[role]


# --- axis: the expression positions a bare family name is written at --------
# A bare family name in an expression is a `NameRef` the resolver stamps
# `ref_kind == "zone"`; the guard is one walk over every such NameRef, so the
# grid SAMPLES expression positions rather than enumerating every `Expr`
# field. Each row names the (node class, field) its sentence places the bare
# `won` at, and `test_each_expression_row_sits_where_it_says` recomputes that
# from the parse, so a row cannot drift from its claim.


@dataclass(frozen=True)
class ExprRow:
    key: str
    node: type
    field: str
    stmt: str  # written inside `for each player p: as p { ... }`
    move_when: bool = False  # True: `stmt` is a move type's `when:` guard
    function: bool = False  # True: `stmt` is a Boolean function's body


EXPR_ROWS: tuple[ExprRow, ...] = (
    ExprRow("move_source", n.Transfer, "source", "move all cards from won to deck"),
    ExprRow("move_dest", n.Transfer, "dest", "move all cards from hand to won"),
    ExprRow("gather_dest", n.Transfer, "dest", "move all cards to won"),
    ExprRow("shuffle", n.EpistemicOp, "zone", "shuffle won"),
    ExprRow("card_count", n.CardQuery, "source",
            "if (number of cards in won) > 0 { score[0] := 1 }"),
    ExprRow("fold_source", n.Comprehension, "source",
            "score[0] := sum of 1 over cards in won"),
    ExprRow("is_empty", n.IfStmt, "cond", "if won is empty { score[0] := 1 }"),
    ExprRow("let_value", n.LetStmt, "value",
            "let w = won  move all cards from hand to w"),
    ExprRow("builtin_arg", n.Call, "args",
            "if (number of cards in won) > 0 and top_of(won).suit is hearts { score[0] := 1 }"),
    ExprRow("move_type_when", n.MoveTypeDef, "when", "won is empty", move_when=True),
    ExprRow("function_body", n.FunctionDef, "body", "won is empty", function=True),
)


# --- axis: the string slots naming a zone ------------------------------------
# DERIVED from resolve's reference-slot registry: every slot whose namespace
# is "zone". A source slot names the per-player family each acting seat plays
# from; a play slot names the one pile every play lands in.
ZONE_SLOTS: tuple[tuple[type, str], ...] = tuple(
    sorted((k for k, v in _REFERENCE_SLOTS.items() if v == "zone"),
           key=lambda k: (k[0].__name__, k[1]))
)
SOURCE_SLOT_FIELD = "source_zone"
PLAY_SLOT_FIELD = "play_zone"
assert {f for _, f in ZONE_SLOTS} == {SOURCE_SLOT_FIELD, PLAY_SLOT_FIELD}, (
    "a new zone reference slot: decide which role its name may have"
)


# --- axis: the Builtins that read a family by name ---------------------------
# DERIVED from `BUILTIN_IMPLICIT_READS`: each reads its family whole and
# hands the instance KEYS back as seats.
IMPLICIT_READS: tuple[tuple[str, str], ...] = tuple(
    (fn, fam) for fn, (fam, _need) in sorted(BUILTIN_IMPLICIT_READS.items())
)
