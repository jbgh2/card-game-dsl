"""The checks a library is held to on its own, before any game uses it.

A shared module with two drivers: the splice runs ``check_library_alone`` on
each library a game `uses`, and the standard library's loader runs it on
`library stdlib` (`cardlang/stdlib/rules.py`). Its refusals are told to the
library's author.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a parsed library, judged with no game beside it; the
              standard library's rule index (``stdlib_rules``), read here
              with no ``resolve()`` above it when the loader is the driver.
Establishes:  a library this module refuses is not judged against any game
              (the splice's Contract Block states the consequence).
Now illegal:  a Primitive named by family-library text, as a call or in
              a ``round``'s query slot, refused to the library's author
              (``_check_library_encapsulation``) before the splice; the
              slot registries are ``_ROUND_QUERY_REGISTRIES``, which
              ``_validate_refs`` reads for every round.
              A library's Definition Contract rows whose shape no game could
              answer (``_check_contract_shapes``; the row law is the
              splice's Contract Block's).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Literal, assert_never, get_args, get_origin, get_type_hints
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.builtins.functions import BUILTIN_CALL_FUNCS, PRIMITIVE_CALL_FUNCS, VALUE_NAMES
from cardlang import kernel_contracts as K
from cardlang.primitives_block import COLLECTION_TYPE_CONSTRUCTOR, walled_namespace_of
from cardlang.attribution import (
    LibrarySort,
    cite_library,
    cite_named,
    cite_where,
    library_sort,
    library_text_codes,
)
from cardlang.diagnostics import Diagnostic, DiagnosticBag, Said, Span, listed
from cardlang.domains import ZONE_INDEX_ROLES, role_names, role_of
from cardlang.stdlib.enums import SEAT_DIRECTION_VALUES
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import stdlib_rules
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.typecheck import COMBINATION_TYPE_NAME, KNOWN_TYPE_NAMES, POSITIVE_PARAM_DOMAIN
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.reserved import (
    RESERVED_VALUE_NAMES,
    _CALL_SITE_PRONOUNS,
    _refuse_play_source_params,
)
from cardlang.resolve.slots import (
    _CONTEXTUAL_SLOTS,
    _DECLARATION_SLOTS,
    _NAMING_SLOTS_BY_TYPE,
    _REFERENCE_SLOTS,
    _ROUND_QUERY_NAMES,
    _ROUND_QUERY_REGISTRIES,
    _round_query_slot,
    slot_namespace,
    slot_strings,
)
from cardlang.resolve.clause_gates import _PROCEDURE_PARAM_DOMAINS
from cardlang.resolve.classifier import (
    ALWAYS_HOLDERS,
    _Categories,
    _always_message,
    _callback_outside_slot,
    _rewrite_value,
)


# Every definition kind a `library { }` may hold, as (Game/Library field name,
# the noun a diagnostic calls it). This tuple IS the closed domain the import
# tier's collision Owner Guards sweep: `_apply_uses` derives its per-kind loops
# from it, so a new definition form added to `Library` without an entry here
# is a static failure in `tests/test_family_libraries.py`, not a silently unguarded
# collision. Zones and state are absent as far as the corpus has forced, not
# permanently — what a library needs from the game it names in `requires`.
_LIBRARY_DEF_KINDS: tuple[tuple[str, str], ...] = (
    ("rules", "rule"),
    ("move_types", "move type"),
    ("functions", "function"),
    ("procedures", "procedure"),
)

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
    # A climbing round's `combinations` slot: a Combination Catalogue of the
    # game, or a registered engine's lead query; its `follows` slot: a
    # function of the game, or a registered engine's follows query.
    "climb_lead": frozenset({"catalogue", "primitive_query"}),
    "climb_follows": frozenset({"function", "primitive_query"}),
}


def _library_node_types() -> frozenset[type]:
    """Every node kind a library can hold, by walking `n.Library`'s own clauses
    through the AST's annotations."""

    def leaves(annotation: object) -> set[type]:
        out: set[type] = set()
        stack = [annotation]
        while stack:
            current = stack.pop()
            if get_origin(current) is not None:
                stack.extend(get_args(current))
            elif isinstance(current, type):
                out.add(current)
        return out

    kinds = set(get_args(n.Node))
    hints = {cls: get_type_hints(cls) for cls in kinds}
    seen: set[type] = set()
    stack = [
        cls
        for f in fields(n.Library)
        if f.name not in ("name", "span")
        for cls in leaves(hints[n.Library][f.name]) & kinds
    ]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for f in fields(current):
            stack.extend(leaves(hints[current][f.name]) & kinds)
    return frozenset(seen)


def library_reachable_namespaces() -> frozenset[str]:
    """The reference namespaces a library's own text can name: every slot of
    every node kind a library can hold, read through the registry."""
    reachable = _library_node_types()
    return frozenset(
        namespace
        for slot, namespace in _REFERENCE_SLOTS.items()
        if slot[0] in reachable and slot not in _CONTEXTUAL_SLOTS
    ) | frozenset(
        namespace
        for (cls, _), slot in _CONTEXTUAL_SLOTS.items()
        if cls in reachable
        for namespace in slot.namespaces
    )


# Each definition kind's declaration keyword, as the grammar spells it — the
# word a designer reaches for when writing a kind in a type slot. Pinned to the
# grammar's own productions by tests/test_definition_contracts.py.
_DEFINITION_KEYWORDS: dict[str, str] = {
    "rules": "rule",
    "move_types": "move_type",
    "functions": "function",
    "procedures": "procedure",
}

# Every word that names a definition KIND rather than a type, for a keyed row's
# type slot: each kind's keyword and its capitalised form, and the move row's
# own word, which names a contract only when the row is bare (`fold : Move`).
# A keyed row spelling any of them is the library author's to fix, and
# `_check_contract_shapes` is its one speaker.
_DEFINITION_KIND_WORDS: dict[str, str] = {
    **{word: field for field, word in _DEFINITION_KEYWORDS.items()},
    **{
        "".join(part.title() for part in word.split("_")): field
        for field, word in _DEFINITION_KEYWORDS.items()
    },
    n.MOVE_CONTRACT_TYPE: "move_types",
}

# The Definition Contract row node for each definition kind that has one.
_CONTRACT_ROWS: dict[str, type] = {
    "move_types": n.MoveContract,
    "functions": n.FunctionContract,
    "procedures": n.ProcedureContract,
}


def _library_element(field: str) -> type:
    """The definition node an `n.Library` field holds (`functions` ->
    `n.FunctionDef`)."""
    (element, _) = get_args(get_type_hints(n.Library)[field])
    assert isinstance(element, type)
    return element


def _contract_kinds() -> tuple[tuple[str, str, type], ...]:
    reachable = library_reachable_namespaces()
    return tuple(
        (field, noun, _CONTRACT_ROWS[field])
        for field, noun in _LIBRARY_DEF_KINDS
        if _DECLARATION_SLOTS[(_library_element(field), "name")] in reachable
    )


