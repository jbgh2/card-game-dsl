"""The `primitives { }` block's coverage grid.

The block declares the [[primitive]]s a game borrows from outside the DSL —
typed signature and declared reads — and its PRESENCE partitions the game's
native-call namespace in both directions (docs/design-notes/primitive-sidecars.md
§2; epic #142, stage 3a). This module is that change's grid, authored red
before the implementation: the born-red counts at the foot of this docstring
are its provenance.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   (1) every combination the `primitives { }` grammar accepts is
            implemented or refused with a named diagnostic in the layer that
            owns the class — never parsed and ignored; (2) a game's Primitive
            regime is a CHECKED partition, so an undeclared game keeps the
            legacy namespace exactly and a declared game can reach no other
            game's Primitive; (3) the declared signature is what freezes the
            arguments and what the call site is checked against, so no
            declared spelling can hand an implementation a raw engine value;
            (4) a declared `reads` clause bounds what the implementation
            receives, per primitive and per call, and an undeclared name is
            ABSENT rather than merely unfetched.
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
registry:   `cardlang/builtins/functions.py` (the six Primitive namespaces
            and `BUILTIN_CALL_FUNCS`); `cardlang/primitives_block.py`
            (`PRIMITIVE_IMPLEMENTATIONS`, `WALLED_NAMESPACES`,
            `DECLARABLE_BUILTIN_TYPE_NAMES`, `UNDECLARABLE_TYPE_CONSTRUCTORS`,
            `InvocationContract`); `cardlang.types.Type` (the constructor
            partition, via `typing.get_args`); the `?game_item` scrape in
            tests/test_game_clause_guards.py for the clause registry; the
            declared-reads accessors' own refusal matrix in
            tests/test_primitive_reads.py.
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
            one place that runs.

Born red (the bare run on this branch, before any of the block's grammar,
resolve, typecheck or runtime existed): `58 failed, 51 passed`. Every
block-bearing cell died at the block's own line, and the 51 that passed are
the registry reconciliations above, which pin tables the same commit added
and are green by construction rather than by the implementation. Every cell
has since flipped, so no mark remains.
"""

from __future__ import annotations

import dataclasses
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
from cardlang.pipeline import check_dsl
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
    """The rendered diagnostic a refused probe produces."""
    with pytest.raises(DiagnosticError) as excinfo:
        _checks(source)
    return str(excinfo.value)


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
    import importlib

    impl = PRIMITIVE_IMPLEMENTATIONS[name]
    module = importlib.import_module(impl.module)
    assert callable(getattr(module, impl.attribute, None)), (
        f"{impl.module}.{impl.attribute} — the index names it for {name!r}, "
        f"and the module does not define it"
    )


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
            if isinstance(t, tuple(typing.get_args(Type))) and hasattr(t, "inner"):
                out.add(type(t.inner).__name__)  # type: ignore[union-attr]
    # A board game's `cell` domain is the one declarable name outside the
    # built-ins whose member type is not `TInteger`; probed on its own game
    # rather than by hand-adding `TCell`, so the reachability is measured.
    board = _checks(_board_game())
    for p in board.positions:
        t = type_from_name(p.name, False, env.structs, {q.name: q for q in board.positions}, {})
        out.add(type(t).__name__)
    return out


