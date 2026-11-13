"""Resolve step: name classification.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the instantiated tree, and the binder sources the rule
              instantiation step refused.
Establishes:  every ``NameRef`` of the game's tree carries its ``ref_kind``,
              stamped by ``classifier._rewrite``. A rule clause's bare
              ``hand`` (not a ``Subscript``'s object, not a binder the
              clause introduces) is ``ref_kind == "play_source"``: the
              trick round's Play Source, so no later pass learns it from
              the spelling ``hand``.
              Every Near Miss the bare-name and round `trump` refusals offer
              classifies where the refusal stands and is admitted there by
              every positional Owner Guard that refuses by the position record
              (``_name_positions``, read off the tree's shape alone, and
              ``_position_refuses``, the disjunction of the guards'
              predicates); a trick round's winner is offered the winners that
              round admits (``_winner_refusals``, the one producer the
              guards refusing a round's winner dispatch on). Held by Derived and Pinned
              (tests/test_near_miss_positions.py). Not established: the
              alias-comparison and hidden-read guards judge by walk state the
              record does not hold (issue #1089), and no Near Miss is judged by
              its Type (issue #1088), so one can be refused there still, or be
              a Pronoun the checker gives no Type (issue #1125).
              Asked for one (``resolve(scopes=...)``), the pass fills the
              Scope Record: at every node the classifying walk visits, keyed by
              ``n.node_key``, the names a bare name written there classifies
              as, by ``_classify`` under that node's categories, less those
              the scope rules refuse at the node (``_scope_facts``, recorded
              at every node from the walks the rules refuse by, and
              ``_scope_refuses``: the State Variable scope rules, the Pronouns
              a definition body may not read, a default's reads, what a
              kernel answer and the functions it reaches may read, what a
              function a rule's clauses reach may read bare, and a Hosted
              Poll's closure's refusal of ``state``) and, where the node is a
              name, those every positional Owner Guard joined to the position
              record refuses (``_position_refuses``) -- ``_record_scope``. The
              rule of who is acting is not applied there (issue #1089). It is
              the one source of "what is in scope here" outside this pass
              (``cardlang.query``), and recording it changes nothing the pass
              decides.
              The step returns the categories it classified against, for the
              references step.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from cardlang.ast import nodes as n
from cardlang.builtins.functions import BUILTIN_IMPLICIT_READS
from cardlang.diagnostics import DiagnosticBag
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.slots import _NAME_SLOTS, _slot_root
from cardlang.resolve.declared import _map_climb_rounds
from cardlang.resolve.scope import (
    _DEFAULT_REFUSED_PRONOUNS,
    _default_reads,
    _keyed_ids,
    _phase_scoped_nodes,
    _refused_call_site_pronouns,
    _state_declarations,
)
from cardlang.resolve.reaches import (
    _answer_reaches,
    _arrival_piles,
    _hosted_unit_nodes,
    _hosted_units,
    _play_source_names,
    _read_limits,
    _rule_function_reads,
    _subscripted_ids,
)
from cardlang.resolve.classifier import _Categories, _NamePosition, _ScopeFacts, _rewrite
from cardlang.resolve.classifier import NamesInScope, _categories


def step(
    game: n.Game,
    refused_binders: dict[int, frozenset[str]],
    bag: DiagnosticBag,
    *,
    scopes: dict[n.NodeKey, NamesInScope] | None = None,
) -> tuple[n.Game, _Categories]:
    """The classification step. Returns the classified game, and the
    categories it was classified against; `scopes`, when given, is filled
    with the Scope Record."""
    # Deep name resolution: classify every bare name and validate calls,
    # card literals, and the rotate/winner targets.
    cats = replace(_categories(game), refused_binders=refused_binders, scopes=scopes)
    game = _classify_names(game, cats, bag)
    game = _stamp_follows_reads(game)
    return game, cats


def _stamp_follows_reads(game: n.Game) -> n.Game:
    """Stamp each Declared Engine with what its follows function reads beyond
    its two plays, through every function it calls: the state variables and
    zones, by their classified names, which key the function's cached answers
    at runtime. A zone a Builtin reads without the call naming it
    (`BUILTIN_IMPLICIT_READS`) joins the zones; a pronoun, a round's published
    state (`state.x`) or a declared Primitive's `reads` is a read no key holds,
    so the function is not cached."""
    functions = {f.name: f for f in game.functions}
    primitives = {d.name for d in game.primitives.decls} if game.primitives else set()

    def stamp(nd: n.ClimbRound) -> n.ClimbRound:
        engine = nd.engine
        if not isinstance(engine, n.DeclaredEngine) or engine.follows not in functions:
            return nd
        state: set[str] = set()
        zones: set[str] = set()
        cacheable = True
        seen: set[str] = set()
        frontier = [functions[engine.follows]]
        while frontier:
            fn = frontier.pop()
            if fn.name in seen:
                continue
            seen.add(fn.name)
            for node in _walk(fn.body):
                if isinstance(node, n.NameRef):
                    if node.ref_kind == "state_var":
                        state.add(node.name)
                    elif node.ref_kind == "zone":
                        zones.add(node.name)
                    elif node.ref_kind == "pronoun":
                        cacheable = False
                elif isinstance(node, n.Call):
                    if node.func in functions:
                        frontier.append(functions[node.func])
                    elif node.func in BUILTIN_IMPLICIT_READS:
                        zones.add(BUILTIN_IMPLICIT_READS[node.func][0])
                    elif node.func in primitives:
                        cacheable = False
        return replace(
            nd,
            engine=replace(
                engine,
                state_reads=tuple(sorted(state)),
                zone_reads=tuple(sorted(zones)),
                cacheable=cacheable,
            ),
        )

    stamped = _map_climb_rounds(game, stamp)
    assert isinstance(stamped, n.Game)
    return stamped


def _scope_facts(game: n.Game) -> dict[int, _ScopeFacts]:
    """Every node of `game` with what a name written there may read, whatever
    slot it fills. Read off the tree's shape and declarations alone, never
    its classification. Each fact is recorded at every node of the walk its
    rule refuses by: a kernel answer's reach (`_answer_reaches`), every node
    of a function a rule's clauses reach (`_rule_function_reads`), and a
    Hosted Poll's closure (`_hosted_units`)."""
    live: dict[int, frozenset[str]] = {}
    for node, in_scope in _phase_scoped_nodes(game):
        live[id(node)] = in_scope
    in_default: set[int] = set()
    for block, decl, in_scope in _state_declarations(game):
        held = block if decl is None else decl
        live[id(held)] = in_scope
        in_default.add(id(held))
    for _decl, node, in_scope in _default_reads(game):
        live[id(node)] = in_scope
        in_default.add(id(node))
    pronouns: dict[int, frozenset[str]] = {}
    definitions: tuple[n.FunctionDef | n.ProcedureDef, ...] = (*game.functions, *game.procedures)
    for definition in definitions:
        refused = _refused_call_site_pronouns(definition)
        for node in _child_nodes(definition.body):
            pronouns[id(node)] = refused
    answer_through: dict[int, set[bool]] = {}
    for reach in _answer_reaches(game):
        for node, fn in reach.sites:
            answer_through.setdefault(id(node), set()).add(fn is not None)
    play_source: dict[int, frozenset[str]] = {}
    named = _play_source_names(game)
    for _rule, _fname, _fn, _reached, nodes in _rule_function_reads(game):
        for node in nodes:
            play_source[id(node)] = named
    hosted = {
        id(node)
        for _poll, _reached, units in _hosted_units(game)
        for unit in units
        for node in _hosted_unit_nodes(unit)
    }
    limits = _read_limits(game)
    return {
        id(node): _ScopeFacts(
            live_state=live.get(id(node)),
            refused_pronouns=(
                _DEFAULT_REFUSED_PRONOUNS if id(node) in in_default else pronouns.get(id(node), frozenset())
            ),
            in_default=id(node) in in_default,
            answer_through=frozenset(answer_through.get(id(node), ())),
            play_source_names=play_source.get(id(node), frozenset()),
            hosted=id(node) in hosted,
            limits=limits,
        )
        for node in _walk(game)
    }