# The definition kinds a library can contract for, as (`n.Library` field, noun,
# row node): `_LIBRARY_DEF_KINDS` restricted to the kinds whose namespace some
# slot a library's own text holds can name. A kind no library text can name
# (rule: only a game's `active_rules:` names one) is excluded by that
# derivation, never by a list.
CONTRACT_KINDS: tuple[tuple[str, str, type], ...] = _contract_kinds()
# Runtime refusal: a row node with no contractable kind, or a contractable kind
# with no row node, would be a contract nothing checks.
if {f for f, _, _ in CONTRACT_KINDS} != set(_CONTRACT_ROWS) or set(
    _DEFINITION_KEYWORDS
) != {f for f, _ in _LIBRARY_DEF_KINDS}:
    raise AssertionError(
        "CONTRACT_KINDS, _CONTRACT_ROWS and _DEFINITION_KEYWORDS disagree about "
        "which definition kinds a library contracts for"
    )
_CONTRACT_KIND_OF: dict[type, tuple[str, str]] = {
    cls: (field, noun) for field, noun, cls in CONTRACT_KINDS
}


def check_library_alone(library: n.Library, bag: DiagnosticBag) -> None:
    """Every property a library holds by itself, with no game in sight —
    reported to the library's own author. Asked of each family library at its
    `uses` line and of the standard library at load (`stdlib.rules`)."""
    _check_library_encapsulation(library, bag)
    _check_contract_shapes(library, bag)
    _check_require_indexes(library, bag)
    for rule in library.rules:
        _refuse_play_source_params(rule, bag)


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
    rule only because no name reaches two of them: `KNOWN_TYPE_NAMES`,
    `LIBRARY_ZONE_TYPES` and the block's collection constructor are pairwise
    disjoint, and the author-chosen namespace that could have collided with
    any of them — a game's `positions { }` — is refused those spellings where
    they are DECLARED (`POSITION_NAME_SOURCES`,
    asked at every site in `RESERVATION_SITES`). Without those Owner Guards
    this function would be picking one meaning of an ambiguous name with
    nowhere to record the choice."""
    return want.type_name in LIBRARY_ZONE_TYPES


def _names_a_kind(want: n.RequireDecl) -> bool:
    """Whether a keyed row's type slot names a definition KIND
    (`_DEFINITION_KIND_WORDS`) — `x : Procedure`, `fold : move_type`,
    `fold[player] : Move`. Every such row is malformed, and
    `_check_contract_shapes` is its one speaker, so the sweeps step over it."""
    return want.type_name in _DEFINITION_KIND_WORDS


def _keyed_rows(library: n.Library) -> tuple[n.RequireDecl, ...]:
    """The library's well-worded keyed rows: the state and zones it
    contracts for."""
    return tuple(
        r
        for r in library.requires
        if isinstance(r, n.RequireDecl) and not _names_a_kind(r)
    )


def _state_rows(library: n.Library) -> tuple[n.RequireDecl, ...]:
    return tuple(r for r in _keyed_rows(library) if not is_zone_contract(r))


def _contract_rows(library: n.Library, field: str) -> tuple[n.DefinitionContract, ...]:
    """The library's Definition Contract rows of one contractable kind."""
    cls = _CONTRACT_ROWS[field]
    return tuple(
        r
        for r in library.requires
        if isinstance(r, cls) and not isinstance(r, n.RequireDecl)
    )


def _contracted(library: n.Library, field: str) -> frozenset[str]:
    return frozenset(r.name for r in _contract_rows(library, field))


def _meant(library: n.Library, field: str) -> frozenset[str]:
    """The names the library's rows contract for as definitions of one kind,
    as the author MEANT them: the well-formed rows, and the keyed rows that
    spell the kind (`fold : move_type`, `respond : Procedure`). A signature
    row whose result is no value type (`settle() : Procedure?`,
    `settle() : Void`) could have meant either a function or a procedure, so
    its name is meant as both. The slot sweep reads this one, so a misworded
    row's uses are not also reported as leaks and `_check_contract_shapes`
    (or, for an unknown result, the type slot's own sweep) stays the row's one
    speaker."""
    misworded = frozenset(
        r.name
        for r in library.requires
        if isinstance(r, n.RequireDecl)
        and _names_a_kind(r)
        and _DEFINITION_KIND_WORDS[r.type_name] == field
    )
    unread = frozenset(
        r.name
        for r in library.requires
        if isinstance(r, n.FunctionContract)
        and r.result_type.removesuffix("?") not in KNOWN_TYPE_NAMES
        and field in ("functions", "procedures")
    )
    return _contracted(library, field) | misworded | unread


