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
from typing import Iterator, Mapping, assert_never

from cardlang.ast import nodes as n
from cardlang.ast.nodes import Game
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.signatures import CALL_SIGS, METHOD_SIGS, ZONE_CONTENT
from cardlang.stdlib.values import DIRECTION_VALUES, deck_suits
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
    for rank in game.ranking:
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
    value_enums: Mapping[str, TEnum] = field(default_factory=dict)
    locals: Mapping[str, Type] = field(default_factory=dict)
    structs: Mapping[str, TStruct] = field(default_factory=dict)

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
            obj = infer(e.obj, env)
            return obj.element if isinstance(obj, TCollection) else TAny()
        case n.Call():
            sig = CALL_SIGS.get(e.func)
            return sig.ret if sig is not None else TAny()
        case n.MethodCall():
            msig = METHOD_SIGS.get(e.method)
            if msig is None:
                return TAny()
            if msig.returns_receiver:
                return infer(e.obj, env)
            return msig.ret if msig.ret is not None else TAny()
        case n.BinOp():
            if e.op in ("==", "!=", "<", ">", "<=", ">=", "and", "or"):
                return TBoolean()
            if e.op in ("+", "-", "*"):
                return TInteger()
            return TAny()  # offset_by and any future operators
        case n.Not() | n.IsCheck() | n.Quantifier():
            return TBoolean()
        case n.Choose():
            return TInteger()
        case n.Comprehension():
            return TInteger() if e.agg in ("sum", "count") else TAny()
        case n.PlayerQuery():
            match e.kind:
                case "set":
                    return TCollection(TPlayer())
                case "count":
                    return TInteger()
                case _:  # "pick"
                    return TPlayer()
        case n.IfExpr():
            return _ifexpr_type(e, env)
        case n.StructLit():
            return env.structs.get(e.type_name, TAny())
        case n.Member():
            obj = infer(e.obj, env)
            if isinstance(obj, TStruct):
                return obj.fields.get(e.field, TAny())
            return TAny()  # pronoun member access / sugar: deferred
        case n.Lambda():
            return TAny()  # lambda values: deferred
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
        case _:
            return TAny()  # pronoun / function / routing / unresolved


def _type_name(t: Type) -> str:
    if isinstance(t, TNull):
        return "none"
    if isinstance(t, TOptional):
        return f"{_type_name(t.inner)}?"
    if isinstance(t, TCollection):
        return f"Collection<{_type_name(t.element)}>"
    if isinstance(t, TEnum):
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
            # An indexed state var (`score[player] : Integer`) is a per-key map —
            # a collection whose subscript yields the declared value type.
            state_vars[decl.name] = TCollection(t) if decl.index is not None else t
    zones: dict[str, Type] = {
        z.name: ZONE_CONTENT.get(z.type_ref.name, TCollection(TAny()))
        for z in game.zones
    }
    return TypeEnv(
        state_vars=state_vars,
        zones=zones,
        value_enums=value_enum_map(game),
        structs=structs,
    )


def _stmt_tree(s: n.Stmt) -> Iterator[n.Stmt]:
    yield s
    if isinstance(s, (n.ForEach, n.EachSimultaneous)):
        yield from _stmt_tree(s.body)
    elif isinstance(s, n.RepeatUntil):
        for x in s.body:
            yield from _stmt_tree(x)
    elif isinstance(s, n.IfStmt):
        for x in s.then_body:
            yield from _stmt_tree(x)
        for x in s.else_body or ():
            yield from _stmt_tree(x)


def _phase_statements(phase: n.Phase) -> Iterator[n.Stmt]:
    for item in phase.items:
        if isinstance(item, n.Phase):
            yield from _phase_statements(item)
        elif isinstance(item, (n.BeforeEach, n.AfterEach)):
            for s in item.body:
                yield from _stmt_tree(s)
        elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo)):
            pass
        else:
            yield from _stmt_tree(item)


def _non_define_statements(game: Game) -> Iterator[n.Stmt]:
    """Every statement outside a `define` body — where `produce` is illegal."""
    for routing in game.routings:
        for s in routing.body:
            yield from _stmt_tree(s)
    for move_type in game.move_types:
        for s in move_type.effect:
            yield from _stmt_tree(s)
    for phase in game.phases:
        yield from _phase_statements(phase)


