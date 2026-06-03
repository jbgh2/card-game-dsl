"""Resolve stage: name resolution.

Walking-skeleton subset: every zone's type must name a known library zone
type, an owner-parameterized type must be given exactly one argument, and a
``[role]`` index or owner argument must name a known role (``player`` today).
The full lexical-scope resolver (phases, rules, mechanics, mechanic-internal
state) lands in Phase B; this proves the seam and the diagnostic plumbing.

On success the (unchanged) :class:`Game` flows on — resolution annotates
rather than rewrites, keeping IR at the resolved-AST level. On any error it
raises with every diagnostic collected, not just the first.
"""

from __future__ import annotations

from cardlang.ast.nodes import Game, ZoneDecl
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES

# Roles a zone may be indexed by or owned by. Grows with the seating model.
_KNOWN_ROLES = {"player"}


def resolve(game: Game) -> Game:
    bag = DiagnosticBag()
    for zone in game.zones:
        _resolve_zone(zone, bag)
    _raise_if_errors(bag)
    return game


def _resolve_zone(zone: ZoneDecl, bag: DiagnosticBag) -> None:
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


def _raise_if_errors(bag: DiagnosticBag) -> None:
    if not bag.has_errors:
        return
    # The first diagnostic rides on the exception; the rest are attached as
    # notes so every problem surfaces in one run.
    error = DiagnosticError(bag.items[0])
    if len(bag.items) > 1:
        error.add_note(bag.format())
    raise error
