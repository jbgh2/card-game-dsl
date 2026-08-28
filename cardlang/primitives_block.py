"""The [[primitives-block]]'s registries: regime, implementation index, walls.

A game declares the [[primitive]]s it borrows from outside the DSL in a
`primitives { }` block beside `uses`
(docs/design-notes/primitive-sidecars.md §2). The block's PRESENCE partitions
the game's native-call namespace in both directions, the `trick_order { }`
mechanism one construct over: a game with a block names its own declared
primitives and no other game's, and a game without one keeps the hand-authored
`PRIMITIVE_CALL_FUNCS` namespace. `regime` below is the ONE site that asks
which, so no consumer re-derives it from `game.primitives is None`.

This module is a LEAF of the front end: it holds names and classifications
only, never types (`typecheck.type_from_name` is the one conversion site) and
never an import of a game's Python (`PRIMITIVE_IMPLEMENTATIONS` is a table of
strings, so the compile gate learns WHICH names Python implements without
importing any of them).

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
              implemented by.
Now illegal:  a consumer deciding the regime by testing `game.primitives`
              itself, and any front-end module importing a game's runtime
              module to learn what it implements.
Verified by:  tests/test_primitives_block.py (the index reconciled against
              `PRIMITIVE_CALL_FUNCS` and against the live attributes; the
              declarable-type partition; the wall's totality over the six
              namespaces).
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


class Regime(Enum):
    """Which namespace a game's `f(...)` calls resolve their Primitives in."""

    DECLARED = "declared"
    """The game declares a `primitives { }` block: its own entries, and no
    other game's Primitive."""

    LEGACY = "legacy"
    """The game declares no block: the hand-authored `PRIMITIVE_CALL_FUNCS`
    namespace, shared corpus-wide."""


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
    Primitive half. A declared game reaching a legacy Primitive is the
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
    answers exactly one of these, and the block admits `DECLARABLE_CONTRACTS`
    alone. The other two are refused BY NAME at resolve rather than left to
    fail as a `TypeError` mid-playout, because the mismatch is between a
    declaration and a Python signature — a compile-time fact.
    """

    BUNDLED = "bundled"
    """`impl(facts, gr, *args) -> value` — the narrowed Primitive contract
    (`narrowing.bind`), and the one the block declares."""

    PURE = "pure"
    """`impl(*args) -> value` — a Primitive that reads no engine state at all
    (500's bid ladder, Skat's Reizen step), so the dispatch hands it the
    coerced arguments and nothing else."""

    EMITTING = "emitting"
    """`impl(facts, gr, *args) -> (value, events)` — a Primitive that computes
    a value AND returns the engine's own trace events for the dispatch layer
    to emit (`narrowing.TraceEvent`). Not declarable: the one member is a
    trace emitter by call shape whose eviction is its own step (issue #142)."""

    SITE_READ = "site_read"
    """The dispatch site materializes the reads itself rather than binding a
    row. Not declarable: the reads such a Primitive makes are written at the
    call site, so a `reads` clause would declare something the implementation
    does not consult (issue #473)."""


@dataclass(frozen=True, slots=True)
class Implementation:
    """Where one Primitive's Python lives, as NAMES.

    `module` is an importable dotted path and `attribute` a module-level
    function in it; neither is imported here. The front end reads this table
    to answer "does anything implement the name this game declares?", which is
    the half of the both-ways check a game file cannot state — declarations
    and implementations are independently authored, and reconciling them IS
    the check (docs/design-notes/primitive-sidecars.md §2)."""

    module: str
    attribute: str
    contract: InvocationContract


PRIMITIVE_IMPLEMENTATIONS: dict[str, Implementation] = {
    "belote_best_is": Implementation("cardlang.runtime.belote", "belote_best_is", InvocationContract.BUNDLED),
    "belote_decl_class": Implementation("cardlang.runtime.belote", "belote_decl_class", InvocationContract.BUNDLED),
    "belote_decl_height": Implementation("cardlang.runtime.belote", "belote_decl_height", InvocationContract.BUNDLED),
    "belote_decl_points": Implementation("cardlang.runtime.belote", "belote_decl_points", InvocationContract.BUNDLED),
    "belote_decl_size": Implementation("cardlang.runtime.belote", "belote_decl_size", InvocationContract.BUNDLED),
    "belote_decl_slot": Implementation("cardlang.runtime.belote", "belote_decl_slot", InvocationContract.BUNDLED),
    "belote_decl_trump": Implementation("cardlang.runtime.belote", "belote_decl_trump", InvocationContract.BUNDLED),
    "belote_royal_player": Implementation("cardlang.runtime.belote", "belote_royal_player", InvocationContract.BUNDLED),
    "bring_in_seat": Implementation("cardlang.runtime.stud", "bring_in_seat", InvocationContract.BUNDLED),
    "canasta_can_start": Implementation("cardlang.runtime.canasta", "canasta_can_start", InvocationContract.BUNDLED),
    "canasta_can_take_pile": Implementation("cardlang.runtime.canasta", "canasta_can_take_pile", InvocationContract.BUNDLED),
    "canasta_canasta_bonus": Implementation("cardlang.runtime.canasta", "canasta_canasta_bonus", InvocationContract.BUNDLED),
    "canasta_close_ok": Implementation("cardlang.runtime.canasta", "canasta_close_ok", InvocationContract.BUNDLED),
    "canasta_must_take_pile": Implementation("cardlang.runtime.canasta", "canasta_must_take_pile", InvocationContract.BUNDLED),
    "canasta_stage_ok": Implementation("cardlang.runtime.canasta", "canasta_stage_ok", InvocationContract.BUNDLED),
    "coup_game_summary": Implementation("cardlang.runtime.coup", "coup_game_summary", InvocationContract.EMITTING),
    "cribbage_crib_value": Implementation("cardlang.runtime.cribbage", "cribbage_crib_value", InvocationContract.BUNDLED),
    "cribbage_show_value": Implementation("cardlang.runtime.cribbage", "cribbage_show_value", InvocationContract.BUNDLED),
    "first_to_act_seat": Implementation("cardlang.runtime.stud", "first_to_act_seat", InvocationContract.BUNDLED),
    "five_hundred_bid_level": Implementation("cardlang.runtime.five_hundred", "five_hundred_bid_level", InvocationContract.PURE),
    "five_hundred_bid_value": Implementation("cardlang.runtime.five_hundred", "five_hundred_bid_value", InvocationContract.PURE),
    "five_hundred_next_bid": Implementation("cardlang.runtime.five_hundred", "five_hundred_next_bid", InvocationContract.PURE),
    "gin_arrange_ok": Implementation("cardlang.runtime.gin", "gin_arrange_ok", InvocationContract.BUNDLED),
    "gin_can_declare": Implementation("cardlang.runtime.gin", "gin_can_declare", InvocationContract.BUNDLED),
    "gin_can_declare_free": Implementation("cardlang.runtime.gin", "gin_can_declare_free", InvocationContract.BUNDLED),
    "gin_can_knock": Implementation("cardlang.runtime.gin", "gin_can_knock", InvocationContract.BUNDLED),
    "gin_deadwood": Implementation("cardlang.runtime.gin", "gin_deadwood", InvocationContract.BUNDLED),
    "gin_knock_ok": Implementation("cardlang.runtime.gin", "gin_knock_ok", InvocationContract.BUNDLED),
    "gin_lay_ok_a": Implementation("cardlang.runtime.gin", "gin_lay_ok_a", InvocationContract.BUNDLED),
    "gin_lay_ok_b": Implementation("cardlang.runtime.gin", "gin_lay_ok_b", InvocationContract.BUNDLED),
    "gin_lay_ok_c": Implementation("cardlang.runtime.gin", "gin_lay_ok_c", InvocationContract.BUNDLED),
    "gin_valid_meld": Implementation("cardlang.runtime.gin", "gin_valid_meld", InvocationContract.BUNDLED),
    "holdem_heads_up_pot_share": Implementation("cardlang.runtime.holdem_heads_up", "holdem_heads_up_pot_share", InvocationContract.BUNDLED),
    "holdem_pot_share": Implementation("cardlang.runtime.holdem", "holdem_pot_share", InvocationContract.BUNDLED),
    "peg_origin_of": Implementation("cardlang.runtime.cribbage", "peg_origin_of", InvocationContract.BUNDLED),
    "peg_pair_points": Implementation("cardlang.runtime.cribbage", "peg_pair_points", InvocationContract.SITE_READ),
    "peg_run_points": Implementation("cardlang.runtime.cribbage", "peg_run_points", InvocationContract.SITE_READ),
    "pinochle_meld_value": Implementation("cardlang.runtime.pinochle", "pinochle_meld_value", InvocationContract.BUNDLED),
    "pot_share": Implementation("cardlang.runtime.stud", "pot_share", InvocationContract.BUNDLED),
    "skat_matadors": Implementation("cardlang.runtime.skat", "skat_matadors", InvocationContract.BUNDLED),
    "skat_next_bid": Implementation("cardlang.runtime.skat", "skat_next_bid", InvocationContract.PURE),
    "tarot_excuse_player": Implementation("cardlang.runtime.tarot", "tarot_excuse_player", InvocationContract.BUNDLED),
    "tarot_per_opp": Implementation("cardlang.runtime.tarot", "tarot_per_opp", InvocationContract.BUNDLED),
    "tichu_dragon_won": Implementation("cardlang.runtime.tichu", "tichu_dragon_won", InvocationContract.BUNDLED),
}

# The contracts the block declares. Stated as the ALLOW-LIST, so a contract
# added to the enum later is refused in the block until someone admits it with
# a witness (decisions.md "Allow-list, never deny-list").
DECLARABLE_CONTRACTS: frozenset[InvocationContract] = frozenset(
    {InvocationContract.BUNDLED, InvocationContract.PURE}
)


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
    "(issue #473)",
    "TOutcome": "a `define`'s or outcome phase's cases — consumed by "
    "`produce` / `produces:`, never returned by `infer`; designed constraint",
    "TLine": "a board line, produced by `lines(k)` alone (issue #472)",
    "TDir": "the board-minted direction domain — a board-frame token "
    "(issue #472)",
    "TCollection": "a card collection — the shape `gin_valid_meld(collection "
    "of Card)` and its siblings need, and the surface has no spelling for it "
    "(issue #472)",
}


