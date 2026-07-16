"""Typecheck stage.

Infers a :class:`~cardlang.types.Type` for every expression (`infer` over a
`TypeEnv` built from declared state vars, zone contents, and the deck/stdlib
enum values) and validates: sensible player counts, assignment compatibility,
stdlib argument types, subscripting only collections, and Boolean conditions
(`if` / `repeat until` / phase qualifiers). It accepts the whole corpus and
rejects real type errors.

Pragmatic by design: unrefined positions (pronoun member access, lambda values,
the `Resource`/`ChipStack` query API) infer the permissive `TAny`, which
propagates without error. Deferred to later stages: variant outcome types and
exhaustiveness (`TVariant`), user-defined `type` declarations (`TStruct`), full
`ZoneContents`/`Resource` typing, and payload-type narrowing.

Like :mod:`cardlang.resolve`, this annotates rather than rewrites: the
(unchanged) :class:`Game` flows on, and the IR stays at the resolved-AST level.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterator, Mapping, assert_never

from cardlang.ast import nodes as n
from cardlang.ast.nodes import Game
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.domains import role_type as _role_type
from cardlang.stdlib.round_state import ROUND_STATE_FIELDS
from cardlang.stdlib.signatures import CALL_SIGS, ZONE_CONTENT, Sig
from cardlang.stdlib.values import DIRECTION_VALUES, deck_ranks, deck_suits
from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TNull,
    TOptional,
    TPlayer,
    TString,
    TStruct,
    TTeam,
    TVariant,
    Type,
    assignable,
    subscriptable,
    unify,
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

# The closed set of built-in declared-type names (scalars + enums). resolve
# validates every declaration's type_name against this set plus the game's
# own struct names, so a typo ('Integar') is a diagnostic, never a silent
# TAny (closed-domain completeness, decisions.md).
KNOWN_TYPE_NAMES: frozenset[str] = frozenset(_SCALAR_TYPES) | _ENUM_TYPES

# A card's fields are a closed pair. One registry, shared by `infer` (typing
# a known-Card member access) and `_check_expr` (rejecting anything else) —
# a third field can be added to this dict and both sites see it; before this
# was two hand-enumerated pairs that could (and did) drift.
CARD_FIELDS: dict[str, Type] = {"rank": TEnum("Rank"), "suit": TEnum("Suit")}

# `action` fields whose type is the same for every move type: the runtime
# `Move` payload (cardlang/runtime/state.py) carries exactly `card: Card` and
# `actor: Player`, always both present, for every move type. This is the
# sound subset of `action`'s shape — full move-type-aware typing (the
# per-move-type params reachable only as `action.<param name>`, e.g. an
# auction bid's `action.amount`) is out of scope; a field not in this
# registry stays `TAny` (residual — see the ledger in
# tests/test_zone_family_typing.py and roadmap.md).
ACTION_FIELDS: dict[str, Type] = {"card": TCard(), "actor": TPlayer()}

# stdlib functions whose result depends on a declared `ranking:` (they index
# `ctx.rs.rank_index`, empty when the game declares none — runtime/stdlib.py
# `rank_value` reads it unguarded and would KeyError). resolve.py already
# gates a bare `Rank` move-parameter domain on the same `has_ranking`
# condition (`_check_move_params`); this is the analogous compile-time gate
# for a *call*. A registry, not an `if`, so the next ranking-dependent
# function joins a set instead of a new branch.
RANKING_GATED_FUNCS: frozenset[str] = frozenset({"rank_value"})


def type_from_name(
    name: str, optional: bool, structs: Mapping[str, TStruct] | None = None
) -> Type:
    """Map a declared type name (a `StateDecl` `type_name`) to a `Type`.

    User-defined struct names resolve to their `TStruct` (via the ``structs``
    registry); names unknown to scalars, enums, and the registry resolve to the
    permissive `TAny`. ``optional`` wraps the result in `TOptional`.
    """
    base: Type
    if name in _SCALAR_TYPES:
        base = _SCALAR_TYPES[name]()
    elif name in _ENUM_TYPES:
        base = TEnum(name)
    elif structs is not None and name in structs:
        base = structs[name]
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
    # Membership comes from the deck alone (Coup/Tarot declare no
    # `ranking:`). resolve's `_resolve_ranking` guarantees ranking ⊆ deck
    # ranks (an unknown rank is a resolve-time error), and resolve always
    # runs before typecheck (cardlang/pipeline.py's `_check`), so unioning
    # `game.ranking` in here would add nothing beyond order.
    for rank in deck_ranks(game.deck):
        m[rank] = TEnum("Rank")
    for direction in DIRECTION_VALUES:
        m[direction] = TEnum("Direction")
    return m


def struct_registry(game: Game) -> dict[str, TStruct]:
    """Build the user-defined struct types. Declared fields resolve eagerly;
    derived fields are typed in an env of the declared fields, so each `TStruct`
    carries both declared and derived field types under one mapping.

    Structs are built in source order: a field whose type is another user type
    only resolves if that type was declared earlier (forward references resolve
    to `TAny` — acceptable for Stage 2)."""
    structs: dict[str, TStruct] = {}
    for tdef in game.types:
        fields: dict[str, Type] = {}
        for f in tdef.fields:
            fields[f.name] = type_from_name(f.type_name, f.optional, structs)
        field_env = TypeEnv(locals=dict(fields), structs=structs)
        for d in tdef.derived:
            fields[d.name] = infer(d.value, field_env)
        structs[tdef.name] = TStruct(
            name=tdef.name,
            fields=fields,
            derived=frozenset(d.name for d in tdef.derived),
        )
    return structs


def _payload_type(name: str, structs: Mapping[str, TStruct]) -> "Type":
    """Resolve a variant payload type name; a trailing `?` marks it nullable."""
    if name.endswith("?"):
        return type_from_name(name[:-1], True, structs)
    return type_from_name(name, False, structs)


def _variant_cases(
    cases: tuple[n.VariantCase, ...], structs: Mapping[str, TStruct]
) -> dict[str, tuple["Type", ...]]:
    return {
        c.tag: tuple(_payload_type(t, structs) for t in c.payload_types) for c in cases
    }


def variant_registry(
    game: Game, structs: Mapping[str, TStruct]
) -> dict[str, TVariant]:
    """Build the variant-outcome type of each `define` and each outcome-declaring
    `phase`: its case tags mapped to their declared payload types."""
    variants: dict[str, TVariant] = {}
    for d in game.defines:
        variants[d.name] = TVariant(name=d.name, cases=_variant_cases(d.cases, structs))
    for phase in _all_phases(game):
        if phase.outcome_cases:
            variants[phase.name] = TVariant(
                name=phase.name, cases=_variant_cases(phase.outcome_cases, structs)
            )
    return variants


@dataclass(frozen=True)
class TypeEnv:
    """The types a bare name resolves against during inference: declared state
    vars, zone contents, deck/stdlib enum values, and scoped local binders."""

    state_vars: Mapping[str, Type] = field(default_factory=dict)
    zones: Mapping[str, Type] = field(default_factory=dict)
    # Zone FAMILIES (`hand[player]`, `captured[team]`) only, name -> the type
    # a subscript's index expression must be `assignable` to. A family zone's
    # bare name (no subscript) still resolves through `zones` above to its
    # content type — unaffected; this map exists so `Subscript` can tell a
    # family instance (`hand[p]`, itself a collection) apart from the generic
    # collection-element indexing every other subscript does.
    zone_families: Mapping[str, Type] = field(default_factory=dict)
    value_enums: Mapping[str, TEnum] = field(default_factory=dict)
    locals: Mapping[str, Type] = field(default_factory=dict)
    structs: Mapping[str, TStruct] = field(default_factory=dict)
    functions: Mapping[str, Sig] = field(default_factory=dict)  # user functions
    # User procedures, name -> declared parameter types (`Sig.ret` is unused: a
    # procedure is a statement, not an expression). This is what makes a
    # procedure's parameter annotations load-bearing rather than decorative —
    # `run` sites check their arguments against them exactly as a call checks its
    # arguments against a function signature. It is also why expansion runs AFTER
    # typecheck (cardlang/expand.py): once a body is spliced inline there is no
    # call site left to check.
    procedures: Mapping[str, Sig] = field(default_factory=dict)
    has_ranking: bool = False  # bool(game.ranking) — gates RANKING_GATED_FUNCS

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
        case n.Subscript():
            # A zone-FAMILY subscript (`hand[p]`) denotes one zone instance —
            # its type is the zone's *content* type (a collection), never the
            # element a generic collection subscript yields (Finding 1: the
            # old flat `element`-of-collection read `hand[p]` as a single
            # Card, degrading every aggregation/membership use downstream to
            # TAny or a spurious rejection). A non-family subscript (a state
            # var, a `[…]` list, a query result) keeps the generic behavior.
            obj_ref = e.obj
            if isinstance(obj_ref, n.NameRef) and obj_ref.ref_kind == "zone":
                family = env.zone_families.get(obj_ref.name)
                if family is not None:
                    return env.zones.get(obj_ref.name, TCollection(TAny(), zone=True))
            obj = infer(e.obj, env)
            return obj.element if isinstance(obj, TCollection) else TAny()
        case n.Call():
            sig = CALL_SIGS.get(e.func) or env.functions.get(e.func)
            return sig.ret if sig is not None else TAny()
        case n.BinOp():
            if e.op in ("==", "!=", "<", ">", "<=", ">=", "and", "or", "in"):
                return TBoolean()
            if e.op in ("+", "-", "*"):
                return TInteger()
            if e.op == "offset_by":
                # Seat arithmetic yields a seat, whatever the walk knows about
                # the operand — a binder-rooted receiver ((p offset_by left),
                # p untyped by the flat walk) must still hit the dot-form
                # rejection rather than fall through to a runtime assert.
                return TPlayer()
            return TAny()  # any future operators
        case n.Not() | n.IsCheck() | n.Quantifier():
            return TBoolean()
        case n.Choose():
            return TInteger()
        case n.Comprehension():
            return TInteger() if e.agg == "sum" else TAny()
        case n.PlayerQuery():
            match e.kind:
                case "set":
                    return TCollection(TPlayer())
                case "count":
                    return TInteger()
                case _:  # "pick"
                    return TPlayer()
        case n.CardQuery():
            match e.kind:
                case "set":
                    return TCollection(TCard())
                case "count":
                    return TInteger()
                case _:  # "any" | "all"
                    return TBoolean()
        case n.IfExpr():
            return _ifexpr_type(e, env)
        case n.StructLit():
            return env.structs.get(e.type_name, TAny())
        case n.Member():
            # `action.card` / `action.actor`: the sound subset of the `action`
            # pronoun's shape (Finding 3) — typed directly off the pronoun,
            # not off `infer(e.obj, env)` (which stays TAny for `action`
            # itself, since most of its shape is move-type-specific).
            obj_ref = e.obj
            if (
                isinstance(obj_ref, n.NameRef)
                and obj_ref.ref_kind == "pronoun"
                and obj_ref.name == "action"
                and e.field in ACTION_FIELDS
            ):
                return ACTION_FIELDS[e.field]
            if (
                isinstance(obj_ref, n.NameRef)
                and obj_ref.ref_kind == "pronoun"
                and obj_ref.name == "state"
                and e.field in ROUND_STATE_FIELDS
            ):
                # The round's published state, typed off the registry rather than
                # left `TAny`. `TAny` was contagious here: `card.suit is state.idx`
                # compared a Suit to an Integer and slipped past the enum wall
                # because the right side was untyped. An unpublished field never
                # reaches this branch — `_check_expr` rejects it.
                return ROUND_STATE_FIELDS[e.field]
            obj = infer(e.obj, env)
            if isinstance(obj, TStruct):
                return obj.fields.get(e.field, TAny())
            if isinstance(obj, TCard):
                # A card's fields are a closed pair; `_check_expr` rejects
                # anything else on a known-Card receiver.
                return CARD_FIELDS.get(e.field, TAny())
            return TAny()  # pronoun member access / sugar: deferred
        case n.ListLit():
            elem: Type | None = infer(e.elements[0], env)
            for item in e.elements[1:]:
                elem = unify(elem, infer(item, env)) if elem is not None else None
            return TCollection(elem if elem is not None else TAny())
        case _ as unreachable:
            assert_never(unreachable)


def _ifexpr_type(e: n.IfExpr, env: TypeEnv) -> Type:
    result = infer(e.then, env)
    for _cond, branch in e.elifs:
        merged = unify(result, infer(branch, env))
        result = merged if merged is not None else TAny()
    merged = unify(result, infer(e.otherwise, env))
    return merged if merged is not None else TAny()


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
            return TNull()  # the `none` literal — assignable only to optionals
        case "pronoun":
            # `actor` is universally the acting player at runtime
            # (evaluate._pronoun -> ctx.current_player, and the `Move`
            # payload's own `actor` field is a bare `Player`, never
            # optional) — the other pronouns (`action`, `outcome`,
            # `state`, `active_rules`) stay TAny; their shape is
            # move-type/mechanic-specific (see ACTION_FIELDS for the
            # sound subset of `action` typed via Member access).
            return TPlayer() if e.name == "actor" else TAny()
        case _:
            return TAny()  # function / unresolved


def _type_name(t: Type) -> str:
    if isinstance(t, TNull):
        return "none"
    if isinstance(t, TOptional):
        return f"{_type_name(t.inner)}?"
    if isinstance(t, TCollection):
        return f"Collection<{_type_name(t.element)}>"
    if isinstance(t, TEnum):
        return t.name
    if isinstance(t, (TStruct, TVariant)):
        # These carry their declared name. Before the general disjointness rule
        # below, no wall ever printed one, so both rendered as the bare kind — which
        # made "comparing Struct with Struct can never be equal" read as nonsense.
        return t.name
    return type(t).__name__[1:]  # TInteger -> "Integer", TPlayer -> "Player", …


def _state_blocks(game: Game) -> list[n.StateBlock]:
    blocks: list[n.StateBlock] = []
    if game.state is not None:
        blocks.append(game.state)

    def rec(phase: n.Phase) -> None:
        for item in phase.items:
            if isinstance(item, n.StateBlock):
                blocks.append(item)
            elif isinstance(item, n.Phase):
                rec(item)

    for phase in game.phases:
        rec(phase)
    return blocks


def env_from_game(game: Game) -> TypeEnv:
    """Build the top-level type environment: declared state vars (value types),
    zone contents, the deck/stdlib enum value map, and the user struct types."""
    structs = struct_registry(game)
    state_vars: dict[str, Type] = {}
    for block in _state_blocks(game):
        for decl in block.decls:
            t = type_from_name(decl.type_name, decl.optional, structs)
            # An indexed state var (`score[player]`) is a per-key map — a
            # collection whose subscript yields the declared value type, KEYED
            # by the index domain's binder type so a wrong-domain key
            # (`score[hearts]`, `n[9]`'s read twin) is a check-time error, not
            # a raw KeyError mid-playout.
            state_vars[decl.name] = (
                TCollection(t, key=_role_type(decl.index))
                if decl.index is not None
                else t
            )
    # The fallback carries zone=True like its twin in `infer`'s zone-family
    # subscript arm: it describes an (unknown-typed) ZONE's contents, and an
    # unflagged default would falsely reject every use of that zone at the
    # endpoint walls. Unreachable today only by pass ordering (resolve raises
    # on unknown zone types first) — kept truthful, not load-bearing.
    zones: dict[str, Type] = {
        z.name: ZONE_CONTENT.get(z.type_ref.name, TCollection(TAny(), zone=True))
        for z in game.zones
    }
    # `ZoneDecl.index` is `None` (a singleton zone) or one of the closed index
    # roles resolve.py validates (the domain table's `ZONE_INDEX_ROLES`); a
    # family's subscript key types as the index domain's binder type — the same
    # table cell `for each <role>` reads, so `hand[p]` and `captured[t]` key by
    # TPlayer/TTeam without this site re-spelling the role list. (`role_type`'s
    # TAny fallback covers the unresolved-role case, whose diagnostic resolve
    # already owns.)
    zone_families: dict[str, Type] = {
        z.name: _role_type(z.index) for z in game.zones if z.index is not None
    }
    return TypeEnv(
        state_vars=state_vars,
        zones=zones,
        zone_families=zone_families,
        value_enums=value_enum_map(game),
        structs=structs,
        has_ranking=bool(game.ranking),
    )


# A statement's enclosing binders, outermost first. A loop or parameter binder
# carries its Type directly; a `let` binder carries its `LetStmt` NODE, because
# its type is its initializer's inferred type *in the environment at that
# point* — which only the consumer holds. `_scoped_env` resolves both kinds.
_Binders = tuple[tuple[str, "Type | n.LetStmt"], ...]


def _scoped_env(env: TypeEnv, binders: _Binders) -> TypeEnv:
    """The environment a statement sees: binders folded in scope order, with a
    `let` binder typed here by inferring its initializer in the environment
    built so far (earlier binders are visible — the walk's sequential fold
    guarantees that is exactly the let's own scope). The indexed form
    (`let base[p] = E`) is a per-player map: `p` types as Player inside E
    only, and `base` as a collection of E's type. This is what closed the
    let-TAny gap: a `let`-bound name used to infer `TAny` everywhere, so every
    wall went dark one binding away (`hearts is 3` rejected; `let z = hearts`
    then `z is 3` accepted)."""
    for name, bound in binders:
        if isinstance(bound, n.LetStmt):
            if bound.index is not None:
                element = infer(bound.value, env.with_local(bound.index, TPlayer()))
                env = env.with_local(name, TCollection(element, key=TPlayer()))
            else:
                env = env.with_local(name, infer(bound.value, env))
        else:
            env = env.with_local(name, bound)
    return env


def _stmt_tree_scoped(
    s: n.Stmt, binders: _Binders = ()
) -> Iterator[tuple[n.Stmt, _Binders]]:
    """The statement tree, each statement paired with the loop binders in
    scope at that point — the single traversal every statement walk views.

    Exhaustive over `Stmt`: a compound statement whose body this walk missed
    would leave that whole body unchecked (no expression walls, no semantic
    checks — accepted-but-ignored at subtree scale), so "descends nothing" is
    a decision each leaf kind states by name, never a default."""
    yield s, binders
    match s:
        case n.ForEach():
            yield from _stmt_tree_scoped(
                s.body, binders + ((s.binder, _role_type(s.role)),)
            )
        case n.EachSimultaneous():
            yield from _stmt_tree_scoped(
                s.body, binders + ((s.role, _role_type(s.role)),)
            )
        case n.RepeatUntil():
            yield from _seq_tree_scoped(s.body, binders)
        case n.IfStmt():
            yield from _seq_tree_scoped(s.then_body, binders)
            yield from _seq_tree_scoped(s.else_body or (), binders)
        case n.Block():
            # Synthetic, and created only by `expand`, which runs AFTER this
            # pass — so nothing here ever sees one today. The arm exists anyway:
            # a future pass ordering that did reach a block must not skip its
            # whole body without a word.
            yield from _seq_tree_scoped(s.body, binders)
        case n.Produces():
            # A deliberate leaf, not an oversight: arm bodies bind the arm's
            # payload binders, which this walk cannot know (they come from the
            # variant registry). `_check_produces` runs the scoped sub-walk over
            # each arm body with those binders typed, and the outcome-plumbing
            # walks (`_produces_in`, `_control_flow_nodes`) descend arms
            # themselves.
            pass
        case (
            n.Movement() | n.EpistemicOp() | n.RotateStmt() | n.LetStmt()
            | n.AssignStmt() | n.Offer() | n.Round() | n.Produce()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt()
        ):
            pass  # no child statements
        case _:
            assert_never(s)


def _seq_tree_scoped(
    stmts: tuple[n.Stmt, ...], binders: _Binders
) -> Iterator[tuple[n.Stmt, _Binders]]:
    """A statement SEQUENCE with the sequential-`let` fold: a `let` binds its
    name for the REST of the tuple — the same fold resolve's `_rewrite_value`
    applies when it scopes the name, and the runtime's `run_body` applies when
    it binds the value. Every statement-tuple walk routes through here, so the
    three passes cannot disagree about where a `let` is visible."""
    current = binders
    for s in stmts:
        yield from _stmt_tree_scoped(s, current)
        if isinstance(s, n.LetStmt):
            current = current + ((s.name, s),)


def _stmt_tree(s: n.Stmt) -> Iterator[n.Stmt]:
    yield from (st for st, _ in _stmt_tree_scoped(s))


def _phase_statements_scoped(
    phase: n.Phase, binders: _Binders = ()
) -> Iterator[tuple[n.Stmt, _Binders]]:
    # The sequential-`let` fold runs across phase ITEMS too, and carries into
    # nested phases that follow the let — mirroring resolve's Phase fold and
    # the driver, which passes the threaded context into `run_phase`. HOOKS
    # deliberately get the phase-ENTRY binders, not the fold's: `before_each`/
    # `after_each` run at iteration boundaries with the entry context, before
    # any body `let` has executed, and resolve rejects a hook reading one.
    current = binders
    for item in phase.items:
        match item:
            case n.Phase():
                yield from _phase_statements_scoped(item, current)
            case n.BeforeEach() | n.AfterEach():
                yield from _seq_tree_scoped(item.body, binders)
            case n.StateBlock() | n.ActiveRules() | n.LegalMoves() | n.TransitionTo():
                pass  # configuration blocks hold no statements
            case _:
                # The residue of PhaseItem is exactly Stmt — mypy checks that on
                # this call, so a new phase-item block kind fails here loudly
                # instead of being walked as a statement.
                yield from _stmt_tree_scoped(item, current)
                if isinstance(item, n.LetStmt):
                    current = current + ((item.name, item),)


def _non_define_statements(game: Game) -> Iterator[n.Stmt]:
    """Every statement outside a `define` body — where `produce` is illegal."""
    for move_type in game.move_types:
        for s in move_type.effect:
            yield from _stmt_tree(s)
    for phase in game.phases:
        yield from (st for st, _ in _phase_statements_scoped(phase))


def _move_param_binders(move_type: n.MoveTypeDef) -> _Binders:
    """A move type's parameters, typed from their declarations — bound in its
    guard and effect exactly as procedure parameters are bound in their body.
    They used to be bound by resolve and NEVER typed, so `move_type m(s :
    Suit) { when: s is 3 … }` passed both positions while the inline spelling
    was rejected — the let-laundering shape, one binder kind over."""
    env = TypeEnv()
    return tuple((p.name, _param_type(p, env)) for p in move_type.params)


def _all_statements_scoped(game: Game) -> Iterator[tuple[n.Stmt, _Binders]]:
    for move_type in game.move_types:
        yield from _seq_tree_scoped(move_type.effect, _move_param_binders(move_type))
    for phase in game.phases:
        yield from _phase_statements_scoped(phase)
    for define in game.defines:
        yield from _seq_tree_scoped(define.body, ())
    # A procedure body is checked ONCE, here, at its declaration — with its
    # parameters bound to their declared types, which is what gives those
    # annotations force. It is not re-checked after expansion, because expansion
    # runs after this pass; the `run` sites check their arguments against the same
    # declared types, so the spliced result is covered from both ends.
    env = TypeEnv()
    for proc in game.procedures:
        binders: _Binders = tuple((p.name, _param_type(p, env)) for p in proc.params)
        yield from _seq_tree_scoped(proc.body, binders)


def _all_statements(game: Game) -> Iterator[n.Stmt]:
    yield from (st for st, _ in _all_statements_scoped(game))


def _arg_exprs(args: tuple[n.Arg, ...]) -> list[n.Expr]:
    """The positional expression arguments of a call (named args are not used by
    the stdlib functions/methods being checked)."""
    return [a for a in args if not isinstance(a, n.NamedArg)]


def _child_exprs(e: n.Expr) -> list[n.Expr]:
    """Every expression's direct sub-expressions — exhaustive over `Expr`, so a
    new expression kind must declare its children (or its leafhood) here before
    anything compiles. A missed kind wouldn't crash anything; its children
    would simply never be walked, and every wall inside them would go dark."""
    match e:
        case n.Member():
            return [e.obj]
        case n.ListLit():
            return list(e.elements)
        case n.StructLit():
            return [fi.value for fi in e.fields]
        case n.Subscript():
            return [e.obj, e.index]
        case n.Call():
            return _arg_exprs(e.args)
        case n.BinOp():
            return [e.left, e.right]
        case n.Not() | n.IsCheck():
            return [e.operand]
        case n.Quantifier():
            return [e.body]
        case n.Comprehension():
            out = [e.source, e.body]
            if e.filter is not None:
                out.append(e.filter)
            if e.default is not None:
                out.append(e.default)
            return out
        case n.Choose():
            return [e.lo, e.hi]
        case n.PlayerQuery():
            return [e.pred]
        case n.CardQuery():
            return [e.source, e.pred] if e.pred is not None else [e.source]
        case n.IfExpr():
            out = [e.cond, e.then]
            for cond, branch in e.elifs:
                out += [cond, branch]
            out.append(e.otherwise)
            return out
        case n.NameRef() | n.IntLit() | n.StrLit() | n.CardLiteral() | n.AllPlayers():
            return []  # leaves
        case _:
            assert_never(e)


def _called_functions(e: n.Expr, fn_names: set[str]) -> set[str]:
    """The user-function names called anywhere in `e`."""
    out: set[str] = set()
    if isinstance(e, n.Call) and e.func in fn_names:
        out.add(e.func)
    for child in _child_exprs(e):
        out |= _called_functions(child, fn_names)
    return out


def _function_sigs(game: Game, env: TypeEnv, bag: DiagnosticBag) -> dict[str, Sig]:
    """Each user function's signature: declared parameter types and the return type
    inferred from the body. Built in dependency order (callees first — the call
    graph is acyclic, enforced by resolve) so a body's calls see their callees'
    return types; each body is checked against its parameters."""
    func_defs = {f.name: f for f in game.functions}
    fn_names = set(func_defs)
    sigs: dict[str, Sig] = {}

    def param_type(p: n.MoveParam) -> Type:
        optional = p.type_name.endswith("?")
        base = p.type_name[:-1] if optional else p.type_name
        return type_from_name(base, optional, env.structs)

    def visit(name: str, on_stack: frozenset[str]) -> None:
        if name in sigs or name in on_stack:  # done, or a cycle resolve already flagged
            return
        f = func_defs[name]
        for callee in _called_functions(f.body, fn_names):
            visit(callee, on_stack | {name})
        func_env = replace(env, functions=sigs)
        param_types: list[Type] = []
        for p in f.params:
            t = param_type(p)
            param_types.append(t)
            func_env = func_env.with_local(p.name, t)
        _check_expr(f.body, func_env, bag)
        sigs[name] = Sig(tuple(param_types), infer(f.body, func_env))

    for fname in func_defs:
        visit(fname, frozenset())
    return sigs


def _param_type(p: n.MoveParam, env: TypeEnv) -> Type:
    optional = p.type_name.endswith("?")
    base = p.type_name[:-1] if optional else p.type_name
    return type_from_name(base, optional, env.structs)


def _procedure_sigs(game: Game) -> dict[str, Sig]:
    """Each user procedure's parameter types. No dependency order is needed (a
    procedure may not run another — resolve rejects it) and there is no return
    type: `Sig.ret` is `TAny` and never read. The bodies themselves are checked by
    the statement walk, which binds these same parameter types as locals."""
    env = TypeEnv()  # `type_from_name` needs structs only for struct params, which
    # the procedure param domain does not admit (resolve gates it to Player).
    return {
        p.name: Sig(tuple(_param_type(x, env) for x in p.params), TAny())
        for p in game.procedures
    }


def _enum_domain(env: TypeEnv, enum_name: str) -> frozenset[str]:
    """Every value of a deck/stdlib enum, from the value->enum map."""
    return frozenset(v for v, t in env.value_enums.items() if t.name == enum_name)


def _check_enum_operand(
    enum: TEnum, other: n.Expr, other_bare: Type, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """The enum-comparison wall: an equality (or membership element) against a
    known enum-typed operand must be able to be true. Cross-enum comparisons,
    Integer operands (a bare `10` is an Integer, never the rank "10"), and
    string literals outside the enum's value set are all silently-false traps
    at run time — reject them here. A name-form value written as a string is
    a second spelling of the bare literal and is rejected too (one spelling
    per concept). Non-literal String expressions stay unchecked (gradual);
    every OTHER concrete type (Card, Player, Boolean, a collection, …) is
    rejected by the default arm — an enum value equals only a value of its
    own enum, so the wall is total over the operand-type axis, not just the
    three shapes that motivated it."""
    if isinstance(other_bare, TEnum):
        if other_bare.name != enum.name:
            bag.error(
                f"comparing {enum.name} with {other_bare.name} can never be "
                f"equal",
                other.span,
            )
        return
    if isinstance(other_bare, TInteger):
        hint = (
            ' — numeric ranks are written as strings ("10")'
            if enum.name == "Rank"
            else ""
        )
        bag.error(
            f"comparing {enum.name} with Integer can never be equal{hint}",
            other.span,
        )
        return
    if isinstance(other, n.StrLit):
        domain = _enum_domain(env, enum.name)
        if other.value not in domain:
            bag.error(
                f'"{other.value}" is not a {enum.name} value of this deck',
                other.span,
            )
        elif not other.value.isdigit():
            bag.error(
                f"write the {enum.name} value bare — {other.value}, not "
                f'"{other.value}" (strings spell only the numeric ranks, '
                f"which would otherwise read as Integers)",
                other.span,
            )
        return
    if isinstance(other_bare, TAny):
        # Gradual: an unrefined `infer` arm must not manufacture errors.
        #
        # `TString` used to return here too, on the grounds that a String-typed
        # variable holding a rank NAME was the one shape that could genuinely equal
        # an enum value — which was Coup's `card.rank is block_claim`, where
        # `block_claim` was a `String`. That was never a feature; it was a
        # silently-false comparison with a carve-out around it, and the cure was to
        # give the variable its real type (`block_claim : Rank?`), which Coup now
        # has. No corpus game declares a String at all. So String is walled like any
        # other disjoint type, and a string LITERAL is still checked against the
        # deck's values by the branch above (`card.rank is "10"`, the numeric-rank
        # spelling).
        return
    hint = (
        " — compare the whole card (`x is Q of spades`) or a field against "
        "its own kind (`x.suit is spades`)"
        if isinstance(other_bare, TCard)
        else ""
    )
    bag.error(
        f"comparing {enum.name} with {_type_name(other_bare)} can never be "
        f"equal{hint}",
        other.span,
    )


# --- BinOp operand walls: one dispatcher over the operator-class registry ---
#
# `infer`'s BinOp arm (above) is the operator registry: every op string a
# `BinOp` node can carry. `OP_CLASSES` classifies each into the operand-shape
# family that determines what a *sound* operand looks like — this is a
# second, independent read of the same registry (not derived from
# `infer`'s tuples in code, since their grouping is by *result* type, not
# operand legality), so `tests/test_operator_walls.py` pins the two against
# each other: a new operator landing in `infer` without a matching
# `OP_CLASSES` entry fails that test instead of silently reaching runtime
# unwalled.


class OpClass(Enum):
    EQUALITY = "equality"
    ORDERING = "ordering"
    ARITHMETIC = "arithmetic"
    LOGICAL = "logical"
    MEMBERSHIP = "membership"
    OFFSET_BY = "offset_by"


OP_CLASSES: dict[str, OpClass] = {
    "==": OpClass.EQUALITY,
    "!=": OpClass.EQUALITY,
    "<": OpClass.ORDERING,
    ">": OpClass.ORDERING,
    "<=": OpClass.ORDERING,
    ">=": OpClass.ORDERING,
    "+": OpClass.ARITHMETIC,
    "-": OpClass.ARITHMETIC,
    "*": OpClass.ARITHMETIC,
    "and": OpClass.LOGICAL,
    "or": OpClass.LOGICAL,
    "in": OpClass.MEMBERSHIP,
    "offset_by": OpClass.OFFSET_BY,
}


def _op_class(op: str) -> OpClass:
    cls = OP_CLASSES.get(op)
    if cls is None:
        # A future operator reached `infer`'s BinOp arm without an entry
        # here — loud, not a silent unwalled pass-through.
        raise AssertionError(
            f"operator '{op}' has no entry in OP_CLASSES — every BinOp "
            "operator the parser builds must be classified (surface "
            "totality, decisions.md); add it to the registry"
        )
    return cls


def _bare(t: Type) -> Type:
    """Unwrap a `T?` to `T` for operand-shape checks — an optional operand
    rejects/accepts exactly like its payload (sweep-the-class: every operand
    wall in this module applies to the optional wrapper of its rejection
    domain, not just the bare form)."""
    return t.inner if isinstance(t, TOptional) else t


def _check_binop(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    cls = _op_class(e.op)
    match cls:
        case OpClass.EQUALITY:
            _check_equality_operands(e, env, bag)
        case OpClass.ORDERING:
            _check_ordering_operands(e, env, bag)
        case OpClass.ARITHMETIC:
            _check_arithmetic_operands(e, env, bag)
        case OpClass.LOGICAL:
            _check_logical_operands(e, env, bag)
        case OpClass.MEMBERSHIP:
            _check_membership_operands(e, env, bag)
        case OpClass.OFFSET_BY:
            _check_offset_by_operands(e, env, bag)
        case _ as unreachable:
            assert_never(unreachable)


def _check_equality_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`==`/`!=` (surface `is`/`is not`): two operands can only be equal if one's
    type is assignable to the other's. Anything else is a comparison that is
    *always false* — the silently-wrong shape this wall exists to catch.

    The enum rows come first and keep their own nuanced diagnostics
    (`_check_enum_operand`: the name-form-vs-string spelling, the not-a-value-of-
    this-deck message, the Rank-vs-Integer hint). Every other pair falls to the
    general disjointness rule below.

    That general rule is new, and it closes a hole the enum-centric wall left wide:
    the wall only ever fired when one side was a `TEnum`, so `Boolean` had no row
    at all (`flag is hearts`, `flag is 1`, `flag is "x"` all passed), and neither
    did `Integer is "x"` or `Player is "x"`. It was found by typing the round-state
    pronoun (stdlib/round_state.py): `state.trick_terminated_early` became a real
    `Boolean` and immediately exposed that comparing one to a suit was accepted.
    Per decisions.md "Closed-domain completeness", the fix sweeps the class rather
    than patching the instance — the class being "equality between disjoint
    concrete types", and the layer that owns it being the type layer every
    comparison consults.

    `TAny` passes on either side (gradual typing — an unrefined `infer` arm must
    not manufacture errors). `Player`/`Integer` stay comparable in BOTH directions
    because a player IS an integer seat here (`assignable(TInteger, TPlayer)`), so
    `turn is 0` and `responder is actor` keep working."""
    lbare, rbare = _bare(infer(e.left, env)), _bare(infer(e.right, env))
    if isinstance(lbare, TEnum):
        _check_enum_operand(lbare, e.right, rbare, env, bag)
        return
    if isinstance(rbare, TEnum):
        _check_enum_operand(rbare, e.left, lbare, env, bag)
        return
    if isinstance(lbare, TAny) or isinstance(rbare, TAny):
        return
    compatible = (
        assignable(lbare, rbare)
        or assignable(rbare, lbare)
        # `unify` as well as `assignable`, because `assignable` honours `TAny` only at
        # the TOP level: a deliberately-unrefined element type (a chip stack is
        # `Collection<Any>` precisely because that part of the object model is
        # unrefined) would be judged disjoint from `Collection<Card>`, and this wall
        # would MANUFACTURE an error — the exact thing its own gradual-typing promise
        # forbids. `assignable` alone is also not enough in the other direction, so
        # both are consulted: `Player`/`Integer` must stay comparable (a player IS an
        # integer seat), and only `assignable` says so.
        or unify(lbare, rbare) is not None
    )
    if not compatible:
        bag.error(
            f"comparing {_type_name(lbare)} with {_type_name(rbare)} can never be "
            f"equal",
            e.span,
        )