def _name_positions(game: n.Game, facts: Mapping[int, _ScopeFacts] | None = None) -> dict[int, _NamePosition]:
    """Every bare name of `game`, by its node, with what may denote it where
    it stands: what any name there may read (`facts`, `_scope_facts` of the
    game where not given) and the slot the name fills. Read off the tree's
    shape and declarations alone, never its classification, so the record
    over a tree before classification is the record over it after."""
    scope = _scope_facts(game) if facts is None else facts
    slots: dict[int, frozenset[n.RefKind]] = {}
    each: set[int] = set()
    for node in _walk(game):
        for (kind, slot), takes in _NAME_SLOTS.items():
            if isinstance(node, kind) and (root := _slot_root(getattr(node, slot))) is not None:
                slots[id(root)] = takes
        if isinstance(node, n.Transfer) and node.dest_each and isinstance(node.dest, n.NameRef):
            each.add(id(node.dest))
    keyed = _keyed_ids(game)
    piles = {id(ref) for _call, _arg, ref in _arrival_piles(game) if ref is not None}
    subscripted = _subscripted_ids(game)
    return {
        id(ref): _NamePosition(
            scope=scope[id(ref)],
            slot=slots.get(id(ref)),
            each_destination=id(ref) in each,
            keyed=id(ref) in keyed,
            arrival_pile=id(ref) in piles,
            subscripted=id(ref) in subscripted,
        )
        for ref in _walk(game)
        if isinstance(ref, n.NameRef)
    }


def _classify_names(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> n.Game:
    """Immutably rewrite every NameRef with its classification, recording an
    error for any name that resolves to nothing."""
    facts = _scope_facts(game)
    result = _rewrite(
        game, replace(cats, positions=_name_positions(game, facts), scope_facts=facts), bag
    )
    assert isinstance(result, n.Game)
    return result
