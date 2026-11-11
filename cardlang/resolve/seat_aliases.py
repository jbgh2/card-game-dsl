"""Names that provably denote the acting seat.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  the binders and lets that alias the acting seat, read by
              the actor-alias comparison check and the hidden-read walk.
"""

from __future__ import annotations

from dataclasses import dataclass
from cardlang.ast import nodes as n
from cardlang.domains import SIMULTANEOUS_ROLES, binds_actor, role_of
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES


@dataclass(frozen=True)
class _ActorAliases:
    """The names that provably denote the acting player at a point in the tree.

    `names` always holds the `actor` pronoun itself (it denotes the acting
    player by definition) plus every binder a construct bound to that same
    seat; `origin` describes the construct that did the binding, for the
    diagnostic. A rebind REPLACES the set rather than extending it: once
    `as q { … }` names a new acting player, the enclosing loop's binder no
    longer denotes them."""

    names: frozenset[str] = frozenset({"actor"})
    origin: str | None = None

    def shadowed(self, bound: tuple[str, ...]) -> _ActorAliases:
        """Drop names a nested construct rebinds to something else — an inner
        `for each suit p` makes `p` a suit, whatever the outer loop bound."""
        if not bound:
            return self
        return _ActorAliases(self.names - set(bound), self.origin)


def _rebound(name: str | None, origin: str) -> _ActorAliases:
    """The alias set inside a construct that binds the acting player: the
    pronoun, plus the construct's own name for them when it has one. With no
    name (`as <expression>`) there is nothing to describe, so no origin —
    only the pronoun denotes the new acting player."""
    if name is None:
        return _ActorAliases()
    return _ActorAliases(frozenset({"actor", name}), origin)


def _seat_rebinding(node: object) -> _ActorAliases | None:
    """The alias set inside the body of a construct that rebinds the acting
    player, or None when `node` rebinds nothing. The one statement of which
    constructs bind a seat, read by the alias sweep below and by the
    Hidden Read Owner Guard.

    Both role tests are membership-guarded before the registry lookup:
    `_resolve_phase_level` checks these roles against the same two sets, but
    it reports into the SAME bag rather than halting, so a caller still walks
    a tree holding a role no row defines (`for each column c`, a declared
    position domain). The registry answers such a role with a
    compiler-channel raise -- correct for a registry divergence, wrong here,
    where it would replace the located diagnostic the author needs with an
    assert and suppress every other diagnostic in the file. Not the Owner
    Guard: the role's legality is decided above.

    `as <expression>` keeps a name only when the expression IS one that
    already denotes a seat immutably -- a state variable can be reassigned in
    the body, so it is not provably the acting player there."""
    match node:
        case n.ForEach() if (
            (role := role_of(node.role)) is not None
            and role in _ITERATION_ROLES
            and binds_actor(role)
        ):
            return _rebound(node.binder, f"`for each {node.role} {node.binder}`")
        case n.EachSimultaneous() if role_of(node.role) in SIMULTANEOUS_ROLES:
            # Binds the role noun itself as the local (`runtime/execute`).
            return _rebound(node.role, f"`each {node.role} simultaneously`")
        case n.Turns():
            return _rebound(node.binder, f"`turns {node.binder}`")
        case n.AsBlock():
            named = isinstance(node.player, n.NameRef) and node.player.ref_kind in (
                "local",
                "pronoun",
            )
            bound = node.player.name if named and isinstance(node.player, n.NameRef) else None
            return _rebound(bound, f"`as {bound}`")
        case _:
            return None


def _aliases_after_let(stmt: n.LetStmt, aliases: _ActorAliases) -> _ActorAliases:
    """The alias set for the statements after `stmt`: `let me = actor` (or
    `let me = p`, where `p` already denotes the actor) makes `me` a further
    name for the same player.

    A `let` REBINDS its name, so the name is dropped and re-added only when
    the value denotes the acting player. Both halves matter, and their ORDER
    is the whole rule: the value is read against the set as it stands BEFORE
    the binding (so `let p = p` keeps the alias -- the right-hand `p` is the
    old one), and the name is dropped after (so `let p = <someone else>`
    inside `for each player p` frees `p`, and the honest `p is actor` after it
    is not refused)."""
    source = (
        stmt.value.name
        if stmt.index is None and isinstance(stmt.value, n.NameRef)
        else None
    )
    binds_the_actor = source is not None and source in aliases.names
    origin = aliases.origin or f"`let {stmt.name} = {source}`"
    aliases = aliases.shadowed((stmt.name,))
    if binds_the_actor:
        aliases = _ActorAliases(aliases.names | {stmt.name}, origin)
    return aliases
