"""The [[primitives-block]]'s registries: regime, implementation index, walls.

A game declares the [[primitive]]s it borrows from outside the DSL in a
`primitives { }` block beside `uses`
(docs/design-notes/primitive-sidecars.md section 2). The block's PRESENCE
partitions the game's native-call namespace in both directions, the `trick_order { }`
mechanism one construct over: a game with a block names its own declared
primitives and no other game's, and a game without one keeps the hand-authored
`PRIMITIVE_CALL_FUNCS` namespace — which admits every Primitive by name and
lets none of them run, since a declaration is a Primitive's only route to
Python. `regime` below is the ONE site that asks which, so no consumer
re-derives it from `game.primitives is None`.

This module is a LEAF of the front end: it holds names, classifications and
each implementation's STATED signature as data — never a CONVERSION from a
spelling to a type, which is `typecheck.type_from_name`'s alone — and never an
import of a game's Python (`PRIMITIVE_IMPLEMENTATIONS` names modules and
attributes as strings, so the compile gate learns WHICH names Python
implements without importing any of them).

Scope: the block covers the CALL-position namespace. The five other Primitive
namespaces — auction outcomes, climb leads, climb follows, early predicates,
game-local trick winners — take their own declaration slots when their
mechanic-driven signatures are spellable (issue #142, the co-location stage);
until then `WALLED_NAMESPACES` refuses their names in the block by name, so a
designer meets a diagnostic rather than a declaration that resolves and then
dispatches through a namespace the block never covered.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a parsed `Game` — `regime` and `declared_names` read the parse
              stamp alone and hold before resolve has validated anything.
Establishes:  ONE classification of a game's Primitive regime, and ONE
              statement of which Python each registered Primitive name is
              implemented by, and of the signature that Python takes. Also the ONE classification of a `reads` name
              (`classify_read`, which the read's own scope tail steers) and
              the collision predicates over the four namespaces such a name
              can be declared in — the game's own `state { }`, a phase's, an
              indexed `zones { }` declaration and an unindexed one — plus the
              fourth, ancestry-carrying one a flat membership set cannot state
              (`descendant_redeclarations`), with the phase attribution the
              diagnostics need (`declaring_phases`, `phase_names`). And the
              ONE path-aware walk of the phase tree (`phase_paths`), from which
              that attribution, the ancestry relation and the nesting question
              (`phase_chain`, which orders a set of phases outer to inner or
              answers None when they lie on no one ancestor path) all derive.
              And the
              ONE decomposition of an entry's type spelling
              (`decompose_type`), beside the element allow-list its collection
              form draws from (`COLLECTION_ELEMENT_NAMES`), which is pinned
              equal to the elements registered Python takes.
Now illegal:  a consumer deciding the regime by testing `game.primitives`
              itself; a Primitive's signature stated anywhere but its index
              row, or read from anywhere but `implementation_sig`; any
              front-end module importing a game's runtime module
              to learn what it implements; any consumer testing a name's
              membership against the state or zone walks itself rather than
              asking the predicates here; and any consumer walking the phase
              tree itself to answer a scope, ancestry or nesting question about
              a `reads` clause or a declared Primitive — the one path-aware
              walk is here, and a POSITION question (which phase's extent holds
              a given node) is resolve's, since it is about the nodes of a game
              rather than about the shape of its phase tree, while resolve's
              state-REFERENCE scope checks walk the tree themselves, outside
              this limit (issue #574); any consumer reading an entry
              spelling's shape itself rather than asking `decompose_type` —
              the BRACKET half of that is held by a scrape over `cardlang/`
              (`tests/test_primitives_block.py::test_a_collection_spelling_is_
              split_in_exactly_one_place`), the trailing `?` by review, since
              every remaining `?` slice in the package reads a payload,
              function-parameter, move-parameter or library-slot spelling —
              never a state one, whose optionality parses to a field rather
              than into the name — and a scrape wide enough to reach an
              entry's `?` would demand the same routing of all of them; and an
              element outside the allow-list reaching typecheck.
Verified by:  tests/test_primitives_block.py (the index reconciled against
              `PRIMITIVE_CALL_FUNCS` and against the live attributes; the
              declarable-type partition; the wall's totality over the six
              namespaces; the reads name's membership product over the four
              namespaces, with the phase-carrying walk pinned against the
              engine's own).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    CALL_FUNCS,
    PRIMITIVE_AUCTION_OUTCOMES,
    PRIMITIVE_CALL_FUNCS,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    PRIMITIVE_EARLY_PREDICATES,
    PRIMITIVE_TRICK_WINNERS,
)
from cardlang.builtins.signatures import Sig
from cardlang.types import (
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TOptional,
    TPlayer,
    TTeam,
)


class Regime(Enum):
    """Which namespace a game's `f(...)` calls resolve their Primitives in."""

    DECLARED = "declared"
    """The game declares a `primitives { }` block: its own entries, and no
    other game's Primitive."""

    LEGACY = "legacy"
    """The game declares no block: the hand-authored `PRIMITIVE_CALL_FUNCS`
    namespace, shared corpus-wide. It ADMITS every Primitive and then refuses
    each one — a declaration is the only route to a Primitive's Python, so
    resolve's declared-only arm speaks for every name in the half this regime
    adds — which is why the namespace is that set rather than the Builtins:
    the name IS a Primitive, and a diagnostic calling it unknown would be
    false. What this regime can actually reach is the Builtins."""


