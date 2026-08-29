"""The `primitives { }` block's coverage grid.

The block declares the [[primitive]]s a game borrows from outside the DSL —
typed signature and declared reads — and its PRESENCE partitions the game's
native-call namespace in both directions (docs/design-notes/primitive-sidecars.md
section 2; epic #142, stage 3a). This module is that change's grid, authored
red before the implementation: the born-red counts at the foot of this docstring
are its provenance.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   (1) every combination the `primitives { }` grammar accepts is
            implemented or refused with a named diagnostic in the layer that
            owns the class — never parsed and ignored; (2) a game's Primitive
            regime is a CHECKED partition, so an undeclared game keeps the
            legacy namespace exactly and a declared game can reach no other
            game's Primitive; (3) a declaration AGREES with the implementation
            it names — about existence, about invocation contract, and about
            SHAPE (arity, parameter types, return type) — so a checked game
            cannot call Python with arguments it does not take; and that
            declared signature is what freezes the arguments and what the call
            site is checked against, so no declared spelling can hand an
            implementation a raw engine value;
            (4) a declared `reads` clause bounds what the implementation
            receives, per primitive and per call, and an undeclared name is
            ABSENT rather than merely unfetched — with every clause a SET whose
            binders key the domain their declaration is indexed by, so no entry
            of a clause can silently replace another and no binder can key an
            instance the declaration has none of; and a `reads` name is
            GAME-scoped state, never a phase's own and never a name both
            levels declare, because the row is materialized on every call and
            the runtime resolves the innermost frame, and never a name the
            game declares in two namespaces at once; and (5) a call that
            resolves to a designer function is not a native call, so no
            registry keyed by native NAME answers about it.
domain:     the block's own surface — clause placement x {game, library},
            entry cardinality x {absent, empty, one, many, second block},
            arity x {0, 1, many}, declared type name x {parameter, return}
            over `primitives_block.declarable_type_names` and its explicitly
            listed complement, reads-name kind x binder x
            {state variable, indexed state variable, zone family, single
            zone, unknown} — crossed with the REGIME axis (declared /
            legacy) wherever a cell's outcome differs between them, and with
            the six Primitive namespaces of `cardlang/builtins/functions.py`.
            Deliberately OUTSIDE it: the five namespaces the block does not
            cover have exactly one cell each here (the block cannot name
            them), because their declaration slots are epic #142's stage-4
            scope; and the corpus is outside it by construction in 3a — no
            corpus game declares a block, so the reconciliation pin's
            declared arm has the witness fixture as its only member, which
            `test_reconciliation_reddens_on_a_planted_orphan` and its dual
            keep from being vacuous.
            Two boundaries the domain has by construction rather than by
            omission. The walled-namespace cells sample one member per
            namespace, and `PRIMITIVE_TRICK_WINNERS` is EMPTY — deliberately,
            as the registry's own comment records — so four of the five walls
            carry a cell and the fifth is unreachable until a game files a
            game-local trick winner there. And a declared Primitive cannot be
            a `where jointly` predicate at all: that position needs a
            collection parameter, which no declared spelling produces
            (issue #472), so the joint-codec pairing obligation the position
            carries is 3b's to meet, not a cell this grid can run.
            `TCell` is reachable at the TYPE-NAME gate and unusable in a
            concrete entry: no registered implementation takes one, so the
            shape check refuses every `cell`-typed declaration. The two guards
            answer different questions and the grid runs the gate's.
registry:   `cardlang/builtins/functions.py` (the six Primitive namespaces
            and `BUILTIN_CALL_FUNCS`); `cardlang/primitives_block.py`
            (`PRIMITIVE_IMPLEMENTATIONS`, `WALLED_NAMESPACES`,
            `DECLARABLE_BUILTIN_TYPE_NAMES`, `UNDECLARABLE_TYPE_CONSTRUCTORS`,
            `InvocationContract`); `cardlang.types.Type` (the constructor
            partition, via `typing.get_args`); the `?game_item` scrape in
            tests/test_game_clause_guards.py for the clause registry; the
            declared-reads accessors' own refusal matrix in
            tests/test_primitive_reads.py; the load site that populates the
            derived table is `runtime/driver.play_game`, the one
            `RuntimeState(` construction in `cardlang/` — every path that can
            reach `native_call`, the OpenSpiel adapter included, replays
            through it (`openspiel/replay.py`); the implementation's own
            signature comes from `primitives_block.implementation_sig`, the one
            site that reads the Python side's statement of it; the validation
            ORDER against minted names is pinned by
            `test_the_only_minted_position_domain_source_is_the_board`, which
            derives the minting sites from resolve's source.
covered:    the parametrized cells below. The clause's duplication and
            absorption cells are tests/test_game_clause_guards.py's, whose
            axes derive from `?game_item` and so cover this clause without
            an edit; the keyword's anchoring cell is
            tests/test_keyword_anchoring.py's, whose axis is Lark's own
            terminal table.
sampled:    the syntactic-position axis is sampled at the two positions a
            declared Primitive's VALUE can differ by — an expression
            statement and a `when:` guard — rather than crossed over every
            call position, because a declared name resolves through one
            namespace lookup that is position-independent by construction
            (`primitives_block.call_namespace`); the bare-name slots are the
            walled namespaces, covered as their own cells.
does not prove: a green here says nothing about whether a declared read is
            SUFFICIENT for its implementation — that a Primitive declaring
            `reads hand[p]` does not also need `trump_suit` is proven by the
            implementation failing, at playout, on the bundle it was handed,
            which only running the game can show. The witness fixture is the
            one place that runs. And every name declarable in 3a is also in
            `CALL_SIGS` with the SAME signature, so no cell here distinguishes
            the two tables by the values they carry — the freeze cell plants a
            divergence to observe which table is read, and the behavioral
            distinction becomes visible only when 3b's declarations differ
            from the registry they replace.

Born red (the bare run on this branch, before any of the block's grammar,
resolve, typecheck or runtime existed): `58 failed, 51 passed`. Every
block-bearing cell died at the block's own line, and the 51 that passed are
the registry reconciliations above, which pin tables the same commit added
and are green by construction rather than by the implementation. Every cell
has since flipped, so no mark remains.

Red a second time, at `14 failed`, when review found five defect CLASSES the
first domain statement did not reach — the declaration's shape against the
implementation's, the index binder's domain, the validation order against
minted names, the invocation contract crossed with the reads-clause shape,
and the reads clause as a multiset. Red a third time, at `5 failed`, on four
more: the parameter list as a multiset (the reads rule's sibling one slot
over, which the first sweep of that class missed), the namespace a
function-shadow check asks, phase-local state in a reads clause, and the
binder compared by erased type rather than by domain identity. Red a fourth
time, at `1 failed`, on cross-level state shadowing — a name the game and a
phase both declare, where the classifier matched one declaration and the
runtime resolved the other. Red a fifth time, at `4 failed`, on a read name
denoting two declarations at once, and on the native name-based guards that
still answered about a call the runtime dispatches to a designer function.
Each class was derived and rowed before its fix, on the same order.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import importlib
import inspect
import pathlib
import random
import typing

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    CALL_FUNCS,
    PRIMITIVE_CALL_FUNCS,
)
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.primitives_block import (
    DECLARABLE_BUILTIN_TYPE_NAMES,
    DECLARABLE_CONTRACTS,
    PRIMITIVE_IMPLEMENTATIONS,
    UNDECLARABLE_TYPE_CONSTRUCTORS,
    Implementation,
    InvocationContract,
    Regime,
    WALLED_NAMESPACES,
    call_namespace,
    declared_names,
    regime,
    walled_namespace_of,
)
from cardlang.runtime.driver import play_game
from cardlang.runtime.reads import PRIMITIVE_READS, PrimitiveReads
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Seating
from cardlang.types import Type

# --- the probe game ----------------------------------------------------------
#
# A complete, PLAYABLE two-seat game: the primitive's value decides the score,
# so a cell that merely parses cannot pass for one that runs. `{0: 1, 1: 0}` is
# the house contract — a true witness and a false witness in one playout.

_PINOCHLE_ENTRY = (
    "pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit"
)


def _game(block: str | None = _PINOCHLE_ENTRY, body: str = "", extra: str = "") -> str:
    """A probe game, with `block` as its `primitives { }` entries (None for a
    game that writes no block at all — the legacy regime)."""
    clause = "" if block is None else "  primitives { " + block + " }\n"
    return (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        + clause
        + "  zones { deck : Deck  hand[player] : Hand<player>\n"
        "          discard : Discard }\n"
        "  state { trump_suit : Suit? = none\n"
        "          seen[player] : Integer = 0\n"
        "          score[player] : Integer = 0 }\n"
        + extra
        + "  phase play {\n"
        "    trump_suit := spades\n"
        "    move all cards from deck as-equally-as-possible to each hand\n"
        + body
        + "\n  }\n"
        "  winner: highest score\n"
        "}\n"
    )


_SCORE_FROM_PRIMITIVE = (
    "    score[0] := if pinochle_meld_value(0) >= 0 then 1 else 0"
)


def _checks(source: str) -> n.Game:
    return check_dsl(source, "probe.cardlang")


def _refused(source: str) -> str:
    """Every diagnostic a refused probe produces, rendered.

    The whole bag, not the first item: resolve reports bag-first, so a probe
    that trips two guards would otherwise be read against whichever spoke
    first — and which that is, is not the cell's claim."""
    with pytest.raises(DiagnosticError) as excinfo:
        _checks(source)
    notes = list(getattr(excinfo.value, "__notes__", None) or [])
    return "\n".join([str(excinfo.value), *notes])


