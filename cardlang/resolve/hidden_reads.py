"""Resolve step: hidden reads at deciding positions."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, fields, is_dataclass, replace
from typing import assert_never
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    ARRIVAL_RECORD_CALLS,
    BUILTIN_ARGUMENT_READS,
    BUILTIN_IMPLICIT_READS,
)
from cardlang.primitives_block import ReadKind, classify_read
from cardlang.attribution import cite_library, cite_all, cite_named, cite_origin, cite_where
from cardlang.diagnostics import DiagnosticBag, Route, Said, Sentence, Span, rendered
from cardlang.domains import ZONE_INDEX_ROLES, Role, role_of
from cardlang.runtime.delegation import CHOOSER_HELPER, SOURCE_HELPER
from cardlang.stdlib.zones import ZONE_PROJECTIONS, reveals
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.binders import _BINDER_SCOPE_FIELDS, _introduced_binders
from cardlang.resolve.declared import _written_state_name
from cardlang.resolve.crossings import _LibraryEntry, _cite_in, _entry_route
from cardlang.resolve.seat_aliases import _ActorAliases, _aliases_after_let, _seat_rebinding


def _library_functions(game: n.Game) -> dict[str, str]:
    """Each spliced library function, by name, to the library it came from,
    read off its `n.LibraryOrigin`."""
    return {f.name: f.origin.library for f in game.functions if f.origin is not None}


# The seat a caller of `_HiddenReads._meeting_callers` runs a procedure as,
# where any one player meets it: a name no game binds, read as the acting seat.
_ANY_PLAYER = "<player>"


# The fix a library procedure's run is told where some caller meets the
# procedure but no run of it as one seat passes with the run's own arguments.
_NO_RUN_FIX = (
    "run it as a seat that can see the cards it reads, and pass it only "
    "arguments that seat can see"
)


@dataclass(frozen=True)
class _RunRoutes:
    """The crossings the game's `run` of a library procedure reports: a read
    the game's own argument makes (`argument`), and a refusal of the seat
    deciding (`body`), None when no caller meets the procedure, which makes
    it the library's own."""

    body: Route | None
    argument: Route


def _made_up_run(proc: n.ProcedureDef, stmt: n.RunStmt, seat: n.Expr) -> n.RunStmt:
    """`stmt` passing `seat` to every Player parameter of `proc`, and to each
    other parameter a name bound to nothing, which reads no cards: what the
    game's own arguments read is the game's, never the procedure's."""
    args = tuple(
        seat if param.type_name == "Player" else n.NameRef(f"<{param.name}>", stmt.span, "local")
        for param in proc.params
    )
    return replace(stmt, args=args)


def _meeting_fix(proc: n.ProcedureDef, stmt: n.RunStmt, seat: n.NameRef, spelled: str) -> Said:
    """A run of `_meeting_callers`, as the game's author writes it: the
    seat to every Player parameter, the run's own argument to each other
    one, named by its parameter (`<k>`) where `_spell` cannot quote it."""
    spelled_args = [
        spelled if param.type_name == "Player"
        else f"<{param.name}>" if "..." in (text := _spell(arg))
        else text
        for param, arg in zip(proc.params, stmt.args)
    ]
    call = cite_named(proc, stmt.name) + f"({', '.join(spelled_args)})"
    passed = [f"`{p.name}`" for p in proc.params if p.type_name == "Player"]
    if seat.name == _ANY_PLAYER:
        lead = "run it as one player"
        given = "that player"
    else:
        lead = f"run it as `{spelled}`"
        given = f"`{spelled}`"
    if passed:
        lead += f" and pass {given} as {', '.join(passed)}"
    return f"{lead}: `as {spelled} {{ run " + call + " }`"


# --- The Hidden Read Owner Guard -----------------------------------------------
#
# decisions.md "Honest Play is assumed, so a rule reading concealed cards is
# mis-modelled".
#
# Where each expression-bearing AST field's value goes, which decides whose
# sight a zone read there is judged against. The rows are every field of every
# `nodes.py` dataclass whose declared type admits an `Expr`, except the fields
# of the expression nodes themselves, which belong to the position their
# expression sits in -- `Choose` excepted, since a `choose` is a decision
# wherever it is nested. Pinned against that derivation by
# tests/test_hidden_reads.py::test_every_expression_position_is_bucketed.
READ_POSITION_NO_SEAT = "no seat deciding"
READ_POSITION_SEAT = "a seat deciding"
READ_POSITION_CHOSEN = "a seat deciding when the movement is chosen"
READ_POSITION_FOLLOWED = "judged where its value flows"
READ_POSITION_OUTSIDE = "not judged"
READ_POSITION_KINDS: frozenset[str] = frozenset(
    {
        READ_POSITION_NO_SEAT,
        READ_POSITION_SEAT,
        READ_POSITION_CHOSEN,
        READ_POSITION_FOLLOWED,
        READ_POSITION_OUTSIDE,
    }
)

_CONTROL = "a control position: it decides who is asked, not what they may do (issue #755)"

HIDDEN_READ_POSITIONS: dict[tuple[type, str], tuple[str, str]] = {
    (n.PhaseQualifier, "expr"): (READ_POSITION_NO_SEAT, "evaluated between seats"),
    (n.MoveEvent, "where"): (READ_POSITION_NO_SEAT, "changes the rules for every later seat"),
    (n.MoveTypeDef, "when"): (READ_POSITION_SEAT, "decides what the offered seat may do"),
    (n.AppliesWhen, "pred"): (READ_POSITION_SEAT, "decides what the acting seat may play"),
    (n.Demands, "expr"): (READ_POSITION_SEAT, "decides what the acting seat may play"),
    (n.RuleDef, "if_impossible"): (READ_POSITION_SEAT, "decides what the acting seat may play"),
    (n.RuleDef, "exempts"): (READ_POSITION_SEAT, "decides what the acting seat may play"),
    (n.Choose, "lo"): (READ_POSITION_SEAT, "the range the choosing seat is offered"),
    (n.Choose, "hi"): (READ_POSITION_SEAT, "the range the choosing seat is offered"),
    (n.Choose, "excluding"): (READ_POSITION_SEAT, "the range the choosing seat is offered"),
    (n.Transfer, "amount"): (READ_POSITION_CHOSEN, "how many the choosing seat is asked for"),
    (n.Transfer, "source"): (READ_POSITION_CHOSEN, "the pool the choosing seat picks from"),
    (n.Transfer, "where"): (READ_POSITION_CHOSEN, "narrows the pool the choosing seat picks from"),
    (n.Transfer, "dest"): (READ_POSITION_CHOSEN, "the destination the choosing seat is told"),
    (n.Transfer, "visibility"): (
        READ_POSITION_OUTSIDE,
        "refused by typecheck: visibility derives from the declared zone types",
    ),
    (n.LetStmt, "value"): (READ_POSITION_FOLLOWED, "a name for a computation, read where it is used"),
    (n.FunctionDef, "body"): (READ_POSITION_FOLLOWED, "read at each call, in its caller's position"),
    (n.RuleRef, "args"): (READ_POSITION_FOLLOWED, "substituted into the instantiated rule's clauses"),
    (n.RunStmt, "args"): (READ_POSITION_FOLLOWED, "bound to the procedure's parameters at the run site"),
    (n.Produce, "payloads"): (
        READ_POSITION_FOLLOWED,
        "bound to the consuming `produces:` arm's binders",
    ),
    (n.AssignStmt, "value"): (
        READ_POSITION_OUTSIDE,
        "state is public: every seat is shown it at each decision node, and "
        "its log keeps each node's State Delta (issue #471 holds a Primitive's "
        "result stored this way)",
    ),
    (n.AssignStmt, "index"): (READ_POSITION_OUTSIDE, "state is public: an assignment's key is announced"),
    (n.AssignStmt, "target"): (READ_POSITION_OUTSIDE, "names the state variable written"),
    (n.RotateStmt, "target"): (READ_POSITION_OUTSIDE, "names the state variable written"),
    (n.StateDecl, "default"): (READ_POSITION_OUTSIDE, "evaluated before any zone holds a card"),
    (n.EpistemicOp, "zone"): (READ_POSITION_OUTSIDE, "a reveal shows every seat; a shuffle decides nothing"),
    (n.EpistemicOp, "where"): (READ_POSITION_OUTSIDE, "a reveal shows every seat the card it picks"),
    (n.Loser, "selection"): (READ_POSITION_OUTSIDE, "the game's result, read once play is over"),
    (n.IfStmt, "cond"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.RepeatUntil, "until"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.AsBlock, "player"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.Offer, "player"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.Turns, "leader"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.Turns, "participants"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.Turns, "until"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.TrickRound, "leader"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.TrickRound, "participants"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.TrickRound, "trump"): (
        READ_POSITION_OUTSIDE,
        "configures the round for every seat before any decides (issue #755)",
    ),
    (n.ClimbRound, "leader"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.ClimbRound, "participants"): (READ_POSITION_OUTSIDE, _CONTROL),
    (n.ClimbRound, "until"): (READ_POSITION_OUTSIDE, _CONTROL),
}


# Where the cards each decision point offers come from: every chooser call
# site in `runtime/delegation.DECISION_POINTS`, the round site fanned out over
# its forms (`FORM_CONSTRUCTS`). A pool a designer expression names is judged
# by `_check_hidden_reads`; a pool the kernel builds from a declared zone, with
# no expression to read, by `_check_implicit_pools`. Pinned against those two
# registries by tests/test_hidden_reads.py::test_every_decision_point_names_its_pool.
POOL_FROM_EXPRESSION = "a designer expression"
POOL_FROM_ROUND_SOURCE = "the round's declared source family"
POOL_FROM_CARD_PARAMETERS = "the acting seat's `hand`, for a `Card` parameter"
POOL_NONE = "no cards"
POOL_KINDS: frozenset[str] = frozenset(
    {POOL_FROM_EXPRESSION, POOL_FROM_ROUND_SOURCE, POOL_FROM_CARD_PARAMETERS, POOL_NONE}
)
DECISION_POOLS: dict[str, str] = {
    "TrickRound": POOL_FROM_ROUND_SOURCE,
    "ClimbRound": POOL_FROM_ROUND_SOURCE,
    "execute._select_from": POOL_FROM_EXPRESSION,
    "execute._select_filtered": POOL_FROM_EXPRESSION,
    "execute._select_joint": POOL_FROM_EXPRESSION,
    "execute._pass_selection": POOL_FROM_EXPRESSION,
    "execute._offer": POOL_FROM_CARD_PARAMETERS,
    "evaluate._choose": POOL_NONE,
}