class ReadKind(Enum):
    """What one `reads` name denotes — the exhaustive classification, since
    each kind materializes differently."""

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


def classify_read(game: n.Game, name: str) -> ReadKind | None:
    """Which of the game's own keyed declarations `name` denotes, or None.

    The ONE classifier. resolve refuses the None, and the driver dispatches on
    the answer to build the primitive's row — neither re-derives the other's,
    which is what keeps the row a primitive receives and the entry a designer
    wrote from being two readings of the same text."""
    for block in n.state_blocks(game):
        for sd in block.decls:
            if sd.name == name:
                return (
                    ReadKind.INDEXED_STATE_VAR
                    if sd.index is not None
                    else ReadKind.STATE_VAR
                )
    for z in game.zones:
        if z.name == name:
            return ReadKind.ZONE_FAMILY if z.index is not None else ReadKind.SINGLE_ZONE
    return None


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


def unimplemented(names: frozenset[str]) -> frozenset[str]:
    """Which of `names` no registered Python implements — the declared-but-
    unimplemented half of the both-ways check, asked at compile time so a
    designer's typo is a diagnostic rather than a playout crash."""
    return names - frozenset(PRIMITIVE_IMPLEMENTATIONS)


def undeclarable_contract(name: str) -> InvocationContract | None:
    """The contract that keeps `name` out of a block, or None when it may be
    declared. A name with no implementation answers None — `unimplemented`
    owns that case, and reporting both would co-report on one defect."""
    impl = PRIMITIVE_IMPLEMENTATIONS.get(name)
    if impl is None or impl.contract in DECLARABLE_CONTRACTS:
        return None
    return impl.contract


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