def _all_statements(game: Game) -> Iterator[n.Stmt]:
    yield from _non_define_statements(game)
    for define in game.defines:
        for s in define.body:
            yield from _stmt_tree(s)


def _arg_exprs(args: tuple[n.Arg, ...]) -> list[n.Expr]:
    """The positional expression arguments of a call (named args are not used by
    the stdlib functions/methods being checked)."""
    return [a for a in args if not isinstance(a, n.NamedArg)]


def _child_exprs(e: n.Expr) -> list[n.Expr]:
    if isinstance(e, n.Member):
        return [e.obj]
    if isinstance(e, n.StructLit):
        return [fi.value for fi in e.fields]
    if isinstance(e, n.Subscript):
        return [e.obj, e.index]
    if isinstance(e, n.Call):
        return _arg_exprs(e.args)
    if isinstance(e, n.MethodCall):
        return [e.obj, *_arg_exprs(e.args)]
    if isinstance(e, n.BinOp):
        return [e.left, e.right]
    if isinstance(e, (n.Not, n.IsCheck)):
        return [e.operand]
    if isinstance(e, (n.Lambda, n.Quantifier)):
        return [e.body]
    if isinstance(e, n.Comprehension):
        return [e.source, e.body]
    if isinstance(e, n.Choose):
        return [e.lo, e.hi]
    if isinstance(e, n.PlayerQuery):
        return [e.pred]
    if isinstance(e, n.IfExpr):
        out = [e.cond, e.then]
        for cond, branch in e.elifs:
            out += [cond, branch]
        out.append(e.otherwise)
        return out
    return []  # leaves: NameRef, IntLit, StrLit, CardLiteral, AllPlayers


