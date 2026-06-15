"""Resolve stage: name resolution.

This pass checks that the structural references in a game hang together —
the class of error a type checker catches before anything runs:

- every zone's type names a known library zone type (and is parameterized
  correctly);
- every `active_rules:` entry names a rule defined in the game;
- every move type referenced by `constrains:`, `legal_moves:`, or a
  transition event is a known library move type;
- every `instantiate` names a known library mechanic;
- every `transition_to:` target is a sibling phase.

Deep expression name resolution (state variables, suits, the `action` fields,
stdlib functions) needs the typed object model and lands with the type
checker; this pass is the structural net.

On success the (unchanged) :class:`Game` flows on. On any error it raises with
every diagnostic collected, not just the first.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Iterator

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError, Span
from cardlang.stdlib.functions import (
    STDLIB_CALL_FUNCS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_VALUE_NAMES,
    ZONE_METHODS,
)
from cardlang.stdlib.mechanics import LIBRARY_MECHANICS
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.values import deck_suits, enum_values
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES

# Roles a zone may be indexed by or owned by. Grows with the seating model.
_KNOWN_ROLES = {"player", "team"}

# The magic namespaces a bare name may resolve to.
_PRONOUNS = frozenset({"state", "action", "outcome", "active_rules", "actor"})


def resolve(game: n.Game) -> n.Game:
    bag = DiagnosticBag()
    for zone in game.zones:
        _resolve_zone(zone, bag)

    defined_rules = {r.name for r in game.rules}
    for rule in game.rules:
        _resolve_rule(rule, bag)
    _resolve_phase_level(game.phases, defined_rules, bag)

    # Deep name resolution: classify every bare name and validate calls,
    # methods, card literals, and the rotate/winner targets.
    cats = _categories(game)
    game = _classify_names(game, cats, bag)
    _validate_refs(game, cats, bag)

    _raise_if_errors(bag)
    return game


def _resolve_zone(zone: n.ZoneDecl, bag: DiagnosticBag) -> None:
    if zone.index is not None and zone.index not in _KNOWN_ROLES:
        bag.error(f"unknown index role '{zone.index}'", zone.span)

    ref = zone.type_ref
    takes_owner = LIBRARY_ZONE_TYPES.get(ref.name)
    if takes_owner is None:
        bag.error(f"unknown zone type '{ref.name}'", ref.span)
        return
    if takes_owner and len(ref.args) != 1:
        bag.error(
            f"zone type '{ref.name}' takes one owner argument, got {len(ref.args)}",
            ref.span,
        )
    if not takes_owner and ref.args:
        bag.error(f"zone type '{ref.name}' takes no type arguments", ref.span)
    for arg in ref.args:
        if arg.name not in _KNOWN_ROLES:
            bag.error(f"unknown owner '{arg.name}'", arg.span)


def _resolve_rule(rule: n.RuleDef, bag: DiagnosticBag) -> None:
    if rule.constrains is not None and rule.constrains not in LIBRARY_MOVE_TYPES:
        bag.error(
            f"rule '{rule.name}' constrains unknown move type '{rule.constrains}'",
            rule.span,
        )


def _resolve_phase_level(
    phases: tuple[n.Phase, ...], defined_rules: set[str], bag: DiagnosticBag
) -> None:
    """Resolve a set of sibling phases, then recurse into each one's children.

    Transition targets resolve against the *sibling* set, since
    `transition_to: Y` inside phase X names a sibling of X.
    """
    sibling_names = {p.name for p in phases}
    for phase in phases:
        for item in phase.items:
            _resolve_phase_item(item, sibling_names, defined_rules, bag)
        children = tuple(i for i in phase.items if isinstance(i, n.Phase))
        _resolve_phase_level(children, defined_rules, bag)


def _resolve_phase_item(
    item: n.PhaseItem,
    sibling_names: set[str],
    defined_rules: set[str],
    bag: DiagnosticBag,
) -> None:
    if isinstance(item, n.ActiveRules):
        for ref in item.refs:
            if ref.name not in defined_rules:
                bag.error(f"active_rules names undefined rule '{ref.name}'", ref.span)
    elif isinstance(item, n.LegalMoves):
        for name in item.names:
            if name not in LIBRARY_MOVE_TYPES:
                bag.error(f"legal_moves names unknown move type '{name}'", item.span)
    elif isinstance(item, n.TransitionTo):
        if item.target not in sibling_names:
            bag.error(
                f"transition_to target '{item.target}' is not a sibling phase",
                item.span,
            )
        if item.event.move_type not in LIBRARY_MOVE_TYPES:
            bag.error(
                f"transition event names unknown move type '{item.event.move_type}'",
                item.event.span,
            )
    elif isinstance(item, (n.BeforeEach, n.AfterEach)):
        for stmt in item.body:
            _resolve_stmt(stmt, bag)
    elif isinstance(item, (n.Phase, n.StateBlock)):
        pass  # phases recurse via the level walk; state blocks resolve later
    else:
        _resolve_stmt(item, bag)


def _resolve_stmt(stmt: n.Stmt, bag: DiagnosticBag) -> None:
    """Walk a statement (recursing into compound bodies) for the references this
    pass checks — currently `instantiate` mechanics."""
    if isinstance(stmt, n.Instantiate):
        if stmt.mechanic not in LIBRARY_MECHANICS:
            bag.error(f"instantiate names unknown mechanic '{stmt.mechanic}'", stmt.span)
    elif isinstance(stmt, n.RepeatUntil):
        for inner in stmt.body:
            _resolve_stmt(inner, bag)
    elif isinstance(stmt, n.EachSimultaneous):
        _resolve_stmt(stmt.body, bag)
    elif isinstance(stmt, n.ForEach):
        _resolve_stmt(stmt.body, bag)
    elif isinstance(stmt, n.IfStmt):
        for inner in stmt.then_body:
            _resolve_stmt(inner, bag)
        for inner in stmt.else_body or ():
            _resolve_stmt(inner, bag)


@dataclass(frozen=True)
class _Categories:
    """The namespaces a bare name resolves against, collected once per game."""

    locals: frozenset[str]
    state_vars: frozenset[str]
    zones: frozenset[str]
    enums: frozenset[str]
    functions: frozenset[str]
    ranks: frozenset[str]
    suits: frozenset[str]


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


def _categories(game: n.Game) -> _Categories:
    state_vars: set[str] = set()
    locals_: set[str] = set()
    for nd in _walk(game):
        match nd:
            case n.StateDecl():
                state_vars.add(nd.name)
            case n.Lambda():
                locals_.add(nd.param)
            case n.Comprehension() | n.Quantifier() | n.ForEach():
                locals_.add(nd.binder)
            case n.MoveTypeDef() if nd.param is not None:
                locals_.add(nd.param.name)  # the param binds in guard/effect
            case n.EachSimultaneous():
                locals_.add(nd.role)
            case n.PlayerQuery():
                locals_.add("player")  # the implicit per-candidate binder
            case n.LetStmt():
                locals_.add(nd.name)
                if nd.index is not None:
                    locals_.add(nd.index)
    return _Categories(
        locals=frozenset(locals_),
        state_vars=frozenset(state_vars),
        zones=frozenset(z.name for z in game.zones),
        enums=enum_values(game.deck),
        functions=STDLIB_VALUE_NAMES,
        ranks=frozenset(game.ranking),
        suits=deck_suits(game.deck),
    )


def _classify(name: str, cats: _Categories) -> str | None:
    if name == "none":
        return "null"  # the universal absence literal (any optional's null)
    if name in ("true", "false"):
        return "bool"  # boolean literals
    if name in cats.locals:
        return "local"
    if name in cats.state_vars:
        return "state_var"
    if name in cats.zones:
        return "zone"
    if name in cats.enums:
        return "enum_value"
    if name in _PRONOUNS:
        return "pronoun"
    if name in cats.functions:
        return "function"
    return None


def _classify_names(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> n.Game:
    """Immutably rewrite every NameRef with its classification, recording an
    error for any name that resolves to nothing."""
    result = _rewrite(game, cats, bag)
    assert isinstance(result, n.Game)
    types = tuple(_classify_type_derived(t, cats, bag) for t in result.types)
    return replace(result, types=types)


def _classify_type_derived(
    tdef: n.TypeDef, cats: _Categories, bag: DiagnosticBag
) -> n.TypeDef:
    """Rewrite a type's derived-field bodies with the type's own fields in local
    scope — derived expressions reference sibling fields by bare name, which the
    generic pass (blind to struct fields) would flag as unresolved."""
    field_names = frozenset(f.name for f in tdef.fields)
    scoped = replace(cats, locals=cats.locals | field_names)
    derived = tuple(
        replace(d, value=_rewrite(d.value, scoped, bag))  # type: ignore[arg-type]
        for d in tdef.derived
    )
    return replace(tdef, derived=derived)


def _rewrite_produce_arm(
    arm: n.ProduceArm, cats: _Categories, bag: DiagnosticBag
) -> n.ProduceArm:
    """Rewrite one produces-arm body with the arm's payload binders in local
    scope — so bare binder references resolve, without leaking into other arms or
    the enclosing game (mirrors `_classify_type_derived` for struct fields)."""
    scoped = replace(cats, locals=cats.locals | frozenset(arm.binders))
    body = tuple(_rewrite(s, scoped, bag) for s in arm.body)
    return replace(arm, body=body)  # type: ignore[arg-type]


def _rewrite(node: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if isinstance(node, n.NameRef):
        kind = _classify(node.name, cats)
        if kind is None:
            bag.error(f"unresolved name '{node.name}'", node.span)
        return replace(node, ref_kind=kind)
    if isinstance(node, n.TypeDef):
        return node  # derived bodies are rewritten by _classify_type_derived
    if isinstance(node, n.Produces):
        # Each arm's payload binders scope to that arm's body only — they must not
        # leak into the global `locals` set (which would shadow same-named state
        # vars across the whole game).
        arms = tuple(_rewrite_produce_arm(arm, cats, bag) for arm in node.arms)
        return replace(node, arms=arms)
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = _rewrite_value(value, cats, bag)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _rewrite_value(value: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, cats, bag)
    if isinstance(value, tuple):
        return tuple(_rewrite_value(item, cats, bag) for item in value)
    return value


def _validate_refs(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> None:
    defined_move_types = {m.name for m in game.move_types}
    defined_types = {t.name for t in game.types}
    defined_defines = {d.name for d in game.defines}
    # A `produces:` consumer may also name an outcome-declaring phase (its outcome
    # is produced as the phase runs, then dispatched by a sibling consumer).
    outcome_phases = {
        nd.name for nd in _walk(game) if isinstance(nd, n.Phase) and nd.outcome_cases
    }
    for nd in _walk(game):
        match nd:
            case n.Call() if nd.func not in STDLIB_CALL_FUNCS:
                bag.error(f"call to unknown function '{nd.func}'", nd.span)
            case n.StructLit() if nd.type_name not in defined_types:
                bag.error(f"unknown type '{nd.type_name}'", nd.span)
            case n.Produces() if (
                nd.define not in defined_defines and nd.define not in outcome_phases
            ):
                bag.error(
                    f"produces names unknown define or outcome phase '{nd.define}'",
                    nd.span,
                )
            case n.MethodCall() if nd.method not in ZONE_METHODS:
                bag.error(f"unknown zone method '{nd.method}'", nd.span)
            case n.CardLiteral():
                if nd.rank not in cats.ranks:
                    bag.error(f"unknown rank '{nd.rank}' in card literal", nd.span)
                if nd.suit not in cats.suits:
                    bag.error(f"unknown suit '{nd.suit}' in card literal", nd.span)
            case n.RotateStmt():
                if nd.var not in cats.state_vars and nd.var not in cats.locals:
                    bag.error(f"rotate of unknown variable '{nd.var}'", nd.span)
                for value in nd.values:
                    if value not in cats.enums:
                        bag.error(f"rotate through unknown value '{value}'", nd.span)
            case n.Winner() if nd.target not in cats.state_vars:
                bag.error(f"winner references unknown variable '{nd.target}'", nd.span)
            case n.Offer():
                for name in nd.move_types:
                    if name not in defined_move_types:
                        bag.error(f"offer names unknown move type '{name}'", nd.span)
            case n.Round():
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.error(f"round source zone '{nd.source_zone}' is unknown", nd.span)
                if nd.play_zone not in zone_names:
                    bag.error(f"round play zone '{nd.play_zone}' is unknown", nd.span)
                if nd.outcome_fn not in STDLIB_VALUE_NAMES:
                    bag.error(f"round outcome '{nd.outcome_fn}' is unknown", nd.span)
                if nd.move_type not in LIBRARY_MOVE_TYPES:
                    bag.error(f"round move type '{nd.move_type}' is unknown", nd.span)
                if (
                    nd.early_termination is not None
                    and nd.early_termination not in STDLIB_EARLY_PREDICATES
                ):
                    bag.error(
                        f"round early-termination predicate "
                        f"'{nd.early_termination}' is unknown",
                        nd.span,
                    )


def _raise_if_errors(bag: DiagnosticBag) -> None:
    if not bag.has_errors:
        return
    error = DiagnosticError(bag.items[0])
    if len(bag.items) > 1:
        error.add_note(bag.format())
    raise error
