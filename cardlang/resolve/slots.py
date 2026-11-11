"""The reference slots: which AST field names which namespace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from cardlang.ast import nodes as n
from cardlang.board_domains import LINE_NOUN
from cardlang.builtins.functions import (
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    PRIMITIVE_EARLY_PREDICATES,
    TRICK_WINNER_NAMES,
)


# ---------------------------------------------------------------------------
# The reference-slot registry
# ---------------------------------------------------------------------------
#
# Every `str`-typed field of every `n.Node`, classified by what the string IS.
# Most name-carrying slots hold a `NameRef`, which `_rewrite` classifies and
# every consumer then reads off `ref_kind`; the slots below hold their name as a
# plain string instead, so a pass built on `NameRef` is structurally blind to
# them. That blindness is not a property of the design — it is a property of
# whichever consumer forgot the slot exists, which is exactly the by-luck hand
# list this table replaces (issue #138).
#
# The table is AUTHORED; only its key set is derived. What a slot MEANS cannot
# be read off an annotation — `str` is `str` — so the semantic column is written
# here and the KEY set is pinned against the module's actual fields by
# `tests/test_reference_slots.py`, which fails when a `str` field is added,
# renamed, or removed. That split is the whole completeness argument: no slot can
# exist unclassified, and no classification can name a slot that does not.
#
# The seven kinds are exhaustive over the key set, and pairwise disjoint:
#
#   declaration — the field IS the binding site of a name in some namespace.
#   binder      — introduces a lexical binder (`_introduced_binders` owns which
#                 names are in scope where; this only records that the slot is
#                 one).
#   reference   — names something declared elsewhere, as a bare string.
#   keyword     — a word from a closed grammar set, not a name: no namespace can
#                 supply it and nothing can shadow it.
#   opaque      — arbitrary author text (a string literal, an echoed spelling).
#   classified  — a `NameRef`'s own name, owned by `_rewrite`. Distinct from
#                 `reference`, not a duplicate of it: these are the slots that
#                 ARE classified, and the reason the rest read as an omission.
#   metadata    — stamped by a pass; holds no name at all.

# declaration slot -> the namespace the name is declared into.
_DECLARATION_SLOTS: dict[tuple[type, str], str] = {
    (n.Game, "name"): "game",
    (n.Library, "name"): "library",
    (n.Phase, "name"): "phase",
    (n.Mode, "name"): "mode",
    (n.ZoneDecl, "name"): "zone",
    (n.PositionDecl, "name"): "position",
    (n.PositionDecl, "members_named"): "position_member",
    (n.StateDecl, "name"): "state",
    (n.RequireDecl, "name"): "state",
    # A Definition Contract row declares the name the game's definition must
    # take, in that definition's own namespace.
    (n.MoveContract, "name"): "move_type",
    (n.FunctionContract, "name"): "function",
    (n.ProcedureContract, "name"): "procedure",
    (n.RuleDef, "name"): "rule",
    (n.MoveTypeDef, "name"): "move_type",
    (n.FunctionDef, "name"): "function",
    (n.ProcedureDef, "name"): "procedure",
    (n.Parameter, "name"): "param",
    (n.PrimitiveDecl, "name"): "primitive",
    (n.CombinationCatalogue, "name"): "catalogue",
    (n.ShapeRow, "label"): "shape_label",
    (n.OutcomeCase, "tag"): "outcome_tag",
    # `let` declares a name and scopes it to the statements after it, so it is
    # both — filed as the declaration, since that is the half a name registry
    # asks about. Its INDEX is the binder (`let x[i] = …` binds `i` per player).
    (n.LetStmt, "name"): "local",
}

# Slots that introduce a lexical binder. `_introduced_binders` remains the
# authority on which names a node brings into scope and over which fields; this
# records only that the slot's string is a binder rather than a reference, which
# is what a name sweep needs to know to leave it alone.
_BINDER_SLOTS: frozenset[tuple[type, str]] = frozenset(
    {
        (n.Comprehension, "binder"),
        (n.Quantifier, "binder"),
        (n.DomainQuery, "binder"),
        (n.SubsetQuery, "binder"),
        (n.ForEach, "binder"),
        (n.Turns, "binder"),
        (n.HostedPoll, "binder"),
        (n.ProduceArm, "binders"),
        (n.LetStmt, "index"),
    }
)

# reference slot -> the namespace the name is drawn from. THIS is the table the
# residual in issue #138 is about: every one of these is a name held as a plain
# string, invisible to any pass built on `NameRef`.
_REFERENCE_SLOTS: dict[tuple[type, str], str] = {
    # State, reached without a `NameRef` in sight. `Turns.again` is the reachable
    # one — a library body may write it — and `Winner.target` is the game-level
    # twin `resolve`'s own comment has documented since before this table.
    (n.Turns, "again"): "state",
    (n.Winner, "state_var"): "state",
    (n.StopResult, "state_var"): "state",
    # Zones. Both round forms name their two zones as bare strings.
    (n.TrickRound, "source_zone"): "zone",
    (n.TrickRound, "play_zone"): "zone",
    (n.ClimbRound, "source_zone"): "zone",
    (n.ClimbRound, "play_zone"): "zone",
    # Phases.
    (n.ContinueTo, "phase"): "phase",
    (n.TransitionTo, "mode"): "mode",
    # Types, in every position a type name can be written.
    (n.StateDecl, "type_name"): "type",
    (n.RequireDecl, "type_name"): "type",
    (n.FunctionContract, "result_type"): "type",
    (n.Parameter, "type_name"): "type",
    (n.PrimitiveDecl, "return_type"): "type",
    # A `reads` name is one of the game's own KEYED declarations — a state
    # variable or a zone — and which it is decides how the binder materializes
    # it, so the slot's namespace is their union and
    # `_classify_primitive_read` is the one site that picks (the
    # `RequireDecl.type_name` shape: one slot, two registries, classified at
    # resolve rather than by the grammar). Its BINDER names a parameter of the
    # entry it sits in, which is why that slot is `param` and not a binder
    # slot: `Parameter` introduces the name and this refers to it.
    (n.PrimitiveRead, "name"): "primitive_read",
    (n.PrimitiveRead, "binder"): "param",
    # The [[phase-scoped-read]]'s tail, beside `ContinueTo.phase`: the phase
    # whose own `state { }` declares the read. A reference like any other, and
    # registered here so a future phase-renaming transform learns of it from
    # the registry rather than from an author remembering.
    (n.PrimitiveRead, "phase"): "phase",
    (n.OutcomeCase, "payload_types"): "type",
    # Definitions, by kind. The move-type slots split across two namespaces and
    # the split is load-bearing, not a nicety: an OFFERING names move types the
    # game defines (`_check_offering_moves` against `defined_move_types`),
    # while `constrains:`, `legal_moves:`, a transition event and a trick/climb
    # round's move type name the kernel registry (`LIBRARY_MOVE_TYPES`). Only
    # the first row is a channel an importing game can feed.
    (n.Offer, "offering"): "move_type",
    (n.TrickRound, "move_type"): "kernel_move_type",
    (n.ClimbRound, "move_type"): "kernel_move_type",
    (n.LegalMoves, "move_types"): "kernel_move_type",
    (n.MoveEvent, "move_type"): "kernel_move_type",
    (n.RuleDef, "constrains"): "kernel_move_type",
    (n.RuleRef, "name"): "rule",
    (n.Produces, "phase"): "phase",
    (n.RunStmt, "name"): "procedure",
    (n.Call, "func"): "function",
    # The query registries a `round` selects from (`_ROUND_QUERY_REGISTRIES`):
    # the same names for a library as for a game, and Primitives among them, so
    # a library naming one is refused at `_check_library_encapsulation`.
    (n.TrickRound, "winner_fn"): "primitive_query",
    (n.TrickRound, "early_termination"): "primitive_query",
    # A climbing round's two slots name its engine: a Combination Catalogue
    # and a function of the game, or a registered engine's two queries
    # (`_resolve_climb_engines` classifies the pair).
    (n.ClimbRound, "combos_fn"): "climb_lead",
    (n.ClimbRound, "follows_fn"): "climb_follows",
    # Deck-derived values, held as strings rather than classified names.
    (n.CardLiteral, "rank"): "deck_rank",
    (n.CardLiteral, "suit"): "deck_suit",
    (n.Game, "ranking"): "deck_rank",
    (n.CardPointsEntry, "rank"): "deck_rank",
    (n.SuitRanking, "suits"): "deck_suit",
    (n.RankSequence, "ranks"): "deck_rank",
    (n.Game, "direction"): "enum_value",
    (n.RotateStmt, "values"): "enum_value",
    (n.Game, "deck"): "component_set",
    (n.BoardDecl, "family"): "board_family",
    (n.UsesDecl, "name"): "library",
    # Roles and the index domains, drawn from the domain registry
    # (`cardlang.domains`) plus a game's declared `positions { }`.
    (n.ForEach, "role"): "role",
    (n.Quantifier, "role"): "role",
    (n.EachSimultaneous, "role"): "role",
    (n.ZoneDecl, "index"): "index_domain",
    (n.StateDecl, "index"): "index_domain",
    (n.RequireDecl, "index"): "index_domain",
    # Zone types and their arguments (`Hand<player>`): the kernel zone-type
    # registry, and a role or type name in parameter position.
    (n.TypeRef, "name"): "zone_type",
    (n.TypeArg, "name"): "zone_type_arg",
    # Names owned by a declaration reached elsewhere: a member's field belongs
    # to the fixed field table of its receiver's type, a produced tag to the
    # outcome phase's cases. Each is a reference, and none is an independent
    # channel — the owning name is a slot above or a closed table.
    (n.Member, "field"): "field",
    (n.Produce, "tag"): "outcome_tag",
    (n.ProduceArm, "tag"): "outcome_tag",
    # The item noun a movement moves (`cards`, `coins`): drawn from the game's
    # CONTENT FLAVOR, which is the component set's, so it is a game-fed slot the
    # way a suit is. Not swept for a library — see `_LIBRARY_UNSWEPT`.
    (n.Transfer, "item"): "content_kind",
}

# Each `primitive_query` slot -> the names a round may write there. The one
# statement of a slot's registry: `_validate_refs` refuses a name outside it,
# and `_round_slot_primitives` refuses a library the Primitives inside it.
_ROUND_QUERY_REGISTRIES: dict[tuple[type, str], frozenset[str]] = {
    (n.TrickRound, "winner_fn"): TRICK_WINNER_NAMES,
    (n.TrickRound, "early_termination"): PRIMITIVE_EARLY_PREDICATES,
    (n.ClimbRound, "combos_fn"): PRIMITIVE_CLIMB_LEADS,
    (n.ClimbRound, "follows_fn"): PRIMITIVE_CLIMB_FOLLOWS,
}

# Each `primitive_query` slot as a designer writes it, with `{name}` the
# callback, for a refusal that names the slot a name belongs to.
_ROUND_QUERY_SLOT_SPELLINGS: dict[tuple[type, str], str] = {
    (n.TrickRound, "winner_fn"): "a trick round's `winner` slot (`... winner {name}`)",
    (n.TrickRound, "early_termination"): "a trick round's `early` slot (`... early {name}`)",
    (n.ClimbRound, "combos_fn"): (
        "a climb round's `combinations` slot (`... combinations {name}`)"
    ),
    (n.ClimbRound, "follows_fn"): "a climb round's `follows` slot (`... follows {name}`)",
}

# Every name a round slot reads. A definition taking one is refused wherever a
# designer introduces it: the slot always runs the native, never the definition.
_ROUND_QUERY_NAMES: frozenset[str] = frozenset().union(*_ROUND_QUERY_REGISTRIES.values())


def _round_query_slot(name: str) -> str | None:
    """The slot that reads `name`, as a designer writes it, or None."""
    for key, names in _ROUND_QUERY_REGISTRIES.items():
        if name in names:
            return _ROUND_QUERY_SLOT_SPELLINGS[key].format(name=name)
    return None

# Closed grammar keyword: a word the parser puts there from a fixed set of
# productions. Not a name, so no namespace supplies it and nothing shadows it.
_KEYWORD_SLOTS: frozenset[tuple[type, str]] = frozenset(
    {
        (n.AssignStmt, "op"),
        (n.BinOp, "op"),
        (n.RuleRef, "delta"),
        (n.EpistemicOp, "op"),
        (n.IsCheck, "kind"),
        (n.CardQuery, "kind"),
        (n.PlayerQuery, "kind"),
        (n.DomainQuery, "kind"),
        (n.SubsetQuery, "kind"),
        (n.SubsetQuery, "agg"),
        (n.SubsetQuery, "size_mode"),
        (n.Quantifier, "kind"),
        (n.PhaseQualifier, "kind"),
        (n.Comprehension, "agg"),
        (n.Choose, "domain"),
        (n.Transfer, "verb"),
        (n.Transfer, "selection_mode"),
        (n.Transfer, "amount"),
        (n.Transfer, "distribution"),
        (n.Winner, "rank_dir"),
        # The Stop Result's member and its ranking's direction: grammar
        # words the builder put there, never names.
        (n.StopResult, "kind"),
        (n.StopResult, "rank_dir"),
        (n.Game, "ranking_convention"),
        # The lowering stamp's two words: `form` is a `Literal`, and `key`
        # names the contract the table answers, never a designer-authored
        # name in any namespace.
        (n.LoweredSpelling, "form"),
        (n.LoweredSpelling, "key"),
        # Annotated `Flavor` (a `Literal`), not `str` — which is exactly why it
        # was the one field the registry's first domain predicate missed. It
        # holds a string like any other keyword slot: the clause that selected
        # the component set, stamped at parse.
        (n.Game, "content_flavor"),
        # Annotated `Stake` (a `Literal`): the row word the `move_stake`
        # production put there, never a name.
        (n.MoveTypeDef, "stake"),
        # A Combination Shape's part kind and qualifiers: `Literal`s keyed by
        # the grammar alias that put them there (`catalogue.SHAPE_PARTS`,
        # `SHAPE_QUALIFIERS`), never names.
        (n.ShapePart, "kind"),
        (n.ShapeRow, "qualifiers"),
    }
)

# Author text that is not a name in any namespace.
_OPAQUE_SLOTS: frozenset[tuple[type, str]] = frozenset(
    {
        (n.StrLit, "value"),
        # The domain noun exactly as written, kept only so the plural-mismatch
        # diagnostic can quote it; `binder` is the derived singular that means
        # something.
        (n.DomainQuery, "spelled"),
    }
)

# The slots this pass owns itself: a name it classifies, and the facts it
# stamps -- a reference's kind, a `winner:` clause's index role.
_CLASSIFIED_SLOTS: frozenset[tuple[type, str]] = frozenset({(n.NameRef, "name")})
_METADATA_SLOTS: frozenset[tuple[type, str]] = frozenset(
    {
        (n.NameRef, "ref_kind"),
        (n.Winner, "keyed_by"),
        (n.StopResult, "keyed_by"),
        # The Definition Contract a `uses` splice records: spellings copied off
        # a row as facts, never names a sweep resolves.
        (n.ContractStamp, "library"),
        (n.ContractStamp, "row"),
        (n.ContractStamp, "param_types"),
        (n.ContractStamp, "result_type"),
        # Where a `uses` splice found the text: facts the splice stamps.
        (n.LibraryOrigin, "library"),
        (n.LibraryOrigin, "where"),
        (n.LibraryOrigin, "provided"),
        (n.LibraryOrigin, "contracted_zones"),
        # A climbing round's engine: its two slot names, copied off the round
        # by `_resolve_climb_engines` as the classified pair, never a second
        # channel a sweep resolves.
        (n.RegisteredEngine, "lead"),
        (n.RegisteredEngine, "follows"),
        (n.DeclaredEngine, "catalogue"),
        (n.DeclaredEngine, "follows"),
        # The follows function's reads, stamped from its classified names by
        # `_stamp_follows_reads`.
        (n.DeclaredEngine, "state_reads"),
        (n.DeclaredEngine, "zone_reads"),
    }
)


# The registry as one view: slot -> kind. Derived from the seven tables above so
# a slot can carry exactly one kind, and the pin can ask a single question.
STRING_SLOT_KINDS: dict[tuple[type, str], str] = {
    **{slot: "declaration" for slot in _DECLARATION_SLOTS},
    **{slot: "binder" for slot in _BINDER_SLOTS},
    **{slot: "reference" for slot in _REFERENCE_SLOTS},
    **{slot: "keyword" for slot in _KEYWORD_SLOTS},
    **{slot: "opaque" for slot in _OPAQUE_SLOTS},
    **{slot: "classified" for slot in _CLASSIFIED_SLOTS},
    **{slot: "metadata" for slot in _METADATA_SLOTS},
}


def _member_namespace(node: object) -> str | None:
    """`x.field` reads a field of whatever `x` is, so the namespace depends on
    the object: `state.foo` names a field a round PUBLISHES
    (`ROUND_STATE_FIELDS`, typecheck's Owner Guard), while every other object's
    fields belong to the type that object has — a namespace reached through the
    declaration that named the type, not through this slot."""
    obj = cast(n.Member, node).obj
    if isinstance(obj, n.NameRef) and obj.name == "state":
        return "round_state"
    return "field"


def _domain_query_namespace(node: object) -> str | None:
    """A position query's noun names a declared position domain and binds a
    member of it, in the bare form and the collection form alike (`any cell
    where …`, `cells in home(p) where …`). The collection form's one fixed
    noun, the board's `line`, names nothing."""
    nd = cast(n.DomainQuery, node)
    return None if nd.source is not None and nd.binder == LINE_NOUN else "position"


@dataclass(frozen=True)
class _ContextualSlot:
    """A slot whose namespace depends on the NODE rather than on the field
    alone. `namespaces` declares every namespace `read` can return, so a
    consumer sweeping "the slots that can reach X" derives the answer from the
    table instead of naming these two by hand — the hand-list, one level up."""

    namespaces: frozenset[str]
    read: Callable[[object], str | None]


# One table, because "it depends" is exactly the shape that otherwise becomes a
# special case inside each consumer — and the second consumer's copy is where
# the two readings drift. A BINDER slot may appear here: `DomainQuery.binder`
# always binds, and additionally names a domain in the bare form.
#
# A row here SUPERSEDES the slot's static row: `slot_namespace` asks this table
# first and returns whatever it says. `Member.field` therefore has both, and
# they agree by construction — the static row records `field`, which is exactly
# what the contextual read falls through to for every object but the `state`
# pronoun.
_CONTEXTUAL_SLOTS: dict[tuple[type, str], _ContextualSlot] = {
    (n.Member, "field"): _ContextualSlot(
        frozenset({"round_state", "field"}), _member_namespace
    ),
    (n.DomainQuery, "binder"): _ContextualSlot(
        frozenset({"position"}), _domain_query_namespace
    ),
}


def _naming_slots_by_type() -> dict[type, tuple[str, ...]]:
    """The registry inverted: node type -> the fields on it that may name
    something. Derived from BOTH naming tables, so a row added to either reaches
    every sweep — which is the point of there being a registry rather than a
    match statement per consumer."""
    by_type: dict[type, list[str]] = {}
    for cls, field_name in (*_REFERENCE_SLOTS, *_CONTEXTUAL_SLOTS):
        by_type.setdefault(cls, []).append(field_name)
    return {cls: tuple(dict.fromkeys(names)) for cls, names in by_type.items()}


_NAMING_SLOTS_BY_TYPE: dict[type, tuple[str, ...]] = _naming_slots_by_type()


def slot_namespace(node: object, field_name: str) -> str | None:
    """The namespace a slot draws its name from, or None if the slot names
    nothing (a keyword, a binder, a declaration, opaque text). THE reader of the
    reference registry — consumers ask this rather than matching node kinds, so
    a slot added to the registry reaches every sweep at once."""
    contextual = _CONTEXTUAL_SLOTS.get((type(node), field_name))
    if contextual is not None:
        return contextual.read(node)
    return _REFERENCE_SLOTS.get((type(node), field_name))


def slot_strings(node: object, field_name: str) -> tuple[str, ...]:
    """The strings a slot holds — one for a `str` field, zero for an unset
    optional, and the whole tuple for a `tuple[str, ...]` field.

    Uniform over the three shapes the annotations take, so a consumer never has
    to know which shape a slot is. `Transfer.amount` is the one slot whose
    string is optional in a different way (it is `str | Expr`), and it is a
    keyword, so no reference consumer reaches it."""
    value = getattr(node, field_name)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        return tuple(v for v in value if isinstance(v, str))
    return ()

# Which move-type-naming reference slots OFFER a move type — put it in play at
# the position they sit at — and which merely mention one. DERIVED candidates,
# authored classification: the table is pinned equal to the `move_type` /
# `kernel_move_type` slots of `_REFERENCE_SLOTS`, so a move-type-naming slot
# added there arrives unclassified and reddens rather than silently widening or
# narrowing the containment relation.
_MOVE_TYPE_SLOT_OFFERS: dict[tuple[type, str], bool] = {
    (n.Offer, "offering"): True,
    (n.TrickRound, "move_type"): True,
    (n.ClimbRound, "move_type"): True,
    (n.LegalMoves, "move_types"): True,
    # A transition event names the move type whose play FIRES it, and a rule
    # names the move type it constrains. Neither puts a move type in play.
    (n.MoveEvent, "move_type"): False,
    (n.RuleDef, "constrains"): False,
}

_UNCLASSIFIED_MOVE_TYPE_SLOTS = {
    slot
    for slot, ns in _REFERENCE_SLOTS.items()
    if ns in ("move_type", "kernel_move_type")
} ^ set(_MOVE_TYPE_SLOT_OFFERS)
if _UNCLASSIFIED_MOVE_TYPE_SLOTS:
    raise AssertionError(
        f"_MOVE_TYPE_SLOT_OFFERS and the move-type reference slots disagree: "
        f"{sorted(f'{c.__name__}.{f}' for c, f in _UNCLASSIFIED_MOVE_TYPE_SLOTS)}"
    )


#: The name slots whose root name must be of a kind the slot takes, by node
#: kind and field: a movement's endpoints and a shuffle or reveal target take
#: a zone (or a binder holding one, whose type typecheck judges), a write
#: target a state variable. `_bad_zone_endpoint` and `_bad_write_target` refuse
#: by it, and `_name_positions` records it.
_ZONE_SLOT_KINDS: frozenset[n.RefKind] = frozenset({"zone", "local"})
_NAME_SLOTS: dict[tuple[type, str], frozenset[n.RefKind]] = {
    (n.Transfer, "source"): _ZONE_SLOT_KINDS,
    (n.Transfer, "dest"): _ZONE_SLOT_KINDS,
    (n.EpistemicOp, "zone"): _ZONE_SLOT_KINDS,
    (n.AssignStmt, "target"): frozenset({"state_var"}),
    (n.RotateStmt, "target"): frozenset({"state_var"}),
}


def _slot_root(expr: object) -> n.NameRef | None:
    """The name a slot's expression is rooted at, through its subscripts and
    fields, or None for an expression no name roots."""
    root = expr
    while isinstance(root, (n.Subscript, n.Member)):
        root = root.obj
    return root if isinstance(root, n.NameRef) else None
