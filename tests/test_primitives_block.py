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
            instance the declaration has none of; and a `reads` name denotes
            exactly ONE declaration — the game's own state, or a phase's when
            the read carries that phase's name as its `in <phase>` tail, whose
            grid and containment rule are tests/test_phase_scoped_reads.py's;
            a BARE name is game-scoped, because the row is materialized on
            every call while the runtime resolves the innermost frame; and it
            belongs to at most one of the four namespaces a keyed name can be
            declared in (the game's `state { }`, a phase's, an indexed
            `zones { }` declaration, an unindexed one), so a name in two of
            them is refused rather than classified by whichever the classifier
            consults first; and (5) a call that resolves to a designer
            function is not a native call, so no registry keyed by native
            NAME answers about it.
domain:     the block's own surface — clause placement x {game, library},
            entry cardinality x {absent, empty, one, many, second block},
            arity x {0, 1, many}, declared type name x {parameter, return}
            over `primitives_block.declarable_type_names` and its explicitly
            listed complement, reads-name kind x binder x
            {state variable, indexed state variable, zone family, single
            zone, unknown} — crossed with the REGIME axis (declared /
            legacy) wherever a cell's outcome differs between them, and with
            the six Primitive namespaces of `cardlang/builtins/functions.py`.
            A `reads` name's MEMBERSHIP across the four namespaces a keyed
            declaration can live in is crossed whole: the powerset of {the
            game's `state { }`, a phase's, an indexed `zones { }`
            declaration, an unindexed one}, one commanded cell per vector.
            Pairwise membership settles the whole product, and the argument
            is OWNERSHIP, not bare intersection: every vector carrying
            game-state membership is refused by `ambiguous_read_names` or
            `shadowed_state_names` (raw intersections a third membership
            never shrinks), and the one game-state-free pair is refused by
            `phase_state_zone_names`, whose game-level subtraction can only
            hand a name TO those two arms, never to acceptance — so a
            refusal is monotone in the vector and the three- and four-way
            cells command "at least one arm speaks" rather than a particular
            one. The within-namespace repeats are the same product's
            self-pairs and their Owner is `_check_duplicate_names`, cited by
            a cell per namespace rather than re-covered: shadowing ACROSS
            levels is settled-legal, so the refusal class is reads-clause
            level and no wider. A family library reaches the product through
            provided state alone — it holds no `zones` clause, and every
            collision between a provided name and a game's own declaration is
            refused upstream by `_apply_uses` — so the library cells command
            the splice (a provided name classifies as game state) and cite
            that Owner for the rest; that a block READING a provided name has
            no playing witness is issue #496. The product is over a `reads`
            name; an ENTRY name colliding with a keyed declaration is the
            other direction and its outcome is undecided (issue #497), so it
            is not a cell here.
            The regime axis is crossed once in full: `PRIMITIVE_CALL_FUNCS`
            — a declaration is the only route to any of them — x {block
            declares it, block omits it, no block}, total over that registry.
            Both directions of the partition are cells of that product: a
            declared game reaching a Primitive it did not declare, and an
            undeclared game reaching one at all.
            The CONTRACT axis is the enum WHOLE: a block declares every
            member, so its cross with the reads-clause shape is total over
            `InvocationContract` rather than over an allow-list stated beside
            it. There is no cell for a member a block may not declare, and
            none for a member the dispatch does not handle: each consumer
            matches the enum structurally and closes with
            `typing.assert_never`, so an added member is a `mypy --strict`
            error at every dispatch site (decisions.md, "Closed-domain
            completeness" — enforcement follows the domain's visibility to
            the type checker, and a pin whose fact could have been a type is
            built on the wrong rung). The registry-side half of the same
            completeness, which the type checker cannot state, is
            `test_every_invocation_contract_has_a_member`.
            Deliberately OUTSIDE it: the five namespaces the block does not
            cover have exactly one cell each here (the block cannot name
            them), because their declaration slots are epic #142's stage-4
            scope. The corpus is IN, through the reconciliation pin's own
            games glob: every declaring game is a member of its declared arm,
            which `test_the_corpus_reconciles_in_every_direction` asserts
            non-empty rather than trusting the glob to have found one, and
            which the witness fixture holds up whatever the corpus has
            migrated — `test_reconciliation_reddens_on_a_planted_orphan` and
            the three row-grain plants beside it are what keep the pin from
            being vacuous. That pin's own domain is the ROWS table it is
            handed crossed with the declared games, and its exemption is the
            rows a walled binder binds — the climb binder's answers over the
            two climb registries, plus the shared dispatch module's rows under
            an assert that no call implementation names that module.
            The COLLECTION SPELLING is crossed on four axes of its own, one
            per layer that owns a refusal. The spelling family x the entry's
            two slots (`_COLLECTION_SPELLINGS` x `_COLLECTION_SLOTS`) is the
            surface's decision table, which no registry can state; the ELEMENT
            axis is derived, every name a bare slot spells crossed with the
            collection form against `COLLECTION_ELEMENT_NAMES`, and that list
            is held equal to the elements registered Python actually takes
            (`implementation_sig` over `PRIMITIVE_IMPLEMENTATIONS`) so a second
            element is an event in both directions; the ADJACENCY cells are the
            boundary tokens a closing `>` can sit against — including the one
            slot where a `=` follows the bracket directly, whose `>=` fusion is
            MEASURED rather than asserted, so the cell cannot pass on a stream
            with nothing to fuse — and the two halves of the zone
            confusion (an element type where a zone's index domain belongs,
            and the constructor word where a zone type belongs — both refused
            by the zone registry, cited as Owner and asserted on the MESSAGE
            because the word is spelled); and the CALL position is crossed
            with the value shapes a collection parameter accepts. The
            spelling's decomposition is held to one site by a scrape over the
            BRACKET alone — the trailing `?` is sliced elsewhere in the
            package, found by that scrape run over `"?"` instead of the
            bracket, and none of those readers reads a `primitives { }` entry
            spelling, so the class is uniform and correct and is named rather
            than swept.
            A declared Primitive IS a `where jointly` predicate: the position
            takes a collection parameter, the subset codec is keyed by the
            call's root name under either regime, and the cell is a synthetic
            declared game that builds its action space and plays, beside the
            corpus proof gin-rummy carries.
            Two boundaries the domain has by construction rather than by
            omission. The walled-namespace cells sample one member per
            namespace, and `PRIMITIVE_TRICK_WINNERS` is EMPTY — deliberately,
            as the registry's own comment records — so four of the five walls
            carry a cell and the fifth is unreachable until a game files a
            game-local trick winner there. And a collection RETURN is
            reachable at the TYPE-NAME gate and unusable in a concrete entry,
            exactly as `TCell` is: no registered implementation returns one, so
            the shape check refuses every such declaration, and the cell
            quantifies over the whole implementation index so the day one
            returns a collection its witness is owed here. The two guards
            answer different questions and the grid runs the gate's.
registry:   `cardlang/builtins/functions.py` (the six Primitive namespaces
            and `BUILTIN_CALL_FUNCS`);
            `cardlang/primitives_block.py`
            (`PRIMITIVE_IMPLEMENTATIONS`, `WALLED_NAMESPACES`,
            `DECLARABLE_BUILTIN_TYPE_NAMES`, `COLLECTION_ELEMENT_NAMES`,
            `COLLECTION_TYPE_CONSTRUCTOR`, `UNDECLARABLE_TYPE_CONSTRUCTORS`,
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
            one place that runs. And a declarable name's entry states the SAME
            signature its implementation row does — the shape check refuses a
            game where they differ — so no cell here distinguishes the two by
            the values they carry: the freeze cell plants a divergence to
            observe which of them the runtime reads.
            And the reconciliation pin's exemption is only as right as the
            climb binder it asks: `primitives.climb_row` is a consumer of the
            rows, not the artifact being judged, so a green here says a
            declared game keeps exactly the rows THAT BINDER names — a binder
            answering with the wrong row reshapes the exemption without
            reddening anything in this module, and the climb machinery's own
            tests are what hold that fault.

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

Red a sixth time, at `1 failed, 5 passed` over the regime product's own six
cells (`-k regime_product`, 2026-08-29), on the one direction of the
partition nothing refused: a Primitive whose only route to Python is a
declaration, called from a game that writes no block. The product was rowed
whole before the fix, so the five cells that already held are cells rather
than absences.

Red a seventh time, at `84 failed, 1341 passed` across the six modules the
collection spelling's grid spans (this one, `test_type_name_positions.py`,
`test_rejections.py`, `test_family_libraries.py`, `test_grammar_ambiguity.py`,
`test_positions.py`; the bare run, 2026-09-03), authored before the grammar
could spell any of it.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import importlib
import inspect
import pathlib
import random
import sys
import typing

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    CALL_FUNCS,
    PRIMITIVE_CALL_FUNCS,
)
from cardlang.builtins.signatures import CALL_SIGS, Sig
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.primitives_block import (
    COLLECTION_ELEMENT_NAMES,
    DECLARABLE_BUILTIN_TYPE_NAMES,
    PRIMITIVE_IMPLEMENTATIONS,
    UNDECLARABLE_TYPE_CONSTRUCTORS,
    Implementation,
    InvocationContract,
    Regime,
    WALLED_NAMESPACES,
    call_namespace,
    declared_names,
    implementation_sig,
    regime,
    walled_namespace_of,
)
from cardlang.runtime.driver import play_game
from cardlang.runtime.reads import PRIMITIVE_READS, PrimitiveReads
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Seating
from cardlang.types import TCollection, TEnum, TInteger, TOptional, TPlayer, Type

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