# --- the registries, reconciled ---------------------------------------------


def test_the_implementation_index_covers_the_primitive_namespace() -> None:
    """Both directions over the call namespace: a registered Primitive with no
    implementation row cannot be declared by any game, and a row for a name no
    registry claims is a classification of nothing.

    red under: delete any row from `PRIMITIVE_IMPLEMENTATIONS`, or add one for
    a name outside `PRIMITIVE_CALL_FUNCS`."""
    assert frozenset(PRIMITIVE_IMPLEMENTATIONS) == PRIMITIVE_CALL_FUNCS


@pytest.mark.parametrize("name", sorted(PRIMITIVE_IMPLEMENTATIONS))
def test_every_indexed_implementation_resolves(name: str) -> None:
    """The index is names-only, so nothing type-checks it: the module path and
    the attribute are strings, and a moved or renamed function would leave a
    row reading as authoritative forever. Importing each here is what makes the
    strings answerable.

    red under: misspell any row's `attribute`."""
    impl = PRIMITIVE_IMPLEMENTATIONS[name]
    module = importlib.import_module(impl.module)
    assert callable(getattr(module, impl.attribute, None)), (
        f"{impl.module}.{impl.attribute} — the index names it for {name!r}, "
        f"and the module does not define it"
    )


# --- the ranking gate, derived from the implementations ----------------------


@functools.cache
def _module_function_sources(module: str) -> dict[str, str]:
    """One runtime module's own top-level functions, name -> source text.

    Functions the module IMPORTS are excluded (`__module__` keys them), so a
    walk that follows a call name stays inside the home module."""
    mod = importlib.import_module(module)
    return {
        attr: inspect.getsource(obj)
        for attr, obj in vars(mod).items()
        if inspect.isfunction(obj) and getattr(obj, "__module__", None) == module
    }


def _implementation_source(name: str) -> str:
    """The Python one registered Primitive runs, as text: its entry point plus
    every top-level function of its home module reachable from it by call name.

    The closure is what makes the read visible when the entry point delegates —
    a scrape of the entry point alone would miss a helper's read, and a scrape
    of the whole module would report every sibling that merely shares the
    file."""
    impl = PRIMITIVE_IMPLEMENTATIONS[name]
    sources = _module_function_sources(impl.module)
    seen: set[str] = set()
    frontier = [impl.attribute]
    chunks: list[str] = []
    while frontier:
        attr = frontier.pop()
        if attr in seen or attr not in sources:
            continue
        seen.add(attr)
        chunks.append(sources[attr])
        for node in ast.walk(ast.parse(sources[attr])):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                frontier.append(node.func.id)
    assert seen, (
        f"{name}: the index names {impl.module}.{impl.attribute}, which is not "
        f"a top-level function of that module — the scrape below would report "
        f"it as reading nothing"
    )
    return "\n".join(chunks)


def _rank_index_readers() -> frozenset[str]:
    """Every registered Primitive whose Python names `rank_index`. The domain
    is the whole index — `_implementation_source` refuses a row it cannot
    resolve, so a green here cannot come from a shrunken one."""
    return frozenset(
        name
        for name in PRIMITIVE_IMPLEMENTATIONS
        if "rank_index" in _implementation_source(name)
    )


def test_every_rank_index_reading_primitive_is_ranking_gated() -> None:
    """A Primitive that reads the declared rank order is gated on the game
    declaring one.

    property:   membership of `typecheck.RANKING_GATED_FUNCS` covers every
                registered Primitive whose implementation reads a rank index.
                Nothing derives that membership today — a name is added by
                hand — so an ungated reader checks clean in a game with no
                `ranking:` and meets an empty order at playout.
    domain:     `PRIMITIVE_IMPLEMENTATIONS`, every row, resolved to the source
                of the Python it names.
    registry:   the gate is `cardlang/typecheck.py`'s `RANKING_GATED_FUNCS`;
                the reader set is derived from the index rather than listed,
                so a Primitive registered later is scraped without an edit
                here.
    does not prove: only that the NAME is gated. That the reader also reaches
                the runtime's typed channel on a PARTIAL `ranking:` is
                tests/test_trump_slot_class.py's driver grid, whose member
                axis is this registry's union with the two slot registries.
                And the walk follows call names inside the implementation's
                own home module: a reader that takes the order under some
                other name and hands it to a function in a DIFFERENT module
                names `rank_index` nowhere the walk looks. No registered
                Primitive is shaped that way; the shape is what a green here
                does not exclude.

    red under: drop `salvo_combos` from `RANKING_GATED_FUNCS`."""
    from cardlang.typecheck import RANKING_GATED_FUNCS

    ungated = _rank_index_readers() - RANKING_GATED_FUNCS
    assert not ungated, (
        f"registered Primitives reading a rank index but ungated: "
        f"{sorted(ungated)} — add each to `typecheck.RANKING_GATED_FUNCS` "
        f"(and give it a driver in tests/test_trump_slot_class.py)"
    )


def test_the_rank_index_scrape_sees_a_reader_and_separates_two_file_mates() -> None:
    """Anti-vacuity floor and discrimination floor in one, because the pin
    above is a SUBSET assertion: an empty reader set satisfies it vacuously,
    and a module-granular scrape satisfies it by over-reporting.

    The control pair is the two cribbage pegging scorers, which share
    `cardlang/runtime/cribbage.py` and sit on opposite sides of typecheck's
    own census — `peg_run_points` reads the order to find a run,
    `peg_pair_points` compares ranks for equality and reads no order. A
    scrape that reported both would be answering about the FILE.

    red under: read the whole module's source instead of the call closure —
    `peg_pair_points` joins the reader set."""
    readers = _rank_index_readers()
    assert readers, "the scrape found no reader at all"
    assert "peg_run_points" in readers, sorted(readers)
    assert "peg_pair_points" not in readers, sorted(readers)


def test_every_invocation_contract_has_a_member() -> None:
    """Every arm of the contract enum classifies at least one registered
    Primitive. An arm with no member is a distinction the registry does not
    make, and the block's refusals would then be unreachable.

    red under: add an arm to `InvocationContract` with no row using it."""
    used = {impl.contract for impl in PRIMITIVE_IMPLEMENTATIONS.values()}
    assert used == set(InvocationContract)


def test_the_declarable_contracts_are_a_proper_subset() -> None:
    """The allow-list admits some arms and refuses others — a partition that
    admitted everything would make the refusal cells below vacuous.

    red under: set `DECLARABLE_CONTRACTS` to `set(InvocationContract)`."""
    assert DECLARABLE_CONTRACTS < set(InvocationContract)
    refused = set(InvocationContract) - DECLARABLE_CONTRACTS
    assert {
        name
        for name, impl in PRIMITIVE_IMPLEMENTATIONS.items()
        if impl.contract in refused
    }, "no registered Primitive carries a refused contract"


def test_the_declarable_builtin_type_names_are_the_languages() -> None:
    """The block's declarable built-in type names and the language's declared-
    type names are the same closed set, stated independently in two modules and
    crossed here rather than one importing the other.

    red under: add a name to `DECLARABLE_BUILTIN_TYPE_NAMES`."""
    from cardlang.typecheck import KNOWN_TYPE_NAMES

    assert DECLARABLE_BUILTIN_TYPE_NAMES == KNOWN_TYPE_NAMES


def test_the_type_constructor_partition_is_total() -> None:
    """Every `Type` constructor is either REACHED by a declared spelling or
    listed as unreachable with its reason — the axis-5 partition, so a
    constructor added to the type model lands unclassified and is named here
    rather than silently joining the unspellable side.

    red under: add a member to `cardlang.types.Type`."""
    all_constructors = {t.__name__ for t in typing.get_args(Type)}
    unreachable = set(UNDECLARABLE_TYPE_CONSTRUCTORS)
    reachable = _reachable_type_constructors()
    assert not (reachable & unreachable), sorted(reachable & unreachable)
    assert reachable | unreachable == all_constructors, sorted(
        all_constructors - reachable - unreachable
    )


