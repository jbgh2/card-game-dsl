"""Where a state read or a pronoun is in scope.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  the scope predicates the classifier and the scope checks
              both read, so the two cannot disagree.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import field
from cardlang.ast import nodes as n
from cardlang import kernel_contracts as K
from cardlang.domains import Role, role_of
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.reserved import _CALL_SITE_PRONOUNS


def _default_reads(game: n.Game) -> Iterator[tuple[n.StateDecl, object, frozenset[str]]]:
    """Every node of every `state { }` default, with its declaration and the
    state a default may read there: the names declared earlier in the same
    block and every name of an enclosing block. The one walk
    `_check_state_default_scope` refuses by and `_scope_facts` records."""

    def declared(
        block: n.StateBlock | None, enclosing: frozenset[str]
    ) -> Iterator[tuple[n.StateDecl, object, frozenset[str]]]:
        if block is None:
            return
        in_scope = enclosing
        for decl in block.decls:
            for node in _walk(decl.default):
                yield decl, node, in_scope
            in_scope = in_scope | {decl.name}

    def descend(
        phase: n.Phase, enclosing: frozenset[str]
    ) -> Iterator[tuple[n.StateDecl, object, frozenset[str]]]:
        block = next((i for i in phase.items if isinstance(i, n.StateBlock)), None)
        yield from declared(block, enclosing)
        inner = enclosing | _phase_state_names(phase)
        for item in phase.items:
            if isinstance(item, n.Phase):
                yield from descend(item, inner)

    yield from declared(game.state, frozenset())
    top = _game_state_names(game)
    for phase in game.phases:
        yield from descend(phase, top)


#: The pronoun a `state { }` default may not read: it is evaluated outside any
#: player's turn.
_DEFAULT_REFUSED_PRONOUNS = frozenset({"actor"})


def _pronoun_refused(name: str, kind: n.RefKind | None, refused: frozenset[str]) -> bool:
    """Whether a name of `kind` is a pronoun its position refuses."""
    return kind == "pronoun" and name in refused


def _bare_seat_family_in_default(
    zone_index: Mapping[str, str | None], name: str, kind: n.RefKind | None, keyed: bool
) -> bool:
    """Whether a name is a zone kept per player, named bare in a default."""
    index = zone_index.get(name)
    return kind == "zone" and not keyed and index is not None and role_of(index) is Role.PLAYER


def _keyed_ids(game: n.Game) -> frozenset[int]:
    """The bare zone names a subscript keys, or a `to each` movement names
    whole: neither names one zone of a family by the acting seat."""
    return frozenset(
        id(nd.obj) for nd in _walk(game) if isinstance(nd, n.Subscript)
    ) | frozenset(id(nd.dest) for nd in _walk(game) if isinstance(nd, n.Transfer) and nd.dest_each)


# `Game` fields `_check_state_scope` does not walk at game level, split by WHY —
# the two reasons are not interchangeable, and collapsing them once already hid
# a defect: `types` sat under the residual comment while the set's name claimed
# a guard owned it, and nothing did.
#
# Pinned against the node's real field set by tests/test_state_scope.py, so a
# new field forces a decision instead of silently joining whichever side it
# happens to fall on.

# Another guard owns these, and does check them.
_GAME_LEVEL_OWNED_BY_ANOTHER_GUARD = frozenset(
    {
        # each phase carries its own scope; `descend` walks these
        "phases",
        # a default is bounded by what exists YET, a different rule:
        # `_check_state_default_scope` owns it
        "state",
    }
)

# NOBODY checks these. A callable body has no enclosing phase, so whether its
# state reads are live depends on which phase invokes it — reachability, not
# lexical scope. 112 callable bodies across 15 corpus games legitimately read
# phase-scoped state, so no conservative rule is available and this is a
# recorded residual, not a guarantee (issue #242).
#
# `_reachable_definitions` answers WHICH of these bodies run, which is the
# half of #242 a conservative rule would need — but not #242 itself, which
# asks which phase's state a body that runs may read. The gap stands.
_GAME_LEVEL_UNCHECKED = frozenset(
    {"rules", "move_types", "functions", "procedures"}
)

_GAME_LEVEL_SKIP = _GAME_LEVEL_OWNED_BY_ANOTHER_GUARD | _GAME_LEVEL_UNCHECKED


def _phase_state_names(phase: n.Phase) -> frozenset[str]:
    """The state names `phase` declares."""
    block = next((i for i in phase.items if isinstance(i, n.StateBlock)), None)
    return frozenset(d.name for d in block.decls) if block else frozenset()


def _game_state_names(game: n.Game) -> frozenset[str]:
    """The state names the game declares at game level."""
    return frozenset(d.name for d in game.state.decls) if game.state else frozenset()


def _phase_scoped_names(game: n.Game) -> Iterator[tuple[n.NameRef, frozenset[str]]]:
    """Every bare name the state-scope rule judges, with the state live where
    it stands (`_phase_scoped_nodes`, its names). The one walk
    `_check_state_scope` refuses by."""
    for node, in_scope in _phase_scoped_nodes(game):
        if isinstance(node, n.NameRef):
            yield node, in_scope


def _phase_scoped_nodes(game: n.Game) -> Iterator[tuple[object, frozenset[str]]]:
    """Every node the state-scope rule judges a name at, with the state live
    there: a phase and its body (its qualifier and outcome cases included)
    against the game's state and every enclosing phase's, and a game-level
    clause against the game's alone. A `state { }` default is
    `_default_reads`', and a callable body is outside the rule (issue #242).
    The one walk `_phase_scoped_names` and `_scope_facts` read."""

    def descend(phase: n.Phase, enclosing: frozenset[str]) -> Iterator[tuple[object, frozenset[str]]]:
        inner = enclosing | _phase_state_names(phase)
        yield phase, inner
        for item in phase.items:
            if isinstance(item, n.Phase):
                yield from descend(item, inner)
            elif isinstance(item, n.StateBlock):
                continue  # `_check_state_default_scope` owns defaults
            else:
                for node in _walk(item):
                    yield node, inner
        # The qualifier and the outcome cases are part of THIS phase, so its
        # own state is live in them.
        for owned in (phase.qualifier, *phase.outcome_cases):
            for node in _walk(owned):
                yield node, inner

    top = _game_state_names(game)
    for phase in game.phases:
        yield from descend(phase, top)

    # Game-level clauses run outside every phase — every frame has been popped
    # by then — so they see game-level state only. DERIVED, not listed: walk the
    # `Game` node's own fields and skip the ones another guard owns, so a clause
    # added later is covered the day it exists rather than the day someone
    # remembers it.
    for field in game.__dataclass_fields__:
        if field in _GAME_LEVEL_SKIP:
            continue
        # `_child_nodes`, not `_walk`: most of these fields hold a TUPLE of
        # nodes, and `_walk` returns immediately on anything that is not a
        # dataclass. Walking them with `_walk` visits nothing at all and the
        # loop looks total while checking only the handful of single-node
        # fields.
        for node in _child_nodes(getattr(game, field, None)):
            yield node, top


def _state_out_of_scope(name: str, kind: n.RefKind | None, in_scope: frozenset[str] | None) -> bool:
    """Whether a name of `kind` is a state variable outside `in_scope`, the
    state live where it stands; None is a position no scope rule judges."""
    return kind == "state_var" and in_scope is not None and name not in in_scope


def _refused_call_site_pronouns(definition: n.FunctionDef | n.ProcedureDef) -> frozenset[str]:
    """The call-site pronouns `definition`'s body may not read: every one,
    since its body runs wherever it is called or run from, but for a game
    function answering a Kernel Definition Contract, whose pronouns are
    `_check_answer_hermeticity`'s."""
    if (
        isinstance(definition, n.FunctionDef)
        and definition.name in K.KERNEL_CONTRACT_NAMES
        and definition.origin is None
    ):
        return frozenset()
    return _CALL_SITE_PRONOUNS


def _bare_family_refused(
    zone_index: Mapping[str, str | None], name: str, kind: n.RefKind | None, keyed: bool
) -> bool:
    """Whether a name is a zone family not kept per player, named bare where
    the engine would key it by the acting seat."""
    index = zone_index.get(name)
    return kind == "zone" and not keyed and index is not None and role_of(index) is not Role.PLAYER