def test_the_index_is_where_a_primitive_signature_is_stated() -> None:
    """The row carries the shape as well as the location, and it is the only
    table that does.

    `implementation_sig` is the seam every consumer reads a Primitive's
    signature through, and this says what it reads: the row's own authored
    column, never the Builtins' table. The second assertion is what keeps the
    first from being a statement about one of two agreeing copies — a name
    keyed in both would let a consumer take either and read as correct.

    red under: key any registered Primitive in `CALL_SIGS`, or return
    `CALL_SIGS.get(name)` from `implementation_sig`."""
    from cardlang.builtins.signatures import CALL_SIGS

    for name, impl in PRIMITIVE_IMPLEMENTATIONS.items():
        assert implementation_sig(name) is impl.sig, (
            f"{name}'s signature does not come from its index row"
        )
    assert set(CALL_SIGS).isdisjoint(PRIMITIVE_IMPLEMENTATIONS), (
        f"Primitives keyed in the Builtins' signature table: "
        f"{sorted(set(CALL_SIGS) & set(PRIMITIVE_IMPLEMENTATIONS))}"
    )


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
    make. This is the registry-side half of the enum's completeness; the
    dispatch-side half is the type checker's, since every consumer matches
    the enum structurally and closes with `assert_never`.

    red under: add an arm to `InvocationContract` with no row using it."""
    used = {impl.contract for impl in PRIMITIVE_IMPLEMENTATIONS.values()}
    assert used == set(InvocationContract)


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

    Reachability is derived through the block's whole SPELLABLE set, not its
    bare names: a conversion run over names alone cannot see a constructor a
    spelling wraps, which is how `TCollection` sat in the exclusion table while
    the surface was about to reach it.

    red under: add a member to `cardlang.types.Type`; or put `TCollection` back
    in `UNDECLARABLE_TYPE_CONSTRUCTORS`, which the overlap assertion catches."""
    all_constructors = {t.__name__ for t in typing.get_args(Type)}
    unreachable = set(UNDECLARABLE_TYPE_CONSTRUCTORS)
    reachable = _reachable_type_constructors()
    assert not (reachable & unreachable), sorted(reachable & unreachable)
    assert reachable | unreachable == all_constructors, sorted(
        all_constructors - reachable - unreachable
    )


def _spellable_types(names: frozenset[str]) -> list[str]:
    """Every type spelling an entry slot admits over `names` — the bare form,
    the `?` form, and the collection form for each admitted element.

    The block's WHOLE spellable set, so reachability is derived from what a
    designer can write rather than from the bare names the conversion site
    happens to take. A second element admitted to `COLLECTION_ELEMENT_NAMES`
    lands here as a new spelling without anyone editing this function."""
    from cardlang.primitives_block import COLLECTION_TYPE_CONSTRUCTOR

    bare = sorted(names)
    return (
        bare
        + [f"{name}?" for name in bare]
        + [
            f"{COLLECTION_TYPE_CONSTRUCTOR}<{element}>"
            for element in sorted(COLLECTION_ELEMENT_NAMES)
        ]
    )


def _constructors_of(t: Type) -> set[str]:
    """Every constructor in a Type, at every depth — the collection's element
    and the optional's inner included, so a nested one cannot hide."""
    out = {type(t).__name__}
    for part in (getattr(t, "inner", None), getattr(t, "element", None)):
        if part is not None:
            out |= _constructors_of(part)
    return out


def _reachable_type_constructors() -> set[str]:
    """Which `Type` constructors a declared spelling can produce, DERIVED by
    running the block's whole spellable set through the site
    `declared_primitive_sigs` itself uses (`typecheck._param_type`, and the one
    conversion site beneath it)."""
    from cardlang.typecheck import TypeEnv, _param_type

    out: set[str] = set()
    probe = _checks(_game(block="", body=""))
    names = DECLARABLE_BUILTIN_TYPE_NAMES | {p.name for p in probe.positions}
    env = TypeEnv()
    for spelling in _spellable_types(names):
        out |= _constructors_of(
            _param_type(n.Parameter(name="x", type_name=spelling), env)
        )
    # A board game's `cell` domain is the one declarable name outside the
    # built-ins whose member type is not `TInteger`; probed on its own game
    # rather than by hand-adding `TCell`, so the reachability is measured.
    board = _checks(_board_game())
    from cardlang.typecheck import _position_types

    board_env = TypeEnv(positions=_position_types(board))
    for spelling in _spellable_types(frozenset(board_env.positions)):
        out |= _constructors_of(
            _param_type(n.Parameter(name="x", type_name=spelling), board_env)
        )
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


# The Primitive every cell needing one name is written at, DERIVED from the
# registry rather than written down: a literal is a name this module would have
# to keep registered on its own account, and a migration that retires it would
# leave the prose false with nothing saying so. Its rendering comes from the
# implementation index's own signature column through `_entry_and_body`, so
# the name's own signature decides the sentence.
def _representative() -> str:
    return min(PRIMITIVE_CALL_FUNCS)


def test_an_empty_block_refuses_a_primitive_call() -> None:
    name = _representative()
    _, body = _entry_and_body(name)
    message = _refused(_game(block="", body=body))
    assert name in message
    assert "primitives" in message


# --- axis 1 x the Primitive's own home: the regime product ------------------
#
# A declaration is the only route to a Primitive's Python — no runtime module
# holds a `call` arm for one — so the home axis has a single value and the
# registry it keys is `PRIMITIVE_CALL_FUNCS`. Crossed with the regime — a
# block that declares the name, a block that does not, no block at all — each
# cell's outcome is stated once here rather than in three places.

# LEAF `Type` -> (its declarable spelling, an EXPRESSION of that type). A
# representative's signature is read from the implementation index's own
# column and rendered through this table, so the product is TOTAL over
# `PRIMITIVE_CALL_FUNCS` rather than sampled at whichever member it holds — a
# member whose signature reaches a type with no row fails by NAME rather than
# producing a sentence the parser rejects for the wrong reason.
#
# An expression, not a literal: the surface has no Card literal, so `Card`'s
# column is a Builtin over a zone the probe game declares, and `Team`'s is a
# Builtin over a seat, because the probe game declares no `teams:` and a team
# literal there names a team it does not have (the empty-domain range refusal
# `tests/test_player_literal_range.py` pins). Both are what a rendered argument
# in that position can be. The rendered sentences are
# CHECKED, never played — `_entry_and_body` writes no `reads` clause, so a
# played bundle would miss the entry's own reads — and the column is chosen to
# type where it is written, not to survive a playout.
#
# `TEnum` is keyed by the enum's own name, not the constructor's: `Suit` and
# `Rank` are two spellings and two literals behind one Python class. The
# COMBINATOR over these leaves — `?` — is structural in `_spelling_of` rather
# than a row here, because it composes with every leaf and a row per
# combination would be the product written out by hand.
_SPELLINGS: dict[str, tuple[str, str]] = {
    "TPlayer": ("Player", "0"),
    "TTeam": ("Team", "team_of(0)"),
    "TInteger": ("Integer", "0"),
    "TBoolean": ("Boolean", "true"),
    "TString": ("String", '"x"'),
    "TCard": ("Card", "top_of(hand[0])"),
    "Suit": ("Suit", "spades"),
    "Rank": ("Rank", "A"),
}

# The `score[0] := …` shape each return spelling lands in, so a rendered call
# sits in a position that types. A PLAYER return lands through a comparison and
# an OPTIONAL one through `is none`, rather than through an assignment target of
# its own type: every shape then ends in the one slot whose value decides the
# probe game's winner, so a cell cannot pass by assigning somewhere nothing
# reads.
_ASSIGNMENTS: dict[str, str] = {
    "Integer": "    score[0] := {call}",
    "Boolean": "    score[0] := if {call} then 1 else 0",
    "Player": "    score[0] := if {call} is 0 then 1 else 0",
    "Player?": "    score[0] := if {call} is none then 0 else 1",
}


def _spelling_of(t: Type) -> tuple[str, str]:
    if isinstance(t, TOptional):
        # `none` inhabits every optional, so the literal is the combinator's
        # own; the inner leaf still has to render, which is what keeps an
        # unknown leaf loud behind a `?`.
        return f"{_spelling_of(t.inner)[0]}?", "none"
    if isinstance(t, TCollection):
        # Structural like `?`, for the same reason: the element leaf still has
        # to render. The column is a ZONE — the zone facet is not part of
        # assignability, so `hand[0]` is what a collection parameter can be
        # handed where the probe game stands, and it holds cards.
        element, _ = _spelling_of(t.element)
        assert element in COLLECTION_ELEMENT_NAMES, (
            f"a Primitive's signature takes a collection of {element}, which "
            f"the block cannot spell — the element registry and this renderer "
            f"disagree"
        )
        return f"Collection<{element}>", "hand[0]"
    key = t.name if isinstance(t, TEnum) else type(t).__name__
    row = _SPELLINGS.get(key)
    assert row is not None, (
        f"no spelling for {key}: a Primitive's signature reaches "
        f"a type this product cannot render — add its row above"
    )
    return row


def _entry_and_body(name: str) -> tuple[str, str]:
    """One Primitive as a `primitives { }` entry and as a call in a body, both
    rendered from the index's own signature column — the shape its
    implementation states, so the entry cannot disagree with the shape check by
    construction."""
    sig = implementation_sig(name)
    assert sig is not None, f"{name} is not a registered Primitive"
    params = ", ".join(f"a{i} : {_spelling_of(p)[0]}" for i, p in enumerate(sig.params))
    args = ", ".join(_spelling_of(p)[1] for p in sig.params)
    ret = _spelling_of(sig.ret)[0]
    assignment = _ASSIGNMENTS.get(ret)
    assert assignment is not None, f"no assignment shape for a {ret} return"
    return f"{name}({params}) : {ret}", assignment.format(call=f"{name}({args})")


# (the Primitive's home, the game's regime) -> whether the call CHECKS. The
# home axis is the registry partition; the regime axis is `Regime` crossed with
# the block's own contents, which is what `call_namespace` reads.
_REGIME_PRODUCT: dict[tuple[str, str], bool] = {
    ("declared-only", "block declares it"): True,
    ("declared-only", "block omits it"): False,
    ("declared-only", "no block"): False,
}


def _homes() -> dict[str, list[str]]:
    """The homes, as the registries state them: one, holding every member, so
    the product below covers the registry rather than sampling it."""
    return {"declared-only": sorted(PRIMITIVE_CALL_FUNCS)}


