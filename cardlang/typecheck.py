"""Typecheck stage.

Walking-skeleton subset: the player count must be sensible (at least one
player; a range's upper bound must not precede its lower bound). The full
typed object model — zone parameterization, the ``<>`` value-parameter rule,
rule-clause types, outcome exhaustiveness — lands in Phase C.

Like :mod:`cardlang.resolve`, this annotates rather than rewrites: the
(unchanged) :class:`Game` flows on, and the IR stays at the resolved-AST
level.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, assert_never

from cardlang.ast import nodes as n
from cardlang.ast.nodes import Game
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.values import DIRECTION_VALUES, deck_suits
from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TOptional,
    TPlayer,
    TString,
    TTeam,
    Type,
)

# Declared scalar type names → their Type. Enum names (`Suit`/`Rank`/`Direction`)
# and unknown names (user-defined types, deferred) are handled separately.
_SCALAR_TYPES: dict[str, type] = {
    "Integer": TInteger,
    "Boolean": TBoolean,
    "String": TString,
    "Player": TPlayer,
    "Team": TTeam,
    "Card": TCard,
}
_ENUM_TYPES = frozenset({"Suit", "Rank", "Direction"})


def type_from_name(name: str, optional: bool) -> Type:
    """Map a declared type name (a `StateDecl` `type_name`) to a `Type`.

    Unknown names — user-defined types, deferred to a later stage — resolve to
    the permissive `TAny`. ``optional`` wraps the result in `TOptional`.
    """
    base: Type
    if name in _SCALAR_TYPES:
        base = _SCALAR_TYPES[name]()
    elif name in _ENUM_TYPES:
        base = TEnum(name)
    else:
        base = TAny()
    return TOptional(base) if optional else base


def value_enum_map(game: Game) -> dict[str, TEnum]:
    """Map each deck/stdlib enum *value* to its enum type.

    `resolve` collapses suits, ranks, and directions into one `enum_value`
    ref_kind; the type checker re-derives which enum each value belongs to so a
    `Suit` is not confused with an `Integer` or a `Direction`.
    """
    m: dict[str, TEnum] = {}
    for suit in deck_suits(game.deck):
        m[suit] = TEnum("Suit")
    for rank in game.ranking:
        m[rank] = TEnum("Rank")
    for direction in DIRECTION_VALUES:
        m[direction] = TEnum("Direction")
    return m


@dataclass(frozen=True)
class TypeEnv:
    """The types a bare name resolves against during inference: declared state
    vars, zone contents, deck/stdlib enum values, and scoped local binders."""

    state_vars: Mapping[str, Type] = field(default_factory=dict)
    zones: Mapping[str, Type] = field(default_factory=dict)
    value_enums: Mapping[str, TEnum] = field(default_factory=dict)
    locals: Mapping[str, Type] = field(default_factory=dict)

    def with_local(self, name: str, t: Type) -> "TypeEnv":
        return replace(self, locals={**self.locals, name: t})


def infer(e: n.Expr, env: TypeEnv) -> Type:
    """Infer the type of an expression. Unrefined arms return `TAny` (the
    permissive top); precision is added construct by construct."""
    match e:
        case n.IntLit():
            return TInteger()
        case n.StrLit():
            return TString()
        case n.CardLiteral():
            return TCard()
        case n.AllPlayers():
            return TCollection(TPlayer())
        case n.NameRef():
            return _name_type(e, env)
        case (
            n.Member()
            | n.Subscript()
            | n.Call()
            | n.MethodCall()
            | n.BinOp()
            | n.Not()
            | n.IsCheck()
            | n.Lambda()
            | n.Quantifier()
            | n.IfExpr()
            | n.Comprehension()
            | n.Choose()
            | n.PlayerQuery()
        ):
            return TAny()
        case _ as unreachable:
            assert_never(unreachable)


def _name_type(e: n.NameRef, env: TypeEnv) -> Type:
    match e.ref_kind:
        case "local":
            return env.locals.get(e.name, TAny())
        case "state_var":
            return env.state_vars.get(e.name, TAny())
        case "zone":
            return env.zones.get(e.name, TAny())
        case "enum_value":
            return env.value_enums.get(e.name, TAny())
        case "bool":
            return TBoolean()
        case "null":
            return TOptional(TAny())
        case _:
            return TAny()  # pronoun / function / routing / unresolved


def typecheck(game: Game) -> Game:
    bag = DiagnosticBag()

    players = game.players
    if players.low < 1:
        bag.error(f"a game needs at least one player, got {players.low}", players.span)
    if players.high is not None and players.high < players.low:
        bag.error(
            f"player range upper bound {players.high} precedes lower bound {players.low}",
            players.span,
        )

    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game