def _check_expr(e: n.Expr, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Recursively validate a single expression: stdlib argument types and
    subscript legality. Types of unrefined sub-parts are `TAny` (permissive)."""
    for child in _child_exprs(e):
        _check_expr(child, env, bag)
    if isinstance(e, n.Call):
        sig = CALL_SIGS.get(e.func)
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
    elif isinstance(e, n.MethodCall):
        msig = METHOD_SIGS.get(e.method)
        if msig is not None and not msig.lambda_arg:
            args = _arg_exprs(e.args)
            if len(args) != len(msig.params):
                bag.error(
                    f".{e.method}() expects {len(msig.params)} argument(s), got {len(args)}",
                    e.span,
                )
            else:
                for arg, param in zip(args, msig.params):
                    got = infer(arg, env)
                    if not assignable(got, param):
                        bag.error(
                            f".{e.method}() expects {_type_name(param)}, got {_type_name(got)}",
                            e.span,
                        )
    elif isinstance(e, n.Subscript):
        obj = infer(e.obj, env)
        if not subscriptable(obj):
            bag.error(f"cannot index {_type_name(obj)} (not a collection)", e.span)
    elif isinstance(e, n.StructLit):
        _check_struct_lit(e, env, bag)
    elif isinstance(e, n.Member):
        obj = infer(e.obj, env)
        if isinstance(obj, TStruct) and e.field not in obj.fields:
            bag.error(f"{obj.name} has no field '{e.field}'", e.span)


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
    visited separately by the statement walk)."""
    if isinstance(s, n.AssignStmt):
        return [s.value] + ([s.index] if s.index is not None else [])
    if isinstance(s, n.LetStmt):
        return [s.value]
    if isinstance(s, n.Movement):
        out: list[n.Expr] = []
        if not isinstance(s.amount, str):
            out.append(s.amount)
        for opt in (s.source, s.dest, s.visibility):
            if opt is not None:
                out.append(opt)
        return out
    if isinstance(s, n.EpistemicOp):
        return [s.target]
    if isinstance(s, n.Offer):
        return [s.player]
    if isinstance(s, n.Round):
        return [s.leader, s.participants] + ([s.trump] if s.trump is not None else [])
    if isinstance(s, n.Instantiate):
        return [a.value for a in s.args if not isinstance(a.value, n.Movement)]
    if isinstance(s, (n.IfStmt, n.RepeatUntil)):
        return [s.cond]
    if isinstance(s, n.Produce):
        return list(s.payloads)
    return []  # ForEach / EachSimultaneous / RotateStmt: no direct value expressions


def _all_phases(game: Game) -> Iterator[n.Phase]:
    def rec(phase: n.Phase) -> Iterator[n.Phase]:
        yield phase
        for item in phase.items:
            if isinstance(item, n.Phase):
                yield from rec(item)

    for phase in game.phases:
        yield from rec(phase)


def _check_assign(stmt: n.AssignStmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    target = env.state_vars.get(stmt.name)
    if target is None:
        return  # not a typed state var (a let-local, or unknown — left permissive)
    if stmt.index is not None and isinstance(target, TCollection):
        target = target.element  # an indexed assignment writes one element
    rhs = infer(stmt.value, env)
    if stmt.op in ("+=", "-="):
        if not assignable(rhs, TInteger()):
            bag.error(
                f"'{stmt.name}' {stmt.op} expects an Integer, got {_type_name(rhs)}",
                stmt.span,
            )
    elif not assignable(rhs, target):
        bag.error(
            f"cannot assign {_type_name(rhs)} to '{stmt.name}' ({_type_name(target)})",
            stmt.span,
        )


def _check_stmt_semantics(stmt: n.Stmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    """The non-expression checks a statement carries: assignment compatibility
    and Boolean conditions. Used by the flat walk and the scoped produces walk."""
    if isinstance(stmt, n.AssignStmt):
        _check_assign(stmt, env, bag)
    elif isinstance(stmt, n.IfStmt):
        _check_bool(stmt.cond, env, bag, "if condition")
    elif isinstance(stmt, n.RepeatUntil):
        _check_bool(stmt.cond, env, bag, "repeat-until condition")


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
    payloads of the declared arity and types."""
    for stmt in define.body:
        for sub in _stmt_tree(stmt):
            if isinstance(sub, n.Produce):
                _check_produce_stmt(sub, variant, f"define '{define.name}'", env, bag)


def _check_misplaced_produce(
    game: Game, variants: Mapping[str, TVariant], env: TypeEnv, bag: DiagnosticBag
) -> None:
    """`produce` is legal only inside a `define` body (checked elsewhere) or the
    body of an outcome-declaring phase. Flag it anywhere else, and type-check the
    legal phase produces against the enclosing phase's variant."""
    for routing in game.routings:
        for s in routing.body:
            for sub in _stmt_tree(s):
                if isinstance(sub, n.Produce):
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
    for move_type in game.move_types:
        for s in move_type.effect:
            for sub in _stmt_tree(s):
                if isinstance(sub, n.Produce):
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
    for phase in game.phases:
        _check_phase_produces(phase, None, variants, env, bag)


def _control_flow_nodes(stmt: n.Stmt) -> Iterator[n.Stmt]:
    """Yield ContinueTo/SkipToNextHand within a statement, descending through
    if/repeat/for-each and `produces:` arm bodies."""
    if isinstance(stmt, (n.ContinueTo, n.SkipToNextHand)):
        yield stmt
    elif isinstance(stmt, n.Produces):
        for arm in stmt.arms:
            for s in arm.body:
                yield from _control_flow_nodes(s)
    elif isinstance(stmt, (n.ForEach, n.EachSimultaneous)):
        yield from _control_flow_nodes(stmt.body)
    elif isinstance(stmt, n.RepeatUntil):
        for s in stmt.body:
            yield from _control_flow_nodes(s)
    elif isinstance(stmt, n.IfStmt):
        for s in stmt.then_body:
            yield from _control_flow_nodes(s)
        for s in stmt.else_body or ():
            yield from _control_flow_nodes(s)


def _check_outcome_scope(game: Game, bag: DiagnosticBag) -> None:
    """The phase-outcome constructs resolve only within sibling scope, matching the
    runtime (which dispatches by name against phases that ran / sit in an enclosing
    body):

    - a `produces:` consumer naming an outcome phase needs that phase to be an
      *earlier-executed* sibling (in this body or an enclosing one), so the
      producer ran first in the same pass;
    - `continue to <phase>` resolves to a *later* sibling in this or an enclosing
      body (it is forward-only and unwinds outward to a body that holds the target);
    - `skip to next hand` sits inside a phase-level `repeats until` hand loop (a
      statement-level trick `repeat until` does not count).

    `before`/`after` carry the sibling phase names that execute before/after the
    current point, accumulated down the ancestor chain."""
    define_names = {d.name for d in game.defines}
    outcome_phases = {p.name for p in _all_phases(game) if p.outcome_cases}

    def walk(
        phase: n.Phase, before: set[str], after: set[str], in_hand_loop: bool
    ) -> None:
        here_loop = in_hand_loop or (
            phase.qualifier is not None and phase.qualifier.kind == "repeats"
        )
        items = phase.items
        child_at = {
            idx: it.name for idx, it in enumerate(items) if isinstance(it, n.Phase)
        }
        for idx, item in enumerate(items):
            earlier = before | {nm for j, nm in child_at.items() if j < idx}
            later = after | {nm for j, nm in child_at.items() if j > idx}
            if isinstance(item, n.Phase):
                walk(item, earlier, later, here_loop)
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
                                "'skip to next hand' must be inside a `repeats until` "
                                "hand loop",
                                node.span,
                            )
                    for sub in _stmt_tree(s):
                        if (
                            isinstance(sub, n.Produces)
                            and sub.define not in define_names
                            and sub.define in outcome_phases
                            and sub.define not in earlier
                        ):
                            bag.error(
                                f"produces names phase '{sub.define}', which is not an "
                                "earlier sibling that has run",
                                sub.span,
                            )

    # Top-level phases are siblings of each other (they run in sequence), so a
    # `produces:` consumer in a later top-level phase can name an earlier one
    # (hence `before`). But `after` stays empty: `play_game` iterates top-level
    # phases with a plain loop (no enclosing `run_body`), so a `continue to`
    # targeting a *later top-level* phase has nowhere to be caught and must be
    # rejected — only later phases within a `run_body` are valid jump targets.
    top_at = {idx: p.name for idx, p in enumerate(game.phases)}
    for idx, phase in enumerate(game.phases):
        before = {nm for j, nm in top_at.items() if j < idx}
        walk(phase, before, set(), False)


def _check_phase_produces(
    phase: n.Phase,
    enclosing: n.Phase | None,
    variants: Mapping[str, TVariant],
    env: TypeEnv,
    bag: DiagnosticBag,
) -> None:
    # The nearest outcome-declaring phase owns the produces in this body.
    owner = phase if phase.outcome_cases else enclosing
    for item in phase.items:
        if isinstance(item, n.Phase):
            _check_phase_produces(item, owner, variants, env, bag)
        elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.TransitionTo)):
            pass
        elif isinstance(item, (n.BeforeEach, n.AfterEach)):
            for s in item.body:
                for sub in _stmt_tree(s):
                    if isinstance(sub, n.Produce):
                        bag.error("'produce' may not appear in a before_each/after_each hook", sub.span)
        else:
            for sub in _stmt_tree(item):
                if not isinstance(sub, n.Produce):
                    continue
                if owner is None:
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
                else:
                    _check_produce_stmt(sub, variants[owner.name], f"phase '{owner.name}'", env, bag)