def _library_slot_names(library: n.Library) -> dict[str, frozenset[str]]:
    provided = library.state.decls if library.state is not None else ()
    return {
        "state": frozenset(r.name for r in _state_rows(library))
        | frozenset(d.name for d in provided),
        # A contract's type slot may name either registry, so the sweep admits
        # both — the entry's own leg then refuses the crossed shapes (a `?` on a
        # zone type, an `<owner>` on a state type), which is a shape question
        # rather than a spelling one.
        "type": KNOWN_TYPE_NAMES | frozenset(LIBRARY_ZONE_TYPES),
        # A library reaches the definitions it holds and the ones its Definition
        # Contract rows name: those are the game's to define and the library's
        # to offer, call or run, which is the whole of why the rows exist.
        "move_type": frozenset(m.name for m in library.move_types)
        | _meant(library, "move_types"),
        "procedure": frozenset(p.name for p in library.procedures)
        | _meant(library, "procedures"),
        # BUILTIN_CALL_FUNCS, not CALL_FUNCS: a library body may call the
        # generic native functions the language ships, and may not call a
        # game-local [[primitive]]. A Primitive's meaning belongs to ONE game,
        # so a library — which several games import — naming one is the
        # cross-game coupling the `primitives { }` block exists to end; and an
        # importing game that declares a block would refuse the call anyway,
        # to ITS author rather than the library's, which is the library-alone
        # property this sweep is for.
        "function": frozenset(f.name for f in library.functions)
        | _meant(library, "functions")
        | BUILTIN_CALL_FUNCS,
        "enum_value": SEAT_DIRECTION_VALUES,
        # No longer empty: a library reaches exactly the zones it contracts for,
        # and nothing else. This is the set every zone-naming slot is swept
        # against — `Transfer.source`/`dest` as ordinary expressions, and
        # `Round.source_zone`/`play_zone` as bare strings.
        "zone": frozenset(r.name for r in _keyed_rows(library) if is_zone_contract(r)),
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


def _slot_leaks(
    library: n.Library,
) -> tuple[tuple[_SlotLeak, ...], dict[str, frozenset[str]]]:
    """Every bare-string reference in `library` that names something outside it,
    and, per namespace, the names its bare-string slots successfully READ.

    The second half is not a by-product: the reads feed the contract's
    MINIMALITY check, and before this sweep existed they accumulated from
    `NameRef`s alone — so `turns … again <var>` had no correct spelling at all.
    Naming the variable in `requires` made the entry look dead and the check
    called the contract non-minimal; leaving it out was the leak. One sweep
    answers both, which is why they are computed together rather than in two
    passes that could disagree about what a slot reaches. A zone named by a
    round's bare-string slot, a move type an offering names, a function a call
    names and a procedure a `run` names are each reached ONLY here."""
    legal = _library_slot_names(library)
    keyed = [r for r in library.requires if isinstance(r, n.RequireDecl)]
    # A `requires` entry spelling the collection constructor is not a name the
    # library is missing. `Collection` is a type word the language owns — the
    # checker prints it, and `RESERVATION_SITES` keeps any declaration from
    # taking the spelling — and its argument is an ELEMENT, not a zone owner.
    # Both slots belong to `_check_contract_shapes`, which names the one place
    # a collection is spellable; sweeping them here would answer the same
    # defect first, and in a voice that sends the author to declare a type the
    # reservation sweep then refuses.
    collection_contracts = frozenset(
        id(want) for want in keyed if want.type_name == COLLECTION_TYPE_CONSTRUCTOR
    )
    collection_elements = frozenset(
        id(arg)
        for want in keyed
        if id(want) in collection_contracts
        for arg in want.type_args
    )
    # A row's type slots are `_check_contract_shapes`' to judge wherever the
    # row names a definition: a keyed row spelling a definition kind, a
    # signature row's parameter types (each kind admits its own domain), and a
    # signature row's result spelled as a kind.
    shaped_params = frozenset(
        id(p)
        for row in library.requires
        if isinstance(row, (n.FunctionContract, n.ProcedureContract))
        for p in row.params
    )
    # `Positive` is a procedure parameter domain and no value type, so it is
    # outside the `type` namespace every other slot reads; a library
    # procedure's parameter spelling it is the procedure domain's to judge
    # (`_PROCEDURE_PARAM_DOMAINS`, checked once the definition is spliced).
    positive_params = frozenset(
        id(p)
        for proc in library.procedures
        for p in proc.params
        if p.type_name == POSITIVE_PARAM_DOMAIN
    )
    reached: dict[str, set[str]] = {
        ns: set() for ns in ("state", "zone", "move_type", "function", "procedure")
    }
    leaks: list[_SlotLeak] = []
    for node in _walk(library):
        if (
            id(node) in collection_elements
            or id(node) in shaped_params
            or id(node) in positive_params
        ):
            continue
        for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
            if field_name == "type_name" and id(node) in collection_contracts:
                continue
            if (
                field_name in ("type_name", "type_args")
                and isinstance(node, n.RequireDecl)
                and _names_a_kind(node)
            ):
                continue
            if (
                isinstance(node, n.FunctionContract)
                and node.result_type.removesuffix("?")
                in {*_DEFINITION_KIND_WORDS, POSITIVE_PARAM_DOMAIN}
            ):
                continue
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
                elif namespace in reached:
                    reached[namespace].add(bare)
    return tuple(leaks), {ns: frozenset(names) for ns, names in reached.items()}


@dataclass(frozen=True)
class _LibraryReach:
    """What a library's definitions reach for, classified against the library's
    OWN namespaces — the input to both directions of the `requires` contract:
    nothing may be reached that the contract does not cover (`unresolved`,
    `refused_calls`, `slot_leaks`), and nothing may be in the contract that is
    never reached (`dead_contract_rows`, over `state_reads`, `zone_reads` and
    `definition_reads`)."""

    unresolved: tuple[n.NameRef, ...]
    refused_calls: tuple[n.Call, ...]
    card_literals: tuple[n.CardLiteral, ...]
    slot_leaks: tuple[_SlotLeak, ...]
    state_reads: frozenset[str]
    zone_reads: frozenset[str]
    #: The refusals `_rewrite` records for an undeclared `always` standing as
    #: a whole predicate: the clause's own words, never a read past the
    #: contract.
    always_refused: tuple[Diagnostic, ...]
    #: The definitions the library's text names, per definition namespace
    #: (`move_type`, `function`, `procedure`).
    definition_reads: dict[str, frozenset[str]]
    #: Each unresolved name's Near Misses, by span, as `_rewrite` ranked them
    #: against the scope it read the name in (locals and pronouns included).
    unresolved_near: dict[Span | None, tuple[str, ...]]


def _library_reach(library: n.Library) -> _LibraryReach:
    """Classify every definition in `library` against the library alone.

    The namespaces are what `_categories` would build for a game whose entire
    state is the contract and which has nothing else — deliberately narrower
    than any real game's:

    - `zones` is empty because a library declares no zones of its own; the
      zones it reaches are the game's, contracted through `requires`
      (decisions.md "Family libraries");
    - `ranks`/`suits`/`enums` are what the unknown-deck branch of `_categories`
      leaves, because a library is deck-agnostic. `hearts` means nothing until
      an including game names a deck, and Kuhn's has none.

    `_Categories` is frozen with every field required, so a namespace added to
    it is a mypy error here rather than a silently permissive hole.

    A name held on a node as a plain `str` is invisible to that classification —
    `_rewrite` classifies `NameRef`s, and nothing else. Those slots are swept
    SEPARATELY and from the registry (`_slot_leaks`), never by a hand-list
    beside it: `card_literals` and `refused_calls` below are derived from that
    sweep rather than collected alongside it, because a table that lands next to
    the list it replaces leaves the drift exactly where it was."""
    provided_state = library.state.decls if library.state is not None else ()
    cats = _Categories(
        locals=frozenset(),
        # Both halves of the library's state surface: what it contracts for and
        # what it owns. A definition may reach either — the contract is
        # sufficient for the library's own variables trivially, since it declares
        # them itself.
        state_vars=frozenset(r.name for r in _state_rows(library))
        | frozenset(d.name for d in provided_state),
        # The OTHER of the two name sets a library is checked against. It is
        # computed here and in `_library_slot_names` from different inputs, so a
        # zone contract fed to one and not the other would leave half the sweep
        # blind — which is the shape of the defect the slot registry exists for.
        zones=frozenset(r.name for r in _keyed_rows(library) if is_zone_contract(r)),
        enums=SEAT_DIRECTION_VALUES,
        ranks=frozenset(),
        suits=frozenset(),
        definitions=frozenset(d.name for field, _ in _LIBRARY_DEF_KINDS for d in getattr(library, field))
        | frozenset(r.name for field, _, _ in CONTRACT_KINDS for r in _contract_rows(library, field)),
    )
    # `_rewrite` both classifies and reports, and its report ("unresolved name
    # 'x'") is the GAME's author — the wrong one here — so that report is
    # dropped and the classified TREE is read instead. Reading `ref_kind` is
    # the sanctioned use of what this pass stamps (see the module Contract),
    # not a re-derivation: which names a body binds, and where, stays the
    # property of `_introduced_binders` and `_BINDER_SCOPE_FIELDS` alone. The
    # one report that stands wherever the clause is written — the `always`
    # refusal, whose words are the clause author's — is kept as `_rewrite`
    # recorded it, so whether it fired is never reconstructed here.
    collected = DiagnosticBag()
    classified: list[object] = []
    for field, _ in _LIBRARY_DEF_KINDS:
        classified.append(_rewrite_value(getattr(library, field), cats, collected))
    # A provided variable's DEFAULT is an expression like any other, so it can
    # leak like any other — `limit : Integer = house_rule` would reach past the
    # contract into the game exactly as a move-type effect would.
    classified.append(_rewrite_value(provided_state, cats, collected))

    teaching = {_always_message(clause) for clause in ALWAYS_HOLDERS}
    always_refused = tuple(d for d in collected.items if d.message in teaching)
    refused_spans = {d.span for d in always_refused}

    unresolved: list[n.NameRef] = []
    state_reads: set[str] = set()
    zone_reads: set[str] = set()
    for node in _child_nodes(tuple(classified)):
        if isinstance(node, n.NameRef):
            if node.ref_kind is None:
                if node.span not in refused_spans:
                    unresolved.append(node)
            elif node.ref_kind == "state_var":
                state_reads.add(node.name)
            elif node.ref_kind == "zone":
                zone_reads.add(node.name)

    # The bare-string half, over the WHOLE library rather than the classified
    # definitions: `requires` has no expression to classify but its type names
    # are references like any other, so a contract can name a type only the
    # importing game defines.
    leaks, slot_reads = _slot_leaks(library)
    # Two namespaces keep a message of their own, so they are lifted out of the
    # generic list rather than reported twice: a card literal says why a family
    # library is deck-agnostic, and a refused call says what the called name
    # is (`_library_own_name_is`, `_language_name_is`). Both are FOUND by the
    # registry — only their wording is special.
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
        refused_calls=calls,
        card_literals=cards,
        slot_leaks=rest,
        state_reads=frozenset(state_reads) | slot_reads["state"],
        zone_reads=frozenset(zone_reads) | slot_reads["zone"],
        definition_reads={
            ns: slot_reads[ns] for ns in ("move_type", "function", "procedure")
        },
        always_refused=always_refused,
        unresolved_near={d.span: d.near_misses for d in collected.items},
    )


