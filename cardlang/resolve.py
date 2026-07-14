"""Resolve stage: name resolution.

This pass checks that the structural references in a game hang together —
the class of error a type checker catches before anything runs:

- every zone's type names a known library zone type (and is parameterized
  correctly);
- every `active_rules:` entry names a rule defined in the game;
- every move type referenced by `constrains:`, `legal_moves:`, or a
  transition event is a known library move type;
- every `transition_to:` target is a sibling phase.

Deep expression name resolution (state variables, suits, the `action` fields,
stdlib functions) needs the typed object model and lands with the type
checker; this pass is the structural net.

On success the (unchanged) :class:`Game` flows on. On any error it raises with
every diagnostic collected, not just the first.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Callable, Iterator, assert_never, cast, get_args

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError, Span
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES
from cardlang.domains import PARAM_DOMAIN_ORDER, PARAM_DOMAINS as _FIXED_DOMAINS
from cardlang.domains import SIMULTANEOUS_ROLES, ZONE_INDEX_ROLES
from cardlang.stdlib.functions import (
    STDLIB_AUCTION_OUTCOMES,
    STDLIB_CALL_FUNCS,
    STDLIB_CLIMB_FOLLOWS,
    STDLIB_CLIMB_LEADS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_TRICK_OUTCOMES,
    STDLIB_VALUE_NAMES,
)
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import library_rules
from cardlang.stdlib.values import DIRECTION_VALUES, deck_ranks, deck_suits, enum_values
from cardlang.typecheck import KNOWN_TYPE_NAMES
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES

# Roles a zone may be indexed by or owned by — the `zone_key_of` column of the
# domain table, not a local list (it used to be a hand-written {player, team}
# here, re-spelled as `== "team"` at four more sites downstream).
_KNOWN_ROLES = ZONE_INDEX_ROLES

# The three domain-registry views this module gates on, all derived from the one
# table in `cardlang.domains` (which also owns typecheck's binder typing and the
# runtime's member enumerators, so the sites can't drift):
#
# - `_ITERATION_ROLES` — the roles `for each <role> <binder>` may range over
#   (the registry's `iterable` column). Quantifier roles are fixed by their
#   grammar productions instead, so they need no set here.
# - `SIMULTANEOUS_ROLES` — the roles `each <role> simultaneously:` may range
#   over (the `simultaneous` column): seat domains only, since a value domain
#   has no actor to move simultaneously.
# - `_FIXED_DOMAINS` / `PARAM_DOMAIN_ORDER` — the statically enumerable
#   move-parameter domains (the union of the rows' `param_domains`), as a set
#   for the membership gate and as a sequence for the diagnostic that lists them.

# The magic namespaces a bare name may resolve to.
_PRONOUNS = frozenset({"state", "action", "outcome", "active_rules", "actor"})

# Pronouns that name call-site context (`_user_function` clears them before a
# function body runs). A hermetic body may not read them — it would see None;
# pass the value in as a parameter instead. `state`/`active_rules` are game/phase
# context and remain readable.
_CALL_SITE_PRONOUNS = frozenset({"actor", "action", "outcome"})

# Value-words a DECLARATION may never take, because a bare NameRef spelling
# the same word can never mean "the declaration" — some other fixed reading
# always wins, silently: `none`/`true`/`false` are literals `_classify` (below)
# intercepts before any declaration namespace even runs; `empty` is intercepted
# earlier still, at PARSE time (`x is empty` always builds an `IsCheck`, never a
# `NameRef`, no matter what `empty` is declared as — parse.py's `compare_is`/
# `compare_is_not`); and each `_PRONOUNS` word is a fixed context namespace
# (`state.led_suit`, bare `actor`, …) a same-named declaration would instead
# shadow — silently changing what `state.foo` means rather than erroring.
# `card`/`player` are deliberately absent: both are established, corpus-wide
# LEXICAL shadow idioms (a card-query/quantifier binder, always scoped strictly
# narrower than a same-named outer declaration — see `_BINDER_SCOPE_FIELDS`),
# which is the intended shadowing `_check_duplicate_names`'s docstring already
# carves out, not a defect this reservation needs to close.
RESERVED_VALUE_NAMES: frozenset[str] = frozenset({"none", "empty", "true", "false"}) | _PRONOUNS

_RESERVED_WHY: dict[str, str] = {
    "none": "`x is none` always reads it as the null check",
    "empty": "`x is empty` always reads it as the emptiness check",
    "true": "it is the boolean literal",
    "false": "it is the boolean literal",
    "state": "it is the phase/game state pronoun (`state.foo`)",
    "action": "it is the call-site action pronoun",
    "outcome": "it is the call-site outcome pronoun",
    "active_rules": "it is the active-rules pronoun",
    "actor": "it is the call-site actor pronoun",
}


def _check_reserved(
    name: str,
    kind: str,
    span: Span | None,
    bag: DiagnosticBag,
    reserved: frozenset[str] = RESERVED_VALUE_NAMES,
) -> None:
    if name in reserved:
        bag.error(
            f"{kind} '{name}' is a reserved word — {_RESERVED_WHY[name]} — "
            f"pick another name",
            span,
        )


def resolve(game: n.Game) -> n.Game:
    bag = DiagnosticBag()
    _resolve_deck(game, bag)
    _resolve_ranking(game, bag)
    _check_duplicate_names(game, bag)
    _check_reserved_params(game, bag)
    _check_reserved_binders(game, bag)
    _resolve_max_length(game, bag)
    for zone in game.zones:
        _resolve_zone(zone, bag)

    # Names that resolve to SOME rule template (local or library), independent
    # of whether that template ever successfully instantiates — the set
    # `active_rules names undefined rule` gates on below. Captured from the
    # ORIGINAL `game.rules` (before instantiation, which drops a local
    # template that fails to instantiate): a name is "undefined" only when no
    # template exists for it anywhere, never merely because its own
    # instantiation attempt hit some OTHER, already-separately-reported
    # mismatch (arity, missing arguments, …) — that conflation used to pile a
    # spurious "undefined rule" note onto every such mismatch.
    known_rule_names = {r.name for r in game.rules} | set(library_rules())

    # Library-rule splice and template instantiation: after this, every rule in
    # `game.rules` is a concrete (parameter-free) definition the runtime can
    # index by name.
    game = _instantiate_rules(game, bag)

    for rule in game.rules:
        _resolve_rule(rule, bag)
    _resolve_phase_level(game.phases, known_rule_names, bag)
    _check_remove_reachability(game.phases, bag)

    # Deep name resolution: classify every bare name and validate calls,
    # methods, card literals, and the rotate/winner targets.
    cats = _categories(game)
    game = _classify_names(game, cats, bag)
    _validate_refs(game, cats, bag)
    _check_functions(game, bag)
    _check_procedures(game, bag)
    _check_chooses(game, bag)

    _raise_if_errors(bag)
    return game


# The Node union's members, for the runtime gate below. `get_args` reads the
# union itself, and tests/test_node_registry.py pins that union to the module's
# actual dataclasses — so this tuple cannot silently miss a node kind.
_NODE_KINDS: tuple[type, ...] = get_args(n.Node)


def _introduced_binders(node: object) -> tuple[str, ...]:
    """The single registry of "which node kinds bind names, and which names":
    every other place that needs to know (`_template_binders`'s collision
    check, `_check_functions`'s allowed-reference set, `_rewrite`'s lexical
    scoping via `_BINDER_SCOPE_FIELDS`) reads this instead of re-enumerating
    the node-kind match itself — three copies of that match previously drifted
    out of sync (missing the `Movement`/`EpistemicOp` filter arm in two of
    them).

    Walks feed this every field value they meet, so non-node values (a `str`
    name, a `Span`, an `int`) answer "nothing" here; every actual node kind is
    dispatched exhaustively in `_node_binders`."""
    if not isinstance(node, _NODE_KINDS):
        return ()
    return _node_binders(cast(n.Node, node))


def _node_binders(node: n.Node) -> tuple[str, ...]:
    """Exhaustive over `Node` — deliberately. This registry's only two known
    escapes (`ProduceArm`, then `TypeDef`) both lived in a `case _: return ()`
    catch-all: a node kind nobody had thought about answered "no binders"
    without anyone having decided that. Now a new node kind is a mypy error
    here until someone files it under binding or non-binding by hand.

    `LetStmt` returns both `name` and `index` (when present) — every name it
    binds *somewhere*, which is what a collision check needs. The two differ
    in WHERE they're visible (`index` scopes only its own `value`; `name`
    scopes to later statements in the same tuple), which is a lexical-scoping
    fact `_rewrite` must handle itself, not this registry (see the `LetStmt`
    branch in `_rewrite` and the sequential fold in `_rewrite_value`).

    Parameter-bearing declarations (`MoveTypeDef`, `RuleDef`, `FunctionDef`,
    `ProcedureDef`) are non-binding HERE by design, not by omission: their
    parameters scope to their own guard/effect/body only, which `_rewrite`
    implements in per-declaration arms, and `_check_reserved_params` sweeps
    them for reserved words. This registry answers for nodes a body walk can
    encounter, where the binder scopes within the walked tree itself."""
    match node:
        case n.Comprehension() | n.Quantifier() | n.ForEach():
            return (node.binder,)
        case n.EachSimultaneous():
            return (node.role,)
        case n.PlayerQuery():
            return ("player",)
        case n.CardQuery():
            return ("card",)
        case n.Movement() | n.EpistemicOp() if node.filter is not None:
            return ("card",)
        case n.LetStmt():
            return (node.name, node.index) if node.index is not None else (node.name,)
        case n.ProduceArm():
            # A `produces:` arm's payload binders (`Doubled(by, level) { … }`) are
            # user-chosen names bound in the arm body, and `_rewrite_produce_arm`
            # scopes them exactly like any other binder. Without this arm,
            # `_check_reserved_binders` never swept them, so an arm binder named
            # `actor` silently hijacked the pronoun (the body's bare `actor`
            # classified as that `local` instead), and `_check_functions` /
            # `_check_procedures` mistook a legitimately-bound arm name for an
            # unbound reference. Both fall out of the registry being complete.
            return node.binders
        case n.TypeDef():
            # A struct's declared field names, which `_classify_type_derived` scopes
            # as locals inside the type's derived-field bodies (`derived { seat =
            # actor }` reads sibling fields by bare name). The same mechanism as the
            # arm binders above, and so the same hazard: a field named `actor` is a
            # user-chosen name that shadows the call-site pronoun inside every
            # derived body. `_rewrite` returns early for `TypeDef` and scopes the
            # fields itself, so listing them here changes no scoping — it only makes
            # them visible to the sweeps that read this registry, which is the point.
            return tuple(f.name for f in node.fields)
        # A filter-less Movement/EpistemicOp falls through its guarded arm above:
        # no candidate set, so no `card` binder.
        case n.Movement() | n.EpistemicOp():
            return ()
        # Declarations and game/phase structure. (The parameter-bearing ones are
        # covered by `_rewrite` + `_check_reserved_params` — see the docstring.)
        case (
            n.Game() | n.PlayersSpec() | n.Winner() | n.Loser()
            | n.MoveTypeDef() | n.MoveParam() | n.RuleDef() | n.RuleRef()
            | n.AppliesWhen() | n.Demands()
            | n.DefineDef() | n.FunctionDef() | n.ProcedureDef()
            | n.VariantCase() | n.StructField() | n.DerivedField()
            | n.ZoneDecl() | n.TypeRef() | n.TypeArg()
            | n.StateBlock() | n.StateDecl()
            | n.Phase() | n.PhaseQualifier() | n.BeforeEach() | n.AfterEach()
            | n.ActiveRules() | n.LegalMoves() | n.TransitionTo() | n.MoveEvent()
        ):
            # `StateDecl` in particular: state variables are a flat, game-wide
            # declaration namespace (`_categories`'s `state_vars`), not a binder
            # any construct introduces.
            return ()
        # Statements that bind nothing.
        case (
            n.RotateStmt() | n.RepeatUntil() | n.IfStmt() | n.AssignStmt()
            | n.Offer() | n.Round() | n.Produce() | n.Produces()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt() | n.Block()
        ):
            return ()
        # Expressions that bind nothing.
        case (
            n.NameRef() | n.IntLit() | n.StrLit() | n.ListLit() | n.CardLiteral()
            | n.AllPlayers() | n.Member() | n.Subscript() | n.FieldInit()
            | n.StructLit() | n.Call() | n.NamedArg() | n.BinOp() | n.Not()
            | n.IsCheck() | n.IfExpr() | n.Choose()
        ):
            return ()
        case _:
            assert_never(node)


def _template_binders(rule: n.RuleDef) -> set[str]:
    """Every binder a rule body introduces — a parameter sharing one of these
    names would be captured by the binder instead of substituted."""
    out: set[str] = set()
    for nd in _walk(rule):
        out.update(_introduced_binders(nd))
    return out


def _check_template(rule: n.RuleDef, bag: DiagnosticBag) -> bool:
    """Validate a parameterized rule's declaration (Suit-only domains,
    corpus-first — recorded in roadmap.md; unique names; no binder capture).
    Returns False when instantiation cannot proceed."""
    ok = True
    names = [p.name for p in rule.params]
    for dup in sorted({nm for nm in names if names.count(nm) > 1}):
        bag.error(
            f"rule '{rule.name}' declares more than one parameter named "
            f"'{dup}' — substitution binds by name, so one would silently "
            f"shadow the other",
            rule.span,
        )
        ok = False
    binders = _template_binders(rule)
    for p in rule.params:
        if p.type_name != "Suit":
            bag.error(
                f"rule parameter '{p.name}: {p.type_name}' has an unsupported "
                f"domain — rule parameters support Suit only (corpus-first; "
                f"extend when a game needs another)",
                rule.span,
            )
            ok = False
        if p.name in binders:
            bag.error(
                f"rule '{rule.name}' introduces a binder named '{p.name}', "
                f"shadowing its own parameter — rename one",
                rule.span,
            )
            ok = False
    return ok


def _traverse(node: object, step: Callable[[str, object], object]) -> object:
    """The immutable one-level descent shared by every default-arm traversal
    in this module (`substitute`'s default arm, `_rewrite`'s default arm, and
    `_rewrite`'s per-field binder-scoping dispatch below): every dataclass
    field — guarded against `Span`, a leaf the walk must not open — is handed
    to `step` along with its field name, and replaced only where `step`
    actually returns something different. `dataclasses.replace` is skipped
    entirely when nothing changed, so an untouched subtree keeps its identity.
    Non-dataclass nodes (a tuple, a leaf) pass through unchanged — tuple
    mapping and leaf handling are the callers' job (`_substitute_value` /
    `_rewrite_value`), since the two differ there: `_rewrite_value`'s tuple
    arm folds `let` bindings sequentially into later siblings, which
    `substitute` (fixed-mapping template substitution, not scope-sensitive)
    has no need of."""
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = step(f.name, value)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def substitute(
    node: object, mapping: dict[str, n.Expr], ref_kind: str | None = None
) -> object:
    """Immutably replace every reference to a parameter with its argument
    expression — the ONE substitution mechanism, shared by the two constructs that
    splice a body into a site: rule-template instantiation (`_instantiate_rules`,
    below) and procedure expansion (`cardlang/expand.py`).

    The two differ only in when they run, which `ref_kind` expresses. Rule
    templates instantiate PRE-classification, where every `NameRef` is unresolved
    and a bare name match is all there is (`ref_kind=None`). Procedures expand
    POST-classification, so a parameter reference in the body carries
    `ref_kind == "local"` and the match can be exact — pass `ref_kind="local"` and
    a same-named zone or state variable can never be mistaken for the parameter."""
    if (
        isinstance(node, n.NameRef)
        and node.name in mapping
        and (ref_kind is None or node.ref_kind == ref_kind)
    ):
        return mapping[node.name]
    return _traverse(node, lambda _field, v: _substitute_value(v, mapping, ref_kind))


def _substitute_value(
    value: object, mapping: dict[str, n.Expr], ref_kind: str | None = None
) -> object:
    if is_dataclass(value) and not isinstance(value, Span):
        return substitute(value, mapping, ref_kind)
    if isinstance(value, tuple):
        return tuple(_substitute_value(item, mapping, ref_kind) for item in value)
    return value


def _instantiate_rules(game: n.Game, bag: DiagnosticBag) -> n.Game:
    """Resolve `active_rules` references against the game's own rules first,
    then the standard library (`cardlang/stdlib/rules.cardlang`):

    - a reference to a library rule the game does not define splices the
      library body into `game.rules` (defining a rule under a library name is
      rejected — a local copy would drift from the shared body silently);
    - a reference with arguments instantiates a parameterized rule (library or
      local) by substituting the arguments into the template body; the local
      template is replaced by its instance in place, so the runtime's
      name->rule index only ever sees concrete definitions.

    Every mismatch is a diagnostic, never a silent drop: args on a
    parameter-free rule, a parameterized rule referenced bare, arity/domain
    mismatches, two instantiations under one name with different arguments,
    and a local template no reference ever instantiates.

    Only `plain`/`add` refs reach any of that: the grammar gives `-NAME`
    (remove) and `override NAME` no argument list at all (cardlang.lark's
    `rule_remove`/`rule_override` productions), so neither can ever
    instantiate a template — asking one for "arguments" would be an
    unsatisfiable diagnostic (no source text repairs it). Both resolve by
    NAME alone: `remove` targets a rule a `plain`/`add` reference already
    activated in the same runtime-consulted scope (validated structurally by
    `_check_remove_reachability`, since `compute_active_rules` only ever
    removes a name it finds already present); `override` has no runtime
    support yet at all and is rejected unconditionally, once, by
    `_resolve_phase_item` — this loop skips it so that is the only diagnostic
    a game ever sees for it, not a second, unsatisfiable "pass arguments"
    alongside "not yet supported"."""
    lib = library_rules()
    local = {r.name: r for r in game.rules}
    for r in game.rules:
        if r.name in lib:
            bag.error(
                f"rule '{r.name}' shadows the standard-library rule of the same "
                f"name — delete the local definition (`active_rules` resolves it "
                f"from the library), or rename it if the body genuinely differs",
                r.span,
            )
    suits = deck_suits(game.deck) if _deck_known(game.deck) else None
    # rule name -> (argument key, concrete instance)
    instances: dict[str, tuple[tuple[str, ...], n.RuleDef]] = {}
    lib_order: list[str] = []
    # Each DISTINCT template's declaration validates once total, however many
    # refs instantiate it (or attempt to) — never once per activating phase
    # (a defective template referenced from two phases previously repeated its
    # diagnostics; `_check_template` is also the bottom loop's "never
    # instantiated" fallback below, so the cache spans both call sites).
    template_checked: dict[str, bool] = {}

    def check_template_once(name: str, template: n.RuleDef) -> bool:
        if name not in template_checked:
            template_checked[name] = _check_template(template, bag)
        return template_checked[name]

    for nd in _walk(game):
        if not isinstance(nd, n.ActiveRules):
            continue
        for ref in nd.refs:
            if ref.op in ("remove", "override"):
                continue
            template = local.get(ref.name, lib.get(ref.name))
            if template is None:
                continue  # undefined name: reported by _resolve_phase_level
            if not template.params:
                if ref.args:
                    bag.error(
                        f"rule '{ref.name}' takes no parameters — drop the "
                        f"argument list",
                        ref.span,
                    )
                elif ref.name not in local and ref.name not in instances:
                    instances[ref.name] = ((), template)
                    lib_order.append(ref.name)
                continue
            if not ref.args:
                bag.error(
                    f"rule '{ref.name}' is parameterized "
                    f"({', '.join(f'{p.name}: {p.type_name}' for p in template.params)}) "
                    f"— pass arguments: `{ref.name}(…)`",
                    ref.span,
                )
                continue
            if len(ref.args) != len(template.params):
                bag.error(
                    f"rule '{ref.name}' takes {len(template.params)} "
                    f"argument(s), got {len(ref.args)}",
                    ref.span,
                )
                continue
            if not check_template_once(ref.name, template):
                continue
            args_ok = True
            for arg, p in zip(ref.args, template.params):
                if not isinstance(arg, n.NameRef) or (
                    suits is not None and arg.name not in suits
                ):
                    bag.error(
                        f"argument for rule parameter '{p.name}: Suit' must be "
                        f"a suit literal (one of the deck's suits)",
                        ref.span,
                    )
                    args_ok = False
            if not args_ok:
                continue
            key = tuple(a.name for a in ref.args if isinstance(a, n.NameRef))
            if ref.name in instances:
                if instances[ref.name][0] != key:
                    bag.error(
                        f"rule '{ref.name}' is instantiated with different "
                        f"arguments elsewhere in this game — one instantiation "
                        f"per rule name (activate under distinct names when a "
                        f"game needs two)",
                        ref.span,
                    )
                continue
            mapping = {p.name: a for p, a in zip(template.params, ref.args)}
            inst = substitute(replace(template, params=()), mapping)
            assert isinstance(inst, n.RuleDef)
            instances[ref.name] = (key, inst)
            if ref.name not in local:
                lib_order.append(ref.name)
    rules: list[n.RuleDef] = []
    for r in game.rules:
        if not r.params:
            rules.append(r)
        elif r.name in instances:
            rules.append(instances[r.name][1])  # instance replaces its template
        else:
            check_template_once(r.name, r)  # surface declaration defects even here
            bag.error(
                f"rule '{r.name}' is parameterized but never instantiated — "
                f"reference it from `active_rules` with arguments, or delete it "
                f"(its body would otherwise go entirely unchecked)",
                r.span,
            )
    rules += [instances[name][1] for name in lib_order]
    return replace(game, rules=tuple(rules)) if tuple(rules) != game.rules else game


def _check_remove_reachability(phases: tuple[n.Phase, ...], bag: DiagnosticBag) -> None:
    """`-X` and (unsupported today) `override X` can never instantiate a rule
    (`_instantiate_rules`'s docstring) — they only resolve X by NAME against a
    rule a `plain`/`add` reference already activated. A reference to a name no
    `plain`/`add` ever activates in the scope the runtime actually consults is
    a structural no-op forever: `runtime/phases.py`'s `compute_active_rules`
    computes one phase's active set from exactly two sources — that phase's
    OWN `active_rules:` entries (applied unconditionally, in the list's own
    order), and, layered on top, each of its DIRECT rule-delta sub-phases
    (`_is_rule_delta` — a child phase with nothing but `active_rules:` /
    `legal_moves:` / `transition_to:` items, imported from there so the two
    can never drift) that is currently active — never a grandparent, and never
    a SIBLING delta sub-phase's own list alone (only one of a "before"/"after"
    pair is ever active at a time, so a name that pair's other branch alone
    added was never in `names` on this call either). This check mirrors that
    exact two-source shape: a `remove` inside a phase's own list validates
    against that same list; a `remove` inside a rule-delta sub-phase validates
    against its parent's list UNION its own. It does not model order WITHIN
    one list (an add-then-remove of the same name earlier in a parent's own
    list still counts as "added" for a child's cluster check below) — an
    accepted imprecision for a construct the corpus does not use at all
    (docs/roadmap.md records the residual)."""
    from cardlang.runtime.phases import _is_rule_delta

    for phase in phases:
        own_refs = [
            ref for item in phase.items if isinstance(item, n.ActiveRules) for ref in item.refs
        ]
        own_added = {r.name for r in own_refs if r.op in ("plain", "add")}
        _validate_removes(own_refs, own_added, bag)

        delta_children = [
            item for item in phase.items if isinstance(item, n.Phase) and _is_rule_delta(item)
        ]
        for child in delta_children:
            child_refs = [
                ref
                for item in child.items
                if isinstance(item, n.ActiveRules)
                for ref in item.refs
            ]
            cluster_added = own_added | {r.name for r in child_refs if r.op in ("plain", "add")}
            _validate_removes(child_refs, cluster_added, bag)

        # Recurse into every child phase EXCEPT the rule-delta ones just
        # handled above (against their parent's cluster) — revisiting them
        # generically here would re-check them against only their own narrow
        # list, which is not the scope the runtime actually consults for them.
        non_delta_children = tuple(
            item
            for item in phase.items
            if isinstance(item, n.Phase) and not any(item is d for d in delta_children)
        )
        _check_remove_reachability(non_delta_children, bag)


def _validate_removes(refs: list[n.RuleRef], added: set[str], bag: DiagnosticBag) -> None:
    for ref in refs:
        if ref.op == "remove" and ref.name not in added:
            bag.error(
                f"`-{ref.name}` removes a rule that is never added in scope "
                f"here (this phase's own `active_rules:`, or a sibling "
                f"rule-delta phase's) — add `{ref.name}` or `+{ref.name}` "
                f"there, or delete this removal",
                ref.span,
            )


def _check_chooses(game: n.Game, bag: DiagnosticBag) -> None:
    """Every integer `choose` must have a statically known, non-negative upper
    bound — the width the OpenSpiel action space reserves for it (decisions.md
    "The integer `choose` domain"). The bound comes from a literal upper range
    (`0 .. 13`) or an explicit `up to N` clause when the upper bound is a runtime
    expression; a runtime upper bound with no `up to` cannot be sized statically
    and is rejected here rather than papered over with a fixed constant (surface
    totality). `up to` on a literal upper bound is likewise rejected: the literal
    is already the exact ceiling, so an `up to` there is either contradictory (a
    ceiling below the literal makes the runtime range guard fail for every
    playout) or redundant (a ceiling above it mints action ids legal in no
    state) — never silently accepted. Finally, a literal lower bound above the
    ceiling (an inverted literal range like `5 .. 3`, or a literal `lo` past an
    `up to` ceiling) is rejected: the minimum candidate already exceeds every
    value the action space reserves, so no value can ever be chosen — a
    statically doomed program the runtime guard would otherwise only catch at
    playout."""
    for node in _walk(game):
        if not isinstance(node, n.Choose):
            continue
        # `static_ceiling` is a non-negative int (INT / IntLit) or None; only the
        # None case — a runtime `hi` with no `up to` — is possible from source.
        ceiling = n.static_ceiling(node)
        if ceiling is None:
            bag.error(
                "`choose integer` needs a statically known upper bound: either "
                "give it a literal upper bound (`0 .. 13`) or declare a ceiling "
                "with `up to N` (`0 .. hand_size up to 10`) — the OpenSpiel "
                "action space reserves that many ids up front",
                node.span,
            )
            continue
        if node.ceiling is not None and isinstance(node.hi, n.IntLit):
            bag.error(
                f"`choose integer` has a literal upper bound ({node.hi.value}), "
                f"which is already its static ceiling — remove the `up to "
                f"{node.ceiling}` clause (it applies only when the upper bound is "
                f"a runtime expression)",
                node.span,
            )
        # A literal lower bound is the smallest value the choose could ever
        # offer; if it exceeds the ceiling, every candidate escapes the reserved
        # `0 .. ceiling` block (or the range is outright empty), so the choose
        # can never yield a value. `lo` scopes to a literal — a runtime `lo` is
        # not statically decidable and the runtime range guard covers it.
        if isinstance(node.lo, n.IntLit) and node.lo.value > ceiling:
            bag.error(
                f"`choose integer` lower bound ({node.lo.value}) exceeds its "
                f"ceiling ({ceiling}): the range is statically empty (or every "
                f"value would fall outside the reserved action block), so no "
                f"value can ever be chosen — lower the start or raise the bound",
                node.span,
            )


def _resolve_max_length(game: n.Game, bag: DiagnosticBag) -> None:
    if game.max_length is None:
        bag.error(
            f"game '{game.name}' must declare `max_length: <n>` — a bound on "
            "decision/loop iterations the runtime enforces and the OpenSpiel "
            "adapter reports (docs/decisions.md, \"Game length as a declared "
            "contract\")",
            game.span,
        )
    elif game.max_length <= 0:
        bag.error(
            f"game '{game.name}' declares `max_length: {game.max_length}` — "
            "it must be a positive integer",
            game.span,
        )


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
    # A card-set `demands` can filter the legal set to empty; the rule must say
    # what happens then (`if_impossible`) rather than relying on a silent default.
    # `actions where` demands constrain the choose-count, not the card set, so
    # they are exempt (no implicit actions — see decisions.md "No implicit actions").
    if (
        rule.demands is not None
        and rule.demands.kind == "cards"
        and rule.if_impossible is None
    ):
        bag.error(
            f"rule '{rule.name}' has a card-set `demands` but no `if_impossible`: "
            f"declare the fallback when no card satisfies it (`if_impossible: hand` "
            f"to play any card, or `error(...)` to reject the move)",
            rule.span,
        )


def _resolve_phase_level(
    phases: tuple[n.Phase, ...], known_rule_names: set[str], bag: DiagnosticBag
) -> None:
    """Resolve a set of sibling phases, then recurse into each one's children.

    Transition targets resolve against the *sibling* set, since
    `transition_to: Y` inside phase X names a sibling of X.
    """
    sibling_names = {p.name for p in phases}
    for phase in phases:
        # Combination validity (decisions.md "Surface totality"): the runtime
        # declares only a phase's FIRST state block and runs the lifecycle
        # hooks only on a `repeat until` phase — reject what it would
        # silently drop.
        state_blocks = [i for i in phase.items if isinstance(i, n.StateBlock)]
        if len(state_blocks) > 1:
            bag.error(
                f"phase '{phase.name}' declares more than one `state {{ }}` "
                f"block — merge the declarations into one",
                state_blocks[1].span,
            )
        if phase.qualifier is None or phase.qualifier.kind != "repeats":
            for hook in phase.items:
                if isinstance(hook, (n.BeforeEach, n.AfterEach)):
                    kw = "before_each" if isinstance(hook, n.BeforeEach) else "after_each"
                    bag.error(
                        f"`{kw}` runs per iteration of a `repeat until` phase; "
                        f"phase '{phase.name}' has no iteration — put the "
                        f"statements in the phase body",
                        hook.span,
                    )
        for item in phase.items:
            _resolve_phase_item(item, sibling_names, known_rule_names, bag)
        children = tuple(i for i in phase.items if isinstance(i, n.Phase))
        _resolve_phase_level(children, known_rule_names, bag)


def _resolve_phase_item(
    item: n.PhaseItem,
    sibling_names: set[str],
    known_rule_names: set[str],
    bag: DiagnosticBag,
) -> None:
    if isinstance(item, n.ActiveRules):
        for ref in item.refs:
            if ref.name not in known_rule_names:
                bag.error(f"active_rules names undefined rule '{ref.name}'", ref.span)
            if ref.op == "override":
                bag.error(
                    f"`override {ref.name}` is not yet supported by the runtime "
                    f"(roadmap.md) — use `add`/`remove` deltas",
                    ref.span,
                )
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
        elif item.event.move_type != "play_to_trick":
            bag.error(
                f"transitions fire from trick plays only today: the event move "
                f"type must be `play_to_trick`, not "
                f"'{item.event.move_type}' (roadmap.md)",
                item.event.span,
            )
    elif isinstance(item, (n.Phase, n.StateBlock, n.BeforeEach, n.AfterEach)):
        # Phases recurse via the level walk; state blocks resolve later; hook
        # bodies are plain statement sequences with nothing item-level to check.
        pass
    else:
        # `item` is a statement — nothing to resolve at phase-item level. The
        # annotated assignment is the exhaustiveness pin: a new PhaseItem block
        # kind falls here and fails mypy until this function decides what to do
        # with it. (A statement walk used to hang off this arm; its one leaf
        # check died with the `instantiate` construct and the walk sat vacuous —
        # recursing into every body, checking nothing. Deleted, not kept.)
        _only_statements_reach_here: n.Stmt = item


@dataclass(frozen=True)
class _Categories:
    """The namespaces a bare name resolves against, collected once per game.

    Every field but `locals` is game-wide and fixed by `_categories` below.
    `locals` is lexical, not game-wide: it starts empty (a bare binder name
    resolves nowhere until something scopes it in) and `_rewrite` extends it
    with `replace(cats, locals=cats.locals | {...})` for exactly the sub-fields
    of a binder-introducing node (`_BINDER_SCOPE_FIELDS`, keyed by
    `_introduced_binders`) or the tail of a statement tuple after a `let`
    (the sequential fold in `_rewrite_value`) — never wider than that subtree."""

    locals: frozenset[str]
    state_vars: frozenset[str]
    zones: frozenset[str]
    enums: frozenset[str]
    functions: frozenset[str]
    ranks: frozenset[str]
    suits: frozenset[str]


def _walk(node: object) -> Iterator[object]:
    """Yield every AST node under (and including) ``node``, skipping spans."""
    if not is_dataclass(node) or isinstance(node, Span):
        return
    yield node
    for f in fields(node):
        value = getattr(node, f.name)
        yield from _child_nodes(value)


def _child_nodes(value: object) -> Iterator[object]:
    if is_dataclass(value) and not isinstance(value, Span):
        yield from _walk(value)
    elif isinstance(value, tuple):
        for item in value:
            yield from _child_nodes(item)


def _categories(game: n.Game) -> _Categories:
    # `locals` starts empty here: binders (comprehension/quantifier/query/
    # for-each/each-simultaneous/movement-filter/let) are lexically scoped by
    # `_rewrite`, not collected game-wide — see the `_Categories` docstring.
    # State vars remain game-wide: `state { }` (top-level or phase-local) is a
    # single flat declaration namespace (`_check_duplicate_names` enforces
    # uniqueness across it), not a binder any construct introduces.
    state_vars = {nd.name for nd in _walk(game) if isinstance(nd, n.StateDecl)}
    return _Categories(
        locals=frozenset(),
        state_vars=frozenset(state_vars),
        zones=frozenset(z.name for z in game.zones),
        enums=enum_values(game.deck) if _deck_known(game.deck) else DIRECTION_VALUES,
        functions=STDLIB_VALUE_NAMES,
        # Card-literal validation asks "does this card EXIST in the deck",
        # so ranks derive from the deck like `suits` below — never from
        # `ranking:`, which is an ORDERING (optional, and legitimately
        # partial: it narrows the Rank move-param domain, not which cards
        # can be named). Deck-vs-ranking is the same two-source divergence
        # `_resolve_ranking` walls from the other side (Codex review of
        # PR #48, round 2).
        ranks=deck_ranks(game.deck) if _deck_known(game.deck) else frozenset(),
        suits=deck_suits(game.deck) if _deck_known(game.deck) else frozenset(),
    )


def _check_duplicate_names(game: n.Game, bag: DiagnosticBag) -> None:
    """Every declaration namespace enforces uniqueness (closed-domain
    completeness): a duplicated name would otherwise shadow silently,
    last-wins — accepted-but-ignored at the declaration level. Scopes that
    legitimately shadow ACROSS levels (a phase-local state var over a game
    var) are separate namespaces and stay legal; duplication is rejected
    only WITHIN one declaration list.

    The same sweep also rejects `RESERVED_VALUE_NAMES` (`reserved=True`
    namespaces only): zones, functions, user type names, and state variables
    are all reachable as a bare `NameRef` in general expression position,
    where a reserved word never means "the declaration" (see
    `RESERVED_VALUE_NAMES`'s docstring). Move-type/rule NAMES, `define`
    names, type FIELD names, and phase names are exempt — none is ever
    referenced as a bare NameRef (each lives in its own fixed syntactic slot:
    `constrains:`, `active_rules:`/`legal_moves:`, `produces:`, `x.field`,
    `transition_to:`), so no reserved word can hijack one."""

    def check(
        kind: str,
        named: "Iterator[object] | tuple[object, ...] | list[object]",
        reserved: bool = False,
    ) -> None:
        seen: dict[str, object] = {}
        for decl in named:
            name = getattr(decl, "name")
            if name in seen:
                bag.error(
                    f"duplicate {kind} '{name}' — the later declaration would "
                    f"silently shadow the earlier one",
                    getattr(decl, "span", None),
                )
            seen[name] = decl
            if reserved:
                _check_reserved(name, kind, getattr(decl, "span", None), bag)

    check("zone", game.zones, reserved=True)
    check("move_type", game.move_types)
    check("type", game.types, reserved=True)
    check("define", game.defines)
    check("function", game.functions, reserved=True)
    check("procedure", game.procedures)
    check("rule", game.rules)
    if game.state is not None:
        check("state variable", game.state.decls, reserved=True)
    phases: list[object] = []
    for nd in _walk(game):
        if isinstance(nd, n.Phase):
            phases.append(nd)
        elif isinstance(nd, n.StateBlock) and nd is not game.state:
            check("state variable", nd.decls, reserved=True)
        elif isinstance(nd, n.TypeDef):
            check(f"field in type '{nd.name}'", nd.fields)
    check("phase", phases)


# The param-bearing declaration kinds: node type -> (the `Game` collection that
# holds them, the diagnostic noun, the reserved set their parameters check
# against). This table is pinned to the AST by tests/test_node_registry.py —
# every `Node` member with a `params` field must have a row — so a new
# parameterized declaration form cannot ship with its parameters silently
# exempt from the reserved-word sweep. (The pronoun carve-out below: function
# and procedure bodies are hermetic — forbidden from READING the call-site
# pronouns — so naming a parameter after one is that error message's own
# prescribed fix, not a hijack. Move-type/rule bodies read the pronouns live,
# so all five stay reserved there. See `_check_reserved_params`.)
_PARAM_BEARING: dict[type, tuple[str, str, frozenset[str]]] = {
    n.FunctionDef: (
        "functions",
        "function parameter",
        RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS,
    ),
    n.ProcedureDef: (
        "procedures",
        "procedure parameter",
        RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS,
    ),
    n.MoveTypeDef: ("move_types", "move-type parameter", RESERVED_VALUE_NAMES),
    n.RuleDef: ("rules", "rule parameter", RESERVED_VALUE_NAMES),
}


def _check_reserved_params(game: n.Game, bag: DiagnosticBag) -> None:
    """Function/move-type/rule parameters are declarations `_check_duplicate_names`
    never reaches (they live on `.params`, not one of its top-level lists) but
    are reachable as a bare `NameRef` inside the body exactly like a state
    variable — a parameter named `empty` is just as unreferenceable via
    `x is empty` as a state variable of the same name would be.

    Function parameters are the ONE exception to `RESERVED_VALUE_NAMES` in
    full: `_CALL_SITE_PRONOUNS` (`actor`/`action`/`outcome`) is exactly the
    set a function body is already forbidden from READING (the runtime
    clears them before a hermetic call — `_check_functions`'s "pass the
    value in as a parameter instead"), so naming a parameter after one is
    not a hijack, it is that error message's own prescribed fix — pinned by
    `tests/test_functions.py::test_function_param_does_not_leak_into_pronoun_sites`
    (`function lead(actor : Player) = score[actor]`). `state`/`active_rules`
    stay reserved for function parameters too: those two remain READABLE
    inside a function body, so a same-named parameter would still shadow
    them. Move-type/rule bodies are not hermetic — they read
    `actor`/`action`/`outcome` directly as live pronouns — so all five stay
    reserved for their parameters."""
    for attr, kind, reserved in _PARAM_BEARING.values():
        for decl in getattr(game, attr):
            for p in decl.params:
                _check_reserved(p.name, kind, p.span, bag, reserved)


def _check_reserved_binders(game: n.Game, bag: DiagnosticBag) -> None:
    """Sweep every binder-introducing node via `_introduced_binders` — the one
    registry of which node kinds bind names — rather than re-enumerating the
    user-choosing ones by hand. This reserved-word check is safe to apply
    uniformly to EVERY name `_introduced_binders` returns, including the FIXED
    ones (`card`/`player`/the quantifier role noun): none of those spellings is
    ever in `RESERVED_VALUE_NAMES` (deliberately — see its docstring), so the
    check is a no-op for them and only ever fires for the genuinely
    user-chosen binders: `for each <role> <binder>:`, `each <role>
    simultaneously:`, and `let <name>[<index>]`."""
    for nd in _walk(game):
        for name in _introduced_binders(nd):
            _check_reserved(name, "binder", getattr(nd, "span", None), bag)


def _deck_known(deck: str) -> bool:
    from cardlang.runtime.values import DECKS

    return deck in DECKS


def _resolve_deck(game: n.Game, bag: DiagnosticBag) -> None:
    """An unknown deck name is a diagnostic, never a raw registry raise from
    inside category building (the suit registry derives from the runtime deck
    table, which fails loudly for unknown names — correct at playout time,
    wrong as a designer-facing check). The categories fall back to an empty
    suit namespace so the rest of the file's diagnostics still collect."""
    if not _deck_known(game.deck):
        from cardlang.runtime.values import DECKS

        bag.error(
            f"unknown deck '{game.deck}' — known decks: {', '.join(sorted(DECKS))}",
            None,
        )


def _resolve_ranking(game: n.Game, bag: DiagnosticBag) -> None:
    """`ranking:` entries must name real ranks of the declared deck. Unchecked,
    a typo (`11` for `10`) silently widens typecheck's Rank enum domain
    (`value_enum_map` unions `game.ranking` into it) rather than erroring: the
    mistyped literal then type-checks fine and every comparison against it is
    simply False forever, at runtime, with no diagnostic anywhere (Surface
    totality). A repeated entry is rejected too — `driver.py` builds
    `rs.rank_index` from `enumerate(game.ranking)`, so a duplicate would
    silently give one rank two strengths and shift the intended strength of
    every rank after it, last-wins, with no error.

    Coverage is NOT required: `ranking:` may legitimately be a PARTIAL
    permutation of the deck's ranks. Every `docs/games/*.cardlang` ranking
    happens to be a full permutation of its deck, but
    `tests/test_action_space_multiparam.py`'s subset-ranking regression
    (`test_rank_domain_sourced_from_game_ranking_not_deck`) pins a partial
    `ranking:` as a deliberate, supported feature — it narrows the `Rank`
    move-parameter domain to fewer than the deck's ranks. A card whose rank
    falls outside a partial ranking still crashes `rank_value`'s
    `ctx.rs.rank_index[...]` lookup at runtime instead of erroring here — an
    accepted residual (docs/roadmap.md), walled only by that runtime
    KeyError, not by this check."""
    if not game.ranking or not _deck_known(game.deck):
        return
    known = deck_ranks(game.deck)
    seen: dict[str, None] = {}
    for rank in game.ranking:
        if rank in seen:
            bag.error(
                f"ranking: repeats rank '{rank}' — each rank may appear at "
                f"most once (a duplicate would silently give it two "
                f"strengths and shift every rank after it down by one)",
                game.span,
            )
        seen[rank] = None
        if rank not in known:
            bag.error(
                f"ranking: names unknown rank '{rank}' — not a rank of deck "
                f"'{game.deck}' (known ranks: {', '.join(sorted(known))})",
                game.span,
            )


def _classify(name: str, cats: _Categories) -> str | None:
    if name == "none":
        return "null"  # the universal absence literal (any optional's null)
    if name in ("true", "false"):
        return "bool"  # boolean literals
    if name in cats.locals:
        return "local"
    if name in cats.state_vars:
        return "state_var"
    if name in cats.zones:
        return "zone"
    if name in cats.enums:
        return "enum_value"
    if name in _PRONOUNS:
        return "pronoun"
    if name in cats.functions:
        return "function"
    return None


def _classify_names(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> n.Game:
    """Immutably rewrite every NameRef with its classification, recording an
    error for any name that resolves to nothing."""
    result = _rewrite(game, cats, bag)
    assert isinstance(result, n.Game)
    types = tuple(_classify_type_derived(t, cats, bag) for t in result.types)
    return replace(result, types=types)


def _classify_type_derived(
    tdef: n.TypeDef, cats: _Categories, bag: DiagnosticBag
) -> n.TypeDef:
    """Rewrite a type's derived-field bodies with the type's own fields in local
    scope — derived expressions reference sibling fields by bare name, which the
    generic pass (blind to struct fields) would flag as unresolved."""
    field_names = frozenset(f.name for f in tdef.fields)
    scoped = replace(cats, locals=cats.locals | field_names)
    derived = tuple(
        replace(d, value=_rewrite(d.value, scoped, bag))  # type: ignore[arg-type]
        for d in tdef.derived
    )
    return replace(tdef, derived=derived)


def _rewrite_produce_arm(
    arm: n.ProduceArm, cats: _Categories, bag: DiagnosticBag
) -> n.ProduceArm:
    """Rewrite one produces-arm body with the arm's payload binders in local
    scope — so bare binder references resolve, without leaking into other arms or
    the enclosing game (mirrors `_classify_type_derived` for struct fields)."""
    scoped = replace(cats, locals=cats.locals | frozenset(arm.binders))
    # Route through `_rewrite_value` (not a bare per-item `_rewrite` map) so a
    # `let` inside the arm body scopes to the arm's later statements too — the
    # same sequential fold every other statement tuple gets.
    body = _rewrite_value(arm.body, scoped, bag)
    return replace(arm, body=body)  # type: ignore[arg-type]


# Binder-introducing node kinds `_rewrite` scopes to specific sub-fields only
# (lexical scoping): each maps to the field name(s) whose subtree sees the
# node's own binder(s) (from `_introduced_binders`) added to `cats.locals` —
# every other field of the node keeps the enclosing scope. A source/default
# field is deliberately absent from a comprehension's/card-query's entry: the
# source zone and the empty-set default are evaluated outside the element
# scope (mirrors typecheck.py `_check_expr`'s identical split). `LetStmt` is
# handled separately in `_rewrite` (its `index` scopes only its own `value`;
# its `name` scopes forward to later statements, not to any field of its own
# node — see the sequential fold in `_rewrite_value`'s tuple arm) and so has
# no entry here.
_BINDER_SCOPE_FIELDS: dict[type, tuple[str, ...]] = {
    n.Quantifier: ("body",),
    n.Comprehension: ("filter", "body"),
    n.CardQuery: ("pred",),
    n.PlayerQuery: ("pred",),
    n.Movement: ("filter",),
    n.EpistemicOp: ("filter",),
    n.ForEach: ("body",),
    n.EachSimultaneous: ("body",),
}


def _rewrite(node: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if isinstance(node, n.NameRef):
        kind = _classify(node.name, cats)
        if kind is None:
            hint = ""
            if node.name == "card":
                hint = (
                    " (`card` is bound only inside a card query, an "
                    "aggregation, or a `where` filter)"
                )
            elif node.name == "player":
                hint = " (`player` is bound only inside a player query or quantifier)"
            bag.error(f"unresolved name '{node.name}'{hint}", node.span)
        return replace(node, ref_kind=kind)
    if isinstance(node, n.TypeDef):
        return node  # derived bodies are rewritten by _classify_type_derived
    if isinstance(node, n.Produces):
        # Each arm's payload binders scope to that arm's body only — they must not
        # leak into the global `locals` set (which would shadow same-named state
        # vars across the whole game).
        arms = tuple(_rewrite_produce_arm(arm, cats, bag) for arm in node.arms)
        return replace(node, arms=arms)
    if isinstance(node, n.MoveTypeDef):
        # The parameters bind only in this move's guard/effect — scope them here
        # rather than the game-wide `locals` set (which would shadow a same-named
        # state var everywhere; mirrors the produce-arm binders above, and the
        # function-parameter branch below for the identical params-tuple shape).
        scoped = (
            replace(cats, locals=cats.locals | {p.name for p in node.params})
            if node.params
            else cats
        )
        guard = _rewrite_value(node.guard, scoped, bag) if node.guard is not None else None
        # `_rewrite_value` (not a bare per-item `_rewrite` map): a `let` in a
        # move's effect scopes to the statements after it, like everywhere else.
        effect = _rewrite_value(node.effect, scoped, bag)
        return replace(node, guard=guard, effect=effect)  # type: ignore[arg-type]
    if isinstance(node, n.FunctionDef):
        # The parameters bind only in this function's body — scope them here rather
        # than the game-wide `locals` set (mirrors the move-type/produce-arm binders
        # above). A bare name in the body that is neither a parameter nor a binding
        # it introduces stays un-shadowed, so the hermeticity check can catch it.
        scoped = replace(cats, locals=cats.locals | {p.name for p in node.params})
        body = _rewrite_value(node.body, scoped, bag)
        return replace(node, body=body)  # type: ignore[arg-type]
    if isinstance(node, n.ProcedureDef):
        # Same isolation as a function: the parameters bind only in this body, and
        # a bare name that is neither a parameter nor a binding the body introduces
        # stays un-shadowed so `_check_procedures` can catch it. `_rewrite_value`
        # (not a per-item map) so a `let` in the body scopes to the statements after
        # it, exactly as it will once the body is spliced inline.
        scoped = replace(cats, locals=cats.locals | {p.name for p in node.params})
        body = _rewrite_value(node.body, scoped, bag)
        return replace(node, body=body)  # type: ignore[arg-type]
    if isinstance(node, n.LetStmt):
        # `index` (the indexed form's per-key binder, `let base[p] = …`) scopes
        # only to this let's own `value` — evaluated once per key and gone
        # afterward (`runtime/execute.py:_let`), unlike `name`. `name` is NOT
        # scoped here: it becomes visible to statements after this one in the
        # same tuple, folded by `_rewrite_value`'s tuple arm below.
        scoped = replace(cats, locals=cats.locals | {node.index}) if node.index is not None else cats
        value = _rewrite_value(node.value, scoped, bag)
        return replace(node, value=value)  # type: ignore[arg-type]
    scope_fields = _BINDER_SCOPE_FIELDS.get(type(node))
    if scope_fields is not None:
        binders = _introduced_binders(node)
        if binders:  # a filter-less Movement/EpistemicOp introduces nothing
            scoped = replace(cats, locals=cats.locals | frozenset(binders))
            return _traverse(
                node,
                lambda f, v: _rewrite_value(v, scoped if f in scope_fields else cats, bag),
            )
    return _traverse(node, lambda _field, v: _rewrite_value(v, cats, bag))


def _rewrite_value(value: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, cats, bag)
    if isinstance(value, tuple):
        # A `let` binds its name for the REST of this tuple (the sequential-`let`
        # idiom every statement-sequence site shares — Phase.items, if/else
        # bodies, repeat/lifecycle-hook bodies, move-type effects, produce-arm
        # bodies: every tuple a `Stmt`/`PhaseItem` sequence can occur in). This
        # fold is safe to apply to EVERY tuple field generically, not just
        # statement sequences: a `LetStmt` node can only ever appear inside one
        # of those Stmt-typed tuples (the grammar has no other production that
        # embeds a statement), so the `isinstance` check below is a no-op on
        # every other kind of tuple (zones, rule params, call args, …).
        out: list[object] = []
        current = cats
        for item in value:
            rewritten = _rewrite_value(item, current, bag)
            out.append(rewritten)
            if isinstance(rewritten, n.LetStmt):
                current = replace(current, locals=current.locals | {rewritten.name})
        return tuple(out)
    return value


def _check_functions(game: n.Game, bag: DiagnosticBag) -> None:
    """Functions are hermetic and non-recursive: a body may reference only its own
    parameters, binders it introduces (`number of players where …`), and game/phase
    state — not a name the flat classifier tagged `local` from some unrelated binder,
    and not the call-site pronouns `actor`/`action`/`outcome` (the runtime clears
    them); and the call graph must be acyclic (a cycle would loop forever at runtime).
    A function may not reuse a stdlib call name: a call would type-check against the
    stdlib signature but dispatch to the user function at run time."""
    fn_names = {f.name for f in game.functions}
    calls: dict[str, set[str]] = {
        f.name: {c.func for c in _walk(f.body) if isinstance(c, n.Call) and c.func in fn_names}
        for f in game.functions
    }
    for fn in game.functions:
        if fn.name in STDLIB_CALL_FUNCS:
            bag.error(
                f"function '{fn.name}' shadows the stdlib function of the same name; "
                f"rename it (a call would type-check against the stdlib signature but "
                f"run this function instead)",
                fn.span,
            )
        allowed = {p.name for p in fn.params}
        for nd in _walk(fn.body):  # binders the body itself introduces are in scope
            allowed.update(_introduced_binders(nd))
        for nd in _walk(fn.body):
            if not isinstance(nd, n.NameRef):
                continue
            if nd.ref_kind == "local" and nd.name not in allowed:
                bag.error(
                    f"function '{fn.name}' references '{nd.name}', which is not one of "
                    f"its parameters or a binding in its body",
                    nd.span,
                )
            elif nd.ref_kind == "pronoun" and nd.name in _CALL_SITE_PRONOUNS:
                bag.error(
                    f"function '{fn.name}' reads the call-site pronoun '{nd.name}'; a "
                    f"function is hermetic and may not read actor/action/outcome — "
                    f"pass the value in as a parameter",
                    nd.span,
                )
        if _reaches(fn.name, fn.name, calls):
            bag.error(
                f"function '{fn.name}' is recursive; functions must be non-recursive",
                fn.span,
            )


# The closed set of procedure-parameter domains (decisions.md "Named
# procedures"), corpus-first. Unlike a move parameter, a procedure argument is
# an arbitrary expression rather than a value the action space must enumerate,
# so this set gates what an argument may *denote*, not what can be enumerated —
# which is why it is a separate registry from `_FIXED_DOMAINS` below and not a
# slice of it. `Zone` is deliberately absent: the design note guessed the corpus
# would need it, and the corpus disagreed (Coup's blocks reach their zones by
# indexing a zone family with the player parameter — `influence[victim]` — so a
# Player parameter already carries the zone). Recorded in roadmap.md; extend
# when a game forces it.
#
# `Rank?` and not `Rank`: Coup's proven-claim swap is called both with a literal
# character (`run prove_claim(actor, Duke)`) and with the block claim, which is a
# `Rank?` because "no block" is a real state. The call sites all sit inside `if
# block_claim is not none`, but the language has no flow narrowing, so a bare
# `Rank` parameter would reject the very argument the block sites must pass. A
# `Rank?` parameter accepts both (`assignable(Rank, Rank?)`), which is why the
# optional form is the one the corpus forces. Bare `Rank` rides along: it is the
# same domain minus the null, meaningful on its own, and free to support.
_PROCEDURE_PARAM_DOMAINS = frozenset({"Player", "Rank", "Rank?"})


# POSITION-DEPENDENT STATEMENTS: the closed class a procedure body may not hold.
#
# A procedure body is written once and spliced into many sites. Any statement whose
# VALIDITY depends on where it sits is therefore unsound in one — the checker sees
# it once, at the declaration, where the surrounding context does not exist yet, and
# the copies it is checked as are never checked again (expansion runs after
# typecheck, which is what makes the parameter types enforceable).
#
# The class is closed by enumerating the checks that are themselves
# position-dependent, not by intuition:
#
#   `_check_outcome_scope`         a `produces:` consumer must name an EARLIER-executed
#                                  sibling phase; `continue to` a LATER one; `skip to
#                                  next hand` must sit inside a hand loop
#   `_check_single_outcome_consumer`  a phase outcome has exactly ONE consumer — a
#                                  count, which a second `run` changes
#   `_check_misplaced_produce`     `produce` terminates the enclosing `define`
#   outcome binding                a `round` binds its own `outcome` for the statements
#                                  after it, which the body's pronoun wall cannot tell
#                                  from the caller's call-site `outcome`
#
# Every statement those checks govern is rejected in a body. The two remaining
# position-sensitive passes — `deckcheck.check_capacity` and the OpenSpiel action
# space — both run AFTER expansion and so see the real, spliced tree.
#
# A `produces:` over a DEFINE is not in the class: a define is invoked fresh at each
# site and has no ordering or uniqueness rule, which is why it stays allowed.
_NON_LOCAL_STMTS = (n.Produce, n.ContinueTo, n.SkipToNextHand)
_OUTCOME_BINDING_STMTS = (n.Round,)


# What a write target may be. `:=`, `+=`, `-=` and `rotate` all write persistent
# state (`runtime/execute.py`'s `_assign` -> `rs.set`, `_rotate`), and persistent state
# is the only thing they can write — so a write target must classify as a state
# variable, full stop.
#
# This is one rule and not three walls because the target is a `NameRef`: it goes
# through `_classify` like every read, so "what is this name?" is already answered by
# the time we get here. Before, it was a bare `str` that no name check ever saw, and
# the three ways it could go wrong needed three separate hand-written checks — one of
# which (the plain typo) nobody had written, so `totaly_score := 1` reached the runtime
# as a bare KeyError.
#
# The subtle one is a binder shadowing a state variable. A READ resolves binders BEFORE
# state variables; a write goes to state regardless. So `let turn = …` followed by
# `turn := 1` used to write the state variable while every `turn` around it meant the
# binder — one name, two things, silently. Classifying the target makes that impossible
# rather than merely detected: the target resolves to the binder, and a binder is not
# assignable.
_WRITE_TARGET_KINDS: dict[str, str] = {
    "local": "a binder (a `let`, a loop binder, or a parameter)",
    "zone": "a zone",
    "enum_value": "a value of the deck",
    "null": "the literal `none`",
    "bool": "a boolean literal",
    "pronoun": "a pronoun",
    "function": "a function",
}


def _bad_write_target(node: n.AssignStmt | n.RotateStmt) -> str | None:
    """Why this write target is illegal, or None if it is a state variable."""
    verb = "assign to" if isinstance(node, n.AssignStmt) else "rotate"
    kind = node.target.ref_kind
    if kind == "state_var":
        return None
    if kind is None:
        return None  # unresolved: `_classify` has already reported it, by name
    what = _WRITE_TARGET_KINDS.get(kind, f"a {kind}")
    return (
        f"cannot {verb} '{node.target.name}': it is {what}, and only a declared state "
        f"variable can be written. A binder is a bound value, not a variable — and if "
        f"a state variable of the same name exists, the two would not agree anyway "
        f"(a read here means the binder; a write always goes to state)"
    )


def _bad_zone_endpoint(expr: n.Expr | None, what: str) -> str | None:
    """Why this movement endpoint (`from <here>` / `to <here>`) is illegal, or
    None. The same move as `_bad_write_target`, one grammar position over: an
    endpoint is name-shaped (the grammar rejects literals there), so its ROOT
    name has a classification, and most classifications cannot possibly be a
    zone. `deal 1 cards from turn to each hand` (with `turn : Integer`) used to
    check clean and die mid-playout on a bare AssertionError in the executor —
    a statically nameable error in the wrong currency at the wrong time.

    A `local` root stays accepted: a binder may legitimately hold a zone value
    (`for each player p: move all cards from hand[p] …` subscripts one), and
    locals are untyped until the scoped-typing work lands (roadmap.md, "Locals
    are typed") — the executor's Zone check remains the loud backstop for that
    residual."""
    root = expr
    while isinstance(root, (n.Subscript, n.Member)):
        root = root.obj
    if not isinstance(root, n.NameRef):
        return None  # not name-rooted: nothing to classify here
    kind = root.ref_kind
    if kind is None or kind in ("zone", "local"):
        return None  # None: unresolved, already reported by the classifier
    what_it_is = _WRITE_TARGET_KINDS.get(kind, f"a {kind}")
    if kind == "state_var":
        what_it_is = "a state variable"
    return (
        f"cannot move cards {what} '{root.name}': it is {what_it_is}, not a zone"
    )


def _check_procedures(game: n.Game, bag: DiagnosticBag) -> None:
    """A procedure body must read as the statements it becomes. Hermeticity is the
    same as a function's — a body references only its own parameters, the binders
    it introduces, and game/phase state, never the caller's locals and never the
    call-site pronouns, so its meaning cannot depend on where it is run from.

    Only ONE hygiene wall lives here, because `expand` makes the rest unnecessary
    by construction: it binds each argument to a `let` in the CALLER's context
    before the body runs (so nothing in the body can capture an argument, and an
    argument naming the actor cannot be re-read under a construct that rebinds it),
    and it wraps the body in a block (so the body's own bindings cannot leak into
    the caller). What expansion cannot fix is a body binder sharing a PARAMETER's
    name: classification tags both `local`, so substitution cannot tell them apart.
    That one is rejected outright.
    """
    known = {p.name: p for p in game.procedures}
    outcome_phases = {
        nd.name for nd in _walk(game) if isinstance(nd, n.Phase) and nd.outcome_cases
    }
    for proc in game.procedures:
        params = {p.name for p in proc.params}

        names = [p.name for p in proc.params]
        for dup in sorted({nm for nm in names if names.count(nm) > 1}):
            bag.error(
                f"procedure '{proc.name}' declares more than one parameter named "
                f"'{dup}' — substitution binds by name, so one would silently "
                f"shadow the other",
                proc.span,
            )
        for p in proc.params:
            if p.type_name not in _PROCEDURE_PARAM_DOMAINS:
                bag.error(
                    f"procedure parameter '{p.name}: {p.type_name}' has an "
                    f"unsupported domain — procedure parameters support "
                    f"{', '.join(sorted(_PROCEDURE_PARAM_DOMAINS))} only "
                    f"(corpus-first; extend when a game needs another)",
                    p.span,
                )

        # Binders the body introduces, and the name-capture wall: a binder
        # sharing a parameter's name would capture it instead of substituting.
        binders: set[str] = set()
        for nd in _walk(proc):
            binders.update(_introduced_binders(nd))
        for p in proc.params:
            if p.name in binders:
                bag.error(
                    f"procedure '{proc.name}' introduces a binder named "
                    f"'{p.name}', shadowing its own parameter — rename one",
                    proc.span,
                )

        if not proc.body:
            bag.error(
                f"procedure '{proc.name}' has an empty body — it would splice "
                f"nothing at every site that runs it; give it statements or delete it",
                proc.span,
            )

        allowed = params | binders
        for stmt in proc.body:
            for nd in _walk(stmt):
                if isinstance(nd, _NON_LOCAL_STMTS):
                    what = {
                        n.Produce: "`produce`",
                        n.ContinueTo: "`continue to`",
                        n.SkipToNextHand: "`skip to next hand`",
                    }[type(nd)]
                    bag.error(
                        f"procedure '{proc.name}' uses {what}, which unwinds past "
                        f"the statement it is written at; a procedure body is "
                        f"spliced into its call sites, which may sit in different "
                        f"enclosing constructs, so it may not contain non-local "
                        f"control flow",
                        nd.span,
                    )
                elif isinstance(nd, _OUTCOME_BINDING_STMTS):
                    bag.error(
                        f"procedure '{proc.name}' contains a `round`, which binds "
                        f"its own `outcome` for the statements after it; a "
                        f"procedure body may not yet hold one, because the body's "
                        f"`outcome` wall cannot distinguish a round-local binding "
                        f"from the caller's call-site pronoun (procedures.md)",
                        nd.span,
                    )
                elif isinstance(nd, n.Produces) and nd.define in outcome_phases:
                    bag.error(
                        f"procedure '{proc.name}' consumes the phase outcome of "
                        f"'{nd.define}'. A phase outcome's consumer must be an "
                        f"EARLIER-executed sibling of the producing phase, and there "
                        f"must be exactly ONE of them — both are facts about where "
                        f"the statement sits, and a procedure body is spliced into "
                        f"sites the checker cannot see when it checks the body. "
                        f"Running it before '{nd.define}', or running it twice, would "
                        f"pass here and then fail at play time. Consume the outcome "
                        f"at the site (a `produces:` over a `define` is fine in a "
                        f"body — a define has no ordering or uniqueness rule)",
                        nd.span,
                    )
                elif isinstance(nd, n.RunStmt):
                    bag.error(
                        f"procedure '{proc.name}' runs procedure '{nd.name}'; a "
                        f"procedure may not invoke another (v1 — expansion is a "
                        f"single splice, not a call graph)",
                        nd.span,
                    )
                elif isinstance(nd, n.NameRef):
                    if nd.ref_kind == "local" and nd.name not in allowed:
                        bag.error(
                            f"procedure '{proc.name}' references '{nd.name}', which "
                            f"is not one of its parameters or a binding in its body",
                            nd.span,
                        )
                    elif nd.ref_kind == "pronoun" and nd.name in _CALL_SITE_PRONOUNS:
                        bag.error(
                            f"procedure '{proc.name}' reads the call-site pronoun "
                            f"'{nd.name}'; a procedure body is spliced into call "
                            f"sites that need not share a call-site context — pass "
                            f"the value in as a parameter (`run {proc.name}"
                            f"({nd.name})`)",
                            nd.span,
                        )

    # Call sites: the procedure must exist, every declared procedure must be
    # invoked — an uninvoked body is spliced nowhere, so nothing downstream ever
    # sees it (the same reasoning `_instantiate_rules` gives an uninstantiated
    # rule template) — and no argument may be captured by a binder in the body.
    invoked: set[str] = set()
    for nd in _walk(game):
        if isinstance(nd, n.RunStmt):
            invoked.add(nd.name)
            if nd.name not in known:
                bag.error(f"run of unknown procedure '{nd.name}'", nd.span)
    for proc in game.procedures:
        if proc.name not in invoked:
            bag.error(
                f"procedure '{proc.name}' is never run — invoke it with `run "
                f"{proc.name}(…)`, or delete it (its body would otherwise be "
                f"spliced nowhere, and go entirely unchecked downstream)",
                proc.span,
            )


def _reaches(start: str, target: str, calls: dict[str, set[str]]) -> bool:
    """Whether `target` is reachable from `start` through the call graph."""
    seen: set[str] = set()
    stack = list(calls.get(start, ()))
    while stack:
        cur = stack.pop()
        if cur == target:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(calls.get(cur, ()))
    return False


# The closed set of statically enumerable move-parameter domains (decisions.md
# "Surface totality") is `cardlang.domains.PARAM_DOMAINS` — the union of the
# registry rows' `param_domains`, imported above as `_FIXED_DOMAINS`. It is
# matched by exact string, not by stripping a trailing `?`: only `Suit?` is
# listed by a row, so only it has a real nullable enumeration. `Rank?`/`Player?`
# parse (payload types are generically optional-able) but no row admits them, so
# they fall through to the "unsupported domain" branch below rather than being
# silently accepted and then ignored at runtime. `Card` is deliberately not a
# registry row at all (state-dependent — the live hand), so it is absent from
# this set and checked separately below.
#
# The one list of legal spellings the diagnostic names, derived from the same
# rows in enumeration order so a new domain row cannot leave the message stale.
_LEGAL_PARAM_DOMAINS = f"{', '.join(PARAM_DOMAIN_ORDER)}, or Card"


def _check_move_params(
    mt: n.MoveTypeDef, bag: DiagnosticBag, span: Span | None, has_ranking: bool
) -> None:
    """Totality gate for a parameterized move offered/enumerated in a decision
    (an `offer` statement or a `round offering` vocabulary). Fixed-from-type
    domains (`Suit`/`Suit?`/`Rank`/`Player`) and a single `Card` parameter are
    allowed; a `Card` parameter combined with any other parameter, a
    bounded-`Integer` parameter (deferred), two parameters sharing a name, and
    a `Rank` parameter in a game with no declared `ranking:` (`has_ranking`)
    are rejected with a message.

    `has_ranking` gates only `Rank`: `Player`'s domain is the seats, always
    non-empty for a real game, and `Suit`'s is `deck_suits`, always non-empty
    for a real deck — neither can be empty the way `game.ranking` (optional,
    `()` by default) can. Without this gate, a Rank-parameterized move in a
    no-`ranking:` game would pass resolve clean and only fail at runtime,
    mid-decision, once `param_domain` enumerates the empty `rank_index` and
    the move contributes zero candidates — a crash where a compile-time
    diagnostic belongs (CLAUDE.md "Surface totality")."""
    types = [p.type_name for p in mt.params]
    if "Card" in types and len(types) > 1:
        bag.error(
            f"move '{mt.name}' combines a Card parameter with another parameter; "
            f"Card's domain is the live hand and its actions are the card block, "
            f"so a Card parameter cannot be combined with another parameter "
            f"(fold into one parameter)",
            span,
        )
    names = [p.name for p in mt.params]
    dup_names = sorted({name for name in names if names.count(name) > 1})
    if dup_names:
        bag.error(
            f"move '{mt.name}' declares more than one parameter named "
            f"{', '.join(dup_names)}; `bind_params` binds parameters by name, "
            f"so a repeated name silently shadows the earlier parameter instead "
            f"of binding both (rename one)",
            span,
        )
    for t in types:
        if t.rstrip("?") == "Integer":
            bag.error(
                f"move '{mt.name}' has parameter domain '{t}'; bounded-Integer "
                f"parameter domains are deferred (see "
                f"open-questions/move-parameter-domains.md)",
                span,
            )
        elif t not in _FIXED_DOMAINS and t != "Card":
            bag.error(
                f"move '{mt.name}' has unsupported parameter domain '{t}' "
                f"(expected {_LEGAL_PARAM_DOMAINS})",
                span,
            )
        # Exact string, matching `_FIXED_DOMAINS`'s own convention (never by
        # stripping a trailing `?`): `Rank?` is not in `_FIXED_DOMAINS`, so it
        # is already rejected by the elif above and never reaches this branch
        # — only bare `Rank` needs the non-empty-`ranking:` gate.
        elif t == "Rank" and not has_ranking:
            bag.error(
                f"move '{mt.name}' has a Rank parameter, but the game declares "
                f"no ranking: — Rank enumerates the declared ranking, so it "
                f"needs a non-empty one",
                span,
            )


def _check_card_vocabulary(
    names: tuple[str, ...],
    move_type_defs: dict[str, n.MoveTypeDef],
    game: n.Game,
    bag: DiagnosticBag,
    span: Span | None,
) -> None:
    """The Card domain's constraints on a vocabulary of move types, wherever
    one is enumerated (a plain `offer` or the auction `round offering` — both
    fold a Card-parameterized move through the same `param_domain`/
    `card_to_action` machinery, decisions.md "Declared parameter
    domains"): at most one Card-parameterized move (its OpenSpiel action id
    is the card itself, so a second would be indistinguishable by id — both
    `offer` and `round offering` would otherwise collapse two card plays onto
    one action, cardlang/openspiel/encoding.py), and the actor's
    `hand[player]` zone must exist (`param_domain`'s Card branch enumerates
    it; without one the decision crashes mid-playout). Unknown move names are
    skipped — the caller's own loop already reports those."""
    card_param_moves = [
        name
        for name in names
        if name in move_type_defs
        and len(move_type_defs[name].params) == 1
        and move_type_defs[name].params[0].type_name == "Card"
    ]
    if len(card_param_moves) > 1:
        bag.error(
            f"vocabulary declares more than one Card-parameterized move "
            f"({', '.join(card_param_moves)}); a card play's action is the "
            f"card itself, so a second Card-parameterized move would be "
            f"indistinguishable — fold them into one move type",
            span,
        )
    if card_param_moves and not any(
        z.name == "hand" and z.index == "player" for z in game.zones
    ):
        bag.error(
            f"vocabulary move '{card_param_moves[0]}' takes a Card parameter, "
            f"which enumerates the actor's `hand[player]` zone — this game "
            f"declares none",
            span,
        )


def _check_vocabulary_moves(
    names: tuple[str, ...],
    move_type_defs: dict[str, n.MoveTypeDef],
    defined_move_types: set[str],
    bag: DiagnosticBag,
    span: Span | None,
    unknown_msg: str,
    has_ranking: bool,
) -> None:
    """The shared body of a vocabulary's per-name loop, wherever one is
    enumerated (a plain `offer` or the auction `round offering` —
    `_check_card_vocabulary`'s docstring has the same "wherever one is
    enumerated" rationale): every named move type must be defined, and a
    defined, parameterized one passes `_check_move_params`'s totality gate.
    `unknown_msg` is the caller-specific wording for an unknown name (the two
    call sites differ only in this message, "offer ..." vs "round vocabulary
    ..."). `has_ranking` (`bool(game.ranking)`) is threaded through to
    `_check_move_params`'s Rank-needs-a-declared-ranking gate."""
    for name in names:
        if name not in defined_move_types:
            bag.error(f"{unknown_msg} '{name}'", span)
            continue
        mt = move_type_defs[name]
        if mt.params:
            _check_move_params(mt, bag, span, has_ranking)


def _validate_refs(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> None:
    move_type_defs = {m.name: m for m in game.move_types}
    defined_move_types = set(move_type_defs)
    defined_types = {t.name for t in game.types}
    defined_defines = {d.name for d in game.defines}
    defined_functions = {f.name for f in game.functions}
    # A `produces:` consumer may also name an outcome-declaring phase (its outcome
    # is produced as the phase runs, then dispatched by a sibling consumer).
    outcome_phases = {
        nd.name for nd in _walk(game) if isinstance(nd, n.Phase) and nd.outcome_cases
    }
    for nd in _walk(game):
        match nd:
            case n.Call() if (
                nd.func not in STDLIB_CALL_FUNCS and nd.func not in defined_functions
            ):
                bag.error(f"call to unknown function '{nd.func}'", nd.span)
            case n.StructLit() if nd.type_name not in defined_types:
                bag.error(f"unknown type '{nd.type_name}'", nd.span)
            case n.NamedArg():
                # Accepted-but-crashing surface walled off (Surface totality):
                # the grammar admits `f(x = 1)`, but typecheck skips the value
                # expression and the runtime raises. Reject until a game needs
                # named arguments (recorded in roadmap.md).
                bag.error(
                    "named call arguments are not supported; pass arguments "
                    "positionally",
                    nd.span,
                )
            case n.StateDecl():
                # One arm, both checks: a match runs its first matching arm
                # only, so two guarded StateDecl arms would report at most one
                # of two independent errors on the same declaration.
                if (
                    nd.type_name not in KNOWN_TYPE_NAMES
                    and nd.type_name not in defined_types
                ):
                    bag.error(
                        f"unknown type '{nd.type_name}' in declaration of "
                        f"'{nd.name}'",
                        nd.span,
                    )
                if nd.index is not None and nd.index not in ZONE_INDEX_ROLES:
                    # Same wall as a zone's index role, same registry. Before
                    # it existed, `state { x[suit] : Integer = 0 }` checked
                    # clean and the runtime silently keyed it BY PLAYERS (the
                    # driver's key-set dispatch defaulted every non-team role
                    # to seats) — the declared index was accepted and ignored.
                    roles = ", ".join(sorted(ZONE_INDEX_ROLES))
                    bag.error(
                        f"state variable '{nd.name}' is indexed by "
                        f"'{nd.index}', which is not an indexable role "
                        f"({roles}) — a value domain has no per-member store "
                        f"(roadmap.md records the extension)",
                        nd.span,
                    )
            case n.StructField() if (
                nd.type_name not in KNOWN_TYPE_NAMES
                and nd.type_name not in defined_types
            ):
                bag.error(
                    f"unknown type '{nd.type_name}' in struct field '{nd.name}'",
                    nd.span,
                )
            case n.Produces() if (
                nd.define not in defined_defines and nd.define not in outcome_phases
            ):
                bag.error(
                    f"produces names unknown define or outcome phase '{nd.define}'",
                    nd.span,
                )
            case n.ForEach() if nd.role not in _ITERATION_ROLES:
                bag.error(
                    f"unknown `for each` role '{nd.role}' (expected one of "
                    f"{', '.join(sorted(_ITERATION_ROLES))})",
                    nd.span,
                )
            case n.EachSimultaneous() if nd.role not in SIMULTANEOUS_ROLES:
                # The registry's `simultaneous` column, not a bare `!= "player"`:
                # the roles that admit a simultaneous block are exactly the seat
                # domains (a value domain has no actor to move simultaneously),
                # and both the gate and the message it prints come from the rows.
                bag.error(
                    f"`each {nd.role} simultaneously` is not runnable — "
                    f"simultaneous moves are per "
                    f"{' or '.join(sorted(SIMULTANEOUS_ROLES))}",
                    nd.span,
                )
            case n.EachSimultaneous() if n.simultaneous_body_error(nd.body) is not None:
                # The form gated its DOMAIN (above) and not its BODY. The executor
                # implements exactly one body shape, so everything else compiled and
                # then died on a bare assert — a runtime crash for a statically
                # checkable error, in the wrong currency. `run` made it reachable
                # from an entirely natural-looking program (`each player
                # simultaneously: run pass_card(player)`), since an expansion is a
                # block and never a bare movement.
                #
                # The reason comes FROM the executor's own requirement
                # (`n.simultaneous_body_error`), not from a hand-written copy of it:
                # the first version of this wall mirrored only the first of five
                # requirements, so `move chosen one card …` still reached the assert.
                bag.error(
                    f"`each {nd.role} simultaneously` runs one chosen movement per "
                    f"{nd.role} and nothing else — "
                    f"{n.simultaneous_body_error(nd.body)}. The form snapshots every "
                    f"{nd.role}'s selection against the state BEFORE the block and "
                    f"applies them together (that is what makes the pass atomic — "
                    f"nobody sees a passed card before choosing their own), and a "
                    f"snapshot is only defined for that one shape",
                    nd.span,
                )
            case n.CardLiteral():
                if nd.rank not in cats.ranks:
                    bag.error(f"unknown rank '{nd.rank}' in card literal", nd.span)
                if nd.suit not in cats.suits:
                    bag.error(f"unknown suit '{nd.suit}' in card literal", nd.span)
            case n.RotateStmt():
                # Both checks in ONE arm: a bare `case n.RotateStmt():` above a guarded
                # one consumes the node, so the guarded arm never runs. (It did exactly
                # that, and `tests/test_binder_scoping.py` caught it.)
                bad = _bad_write_target(nd)
                if bad is not None:
                    bag.error(bad, nd.span)
                for value in nd.values:
                    if value not in cats.enums:
                        bag.error(f"rotate through unknown value '{value}'", nd.span)
            case n.AssignStmt():
                bad = _bad_write_target(nd)
                if bad is not None:
                    bag.error(bad, nd.span)
            case n.Movement():
                for endpoint, direction in ((nd.source, "from"), (nd.dest, "to")):
                    bad = _bad_zone_endpoint(endpoint, direction)
                    if bad is not None:
                        bag.error(bad, nd.span)
            case n.Winner() if nd.target not in cats.state_vars:
                bag.error(f"winner references unknown variable '{nd.target}'", nd.span)
            case n.Offer():
                _check_vocabulary_moves(
                    nd.move_types,
                    move_type_defs,
                    defined_move_types,
                    bag,
                    nd.span,
                    "offer names unknown move type",
                    bool(game.ranking),
                )
                _check_card_vocabulary(nd.move_types, move_type_defs, game, bag, nd.span)
            case n.Round() if nd.move_types is not None:
                # Auction form: a vocabulary of game-defined move types, no card
                # zones. The termination predicate's names are checked by the
                # generic NameRef pass.
                #
                # Parameter domains are a closed set (decisions.md "Surface
                # totality"): the runtime enumerates `Suit`/`Suit?`/`Rank`/
                # `Player` statically and `Card` over the actor's live hand —
                # any other type, or a domain combination `_check_move_params`
                # rejects, would crash `enumerate_domain`/produce an
                # indistinguishable action id mid-playout, so reject it here.
                _check_vocabulary_moves(
                    nd.move_types,
                    move_type_defs,
                    defined_move_types,
                    bag,
                    nd.span,
                    "round vocabulary names unknown move type",
                    bool(game.ranking),
                )
                _check_card_vocabulary(nd.move_types, move_type_defs, game, bag, nd.span)
                # The betting form omits `outcome` (it mutates state directly and
                # produces no variant); only an auction's outcome fn is validated.
                if nd.outcome_fn is not None and nd.outcome_fn not in STDLIB_AUCTION_OUTCOMES:
                    bag.error(
                        f"auction round outcome '{nd.outcome_fn}' is not an auction "
                        f"outcome function",
                        nd.span,
                    )
                if nd.order_mode is not None and nd.order_mode not in n.ROUND_ORDER_MODES:
                    bag.error(
                        f"round order '{nd.order_mode}' is unknown (expected one of "
                        f"{sorted(n.ROUND_ORDER_MODES)})",
                        nd.span,
                    )
            case n.Round() if nd.combos_fn is not None:
                # Climbing form: trick zones plus the two combination-engine queries
                # (`combinations` lead, `follows` legal-follows). The termination
                # predicate's names are checked by the generic NameRef pass; its
                # Boolean type by the type checker.
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.error(f"climb round source zone '{nd.source_zone}' is unknown", nd.span)
                if nd.play_zone not in zone_names:
                    bag.error(f"climb round play zone '{nd.play_zone}' is unknown", nd.span)
                if nd.move_type not in LIBRARY_MOVE_TYPES:
                    bag.error(f"climb round move type '{nd.move_type}' is unknown", nd.span)
                if nd.combos_fn not in STDLIB_CLIMB_LEADS:
                    bag.error(
                        f"climb round `combinations` query '{nd.combos_fn}' is not a "
                        f"combination lead query",
                        nd.span,
                    )
                if nd.follows_fn not in STDLIB_CLIMB_FOLLOWS:
                    bag.error(
                        f"climb round `follows` query '{nd.follows_fn}' is not a "
                        f"combination follows query",
                        nd.span,
                    )
            case n.Round():
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.error(f"round source zone '{nd.source_zone}' is unknown", nd.span)
                if nd.play_zone not in zone_names:
                    bag.error(f"round play zone '{nd.play_zone}' is unknown", nd.span)
                if nd.outcome_fn not in STDLIB_TRICK_OUTCOMES:
                    bag.error(
                        f"trick round outcome '{nd.outcome_fn}' is not a trick "
                        f"outcome function",
                        nd.span,
                    )
                if nd.move_type not in LIBRARY_MOVE_TYPES:
                    bag.error(f"round move type '{nd.move_type}' is unknown", nd.span)
                elif nd.move_type != "play_to_trick":
                    # The trick form's decision site is hardwired to
                    # `play_to_trick`; any other name would silently run as a
                    # trick anyway (decisions.md "Surface totality").
                    bag.error(
                        f"the trick round form runs `play_to_trick`; "
                        f"'{nd.move_type}' is not runnable on it (roadmap.md)",
                        nd.span,
                    )
                if (
                    nd.early_termination is not None
                    and nd.early_termination not in STDLIB_EARLY_PREDICATES
                ):
                    bag.error(
                        f"round early-termination predicate "
                        f"'{nd.early_termination}' is unknown",
                        nd.span,
                    )


def _raise_if_errors(bag: DiagnosticBag) -> None:
    if not bag.has_errors:
        return
    error = DiagnosticError(bag.items[0])
    if len(bag.items) > 1:
        error.add_note(bag.format())
    raise error