def _board_game() -> str:
    return (
        "game BoardProbe {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  pieces: chequers\n"
        "  board: grid(3, 3)\n"
        "  zones { supply : Pile }\n"
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
    "spelling",
    ["Any", "collection of Card", "Line", "dir", "Bid"],
    ids=["any", "collection", "line", "direction", "struct"],
)
def test_an_unspellable_type_is_refused(spelling: str) -> None:
    """The complement of the declarable set, probed at the parameter slot. Each
    is refused by NAME — never accepted and silently typed as the permissive
    top, which is the one reading that would let a declared Primitive receive
    an unfrozen engine value."""
    entry = f"probe_fn(x : {spelling}) : Integer"
    source = _game(block=entry, body="    score[0] := 1")
    message = _refused(source)
    assert "probe_fn" in message or spelling.split()[0] in message


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
    source = _game(
        block="probe_fn(p : Player) : Integer",
        body="    score[0] := 1",
        extra="  function probe_fn(p : Player) = 0\n",
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


# --- axis 18: the declared signature is what freezes -------------------------


def test_the_declared_signature_drives_the_argument_coercion() -> None:
    """`coerce_args` is signature-driven, and for a declared Primitive the
    signature is the DECLARATION's. A wrong declared type would change what the
    implementation receives, so the materialized signature is what the runtime
    reads — never `CALL_SIGS`, which a declared game's name need not be in."""
    from cardlang.typecheck import declared_primitive_sigs
    from cardlang.types import TInteger, TPlayer

    game = _checks(_game(body=_SCORE_FROM_PRIMITIVE))
    sigs = declared_primitive_sigs(game)
    assert sigs["pinochle_meld_value"].params == (TPlayer(),)
    assert sigs["pinochle_meld_value"].ret == TInteger()


# --- axis 8: the binder narrows what the bundle materializes ----------------


def _bundle_for(clause: str) -> object:
    """The `GameReads` a declared Primitive receives, captured from a playout."""
    from cardlang.runtime import narrowing

    seen: list[object] = []
    real = narrowing.bind

    def spy(rs: object, actor: object, r: object, **kwargs: object) -> object:
        bundle = real(rs, actor, r, **kwargs)  # type: ignore[arg-type]
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
        narrowing.bind = real  # type: ignore[assignment]
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


def test_an_undeclared_name_is_absent_from_the_bundle() -> None:
    gr = _bundle_for("hand[p], trump_suit")
    assert "discard" not in gr.singles  # type: ignore[attr-defined]
    assert "seen" not in gr.state  # type: ignore[attr-defined]


# --- axis 15: the corpus reconciliation pin ---------------------------------


def _reconcile(games: dict[str, frozenset[str]]) -> None:
    """The corpus pin's body, over a supplied game -> declared-names map so the
    reddening mutations below can plant into it."""
    from cardlang.primitives_block import reconcile

    reconcile(games)


def test_the_corpus_reconciles_both_ways() -> None:
    """Every game reaches its Primitives through exactly one regime, and every
    registered implementation is claimed by exactly one side. Derived from the
    games glob THROUGH the pipeline, so a game added to the corpus is covered
    with nothing to keep in sync."""
    from cardlang.primitives_block import corpus_declarations, reconcile

    declarations = corpus_declarations()
    assert declarations, "the corpus glob came up empty — wrong path, not a clean corpus"
    reconcile(declarations)


def test_reconciliation_reddens_on_a_planted_orphan() -> None:
    """A planted implementation nothing claims. Without this the pin's declared
    arm is empty in 3a and would read as proof while proving nothing."""
    from cardlang import primitives_block as pb

    planted = dict(pb.PRIMITIVE_IMPLEMENTATIONS)
    planted["orphan_primitive"] = Implementation(
        "cardlang.runtime.pinochle", "pinochle_meld_value", InvocationContract.BUNDLED
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pb, "PRIMITIVE_IMPLEMENTATIONS", planted)
        with pytest.raises(AssertionError, match="orphan_primitive"):
            _reconcile(pb.corpus_declarations())


def test_reconciliation_reddens_on_a_dual_claim() -> None:
    """A name claimed by a game's block AND by the legacy namespace — the
    dual-definition-site state the coexistence window is priced to keep
    impossible."""
    from cardlang import primitives_block as pb

    claims = dict(pb.corpus_declarations())
    claims["planted.cardlang"] = frozenset({"tichu_dragon_won"})
    with pytest.raises(AssertionError, match="tichu_dragon_won"):
        _reconcile(claims)


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