# A chosen movement's sub-positions: (field, whether it moves `to each`) ->
# (the seat whose decision its value reaches, the seat that evaluates it and
# so makes any `choose` nested in it). Each is the runtime's own reading of
# `execute._movement` and `_select_from`, pinned against a run that records
# the acting seat at every evaluation and the decider at every pick by
# tests/test_hidden_reads.py::test_a_chosen_movements_seats_are_the_runtimes.
SEAT_ACTING = "the acting seat"
SEAT_EACH_RECEIVER = "each receiving seat"
CHOSEN_MOVEMENT_SEATS: dict[tuple[str, bool], tuple[str, str]] = {
    ("amount", False): (SEAT_ACTING, SEAT_ACTING),
    ("source", False): (SEAT_ACTING, SEAT_ACTING),
    ("where", False): (SEAT_ACTING, SEAT_ACTING),
    ("dest", False): (SEAT_ACTING, SEAT_ACTING),
    ("amount", True): (SEAT_EACH_RECEIVER, SEAT_ACTING),
    ("source", True): (SEAT_EACH_RECEIVER, SEAT_ACTING),
    ("where", True): (SEAT_EACH_RECEIVER, SEAT_ACTING),
    ("dest", True): (SEAT_EACH_RECEIVER, SEAT_ACTING),
}


# A rule clause, asked at the trick round's card decision: clause -> (the seat
# whose decision its value reaches, the seat that evaluates it and so makes
# any `choose` nested in it). `rules.legal_cards` evaluates every clause
# acting as the attributed seat, and the trick decision is the decider's --
# `chooser_for(actor)` under Delegated Play. Pinned against a run by
# tests/test_hidden_reads.py::test_a_rule_clauses_seats_are_the_runtimes.
SEAT_TRICK_DECIDER = "the seat deciding the trick play"
RULE_CLAUSE_SEATS: dict[str, tuple[str, str]] = {
    "applies_when": (SEAT_TRICK_DECIDER, SEAT_ACTING),
    "demands": (SEAT_TRICK_DECIDER, SEAT_ACTING),
    "if_impossible": (SEAT_TRICK_DECIDER, SEAT_ACTING),
    "exempts": (SEAT_TRICK_DECIDER, SEAT_ACTING),
}


@dataclass(frozen=True)
class _Binding:
    """What a local name stands for, as the reader follows it: the expression
    and the scope it is read in. A parameter's value substitutes into an
    index; a `let` with an index binder takes the subscript as that binder."""

    value: n.Expr
    scope: _ReadScope
    via: Said
    index_binder: str | None = None


@dataclass(frozen=True)
class _ReadScope:
    """What the reader knows at a point in the tree: the locals it can follow,
    the names that denote the acting seat (`_ActorAliases`), whether a seat
    acts at all, and the State Variable an enclosing `as` names -- live while
    no path from that `as` has written it, or the seat number a literal `as`
    names. `seat` identifies the acting seat those proofs are about: a value
    bound under one seat and read under another carries none of them."""

    names: tuple[tuple[str, tuple[_Binding, ...]], ...] = ()
    aliases: _ActorAliases = _ActorAliases(frozenset())
    acting: bool = False
    seat_var: str | None = None
    seat_var_live: bool = False
    seat_literal: int | None = None
    seat: int = 0
    # Under Delegated Play, the families bare-family sugar routes to the pool
    # the decider plays from; None where the acting seat decides.
    routed: frozenset[str] | None = None
    # The families bare-family sugar routes to a pool `play_source_for`
    # chooses, read by a seat other than the decider: not provably its own.
    rerouted: frozenset[str] = frozenset()

    def follow(self, binding: _Binding) -> _ReadScope:
        """The scope `binding`'s value is read in, from here: its own, or,
        when it was bound under another acting seat, its own with every proof
        of who acts removed -- what that seat could see proves nothing for
        this one."""
        if binding.scope.seat == self.seat:
            return binding.scope
        return replace(
            binding.scope,
            aliases=_ActorAliases(frozenset()),
            acting=False,
            seat_var=None,
            seat_var_live=False,
            seat_literal=None,
            seat=_NO_ACTING_SEAT,
        )

    def lookup(self, name: str) -> tuple[_Binding, ...]:
        for bound, bindings in reversed(self.names):
            if bound == name:
                return bindings
        return ()

    def bind(self, name: str, bindings: tuple[_Binding, ...]) -> _ReadScope:
        return replace(self, names=self.names + ((name, bindings),))

    def shadow(self, names: tuple[str, ...]) -> _ReadScope:
        if not names:
            return self
        return replace(
            self,
            names=self.names + tuple((name, ()) for name in names),
            aliases=self.aliases.shadowed(names),
        )


@dataclass(frozen=True)
class _Crossing:
    """A library's call of a function its Definition Contract names, as a
    read reached through the game's answer crossed it: the row's stamp, the
    answering function, the call's arguments bound to its parameters and the
    scope they are read in, the route inside the answer, and the last node of
    the game's text on the way to the read."""

    stamp: n.ContractStamp
    function: n.FunctionDef
    args: tuple[n.Expr, ...]
    scope: _ReadScope
    inner_route: tuple[Said, ...]
    anchor: Span | None


@dataclass(frozen=True)
class _Answered:
    """A library's call of the game's answer to a Definition Contract, as the
    walk for decisions no seat can make crossed it: the row's stamp, the
    answer, how deep in the route it stands, and the game's call of a library
    function the walk left the game's text by."""

    stamp: n.ContractStamp
    function: str
    depth: int
    anchor: Span | None


@dataclass(frozen=True)
class ZoneRead:
    """One read of a zone an expression makes: the zone, its index as written
    (None for a bare family or an unindexed zone), whether every instance of
    a family is read, what the read needs, and the route it was reached by.
    `choose` names the `choose` field the read sits in, when it does. `exit`
    is the call of a library function a read in that function's body was
    reached by, `crossing` the contracted call a read in the game's answer to
    a library was reached by, and `bindings` the names followed by value on
    the way to it."""

    zone: str
    index: n.Expr | None
    index_scope: _ReadScope
    every: bool
    need: str
    route: tuple[Said, ...]
    span: Span | None
    choose: str | None = None
    exit: n.Call | None = None
    crossing: _Crossing | None = None
    bindings: tuple[_Binding, ...] = ()


@dataclass(frozen=True)
class HiddenReadVerdict:
    """`_check_hidden_reads`' judgement of one read at one position: accepted or not, and
    why -- `public`, or the reason the deciding seat owns what it reads. `site`
    locates the position's expression."""

    position: str
    read: ZoneRead
    accepted: bool
    reason: str
    site: Span | None = None


_NEED_PHRASE: dict[str, str] = {
    "existence": "whether {z} is empty",
    "count": "how many cards {z} holds",
    "identity": "the cards in {z}",
    "order": "the order of the cards in {z}",
}


def _needs(need: str, zone: Said) -> Said:
    """What a read needs of `zone`, in the designer's words."""
    before, _, after = _NEED_PHRASE[need].partition("{z}")
    return before + zone + after


def _spell(expr: object) -> str:
    """An expression as a diagnostic quotes it: the shapes an index takes."""
    match expr:
        case n.NameRef() as ref:
            return ref.name
        case n.IntLit() as lit:
            return str(lit.value)
        case n.Member() as m:
            return f"{_spell(m.obj)}.{m.field}"
        case n.Subscript() as s:
            return f"{_spell(s.obj)}[{_spell(s.index)}]"
        case n.Call() as c:
            return f"{c.func}({', '.join(_spell(a) for a in c.args)})"
        case n.BinOp() as b:
            return f"{_spell(b.left)} {b.op} {_spell(b.right)}"
        case _:
            return "..."


class _Seat:
    """Who decides at a judged position: the acting seat (named by `label`),
    every receiving seat of a chosen movement `to each`, or nobody."""

    def __init__(self, label: Said, every: bool = False) -> None:
        self.label = label
        self.every = every


_NO_SEAT = _Seat("every seat", every=True)
# The context a position gives a zone it names without reading what the zone
# holds: a chosen movement's destination. Not a read need -- a zone reference
# in this context reads nothing, and only its index is read. It travels
# through a `let`, a parameter and a phase outcome like every need, so the use
# site decides it, never the initialiser.
_LOCATE = "locate"
# The seat of a scope whose value was bound under another acting seat: equal
# to no scope's own, so nothing it binds carries a proof either.
_NO_ACTING_SEAT = -2
# Where a decision is refused for want of an acting seat, which decides the fix
# the refusal names: a statement takes a binder, a gate or the result reads a
# state variable decided during play.
_NO_ACTOR_STATEMENT = "statement"
_NO_ACTOR_GATE = "gate"
_NO_ACTOR_RESULT = "result"
_NO_ACTOR_ROUND = "round"
_NO_ACTOR_WHERE = {
    _NO_ACTOR_STATEMENT: (
        "outside any `as <player>`, `for each player`, `turns` or offered "
        "move, nobody is taking a turn"
    ),
    _NO_ACTOR_GATE: "a phase's `when` or `repeat until` is read between turns",
    _NO_ACTOR_RESULT: "`loser:` is read after the last phase",
    _NO_ACTOR_ROUND: (
        "a trick round reads its mode triggers and Delegated Play helpers in "
        "its own context, and a trick round that reads this one stands "
        "outside any binder that names who acts"
    ),
}
_ACTOR_SCOPE = _ReadScope(aliases=_ActorAliases(), acting=True, seat=-1)