def _reachable_type_constructors() -> set[str]:
    """Which `Type` constructors a declared spelling can produce, DERIVED by
    running every declarable name through the language's one conversion site
    (`typecheck.type_from_name`), in both the bare and the `?` spelling."""
    from cardlang.typecheck import TypeEnv, type_from_name

    env = TypeEnv()
    out: set[str] = set()
    probe = _checks(_game(block="", body=""))
    names = DECLARABLE_BUILTIN_TYPE_NAMES | {p.name for p in probe.positions}
    for name in sorted(names):
        for optional in (False, True):
            t = type_from_name(name, optional, env.structs, env.positions, env.directions)
            out.add(type(t).__name__)
            inner = getattr(t, "inner", None)
            if inner is not None:
                out.add(type(inner).__name__)
    # A board game's `cell` domain is the one declarable name outside the
    # built-ins whose member type is not `TInteger`; probed on its own game
    # rather than by hand-adding `TCell`, so the reachability is measured.
    board = _checks(_board_game())
    from cardlang.typecheck import _position_types

    positions = _position_types(board)
    for name in sorted(positions):
        t = type_from_name(name, False, env.structs, positions, {})
        out.add(type(t).__name__)
    return out


def _board_game() -> str:
    return (
        "game BoardProbe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  pieces: xo_marks\n"
        "  board: grid(3, 3)\n"
        "  zones { supply : Discard }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase play { score[0] := 1 }\n"
        "  winner: highest score\n"
        "}\n"
    )


def test_the_walls_cover_every_namespace_the_block_does_not() -> None:
    """The six Primitive namespaces partition into the one the block covers and
    the five it walls, with nothing in both and nothing in neither.

    red under: drop a row from `WALLED_NAMESPACES`."""
    walled: set[str] = set()
    for names in WALLED_NAMESPACES.values():
        walled |= set(names)
    assert not (walled & PRIMITIVE_CALL_FUNCS), sorted(walled & PRIMITIVE_CALL_FUNCS)
    for name in sorted(walled):
        assert walled_namespace_of(name) is not None
    for name in sorted(PRIMITIVE_CALL_FUNCS):
        assert walled_namespace_of(name) is None


# --- axis 1-3: clause placement, cardinality, repeatability ------------------


def test_a_block_is_a_game_clause() -> None:
    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    assert regime(game) is Regime.DECLARED
    assert declared_names(game) == {"pinochle_meld_value"}


def test_an_absent_block_is_the_legacy_regime() -> None:
    game = _checks(_game(block=None, body="    score[0] := 1"))
    assert regime(game) is Regime.LEGACY
    assert declared_names(game) == frozenset()
    assert call_namespace(game) == CALL_FUNCS


def test_an_empty_block_is_a_declaration_not_an_absence() -> None:
    """The block's presence, not its contents, picks the regime: an empty block
    says this game borrows no Python, and its native namespace is the Builtins
    exactly."""
    game = _checks(_game(block="", body="    score[0] := 1"))
    assert regime(game) is Regime.DECLARED
    assert declared_names(game) == frozenset()
    assert call_namespace(game) == BUILTIN_CALL_FUNCS


def test_an_empty_block_refuses_a_legacy_primitive_call() -> None:
    message = _refused(
        _game(block="", body="    score[0] := if tichu_dragon_won() then 1 else 0")
    )
    assert "tichu_dragon_won" in message
    assert "primitives" in message


def test_a_second_block_is_refused() -> None:
    source = _game(body=_SCORE_FROM_PRIMITIVE).replace(
        "  zones {", "  primitives { }\n  zones {", 1
    )
    message = _refused(source)
    assert "one `primitives { }` block" in message


def test_a_block_in_a_library_is_refused() -> None:
    """A library holds definitions, not the game's borrowings: a Primitive
    belongs to ONE game, so a shared library declaring one would be the
    cross-game coupling the block exists to end."""
    from cardlang.parse import parse_library

    with pytest.raises(DiagnosticError) as excinfo:
        parse_library(
            "library probe { primitives { f() : Integer } }",
            "docs/libraries/probe.cardlang",
        )
    assert "primitives" in str(excinfo.value)


# --- axis 2/4: the three wrong spellings ------------------------------------


@pytest.mark.parametrize(
    "source,fragment",
    [
        ("  primitives : { }\n", "takes no colon"),
        (
            "  primitives { pinochle_meld_value(p : Player) -> Integer }\n",
            "not an arrow",
        ),
        (
            "  primitives { pinochle_meld_value(p : Player) : Integer = 0 }\n",
            "declares a signature, never a value",
        ),
    ],
    ids=["colon-habit", "arrow-return", "state-row-default"],
)
def test_a_wrong_entry_spelling_is_refused_in_the_designers_voice(
    source: str, fragment: str
) -> None:
    """The three shapes an author reaches for: the colon habit every other
    block clause refuses, the arrow the design note sketched before the block
    had a surface, and the `= <default>` a `state { }` row carries. Each is a
    plausible sentence, so each earns a rejection NAMING the right spelling
    rather than the lexer's voice."""
    game = _game(block=None, body="    score[0] := 1").replace(
        "  zones {", source + "  zones {", 1
    )
    message = _refused(game)
    assert fragment in message


def test_one_wrong_entry_among_right_ones_still_speaks() -> None:
    """The reject arms' tails admit the well-formed entry too, so a block whose
    LAST entry is wrong reaches the designer-voice rejection rather than the
    lexer's — the `trick_order` comma arm's rule, which exists because the
    likeliest slip is one row among many."""
    block = _PINOCHLE_ENTRY + "  tichu_dragon_won() -> Boolean"
    message = _refused(_game(block=block, body=_SCORE_FROM_PRIMITIVE))
    assert "not an arrow" in message
    assert "tichu_dragon_won" in message


# --- axis 22: the declared signature is what the CALL is checked against ----


def test_a_call_with_the_wrong_arity_is_refused() -> None:
    message = _refused(_game(body="    score[0] := pinochle_meld_value(0, 1)"))
    assert "pinochle_meld_value" in message
    assert "argument" in message


def test_a_call_with_a_wrong_typed_argument_is_refused() -> None:
    """The declared parameter type is what the call site is checked against —
    so a declaration is not decoration, it is the contract."""
    message = _refused(
        _game(body="    score[0] := pinochle_meld_value(A of spades)")
    )
    assert "pinochle_meld_value" in message
    assert "Player" in message


# --- axis 6: arity -----------------------------------------------------------


@pytest.mark.parametrize(
    "entry,call",
    [
        ("tichu_dragon_won() : Boolean", "tichu_dragon_won()"),
        ("pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit",
         "pinochle_meld_value(0) >= 0"),
        ("gin_knock_ok(p : Player, c : Card) : Boolean reads hand[p], taken[p]",
         "gin_knock_ok(0, A of spades)"),
    ],
    ids=["zero-arg", "one-arg", "two-arg"],
)
def test_every_arity_declares(entry: str, call: str) -> None:
    """Zero-argument entries are legal — real members exist — so the parameter
    list is `[...]`, not a required one."""
    extra = "" if "taken" not in entry else ""
    source = _game(block=entry, body=f"    score[0] := if {call} then 1 else 0", extra=extra)
    if "taken" in entry:
        source = source.replace(
            "          discard : Discard }",
            "          taken[player] : HiddenPile<player>\n          discard : Discard }",
        )
    game = _checks(source)
    assert declared_names(game) == {entry.split("(")[0]}


# --- axis 5/18: the declared type set ---------------------------------------


@pytest.mark.parametrize("type_name", sorted(DECLARABLE_BUILTIN_TYPE_NAMES))
def test_every_declarable_type_name_is_spellable_in_both_slots(type_name: str) -> None:
    """Parameter slot and return slot take the same name set — a type spellable
    in one and not the other would be a surface a designer cannot predict."""
    entry = f"probe_fn(x : {type_name}) : {type_name}"
    source = _game(block=entry, body="    score[0] := 1")
    # The name has no implementation, so the both-ways check refuses it — which
    # is the point: the TYPE must not be what fails.
    message = _refused(source)
    assert "probe_fn" in message
    assert type_name not in message.split("probe_fn")[0]


@pytest.mark.parametrize(
    "spelling", ["Any", "Line", "dir", "Bid"], ids=["any", "line", "direction", "struct"]
)
def test_an_unspellable_type_name_is_refused(spelling: str) -> None:
    """The complement of the declarable set, at the parameter slot. Each parses
    (they are bare names, so the grammar cannot tell them apart from a
    declarable one) and is refused by NAME — never accepted and silently typed
    as the permissive top, which is the one reading that would let a declared
    Primitive receive an unfrozen engine value."""
    entry = f"pinochle_meld_value(x : {spelling}) : Integer"
    message = _refused(_game(block=entry, body="    score[0] := 1"))
    assert spelling in message
    assert "#472" in message