@pytest.mark.parametrize(
    "home,regime_label,name",
    [
        (home, regime_label, name)
        for (home, regime_label) in sorted(_REGIME_PRODUCT)
        for name in _homes()[home]
    ],
)
def test_the_regime_product_lands_where_the_table_says(
    home: str, regime_label: str, name: str
) -> None:
    """The product's cells, run.

    The one that was ever in doubt is (declared-only, no block): the name IS in
    `CALL_FUNCS`, so the legacy namespace admits it, and the dispatch it then
    reaches has no arm for it. A refusal here is what keeps the declared-only
    half from being a namespace a game can enter without declaring anything.

    red under: drop the declared-only arm from resolve's `_validate_refs`."""
    entry, body = _entry_and_body(name)
    block = {"block declares it": entry, "block omits it": "", "no block": None}[
        regime_label
    ]
    source = _game(block=block, body=body)
    if _REGIME_PRODUCT[(home, regime_label)]:
        assert name in call_namespace(_checks(source))
        return
    message = _refused(source)
    assert name in message, message
    assert "primitives" in message, message


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
    assert "#547" in message


def test_the_phrase_spelling_teaches_the_ruled_one() -> None:
    """A collection HAS a spelling, and the phrase form is not it.

    No declaration in this language spells a type as a phrase, and `of` already
    carries three senses in expressions — so the sentence the issue itself
    wrote, and the first thing a reader of the design note writes, earns a
    replacement naming the ruled form rather than a bare syntax error."""
    entry = "pinochle_meld_value(x : collection of Card) : Integer"
    message = _refused(_game(block=entry, body="    score[0] := 1"))
    assert "not a phrase" in message
    assert "`Collection<Card>`" in message


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
    """One registered Primitive per contract, DERIVED — so a contract added
    later arrives here as a missing key rather than a cell nobody wrote."""
    out: dict[str, str] = {}
    for name, impl in sorted(PRIMITIVE_IMPLEMENTATIONS.items()):
        out.setdefault(impl.contract.value, name)
    return out


