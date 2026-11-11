"""Resolve step: zone declarations against the position domains."""

from __future__ import annotations

from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.primitives_block import COLLECTION_TYPE_CONSTRUCTOR
from cardlang.diagnostics import DiagnosticBag
from cardlang.domains import ZONE_INDEX_ROLES, Role, role_names, role_of
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, ZONE_PROJECTIONS

# Roles a zone may be indexed by or owned by — the `zone_key_of` column of the
# domain table, not a hand-written local list.
_KNOWN_ROLES = ZONE_INDEX_ROLES

# The EMPTY-DOMAIN Owner Guards below (a team-indexed state/zone declaration in a game
# that declares no `teams:`) implement the `team` row only, because
# `team` is the one role domain a game can leave undeclared: seats come from the
# mandatory `players:` clause, the card axes from the deck. That is a fact about
# the registry, so it is pinned against the registry rather than assumed — the
# same contract `runtime/execute.py` keeps for `SIMULTANEOUS_ROLES`. Without
# this, adding a zone-indexable role whose domain can also be empty would slip
# past those Owner Guards silently, which is the drift the domain table exists
# to end (domains.py, `zone_key_of`).
# This IS the registry reconciliation: the assert exists so a new
# zone-indexable role fails here BY NAME rather than escaping the Owner Guards
# below, which implement the `team` row only.
assert ZONE_INDEX_ROLES == {Role.PLAYER, Role.TEAM}, (
    f"resolve's empty-domain Owner Guards implement the `team` row only; "
    f"ZONE_INDEX_ROLES is {role_names(ZONE_INDEX_ROLES)} — decide whether the new "
    f"role's domain can be empty, and extend those Owner Guards, before widening the "
    f"domain table"
)


def _resolve_zone(
    zone: n.ZoneDecl, bag: DiagnosticBag, positions: frozenset[str]
) -> None:
    index_known = (
        zone.index is None
        or role_of(zone.index) in _KNOWN_ROLES
        or zone.index in positions
    )
    if not index_known:
        bag.unknown(
            f"unknown index role '{zone.index}'",
            zone.index or "",
            (*role_names(_KNOWN_ROLES), *positions),
            zone.span,
            code=Code.UNKNOWN_INDEX_DOMAIN,
        )

    ref = zone.type_ref
    takes_owner = LIBRARY_ZONE_TYPES.get(ref.name)
    if takes_owner is None:
        if ref.name == COLLECTION_TYPE_CONSTRUCTOR:
            # A word the language HAS a meaning for, so "unknown" would spend
            # that currency on a spelling the checker itself prints. The two
            # angle brackets are the confusion — a zone's takes an index
            # domain, a collection's takes an element (decisions.md "Typed
            # object model") — so the refusal says which bracket this is.
            bag.error(
                f"`{COLLECTION_TYPE_CONSTRUCTOR}` is a value type a "
                f"`primitives {{ }}` entry declares, not a zone type — a "
                f"zone's angle brackets take an index domain: write a zone "
                f"type such as `Hand<player>`",
                ref.span,
                code=Code.TYPE_NOT_ALLOWED_HERE,
            )
        else:
            bag.unknown(f"unknown zone type '{ref.name}'", ref.name, LIBRARY_ZONE_TYPES, ref.span, code=Code.UNKNOWN_ZONE_TYPE)
        return
    if takes_owner and len(ref.args) != 1:
        bag.error(
            f"zone type '{ref.name}' takes one owner argument, got {len(ref.args)}",
            ref.span,
            code=Code.WRONG_ARGUMENT_COUNT,
        )
    if not takes_owner and ref.args:
        bag.error(f"zone type '{ref.name}' takes no type arguments", ref.span, code=Code.WRONG_ARGUMENT_COUNT)
    for arg in ref.args:
        if role_of(arg.name) not in _KNOWN_ROLES and arg.name not in positions:
            bag.unknown(
                f"unknown owner '{arg.name}'",
                arg.name,
                (*role_names(_KNOWN_ROLES), *positions),
                arg.span,
                code=Code.UNKNOWN_INDEX_DOMAIN,
            )
        elif takes_owner and zone.index is None:
            # An owned zone type has no index to key its owner by. The runtime
            # keys a family solely by its index (ZoneStore / zone_observer_key
            # read ZoneDecl.index; the owner argument's domain is never
            # consulted), so an owner with no index is unkeyed — the argument
            # is accepted and then ignored, the worst class. An owned zone
            # must be indexed by its owner.
            bag.error(
                f"zone '{zone.name}' is typed '{ref.name}<{arg.name}>' but has "
                f"no index — an owned zone type must be indexed by its owner; "
                f"write '{zone.name}[{arg.name}] : {ref.name}<{arg.name}>'",
                zone.span,
                code=Code.WRONG_SUBSCRIPT,
            )
        elif takes_owner and arg.name != zone.index:
            # Same silent-ignore: the runtime keys the family by the index, so
            # an owner argument that names a different domain than the index is
            # accepted and then ignored (`{ref.name}<{arg.name}>` on a
            # `[{zone.index}]` family still keys by `{zone.index}`). Require the
            # argument to name the index's domain.
            bag.error(
                f"zone '{zone.name}' is indexed by '{zone.index}' but typed "
                f"'{ref.name}<{arg.name}>' — the owner argument must name the "
                f"same domain as the index (the runtime keys the family by the "
                f"index, so '<{arg.name}>' would be silently ignored); write "
                f"'{ref.name}<{zone.index}>'",
                arg.span,
                code=Code.WRONG_SUBSCRIPT,
            )
    if zone.index in positions:
        # A position-indexed family has no owner (no observer IS a column —
        # decisions.md "Position domains and positional zones"), so a zone
        # type with distinct owner/others projections would leave its owner
        # projection silently unreachable: accepted-but-ignored at the
        # visibility level, the worst class.
        vis = ZONE_PROJECTIONS[ref.name]
        if vis.owner != vis.others:
            bag.error(
                f"zone '{zone.name}' is indexed by position '{zone.index}', "
                f"which no observer owns, but type '{ref.name}' declares "
                f"different owner/others projections ({vis.owner} vs "
                f"{vis.others}) — its owner projection would be unreachable; "
                f"use a uniform-projection type (Cascade, HiddenStack, "
                f"Foundation, Cell, …)",
                ref.span,
                code=Code.WRONG_ZONE_VISIBILITY,
            )