def test_a_collection_type_has_no_spelling_at_all() -> None:
    """The one unspellable shape that is grammatically inexpressible rather
    than refused by name: the type slot is a bare name with an optional `?`,
    and no production spells a collection. That is the state surface totality
    calls inexpressible, and issue #472 is what would change it."""
    entry = "pinochle_meld_value(x : collection of Card) : Integer"
    message = _refused(_game(block=entry, body="    score[0] := 1"))
    assert "syntax error" in message


# --- axis 7-9: the reads clause ---------------------------------------------


@pytest.mark.parametrize(
    "clause",
    [
        "trump_suit",
        "seen",
        "hand",
        "discard",
        "hand[p]",
        "seen[p]",
    ],
    ids=["state-var", "indexed-state-var", "zone-family", "single-zone",
         "family-instance", "state-instance"],
)
def test_every_reads_name_kind_classifies(clause: str) -> None:
    entry = f"pinochle_meld_value(p : Player) : Integer reads {clause}"
    game = _checks(_game(block=entry, body=_SCORE_FROM_PRIMITIVE))
    assert declared_names(game) == {"pinochle_meld_value"}


@pytest.mark.parametrize(
    "clause,fragment",
    [
        ("no_such_name", "no_such_name"),
        ("trump_suit[p]", "trump_suit"),
        ("discard[p]", "discard"),
        ("hand[q]", "q"),
        ("seating", "seating"),
    ],
    ids=["unknown-name", "binder-on-scalar-state", "binder-on-single-zone",
         "undeclared-binder", "engine-fact"],
)
def test_a_bad_reads_name_is_refused(clause: str, fragment: str) -> None:
    entry = f"pinochle_meld_value(p : Player) : Integer reads {clause}"
    message = _refused(_game(block=entry, body=_SCORE_FROM_PRIMITIVE))
    assert fragment in message


def test_an_engine_fact_name_names_its_deferral() -> None:
    """The reads vocabulary covers the name-keyed half only; the engine-
    structural half stays whole-bundle behind a refusal that CITES its issue,
    so the deferral is loud rather than a name that simply looks unknown."""
    entry = "pinochle_meld_value(p : Player) : Integer reads round_state"
    message = _refused(_game(block=entry, body=_SCORE_FROM_PRIMITIVE))
    assert "#474" in message


# --- axis 15: the both-ways check's THIRD leg — shape agreement -------------
#
# Existence and contract category are two legs; a declaration that names a real
# implementation of the right category can still DISAGREE with it about arity,
# parameter types or return type. The class is every field of the declared
# entry crossed against the implementation's own signature, and the whole class
# lands in one comparison because the two sides are `Sig`s.


@pytest.mark.parametrize(
    "entry,call",
    [
        ("pinochle_meld_value() : Integer reads hand, trump_suit",
         "pinochle_meld_value()"),
        ("pinochle_meld_value(p : Player, q : Player) : Integer reads hand, trump_suit",
         "pinochle_meld_value(0, 1)"),
        ("pinochle_meld_value(c : Card) : Integer reads hand, trump_suit",
         "pinochle_meld_value(A of spades)"),
        ("pinochle_meld_value(p : Player) : Boolean reads hand, trump_suit",
         "0"),
    ],
    ids=["arity-short", "arity-long", "param-type", "return-type"],
)
def test_a_declaration_disagreeing_with_its_implementation_is_refused(
    entry: str, call: str
) -> None:
    """Every field of the declared entry, against the signature the Python side
    states. Unrefused, each would compile clean and die mid-playout — a
    `TypeError` for a wrong arity, a `KeyError` for a wrong parameter type —
    which is the designer's error arriving in the runtime's channel."""
    body = f"    score[0] := if {call} >= 0 then 1 else 0" if "Boolean" not in entry \
        else "    score[0] := 1"
    message = _refused(_game(block=entry, body=body))
    assert "pinochle_meld_value" in message
    assert "implement" in message or "signature" in message


def test_a_declaration_agreeing_with_its_implementation_is_admitted() -> None:
    """The positive control: the shape check must not refuse the agreeing
    declaration, or every cell above would pass for the wrong reason."""
    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    assert declared_names(game) == {"pinochle_meld_value"}


# --- axis 9: the index binder's DOMAIN, not just its name -------------------


def _index_domain_names(game: n.Game) -> frozenset[str]:
    """Every index domain a declaration in the probe game can be keyed by —
    the roles a zone family or indexed state variable may carry, plus the
    game's own position domains. Derived so a role added to the registry
    arrives here as an uncovered spelling rather than silently."""
    from cardlang.domains import ZONE_INDEX_ROLES, role_names

    return frozenset(role_names(ZONE_INDEX_ROLES)) | {p.name for p in game.positions}


def test_the_binder_domain_axis_is_derived() -> None:
    """Anti-vacuity for the cells below: the wrong-domain axis is the index
    domains MINUS the one the read actually carries, so a registry with one
    member would make every rejection cell disappear."""
    probe = _checks(_game(block="", body="    score[0] := 1"))
    assert len(_index_domain_names(probe)) >= 2


@pytest.mark.parametrize(
    "param_type,read,accepted",
    [
        ("Player", "hand[x]", True),
        ("Suit", "hand[x]", False),
        ("Team", "hand[x]", False),
        ("Player", "seen[x]", True),
        ("Rank", "seen[x]", False),
    ],
    ids=["player-family-ok", "suit-keys-player-family", "team-keys-player-family",
         "player-state-ok", "rank-keys-player-state"],
)
def test_an_index_binders_declared_type_must_match_the_index_domain(
    param_type: str, read: str, accepted: bool
) -> None:
    """A binder keys an INSTANCE, so its declared type must be the domain the
    declaration is indexed by. Checking only that the name is a parameter let
    `reads hand[s]` with `s : Suit` compile clean and fail at playout, in the
    runtime's channel, on a compile-time fact."""
    entry = f"pinochle_meld_value(x : {param_type}) : Integer reads {read}, trump_suit"
    source = _game(block=entry, body="    score[0] := 1")
    if accepted:
        # The shape check owns the disagreement with the implementation, which
        # every cell here provokes; what must NOT appear is the domain refusal.
        try:
            _checks(source)
        except DiagnosticError as exc:
            assert "index domain" not in str(exc)
    else:
        assert "index domain" in _refused(source)


def test_the_binder_domain_guard_fires_without_the_shape_check() -> None:
    """The binder guard, ALONE.

    Every cell above provokes the shape check too — a single-parameter entry's
    binder IS its parameter, so a wrong binder type is also a wrong signature,
    and the two co-report. A guard only ever seen beside a broader sibling is
    a guard nobody has watched work: this entry's signature AGREES with the
    implementation exactly, and only the binder is wrong.

    red under: delete the binder arm from `_check_primitive_signatures`."""
    source = _game(
        block="gin_knock_ok(p : Player, c : Card) : Boolean reads hand[c]",
        body="    score[0] := if gin_knock_ok(0, A of spades) then 1 else 0",
    )
    message = _refused(source)
    assert "index domain" in message
    assert "is not the signature" not in message


# --- axis 3: validation ordering against every minted-domain source ---------


def test_the_only_minted_position_domain_source_is_the_board() -> None:
    """The ordering class, derived rather than remembered: a name minted AFTER
    the block is validated is a name the block cannot spell, however the
    partition describes it. `game.positions` is the only declarable-name source
    resolve extends, and `_resolve_board` is the only site that extends it — so
    the ordering obligation has exactly one member, and this is what would fail
    if a second minting site appeared."""
    import re

    source = (ROOT_DIR / "cardlang" / "resolve.py").read_text()
    minting = re.findall(r"replace\((?:game|result), positions=[^)]*\)", source)
    assert len(minting) == 1, (
        f"resolve mints into `game.positions` at {len(minting)} sites — the "
        f"block's type-name validation must run after every one of them"
    )


def test_a_board_minted_cell_reaches_the_declarable_type_names() -> None:
    """The ordering claim: `cell` exists only after `_resolve_board` mints it,
    so a block validated before that point refuses a name the rest of the
    pipeline accepts — the signature builder maps the resolved named-member
    position to `TCell`, and the constructor partition calls that constructor
    reachable.

    The gate is what this asserts, not a whole declaration: no registered
    implementation takes a `TCell`, so the shape check refuses every concrete
    `cell`-typed entry — a SECOND guard, for a different reason, and the one
    that bounds the cell in practice until an implementation takes one.

    red under: move `_check_primitives_block` back above `_resolve_board`."""
    from cardlang.primitives_block import declarable_type_names

    board = _checks(_board_game())
    assert any(p.name == "cell" for p in board.positions)
    assert "cell" in declarable_type_names(board)


def test_a_declared_position_domain_reaches_them_too() -> None:
    """The control the ordering cell needs: a domain the DESIGNER declares is
    in `game.positions` from the start, so it would pass at either validation
    point — which is why it cannot stand in for the minted one."""
    from cardlang.primitives_block import declarable_type_names

    game = _checks(
        _game(block="", body="    score[0] := 1").replace(
            "  zones {", "  positions { column : 1..3 }\n  zones {", 1
        )
    )
    assert "column" in declarable_type_names(game)