def test_every_declarable_contract_has_a_reads_shape_cell() -> None:
    """The cross below is complete over the contract enum, which the block
    declares whole.

    red under: add an arm to `InvocationContract`."""
    assert set(_declarable_contract_names()) == {
        c.value for c in InvocationContract
    }
    assert set(_READS_SHAPE_CELLS) == {
        (c.value, shape)
        for c in InvocationContract
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


# --- axis 7: a reads name reaches phase state only by naming the phase ------


def _grammar_alternatives(nonterminal: str) -> frozenset[str]:
    """One `?nonterminal:` production's alternatives, read off the grammar."""
    import re

    grammar = (ROOT_DIR / "cardlang" / "grammar" / "cardlang.lark").read_text()
    body = re.search(rf"\{nonterminal}:(.*?)\n\n", grammar, re.S)
    assert body is not None, f"{nonterminal} is not a production of the grammar"
    return frozenset(a.strip().lstrip("| ") for a in body.group(1).split("\n"))


def test_the_shadowable_read_kinds_are_derived() -> None:
    """Which declarable read kinds a PHASE can shadow at all — the class of the
    two cells below, read off the grammar rather than remembered. A phase
    declares state and nothing else, so state is the only kind whose runtime
    resolution can differ from the declaration the classifier matched.

    red under: add another declaration block to `?phase_item` in the grammar."""
    alternatives = _grammar_alternatives("?phase_item")
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
    """A BARE `reads` name is materialized on EVERY call, so a phase-local
    variable is readable only while that phase's frame stands — and a Primitive
    called from anywhere else meets a `PrimitiveReadError` on a name its
    declaration said it had. Naming the phase on the read is what lets a
    declaration reach it (`trump_suit in setup`, the [[phase-scoped-read]],
    whose grid and containment rule are tests/test_phase_scoped_reads.py's);
    with no tail the read is game-scoped and this name is not."""
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


# --- axis 7: a reads name's MEMBERSHIP across the four name namespaces ------
#
# A `reads` clause merges into ONE flat name namespace what the game's syntax
# keeps in four: the game's own `state { }`, a phase's `state { }`, an indexed
# `zones { }` declaration, and an unindexed one. The domain is the membership
# product over those four, and the grid below is its powerset — one cell per
# vector, each commanded accept (with the kind the name classifies as) or
# refuse (with the fragment that says WHICH arm speaks).
#
# Pairwise coverage is the whole domain, by ownership: every game-state-
# carrying vector is refused by `ambiguous_read_names` or
# `shadowed_state_names` — raw intersections a third membership never
# shrinks — and the one game-state-free pair by `phase_state_zone_names`,
# whose game-level subtraction can only hand a name TO those two arms, never
# to acceptance. A refusal is never un-said by adding a declaration; the
# three- and four-way vectors are therefore commanded "at least one arm
# speaks" rather than pinned to a particular one.

_NAME_NAMESPACES = ("game_state", "phase_state", "zone_family", "single_zone")
_PROBE_NAME = "pot"


def test_the_collision_namespace_axis_is_derived() -> None:
    """The four namespaces a `reads` name can be declared in, read off the two
    registries that define them rather than remembered: the state LEVELS from
    the grammar productions that admit a `state_block`, and the two zone kinds
    from `ReadKind` itself.

    The same read settles the library cross. A family library holds no `zones`
    clause, so no library can contribute a zone to the collision domain — what
    a library reaches is provided STATE, and
    `test_library_provided_state_reaches_the_reads_clause` runs that boundary.
    The day `?library_item` admits zones, a library-contributed zone becomes
    constructible and this pin reddens rather than the gap going unnoticed.

    red under: delete `state_block` from `?phase_item`, or add a fifth zone
    kind to `ReadKind`."""
    from cardlang.primitives_block import ReadKind

    levels = {
        level
        for level, production in (
            ("game_state", "?game_item"),
            ("phase_state", "?phase_item"),
        )
        if "state_block" in _grammar_alternatives(production)
    }
    zone_kinds = {k.name.lower() for k in ReadKind if "ZONE" in k.name}
    assert levels | zone_kinds == set(_NAME_NAMESPACES), sorted(levels | zone_kinds)
    assert "zones" not in _grammar_alternatives("?library_item")


def test_the_phase_carrying_walk_agrees_with_the_engines() -> None:
    """The attribution walk is a SECOND walk over the same declarations — the
    engine-wide one (`n.state_blocks`) cannot carry the declaring phase — so
    the two are pinned equal on a game whose phases NEST, which is the shape a
    walk that only looks at `game.phases` gets wrong.

    red under: drop the `n.Phase` recursion from
    `primitives_block._phase_tree`, the ONE walk the attribution and the paths
    both derive from."""
    from cardlang.primitives_block import _phase_state_declarations

    source = (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase outer {\n"
        "    state { shallow : Integer = 0 }\n"
        "    phase inner {\n"
        "      state { deep : Integer = 0 }\n"
        "      score[0] := 1\n"
        "    }\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
    )
    game = _checks(source)
    engine = {
        sd.name
        for block in n.state_blocks(game)
        for sd in block.decls
        if block is not game.state
    }
    assert {name for _, name in _phase_state_declarations(game)} == engine
    assert engine == {"shallow", "deep"}, sorted(engine)
    assert set(_phase_state_declarations(game)) == {("outer", "shallow"), ("inner", "deep")}


_NESTING_SOURCE = (
    "game Probe {\n"
    "  players: 2\n"
    "  max_length: 1000\n"
    "  cards: standard52\n"
    "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
    "  zones { deck : Deck  hand[player] : Hand<player> }\n"
    "  state { score[player] : Integer = 0 }\n"
    "  phase top {\n"
    "    phase outer {\n"
    "      state { shallow : Integer = 0 }\n"
    "      phase inner {\n"
    "        state { deep : Integer = 0 }\n"
    "        score[0] := 1\n"
    "      }\n"
    "    }\n"
    "    phase later {\n"
    "      state { aside : Integer = 0 }\n"
    "      score[1] := 1\n"
    "    }\n"
    "  }\n"
    "  winner: highest score\n"
    "}\n"
)


def test_the_path_walk_carries_a_phase_that_declares_nothing() -> None:
    """`top` declares no state, and its path is in the table anyway.

    Ancestry is asked ABOUT phases, not about declarations: the phase a call
    sits in may declare nothing and still enclose the region, and the
    diagnostic that says "encloses" needs its path to know. A table built from
    the declaring walk alone answers nothing about such a phase, and a
    diagnostic would then have to guess.

    Born green — the walk is written over the phase tree. red under: derive
    `phase_paths` from `_phase_state_decls`'s paths instead of from
    `_phase_tree`; `top` leaves the table and this cell names it."""
    from cardlang.primitives_block import phase_paths

    paths = phase_paths(_checks(_NESTING_SOURCE))
    assert paths["top"] == ("top",)
    assert paths["outer"] == ("top", "outer")
    assert paths["inner"] == ("top", "outer", "inner")
    assert paths["later"] == ("top", "later")


@pytest.mark.parametrize(
    "phases,expected",
    [
        (frozenset(), ()),
        (frozenset({"inner"}), ("inner",)),
        (frozenset({"outer", "inner"}), ("outer", "inner")),
        (frozenset({"inner", "outer"}), ("outer", "inner")),
        (frozenset({"top", "inner"}), ("top", "inner")),
        (frozenset({"top", "outer", "inner"}), ("top", "outer", "inner")),
        (frozenset({"outer", "later"}), None),
        (frozenset({"inner", "later"}), None),
        (frozenset({"top", "outer", "later"}), None),
        (frozenset({"outer", "nowhere"}), None),
    ],
    ids=[
        "empty",
        "singleton",
        "nested-outer-first",
        "nested-inner-first",
        "skip-level",
        "three-chain",
        "siblings",
        "cousins",
        "mixed-triple",
        "not-a-phase",
    ],
)
def test_the_nesting_predicate_orders_a_chain_and_refuses_the_rest(
    phases: frozenset[str], expected: tuple[str, ...] | None
) -> None:
    """The nesting question over the phase tree: a set that lies on one
    ancestor path comes back ordered OUTER to INNER, and everything else comes
    back None.

    The order the caller wrote the tails in carries no meaning — a set has
    none — so the two spellings of one nested pair answer identically. The
    empty set and the singleton answer rather than raising: one phase is the
    degenerate chain, which is what keeps a single-phase entry and a nested one
    on the same path through the resolver."""
    from cardlang.primitives_block import phase_chain

    assert phase_chain(_checks(_NESTING_SOURCE), phases) == expected


def _collision_source(namespaces: frozenset[str], repeat: str | None = None) -> str:
    """A probe game declaring `_PROBE_NAME` in exactly `namespaces`, read by the
    block's one entry. `repeat` declares it TWICE in one namespace — the
    within-list duplicate, whose Owner Guard is `_check_duplicate_names`."""

    def times(namespace: str) -> int:
        return (1 if namespace in namespaces else 0) + (1 if repeat == namespace else 0)

    zones = "".join(
        f"  {_PROBE_NAME}[player] : Discard" for _ in range(times("zone_family"))
    ) + "".join(f"  {_PROBE_NAME} : Discard" for _ in range(times("single_zone")))
    game_state = "".join(
        f"  {_PROBE_NAME} : Integer = 0" for _ in range(times("game_state"))
    )
    phase_state = (
        "    state { "
        + "  ".join(f"{_PROBE_NAME} : Integer = 0" for _ in range(times("phase_state")))
        + " }\n"
        if times("phase_state")
        else ""
    )
    return (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  primitives { pinochle_meld_value(p : Player) : Integer"
        f" reads {_PROBE_NAME} }}\n"
        "  zones { deck : Deck  hand[player] : Hand<player>" + zones + " }\n"
        "  state { score[player] : Integer = 0" + game_state + " }\n"
        "  phase play {\n" + phase_state + "    score[0] := 1\n  }\n"
        "  winner: highest score\n"
        "}\n"
    )


# The commanded outcome per membership vector: a `ReadKind` for a vector the
# clause accepts (the kind the name classifies as), or the message fragments a
# refusal must carry. The keys are checked against the derived powerset below,
# so a fifth namespace lands as a missing cell rather than an unnoticed gap.
_COLLISION_OUTCOMES: dict[frozenset[str], str | tuple[str, ...]] = {
    frozenset(): ("neither `zones",),
    frozenset({"game_state"}): "STATE_VAR",
    frozenset({"phase_state"}): ("a PHASE declares",),
    frozenset({"zone_family"}): "ZONE_FAMILY",
    frozenset({"single_zone"}): "SINGLE_ZONE",
    frozenset({"game_state", "phase_state"}): ("game AND a phase",),
    frozenset({"game_state", "zone_family"}): ("BOTH a state variable and a zone",),
    frozenset({"game_state", "single_zone"}): ("BOTH a state variable and a zone",),
    frozenset({"phase_state", "zone_family"}): ("phase `play`", "zone"),
    frozenset({"phase_state", "single_zone"}): ("phase `play`", "zone"),
    frozenset({"zone_family", "single_zone"}): ("duplicate zone",),
    frozenset({"game_state", "phase_state", "zone_family"}): (_PROBE_NAME,),
    frozenset({"game_state", "phase_state", "single_zone"}): (_PROBE_NAME,),
    frozenset({"game_state", "zone_family", "single_zone"}): (_PROBE_NAME,),
    frozenset({"phase_state", "zone_family", "single_zone"}): (_PROBE_NAME,),
    frozenset(_NAME_NAMESPACES): (_PROBE_NAME,),
}


def _membership_vectors() -> list[frozenset[str]]:
    import itertools

    return [
        frozenset(combo)
        for size in range(len(_NAME_NAMESPACES) + 1)
        for combo in itertools.combinations(_NAME_NAMESPACES, size)
    ]


def test_the_membership_product_is_covered_whole() -> None:
    """Anti-vacuity for the grid below: its commanded outcomes are exactly the
    powerset of the derived axis, so a namespace added to `_NAME_NAMESPACES`
    doubles the cells instead of leaving half the product unspoken.

    red under: delete any key from `_COLLISION_OUTCOMES`."""
    assert set(_COLLISION_OUTCOMES) == set(_membership_vectors())


@pytest.mark.parametrize(
    "vector",
    _membership_vectors(),
    ids=lambda v: "-".join(sorted(v)) or "declared-nowhere",
)
def test_a_reads_name_declared_in_two_namespaces_is_refused(
    vector: frozenset[str],
) -> None:
    """One cell of the membership product. An accepted vector classifies as the
    commanded kind; a refused one names the probe and carries the fragment of
    the arm that owns it."""
    from cardlang.primitives_block import classify_read

    expected = _COLLISION_OUTCOMES[vector]
    source = _collision_source(vector)
    if isinstance(expected, str):
        game = _checks(source)
        kind = classify_read(game, _PROBE_NAME)
        assert kind is not None and kind.name == expected
        return
    message = _refused(source)
    assert _PROBE_NAME in message, message
    for fragment in expected:
        assert fragment in message, message


@pytest.mark.parametrize(
    "vector",
    [
        frozenset({"game_state", "zone_family"}),
        frozenset({"phase_state", "zone_family"}),
    ],
    ids=["ambiguous", "phase-state-zone"],
)
def test_a_collision_speaks_before_the_binder_arms(vector: frozenset[str]) -> None:
    """The product crossed with the BINDER, at the two vectors where a binder
    is even well-formed (the colliding name is a zone family either way). The
    collision arms run before `classify_read`, so they own a colliding name
    whether the read carries a binder or not — a binder diagnostic here would
    be answering about a kind the declaration cannot be said to have."""
    source = _collision_source(vector).replace(
        f"reads {_PROBE_NAME} }}", f"reads {_PROBE_NAME}[p] }}"
    )
    message = _refused(source)
    assert _PROBE_NAME in message, message
    assert "index binder" not in message and "no instances to key" not in message, message


@pytest.mark.parametrize(
    "namespace,noun",
    [
        ("game_state", "duplicate state variable"),
        ("phase_state", "duplicate state variable"),
        ("zone_family", "duplicate zone"),
        ("single_zone", "duplicate zone"),
    ],
    ids=_NAME_NAMESPACES,
)
def test_a_name_repeated_in_ONE_namespace_is_the_duplicate_guards(
    namespace: str, noun: str
) -> None:
    """The self-pairs of the product, whose Owner is `_check_duplicate_names`:
    duplication is rejected WITHIN one declaration list, while shadowing ACROSS
    levels stays legal. Cited rather than re-covered — the collision arms above
    would over-refuse if they spoke here, and the diagnostic a designer reads
    for a repeat is the duplicate one."""
    message = _refused(_collision_source(frozenset({namespace}), repeat=namespace))
    assert noun in message, message
    assert _PROBE_NAME in message, message


def _with_provider(source: str) -> str:
    return source.replace("game Probe {\n", "game Probe {\n  uses provider\n", 1)


def _provider_library() -> n.Library:
    from cardlang.parse import parse_library

    return parse_library(
        f"library provider {{ state {{ {_PROBE_NAME} : Integer = 0 }} }}",
        "docs/libraries/provider.cardlang",
    )


@pytest.mark.parametrize(
    "vector,fragment",
    [
        (frozenset(), None),
        (frozenset({"zone_family"}), "already uses"),
        (frozenset({"phase_state"}), "provided by library"),
    ],
    ids=["provided-alone", "provided-vs-zone", "provided-vs-phase-state"],
)
def test_library_provided_state_reaches_the_reads_clause(
    vector: frozenset[str], fragment: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The library path's boundary in this domain, stated positively.

    A library's provided state splices into the game's own `state { }` BEFORE
    the block is checked, so a `reads` name may denote it and classifies as
    game-level state — the first cell. Every collision between a provided name
    and one the game declares is refused UPSTREAM, by `_apply_uses`'s own
    collision Owner Guards, which is why the arms above meet only provided
    names the game does not redeclare.

    A library-contributed ZONE is not constructible at all: a family library
    holds no `zones` clause, which
    `test_the_collision_namespace_axis_is_derived` reads off the grammar."""
    from cardlang.primitives_block import ReadKind, classify_read
    from tests.test_family_libraries import _patch_libraries

    _patch_libraries(monkeypatch, {"provider": _provider_library()})
    source = _with_provider(_collision_source(vector))
    if fragment is None:
        game = _checks(source)
        assert classify_read(game, _PROBE_NAME) is ReadKind.STATE_VAR
        return
    message = _refused(source)
    assert _PROBE_NAME in message, message
    assert fragment in message, message


# --- axis 16/17: a call that resolves to a DESIGNER function is not native --
#
# A declared game may define a function named after a Primitive absent from its
# namespace. Every guard keyed on the name against a corpus-wide native
# registry would then fire on a call the runtime dispatches to the user
# function. The axis is those registries, crossed with the Primitive registry:
# a nonempty intersection is a registry whose names a designer function may
# legally take.


def _collidable_native_registries() -> dict[str, frozenset[str]]:
    """Native name registries whose members a designer function may take.

    The candidate list is AUTHORED and its completeness argument is a GUARD
    census rather than a registry one: the class is "a compile-stage guard
    that keys a call by its native NAME", and a guard may key any set, so no
    registry defines the class. The census below is the set every such site
    keys, read off the two passes that hold them:

        grep -n '\\.func in \\|\\.func not in ' cardlang/resolve.py \\
            cardlang/typecheck.py

    Sites keying a set of the GAME's own names (`fn_names`,
    `defined_functions`) are outside the class by construction — they answer
    about designer functions rather than about them. Sites exempt by ORDER —
    a designer-function arm preceding them in their own function — are the
    declared-only arm's `PRIMITIVE_CALL_FUNCS` in `_validate_refs`, and the
    derivation query's two other hits, the `CALL_FUNCS` and `native_namespace`
    guards in resolve, each behind its function's own designer arm.

    What is DERIVED is which of the census members can collide at all: each
    crossed with the Primitive registry, since a Builtin's name is refused to
    a designer function under every regime. The empty ones are kept as members
    so the boundary is computed here rather than asserted — a Primitive landing
    in one of them turns it into a cell."""
    from cardlang.builtins.functions import (
        ARRIVAL_RECORD_CALLS,
        BOARD_ONLY_CALL_FUNCS,
        DECK_ONLY_CALL_FUNCS,
        TRICK_ORDER_EXCLUDED_FUNCS,
        TRICK_ORDER_GATED_FUNCS,
        TRICK_ORDER_READERS,
    )
    from cardlang.resolve import _FRAME_CALL_FUNCS
    from cardlang.typecheck import RANKING_GATED_FUNCS

    candidates = {
        # resolve's content-flavor guard, and its boardless sibling.
        "DECK_ONLY_CALL_FUNCS": DECK_ONLY_CALL_FUNCS,
        "BOARD_ONLY_CALL_FUNCS": BOARD_ONLY_CALL_FUNCS,
        # resolve's two-seat frame guard, inside the board-call check.
        "_FRAME_CALL_FUNCS": frozenset(_FRAME_CALL_FUNCS),
        # typecheck's `ranking:`-required call gate.
        "RANKING_GATED_FUNCS": RANKING_GATED_FUNCS,
        # resolve's arrival-record gate, over the winners that read one.
        "ARRIVAL_RECORD_CALLS": frozenset(ARRIVAL_RECORD_CALLS),
        # The Trick Order's presence partition: what a block gates, what it
        # excludes, and what reads one.
        "TRICK_ORDER_GATED_FUNCS": TRICK_ORDER_GATED_FUNCS,
        "TRICK_ORDER_EXCLUDED_FUNCS": TRICK_ORDER_EXCLUDED_FUNCS,
        "TRICK_ORDER_READERS": frozenset(TRICK_ORDER_READERS),
        # The Trick Order row check refuses every CALL_FUNCS member outside its
        # own allow-list, so its collidable set is the whole Primitive half.
        "TRICK_ORDER_ROW_CALLS": PRIMITIVE_CALL_FUNCS,
    }
    return {k: v & PRIMITIVE_CALL_FUNCS for k, v in candidates.items()}


def test_the_collidable_registry_intersections_are_derived() -> None:
    """Anti-vacuity, and the boundary stated: exactly the registries with a
    nonempty intersection need a designer-function cell, and the empty ones are
    empty because they hold Builtin names only — which a designer function may
    not take under any regime. The intersection is what this pins; the
    candidate list is authored, and `_collidable_native_registries` states the
    argument for it.

    red under: add a Primitive's name to `BOARD_ONLY_CALL_FUNCS`."""
    collidable = _collidable_native_registries()
    assert len(collidable) > 5, sorted(collidable)
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
    game's namespace, so the call is an unknown name.

    What the refusal is the doing OF is the regime product's business, not this
    cell's: no Primitive resolves in a game with no block either, so the two
    regimes agree on the verdict and differ on which arm speaks it."""
    name = _representative()
    _, body = _entry_and_body(name)
    message = _refused(_game(body=body))
    assert name in message


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

    A declarable name's entry and its implementation row state the same
    signature — the shape check refuses a game where they differ — so the two
    agree on every reachable cell and the distinction this claims is
    unobservable as things stand. Made observable by planting a DIFFERENT
    signature on the IMPLEMENTATION ROW for the declared name: the coercion
    must still see the declaration's. Without the plant the assertion below
    could not fail, which is what makes the plant the cell rather than
    decoration."""
    import dataclasses

    from cardlang.builtins.signatures import Sig
    from cardlang.primitives_block import PRIMITIVE_IMPLEMENTATIONS
    from cardlang.runtime import reads as reads_mod
    from cardlang.types import TAny, TInteger, TPlayer

    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    planted = Sig((TAny(),), TInteger())
    row = PRIMITIVE_IMPLEMENTATIONS["pinochle_meld_value"]
    assert planted != row.sig, "the plant changes nothing"
    seen: list[object] = []
    real = reads_mod.coerce_args

    def spy(sig: object, args: list[object]) -> object:
        seen.append(sig)
        return real(sig, args)

    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(
            PRIMITIVE_IMPLEMENTATIONS,
            "pinochle_meld_value",
            dataclasses.replace(row, sig=planted),
        )
        mp.setattr(reads_mod, "coerce_args", spy)
        play_game(game, random.Random(0))
    assert seen, "no native call was coerced — the probe reached nothing"
    assert planted not in seen, (
        "the runtime froze the declared Primitive's arguments against the "
        "implementation index"
    )
    assert Sig((TPlayer(),), TInteger()) in seen
    # red under: point `native_call`'s declared branch at
    # `implementation_sig(name)` instead of `ctx.rs.declared_sigs`
    # (demonstrated and reverted).


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
#
# It quantifies per ROW, not per game, because a game's rows are not all its
# block's to replace. The block covers the call-position namespace; the walled
# namespaces keep their own rows and their binders bind them at load, so a
# declared game legitimately keeps the rows those binders name and no others.
# The exemption is derived by asking the binders rather than authored beside
# them: an authored copy is a second statement of a fact its consumers already
# hold, hand-edited once per migration, and its drift check would be this pin
# again with one more table.

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT_DIR / "docs" / "games"
WITNESS = pathlib.Path(__file__).resolve().parent / "fixtures" / "primitives_witness.cardlang"


def game_sources() -> list[pathlib.Path]:
    """Every game whose declarations couple to the package tables: the corpus
    glob, the witness fixture, and the experiment games that declare a block.

    The fixture is IN the domain deliberately: it is the controlled declaring
    game the plants below key to, whose text the failure-channel cell edits,
    and it is what keeps the declared arm of every check non-empty
    independently of which corpus games have migrated. Salvo is in for the
    other direction: it declares the only Primitive no corpus game reaches, and
    a package registration nothing in this domain declares is refused below as
    an orphan. The experiment games are named one by one rather than globbed:
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


_SHARED_DISPATCH_MODULE = "cardlang/runtime/primitives.py"


def _implementation_modules(implementations: dict[str, Implementation]) -> frozenset[str]:
    """The implementation index's modules in `PrimitiveReads.module` spelling.

    The index states an importable DOTTED path and a row a repo-relative FILE,
    and this is the one site that compares them — the normalization
    `runtime/driver.declared_primitives` performs when it builds a declared
    entry's row, so the exemption below and the rows it exempts are spelled
    alike. `test_the_module_spellings_meet` is the control under it: a
    normalization that produced nothing would make that assert pass forever."""
    return frozenset(
        impl.module.replace(".", "/") + ".py" for impl in implementations.values()
    )


def _climb_bound_rows() -> frozenset[tuple[str, str]]:
    """The declared-reads rows the CLIMB binder binds, asked of the binder.

    A climb query is invoked by the round machinery rather than through the
    call dispatch, and `primitives.climb_row` is what hands it its module's
    row — at ROUND time, off a module-level binding made at import. So the
    set is derived by asking that binder about every registered climb name
    rather than authored a second time here, where it would drift the day a
    climb home moves."""
    from cardlang.builtins.functions import (
        PRIMITIVE_CLIMB_FOLLOWS,
        PRIMITIVE_CLIMB_LEADS,
    )
    from cardlang.runtime import primitives as dispatch

    rows = [
        dispatch.climb_row(name)
        for name in sorted(PRIMITIVE_CLIMB_LEADS | PRIMITIVE_CLIMB_FOLLOWS)
    ]
    return frozenset((r.module, r.game_file) for r in rows)


def _walled_binder_rows(rows: tuple[PrimitiveReads, ...]) -> frozenset[tuple[str, str]]:
    """The rows a WALLED namespace's binder binds, keyed as the rows table keys
    them — the rows a declared game's block does NOT replace, because the block
    covers the call-position namespace alone.

    Two sources, both consumer-derived: the climb binder's own answers, and the
    shared dispatch module's rows, which serve the auction outcomes. The
    second is stated per MODULE, which is
    only safe while that module implements no call Primitive — `_reconcile`
    asserts exactly that, so a call implementation landing there reddens the
    pin instead of silently widening the exemption."""
    return _climb_bound_rows() | frozenset(
        (r.module, r.game_file) for r in rows if r.module == _SHARED_DISPATCH_MODULE
    )


def _reconcile(
    games: tuple[tuple[str, n.Game], ...],
    implementations: dict[str, Implementation],
    rows: tuple[PrimitiveReads, ...],
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

    # (3) one definition site per ROW. A game whose block declares its
    # Primitives must not ALSO have an authored `PRIMITIVE_READS` row for the
    # coupling the block states: the same fact stated twice drifts. Quantified
    # per row rather than per game because a game's rows are not all the
    # block's to replace — the walled namespaces keep their own, and their
    # binders bind them at load, so deleting one to satisfy a game-grain claim
    # would kill the mechanic rather than end a duplication.
    assert _SHARED_DISPATCH_MODULE not in _implementation_modules(implementations), (
        f"{_SHARED_DISPATCH_MODULE} implements a call Primitive, so "
        f"exempting its rows per module would exempt a row a declared block "
        f"replaces; give that half of the exemption a per-row basis"
    )
    declared_files = {name for name, game in games if regime(game) is Regime.DECLARED}
    exempt = _walled_binder_rows(rows)
    both = sorted(
        f"{row.game_file} ({row.module})"
        for row in rows
        if row.game_file in declared_files
        and (row.module, row.game_file) not in exempt
    )
    assert not both, (
        f"rows stating a Primitive coupling their game's block states too: "
        f"{both} — a `primitives {{ }}` block and a PRIMITIVE_READS row "
        f"declare the same coupling, and two statements of one fact drift; a "
        f"row a walled binder binds is exempt and survives its game's block"
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
    _reconcile(games, dict(PRIMITIVE_IMPLEMENTATIONS), PRIMITIVE_READS)


def test_the_module_spellings_meet() -> None:
    """The control under claim (3)'s backing assert. The index spells a module
    dotted and a row spells it as a path, so an assert written in the wrong one
    matches nothing and passes forever — this is what says the normalization
    produces the rows' spelling and that the set it produces is not empty.

    red under: drop the `.replace(".", "/")` from `_implementation_modules`."""
    modules = _implementation_modules(dict(PRIMITIVE_IMPLEMENTATIONS))
    assert "cardlang/runtime/pinochle.py" in modules, sorted(modules)
    assert modules & {r.module for r in PRIMITIVE_READS}, sorted(modules)


def test_the_walled_exemption_names_the_rows_the_binders_bind() -> None:
    """The exemption is derived from two consumers, and this is what says it
    landed on real rows rather than on a key shape nothing in the registry
    uses. Both halves are asserted non-empty separately: a climb binder that
    answered nothing and a shared module with no rows would each leave the
    exemption silently narrower than it reads.

    red under: return `frozenset()` from `_climb_bound_rows`."""
    keys = {(r.module, r.game_file) for r in PRIMITIVE_READS}
    climb = _climb_bound_rows()
    shared = _walled_binder_rows(PRIMITIVE_READS) - climb
    assert climb and climb <= keys, sorted(climb)
    assert shared and shared <= keys, sorted(shared)
    assert ("cardlang/runtime/tichu.py", "tichu.cardlang") in climb


def test_every_authored_row_is_one_a_walled_binder_binds() -> None:
    """The registry's end state, stated positively.

    `_reconcile`'s claim (3) says no authored row states a coupling a block
    states — a statement about the DECLARED games, which leaves a row for a
    game that writes no block outside what it can see. This says the other
    thing: there is no such row at all. Every row the table holds is one the
    climb binder or the shared dispatch module's auction outcomes bind at
    load, which is what makes `PRIMITIVE_READS` the declaration for the two
    namespaces a block cannot name rather than a second route into the
    call-position one.

    Born green, and the mutation that reddens it is a call-namespace row —
    executed 2026-09-04 by appending
    `PrimitiveReads(module="cardlang/runtime/canasta.py",
    game_file="canasta.cardlang", state_vars=frozenset({"stage"}))`:
    "authored rows no walled binder binds: [('cardlang/runtime/canasta.py',
    'canasta.cardlang')]"; demonstrated and reverted."""
    keys = {(r.module, r.game_file) for r in PRIMITIVE_READS}
    assert keys == _walled_binder_rows(PRIMITIVE_READS), (
        f"authored rows no walled binder binds: "
        f"{sorted(keys - _walled_binder_rows(PRIMITIVE_READS))}"
    )


@pytest.mark.slow
def test_reconciliation_reddens_on_a_planted_orphan() -> None:
    """An implementation nothing reaches. Demonstrated rather than asserted:
    a pin whose author cannot name a reddening edit is the vacuously-green
    defect wearing a test's name."""
    planted = dict(PRIMITIVE_IMPLEMENTATIONS)
    planted["orphan_primitive"] = Implementation(
        "cardlang.runtime.pinochle",
        "pinochle_meld_value",
        InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    )
    with pytest.raises(AssertionError, match="orphan_primitive"):
        _reconcile(_checked_games(), planted, PRIMITIVE_READS)


@pytest.mark.slow
def test_reconciliation_reddens_on_a_dual_definition_site() -> None:
    """A declared game whose authored `PRIMITIVE_READS` row still stands — the
    exact state the corpus sweep removes, planted here so the window is checked
    while it is open.

    The plant is a ROW, keyed to the declaring witness game, because the claim
    quantifies over rows: a game-shaped plant would say only that SOME row of
    that game's remains, which the walled survivors make true for games that
    are correctly migrated."""
    planted = PRIMITIVE_READS + (
        PrimitiveReads(
            module="cardlang/runtime/pinochle.py",
            game_file=WITNESS.name,
            zone_families=frozenset({"hand"}),
        ),
    )
    with pytest.raises(AssertionError, match=WITNESS.name):
        _reconcile(_checked_games(), dict(PRIMITIVE_IMPLEMENTATIONS), planted)


@pytest.mark.slow
def test_the_narrowing_exempts_a_surviving_auction_row() -> None:
    """The exemption exempts something. A game declaring a block while the
    shared dispatch module still holds its AUCTION row is the day-one state of
    the wave — the block covers the call-position namespace, the auction
    outcome takes its own declaration slot later (issue #142), and the row
    stays because the outcome's dispatch reads it.

    The unnarrowed membership is asserted non-empty on the same state, so the
    pass is the narrowing's doing and not an empty intersection. The rows table
    is restricted to the shared module's own: the game's OTHER row — the one
    its block replaces — is exactly what claim (3) must still refuse, and
    leaving it in would prove the cell for the wrong reason."""
    games = _checked_games() + (("pinochle.cardlang", check_source(WITNESS)),)
    rows = tuple(r for r in PRIMITIVE_READS if r.module == _SHARED_DISPATCH_MODULE)
    assert {"pinochle.cardlang"} & {r.game_file for r in rows}, (
        "the shared module holds no pinochle row — the cell would pass by "
        "having nothing to exempt"
    )
    _reconcile(games, dict(PRIMITIVE_IMPLEMENTATIONS), rows)


@pytest.mark.slow
def test_a_call_implementation_in_the_shared_module_reddens_the_exemption() -> None:
    """The exemption states the shared dispatch module's rows per MODULE, which
    is sound only while nothing there is a call Primitive. A call
    implementation landing in that module would make one of those rows a row a
    block replaces, and the module-grain half would exempt it silently — so the
    condition is asserted rather than assumed, and this is the plant that says
    the assert can speak."""
    planted = dict(PRIMITIVE_IMPLEMENTATIONS)
    planted["pinochle_meld_value"] = Implementation(
        "cardlang.runtime.primitives",
        "bridge_auction_outcome",
        InvocationContract.BUNDLED,
        Sig((TPlayer(),), TInteger()),
    )
    with pytest.raises(AssertionError, match=_SHARED_DISPATCH_MODULE):
        _reconcile(_checked_games(), planted, PRIMITIVE_READS)


@pytest.mark.slow
def test_the_narrowing_exempts_the_climb_row_its_binder_binds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tichu's carve-out, which the corpus sweep meets for real: the module
    implements a call Primitive AND is a climb home, its row is what the climb
    binder imports at load, and the block does not cover climb queries — so the
    row outlives the block, and deleting it to satisfy a coarser claim would
    crash the climb machinery at load rather than end a duplication.

    red under (run): drop the climb half of the exemption."""
    games = _checked_games() + (("tichu.cardlang", check_source(WITNESS)),)
    _reconcile(games, dict(PRIMITIVE_IMPLEMENTATIONS), PRIMITIVE_READS)
    monkeypatch.setattr(
        sys.modules[__name__], "_climb_bound_rows", lambda: frozenset()
    )
    with pytest.raises(AssertionError, match="tichu.cardlang"):
        _reconcile(games, dict(PRIMITIVE_IMPLEMENTATIONS), PRIMITIVE_READS)


# --- the witness fixture, played --------------------------------------------


def test_an_under_declared_reads_clause_fails_in_the_typed_channel() -> None:
    """Whether a declared read SUFFICES for its implementation is a fact about
    Python, so the compile stage cannot settle it and the playout is where an
    under-declaring clause surfaces. What the designer meets there is the
    block's own failure channel: the primitive, the name its implementation
    wanted, and the clause to extend — never a bare `KeyError` from a module
    the reader has no reason to suspect.

    The witness fixture with one read removed is the shape every hand-authored
    block can take, which is what makes this the wave's channel rather than one
    game's."""
    from cardlang.runtime.reads import PrimitiveReadError

    whole = WITNESS.read_text()
    source = whole.replace("reads hand[p], trump_suit", "reads hand[p]")
    assert source != whole, (
        "the under-declaration did not apply — the fixture's clause moved"
    )
    game = check_dsl(source, "under_declared.cardlang")
    with pytest.raises(PrimitiveReadError) as exc:
        play_game(game, random.Random(0))
    message = str(exc.value)
    assert "pinochle_meld_value" in message, message
    assert "trump_suit" in message, message
    assert "reads" in message and "primitives" in message, message


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


# --- axis 27: the collection spelling (issue #472) ---------------------------
#
# `Collection<Card>` in an entry's two type slots and nowhere else. The three
# refusal layers are separate registries and are crossed separately: the SHAPE
# (a bracket anywhere but an entry slot; the phrase form; a comma, a `?`, a
# nested bracket) is the grammar's, the ELEMENT is the resolver's from the
# block's own one-member allow-list, and the FACETS are unspellable by
# construction and pinned by the both-ways shape check.

# The spelling family at an entry slot, and the outcome each is ruled to have.
# One row per DECISION — the element axis below is the derived cross, and this
# is the surface's own decision table, which no registry can state.
_COLLECTION_SPELLINGS: dict[str, str] = {
    # The ruled form. Admitted at the type gate; a concrete entry then meets
    # the shape check, which is the both-slots symmetry's whole mechanism.
    "Collection<Card>": "gate-admits",
    # A plural-as-type: a bare NAME outside the declarable set, so the
    # existing name gate answers and the new surface never sees it.
    "Cards": "unspellable",
    # The constructor word with no element.
    "Collection": "element-missing",
    # The issue's own spelling, taught back as the ruled one.
    "collection of Card": "phrase",
    # An index domain where an element type belongs — the `Hand<player>`
    # confusion, refused by name rather than by shape.
    "Collection<player>": "element",
    # The wall: the checker mints `Collection<Player>` for `all players`, and
    # no registered signature takes one.
    "Collection<Player>": "element",
    # The four shapes the element slot cannot hold — a `?` on the collection,
    # a second argument, a nested bracket, a `?` on the element. Each is a
    # sentence a designer writes on purpose, so each answers in the designer's
    # register with the ruled form rather than in the lexer's with the
    # character it stopped at (the operator's ruling, 2026-09-03).
    "Collection<Card>?": "optional-collection",
    "Collection<Card, Card>": "arity",
    "Collection<Collection<Card>>": "nested",
    "Collection<Suit?>": "optional-element",
}

# What the gate did, as an ALLOW-LIST over the message space. A deny-list here
# would read an unrecognized refusal as an admit, which is the one reading a
# grid over a new surface must not have.
_COLLECTION_OUTCOMES: tuple[tuple[str, str], ...] = (
    ("is spellable in a `primitives { }` entry only", "elsewhere"),
    ("not a phrase — write", "phrase"),
    ("a collection is never optional", "optional-collection"),
    ("takes ONE element type", "arity"),
    ("a collection of collections has no spelling", "nested"),
    ("an element is never optional", "optional-element"),
    ("takes an element type", "element-missing"),
    ("is not an element type", "element"),
    ("no registered Primitive has an implementation taking it", "element"),
    ("may not spell", "unspellable"),
    ("syntax error", "syntax"),
    ("is not the signature its implementation takes", "gate-admits"),
)


def _collection_outcome(source: str) -> str:
    """Which layer answered, classified by an allow-list that RAISES.

    An unrecognized message is a cell nobody classified, and reading it as an
    admit is how a refusal in the wrong voice passes for the ruled one."""
    try:
        _checks(source)
    except DiagnosticError as e:
        message = "\n".join(
            [str(e), *(list(getattr(e, "__notes__", None) or []))]
        )
        for needle, label in _COLLECTION_OUTCOMES:
            if needle in message:
                return label
        raise AssertionError(
            f"unclassified refusal — no row of `_COLLECTION_OUTCOMES` names "
            f"it, so the grid cannot say which layer spoke: {message}"
        ) from e
    return "admit"


_COLLECTION_SLOTS: dict[str, str] = {
    # A Primitive whose implementation takes neither a collection nor the
    # spelling under test, so the only thing the cell measures is the gate:
    # every spelling that clears it meets the shape check next.
    "parameter": "pinochle_meld_value(x : {spelling}) : Integer",
    "return": "pinochle_meld_value(p : Player) : {spelling}",
}


@pytest.mark.parametrize("slot", sorted(_COLLECTION_SLOTS))
@pytest.mark.parametrize("spelling", sorted(_COLLECTION_SPELLINGS))
def test_the_collection_spelling_lands_where_the_ruling_says(
    spelling: str, slot: str
) -> None:
    """spelling x slot, at the entry. Both slots take the same spellings —
    a form legal in one and refused in the other is a surface a designer
    cannot predict — so the expected column is the same for both."""
    entry = _COLLECTION_SLOTS[slot].format(spelling=spelling)
    actual = _collection_outcome(_game(block=entry, body="    score[0] := 1"))
    assert actual == _COLLECTION_SPELLINGS[spelling], (
        f"`{entry}` answered {actual!r}, and the ruling says "
        f"{_COLLECTION_SPELLINGS[spelling]!r}"
    )


@pytest.mark.parametrize(
    "entry",
    [
        "gin_valid_meld(cards : Collection<Card>) : Boolean",
        "gin_arrange_ok(p : Player, cards : Collection<Card>) : Boolean"
        " reads hand[p], taken[p]",
    ],
    ids=["valid_meld", "arrange_ok"],
)
def test_a_collection_entry_agrees_with_its_implementation(entry: str) -> None:
    """The accept cells: the two corpus witnesses, whose declared `Sig` the
    both-ways shape check forces equal to the implementation's — facets
    included, which is what makes `Collection<Card>` denote exactly
    `TCollection(TCard(), key=None, zone=False)` and nothing else."""
    source = _game(block=entry, body="    score[0] := 1").replace(
        "          discard : Discard }",
        "          taken[player] : HiddenPile<player>\n          discard : Discard }",
    )
    game = _checks(source)
    assert declared_names(game) == {entry.split("(")[0]}


def test_a_declared_collection_parameter_is_the_registry_s_signature() -> None:
    """The materialized `Sig`, read off the declaration rather than off the
    table it is checked against: the spelling's facets are the defaults, so
    the runtime's signature-driven freeze sees the same arm under either
    regime."""
    from cardlang.typecheck import declared_primitive_sigs

    entry = "gin_valid_meld(cards : Collection<Card>) : Boolean"
    game = _checks(_game(block=entry, body="    score[0] := 1"))
    assert declared_primitive_sigs(game)["gin_valid_meld"] == implementation_sig(
        "gin_valid_meld"
    )


# The ELEMENT axis, derived: every name an entry can spell in a bare slot,
# crossed with the collection form. The allow-list is what decides, so a name
# admitted into it lands here as an accept without anyone editing a row.
def _element_cells() -> list[tuple[str, bool]]:
    probe = _checks(_game(block=_PINOCHLE_ENTRY, body=""))
    names = sorted(
        DECLARABLE_BUILTIN_TYPE_NAMES | {p.name for p in probe.positions}
    )
    return [(name, name in COLLECTION_ELEMENT_NAMES) for name in names]


@pytest.mark.parametrize(
    "element,allowed", _element_cells(), ids=[c[0] for c in _element_cells()]
)
def test_the_element_slot_admits_exactly_the_allow_list(
    element: str, allowed: bool
) -> None:
    """The element registry, at the resolver. A name outside the list must be
    refused BY NAME — never mapped to the permissive top at the element
    position, which would hand a Primitive an unfrozen engine value one
    constructor down."""
    entry = f"pinochle_meld_value(x : Collection<{element}>) : Integer"
    actual = _collection_outcome(_game(block=entry, body="    score[0] := 1"))
    assert actual == ("gate-admits" if allowed else "element"), (
        f"`Collection<{element}>` answered {actual!r}; the block's element "
        f"allow-list says {'in' if allowed else 'out'}"
    )


def test_the_element_allow_list_is_what_the_implementations_take() -> None:
    """The list and the registered Python are held EQUAL, both directions:
    a Primitive registered over a collection of something else lands red here
    until the list admits its element with a witness, and an element admitted
    with no implementation lands red too.

    red under: give any `PRIMITIVE_IMPLEMENTATIONS` row a
    `Collection<Player>` parameter in its `sig` — verified on
    `gin_arrange_ok`, which reports `TPlayer at gin_arrange_ok's
    parameter 2`."""
    from cardlang.primitives_block import implementation_sig
    from cardlang.typecheck import TypeEnv, type_from_name

    env = TypeEnv()
    # Keyed by element constructor so a mismatch can name the REGISTRATION
    # that caused it — which Primitive, and which slot of its signature. The
    # two sets alone say a number disagrees; an engine author needs the row.
    implemented: dict[str, list[str]] = {}
    for name in sorted(PRIMITIVE_IMPLEMENTATIONS):
        sig = implementation_sig(name)
        assert sig is not None, (
            f"{name} is registered as implemented and states no signature, so "
            f"the element derivation below would skip it silently"
        )
        slots = [(f"parameter {i + 1}", t) for i, t in enumerate(sig.params)]
        slots.append(("return", sig.ret))
        for slot, t in slots:
            if isinstance(t, TCollection):
                implemented.setdefault(type(t.element).__name__, []).append(
                    f"{name}'s {slot}"
                )
    declarable = {
        type(
            type_from_name(name, False, env.structs, env.positions, env.directions)
        ).__name__: name
        for name in COLLECTION_ELEMENT_NAMES
    }
    unregistered = sorted(set(declarable) - set(implemented))
    unspellable = sorted(set(implemented) - set(declarable))
    assert not unregistered, (
        f"the block spells collections of "
        f"{[declarable[c] for c in unregistered]} and no registered Primitive "
        f"takes one — an element admitted with no implementation is a "
        f"spelling that dies at the shape check"
    )
    assert not unspellable, (
        "a registered Primitive takes a collection element the block cannot "
        "spell: "
        + "; ".join(
            f"{constructor} at {', '.join(implemented[constructor])}"
            for constructor in unspellable
        )
        + " — admit it with its witness, or the declaration route is closed "
        "to that Primitive"
    )


# The adjacency cells: the boundary tokens a `>` can meet, and the one place
# `=` can follow a type in each of the two blocks that carry a type slot.
_COLLECTION_ADJACENCY: dict[str, tuple[str, str]] = {
    # `>` followed by `=` is `>=` under maximal munch, and `>=` is a real
    # terminal — so the collection's closing bracket sits against the one
    # token that can swallow it. Only the RETURN slot puts them adjacent (a
    # parameter's `>` meets the closing paren), and the twin must be reached
    # on that stream. `_FUSED_SPELLINGS` below pins that the fusion is real,
    # so this cell cannot pass by there being nothing to fuse.
    "fused-default": (
        "    primitives { pinochle_meld_value(p : Player) : Collection<Card>= 0 }\n",
        "declares a signature, never a value",
    ),
    # The same fusion at the other `=`-carrying type slot, whose refusal is
    # the teaching twin's rather than the default twin's.
    "fused-state": (
        "    state { s : Collection<Card>= 0 }\n",
        "is spellable in a `primitives { }` entry only",
    ),
    # No fusion here — the parameter's `>` meets `)` and the `=` follows the
    # return type — and the cell is kept for the OTHER claim the grammar
    # comment makes: all three entry forms take the entry type family, so a
    # default-arm entry carrying a collection parameter reaches its own reject
    # arm's message instead of dying at the `<`.
    "default-arm-collection-param": (
        "    primitives { pinochle_meld_value(x : Collection<Card>) : Integer= 0 }\n",
        "declares a signature, never a value",
    ),
    # `>` against the closing paren, the comma, and the reads keyword.
    "close-paren": (
        "    primitives { gin_valid_meld(cards : Collection<Card>) : Boolean }\n",
        "",
    ),
    "comma": (
        "    primitives { gin_arrange_ok(p : Player, cards : Collection<Card>)"
        " : Boolean reads hand[p], taken[p] }\n",
        "",
    ),
    "reads-keyword": (
        "    primitives { gin_arrange_ok(p : Player, cards : Collection<Card>)"
        " : Boolean\n        reads hand[p], taken[p] }\n",
        "",
    ),
    # A comment closing the line the spelling ends.
    "trailing-comment": (
        "    primitives { gin_valid_meld(cards : Collection<Card>) : Boolean"
        "  // the defender's guard\n    }\n",
        "",
    ),
    # The reverse confusion, which must stay refused: an element type where a
    # zone's index domain belongs.
    "zone-element": ("", "unknown owner 'Card'"),
    # The other half of that confusion, one slot over: the CONSTRUCTOR word
    # where a zone type belongs. `Collection` means something now, so a zone
    # slot that calls it unknown spends the "unknown" currency on a spelled
    # word — the positions ledger's own refusal.
    "zone-head": ("", "a zone's angle brackets take an index domain"),
}


@pytest.mark.parametrize("cell", sorted(_COLLECTION_ADJACENCY))
def test_the_collection_spelling_s_neighbours_read_as_written(cell: str) -> None:
    """The tokens a `>` can sit against. Each accept cell PARSES to the same
    declaration a spaced form would, and each reject cell reaches the message
    its own layer owns rather than the lexer's."""
    clause, needle = _COLLECTION_ADJACENCY[cell]
    if cell == "zone-element":
        source = _game(block=None, body="").replace(
            "hand[player] : Hand<player>", "hand[player] : Hand<Card>"
        )
    elif cell == "zone-head":
        source = _game(block=None, body="").replace(
            "hand[player] : Hand<player>", "hand[player] : Collection<Card>"
        )
    else:
        source = _game(block=None, body="").replace(
            "  zones {", clause + "  zones {"
        )
        if "taken[p]" in clause:
            source = source.replace(
                "          discard : Discard }",
                "          taken[player] : HiddenPile<player>\n"
                "          discard : Discard }",
            )
    if needle:
        message = _refused(source)
        assert needle in message, message
        return
    game = _checks(source)
    assert game.primitives is not None
    assert [p.type_name for d in game.primitives.decls for p in d.params][-1] == (
        "Collection<Card>"
    )


# The cells whose sentence puts the collection's closing `>` against a `=`.
# Named here so the fusion they are about can be MEASURED rather than
# asserted in a comment: a cell claiming to survive `>=` proves nothing if the
# stream never held a `>=` to survive.
_FUSED_SPELLINGS: frozenset[str] = frozenset({"fused-default", "fused-state"})


@pytest.mark.parametrize("cell", sorted(_FUSED_SPELLINGS))
def test_the_fused_cells_really_do_fuse(cell: str) -> None:
    """`>=` is a terminal, and maximal munch takes it.

    The parse must still see `>` then `=` — the contextual lexer is what
    supplies that, by offering `>=` only where a comparison can stand — so the
    two cells above are about a real hazard rather than a spelling nobody's
    lexer would join. Measured on the BASIC lexer, which is the munch without
    the context: a stream with no `>=` in it would make those cells vacuous.

    red under: put a space before the `=` in either cell's clause.
    """
    from cardlang.parse import _parser

    clause, _needle = _COLLECTION_ADJACENCY[cell]
    fused = [t for t in _parser().lex(clause.strip()) if str(t) == ">="]
    assert fused, (
        f"{cell}'s sentence lexes with no `>=` in it, so the cell cannot be "
        f"about surviving the fusion: {clause.strip()}"
    )


# The string methods that read a spelling's SHAPE. A bracket handed to one of
# these is a second decomposition of a type spelling, which is the fact the
# scrape below holds to one site.
_SHAPE_READERS: frozenset[str] = frozenset(
    {
        "split", "rsplit", "partition", "rpartition", "index", "find", "rfind",
        "startswith", "endswith", "removeprefix", "removesuffix", "strip",
        "lstrip", "rstrip", "count", "replace",
    }
)


def test_a_collection_spelling_is_split_in_exactly_one_place() -> None:
    """The decomposition is the ONE reader of the spelling's bracket.

    The trailing `?` is sliced elsewhere in the package — this same scrape run
    over `"?"` in place of the bracket names those sites, and none of them
    reads a `primitives { }` entry spelling — uniform and correct. A second
    delimiter must not join that class: two readings of one spelling is how a
    declaration and the type it denotes come apart. The scrape is over the
    BRACKET alone, which is the claim; the `?` class is named here rather than
    swept, because this change's proportion is the block.

    red under: write `type_name.split("<")` in any `cardlang/` module outside
    `primitives_block.py`."""
    root = pathlib.Path(__file__).resolve().parent.parent / "cardlang"
    owner = root / "primitives_block.py"

    def has_bracket(value: object) -> bool:
        return isinstance(value, str) and ("<" in value or ">" in value)

    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path == owner:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            where = f"{path.relative_to(root.parent)}:{getattr(node, 'lineno', 0)}"
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _SHAPE_READERS
                and any(
                    isinstance(a, ast.Constant) and has_bracket(a.value)
                    for a in node.args
                )
            ):
                offenders.append(where)
            if (
                isinstance(node, ast.Compare)
                and any(isinstance(o, (ast.In, ast.NotIn)) for o in node.ops)
                and isinstance(node.left, ast.Constant)
                and has_bracket(node.left.value)
            ):
                offenders.append(where)
    assert not offenders, (
        f"a module outside the decomposition reads a type spelling's bracket "
        f"itself: {offenders} — the shape is `primitives_block`'s to read"
    )


