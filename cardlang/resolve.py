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

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.mechanics import LIBRARY_MECHANICS
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES

# Roles a zone may be indexed by or owned by. Grows with the seating model.
_KNOWN_ROLES = {"player"}


def resolve(game: n.Game) -> n.Game:
    bag = DiagnosticBag()
    for zone in game.zones:
        _resolve_zone(zone, bag)

    defined_rules = {r.name for r in game.rules}
    for rule in game.rules:
        _resolve_rule(rule, bag)
    _resolve_phase_level(game.phases, defined_rules, bag)

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


def _raise_if_errors(bag: DiagnosticBag) -> None:
    if not bag.has_errors:
        return
    error = DiagnosticError(bag.items[0])
    if len(bag.items) > 1:
        error.add_note(bag.format())
    raise error