def _check_ordering_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`< > <= >=`: only Integers have an order in this language. A concrete
    Rank operand is the plausible mistake (its declared order lives in
    `ranking:`, not code-point order — Python would compare the rank
    *strings*, e.g. "10" < "9"), so it gets a named fix; every other
    concrete non-Integer operand (another enum, Boolean, Card, Player, Team,
    a collection) is equally nonsensical and rejected the same way.
    TAny/TInteger pass (gradual)."""
    for operand in (e.left, e.right):
        bare = _bare(infer(operand, env))
        if isinstance(bare, (TAny, TInteger)):
            continue
        if isinstance(bare, TEnum) and bare.name == "Rank":
            bag.error(
                f"'{e.op}' compares Integers — enum values have no "
                "arithmetic order — compare strength via rank_value(...)",
                operand.span,
            )
        elif isinstance(bare, TEnum):
            bag.error(
                f"'{e.op}' compares Integers — {bare.name} enum values have "
                "no arithmetic order",
                operand.span,
            )
        else:
            bag.error(
                f"'{e.op}' compares Integers, got {_type_name(bare)}",
                operand.span,
            )


def _check_arithmetic_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`+ - *`: only Integers are numeric in this language. A concrete enum
    operand is the worst case here — `+` string-concatenates it at runtime
    instead of raising, so a bug like `card.rank + 1` reads as legal and is
    silently wrong every time it runs. Every other concrete non-Integer
    operand rejects the same way as ordering. TAny/TInteger pass."""
    for operand in (e.left, e.right):
        bare = _bare(infer(operand, env))
        if isinstance(bare, (TAny, TInteger)):
            continue
        if isinstance(bare, TEnum) and bare.name == "Rank":
            bag.error(
                f"'{e.op}' expects Integer operands — enum values have no "
                "numeric value — compare strength via rank_value(...)",
                operand.span,
            )
        elif isinstance(bare, TEnum):
            bag.error(
                f"'{e.op}' expects Integer operands, got {bare.name} — an "
                "enum value concatenates as a string at runtime, not adds",
                operand.span,
            )
        else:
            bag.error(
                f"'{e.op}' expects Integer operands, got {_type_name(bare)}",
                operand.span,
            )