def dead_contract_rows(library: n.Library) -> frozenset[str]:
    """The `requires` rows no text in the library reaches: a state row no
    read names, a zone row no zone slot names, a Definition Contract row no
    offering, call or `run` names. The contract's MINIMALITY, asked of every
    library by tests/test_family_libraries.py, and of a dead move or procedure
    row by `_check_contract_shapes`, since no game could answer one."""
    reach = _library_reach(library)
    reached = (
        reach.state_reads
        | reach.zone_reads
        | frozenset().union(*reach.definition_reads.values())
    )
    return frozenset(r.name for r in library.requires) - reached


_NAMESPACE_NOUN: dict[str, str] = {
    "state": "state variable",
    "zone": "zone",
    "phase": "phase",
    "mode": "mode",
    "type": "type",
    "move_type": "move type",
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
        "use a built-in type, or keep this definition in the game (a `requires` "
        "row's type is a state type, a kernel zone type, `Move` for a move type "
        "the game defines, or a function row's result type)"
    ),
    "move_type": (
        "define the move type in the library, contract for it with "
        "`<name> : Move` in `requires { }` so the including game defines it, "
        "or keep this definition in the game"
    ),
    "procedure": (
        "define the procedure in the library, contract for it with "
        "`<name>(<parameter> : <type>, …) : Procedure` in `requires { }` so the "
        "including game defines it, or keep this definition in the game"
    ),
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


@dataclass(frozen=True)
class _LibraryNameIs:
    """What a name a library body cannot reach actually is: the phrase that
    says so, and which refusal it earns — `primitive` the rule that keeps
    game-local Python out of a shared library, `function` a reminder that a
    function is called, `other` the plain statement of what the name is."""

    phrase: str
    kind: Literal["primitive", "function", "other"]


# The namespaces `_library_slot_names` holds that are the library's own — its
# contract, and the direction values every body holds — in the order a name
# held by two is reported. `function` and `procedure` are the library's own
# definitions, answered by `_LIBRARY_DEF_KINDS` first.
_LIBRARY_OWN_NAMESPACES: tuple[str, ...] = ("state", "zone", "move_type", "enum_value")


def _cite_own(library: n.Library, name: str, words: str) -> Said:
    """`words` naming `name` in `library`: a citation of its own definition,
    provided declaration or contract row of that name, and the bare words
    where it holds none."""
    held: list[object] = [
        *(d for field, _noun in _LIBRARY_DEF_KINDS for d in getattr(library, field)),
        *(library.state.decls if library.state is not None else ()),
        *library.requires,
    ]
    found = next((d for d in held if getattr(d, "name", None) == name), None)
    return words if found is None else cite_named(found, words)


def _library_own_name_is(library: n.Library, name: str) -> _LibraryNameIs | None:
    """What `name` is in the library itself: one of its own definitions, or a
    name its contract or the direction values hold — or None. Every answer is
    the library's own, the same whichever game imports it, so both a call and
    a bare read are answered from here."""
    for field, noun in _LIBRARY_DEF_KINDS:
        if any(d.name == name for d in getattr(library, field)):
            kind: Literal["function", "other"] = "function" if field == "functions" else "other"
            return _LibraryNameIs(f"a {noun} the library defines", kind)
    for field, noun, _cls in CONTRACT_KINDS:
        if name in _contracted(library, field):
            kind = "function" if field == "functions" else "other"
            return _LibraryNameIs(
                f"a {noun} the including game defines under this library's contract",
                kind,
            )
    legal = _library_slot_names(library)
    for namespace in _LIBRARY_OWN_NAMESPACES:
        if name in legal[namespace]:
            return _LibraryNameIs(f"a {_NAMESPACE_NOUN[namespace]}", "other")
    return None


def _language_name_is(library: n.Library, name: str) -> _LibraryNameIs | None:
    """What `name` is in the language — a type, a kernel move type, a stdlib
    rule, a walled Primitive, a Primitive, or a Builtin — or None. True of the
    spelling in every game, but it is not what a BARE read means: an importing
    game may declare state under any of these spellings, and the library then
    reaches it by contracting for it, so an uncontracted bare read is a
    missing contract entry as plausibly as anything here. Only a call is
    answered from here, since nothing an importer declares is callable from a
    library. The trick winners are not asked: `_callback_outside_slot` is
    their one sentence, in a game and a library alike."""
    if name in _library_slot_names(library)["type"]:
        return _LibraryNameIs("a type", "other")
    if name in LIBRARY_MOVE_TYPES:
        return _LibraryNameIs("a move type", "other")
    if name in stdlib_rules():
        return _LibraryNameIs("a rule", "other")
    walled = walled_namespace_of(name)
    if walled is not None:
        return _LibraryNameIs(walled, "other")
    if name in PRIMITIVE_CALL_FUNCS:
        return _LibraryNameIs("a Primitive", "primitive")
    if name in BUILTIN_CALL_FUNCS:
        return _LibraryNameIs("a function", "function")
    return None