def test_a_collection_return_is_refused_against_every_implementation() -> None:
    """The return slot is admitted at the gate and refused by SHAPE, for every
    registered Primitive: no implementation returns a collection, so the
    both-slots symmetry costs nothing a designer can reach.

    An empty registry, not a gap — the day an implementation returns one, its
    witness is owed."""
    from cardlang.primitives_block import implementation_sig

    returning: list[str] = []
    for name in sorted(PRIMITIVE_IMPLEMENTATIONS):
        sig = implementation_sig(name)
        assert sig is not None, name
        if isinstance(sig.ret, TCollection):
            returning.append(name)
    assert not returning, (
        f"{returning} return a collection — the return slot's refusal is by "
        f"shape alone, so this cell owes a witness now"
    )
    entry = "pinochle_meld_value(p : Player) : Collection<Card>"
    assert _collection_outcome(
        _game(block=entry, body="    score[0] := 1")
    ) == "gate-admits"


# The keyed map at a collection parameter: issue #539's cell, NOT this
# change's fix. `coercible` compares elements only, so a player-keyed map
# reaches the parameter and the implementation answers on the keys.
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #539: a keyed collection coerces into an unkeyed parameter",
)
def test_a_keyed_map_is_refused_at_a_collection_parameter() -> None:
    """A per-player map handed where a card collection is wanted.

    `coercible` compares collection ELEMENTS only, so the map reaches the
    implementation and it answers on the player ids. The call site is where
    the refusal belongs (issue #539); the cell is here because the spelling is
    what puts a declared collection parameter in a designer's reach."""
    entry = "gin_valid_meld(cards : Collection<Card>) : Boolean"
    body = (
        "    let probe[p] = A of spades\n"
        "    score[0] := if gin_valid_meld(probe) then 1 else 0"
    )
    try:
        _checks(_game(block=entry, body=body))
        refused = False
    except DiagnosticError:
        refused = True
    assert refused, (
        "a player-keyed map checked clean at a `Collection<Card>` parameter"
    )