# --- axis 22: the contract category crossed with the reads-clause shape -----


def _declarable_contract_names() -> dict[str, str]:
    """One registered Primitive per declarable contract, DERIVED — so a
    contract admitted later arrives here as a missing key rather than a cell
    nobody wrote."""
    out: dict[str, str] = {}
    for name, impl in sorted(PRIMITIVE_IMPLEMENTATIONS.items()):
        if impl.contract in DECLARABLE_CONTRACTS:
            out.setdefault(impl.contract.value, name)
    return out


def test_every_declarable_contract_has_a_reads_shape_cell() -> None:
    """The cross below is complete over the contracts the block admits.

    red under: admit a third contract in `DECLARABLE_CONTRACTS`."""
    assert set(_declarable_contract_names()) == {
        c.value for c in DECLARABLE_CONTRACTS
    }
    assert set(_READS_SHAPE_CELLS) == {
        (c.value, shape)
        for c in DECLARABLE_CONTRACTS
        for shape in ("empty", "nonempty")
    }


# contract x reads-clause shape -> whether the declaration is admitted. A PURE
# implementation never receives the bundle, so a `reads` clause on one declares
# a dependency the dispatch cannot honour — accepted-but-ignored, refused.
_READS_SHAPE_CELLS: dict[tuple[str, str], bool] = {
    ("bundled", "empty"): True,
    ("bundled", "nonempty"): True,
    ("pure", "empty"): True,
    ("pure", "nonempty"): False,
}


@pytest.mark.parametrize("cell", sorted(_READS_SHAPE_CELLS))
def test_the_contract_and_reads_shape_cross(cell: tuple[str, str]) -> None:
    contract, shape = cell
    name = _declarable_contract_names()[contract]
    params = "(p : Player)" if contract == "bundled" else "(x : Integer)"
    ret = "Integer" if contract == "bundled" else "Integer"
    reads = " reads trump_suit" if shape == "nonempty" else ""
    entry = f"{name}{params} : {ret}{reads}"
    source = _game(block=entry, body="    score[0] := 1")
    if _READS_SHAPE_CELLS[cell]:
        try:
            _checks(source)
        except DiagnosticError as exc:
            assert "reads" not in str(exc), str(exc)
    else:
        message = _refused(source)
        assert "reads" in message
        assert name in message


# --- axis 7: the reads clause as a MULTISET ---------------------------------


@pytest.mark.parametrize(
    "clause",
    [
        "hand, hand, trump_suit",
        "hand[p], hand[q], trump_suit",
        "hand, hand[p], trump_suit",
        "trump_suit, trump_suit",
    ],
    ids=["bare-twice", "two-binders", "family-and-instance", "state-twice"],
)
def test_a_repeated_reads_name_is_refused(clause: str) -> None:
    """A `reads` clause is a SET of declarations, and the materialization keys
    by name — so a repeat is not additive, it is one entry silently winning.
    `hand, hand[p]` would play to completion returning a value computed from
    ONE hand while the declaration says every hand: a silent wrong answer, which
    is why the whole multiset is refused rather than the colliding pair."""
    entry = f"gin_knock_ok(p : Player, q : Card) : Boolean reads {clause}"
    message = _refused(_game(block=entry, body="    score[0] := 1"))
    assert "reads" in message
    assert "once" in message or "repeat" in message


# --- axis 6/7: the entry's own name lists, as multisets ---------------------


def _block_name_lists() -> set[tuple[str, str]]:
    """Every name-bearing LIST the block's nodes carry, derived from the AST.

    The duplicate rule's domain. It was swept once for `reads` and the
    parameter list escaped, which is what a remembered domain does — so the
    axis is read off the nodes and a fourth list arrives as an uncovered
    member rather than as the next review finding."""
    return {
        (cls.__name__, f.name)
        for cls in (n.PrimitivesBlock, n.PrimitiveDecl)
        for f in dataclasses.fields(cls)
        if f.name != "span" and "tuple" in str(f.type)
    }


def test_every_name_list_the_block_carries_refuses_duplicates() -> None:
    """The class, closed by derivation: entries, parameters and reads are the
    three lists, and each has a cell below refusing a repeat.

    red under: add a name-bearing tuple field to `PrimitiveDecl` or
    `PrimitivesBlock` without a duplicate cell for it."""
    assert _block_name_lists() == {
        ("PrimitivesBlock", "decls"),  # test_a_duplicate_entry_is_refused
        ("PrimitiveDecl", "params"),  # test_a_duplicate_parameter_name_is_refused
        ("PrimitiveDecl", "reads"),  # test_a_repeated_reads_name_is_refused
    }


def test_a_duplicate_parameter_name_is_refused() -> None:
    """The parameter list is a SET too — the sibling of the reads-multiset rule
    one slot over, and the same failure: the type check reads the list as a map
    (last wins) while the driver's binder resolves a binder by `index` (first
    wins), so the two halves of one declaration disagree about which parameter
    a binder names."""
    entry = "gin_lay_ok_a(x : Card, x : Player) : Boolean reads meldA[x]"
    source = _game(
        block=entry,
        body="    score[0] := if gin_lay_ok_a(A of spades, 0) then 1 else 0",
    ).replace(
        "          discard : Discard }",
        "          meldA[player] : PlayerPile<player>\n          discard : Discard }",
    )
    message = _refused(source)
    assert "x" in message
    assert "once" in message or "repeat" in message


# --- axis 13/17: the namespace a SHADOW check asks -------------------------


def test_a_declared_game_may_define_a_function_named_after_a_walled_primitive() -> None:
    """The regime's isolation runs both ways. A Primitive absent from this
    game's namespace cannot be called here, so a user function of that name
    shadows nothing — refusing it would make the declared regime narrower than
    the legacy one it replaces, which is the opposite of what it promises."""
    source = "function tichu_dragon_won() = true\n" + _game(
        block="", body="    score[0] := if tichu_dragon_won() then 1 else 0"
    )
    game = _checks(source)
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 1, 1: 0}


def test_a_legacy_game_still_may_not_shadow_a_primitive() -> None:
    """The control: without a block the whole registry IS the namespace, so the
    shadow guard must still fire — a namespace-scoped check that stopped firing
    for legacy games would trade one silent dispatch for another."""
    source = "function tichu_dragon_won() = true\n" + _game(
        block=None, body="    score[0] := 1"
    )
    assert "shadows" in _refused(source)


# --- axis 7: a reads name must be GAME-scoped state -------------------------


def test_the_shadowable_read_kinds_are_derived() -> None:
    """Which declarable read kinds a PHASE can shadow at all — the class of the
    two cells below, read off the grammar rather than remembered. A phase
    declares state and nothing else, so state is the only kind whose runtime
    resolution can differ from the declaration the classifier matched.

    red under: add another declaration block to `?phase_item` in the grammar."""
    import re

    grammar = (
        ROOT_DIR / "cardlang" / "grammar" / "cardlang.lark"
    ).read_text()
    body = re.search(r"\?phase_item:(.*?)\n\n", grammar, re.S)
    assert body is not None
    alternatives = {a.strip().lstrip("| ") for a in body.group(1).split("\n")}
    declaring = alternatives & {"state_block", "zones", "positions", "type_def"}
    assert declaring == {"state_block"}, (
        f"a phase now declares {sorted(declaring)} — every declarable read kind "
        f"it can carry needs a shadowing cell beside the state one"
    )


def test_a_state_name_shadowed_by_a_phase_is_refused() -> None:
    """A declared read of a name a phase ALSO declares.

    The classifier matches the game-level declaration and the runtime resolves
    the innermost frame, so the primitive silently receives the phase's value
    while that phase runs, so it would play to completion scoring meld under
    the wrong trump. The declaration cannot say which of the two it means, so
    the ambiguity is refused rather than resolved by whichever end happens to
    win."""
    source = (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: pinochle48\n"
        "  ranking: A 10 K Q J 9\n"
        "  primitives { pinochle_meld_value(p : Player) : Integer"
        " reads hand[p], trump_suit }\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { trump_suit : Suit? = spades  score[player] : Integer = 0 }\n"
        "  phase play {\n"
        "    state { trump_suit : Suit? = hearts }\n"
        "    deal 12 cards from deck to each hand\n"
        "    score[0] := pinochle_meld_value(0)\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
    )
    message = _refused(source)
    assert "trump_suit" in message
    assert "phase" in message