# Where library text names a Primitive -> (what the library does with it, the
# fix). A call's value can be computed by the game and passed in; a round slot
# takes a bare name, so the round itself moves to the game.
_PrimitivePosition = Literal["call", "round slot"]
_PRIMITIVE_POSITIONS: dict[_PrimitivePosition, tuple[str, str, str]] = {
    "call": (
        "calls",
        "call",
        "compute the value in the game and pass it to the library's function as "
        "an argument, or keep the definition that needs it in the game",
    ),
    "round slot": (
        "names",
        "name",
        "a round slot takes a name, never a value, so the game cannot pass this "
        "one in — write the round in the game, in a phase or in a move type the "
        "game defines",
    ),
}


def _by_sort(library: n.Library, family: Said, standard: Said) -> Said:
    """The sentence that is true of `library`'s sort: a family library asks a
    game through its `requires` contract, and the standard library, which no
    `uses` line imports, defines what it reads."""
    sort = library_sort(library.name)
    match sort:
        case LibrarySort.FAMILY:
            return family
        case LibrarySort.STANDARD:
            return standard
        case _:
            assert_never(sort)


def _primitive_in_library(
    library: n.Library, position: _PrimitivePosition, name: str, at: Span | None
) -> Said:
    """The refusal for a Primitive library text names. The library's
    `function` namespace is `BUILTIN_CALL_FUNCS` (`_library_slot_names`) and
    its round slots admit no Primitive (`_round_slot_primitives`), so this is
    that rule said to the library's author, with the fix that keeps the
    Primitive in the one game that declares it."""
    verb, act, fix = _PRIMITIVE_POSITIONS[position]
    return (
        cite_library(library.name, at) + f" {verb} '{name}', which is a Primitive — a "
        f"Primitive belongs to the one game that declares it, so a library that "
        f"several games import may not {act} one: {fix}"
    )


# The reference namespaces whose slot may hold a registered round query.
_PRIMITIVE_QUERY_NAMESPACES = frozenset(
    ns for ns, members in {"primitive_query": {"primitive_query"}, **_UNION_NAMESPACES}.items()
    if "primitive_query" in members
)


def _round_slot_primitives(library: n.Library) -> list[tuple[object, str]]:
    """Every (node, name) where a round in `library` names, in a query slot, a
    Primitive that slot's registry holds. A name outside the registry is left
    to `_validate_refs`, which refuses it for a game and a library alike."""
    found: list[tuple[object, str]] = []
    for node in _walk(library):
        for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
            if slot_namespace(node, field_name) not in _PRIMITIVE_QUERY_NAMESPACES:
                continue
            accepted = _ROUND_QUERY_REGISTRIES[(type(node), field_name)]
            found.extend(
                (node, name)
                for name in slot_strings(node, field_name)
                if name in accepted and walled_namespace_of(name) is not None
            )
    return found


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
    bag.items.extend(reach.always_refused)
    # A bare read is answered only from the library itself: every language-wide
    # spelling (`_language_name_is`, the trick winners) is one an importing
    # game may declare as state, which the library then reaches by contract.
    for ref in reach.unresolved:
        what = _library_own_name_is(library, ref.name)
        if what is None:
            # The set the name was read against is the scope `_rewrite` held,
            # and its Near Misses are the ones ranked there.
            bag.unknown(
                _by_sort(
                    library,
                    cite_library(library.name, ref.span) + f" reads '{ref.name}', which is neither in "
                    f"its `requires` contract nor defined in the library — add it to "
                    f"`requires {{ }}` if the including game must declare it, or move "
                    f"the definition that needs it into the game",
                    cite_library(library.name, ref.span) + f" reads '{ref.name}', which it does "
                    f"not define; it may read only what it defines and what every "
                    f"game has, so define the name in it",
                ),
                ref.name,
                reach.unresolved_near.get(ref.span, ()),
                ref.span,
                code=library_text_codes(library.name).reads_undefined_name,
            )
        else:
            call_it: Said = (
                " — call it: `" + _cite_own(library, ref.name, ref.name) + "(...)`"
                if what.kind == "function" else ""
            )
            bag.error(
                cite_library(library.name, ref.span) + " reads "
                + _cite_own(library, ref.name, f"'{ref.name}'") + ", which is "
                f"{what.phrase}, not a value" + call_it,
                ref.span,
                code=Code.WRONG_SORT_OF_NAME,
            )
    for call in reach.refused_calls:
        if call.func in VALUE_NAMES:
            bag.error(_callback_outside_slot(call.func), call.span, code=Code.WRONG_SORT_OF_NAME)
            continue
        what = _library_own_name_is(library, call.func) or _language_name_is(
            library, call.func
        )
        if what is None and call.func in K.CONTRACTS:
            # The game owns the fact; a library reaches it through the row the
            # kernel states.
            bag.error(
                _by_sort(
                    library,
                    cite_library(library.name, call.span) + f" calls '{call.func}', a "
                    f"fact each game answers for itself — contract for it with "
                    f"`{K.CONTRACTS[call.func].spelled}` in `requires {{ }}`",
                    cite_library(library.name, call.span) + f" calls '{call.func}', a "
                    f"fact each game answers for itself, and it has no `requires` "
                    f"contract to ask a game for one, so it may not call it",
                ),
                call.span,
                code=library_text_codes(library.name).reads_undefined_name,
            )
        elif what is None:
            bag.unknown(
                _by_sort(
                    library,
                    cite_library(library.name, call.span) + f" calls '{call.func}', which is neither "
                    f"defined in the library nor a native function — contract for it "
                    f"with `{call.func}(<parameter> : <type>, …) : <result type>` in "
                    f"`requires {{ }}` so the including game defines it, or keep the "
                    f"definition that needs it in the game",
                    cite_library(library.name, call.span) + f" calls '{call.func}', which is neither "
                    f"defined in it nor a native function — define the function in it",
                ),
                call.func,
                _library_slot_names(library)["function"],
                call.span,
                code=library_text_codes(library.name).reads_undefined_name,
            )
        elif what.kind == "primitive":
            bag.error(_primitive_in_library(library, "call", call.func, call.span), call.span, code=library_text_codes(library.name).reaches_one_game)
        else:
            bag.error(
                cite_library(library.name, call.span) + " calls "
                + _cite_own(library, call.func, f"'{call.func}'") + ", which is "
                f"{what.phrase}, not a function",
                call.span,
                code=Code.WRONG_SORT_OF_NAME,
            )
    for node, name in _round_slot_primitives(library):
        at = getattr(node, "span", None)
        bag.error(_primitive_in_library(library, "round slot", name, at), at, code=library_text_codes(library.name).reaches_one_game)
    for card in reach.card_literals:
        bag.error(
            _by_sort(
                library,
                cite_library(library.name, card.span) + f" names the card `{card.rank} of "
                f"{card.suit}`, but a family library is deck-agnostic — its members "
                f"do not share a deck, and Kuhn's holds three cards. Take the card "
                f"as a parameter, or keep the definition that needs it in the game",
                cite_library(library.name, card.span) + f" names the card `{card.rank} of "
                f"{card.suit}`, but it is deck-agnostic — every game "
                f"reads it, whatever its deck. Take the card as a parameter",
            ),
            card.span,
            code=library_text_codes(library.name).reaches_one_game,
        )
    for leak in reach.slot_leaks:
        # A `run` or an offering naming one of the library's own definitions
        # of another kind is told what the name is, as a call is.
        own = (
            _library_own_name_is(library, leak.name)
            if leak.namespace in ("procedure", "move_type")
            else None
        )
        if own is not None:
            bag.error(
                cite_library(library.name, getattr(leak.node, "span", None)) + " names "
                + _cite_own(library, leak.name, f"'{leak.name}'") + " as a "
                f"{_NAMESPACE_NOUN[leak.namespace]}, but it is {own.phrase}, not "
                f"a {_NAMESPACE_NOUN[leak.namespace]}",
                getattr(leak.node, "span", None),
                code=Code.WRONG_SORT_OF_NAME,
            )
            continue
        if leak.namespace == "type" and leak.name.removesuffix("?") == COMBINATION_TYPE_NAME:
            # The one built-in type no library names: a climbing play exists
            # while a game's round asks the game's own follows function.
            bag.error(
                cite_library(library.name, getattr(leak.node, "span", None)) + f" names "
                f"the type '{leak.name}', a climbing play of a game's own "
                f"combination catalogue, which only that game's follows "
                f"function and the helpers it passes one to hold — keep the "
                f"definition in the game",
                getattr(leak.node, "span", None),
                code=library_text_codes(library.name).reaches_one_game,
            )
            continue
        bag.unknown(
            _by_sort(
                library,
                cite_library(library.name, getattr(leak.node, "span", None)) + f" names the "
                f"{_NAMESPACE_NOUN[leak.namespace]} '{leak.name}', which the library "
                f"does not have — it would resolve against whichever game imports "
                f"this, so the library is not self-contained: "
                f"{_NAMESPACE_ADVICE[leak.namespace]}",
                cite_library(library.name, getattr(leak.node, "span", None)) + f" names the "
                f"{_NAMESPACE_NOUN[leak.namespace]} '{leak.name}', which it does not "
                f"define; it may read only what it defines and what every game has",
            ),
            leak.name.removesuffix("?"),
            _library_slot_names(library).get(leak.namespace, frozenset()),
            getattr(leak.node, "span", None),
            code=library_text_codes(library.name).reads_undefined_name,
        )
    # A PROVIDED default reaching the contract is in scope for the general
    # declare-order Owner Guard too (`_check_state_default_scope`), which would refuse
    # it after the splice with a span in this same file. It is caught here as
    # well, and first, because the splice destroys the distinction the library
    # author needs: post-splice a required name is just a state variable
    # declared later, so the general Owner Guard's advice — declare it earlier — is
    # advice they cannot take. Only the game can declare required state, and it
    # always lands after the library's own.
    required = {r.name for r in _keyed_rows(library)}
    provided = library.state.decls if library.state is not None else ()
    for decl in provided:
        for node in _walk(decl.default):
            # Matched by name, not by `ref_kind`: these decls are the raw ones,
            # classified only inside `_library_reach`. A binder inside a default
            # shadowing a required name would be refused too — conservative, and
            # unreachable from a default worth writing.
            if isinstance(node, n.NameRef) and node.name in required:
                bag.error(
                    cite_library(library.name, node.span or decl.span)
                    + " initialises provided state " + cite_named(decl, f"'{decl.name}'")
                    + " from " + _cite_own(library, node.name, f"'{node.name}'")
                    + ", which its `requires` contract asks the game to declare — so "
                    + _cite_own(library, node.name, f"'{node.name}'") + " does "
                    f"not exist yet when this default runs: provided state is "
                    f"declared before the game's own, never after. Give "
                    + cite_named(decl, f"'{decl.name}'") + " a literal default and set it from "
                    + _cite_own(library, node.name, f"'{node.name}'") + " in a phase",
                    node.span or decl.span,
                    code=Code.OUTSIDE_FAMILY_LIBRARY_CONTRACT,
                )