def _check_logical_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`and or`: both operands must be Boolean. This walls the operator's own
    operands, independent of `_check_bool` on whatever *contains* the
    expression — `if (a and 3) { … }` is Boolean overall (`and`'s `infer()`
    arm is a fixed `TBoolean`, regardless of its operands), so a top-level
    Boolean check on the whole `if` condition never sees the smuggled
    Integer. TAny passes (gradual)."""
    for operand in (e.left, e.right):
        bare = _bare(infer(operand, env))
        if not isinstance(bare, (TAny, TBoolean)):
            bag.error(
                f"'{e.op}' expects Boolean operands, got {_type_name(bare)}",
                operand.span,
            )


def _check_membership_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`in`: the right-hand side must be a collection (unchanged wall); the
    left operand must be a plausible element of it. A `[...]` literal against
    a known enum-typed left operand keeps the existing per-element literal
    validation (`card.rank in [A, "10"]` — doppelkopf), since that catches
    misspelled/mistyped *literals* `unify` cannot see (a bad numeral, a
    cross-enum literal). Every other combination is walled generally: when
    both the left type and the collection's element type are concrete and
    `unify` finds them incompatible, the membership can never be true."""
    right_t = infer(e.right, env)
    if not isinstance(right_t, (TCollection, TAny)):
        bag.error(
            "the right-hand side of `in` must be a collection (a zone or "
            f"a `[…]` list), got {_type_name(right_t)}",
            e.span,
        )
        return
    if isinstance(right_t, TCollection) and right_t.key is not None:
        # A keyed map is ambiguous under `in`: the sentence reads as a VALUE
        # test, but the runtime store is a dict, whose `in` asks about KEYS —
        # `2 in m` with every value 99 answered True because seat 2 exists.
        # Reject rather than pick a side silently; both meanings have direct
        # spellings.
        bag.error(
            f"`in` on a map keyed by {_type_name(right_t.key)} is ambiguous "
            f"(keys or values?) — test a specific entry (`m[k] is …`) or "
            f"quantify over the key domain instead",
            e.span,
        )
        return
    lbare = _bare(infer(e.left, env))
    if isinstance(lbare, TEnum) and isinstance(e.right, n.ListLit):
        for item in e.right.elements:
            ibare = _bare(infer(item, env))
            _check_enum_operand(lbare, item, ibare, env, bag)
        return
    if not isinstance(right_t, TCollection):
        return  # a TAny collection: nothing more `unify` can say
    ebare = _bare(right_t.element)
    if isinstance(lbare, TAny) or isinstance(ebare, TAny):
        return
    if unify(lbare, ebare) is None:
        bag.error(
            f"membership compares {_type_name(lbare)} with a collection of "
            f"{_type_name(ebare)} — never true",
            e.span,
        )