def _check_produces(
    stmt: n.Produces, variant: TVariant, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """A `produces:` consumer: arms name declared variants, are exhaustive and
    non-duplicated, bind the right payload arity, and have their bodies checked
    with the payload binders typed (a scoped sub-walk, since the flat walk treats
    `Produces` as a leaf)."""
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
        for body_stmt in arm.body:
            for sub in _stmt_tree(body_stmt):
                if isinstance(sub, n.Produce):
                    # `_stmt_tree` does not descend into `produces:` arms, so the
                    # outer misplaced-produce walk never sees this — reject it here.
                    bag.error("'produce' may not appear in a produces: arm", sub.span)
                for expr in _stmt_exprs(sub):
                    _check_expr(expr, arm_env, bag)
                _check_stmt_semantics(sub, arm_env, bag)
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
    variants = variant_registry(game, env.structs)
    for stmt in _all_statements(game):
        for expr in _stmt_exprs(stmt):
            _check_expr(expr, env, bag)
        if isinstance(stmt, n.Produces):
            variant = variants.get(stmt.define)
            if variant is not None:
                _check_produces(stmt, variant, env, bag)
        else:
            _check_stmt_semantics(stmt, env, bag)
    for define in game.defines:
        variant = variants.get(define.name)
        if variant is not None:
            _check_define_outcomes(define, variant, env, bag)
    _check_misplaced_produce(game, variants, env, bag)
    _check_outcome_scope(game, bag)
    for phase in _all_phases(game):
        if phase.qualifier is not None:
            _check_expr(phase.qualifier.expr, env, bag)
            _check_bool(
                phase.qualifier.expr, env, bag, f"phase '{phase.name}' condition"
            )
    if game.loser is not None:
        _check_expr(game.loser.selection, env, bag)

    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game