def _spelled_contract(want: n.ContractRow) -> str:
    """A `requires` entry as its author wrote it, for a diagnostic to quote."""
    if isinstance(want, n.MoveContract):
        return f"{want.name} : {n.MOVE_CONTRACT_TYPE}"
    if isinstance(want, (n.FunctionContract, n.ProcedureContract)):
        listed = ", ".join(f"{p.name} : {p.type_name}" for p in want.params)
        result = (
            want.result_type
            if isinstance(want, n.FunctionContract)
            else n.PROCEDURE_CONTRACT_TYPE
        )
        return f"{want.name}({listed}) : {result}"
    index = f"[{want.index}]" if want.index else ""
    args = f"<{', '.join(a.name for a in want.type_args)}>" if want.type_args else ""
    return f"{want.name}{index} : {want.type_name}{args}"


def _check_contract_shapes(library: n.Library, bag: DiagnosticBag) -> None:
    """Every `requires` entry names a shape SOME game could declare or define —
    checked against the library alone, before any game is consulted.

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
    no game could meet. A signature row's parameter domains are the same kind
    of second implementation, of `_check_declared_type_names` (functions) and
    `_PROCEDURE_PARAM_DOMAINS` (procedures), pinned equal by
    tests/test_definition_contracts.py.

    One asymmetry, by exclusion: `_resolve_zone` also refuses a position-indexed
    family whose type has distinct owner/others projections. A contract cannot
    be position-indexed at all (`index_domain` is swept to the roles), so the
    case does not arise here."""
    _check_contract_names(library, bag)
    for want in library.requires:
        if isinstance(want, (n.FunctionContract, n.ProcedureContract)):
            _check_signature_row(library, want, bag)
            continue
        if isinstance(want, n.MoveContract):
            continue
        spelled = _spelled_contract(want)
        if _names_a_kind(want):
            _refuse_kind_word(library, want, bag)
            continue
        if want.type_name == COLLECTION_TYPE_CONSTRUCTOR:
            # A collection is neither a zone type nor a state type, so the
            # split below would answer a placement question with a shape one.
            # No parse twin lands here: a contract spells its type inline and
            # derives `<…>` through `type_args`, and a twin over that
            # derivation would give one string two derivations. This is the
            # entry's ONLY speaker: `_slot_leaks` steps over both slots of a
            # collection contract so the author does not first meet a sweep
            # calling a word the language owns a name the library lacks.
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span) + f", and a "
                f"collection type (`Collection<Card>`) is spellable in a "
                f"`primitives {{ }}` entry only — a contract names a "
                f"`state {{ }}` or a `zones {{ }}` declaration, or a definition "
                f"the game defines (`<name> : {n.MOVE_CONTRACT_TYPE}`, "
                f"`<name>(…) : <result type>`, `<name>(…) : "
                f"{n.PROCEDURE_CONTRACT_TYPE}`), and a library declares no "
                f"Primitives",
                want.span,
                code=Code.CHECKER_TYPE_NOT_ALLOWED_HERE,
            )
            continue
        if not is_zone_contract(want):
            if want.type_args:
                bag.error(
                    cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span) + f", but "
                    f"'{want.type_name}' is a state type and takes no type "
                    f"argument — the `<…>` form belongs to zone types",
                    want.span,
                    code=Code.WRONG_ARGUMENT_COUNT,
                )
            continue
        takes_owner = LIBRARY_ZONE_TYPES[want.type_name]
        if takes_owner and len(want.type_args) != 1:
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span) + f", but zone type "
                f"'{want.type_name}' takes one owner argument, got "
                f"{len(want.type_args)}",
                want.span,
                code=Code.WRONG_ARGUMENT_COUNT,
            )
        elif not takes_owner and want.type_args:
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span) + f", but zone type "
                f"'{want.type_name}' takes no type arguments",
                want.span,
                code=Code.WRONG_ARGUMENT_COUNT,
            )
        for arg in want.type_args:
            if want.index is None:
                bag.error(
                    cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span) + f", an owned "
                    f"zone type with no index — the runtime keys a zone family "
                    f"by its index, so the owner would be silently ignored; "
                    f"write `{want.name}[{arg.name}] : {want.type_name}"
                    f"<{arg.name}>`",
                    want.span,
                    code=Code.WRONG_SUBSCRIPT,
                )
            elif arg.name != want.index:
                bag.error(
                    cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span) + f", whose "
                    f"owner argument names a different domain than its index — "
                    f"write `{want.type_name}<{want.index}>`",
                    want.span,
                    code=Code.WRONG_SUBSCRIPT,
                )
    _check_contract_reach(library, bag)