def regime(game: n.Game) -> Regime:
    """The game's Primitive regime — the presence partition, asked once.

    `Game.primitives` distinguishes three states and this reads two of them
    as one: an ABSENT block is `None` (legacy), an EMPTY block is a block with
    no entries (declared, and every Primitive call in the game is therefore
    refused). The empty block is a real declaration — "this game borrows no
    Python" — the way an empty declared-reads row is
    (`reads.PRIMITIVE_READS`, president.py's row)."""
    return Regime.LEGACY if game.primitives is None else Regime.DECLARED


def declared_names(game: n.Game) -> frozenset[str]:
    """The Primitive names this game declares. Empty for a legacy game and for
    a game whose block is empty — which `regime` tells apart."""
    if game.primitives is None:
        return frozenset()
    return frozenset(d.name for d in game.primitives.decls)


def call_namespace(game: n.Game) -> frozenset[str]:
    """Every name the game may write as a native `f(...)` call.

    The union both regimes agree on is the Builtins; what differs is the
    Primitive half. A declared game reaching another game's Primitive is the
    cross-game leakage this block exists to end (issue #364): its neighbour's
    trick winner is not in ITS namespace, so the call is an unknown name."""
    match regime(game):
        case Regime.DECLARED:
            return BUILTIN_CALL_FUNCS | declared_names(game)
        case Regime.LEGACY:
            return CALL_FUNCS


# --- the implementation index ------------------------------------------------


class InvocationContract(Enum):
    """How the dispatch layer calls one Primitive's Python.

    A closed domain over `PRIMITIVE_CALL_FUNCS`: every registered Primitive
    answers exactly one of these, and a `primitives { }` block declares them
    all. Every member is a dispatch SHAPE, so every consumer dispatches with
    a structural `match` closed by `typing.assert_never` — an added member is
    a type error at each of them, which is where "a contract arrives with the
    site that calls it" belongs (decisions.md "Closed-domain completeness":
    enforcement follows the domain's visibility to the type checker). What
    keeps a member from arriving with no Primitive answering it is the
    registry-side reconciliation `test_every_invocation_contract_has_a_member`.
    """

    BUNDLED = "bundled"
    """`impl(facts, gr, *args) -> value` — the narrowed Primitive contract
    (`narrowing.bind`), and the one the block declares."""

    PURE = "pure"
    """`impl(*args) -> value` — a Primitive that reads no engine state at all
    (500's bid ladder, Skat's Reizen step), so the dispatch hands it the
    coerced arguments and nothing else."""


@dataclass(frozen=True, slots=True)
class Implementation:
    """Where one Primitive's Python lives, as NAMES.

    `module` is an importable dotted path and `attribute` a module-level
    function in it; neither is imported here. The front end reads this table
    to answer "does anything implement the name this game declares?", which is
    the half of the both-ways check a game file cannot state — declarations
    and implementations are independently authored, and reconciling them IS
    the check (docs/design-notes/primitive-sidecars.md section 2)."""

    module: str
    attribute: str
    contract: InvocationContract
    sig: Sig
    """The signature the Python states, authored beside the location that
    finds it. Required, so an implementation registered without one does not
    construct, and read through `implementation_sig` — the one seam every
    consumer takes a Primitive's shape through. Authored rather than derived
    from the Python annotations: a `Player`, a `Team` and an `Integer` are all
    `int` there, and a collection has no annotation the mapping reads, so an
    annotation cannot state a DSL type. What the two independent statements
    buy is `tests/test_signatures.py`'s cross-check of one against the
    other."""