def _check_offset_by_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`offset_by`: rotates a Player around the seating ring by a Direction
    (`runtime.values.Seating.offset_by`) — the left operand must be a Player,
    the right a Direction-enum value (`hand[player offset_by pass_direction]`
    in hearts.cardlang reads the direction off a declared `Direction` state
    var, not only a bare `left`/`right`/`across`/`hold` literal, so this
    checks the *type*, not the ref-kind)."""
    lbare = _bare(infer(e.left, env))
    if not isinstance(lbare, (TAny, TPlayer)):
        bag.error(
            "'offset_by' rotates a Player around the seating ring — the "
            f"left operand must be a Player, got {_type_name(lbare)}",
            e.left.span,
        )
    rbare = _bare(infer(e.right, env))
    if isinstance(rbare, TAny):
        return
    if not (isinstance(rbare, TEnum) and rbare.name == "Direction"):
        bag.error(
            "'offset_by' expects a Direction (left/right/across/hold) on "
            f"the right, got {_type_name(rbare)}",
            e.right.span,
        )


def _check_card_source(source: n.Expr, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Both `cards in <source>` (CardQuery) and `over cards in <source>` (an
    aggregation) expect a zone or a collection of cards — the shared source
    wall, since a wrong source degrades every downstream Card wall to `TAny`
    (the `card` binder types off this same inference — Finding 1 in
    tests/test_zone_family_typing.py was exactly this failure mode for zone
    families). A non-collection source and a collection of the wrong element
    type both fail the same way: `unify` against `TCard` finds nothing in
    common."""
    src_t = infer(source, env)
    bare_src = _bare(src_t)
    if isinstance(bare_src, TAny):
        return
    if not isinstance(bare_src, TCollection):
        # A non-collection source is wrong even when it is card-TYPED: a
        # single Card unifies with TCard, but iterating it at runtime is a
        # crash, not a one-card query.
        hint = (
            " — a single Card is not a collection of cards"
            if isinstance(bare_src, TCard)
            else ""
        )
        bag.error(
            f"'cards in ...' expects a zone or collection of cards, got "
            f"{_type_name(src_t)}{hint}",
            source.span,
        )
        return
    ebare = _bare(bare_src.element)
    if isinstance(ebare, TAny):
        return
    if unify(ebare, TCard()) is None:
        bag.error(
            f"'cards in ...' expects a zone or collection of cards, got "
            f"{_type_name(src_t)}",
            source.span,
        )


def _check_agg_body(e: n.Comprehension, scoped: TypeEnv, bag: DiagnosticBag) -> None:
    """`sum`/`max`/`min` all fold Integers, and an enum-typed body (most
    plausibly a bare `card.rank`/`card.suit` where the author meant its
    strength) is the plausible-mistake case, so it gets the rank_value hint
    — but the two aggregators diverge at runtime (evaluate._comprehension),
    so the message names what actually happens: `sum` folds Python's
    `sum()`, whose zero-valued start makes `0 + "hearts"` a `TypeError` —
    loud, but only at play time, arbitrarily deep into a game; `max`/`min`
    fold Python's `max()`/`min()`, which silently compare the enum values
    *lexicographically as strings* — no crash, just the wrong card, forever.
    Every other concrete non-Integer body is equally nonsensical and gets
    the generic message. TAny/TInteger pass (gradual)."""
    bare = _bare(infer(e.body, scoped))
    if isinstance(bare, (TAny, TInteger)):
        return
    if isinstance(bare, TEnum):
        runtime_note = (
            "summing enum values type-errors at runtime (adding a string "
            "to an integer)"
            if e.agg == "sum"
            else "comparing enum values folds the underlying strings "
            "lexicographically at runtime, not the card's actual strength"
        )
        bag.error(
            f"'{e.agg}' aggregates a numeric strength — rank_value(card) — "
            f"not the enum value itself ({runtime_note})",
            e.body.span,
        )
        return
    bag.error(
        f"'{e.agg}' expects an Integer body, got {_type_name(bare)}",
        e.body.span,
    )


def _check_agg_default(
    e: n.Comprehension, env: TypeEnv, scoped: TypeEnv, bag: DiagnosticBag
) -> None:
    """The order aggregators' mandatory `or <default>` clause shares its
    leading `or` with a compound `where` predicate — `where A or B` reads as
    filter=A, default=B, the headline misparse this wall exists to catch. A
    Boolean default is the tell (a real default is body-shaped, e.g. an
    Integer for a `rank_value(card)` body; a leftover predicate is not) —
    flagged whenever there IS a `where` clause for the `or` to have been
    split from (no `where`, no ambiguity: a Boolean default there is an
    ordinary type mismatch, handled by the generic check below). Otherwise, a
    concrete body/default type mismatch `unify` can't reconcile is rejected
    generically."""
    assert e.default is not None
    dbare = _bare(infer(e.default, env))
    if isinstance(dbare, TBoolean) and e.filter is not None:
        bag.error(
            "the aggregation default is Boolean — this is almost always the "
            "last disjunct of the `where` predicate, absorbed by the "
            "mandatory `or <default>` clause: parenthesize the whole `where` "
            "predicate, or supply a real default after `or`",
            e.default.span,
        )
        return
    bbare = _bare(infer(e.body, scoped))
    if isinstance(bbare, TAny) or isinstance(dbare, TAny):
        return
    if unify(bbare, dbare) is None:
        bag.error(
            f"'{e.agg}' aggregation default type mismatch: the body is "
            f"{_type_name(bbare)}, the default is {_type_name(dbare)}",
            e.default.span,
        )


