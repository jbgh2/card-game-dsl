"""Resolve stage: name resolution.

This pass checks that the structural references in a game hang together —
the class of error a type checker catches before anything runs:

- every zone's type names a known library zone type (and is parameterized
  correctly);
- every `active_rules:` entry names a rule defined in the game;
- every [[move-type]] referenced by `constrains:`, `legal_moves:`, or a
  transition event is a known library move type;
- every `transition_to:` target is a sibling phase.

Deep expression name resolution (state variables, suits, the `action` fields,
native functions) needs the typed object model and lands with the type
checker; this pass is the structural net.

On success an immutably rewritten :class:`Game` flows on (rule templates
instantiated, every name classified). On any error it raises with every
diagnostic collected, not just the first.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a parsed AST (spans present, ``NameRef.ref_kind`` still
              ``None``).
Establishes:  every ``NameRef`` carries its ``ref_kind`` classification;
              rule templates are instantiated into concrete rules; every
              structural reference names a real declaration. This is the
              ONLY pass that classifies names — downstream dispatches on
              ``ref_kind``, never re-derives it. ``game.ranking`` is the
              operative strength order: a ``ranking:`` convention keyword
              is expanded against the deck here (``_expand_ranking``), so
              no later pass may branch on ``ranking_convention`` for
              semantics — it survives only as the source-form record
              ``ir.emit`` prints.
Now illegal:  an unresolved name (``ref_kind is None``) or a dangling
              zone/rule/move-type/phase reference reaching a later pass;
              the runtime hard-fails on an unclassified name
              (``runtime/evaluate.py``, ``_name``) as its Shadow Guard. Also
              a ``state { }`` default that cannot be evaluated where it
              is written — one reading state not yet declared, calling a
              function, or containing a ``choose``
              (``_check_state_default_scope``). ``runtime/driver``'s
              ``_declare_state`` may therefore assume every default
              evaluates against the frames standing at that moment. And an
              equality comparison whose two operands are names that
              provably denote the same acting player — the binder of a
              construct that rebinds ``acting_as`` against the ``actor``
              pronoun, or against a ``let`` transitively bound to either
              (``_check_actor_alias_comparisons``, decisions.md "Naming
              the acting player twice"). This is a scope fact, not a type
              fact — both operands are ``Player`` — so it is settled here
              rather than in the type layer. And a named trump nobody
              reads: a game-level ``trump:`` that is not a suit of the deck
              or that no trick round inherits, and a round ``trump`` clause
              on a winner whose body reads no trump
              (``_resolve_trump``, the winner-slot arm of
              ``_validate_refs``; the partition is
              ``TRUMP_READING_WINNERS``). The round clause's TYPE (``Suit?``)
              is typecheck's (``_check_round_trump``); its presence against
              its winner is settled here, with the winner namespace. And a
              ``winner:`` target that is not a per-member score — unindexed,
              optional, or declared outside ``Integer``/``Boolean``
              (``_check_winner_target``, decisions.md "Game result:
              `winner:` and `loser:`"); ``runtime/driver`` may therefore
              assume the target reads as a map from member to score, and
              hard-fails on one this pass did not admit as its Shadow Guard.
              And a ``teams:`` list that does not PARTITION the seats
              (``_check_teams``); every consumer building ``{p: ti for ti,
              members in enumerate(game.teams) for p in members}`` — the
              driver, the returns path, and the readiness proofs — may
              therefore read it as one.
              And a call, in a game that writes no ``primitives { }`` block,
              to a Primitive that has no legacy dispatch arm
              (``DECLARED_ONLY_CALL_FUNCS``, the declared-only arm of
              ``_validate_refs``): the name is in the legacy namespace, so
              the unknown-name arm cannot speak for it, and a declaration is
              its only route to Python. ``runtime/primitives.py``'s
              ``call`` fallthrough is the Shadow Guard behind this.
Verified by:  the per-guard diagnostic tests; the runtime Shadow Guard above.
              For the declare-time rule, the grid in
              ``tests/test_state_default_scope.py`` — which PLAYS every
              accepted cell rather than only resolving it, since
              "accepted" was exactly the assertion that hid the defect
              the grid was written for.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import assert_never, cast, get_args

from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN, DIRECTION_DOMAIN, directions_of
from cardlang.builtins.functions import (
    ARRIVAL_RECORD_CALLS,
    BOARD_ONLY_CALL_FUNCS,
    CALL_FUNCS,
    DECK_ONLY_CALL_FUNCS,
    DECLARED_ONLY_CALL_FUNCS,
    BUILTIN_CALL_FUNCS,
    PRIMITIVE_AUCTION_OUTCOMES,
    PRIMITIVE_CALL_FUNCS,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    PRIMITIVE_EARLY_PREDICATES,
    TRICK_ORDER_EARLY_PREDICATES,
    TRICK_ORDER_EXCLUDED_FUNCS,
    TRICK_ORDER_EXCLUDED_WINNERS,
    TRICK_ORDER_GATED_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
    TRICK_ORDER_READERS,
    TRICK_ORDER_ROW_CALLS,
    TRICK_ORDER_ROWS,
    TRICK_WINNER_NAMES,
    TRUMP_READING_WINNERS,
    VALUE_NAMES,
)
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.primitives_block import (
    BINDABLE_READ_KINDS,
    PRIMITIVE_IMPLEMENTATIONS,
    InvocationContract,
    Regime,
    call_namespace,
    classify_read,
    declared_names,
    ambiguous_read_names,
    phase_local_state_names,
    shadowed_state_names,
    declarable_type_names,
    engine_fact_names,
    regime,
    undeclarable_contract,
    unimplemented,
    walled_namespace_of,
)
from cardlang.diagnostics import DiagnosticBag, DiagnosticError, Span
from cardlang.domains import (
    CARD_AXIS_ROLES,
    CARD_PARAM_DOMAINS,
    PARAM_DOMAIN_ORDER,
    SIMULTANEOUS_ROLES,
    ZONE_INDEX_ROLES,
    Role,
    binds_actor,
    index_phrase,
    role_names,
    role_of,
)
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES
from cardlang.domains import PARAM_DOMAINS as _FIXED_DOMAINS
from cardlang.libraries import library_names, load_library
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import content_kind_clause, content_noun
from cardlang.stdlib.boards import board_entry
from cardlang.stdlib.enums import (
    SEAT_DIRECTION_VALUES,
    enum_values,
    rank_names,
    suit_names,
)
from cardlang.stdlib.moves import (
    CLIMB_DECISION_MOVE_TYPE,
    LIBRARY_MOVE_TYPES,
    RULE_ENFORCED_MOVE_TYPE,
)
from cardlang.stdlib.rules import stdlib_rules
from cardlang.stdlib.zones import (
    LIBRARY_ZONE_TYPES,
    ZONE_PROJECTIONS,
    identity_to_all,
)
from cardlang.typecheck import KNOWN_TYPE_NAMES
from cardlang.types import Flavor, TPlayer

# The board-only calls that read a grid's PER-PLAYER frame -- one seat's forward
# is the other's backward, the 180-degree opposite (cardlang/stdlib/boards.py).
# Derived as exactly the board verbs taking a player argument, so a later
# player-taking board verb joins this set (and its two-seat Owner Guard) by
# construction rather than by a hand-list that would drift. The player-free
# board calls (`lines`, `is_diagonal`) are not frame reads and stay unaffected.
_FRAME_CALL_FUNCS = frozenset(
    fn
    for fn in BOARD_ONLY_CALL_FUNCS
    if any(isinstance(p, TPlayer) for p in CALL_SIGS[fn].params)
)

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

# Domain nouns that mislead as an indexed-`let` binder. `let x[i] = …` builds a
# per-PLAYER map — the index is a binder bound to each player in turn, whatever
# it is named — so a binder named after a NON-player domain reads as a
# per-suit/per-team store the form does not build (`let x[suit] = 1` keyed by
# players, then `x[hearts]` key-errors; a team read silently lands on a seat).
# Derived from the iteration-role column, minus the domain the form actually
# ranges over.
_MISLEADING_LET_INDEXES = role_names(_ITERATION_ROLES - {Role.PLAYER})

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
_PRONOUNS = frozenset({"state", "action", "winner", "active_rules", "actor"})

# Pronouns that name call-site context (`_user_function` clears them before a
# function body runs). A hermetic body may not read them — it would see None;
# pass the value in as a parameter instead. `state`/`active_rules` are game/phase
# context and remain readable.
_CALL_SITE_PRONOUNS = frozenset({"actor", "action", "winner"})

# Reserved because the language spells them as CLAUSE KEYWORDS, not because a
# pronoun namespace claims them. `outcome` is the only member: it opens a phase's
# `-> outcome { }` and names an auction's outcome function, but nothing binds it
# as a value (an auction's tagged result reaches its consumer through the produce
# path — `execute.py`'s `_ProduceSignal` — never a context slot). Keeping it
# reserved is what makes the pre-#205 spelling of a trick winner (`leader :=
# outcome`) fail loudly rather than bind to whatever state variable a game
# happens to declare. Un-reserving it would widen the accepted surface, so it
# waits for its own change.
_KEYWORD_RESERVED = frozenset({"outcome"})

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
# The third arm, `_KEYWORD_RESERVED`, has its own mechanism (above): the word is
# a clause keyword rather than a namespace.
RESERVED_VALUE_NAMES: frozenset[str] = (
    frozenset({"none", "empty", "true", "false"}) | _PRONOUNS | _KEYWORD_RESERVED
)

_RESERVED_WHY: dict[str, str] = {
    "none": "`x is none` always reads it as the null check",
    "empty": "`x is empty` always reads it as the emptiness check",
    "true": "it is the boolean literal",
    "false": "it is the boolean literal",
    "state": "it is the phase/game state pronoun (`state.foo`)",
    "action": "it is the call-site action pronoun",
    "winner": "it is the call-site winner pronoun",
    "outcome": "it is a clause keyword (a phase's `-> outcome`, an auction's `outcome`)",
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


# Every definition kind a `library { }` may hold, as (Game/Library field name,
# the noun a diagnostic calls it). This tuple IS the closed domain the import
# tier's collision Owner Guards sweep: `_apply_uses` derives its per-kind loops
# from it, so a seventh definition form added to `Library` without an entry here
# is a static failure in `tests/test_family_libraries.py`, not a silently unguarded
# collision. Zones and state are absent as far as the corpus has forced, not
# permanently — what a library needs from the game it names in `requires`.
_LIBRARY_DEF_KINDS: tuple[tuple[str, str], ...] = (
    ("rules", "rule"),
    ("move_types", "move type"),
    ("types", "type"),
    ("defines", "define"),
    ("functions", "function"),
    ("procedures", "procedure"),
)


# Every statement that WRITES persistent state, as (node class, the field holding
# the written name). `runtime/state.py`'s `Store.set` is the one door onto
# persistent state, and `runtime/execute.py` reaches it from exactly these three
# handlers — which is the direction the pin runs in:
# `tests/test_family_libraries.py::test_write_sites_cover_every_state_writing_node`
# scrapes the runtime and compares, so this tuple answers to the executor rather
# than being a list maintained alongside it.
#
# `:=`/`+=`/`-=` and `rotate` carry a classified `NameRef`; `again` is a bare
# string the runtime clears at each turn boundary, which is why it is a write
# site at all and why a hand-written axis would have missed it.
_STATE_WRITE_SITES: tuple[tuple[type[n.Stmt], str], ...] = (
    (n.AssignStmt, "target"),
    (n.RotateStmt, "target"),
    (n.Turns, "again"),
)


def _written_state_name(node: object) -> str | None:
    """The state name this node writes, or None if it writes no state."""
    for cls, field_name in _STATE_WRITE_SITES:
        if isinstance(node, cls):
            written = getattr(node, field_name)
            if isinstance(written, n.NameRef):
                return written.name
            return written if isinstance(written, str) else None
    return None


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
    (n.RuleDef, "name"): "rule",
    (n.MoveTypeDef, "name"): "move_type",
    (n.FunctionDef, "name"): "function",
    (n.ProcedureDef, "name"): "procedure",
    (n.DefineDef, "name"): "define",
    (n.TypeDef, "name"): "type",
    (n.StructField, "name"): "field",
    (n.DerivedField, "name"): "field",
    (n.Parameter, "name"): "param",
    (n.PrimitiveDecl, "name"): "primitive",
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
        (n.ForEach, "binder"),
        (n.Turns, "binder"),
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
    # Zones. The two card-moving round forms name both of their zones as bare
    # strings; the auction form moves no cards and so has neither.
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
    (n.StructField, "type_name"): "type",
    (n.StructLit, "type_name"): "type",
    (n.OutcomeCase, "payload_types"): "type",
    # Definitions, by kind. The move-type slots split across two namespaces and
    # the split is load-bearing, not a nicety: an OFFERING names move types the
    # game defines (`_check_offering_moves` against `defined_move_types`),
    # while `constrains:`, `legal_moves:`, a transition event and a trick/climb
    # round's move type name the kernel registry (`LIBRARY_MOVE_TYPES`). Only
    # the first pair is a channel an importing game can feed.
    (n.Offer, "offering"): "move_type",
    (n.AuctionRound, "offering"): "move_type",
    (n.TrickRound, "move_type"): "kernel_move_type",
    (n.ClimbRound, "move_type"): "kernel_move_type",
    (n.LegalMoves, "move_types"): "kernel_move_type",
    (n.MoveEvent, "move_type"): "kernel_move_type",
    (n.RuleDef, "constrains"): "kernel_move_type",
    (n.RuleRef, "name"): "rule",
    (n.Produces, "define"): "define",
    (n.RunStmt, "name"): "procedure",
    (n.Call, "func"): "function",
    # The Primitive query registries a `round` selects from. A closed kernel table
    # in every direction — the same names for a library as for a game — which is
    # why they are references and yet not a channel a game can feed.
    (n.TrickRound, "winner_fn"): "primitive_query",
    (n.TrickRound, "early_termination"): "primitive_query",
    (n.AuctionRound, "outcome_fn"): "primitive_query",
    (n.ClimbRound, "combos_fn"): "primitive_query",
    (n.ClimbRound, "follows_fn"): "primitive_query",
    # Deck-derived values, held as strings rather than classified names.
    (n.CardLiteral, "rank"): "deck_rank",
    (n.CardLiteral, "suit"): "deck_suit",
    (n.Game, "ranking"): "deck_rank",
    (n.CardPointsEntry, "rank"): "deck_rank",
    (n.Game, "trump"): "deck_suit",
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
    # Names owned by a declaration reached elsewhere: a struct's fields belong to
    # the type its literal names, a named argument's to the callee's parameter
    # list, a produced tag to the define's outcome cases. Each is a reference,
    # and none is an independent channel — the owning name is a slot above.
    (n.Member, "field"): "field",
    (n.FieldInit, "name"): "field",
    (n.NamedArg, "name"): "param",
    (n.Produce, "tag"): "outcome_tag",
    (n.ProduceArm, "tag"): "outcome_tag",
    # The item noun a movement moves (`cards`, `coins`): drawn from the game's
    # CONTENT FLAVOR, which is the component set's, so it is a game-fed slot the
    # way a suit is. Not swept for a library — see `_LIBRARY_UNSWEPT`.
    (n.Transfer, "item"): "content_kind",
}

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
        (n.Quantifier, "kind"),
        (n.PhaseQualifier, "kind"),
        (n.Demands, "kind"),
        (n.Comprehension, "agg"),
        (n.Choose, "domain"),
        (n.Transfer, "verb"),
        (n.Transfer, "selection_mode"),
        (n.Transfer, "amount"),
        (n.Transfer, "distribution"),
        (n.AuctionRound, "order_mode"),
        (n.Winner, "rank_dir"),
        (n.Game, "ranking_convention"),
        # Annotated `TrickOrderRowKey` (a `Literal`), like `content_flavor`
        # below: a KEYWORD, not a reference — the row key names a row of the
        # language's `TRICK_ORDER_ROWS`, a fixed set the parse builder
        # validates against, never a designer-authored name in any namespace.
        (n.TrickOrderRow, "key"),
        # Annotated `Flavor` (a `Literal`), not `str` — which is exactly why it
        # was the one field the registry's first domain predicate missed. It
        # holds a string like any other keyword slot: the clause that selected
        # the component set, stamped at parse.
        (n.Game, "content_flavor"),
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

# The two slots this pass owns itself.
_CLASSIFIED_SLOTS: frozenset[tuple[type, str]] = frozenset({(n.NameRef, "name")})
_METADATA_SLOTS: frozenset[tuple[type, str]] = frozenset({(n.NameRef, "ref_kind")})


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

# Reference namespaces that are the UNION of declaration namespaces, and which
# ones each draws from. A slot whose name may come from either of two
# declaration blocks cannot name one of them, and naming neither would leave
# the namespace unowned — the state `test_every_namespace_is_named` exists to
# keep impossible. WHICH declaration a given name is stays resolve's
# classification, made where the declarations are in hand.
_UNION_NAMESPACES: dict[str, frozenset[str]] = {
    # A `primitives { }` entry's `reads` name is one of the game's own keyed
    # declarations: a `state { }` variable or a `zones { }` zone
    # (`_classify_primitive_read`).
    "primitive_read": frozenset({"state", "zone"}),
}


def _member_namespace(node: object) -> str | None:
    """`x.field` reads a field of whatever `x` is, so the namespace depends on
    the object: `state.foo` names a STATE variable, while every other object's
    fields belong to the type that object has — a namespace reached through the
    declaration that named the type, not through this slot."""
    obj = cast(n.Member, node).obj
    if isinstance(obj, n.NameRef) and obj.name == "state":
        return "state"
    return "field"


def _domain_query_namespace(node: object) -> str | None:
    """A bare `any <domain> where …` names a declared position domain and binds
    a member of it; the collection form (`all cells in <expr>`) binds a fixed
    noun and names nothing. Only the bare form is a reference."""
    return "position" if cast(n.DomainQuery, node).source is None else None


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
    (n.Member, "field"): _ContextualSlot(frozenset({"state", "field"}), _member_namespace),
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


# The DEFINITION containers: a statement body reached by NAME, never by
# containment. Every other statement holder (`if`, `repeat until`, `turns`,
# `as`, a `produces:` arm, the loop hooks) sits inside a phase body, so
# walking the phases reaches it; these three are top-level lists on `n.Game`
# and their bodies run only where something names them.
#
# The value is (the `n.Game` field holding them, the reference namespace that
# names one). Authored, and pinned complete against the AST-derived container
# set by `tests/test_trump_slot_class.py::test_every_name_reached_container_
# is_classified` — a new statement-holding definition form fails there rather
# than silently defaulting to "always reachable", which is the shape of the
# defect this table exists to end.
_DEFINITION_CONTAINERS: dict[type, tuple[str, str]] = {
    n.DefineDef: ("defines", "define"),
    n.MoveTypeDef: ("move_types", "move_type"),
    n.ProcedureDef: ("procedures", "procedure"),
}

# Runtime refusal (decisions.md "Closed-domain completeness"): each namespace
# above must be one the reference registry actually issues, or the lookup below
# silently matches nothing and every container reads as unreachable.
_UNKNOWN_CONTAINER_NAMESPACES = {
    ns for _, ns in _DEFINITION_CONTAINERS.values()
} - set(_REFERENCE_SLOTS.values())
if _UNKNOWN_CONTAINER_NAMESPACES:
    raise AssertionError(
        f"_DEFINITION_CONTAINERS names namespaces no reference slot issues: "
        f"{sorted(_UNKNOWN_CONTAINER_NAMESPACES)}"
    )


def _reachable_definitions(game: n.Game) -> dict[tuple[str, str], object]:
    """Every definition container reachable from a phase body, keyed by
    (namespace, name).

    A fixpoint, not one pass: a define invoked from a reachable move-type
    effect is reachable, and so is a move type offered from inside a reachable
    define body. Which slots NAME a container is read off `slot_namespace`
    rather than matched by node kind, so a future invoking construct added to
    `_REFERENCE_SLOTS` reaches this sweep without editing it.

    NOT a Shadow of `_reaches`: that walks the function-to-function call graph
    for recursion detection (name to name, one namespace). This walks name to
    CONTAINER across three namespaces, and answers a different question — does
    this body run at all. It also does not close issue #242, which is about
    what STATE a callable body may read; this establishes only which bodies
    run, which #242's conservative rule would need but is not."""
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)}
        for field, ns in _DEFINITION_CONTAINERS.values()
    }
    reached: dict[tuple[str, str], object] = {}
    frontier: list[object] = list(game.phases)
    while frontier:
        for node in _walk(frontier.pop()):
            for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
                namespace = slot_namespace(node, field_name)
                if namespace is None:
                    continue
                pool = pools.get(namespace)
                if pool is None:
                    continue
                for name in slot_strings(node, field_name):
                    key = (namespace, name)
                    target = pool.get(name)
                    if target is None or key in reached:
                        continue
                    reached[key] = target
                    frontier.append(target)
    return reached


def _reachable_nodes(game: n.Game) -> Iterator[object]:
    """Every AST node the game can actually reach: the phase bodies, plus the
    definition bodies something reachable names. The counterpart of `_walk` for
    a guard whose question is "does this RUN", not "is this written"."""
    for phase in game.phases:
        yield from _walk(phase)
    for container in _reachable_definitions(game).values():
        yield from _walk(container)


@dataclass(frozen=True)
class _StateClaims:
    """The outcome of resolving who claims which state name across a game and
    the libraries it uses.

    `provided` maps a surviving provided name to the library that owns it — the
    input to both the read-only Owner Guard and the splice. `contested` is the names a
    claim collision has already been reported for, which `_check_requires` skips
    so one bad name yields one diagnostic instead of two."""

    provided: dict[str, str]
    contested: frozenset[str]


def _apply_uses(game: n.Game, bag: DiagnosticBag) -> n.Game:
    """Resolve every `uses <library>` line: load the named libraries, refuse the
    three-way collisions, check each library's `requires` contract against the
    game's declared state, and splice the definitions into the game.

    Runs FIRST in `resolve`, before every other name check, so that what flows on
    is one flat `Game` and no later pass needs to know imports exist — which is
    what makes an import pure name resolution, with no runtime or
    information-set implication.

    Collisions are errors, never overrides: `uses` is composition, and a game
    redefining what it imports would make the tier inheritance (decisions.md
    "Family libraries"). That is also why the game's own definitions are spliced
    alongside, not merged over, the library's."""
    if not game.uses:
        return game

    available = library_names()
    libraries: list[tuple[n.UsesDecl, n.Library]] = []
    seen_uses: dict[str, n.UsesDecl] = {}
    for use in game.uses:
        if use.name in seen_uses:
            bag.error(
                f"game '{game.name}' already uses library '{use.name}' — the "
                f"repeat imports nothing further; delete it",
                use.span,
            )
            continue
        seen_uses[use.name] = use
        if use.name not in available:
            known = ", ".join(sorted(available)) or "none"
            bag.error(
                f"unknown library '{use.name}' — `uses` names a family library "
                f"in docs/libraries/ (available: {known})",
                use.span,
            )
            continue
        libraries.append((use, load_library(use.name)))

    _check_library_collisions(game, libraries, bag)
    claims = _check_state_claims(game, libraries, bag)
    _check_library_shadows_game(game, libraries, bag)
    _check_provided_readonly(game, claims.provided, bag)
    skip = claims.contested | frozenset(claims.provided)
    for use, library in libraries:
        _check_library_encapsulation(library, bag)
        _check_contract_shapes(library, bag)
        _check_require_indexes(library, bag)
        _check_requires(game, use, library, bag, skip)

    # Imported definitions come FIRST, in `uses` order, then the game's own: the
    # import is the base a game extends, which is the order the game file itself
    # reads in (`uses` sits at the top). Names are unique across the two by the
    # collision Owner Guards above, so order carries no meaning beyond IR stability —
    # but it must be STABLE, since `ir.emit` prints these tuples in order and the
    # goldens pin the printout.
    spliced: dict[str, tuple[object, ...]] = {}
    for field, _ in _LIBRARY_DEF_KINDS:
        from_libraries = tuple(
            d for _, library in libraries for d in getattr(library, field)
        )
        spliced[field] = from_libraries + tuple(getattr(game, field))
    # Provided state splices the same way and for the same reason: a library's
    # `state { }` becomes part of the game's own, so no later pass can tell a
    # provided variable from one the game declared, and the tier keeps carrying
    # no runtime and no information-set implication. The read-only rule is
    # therefore enforced ENTIRELY above this line — once the two are one block
    # the distinction no longer exists to check.
    provided_decls = tuple(
        decl
        for _, library in libraries
        if library.state is not None
        for decl in library.state.decls
    )
    state = game.state
    if provided_decls:
        state = (
            replace(state, decls=provided_decls + state.decls)
            if state is not None
            else n.StateBlock(decls=provided_decls)
        )
    # `uses` is emptied here for the same reason `procedures` is emptied by
    # `expand`: a surviving entry downstream would mean the import was parsed and
    # ignored, and `openspiel.encoding` walks every dataclass field of the Game.
    return replace(game, uses=(), state=state, **spliced)  # type: ignore[arg-type]