class _HiddenReads:
    """The reader of expression reads and the two verdicts over it.

    `reads_of` follows a `let` into its initialiser, a designer or library
    function into its body with its parameters bound to the arguments, a
    procedure run into its body, a phase outcome's payload into the
    `produces:` arm binder that receives it, a declared Primitive into its
    `reads` clause (a keyed read keyed by the call's argument), and a Builtin
    through `BUILTIN_ARGUMENT_READS` / `BUILTIN_READS_NOTHING` /
    `BUILTIN_IMPLICIT_READS`. The Delegated Play helpers are called by the
    engine, not by designer text, so no call reaches `play_source_for`: its
    pool is judged per delegated decision by the runtime Owner Guard
    `delegation.check_decider_sees`, which this check shadows statically."""

    def __init__(self, game: n.Game, bag: DiagnosticBag, alone: bool = False) -> None:
        self.game = game
        self.bag = bag
        # The spliced functions a library brought, so a read in one's body is
        # located at the game's call of it.
        self.library_functions = frozenset(_library_functions(game))
        # Whether each procedure body or move type effect being walked is a
        # library's: the text a walk stands in, where a `run` has carried it.
        self.library_text: list[bool] = []
        # Whether this walk judges a library procedure alone, under a caller
        # `_tells_nothing` makes; such a walk asks no caller of its own.
        self.alone = alone
        # The crossings of each `run` the walk is inside, for the refusals
        # `_tell` makes there; None for a `run` that crosses into no library.
        self.run_routes: list[_RunRoutes | None] = []
        # The library definition being judged at a position the game's own
        # choice decides, and the fix the game can take there.
        self.game_fix: tuple[n.LibraryOrigin, Said, Span | None] | None = None
        # The bindings of each `run`'s arguments to its procedure's
        # parameters, by identity, innermost last.
        self.run_args: list[frozenset[int]] = []
        # The caller meeting each library procedure the game runs, by `run`.
        self.meeting: dict[int, tuple[tuple[n.NameRef, str], ...]] = {}
        # How many refusals `_tell` was asked to make.
        self.told = 0
        self.zones = {z.name: z for z in game.zones}
        self.player_families = frozenset(
            z.name for z in game.zones if z.index is not None and role_of(z.index) is Role.PLAYER
        )
        # The families a rule clause's Play Source can be an instance of.
        self.play_sources = frozenset(
            nd.source_zone for nd in _walk(game)
            if isinstance(nd, n.TrickRound) and nd.source_zone in self.zones
        )
        self.functions = {f.name: f for f in game.functions}
        self.procedures = {p.name: p for p in game.procedures}
        self.move_types = {m.name: m for m in game.move_types}
        self.primitives = (
            {d.name: d for d in game.primitives.decls} if game.primitives else {}
        )
        self.positions = frozenset(p.name for p in game.positions)
        self.flavor = game.content_flavor
        # Every phase outcome's `produce` sites, by the producing phase: the
        # ones this walk has met, and the ones the previous walk collected.
        self.produced: dict[str, list[tuple[str, tuple[n.Expr, ...], _ReadScope]]] = {}
        self.collected: dict[str, list[tuple[str, tuple[n.Expr, ...], _ReadScope]]] = {}
        self.outcome_phase: list[str] = []
        # The procedures whose bodies the walk is inside, so a cycle is met
        # once and left to the check that refuses it.
        self.running: list[str] = []
        self.seats = 0
        self.verdicts: list[HiddenReadVerdict] = []
        self._reported: set[tuple[object, ...]] = set()
        # Where the walk stands when no seat is acting, for the fix a refused
        # decision there is told: a statement, a gate, or the result.
        self.place = _NO_ACTOR_STATEMENT

    # --- the reader ---------------------------------------------------------

    def reads_of(
        self,
        expr: object,
        scope: _ReadScope,
        need: str = "identity",
        route: tuple[Said, ...] = (),
        choose: str | None = None,
        calls: tuple[str, ...] = (),
    ) -> Iterator[ZoneRead]:
        """Every zone read `expr` makes, with the need its context gives a
        zone reference standing where a value is read."""
        match expr:
            case n.NameRef() as ref:
                if ref.ref_kind == "play_source" and need != _LOCATE:
                    # The acting seat's instance of whichever trick round's
                    # source asks the rule; where a pool is routed, the Play
                    # Source is it.
                    for family in sorted(self.play_sources):
                        at = (
                            scope if scope.routed is None
                            else replace(scope, routed=scope.routed | {family})
                        )
                        yield ZoneRead(family, None, at, False, need, route, ref.span, choose)
                elif ref.ref_kind == "zone" and ref.name in self.zones:
                    if need != _LOCATE:
                        yield ZoneRead(ref.name, None, scope, False, need, route, ref.span, choose)
                elif ref.ref_kind == "local":
                    for b in scope.lookup(ref.name):
                        if b.index_binder is None:
                            yield from self._by_value(
                                b, self.reads_of(
                                    b.value, scope.follow(b), need, route + (b.via,), choose, calls
                                )
                            )
            case n.Subscript() as sub:
                obj = sub.obj
                if isinstance(obj, n.NameRef) and obj.ref_kind == "zone" and obj.name in self.zones:
                    if need != _LOCATE:
                        yield ZoneRead(obj.name, sub.index, scope, False, need, route, sub.span, choose)
                elif isinstance(obj, n.NameRef) and obj.ref_kind == "local":
                    for b in scope.lookup(obj.name):
                        if b.index_binder is not None:
                            inner = scope.follow(b).bind(
                                b.index_binder, (_Binding(sub.index, scope, b.via),)
                            )
                            yield from self._by_value(
                                b, self.reads_of(b.value, inner, need, route + (b.via,), choose, calls)
                            )
                        else:
                            yield from self._by_value(
                                b, self.reads_of(
                                    b.value, scope.follow(b), need, route + (b.via,), choose, calls
                                )
                            )
                else:
                    yield from self.reads_of(obj, scope, "identity", route, choose, calls)
                yield from self.reads_of(sub.index, scope, "identity", route, choose, calls)
            case n.CardQuery() as q:
                if q.kind == "count" and q.where is None:
                    src_need = "count"
                elif q.kind == "set" and need == "order":
                    src_need = "order"
                else:
                    src_need = "identity"
                yield from self.reads_of(q.source, scope, src_need, route, choose, calls)
                inner = scope.shadow(_introduced_binders(q, self.flavor))
                yield from self.reads_of(q.where, inner, "identity", route, choose, calls)
            case n.IsCheck() as chk:
                operand_need = "existence" if chk.kind in ("empty", "not_empty") else "identity"
                yield from self.reads_of(chk.operand, scope, operand_need, route, choose, calls)
            case n.IfExpr() as ife:
                yield from self.reads_of(ife.cond, scope, "identity", route, choose, calls)
                yield from self.reads_of(ife.then, scope, need, route, choose, calls)
                for cond, then in ife.elifs:
                    yield from self.reads_of(cond, scope, "identity", route, choose, calls)
                    yield from self.reads_of(then, scope, need, route, choose, calls)
                yield from self.reads_of(ife.otherwise, scope, need, route, choose, calls)
            case n.Choose() as ch:
                for field_name in ("lo", "hi", "excluding"):
                    yield from self.reads_of(
                        getattr(ch, field_name), scope, "identity", route, field_name, calls
                    )
            case n.Call() as call:
                yield from self._call_reads(call, scope, need, route, choose, calls)
            case tuple() as items:
                for item in items:
                    yield from self.reads_of(item, scope, "identity", route, choose, calls)
            case _ if is_dataclass(expr) and not isinstance(expr, (type, Span)):
                introduced = _introduced_binders(expr, self.flavor)
                scope_fields = _BINDER_SCOPE_FIELDS.get(type(expr))
                for f in fields(expr):
                    shadowed = scope_fields is None or f.name in scope_fields
                    inner = scope.shadow(introduced) if shadowed else scope
                    yield from self.reads_of(
                        getattr(expr, f.name), inner, "identity", route, choose, calls
                    )
            case _:
                return

    @staticmethod
    def _by_value(binding: _Binding, reads: Iterator[ZoneRead]) -> Iterator[ZoneRead]:
        """`reads`, each recording that it was reached through `binding`."""
        for read in reads:
            yield replace(read, bindings=read.bindings + (binding,))

    def _call_reads(
        self,
        call: n.Call,
        scope: _ReadScope,
        need: str,
        route: tuple[Said, ...],
        choose: str | None,
        calls: tuple[str, ...],
    ) -> Iterator[ZoneRead]:
        fn = self.functions.get(call.func)
        if fn is not None:
            if call.func in calls:
                return  # recursion: `_check_functions` reports it
            via: Said = "function " + cite_named(fn, f"`{fn.name}`")
            # A function body is hermetic: it names no binder of the caller's,
            # and inherits the acting seat.
            body_scope = replace(scope, names=(), aliases=_ActorAliases(frozenset()))
            bound: list[_Binding] = []
            for param, arg in zip(fn.params, call.args):
                binding = _Binding(arg, scope, via)
                bound.append(binding)
                body_scope = body_scope.bind(param.name, (binding,))
            for found in self.reads_of(
                fn.body, body_scope, need, route + (via,), choose, calls + (call.func,)
            ):
                # A read reached through a parameter is the caller's own text,
                # read by value, however the caller computed the argument.
                by_value = any(b is mine for b in found.bindings for mine in bound)
                if found.crossing is None and not by_value:
                    if call.contract is not None:
                        anchor = found.exit.span if found.exit is not None else found.span
                        crossing = _Crossing(
                            call.contract, fn, call.args, scope,
                            found.route[len(route) + 1:], anchor,
                        )
                        found = replace(found, crossing=crossing)
                    elif fn.name in self.library_functions:
                        found = replace(found, exit=call)
                yield found
            return
        decl = self.primitives.get(call.func)
        if decl is not None:
            via = f"Primitive `{decl.name}`'s `reads`"
            params = [p.name for p in decl.params]
            for read in decl.reads:
                kind = classify_read(self.game, read.name, read.phase)
                if kind is ReadKind.SINGLE_ZONE:
                    yield ZoneRead(read.name, None, scope, False, "identity", route + (via,), call.span, choose)
                elif kind is ReadKind.ZONE_FAMILY:
                    if read.binder is not None and read.binder in params:
                        at = params.index(read.binder)
                        if at < len(call.args):
                            yield ZoneRead(
                                read.name, call.args[at], scope, False, "identity",
                                route + (via,), call.span, choose,
                            )
                    else:
                        yield ZoneRead(read.name, None, scope, True, "identity", route + (via,), call.span, choose)
            for arg in call.args:
                yield from self.reads_of(arg, scope, "identity", route, choose, calls)
            return
        if call.func in BUILTIN_ARGUMENT_READS:
            pile = ARRIVAL_RECORD_CALLS.get(call.func)
            for at, arg in enumerate(call.args):
                if at == pile:
                    # A pile's Arrival Record: `_check_arrival_record_pile_args`
                    # judges it in every position, this one included.
                    continue
                yield from self.reads_of(
                    arg, scope, BUILTIN_ARGUMENT_READS[call.func], route, choose, calls
                )
            return
        if call.func in BUILTIN_IMPLICIT_READS:
            family, implicit_need = BUILTIN_IMPLICIT_READS[call.func]
            if family in self.zones:
                via = f"`{call.func}`"
                yield ZoneRead(family, None, scope, True, implicit_need, route + (via,), call.span, choose)
        for arg in call.args:
            yield from self.reads_of(arg, scope, "identity", route, choose, calls)

    # --- the verdicts -------------------------------------------------------

    def _owned_by(self, zone: str) -> Role | None:
        """The role a zone family is owned by, or None for an unowned zone."""
        decl = self.zones[zone]
        if decl.index is None or decl.index in self.positions:
            return None
        role = role_of(decl.index)
        return role if role in ZONE_INDEX_ROLES else None

    def _names_acting_seat(self, index: n.Expr, scope: _ReadScope) -> str | None:
        """Why `index` statically denotes the acting seat, or None: as
        written, or as any name it is bound to by value."""
        for spelled, at in self._spellings(index, scope):
            if (
                at.routed is not None
                and isinstance(spelled, n.Call)
                and spelled.func == CHOOSER_HELPER
                and len(spelled.args) == 1
                and isinstance(spelled.args[0], n.NameRef)
                and spelled.args[0].ref_kind == "pronoun"
                and spelled.args[0].name == "actor"
            ):
                return f"`{CHOOSER_HELPER}(actor)` names the deciding seat"
            if isinstance(spelled, n.IntLit) and spelled.value == at.seat_literal:
                return f"seat {spelled.value} is the seat `as {spelled.value}` binds"
            if not isinstance(spelled, n.NameRef):
                continue
            if spelled.ref_kind in ("local", "pronoun") and spelled.name in at.aliases.names:
                return f"`{spelled.name}` names the acting seat"
            if (
                spelled.ref_kind == "state_var"
                and spelled.name == at.seat_var
                and at.seat_var_live
            ):
                return f"the State Variable `{spelled.name}` names the seat `as` binds"
        return None

    def _chooser(self) -> Said:
        """The Delegated Play helper naming the deciding seat, as a refusal
        names it."""
        return _cite_in(self.game, "function", CHOOSER_HELPER, f"`{CHOOSER_HELPER}(actor)`")

    def _why_not_owned(self, index: n.Expr | None, scope: _ReadScope) -> Said:
        if scope.routed is not None:
            return (
                " (under Delegated Play `actor` is the seat whose card is played, and "
                + self._chooser() + " chooses it; the bare `hand` reads the "
                "pool the chooser plays from)"
            )
        if (
            isinstance(index, n.NameRef)
            and index.ref_kind == "state_var"
            and index.name == scope.seat_var
            and not scope.seat_var_live
        ):
            return (
                f" (`{index.name}` is written after `as {index.name}` names the "
                f"deciding seat, so it may name another seat by then)"
            )
        return ""

    def _own_reason(self, read: ZoneRead) -> str | None:
        """Why the acting seat owns the instance `read` reads, or None."""
        if read.every:
            return None
        role = self._owned_by(read.zone)
        if role is None:
            return None
        if read.index is None:
            if role is not Role.PLAYER:
                # Bare sugar names the acting seat's instance only in a family
                # keyed by seat; `_check_bare_family_refs` refuses the rest,
                # and this shadows it.
                return None
            routed = read.index_scope.routed
            if routed is not None:
                # The routed pool: its visibility to the decider is the runtime
                # Owner Guard `delegation.check_decider_sees`'s, which this
                # shadows statically.
                return (
                    "bare-family sugar reads the routed pool its decider plays from"
                    if read.zone in routed
                    else None
                )
            if read.zone in read.index_scope.rerouted:
                return None
            return "bare-family sugar reads the acting seat's own" if read.index_scope.acting else None
        for index, scope in self._spellings(read.index, read.index_scope):
            if role is Role.TEAM:
                if isinstance(index, n.Call) and index.func == "team_of" and len(index.args) == 1:
                    for inner, inner_scope in self._spellings(index.args[0], scope):
                        why = self._names_acting_seat(inner, inner_scope)
                        if why is not None:
                            return f"`team_of` of the acting seat ({why})"
            else:
                why = self._names_acting_seat(index, scope)
                if why is not None:
                    return why
        return None

    def _spellings(self, index: n.Expr, scope: _ReadScope) -> list[tuple[n.Expr, _ReadScope]]:
        """`index` as written, then with each name the reader follows by
        value -- a parameter, a `let`, a phase outcome's payload -- replaced
        by what it is bound to, in turn: a name may denote the acting seat
        where it is written (a procedure's `as victim`) or where its value is
        (`let t = team_of(actor)`)."""
        out = [(index, scope)]
        # A binding's value is read in the scope it was bound in, which holds
        # only earlier bindings, so the chain ends; the seen set is the
        # Shadow of that, never a length.
        seen: set[int] = set()
        while isinstance(index, n.NameRef) and index.ref_kind == "local":
            bindings = scope.lookup(index.name)
            if len(bindings) != 1 or bindings[0].index_binder is not None:
                break
            if id(bindings[0]) in seen:
                break
            seen.add(id(bindings[0]))
            index, scope = bindings[0].value, scope.follow(bindings[0])
            out.append((index, scope))
        return out

    def _zone_text(self, read: ZoneRead) -> Said:
        if read.every:
            return f"every `{read.zone}`"
        if read.index is None:
            return f"`{read.zone}`"
        index, _ = self._spellings(read.index, read.index_scope)[-1]
        return self._quoted(index, f"`{read.zone}[{_spell(index)}]`")

    def _quoted(self, expr: object, words: str) -> Said:
        """`words` quoting `expr`: a citation of every definition a call in
        it names, the bare words where it calls none."""
        called: dict[str, object] = {}
        for nd in _walk(expr):
            if isinstance(nd, n.Call) and nd.func in self.functions:
                found = next((f for f in self.game.functions if f.name == nd.func), None)
                if found is not None:
                    called.setdefault(nd.func, found)
        return cite_all(tuple(called.values()), words)

    def _judge(
        self, what: Said, reads: Iterator[ZoneRead], decider: _Seat, span: Span | None,
        only_choose: bool = False, source: bool = False, evaluator: _Seat | None = None,
        skip_choose: bool = False,
    ) -> None:
        """Judge each read: at `decider`, the seat whose decision the
        position's value reaches, or -- for a read inside a nested `choose`
        where the position is evaluated by another seat -- at `evaluator`,
        the seat that makes that `choose`."""
        for read in reads:
            if only_choose and read.choose is None:
                continue
            if skip_choose and read.choose is not None:
                continue
            decl = self.zones.get(read.zone)
            if decl is None or decl.type_ref.name not in ZONE_PROJECTIONS:
                continue
            ztype = decl.type_ref.name
            in_choose = read.choose is not None and (only_choose or evaluator is not None)
            seat = evaluator if read.choose is not None and evaluator is not None else decider
            position = (
                ("a `choose`'s `excluding`" if read.choose == "excluding" else "a `choose`'s range")
                if in_choose
                else what
            )
            owned = self._owned_by(read.zone) is not None
            to_others = reveals(ztype, read.need, False)
            to_owner = reveals(ztype, read.need, True)
            if seat.every:
                accepted = to_others and (to_owner or not owned)
                reason = "public" if accepted else ""
            else:
                own = self._own_reason(read) if owned else None
                if to_others:
                    accepted, reason = True, "public"
                elif own is not None and to_owner:
                    accepted, reason = True, own
                else:
                    accepted, reason = False, ""
            self.verdicts.append(
                HiddenReadVerdict(rendered(position)[0], read, accepted, reason, span)
            )
            if accepted:
                continue
            if read.crossing is not None:
                self._report_crossed(position, read, seat, to_owner)
                continue
            self._report(position, read, seat, to_owner, span or read.span, source and not in_choose)

    def _report_crossed(self, what: Said, read: ZoneRead, seat: _Seat, to_owner: bool) -> None:
        """A refused read the game's answer to a Definition Contract makes,
        told to the game's author at the last text the game wrote on the way
        to it (decisions.md "Family libraries"): a library is sound when some
        answer meets its row, so a read only some answers make is the
        answer's. The zone is spelled as the game wrote it, and where the
        instance read is the one the library's argument names, the sentence
        names that argument."""
        crossing = read.crossing
        assert crossing is not None
        fn = crossing.function
        written, passed = self._game_spelling(read, crossing)
        needs = _needs(read.need, written)
        through = (
            " (through " + Sentence.join(", then ", crossing.inner_route) + ")"
            if crossing.inner_route else ""
        )
        library = cite_library(crossing.stamp.library, crossing.stamp.row_span)
        calls = library + f" calls it under its contract " + cite_where(f"`{crossing.stamp.row}`", crossing.stamp.row_span) + f" in " + what
        decider = seat.label
        decides = (
            "which each receiving seat decides, so every receiving seat"
            if seat.every
            else f"which " + decider + f" decides, so " + decider
        )
        if passed is not None:
            value, param = passed
            cannot = "not every receiving seat can see them" if seat.every else f"" + decider + f" cannot see them"
            # `_spell` quotes the shapes an index takes; any other argument is
            # named by what it is not.
            argument = (
                f"a seat it does not show to be " + decider if "..." in value else f"`{value}`"
            )
            message: Said = (
                "function " + cite_named(fn, f"`{fn.name}`") + f" reads " + needs + through
                + ", and " + library
                + f" passes " + argument + f" as `{param}` when it "
                f"calls it under its contract " + cite_where(f"`{crossing.stamp.row}`", crossing.stamp.row_span) + f" in " + what + f", "
                f"" + decides + f" must be able to check it, but " + cannot
            )
        else:
            blind = (
                "which not every receiving seat can see" if seat.every
                else f"which " + decider + f" cannot see" + self._why_not_owned(read.index, read.index_scope)
            )
            message = (
                "function " + cite_named(fn, f"`{fn.name}`") + f" reads " + needs + through
                + ", " + blind + ", but " + calls
                + f", " + decides + f" must be able to check it"
            )
        own = (
            self._passed_deciding_seat(read, crossing)
            if passed is None and not seat.every and to_owner
            else None
        )
        also = f", or the cards of the seat the library passes as `{own}`" if own else ""
        message += (
            f". Read cards every seat can see{also}, or have the holder announce "
            f"or reveal the fact first"
        )
        key = (message, crossing.anchor)
        if key not in self._reported:
            self._reported.add(key)
            self.bag.error(message, crossing.anchor, code=Code.DECIDES_ON_HIDDEN_CARDS)

    def _game_spelling(
        self, read: ZoneRead, crossing: _Crossing
    ) -> tuple[Said, tuple[str, str] | None]:
        """The zone as the game's text spells it, and -- where the instance
        read is named by one of the library's arguments -- that argument and
        the parameter it binds."""
        if read.index is None:
            return self._zone_text(read), None
        chain = self._spellings(read.index, read.index_scope)
        start = 0
        if read.exit is not None:
            start = next(
                (at for at, (expr, _) in enumerate(chain) if any(expr is a for a in read.exit.args)),
                0,
            )
        passed: tuple[str, str] | None = None
        for at, (expr, _) in enumerate(chain):
            for param, arg in zip(crossing.function.params, crossing.args):
                if expr is arg and at > start:
                    passed = (_spell(arg), param.name)
                    break
            if passed is not None:
                break
        index, _ = chain[start]
        return self._quoted(index, f"`{read.zone}[{_spell(index)}]`"), passed

    def _passed_deciding_seat(self, read: ZoneRead, crossing: _Crossing) -> str | None:
        """The parameter the library binds to the deciding seat, where the
        zone read is a family keyed by player: reading that parameter's
        instance is the remedy that passes."""
        if self._owned_by(read.zone) is not Role.PLAYER:
            return None
        for param, arg in zip(crossing.function.params, crossing.args):
            if param.type_name == "Player" and self._names_acting_seat(arg, crossing.scope):
                return param.name
        return None

    def _report(
        self, what: Said, read: ZoneRead, seat: _Seat, to_owner: bool,
        span: Span | None, source: bool,
    ) -> None:
        zone = self._zone_text(read)
        needs = _needs(read.need, zone)
        route: Said = " (through " + Sentence.join(", then ", read.route) + ")" if read.route else ""
        if seat is _NO_SEAT:
            who = "only its owner can see" if to_owner else "no seat can see"
            extra = (
                "; or read the card as it is played (`action.card`), as Hearts breaks "
                "hearts on the card played"
                if rendered(what)[0].endswith("`transition_to` trigger") else ""
            )
            message = (
                f"" + what + f" is a fact every seat can check, but it reads " + needs + route + f", "
                f"which {who}. Make the holder announce it, as Gin Rummy's knock sets "
                f"`knocked`, and read the announcement{extra}"
            )
        else:
            decider = seat.label
            blind = (
                "which not every receiving seat can see" if seat.every
                else f"which " + decider + f" cannot see" + self._why_not_owned(read.index, read.index_scope)
            )
            if source:
                message = (
                    f"a chosen movement's source is the pool " + decider + f" picks from, but "
                    f"it reads " + needs + route + f", " + blind + f", so the pick would name cards "
                    f"the chooser cannot see. Pick from cards the chooser can see; a "
                    f"blind pick from cards the chooser cannot see (Old Maid's draw) "
                    f"needs a pick by position, which the language does not have yet "
                    f"(issue #756)"
                )
            else:
                head = (
                    f"" + what + f" is decided by " + decider + f", so " + decider + f" must be able to "
                    f"check it, but it reads " + needs + route + f", " + blind
                )
                message = (
                    head + f". Read the deciding seat's own cards, or have the holder "
                    f"announce or reveal the fact first"
                )
                self._tell(
                    message,
                    span,
                    read,
                    for_game=self._for_game(head),
                    code=Code.DECIDES_ON_HIDDEN_CARDS,
                )
                return
        self._tell(message, span, read, code=Code.DECIDES_ON_HIDDEN_CARDS)

    def _for_game(self, head: Said) -> Said | None:
        """`head` as the game's author reads it, where the library definition
        being judged stands at a position the game's choice decides."""
        if self.game_fix is None:
            return None
        origin, fix, at = self.game_fix
        return cite_origin(origin, at) + ": " + head + " — " + fix

    def _emit(
        self,
        message: Said,
        span: Span | None,
        route: Route | None = None,
        for_game: Said | None = None,
        stands_on: tuple[Span, ...] = (),
        *,
        code: Code,
    ) -> None:
        key = (message, span, None if route is None else route.at)
        if key not in self._reported:
            self._reported.add(key)
            self.bag.error(message, span, route=route, for_game=for_game, stands_on=stands_on, code=code)

    def _tell(
        self,
        message: Said,
        span: Span | None,
        read: ZoneRead | None = None,
        route: Route | None = None,
        for_game: Said | None = None,
        *,
        code: Code,
    ) -> None:
        """A refusal of a decision's seat, carrying the crossing it was
        reached by: `route` where the walk entered library text by a call,
        else the crossing of the `run` the walk is inside (`_RunRoutes`) --
        `read` reached through the run's own arguments is the game's text."""
        self.told += 1
        routes = self.run_routes[-1] if self.run_routes else None
        if route is None and routes is not None:
            argument = read is not None and any(id(b) in self.run_args[-1] for b in read.bindings)
            route = routes.argument if argument else routes.body
        self._emit(message, span, route, for_game, self._stands_on(read), code=code)

    def _stands_on(self, read: ZoneRead | None) -> tuple[Span, ...]:
        """The library text a refused read reaches: the read itself, or each
        library function whose call names the instance it reads."""
        if read is None:
            return ()
        if read.span is not None and read.route:
            return (read.span,)
        library = {f.name: f.span for f in self.game.functions if f.origin is not None}
        if read.index is not None:
            called = tuple(
                at for nd in _walk(read.index)
                if isinstance(nd, n.Call) and (at := library.get(nd.func)) is not None
            )
            if called:
                return called
        return () if read.span is None else (read.span,)

    # --- the positions ------------------------------------------------------

    def run(self) -> None:
        """Walk the game until every producer is collected, then judge. A
        consumer may precede its producer in the text (an `after_each`
        consuming a child outcome declared after it), so the verdicts are
        taken on a walk that already holds every `produce` site; a payload
        read through another outcome's binder settles on the next walk."""
        bag = self.bag
        self.bag = DiagnosticBag()
        # A fixed point over the outcome graph: each walk binds every
        # `produces:` arm to what the previous walk collected, until a walk
        # collects exactly what it was given. A payload reaches a consumer
        # through at most one outcome per `produce` site, so the walks are
        # bounded by the sites plus the one that finds nothing new.
        sites = sum(1 for node in _walk(self.game) if isinstance(node, n.Produce))
        for _ in range(sites + 1):
            self._walk_game()
            stable = self.produced == self.collected
            self.collected, self.produced = self.produced, {}
            if stable:
                break
        self.bag = bag
        self.verdicts = []
        self._reported = set()
        self._walk_game()

    def _walk_game(self) -> None:
        self.seats = 0
        self.outcome_phase = []
        self.place = _NO_ACTOR_STATEMENT
        # Whether each trick round stands where a seat acts, by the phase it
        # runs in: a round's mode triggers and its Delegated Play helpers are
        # evaluated in the round statement's own context.
        self.trick_rounds_acting: list[tuple[int, bool]] = []
        self.phase_stack: list[int] = []
        for phase in self.game.phases:
            self._phase(phase, _ReadScope())
        for mt in self.game.move_types:
            scope = _ACTOR_SCOPE.shadow(tuple(p.name for p in mt.params))
            if mt.when is not None:
                self._judge(
                    "move type " + cite_named(mt, f"`{mt.name}`") + "'s `when:`",
                    self.reads_of(mt.when, scope), _Seat("the acting seat"), mt.when.span,
                )
            self.library_text.append(mt.origin is not None)
            self._stmts(mt.effect, scope, _Seat("the acting seat"))
            self.library_text.pop()
        # A Declared Engine asks its follows function at each seat's climb
        # decision: what it admits is what that seat may play.
        follows = sorted({
            node.engine.follows for node in _walk(self.game)
            if isinstance(node, n.ClimbRound) and isinstance(node.engine, n.DeclaredEngine)
        })
        for name in follows:
            fn = self.functions.get(name)
            if fn is None:
                continue
            self._judge(
                "the follows function " + cite_named(fn, f"`{fn.name}`"),
                self.reads_of(fn.body, _ACTOR_SCOPE.shadow(tuple(p.name for p in fn.params))),
                _Seat("the acting seat"), fn.body.span,
            )
        rule_scope, rule_seat = _ACTOR_SCOPE, _Seat("the acting seat")
        # The seat evaluating a clause, which makes a `choose` nested in it
        # (`RULE_CLAUSE_SEATS`): the attributed seat. Where it is not the
        # decider, it is judged apart. Issue #760 may refuse a `choose` in a
        # rule clause outright, which would leave this arm unreachable.
        evaluator_scope: _ReadScope | None = None
        evaluator_seat = _Seat("`actor`, the seat whose card is played")
        if any(f.name == CHOOSER_HELPER for f in self.game.functions):
            # Every rule is asked at the trick round's card decision, the one
            # decision `chooser_for` routes: its clauses are decided by
            # `chooser_for(actor)`, so no proof about `actor` stands. The
            # Play Source is the routed pool (`reads_of` adds its family per
            # read), and so is the CURRENT round's source family named bare; a
            # rule may be active in any trick round, so a named family is the
            # routed pool only where every trick round of the game sources it.
            sources = [
                node.source_zone for node in _walk(self.game) if isinstance(node, n.TrickRound)
            ]
            every_round = frozenset(sources) if len(set(sources)) == 1 else frozenset()
            rule_scope = _ReadScope(
                aliases=_ActorAliases(frozenset()),
                acting=True,
                seat=-3,
                routed=every_round,
            )
            rule_seat = _Seat(self._chooser())
            rerouted = (
                every_round | self.play_sources
                if any(f.name == SOURCE_HELPER for f in self.game.functions)
                else frozenset()
            )
            evaluator_scope = replace(_ACTOR_SCOPE, rerouted=rerouted)
        for rule in self.game.rules:
            # A library rule is judged where the game activates it.
            self.game_fix = None if rule.origin is None else (
                rule.origin,
                "take " + cite_named(rule, f"'{rule.name}'") + " out of `active_rules:`",
                rule.span,
            )
            clauses: list[tuple[str, n.Expr | None]] = [
                ("applies_when", rule.applies_when.pred if rule.applies_when else None),
                ("demands", rule.demands.expr if rule.demands else None),
                ("if_impossible", rule.if_impossible),
                ("exempts", rule.exempts),
            ]
            for clause, expr in clauses:
                if expr is None:
                    continue
                seats = {
                    SEAT_TRICK_DECIDER: (rule_scope, rule_seat),
                    SEAT_ACTING: (evaluator_scope or rule_scope, evaluator_seat),
                }
                decider, evaluator = (seats[seat] for seat in RULE_CLAUSE_SEATS[clause])
                self._judge(
                    "rule " + cite_named(rule, f"`{rule.name}`") + f"'s `{clause}:`",
                    self.reads_of(expr, decider[0]), decider[1], expr.span,
                    skip_choose=evaluator_scope is not None,
                )
                if evaluator_scope is not None:
                    self._judge(
                        "", self.reads_of(expr, evaluator[0]), evaluator[1], expr.span,
                        only_choose=True,
                    )
        self.game_fix = None
        self._judge_trick_context_positions()
        if self.game.loser is not None:
            self.place = _NO_ACTOR_RESULT
            self._outside(self.game.loser.selection, _ReadScope(), _NO_SEAT)

    def _judge_trick_context_positions(self) -> None:
        """A mode's `transition_to` trigger and a Delegated Play helper's body
        are evaluated by a trick round, in the round statement's context. A
        trigger is read by the trick rounds of its own phase's subtree
        (`active_rules.active_mode_exits` walks the round's chain of enclosing
        phases), so a seat acts there where each of them stands under a binder
        that names one; a helper is read by every trick round of the game."""
        self.place = _NO_ACTOR_ROUND
        for phase in (nd for nd in _walk(self.game) if isinstance(nd, n.Phase)):
            if all(acting for at, acting in self.trick_rounds_acting if at == id(phase)):
                continue
            for item in phase.items:
                if not isinstance(item, n.Mode):
                    continue
                for transition in item.transitions:
                    if transition.event.where is not None:
                        self._refuse_unacting_decisions(transition.event.where, _ReadScope())
        if not all(acting for _, acting in self.trick_rounds_acting):
            for fn in self.game.functions:
                if fn.name in (CHOOSER_HELPER, SOURCE_HELPER):
                    self.library_text.append(fn.origin is not None)
                    self.game_fix = None if fn.origin is None else (
                        fn.origin,
                        "play this game's trick rounds inside a binder that names "
                        "who acts (`as <player> { round ... }`)",
                        fn.span,
                    )
                    self._refuse_unacting_decisions(fn.body, _ReadScope())
                    self.game_fix = None
                    self.library_text.pop()
        self.place = _NO_ACTOR_STATEMENT

    def _outside(self, expr: object, scope: _ReadScope, seat: _Seat) -> None:
        """A position no verdict judges: only a `choose` nested in it decides."""
        if expr is None:
            return
        if self._refuse_unacting_decisions(expr, scope):
            return
        self._judge("", self.reads_of(expr, scope), seat, getattr(expr, "span", None), only_choose=True)

    def _refuse_unacting_decisions(self, expr: object, scope: _ReadScope) -> bool:
        """Where no seat is acting, a `choose` the expression evaluates has no
        one to decide it, and an `actor` it reads names no one -- in it, or in
        a function it calls, whose body inherits the caller's acting seat. A
        `let` is not followed: its initialiser is evaluated where the `let`
        stands. Reports each, and answers whether there was one."""
        if scope.acting:
            return False
        found = False
        in_library = bool(self.library_text) and self.library_text[-1]
        for node, route, answered, entered in self._actor_needs_in(expr, (), in_library=in_library):
            found = True
            if isinstance(node, n.NameRef) and node.ref_kind == "zone" and answered is not None:
                self._report_unacting_answer(
                    route, answered, node.span,
                    f"names `{node.name}` bare (the acting player's own)",
                    "so it names no player's. Name whose from the parameters the "
                    "row passes, or read the game's own state",
                )
            elif isinstance(node, n.NameRef) and node.ref_kind == "zone":
                crossing = None if entered is None else _entry_route("call", entered, node.span)
                self._report_bare_family(node.name, route, node.span, crossing)
            elif answered is not None and isinstance(node, n.Choose):
                self._report_unacting_answer(route, answered, node.span)
            elif answered is not None:
                # Shadows `_check_functions`' call-site pronoun refusal, the
                # Owner Guard of `actor` in a function body, which sends the
                # answer's author to the parameter the row passes.
                continue
            elif entered is not None and isinstance(node, n.Choose):
                at = entered.depth - 1
                told = route[:at] + (entered.through,) + route[at + 1:]
                self._report_no_actor(
                    "a `choose`", told, node.span, crossing=_entry_route("call", entered, node.span)
                )
            elif entered is not None:
                # Shadows `_check_functions`' call-site pronoun refusal, which
                # tells the library's author in every game.
                continue
            elif isinstance(node, n.Choose):
                self._report_no_actor("a `choose`", route, node.span)
            else:
                self._report_no_actor("`actor`", route, node.span, reads=True)
        return found

    def _actor_needs_in(
        self,
        expr: object,
        calls: tuple[str, ...],
        answered: _Answered | None = None,
        entered: _LibraryEntry | None = None,
        in_library: bool = False,
    ) -> Iterator[
        tuple[n.Choose | n.NameRef, tuple[Said, ...], _Answered | None, _LibraryEntry | None]
    ]:
        """Each `choose`, each `actor` read and each per-player zone named
        bare (the acting seat's own instance) `expr` evaluates, with the
        functions it is reached through; when the route crossed a library's
        call of the game's answer to a Definition Contract, that crossing; and
        when it left the game's text for a library function, that entry. A
        family a subscript keys names its own instance."""
        keyed: set[int] = set()
        for node in _child_nodes(expr):
            route = tuple(
                "function " + _cite_in(self.game, "function", c, f"`{c}`") for c in calls
            )
            if isinstance(node, n.Subscript):
                keyed.add(id(node.obj))
            if isinstance(node, n.Choose):
                yield node, route, answered, entered
            elif isinstance(node, n.NameRef) and node.ref_kind == "pronoun" and node.name == "actor":
                yield node, route, answered, entered
            elif (
                isinstance(node, n.NameRef)
                and node.ref_kind == "zone"
                and node.name in self.player_families
                and id(node) not in keyed
            ):
                yield node, route, answered, entered
            elif isinstance(node, n.Call) and node.func in self.functions and node.func not in calls:
                inner = answered
                callee = self.functions[node.func]
                into = entered
                if inner is None and node.contract is not None:
                    inner = _Answered(node.contract, node.func, len(calls) + 1, None)
                elif (
                    inner is not None
                    and inner.anchor is None
                    and node.func in self.library_functions
                ):
                    inner = replace(inner, anchor=node.span)
                elif inner is None and into is None and not in_library and callee.origin is not None:
                    into = _LibraryEntry(
                        node.span, callee.origin, len(calls) + 1, callee.name, callee.span
                    )
                yield from self._actor_needs_in(
                    callee.body, calls + (node.func,), inner, into, callee.origin is not None
                )

    def _report_unacting_answer(
        self,
        route: tuple[Said, ...],
        answered: _Answered,
        span: Span | None,
        does: str = "makes a `choose`",
        then: str = (
            "so no one can make the decision. Compute the answer from the "
            "parameters the row passes, or from the game's own state"
        ),
    ) -> None:
        """What the game's answer to a Definition Contract needs an acting
        player for -- a `choose`, a per-player zone named bare -- where the
        library reads it with no player acting: told to the game's author, at
        the last text the game wrote on the way to it, with the fix the answer
        can take."""
        inner = route[answered.depth:]
        through: Said = " (through " + Sentence.join(", then ", inner) + ")" if inner else ""
        where = _NO_ACTOR_WHERE[self.place]
        message = (
            "function " + _cite_in(self.game, "function", answered.function, f"`{answered.function}`")
            + f" {does}" + through + ", but "
            + cite_library(answered.stamp.library, answered.stamp.row_span)
            + " calls it under its contract "
            f"" + cite_where(f"`{answered.stamp.row}`", answered.stamp.row_span) + f" where no player is acting ({where}), {then}"
        )
        at = answered.anchor or span
        key = (message, at)
        if key not in self._reported:
            self._reported.add(key)
            self.bag.error(message, at, code=Code.NO_PLAYER_ACTING)

    def _report_bare_family(
        self, family: str, route: tuple[Said, ...], span: Span | None, crossing: Route | None
    ) -> None:
        """A per-player zone named bare where no player is acting: the bare
        name is the acting seat's own instance, and there is none."""
        through: Said = " (through " + Sentence.join(", then ", route) + ")" if route else ""
        where = _NO_ACTOR_WHERE[self.place]
        binder = (
            ", or read it under a binder that names who acts (`as <player> { ... }`, "
            "`for each player p: ...`)"
            if self.place == _NO_ACTOR_STATEMENT
            else ""
        )
        head = (
            f"`{family}`" + through + f" is one zone per player, named bare where no "
            f"player is acting ({where}), so it names no player's"
        )
        self._tell(
            head + f". Say whose: `{family}[<player>]`{binder}",
            span,
            route=crossing,
            for_game=self._for_game(head),
            code=Code.NO_PLAYER_ACTING,
        )

    def _report_no_actor(
        self,
        what: Said,
        route: tuple[Said, ...],
        span: Span | None,
        reads: bool = False,
        crossing: Route | None = None,
    ) -> None:
        through: Said = " (through " + Sentence.join(", then ", route) + ")" if route else ""
        where = _NO_ACTOR_WHERE[self.place]
        if reads:
            fix = (
                "Name the player itself, or read it under a binder that names "
                "who acts (`as <player> { ... }`, `for each player p: ...`)"
                if self.place == _NO_ACTOR_STATEMENT
                else "Name the player itself, or record who acted in a state "
                "variable during play and read that variable here"
            )
            message = (
                what + through + " names the acting player, but it is read where "
                f"no player is acting ({where}), so it names no one. {fix}"
            )
        else:
            fix = {
                _NO_ACTOR_STATEMENT: (
                    "Name who decides: `as <player> { ... }` for one player, "
                    "`for each player p: ...` for every player"
                ),
                _NO_ACTOR_GATE: (
                    "Make the decision before the gate is read -- in an earlier "
                    "phase, or for `repeat until` in the phase's own body -- into "
                    "a state variable (`as <player> { pick := choose ... }`), and "
                    "read that variable here"
                ),
                _NO_ACTOR_RESULT: (
                    "Make it during play into a state variable "
                    "(`as <player> { pick := choose ... }`) and name that "
                    "variable here"
                ),
                _NO_ACTOR_ROUND: (
                    "Make it during play into a state variable "
                    "(`as <player> { pick := choose ... }`) and read that "
                    "variable here"
                ),
            }[self.place]
            head = (
                what + through + " is written where no player is acting "
                f"({where}), so no one can make the decision"
            )
            self._tell(
                head + f". {fix}",
                span,
                route=crossing,
                for_game=self._for_game(head),
                code=Code.NO_PLAYER_ACTING,
            )
            return
        # An `actor` read is told where it is written, never at a `run`: in a
        # procedure body it shadows `_check_procedures`' call-site pronoun
        # refusal, which tells the procedure's author in every game.
        self._emit(message, span, code=Code.NO_PLAYER_ACTING)

    def _phase(self, phase: n.Phase, scope: _ReadScope) -> None:
        if phase.qualifier is not None:
            kind = "`when` gate" if phase.qualifier.kind == "when" else "`repeat until` condition"
            self.place = _NO_ACTOR_GATE
            refused = self._refuse_unacting_decisions(phase.qualifier.expr, scope)
            self.place = _NO_ACTOR_STATEMENT
            if not refused:
                self._judge(
                    f"phase `{phase.name}`'s {kind}",
                    self.reads_of(phase.qualifier.expr, scope), _NO_SEAT, phase.qualifier.expr.span,
                )
        if phase.outcome_cases:
            self.outcome_phase.append(phase.name)
        self.phase_stack.append(id(phase))
        for item in phase.items:
            match item:
                case n.StateBlock():
                    # A default's `choose` is `_check_state_default_scope`'s,
                    # which refuses every `choose` there; judged as acting so
                    # the two never co-report.
                    for decl in item.decls:
                        self._outside(decl.default, _ACTOR_SCOPE, _NO_SEAT)
                case n.Mode():
                    for transition in item.transitions:
                        where = transition.event.where
                        if where is not None:
                            self._judge(
                                f"mode `{item.name}`'s `transition_to` trigger",
                                self.reads_of(where, _ACTOR_SCOPE), _NO_SEAT, where.span,
                            )
                case n.BeforeEach() | n.AfterEach():
                    self._stmts(item.body, scope, _Seat("the acting seat"))
                case n.Phase():
                    self._phase(item, scope)
                case n.ActiveRules() | n.LegalMoves():
                    pass
                case _:
                    scope = self._stmt(item, scope, _Seat("the acting seat"))
        self.phase_stack.pop()
        if phase.outcome_cases:
            self.outcome_phase.pop()

    def _stmts(self, stmts: tuple[n.Stmt, ...], scope: _ReadScope, seat: _Seat) -> _ReadScope:
        for stmt in stmts:
            scope = self._stmt(stmt, scope, seat)
        return scope

    def _after(self, stmt: object, scope: _ReadScope) -> _ReadScope:
        """The scope after `stmt`: the `as` State Variable dies once a path
        through `stmt` may write it."""
        if scope.seat_var is not None and scope.seat_var_live and self._writes(stmt, scope.seat_var):
            return replace(scope, seat_var_live=False)
        return scope

    def _writes(self, node: object, name: str, visiting: frozenset[str] = frozenset()) -> bool:
        """Whether some path through `node` writes the state variable `name`,
        a move type it offers and a procedure it runs included."""
        for nd in _child_nodes(node):
            if _written_state_name(nd) == name:
                return True
            offered: tuple[str, ...] = ()
            match nd:
                case n.Offer():
                    offered = nd.offering
                case n.TrickRound() | n.ClimbRound():
                    offered = (nd.move_type,)
                case n.RunStmt() if nd.name in self.procedures and nd.name not in visiting:
                    if self._writes(self.procedures[nd.name].body, name, visiting | {nd.name}):
                        return True
            for mt_name in offered:
                mt = self.move_types.get(mt_name)
                if mt is not None and mt_name not in visiting:
                    if self._writes(mt.effect, name, visiting | {mt_name}):
                        return True
        return False

    def _seat_for(self, node: n.ForEach | n.EachSimultaneous | n.Turns | n.AsBlock,
                  rebound: _ActorAliases, scope: _ReadScope) -> tuple[_ReadScope, _Seat]:
        if isinstance(node, n.AsBlock) and self._names_acting_seat(node.player, scope):
            # The seat is canonical: an `as` naming the seat already acting
            # changes no seat, so every proof of who acts stands, and the name
            # it binds is one more.
            label = (
                f"seat `{node.player.name}`" if isinstance(node.player, n.NameRef)
                else f"the seat `as {_spell(node.player)}` names"
            )
            names = scope.aliases.names | rebound.names
            return replace(scope, aliases=_ActorAliases(names, scope.aliases.origin)), _Seat(label)
        self.seats += 1
        inner = replace(
            scope,
            aliases=rebound,
            acting=True,
            seat_var=None,
            seat_var_live=False,
            seat_literal=None,
            seat=self.seats,
        )
        match node:
            case n.ForEach():
                return inner, _Seat(f"seat `{node.binder}`")
            case n.EachSimultaneous():
                return inner, _Seat(f"seat `{node.role}`")
            case n.Turns():
                return inner, _Seat(f"seat `{node.binder}`")
            case n.AsBlock():
                player = node.player
                if isinstance(player, n.NameRef) and player.ref_kind == "state_var":
                    # This check's own rule beside `_ActorAliases`, which leaves
                    # State Variables out because a later write would falsify
                    # the comparisons it proves dead: here the variable names
                    # the seat only while no path from the `as` has written it.
                    inner = replace(inner, seat_var=player.name, seat_var_live=True)
                    return inner, _Seat(f"seat `{player.name}`")
                if isinstance(player, n.NameRef):
                    return inner, _Seat(f"seat `{player.name}`")
                if isinstance(player, n.IntLit):
                    return replace(inner, seat_literal=player.value), _Seat(f"seat {player.value}")
                return inner, _Seat(f"the seat `as {_spell(player)}` names")

    def _stmt(self, stmt: n.Stmt, scope: _ReadScope, seat: _Seat) -> _ReadScope:
        match stmt:
            case n.LetStmt():
                index = (stmt.index,) if stmt.index is not None else ()
                value_scope = scope.shadow(index)
                self._outside(stmt.value, value_scope, seat)
                binding = _Binding(stmt.value, value_scope, f"`let {stmt.name}`", stmt.index)
                aliases = _aliases_after_let(stmt, scope.aliases)
                return replace(scope.bind(stmt.name, (binding,)), aliases=aliases)
            case n.AssignStmt():
                self._outside(stmt.index, scope, seat)
                self._outside(stmt.value, scope, seat)
            case n.RotateStmt() | n.ContinueTo() | n.SkipToNextHand():
                pass
            case n.EpistemicOp():
                inner = scope.shadow(_introduced_binders(stmt, self.flavor))
                self._outside(stmt.zone, scope, seat)
                self._outside(stmt.where, inner, seat)
            case n.IfStmt():
                self._outside(stmt.cond, scope, seat)
                self._stmts(stmt.then_body, scope, seat)
                if stmt.else_body is not None:
                    self._stmts(stmt.else_body, scope, seat)
            case n.RepeatUntil():
                loop = self._after(stmt.body, scope)
                self._outside(stmt.until, loop, seat)
                self._stmts(stmt.body, loop, seat)
            case n.ForEach() | n.EachSimultaneous() | n.Turns() | n.AsBlock():
                rebound = _seat_rebinding(stmt)
                if isinstance(stmt, n.Turns):
                    for outer in (stmt.leader, stmt.participants, stmt.until):
                        self._outside(outer, scope, seat)
                if isinstance(stmt, n.AsBlock):
                    self._outside(stmt.player, scope, seat)
                if rebound is None:
                    # A value domain (or a role no row defines, reported
                    # elsewhere): the acting seat stands, and the body loops.
                    assert isinstance(stmt, (n.ForEach, n.EachSimultaneous))
                    binder = stmt.binder if isinstance(stmt, n.ForEach) else stmt.role
                    loop = self._after(stmt.body, scope).shadow((binder,))
                    self._stmt(stmt.body, loop, seat)
                else:
                    inner, inner_seat = self._seat_for(stmt, rebound, scope)
                    if isinstance(stmt, (n.ForEach, n.EachSimultaneous)):
                        self._stmt(stmt.body, inner, inner_seat)
                    else:
                        self._stmts(stmt.body, self._after_loop(stmt, inner), inner_seat)
            case n.Offer():
                self._outside(stmt.player, scope, seat)
            case n.TrickRound():
                # Every enclosing phase's modes are read by this round.
                self.trick_rounds_acting.extend(
                    (phase, scope.acting) for phase in self.phase_stack
                )
                self._outside(stmt.leader, scope, seat)
                self._outside(stmt.participants, scope, seat)
                self._outside(stmt.trump, scope, seat)
            case n.ClimbRound():
                for outer in (stmt.leader, stmt.participants, stmt.until):
                    self._outside(outer, scope, seat)
                if stmt.hosted is not None:
                    # The Hosted Poll runs before every ask in the round's
                    # own context: the acting seat stands, the binder names
                    # a seat that is not proven to be it, and the body runs
                    # again after any write in it.
                    hosted = stmt.hosted
                    loop = self._after(hosted.body, scope).shadow((hosted.binder,))
                    self._stmts(hosted.body, loop, seat)
            case n.Transfer():
                self._transfer(stmt, scope, seat)
            case n.Produce():
                for payload in stmt.payloads:
                    self._outside(payload, scope, seat)
                if self.outcome_phase:
                    self.produced.setdefault(self.outcome_phase[-1], []).append(
                        (stmt.tag, stmt.payloads, scope)
                    )
            case n.Produces():
                sites = self.collected.get(stmt.phase, [])
                for arm in stmt.arms:
                    arm_scope = scope
                    for at, binder in enumerate(arm.binders):
                        via = f"phase `{stmt.phase}`'s outcome `{arm.tag}`"
                        bindings = tuple(
                            _Binding(payloads[at], produced_scope, via)
                            for tag, payloads, produced_scope in sites
                            if tag == arm.tag and at < len(payloads)
                        )
                        arm_scope = arm_scope.bind(binder, bindings)
                    self._stmts(arm.body, arm_scope, seat)
            case n.RunStmt():
                self._run(stmt, scope, seat)
            case n.Block():
                self._stmts(stmt.body, scope, seat)
            case _:
                assert_never(stmt)
        return self._after(stmt, scope)

    def _after_loop(self, stmt: n.Turns | n.AsBlock, scope: _ReadScope) -> _ReadScope:
        """A turn loop's body runs again after a write in it; an `as` body
        runs once."""
        return self._after(stmt.body, scope) if isinstance(stmt, n.Turns) else scope

    def _run(self, stmt: n.RunStmt, scope: _ReadScope, seat: _Seat) -> None:
        for arg in stmt.args:
            self._outside(arg, scope, seat)
        proc = self.procedures.get(stmt.name)
        if proc is None or stmt.name in self.running:
            return  # unknown, or a cycle another check refuses
        self.running.append(stmt.name)
        self.run_routes.append(self._run_crossing(proc, stmt, scope, seat))
        self.library_text.append(proc.origin is not None)
        try:
            self._run_body(proc, stmt, scope, seat)
        finally:
            self.running.pop()
            self.run_routes.pop()
            self.library_text.pop()

    def _run_crossing(
        self, proc: n.ProcedureDef, stmt: n.RunStmt, scope: _ReadScope, seat: _Seat
    ) -> _RunRoutes | None:
        """The crossings the refusals this `run` makes in `proc`'s body
        carry, when it is the game's run of a library procedure: the run
        causes a refusal of the seat deciding when some caller meets the
        procedure (decisions.md "Family libraries": a library definition is
        sound when some calling position meets it); where none does, the
        refusal is the library's own fault in every game, and carries no
        crossing. The fix offered is the first meeting caller that, written
        in place of this `run` with its own arguments, tells nothing; where
        none does, no run is offered."""
        if proc.origin is None or self.alone or (self.library_text and self.library_text[-1]):
            return None
        library = proc.origin.library
        argument = Route("run_argument", stmt.span, library, stmt.name)
        met = self._meeting_callers(proc, stmt)
        if not met:
            return _RunRoutes(None, argument)
        passing = next(
            (m for m in met if self._passing_fix(proc, stmt, m[0], scope, seat)), None
        )
        fix = _NO_RUN_FIX if passing is None else _meeting_fix(proc, stmt, *passing)
        return _RunRoutes(Route("run", stmt.span, library, stmt.name, fix), argument)

    def _meeting_callers(
        self, proc: n.ProcedureDef, stmt: n.RunStmt
    ) -> tuple[tuple[n.NameRef, str], ...]:
        """Each caller that meets `proc`, judged alone, in order: run as one
        player passed to every Player parameter, then as each Player-typed
        State Variable passed the same way, every other parameter passed a
        value reading no cards (`_made_up_run`). A caller meets it when its
        walk tells no refusal. These are every caller `_names_acting_seat`
        can prove a library's index the acting seat for: a library names no
        seat literal, no caller's binder and no routed pool, so its index is
        a parameter or a State Variable. Empty when no caller meets it."""
        key = id(stmt)
        if key in self.meeting:
            return self.meeting[key]
        seats = [(n.NameRef(_ANY_PLAYER, stmt.span, "local"), _ANY_PLAYER)] + [
            (n.NameRef(decl.name, stmt.span, "state_var"), decl.name)
            for decl in (self.game.state.decls if self.game.state is not None else ())
            if decl.type_name == "Player" and decl.index is None and not decl.optional
        ]
        found = tuple(
            (ref, spelled)
            for ref, spelled in seats
            if self._tells_nothing(
                n.AsBlock(ref, (_made_up_run(proc, stmt, ref),), stmt.span),
                _ReadScope(), _Seat("the acting seat"),
            )
        )
        self.meeting[key] = found
        return found

    def _passing_fix(
        self, proc: n.ProcedureDef, stmt: n.RunStmt, ref: n.NameRef, scope: _ReadScope,
        seat: _Seat,
    ) -> bool:
        """Whether the run `_meeting_fix` spells for `ref`, standing where
        `stmt` stands with `stmt`'s own non-seat arguments, tells nothing."""
        args = tuple(
            ref if param.type_name == "Player" else arg
            for param, arg in zip(proc.params, stmt.args)
        )
        fix = n.AsBlock(ref, (replace(stmt, args=args),), stmt.span)
        return self._tells_nothing(fix, scope, seat)

    def _tells_nothing(self, stmt: n.Stmt, scope: _ReadScope, seat: _Seat) -> bool:
        """Whether `stmt`, walked alone from `scope`, tells no refusal: a
        fresh walk, so nothing it finds reaches this walk's verdicts, with
        seat numbers past this walk's, so no proof of who acts carries in."""
        alone = _HiddenReads(self.game, DiagnosticBag(), alone=True)
        alone.collected = self.collected
        alone.trick_rounds_acting, alone.phase_stack = [], []
        alone.seats = self.seats
        alone._stmt(stmt, scope, seat)
        return alone.told == 0

    def _run_body(
        self, proc: n.ProcedureDef, stmt: n.RunStmt, scope: _ReadScope, seat: _Seat
    ) -> None:
        via: Said = "procedure " + cite_named(proc, f"`{proc.name}`")
        # The body is spliced in at the run site: the acting seat and the
        # `as` State Variable carry in; the caller's binders do not.
        body_scope = replace(scope, names=(), aliases=_ActorAliases(frozenset()))
        bound: list[_Binding] = []
        for param, arg in zip(proc.params, stmt.args):
            bound.append(_Binding(arg, scope, via))
            body_scope = body_scope.bind(param.name, (bound[-1],))
        self.run_args.append(frozenset(id(b) for b in bound))
        try:
            self._stmts(proc.body, body_scope, seat)
        finally:
            self.run_args.pop()

    def _transfer(self, stmt: n.Transfer, scope: _ReadScope, seat: _Seat) -> None:
        filtered = scope.shadow(_introduced_binders(stmt, self.flavor))
        if stmt.selection_mode != "chosen":
            if not isinstance(stmt.amount, str):
                self._outside(stmt.amount, scope, seat)
            self._outside(stmt.source, scope, seat)
            self._outside(stmt.where, filtered, seat)
            # A `to each` destination names the family whole, every seat's.
            self._outside(None if stmt.dest_each else stmt.dest, scope, seat)
            return
        if not scope.acting:
            if not stmt.dest_each:
                # A chosen movement to one zone is decided by the acting seat;
                # one `to each` is decided by each receiving seat in turn.
                self._report_no_actor("a chosen movement", (), stmt.span)
                return
            # The destination is a `to each` family, named whole.
            clauses = (stmt.amount, stmt.source, stmt.where)
            if any(
                [self._refuse_unacting_decisions(c, scope) for c in clauses if not isinstance(c, str)]
            ):
                return
        seats = {
            SEAT_ACTING: seat,
            SEAT_EACH_RECEIVER: _Seat("each receiving seat", every=True),
        }

        def judge(field: str, what: Said, reads: Iterator[ZoneRead], span: Span | None) -> None:
            decider, evaluator = CHOSEN_MOVEMENT_SEATS[(field, stmt.dest_each)]
            self._judge(
                what, reads, seats[decider], span,
                source=field == "source", evaluator=seats[evaluator],
            )

        if not isinstance(stmt.amount, str):
            judge("amount", "a chosen movement's amount", self.reads_of(stmt.amount, scope), stmt.amount.span)
        if stmt.source is not None:
            judge("source", "a chosen movement's source", self.reads_of(stmt.source, scope), stmt.source.span)
        if stmt.where is not None:
            judge("where", "a chosen movement's `where`", self.reads_of(stmt.where, filtered), stmt.where.span)
        judge(
            "dest",
            "a chosen movement's destination",
            self.reads_of(stmt.dest, scope, _LOCATE),
            stmt.dest.span,
        )


def hidden_read_verdicts(game: n.Game) -> list[HiddenReadVerdict]:
    """Every read `_check_hidden_reads` judges in a resolved game, with its
    verdict."""
    reads = _HiddenReads(game, DiagnosticBag())
    reads.run()
    return reads.verdicts


def _check_hidden_reads(game: n.Game, bag: DiagnosticBag) -> None:
    """A read of a zone at a position whose value reaches a decision must be
    one the deciders can make (decisions.md "Honest Play is assumed, so a rule
    reading concealed cards is mis-modelled"). Where no seat is deciding
    (`HIDDEN_READ_POSITIONS`' `READ_POSITION_NO_SEAT` rows) every seat must be
    able to see what the read needs; where a seat is deciding, that seat must
    -- a zone every seat sees, or the deciding seat's own instance of a zone
    its owner sees. The refusal names the announcement the rules are missing.

    After `_classify_names` (every name's `ref_kind` is stamped),
    `_validate_refs` and `_check_primitive_reads` (every call resolves, every
    `reads` name is single-membership), and `_check_functions` and
    `_check_procedures` (the call graph the reader follows is acyclic, and a
    cycle it meets is reported there)."""
    _HiddenReads(game, bag).run()