def _refuse_kind_word(library: n.Library, want: n.RequireDecl, bag: DiagnosticBag) -> None:
    """A keyed row whose type slot names a definition kind
    (`_DEFINITION_KIND_WORDS`): each kind is told the row to write."""
    spelled = _spelled_contract(want)
    field = _DEFINITION_KIND_WORDS[want.type_name]
    head = cite_library(library.name, want.span) + f" requires " + cite_where(f"`{spelled}`", want.span)
    if field == "move_types":
        if want.type_name != n.MOVE_CONTRACT_TYPE:
            why = f"`{want.type_name}` names the kind, not the row's type word"
            code = Code.WRONG_SPELLING
        elif want.index is not None:
            why = "a move type has no index"
            code = Code.WRONG_SUBSCRIPT
        else:
            why = "a move type contract takes no type argument"
            code = Code.WRONG_ARGUMENT_COUNT
        message = (
            head + f", but {why} — write `" + cite_named(want, want.name)
            + f" : {n.MOVE_CONTRACT_TYPE}`"
        )
    elif field == "functions":
        message = (
            head + f", but a function the game defines is contracted by its "
            f"signature, not by a kind word — write `" + cite_named(want, want.name)
            + "(<parameter> : <type>, …) : <result type>`"
        )
        code = Code.WRONG_SPELLING
    elif field == "procedures":
        message = (
            head + f", but a procedure the game defines is contracted by its "
            f"signature, not by a kind word — write `" + cite_named(want, want.name)
            + f"(<parameter> : <type>, …) : {n.PROCEDURE_CONTRACT_TYPE}`"
        )
        code = Code.WRONG_SPELLING
    else:
        message = (
            head + f", but a rule cannot be contracted: only a game's "
            f"`active_rules:` names a rule, and a library has no `active_rules:`, "
            f"so no library text could use one — keep the definition that needs "
            f"it in the game"
        )
        code = Code.FAMILY_LIBRARY_CANNOT_REQUIRE_A_GAME_RULE
    bag.error(message, want.span, code=code)


def _check_signature_row(
    library: n.Library,
    want: n.FunctionContract | n.ProcedureContract,
    bag: DiagnosticBag,
) -> None:
    """A function or procedure row's own spelling: a name the language does not
    already hold, parameters a definition of that kind could declare, and — for
    a function — a result type a value can have."""
    head = cite_library(library.name, want.span) + f" requires " + cite_where(f"`{_spelled_contract(want)}`", want.span)
    if isinstance(want, n.FunctionContract):
        if want.name in BUILTIN_CALL_FUNCS:
            bag.error(
                head + f", but " + cite_where(f"'{want.name}'", want.span) + f" is a function every game has — call "
                f"it directly; it needs no contract row",
                want.span,
                code=Code.REQUIRES_WHAT_IS_PROVIDED,
            )
        elif want.name in K.KERNEL_CONTRACT_NAMES:
            row = K.CONTRACTS[want.name]
            if (
                tuple(p.type_name for p in want.params) != ("Card",)
                or want.result_type != row.result_spelling
            ):
                bag.error(
                    head + f", but the kernel's contract is `{row.spelled}` — "
                    f"the game answers the kernel's row, so write the row as "
                    f"the kernel states it",
                    want.span,
                    code=Code.WRONG_SIGNATURE,
                )
        elif want.name in _ROUND_QUERY_NAMES:
            bag.error(
                head + f", but " + cite_where(f"'{want.name}'", want.span) + f" is the language's own callback "
                f"that {_round_query_slot(want.name)} names, and a game whose "
                f"round names it may not define a function of that name — rename "
                f"the row",
                want.span,
                code=Code.NAME_TAKEN,
            )
        elif want.name in PRIMITIVE_CALL_FUNCS:
            bag.error(
                head + f", but " + cite_where(f"'{want.name}'", want.span) + f" is a Primitive, which belongs to the "
                f"one game that declares it — a library several games import may "
                f"not reach one, so name a function each game defines in the "
                f"language",
                want.span,
                code=Code.FAMILY_LIBRARY_REACHES_ONE_GAME,
            )
        _check_signature_result(library, want, bag)
    seen: set[str] = set()
    for p in want.params:
        if p.name in seen:
            bag.error(
                head + f", which names more than one parameter named '{p.name}' — "
                f"rename one",
                want.span,
                code=Code.NAME_TAKEN,
            )
        seen.add(p.name)
        if p.name in RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS:
            bag.error(
                head + f", whose parameter '{p.name}' is spelled like a word the "
                f"language reserves — the game's definition could not take it, "
                f"so rename it",
                want.span,
                code=Code.RESERVED_WORD,
            )
        if isinstance(want, n.FunctionContract):
            admitted = p.type_name.removesuffix("?") in KNOWN_TYPE_NAMES
            domains = "a value type (" + ", ".join(sorted(KNOWN_TYPE_NAMES)) + "), with or without `?`"
        else:
            admitted = p.type_name in _PROCEDURE_PARAM_DOMAINS
            domains = ", ".join(sorted(_PROCEDURE_PARAM_DOMAINS))
        if not admitted:
            noun = "function" if isinstance(want, n.FunctionContract) else "procedure"
            bag.error(
                head + f", whose parameter `{p.name} : {p.type_name}` no {noun} "
                f"could declare — a {noun} parameter is {domains}",
                want.span,
                code=Code.CHECKER_TYPE_NOT_ALLOWED_HERE,
            )