# --- the joint-selection position, run ---------------------------------------

# A declared game rooting `where jointly` in a declared entry: the position a
# collection parameter unlocks, played rather than checked. Seat 0 holds the
# four 7s (a valid meld — the true witness) and seat 1 holds kings and queens
# (no meld — the false one), so the score the melds decide separates them.
_JOINT_GAME = """game JointProbe {
  players: 2
  max_length: 200
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  primitives {
    gin_valid_meld(cards : Collection<Card>) : Boolean
    gin_can_declare_free(p : Player) : Boolean   reads hand[p], taken[p]
  }
  zones { deck : Deck  hand[player] : Hand<player>
          taken[player] : HiddenPile<player>
          meldA[player] : Discard  discard : Discard }
  state { score[player] : Integer = 0  arranged[player] : Boolean = false }
  phase play {
    move all cards to deck
    move all cards from deck where card.rank is "7" to hand[0]
    move 2 cards from deck where card.rank is K to hand[1]
    move all cards from deck to discard
    turns t from 0 over all players until arranged[0] and arranged[1] {
      offer to t one of [declare_meld, pass_arranging]
    }
  }
  winner: highest score
}
move_type declare_meld {
  when: not arranged[actor] and gin_can_declare_free(actor)
  effect {
    move chosen some cards from hand[actor]
         where jointly gin_valid_meld(cards) to meldA[actor]
    arranged[actor] := true
    score[actor] := number of cards in meldA[actor]
  }
}
move_type pass_arranging {
  when: not arranged[actor]
  effect { arranged[actor] := true }
}
"""


