"""The positions a definition's reach makes: what a name may not be there.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  for each positional Owner Guard that judges a name by what
              reaches it, the one producer the guard iterates and
              ``_name_positions`` records, and the one predicate the guard
              refuses by and the Near Miss filter reads: a Kernel Definition
              Contract's answer and the functions it reaches
              (``_answer_reaches``, ``_answer_read_refusal``), a function a
              rule's clauses reach (``_rule_function_reads``,
              ``_play_source_refused``), an Arrival Record call's pile
              (``_arrival_piles``, ``_arrival_pile_refusal``), and a Hosted
              Poll's body and what it reaches (``_hosted_units``,
              ``_hosted_read_refused``). Each producer reads the tree's shape
              and declarations alone, never a name's classification.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, fields
from typing import Literal, cast
from cardlang.ast import nodes as n
from cardlang import kernel_contracts as K
from cardlang.builtins.functions import ARRIVAL_RECORD_CALLS
from cardlang.diagnostics import Span
from cardlang.domains import Role, role_of
from cardlang.primitives_block import phase_local_state_names
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, identity_to_all
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.reserved import PLAY_SOURCE_NAME, _CALL_SITE_PRONOUNS
from cardlang.resolve.crossings import _definition_closure


@dataclass(frozen=True)
class _ReadLimits:
    """What a kernel answer or an Arrival Record pile may not name, in one
    game: the state a phase declares and the game does not, each zone of a
    library type that does not project identity to every observer, and each
    zone of a library type kept per player."""

    phase_local: frozenset[str]
    hidden: frozenset[str]
    per_player: frozenset[str]


def _read_limits(game: n.Game) -> _ReadLimits:
    library = [z for z in game.zones if z.type_ref.name in LIBRARY_ZONE_TYPES]
    return _ReadLimits(
        phase_local=phase_local_state_names(game),
        hidden=frozenset(z.name for z in library if not identity_to_all(z.type_ref.name)),
        per_player=frozenset(
            z.name for z in library if z.index is not None and role_of(z.index) is Role.PLAYER
        ),
    )


def _subscripted_ids(game: n.Game) -> frozenset[int]:
    """The bare names a subscript keys."""
    return frozenset(
        id(nd.obj) for nd in _walk(game) if isinstance(nd, n.Subscript) and isinstance(nd.obj, n.NameRef)
    )


# --------------------------------------------------------------------------
# A kernel answer's reach.
# --------------------------------------------------------------------------


def _answer_routes(
    answer: n.FunctionDef, fns: dict[str, n.FunctionDef]
) -> dict[str, list[tuple[Span | None, object]]]:
    """Each function an answer reaches, with the route it is first reached
    by: every function the route enters, from the answer's own call, with the
    call that enters it (`_library_entry`'s steps). Another answer is not
    entered: it is checked on its own, and the reference order owns the call."""
    routes: dict[str, list[tuple[Span | None, object]]] = {}
    frontier: list[tuple[object, list[tuple[Span | None, object]]]] = [(answer.body, [])]
    while frontier:
        container, steps = frontier.pop(0)
        for nd in _walk(container):
            if isinstance(nd, n.Call) and nd.func in fns and nd.func not in routes:
                route = steps + [(nd.span, fns[nd.func])]
                routes[nd.func] = route
                frontier.append((fns[nd.func].body, route))
    return routes


@dataclass(frozen=True)
class _AnswerReach:
    """One answer's reach: the functions it may reach (`pool`), the route to
    each (`routes`), and every node it is judged at, with the function the
    node is reached through, None for the answer's own body. A Trick Order
    answer's reach runs on through `card_points`, where the reference order
    still binds it, so a node reached through `card_points` is judged only as
    a call of an answer; the rest of `card_points`' reach is that answer's own."""

    answer: n.FunctionDef
    pool: dict[str, n.FunctionDef]
    routes: dict[str, list[tuple[Span | None, object]]]
    sites: tuple[tuple[object, str | None], ...]


def _answer_reaches(game: n.Game) -> Iterator[_AnswerReach]:
    """Every answer the game writes to a Kernel Definition Contract, with its
    reach: the one walk `_check_answer_hermeticity` refuses by and
    `_name_positions` records."""
    answers = list(K.answers(game))
    answer_names = {a.name for a in answers}
    fns = {f.name: f for f in game.functions if f.name not in answer_names}
    points = K.answer(game, "card_points")
    for answer in answers:
        pool = (
            {**fns, points.name: points}
            if points is not None and answer.name in K.TRICK_ORDER_CONTRACTS
            else fns
        )
        routes = _answer_routes(answer, pool)
        through_points = {
            name for name, steps in routes.items() if any(d is points for _at, d in steps)
        }
        sites: list[tuple[object, str | None]] = [(nd, None) for nd in _walk(answer.body)]
        for name in routes:
            sites.extend(
                (nd, name)
                for nd in _walk(pool[name].body)
                if name not in through_points
                or (isinstance(nd, n.Call) and nd.func in K.KERNEL_CONTRACT_NAMES)
            )
        yield _AnswerReach(answer, pool, routes, tuple(sites))


_AnswerRefusal = Literal["pronoun", "hidden zone", "bare family", "phase state"]


def _answer_read_refusal(
    name: str, kind: n.RefKind | None, through: bool, subscripted: bool, limits: _ReadLimits
) -> _AnswerRefusal | None:
    """Why an answer refuses a name of `kind` at a node it reaches, directly or
    `through` a designer function, or None. A call-site pronoun reached
    through a function is `_check_functions`' to refuse, at that function."""
    if kind == "pronoun":
        return None if through and name in _CALL_SITE_PRONOUNS else "pronoun"
    if kind == "zone" and name in limits.hidden:
        return "hidden zone"
    if kind == "zone" and name in limits.per_player and not subscripted:
        return "bare family"
    if kind == "state_var" and name in limits.phase_local:
        return "phase state"
    return None


# --------------------------------------------------------------------------
# A function a rule's clauses reach.
# --------------------------------------------------------------------------


def _rule_clauses(rule: n.RuleDef) -> tuple[n.Expr, ...]:
    """The expressions a rule's clauses hold, in clause order."""
    exprs = (
        rule.applies_when.pred if rule.applies_when else None,
        rule.demands.expr if rule.demands else None,
        rule.if_impossible,
        rule.exempts,
    )
    return tuple(e for e in exprs if e is not None)


def _play_source_names(game: n.Game) -> frozenset[str]:
    """The names a function a rule reaches may not read bare: `hand`, and every
    trick round's source family."""
    sources = {nd.source_zone for nd in _walk(game) if isinstance(nd, n.TrickRound)}
    return frozenset({PLAY_SOURCE_NAME}) | frozenset(sources)


Reached = dict[tuple[str, str], tuple[object, tuple[str, str] | None]]


def _rule_function_reads(
    game: n.Game,
) -> Iterator[tuple[n.RuleDef, str, n.FunctionDef, Reached, tuple[n.NameRef, ...]]]:
    """Each rule, each function its clauses reach (in name order), the closure
    that reached it, and the bare names the function's body holds: the one
    walk `_check_play_source` refuses by and `_name_positions` records."""
    functions: dict[str, object] = {f.name: f for f in game.functions}
    for rule in game.rules:
        reached = _definition_closure(list(_rule_clauses(rule)), {"function": functions})
        for (_ns, fname), (fn, _via) in sorted(reached.items(), key=lambda kv: kv[0]):
            assert isinstance(fn, n.FunctionDef)
            names = tuple(nd for nd in _walk(fn.body) if isinstance(nd, n.NameRef))
            yield rule, fname, fn, reached, names


def _play_source_refused(
    name: str, kind: n.RefKind | None, named: frozenset[str], subscripted: bool
) -> bool:
    """Whether a function a rule reaches reads `name` of `kind` as the Play
    Source or a trick round's source family, bare: the cards a function
    cannot see."""
    return name in named and kind in ("zone", None) and not subscripted


# --------------------------------------------------------------------------
# An Arrival Record call's pile.
# --------------------------------------------------------------------------


def _arrival_piles(game: n.Game) -> Iterator[tuple[n.Call, object, n.NameRef | None]]:
    """Every Arrival Record call, its pile argument, and the bare name the
    argument is or keys, or None: the one walk
    `_check_arrival_record_pile_args` refuses by and `_name_positions`
    records."""
    for nd in _walk(game):
        if not isinstance(nd, n.Call) or nd.func not in ARRIVAL_RECORD_CALLS:
            continue
        idx = ARRIVAL_RECORD_CALLS[nd.func]
        arg = nd.args[idx] if len(nd.args) > idx else None
        ref: n.NameRef | None = None
        if isinstance(arg, n.NameRef):
            ref = arg
        elif isinstance(arg, n.Subscript) and isinstance(arg.obj, n.NameRef):
            ref = arg.obj
        yield nd, arg, ref


_PileRefusal = Literal["not a zone", "hidden zone"]


def _arrival_pile_refusal(name: str, kind: n.RefKind | None, limits: _ReadLimits) -> _PileRefusal | None:
    """Why an Arrival Record pile named `name` of `kind` is refused, or None:
    it names no zone, or a zone not every observer sees the arrivals of."""
    if kind != "zone":
        return "not a zone"
    if name in limits.hidden:
        return "hidden zone"
    return None


# --------------------------------------------------------------------------
# A Hosted Poll's reach.
# --------------------------------------------------------------------------


# What a Hosted Poll's body can EXECUTE, beyond its own text: the definitions
# it names whose bodies then run, by the reference namespace that names them
# (namespace -> the `n.Game` field holding them). A procedure it runs, a move
# type it offers — by `offer`, guard and effect alike —
# and a function it calls, each followed transitively. Pinned against every
# naming slot on a statement or expression node by tests/test_hosted_poll.py,
# with `HOSTED_REACH_INERT_SLOTS` beside it.
HOSTED_REACH_POOLS: dict[str, str] = {
    "procedure": "procedures",
    "move_type": "move_types",
    "function": "functions",
}


#: One unit a Hosted Poll's closure is judged over: its text, the key of the
#: definition holding it (None for the poll's own body), the field it is, and
#: the node holding it.
HostedUnit = tuple[object, tuple[str, str] | None, str | None, object]


def _hosted_units(game: n.Game) -> Iterator[tuple[n.HostedPoll, Reached, tuple[HostedUnit, ...]]]:
    """Every Hosted Poll, the definitions its body reaches by name
    (`HOSTED_REACH_POOLS`), and the units its closure is judged over: the
    one walk `_check_hosted_polls` refuses by and `_name_positions` records."""
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)} for ns, field in HOSTED_REACH_POOLS.items()
    }
    for poll in (nd for nd in _walk(game) if isinstance(nd, n.HostedPoll)):
        reached = _definition_closure([poll], pools)
        units: list[HostedUnit] = [(poll.body, None, None, poll)]
        for key, (target, _via) in reached.items():
            for f in fields(cast(n.Node, target)):
                units.append((getattr(target, f.name), key, f.name, target))
        yield poll, reached, tuple(units)


def _hosted_unit_nodes(unit: HostedUnit) -> Iterator[object]:
    """The nodes a unit of a Hosted Poll's closure is judged at."""
    return _child_nodes(unit[0])


def _hosted_read_refused(name: str, kind: n.RefKind | None) -> bool:
    """Whether a Hosted Poll's closure refuses a name of `kind`: the `state`
    pronoun, the round's live and unpublished frame."""
    return name == "state" and kind == "pronoun"