def test_a_phase_local_state_read_is_refused() -> None:
    """A `reads` name is materialized on EVERY call, so a phase-local variable
    is readable only while that phase's frame stands — and a Primitive called
    from anywhere else meets a `PrimitiveReadError` on a name its declaration
    said it had. The declaration is game-level, so its reads are too."""
    source = (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  primitives { pinochle_meld_value(p : Player) : Integer"
        " reads hand[p], trump_suit }\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase setup {\n"
        "    state { trump_suit : Suit? = none }\n"
        "    trump_suit := spades\n"
        "  }\n"
        "  phase play { score[0] := pinochle_meld_value(0) }\n"
        "  winner: highest score\n"
        "}\n"
    )
    message = _refused(source)
    assert "trump_suit" in message
    assert "phase" in message


# --- axis 9: the binder's domain IDENTITY, not its erased type --------------


@pytest.mark.parametrize(
    "entry,zones,ok",
    [
        ("tarot_per_opp(x : Integer) : Integer reads hand[x]", "", False),
        ("gin_deadwood(x : Player) : Integer reads hand[x]", "", True),
    ],
    ids=["integer-erases-to-player", "player-keys-player"],
)
def test_a_binder_is_compared_by_domain_identity(
    entry: str, zones: str, ok: bool
) -> None:
    """`coercible` is a COERCION relation — an Integer may stand where a Player
    is wanted, which is right for an operand and wrong for a key. Two position
    domains both erase to Integer as well, so an erased comparison admits a
    binder whose domain has a different member range. The declaration names a
    domain; the comparison is with that domain."""
    source = _game(block=entry, body="    score[0] := 1")
    if ok:
        try:
            _checks(source)
        except DiagnosticError as exc:
            assert "index domain" not in str(exc)
    else:
        assert "index domain" in _refused(source)


def test_two_position_domains_do_not_erase_together() -> None:
    """The second half of the identity claim, which no player/team cell can
    reach: both domains type as `TInteger`, so only an identity comparison
    tells them apart."""
    source = (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  positions { col : 1..3  slot : 1..9 }\n"
        "  primitives { tarot_per_opp(x : slot) : Integer reads pile[x] }\n"
        "  zones { deck : Deck  hand[player] : Hand<player>"
        "  pile[col] : Discard }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase play { score[0] := tarot_per_opp(1) }\n"
        "  winner: highest score\n"
        "}\n"
    )
    message = _refused(source)
    assert "index domain" in message
    assert "col" in message


# --- axis 7: a read name must denote ONE declaration ------------------------


def test_a_name_declared_as_both_a_state_variable_and_a_zone_is_refused() -> None:
    """A game may legally give a state variable and a zone the same name, and
    the classifier consults the two namespaces in order — so it would pick
    state silently and the derived row would carry the name in `state_vars`
    with `zone_families` empty, while a bundled implementation reads
    `gr.families[...]`. The declaration cannot say which it means."""
    source = (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: pinochle48\n"
        "  ranking: A 10 K Q J 9\n"
        "  primitives { pinochle_meld_value(p : Player) : Integer"
        " reads hand[p], trump_suit }\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { hand[player] : Integer = 0  trump_suit : Suit? = spades\n"
        "          score[player] : Integer = 0 }\n"
        "  phase play { score[0] := pinochle_meld_value(0) }\n"
        "  winner: highest score\n"
        "}\n"
    )
    message = _refused(source)
    assert "hand" in message
    assert "zone" in message and "state" in message


# --- axis 16/17: a call that resolves to a DESIGNER function is not native --
#
# A declared game may define a function named after a Primitive absent from its
# namespace. Every guard keyed on the name against a corpus-wide native
# registry would then fire on a call the runtime dispatches to the user
# function. The axis is those registries, crossed with the legacy Primitive
# set: a nonempty intersection is a registry whose names a designer function
# can now legally take.


def _collidable_native_registries() -> dict[str, frozenset[str]]:
    """Native name registries whose members a designer function may now take,
    DERIVED — each registry intersected with the legacy Primitive set, since a
    Builtin's name is still refused to a designer function in every regime."""
    from cardlang.builtins.functions import (
        ARRIVAL_RECORD_CALLS,
        BOARD_ONLY_CALL_FUNCS,
        DECK_ONLY_CALL_FUNCS,
    )
    from cardlang.typecheck import RANKING_GATED_FUNCS

    candidates = {
        "DECK_ONLY_CALL_FUNCS": DECK_ONLY_CALL_FUNCS,
        "RANKING_GATED_FUNCS": RANKING_GATED_FUNCS,
        "BOARD_ONLY_CALL_FUNCS": BOARD_ONLY_CALL_FUNCS,
        "ARRIVAL_RECORD_CALLS": frozenset(ARRIVAL_RECORD_CALLS),
        # The Trick Order row check refuses every CALL_FUNCS member outside its
        # own allow-list, so its collidable set is the whole Primitive half.
        "TRICK_ORDER_ROW_CALLS": PRIMITIVE_CALL_FUNCS,
    }
    return {k: v & PRIMITIVE_CALL_FUNCS for k, v in candidates.items()}


def test_the_collidable_registry_axis_is_derived() -> None:
    """Anti-vacuity, and the boundary stated: exactly the registries with a
    nonempty intersection need a designer-function cell, and the empty ones are
    empty because they hold Builtin names only — which a designer function may
    not take under any regime.

    red under: add a Primitive's name to `BOARD_ONLY_CALL_FUNCS`."""
    collidable = _collidable_native_registries()
    nonempty = {k for k, v in collidable.items() if v}
    assert nonempty == {
        "DECK_ONLY_CALL_FUNCS",
        "RANKING_GATED_FUNCS",
        "TRICK_ORDER_ROW_CALLS",
    }, sorted(nonempty)


def test_a_designer_function_named_after_an_absent_primitive_escapes_the_flavor_guard() -> None:
    """DECK_ONLY: a piece game's designer function whose spelling reads a
    card's rank in the legacy registry, but which the runtime dispatches to the
    user function.

    Checked rather than played, like its ranking-gate sibling: the guard under
    test is a compile-stage one, and the playout that proves a designer
    function of a shadowing name actually RUNS is
    `test_a_declared_game_may_define_a_function_named_after_a_walled_primitive`,
    which plays a card game where the driver has a deck to open."""
    name = min(_collidable_native_registries()["DECK_ONLY_CALL_FUNCS"])
    source = (
        f"function {name}() = true\n"
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  pieces: xo_marks\n"
        "  primitives { }\n"
        "  zones { supply : Discard }\n"
        "  state { score[player] : Integer = 0 }\n"
        f"  phase play {{ score[0] := if {name}() then 1 else 0 }}\n"
        "  winner: highest score\n"
        "}\n"
    )
    assert declared_names(_checks(source)) == frozenset()


def test_a_designer_function_named_after_an_absent_primitive_escapes_the_ranking_gate() -> None:
    """RANKING_GATED: the same shape at the type layer, in a game with no
    `ranking:` — the gate reads the name against a registry, and the name is
    the user's."""
    name = min(_collidable_native_registries()["RANKING_GATED_FUNCS"])
    source = (
        f"function {name}(p : Player) = 1\n"
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  primitives { }\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        f"  phase play {{ score[0] := {name}(0) }}\n"
        "  winner: highest score\n"
        "}\n"
    )
    assert declared_names(_checks(source)) == frozenset()


def test_a_designer_function_named_after_an_absent_primitive_may_be_called_from_a_row() -> None:
    """TRICK_ORDER_ROW: a row calls the card and public state only, and a
    designer function is neither native nor a Primitive — the original arm
    already meant to let one through, using `not in CALL_FUNCS` as the proxy,
    which a shadowing spelling defeats."""
    source = (
        "function tichu_dragon_won(c : Card) = true\n"
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  primitives { }\n"
        "  trick_order { trump: tichu_dragon_won(card) }\n"
        "  zones { deck : Deck  hand[player] : Hand<player>"
        "  trick_pile : TrickPile }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase play {\n"
        "    move all cards from deck as-equally-as-possible to each hand\n"
        "    let w = highest_by_trick_order(trick_pile)\n"
        "    score[0] := 1\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
    )
    assert declared_names(_checks(source)) == frozenset()


def test_a_legacy_game_still_meets_every_native_guard() -> None:
    """The control for all three above: without a block the Primitive IS in the
    namespace, the shadow guard refuses the designer function outright, and no
    native guard is skipped. A fix that stopped applying them to legacy games
    would trade one silent dispatch for another."""
    name = min(_collidable_native_registries()["DECK_ONLY_CALL_FUNCS"])
    source = (
        f"function {name}() = true\n"
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  pieces: xo_marks\n"
        "  zones { supply : Discard }\n"
        "  state { score[player] : Integer = 0 }\n"
        f"  phase play {{ score[0] := if {name}() then 1 else 0 }}\n"
        "  winner: highest score\n"
        "}\n"
    )
    assert "shadows" in _refused(source)


# --- axis 12: the namespace walls -------------------------------------------


@pytest.mark.parametrize(
    "name",
    sorted({next(iter(sorted(names))) for names in WALLED_NAMESPACES.values() if names}),
)
def test_a_walled_namespace_name_cannot_be_declared(name: str) -> None:
    """The block covers the CALL-position namespace only. A round-slot name
    written in it is refused by NAME — not as an unknown Primitive, which it is
    not — with the label of the namespace it belongs to."""
    entry = f"{name}() : Integer"
    message = _refused(_game(block=entry, body="    score[0] := 1"))
    assert name in message
    assert "#142" in message


# --- axis 13/17: regime attribution and collisions --------------------------


def test_a_declared_game_cannot_reach_another_games_primitive() -> None:
    """Issue #364's class: with a block, a neighbour's Primitive is not in this
    game's namespace, so the call is an unknown name."""
    message = _refused(
        _game(body="    score[0] := if tichu_dragon_won() then 1 else 0")
    )
    assert "tichu_dragon_won" in message


def test_a_declaration_may_not_shadow_a_builtin() -> None:
    message = _refused(_game(block="team_of(p : Player) : Team", body="    score[0] := 1"))
    assert "team_of" in message


def test_a_duplicate_entry_is_refused() -> None:
    entry = _PINOCHLE_ENTRY + "  " + _PINOCHLE_ENTRY
    message = _refused(_game(block=entry, body=_SCORE_FROM_PRIMITIVE))
    assert "pinochle_meld_value" in message


def test_a_declaration_may_not_shadow_a_game_function() -> None:
    """A `function` is a top-level definition the game holds, so a Primitive of
    the same name would make one call name two things."""
    source = "function probe_fn(p : Player) = 0\n" + _game(
        block="probe_fn(p : Player) : Integer", body="    score[0] := 1"
    )
    message = _refused(source)
    assert "probe_fn" in message


def test_an_unimplemented_declaration_is_a_compile_diagnostic() -> None:
    """The declared-but-unimplemented half of the both-ways check, in the
    compile stage's own channel: `check_dsl` must not report clean on a game
    nothing can run."""
    message = _refused(_game(block="no_such_primitive() : Integer", body="    score[0] := 1"))
    assert "no_such_primitive" in message


@pytest.mark.parametrize(
    "name",
    sorted(
        {
            name
            for name, impl in PRIMITIVE_IMPLEMENTATIONS.items()
            if impl.contract not in DECLARABLE_CONTRACTS
        }
    ),
)
def test_an_undeclarable_contract_is_refused_by_name(name: str) -> None:
    """A Primitive whose Python does not answer the narrowed contract is
    refused where the mismatch is a compile-time fact — between a declaration
    and a signature — rather than left to fail as a `TypeError` mid-playout."""
    message = _refused(_game(block=f"{name}() : Integer", body="    score[0] := 1"))
    assert name in message


# --- axis 16/21: the value reaches the positions a Primitive is called in ----


@pytest.mark.parametrize(
    "body",
    [
        _SCORE_FROM_PRIMITIVE,
        "    if pinochle_meld_value(0) >= 0 { score[0] := 1 }",
    ],
    ids=["expression", "if-condition"],
)
def test_a_declared_primitive_is_callable(body: str) -> None:
    game = _checks(_game(body=body))
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 1, 1: 0}