def test_a_declared_entry_roots_a_joint_selection_that_plays() -> None:
    """The joint-selection position, under the declared regime.

    The predicate's subset codec is found by the call's ROOT NAME, which no
    regime changes, so a declared game reaches the same universe the legacy
    one did — and the action space BUILDS, which is the half a resolve-clean
    fixture cannot show. The game is synthetic beside the corpus proof: gin
    itself confounds the arm, since its own reads would materialize whether or
    not the entry declared them, and here the entry declares none.

    Seat 0 holds the four 7s (a meld — the true witness) and seat 1 two cards
    (no subset of them melds — the false one), so the score separates on the
    declared predicates' own answers: the guard entry decides whether the
    joint move is offered at all, and the joint entry decides which subsets it
    offers."""
    from cardlang.openspiel.encoding import ActionSpace

    game = check_dsl(_JOINT_GAME, "joint.cardlang")
    assert declared_names(game) == {"gin_valid_meld", "gin_can_declare_free"}
    space = ActionSpace.for_game(game)
    assert space.num_distinct_actions > 0
    seen: set[tuple[int, int]] = set()
    for seed in range(12):
        result = play_game(game, random.Random(seed))
        seen.add((result.scores[0], result.scores[1]))
    assert all(s1 == 0 for _, s1 in seen), sorted(seen)
    assert any(s0 > 0 for s0, _ in seen), sorted(seen)


def test_a_declared_collection_argument_is_frozen_at_the_boundary() -> None:
    """The freeze, reconciled against the DECLARED table rather than the
    registry it is checked against: the argument a declared entry's Python
    receives is the deep-frozen element tuple, never the live zone list.

    red under: return `list(...)` instead of the frozen tuple from
    `reads.coerce_args`' `TCollection` arm."""
    from cardlang.runtime.reads import coerce_args
    from cardlang.runtime.state import Zone
    from cardlang.runtime.values import Card
    from cardlang.typecheck import declared_primitive_sigs

    entry = "gin_valid_meld(cards : Collection<Card>) : Boolean"
    game = _checks(_game(block=entry, body="    score[0] := 1"))
    sig = declared_primitive_sigs(game)["gin_valid_meld"]
    zone = Zone()
    zone.cards.extend([Card("7", "clubs"), Card("8", "clubs")])
    coerced = coerce_args(sig, [zone])[0]
    assert isinstance(coerced, tuple)
    assert list(coerced) == [Card("7", "clubs"), Card("8", "clubs")]
    # The frozen snapshot, not the zone's live list — a primitive holding the
    # latter could `clear()` the argument and empty the zone.
    assert not any(c is live for c, live in zip(coerced, zone.cards))