def _check_library_collisions(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> None:
    """The three-way collision matrix — game / library / engine — swept across
    every definition kind in `_LIBRARY_DEF_KINDS` rather than the kinds that
    happen to collide in today's corpus (decisions.md "Closed-domain
    completeness": sweep the class, don't patch the instance).

    The engine leg covers the two registries whose names share ONE namespace with
    a game's definitions: rules (the stdlib rule index, which library rules splice
    into `game.rules`) and native call functions — two different namespaces, which
    is why the leg is named for the engine rather than for either of them. Kernel MOVE types are deliberately not a cell: they and a game's
    `move_type` definitions are two disjoint consult paths that never merge
    (`stdlib/moves.py`, and Stud/Skat/Schnapsen/Coup all rely on it), so a guard
    here would reject four games that are correct today."""
    for field, noun in _LIBRARY_DEF_KINDS:
        local = {d.name: d for d in getattr(game, field)}
        from_libraries: dict[str, str] = {}
        for use, library in libraries:
            for definition in getattr(library, field):
                if definition.name in local:
                    bag.error(
                        f"{noun} '{definition.name}' is defined by this game and "
                        f"also by library '{library.name}' — `uses` imports, it "
                        f"does not inherit, so there is no override: rename the "
                        f"game's {noun}, or drop it and use the library's",
                        local[definition.name].span,
                    )
                elif definition.name in from_libraries:
                    bag.error(
                        f"{noun} '{definition.name}' is defined by both library "
                        f"'{from_libraries[definition.name]}' and library "
                        f"'{library.name}' — resolution is flat, so neither wins; "
                        f"use only one of them, or rename in one library",
                        use.span,
                    )
                else:
                    from_libraries[definition.name] = library.name

    stdlib_rule_index = stdlib_rules()
    for _, library in libraries:
        for rule in library.rules:
            if rule.name in stdlib_rule_index:
                bag.error(
                    f"library '{library.name}' defines rule '{rule.name}', which "
                    f"shadows the standard-library rule of the same name — "
                    f"delete it (`active_rules` resolves it from the stdlib), or "
                    f"rename it if the body genuinely differs",
                    rule.span,
                )
        for fn in library.functions:
            # The WHOLE registry, unlike the namespace `_library_slot_names`
            # gives a library's CALLS: naming and calling are different
            # questions. A library body may not CALL a game-local Primitive,
            # but a library function that TAKES one's name shadows it in every
            # legacy game that imports the library — and a library cannot know
            # which games those are, so the widest namespace is the only sound
            # one here, and it reports to the library's own author.
            if fn.name in CALL_FUNCS:
                bag.error(
                    f"library '{library.name}' defines function '{fn.name}', "
                    f"which shadows the native function of the same name; rename "
                    f"it (a call would type-check against the native signature "
                    f"but run this one instead)",
                    fn.span,
                )


# Where a name a library injects can land in the game, as (game field, the noun
# a diagnostic calls it). Read off `_classify`'s precedence chain plus the
# namespaces that own a name outside it (positions; the definition kinds). This
# is the axis `_game_bindings` sweeps, so a namespace added to `_classify` or a
# def kind added to `_LIBRARY_DEF_KINDS` without an entry here fails a static
# test rather than silently leaving a hole a library could inject through.
_INJECTABLE_TARGETS: tuple[tuple[str, str], ...] = (
    ("zones", "zone"),
    ("positions", "position domain"),
    # The six definition kinds, with the SAME nouns as `_LIBRARY_DEF_KINDS` so
    # the same-kind skip below matches by noun. Pinned equal to it by
    # `tests/test_family_libraries.py::test_injectable_targets_cover_every_def_kind`.
    ("functions", "function"),
    ("types", "type"),
    ("defines", "define"),
    ("move_types", "move type"),
    ("rules", "rule"),
    ("procedures", "procedure"),
)


def _game_bindings(game: n.Game) -> dict[str, tuple[str, Span | None]]:
    """Every name the game binds that a bare reference could resolve to, mapped
    to (the noun for a diagnostic, the span to point at). Built in `_classify`
    precedence order with `setdefault`, so when a game reuses one name across its
    own namespaces (which the base language allows — the author wrote both and
    can see both) the reported noun is the one a reference actually resolves to.

    Deck values have no declaration site, so their span is None; the caller
    points at the library's injected declaration instead, which is the only text
    an author can edit to fix the clash."""
    bindings: dict[str, tuple[str, Span | None]] = {}
    for nd in _walk(game):
        if isinstance(nd, n.StateDecl):
            bindings.setdefault(nd.name, ("state variable", nd.span))
    for zone in game.zones:
        bindings.setdefault(zone.name, ("zone", zone.span))
    deck = game.deck
    if _deck_known(deck):
        for suit in suit_names(deck):
            bindings.setdefault(suit, ("suit value", None))
        for rank in rank_names(deck):
            bindings.setdefault(rank, ("rank value", None))
    for direction in SEAT_DIRECTION_VALUES:
        bindings.setdefault(direction, ("direction value", None))
    for pos in game.positions:
        bindings.setdefault(pos.name, ("position domain", pos.span))
    for field, noun in _INJECTABLE_TARGETS:
        if field in ("zones", "positions"):
            continue  # already added above, with their own spans
        for definition in getattr(game, field):
            bindings.setdefault(definition.name, (noun, definition.span))
    # `_classify`'s `function` bucket is the native value names, not the game's
    # own functions (those resolve as `Call`s, never as bare names) — so a
    # provided variable spelled like a native value shadows it exactly as a
    # deck-value clash does, `state_vars` winning over `functions`. Lowest
    # precedence, added last, so a real game binding keeps the reported noun.
    # `test_game_bindings_covers_every_resolvable_value_bucket` pins this against
    # `_categories` so a value bucket added there cannot slip past uncovered.
    for value_fn in VALUE_NAMES:
        bindings.setdefault(value_fn, ("standard-library value", None))
    return bindings


def _check_library_shadows_game(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> None:
    """A name a library injects into the game must not already name something in
    the game — in ANY namespace, not merely the same kind.

    `_check_library_collisions` owns the same-kind diagonal (a library function
    over a game function is an attempted override) and `_check_state_claims` owns
    provided-over-game-state; this owns everything off both — a provided name or
    a library definition landing on the game's zones, deck values, positions, or
    definitions of a DIFFERENT kind. Those are the silent traps: a `uses` import
    adds names and cannot override, and the game's author never opens the library
    file, so a bare reference they write meaning their own zone or the suit
    `hearts` would resolve to the library's variable instead, or the reverse. The
    base language lets a game reuse one name across its own namespaces because the
    author wrote and can see both; here one side is invisible, which is the whole
    difference.

    The refusal is deliberately CONSERVATIVE: a coincidence is refused even where
    `_classify` precedence would keep it harmless (a library `function` named
    after a game `state` variable, which a reference never confuses), because the
    rule a designer holds is "a library may not bring in a name you already use",
    not a table of safe precedence pairs. No corpus game pays for it.

    Matched by NAME, not `ref_kind`: this runs before classification (like
    `_check_provided_readonly`), which is what lets it see a zone reached only
    through the bare-string `round … into <zone>` slot that classification never
    stamps — the silent half of the collision matrix that a classify-based check
    would leave open.

    Reported naming the library, because the game author cannot see what they
    collided with. The span points at the game's own declaration when it has one
    (a zone, a definition), and at the library's injected declaration for a deck
    value, which has none."""
    game_names = _game_bindings(game)
    def_nouns = {noun for _, noun in _LIBRARY_DEF_KINDS}
    for use, library in libraries:
        injected: list[tuple[str, str, Span | None]] = [
            (decl.name, "provided state", decl.span)
            for decl in (library.state.decls if library.state is not None else ())
        ]
        for field, noun in _LIBRARY_DEF_KINDS:
            for definition in getattr(library, field):
                injected.append((definition.name, noun, definition.span))

        for name, inject_noun, inject_span in injected:
            hit = game_names.get(name)
            if hit is None:
                continue
            game_noun, game_span = hit
            # The two pairs other Owner Guards already report — skip them so one clash
            # yields one diagnostic. Same-kind definition collisions are
            # `_check_library_collisions` ("does not inherit"); a provided name
            # over the game's own state is `_check_state_claims`.
            if inject_noun == game_noun and inject_noun in def_nouns:
                continue
            if inject_noun == "provided state" and game_noun == "state variable":
                continue
            bag.error(
                f"library '{library.name}' brings in {inject_noun} '{name}', but "
                f"this game already uses '{name}' as a {game_noun} — a `uses` "
                f"import adds names without overriding, and the game's author "
                f"cannot see the library's, so the two would silently mean "
                f"different things: rename one",
                game_span if game_span is not None else inject_span,
            )


def _check_state_claims(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> _StateClaims:
    """Refuse every way two claims on one state name can collide, and report which
    names survive as PROVIDED.

    A state name can be claimed from three places — the game's own `state { }`, a
    library's `state { }`, and a library's `requires { }` — and only two
    coexistences are legal: a requirement the game answers, and two libraries
    requiring one name, which one game declaration answers. The rest are refused:

    - A library that both provides and requires a name is incoherent, not merely
      redundant. The two clauses point opposite ways — `state` says the library
      owns the initial value, `requires` says the game picks it — so there is no
      reading under which both hold.
    - A game declaring what a library provides is the state face of "`uses`
      imports, it does not inherit". Keeping the game's would be an override;
      keeping the library's would discard a declaration the author wrote.
    - Two libraries providing one name have no winner, because resolution is
      flat. Picking one by `uses` order would make the game's meaning depend on
      the order of its import lines.
    - A requirement answered by ANOTHER library's provision is refused because
      `requires` says the including GAME declares the name. Letting a second
      library's variable answer it would couple two libraries through a name
      neither mentions the other in, and would do it silently.

    Each is reported where its author can fix it: the provision's own span when
    the library contradicts itself, the game's declaration when the game
    shadows, and the `uses` line when two imports disagree."""
    declared: dict[str, n.StateDecl] = {}
    for node in _walk(game):
        if isinstance(node, n.StateBlock):
            for decl in node.decls:
                declared.setdefault(decl.name, decl)

    provided: dict[str, str] = {}
    contested: set[str] = set()
    for use, library in libraries:
        required = {r.name for r in library.requires}
        for decl in library.state.decls if library.state is not None else ():
            if decl.name in required:
                contested.add(decl.name)
                bag.error(
                    f"library '{library.name}' both provides and requires state "
                    f"'{decl.name}' — `state` owns the variable and its initial "
                    f"value, `requires` leaves both to the including game, so a "
                    f"name can be one or the other: drop it from whichever "
                    f"clause is wrong",
                    decl.span,
                )
            elif decl.name in provided:
                contested.add(decl.name)
                bag.error(
                    f"state '{decl.name}' is provided by both library "
                    f"'{provided[decl.name]}' and library '{library.name}' — "
                    f"resolution is flat, so neither wins; use only one of them, "
                    f"or rename in one library",
                    use.span,
                )
            elif decl.name in declared:
                contested.add(decl.name)
                bag.error(
                    f"state '{decl.name}' is declared by this game and also "
                    f"provided by library '{library.name}' — `uses` imports, it "
                    f"does not inherit, so there is no override: delete the "
                    f"game's declaration and read the library's, or rename the "
                    f"game's",
                    declared[decl.name].span,
                )
            else:
                provided[decl.name] = library.name

    for use, library in libraries:
        for want in library.requires:
            owner = provided.get(want.name)
            if owner is not None and owner != library.name:
                contested.add(want.name)
                bag.error(
                    f"library '{library.name}' requires state '{want.name}', "
                    f"which library '{owner}' provides — a requirement names "
                    f"state the including GAME declares, and is not answered by "
                    f"another library's provision; declare it in the game and "
                    f"rename one of the two",
                    use.span,
                )
    return _StateClaims(provided=provided, contested=frozenset(contested))


def _check_provided_readonly(
    game: n.Game, provided: dict[str, str], bag: DiagnosticBag
) -> None:
    """A game may READ library-provided state and may not WRITE it.

    Runs BEFORE the splice, over the game's own text alone, which is the only
    moment the distinction exists: afterwards a provided variable is one of the
    game's own state declarations and the library's definitions — which write
    their own state freely — are indistinguishable from the game's.

    Every write form is swept, not just `:=`: `_STATE_WRITE_SITES` is the
    executor's own set of state-writing statements, so `rotate` and a `turns …
    again <flag>` are covered by construction rather than by remembering them.

    Matched by NAME rather than by `ref_kind`, because `_apply_uses` runs before
    classification — deliberately, since the splice is what later passes must see
    a flat game after. That is sound for the class this Owner Guard owns: a write
    target must classify as a state variable (`_bad_write_target`), and a provided
    name IS one. The one case where the two readings differ is a game-local binder
    named after a provided variable, which this Owner Guard reports as the write it
    refuses rather than as the shadow `_bad_write_target` would call it — a
    different sentence about the same defect, and the fix (rename) is the same.

    Reported to the GAME's author, unlike `_check_library_encapsulation` next
    door: the game's author wrote the assignment and is the only one who can
    withdraw it."""
    for node in _walk(game):
        name = _written_state_name(node)
        if name is None or name not in provided:
            continue
        bag.error(
            f"cannot write '{name}': library '{provided[name]}' provides it. "
            f"Provided state belongs to the library — the game may read it, but "
            f"only the library's own definitions may write it. Keep a state "
            f"variable of the game's own for what the game must change, or have "
            f"the library expose a procedure that makes the change",
            getattr(node, "span", None),
        )


# Binder-introducing node kinds whose introduced SPELLING the GAME's own text
# fixes, as against the kinds the LANGUAGE fixes it for (`any player where`
# always binds `player`, an aggregation always binds `card`, a transfer filter
# binds the content noun, a position query binds the domain's noun). Both halves
# shadow identically, so this is not a scoping table: it decides only WHOSE text
# can fix a collision with a provided name, and therefore which fix the
# diagnostic prescribes.
#
# Membership is the claim "the game's own text fixes this spelling, so its author
# can respell it". A free `NAME` token is NOT the test, and reading it that way
# mis-sorts both borders: `each <role> simultaneously` takes a free `NAME` that
# `SIMULTANEOUS_ROLES` admits exactly one spelling for, and `n.DomainQuery`'s
# bare form takes its noun from the game's own `positions { }` row. `DomainQuery`
# is filed under the language because the only sub-position that is the author's
# is one `_game_bindings` holds, which
# `_check_provided_shadowed_by_binder` skips — so no cell reaching the guard
# through this kind is respellable. Pinned against `_node_binders`'s own domain by
# `tests/test_family_libraries.py::test_the_author_chosen_split_classifies_every_
# binding_kind`, so a new binding node kind must be filed under one side or the
# other rather than defaulting to either.
_AUTHOR_CHOSEN_BINDERS: frozenset[type] = frozenset(
    {n.ForEach, n.Turns, n.LetStmt, n.ProduceArm, n.TypeDef}
)


@dataclass(frozen=True)
class _SlotLeak:
    """One bare-string reference in a library that names something the library
    does not have — the slot registry's finding, addressed as the
    encapsulation Owner Guard addresses it."""

    node: object
    field: str
    name: str
    namespace: str


# What a LIBRARY may legally write in a bare-string slot of each namespace. The
# empty sets are the design, not an omission: a library declares no zones and no
# phases and names no deck (decisions.md "Family libraries"), so there is no
# spelling of a zone, a phase or a suit it may write at all.
#
# A namespace absent from this table is NOT swept. That is a claim, so it is
# recorded rather than implied — `_LIBRARY_UNSWEPT` below carries one reason per
# absence, and `tests/test_family_libraries.py` pins the two together against
# every reference namespace reachable from a library's own clauses, so a slot
# whose namespace nobody classified fails a static test instead of quietly
# joining the blind spot this registry exists to end.
def is_zone_contract(want: n.RequireDecl) -> bool:
    """Whether a `requires` entry names a `zones { }` declaration rather than a
    `state { }` one.

    Read off the type registries, which is a DERIVATION rather than an authored
    rule only because no name reaches two of them: `KNOWN_TYPE_NAMES` and
    `LIBRARY_ZONE_TYPES` are disjoint, and the two author-chosen namespaces that
    could have collided with either — a game's `positions { }` and a library's
    own `type`s — are refused the zone spellings where they are DECLARED
    (`POSITION_NAME_SOURCES`, `_check_zone_type_names_are_not_taken`). Without
    those Owner Guards this function would be picking one meaning of an ambiguous name
    with nowhere to record the choice."""
    return want.type_name in LIBRARY_ZONE_TYPES


def _library_slot_names(library: n.Library) -> dict[str, frozenset[str]]:
    provided = library.state.decls if library.state is not None else ()
    return {
        "state": frozenset(
            r.name for r in library.requires if not is_zone_contract(r)
        )
        | frozenset(d.name for d in provided),
        # A contract's type slot may name either registry, so the sweep admits
        # both — the entry's own leg then refuses the crossed shapes (a `?` on a
        # zone type, an `<owner>` on a state type), which is a shape question
        # rather than a spelling one.
        "type": frozenset(t.name for t in library.types)
        | KNOWN_TYPE_NAMES
        | frozenset(LIBRARY_ZONE_TYPES),
        "move_type": frozenset(m.name for m in library.move_types),
        "define": frozenset(d.name for d in library.defines),
        "procedure": frozenset(p.name for p in library.procedures),
        # BUILTIN_CALL_FUNCS, not CALL_FUNCS: a library body may call the
        # generic native functions the language ships, and may not call a
        # game-local [[primitive]]. A Primitive's meaning belongs to ONE game,
        # so a library — which several games import — naming one is the
        # cross-game coupling the `primitives { }` block exists to end; and an
        # importing game that declares a block would refuse the call anyway,
        # to ITS author rather than the library's, which is the library-alone
        # property this sweep is for.
        "function": frozenset(f.name for f in library.functions) | BUILTIN_CALL_FUNCS,
        "enum_value": SEAT_DIRECTION_VALUES,
        # No longer empty: a library reaches exactly the zones it contracts for,
        # and nothing else. This is the set every zone-naming slot is swept
        # against — `Transfer.source`/`dest` as ordinary expressions, and
        # `Round.source_zone`/`play_zone` as bare strings.
        "zone": frozenset(r.name for r in library.requires if is_zone_contract(r)),
        # A zone type's `<owner>` argument. A library has no `positions { }` and
        # cannot declare one, so the roles are all it may name — which is also
        # why a position-indexed zone family cannot be contracted at all. The
        # sibling slot, an index, is NOT swept here: `_check_require_indexes`
        # owns that class and says more than a leak message can.
        "zone_type_arg": frozenset(role_names(ZONE_INDEX_ROLES)),
        "phase": frozenset(),
        "mode": frozenset(),
        "position": frozenset(),
        "deck_rank": frozenset(),
        "deck_suit": frozenset(),
    }


# Why each REACHABLE reference namespace is not swept here. Rows exist only for
# namespaces a library's own text can actually name: an excuse for something
# unreachable excuses nothing, and a table holding those cannot be pinned in the
# deleting direction — `test_every_reachable_reference_namespace_is_swept_or_
# excused` would stay green with the row gone, which makes the row read as a
# guarantee it never was. (The unreachable namespaces are `rule`, `game`,
# `library`, `component_set`, `board_family`, `zone_type` and `zone_type_arg`,
# each because its clause — `active_rules:`, `zones { }`, `cards:`, `board:`,
# `uses` — is a GAME clause the library grammar has no production for. One
# SLOT of a swept namespace is unreachable the same way and is recorded here
# rather than as a row, since its namespace is swept and a row would read as
# "not swept": `deck_suit` is swept for the card literal's suit, which a
# library can write, and vacuous for `(n.Game, "trump")` — `trump:` is a game
# clause with no library production, so no library ever names a suit there;
# the value's Owner Guard is `_resolve_trump`, over the game.)
#
# Three shapes of reason, and they are not interchangeable. CLOSED: the
# namespace is the same for a library as for a game, so no importing game can
# feed it. GUARDED ELSEWHERE: the name IS game-fed, and another pass refuses it —
# the row must then say WHICH pass, because "something catches it" is how a
# reason becomes untrue without anyone noticing. DESIGNED: nothing checks the
# name anywhere, by a recorded decision.
#
# Every reason below was PROBED, not reasoned. The three that are not simply
# closed were all wrong on first writing — each said the classified pass refused
# the case, and each case in fact resolves clean and is refused a stage later.
_LIBRARY_UNSWEPT: dict[str, str] = {
    "kernel_move_type": "closed: `LIBRARY_MOVE_TYPES`, identical for a library and a game",
    "primitive_query": "closed: the Primitive round-query registries, identical either side",
    "index_domain": (
        "guarded elsewhere, and NOT closed — the row's earlier reading claimed the "
        "namespace was closed because a game may not declare a non-role index "
        "either. Zone contracts falsified that: a game DOES declare "
        "position-indexed zone families (Klondike's `tableau_down[column]`), so a "
        "contract could name a position domain the importing game alone declares. "
        "`_check_require_indexes` refuses it, to the library's author, for a "
        "requirement and for a provided variable alike"
    ),
    "role": (
        "guarded elsewhere, and NOT closed — the row's first reading was wrong. The role "
        "NAMES are the domain registry's, but `suit`/`rank` admissibility follows the "
        "importing game's component set: `for each suit` is accepted by a card game and "
        "refused by a piece game. So this is deck-agnosticism escaping through a role, "
        "the same property `deck_rank`/`deck_suit` are swept for. It is not silent — "
        "typecheck's flavor Owner Guard refuses it to the LIBRARY's author — but the "
        "library-alone property is weaker here than the sweep provides (issue #183)"
    ),
    "content_kind": (
        "guarded elsewhere: typecheck compares the item noun against the game's content "
        "flavor and reports to the library's author. NOT, as this row first claimed, "
        "because a movement always names a zone the classified pass refuses — that "
        "premise is now doubly false, since a movement may also name a CONTRACTED "
        "zone; re-probed with an unknown noun and with a flavor-wrong one, both "
        "refused to the library's author (issue #170)"
    ),
    "outcome_tag": (
        "guarded elsewhere: a `produce` outside a define or outcome-phase body is "
        "refused outright, and a tag naming no declared outcome is refused against the "
        "outcome registry — both to the library's author (probed via the full "
        "pipeline; `resolve` alone accepts them, which is what made the first reading "
        "of this row say the tags were merely `owned` by a swept name)"
    ),
    "param": (
        "guarded elsewhere: `NamedArg` is refused outright — named call arguments are "
        "not supported, so the parameter name never reaches a namespace"
    ),
    "field": (
        "designed: `x.field` on anything but the `state` pronoun is a field of that "
        "object's type, and the pronoun namespaces' fields are `TAny` by decision "
        "(decisions.md, the `action` trap) — so there is nothing to check rather than "
        "something owned elsewhere"
    ),
}


def _slot_leaks(
    library: n.Library,
) -> tuple[tuple[_SlotLeak, ...], frozenset[str], frozenset[str]]:
    """Every bare-string reference in `library` that names something outside it,
    and the state names its bare-string slots successfully READ.

    The second half is not a by-product: `state_reads` feeds the contract's
    MINIMALITY check, and before this sweep existed it accumulated from
    `NameRef`s alone — so `turns … again <var>` had no correct spelling at all.
    Naming the variable in `requires` made the entry look dead and the check
    called the contract non-minimal; leaving it out was the leak. One sweep
    answers both, which is why they are computed together rather than in two
    passes that could disagree about what a slot reaches."""
    legal = _library_slot_names(library)
    leaks: list[_SlotLeak] = []
    reads: set[str] = set()
    zone_reads: set[str] = set()
    for node in _walk(library):
        for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
            namespace = slot_namespace(node, field_name)
            if namespace is None:
                continue
            allowed = legal.get(namespace)
            if allowed is None:
                continue
            for name in slot_strings(node, field_name):
                # A type name carries its nullability with it (`Suit?`), exactly
                # as `_check_declared_type_names` reads it.
                bare = name.removesuffix("?") if namespace == "type" else name
                if bare not in allowed:
                    leaks.append(_SlotLeak(node, field_name, name, namespace))
                elif namespace == "state":
                    reads.add(bare)
                elif namespace == "zone":
                    # `Round.source_zone` / `play_zone` name a zone as a bare
                    # string, so the minimality check needs them for the same
                    # reason it needs `turns … again <var>`: a contract entry
                    # reached only through a bare-string slot would look dead.
                    zone_reads.add(bare)
    return tuple(leaks), frozenset(reads), frozenset(zone_reads)


@dataclass(frozen=True)
class _LibraryReach:
    """What a library's definitions reach for, classified against the library's
    OWN namespaces — the input to both directions of the `requires` contract:
    nothing may be reached that the contract does not cover (`unresolved`,
    `unknown_calls`, `slot_leaks`), and nothing may be in the contract that is
    never reached (`state_reads`, which the tier's ledger test reads)."""

    unresolved: tuple[n.NameRef, ...]
    unknown_calls: tuple[n.Call, ...]
    card_literals: tuple[n.CardLiteral, ...]
    slot_leaks: tuple[_SlotLeak, ...]
    state_reads: frozenset[str]
    zone_reads: frozenset[str]


def _library_reach(library: n.Library) -> _LibraryReach:
    """Classify every definition in `library` against the library alone.

    The namespaces are what `_categories` would build for a game whose entire
    state is the contract and which has nothing else — deliberately narrower
    than any real game's:

    - `zones` is empty because a library declares no zones (decisions.md
      "Family libraries": a move touching a game-specific zone stays
      game-local, which is why the contract is state-only);
    - `ranks`/`suits`/`enums` are what the unknown-deck branch of `_categories`
      leaves, because a library is deck-agnostic. `hearts` means nothing until
      an including game names a deck, and Kuhn's has none.

    `_Categories` is frozen with every field required, so a namespace added to
    it is a mypy error here rather than a silently permissive hole.

    A name held on a node as a plain `str` is invisible to that classification —
    `_rewrite` classifies `NameRef`s, and nothing else. Those slots are swept
    SEPARATELY and from the registry (`_slot_leaks`), never by a hand-list
    beside it: `card_literals` and `unknown_calls` below are derived from that
    sweep rather than collected alongside it, because a table that lands next to
    the list it replaces leaves the drift exactly where it was."""
    provided_state = library.state.decls if library.state is not None else ()
    cats = _Categories(
        locals=frozenset(),
        # Both halves of the library's state surface: what it contracts for and
        # what it owns. A definition may reach either — the contract is
        # sufficient for the library's own variables trivially, since it declares
        # them itself.
        state_vars=frozenset(
            r.name for r in library.requires if not is_zone_contract(r)
        )
        | frozenset(d.name for d in provided_state),
        # The OTHER of the two name sets a library is checked against. It is
        # computed here and in `_library_slot_names` from different inputs, so a
        # zone contract fed to one and not the other would leave half the sweep
        # blind — which is the shape of the defect the slot registry exists for.
        zones=frozenset(r.name for r in library.requires if is_zone_contract(r)),
        enums=SEAT_DIRECTION_VALUES,
        functions=VALUE_NAMES,
        ranks=frozenset(),
        suits=frozenset(),
    )
    # `_rewrite` both classifies and reports, and its report ("unresolved name
    # 'x'") is the GAME's author — the wrong one here — so the bag is thrown
    # away and the classified TREE is read instead. Reading `ref_kind` is the
    # sanctioned use of what this pass stamps (see the module Contract), not a
    # re-derivation: which names a body binds, and where, stays the property of
    # `_introduced_binders` and `_BINDER_SCOPE_FIELDS` alone.
    discarded = DiagnosticBag()
    classified: list[object] = []
    for field, _ in _LIBRARY_DEF_KINDS:
        value = getattr(library, field)
        if field == "types":
            # `_rewrite` returns a `TypeDef` untouched — a derived body reads
            # sibling fields by bare name and needs them scoped in. Split
            # exactly as `_classify_names` splits it, for the same reason.
            classified.extend(_classify_type_derived(t, cats, discarded) for t in value)
        else:
            classified.append(_rewrite_value(value, cats, discarded))
    # A provided variable's DEFAULT is an expression like any other, so it can
    # leak like any other — `limit : Integer = house_rule` would reach past the
    # contract into the game exactly as a move-type effect would.
    classified.append(_rewrite_value(provided_state, cats, discarded))

    unresolved: list[n.NameRef] = []
    state_reads: set[str] = set()
    zone_reads: set[str] = set()
    for node in _child_nodes(tuple(classified)):
        if isinstance(node, n.NameRef):
            if node.ref_kind is None:
                unresolved.append(node)
            elif node.ref_kind == "state_var":
                state_reads.add(node.name)
            elif node.ref_kind == "zone":
                zone_reads.add(node.name)

    # The bare-string half, over the WHOLE library rather than the classified
    # definitions: `requires` has no expression to classify but its type names
    # are references like any other, so a contract can name a type only the
    # importing game defines.
    leaks, slot_reads, slot_zone_reads = _slot_leaks(library)
    # Two namespaces keep a message of their own, so they are lifted out of the
    # generic list rather than reported twice: a card literal says why a family
    # library is deck-agnostic, and an unknown call says a library may not reach
    # into the game that imports it. Both are now FOUND by the registry — only
    # their wording is special.
    cards = tuple(
        dict.fromkeys(
            leak.node
            for leak in leaks
            if isinstance(leak.node, n.CardLiteral)
        )
    )
    calls = tuple(
        leak.node for leak in leaks if isinstance(leak.node, n.Call) and leak.namespace == "function"
    )
    rest = tuple(leak for leak in leaks if leak.node not in cards and leak.node not in calls)
    return _LibraryReach(
        unresolved=tuple(unresolved),
        unknown_calls=calls,
        card_literals=cards,
        slot_leaks=rest,
        state_reads=frozenset(state_reads) | slot_reads,
        zone_reads=frozenset(zone_reads) | slot_zone_reads,
    )


_NAMESPACE_NOUN: dict[str, str] = {
    "state": "state variable",
    "zone": "zone",
    "phase": "phase",
    "mode": "mode",
    "type": "type",
    "move_type": "move type",
    "define": "define",
    "procedure": "procedure",
    "position": "position domain",
    "enum_value": "direction value",
    "zone_type_arg": "zone owner",
    "index_domain": "index domain",
}

# What a library may hold of each namespace, said in the second person, for the
# advice half of the diagnostic. The three empty namespaces get the design's
# reason rather than "define one": a library CANNOT declare a zone, a phase or a
# position domain, so "declare it here" would be advice its author cannot take.
_NAMESPACE_ADVICE: dict[str, str] = {
    "state": "name it in the `requires` contract and let the including game declare it",
    # A library reaches exactly the zones its contract names — the same shape as
    # state, and for the same reason: the game owns the declaration, the library
    # names what it needs.
    "zone": (
        "name it in the `requires` contract and let the including game declare "
        "it in `zones { }`"
    ),
    "phase": (
        "a library holds no phases, and the phase sequence is the including game's — "
        "keep the definition that needs it in the game"
    ),
    "mode": (
        "a library holds no modes: a mode is a condition of one of the including "
        "game's phases — keep the definition that needs it in the game"
    ),
    "type": (
        "declare the type in the library, or keep this definition in the game "
        "(a `requires` entry's type is a state type or a kernel zone type)"
    ),
    "move_type": "define the move type in the library, or keep this definition in the game",
    "define": "define it in the library, or keep this definition in the game",
    "procedure": "define the procedure in the library, or keep this definition in the game",
    "position": (
        "a library declares no position domains — keep the definition that needs it "
        "in the game"
    ),
    # The `<owner>` of a zone contract. A position domain is the game's alone, so
    # a position-indexed zone family cannot be contracted at all — the advice
    # says which owners ARE nameable rather than sending the author to declare
    # something a library has no clause for.
    "zone_type_arg": (
        "a zone contract's owner may only be a seat or a team ('player', "
        "'team') — a position domain is declared by the game and a library "
        "cannot name one, so keep the definition that needs it in the game"
    ),
    # Same reason, one slot over: the index of anything a library declares or
    # contracts for. A position domain exists only once a game declares it.
    "index_domain": (
        "a library indexes by a seat or a team ('player', 'team') — a position "
        "domain is declared by the game and a library cannot name one, so keep "
        "the definition that needs it in the game"
    ),
    # Likewise: `rotate … through [ … ]` takes a list of literal names, not
    # expressions, so a parameter can never stand in one of those slots.
    "enum_value": (
        "a family library is deck-agnostic, so only the direction values mean anything "
        "here — and `rotate` takes literal names rather than expressions, so a "
        "parameter cannot stand in for one: keep the definition that needs it in the game"
    ),
}


def _check_library_encapsulation(library: n.Library, bag: DiagnosticBag) -> None:
    """Every name a library's definitions reach must be in its `requires`
    contract, its own definitions, the stdlib, or the pronouns and binders any
    body has anyway.

    This is what makes the contract sufficient rather than advisory for that
    class of reference, and it is a property of the library alone — so it is
    checked against the library alone, never against the game that happens to be
    importing it. Without it a body reading past its contract resolves against a
    game that happens to declare the extra name and fails against a game meeting
    the contract in full, with an unresolved-name error pointing inside library
    text the game's author never wrote. That is the exact misaddressed failure
    `_check_requires` exists to prevent, arriving through the back door.

    The class is bounded by the reference-slot registry rather than by which
    slots anyone remembered: a name reaching a namespace `_library_slot_names`
    covers is refused, and every remaining namespace carries its reason in
    `_LIBRARY_UNSWEPT`. That is the property this Owner Guard can be read as proving —
    it is no longer "everything the classifier happens to see".

    Reported to the LIBRARY's author: the span is in the library file, because
    the library author is the only one who can fix it. The importing game's one
    available "fix" — declaring the extra name — is the accident that hid the
    leak in the first place."""
    reach = _library_reach(library)
    for ref in reach.unresolved:
        bag.error(
            f"library '{library.name}' reads '{ref.name}', which is neither in "
            f"its `requires` contract nor defined in the library — add it to "
            f"`requires {{ }}` if the including game must declare it, or move "
            f"the definition that needs it into the game",
            ref.span,
        )
    for call in reach.unknown_calls:
        bag.error(
            f"library '{library.name}' calls '{call.func}', which is neither "
            f"defined in the library nor a native function — a library's "
            f"definitions may not reach into the game that imports them",
            call.span,
        )
    for card in reach.card_literals:
        bag.error(
            f"library '{library.name}' names the card `{card.rank} of "
            f"{card.suit}`, but a family library is deck-agnostic — its members "
            f"do not share a deck, and Kuhn's holds three cards. Take the card "
            f"as a parameter, or keep the definition that needs it in the game",
            card.span,
        )
    for leak in reach.slot_leaks:
        bag.error(
            f"library '{library.name}' names the "
            f"{_NAMESPACE_NOUN[leak.namespace]} '{leak.name}', which the library "
            f"does not have — it would resolve against whichever game imports "
            f"this, so the library is not self-contained: "
            f"{_NAMESPACE_ADVICE[leak.namespace]}",
            getattr(leak.node, "span", None),
        )
    # A PROVIDED default reaching the contract is in scope for the general
    # declare-order Owner Guard too (`_check_state_default_scope`), which would refuse
    # it after the splice with a span in this same file. It is caught here as
    # well, and first, because the splice destroys the distinction the library
    # author needs: post-splice a required name is just a state variable
    # declared later, so the general Owner Guard's advice — declare it earlier — is
    # advice they cannot take. Only the game can declare required state, and it
    # always lands after the library's own.
    required = {r.name for r in library.requires}
    provided = library.state.decls if library.state is not None else ()
    for decl in provided:
        for node in _walk(decl.default):
            # Matched by name, not by `ref_kind`: these decls are the raw ones,
            # classified only inside `_library_reach`. A binder inside a default
            # shadowing a required name would be refused too — conservative, and
            # unreachable from a default worth writing.
            if isinstance(node, n.NameRef) and node.name in required:
                bag.error(
                    f"library '{library.name}' initialises provided state "
                    f"'{decl.name}' from '{node.name}', which its `requires` "
                    f"contract asks the game to declare — so '{node.name}' does "
                    f"not exist yet when this default runs: provided state is "
                    f"declared before the game's own, never after. Give "
                    f"'{decl.name}' a literal default and set it from "
                    f"'{node.name}' in a phase",
                    node.span or decl.span,
                )


def _spelled_contract(want: n.RequireDecl) -> str:
    """A `requires` entry as its author wrote it, for a diagnostic to quote."""
    index = f"[{want.index}]" if want.index else ""
    args = f"<{', '.join(a.name for a in want.type_args)}>" if want.type_args else ""
    return f"{want.name}{index} : {want.type_name}{args}{'?' if want.optional else ''}"


def _check_contract_shapes(library: n.Library, bag: DiagnosticBag) -> None:
    """Every `requires` entry names a shape SOME game could declare — checked
    against the library alone, before any game is consulted.

    Without this the crossed spellings would surface as "your game does not
    declare it", which is advice no game can take: `x : Hand` names an owned
    zone type with no owner, and no `zones { }` line the author could write
    would answer it. A contract that cannot be met is the library author's bug,
    so it is reported to the library's author, like every other
    library-alone property (decisions.md "Family libraries").

    The zone SHAPE rules are `_resolve_zone`'s, which owns that class for the
    game's own declarations. This is a SECOND implementation of them, not a call
    into the first, and deliberately: the two report to different authors (a
    library's own file, against the library alone; a game's declaration, while
    resolving it) and run at different times, so sharing a body would mean
    threading an author through it. This copy is the Owner Guard of its own
    class, not a Shadow Guard of `_resolve_zone`'s: a library author can write
    `x : Hand` with no game in sight, `_resolve_zone` never runs on that path,
    and so nothing else can decide the case (decisions.md "Closed-domain
    completeness", write-time triage). Duplication is not a shadow relation —
    the two are pinned EQUAL over the whole registry by
    `tests/test_family_libraries.py`'s
    `test_a_contract_shape_is_refused_exactly_when_the_declaration_would_be` —
    a contract admitting a shape a `zones { }` line refuses would be a contract
    no game could meet.

    One asymmetry, by exclusion: `_resolve_zone` also refuses a position-indexed
    family whose type has distinct owner/others projections. A contract cannot
    be position-indexed at all (`index_domain` is swept to the roles), so the
    case does not arise here."""
    for want in library.requires:
        spelled = _spelled_contract(want)
        if not is_zone_contract(want):
            if want.type_args:
                bag.error(
                    f"library '{library.name}' requires `{spelled}`, but "
                    f"'{want.type_name}' is a state type and takes no type "
                    f"argument — the `<…>` form belongs to zone types",
                    want.span,
                )
            continue
        if want.optional:
            bag.error(
                f"library '{library.name}' requires `{spelled}`, but "
                f"'{want.type_name}' is a zone type and a zone has no nullable "
                f"form — drop the `?`",
                want.span,
            )
        takes_owner = LIBRARY_ZONE_TYPES[want.type_name]
        if takes_owner and len(want.type_args) != 1:
            bag.error(
                f"library '{library.name}' requires `{spelled}`, but zone type "
                f"'{want.type_name}' takes one owner argument, got "
                f"{len(want.type_args)}",
                want.span,
            )
        elif not takes_owner and want.type_args:
            bag.error(
                f"library '{library.name}' requires `{spelled}`, but zone type "
                f"'{want.type_name}' takes no type arguments",
                want.span,
            )
        for arg in want.type_args:
            if want.index is None:
                bag.error(
                    f"library '{library.name}' requires `{spelled}`, an owned "
                    f"zone type with no index — the runtime keys a zone family "
                    f"by its index, so the owner would be silently ignored; "
                    f"write `{want.name}[{arg.name}] : {want.type_name}"
                    f"<{arg.name}>`",
                    want.span,
                )
            elif arg.name != want.index:
                bag.error(
                    f"library '{library.name}' requires `{spelled}`, whose "
                    f"owner argument names a different domain than its index — "
                    f"write `{want.type_name}<{want.index}>`",
                    want.span,
                )


def _check_zone_requirement(
    game: n.Game,
    use: n.UsesDecl,
    library: n.Library,
    want: n.RequireDecl,
    zoned: dict[str, list[n.ZoneDecl]],
    bag: DiagnosticBag,
) -> None:
    """The zone leg of the contract: the game declares this zone, in its
    `zones { }` block, at the library's index and type.

    The same "exactly one declaration" rule as the state leg, and for a weaker
    reason: `zones { }` is a game-level block with no phase-local form, so a
    second declaration is already a duplicate (`_check_duplicate_names`). The
    count is still checked here so the contract's guarantee does not depend on
    another Owner Guard's coverage.

    Reported on the game's `uses` line, to the game's author — the shape
    questions the LIBRARY could get wrong are `_check_contract_shapes`', and
    ran before any game was consulted."""
    spelled = _spelled_contract(want)
    found = zoned.get(want.name, [])
    if not found:
        # The near-miss worth naming: a game that declared the name as STATE has
        # not simply forgotten it, and telling it to add a zone without saying
        # why would read as the checker missing the declaration in front of it.
        as_state = any(
            decl.name == want.name
            for node in _walk(game)
            if isinstance(node, n.StateBlock)
            for decl in node.decls
        )
        if as_state:
            bag.error(
                f"library '{library.name}' requires zone `{spelled}`, which "
                f"game '{game.name}' declares as state — '{want.type_name}' is "
                f"a zone type, so the declaration belongs in `zones {{ }}`",
                use.span,
            )
        else:
            bag.error(
                f"library '{library.name}' requires zone `{spelled}`, which "
                f"game '{game.name}' does not declare — add it to the game's "
                f"`zones {{ }}` block",
                use.span,
            )
        return
    if len(found) > 1:
        bag.error(
            f"library '{library.name}' requires zone `{spelled}`, which game "
            f"'{game.name}' declares {len(found)} times — a requirement must "
            f"name ONE declaration",
            use.span,
        )
        return
    have = found[0]
    if have.index != want.index:
        shown_index = f"'{have.index}'" if have.index else "nothing"
        bag.error(
            f"library '{library.name}' requires zone `{spelled}`, but game "
            f"'{game.name}' declares it indexed by {shown_index}",
            use.span,
        )
    wanted_args = tuple(a.name for a in want.type_args)
    have_args = tuple(a.name for a in have.type_ref.args)
    if (have.type_ref.name, have_args) != (want.type_name, wanted_args):
        shown = have.type_ref.name + (
            f"<{', '.join(have_args)}>" if have_args else ""
        )
        bag.error(
            f"library '{library.name}' requires zone `{spelled}`, but game "
            f"'{game.name}' declares it as `{shown}` — a zone type fixes the "
            f"per-observer projection, so the contract names the type the "
            f"library's definitions were written against",
            use.span,
        )


def _check_require_indexes(library: n.Library, bag: DiagnosticBag) -> None:
    """The index of any state a library WRITES — required or provided — must be a
    role a state variable can be indexed by.

    Provided state is here for the same reason a requirement is, and the class is
    "a declaration a library authored", not "a requirement": a provided
    `flag[hearts]` splices into the game and is refused post-splice at a span in
    the library's file, which reads as the library being blamed by a pass that
    never saw it. Caught here instead, before any game is consulted.

    Reported to the LIBRARY's author, unlike every other `requires` failure,
    and the difference is who can fix it: an unmet contract is a fact about the
    importing GAME (it did not declare what the library asked for), while an
    index naming no indexable role is wrong in the library's own text, and no
    game can answer it.

    Without this the name was never checked at all. `requires { q[hearts] :
    Integer }` reached `_check_requires`, which compares the requirement's
    index against the declaration's and reports a SHAPE mismatch — so the
    library's typo was echoed back as though `hearts` were a role the game had
    failed to use, in a sentence whose two halves both read "per-player". The
    game side of the same class already had an Owner Guard (a
    `state { x[hearts] }` is refused); this is its library twin.

    Does NOT honour `_check_requires`'s `skip` set, deliberately. `skip`
    suppresses a SECOND report of one defect — a name already ruled on as
    provided or contested would otherwise also be reported as undeclared,
    advice pointing away from the real mistake. A malformed index is an
    independent defect in a different file: the collision is the game's to
    resolve, the index is the library's, and silencing one because of the
    other would leave the library author with nothing to act on."""
    provided = library.state.decls if library.state is not None else ()
    for decl, verb in [(w, "requires") for w in library.requires] + [
        (d, "provides") for d in provided
    ]:
        if decl.index is None or role_of(decl.index) in ZONE_INDEX_ROLES:
            continue
        roles = ", ".join(role_names(ZONE_INDEX_ROLES))
        bag.error(
            f"library '{library.name}' {verb} state '{decl.name}' indexed by "
            f"'{decl.index}', which is not an indexable role ({roles}) — a "
            f"library indexes by a seat or a team, and a game may not declare "
            f"that index either",
            decl.span,
        )


def _check_requires(
    game: n.Game,
    use: n.UsesDecl,
    library: n.Library,
    bag: DiagnosticBag,
    skip: frozenset[str] = frozenset(),
) -> None:
    """Check a library's `requires` contract against the game's declarations.

    An entry names state or a zone, and its type says which (`is_zone_contract`).
    The zone leg is `_check_zone_requirement`; what follows is the state one.

    `skip` names the state `_check_state_claims` has already ruled on — provided
    names and contested ones. Without it a name claimed both ways would fail
    twice, and the second failure ("the game does not declare it") would be
    advice pointing away from the real defect.

    Reported on the game's `uses` line, to the game's author: the author wrote
    that line, and an undeclared-name error surfacing from inside spliced library
    text would name symbols they never typed.

    What is checked is that EXACTLY ONE declaration of the name exists somewhere
    in the game, at the library's arity and type. Which `state { }` block holds
    it is not checked, and deliberately so: a phase's state block is the natural
    home for state that resets on phase re-entry, which is exactly what per-hand
    betting state is, and Stud declares all seven of `poker_betting`'s
    requirements inside `phase play`. A ZONE requirement has no such freedom to
    misuse: `zones { }` is game-level only, so `_check_zone_requirement` looks in
    exactly one place.

    That is weaker than "the library's definitions can read it where they run",
    and the gap is real rather than theoretical: move Kuhn's `limit` into `phase
    deal` while the imported `bet` runs in `phase betting`, and this check passes,
    typecheck passes, and the playout dies on a bare KeyError from
    `runtime/state.py`. The gap is NOT the import tier's — a plain game with no
    library reproduces it, one phase declaring what another reads — so closing it
    means use-site scope reachability for state generally, which this contract
    cannot stand in for. Recorded as a residual in issue #138, and in the ledger of
    tests/test_family_libraries.py. Narrowing the contract to game-level
    declarations would not close it either, and would reject Stud.

    Exactly one, and the count is the Owner Guard — not a tie broken by declaration
    order. Cross-block shadowing is legal in general (`_check_duplicate_names`),
    but the two shadowed declarations are answers to different questions and no
    fixed bias picks correctly: a shadow in the phase where the library's
    definitions run makes last-wins right, a shadow in some other phase makes
    first-wins right. This function used to take the first while `typecheck` and
    `runtime/driver.py` took the last, so a game could satisfy the contract on
    one declaration and bind the other. Refusing the shadow outright is the only
    answer that does not depend on a scope question the contract cannot see; it
    costs a `requires`d name nothing, because that name is the library's
    interface rather than game-private state (decisions.md "Family libraries" —
    the same reason the metamorphic rename transform excludes it)."""
    declared: dict[str, list[n.StateDecl]] = {}
    for node in _walk(game):
        if isinstance(node, n.StateBlock):
            for decl in node.decls:
                declared.setdefault(decl.name, []).append(decl)
    zoned: dict[str, list[n.ZoneDecl]] = {}
    for zone in game.zones:
        zoned.setdefault(zone.name, []).append(zone)
    # Requirements already reported as malformed in the LIBRARY's own text.
    # Comparing one against the game's declaration derives a second error that
    # is worse than useless: it renders the malformation as a MISMATCH, so a
    # non-role index prints as "a scalar" and an unresolvable type prints as
    # the game's type being wrong — blaming the game author for a defect in a
    # file they did not write, and, when the name is undeclared, advising them
    # to add a declaration the language would refuse.
    #
    # Matched by SPAN rather than by re-deriving which requirements are
    # well-formed. That is what makes this complete over the class rather than
    # over the two members known today: a requirement is malformed exactly when
    # some Owner Guard has already reported against its own span, so a future
    # Owner Guard on a new `RequireDecl` field is covered the day it lands,
    # with nothing to remember here. Both malformation Owner Guards run before
    # this pass, in `_apply_uses`'s loop, and report at the requirement's span
    # (`_check_require_indexes` for the index, `_check_library_encapsulation`
    # for the type name).
    #
    # This is the opposite direction from `skip`, which suppresses a downstream
    # report about a name the GAME's own claims already ruled on.
    malformed = {d.span for d in bag.items if d.span is not None}
    for want in library.requires:
        # Span-keyed, so it speaks about BOTH legs and is hoisted above the
        # split: a malformed zone contract would otherwise get its shape error
        # in the library AND a mismatch pinned on the game, which is the second
        # report this suppression exists to prevent.
        if want.span is not None and want.span in malformed:
            continue
        if is_zone_contract(want):
            # `skip` is the STATE-claim set (`_check_state_claims`), so it never
            # speaks about a zone name — reading it here would silently drop a
            # zone contract whenever the game happened to declare a state
            # variable of the same name.
            _check_zone_requirement(game, use, library, want, zoned, bag)
            continue
        if want.name in skip:
            continue
        found = declared.get(want.name, [])
        wanted = f"{want.name}{f'[{want.index}]' if want.index else ''}"
        spelled = f"{wanted} : {want.type_name}{'?' if want.optional else ''}"
        if not found:
            bag.error(
                f"library '{library.name}' requires state `{spelled}`, which "
                f"game '{game.name}' does not declare — add it to the game's "
                f"`state {{ }}` block with the initial value the game wants",
                use.span,
            )
            continue
        if len(found) > 1:
            bag.error(
                f"library '{library.name}' requires state `{spelled}`, which "
                f"game '{game.name}' declares {len(found)} times — a requirement "
                f"must name ONE declaration, or which one the library's "
                f"definitions read depends on where they run; keep a single "
                f"declaration of '{want.name}'",
                use.span,
            )
            continue
        have = found[0]
        if have.index != want.index:
            # Rendered from the ROLE, not from the truthiness of the field: the
            # index is a member of a closed domain, and collapsing it to a
            # boolean printed "to be per-player, but … declares it as
            # per-player" for a `[team]`-against-`[player]` mismatch — the two
            # roles Bridge and Belote both use (issue #144). Both sides are
            # classified rather than assumed: `_check_require_indexes` has
            # already refused a requirement whose index names no role, and
            # resolve's state-index Owner Guard the declaration's.
            got = index_phrase(role_of(have.index) if have.index else None)
            need = index_phrase(role_of(want.index) if want.index else None)
            bag.error(
                f"library '{library.name}' requires state `{spelled}` to be "
                f"{need}, but game '{game.name}' declares it as {got}",
                use.span,
            )
        if (have.type_name, have.optional) != (want.type_name, want.optional):
            bag.error(
                f"library '{library.name}' requires state `{spelled}`, but game "
                f"'{game.name}' declares it as "
                f"`{have.type_name}{'?' if have.optional else ''}`",
                use.span,
            )


def resolve(game: n.Game) -> n.Game:
    bag = DiagnosticBag()
    # First: `uses` splices each named library's definitions in, so everything
    # below sees one flat game. Errors here (unknown library, a collision, an
    # unmet `requires`) make the spliced game unrepresentative, so they are
    # reported as a complete set and raised before the rest of the pass adds
    # noise derived from a half-assembled game.
    game = _apply_uses(game, bag)
    _raise_if_errors(bag)
    _resolve_component_set(game, bag)
    _reject_card_content_clauses(game, bag)
    _resolve_direction(game, bag)
    game = _expand_ranking(game, bag)
    _resolve_ranking(game, bag)
    _resolve_card_points(game, bag)
    # Before `_resolve_trump`, which returns early on a block game: R1 owns the
    # game-clause-beside-a-block cell, so the two never co-report on it.
    _check_trick_order_partition(game, bag)
    _resolve_trump(game, bag)
    _check_duplicate_names(game, bag)
    _check_zone_type_names_are_not_taken(game, bag)
    _check_reserved_params(game, bag)
    _check_reserved_binders(game, bag)
    _resolve_max_length(game, bag)
    _check_teams(game, bag)
    position_names = _resolve_positions(game, bag)
    # The board mints its `cell` domain into `game.positions` (after the
    # declared positions are validated, so the collision Owner Guard reads the
    # pre-injection names); from here `game.positions` is the union and
    # `position_names` names both kinds for the zone-index and move-parameter
    # checks below.
    game = _resolve_board(game, bag, position_names)
    position_names = frozenset(p.name for p in game.positions)
    # AFTER the board has minted its `cell` domain, because an entry's type
    # slot may spell any of the game's position domains and `_resolve_board` is
    # the one site that adds one. Validating earlier refused a name the rest of
    # the pipeline accepts — the signature builder maps the resolved
    # named-member position to `TCell`. Still before `_validate_refs`, which
    # resolves calls against the namespace the block defines: a game whose
    # block is wrong should hear about the block rather than about every call
    # that then fails to resolve.
    _check_primitives_block(game, bag)
    for zone in game.zones:
        _resolve_zone(zone, bag, position_names)

    # Names that resolve to SOME rule template (local or library), independent
    # of whether that template ever successfully instantiates — the set
    # `active_rules names undefined rule` gates on below. Captured from the
    # ORIGINAL `game.rules` (before instantiation, which drops a local
    # template that fails to instantiate): a name is "undefined" only when no
    # template exists for it anywhere, never merely because its own
    # instantiation attempt hit some OTHER, already-separately-reported
    # mismatch (arity, missing arguments, …) — that conflation would pile a
    # spurious "undefined rule" note onto every such mismatch.
    known_rule_names = {r.name for r in game.rules} | set(stdlib_rules())

    # Library-rule splice and template instantiation: after this, every rule in
    # `game.rules` is a concrete (parameter-free) definition the runtime can
    # index by name.
    game = _instantiate_rules(game, bag)

    for rule in game.rules:
        _resolve_rule(rule, bag)
    _resolve_phase_level(game.phases, known_rule_names, bag)
    _check_rule_removes(game.phases, bag)

    # DomainQuery nouns validate BEFORE deep name resolution: a typo'd noun
    # (`any cel where square[cell] …`) changes the binder name, so the body's
    # `cell` reference would classify as unresolved first and mask the sharper
    # unknown-noun diagnostic (bag order is report order). After
    # `_instantiate_rules`, so instantiated rule bodies are covered too.
    for dq in _walk(game):
        if isinstance(dq, n.DomainQuery):
            _check_domain_query(dq, game, bag)

    # Deep name resolution: classify every bare name and validate calls,
    # card literals, and the rotate/winner targets.
    cats = _categories(game)
    game = _classify_names(game, cats, bag)
    _validate_refs(game, cats, bag)
    _check_position_family_refs(game, bag, position_names)
    _check_declared_type_names(game, bag)
    _check_state_default_scope(game, bag)
    _check_state_scope(game, bag)
    _check_functions(game, bag)
    # After `_check_functions`: the row walk reuses its call map and `_reaches`
    # to follow a row's reach through the designer functions.
    _check_trick_order_rows(game, bag)
    # After `_classify_names`: both read the `ref_kind` the classifier stamped,
    # rather than re-deriving what is or is not a zone reference.
    _check_arrival_record_pile_args(game, bag)
    _check_procedures(game, bag)
    _check_chooses(game, bag)
    _check_actor_alias_comparisons(game, bag)
    _check_delegation(game, bag)
    _check_winner_target(game, bag)
    # Last, so a fixture missing its result clause still surfaces the
    # sharper diagnostic it was aimed at first (bag order is report order).
    _resolve_winner_loser(game, bag)

    _raise_if_errors(bag)
    return game


# The Node union's members, for the runtime gate below. `get_args` reads the
# union itself, and tests/test_node_registry.py pins that union to the module's
# actual dataclasses — so this tuple cannot silently miss a node kind.
_NODE_KINDS: tuple[type, ...] = get_args(n.Node)


def _introduced_binders(node: object, flavor: Flavor = "card") -> tuple[str, ...]:
    """The single registry of "which node kinds bind names, and which names":
    every other place that needs to know (`_template_binders`'s collision
    check, `_check_functions`'s allowed-reference set, `_rewrite`'s lexical
    scoping via `_BINDER_SCOPE_FIELDS`) reads this instead of re-enumerating
    the node-kind match itself — separate copies of that match would drift out
    of sync, the `Transfer`/`EpistemicOp` filter arm being especially easy to
    miss.

    `flavor` sets the ONE binder that varies with content kind — the
    movement/reveal filter candidate, `card` vs `piece` (`content_noun`); every
    other binder is user-chosen or a card-only construct's fixed name. The
    scoping site passes the game's flavor so `piece` resolves in a piece game's
    filter; the collision/reserved sweeps default `card` (the fixed nouns are
    never reserved and a movement can only occur where the game's own flavor
    already governs).

    Walks feed this every field value they meet, so non-node values (a `str`
    name, a `Span`, an `int`) answer "nothing" here; every actual node kind is
    dispatched exhaustively in `_node_binders`."""
    if not isinstance(node, _NODE_KINDS):
        return ()
    return _node_binders(cast(n.Node, node), flavor)


def _node_binders(node: n.Node, flavor: Flavor = "card") -> tuple[str, ...]:
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
    encounter, where the binder scopes within the walked tree itself.

    A movement/reveal filter binds the CONTENT noun (`card` for a card game,
    `piece` for a piece game — `content_noun`); the card-query and aggregation
    binders stay `card` because those forms are card-only (rejected in a piece
    game), so the noun they bind is fixed."""
    match node:
        case n.Comprehension() | n.Quantifier() | n.ForEach() | n.Turns() | n.DomainQuery():
            return (node.binder,)
        case n.EachSimultaneous():
            return (node.role,)
        case n.PlayerQuery():
            return ("player",)
        case n.CardQuery():
            return ("card",)
        case n.TrickOrderRow():
            # A Trick Order row's body is an expression over the implicit
            # `card` — the card-query and filter convention, in a clause
            # position. Card-only like the query binders: a piece game's
            # `trick_order` is refused outright
            # (`_reject_card_content_clauses`), so the noun is fixed.
            return ("card",)
        case n.Transfer() if node.where is not None:
            # `where jointly` binds the candidate SET; a per-card `where`
            # binds each candidate (decisions.md "Joint-predicate selection").
            return (content_noun(flavor, plural=node.joint),)
        case n.EpistemicOp() if node.where is not None:
            return (content_noun(flavor, plural=False),)
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
        # A filter-less Transfer/EpistemicOp falls through its guarded arm above:
        # no candidate set, so no `card` binder.
        case n.Transfer() | n.EpistemicOp():
            return ()
        # Declarations and game/phase structure. (The parameter-bearing ones are
        # covered by `_rewrite` + `_check_reserved_params` — see the docstring.)
        case (
            n.Game() | n.PlayersSpec() | n.Winner() | n.Loser()
            # The import trio binds nothing: `uses` and `requires` name state and
            # definitions that already live in flat, game-wide namespaces, and a
            # `Library` is gone by the end of `_apply_uses` — its definitions are
            # spliced into the Game and reached through the arms below.
            | n.Library() | n.UsesDecl() | n.RequireDecl()
            | n.MoveTypeDef() | n.Parameter() | n.RuleDef() | n.RuleRef()
            # A `primitives { }` entry's parameters name the arguments its
            # Python receives and key its `reads` binders; no DSL body is
            # scoped by them, so the entry introduces no name into any scope
            # (`_check_reserved_params` covers them via `_PARAM_BEARING`).
            | n.PrimitivesBlock() | n.PrimitiveDecl() | n.PrimitiveRead()
            | n.AppliesWhen() | n.Demands()
            | n.DefineDef() | n.FunctionDef() | n.ProcedureDef()
            | n.OutcomeCase() | n.StructField() | n.DerivedField()
            | n.ZoneDecl() | n.TypeRef() | n.TypeArg()
            | n.CardPointsTable() | n.CardPointsEntry()
            | n.StateBlock() | n.StateDecl() | n.PositionDecl() | n.BoardDecl()
            | n.Phase() | n.PhaseQualifier() | n.BeforeEach() | n.AfterEach()
            | n.ActiveRules() | n.LegalMoves() | n.Mode() | n.TransitionTo() | n.MoveEvent()
        ):
            # `StateDecl` in particular: state variables are a flat, game-wide
            # declaration namespace (`_categories`'s `state_vars`), not a binder
            # any construct introduces.
            return ()
        # Statements that bind nothing. `AsBlock` rebinds the ACTING player, not a
        # named binder — its player is an expression, not a NAME — so it introduces
        # no name into scope; its body is an ordinary block (see `_BINDER_SCOPE_FIELDS`).
        case (
            n.RotateStmt() | n.RepeatUntil() | n.IfStmt() | n.AsBlock() | n.AssignStmt()
            | n.Offer() | n.TrickRound() | n.AuctionRound() | n.ClimbRound()
            | n.Produce() | n.Produces()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt() | n.Block()
        ):
            return ()
        # Expressions that bind nothing.
        case (
            n.NameRef() | n.IntLit() | n.StrLit() | n.ListLit() | n.CardLiteral()
            | n.AllPlayers() | n.Member() | n.Subscript() | n.FieldInit()
            | n.StructLit() | n.Call() | n.NamedArg() | n.BinOp() | n.Not()
            | n.IsCheck() | n.IfExpr() | n.Choose()
            # The block itself binds nothing: each ROW binds `card` over its
            # own body (above).
            | n.TrickOrder()
        ):
            return ()
        case _:
            assert_never(node)


def _template_binders(rule: n.RuleDef, flavor: Flavor) -> set[str]:
    """Every binder a rule body introduces — a parameter sharing one of these
    names would be captured by the binder instead of substituted. A rule body
    can hold a movement, so its filter binder follows the game's flavor."""
    out: set[str] = set()
    for nd in _walk(rule):
        out.update(_introduced_binders(nd, flavor))
    return out


def _check_template(rule: n.RuleDef, bag: DiagnosticBag, flavor: Flavor) -> bool:
    """Validate a parameterized rule's declaration (Suit-only domains,
    corpus-first — recorded in roadmap.md, "Grammar surface deferred by the
    checker"; unique names; no binder capture).
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
    binders = _template_binders(rule, flavor)
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
    `_check_rule_removes`, since `compute_active_rules` only ever
    removes a name it finds already present); `override` has no runtime
    support yet at all and is rejected unconditionally, once, by
    `_resolve_phase_item` — this loop skips it so that is the only diagnostic
    a game ever sees for it, not a second, unsatisfiable "pass arguments"
    alongside "not yet supported"."""
    lib = stdlib_rules()
    local = {r.name: r for r in game.rules}
    for r in game.rules:
        if r.name in lib:
            bag.error(
                f"rule '{r.name}' shadows the standard-library rule of the same "
                f"name — delete the local definition (`active_rules` resolves it "
                f"from the library), or rename it if the body genuinely differs",
                r.span,
            )
    suits = suit_names(game.deck) if _deck_known(game.deck) else None
    # rule name -> (argument key, concrete instance)
    instances: dict[str, tuple[tuple[str, ...], n.RuleDef]] = {}
    lib_order: list[str] = []
    # Each DISTINCT template's declaration validates once total, however many
    # refs instantiate it (or attempt to) — never once per activating phase
    # (without the cache, a defective template referenced from two phases would
    # repeat its diagnostics; `_check_template` is also the bottom loop's
    # "never instantiated" fallback below, so the cache spans both call sites).
    template_checked: dict[str, bool] = {}

    def check_template_once(name: str, template: n.RuleDef) -> bool:
        if name not in template_checked:
            template_checked[name] = _check_template(template, bag, game.content_flavor)
        return template_checked[name]

    for nd in _walk(game):
        if not isinstance(nd, n.ActiveRules):
            continue
        for ref in nd.refs:
            if ref.delta in ("remove", "override"):
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


def _check_rule_removes(phases: tuple[n.Phase, ...], bag: DiagnosticBag) -> None:
    """`-X` remove reachability, over a phase and its modes.

    `-X` and (unsupported today) `override X` can never instantiate a rule
    (`_instantiate_rules`'s docstring) — they only resolve X by NAME against a
    rule a `plain`/`add` reference already activated. A reference to a name no
    `plain`/`add` ever activates in the scope the runtime actually consults is
    a structural no-op forever: `runtime/active_rules.py`'s `compute_active_rules`
    computes one phase's active set from exactly two sources — that phase's
    OWN `active_rules:` entries (applied unconditionally, in the list's own
    order), and, layered on top, each of its currently-active MODES. This check
    mirrors that exact two-source shape: a `remove` inside a phase's own list
    validates against that same list; a `remove` inside a mode validates
    against its phase's list UNION its own.

    It deliberately does NOT widen the scope to sibling modes. Modes are
    independent conditions, so two of them may hold at once and one's `+X`
    genuinely can be live while another's `-X` runs — but only in orders no
    declaration site fixes, so a `-X` that depends on a sibling is a race the
    designer cannot read off the page. It also does not model order WITHIN one
    list (an add-then-remove of the same name earlier in a phase's own list
    still counts as "added" for a mode's cluster check) — an accepted
    imprecision for a construct the corpus does not use at all (issue #103
    records the residual)."""
    for phase in phases:
        own_refs = [
            ref for item in phase.items if isinstance(item, n.ActiveRules) for ref in item.refs
        ]
        own_added = {r.name for r in own_refs if r.delta in ("plain", "add")}
        _validate_removes(own_refs, own_added, bag)

        for mode in (i for i in phase.items if isinstance(i, n.Mode)):
            mode_refs = [ref for block in mode.active_rules for ref in block.refs]
            cluster_added = own_added | {r.name for r in mode_refs if r.delta in ("plain", "add")}
            _validate_removes(mode_refs, cluster_added, bag)

        children = tuple(i for i in phase.items if isinstance(i, n.Phase))
        _check_rule_removes(children, bag)


def _validate_removes(refs: list[n.RuleRef], added: set[str], bag: DiagnosticBag) -> None:
    for ref in refs:
        if ref.delta == "remove" and ref.name not in added:
            bag.error(
                f"`-{ref.name}` removes a rule that is never added in scope "
                f"here (this phase's own `active_rules:`, or one of its "
                f"mode's) — add `{ref.name}` or `+{ref.name}` "
                f"there, or delete this removal",
                ref.span,
            )


def _check_state_default_scope(game: n.Game, bag: DiagnosticBag) -> None:
    """A `state { }` default is evaluated while its own block is still being
    declared, so it may only reach state that exists by then: a name declared
    earlier in the SAME block, or one in an ENCLOSING block. `_categories`
    flattens every declaration into one game-wide `state_vars` set — right for
    the rest of the language, where state is read during play and all of it is
    live — but a default runs before its block is finished, and reading a name
    from later in the block, from a sibling phase, or from a phase nested inside
    this one dies at playout on `KeyError: variable '…' not in scope`.

    The scope model is the runtime's, mirrored rather than re-derived: `driver`
    pushes a frame per phase and pops it at phase end, and finds a phase's
    nested phases by scanning `items` for `n.Phase` — so an enclosing block's
    names are live and a sibling's are not.

    This is also where a family library's provided state lands. `_apply_uses`
    splices the provided decls in FRONT of the game's own, so a provided default
    reading one of the library's `requires` names reaches a variable the game
    declares strictly later — never in scope, whatever the game does. That
    subclass is refused before the splice, to the library's own author, by
    `_check_library_encapsulation`; this Owner Guard is what owns the general class,
    and would catch it here too if the library check were removed.

    Two constructs are refused outright rather than analysed, both because a
    default runs before the world a body assumes exists:

    - a `Call`, whose state reads live in a body `_walk` never enters from a
      default — so the choice is an interprocedural scope check or a ban, and no
      default in the corpus calls anything (decisions.md "State scoping
      (lexical)" records the narrowing; ledger tests/test_state_default_scope.py);
    - a `Choose`, which needs an acting player. A default is evaluated outside
      any turn, so the runtime raised "a `choose` with no acting player" at
      declare time; for the OpenSpiel target a decision with no actor also has
      no information set to attach to.

    The arms are three because the domain — `n.Expr` — was swept, not because
    three defects were reported: the `Choose` cell had no witness and was found
    by running every member of the union in default position (the grid in
    `tests/test_state_default_scope.py` carries the outcome per member)."""

    def declared(
        block: n.StateBlock | None, enclosing: frozenset[str]
    ) -> frozenset[str]:
        if block is None:
            return enclosing
        in_scope = enclosing
        for decl in block.decls:
            for node in _walk(decl.default):
                if isinstance(node, n.Choose):
                    bag.error(
                        f"the default of state variable '{decl.name}' cannot "
                        f"`choose`: a default is evaluated where it is written, "
                        f"outside any player's turn, so there is no one to make "
                        f"the decision — and a decision with no actor has no "
                        f"information set to attach to. Move it into a phase",
                        node.span or decl.span,
                    )
                elif isinstance(node, n.Call):
                    bag.error(
                        f"the default of state variable '{decl.name}' cannot "
                        f"call '{node.func}': a default is evaluated while the "
                        f"`state {{ }}` block is still being declared, and a "
                        f"function body can reach a variable that does not "
                        f"exist yet — use a literal here and compute the value "
                        f"in the phase that needs it",
                        node.span or decl.span,
                    )
                elif (
                    isinstance(node, n.NameRef)
                    and node.ref_kind == "state_var"
                    and node.name not in in_scope
                ):
                    bag.error(
                        f"the default of state variable '{decl.name}' reads "
                        f"'{node.name}', which is not declared yet: a default "
                        f"can only read state declared before it — earlier in "
                        f"the same `state {{ }}` block, or in an enclosing one",
                        node.span or decl.span,
                    )
            in_scope = in_scope | {decl.name}
        return in_scope

    def descend(phase: n.Phase, enclosing: frozenset[str]) -> None:
        block = next((i for i in phase.items if isinstance(i, n.StateBlock)), None)
        inner = declared(block, enclosing)
        for item in phase.items:
            if isinstance(item, n.Phase):
                descend(item, inner)

    top = declared(game.state, frozenset())
    for phase in game.phases:
        descend(phase, top)


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
#
# `types` is deliberately NOT here. A `derived { }` body has the same shape —
# evaluated lazily at member access, so it too has no single lexical phase —
# but NO corpus game declares one, so the conservative rule that is unavailable
# above is free here: a derived body may read game-level state only. It is
# walked with the rest.
_GAME_LEVEL_UNCHECKED = frozenset(
    {"rules", "move_types", "functions", "procedures", "defines"}
)

_GAME_LEVEL_SKIP = _GAME_LEVEL_OWNED_BY_ANOTHER_GUARD | _GAME_LEVEL_UNCHECKED


def _check_state_scope(game: n.Game, bag: DiagnosticBag) -> None:
    """A state reference names a variable live at its lexical position.

    decisions.md "State scoping (lexical)": a variable is scoped to the phase
    that lexically encloses its declaration, reads from enclosing scopes are
    free, and writes follow the same rule — a phase may not touch a variable
    declared in a SIBLING or DESCENDANT scope, because that variable's owning
    phase may not be active. That section ends "This is statically checkable",
    and until this guard existed it was not checked: every out-of-scope
    reference passed the whole front end and died at playout on a bare
    `KeyError` out of `runtime/state.py`, with no span and no mention of the
    rule.

    `_check_state_default_scope` is the same traversal over the narrower
    declare-time question (what a `= <default>` may read, which is bounded by
    what exists *yet*). This one owns references in phase BODIES, where the
    whole block exists and only the frame stack bounds them. Their domains are
    disjoint by construction: `n.StateBlock` items are skipped here, so a bad
    default is reported once, by the guard whose rule actually decides it.

    Out of domain, deliberately: callable bodies — move types, rules,
    functions, procedures, defines. They have no enclosing phase; a move type
    is declared once and offered from wherever a game offers it, so its
    legality is a reachability question, not a lexical one, and 112 callable
    bodies across the corpus legitimately read phase-scoped state (issue #242).
    `Turns.again` and `RequireDecl.name` are bare `str`s that never become a
    `NameRef` (issue #243); `winner:` is the third of that shape and is checked
    here directly, because its name is right there to read.
    """
    declared_at: dict[str, list[str]] = {}

    def phase_names(phase: n.Phase) -> frozenset[str]:
        """The state names this phase declares. Pure: the declaration record is
        `collect`'s job, because this runs once per phase per traversal and
        would otherwise record every name as many times as it is called."""
        block = next((i for i in phase.items if isinstance(i, n.StateBlock)), None)
        return frozenset(d.name for d in block.decls) if block else frozenset()

    def report(node: n.NameRef, in_scope: frozenset[str]) -> None:
        if node.ref_kind != "state_var" or node.name in in_scope:
            return
        where = declared_at.get(node.name, [])
        # Name the declaring phase: "not in scope" alone sends the author
        # looking in the wrong place for a variable they can see on the page.
        home = " or ".join(f"phase '{w}'" for w in where) or "another scope"
        bag.error(
            f"state variable '{node.name}' is not in scope here: it is "
            f"declared in {home}, which does not enclose this reference, so "
            f"it does not exist while this runs. State is scoped to the phase "
            f"that declares it — move the declaration to a phase that encloses "
            f"both, or move this reference into {home}",
            node.span,
        )

    def descend(phase: n.Phase, enclosing: frozenset[str]) -> None:
        inner = enclosing | phase_names(phase)
        for item in phase.items:
            if isinstance(item, n.Phase):
                descend(item, inner)
            elif isinstance(item, n.StateBlock):
                continue  # `_check_state_default_scope` owns defaults
            else:
                for node in _walk(item):
                    if isinstance(node, n.NameRef):
                        report(node, inner)
        # The qualifier and the outcome cases are part of THIS phase, so its
        # own state is live in them (measured: `repeat until <own state>` runs).
        for owned in (phase.qualifier, *phase.outcome_cases):
            for node in _walk(owned):
                if isinstance(node, n.NameRef):
                    report(node, inner)

    top = frozenset(d.name for d in game.state.decls) if game.state else frozenset()

    # Collect every declaration first, so a diagnostic can name a declaring
    # phase that appears LATER in the file than the reference it explains.
    def collect(phase: n.Phase) -> None:
        for name in sorted(phase_names(phase)):
            declared_at.setdefault(name, []).append(phase.name)
        for item in phase.items:
            if isinstance(item, n.Phase):
                collect(item)

    for phase in game.phases:
        collect(phase)
    for phase in game.phases:
        descend(phase, top)

    # Game-level clauses run outside every phase — every frame has been popped
    # by then — so they see game-level state only. DERIVED, not listed: walk the
    # `Game` node's own fields and skip the ones another guard owns, so a clause
    # added later is covered the day it exists rather than the day someone
    # remembers it. `loser:` was found missing here by review, and it was found
    # because it had been enumerated by hand.
    for field in game.__dataclass_fields__:
        if field in _GAME_LEVEL_SKIP:
            continue
        # `_child_nodes`, not `_walk`: most of these fields hold a TUPLE of
        # nodes, and `_walk` returns immediately on anything that is not a
        # dataclass. Walking them with `_walk` visits nothing at all and the
        # loop looks total while checking only the handful of single-node
        # fields.
        for node in _child_nodes(getattr(game, field, None)):
            if isinstance(node, n.NameRef):
                report(node, top)

    # `winner: <dir> NAME` needs naming separately: `Winner.target` is a bare
    # `str` and never becomes a `NameRef` (issue #243), so the walk above cannot
    # see it.
    if game.winner is not None and game.winner.state_var not in top:
        where = declared_at.get(game.winner.state_var, [])
        home = " or ".join(f"phase '{w}'" for w in where) or "a phase"
        bag.error(
            f"`winner:` ranks on state variable '{game.winner.state_var}', which "
            f"is declared in {home} and so does not exist when the winner is "
            f"decided — the phase has exited by then. Declare it at game level",
            game.winner.span,
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


def _check_actor_alias_comparisons(game: n.Game, bag: DiagnosticBag) -> None:
    """A comparison between two names that provably denote the same acting
    player is dead code, and is refused here.

    `for each player p:` binds the acting player to `p` for its body (the
    `binds_actor` column of the domain registry), and the `actor` pronoun reads
    the acting player — so `p is actor` is true for every `p`, and `p is not
    actor` guards a body that never runs. Both operands are `Player`, so no
    guard in the type layer can see it (`typecheck`'s always-false Owner Guard
    compares TYPES, and these agree); and a branch that is never taken cannot
    fail at runtime either. That leaves it silently accepted, which for a
    designer tool is the worst outcome — "an operand comparing as
    always-false", decisions.md "Surface totality".

    The class is the aliasing, not the `for each` spelling, so this sweeps
    every construct that binds a seat AND rebinds the acting player to it
    (`for each` over a `binds_actor` role, `turns`, `each … simultaneously`,
    `as <name>`), plus the transitive `let me = actor`. The innermost rebind
    wins: inside a nested `as`/seat loop the outer binder no longer denotes
    the acting player, so the corpus idiom — capture the outer actor ABOVE the
    loop (`let w = actor`), compare against `w` inside — stays legal, which is
    the whole point of hoisting it.

    Runs after `_classify_names`, so it reads the `ref_kind` the resolver
    stamped rather than re-deciding what a name is.

    One walk from the game root, rather than a list of the declaration kinds
    that hold statements: an alias can only be established by a construct with
    an arm below, so every tree starts with the pronoun alone and a declaration
    form added later is swept without being enumerated here. (Each declaration
    body is nonetheless independent, which is the correct reading: the acting
    player inside a move effect or a rule body comes from the CALL site, so
    nothing lexically above it can have bound a second name to them.)"""
    _sweep_aliases(game, _ActorAliases(), game.content_flavor, bag)


def _sweep_aliases(
    node: object, aliases: _ActorAliases, flavor: Flavor, bag: DiagnosticBag
) -> None:
    """Walk `node`, threading the set of names that denote the acting player.

    Generic over the tree — a field walk driven by `_introduced_binders` and
    `_BINDER_SCOPE_FIELDS`, the same two registries lexical scoping already
    reads — with an arm per construct that rebinds the actor. A new binding
    construct therefore inherits correct shadowing for free, and only a
    construct that binds a SEAT needs an arm here."""
    if isinstance(node, n.BinOp):
        _check_alias_operands(node, aliases, bag)
    match node:
        # Both role tests are membership-guarded before the registry lookup:
        # `_resolve_phase_level` checks these roles against the same two sets,
        # but it reports into the SAME bag rather than halting, so this sweep
        # still walks a tree holding a role no row defines (`for each column
        # c`, a declared position domain). The registry answers such a role
        # with a compiler-channel raise — correct for a registry divergence,
        # wrong here, where it would replace the located diagnostic the author
        # needs with an assert and suppress every other diagnostic in the file.
        # Not the Owner Guard: the role's legality is decided above.
        case n.ForEach() if (
            (role := role_of(node.role)) is not None
            and role in _ITERATION_ROLES
            and binds_actor(role)
        ):
            # A SEAT role: the body's acting player IS the binder.
            _sweep_aliases(node.body, _rebound(node.binder, f"`for each {node.role} {node.binder}`"), flavor, bag)
            return
        case n.EachSimultaneous() if role_of(node.role) in SIMULTANEOUS_ROLES:
            # Binds the role noun itself as the local (`runtime/execute`).
            _sweep_aliases(node.body, _rebound(node.role, f"`each {node.role} simultaneously`"), flavor, bag)
            return
        case n.Turns():
            # leader/participants/termination evaluate OUTSIDE the turn, in the
            # enclosing scope — the binder does not exist there yet.
            for outer in (node.leader, node.participants, node.until):
                _sweep_aliases(outer, aliases, flavor, bag)
            turn = _rebound(node.binder, f"`turns {node.binder}`")
            _sweep_stmt_seq(node.body, turn, flavor, bag)
            return
        case n.AsBlock():
            # The player expression is evaluated in the OUTER context, so it
            # sees the enclosing aliases; the body sees a new acting player. It
            # keeps a name only when the expression IS one that already denotes
            # a seat immutably — a state variable can be reassigned in the
            # body, so it is not provably the acting player there.
            _sweep_aliases(node.player, aliases, flavor, bag)
            named = isinstance(node.player, n.NameRef) and node.player.ref_kind in (
                "local",
                "pronoun",
            )
            bound = node.player.name if named and isinstance(node.player, n.NameRef) else None
            _sweep_stmt_seq(node.body, _rebound(bound, f"`as {bound}`"), flavor, bag)
            return
        case n.LetStmt():
            # The value is evaluated in the ENCLOSING scope, before the name is
            # bound — so it sees the aliases as they stand, and `let p = p`
            # reads the old `p`. (Rebinding the name for the statements that
            # FOLLOW is `_sweep_stmt_seq`'s half of the rule.) An index binder
            # scopes to this value and nowhere else.
            index = (node.index,) if node.index is not None else ()
            _sweep_aliases(node.value, aliases.shadowed(index), flavor, bag)
            return
        case _:
            pass
    if isinstance(node, tuple) and any(_is_stmt(item) for item in node):
        _sweep_stmt_seq(node, aliases, flavor, bag)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _sweep_aliases(item, aliases, flavor, bag)
        return
    if is_dataclass(node) and not isinstance(node, type):
        introduced = _introduced_binders(node, flavor)
        scope_fields = _BINDER_SCOPE_FIELDS.get(type(node))
        for f in fields(node):
            # `_BINDER_SCOPE_FIELDS` is not the whole scoping story: `_rewrite`
            # scopes some binder-introducing kinds itself and so leaves them out
            # of the table (a `produces:` arm's payload binders, a struct's
            # derived-field names). Absent an entry, shadow the node's binders in
            # EVERY field — the safe direction, since over-shadowing can only
            # miss a degenerate comparison, while under-shadowing REFUSES a
            # sound one (`for each player p: … produces: won(p) { p is actor }`,
            # where the arm's `p` is the payload, not the acting player).
            shadowed = scope_fields is None or f.name in scope_fields
            inner = aliases.shadowed(introduced) if shadowed else aliases
            _sweep_aliases(getattr(node, f.name), inner, flavor, bag)


def _sweep_stmt_seq(
    stmts: tuple[object, ...], aliases: _ActorAliases, flavor: Flavor, bag: DiagnosticBag
) -> None:
    """A statement tuple, with `let` threading forward exactly as the runtime
    threads `ctx.locals` through a body: `let me = actor` (or `let me = p`,
    where `p` already denotes the actor) makes `me` a further name for the
    same player, for the statements that follow it.

    A `let` REBINDS its name, so the name is dropped and re-added only when the
    value denotes the acting player. Both halves matter, and their ORDER is the
    whole rule: the value is read against the set as it stands BEFORE the
    binding (so `let p = p` keeps the alias — the right-hand `p` is the old
    one), and the name is dropped after (so `let p = <someone else>` inside
    `for each player p` frees `p`, and the honest `p is actor` after it is not
    refused). This is the same "initializer runs in the enclosing scope" rule
    `as`'s player expression and `turns`' leader already follow; `let` needs it
    spelled out here because its name scopes forward to later siblings rather
    than to a field of its own node, which is why `_introduced_binders` and the
    generic walk do not reach it."""
    for stmt in stmts:
        _sweep_aliases(stmt, aliases, flavor, bag)
        if not isinstance(stmt, n.LetStmt):
            continue
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


def _is_stmt(node: object) -> bool:
    return isinstance(node, get_args(n.Stmt))


def _check_alias_operands(
    node: n.BinOp, aliases: _ActorAliases, bag: DiagnosticBag
) -> None:
    """Refuse `<alias> is <alias>` / `<alias> is not <alias>`: both operands
    name the acting player, so the comparison is a constant."""
    if node.op not in ("is", "is_not"):
        return
    left, right = node.left, node.right
    if not (isinstance(left, n.NameRef) and isinstance(right, n.NameRef)):
        return
    if not all(
        ref.name in aliases.names and ref.ref_kind in ("local", "pronoun")
        for ref in (left, right)
    ):
        return
    word = "is" if node.op == "is" else "is not"
    verdict = "always true" if node.op == "is" else "never true"
    where = (
        f"{aliases.origin} binds the acting player, so "
        if aliases.origin is not None
        else ""
    )
    bag.error(
        f"`{left.name} {word} {right.name}` is {verdict}: {where}"
        f"`{left.name}` and `{right.name}` are the same player here. "
        f"To compare against a DIFFERENT player, bind them outside the "
        f"construct that rebinds the acting player (`let w = actor` above the "
        f"loop, then `{left.name} is not w`); to act as one named player, use "
        f"`as <player> {{ … }}`.",
        node.span,
    )


def _resolve_winner_loser(game: n.Game, bag: DiagnosticBag) -> None:
    """A game names its result. `winner:` and `loser:` are each optional
    grammar positions, so their joint absence is checked here; without this
    Owner Guard a game with neither would compile clean and then reach a driver that
    requires at least one of them before it can play a single decision."""
    if game.winner is None and game.loser is None:
        bag.error(
            f"game '{game.name}' must declare `winner: <rank-dir> <var>` or "
            "`loser: <player-expr>` — without one the playout has no result",
            game.span,
        )


# The declared types a game may be RANKED by: totally ordered, and their
# values are what `openspiel/replay.returns_for` hands OpenSpiel as utilities.
# `Boolean` is here on the corpus's authority, not as a lenience -- `cheat`
# ranks on `won[player]` and `coup` on `alive[player]`, so an Integer-only
# rule would refuse two corpus games. Every other member of
# `typecheck.KNOWN_TYPE_NAMES` either cannot be compared at all (`Card` and a
# struct are unorderable) or -- worse -- compares fine and means nothing: a
# `Player`-typed target ranks without complaint and delivers SEAT IDS as
# utilities, silently, at every layer.
_RANKABLE_TYPES: frozenset[str] = frozenset({"Integer", "Boolean"})


def _check_delegation(game: n.Game, bag: DiagnosticBag) -> None:
    """The Delegated Play helpers' three Owner Guards (decisions.md "Delegated
    play"; the grid is tests/test_delegated_play.py):

    - a helper of the exact name must take exactly one Player — the routing
      contract is per-seat, and any other shape is a mis-remembered API;
    - a game defining a helper must hold a trick round somewhere for it to
      route — helpers no site consults are accepted-but-ignored, the defect
      class this repo ranks worst;
    - every trick round's DECLARED source projects identity to its own seat
      (helpers or not): the unrouted actor draws from their own instance, and
      an owner-blind declared source is a game nobody can play, statically
      known from the declaration.

    The routed pool's guard — the DECIDER must see it — is deliberately NOT
    here: whether a seat's pool is routed, and to whom the decision goes,
    are the helpers' values at that seat, and correlating two opaque
    expression bodies is not statically decidable (Bridge's own helper
    routes undelegated seats to their private hands, legally). The precise
    check is the runtime Owner Guard at the draw (`runtime/mechanics.py`),
    fired whenever either helper routes.
    """
    from cardlang.runtime.delegation import HELPER_NAMES

    helpers = [f for f in game.functions if f.name in HELPER_NAMES]
    zone_types = {z.name: z.type_ref.name for z in game.zones}
    for node in _walk(game):
        if not isinstance(node, n.TrickRound):
            continue
        ztype = zone_types.get(node.source_zone)
        if ztype is not None and ZONE_PROJECTIONS[ztype].owner != "identity":
            bag.error(
                f"a trick round's source '{node.source_zone}' ({ztype}) does "
                f"not project identity to its own seat — the acting player "
                f"could not see the cards offered from it. Play tricks from "
                f"an owner-visible zone",
                node.span,
            )
    if not helpers:
        return
    for fn in helpers:
        if len(fn.params) != 1 or fn.params[0].type_name != "Player":
            got = ", ".join(f"{q.name} : {q.type_name}" for q in fn.params) or "none"
            bag.error(
                f"'{fn.name}' is a Delegated Play helper and must take exactly "
                f"one Player parameter (the seat whose move is routed); it "
                f"takes ({got})",
                fn.span,
            )
    if not any(isinstance(node, n.TrickRound) for node in _walk(game)):
        names = ", ".join(sorted(f.name for f in helpers))
        bag.error(
            f"this game defines {names} but holds no trick round for the "
            f"routing to reach — the helpers would be silently ignored "
            f"(routing at other decision points is issue #458)",
            helpers[0].span,
        )

def _check_winner_target(game: n.Game, bag: DiagnosticBag) -> None:
    """A `winner:` target must be a state variable a game can be ranked by.

    Resolve already walls the NAME -- undeclared, or declared inside a phase
    -- and says nothing about the DECLARATION it lands on. Two of that
    declaration's properties decide whether the result path works at all, and
    neither was checked:

    * UNINDEXED. `driver` builds the result with
      `dict(rs.get(game.winner.state_var))`, so a scalar target dies with a
      bare `TypeError: 'int' object is not iterable` (issue #153) -- and in a
      game with a `repeat until` phase it dies earlier still, at the per-hand
      trace, so which Python error the author meets depends on whether their
      game loops.
    * UNRANKABLE TYPE. Nothing anywhere read it. The crashing cells are the
      mild ones; the dangerous cells are the silent ones (`_RANKABLE_TYPES`).

    Reported only when the target IS a game-level declaration. `game.state`
    being absent, and the name resolving to nothing or to a phase-local
    declaration, are all `_check_state_scope`'s to report -- it is the Owner
    Guard for whether a `winner:` name names a game-level state variable at
    all. Speaking here too would add a second diagnostic about a name the
    author has just been told does not exist, burying the one that matters.

    The grid is tests/test_winner_target.py.
    """
    if game.winner is None or game.state is None:
        return
    decl = next(
        (d for d in game.state.decls if d.name == game.winner.state_var), None
    )
    if decl is None:
        return
    what = f"`winner:` ranks the game on state variable '{decl.name}', "
    if decl.index is None:
        bag.error(
            f"{what}which is not indexed — a game is ranked by a score each "
            f"player or team holds, so the target is declared "
            f"`{decl.name}[player]` or `{decl.name}[team]`. A scalar has no "
            f"per-member value to rank",
            game.winner.span,
        )
        return
    if decl.optional:
        bag.error(
            f"{what}declared `{decl.type_name}?` — an optional score may be "
            f"`none`, which cannot be ranked against a number",
            game.winner.span,
        )
        return
    if decl.type_name not in _RANKABLE_TYPES:
        rankable = ", ".join(sorted(_RANKABLE_TYPES))
        bag.error(
            f"{what}declared `{decl.type_name}` — a game is ranked by a "
            f"score, so the target must be {rankable}. Its values become "
            f"the game's OpenSpiel returns",
            game.winner.span,
        )


def _check_teams(game: n.Game, bag: DiagnosticBag) -> None:
    """`teams:` must PARTITION the seats — every seat in exactly one team.

    Every consumer already reads it as one: the driver and the OpenSpiel
    returns path both build `{p: ti for ti, members in enumerate(game.teams)
    for p in members}`, which is a partition or it is a lie. The three ways
    to break it were all accepted silently (issue #155), and the dict
    comprehension makes the worst one quiet rather than loud — a seat listed
    in two teams is assigned the LATER one, because a later key overwrites an
    earlier one, so the game plays on with that seat scoring for a team its
    author did not put it on.

    The Owner Guard belongs HERE, at the declaration, and not at any of the readers,
    because one of the readers is the information sets. A team zone family
    asks `domains.zone_observer_key` who owns an instance, which for a team
    is `rs.team_of.get(observer)` -- so a seat in no team is silently a
    non-owner of every team family, and a zone type whose owner projection
    differs from its others projection shows that seat the count-only view of
    its own team's zone. `tests/openspiel_ready/partition.py` asks the SAME
    function, so the readiness proofs and the runtime agree on the same wrong
    owner and the soundness matrix stays green: no downstream oracle can see
    this, which is what makes the declaration the only place it can be
    caught.

    The grid is tests/test_teams_partition.py.
    """
    if not game.teams:
        return
    if not game.players.is_well_formed:
        # Shadow Guard. `typecheck` owns the players-count diagnostic ("a game
        # needs at least one player", "upper bound precedes lower bound") and
        # is the only place it should be reported. Resolve raises before
        # typecheck ever runs, so building a partition complaint on top of a
        # malformed `players:` would REPLACE the real diagnostic with a
        # derivative one and send the author to fix the wrong clause.
        return
    if game.players.varies:
        # A fixed team list cannot partition a seat set that varies, and
        # WHICH count it would have to cover is genuinely undecided: the
        # engine plays a range game at `players.low` while the seat-literal
        # bound uses `high` (issue #296). Refused rather than given a
        # meaning here -- guessing one would pin a decision nobody made, and
        # the next author would read its correction as a regression.
        bag.error(
            f"game '{game.name}' declares `teams:` beside a variable player "
            f"count ({game.players.low}..{game.players.high}) — a fixed team "
            f"list names fixed seats, so it cannot cover a seat set that "
            f"changes with the count. Declare a single `players:` count",
            game.span,
        )
        return
    count = game.players.low
    holding: dict[int, list[int]] = {}
    for team_index, members in enumerate(game.teams):
        for seat in members:
            holding.setdefault(seat, []).append(team_index)

    for seat in sorted(s for s in holding if not 0 <= s < count):
        bag.error(
            f"`teams:` names seat {seat}, which the game does not have: it "
            f"declares {count} player(s) (0..{count - 1}). The seat never "
            f"matches, so its team silently plays a member short",
            game.span,
        )
    for seat in sorted(s for s, ts in holding.items() if len(ts) > len(set(ts))):
        bag.error(
            f"`teams:` lists seat {seat} twice in the same team — a seat "
            f"belongs to its team once",
            game.span,
        )
    for seat in sorted(s for s, ts in holding.items() if len(set(ts)) > 1):
        named = ", ".join(str(t) for t in sorted(set(holding[seat])))
        bag.error(
            f"`teams:` puts seat {seat} on more than one team (teams "
            f"{named}) — the engine keeps only the last, so this seat would "
            f"score for a team you did not put it on",
            game.span,
        )
    for seat in (s for s in range(count) if s not in holding):
        bag.error(
            f"`teams:` leaves seat {seat} on no team, but the game declares "
            f"{count} player(s) — every seat must belong to exactly one team",
            game.span,
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


# The bound on a declared position domain's member count: a Suit-sized or
# column-sized layout is orders of magnitude below it, and a cross-product of
# two runaway domains would otherwise silently explode the OpenSpiel
# offering block (every member pair mints an action id). No physical
# tabletop layout approaches it.
_POSITION_MEMBER_CEILING = 256


def _check_zone_type_names_are_not_taken(game: n.Game, bag: DiagnosticBag) -> None:
    """A declared `type` may not take a kernel zone type's spelling.

    `Hand` already means a zone type. A `type Hand = { … }` beside it would make
    one name mean two things in the one position that reads BOTH registries — a
    library's `requires` entry, whose type slot says whether the entry names a
    `state { }` or a `zones { }` declaration. Refused where the name is
    DECLARED, so the ambiguity cannot be built, rather than disambiguated at
    each use by a precedence nobody wrote down.

    The mirror for position domains is `POSITION_NAME_SOURCES`, which reserves
    the same set: the two declaration sites that could take a zone-type
    spelling, refused against one registry.

    Free against the corpus — no game declares a struct type, and every position
    domain is lowercase — so this reserves a name space nobody is using rather
    than reclaiming one."""
    for declared in game.types:
        if declared.name in LIBRARY_ZONE_TYPES:
            bag.error(
                f"type '{declared.name}' takes the name of a zone type, which a "
                f"library's `requires` entry reads to tell a state contract from "
                f"a zone one — a name may not mean two things there; rename the "
                f"type",
                declared.span,
            )


# The sites that reserve a name against the sources below. A position domain
# reaches the language from three places and the reservation is asked once per
# place: the author's `positions { }` block, and the two domains a `board:`
# clause mints. Named here so the set can be enumerated — the sources'
# accumulation is one axis of this guard, and its consumers are the other;
# tests/test_positions.py crosses them and scrapes the call sites, so a fourth
# consumer cannot join in silence any more than a fifth source can.
DECLARED_POSITION_SITE = "declared"
MINTED_CELL_SITE = "board-minted cell"
MINTED_DIRECTION_SITE = "board-minted dir"
RESERVATION_SITES: tuple[str, ...] = (
    DECLARED_POSITION_SITE,
    MINTED_CELL_SITE,
    MINTED_DIRECTION_SITE,
)


@dataclass(frozen=True)
class ReservedNameSource:
    """One namespace a position domain's name is reserved against.

    The registry below is the AXIS of the reservation. Its domain is "every
    namespace whose names a position domain must not collide with", and those
    accumulate silently: three sources were unioned inline with `|` when review
    found `positions { R : 1..4 }` beside `type R` reading the struct as the
    position's Integer, and a fourth (the zone types) was added the same way
    afterwards. An inline union has nothing to enumerate, so the sweep in
    tests/test_positions.py could derive from each source it already knew and
    still be blind to the next one — which is how the fifth (the collection
    nouns) stayed invisible. A table can be iterated: by the guard below, by
    the diagnostic that names which source matched, and by the grid that
    crosses the sources against `RESERVATION_SITES`.

    `names` takes the game because the sources are not homogeneous: some are
    static registries, fixed for every game, and one is the game's own `type`
    declarations. A source that ignores the argument is answering "the same
    names for every game", which is a fact about that source, not a reason to
    split the table.

    A source that reserves a name only under some condition expresses that in
    `names` — an empty answer for a game where the ambiguity cannot arise —
    rather than by being consulted at some sites and not others. Every
    reservation site asks every source, so a new site inherits the whole
    registry and a new source reaches every site.
    """

    label: str
    names: Callable[[n.Game], frozenset[str]]


#: Every namespace a position domain's name is reserved against.
#: ORDERED: `_reserved_domain_source` reports the first match, so a spelling
#: reachable from two sources names one of them deterministically.
POSITION_NAME_SOURCES: tuple[ReservedNameSource, ...] = (
    ReservedNameSource(
        "a built-in domain id",
        lambda game: frozenset(
            role_names(_ITERATION_ROLES | SIMULTANEOUS_ROLES | ZONE_INDEX_ROLES)
        ),
    ),
    ReservedNameSource("a built-in type name", lambda game: KNOWN_TYPE_NAMES),
    ReservedNameSource("a zone type", lambda game: frozenset(LIBRARY_ZONE_TYPES)),
    ReservedNameSource(
        "a declared type name", lambda game: frozenset(t.name for t in game.types)
    ),
    # The fifth, found by crossing the sources against the slots that read
    # them. `DomainQuery.binder` carries ONE name resolved against two
    # namespaces, and the optional `in <collection>` clause is what picks: bare
    # reads `game.positions`, the collection form reads `_COLLECTION_NOUNS`. So
    # in a board game `positions { line : 1..3 }` turns `any line where ...` —
    # rejected in every other board game, with a diagnostic pointing at the
    # collection form — into an accepted quantifier over the declared integer
    # domain, while `any line in lines(3)` in the SAME game still means board
    # lines. One spelling, two meanings, no diagnostic: the
    # `positions { R } / type R` defect at a different pair of slots.
    #
    # Two derived narrowings, each closing what would otherwise be an
    # over-reservation the corpus refutes:
    #  * BOARD GAMES ONLY. The collection form needs a `TLine`, which only
    #    `lines(k)` produces and which is board-only, so in a boardless game
    #    the noun has exactly one meaning and reserving it would take a name
    #    nothing else can claim.
    #  * MINUS the board's minted domain. `cell` is a collection noun AND the
    #    name the board mints, on purpose — `all cells in <line>` iterates
    #    exactly those members. A declared `cell` beside a board is refused by
    #    `_resolve_board`, whose message names both sites; reserving it here
    #    too would answer the same mistake twice and less well. FreeCell's
    #    `positions { cell : 1..4 }` — boardless — stays legal under both
    #    narrowings.
    # `_COLLECTION_NOUNS` is defined below, beside the guard that reads it; the
    # lambda resolves it at call time.
    ReservedNameSource(
        "a collection noun",
        lambda game: (
            _COLLECTION_NOUNS - {BOARD_DOMAIN}
            if game.board is not None
            else frozenset()
        ),
    ),
)


def _reserved_domain_source(game: n.Game, name: str, site: str) -> str | None:
    """The label of the first source reserving `name`, or None if it is free.

    The diagnostic says WHICH namespace a name was already taken from rather
    than listing the namespaces it might have come from: a message that
    enumerates the sources in prose goes stale the moment the registry above
    grows, and a stale enumeration reads exactly like a fresh one.

    `site` does not select sources — every site asks the whole registry, and a
    source that reserves conditionally says so in its own `names`. It is taken
    so each call NAMES which reservation it is, which is what lets
    tests/test_positions.py derive the consumer axis from the calls instead of
    from a list someone has to remember to extend.
    """
    assert site in RESERVATION_SITES, f"unknown reservation site {site!r}"
    for source in POSITION_NAME_SOURCES:
        if name in source.names(game):
            return source.label
    return None


def _resolve_positions(game: n.Game, bag: DiagnosticBag) -> frozenset[str]:
    """Validate the `positions { }` block (decisions.md "Position domains and
    positional zones"): static, non-empty, bounded ranges, and names reserved
    against every namespace in `POSITION_NAME_SOURCES` — the reconciliation
    between a definition site the author owns and the ones the kernel owns is
    rejection, so a lookup that consults positions first can never shadow a
    kernel row. Duplicates are rejected by `_check_duplicate_names`, with every
    other declaration namespace. Returns the declared names for the consumers
    (zone indexes, move parameters, the bare-reference Owner Guard).

    AUTHOR-DECLARED entries only. A re-resolve of an already-resolved game
    sees the board's minted `cell` beside them (`_resolve_board` appends it to
    `game.positions`), and the mint is not a declaration: its bounds are
    unread, and the kernel is entitled to its own spellings — the two guards in
    `_resolve_board` are what reconcile a minted name, at their own sites.

    The member ceiling is not lost by that skip. A minted domain's member count
    is bounded where the mint is: `board_entry` refuses a family argument
    outside its declared range, so the widest board a designer can write mints
    no more cells than `_POSITION_MEMBER_CEILING` admits. That is an agreement
    between two registries rather than one rule, so it is crossed rather than
    assumed — tests/test_positions.py."""
    for p in (p for p in game.positions if p.members_named is None):
        if p.lo > p.hi:
            bag.error(
                f"position domain '{p.name}' declares an empty range "
                f"{p.lo}..{p.hi} — the bounds are inclusive and must satisfy "
                f"lo <= hi",
                p.span,
            )
        elif p.hi - p.lo + 1 > _POSITION_MEMBER_CEILING:
            bag.error(
                f"position domain '{p.name}' declares {p.hi - p.lo + 1} "
                f"members — more than the ceiling "
                f"({_POSITION_MEMBER_CEILING}); every member mints action-"
                f"space ids, so a runaway range is a declaration error",
                p.span,
            )
        source = _reserved_domain_source(game, p.name, DECLARED_POSITION_SITE)
        if source is not None:
            bag.error(
                f"position domain '{p.name}' collides with {source} — "
                f"pick another name",
                p.span,
            )
    return frozenset(p.name for p in game.positions)


def _resolve_board(
    game: n.Game, bag: DiagnosticBag, declared_positions: frozenset[str]
) -> n.Game:
    """Validate the `board:` clause and mint its `cell` position domain
    (decisions.md "Boards and cells"). A board mints one named-member domain
    (`cell`) whose members are the board's cells; it rides the `positions { }`
    substrate, so the minted domain is injected into `game.positions` as a
    named-member `PositionDecl` and thereafter flows through every surface the
    integer position domains flow through (zone index, move parameter, unowned
    projection, action space, IR).

    Returns the game unchanged when there is no board, or with the minted
    domain appended; every rejection path returns without minting (the game is
    left boardless downstream, so a single mistake yields a single
    diagnostic)."""
    if game.board is None:
        return game
    # Idempotency: a re-resolve of an already-resolved game sees the MINTED
    # `cell` domain (a named-member PositionDecl, `members_named` set) and must
    # neither re-mint it nor misread it as a user collision. A user-DECLARED
    # `cell` (integer range, `members_named is None`) is not this case — it is
    # the collision the Owner Guard below reports.
    if any(
        p.name == BOARD_DOMAIN and p.members_named is not None for p in game.positions
    ):
        return game
    # `board:` requires `pieces:`. Parse enforces cards XOR pieces, so a
    # non-piece flavor here is exactly a card game — the `board: + cards:`
    # rejection and the `board: without pieces:` one are the same Owner Guard (no game
    # has witnessed needing a board on a card deck).
    if game.content_flavor != "piece":
        bag.error(
            f"game '{game.name}' declares `board:` but not `pieces:` — a board "
            f"lays out piece positions and is only valid alongside `pieces:` "
            f"(a card game with a board is rejected until a game witnesses "
            f"needing both)",
            game.board.span,
        )
        return game
    # Collision: the minted `cell` may shadow neither a declared `positions { }`
    # name (name both sites) nor a built-in spelling (the standing Owner Guard, reused
    # so a future built-in named `cell` cannot land silently). `declared_positions`
    # names only the user's declared domains (this runs right after
    # `_resolve_positions`, before the mint below appends to `game.positions`).
    if BOARD_DOMAIN in declared_positions:
        bag.error(
            f"the board mints a position domain named '{BOARD_DOMAIN}', which "
            f"collides with the declared `positions {{ {BOARD_DOMAIN} : ... }}` "
            f"— rename the declared domain (a board already provides '{BOARD_DOMAIN}')",
            game.board.span,
        )
        return game
    minted_clash = _reserved_domain_source(game, BOARD_DOMAIN, MINTED_CELL_SITE)
    if minted_clash is not None:
        bag.error(
            f"the board mints a position domain named '{BOARD_DOMAIN}', which "
            f"collides with {minted_clash}",
            game.board.span,
        )
        return game
    # The board mints a SECOND domain, `dir` (the movement directions), as a
    # separate source (`directions_of`) rather than a `game.positions` entry.
    # A declared `positions { dir : ... }` clashes with it -- the `cell`
    # collision's twin. No early return: unlike a `cell` clash, a declared
    # `dir` does not block minting `cell` (they are different names), so the
    # error is emitted and cell minting proceeds; the bag halts the pipeline
    # either way.
    if DIRECTION_DOMAIN in declared_positions:
        bag.error(
            f"the board mints a movement-direction domain named "
            f"'{DIRECTION_DOMAIN}', which collides with the declared "
            f"`positions {{ {DIRECTION_DOMAIN} : ... }}` — rename the declared "
            f"domain (a board already provides '{DIRECTION_DOMAIN}')",
            game.board.span,
        )
    # The `cell` clash above is checked against BOTH declared positions and the
    # reserved set (built-ins + declared type names); `dir` gets the same second
    # check, or a `type dir = { … }` would resolve clean while `along : dir`
    # silently read as the minted domain (direction lookup precedes struct
    # lookup) -- one spelling, two meanings.
    direction_clash = _reserved_domain_source(
        game, DIRECTION_DOMAIN, MINTED_DIRECTION_SITE
    )
    if direction_clash is not None:
        bag.error(
            f"the board mints a movement-direction domain named "
            f"'{DIRECTION_DOMAIN}', which collides with {direction_clash} — "
            f"rename the declared type (a board already provides "
            f"'{DIRECTION_DOMAIN}')",
            game.board.span,
        )
    # Family/args validity is the registry's to judge: `board_entry` raises an
    # OwnerGuardError naming the violated bound (unknown family, wrong arity,
    # out-of-bounds arg), which becomes a diagnostic at the clause span.
    # Narrow BY TYPE, not by `ValueError`: the same call builds a `BoardEntry`,
    # whose `__post_init__` pins the registry's own output. Those address the
    # engine maintainer, and a `ValueError` catch swallowed all 14 of them into
    # a diagnostic on the designer's `board:` line — an engine bug presenting
    # as a compile error on a correct game.
    try:
        entry = board_entry(game.board.family, game.board.args)
    except OwnerGuardError as exc:
        bag.error(str(exc), game.board.span)
        return game
    # `lo`/`hi` are unread for a named-member domain (`.members` returns
    # `members_named`); they carry the member count so the struct stays
    # internally consistent if ever inspected.
    minted = n.PositionDecl(
        name=BOARD_DOMAIN,
        lo=0,
        hi=len(entry.cells) - 1,
        members_named=entry.cells,
        span=game.board.span,
    )
    return replace(game, positions=game.positions + (minted,))


def _resolve_zone(
    zone: n.ZoneDecl, bag: DiagnosticBag, positions: frozenset[str]
) -> None:
    index_known = (
        zone.index is None
        or role_of(zone.index) in _KNOWN_ROLES
        or zone.index in positions
    )
    if not index_known:
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
        if role_of(arg.name) not in _KNOWN_ROLES and arg.name not in positions:
            bag.error(f"unknown owner '{arg.name}'", arg.span)
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
            )


def _check_position_family_refs(
    game: n.Game, bag: DiagnosticBag, positions: frozenset[str]
) -> None:
    """A position-indexed family must always be subscripted: the bare-family
    actor sugar (`hand` = the acting player's hand) keys the family by the
    acting SEAT, and a position family has no seat keys — the runtime read
    would land outside the key set. Refused here, after classification (so a
    local binder shadowing the family name is exempt: only `ref_kind ==
    "zone"` references are family reads). The runtime's phantom-key error in
    `evaluate._name` is the Shadow Guard behind this Owner Guard."""
    pos_families = {z.name for z in game.zones if z.index in positions}
    if not pos_families:
        return
    subscript_objs = {
        id(nd.obj) for nd in _walk(game) if isinstance(nd, n.Subscript)
    }
    for nd in _walk(game):
        if (
            isinstance(nd, n.NameRef)
            and nd.ref_kind == "zone"
            and nd.name in pos_families
            and id(nd) not in subscript_objs
        ):
            index = next(z.index for z in game.zones if z.name == nd.name)
            bag.error(
                f"'{nd.name}' is a position-indexed zone family and must be "
                f"subscripted (`{nd.name}[<{index}>]`) — the bare-family "
                f"actor sugar reads the acting player's instance, and a "
                f"position family has no per-player instances",
                nd.span,
            )


def _check_rule_reaches_a_reader(rule: n.RuleDef, bag: DiagnosticBag) -> None:
    """Reject rule surface no decision site can consult (decisions.md "Surface
    totality"): accepted-but-ignored is the worst failure mode for a designer
    tool, so a clause that enforces nothing is refused rather than parsed and
    dropped. Every test is the COMPLEMENT of what `rules.legal_cards` actually
    reads, never a list of the dead spellings — `LIBRARY_MOVE_TYPES` grows as
    games land and `DEMAND_KINDS` could too, and an enumeration of the dead
    would silently re-open this hole for the new member.

    Runs after `_instantiate_rules`, so spliced library rules and instantiated
    templates are checked on the same path as hand-written ones.

    Widening enforcement (draughts' mandatory capture, morris's removal
    restriction) retires these Owner Guards — the surface returns with an
    implementation behind it. Until then it is deferred, not deleted:
    docs/roadmap.md "Grammar surface deferred by the checker",
    docs/open-questions/rule-scope-beyond-trick-play.md.
    """
    where = "docs/open-questions/rule-scope-beyond-trick-play.md"
    if rule.constrains is not None and rule.constrains not in LIBRARY_MOVE_TYPES:
        return  # already reported as an unknown move type; one error, not two
    if rule.constrains != RULE_ENFORCED_MOVE_TYPE:
        named = (
            f"'{rule.constrains}'"
            if rule.constrains is not None
            else "no move type (the `constrains:` clause is absent)"
        )
        bag.error(
            f"rule '{rule.name}' constrains {named}, which no decision site "
            f"consults: rules are applied at exactly one place — the trick "
            f"round's card decision, which asks about "
            f"`{RULE_ENFORCED_MOVE_TYPE}` — so this rule would never fire. "
            f"Constrain `{RULE_ENFORCED_MOVE_TYPE}`, or enforce the "
            f"constraint where the move is made (a movement's `chosen N`, a "
            f"move type's `when:` guard). Widening rule scope is an open "
            f"question ({where}).",
            rule.span,
        )
        return  # the clause Owner Guards below would pile onto the same broken rule
    if rule.demands is not None and rule.demands.kind != n.DEMAND_KIND_CARDS:
        bag.error(
            f"rule '{rule.name}' has a `demands: actions where …` move-shape "
            f"predicate, which is never enforced: the legal-move engine "
            f"consults card-set demands only, and no other site consults "
            f"rules at all. Enforce the move's shape where the move is made "
            f"(a movement's `chosen N` binds the count, a move type's "
            f"`when:` guard binds its parameters), or state the constraint "
            f"as a card set. Binding move-shape predicates is an open "
            f"question ({where}).",
            rule.demands.span or rule.span,
        )
        return
    if rule.demands is None and rule.exempts is None:
        bag.error(
            f"rule '{rule.name}' enforces nothing: it declares neither a "
            f"`demands:` card set nor an `exempts:` set, so activating it "
            f"cannot change which cards are legal. Give it a `demands:` (with "
            f"its `if_impossible:` fallback) or an `exempts:`, or delete it — "
            f"`applies_when:` alone selects when a rule fires, not what it "
            f"does.",
            rule.span,
        )


def _resolve_rule(rule: n.RuleDef, bag: DiagnosticBag) -> None:
    if rule.constrains is not None and rule.constrains not in LIBRARY_MOVE_TYPES:
        bag.error(
            f"rule '{rule.name}' constrains unknown move type '{rule.constrains}'",
            rule.span,
        )
    _check_rule_reaches_a_reader(rule, bag)
    # A card-set `demands` can filter the legal set to empty; the rule must say
    # what happens then (`if_impossible`) rather than relying on a silent default.
    # `actions where` demands never narrow the card set — they have no runtime
    # enforcement point at all (rules.py) — so there is no empty set for an
    # `if_impossible` to answer and they are exempt from this requirement.
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

    A `transition_to: Y` inside a mode names a sibling MODE of that mode — the
    modes of one phase body are one condition's sides, so the namespace a
    target resolves against is the enclosing phase's own modes.
    """
    sibling_names = {p.name for p in phases}
    for phase in phases:
        _check_modes(phase, bag)
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
        if phase.qualifier is None or phase.qualifier.kind != "repeat_until":
            for hook in phase.items:
                if isinstance(hook, (n.BeforeEach, n.AfterEach)):
                    kw = "before_each" if isinstance(hook, n.BeforeEach) else "after_each"
                    bag.error(
                        f"`{kw}` runs per iteration of a `repeat until` phase; "
                        f"phase '{phase.name}' has no iteration — put the "
                        f"statements in the phase body",
                        hook.span,
                    )
        modes = tuple(i for i in phase.items if isinstance(i, n.Mode))
        mode_names = {m.name for m in modes}
        for item in phase.items:
            scope = mode_names if isinstance(item, n.Mode) else sibling_names
            _resolve_phase_item(item, scope, known_rule_names, bag)
        children = tuple(i for i in phase.items if isinstance(i, n.Phase))
        _resolve_phase_level(children, known_rule_names, bag)


def _resolve_transition(
    transition: n.TransitionTo, mode_names: set[str], bag: DiagnosticBag
) -> None:
    if transition.mode not in mode_names:
        bag.error(
            f"transition_to target '{transition.mode}' is not a sibling mode "
            f"of this phase — a transition ends one condition and begins "
            f"another, so its target is a `mode` declared beside this one",
            transition.span,
        )
    if transition.event.move_type not in LIBRARY_MOVE_TYPES:
        bag.error(
            f"transition event names unknown move type '{transition.event.move_type}'",
            transition.event.span,
        )
    elif transition.event.move_type != "play_to_trick":
        bag.error(
            f"transitions fire from trick plays only today: the event move "
            f"type must be `play_to_trick`, not "
            f"'{transition.event.move_type}' (roadmap.md)",
            transition.event.span,
        )


def _check_modes(phase: n.Phase, bag: DiagnosticBag) -> None:
    """The mode-role invariant: every mode is exactly one of a transition
    SOURCE or a transition TARGET.

    A mode is one side of one condition — the "before", which declares the
    transitions that end it, or the "after", which a sibling names. The two
    rejected shapes are not hypothetical; both ran silently wrong before this
    Owner Guard existed, and `check_dsl` accepted both:

    - BOTH (a chain, or a self-loop): the runtime keys a mode's activity on ITS
      target having fired, not on its having been entered, so the middle mode
      of a three-mode chain is active from the very start and its transition is
      live before anything reaches it.
    - NEITHER (an orphan): a transition-less mode holds only once its own name
      has fired, which for a mode nobody targets never happens — so its
      `active_rules:` silently never apply.
    """
    modes = [i for i in phase.items if isinstance(i, n.Mode)]
    targeted = {t.mode for m in modes for t in m.transitions}

    # A target belongs to ONE condition. Two sources naming the same target
    # read as "two conditions that happen to end together", but the runtime
    # keys a source's activity on its TARGET having fired, not on the source's
    # own identity — so either trigger ends both, and a condition can end
    # without its own event ever occurring. Rejected rather than given that
    # meaning: nobody writing two separate conditions wants one to cancel the
    # other. Lifting this means keying activity on the mode rather than the
    # target name (issue #283).
    claimed_by: dict[str, str] = {}
    for mode in modes:
        for transition in mode.transitions:
            owner = claimed_by.setdefault(transition.mode, mode.name)
            if owner != mode.name:
                bag.error(
                    f"modes '{owner}' and '{mode.name}' both transition to "
                    f"'{transition.mode}' — a target is the far side of one "
                    f"condition, and sharing it makes either trigger end both. "
                    f"Give each condition its own target mode",
                    transition.span,
                )

    for mode in modes:
        is_source = bool(mode.transitions)
        is_target = mode.name in targeted
        if is_source and is_target:
            bag.error(
                f"mode '{mode.name}' is both entered by a transition and "
                f"declares one — modes are independent two-sided conditions, "
                f"not a chain. Give each condition its own pair of modes, or "
                f"use a state variable with `applies_when` for a progression "
                f"through three or more stages",
                mode.span,
            )
        elif not is_source and not is_target:
            bag.error(
                f"mode '{mode.name}' is never active: nothing transitions to "
                f"it and it declares no transition of its own, so its "
                f"`active_rules:` would never apply. Have a sibling mode "
                f"`transition_to: {mode.name}`, or put these rules on the "
                f"phase itself",
                mode.span,
            )


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
            if ref.delta == "override":
                bag.error(
                    f"`override {ref.name}` is not yet supported by the runtime "
                    f"(roadmap.md) — use `add`/`remove` deltas",
                    ref.span,
                )
    elif isinstance(item, n.LegalMoves):
        for name in item.move_types:
            if name not in LIBRARY_MOVE_TYPES:
                bag.error(f"legal_moves names unknown move type '{name}'", item.span)
    elif isinstance(item, n.Mode):
        for block in item.active_rules:
            _resolve_phase_item(block, sibling_names, known_rule_names, bag)
        for transition in item.transitions:
            _resolve_transition(transition, sibling_names, bag)
    elif isinstance(item, (n.Phase, n.StateBlock, n.BeforeEach, n.AfterEach)):
        # Phases recurse via the level walk; state blocks resolve later; hook
        # bodies are plain statement sequences with nothing item-level to check.
        pass
    else:
        # `item` is a statement — nothing to resolve at phase-item level. The
        # annotated assignment is the exhaustiveness pin: a new PhaseItem block
        # kind falls here and fails mypy until this function decides what to do
        # with it. (No statement walk hangs off this arm: with nothing to check
        # at the leaves, a walk recursing into every body would be vacuously
        # green — checking nothing while presenting as a guarantee.)
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
    # `Game.content_flavor` — the dispatch key for the flavor-aware Owner Guards
    # (decisions.md, "Component sets: cards and pieces").
    flavor: Flavor = "card"


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
        enums=enum_values(game.deck) if _component_known(game.deck) else SEAT_DIRECTION_VALUES,
        functions=VALUE_NAMES,
        # Card-literal validation asks "does this card EXIST in the deck",
        # so ranks derive from the deck like `suits` below — never from
        # `ranking:`, which is an ORDERING (optional, and legitimately
        # partial: it narrows the Rank move-param domain, not which cards
        # can be named). Deck-vs-ranking is the same two-source divergence
        # `_resolve_ranking` guards from the other side.
        ranks=rank_names(game.deck) if _component_known(game.deck) else frozenset(),
        suits=suit_names(game.deck) if _component_known(game.deck) else frozenset(),
        flavor=game.content_flavor,
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
        named: Iterator[object] | tuple[object, ...] | list[object],
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
    # Position names live in dedicated slots (zone index, type arg, parameter
    # type) — never bare expression position — so, like move_type names, they
    # need uniqueness but not the reserved-word sweep.
    check("position", game.positions)
    check("move_type", game.move_types)
    check("type", game.types, reserved=True)
    check("define", game.defines)
    check("function", game.functions, reserved=True)
    check("procedure", game.procedures)
    check("rule", game.rules)
    if game.state is not None:
        check("state variable", game.state.decls, reserved=True)
    phases: list[object] = []
    modes: list[object] = []
    for nd in _walk(game):
        if isinstance(nd, n.Phase):
            phases.append(nd)
        elif isinstance(nd, n.Mode):
            modes.append(nd)
        elif isinstance(nd, n.StateBlock) and nd is not game.state:
            check("state variable", nd.decls, reserved=True)
        elif isinstance(nd, n.TypeDef):
            check(f"field in type '{nd.name}'", nd.fields)
    check("phase", phases)
    # Modes are collected GAME-WIDE, not per phase, for the same reason phases
    # are: the runtime keys reached transitions by bare mode name in one
    # `RuntimeState.fired_transitions` set, and that set is cleared per
    # ITERATION of a `repeat until`-qualified phase — never on entering a
    # phase. A name reached under one phase is therefore still present when a
    # later one runs. Two phases each declaring a `done` would share that key —
    # one phase's transition would put the other phase straight into its
    # "after" mode, whose rules then apply from the start and whose "before"
    # mode never holds at all. Uniqueness here is what lets the runtime keep
    # using a bare name, so the checker's scope and the runtime's agree.
    check("mode", modes)


# The param-bearing declaration kinds: node type -> (how to reach them from a
# `Game`, the diagnostic noun, the reserved set their parameters check
# against). This table is pinned to the AST by tests/test_node_registry.py —
# every `Node` member with a `params` field must have a row — so a new
# parameterized declaration form cannot ship with its parameters silently
# exempt from the reserved-word sweep. The reach is a CALLABLE rather than an
# attribute name because a declaration form's holder need not be a top-level
# `Game` list: a `primitives { }` entry lives inside the block, and reaching
# it by attribute would mean either a special case here or a second top-level
# field mirroring the block. (The pronoun carve-out below: function
# and procedure bodies are hermetic — forbidden from READING the call-site
# pronouns — so naming a parameter after one is that error message's own
# prescribed fix, not a hijack. Move-type/rule bodies read the pronouns live,
# so all five stay reserved there. A Primitive's parameters read nothing at
# all — they label the declaration and key its `reads` binders — so the full
# set stays reserved for them. See `_check_reserved_params`.)
_ParamBearer = n.FunctionDef | n.ProcedureDef | n.MoveTypeDef | n.RuleDef | n.PrimitiveDecl


@dataclass(frozen=True, slots=True)
class _ParamBearing:
    """One param-bearing declaration kind's row."""

    reach: Callable[[n.Game], tuple[_ParamBearer, ...]]
    noun: str
    reserved: frozenset[str]
    library_field: str | None
    """The `n.Library` field holding this kind, or None for a kind a library
    cannot hold. `primitives { }` is a game clause and no `?library_item`, so
    a Primitive declaration has no library home — stated here so the family-
    library sweep derives which kinds it must cover instead of intersecting
    two name lists that happen to coincide."""
    scopes_body: bool
    """Whether DSL text sits inside these parameters' scope — the region where a
    bare `NameRef` means the parameter rather than a state variable. True for
    the four kinds `_classify_names` widens `cats.locals` for; False for a
    Primitive declaration, whose parameters label a Python signature and key its
    `reads` binders, so no DSL body is scoped by them and nothing can shadow.
    Declared rather than read off `library_field is None`, which happens to
    agree today and means something else entirely — the sweeps that must skip a
    body-less kind ask this question, so a sixth row answers it rather than
    inheriting an answer. Pinned against `_rewrite`'s own params-scoping arms by
    `tests/test_family_libraries.py::test_every_param_bearing_row_agrees_with_
    the_pass_that_scopes_it`."""


_PARAM_BEARING: dict[type, _ParamBearing] = {
    n.FunctionDef: _ParamBearing(
        lambda game: game.functions,
        "function parameter",
        RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS,
        "functions",
        scopes_body=True,
    ),
    n.ProcedureDef: _ParamBearing(
        lambda game: game.procedures,
        "procedure parameter",
        RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS,
        "procedures",
        scopes_body=True,
    ),
    n.MoveTypeDef: _ParamBearing(
        lambda game: game.move_types,
        "move-type parameter",
        RESERVED_VALUE_NAMES,
        "move_types",
        scopes_body=True,
    ),
    n.RuleDef: _ParamBearing(
        lambda game: game.rules,
        "rule parameter",
        RESERVED_VALUE_NAMES,
        "rules",
        scopes_body=True,
    ),
    n.PrimitiveDecl: _ParamBearing(
        lambda game: () if game.primitives is None else game.primitives.decls,
        "Primitive parameter",
        RESERVED_VALUE_NAMES,
        None,
        scopes_body=False,
    ),
}


def _check_reserved_params(game: n.Game, bag: DiagnosticBag) -> None:
    """Function/move-type/rule parameters are declarations `_check_duplicate_names`
    never reaches (they live on `.params`, not one of its top-level lists) but
    are reachable as a bare `NameRef` inside the body exactly like a state
    variable — a parameter named `empty` is just as unreferenceable via
    `x is empty` as a state variable of the same name would be.

    Function parameters are the ONE exception to `RESERVED_VALUE_NAMES` in
    full: `_CALL_SITE_PRONOUNS` (`actor`/`action`/`winner`) is exactly the
    set a function body is already forbidden from READING (the runtime
    clears them before a hermetic call — `_check_functions`'s "pass the
    value in as a parameter instead"), so naming a parameter after one is
    not a hijack, it is that error message's own prescribed fix — pinned by
    `tests/test_functions.py::test_function_param_does_not_leak_into_pronoun_sites`
    (`function lead(actor : Player) = score[actor]`). `state`/`active_rules`
    stay reserved for function parameters too: those two remain READABLE
    inside a function body, so a same-named parameter would still shadow
    them. `outcome` is reserved for them as well, for the separate reason
    `_KEYWORD_RESERVED` records — it is a clause keyword, not a pronoun a
    hermetic call clears. Move-type/rule bodies are not hermetic — they read
    `actor`/`action`/`winner` directly as live pronouns — so every reserved
    word stays reserved for their parameters."""
    for row in _PARAM_BEARING.values():
        for decl in row.reach(game):
            for p in decl.params:
                _check_reserved(p.name, row.noun, p.span, bag, row.reserved)


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
    """True iff `deck` names a known CARD deck — the gate on the card-specific
    resolve paths that read a rank/suit ORDER (`ranking:` membership and
    convention expansion). Deliberately False for a piece set, not only an
    unknown name: those clauses are rejected outright for a piece game by
    `_reject_card_content_clauses` before these paths run, so the gate need only
    admit real card decks."""
    from cardlang.runtime.values import DECKS

    return deck in DECKS


def _component_known(deck: str) -> bool:
    """True iff `deck` names a known component set of EITHER flavor — the gate
    on the flavor-agnostic namespaces (a game's suits, ranks, and bare enum
    values), which a piece set populates from its own axes exactly as a card
    deck does. `component_set` is the registry; an unknown name yields empty
    namespaces (its own diagnostic is `_resolve_component_set`'s)."""
    from cardlang.runtime.values import component_set

    return component_set(deck) is not None


def _resolve_component_set(game: n.Game, bag: DiagnosticBag) -> None:
    """An unknown or wrong-flavor component-set name is a diagnostic, never a
    raw registry raise from inside category building (the suit registry
    derives from the runtime deck table, which fails loudly for unknown
    names — correct at playout time, wrong as a designer-facing check); the
    categories fall back to an empty suit namespace so the rest of the
    file's diagnostics still collect. The unknown-name message lists only
    the sets of the CLAUSE'S flavor; a known name of the other flavor gets
    the cross-flavor message instead."""
    from cardlang.runtime.values import COMPONENT_SETS, DECKS, component_set

    cs = component_set(game.deck)
    if cs is None:
        if game.content_flavor == "card":
            bag.error(
                f"unknown deck '{game.deck}' — known decks: "
                f"{', '.join(sorted(DECKS))}",
                game.span,
            )
        else:
            piece_sets = sorted(
                name for name, c in COMPONENT_SETS.items() if c.flavor == "piece"
            )
            bag.error(
                f"unknown piece set '{game.deck}' — known piece sets: "
                f"{', '.join(piece_sets)}",
                game.span,
            )
    elif cs.flavor != game.content_flavor:
        if cs.flavor == "piece":
            bag.error(
                f"'{game.deck}' is a piece set — declare it with "
                f"`pieces: {game.deck}`, not `cards:`",
                game.span,
            )
        else:
            bag.error(
                f"'{game.deck}' is a card deck — declare it with "
                f"`cards: {game.deck}`, not `pieces:`",
                game.span,
            )


def _reject_card_content_clauses(game: n.Game, bag: DiagnosticBag) -> None:
    """`ranking:` and `trump:` read a deck's rank order and suits; a piece set
    has neither, so both are rejected NAMING THE KIND in a piece game (rather
    than the silent no-op the `_deck_known` gate on `_expand_ranking`/
    `_resolve_ranking` would otherwise give -- accepted-but-ignored, either the
    enumeration or the convention form). A card game is unaffected."""
    if game.content_flavor != "piece":
        return
    kind = content_kind_clause(game.content_flavor, game.deck)
    if game.ranking or game.ranking_convention is not None:
        bag.error(
            f"{kind} -- `ranking:` orders a deck's cards by rank, which a "
            f"piece set has no notion of; drop the clause",
            game.span,
        )
    if game.trump is not None:
        bag.error(
            f"{kind} -- `trump:` names the suit that beats others in a trick, "
            f"a card-play notion; drop the clause",
            game.span,
        )
    if game.card_points is not None:
        bag.error(
            f"{kind} -- `card_points` prices a deck's cards by rank, which a "
            f"piece set has no notion of; drop the clause",
            game.card_points.span or game.span,
        )
    if game.trick_order is not None:
        bag.error(
            f"{kind} — `trick_order` orders a deck's cards for trick play, "
            f"which a piece set has no notion of; drop the block",
            game.trick_order.span or game.span,
        )


def _resolve_direction(game: n.Game, bag: DiagnosticBag) -> None:
    """`direction:` is grammatically a bare NAME; an unguarded unknown value
    (`direction: anticlockwise`) would silently seat the turn ring clockwise —
    driver.py reads the clause as `clockwise = direction != "counterclockwise"`
    (Surface totality: accepted-with-different-semantics)."""
    from cardlang.runtime.values import GAME_DIRECTIONS

    if game.direction is not None and game.direction not in GAME_DIRECTIONS:
        options = " or ".join(f"`direction: {d}`" for d in GAME_DIRECTIONS)
        bag.error(
            f"unknown direction '{game.direction}' — declare {options} "
            f"(omitting the clause means clockwise)",
            game.span,
        )


def _expand_ranking(game: n.Game, bag: DiagnosticBag) -> n.Game:
    """Expand a `ranking:` convention keyword (`aces high`, …) into the
    operative strongest-first tuple: the `RANKING_CONVENTIONS` template
    filtered to the declared deck's ranks. Establishes: post-resolve,
    `game.ranking` IS the strength order for every game;
    `game.ranking_convention` survives only as the record of the source
    form (`ir.emit` prints it). Every consumer downstream of resolve
    (typecheck's Rank enum, `domains.py`'s move-param domain, the driver's
    `rank_index`, the OpenSpiel action space) reads the expanded tuple and
    never learns conventions exist.

    The Owner Guard: a convention is only meaningful for a deck whose ranks all
    have a place in the French template — for any other deck (tarot78's
    atouts, tichu56's specials, coup15's characters) filtering would
    silently produce a partial or empty ranking, an accepted-but-ignored
    declaration. Rejected here, in deck-membership terms, with the
    offending ranks named. An unknown deck already got its diagnostic in
    `_resolve_component_set`; the convention is left unexpanded then (empty
    `ranking`), matching how the rest of resolve degrades without a deck."""
    if game.ranking_convention is None:
        return game
    if not _deck_known(game.deck):
        return game
    from cardlang.runtime.values import RANKS, expand_ranking_convention
    from cardlang.runtime.values import deck_ranks as ordered_deck_ranks

    french = frozenset(RANKS)
    # The ORDERED runtime deck_ranks (first-appearance tuple), not this
    # kernel enums' frozenset wrapper: the offenders appear in the
    # diagnostic, and frozenset iteration is hash-seed-dependent — a
    # rejection golden built on it flakes across CI runs.
    offenders = [r for r in ordered_deck_ranks(game.deck) if r not in french]
    if offenders:
        bag.error(
            f"ranking: {game.ranking_convention} — deck '{game.deck}' has "
            f"ranks outside the standard A..2 set "
            f"({', '.join(offenders)}), so no named convention orders it; "
            f"enumerate the ranking explicitly instead",
            game.span,
        )
        return game
    return replace(
        game,
        ranking=expand_ranking_convention(game.ranking_convention, game.deck),
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
    move-parameter domain to fewer than the deck's ranks. Which cards reach
    a rank-strength read is a fact of zone contents, decidable only at play
    time, so a card whose rank falls outside a partial ranking is the
    RUNTIME's Owner Guard (`runtime/values.py`, `rank_strength`, the one
    lookup every `rank_index` consumer routes through), never this
    check's; the ledgers are tests/test_ranking_guard.py and
    tests/test_trump_slot_class.py."""
    if game.ranking_convention is not None:
        # Convention arm: `_expand_ranking` built the tuple from the deck's
        # own ranks filtered through a registry template — unique and
        # deck-member by construction, so re-validating it here would be
        # re-deriving an established fact. The convention's Owner Guards (French
        # deck, known spelling) live in `_expand_ranking` and the grammar.
        return
    if not game.ranking or not _deck_known(game.deck):
        return
    known = rank_names(game.deck)
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
            # A misspelled convention ("aces sideways", "high aces", a
            # newline inside "aces high") arrives HERE, as enumeration
            # words the deck doesn't know — the grammar falls through
            # rather than erroring, since the words are legal NAMEs. When
            # the bad entry is a word from some convention's spelling,
            # point at the closed set instead of leaving the author to
            # guess rank spellings.
            from cardlang.runtime.values import RANKING_CONVENTIONS

            conv_words = {
                w.lower()
                for key in RANKING_CONVENTIONS
                for w in (key, *key.replace("-", " ").split())
            }
            hint = (
                "  (did you mean a ranking convention? one of: "
                + ", ".join(sorted(RANKING_CONVENTIONS)) + ")"
                if rank.lower() in conv_words
                else ""
            )
            bag.error(
                f"ranking: names unknown rank '{rank}' — not a rank of deck "
                f"'{game.deck}' (known ranks: {', '.join(sorted(known))})"
                + hint,
                game.span,
            )


def _resolve_card_points(game: n.Game, bag: DiagnosticBag) -> None:
    """`card_points { }` keys must name real ranks of the declared deck, each
    at most once — `_resolve_ranking`'s two Owner Guards, applied to the
    table's key position. Unchecked, a typo (`ace` for `A`) would price the
    intended rank 0 (or the else value) forever, at runtime, with no
    diagnostic anywhere — the accepted-but-ignored class; and a duplicate key
    would silently last-win in the driver's materialized dict. Coverage is
    NOT required: the table may legitimately be sparse (Tichu prices five
    ranks; the rest read 0), exactly as `ranking:` may be partial. The else
    row needs no key check — `else` is the grammar's own keyword, excluded
    from the key terminal."""
    if game.card_points is None or not _deck_known(game.deck):
        return
    if game.content_flavor != "card":
        return  # `_reject_card_content_clauses` already named the kind
    known = rank_names(game.deck)
    seen: set[str] = set()
    for entry in game.card_points.entries:
        if entry.rank in seen:
            bag.error(
                f"card_points repeats rank '{entry.rank}' — each rank may "
                f"appear at most once (a duplicate would silently keep only "
                f"the last value)",
                entry.span or game.span,
            )
        seen.add(entry.rank)
        if entry.rank not in known:
            bag.error(
                f"card_points names unknown rank '{entry.rank}' — not a rank "
                f"of deck '{game.deck}' (known ranks: {', '.join(sorted(known))})",
                entry.span or game.span,
            )


# The callable containers a CONSUMPTION question must follow into, beyond the
# three `_DEFINITION_CONTAINERS` that `_reachable_nodes` already covers: a
# function body and a rule body both run, and both can hold the call that
# consumes a declaration. Keyed by the namespace `_REFERENCE_SLOTS` issues for
# each, so the sweep below finds them through the slot registry rather than by
# matching node kinds — a future callable added to that registry joins without
# an edit here.
_CALLABLE_CONTAINERS: dict[str, str] = {"function": "functions", "rule": "rules"}


# Every field of `n.Game`, classified by WHEN the engine evaluates what it
# holds. Exhaustive over the node's fields and pinned there
# (tests/test_trick_order.py::test_every_game_field_is_classified_for_consumption),
# so a field added to `Game` lands unclassified and fails rather than being
# silently left out of every consumption question.
#
#   "root"       -- reached at GAME level, outside any phase body, so a
#                   consumption walk must start here. The engine evaluates
#                   these directly (`driver.play_game`: the `loser:` terminal
#                   selection after the phases finish, the game-level `state`
#                   declaration defaults at setup) or they are inert today but
#                   could hold an expression tomorrow, which is the safe side
#                   to be on: an extra root can only over-count consumption,
#                   never miss it.
#   "phase"      -- the phase bodies, the walk's base.
#   "definition" -- a body that runs only when something reachable NAMES it;
#                   reached by the closure below, never as a root.
#   "declared"   -- the block whose consumers this question is ABOUT. Its own
#                   rows may not consume it, which R7 enforces separately.
_GAME_FIELD_ROLES: dict[str, str] = {
    "phases": "phase",
    "defines": "definition",
    "move_types": "definition",
    "procedures": "definition",
    "functions": "definition",
    "rules": "definition",
    "trick_order": "declared",
    # A declaration whose consumers are the game's `f(...)` calls, exactly as
    # a Trick Order's are: an entry's body is Python, so the block itself
    # evaluates nothing and must not be walked as a root.
    "primitives": "declared",
    "state": "root",  # declaration defaults, evaluated at setup
    "loser": "root",  # the terminal selection, evaluated after the phases
    "winner": "root",  # names a state variable today; walked for symmetry
    "board": "root",
    "zones": "root",
    "positions": "root",
    "card_points": "root",
    "types": "root",
    "uses": "root",
    "players": "root",
    "teams": "root",
    "name": "root",
    "deck": "root",
    "content_flavor": "root",
    "direction": "root",
    "ranking": "root",
    "ranking_convention": "root",
    "trump": "root",
    "max_length": "root",
    "span": "root",
}


def _consumption_roots(game: n.Game) -> Iterator[object]:
    """Every node a consumption question starts from: the phase bodies, plus
    each game-level field the engine evaluates outside them.

    Derived from `_GAME_FIELD_ROLES` rather than listed at the call site --
    the roots used to BE a list (phases and nothing else), and a game whose
    only consumer sat in `loser:` or in a game-level `state` default was told
    its declaration was read by nothing."""
    for phase in game.phases:
        yield from _walk(phase)
    for field, role in _GAME_FIELD_ROLES.items():
        if role == "root":
            yield from _walk(getattr(game, field))


def _consumption_reachable_nodes(game: n.Game) -> list[object]:
    """Every node the game can actually RUN — `_reachable_nodes` (the phase
    bodies plus the definition containers something reachable names) closed
    over the FUNCTION and RULE bodies those reach, transitively.

    The distinction this exists for: `_reachable_nodes` answers "does this
    body run" for defines, move types and procedures, and stops there. A
    function is not one of those, so a game whose only consumer of a
    declaration sits in a helper called from a phase looked, to a guard built
    on `_reachable_nodes` alone, exactly like a game with no consumer at
    all — and was refused. Rules have the same shape: a rule body runs when
    a reachable phase activates it.

    Used ONLY by consumption questions (is this declaration read by anything).
    A guard that REFUSES a construct validates it where it is WRITTEN and
    walks the whole text instead — over-reporting into dead code, which
    over-reports in the safe direction and can never miss."""
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)}
        for ns, field in _CALLABLE_CONTAINERS.items()
    }
    nodes: list[object] = list(_consumption_roots(game))
    nodes.extend(
        node
        for container in _reachable_definitions(game).values()
        for node in _walk(container)
    )
    reached: set[tuple[str, str]] = set()
    frontier: list[object] = list(nodes)
    while frontier:
        node = frontier.pop()
        for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
            namespace = slot_namespace(node, field_name)
            if namespace is None or namespace not in pools:
                continue
            pool = pools[namespace]
            for name in slot_strings(node, field_name):
                key = (namespace, name)
                target = pool.get(name)
                if target is None or key in reached:
                    continue
                reached.add(key)
                body = list(_walk(target))
                nodes.extend(body)
                frontier.extend(body)
    return nodes


def _trick_order_rounds(game: n.Game) -> list[n.TrickRound]:
    """Every trick round the game's TEXT holds. The refusal half of the
    partition validates a round WHERE IT IS WRITTEN, so a round in a container
    nothing invokes is refused too: over-reporting in the safe direction,
    which can never miss. Consumption asks the other question and uses
    `_consumption_reachable_nodes`."""
    return [nd for nd in _walk(game) if isinstance(nd, n.TrickRound)]


def _row_order(key: str) -> int:
    """A row's position in the language's reference order — the order rows are
    READ in, fixed by `TRICK_ORDER_ROWS`, never the textual one."""
    return [k for k, _ in TRICK_ORDER_ROWS].index(key)


def _undeclared_primitive_hint(game: n.Game, func: str) -> str:
    """The half-sentence an unknown call earns when the name IS a Primitive
    some other game declares. Without it a declared game's author reads
    "unknown function" about a name they can see in the registry, and the
    regime — the thing that actually refused it — stays invisible."""
    if regime(game) is not Regime.DECLARED or func not in PRIMITIVE_CALL_FUNCS:
        return ""
    return (
        f" — `{func}` is a Primitive another game declares, and this game's "
        f"`primitives {{ }}` block does not; declare it here to call it"
    )


def _check_primitives_block(game: n.Game, bag: DiagnosticBag) -> None:
    """The `primitives { }` block, validated whole.

    Everything a declaration can be wrong about is settled here, in the compile
    stage's own channel, because every one of them is a fact about the game
    text against a registry the front end holds: the entry's name against the
    game's other namespaces and the implementation index, its declared types
    against the spellable set, and each `reads` name against the game's own
    `zones { }` and `state { }`. What is deliberately NOT settled here is
    whether a declared read SUFFICES for the implementation — that is a fact
    about Python, and only running the game shows it."""
    if game.primitives is None:
        return
    declarable = declarable_type_names(game)
    own_definitions = (
        {f.name for f in game.functions}
        | {p.name for p in game.procedures}
        | {m.name for m in game.move_types}
        | {d.name for d in game.defines}
        | {r.name for r in game.rules}
    )
    seen: set[str] = set()
    for decl in game.primitives.decls:
        _check_primitive_name(game, decl, own_definitions, seen, bag)
        seen.add(decl.name)
        for slot, type_name in [("return type", decl.return_type)] + [
            (f"parameter `{p.name}`", p.type_name) for p in decl.params
        ]:
            bare = type_name.removesuffix("?")
            if bare not in declarable:
                bag.error(
                    f"`{decl.name}`'s {slot} names `{bare}`, which a "
                    f"`primitives` entry may not spell — a declared signature "
                    f"is what freezes the arguments, so its types are the "
                    f"declared-type names ({', '.join(sorted(declarable))}); "
                    f"issue #472 tracks the shapes that have no spelling",
                    decl.span,
                )
        _check_primitive_reads(game, decl, bag)


def _check_primitive_name(
    game: n.Game,
    decl: n.PrimitiveDecl,
    own_definitions: set[str],
    seen: set[str],
    bag: DiagnosticBag,
) -> None:
    """One entry's NAME, against every namespace it could collide with and
    against the implementation index. Ordered so the most specific reason
    speaks: a walled namespace before an unknown name, because the name IS a
    Primitive and "nothing implements it" would be false."""
    if decl.name in seen:
        bag.error(
            f"`primitives` declares one `{decl.name}` entry — the repeat would "
            f"silently replace the first; keep one",
            decl.span,
        )
        return
    if decl.name in BUILTIN_CALL_FUNCS:
        bag.error(
            f"`{decl.name}` is a Builtin the language ships, so a "
            f"`primitives` entry may not declare it — a call would resolve "
            f"against two homes at once; rename the Primitive",
            decl.span,
        )
        return
    if decl.name in own_definitions:
        bag.error(
            f"`{decl.name}` is already defined in this game, so a `primitives` "
            f"entry may not declare it too — a call would name both; rename one",
            decl.span,
        )
        return
    walled = walled_namespace_of(decl.name)
    if walled is not None:
        bag.error(
            f"`{decl.name}` is {walled}, not a call-position Primitive, so "
            f"the `primitives` block cannot declare it — its signature is the "
            f"mechanic's, not a parameter list; the round slots take their own "
            f"declaration form (issue #142)",
            decl.span,
        )
        return
    contract = undeclarable_contract(decl.name)
    if contract is not None:
        bag.error(
            f"`{decl.name}`'s implementation does not answer the declared "
            f"Primitive contract (it is {contract.value}), so a `primitives` "
            f"entry cannot bind it — see issue "
            f"{'#142' if contract is InvocationContract.EMITTING else '#473'}",
            decl.span,
        )
        return
    if unimplemented(frozenset({decl.name})):
        bag.error(
            f"nothing implements the Primitive `{decl.name}` — a "
            f"`primitives` entry names Python the engine can find "
            f"(cardlang/primitives_block.py, PRIMITIVE_IMPLEMENTATIONS); check "
            f"the spelling, or register the implementation",
            decl.span,
        )


def _check_primitive_reads(
    game: n.Game, decl: n.PrimitiveDecl, bag: DiagnosticBag
) -> None:
    """One entry's `reads` clause: every name classified, every binder bound.

    The engine-structural half of what a Primitive sees (`EngineFacts`) is not
    spellable here, and its field names are refused at THIS site rather than
    left to read as ordinary unknowns, so the deferral is loud and cites its
    issue."""
    params = {p.name for p in decl.params}
    # A clause is a SET of declarations: the row it becomes is keyed by name,
    # and so is the per-call key map, so a repeat is not additive — one entry
    # silently wins. `hand, hand[p]` would play to completion returning a
    # value computed from ONE hand while the declaration says every hand, which
    # is a wrong answer with no failure anywhere. Refused as a multiset before any
    # per-entry check, so the diagnostic names the repeat rather than whichever
    # of the two copies happens to be malformed.
    # The parameter list is a SET for the same reason, one slot over: the type
    # pass reads it as a map (last wins) while the driver resolves a binder by
    # its INDEX (first wins), so a repeat makes the two halves of one
    # declaration disagree about which parameter a binder names.
    seen_params: set[str] = set()
    for param in decl.params:
        if param.name in seen_params:
            bag.error(
                f"`{decl.name}` declares the parameter `{param.name}` more than "
                f"once — each parameter is named once, and the repeat would "
                f"silently replace the first; rename one",
                param.span or decl.span,
            )
            return
        seen_params.add(param.name)
    seen: set[str] = set()
    for read in decl.reads:
        if read.name in seen:
            bag.error(
                f"`{decl.name}` reads `{read.name}` more than once — a `reads` "
                f"clause names each declaration at most once, and the repeat "
                f"would silently replace the first; keep one",
                read.span or decl.span,
            )
            return
        seen.add(read.name)
    # A PURE implementation never receives the bundle (`primitives.call_declared`
    # hands it the coerced arguments and nothing else), so a `reads` clause on
    # one declares a dependency the dispatch cannot honour — accepted-and-
    # ignored, which is the defect class this block exists to end.
    impl = PRIMITIVE_IMPLEMENTATIONS.get(decl.name)
    if decl.reads and impl is not None and impl.contract is InvocationContract.PURE:
        bag.error(
            f"`{decl.name}` is implemented pure over its arguments, so it "
            f"never receives the declared reads — a `reads` clause on it would "
            f"be accepted and ignored; drop the clause",
            decl.span,
        )
        return
    for read in decl.reads:
        if read.name in ambiguous_read_names(game):
            bag.error(
                f"`{decl.name}` reads `{read.name}`, which this game declares "
                f"as BOTH a state variable and a zone — the declaration cannot "
                f"say which, and the two are materialized into different halves "
                f"of what the implementation receives; rename one of the two",
                read.span or decl.span,
            )
            continue
        if read.name in shadowed_state_names(game):
            bag.error(
                f"`{decl.name}` reads `{read.name}`, which the game AND a phase "
                f"both declare — the declaration cannot say which, and at run "
                f"time the phase's value wins while that phase is active; "
                f"rename one of the two",
                read.span or decl.span,
            )
            continue
        kind = classify_read(game, read.name)
        if kind is None:
            if read.name in phase_local_state_names(game):
                bag.error(
                    f"`{decl.name}` reads `{read.name}`, which a PHASE declares "
                    f"— a Primitive's row is materialized on every call, so a "
                    f"phase-local variable is readable only while that phase "
                    f"runs; declare it in the game's `state {{ }}` block, or "
                    f"pass the value as an argument",
                    read.span or decl.span,
                )
                continue
            hint = (
                f" — `{read.name}` is an engine fact a Primitive receives "
                f"whole today; the `reads` clause names this game's own zones "
                f"and state variables only (issue #474)"
                if read.name in engine_fact_names()
                else ""
            )
            bag.error(
                f"`{decl.name}` reads `{read.name}`, which this game declares "
                f"in neither `zones {{ }}` nor `state {{ }}`{hint}",
                read.span or decl.span,
            )
            continue
        if read.binder is None:
            continue
        if kind not in BINDABLE_READ_KINDS:
            bag.error(
                f"`{decl.name}` reads `{read.name}[{read.binder}]`, but "
                f"`{read.name}` is a {kind.value} — it has no instances to key, "
                f"so write `{read.name}`",
                read.span or decl.span,
            )
        elif read.binder not in params:
            bag.error(
                f"`{decl.name}` reads `{read.name}[{read.binder}]`, but "
                f"`{read.binder}` is not one of its parameters "
                f"({', '.join(p.name for p in decl.params) or 'it declares none'}) "
                f"— an index binder keys the instance the CALL names",
                read.span or decl.span,
            )


def _check_trick_order_partition(game: n.Game, bag: DiagnosticBag) -> None:
    """The presence partition, both directions: a game either declares a
    [[trick-order]] and names the winner and calls that read it, or declares
    none and names the round-configured ones. Never a mixture.

    The Owner Guard for a class that would otherwise be silent in both
    directions. WITH a block, the round-configured trumps (`trump:`, a round's
    `trump` clause) and the winners that read them are not merely redundant —
    they describe a DIFFERENT order from the one the block declares, and the
    engine would quietly run one of the two. WITHOUT a block, every gated name
    reads a table that was never materialized, which is a crash at play time
    rather than a diagnostic at check time.

    A block nobody reads is refused too (R7): an unread `trick_order { }` is
    the accepted-but-ignored class in its purest form — a whole declared order
    the game never consults. Consumption counts readers OUTSIDE the block, so
    rows reading each other's readers never make a block look live.
    """
    if game.content_flavor != "card":
        return  # `_reject_card_content_clauses` already named the kind
    if game.trick_order is None:
        # --- without a block: no gated name may appear -----------------------
        for rnd in _trick_order_rounds(game):
            if rnd.winner_fn in TRICK_ORDER_GATED_WINNERS:
                others = ", ".join(sorted(TRICK_WINNER_NAMES - TRICK_ORDER_GATED_WINNERS))
                bag.error(
                    f"round winner {rnd.winner_fn} reads the game's "
                    f"`trick_order {{ }}` block, but this game declares none — "
                    f"declare one (rows "
                    + ", ".join(f"`{k}:`" for k, _ in TRICK_ORDER_ROWS)
                    + f"), or name {others}",
                    rnd.span,
                )
        for call in _gated_calls(game):
            reader_hint = ""
            for row_key, reader in TRICK_ORDER_ROWS:
                if call.func == reader:
                    reader_hint = (
                        f" (`{reader}(card)` is the reader of the block's "
                        f"`{row_key}:` row)"
                    )
            bag.error(
                f"`{call.func}(...)` reads the game's `trick_order {{ }}` "
                f"block, but this game declares none — declare one"
                + reader_hint,
                call.span or game.span,
            )
        return

    # --- with a block: the round-configured names are refused ----------------
    if game.trump is not None:
        remedy = ""
        if _deck_known(game.deck) and game.trump in suit_names(game.deck):
            remedy = f" (for a fixed suit, `trump: card.suit is {game.trump}`)"
        bag.error(
            f"`trump: {game.trump}` beside a `trick_order {{ }}` block — with a "
            f"Trick Order the block's `trump:` row is the trump{remedy}; drop "
            f"the game-level clause",
            game.span,
        )
    for rnd in _trick_order_rounds(game):
        if rnd.trump is not None:
            bag.error(
                "round `trump` clause beside a `trick_order { }` block — the "
                "block's `trump:` row is the trump; drop the clause",
                rnd.span,
            )
        if rnd.winner_fn in TRICK_ORDER_EXCLUDED_WINNERS:
            gated = ", ".join(sorted(TRICK_ORDER_GATED_WINNERS))
            bag.error(
                f"round winner {rnd.winner_fn} beside a `trick_order {{ }}` "
                f"block — the block declares the Trick Order, and {gated} is "
                f"the winner that reads it; name that, or drop the block",
                rnd.span,
            )
        if (
            rnd.early_termination is not None
            and rnd.early_termination not in TRICK_ORDER_EARLY_PREDICATES
            and rnd.winner_fn in TRICK_ORDER_GATED_WINNERS
        ):
            bag.error(
                f"`early` clause on winner {rnd.winner_fn} — `early` "
                f"predicates read the literal led suit, and a Trick Order's "
                f"follow class may differ; no game has needed both — drop the "
                f"clause",
                rnd.span,
            )
    # EVERY registered climbing query, not the `ranking:`-reading subset: a
    # climb query carries its own card order whether it reads `rank_index`
    # (president's) or hard-codes one (the bigtwo_* and tichu_* engines), and
    # either way a game naming one beside a Trick Order has two orders that
    # the engine runs side by side. Derived from the two registries by union
    # so a query added to either is refused without an edit here.
    climb_queries = PRIMITIVE_CLIMB_LEADS | PRIMITIVE_CLIMB_FOLLOWS
    for nd in _walk(game):
        if isinstance(nd, n.ClimbRound):
            for query_slot, fname in (
                ("combinations", nd.combos_fn),
                ("follows", nd.follows_fn),
            ):
                if fname in climb_queries:
                    bag.error(
                        f"climb round `{query_slot} {fname}` beside a "
                        f"`trick_order {{ }}` block — the climbing round's "
                        f"queries carry their own order; a game with a Trick "
                        f"Order cannot also name {fname} (the climb family "
                        f"reading the Trick Order is issue #251)",
                        nd.span,
                    )
    for nd in _walk(game):
        if isinstance(nd, n.Call) and nd.func in TRICK_ORDER_EXCLUDED_FUNCS:
            arg = "pile"
            if nd.args and isinstance(nd.args[0], n.NameRef):
                arg = nd.args[0].name
            bag.error(
                f"`{nd.func}(...)` beside a `trick_order {{ }}` block — the "
                f"block's rows are the trick order; call "
                f"`{min(TRICK_ORDER_GATED_WINNERS)}({arg})`",
                nd.span or game.span,
            )
    # R7: the block must have a consumer OUTSIDE its own rows.
    #
    # Consumption counts what the game RUNS, not what its text holds — and
    # "runs" has to include function and rule bodies, or a game whose only
    # consumer sits in a helper is told its block is read by nothing
    # (`_consumption_reachable_nodes`, which says why). This is the ONE
    # reachability notion the whole partition uses for that question; the
    # refusal guards above deliberately use the other one, walking the text so
    # a gated name in a dead container is refused where it is written.
    rows = set(game.trick_order.rows)
    running = _consumption_reachable_nodes(game)
    outside = [
        nd
        for nd in running
        if isinstance(nd, n.Call)
        and nd.func in TRICK_ORDER_GATED_FUNCS
        and not any(nd in set(_walk(r)) for r in rows)
    ]
    slot = any(
        isinstance(nd, n.TrickRound) and nd.winner_fn in TRICK_ORDER_GATED_WINNERS
        for nd in running
    )
    if not slot and not outside:
        gated = ", ".join(f"`{f}`" for f in sorted(TRICK_ORDER_GATED_FUNCS))
        bag.error(
            f"`trick_order {{ }}` is read by nothing — no round names "
            f"{min(TRICK_ORDER_GATED_WINNERS)}, and nothing outside the block "
            f"calls {gated}; name {min(TRICK_ORDER_GATED_WINNERS)} on a trick "
            f"round or call it over the trick pile, or drop the block",
            game.trick_order.span or game.span,
        )


def _gated_calls(game: n.Game) -> list[n.Call]:
    return [
        nd
        for nd in _walk(game)
        if isinstance(nd, n.Call) and nd.func in TRICK_ORDER_GATED_FUNCS
    ]


def _check_trick_order_rows(game: n.Game, bag: DiagnosticBag) -> None:
    """Every row of a [[trick-order]] is HERMETIC: a pure function of the card
    and public state.

    The Owner Guard for that property, and the reason the construct can be
    trusted at all. A row is asked from three places under three different live
    frames — the legality filter (mid-decision, an actor bound), the winner
    slot (end of trick, a `winner` in scope), and a hand-rolled body (any
    frame, or none) — so a row whose answer depended on WHO was asking, or on
    how far the trick had run, would give different orders to the filter and to
    the winner. Every refusal below removes one way for that to happen:

    * no pronoun of any namespace (`_PRONOUNS`), so the answer cannot vary with
      the live frame;
    * no `choose`, so a row is a fact and never a decision site (an info-set
      leak: a decision inside a legality computation);
    * only zones that project identity to EVERY observer, and never a bare
      per-player family, so a row cannot read a card some observer cannot see;
    * only the row-callable Builtins (`TRICK_ORDER_ROW_CALLS`) and the readers
      of EARLIER rows, so a row cannot reach the order it helps define.

    Each refusal follows the call graph, so a row that reaches the forbidden
    thing THROUGH a designer function is refused with the function named — a
    row's hermeticity is a property of what it can reach, not of its own text.
    """
    if game.trick_order is None:
        return
    fn_names = {f.name for f in game.functions}
    fns = {f.name: f for f in game.functions}
    # The zone references that carry a subscript (`won[0]`). A family read is
    # BARE — the acting player's instance, which a row does not have — only
    # when it is not one of these; identity, because two reads of the same zone
    # are distinct nodes and only one of them may be subscripted.
    subscripted = {
        id(nd.obj)
        for nd in _walk(game)
        if isinstance(nd, n.Subscript) and isinstance(nd.obj, n.NameRef)
    }
    calls: dict[str, set[str]] = {
        f.name: {
            c.func for c in _walk(f.body) if isinstance(c, n.Call) and c.func in fn_names
        }
        for f in game.functions
    }

    for row in game.trick_order.rows:
        # (node, the function it was reached through, or None when direct)
        sites: list[tuple[object, str | None]] = [(nd, None) for nd in _walk(row.body)]
        direct = {
            c.func
            for c in _walk(row.body)
            if isinstance(c, n.Call) and c.func in fn_names
        }
        for name in sorted(fn_names):
            if any(f == name or _reaches(f, name, calls) for f in direct):
                sites.extend((nd, name) for nd in _walk(fns[name].body))

        def through(fn: str | None) -> str:
            return f" through function `{fn}`" if fn else ""

        for nd, fn in sites:
            if isinstance(nd, n.NameRef) and nd.ref_kind == "pronoun":
                # actor/action/winner reached through a function are already
                # refused by `_check_functions`' own hermeticity guard, which
                # owns that class; this names the ROW as well, and is the only
                # guard for the other two.
                if fn is not None and nd.name in _CALL_SITE_PRONOUNS:
                    continue
                bag.error(
                    f"`{row.key}:` reads the pronoun '{nd.name}'"
                    + through(fn)
                    + f" — a Trick Order row is hermetic: it is asked from the "
                    f"legality filter, the winner slot and a hand-rolled body "
                    f"under different live frames, so it may read no pronoun "
                    f"({', '.join(sorted(_PRONOUNS))}); a card's trick order is "
                    f"a fact of the card and public state alone",
                    nd.span or row.span,
                )
            elif isinstance(nd, n.Choose):
                bag.error(
                    f"`{row.key}:` makes a `choose`"
                    + through(fn)
                    + " — a Trick Order row is a fact, not a decision: it may "
                    "not choose",
                    nd.span or row.span,
                )
            elif isinstance(nd, n.NameRef) and nd.ref_kind == "zone":
                _check_row_zone_read(
                    game, row, nd, fn, bag, through, id(nd) in subscripted
                )
            elif isinstance(nd, n.Call):
                _check_row_call(game, row, nd, fn, bag, through)


def _check_row_zone_read(
    game: n.Game,
    row: n.TrickOrderRow,
    nd: n.NameRef,
    fn: str | None,
    bag: DiagnosticBag,
    through: Callable[[str | None], str],
    is_subscripted: bool,
) -> None:
    decl = next((z for z in game.zones if z.name == nd.name), None)
    if decl is None:
        return
    ztype = decl.type_ref.name
    if ztype not in LIBRARY_ZONE_TYPES:
        return
    if not identity_to_all(ztype):
        bag.error(
            f"`{row.key}:` reads zone '{nd.name}' ({ztype})"
            + through(fn)
            + ", which does not project identity to every observer — a Trick "
            "Order is public by construction and may read only fully public "
            "zones",
            nd.span or row.span,
        )
    elif decl.index is not None and not is_subscripted:
        # A bare per-player family read sugars to the ACTING player's instance
        # — and a row has no acting player, by construction (the runtime
        # clears it, `evaluate.row_context`). Named here rather than left to
        # that Shadow Guard so the fix is a subscript the author can write.
        # A player-typed state variable of THIS game, so the suggested
        # subscript is a name the designer can actually write.
        example = "declarer"
        if game.state is not None:
            example = next(
                (v.name for v in game.state.decls if v.type_name == "Player"), example
            )
        bag.error(
            f"`{row.key}:` reads `{nd.name}` bare (the acting player's "
            f"instance)"
            + through(fn)
            + f" — a Trick Order row has no acting player; subscript it with a "
            f"player the state names (`{nd.name}[{example}]`)",
            nd.span or row.span,
        )


def _check_row_call(
    game: n.Game,
    row: n.TrickOrderRow,
    nd: n.Call,
    fn: str | None,
    bag: DiagnosticBag,
    through: Callable[[str | None], str],
) -> None:
    if nd.func in declared_names(game):
        # A [[primitive]] this game's own `primitives { }` block declares.
        # Uncallable from a row for the reason every registered Primitive is:
        # a row is HERMETIC, a pure function of the card and public state, and
        # a Primitive reads whatever its `reads` clause names — a concealed
        # hand among them. The registered half is uncallable because
        # `TRICK_ORDER_ROW_CALLS` admits none of it; the declared half is not
        # in that registry at all, so it needs this arm rather than inheriting
        # the exclusion.
        bag.error(
            f"`{row.key}:` calls the declared Primitive `{nd.func}(...)`"
            + through(fn)
            + " — a Trick Order row reads the card and public state only, and "
            "a Primitive reads whatever its `reads` clause names",
            nd.span or row.span,
        )
        return
    if nd.func in {f.name for f in game.functions}:
        # A designer function, walked on its own. The arm below meant to admit
        # one all along and used `not in CALL_FUNCS` as the proxy; a declared
        # game may now legally name a function after an absent Primitive, and
        # that spelling IS in `CALL_FUNCS`, so the test is stated directly.
        return
    if nd.func in TRICK_ORDER_ROW_CALLS or nd.func not in CALL_FUNCS:
        return  # allowed, or a name no native registry claims
    if nd.func in TRICK_ORDER_GATED_FUNCS - frozenset(TRICK_ORDER_READERS):
        bag.error(
            f"`{row.key}:` calls `{nd.func}(...)`, which reads every row of "
            f"the Trick Order"
            + through(fn)
            + " — a row may not read the Trick Order it defines",
            nd.span or row.span,
        )
        return
    if nd.func in TRICK_ORDER_READERS:
        reader_row = next(k for k, r in TRICK_ORDER_ROWS if r == nd.func)
        if reader_row == row.key:
            bag.error(
                f"`{row.key}:` reads its own reader `{nd.func}(...)`"
                + through(fn),
                nd.span or row.span,
            )
        elif _row_order(reader_row) > _row_order(row.key):
            order = ", then ".join(f"`{k}:`" for k, _ in TRICK_ORDER_ROWS)
            bag.error(
                f"`{row.key}:` reads `{nd.func}(...)`, the reader of a row "
                f"that comes after it in the Trick Order"
                + through(fn)
                + f" — the rows are read in one order, {order}, whatever order "
                f"they are written in, and a row may read only the readers of "
                f"the rows before it; spell the fact in this row, or move it "
                f"to the later one",
                nd.span or row.span,
            )
        return
    bag.error(
        f"`{nd.func}(...)` may not be called from a Trick Order row"
        + through(fn)
        + " — a row reads the card and public state only",
        nd.span or row.span,
    )


def _check_arrival_record_pile_args(game: n.Game, bag: DiagnosticBag) -> None:
    """Every [[arrival-record]] read names a fully public zone, STATICALLY.

    The Owner Guard for the provenance rule (issue #256's decision-context
    rule, tightened here to a static check): a winner is named from who played
    what, so the pile it reads must be one whose arrivals every observer can
    derive from their own stream. Two facts must hold, and both are decidable
    without running anything — the argument is a zone REFERENCE (not a
    computed value, whose zone nobody can name until play time), and that
    zone's declared type projects identity to all.

    Deciding them here rather than at the call is what makes the proof
    harness's provenance derivation possible: it walks the checked AST for
    these calls and reads the pile's zone name off the argument
    (`tests/openspiel_ready/harness.py`), which is only sound because the
    argument is guaranteed to BE a name. The runtime's matching guards become
    Shadow Guards behind this one."""
    zones = {z.name: z for z in game.zones}
    for nd in _walk(game):
        if not isinstance(nd, n.Call) or nd.func not in ARRIVAL_RECORD_CALLS:
            continue
        idx = ARRIVAL_RECORD_CALLS[nd.func]
        arg = nd.args[idx] if len(nd.args) > idx else None
        name: str | None = None
        if isinstance(arg, n.NameRef) and arg.ref_kind == "zone":
            name = arg.name
        elif (
            isinstance(arg, n.Subscript)
            and isinstance(arg.obj, n.NameRef)
            and arg.obj.ref_kind == "zone"
        ):
            name = arg.obj.name
        if name is None:
            bag.error(
                f"`{nd.func}` reads the Arrival Record of its pile argument, "
                f"which must name a zone (`{nd.func}(trick_pile)`); got "
                f"{_arg_shape(arg)}",
                nd.span or game.span,
            )
            continue
        decl = zones.get(name)
        if decl is None or decl.type_ref.name not in LIBRARY_ZONE_TYPES:
            continue
        ztype = decl.type_ref.name
        if not identity_to_all(ztype):
            bag.error(
                f"`{nd.func}` over '{name}' ({ztype}): the zone type does not "
                f"project identity to every observer, so its provenance is not "
                f"derivable from any observer's stream — a winner may only be "
                f"named over a fully public pile",
                nd.span or game.span,
            )


def _arg_shape(arg: object) -> str:
    """How a rejected pile argument is described back to the author — its
    SHAPE, in the language's words, never a node class name."""
    match arg:
        case None:
            return "no argument"
        case n.IntLit() | n.StrLit():
            return "a literal"
        case n.Call() as c:
            return f"the value of `{c.func}(...)`"
        case n.CardQuery():
            return "a card query"
        case n.NameRef() as r:
            return f"'{r.name}', which is not a zone"
        case _:
            return "an expression"


def _resolve_trump(game: n.Game, bag: DiagnosticBag) -> None:
    """`trump: NAME` names a suit of the declared deck, and some trick round
    reads it — the two Owner Guards of the game-level trump slot.

    Membership: the slot is grammatically a bare NAME (`trump: bogus`, a
    rank, a suit of some other deck all parse), and the runtime compares the
    string against card suits — an unknown value matched nothing and the game
    silently played no-trumps (Surface totality: accepted-with-different-
    semantics). Same two-source rule as `_resolve_ranking` and the card
    literal's suit: the value derives from the deck (`suit_names`), so a
    deck's pseudo-suits (tarot78's `excuse`, five_hundred43's `joker`) are
    members — they are the deck's suits, the same domain `Suit` types over.
    `none` is a NAME too, and used to parse as the STRING "none": refused
    with the omission that means no trump, rather than accepted for the
    coincidence that no suit is spelled "none".

    Consumption: `game.trump` reaches the runtime as the trick form's default
    trump — the trump of a round that names a trump-reading winner and
    supplies no `trump` clause of its own (`runtime/mechanics.py`,
    `TrickForm`). That round is the value's only reader in the corpus. The
    form ALSO publishes it as `state["trump"]` (mechanics.py), a channel any
    Primitive behind a trick round could read back and this guard cannot
    see; Belote's two were the corpus instance, and both left with the
    Trick Order migration (issue #250 PR 4) — the surviving one reads the
    GAME's own `trump_suit` state variable instead. So the reader model is
    exact today, and a game that revived the `state["trump"]` channel under
    a blind winner would meet a FALSE REFUSAL here: over-reach in the safe
    direction, never a miss.

    A `trump:` no round reads — the game runs no trick round; every round's
    winner ignores its trump (`TRUMP_READING_WINNERS`' complement); every
    reading round overrides with its own clause — is accepted-but-ignored,
    the class this repo ranks worst, and is refused naming what would read
    it. No corpus game holds the shape: French Tarot's `trump: atouts` beside
    a trump-blind winner was the instance, and it retired with the game's
    Trick Order (issue #250 PR 5), which refuses a game-level `trump:` beside
    a block outright.

    Consumption counts the rounds the game RUNS, not the rounds its text
    holds: a `round` is a `statement`, and the three definition forms hold
    `statement*`, so a reading round inside a `define` no `produces:` names
    (or a `move_type` no `offer` names) made a provably inert clause look
    consumed. `_reachable_nodes` is the Owner of that question. Its sibling
    guards need no such filter and are not shadowing one: the membership
    check above is over `game.trump`, a game clause sitting in no container
    at all, and the round-clause guards (`_validate_refs`' winner-slot arm,
    typecheck's `_check_round_trump`) validate a clause WHERE IT IS WRITTEN —
    a dead container's clause is checked too, which over-reports in the safe
    direction and can never miss.

    A round whose winner is not a trick winner at
    all is `_validate_refs`'s diagnostic; the dead-clause question is not
    asked over a game with one, so it never reports on top of that error.
    A piece game's `trump:` is `_reject_card_content_clauses`'s, and an
    unknown deck is `_resolve_component_set`'s (the value has no domain to
    check against, so this returns, as `_resolve_ranking` does)."""
    if game.trump is None or game.content_flavor != "card" or not _deck_known(game.deck):
        return
    if game.trick_order is not None:
        # A block game's `trump:` is `_check_trick_order_partition`'s cell (R1),
        # whose message names the block and the row that replaces the clause.
        # Returning here is what keeps the two from co-reporting on one defect.
        return
    if game.trump == "none":
        bag.error(
            "trump: none — no trump is the ABSENT clause: drop `trump: none` "
            "(a round that turns a trump per hand writes `trump <expr>` on the "
            "round, where `none` means no trump)",
            game.span,
        )
        return
    known = suit_names(game.deck)
    if game.trump not in known:
        bag.error(
            f"trump: names unknown suit '{game.trump}' — not a suit of deck "
            f"'{game.deck}' (known suits: {', '.join(sorted(known))})",
            game.span,
        )
        return
    rounds = [nd for nd in _reachable_nodes(game) if isinstance(nd, n.TrickRound)]
    if any(r.winner_fn not in TRICK_WINNER_NAMES for r in rounds):
        return
    if any(r.trump is None and r.winner_fn in TRUMP_READING_WINNERS for r in rounds):
        return
    readers = ", ".join(sorted(TRUMP_READING_WINNERS))
    # A round that WOULD have inherited the clause but sits in a body nothing
    # invokes: without this the author is told "the game runs no trick round"
    # while looking straight at one, which is a misleading message rather than
    # merely a missing one.
    reached = _reachable_definitions(game)
    stranded = sorted(
        {
            namespace
            for cls, (field, namespace) in _DEFINITION_CONTAINERS.items()
            for d in getattr(game, field)
            if (namespace, d.name) not in reached
            and any(
                isinstance(x, n.TrickRound)
                and x.trump is None
                and x.winner_fn in TRUMP_READING_WINNERS
                for x in _walk(d)
            )
        }
    )
    parts: list[str] = []
    if rounds:
        blind = sorted({r.winner_fn for r in rounds if r.winner_fn not in TRUMP_READING_WINNERS})
        if blind:
            parts.append(
                f"a trick round names a winner that reads no trump ({', '.join(blind)})"
            )
        if any(r.trump is not None and r.winner_fn in TRUMP_READING_WINNERS for r in rounds):
            parts.append(
                "every trick round whose winner reads a trump supplies its "
                "own `trump` clause"
            )
    elif not stranded:
        parts.append(
            "the game runs no trick round (a hand-rolled trick passes its "
            "trump to `highest_trump_or_led_suit(pile, trump)` itself)"
        )
    if stranded:
        parts.append(
            f"a trick round that would read it sits in a definition nothing "
            f"reaches ({', '.join(stranded)}) — a `define` body runs only where "
            f"a `produces:` names it, a `move_type` effect only where an "
            f"`offer` names it"
        )
    why = "; ".join(parts)
    bag.error(
        f"trump: {game.trump} is read by no trick round — {why}. The game-level "
        f"`trump:` is the default trump of a `round … winner` whose winner "
        f"reads a trump ({readers}) and that writes no `trump` clause of its "
        f"own; drop the clause, or route it to such a round",
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
    n.Comprehension: ("where", "body"),
    n.CardQuery: ("where",),
    n.TrickOrderRow: ("body",),
    # A PlayerQuery's binder scopes to its `where` only; the ring search's
    # `start` seat is evaluated in the enclosing scope (the same split as
    # every source field absent from this table), so `player` in a start
    # slot means an OUTER binder or nothing.
    n.PlayerQuery: ("where",),
    # A DomainQuery's binder scopes to its `where` only; the `in` source is
    # evaluated in the enclosing scope (mirrors Comprehension/CardQuery, whose
    # source field is likewise absent here).
    n.DomainQuery: ("where",),
    n.Transfer: ("where",),
    n.EpistemicOp: ("where",),
    n.ForEach: ("body",),
    n.EachSimultaneous: ("body",),
    # `turns`' binder scopes to the body only: leader/participants/termination
    # evaluate in the enclosing scope (the binder does not exist until a turn
    # is bound — decisions.md "The `turns` form").
    n.Turns: ("body",),
}


def _rewrite(node: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if isinstance(node, n.NameRef):
        kind = _classify(node.name, cats)
        if kind is None:
            hint = ""
            noun = content_noun(cats.flavor, plural=False)
            if node.name == noun:
                where = (
                    "a card query, an aggregation, or a `where` filter"
                    if cats.flavor == "card"
                    else "a movement's `where` filter"
                )
                hint = f" (`{noun}` is bound only inside {where})"
            # Not a role dispatch: `player` is the unresolved NAME this hint
            # is about, so it stays a string (guarded as a coincidence in
            # tests/test_role_comparison_pin.py).
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
        when_pred = _rewrite_value(node.when, scoped, bag) if node.when is not None else None
        # `_rewrite_value` (not a bare per-item `_rewrite` map): a `let` in a
        # move's effect scopes to the statements after it, like everywhere else.
        effect = _rewrite_value(node.effect, scoped, bag)
        return replace(node, when=when_pred, effect=effect)  # type: ignore[arg-type]
    if isinstance(node, n.RuleDef) and node.params:
        # A template's parameters bind in its clauses, exactly as a move type's do
        # in its guard and effect. The GAME path never reaches this arm — a
        # template is instantiated (arguments substituted for parameters) before
        # `_classify_names` runs, and a template no reference instantiates is
        # already its own diagnostic from `_instantiate_rules` — so this exists
        # for the callers that classify a declaration where it is WRITTEN rather
        # than where it is used: `_library_reach`, which reads a family library's
        # definitions against the library alone. Without it, `_PARAM_BEARING`'s
        # four kinds would be scoped three-and-a-bit.
        scoped = replace(cats, locals=cats.locals | {p.name for p in node.params})
        return _traverse(node, lambda _field, v: _rewrite_value(v, scoped, bag))
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
    if isinstance(node, n.Phase):
        # The items fold with the configuration carve-out. A body `let` scopes
        # over later statements and nested phases (their qualifiers included) —
        # what the driver evaluates mid-body with the threaded context — but
        # NOT over this phase's own hooks, state defaults, or TRANSITION
        # predicates. Hooks and state declare/run at entry, before any body
        # `let` has executed (`run_phase` declares state and captures hooks
        # first); a transition predicate is CONFIGURATION collected
        # position-independently and evaluated with the context captured at
        # whichever round fires it — which may run before the `let`. The
        # generic tuple fold would scope all three anyway, so `let z = 5`
        # followed by `before_each { n[1] := z }` (or a transition reading a
        # body let, fired by an earlier round) would resolve, type-check, and
        # then ask the runtime's scope stack for a binding no live frame holds
        # — a lookup it requires to succeed, mid-playout.
        entry = cats
        current = cats
        out_items: list[object] = []
        for item in node.items:
            if isinstance(item, n.Mode):
                # A MODE reads no `let` at all — not even an enclosing one —
                # and that covers its whole body, not just its transitions.
                # A transition is fired by whichever round matches its event,
                # and rounds both before and after any given `let` can be in
                # scope, so no lexical position makes a binding reliably live
                # at evaluation time; a mode's `active_rules:` are collected
                # the same way, applying whenever the mode holds rather than
                # where they are written. Configuration reads state and the
                # action; body bindings are the body's.
                no_locals = replace(entry, locals=frozenset())
                out_items.append(_rewrite_value(item, no_locals, bag))
            elif isinstance(item, (n.BeforeEach, n.AfterEach, n.StateBlock)):
                out_items.append(_rewrite_value(item, entry, bag))
            else:
                rewritten = _rewrite_value(item, current, bag)
                out_items.append(rewritten)
                if isinstance(rewritten, n.LetStmt):
                    current = replace(
                        current, locals=current.locals | {rewritten.name}
                    )
        qualifier = (
            _rewrite_value(node.qualifier, entry, bag)
            if node.qualifier is not None
            else None
        )
        return replace(
            node,
            qualifier=qualifier,  # type: ignore[arg-type]
            items=tuple(out_items),  # type: ignore[arg-type]
        )
    scope_fields = _BINDER_SCOPE_FIELDS.get(type(node))
    if scope_fields is not None:
        binders = _introduced_binders(node, cats.flavor)
        if binders:  # a filter-less Transfer/EpistemicOp introduces nothing
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
    and not the call-site pronouns (`_CALL_SITE_PRONOUNS` — the runtime clears
    them); and the call graph must be acyclic (a cycle would loop forever at runtime).
    A function may not reuse a native call name: a call would type-check against the
    native signature but dispatch to the user function at run time."""
    fn_names = {f.name for f in game.functions}
    calls: dict[str, set[str]] = {
        f.name: {c.func for c in _walk(f.body) if isinstance(c, n.Call) and c.func in fn_names}
        for f in game.functions
    }
    native = call_namespace(game)
    for fn in game.functions:
        # The GAME's namespace, not the corpus-wide registry: a Primitive this
        # game cannot call shadows nothing here, and refusing the name anyway
        # would make the declared regime narrower than the legacy one it
        # replaces — the opposite of the isolation it promises.
        if fn.name in native:
            # A reader is MINTED from a row, so the designer who wrote one very
            # likely meant to write the row instead of a function beside it:
            # the hint names that fix, without changing the class this guard
            # owns (a native name a function may not take).
            hint = ""
            for row_key, reader in TRICK_ORDER_ROWS:
                if fn.name == reader:
                    hint = (
                        f" — the language mints `{reader}(card)` from a "
                        f"`trick_order {{ {row_key}: ... }}` row; move the body "
                        f"into the row, or rename"
                    )
            bag.error(
                f"function '{fn.name}' shadows the native function of the same name; "
                f"rename it (a call would type-check against the native signature but "
                f"run this function instead){hint}",
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
                # The list is RENDERED from the registry, not spelled out: a
                # hand-written enumeration goes stale the next time the pronoun set
                # moves, and a diagnostic that names the wrong words misdirects the
                # designer it is meant to repair.
                bag.error(
                    f"function '{fn.name}' reads the call-site pronoun '{nd.name}'; a "
                    f"function is hermetic and may not read "
                    f"{'/'.join(sorted(_CALL_SITE_PRONOUNS))} — "
                    f"pass the value in as a parameter",
                    nd.span,
                )
        if _reaches(fn.name, fn.name, calls):
            bag.error(
                f"function '{fn.name}' is recursive; functions must be non-recursive",
                fn.span,
            )


def _check_declared_type_names(game: n.Game, bag: DiagnosticBag) -> None:
    """A function parameter's and a outcome payload's declared type name names
    a real type.

    Validating a declared type name is resolve's job, and it was being done in
    only some of the positions that declare one: `StateDecl` and `StructField`
    were guarded and move parameters had their own domain gate, while function
    parameters and outcome payloads were not checked at all.
    `typecheck.type_from_name` maps an unknown name to the permissive `TAny`,
    so a mere TYPO exempted the annotated value from every downstream guard —
    `function f(x : Integar) = x is hearts` was accepted while the
    correctly-spelled `Integer` version was rejected. Making a type name worse
    must never make the checker more permissive (decisions.md "Surface
    totality"; "`Any` means the top, never a failed lookup").

    Both positions here are built with the struct registry threaded
    (`type_from_name(..., structs)`), so a user-declared `type` is legal
    alongside the built-ins — the allowed set mirrors exactly what the builder
    can resolve, since a guard admitting a name its builder still maps to
    `TAny` would trade one silent hole for another.

    The other declaring positions are deliberately absent, each already owned
    by an Owner Guard at least as tight: move parameters by `_check_move_params`
    (which additionally requires an ENUMERABLE domain, and now runs for every
    declared move type), procedure parameters by `_PROCEDURE_DOMAINS`, and
    rule-template parameters by `_check_template`'s Suit-only gate. Adding a
    second name check over any of them would report one defect twice, in two
    channels.
    """
    defined_types = {t.name for t in game.types}
    # A declared position domain is a legal annotation here: the parameter or
    # payload carries an integer member of the declared range, and the type
    # builder resolves it to that Integer. Omitting it rejected a name
    # declared in the same file as "unknown" while the same name stayed legal
    # on a move parameter.
    position_names = {p.name for p in game.positions}
    known = KNOWN_TYPE_NAMES | defined_types | position_names

    def base_of(type_name: str) -> str:
        # A trailing `?` marks a nullable domain/payload (`Suit?`), not part of
        # the name — strip it before the lookup, never by a blanket rstrip.
        return type_name.removesuffix("?")

    for fn in game.functions:
        for p in fn.params:
            if base_of(p.type_name) not in known:
                bag.error(
                    f"unknown type '{p.type_name}' in parameter '{p.name}' of "
                    f"function '{fn.name}'",
                    fn.span,
                )
    for define in game.defines:
        for case in define.cases:
            for payload in case.payload_types:
                if base_of(payload) not in known:
                    bag.error(
                        f"unknown type '{payload}' in payload of case "
                        f"'{case.tag}'",
                        case.span or define.span,
                    )
    for phase in _walk(game):
        if not isinstance(phase, n.Phase) or not phase.outcome_cases:
            continue
        for case in phase.outcome_cases:
            for payload in case.payload_types:
                if base_of(payload) not in known:
                    bag.error(
                        f"unknown type '{payload}' in payload of case "
                        f"'{case.tag}'",
                        case.span or phase.span,
                    )
    # Move parameters are deliberately NOT checked here: `_check_move_params`
    # already owns them with a stricter, better-worded gate (it names the legal
    # domains, including the game's declared position domains). Its gap was
    # REACH, not strength — it ran only for a move an offering enumerates —
    # and the fix is to run it for every declared move type, at its own call
    # site, rather than to shadow it with a second diagnostic in a different
    # channel (two messages for one defect is noise).


# The closed set of procedure-parameter domains (decisions.md "Named
# procedures"), corpus-first. Unlike a move parameter, a procedure argument is
# an arbitrary expression rather than a value the action space must enumerate,
# so this set gates what an argument may *denote*, not what can be enumerated —
# which is why it is a separate registry from `_FIXED_DOMAINS` below and not a
# slice of it. `Zone` is deliberately absent: the design note guessed the corpus
# would need it, and the corpus disagreed (Coup's blocks reach their zones by
# indexing a zone family with the player parameter — `influence[victim]` — so a
# Player parameter already carries the zone). Recorded in issue #134; extend
# when a game forces it.
#
# `Rank?` and not `Rank`: Coup's proven-claim swap is called both with a literal
# character (`run prove_claim(actor, Duke)`) and with the block claim, which is a
# `Rank?` because "no block" is a real state. The call sites all sit inside `if
# block_claim is not none`, but the language has no flow narrowing, so a bare
# `Rank` parameter would reject the very argument the block sites must pass. A
# `Rank?` parameter accepts both (`coercible(Rank, Rank?)`), which is why the
# optional form is the one the corpus forces. Bare `Rank` rides along: it is the
# same domain minus the null, meaningful on its own, and free to support.
#
# `Integer` is forced by poker_betting's `open_street(bet_size)`: the five street
# resets across Leduc and Stud are one shape differing in one integer. It strains
# nothing — an argument is an expression the caller evaluates once, not a value
# the action space enumerates, and `function` parameters have always taken
# Integer. The gap was which games existed, not a design position.
_PROCEDURE_PARAM_DOMAINS = frozenset({"Player", "Rank", "Rank?", "Integer"})


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
#                                  after it, which the body's pronoun guard cannot tell
#                                  from the caller's call-site `outcome`
#
# Every statement those checks govern is rejected in a body. The two remaining
# position-sensitive passes — `deckcheck.check_capacity` and the OpenSpiel action
# space — both run AFTER expansion and so see the real, spliced tree.
#
# A `produces:` over a DEFINE is not in the class: a define is invoked fresh at each
# site and has no ordering or uniqueness rule, which is why it stays allowed.
_NON_LOCAL_STMTS = (n.Produce, n.ContinueTo, n.SkipToNextHand)
# All three forms, not only the two that bind a winner: the Owner Guard enforces
# more than its name and message say (issue #290), and narrowing it here
# would relax it as a side effect of a refactor.
_WINNER_BINDING_STMTS = (n.TrickRound, n.AuctionRound, n.ClimbRound)


# What a write target may be. `:=`, `+=`, `-=` and `rotate` all write persistent
# state (`runtime/execute.py`'s `_assign` -> `rs.set`, `_rotate`), and persistent state
# is the only thing they can write — so a write target must classify as a state
# variable, full stop.
#
# This is one rule and not three Owner Guards because the target is a `NameRef`: it goes
# through `_classify` like every read, so "what is this name?" is already answered by
# the time we get here. Were it a bare `str` that no name check ever saw, the three
# ways it can go wrong would need three separate hand-written checks — and the easiest
# to omit is the plain typo, so `totaly_score := 1` would reach the runtime, which
# requires every name it writes to have been declared.
#
# The subtle one is a binder shadowing a state variable. A READ resolves binders BEFORE
# state variables; a write goes to state regardless. So `let turn = …` followed by
# `turn := 1` would write the state variable while every `turn` around it meant the
# binder — one name, two things, silently. Classifying the target makes that impossible
# rather than merely detected: the target resolves to the binder, and a binder is not
# a write target.
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
    """Why this zone-position expression (a movement's `from <here>` /
    `to <here>`, an epistemic op's target) is illegal, or None. The same move
    as `_bad_write_target`, one grammar position over: the position is
    name-shaped (the grammar rejects literals there), so its ROOT name has a
    classification, and most classifications cannot possibly be a zone.
    `deal 1 cards from turn to each hand` and `shuffle turn` (with
    `turn : Integer`) would otherwise both check clean and reach the executor,
    which requires an actual Zone in this position and refuses anything else at
    play time — a statically nameable error deferred to the wrong time.

    A `local` root stays accepted HERE: a binder may legitimately hold a zone
    value (`let h = hand[0]`), and which one it holds is a TYPE question —
    typecheck's `_check_transfer`/EpistemicOp arms decide it from the binder's
    inferred type (decisions.md, "`let` bindings scope forward and carry
    their type"). The executor's typed error remains the Owner Guard for the
    deliberately-loose initializers (`outcome`, unregistered action fields)."""
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
    return f"cannot {what} '{root.name}': it is {what_it_is}, not a zone"


def _check_procedures(game: n.Game, bag: DiagnosticBag) -> None:
    """A procedure body must read as the statements it becomes. Hermeticity is the
    same as a function's — a body references only its own parameters, the binders
    it introduces, and game/phase state, never the caller's locals and never the
    call-site pronouns, so its meaning cannot depend on where it is run from.

    Only ONE hygiene Owner Guard lives here, because `expand` makes the rest unnecessary
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

        # Binders the body introduces, and the name-capture Owner Guard: a binder
        # sharing a parameter's name would capture it instead of substituting.
        # A procedure body can hold a movement, so its filter binder follows
        # the game's flavor (a piece game's `piece`, not `card`).
        binders: set[str] = set()
        for nd in _walk(proc):
            binders.update(_introduced_binders(nd, game.content_flavor))
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
                elif isinstance(nd, _WINNER_BINDING_STMTS):
                    bag.error(
                        f"procedure '{proc.name}' contains a `round`, which binds "
                        f"its own `winner` for the statements after it; a "
                        f"procedure body may not yet hold one, because the body's "
                        f"`winner` Owner Guard cannot distinguish a round-local binding "
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
    mt: n.MoveTypeDef,
    bag: DiagnosticBag,
    span: Span | None,
    has_ranking: bool,
    positions: frozenset[str],
    directions: frozenset[str],
    flavor: Flavor,
    deck: str,
) -> None:
    """Totality gate for a parameterized move offered/enumerated in a decision
    (an `offer` statement or a `round offering`). Fixed-from-type
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
    # A piece game has no suit/rank/card domain to enumerate, so a move
    # parameterized by one has no candidate space. Checked before the
    # has_ranking / unsupported-domain arms so the diagnostic names the KIND
    # (a Rank param in a piece game is a flavor error, not a missing-ranking
    # one); Player and position domains stay legal.
    if flavor == "piece":
        offending = [t for t in types if t in CARD_PARAM_DOMAINS]
        if offending:
            bag.error(
                f"{content_kind_clause(flavor, deck)} -- move '{mt.name}' has a "
                f"{offending[0]} parameter, whose domain is the deck's "
                f"suits/ranks; a piece set enumerates neither",
                span,
            )
            return
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
        elif (
            t not in _FIXED_DOMAINS
            and t != "Card"
            and t not in positions
            and t not in directions
        ):
            expected = _LEGAL_PARAM_DOMAINS
            if positions:
                expected += ", or a declared position domain (" + ", ".join(sorted(positions)) + ")"
            if directions:
                expected += (
                    ", or a movement direction domain ("
                    + ", ".join(sorted(directions))
                    + ")"
                )
            bag.error(
                f"move '{mt.name}' has unsupported parameter domain '{t}' "
                f"(expected {expected})",
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


def _check_card_offering(
    names: tuple[str, ...],
    move_type_defs: dict[str, n.MoveTypeDef],
    game: n.Game,
    bag: DiagnosticBag,
    span: Span | None,
) -> None:
    """The Card domain's constraints on an offering of move types, wherever
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
            f"offering declares more than one Card-parameterized move "
            f"({', '.join(card_param_moves)}); a card play's action is the "
            f"card itself, so a second Card-parameterized move would be "
            f"indistinguishable — fold them into one move type",
            span,
        )
    if card_param_moves and not any(
        # Intrinsic: a Card parameter enumerates the ACTOR's hand, which is
        # player-keyed by definition.
        z.name == "hand" and z.index is not None and role_of(z.index) is Role.PLAYER
        for z in game.zones
    ):
        bag.error(
            f"offering move '{card_param_moves[0]}' takes a Card parameter, "
            f"which enumerates the actor's `hand[player]` zone — this game "
            f"declares none",
            span,
        )


def _check_offering_moves(
    names: tuple[str, ...],
    defined_move_types: set[str],
    bag: DiagnosticBag,
    span: Span | None,
    unknown_msg: str,
) -> None:
    """The shared body of an offering's per-name loop, wherever one is
    enumerated (a plain `offer` or the auction `round offering` —
    `_check_card_offering`'s docstring has the same "wherever one is
    enumerated" rationale): every named move type must be defined.
    `unknown_msg` is the caller-specific wording for an unknown name (the two
    call sites differ only in this message, "offer ..." vs "round offering
    ...").

    Parameter DOMAINS are deliberately not checked here. They are a property
    of the move type's DECLARATION, so `_validate_refs` gates every declared
    move type once — which both closes the old gap (a move type no offering
    named was never gated at all) and stops a move type named by two
    offerings from reporting the same defect once per mention."""
    for name in names:
        if name not in defined_move_types:
            bag.error(f"{unknown_msg} '{name}'", span)


# The collection quantifier nouns admitted at rung 1 (decisions.md "Boards and
# cells"): `any line in …` / `all cells in …`. Any other `in` noun is rejected
# naming these two; further nouns are a recorded residual (issue #111).
_COLLECTION_NOUNS: frozenset[str] = frozenset({"line", "cell"})

def _check_domain_query(nd: n.DomainQuery, game: n.Game, bag: DiagnosticBag) -> None:
    """Validate a positional-quantifier noun (decisions.md "Boards and cells").

    A BARE form (`source is None`) ranges over a declared position domain; a
    COLLECTION form (`in <expr>`) over one of the rung-1 collection nouns
    {line, cell}. The plural convention is a resolve Owner Guard, not a grammar one:
    `any` takes the singular noun, `all`/`number of` the plural (singular +
    "s"); a singular where the plural is required is guided to the plural
    spelling, an unknown noun to the declared universe.

    suit/rank quantifiers never reach here: QNOUN excludes those spellings, so
    `any suit where …` is the fixed `Quantifier` form (guarded in a piece game
    by the CARD_AXIS_ROLES case below) -- the noun exclusion IS that guard."""
    phrase = n.DOMAIN_QUERY_KIND_PHRASE[nd.kind]
    if nd.source is None:
        declared = {p.name for p in game.positions}
        universe = (
            f"declared position domains: {', '.join(sorted(declared))}"
            if declared
            else "this game declares no position domains"
        )
        if nd.binder in _COLLECTION_NOUNS and nd.binder not in declared:
            # A bare `any line where …`: the noun is a collection noun, so the
            # designer almost certainly dropped the `in <collection>` clause.
            universe += (
                f" (a `{nd.binder}` is quantified from a collection: "
                f"`{phrase} {nd.spelled} in <collection> where ...`)"
            )
        target_ok = nd.binder in declared
        noun_kind = "position domain"
    else:
        universe = "the `in` forms iterate a `line` or a `cell` collection"
        target_ok = nd.binder in _COLLECTION_NOUNS
        noun_kind = "collection noun"
    if nd.kind != "any" and not nd.spelled.endswith("s"):
        # A singular noun under `all`/`number of`: guide to the plural if the
        # singular names a real target, else fall through to unknown-noun.
        if target_ok:
            bag.error(
                f"`{phrase} {nd.spelled}` needs the plural noun -- write "
                f"`{phrase} {nd.spelled}s`",
                nd.span,
            )
            return
        bag.error(f"unknown {noun_kind} '{nd.spelled}' -- {universe}", nd.span)
        return
    if not target_ok:
        bag.error(f"unknown {noun_kind} '{nd.binder}' -- {universe}", nd.span)


def _check_board_call(nd: n.Call, game: n.Game, bag: DiagnosticBag) -> None:
    """The board-reading native calls (`lines`, BOARD_ONLY_CALL_FUNCS): a
    boardless game has no board to read, and a literal `k` outside the board's
    line span is a static error. The bound is reused from the board entry's own
    `lines()` (cardlang/stdlib/boards.py), so resolve and the runtime share one
    definition of it; a NON-literal `k` (no rung-1 witness) is left to that
    runtime bound, surfaced as a typed error (recorded residual, issue #111)."""
    if game.board is None:
        bag.error(
            f"`{nd.func}` reads the board, but the game declares no `board:`",
            nd.span,
        )
        return
    # A frame verb reads the grid's two-seat per-player frame, defined only for
    # players 0 and 1. Without this Owner Guard a game with three-plus (or one) seats
    # resolves clean and then dies at setup/play with the frame's registry-bug
    # `ValueError` when a verb is called for seat 2 -- a typechecked game
    # failing at runtime, in the wrong channel. Require exactly two players (a
    # RANGE is refused even where it includes two, since the game may be
    # instantiated with more).
    players = game.players
    if nd.func in _FRAME_CALL_FUNCS and (players.varies or players.low != 2):
        count = f"{players.low}-{players.high}" if players.varies else str(players.low)
        bag.error(
            f"`{nd.func}` reads a grid's two-player movement frame (one seat's "
            f"forward is the other's, the 180-degree opposite), but the game "
            f"declares {count} players — the frame is defined for two seats "
            f"(design-notes/board-topology.md); name seats directly for more",
            nd.span,
        )
    pos_args = [a for a in nd.args if not isinstance(a, n.NamedArg)]
    if nd.func == "lines" and len(pos_args) == 1 and isinstance(pos_args[0], n.IntLit):
        try:
            board_entry(game.board.family, game.board.args).lines(pos_args[0].value)
        except OwnerGuardError as exc:
            bag.error(str(exc), nd.span)


def _validate_refs(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> None:
    move_type_defs = {m.name: m for m in game.move_types}
    defined_move_types = set(move_type_defs)
    defined_types = {t.name for t in game.types}
    defined_defines = {d.name for d in game.defines}
    defined_functions = {f.name for f in game.functions}
    native_namespace = call_namespace(game)
    # Which role (if any) each declared zone family is keyed by — the fact the
    # `to each <family>` Owner Guard needs (the executor keys parcels per PLAYER).
    zone_index = {z.name: z.index for z in game.zones}
    # A `produces:` consumer may also name an outcome-declaring phase (its outcome
    # is produced as the phase runs, then dispatched by a sibling consumer).
    outcome_phases = {
        nd.name for nd in _walk(game) if isinstance(nd, n.Phase) and nd.outcome_cases
    }
    # Every DECLARED move type's parameter domains, gated exactly once. The
    # gate itself is unchanged; its REACH was the hole. It used to run from the
    # offering call sites, so a move type no `offer`/`round offering` names
    # had its parameter domains unchecked entirely — and an unchecked domain
    # name falls through `typecheck.type_from_name` to the permissive top,
    # which silently exempts the parameter from every downstream guard
    # (decisions.md, "`Any` means the top, never a failed lookup"). Declaring
    # a move type is what makes its parameters real; whether some phase happens
    # to offer it is not the checker's business — and gating at the declaration
    # also stops a move named by two offerings from reporting one defect
    # twice.
    declared_positions = frozenset(p.name for p in game.positions)
    # `for each <role>` iterates the closed seat/axis roles plus a board's
    # NAMED-MEMBER position domain (`cell`) -- breakthrough's fixed setup array
    # is the witness that lifts it. Integer `positions {}` domains stay refused:
    # no game addresses columns by loop (guards and parameters cover both
    # solitaires), so they stay rejected rather than accepted-and-unwitnessed
    # (issue #111). A boardless game
    # therefore reports the unchanged closed-role list.
    iterable_positions = frozenset(
        p.name for p in game.positions if p.members_named is not None
    )
    # The board-minted `dir` domain, a SEPARATE source from `game.positions`
    # (decisions.md "Boards and cells"): `{dir}` for a board game, `{}` for a
    # boardless one, so a `dir` move parameter is admitted only where a board
    # mints it. Gated on the board having MINTED (`cell` present as a
    # named-member domain): an INVALID board (`_resolve_board` already emitted
    # its diagnostic and minted nothing) leaves `directions_of` -- which
    # re-derives from `board_entry` -- unsafe to call, and admitting `dir` off
    # a board that failed validation would be wrong anyway. So `cell` and `dir`
    # stand or fall together.
    board_minted = any(
        p.name == BOARD_DOMAIN and p.members_named is not None for p in game.positions
    )
    move_directions = frozenset(directions_of(game)) if board_minted else frozenset()
    for mt in game.move_types:
        if mt.params:
            _check_move_params(
                mt, bag, mt.span, bool(game.ranking),
                declared_positions, move_directions, game.content_flavor, game.deck,
            )
    for nd in _walk(game):
        match nd:
            case n.Call() if (
                nd.func not in native_namespace and nd.func not in defined_functions
            ):
                # `native_namespace` is the game's own, not the corpus-wide
                # registry: a game with a `primitives { }` block names the
                # Primitives it declares and no other game's, so a neighbour's
                # trick winner is an unknown name here rather than a call that
                # resolves and then dispatches through a table this game never
                # claimed (issue #364).
                bag.error(
                    f"call to unknown function '{nd.func}'"
                    + _undeclared_primitive_hint(game, nd.func),
                    nd.span,
                )
            case n.Call() if nd.func in defined_functions:
                # A call the game's OWN `function` defines. Every arm below
                # keys a name against a corpus-wide native registry, and a
                # declared game may legally define a function named after a
                # Primitive absent from its namespace — so those registries
                # would answer about Python this call never reaches. The
                # runtime dispatches a defined function first
                # (`evaluate.Call`), and this arm is what keeps resolve's
                # reading of the name the same as the runtime's.
                pass
            case n.Call() if (
                game.content_flavor == "piece" and nd.func in DECK_ONLY_CALL_FUNCS
            ):
                # A deck-reading native call (suit_of, rank_value, a trick-
                # winner, ...) has nothing to read in a piece game. The generic
                # calls (top_of, team_of, ...) are absent from DECK_ONLY and
                # stay legal.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                    f"`{nd.func}` reads a card's suit/rank/points, which a piece "
                    f"set has none of",
                    nd.span,
                )
            case n.Call() if nd.func == "card_points" and game.card_points is None:
                # The table has ONE source, the game's own clause (the deck
                # registry carries no point table), so a clause-less call has
                # nothing to read: without this guard it would silently price
                # every card 0 — accepted-but-ignored wearing a green check.
                # The `_check_board_call` mechanism, keyed on the clause. The
                # piece-game cell never reaches here: `card_points` is
                # DECK_ONLY, so the flavor arm above already rejected it.
                bag.error(
                    "`card_points(card)` reads the game's card-point table, "
                    "but this game declares no `card_points { }` clause",
                    nd.span,
                )
            case n.Call() if nd.func in BOARD_ONLY_CALL_FUNCS:
                # A board-reading call (lines) in a boardless game, or a literal
                # out-of-range k. The DECK_ONLY twin above (`game.board is None`
                # keyed instead of the flavor). DomainQuery noun validation runs
                # earlier (in `resolve`, before deep name resolution) so its
                # diagnostic is not masked by the pred's unresolved binder.
                _check_board_call(nd, game, bag)
            case n.Call() if (
                regime(game) is Regime.LEGACY
                and nd.func in DECLARED_ONLY_CALL_FUNCS
            ):
                # The regime partition's other direction, and the Owner Guard
                # for it. A declared-only Primitive is one
                # `runtime/primitives.py` holds no `call` arm for, so a
                # declaration is the ONLY route to its Python — yet the name IS
                # a Primitive, so the legacy namespace (`CALL_FUNCS`) admits it
                # and the unknown-name arm above says nothing. Without this the
                # call checks clean and the dispatch falls through to a
                # compiler-bug assert: the wrong channel, about a name the
                # registry does hold.
                #
                # AFTER the flavor arms deliberately: a piece game cannot fix
                # this call by writing a block — the deck-only refusal stands
                # either way — so the reason that speaks there is the one whose
                # fix is real (`_check_primitive_name`'s ordering rule).
                bag.error(
                    f"`{nd.func}` is a Primitive a game reaches only by "
                    f"declaring it, and this game writes no `primitives {{ }}` "
                    f"block; declare it in one to call it",
                    nd.span,
                )
            case n.StructLit() if nd.type_name not in defined_types:
                bag.error(f"unknown type '{nd.type_name}'", nd.span)
            case n.NamedArg():
                # Accepted-but-crashing surface refused outright (Surface totality):
                # the grammar admits `f(x = 1)`, but typecheck skips the value
                # expression and the runtime raises. Reject until a game needs
                # named arguments (recorded in roadmap.md, "Grammar surface
                # deferred by the checker").
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
                if nd.index is not None and role_of(nd.index) not in ZONE_INDEX_ROLES:
                    # Same guard as a zone's index role, same registry. Before
                    # it existed, `state { x[suit] : Integer = 0 }` checked
                    # clean and the runtime silently keyed it BY PLAYERS (the
                    # driver's key-set dispatch defaulted every non-team role
                    # to seats) — the declared index was accepted and ignored.
                    roles = ", ".join(role_names(ZONE_INDEX_ROLES))
                    bag.error(
                        f"state variable '{nd.name}' is indexed by "
                        f"'{nd.index}', which is not an indexable role "
                        f"({roles}) — a value domain has no per-member store "
                        f"(roadmap.md records the extension)",
                        nd.span,
                    )
                elif (
                    nd.index is not None
                    and role_of(nd.index) is Role.TEAM
                    and not game.teams
                ):
                    # A team-indexed store in a game with no teams has
                    # an EMPTY key set: it declares fine, holds nothing, and
                    # every later `x[…] := …` hits the runtime key guard far
                    # from the real mistake (the missing `teams:`).
                    bag.error(
                        f"state variable '{nd.name}' is indexed by 'team' but "
                        f"the game declares no `teams:` — there are no "
                        f"teams to key it by",
                        nd.span,
                    )
            case n.ZoneDecl() if (
                nd.index is not None
                and role_of(nd.index) is Role.TEAM
                and not game.teams
            ):
                bag.error(
                    f"zone '{nd.name}' is indexed by 'team' but the game "
                    f"declares no `teams:` — there are no teams to key "
                    f"it by",
                    nd.span,
                )
            case n.LetStmt() if (
                nd.index is not None and nd.index in _MISLEADING_LET_INDEXES
            ):
                bag.error(
                    f"`let {nd.name}[{nd.index}]` builds a per-PLAYER map — "
                    f"the index is a binder bound to each player in turn, "
                    f"whatever its name — so a binder named '{nd.index}' "
                    f"reads as a per-{nd.index} store this form does not "
                    f"build. Rename the binder; per-value stores are recorded "
                    f"in roadmap.md",
                    nd.span,
                )
            case n.StructField() if (
                nd.type_name not in KNOWN_TYPE_NAMES
                and nd.type_name not in defined_types
            ):
                # The sole struct-field declaration-type Owner Guard (an unknown
                # name would silently type TAny and skip every operand guard). A
                # struct field types via scalars/enums/structs only; a position
                # domain is deliberately NOT admitted here (main's type-name
                # grid, tests/test_type_name_positions.py P2). Function-param
                # and outcome-payload type names are the sibling slots, but
                # those are owned by `_check_declared_type_names`, which admits
                # position domains — so they are not re-checked here.
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
            case n.ForEach() if (
                role_of(nd.role) not in _ITERATION_ROLES
                and nd.role not in iterable_positions
            ):
                bag.error(
                    f"unknown `for each` role '{nd.role}' (expected one of "
                    f"{', '.join(sorted(role_names(_ITERATION_ROLES) + sorted(iterable_positions)))})",
                    nd.span,
                )
            case (n.ForEach() | n.Quantifier()) if (
                game.content_flavor == "piece" and role_of(nd.role) in CARD_AXIS_ROLES
            ):
                # `for each suit` / `any rank where` enumerate the deck's axes;
                # a piece set has no role surface for its own axes (side/kind),
                # so the card-axis roles are rejected naming the kind. The seat
                # roles (player/team) fall through, legal in both flavors.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                    f"the `{nd.role}` role ranges over a deck's {nd.role}s, which "
                    f"a piece set has none of",
                    nd.span,
                )
            case n.EachSimultaneous() if role_of(nd.role) not in SIMULTANEOUS_ROLES:
                # The registry's `simultaneous` column, not a bare `!= "player"`:
                # the roles that admit a simultaneous block are exactly the seat
                # domains (a value domain has no actor to move simultaneously),
                # and both the gate and the message it prints come from the rows.
                bag.error(
                    f"`each {nd.role} simultaneously` is not runnable — "
                    f"simultaneous moves are per "
                    f"{' or '.join(role_names(SIMULTANEOUS_ROLES))}",
                    nd.span,
                )
            case n.EachSimultaneous() if n.simultaneous_body_error(nd.body) is not None:
                # The form gated its DOMAIN (above) and not its BODY. The executor
                # implements exactly one body shape, so everything else compiled and
                # then died on a bare assert — a runtime crash for a statically
                # checkable error, in the wrong channel. `run` made it reachable
                # from an entirely natural-looking program (`each player
                # simultaneously: run pass_card(player)`), since an expansion is a
                # block and never a bare movement.
                #
                # The reason comes FROM the executor's own requirement
                # (`n.simultaneous_body_error`), not from a hand-written copy of it:
                # the first version of this Owner Guard mirrored only the first of five
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
            case n.CardLiteral() if game.content_flavor == "piece":
                # `mark of x` is a well-formed literal against a piece set's own
                # ranks/suits (the axis values populate the same namespaces), so
                # the membership check below would ACCEPT it -- a card-literal
                # form given piece meaning. Reject the form itself, naming the
                # kind, before that.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- a "
                    f"card literal (`{nd.rank} of {nd.suit}`) names a deck card; "
                    f"a piece has no rank-of-suit identity",
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
            case n.Transfer():
                # The `in <zone>` form has no `from` clause (its zone parses
                # into `source`) — say `in`, not `from`, when rejecting it.
                source_phrase = (
                    f"{nd.verb} cards in"
                    if nd.dest is None and nd.source is not None
                    else "move cards from"
                )
                for endpoint, direction in (
                    (nd.source, source_phrase),
                    (nd.dest, "move cards to"),
                ):
                    bad = _bad_zone_endpoint(endpoint, direction)
                    if bad is not None:
                        bag.error(bad, nd.span)
                # The joint-selection matrix (decisions.md "Joint-predicate
                # selection"): `jointly` is a DECISION over subsets, so it
                # requires `chosen` — a dealt jointly-selection has no
                # decider and a `random` one has no corpus user (both
                # recorded in roadmap.md, "Grammar surface deferred by
                # the checker"); `some` (any-size) is meaningless
                # without a joint predicate to own the size.
                if nd.joint and nd.selection_mode != "chosen":
                    bag.error(
                        "`where jointly` selects one subset as a player "
                        "decision — it requires `chosen` (a dealt or "
                        "`random` joint selection is not implemented; "
                        "recorded in roadmap.md)",
                        nd.span,
                    )
                if nd.joint and nd.dest_each:
                    # `to each` would silently make EACH destination seat its
                    # own subset-decider over the shrinking pool — the decider
                    # identity is info-set-load-bearing, and no corpus game
                    # wants the shape (recorded in roadmap.md, "Grammar
                    # surface deferred by the checker").
                    bag.error(
                        "`where jointly` with `to each` is not implemented — "
                        "each destination seat would become its own subset "
                        "decider; write one joint selection per destination "
                        "instead (recorded in roadmap.md)",
                        nd.span,
                    )
                if nd.amount == "some" and not nd.joint:
                    bag.error(
                        "amount `some` (any satisfying size) is only "
                        "meaningful under `where jointly`, whose predicate "
                        "owns the size constraint — use a count, `one`, or "
                        "`all` otherwise",
                        nd.span,
                    )
                if nd.dest_each and not isinstance(nd.dest, n.NameRef):
                    # The executor keys the family by BARE name per seat, so a
                    # subscripted or computed destination has no meaning under
                    # `each`. Before this Owner Guard, `to each hand[0]` checked
                    # clean and reached an executor that requires this
                    # destination to be a bare name it can key per seat.
                    bag.error(
                        "`to each` deals into a player-indexed family named "
                        "bare (like `to each hand`) — a subscripted or "
                        "computed destination targets one zone, so drop "
                        "`each` or name the family",
                        nd.span,
                    )
                if nd.dest_each and isinstance(nd.dest, n.NameRef):
                    # `to each X` deals one parcel per PLAYER (the executor
                    # iterates seats and keys `X[player]`), so X must be a
                    # player-indexed family. Before this Owner Guard, `to each deck`
                    # (a singleton) checked clean and then asked the zone store
                    # for a player-keyed family of that name, which it requires
                    # to be declared and refuses at play time;
                    # and `to each captured` (a TEAM family) silently dealt
                    # into team slots AS IF team ids were seats before crashing
                    # — player keying was assumed, not checked, the same class
                    # as the `== "team"` defaults the domain table replaced.
                    idx = zone_index.get(nd.dest.name)
                    # Intrinsic: `to each` deals one share per PLAYER, so the
                    # destination family must be player-keyed whatever else the
                    # table gains.
                    if nd.dest.ref_kind == "zone" and (
                        idx is None or role_of(idx) is not Role.PLAYER
                    ):
                        what_z = (
                            "a singleton zone"
                            if idx is None
                            else f"a family keyed by {idx}"
                        )
                        bag.error(
                            f"`to each {nd.dest.name}` deals one parcel per "
                            f"player, but '{nd.dest.name}' is {what_z} — name "
                            f"a player-indexed family (like hand[player]), or "
                            f"target one instance directly",
                            nd.span,
                        )
                    elif nd.dest.ref_kind is not None and nd.dest.ref_kind != "zone":
                        # The executor consumes the NAME (`zones.instance(X,
                        # player)`), not a zone value — so unlike the generic
                        # endpoints, a binder can never stand here even when it
                        # HOLDS a zone: `let h = hand[0]` / `to each h` would
                        # type clean (h is a zone) and then ask the zone store
                        # for a family literally named 'h', which requires a
                        # declared family of that name and refuses at play time.
                        what_k = _WRITE_TARGET_KINDS.get(
                            nd.dest.ref_kind, f"a {nd.dest.ref_kind}"
                        )
                        bag.error(
                            f"`to each {nd.dest.name}` deals into "
                            f"{nd.dest.name}[player] BY NAME, so it must name "
                            f"a player-indexed zone family declared in "
                            f"`zones {{ }}` — '{nd.dest.name}' is {what_k}",
                            nd.span,
                        )
            case n.EpistemicOp() if (
                game.content_flavor == "piece" and nd.op == "reveal"
            ):
                # `reveal one card from ...` hardcodes the noun "card"; a piece
                # game has no such statement (the piece twin is grammatically
                # inexpressible). `shuffle` falls through -- it moves a zone's
                # order, no card content, legal in both flavors.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                    f"`reveal one card` identifies a deck card; reveal a piece is "
                    f"not expressible",
                    nd.span,
                )
            case n.EpistemicOp():
                # The other member of the zone-position class: `shuffle turn` /
                # `reveal one card from turn` checked clean and then reached an
                # executor that requires an actual Zone as the op's target and
                # refuses anything else, exactly like the movement endpoints.
                bad = _bad_zone_endpoint(nd.zone, nd.op)
                if bad is not None:
                    bag.error(bad, nd.span)
            case n.Winner() if nd.state_var not in cats.state_vars:
                bag.error(f"winner references unknown variable '{nd.state_var}'", nd.span)
            case n.Turns() if nd.again is not None and nd.again not in cats.state_vars:
                # The go-again flag is ordinary game state the body's effects
                # write (decisions.md "The `turns` form") — a plain string
                # field like `Winner.target`, so the generic NameRef pass
                # never sees it; validate it here or it fails only at the
                # first turn boundary, where the executor reads it out of
                # round state — which requires the name to be in scope.
                bag.error(
                    f"`again {nd.again}`: names no declared state variable — "
                    f"the go-again flag is ordinary Boolean game state the "
                    f"body's move effects write",
                    nd.span,
                )
            case n.Offer():
                _check_offering_moves(
                    nd.offering,
                    defined_move_types,
                    bag,
                    nd.span,
                    "offer names unknown move type",
                )
                _check_card_offering(nd.offering, move_type_defs, game, bag, nd.span)
            case n.AuctionRound():
                # An offering of game-defined move types, no card zones. The
                # termination predicate's names are checked by the generic
                # NameRef pass.
                #
                # Parameter domains are a closed set (decisions.md "Surface
                # totality"): the runtime enumerates `Suit`/`Suit?`/`Rank`/
                # `Player` statically and `Card` over the actor's live hand —
                # any other type, or a domain combination `_check_move_params`
                # rejects, would crash `enumerate_domain`/produce an
                # indistinguishable action id mid-playout. That gate now runs
                # over every DECLARED move type (above), which covers these and
                # the ones no offering names.
                _check_offering_moves(
                    nd.offering,
                    defined_move_types,
                    bag,
                    nd.span,
                    "round offering names unknown move type",
                )
                _check_card_offering(nd.offering, move_type_defs, game, bag, nd.span)
                # The betting form omits `outcome` (it mutates state directly and
                # produces no outcome); only an auction's outcome fn is validated.
                if nd.outcome_fn is not None and nd.outcome_fn not in PRIMITIVE_AUCTION_OUTCOMES:
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
            case n.ClimbRound():
                # Trick zones plus the two combination-engine queries
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
                elif nd.move_type != CLIMB_DECISION_MOVE_TYPE:
                    # The climbing form's decision site is hardwired to
                    # `play_combination` — nothing in `ClimbForm` reads this
                    # field at all — so any other name ran as a climb regardless
                    # and meant nothing (decisions.md "Surface totality"). The
                    # trick form has carried the same Owner Guard since its surface was
                    # written; this form went without one.
                    bag.error(
                        f"the climb round form runs `{CLIMB_DECISION_MOVE_TYPE}`; "
                        f"'{nd.move_type}' is not runnable on it (roadmap.md)",
                        nd.span,
                    )
                if nd.combos_fn not in PRIMITIVE_CLIMB_LEADS:
                    bag.error(
                        f"climb round `combinations` query '{nd.combos_fn}' is not a "
                        f"combination lead query",
                        nd.span,
                    )
                if nd.follows_fn not in PRIMITIVE_CLIMB_FOLLOWS:
                    bag.error(
                        f"climb round `follows` query '{nd.follows_fn}' is not a "
                        f"combination follows query",
                        nd.span,
                    )
            case n.TrickRound():
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.error(f"round source zone '{nd.source_zone}' is unknown", nd.span)
                if nd.play_zone not in zone_names:
                    bag.error(f"round play zone '{nd.play_zone}' is unknown", nd.span)
                else:
                    # A trick's plays ARE the provenance every winner reads, so
                    # the zone they land in must project identity to every
                    # observer — otherwise the winner is computed from facts no
                    # player's own stream could derive. Every trick round, not
                    # only a Trick Order one: the rule is the [[arrival-record]]
                    # rule (issue #256), and this is where the play zone is
                    # named (issue #250 PR 1, ruled point 4).
                    play_decl = next(
                        (z for z in game.zones if z.name == nd.play_zone), None
                    )
                    if (
                        play_decl is not None
                        and play_decl.type_ref.name in LIBRARY_ZONE_TYPES
                        and not identity_to_all(play_decl.type_ref.name)
                    ):
                        bag.error(
                            f"round `into {nd.play_zone}` "
                            f"({play_decl.type_ref.name}): a trick's play zone "
                            f"must project identity to every observer — the "
                            f"plays are the provenance every winner reads; use "
                            f"a TrickPile",
                            nd.span,
                        )
                if nd.winner_fn not in TRICK_WINNER_NAMES:
                    bag.error(
                        f"trick round winner '{nd.winner_fn}' is not a trick "
                        f"winner function",
                        nd.span,
                    )
                elif nd.winner_fn in TRICK_ORDER_GATED_WINNERS:
                    # A Trick Order winner takes no `trump` argument at all --
                    # its trumps are the block's row — so this arm's question
                    # (a clause the winner would ignore) is not the one to ask.
                    # `_check_trick_order_partition` owns both cells: R2 with a
                    # block, R5 without one, and each names the block.
                    pass
                elif nd.trump is not None and nd.winner_fn not in TRUMP_READING_WINNERS:
                    # The winner contract carries a `trump` argument for every
                    # member, but only TRUMP_READING_WINNERS' bodies read it:
                    # on the others the round's `trump` clause was evaluated,
                    # traced, passed, and dropped — accepted-but-ignored
                    # (decisions.md "Surface totality"). Same arm as the
                    # `play_to_trick` guard below: a round-configuration
                    # clause its own slot cannot use.
                    readers = ", ".join(sorted(TRUMP_READING_WINNERS))
                    bag.error(
                        f"round `trump` clause on winner {nd.winner_fn}, which "
                        f"reads no trump — the clause would be silently ignored; "
                        f"drop it, or name a winner that reads a trump ({readers})",
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
                    and nd.early_termination not in PRIMITIVE_EARLY_PREDICATES
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