# --- axis 19: the partitions that must stay total ---------------------------


def test_a_trick_order_row_cannot_call_a_declared_primitive() -> None:
    """The Trick Order's row-callable partition covers the Builtin half only,
    on the ground that a row calls no game-local Python. A declared Primitive
    is game-local Python in NO registry that partition reads, so the argument
    holds only because the name is refused on its own — not by inheriting an
    exclusion it is not in."""
    source = _game(
        block=_PINOCHLE_ENTRY,
        body="    score[0] := if follows_lead(A of spades, discard) then 1 else 0",
        extra="  trick_order { trump: pinochle_meld_value(0) > 0 }\n",
    )
    message = _refused(source)
    assert "pinochle_meld_value" in message
    assert "Trick Order row" in message


# --- axis 18: the declared signature is what freezes -------------------------


def test_the_declared_signature_is_materialized() -> None:
    """The type pass materializes the `Sig` each entry declares — the one
    exception its own contract sanctions, because the runtime's `coerce_args`
    is a downstream consumer that needs a type."""
    from cardlang.typecheck import declared_primitive_sigs
    from cardlang.types import TInteger, TPlayer

    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    sigs = declared_primitive_sigs(game)
    assert sigs["pinochle_meld_value"].params == (TPlayer(),)
    assert sigs["pinochle_meld_value"].ret == TInteger()


def test_the_freeze_follows_the_declaration_not_the_registry() -> None:
    """The table the runtime FREEZES against, observed.

    Every name declarable in 3a is also in `CALL_SIGS` with the same
    signature, so the two agree on every reachable cell and the distinction
    this claims is unobservable as things stand. Made observable by planting a
    DIFFERENT signature in `CALL_SIGS` for the declared name: the coercion
    must still see the declaration's. Without the plant the assertion below
    could not fail, which is what makes the plant the cell rather than
    decoration."""
    from cardlang.builtins.signatures import CALL_SIGS, Sig
    from cardlang.runtime import reads as reads_mod
    from cardlang.types import TAny, TInteger, TPlayer

    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    planted = Sig((TAny(),), TInteger())
    assert planted != CALL_SIGS["pinochle_meld_value"], "the plant changes nothing"
    seen: list[object] = []
    real = reads_mod.coerce_args

    def spy(sig: object, args: list[object]) -> object:
        seen.append(sig)
        return real(sig, args)

    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(CALL_SIGS, "pinochle_meld_value", planted)
        mp.setattr(reads_mod, "coerce_args", spy)
        play_game(game, random.Random(0))
    assert seen, "no native call was coerced — the probe reached nothing"
    assert planted not in seen, (
        "the runtime froze the declared Primitive's arguments against CALL_SIGS"
    )
    assert Sig((TPlayer(),), TInteger()) in seen
    # red under: point `native_call`'s declared branch at `CALL_SIGS.get(name)`
    # instead of `ctx.rs.declared_sigs` (demonstrated and reverted).


# --- axis 8: the binder narrows what the bundle materializes ----------------


def _bundle_for(clause: str) -> object:
    """The `GameReads` a declared Primitive receives, captured from a playout."""
    from cardlang.runtime import narrowing

    seen: list[object] = []
    real = narrowing.bind

    def spy(*args: object, **kwargs: object) -> object:
        bundle = real(*args, **kwargs)  # type: ignore[arg-type]
        seen.append(bundle.reads)
        return bundle

    game = _checks(
        _game(
            block=f"pinochle_meld_value(p : Player) : Integer reads {clause}",
            body=_SCORE_FROM_PRIMITIVE,
        )
    )
    narrowing.bind = spy  # type: ignore[assignment]
    try:
        play_game(game, random.Random(0))
    finally:
        narrowing.bind = real
    assert seen, "the Primitive was never called"
    return seen[0]


def test_a_bare_family_read_grants_the_whole_family() -> None:
    gr = _bundle_for("hand, trump_suit")
    assert set(gr.families["hand"]) == {0, 1}  # type: ignore[attr-defined]


def test_a_binder_read_narrows_to_the_instance() -> None:
    """The per-primitive granularity stage 3 buys, measured: `hand[p]` gives
    the ONE hand the call names, not the family."""
    gr = _bundle_for("hand[p], trump_suit")
    assert set(gr.families["hand"]) == {0}  # type: ignore[attr-defined]


def test_an_indexed_state_read_narrows_to_the_instance() -> None:
    """The binder narrows a state variable exactly as it narrows a family: the
    two kinds materialize differently, so the arm needs its own cell."""
    gr = _bundle_for("hand[p], trump_suit, seen[p]")
    assert set(gr.state["seen"]) == {0}  # type: ignore[attr-defined]


def test_an_undeclared_name_is_absent_from_the_bundle() -> None:
    gr = _bundle_for("hand[p], trump_suit")
    assert "discard" not in gr.singles  # type: ignore[attr-defined]
    assert "seen" not in gr.state  # type: ignore[attr-defined]


def test_a_key_the_live_value_does_not_hold_is_refused() -> None:
    """A narrowing that found no instance would hand the implementation an
    EMPTY family, which reads exactly like a family with no members — the
    silent-wrong-answer shape the accessors exist to prevent."""
    from cardlang.runtime import reads as reads_mod

    rs, row = _live_state_and_row()
    with pytest.raises(reads_mod.PrimitiveReadError, match="does not hold"):
        reads_mod.game_reads(rs, row, {"hand": 7})


def test_a_key_naming_an_undeclared_read_is_refused() -> None:
    """A key narrows a name the ROW declares; one it omits is a narrowing of
    nothing, and silently ignoring it would let a binder point anywhere."""
    from cardlang.runtime import reads as reads_mod

    rs, row = _live_state_and_row()
    with pytest.raises(reads_mod.PrimitiveReadError, match="indexed read"):
        reads_mod.game_reads(rs, row, {"discard": 0})