def _check_is_check(e: n.IsCheck, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`is empty`/`is not empty` ask a zone or collection; `is none`/`is not
    none` ask an optional. A concrete operand outside that domain isn't
    merely wrong, it's dead: both checks then have a fixed truth value
    regardless of the game's live state — never a check worth writing.
    TAny passes (gradual); TOptional/TNull pass the none-checks (their whole
    point)."""
    t = infer(e.operand, env)
    bare = _bare(t)
    if e.kind in ("empty", "not_empty"):
        if isinstance(bare, (TAny, TCollection)):
            return
        surface = "is empty" if e.kind == "empty" else "is not empty"
        bag.error(
            f"`{surface}` asks a zone or collection — got {_type_name(bare)}",
            e.operand.span,
        )
    else:  # "none" | "not_none"
        if isinstance(t, (TAny, TOptional, TNull)):
            return
        surface = "is none" if e.kind == "none" else "is not none"
        always = "always false" if e.kind == "none" else "always true"
        bag.error(
            f"`{surface}` on a non-optional {_type_name(bare)} is {always} "
            "— never a check worth writing",
            e.operand.span,
        )


def _check_expr(e: n.Expr, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Recursively validate a single expression: stdlib argument types and
    subscript legality. Types of unrefined sub-parts are `TAny` (permissive).

    Binder-introducing expressions extend the environment for their body, so
    type-directed checks (the dot-form rejection above all) see quantifier,
    player-query, card-query, and aggregation binders at their real types
    rather than `TAny`."""
    if isinstance(e, n.Quantifier):
        scoped = env.with_local(e.binder, _role_type(e.role))
        _check_expr(e.body, scoped, bag)
        _check_bool(e.body, scoped, bag, f"'{e.kind} {e.role}' quantifier body")
        return
    if isinstance(e, n.PlayerQuery):
        scoped = env.with_local("player", TPlayer())
        _check_expr(e.pred, scoped, bag)
        _check_bool(e.pred, scoped, bag, "player-query predicate")
        return
    if isinstance(e, n.CardQuery):
        _check_expr(e.source, env, bag)
        _check_card_source(e.source, env, bag)
        if e.pred is not None:
            scoped = env.with_local("card", TCard())
            _check_expr(e.pred, scoped, bag)
            _check_bool(e.pred, scoped, bag, "card-query predicate")
        return
    if isinstance(e, n.Comprehension):
        _check_expr(e.source, env, bag)
        _check_card_source(e.source, env, bag)
        src = infer(e.source, env)
        elem: Type = src.element if isinstance(src, TCollection) else TAny()
        scoped = env.with_local(e.binder, elem)
        if e.filter is not None:
            _check_expr(e.filter, scoped, bag)
            _check_bool(e.filter, scoped, bag, "aggregation `where` filter")
        _check_expr(e.body, scoped, bag)
        _check_agg_body(e, scoped, bag)
        if e.default is not None:
            _check_expr(e.default, env, bag)
            _check_agg_default(e, env, scoped, bag)
        return
    for child in _child_exprs(e):
        _check_expr(child, env, bag)
    if isinstance(e, n.Call):
        sig = CALL_SIGS.get(e.func) or env.functions.get(e.func)
        if sig is not None:
            args = _arg_exprs(e.args)
            if len(args) != len(sig.params):
                bag.error(
                    f"{e.func}() expects {len(sig.params)} argument(s), got {len(args)}",
                    e.span,
                )
            else:
                for arg, param in zip(args, sig.params):
                    got = infer(arg, env)
                    if not assignable(got, param):
                        bag.error(
                            f"{e.func}() expects {_type_name(param)}, got {_type_name(got)}",
                            e.span,
                        )
        if e.func in RANKING_GATED_FUNCS and not env.has_ranking:
            bag.error(
                f"{e.func}() reads a card's rank strength from ranking:, "
                f"but the game declares no ranking: — declare one, or use a "
                f"game-specific rank function",
                e.span,
            )
    elif isinstance(e, n.Subscript):
        obj_ref = e.obj
        if isinstance(obj_ref, n.NameRef) and obj_ref.ref_kind == "zone":
            # A zone-family subscript (`hand[p]`) is checked against the
            # zone's declared index role (Finding 1), not the generic
            # subscriptable-collection check below — a family isn't a
            # collection being indexed, it's ONE zone instance among many
            # selected by key.
            family = env.zone_families.get(obj_ref.name)
            if family is None:
                bag.error(
                    f"zone '{obj_ref.name}' is not indexed — drop the "
                    f"brackets",
                    e.span,
                )
            else:
                idx_t = infer(e.index, env)
                if not assignable(idx_t, family):
                    bag.error(
                        f"`{obj_ref.name}` is keyed by {_type_name(family)}"
                        f" — got {_type_name(idx_t)}",
                        e.span,
                    )
        else:
            obj = infer(e.obj, env)
            if not subscriptable(obj):
                bag.error(f"cannot index {_type_name(obj)} (not a collection)", e.span)
            elif isinstance(obj, TCollection) and obj.key is not None:
                # A KEYED map (a per-player/team state var, an indexed `let`)
                # is addressed by its key domain, and the checker knows both
                # sides now — `n[hearts]` used to sail through and die on a
                # raw KeyError at the read.
                idx_t = infer(e.index, env)
                if not assignable(idx_t, obj.key):
                    what = (
                        f"`{obj_ref.name}`"
                        if isinstance(obj_ref, n.NameRef)
                        else "this map"
                    )
                    bag.error(
                        f"{what} is keyed by {_type_name(obj.key)} — got "
                        f"{_type_name(idx_t)}",
                        e.span,
                    )
    elif isinstance(e, n.StructLit):
        _check_struct_lit(e, env, bag)
    elif isinstance(e, n.Member):
        obj_ref = e.obj
        if (
            isinstance(obj_ref, n.NameRef)
            and obj_ref.ref_kind == "pronoun"
            and obj_ref.name == "state"
            and e.field not in ROUND_STATE_FIELDS
        ):
            # `state.` names a round's PUBLISHED state, and that is a closed set.
            # Without this wall the receiver inferred `TAny`, every arm below
            # missed, and the read went through: a typo (`state.lead_suit`)
            # surfaced as a bare KeyError at play time, and — far worse — a form's
            # private working memory (`state.idx`, the trick's ring cursor) read
            # clean, ran, and silently changed the game. See stdlib/round_state.py.
            field_list = ", ".join(f"`{f}`" for f in sorted(ROUND_STATE_FIELDS))
            bag.error(
                f"a round publishes no `{e.field}` — `state.` names a round's "
                f"published state, which is {field_list}",
                e.span,
            )
            return
        obj = infer(e.obj, env)
        # Optionals reject like their payload: `d : Player?` is as much a
        # non-object receiver as `d : Player` (the closed rejection domain
        # includes the optional wrappers of its members).
        bare = obj.inner if isinstance(obj, TOptional) else obj
        if isinstance(obj, TStruct) and e.field not in obj.fields:
            bag.error(f"{obj.name} has no field '{e.field}'", e.span)
        elif isinstance(bare, TCard) and e.field not in CARD_FIELDS:
            # A card's fields are a closed pair — an unknown one would read
            # as `TAny` and only fail (or worse, not fail) at play time.
            field_list = " and ".join(f"`{f}`" for f in sorted(CARD_FIELDS))
            bag.error(
                f"Card has no field '{e.field}' (its fields are {field_list})",
                e.span,
            )
        elif isinstance(bare, TCollection):
            # A zone-family subscript (`hand[p]`) is now correctly typed as
            # the zone's content collection (Finding 1) rather than a single
            # Card, so a dot-form access on it (`hand[p].rank`) needs its own
            # wall — previously this silently read as TAny and only crashed
            # at play time (`_member` has no case for a `Zone`/list).
            bag.error(
                "a collection has no fields — aggregate over it ('sum of … "
                "over cards in …') or take a specific card",
                e.span,
            )
        elif isinstance(bare, (TPlayer, TTeam, TInteger, TBoolean)):
            # The dot form is object-member access only (Card, Move, and
            # struct fields). Zone/state indexing is the bracket form, and
            # relational chains derive through functions and state
            # (decisions.md "Typed object model", access discipline).
            bag.error(
                f"cannot read field '{e.field}' of {_type_name(obj)}: the dot "
                f"form is object-member access only — index with brackets "
                f"('{e.field}[...]') instead",
                e.span,
            )
    elif isinstance(e, n.BinOp):
        _check_binop(e, env, bag)
    elif isinstance(e, n.IsCheck):
        _check_is_check(e, env, bag)


def _check_struct_lit(e: n.StructLit, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Validate a struct literal against its declared type: every declared
    (non-derived) field is provided exactly once, no unknown fields, and each
    field value is assignable to the field's declared type."""
    struct = env.structs.get(e.type_name)
    if struct is None:
        return  # unknown type: flagged by resolve (`_validate_refs`)
    declared = {k for k in struct.fields if k not in struct.derived}
    provided = {fi.name for fi in e.fields}
    for missing in sorted(declared - provided):
        bag.error(f"{e.type_name} {{}} is missing field '{missing}'", e.span)
    for extra in sorted(provided - declared):
        if extra in struct.derived:
            bag.error(f"{e.type_name} {{}} cannot supply derived field '{extra}'", e.span)
        else:
            bag.error(f"{e.type_name} {{}} has unknown field '{extra}'", e.span)
    for fi in e.fields:
        expected = struct.fields.get(fi.name)
        if expected is None or fi.name in struct.derived:
            continue
        got = infer(fi.value, env)
        if not assignable(got, expected):
            bag.error(
                f"field '{fi.name}' expects {_type_name(expected)}, "
                f"got {_type_name(got)}",
                e.span,
            )


def _check_bool(e: n.Expr, env: TypeEnv, bag: DiagnosticBag, where: str) -> None:
    t = infer(e, env)
    if not isinstance(t, (TBoolean, TAny)):
        bag.error(f"{where} must be Boolean, got {_type_name(t)}", e.span)


def _stmt_exprs(s: n.Stmt) -> list[n.Expr]:
    """The expressions held directly by a statement (its child *statements* are
    visited separately by the statement walk). Exhaustive over `Stmt`: a kind
    missed here has its expressions silently skipped by every check downstream
    of the walk, so "holds no expressions" is stated per kind, not defaulted."""
    match s:
        case n.AssignStmt():
            # `s.target` is deliberately absent: a write target is validated by
            # resolve (`_bad_write_target`) and typed by `_check_assign`, not
            # walked as a value read.
            return [s.value] + ([s.index] if s.index is not None else [])
        case n.LetStmt():
            return [s.value]
        case n.Movement():
            out: list[n.Expr] = []
            if not isinstance(s.amount, str):
                out.append(s.amount)
            for opt in (s.source, s.dest, s.visibility, s.filter):
                if opt is not None:
                    out.append(opt)
            return out
        case n.EpistemicOp():
            return [s.target] if s.filter is None else [s.target, s.filter]
        case n.Offer():
            return [s.player]
        case n.Round():
            exprs = [s.leader, s.participants]
            if s.trump is not None:
                exprs.append(s.trump)
            if s.termination is not None:
                exprs.append(s.termination)
            return exprs
        case n.IfStmt() | n.RepeatUntil():
            return [s.cond]
        case n.Produce():
            return list(s.payloads)
        case n.RunStmt():
            return list(s.args)
        case n.ForEach() | n.EachSimultaneous() | n.RotateStmt():
            # ForEach/EachSimultaneous hold a role name and a binder (strings,
            # not expressions); RotateStmt's target is a write target, validated
            # by resolve like AssignStmt's.
            return []
        case n.Produces() | n.ContinueTo() | n.SkipToNextHand() | n.Block():
            # Produces holds statements only (its arms' bodies are walked by
            # `_check_produces` with the arm binders in scope); the control-flow
            # pair hold a phase name / nothing; Block holds child statements.
            return []
        case _:
            assert_never(s)


def _check_stmt_exprs(s: n.Stmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Check every expression `_stmt_exprs` holds directly, binding an
    implicit name where the construct's own runtime semantics require one.

    `Movement.filter` and `EpistemicOp.filter` are evaluated with `card`
    bound per candidate (runtime/execute.py's shared `_card_pred`:
    `ctx.with_local("card", c)`, used by both the movement selection and
    `reveal`) — the *only* two `_stmt_exprs` members whose
    predicate binds an implicit name (every other branch — AssignStmt,
    LetStmt, Offer, Round, IfStmt/RepeatUntil, Produce — holds plain value
    expressions in the ambient environment, no binder). Before this, both
    filters ran through the flat, unbound `env`, so `card.<field>` inside a
    `deal`/`move`/`reveal` filter typed as `TAny` (Member on an untyped
    `card` local) and every Card wall — the closed CARD_FIELDS pair among
    them — was dark there. The filter must also itself be Boolean; the
    other direct expressions on these two node kinds (source/dest/amount/
    visibility, target) carry no binder and stay in the ambient `env`."""
    if isinstance(s, (n.Movement, n.EpistemicOp)) and s.filter is not None:
        scoped = env.with_local("card", TCard())
        _check_expr(s.filter, scoped, bag)
        verb = s.verb if isinstance(s, n.Movement) else s.op
        _check_bool(s.filter, scoped, bag, f"'{verb}' filter")
        for expr in _stmt_exprs(s):
            if expr is not s.filter:
                _check_expr(expr, env, bag)
        return
    if isinstance(s, n.LetStmt) and s.index is not None:
        # The indexed form's key binder (`let base[p] = E`) is bound to each
        # player inside E only — check E in that scope, the same binding
        # `_scoped_env` uses to type `base` and the runtime `_let` uses to
        # evaluate it.
        _check_expr(s.value, env.with_local(s.index, TPlayer()), bag)
        return
    if isinstance(s, n.RunStmt):
        # Arity and argument types against the declared parameters — the same
        # check a `Call` gets against a function signature, and the only place a
        # procedure's parameter annotations can bite (after expansion, the call
        # site is gone). Resolve has already established that the procedure exists.
        sig = env.procedures.get(s.name)
        if sig is not None:
            if len(s.args) != len(sig.params):
                bag.error(
                    f"procedure '{s.name}' expects {len(sig.params)} argument(s), "
                    f"got {len(s.args)}",
                    s.span,
                )
            else:
                for arg, param in zip(s.args, sig.params):
                    got = infer(arg, env)
                    if not assignable(got, param):
                        bag.error(
                            f"procedure '{s.name}' expects {_type_name(param)}, got "
                            f"{_type_name(got)}",
                            arg.span,
                        )
    for expr in _stmt_exprs(s):
        _check_expr(expr, env, bag)


def _all_phases(game: Game) -> Iterator[n.Phase]:
    def rec(phase: n.Phase) -> Iterator[n.Phase]:
        yield phase
        for item in phase.items:
            if isinstance(item, n.Phase):
                yield from rec(item)

    for phase in game.phases:
        yield from rec(phase)


def _check_assign(stmt: n.AssignStmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    name = stmt.target.name
    target = env.state_vars.get(name)
    if target is None:
        # Resolve guarantees a write target classifies as a state variable — a binder,
        # a zone and an unknown name are all rejected there — so this is unreachable
        # for a checked game. It used to be the permissive escape for exactly those
        # cases, which is why an assignment to a `let` or a typo sailed through here.
        return
    if stmt.index is not None and isinstance(target, TCollection):
        if target.key is not None:
            # The write twin of the subscript key check: `n[hearts] := 1` on a
            # player-keyed store is a check-time error here; the runtime's
            # domain wall (execute._assign) stays behind it for computed keys.
            idx_t = infer(stmt.index, env)
            if not assignable(idx_t, target.key):
                bag.error(
                    f"`{name}` is keyed by {_type_name(target.key)} — got "
                    f"{_type_name(idx_t)}",
                    stmt.span,
                )
        target = target.element  # an indexed assignment writes one element
    rhs = infer(stmt.value, env)
    if stmt.op in ("+=", "-="):
        if not assignable(rhs, TInteger()):
            bag.error(
                f"'{name}' {stmt.op} expects an Integer, got {_type_name(rhs)}",
                stmt.span,
            )
    elif not assignable(rhs, target):
        bag.error(
            f"cannot assign {_type_name(rhs)} to '{name}' ({_type_name(target)})",
            stmt.span,
        )


def _check_stmt_semantics(stmt: n.Stmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    """The non-expression checks a statement carries: assignment compatibility,
    Boolean conditions, and movement-combination validity. Used by the flat walk
    and the scoped produces walk.

    Exhaustive over `Stmt` so that "this kind needs no semantic check" is a
    recorded decision per kind. A silent default here is how a new statement
    ships with its expressions typed but its own rules unenforced."""
    match stmt:
        case n.AssignStmt():
            _check_assign(stmt, env, bag)
        case n.IfStmt():
            _check_bool(stmt.cond, env, bag, "if condition")
        case n.RepeatUntil():
            _check_bool(stmt.cond, env, bag, "repeat-until condition")
        case n.Round() if stmt.termination is not None:
            _check_bool(stmt.termination, env, bag, "round `until` condition")
        case n.Movement():
            _check_movement(stmt, env, bag)
        case n.EpistemicOp():
            # The type half of the zone-target rule, like `_check_movement`'s
            # endpoints: a `local` root passes resolve's classification, and
            # the binder's inferred type decides here.
            t = infer(stmt.target, env)
            if not _is_zone_type(t):
                bag.error(
                    f"'{stmt.op}' target must be a zone, got "
                    f"{_type_name(t)}{_zone_hint(t, filterable=False)}",
                    stmt.span,
                )
        case n.Round():
            pass  # a round without `until` has no Boolean position to check
        case (
            n.RotateStmt() | n.EachSimultaneous() | n.ForEach()
            | n.LetStmt() | n.Offer() | n.Produce() | n.Produces()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt() | n.Block()
        ):
            # No statement-level semantics beyond what resolve walls (write
            # targets, rotate enum values, simultaneous bodies, run arity is
            # `_check_stmt_exprs`'s RunStmt arm) and the expression walk covers.
            pass
        case _:
            assert_never(stmt)


def _is_zone_type(t: "Type") -> bool:
    """Whether a value of this type IS a zone at runtime: the `zone` marker
    (`ZONE_CONTENT`, a zone-family subscript), or TAny (a deliberately-loose
    value the runtime backstop owns). The marker matters twice over: `all
    players` is a collection of the wrong element, and a card QUERY is a
    collection of the RIGHT element that still evaluates to a plain list —
    only the marker separates `hand[0]` from `cards in hand[0] where …`."""
    if isinstance(t, TAny):
        return True
    return isinstance(t, TCollection) and t.zone


def _zone_hint(t: "Type", filterable: bool) -> str:
    """A computed card collection fails the zone check with the RIGHT element,
    which reads as a contradiction without this: say why it is still not a
    zone, and what to write instead. The `where`-filter suggestion is offered
    only where the grammar can actually take one (`filterable` — a movement's
    FROM position); destinations, the gather form, and epistemic targets have
    no filter slot, and a hint naming unwritable syntax is worse than none."""
    if isinstance(t, TCollection) and isinstance(t.element, TCard) and not t.zone:
        fix = (
            "name the zone itself, or narrow the movement with a `where` filter"
            if filterable
            else "name the zone itself"
        )
        return f" (a computed card collection — a query result or list — is not a zone; {fix})"
    return ""


def _check_movement(stmt: n.Movement, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Combination validity for the movement production (decisions.md, "Surface
    totality"): every combination the grammar accepts is either implemented by
    the executor or rejected here with a clear message — a clause the runtime
    would silently ignore must not reach it."""
    # The TYPE half of the endpoint rule. Resolve rejects an endpoint whose
    # root CLASSIFIES as a non-zone (a state var, a deck value); a `local`
    # root passes classification because a binder may hold a zone — and now
    # that lets are typed, the type says whether this one does. A zone value
    # types as a CARD collection (ZONE_CONTENT), and the element matters:
    # `let z = all players` is a collection too, and waving it through on the
    # container shape alone sent it to the runtime's backstop with a message
    # claiming the checker couldn't know — it knew Collection<Player> exactly.
    for endpoint, what, filterable in (
        # Only the from-position takes a `where` filter; the in-form's zone
        # parses into `source` but has no dest, hence no filter slot either.
        (stmt.source, "source", stmt.dest is not None),
        (stmt.dest, "destination", False),
    ):
        if endpoint is None:
            continue
        t = infer(endpoint, env)
        if not _is_zone_type(t):
            bag.error(
                f"movement {what} must be a zone, got "
                f"{_type_name(t)}{_zone_hint(t, filterable)}",
                stmt.span,
            )
    if stmt.item not in ("card", "cards"):
        bag.error(
            f"movements move cards; '{stmt.item}' is not a supported item noun "
            "(resource movements are deferred — roadmap.md)",
            stmt.span,
        )
    if stmt.source is not None and stmt.dest is None:
        bag.error(
            f"the `{stmt.verb} ... in <zone>` form is not yet supported by the "
            "runtime (roadmap.md); name the destination with `to <zone>`",
            stmt.span,
        )
    if stmt.visibility is not None:
        bag.error(
            "per-movement visibility overrides are not yet honored by the "
            "runtime — visibility derives from the declared zone types "
            "(roadmap.md)",
            stmt.span,
        )
    if stmt.source is None and stmt.dest is not None:  # a gather
        if stmt.amount != "all" or stmt.mode is not None:
            bag.error(
                "a gather (`move ... to <zone>` with no `from`) collects every "
                "card: write `move all cards to <zone>`",
                stmt.span,
            )
        if stmt.dest_each:
            bag.error(
                "a gather collects into one zone; `to each` is not supported — "
                "gather to a single zone, then deal from it",
                stmt.span,
            )
    if stmt.distribution is not None:
        if not stmt.dest_each:
            bag.error(
                "`as-equally-as-possible` distributes a `to each` deal; it has "
                "no meaning with a single destination",
                stmt.span,
            )
        if stmt.amount != "all":
            bag.error(
                "an `as-equally-as-possible` deal distributes the whole source "
                "(or the whole `where` pool): the amount must be `all`",
                stmt.span,
            )
        if stmt.mode is not None:
            bag.error(
                f"`as-equally-as-possible` deals round-robin; a `{stmt.mode}` "
                "selection cannot combine with it",
                stmt.span,
            )
    elif stmt.dest_each and stmt.amount == "all":
        bag.error(
            "`deal all ... to each` would give the whole source to the first "
            "player; use `as-equally-as-possible` to distribute it",
            stmt.span,
        )


def _check_produce_stmt(
    sub: n.Produce, variant: TVariant, owner: str, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """One `produce` names a declared variant and supplies payloads of the
    declared arity and types."""
    if sub.tag not in variant.cases:
        bag.error(f"{owner} produces unknown variant '{sub.tag}'", sub.span)
        return
    payload_types = variant.cases[sub.tag]
    if len(sub.payloads) != len(payload_types):
        bag.error(
            f"variant '{sub.tag}' takes {len(payload_types)} payload(s), "
            f"got {len(sub.payloads)}",
            sub.span,
        )
        return
    for expr, expected in zip(sub.payloads, payload_types):
        got = infer(expr, env)
        if not assignable(got, expected):
            bag.error(
                f"variant '{sub.tag}' expects {_type_name(expected)}, "
                f"got {_type_name(got)}",
                sub.span,
            )


def _check_define_outcomes(
    define: n.DefineDef, variant: TVariant, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """Every `produce` in a define's body names a declared variant and supplies
    payloads of the declared arity and types — checked in the SCOPED
    environment, so a payload routed through a `let` types like its inline
    twin (`let z = hearts / produce Won(z)` used to pass a `Player` payload
    the inline spelling had just been rejected for)."""
    for sub, binders in _seq_tree_scoped(define.body, ()):
        if isinstance(sub, n.Produce):
            _check_produce_stmt(
                sub, variant, f"define '{define.name}'", _scoped_env(env, binders), bag
            )


def _check_misplaced_produce(
    game: Game, variants: Mapping[str, TVariant], env: TypeEnv, bag: DiagnosticBag
) -> None:
    """`produce` is legal only inside a `define` body (checked elsewhere) or the
    body of an outcome-declaring phase. Flag it anywhere else, and type-check the
    legal phase produces against the enclosing phase's variant."""
    for move_type in game.move_types:
        for s in move_type.effect:
            for sub in _stmt_tree(s):
                if isinstance(sub, n.Produce):
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
    for phase in game.phases:
        _check_phase_produces(phase, None, variants, env, bag)


def _produces_in(stmt: n.Stmt) -> Iterator[n.Produces]:
    """Every `produces:` consumer reachable from a root statement, descending into
    if/repeat/for-each bodies and (unlike `_stmt_tree`) into `produces:` arm bodies
    too — so a consumer nested in an arm is still validated. Call on root
    statements only (it walks if/repeat itself, so feeding it pre-flattened
    statements would double-count)."""
    for sub in _stmt_tree(stmt):
        if isinstance(sub, n.Produces):
            yield sub
            for arm in sub.arms:
                for s in arm.body:
                    yield from _produces_in(s)


def _continue_targets_in_item(item: "n.PhaseItem") -> set[str]:
    """Every `continue to` target reachable while executing one phase-body item,
    recursing into nested phases (a jump there can unwind to this body) and
    statement bodies. Hooks/config carry none (control flow in hooks is rejected)."""
    targets: set[str] = set()
    if isinstance(item, n.Phase):
        for sub in item.items:
            targets |= _continue_targets_in_item(sub)
        # A jump to one of this phase's own children is caught by its own
        # `run_body` and never unwinds to the parent, so it doesn't escape.
        targets -= {it.name for it in item.items if isinstance(it, n.Phase)}
    elif isinstance(
        item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo,
               n.BeforeEach, n.AfterEach)
    ):
        pass
    else:
        for node in _control_flow_nodes(item):
            if isinstance(node, n.ContinueTo):
                targets.add(node.target)
    return targets


def _item_can_skip(item: "n.PhaseItem") -> bool:
    """Whether executing one phase-body item can `skip to next hand` against *this*
    body's hand loop. A nested `repeat until` catches its own skips, so they don't
    unwind here."""
    if isinstance(item, n.Phase):
        if item.qualifier is not None and item.qualifier.kind == "repeats":
            return False
        return any(_item_can_skip(sub) for sub in item.items)
    if isinstance(
        item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo,
               n.BeforeEach, n.AfterEach)
    ):
        return False
    return any(isinstance(node, n.SkipToNextHand) for node in _control_flow_nodes(item))


def _control_flow_nodes(stmt: n.Stmt) -> Iterator[n.Stmt]:
    """Yield ContinueTo/SkipToNextHand within a statement, descending through
    if/repeat/for-each, `produces:` arm bodies, and blocks. Exhaustive over
    `Stmt`: a compound kind missed here hides its jumps from `_check_outcome_
    scope`, which then under-reports skippable producers — a wrong info-set-
    adjacent conclusion, not just a missed diagnostic."""
    match stmt:
        case n.ContinueTo() | n.SkipToNextHand():
            yield stmt
        case n.Produces():
            for arm in stmt.arms:
                for s in arm.body:
                    yield from _control_flow_nodes(s)
        case n.ForEach() | n.EachSimultaneous():
            yield from _control_flow_nodes(stmt.body)
        case n.RepeatUntil():
            for s in stmt.body:
                yield from _control_flow_nodes(s)
        case n.IfStmt():
            for s in stmt.then_body:
                yield from _control_flow_nodes(s)
            for s in stmt.else_body or ():
                yield from _control_flow_nodes(s)
        case n.Block():
            # A block is transparent to control flow: a jump written in a
            # procedure body unwinds exactly as it would inline. Unreachable
            # today (resolve rejects non-local control flow in procedure bodies,
            # and expansion runs after this pass) — but "unreachable today" is
            # what silent defaults always say right before they bite.
            for s in stmt.body:
                yield from _control_flow_nodes(s)
        case (
            n.Movement() | n.EpistemicOp() | n.RotateStmt() | n.LetStmt()
            | n.AssignStmt() | n.Offer() | n.Round() | n.Produce() | n.RunStmt()
        ):
            pass  # no jumps, no child statements to hold any
        case _:
            assert_never(stmt)


def _check_single_outcome_consumer(game: Game, bag: DiagnosticBag) -> None:
    """A phase produces one outcome and the runtime `pop`s it on the first
    consumer, so an outcome phase may have at most one `produces:` block (a second
    would deterministically find nothing). Defines, re-invoked per consumer, are
    unrestricted."""
    outcome_phases = {p.name for p in _all_phases(game) if p.outcome_cases}
    seen: set[str] = set()
    for stmt in _all_statements(game):
        # `_all_statements` is pre-flattened, so only expand the Produces roots
        # (each into itself + any arm-nested consumers) to avoid double-counting.
        if not isinstance(stmt, n.Produces):
            continue
        for sub in _produces_in(stmt):
            if sub.define not in outcome_phases:
                continue
            if sub.define in seen:
                bag.error(
                    f"phase outcome '{sub.define}' is consumed by more than one "
                    "produces: block",
                    sub.span,
                )
            seen.add(sub.define)


def _check_outcome_name_collisions(game: Game, bag: DiagnosticBag) -> None:
    """Outcome phases dispatch by name through one shared registry / runtime dict,
    so an outcome-phase name must be unique and must not collide with a `define`
    (either would silently shadow the other in a `produces:` consumer)."""
    define_names = {d.name for d in game.defines}
    seen: set[str] = set()
    for phase in _all_phases(game):
        if not phase.outcome_cases:
            continue
        if phase.name in define_names:
            bag.error(
                f"outcome phase '{phase.name}' collides with a define of the same "
                "name",
                phase.span,
            )
        if phase.name in seen:
            bag.error(
                f"duplicate outcome phase name '{phase.name}'", phase.span
            )
        seen.add(phase.name)


def _check_outcome_scope(game: Game, bag: DiagnosticBag) -> None:
    """The phase-outcome constructs resolve only within sibling scope, matching the
    runtime (which dispatches by name against phases that ran / sit in an enclosing
    body):

    - a `produces:` consumer naming an outcome phase needs that phase to be an
      *earlier-executed* sibling (in this body or an enclosing one), so the
      producer ran first in the same pass;
    - `continue to <phase>` resolves to a *later* sibling in this or an enclosing
      body (it is forward-only and unwinds outward to a body that holds the target);
    - `skip to next hand` sits inside a phase-level `repeat until` hand loop (a
      statement-level trick `repeat until` does not count).

    `before`/`after` carry the sibling phase names that execute before/after the
    current point, accumulated down the ancestor chain."""
    define_names = {d.name for d in game.defines}
    outcome_phases = {p.name for p in _all_phases(game) if p.outcome_cases}

    def check_produces_scope(stmt: n.Stmt, avail: set[str]) -> None:
        """Validate a `produces:` consumer (and any nested in arms/blocks) against
        the available producers. A statement-level `repeat until` reruns, but phase
        producers run once, so none are available inside its body."""
        if isinstance(stmt, n.Produces):
            if (
                stmt.define not in define_names
                and stmt.define in outcome_phases
                and stmt.define not in avail
            ):
                bag.error(
                    f"produces names phase '{stmt.define}', which is not an earlier "
                    "sibling that has run",
                    stmt.span,
                )
            for arm in stmt.arms:
                for s in arm.body:
                    check_produces_scope(s, avail)  # the arm runs at this position
        elif isinstance(stmt, (n.RepeatUntil, n.ForEach, n.EachSimultaneous)):
            # Any statement-level loop reruns its body; a run-once phase producer
            # is gone after the first iteration, so none are available inside.
            bodies = (
                stmt.body
                if isinstance(stmt, n.RepeatUntil)
                else (stmt.body,)
            )
            for s in bodies:
                check_produces_scope(s, set())
        elif isinstance(stmt, n.IfStmt):
            for s in stmt.then_body:
                check_produces_scope(s, avail)
            for s in stmt.else_body or ():
                check_produces_scope(s, avail)

    def walk(
        phase: n.Phase,
        before_outcomes: set[str],
        after_phases: set[str],
        in_hand_loop: bool,
    ) -> None:
        here_loop = in_hand_loop or (
            phase.qualifier is not None and phase.qualifier.kind == "repeats"
        )
        items = phase.items
        # All child phases are valid `continue to` targets; only *unqualified*
        # outcome phases are reliable `produces:` producers — a `when`/`repeats`
        # phase may not run (or produce), so a consumer can't depend on it.
        child_at = {
            idx: it.name for idx, it in enumerate(items) if isinstance(it, n.Phase)
        }
        child_outcome_at = {
            idx: it.name
            for idx, it in enumerate(items)
            if isinstance(it, n.Phase) and it.outcome_cases and it.qualifier is None
        }
        # A `continue to T` at position j jumps over items (j, k) where k is T's
        # index (or the body's end if T is an outer phase). A producer in that gap
        # may be skipped, so it is not reliably available to any later consumer.
        child_idx_by_name = {name: idx for idx, name in child_at.items()}
        skippable: set[str] = set()
        for j, it in enumerate(items):
            for target in _continue_targets_in_item(it):
                # A target outside this body unwinds past it, skipping the rest.
                k = child_idx_by_name.get(target, len(items))
                for i, nm in child_outcome_at.items():
                    if j < i < k:
                        skippable.add(nm)
        # A `skip to next hand` aborts the body from its position on, but after_each
        # still runs — so producers at or after the first possible skip aren't
        # available to after_each.
        first_skip = next(
            (j for j, it in enumerate(items) if _item_can_skip(it)), len(items)
        )
        for idx, item in enumerate(items):
            earlier = (
                before_outcomes
                | {nm for j, nm in child_outcome_at.items() if j < idx}
            ) - skippable
            later = after_phases | {nm for j, nm in child_at.items() if j > idx}
            if isinstance(item, n.Phase):
                # A consumer inside a `repeat until` body can only rely on a
                # producer that reruns each pass — i.e. one inside the same loop —
                # so outer producers don't carry in (continue-to targets still do).
                child_before = (
                    set()
                    if item.qualifier is not None and item.qualifier.kind == "repeats"
                    else earlier
                )
                walk(item, child_before, later, here_loop)
            elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo)):
                pass
            else:
                in_hook = isinstance(item, (n.BeforeEach, n.AfterEach))
                # Inline isinstance (not the `in_hook` flag) so mypy narrows the
                # `(item,)` branch to a Stmt.
                stmts = (
                    item.body
                    if isinstance(item, (n.BeforeEach, n.AfterEach))
                    else (item,)
                )
                # Hooks run by timing, not lexical position: before_each runs
                # before the whole body (no producer has run), after_each after it
                # (all body producers have).
                if isinstance(item, n.BeforeEach):
                    # Runs before the body: only ancestor producers have run (and
                    # `before_outcomes` is already empty inside a repeats loop).
                    avail = before_outcomes
                elif isinstance(item, n.AfterEach):
                    # Runs after the body: ancestor producers plus this body's own
                    # producers that are reached before any skip.
                    avail = before_outcomes | (
                        {nm for i, nm in child_outcome_at.items() if i < first_skip}
                        - skippable
                    )
                else:
                    avail = earlier
                for s in stmts:
                    for node in _control_flow_nodes(s):
                        if in_hook:
                            # `run_phase` only catches `_SkipHand`/`_ContinueTo`
                            # around the phase body, not the hooks — a skip from a
                            # hook would abort the whole run, not the hand.
                            bag.error(
                                "'continue to' / 'skip to next hand' is not allowed "
                                "in a before_each/after_each hook",
                                node.span,
                            )
                        elif isinstance(node, n.ContinueTo) and node.target not in later:
                            bag.error(
                                f"continue to '{node.target}' is not a later sibling "
                                "phase",
                                node.span,
                            )
                        elif isinstance(node, n.SkipToNextHand) and not here_loop:
                            bag.error(
                                "'skip to next hand' must be inside a `repeat until` "
                                "hand loop",
                                node.span,
                            )
                    check_produces_scope(s, avail)

    # Top-level phases are siblings of each other (they run in sequence), so a
    # `produces:` consumer in a later top-level phase can name an earlier one
    # (hence `before`). But `after` stays empty: `play_game` iterates top-level
    # phases with a plain loop (no enclosing `run_body`), so a `continue to`
    # targeting a *later top-level* phase has nowhere to be caught and must be
    # rejected — only later phases within a `run_body` are valid jump targets.
    top_outcome_at = {
        idx: p.name
        for idx, p in enumerate(game.phases)
        if p.outcome_cases and p.qualifier is None
    }
    for idx, phase in enumerate(game.phases):
        # Same rule as the recursion: a top-level `repeat until` body can't rely
        # on an earlier top-level producer (it ran once, the loop reruns).
        is_repeat = phase.qualifier is not None and phase.qualifier.kind == "repeats"
        before = (
            set()
            if is_repeat
            else {nm for j, nm in top_outcome_at.items() if j < idx}
        )
        walk(phase, before, set(), False)

    # `continue to` / `skip to next hand` are phase control flow. Outside a phase
    # body — in a define or move-type body — they would unwind out of
    # `play_game` uncaught, so reject them there.
    non_phase_bodies = (
        [d.body for d in game.defines]
        + [m.effect for m in game.move_types]
    )
    for body in non_phase_bodies:
        for s in body:
            for node in _control_flow_nodes(s):
                bag.error(
                    "'continue to' / 'skip to next hand' may only appear in a phase "
                    "body",
                    node.span,
                )


def _check_phase_produces(
    phase: n.Phase,
    enclosing: n.Phase | None,
    variants: Mapping[str, TVariant],
    env: TypeEnv,
    bag: DiagnosticBag,
    binders: _Binders = (),
) -> None:
    # The nearest outcome-declaring phase owns the produces in this body. The
    # binder fold mirrors `_phase_statements_scoped`, so a payload routed
    # through a preceding `let` types exactly like its inline twin.
    owner = phase if phase.outcome_cases else enclosing
    current = binders
    for item in phase.items:
        if isinstance(item, n.Phase):
            _check_phase_produces(item, owner, variants, env, bag, current)
        elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo)):
            pass
        elif isinstance(item, (n.BeforeEach, n.AfterEach)):
            for s in item.body:
                for sub in _stmt_tree(s):
                    if isinstance(sub, n.Produce):
                        bag.error("'produce' may not appear in a before_each/after_each hook", sub.span)
        else:
            for sub, sub_binders in _stmt_tree_scoped(item, current):
                if not isinstance(sub, n.Produce):
                    continue
                if owner is None:
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
                else:
                    _check_produce_stmt(
                        sub,
                        variants[owner.name],
                        f"phase '{owner.name}'",
                        _scoped_env(env, sub_binders),
                        bag,
                    )
            if isinstance(item, n.LetStmt):
                current = current + ((item.name, item),)