def _check_signature_result(
    library: n.Library, want: n.FunctionContract, bag: DiagnosticBag
) -> None:
    """A function row's result: a value type, with or without `?`. An unknown
    word is the slot sweep's (`_slot_leaks`, the `type` namespace); every
    spelling the language gives another meaning is refused here, naming it."""
    head = cite_library(library.name, want.span) + f" requires " + cite_where(f"`{_spelled_contract(want)}`", want.span)
    bare = want.result_type.removesuffix("?")
    if bare in KNOWN_TYPE_NAMES:
        return
    if bare == n.PROCEDURE_CONTRACT_TYPE:
        message = (
            head + f", but a procedure returns no value, so its row carries no "
            f"`?` — write `" + cite_named(want, want.name) + f"(…) : {n.PROCEDURE_CONTRACT_TYPE}`"
        )
        code = Code.WRONG_SPELLING
    elif bare == n.MOVE_CONTRACT_TYPE:
        message = (
            head + f", but a move type is offered by name and passed no "
            f"arguments — write `" + cite_named(want, want.name) + f" : {n.MOVE_CONTRACT_TYPE}`"
        )
        code = Code.WRONG_SPELLING
    elif bare in _DEFINITION_KIND_WORDS:
        message = (
            head + f", but '{want.result_type}' names a kind of definition, not "
            f"the type the function returns — write the result's type"
        )
        code = Code.CHECKER_TYPE_NOT_ALLOWED_HERE
    elif bare in LIBRARY_ZONE_TYPES:
        message = (
            head + f", but '{bare}' is a zone type — a function returns a value, "
            f"and a zone the game declares is contracted as a keyed row"
        )
        code = Code.CHECKER_TYPE_NOT_ALLOWED_HERE
    elif bare == POSITIVE_PARAM_DOMAIN:
        message = (
            head + f", but `{POSITIVE_PARAM_DOMAIN}` is a procedure parameter's "
            f"domain, a number written at the `run`, not the type a function "
            f"returns — write `Integer`"
        )
        code = Code.CHECKER_TYPE_NOT_ALLOWED_HERE
    else:
        return
    bag.error(message, want.span, code=code)


def _check_contract_names(library: n.Library, bag: DiagnosticBag) -> None:
    """A library names each thing once: two rows of one name, or a Definition
    Contract row whose name the library also provides as state or defines as a
    definition of ANOTHER kind, would leave a body's use of the name meaning
    whichever reading the sweep happens to try first. The same kind is
    `_check_definition_claims`', whose sentence names the two clauses."""
    seen: dict[str, n.ContractRow] = {}
    provided = {d.name for d in library.state.decls} if library.state is not None else set()
    for want in library.requires:
        if want.name in seen:
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"'{want.name}'", want.span) + f" in more than "
                f"one row — a contract names each thing once; keep one row",
                want.span,
                code=Code.WRITTEN_TWICE,
            )
            continue
        seen[want.name] = want
        if isinstance(want, n.RequireDecl):
            continue
        own_field = _CONTRACT_KIND_OF[type(want)][0]
        clashes = [
            noun
            for field, noun in _LIBRARY_DEF_KINDS
            if field != own_field and any(d.name == want.name for d in getattr(library, field))
        ] + (["provided state"] if want.name in provided else [])
        for noun in clashes:
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"'{want.name}'", want.span) + f" as a "
                f"{_CONTRACT_KIND_OF[type(want)][1]} and also holds a {noun} of "
                f"that name — rename one",
                want.span,
                code=Code.NAME_TAKEN,
            )


def _check_contract_reach(library: n.Library, bag: DiagnosticBag) -> None:
    """The Definition Contract rows the library's own text must reach for any
    game to answer them, and the one place a procedure row may be run.

    A move-type row the library never offers, or a procedure row it never
    runs, is a contract no game can meet: the game's move type would be
    refused as never offered and its procedure as never run. A function row
    nothing calls is merely dead, which the minimality pin asks of every
    library (`dead_contract_rows`). And a procedure may not run another, so a
    library procedure running a procedure row is told the row's one home: a
    library move type's effect."""
    dead = dead_contract_rows(library)
    for want in library.requires:
        if want.name not in dead:
            continue
        if isinstance(want, n.MoveContract):
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"`{_spelled_contract(want)}`", want.span) + f" "
                f"but never offers it — a game's " + cite_where(f"`{want.name}`", want.span) + f" would be refused "
                f"as never offered, so no game could answer the row: offer it, "
                f"or drop the row",
                want.span,
                code=Code.UNUSED_DECLARATION,
            )
        elif isinstance(want, n.ProcedureContract):
            bag.error(
                cite_library(library.name, want.span) + f" requires " + cite_where(f"`{_spelled_contract(want)}`", want.span) + f" "
                f"but never runs it — a game's " + cite_where(f"`{want.name}`", want.span) + f" would be refused as "
                f"never run, so no game could answer the row: run it from a "
                f"move type's effect, or drop the row",
                want.span,
                code=Code.UNUSED_DECLARATION,
            )
    rows = _contracted(library, "procedures")
    for proc in library.procedures:
        for nd in _walk(proc):
            if isinstance(nd, n.RunStmt) and nd.name in rows:
                bag.error(
                    cite_library(library.name, nd.span) + f": procedure " + cite_named(proc, f"'{proc.name}'") + " runs "
                    + _cite_own(library, nd.name, f"'{nd.name}'") + ", which the including game "
                    "defines under " + cite_library(library.name, nd.span) + "'s contract — a "
                    "procedure may not run another, so "
                    f"run it from a move type's effect",
                    nd.span,
                    code=Code.NOT_YET_SUPPORTED,
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
    # A move-type contract's index is `_check_contract_shapes`' to refuse: a
    # move type has no index at all, so a role question would be the wrong one.
    for decl, verb in [(w, "requires") for w in _keyed_rows(library)] + [
        (d, "provides") for d in provided
    ]:
        if decl.index is None or role_of(decl.index) in ZONE_INDEX_ROLES:
            continue
        roles = ", ".join(role_names(ZONE_INDEX_ROLES))
        bag.unknown(
            cite_library(library.name, decl.span) + f" {verb} state "
            + cite_named(decl, f"'{decl.name}'") + " indexed by "
            f"'{decl.index}', which is not an indexable role ({roles}) — a "
            f"library indexes by a seat or a team, and a game may not declare "
            f"that index either",
            decl.index,
            role_names(ZONE_INDEX_ROLES),
            decl.span,
            code=Code.WRONG_SUBSCRIPT,
        )