def _live_state_and_row() -> tuple[RuntimeState, PrimitiveReads]:
    """A live two-seat world and a declared row over it — built directly, so
    the refusals above are probed at the accessor rather than through a game
    that resolve would refuse before the runtime ever ran."""
    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    rs = RuntimeState(Seating(2), ZoneStore(game.zones, (0, 1)), random.Random(0))
    row = PrimitiveReads(
        module="cardlang/runtime/pinochle.py",
        game_file="probe.cardlang",
        zone_families=frozenset({"hand"}),
    )
    return rs, row


# --- axis 13/15: the corpus reconciliation pin ------------------------------
#
# The coexistence window is a live DUAL-DEFINITION-SITE domain: a game's
# Primitive coupling can be stated in its own `primitives { }` block or in the
# authored `PRIMITIVE_READS` registry, and two statements of one fact drift.
# The pin below is what keeps the window checked rather than merely scheduled.

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT_DIR / "docs" / "games"
WITNESS = pathlib.Path(__file__).resolve().parent / "fixtures" / "primitives_witness.cardlang"


def game_sources() -> list[pathlib.Path]:
    """Every game whose declarations couple to the package tables: the corpus
    glob, the witness fixture, and the experiment games that declare a block.

    The fixture is IN the domain deliberately — no corpus game declares a
    block, so without it the declared arm of every check below would be empty
    and green by having nothing to look at. Salvo is in for the other
    direction: it declares the only Primitive no corpus game reaches, and a
    package registration nothing in this domain declares is refused below as an
    orphan. The experiment games are named one by one rather than globbed:
    Salvo's mini and its zc variant declare nothing, and a glob would quantify
    over every future experiment file whether or not it is a game."""
    return sorted(GAMES_DIR.glob("*.cardlang")) + [
        WITNESS,
        ROOT_DIR / "experiments" / "salvo" / "salvo.cardlang",
    ]


@functools.cache
def _checked_games() -> tuple[tuple[str, n.Game], ...]:
    """(game-file basename, checked game) for every source, through the
    pipeline's own entry point — so a block written in a `.md` game reaches
    this pin by the same extraction the runtime uses."""
    return tuple((p.name, check_source(p)) for p in game_sources())


def _reconcile(
    games: tuple[tuple[str, n.Game], ...],
    implementations: dict[str, Implementation],
) -> None:
    """The pin's body, over supplied tables so the mutations below can plant.

    Three claims, in both directions between the three independently authored
    sides — each game's block, the implementation index, and the authored
    `PRIMITIVE_READS` registry."""
    declared: dict[str, str] = {}
    reached: set[str] = set()
    for name, game in games:
        for primitive in sorted(declared_names(game)):
            declared[primitive] = name
        reached |= declared_names(game)
        if regime(game) is Regime.LEGACY:
            # A legacy game reaches every Primitive it CALLS. Reading the calls
            # rather than the namespace is what makes the orphan question
            # answerable: the namespace is corpus-wide, so quantifying over it
            # would claim every implementation is reached by every game.
            reached |= {
                nd.func
                for nd in _walk_calls(game)
                if nd.func in PRIMITIVE_CALL_FUNCS
            }

    # (1) declared -> implemented. resolve refuses this per game; the pin says
    # it over the whole corpus, so a game the pipeline never checks cannot
    # carry a declaration nothing implements.
    orphan_declarations = sorted(set(declared) - set(implementations))
    assert not orphan_declarations, (
        f"declared with no implementation: {orphan_declarations}"
    )

    # (2) implemented -> reached. An index row no game declares and no game
    # calls is an orphan: Python the corpus cannot run.
    orphans = sorted(set(implementations) - reached)
    assert not orphans, (
        f"implementations no game reaches: {orphans} — a Primitive nothing "
        f"declares and nothing calls is dead Python in the language package"
    )

    # (3) one definition site per game. A game whose block declares its
    # Primitives must not ALSO have authored `PRIMITIVE_READS` rows: the same
    # coupling stated twice is the dual-definition-site state the coexistence
    # window is priced to keep impossible.
    with_rows = {row.game_file for row in PRIMITIVE_READS}
    both = sorted(
        {name for name, game in games if regime(game) is Regime.DECLARED} & with_rows
    )
    assert not both, (
        f"games stating their Primitive reads twice: {both} — a `primitives "
        f"{{ }}` block and a PRIMITIVE_READS row declare the same coupling, "
        f"and two statements of one fact drift"
    )


def _walk_calls(game: n.Game) -> list[n.Call]:
    from cardlang.resolve import _walk

    return [nd for nd in _walk(game) if isinstance(nd, n.Call)]


@pytest.mark.slow
def test_the_corpus_reconciles_in_every_direction() -> None:
    """Derived from the games glob THROUGH the pipeline, so a game added to the
    corpus is covered with nothing to keep in sync."""
    games = _checked_games()
    assert len(games) > 20, "the corpus glob came up short — wrong path, not a clean corpus"
    assert any(regime(g) is Regime.DECLARED for _, g in games), (
        "no game in the pin's domain declares a block — the declared arm would "
        "be green by having nothing to look at"
    )
    _reconcile(games, dict(PRIMITIVE_IMPLEMENTATIONS))


@pytest.mark.slow
def test_reconciliation_reddens_on_a_planted_orphan() -> None:
    """An implementation nothing reaches. Demonstrated rather than asserted:
    a pin whose author cannot name a reddening edit is the vacuously-green
    defect wearing a test's name."""
    planted = dict(PRIMITIVE_IMPLEMENTATIONS)
    planted["orphan_primitive"] = Implementation(
        "cardlang.runtime.pinochle", "pinochle_meld_value", InvocationContract.BUNDLED
    )
    with pytest.raises(AssertionError, match="orphan_primitive"):
        _reconcile(_checked_games(), planted)


@pytest.mark.slow
def test_reconciliation_reddens_on_a_dual_definition_site() -> None:
    """A game declaring a block while its authored `PRIMITIVE_READS` rows still
    stand — the exact state 3b removes, planted here so the window is checked
    while it is open."""
    dual = _checked_games() + ((
        "pinochle.cardlang",
        check_source(WITNESS),
    ),)
    with pytest.raises(AssertionError, match="pinochle.cardlang"):
        _reconcile(dual, dict(PRIMITIVE_IMPLEMENTATIONS))


# --- the witness fixture, played --------------------------------------------


def test_the_witness_fixture_plays() -> None:
    """A complete game that declares a Primitive, calls it, and reaches a
    result — the one cell in this module where the whole path runs rather than
    being checked. `Collection.does not prove` names why it has to exist: only
    a playout can show a declared read SUFFICES for its implementation."""
    game = check_source(WITNESS)
    assert declared_names(game) == {"pinochle_meld_value"}
    winners = set()
    for seed in range(8):
        result = play_game(game, random.Random(seed))
        assert set(result.scores) == {0, 1}
        assert all(v >= 0 for v in result.scores.values())
        winners.add(result.winner)
    # Both seats win on some seed: a fixture whose result never moved would
    # pass on an implementation that returned a constant.
    assert winners == {0, 1}


# --- axis 25: the game-file input form --------------------------------------


def test_both_game_file_forms_reach_the_same_declarations() -> None:
    """The derivation reads the pipeline's own extraction path, so a block in a
    fenced Markdown game and the same block in a `.cardlang` produce identical
    declarations rather than the Markdown half being silently unread."""
    from cardlang.pipeline import check_markdown

    source = _game(body=_SCORE_FROM_PRIMITIVE)
    fenced = "# Probe\n\n```\n" + source + "```\n"
    assert declared_names(check_markdown(fenced, "probe.md")) == declared_names(
        _checks(source)
    )


# --- axis 26: the censuses --------------------------------------------------


def test_the_new_module_is_a_census_row() -> None:
    """The registry census's derivation query names every module that consults
    a native registry; this module's own registry belongs to it."""
    import pathlib
    import subprocess

    root = pathlib.Path(__file__).resolve().parent.parent
    out = subprocess.run(
        [
            "grep", "-rln", "--include=*.py", "-E",
            "CALL_FUNCS|CALL_SIGS|PRIMITIVE_READS|VALUE_NAMES|PRIMITIVE_IMPLEMENTATIONS",
            "cardlang", "tests",
        ],
        cwd=root, capture_output=True, text=True,
    )
    hits = set(out.stdout.split())
    assert "cardlang/primitives_block.py" in hits
    assert "tests/test_primitives_block.py" in hits


def test_the_grid_is_not_empty() -> None:
    """Anti-vacuity: the parametrized axes above are derived from registries,
    and a registry read wrong would silently shrink them to nothing."""
    assert len(DECLARABLE_BUILTIN_TYPE_NAMES) > 5
    assert len(PRIMITIVE_IMPLEMENTATIONS) > 20
    assert len(WALLED_NAMESPACES) == 5
    assert dataclasses.fields(n.PrimitiveDecl)