def _check_produces(
    stmt: n.Produces,
    variants: Mapping[str, TVariant],
    env: TypeEnv,
    bag: DiagnosticBag,
) -> None:
    """A `produces:` consumer: arms name declared variants, are exhaustive and
    non-duplicated, bind the right payload arity, and have their bodies checked
    with the payload binders typed (a scoped sub-walk, since the flat walk treats
    `Produces` as a leaf). A consumer nested in an arm is checked recursively with
    the enclosing arm binders in scope."""
    variant = variants.get(stmt.define)
    if variant is None:
        return
    seen: set[str] = set()
    for arm in stmt.arms:
        if arm.tag not in variant.cases:
            bag.error(
                f"produces names unknown variant '{arm.tag}' of '{stmt.define}'",
                arm.span,
            )
            continue
        if arm.tag in seen:
            bag.error(f"duplicate arm '{arm.tag}' in produces", arm.span)
        seen.add(arm.tag)
        payload_types = variant.cases[arm.tag]
        if len(arm.binders) != len(payload_types):
            bag.error(
                f"arm '{arm.tag}' binds {len(arm.binders)} value(s), "
                f"expected {len(payload_types)}",
                arm.span,
            )
        arm_env = env
        for binder, t in zip(arm.binders, payload_types):
            arm_env = arm_env.with_local(binder, t)
        # Arm bodies carry the same binder typing as the main walk — a `for
        # each` or a sequential `let` inside an arm is not a TAny loophole.
        for sub, loop_binders in _seq_tree_scoped(arm.body, ()):
            sub_env = _scoped_env(arm_env, loop_binders)
            if isinstance(sub, n.Produce):
                # `_stmt_tree` does not descend into `produces:` arms, so the
                # outer misplaced-produce walk never sees this — reject it here.
                bag.error("'produce' may not appear in a produces: arm", sub.span)
            if isinstance(sub, n.Produces):
                # Nested consumer: check it with the enclosing arm binders in
                # scope (so outer payload binders are typed, not TAny).
                _check_produces(sub, variants, sub_env, bag)
            _check_stmt_exprs(sub, sub_env, bag)
            _check_stmt_semantics(sub, sub_env, bag)
    missing = sorted(set(variant.cases) - seen)
    if missing:
        bag.error(
            f"produces on '{stmt.define}' is not exhaustive: missing "
            f"{', '.join(missing)}",
            stmt.span,
        )


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

    env = env_from_game(game)
    env = replace(env, functions=_function_sigs(game, env, bag))
    env = replace(env, procedures=_procedure_sigs(game))
    variants = variant_registry(game, env.structs)
    for stmt, binders in _all_statements_scoped(game):
        senv = _scoped_env(env, binders)
        _check_stmt_exprs(stmt, senv, bag)
        if isinstance(stmt, n.Produces):
            # `_check_produces` recurses into arm-nested consumers itself, carrying
            # the arm binders into their environment.
            _check_produces(stmt, variants, senv, bag)
        else:
            _check_stmt_semantics(stmt, senv, bag)
    for define in game.defines:
        variant = variants.get(define.name)
        if variant is not None:
            _check_define_outcomes(define, variant, env, bag)
    _check_misplaced_produce(game, variants, env, bag)
    _check_outcome_scope(game, bag)
    _check_outcome_name_collisions(game, bag)
    _check_single_outcome_consumer(game, bag)

    def check_phase_positions(phase: n.Phase, binders: _Binders) -> None:
        """Phase-level expression positions, typed with the binders the runtime
        actually evaluates them under. A nested phase's qualifier and a
        transition predicate run mid-body with the THREADED context (a
        preceding body `let` is bound — checking them with the bare env made
        the same expression get three different verdicts by position); state
        defaults run at ENTRY, so they see enclosing binders only (resolve
        rejects a same-phase body `let` in them, like the hooks)."""
        current = binders
        for item in phase.items:
            match item:
                case n.Phase():
                    if item.qualifier is not None:
                        qenv = _scoped_env(env, current)
                        _check_expr(item.qualifier.expr, qenv, bag)
                        _check_bool(
                            item.qualifier.expr,
                            qenv,
                            bag,
                            f"phase '{item.name}' condition",
                        )
                    check_phase_positions(item, current)
                case n.TransitionTo() if item.event.where is not None:
                    # NO binders at all: a transition predicate may not read
                    # any `let` (resolve rejects the reference — it is fired
                    # by whichever round matches its event, and no lexical
                    # position makes a binding reliably live then), so the
                    # bare env is exactly its scope.
                    _check_expr(item.event.where, env, bag)
                case n.StateBlock():
                    entry_env = _scoped_env(env, binders)
                    for decl in item.decls:
                        _check_expr(decl.default, entry_env, bag)
                case n.LetStmt():
                    current = current + ((item.name, item),)
                case _:
                    pass

    for phase in game.phases:
        if phase.qualifier is not None:
            # Top-level: nothing can precede a top-level phase, so the bare env
            # is exactly its entry scope.
            _check_expr(phase.qualifier.expr, env, bag)
            _check_bool(
                phase.qualifier.expr, env, bag, f"phase '{phase.name}' condition"
            )
        check_phase_positions(phase, ())
    if game.loser is not None:
        _check_expr(game.loser.selection, env, bag)

    # The remaining expression positions: a function call in any of these needs the
    # same arity/type validation as one in a statement, but the statement walk above
    # does not reach them. This is every place a call can appear that isn't already
    # covered (statements, round over/until, phase qualifiers, loser, function
    # bodies): move guards, rule predicates, state defaults, transition predicates,
    # and derived type-field bodies.
    for move_type in game.move_types:
        if move_type.guard is not None:
            _check_expr(
                move_type.guard,
                _scoped_env(env, _move_param_binders(move_type)),
                bag,
            )
    for rule in game.rules:
        if rule.applies_when is not None and rule.applies_when.pred is not None:
            _check_expr(rule.applies_when.pred, env, bag)
        if rule.demands is not None:
            _check_expr(rule.demands.expr, env, bag)
        if rule.if_impossible is not None:
            _check_expr(rule.if_impossible, env, bag)
        if rule.exempts is not None:
            _check_expr(rule.exempts, env, bag)
    # Phase-level state defaults and transition predicates are checked by
    # `check_phase_positions` above, with their real binder scope; only the
    # game-level state block remains here (nothing can precede it).
    if game.state is not None:
        for decl in game.state.decls:
            _check_expr(decl.default, env, bag)
    for tdef in game.types:
        # A derived body reads sibling fields by bare name (resolve scopes
        # them); their declared types are in the struct registry, so bind
        # them — `derived { bad = seat is hearts }` on a Player field used to
        # type `seat` as TAny and accept the always-false comparison.
        struct = env.structs.get(tdef.name)
        denv = env
        if struct is not None:
            for fname, ftype in struct.fields.items():
                denv = denv.with_local(fname, ftype)
        for derived in tdef.derived:
            _check_expr(derived.value, denv, bag)

    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game