PRIMITIVE_IMPLEMENTATIONS: dict[str, Implementation] = {
    "belote_best_is": Implementation(
        "cardlang.runtime.belote", "belote_best_is", InvocationContract.BUNDLED,
        Sig((TPlayer(), TInteger(), TEnum("Rank"), TBoolean()), TBoolean()),
    ),
    "belote_decl_class": Implementation(
        "cardlang.runtime.belote", "belote_decl_class", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "belote_decl_height": Implementation(
        "cardlang.runtime.belote", "belote_decl_height", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "belote_decl_points": Implementation(
        "cardlang.runtime.belote", "belote_decl_points", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "belote_decl_size": Implementation(
        "cardlang.runtime.belote", "belote_decl_size", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "belote_decl_slot": Implementation(
        "cardlang.runtime.belote", "belote_decl_slot", InvocationContract.BUNDLED,
        Sig((TPlayer(), TInteger(), TCard()), TBoolean()),
    ),
    "belote_decl_trump": Implementation(
        "cardlang.runtime.belote", "belote_decl_trump", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "belote_royal_player": Implementation(
        "cardlang.runtime.belote", "belote_royal_player", InvocationContract.BUNDLED,
        Sig((), TOptional(TPlayer())),
    ),
    "bring_in_seat": Implementation(
        "cardlang.runtime.stud", "bring_in_seat", InvocationContract.BUNDLED,
        Sig((), TPlayer()),
    ),
    "canasta_can_start": Implementation(
        "cardlang.runtime.canasta", "canasta_can_start", InvocationContract.BUNDLED,
        Sig((TPlayer(), TEnum("Rank")), TBoolean()),
    ),
    "canasta_can_take_pile": Implementation(
        "cardlang.runtime.canasta", "canasta_can_take_pile", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "canasta_canasta_bonus": Implementation(
        "cardlang.runtime.canasta", "canasta_canasta_bonus", InvocationContract.BUNDLED,
        Sig((TTeam(),), TInteger()),
    ),
    "canasta_close_ok": Implementation(
        "cardlang.runtime.canasta", "canasta_close_ok", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "canasta_must_take_pile": Implementation(
        "cardlang.runtime.canasta", "canasta_must_take_pile", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "canasta_stage_ok": Implementation(
        "cardlang.runtime.canasta", "canasta_stage_ok", InvocationContract.BUNDLED,
        Sig((TPlayer(), TCard()), TBoolean()),
    ),
    "cribbage_crib_value": Implementation(
        "cardlang.runtime.cribbage", "cribbage_crib_value", InvocationContract.BUNDLED,
        Sig((), TInteger()),
    ),
    "cribbage_show_value": Implementation(
        "cardlang.runtime.cribbage", "cribbage_show_value", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "first_to_act_seat": Implementation(
        "cardlang.runtime.stud", "first_to_act_seat", InvocationContract.BUNDLED,
        Sig((), TPlayer()),
    ),
    "five_hundred_bid_level": Implementation(
        "cardlang.runtime.five_hundred", "five_hundred_bid_level", InvocationContract.PURE,
        Sig((TInteger(),), TInteger()),
    ),
    "five_hundred_bid_value": Implementation(
        "cardlang.runtime.five_hundred", "five_hundred_bid_value", InvocationContract.PURE,
        Sig((TInteger(),), TInteger()),
    ),
    # 0 is the return that means "no bid in this strain beats the standing one".
    "five_hundred_next_bid": Implementation(
        "cardlang.runtime.five_hundred", "five_hundred_next_bid", InvocationContract.PURE,
        Sig((TInteger(), TOptional(TEnum("Suit"))), TInteger()),
    ),
    "gin_arrange_ok": Implementation(
        "cardlang.runtime.gin", "gin_arrange_ok", InvocationContract.BUNDLED,
        Sig((TPlayer(), TCollection(TCard())), TBoolean()),
    ),
    "gin_can_declare": Implementation(
        "cardlang.runtime.gin", "gin_can_declare", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "gin_can_declare_free": Implementation(
        "cardlang.runtime.gin", "gin_can_declare_free", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "gin_can_knock": Implementation(
        "cardlang.runtime.gin", "gin_can_knock", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TBoolean()),
    ),
    "gin_deadwood": Implementation(
        "cardlang.runtime.gin", "gin_deadwood", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "gin_knock_ok": Implementation(
        "cardlang.runtime.gin", "gin_knock_ok", InvocationContract.BUNDLED,
        Sig((TPlayer(), TCard()), TBoolean()),
    ),
    "gin_lay_ok_a": Implementation(
        "cardlang.runtime.gin", "gin_lay_ok_a", InvocationContract.BUNDLED,
        Sig((TCard(), TPlayer()), TBoolean()),
    ),
    "gin_lay_ok_b": Implementation(
        "cardlang.runtime.gin", "gin_lay_ok_b", InvocationContract.BUNDLED,
        Sig((TCard(), TPlayer()), TBoolean()),
    ),
    "gin_lay_ok_c": Implementation(
        "cardlang.runtime.gin", "gin_lay_ok_c", InvocationContract.BUNDLED,
        Sig((TCard(), TPlayer()), TBoolean()),
    ),
    "gin_valid_meld": Implementation(
        "cardlang.runtime.gin", "gin_valid_meld", InvocationContract.BUNDLED,
        Sig((TCollection(TCard()),), TBoolean()),
    ),
    # A second binding of `holdem_pot_share`'s query, not a second query;
    # issue #232 retires the name.
    "holdem_heads_up_pot_share": Implementation(
        "cardlang.runtime.holdem_heads_up", "holdem_heads_up_pot_share", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "holdem_pot_share": Implementation(
        "cardlang.runtime.holdem", "holdem_pot_share", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "peg_origin_of": Implementation(
        "cardlang.runtime.cribbage", "peg_origin_of", InvocationContract.BUNDLED,
        Sig((TCard(),), TPlayer()),
    ),
    "peg_pair_points": Implementation(
        "cardlang.runtime.cribbage", "peg_pair_points", InvocationContract.BUNDLED,
        Sig((), TInteger()),
    ),
    "peg_run_points": Implementation(
        "cardlang.runtime.cribbage", "peg_run_points", InvocationContract.BUNDLED,
        Sig((), TInteger()),
    ),
    "pinochle_meld_value": Implementation(
        "cardlang.runtime.pinochle", "pinochle_meld_value", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "pot_share": Implementation(
        "cardlang.runtime.stud", "pot_share", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "salvo_combos": Implementation(
        "cardlang.runtime.salvo", "salvo_combos", InvocationContract.BUNDLED,
        Sig((TPlayer(), TInteger()), TInteger()),
    ),
    "skat_matadors": Implementation(
        "cardlang.runtime.skat", "skat_matadors", InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    ),
    "skat_next_bid": Implementation(
        "cardlang.runtime.skat", "skat_next_bid", InvocationContract.PURE,
        Sig((TInteger(),), TInteger()),
    ),
    "tarot_excuse_player": Implementation(
        "cardlang.runtime.tarot", "tarot_excuse_player", InvocationContract.BUNDLED,
        Sig((), TOptional(TPlayer())),
    ),
    "tarot_per_opp": Implementation(
        "cardlang.runtime.tarot", "tarot_per_opp", InvocationContract.BUNDLED,
        Sig((TInteger(),), TInteger()),
    ),
    "tichu_dragon_won": Implementation(
        "cardlang.runtime.tichu", "tichu_dragon_won", InvocationContract.BUNDLED,
        Sig((), TBoolean()),
    ),
}


# --- the walls ---------------------------------------------------------------

# The Primitive namespaces the block does NOT cover, label -> names. A name
# here is a Primitive, so refusing it as "unknown" would be a lie; the label is
# what the diagnostic says instead. Keyed by label rather than derived by
# subtraction from some union, because each namespace has a DIFFERENT reason it
# is out of scope — a mechanic-driven signature a typed parameter list cannot
# spell — and the label is that reason's short form.
WALLED_NAMESPACES: dict[str, frozenset[str]] = {
    "an auction outcome (a `round auction ... outcome` slot)": PRIMITIVE_AUCTION_OUTCOMES,
    "a climb lead query (a `round climb ... combinations` slot)": PRIMITIVE_CLIMB_LEADS,
    "a climb follows query (a `round climb ... follows` slot)": PRIMITIVE_CLIMB_FOLLOWS,
    "an early-termination predicate (a `round ... early` slot)": PRIMITIVE_EARLY_PREDICATES,
    "a game-local trick winner (a `round ... winner` slot)": PRIMITIVE_TRICK_WINNERS,
}


def walled_namespace_of(name: str) -> str | None:
    """The label of the walled namespace `name` belongs to, or None.

    Ordered by the table above, so a name reachable from two namespaces names
    one of them deterministically (`_reserved_domain_source`'s rule)."""
    for label, names in WALLED_NAMESPACES.items():
        if name in names:
            return label
    return None


# --- declarable type names ---------------------------------------------------

# The built-in type names an entry's parameters and return may be spelled with:
# the scalars and the value enums. Stated here as the block's own allow-list
# and pinned EQUAL to `typecheck.KNOWN_TYPE_NAMES` — two independent statements
# of the same closed set, crossed by the grid, rather than one importing the
# other and checking itself.
#
# What the omissions BUY is the freeze contract: `reads.coerce_args` is
# signature-driven, and a `TAny` parameter passes its argument RAW into the
# implementation (the adapter dispatches on the shape itself). A surface that
# cannot spell `TAny` cannot hand a declared Primitive an unfrozen engine
# value, which is why the exclusion is a property of the block rather than a
# gap in it.
DECLARABLE_BUILTIN_TYPE_NAMES: frozenset[str] = frozenset(
    {"Integer", "Boolean", "String", "Player", "Team", "Card", "Suit", "Rank", "SeatDirection"}
)


# The constructor word an entry's collection spelling is written with, and the
# element types it may take. `Collection<Card>` is the whole surface: one
# constructor, one element, stated as the block's own allow-list beside the
# scalar names above (decisions.md "Allow-list, never deny-list").
#
# The list is held EQUAL to what registered Python actually takes
# (`implementation_sig` over `PRIMITIVE_IMPLEMENTATIONS`), so admitting a
# second element is an event with a witness rather than a widening: a designer
# spelling one is refused here, and an engine author registering one lands red
# in the pin. A collection is never OPTIONAL and never KEYED or zone-flagged:
# the element slot is a bare name and composes with neither the `?` arm nor the
# zone type-argument list, and the runtime reason is `coerce_args` — its
# dispatch is on the declared `TCollection` itself, so an optional wrapper
# would pass the argument raw and die at the boundary. `is empty` is the
# absence a designer writes instead.
COLLECTION_TYPE_CONSTRUCTOR = "Collection"

COLLECTION_ELEMENT_NAMES: frozenset[str] = frozenset({"Card"})


@dataclass(frozen=True, slots=True)
class DeclaredType:
    """One entry type slot's spelling, read into its parts.

    ``base`` is the head name, ``optional`` its trailing `?`, and ``element``
    the collection's argument or None. The spelling rides the AST as a string,
    the way `Suit?` carries its own combinator, and this is the ONE place its
    shape is read: every consumer asks here rather than slicing the string, so
    a declaration and the Type it denotes cannot become two readings of one
    text. `Collection<Card>?` has no derivation, so the two combinators never
    both appear."""

    base: str
    optional: bool
    element: str | None

    @property
    def is_collection(self) -> bool:
        return self.element is not None


def decompose_type(spelling: str) -> DeclaredType:
    """An entry's type spelling, decomposed. The grammar guarantees the three
    shapes — `Name`, `Name?`, `Name<Element>` — and nothing else reaches an
    entry's slots, so this reads them rather than validating them."""
    if spelling.endswith(">"):
        head, _, rest = spelling.partition("<")
        return DeclaredType(base=head, optional=False, element=rest[:-1])
    optional = spelling.endswith("?")
    return DeclaredType(
        base=spelling[:-1] if optional else spelling, optional=optional, element=None
    )


def declarable_type_names(game: n.Game) -> frozenset[str]:
    """Every type name an entry of `game`'s block may spell.

    The built-ins plus the game's own position domains — a positional zone's
    index binder is a position-domain member (`tableau_down[column]`), so a
    Primitive taking one needs the domain's name in this set. Struct type
    names and the board-minted direction domain are deliberately absent: a
    struct crosses the value boundary as a live `StructValue` and a direction
    is a board-frame token, neither of which a Primitive's declared signature
    has a witness for."""
    return DECLARABLE_BUILTIN_TYPE_NAMES | frozenset(p.name for p in game.positions)


# The `Type` constructors NO declared spelling reaches, each with the reason.
# The complement of what `declarable_type_names` can produce, listed rather
# than derived by subtraction so a constructor added to `types.Type` lands
# unclassified and the partition test names it.
UNDECLARABLE_TYPE_CONSTRUCTORS: dict[str, str] = {
    "TAny": "the permissive top — a TAny parameter passes RAW through "
    "`coerce_args`, so spelling it would hand a Primitive an unfrozen engine "
    "value; designed constraint, deliberately unreachable",
    "TNull": "the type of the `none` literal alone — a value, never a "
    "declaration; designed constraint",
    "TStruct": "a game's `type` declaration — a declared Primitive receives "
    "values, and a `StructValue` crossing the boundary has no witness "
    "(issue #547)",
    "TOutcome": "a `define`'s or outcome phase's cases — consumed by "
    "`produce` / `produces:`, never returned by `infer`; designed constraint",
    "TLine": "a board line, produced by `lines(k)` alone (issue #547)",
    "TDir": "the board-minted direction domain — a board-frame token "
    "(issue #547)",
}


class ReadKind(Enum):
    """What one `reads` name denotes — the exhaustive classification, since
    each kind materializes differently.

    SCOPE is deliberately not a kind here, and no member for a
    [[phase-scoped-read]] belongs in this enum: a phase-declared state variable
    materializes identically to a game-level one — the same frame walk, the
    same bundle half, the same narrowing — so a member would carry no
    information the read's own `phase` field lacks while costing this closed
    domain's whole consumer sweep. WHICH declaration decides the kind is
    `classify_read`'s `phase` parameter. A designed constraint, not a gap."""

    STATE_VAR = "state variable"
    INDEXED_STATE_VAR = "indexed state variable"
    ZONE_FAMILY = "zone family"
    SINGLE_ZONE = "single zone"


# The kinds a `reads` name may carry a BINDER on: the indexed ones, because the
# binder keys an instance. Stated as the allow-list so a kind added above is
# refused a binder until someone admits it with a witness.
BINDABLE_READ_KINDS: frozenset[ReadKind] = frozenset(
    {ReadKind.INDEXED_STATE_VAR, ReadKind.ZONE_FAMILY}
)


def _state_kind(decl: n.StateDecl) -> ReadKind:
    return ReadKind.INDEXED_STATE_VAR if decl.index is not None else ReadKind.STATE_VAR


def classify_read(game: n.Game, name: str, phase: str | None = None) -> ReadKind | None:
    """Which of the game's own keyed declarations `name` denotes, or None.

    The ONE classifier. resolve refuses the None, and the driver dispatches on
    the answer to build the primitive's row — neither re-derives the other's,
    which is what keeps the row a primitive receives and the entry a designer
    wrote from being two readings of the same text.

    `phase` is the read's own scope tail. WITH one, the named phase's own
    `state { }` is the only block consulted, and it alone decides the kind and
    the indexedness — which is the fact the tail is needed for, since one game
    may declare `committed[player]` where another declares a plain
    `committed`. Zones and the game's own state are not consulted for a scoped
    read: a zone is game-level (the language has no phase-local `zones { }`),
    and a game-level declaration of the same name is a collision resolve
    refuses before this runs.

    WITHOUT one, the game's own `state { }` and its zones, in that order. A
    phase's block is not among them: an untailed row is materialized on EVERY
    call, so a phase-local variable would be readable only while that phase's
    frame stands — `phase_local_state_names` is what turns that into a
    diagnostic naming the phase, and now the tail to write."""
    if phase is not None:
        for path, decl in _phase_state_decls(game):
            if path[-1] == phase and decl.name == name:
                return _state_kind(decl)
        return None
    if game.state is not None:
        for sd in game.state.decls:
            if sd.name == name:
                return _state_kind(sd)
    for z in game.zones:
        if z.name == name:
            return ReadKind.ZONE_FAMILY if z.index is not None else ReadKind.SINGLE_ZONE
    return None


def _game_level_state_names(game: n.Game) -> frozenset[str]:
    return frozenset(d.name for d in game.state.decls) if game.state else frozenset()


def _phase_tree(game: n.Game) -> tuple[tuple[tuple[str, ...], n.Phase], ...]:
    """(the PATH from a top-level phase down to it, the phase) for EVERY phase
    of the game — the one whose `state { }` declares a name and the one that
    declares nothing alike.

    The ONE path-aware walk. `phase_paths`, `phase_names`, `phase_chain` and
    `_phase_state_decls` derive from it rather than walking again, so the phase
    set, the attribution, the ancestry and the nesting question can never
    disagree; that they agree with the engine-wide walk (`n.state_blocks`) is
    tests/test_primitives_block.py's.

    Every phase and not only the declarers, because ancestry is asked ABOUT
    phases rather than about declarations: a phase that declares nothing can
    still enclose the region an entry is callable in, and a diagnostic that
    names the phase a call sits in has to find that phase's path to say whether
    it encloses the region or merely runs elsewhere. Phase names are
    game-unique (`_check_duplicate_names`), so a path is one chain and not a
    set of them."""
    found: list[tuple[tuple[str, ...], n.Phase]] = []

    def rec(phase: n.Phase, path: tuple[str, ...]) -> None:
        here = path + (phase.name,)
        found.append((here, phase))
        for item in phase.items:
            if isinstance(item, n.Phase):
                rec(item, here)

    for phase in game.phases:
        rec(phase, ())
    return tuple(found)


def phase_paths(game: n.Game) -> dict[str, tuple[str, ...]]:
    """Every phase of the game -> its path from a top-level phase down to it.

    The ancestry table: one path is a prefix of another exactly when the first
    phase's extent contains the second's, which is the whole of what nesting,
    enclosure and strict descent are asked here."""
    return {path[-1]: path for path, _ in _phase_tree(game)}


def phase_chain(game: n.Game, phases: frozenset[str]) -> tuple[str, ...] | None:
    """`phases` ordered OUTER to INNER when they lie on ONE ancestor path, or
    None when they do not.

    The nesting question, asked once. Sorted by depth, their paths are
    prefix-ordered exactly when each phase's extent contains the next's — and
    then the innermost phase's subtree IS the intersection of all of them,
    which is the region an entry naming them is callable in. Two phases neither
    of which is inside the other intersect in nothing, and no position in the
    game runs both, so they answer None.

    The empty set answers `()` and a singleton `(p,)`: one phase is the
    degenerate chain rather than a special case, which is what keeps a
    single-phase entry on the same path as a nested one. A name that is not a
    phase of the game answers None too — the tail arm speaks for that name
    first, so no caller reaches here with one."""
    paths = phase_paths(game)
    if any(name not in paths for name in phases):
        return None
    ordered = tuple(sorted(phases, key=lambda name: len(paths[name])))
    nests = all(
        paths[ordered[i]] == paths[ordered[i + 1]][: len(paths[ordered[i]])]
        for i in range(len(ordered) - 1)
    )
    return ordered if nests else None


def _phase_state_decls(
    game: n.Game,
) -> tuple[tuple[tuple[str, ...], n.StateDecl], ...]:
    """(the phase PATH from a top-level phase down to the declarer, the
    declaration) for every name a PHASE's own `state { }` declares.

    The path, not just the declaring phase's name, because the fourth collision
    predicate asks an ANCESTRY question — is this declarer a strict descendant
    of the phase a read names — and a name-keyed attribution cannot answer it.

    The declaring subset of `_phase_tree`, which is the ONE walk."""
    return tuple(
        (path, sd)
        for path, phase in _phase_tree(game)
        for item in phase.items
        if isinstance(item, n.StateBlock)
        for sd in item.decls
    )


def _phase_state_paths(game: n.Game) -> tuple[tuple[tuple[str, ...], str], ...]:
    """`_phase_state_decls` as (path, name) pairs — the shape a consumer asking
    only about names and ancestry wants."""
    return tuple((path, decl.name) for path, decl in _phase_state_decls(game))


def _phase_state_declarations(game: n.Game) -> tuple[tuple[str, str], ...]:
    """(declaring phase's name, state name) for every name a PHASE's own
    `state { }` declares — nested phases included.

    The walk carries the phase because a diagnostic about a phase-declared name
    is unusable without it: the addressee is a designer who has to FIND the
    declaration."""
    return tuple((path[-1], name) for path, name in _phase_state_paths(game))


def phase_names(game: n.Game) -> frozenset[str]:
    """Every phase of the game, nested ones included — what a scope tail may
    name. Game-unique by `_check_duplicate_names`, so a tail names one phase."""
    return frozenset(phase_paths(game))


def descendant_redeclarations(game: n.Game, phase: str, name: str) -> frozenset[str]:
    """The STRICT descendants of `phase` that also declare `name` as their own
    state — the fourth collision, and the one only a path-aware walk can see.

    The runtime resolves a name against the innermost standing frame, so a call
    from inside such a descendant would receive the descendant's value while
    the declaration names the ancestor's: a wrong answer with no failure
    anywhere, which is the register the three sibling predicates exist to
    refuse. Refusing the pair at compile is what lets the materializer keep its
    innermost-first walk unchanged and untagged.

    A designed constraint. The obvious alternative — tag frames with their
    phase and target the declared one at run time — is rejected and should not
    be revisited without new evidence: frames are anonymous by design, tagging
    taxes every push site, and it buys correctness only for the case this
    refusal removes at no measured corpus cost, while letting two textually
    identical calls read different stores."""
    return frozenset(
        path[-1]
        for path, declared in _phase_state_paths(game)
        if declared == name and phase in path[:-1]
    )


def _phase_state_names(game: n.Game) -> frozenset[str]:
    """Every name a PHASE's own `state { }` declares."""
    return frozenset(name for _, name in _phase_state_declarations(game))


def declaring_phases(game: n.Game, name: str) -> frozenset[str]:
    """The phases whose own `state { }` declares `name` — what a diagnostic
    about a phase-declared name says instead of leaving the designer to search
    for it."""
    return frozenset(
        phase for phase, declared in _phase_state_declarations(game) if declared == name
    )


def phase_local_state_names(game: n.Game) -> frozenset[str]:
    """State a PHASE declares and the game does not — readable by a declaration
    that NAMES the phase (`X in P`) and by no other, because the row is
    materialized on every call and the frame stands only while that phase
    runs. An untailed read of one of these is what the phase-local arm
    refuses, teaching the tail."""
    return _phase_state_names(game) - _game_level_state_names(game)


def ambiguous_read_names(game: n.Game) -> frozenset[str]:
    """Names a game declares as BOTH a game-level state variable and a zone.

    `classify_read` consults the two namespaces in order, so it would pick one
    silently — and the pick decides which half of the bundle the name is
    materialized into, `GameReads.state` or `.families`. An implementation
    reading the other half meets a bundle that simply does not carry the name.
    The two namespaces are flat and independent (a game may legally use one
    spelling in each), so the declaration cannot say which it means and the
    ambiguity is refused."""
    zones = frozenset(z.name for z in game.zones)
    return _game_level_state_names(game) & zones


def shadowed_state_names(game: n.Game) -> frozenset[str]:
    """State declared at BOTH levels — also unreadable by a declaration, and
    for a worse reason.

    An untailed `classify_read` matches the game-level declaration while the
    runtime resolves the innermost frame, so a primitive declaring the name
    receives the PHASE's value whenever that phase runs: a wrong answer with no
    failure anywhere. The declaration cannot say which of the two it means, so
    the ambiguity is refused rather than settled by whichever end happens to
    win.

    A scope tail does not lift it. `X in P` says which declaration is meant,
    but the game-level variable of that spelling is then unreadable by any
    declaration at all, with nothing on the page saying so — so the pair stays
    refused and the tailed refusal states that reason instead of this one.

    With `phase_local_state_names` and the game-level set this partitions every
    state name the engine can see, which is what lets each arm's diagnostic
    name the right fix."""
    return _phase_state_names(game) & _game_level_state_names(game)


def phase_state_zone_names(game: n.Game) -> frozenset[str]:
    """Names a PHASE declares as state while the game declares them as a zone —
    the third collision, and the one nothing about the classification reveals.

    An untailed `classify_read` consults the game's zones and its GAME-level
    state and never a phase's, so a colliding name classifies as the zone with
    no sign that the declaration also names something else. The zone is then
    what the primitive receives whenever it is called, including from inside
    the phase whose variable the designer meant. A scope tail does not lift it
    either: a zone is game-level in this language, so the two spellings would
    still both stand and one of them would be silently unreachable.

    Disjoint from both siblings by construction: it intersects with
    `phase_local_state_names`, which subtracts the game-level set, so a name
    here is in neither `ambiguous_read_names` nor `shadowed_state_names` — the
    three arms partition the CROSS-namespace collisions a `reads` name can
    carry (the within-zones pair is `_check_duplicate_names`' own), and each
    names its own fix."""
    zones = frozenset(z.name for z in game.zones)
    return phase_local_state_names(game) & zones


def engine_fact_names() -> frozenset[str]:
    """The `EngineFacts` field names — the OTHER half of what a Primitive sees.

    Not spellable in a `reads` clause: the block declares the name-keyed half
    only, and the engine-structural half arrives whole (issue #474). Derived from the
    dataclass rather than listed, so a field added to that closed set is
    refused in the clause without an edit here — and imported lazily, because
    the front end must not pull the runtime in to answer a name question.
    """
    from dataclasses import fields

    from cardlang.runtime.narrowing import EngineFacts

    return frozenset(f.name for f in fields(EngineFacts))


# --- reconciliation ----------------------------------------------------------


def implementation_sig(name: str) -> Sig | None:
    """The signature the PYTHON side states for `name`, or None if unregistered.

    The index row's own column, which is the only place a Primitive's shape is
    stated. Reading it through this function rather than reaching into the
    table at each consumer is what keeps that a fact about one site.

    This is the reconciliation side of the both-ways check: a declaration and
    an implementation are independently authored, so agreeing about EXISTENCE
    is only one leg. Agreeing about shape is the other."""
    impl = PRIMITIVE_IMPLEMENTATIONS.get(name)
    return None if impl is None else impl.sig


def unimplemented(names: frozenset[str]) -> frozenset[str]:
    """Which of `names` no registered Python implements — the declared-but-
    unimplemented half of the both-ways check, asked at compile time so a
    designer's typo is a diagnostic rather than a playout crash."""
    return names - frozenset(PRIMITIVE_IMPLEMENTATIONS)


# registry: a name registered as a Primitive with no implementation row, or a
# row for a name no registry claims, is an authoring defect in the two tables
# right here and in `builtins/functions.py` — unreachable from any game
# description; loud at first import of this module. The reconciliation the
# GAMES need (a corpus game's calls against its regime's namespace) is
# tests/test_primitives_block.py's, which this cannot stand in for.
assert frozenset(PRIMITIVE_IMPLEMENTATIONS) == PRIMITIVE_CALL_FUNCS, (
    "PRIMITIVE_IMPLEMENTATIONS and PRIMITIVE_CALL_FUNCS disagree: "
    f"{sorted(frozenset(PRIMITIVE_IMPLEMENTATIONS) ^ PRIMITIVE_CALL_FUNCS)}"
)
