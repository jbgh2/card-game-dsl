"""Position domains (decisions.md "Position domains and positional zones").

Completeness ledger (decisions.md "Surface totality" / "Closed-domain
completeness")
----------------------------------------------------------------------
property:   a declared position domain works in exactly two slots — zone-
            family index and move-parameter domain — with identical member
            enumeration at runtime and in the static action space, and is
            rejected with a diagnostic everywhere else a domain/role/type
            name can appear.
domain:     (a) the surface slots a domain id can occupy: zone index, zone
            type-arg, move/rule/procedure/function parameter type, state
            index, state type, `for each` role, `each … simultaneously`
            role, quantifier noun, `to each` destination, bare zone
            reference; (b) the declaration's own value space (bounds,
            duplicates, name collisions); (c) the consumers of the domain
            (ZoneStore keys, observation ownership, runtime candidate
            enumeration, static vocab enumeration); (d) the name reservation
            as a PRODUCT — every namespace a position name is reserved
            against, crossed with every site that mints or declares one.
            (d) is its own axis because both halves accumulate silently: the
            sources were unioned inline with `|` until a fifth (the collection
            nouns) was found by crossing them against the slots that read
            them, and the sites grew from one to three when `board:` landed.
            Two things sit deliberately outside. A quantifier noun is
            grammatically inexpressible as a domain id -- the quantifier
            production is a closed alternative set -- so that slot is out by
            construction rather than by guard, and there is no cell to cover.
            And the reservation product reaches namespaces that share ONE
            slot with a position name; where the two spellings land in
            ADJACENT slots instead it does not reach, and is not meant to.
            Every member of that class is guarded at the slot that reads both
            meanings; whether a slot partition should reserve at all is
            issue #403.
registry:   cardlang/domains.py (built-in rows; DomainSources.positions) +
            n.Game.positions; and, for the reservation product,
            cardlang/resolve.py's `POSITION_NAME_SOURCES` (the namespaces,
            each carrying its own `names(game)`) x `RESERVATION_SITES` (the
            declaring/minting sites). The sweep reads the SOURCE, never the
            guard's own set, so a registry that grows is swept without anyone
            editing this module.
            Owner==index over roles:
            tests/test_zone_index_roles.py::test_owned_zone_owner_arg_must_match_its_index.
            Unowned ownership, `zone_observer_key` -> None and hence the
            `others` projection for every observer:
            tests/openspiel_ready/partition.py.
does not prove:  three things a green here leaves open, each with where it
            IS established if anywhere.
            (1) The canonical gather over a position family. No corpus game
            gathers one, so the order-preserving interaction is stated in
            decisions.md and reasoned about, never executed end to end -- the
            rule is written down, and nothing here runs it.
            (2) That every reserved NAME is refused at every site. The
            source x site grid asks each source with one of its names, not
            all of them. Which name is asked cannot change the answer,
            because the guard tests membership in the source's own set and
            the per-name sweep runs that whole set at the declared site --
            but the product itself is sampled on that axis, and a source
            whose membership test stopped being uniform over its own names
            would pass here.
            (3) `top_of`/`bottom_of` in a move GUARD over a non-identity
            zone. Nothing static reaches it: it is policed per game, and
            dynamically, by the openspiel_ready legal-action-agreement
            proofs. A green in this module says nothing about that case.

`top_of`/`bottom_of` share this module: the sequence-orientation pin
(top = the sequence end, bottom = the front) is what the positional games'
movement semantics rest on.
"""

from __future__ import annotations

import ast
import random
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang import resolve as resolve_mod
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import (
    DomainSources,
    enumerate_domain,
    zone_observer_key,
)
from cardlang.ir import emit
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import (
    POSITION_NAME_SOURCES,
    RESERVATION_SITES,
    _POSITION_MEMBER_CEILING,
)
from cardlang.stdlib.boards import BOARD_FAMILIES, board_entry
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.mechanics import param_domain


def _game(
    positions: str = "positions { column : 1..3 }",
    zones: str = "pile[column] : Cascade<column>",
    stmt: str = "",
    vocab: str = "",
    moves: str = "",
) -> str:
    return (
        "game G {\n"
        "  players: 1\n"
        "  direction: clockwise\n"
        "  max_length: 100\n"
        "  cards: standard52\n"
        f"  {positions}\n"
        "  zones {\n"
        "    deck : Deck\n"
        f"    {zones}\n"
        "  }\n"
        "  state { resigned : Boolean = false\n"
        "          score[player] : Integer = 0 }\n"
        "  phase setup { shuffle deck }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until resigned {\n"
        f"      offer to t one of [quit{vocab}]\n"
        "    }\n"
        f"    {stmt}\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        f"{moves}"
        "move_type quit { effect { resigned := true } }\n"
    )


# --- the declaration's value space ------------------------------------------


def test_single_member_and_zero_based_domains_are_legal() -> None:
    check_dsl(
        _game(positions="positions { column : 1..1  slot : 0..2 }",
              zones="pile[column] : Cascade<column>  s[slot] : Cell<slot>"),
        "t",
    )


def test_member_ceiling_boundary() -> None:
    check_dsl(_game(positions="positions { column : 1..256 }"), "t")  # at the ceiling
    with pytest.raises(DiagnosticError, match="more than the ceiling"):
        check_dsl(_game(positions="positions { column : 1..257 }"), "t")


def test_no_board_family_can_mint_past_the_member_ceiling() -> None:
    """The ceiling's second definition site, reconciled.

    `_resolve_positions` runs the ceiling check on AUTHOR-DECLARED domains
    only: a minted domain's member count comes from the board family, not from
    bounds the author wrote. That leaves the ceiling resting on the family
    registry's argument range — a different registry with a different
    maintainer — so the two are crossed here rather than assumed to agree.
    Every member mints action-space ids, which is what the ceiling counts.

    Measured 2026-08-20: the widest family (`grid`, arguments 1..16) mints 256
    cells against a ceiling of 256 — agreement with no margin, which is exactly
    the shape that breaks in silence when someone widens an argument range.

    red under: lower `_POSITION_MEMBER_CEILING` to 255 (run: "board family
    'grid' at its widest mints 256 cells, past the 255-member ceiling").
    Widening a family's `hi` instead reddens this too, but on an `IndexError`
    from `_cell_name` — `_FILES` runs out of file letters at 16, so a family
    range widened past its own coordinate alphabet fails before the ceiling is
    reached. Recorded because a reddening edit that lands on a neighbouring
    wall proves nothing about this one.
    """
    assert BOARD_FAMILIES, "the board-family registry derived to nothing"
    for name, family in sorted(BOARD_FAMILIES.items()):
        widest = board_entry(name, (family.hi,) * family.arity)
        assert len(widest.cells) <= _POSITION_MEMBER_CEILING, (
            f"board family '{name}' at its widest mints {len(widest.cells)} "
            f"cells, past the {_POSITION_MEMBER_CEILING}-member ceiling a "
            f"DECLARED domain is held to — one registry grew past the other"
        )


# --- the name-source x reservation-site grid ---------------------------------


def _board_game(positions: str = "", zones: str = "", extra: str = "") -> str:
    """A minimal piece-and-board game — the shape the board-only sources need.

    A board mints `cell` and `dir`, and makes `lines(k)` (hence the collection
    quantifier form) writable; a card game reaches none of that, so a probe
    that only ever uses `_game()` cannot see the board-gated sources at all.
    """
    return (
        "game B {\n"
        "  players: 2\n"
        "  max_length: 20\n"
        "  board: grid(3, 3)\n"
        "  pieces: xo_marks\n"
        f"  {positions}\n"
        "  zones { box : Deck  reserve[player] : PlayerPile<player>\n"
        f"          square[cell] : Cell<cell>  {zones} }}\n"
        "  state { result[player] : Integer = 0 }\n"
        "  phase play { move all pieces from box where piece.side is x "
        "to reserve[0] }\n"
        "  winner: highest result\n"
        "}\n"
    ) + extra


@dataclass(frozen=True)
class _SourceProbe:
    """How to give one `ReservedNameSource` something to reserve.

    Only the SETUP lives here: the names themselves are read off the source,
    never listed, so a probe cannot narrow the sweep to the spellings its
    author happened to think of.

    `extra` is the top-level text a game needs before the source holds any
    names at all — empty for the static registries, a `type` declaration for
    the per-game one. `board` says the source answers empty for a card game,
    so the sweep must build the probe on a board fixture or run its cells over
    nothing — the vacuously-green shape this whole grid exists to avoid.
    """

    extra: str = ""
    board: bool = False

    def source_text(self, positions: str = "", zones: str = "") -> str:
        build = _board_game if self.board else _game
        return build(positions=positions, zones=zones) + self.extra

    def zone_type(self) -> str:
        """The zone type a probe indexes by the offending name.

        A board game holds pieces, so its positional family must be a piece
        zone; a card game's must be a card zone. The declared-site sweep needs
        one, because a position domain no zone indexes is not a witness.
        """
        return "Cell" if self.board else "Cascade"


_SOURCE_PROBES: dict[str, _SourceProbe] = {
    "a built-in domain id": _SourceProbe(),
    "a built-in type name": _SourceProbe(),
    "a zone type": _SourceProbe(),
    "a declared type name": _SourceProbe(extra="type R = { a : Integer }\n"),
    "a collection noun": _SourceProbe(board=True),
    # The constructor word reserves for every game — the block's spelling is
    # not conditional on anything a game declares — so the plain recipe is the
    # whole recipe.
    "a collection type constructor": _SourceProbe(),
}

assert _SOURCE_PROBES.keys() == {s.label for s in POSITION_NAME_SOURCES}, (
    "a name source has no probe recipe (or a recipe outlived its source). The "
    "sweep below derives its names from the registry, so an unprobed source is "
    "an unswept namespace — write the recipe rather than shrinking the grid."
)


def _probe_game(label: str) -> n.Game:
    """A parsed game on which the named source holds names.

    Parsed, not resolved: the probe games are deliberately ill-formed (that is
    what they test), and a source's `names` reads declarations the parser has
    already produced.
    """
    return parse_text(_SOURCE_PROBES[label].source_text(), "probe.cardlang")


def _declared_site_cells() -> list[tuple[str, str]]:
    """(source label, reserved name) for every name any source reserves — one
    cell per NAME, derived from the source, so a registry that grows is swept
    without anyone editing this module.

    Every source contributes: a source that reserves only in a board game is
    probed on a board game, so no row runs over an empty name set.
    """
    cells: list[tuple[str, str]] = []
    for source in POSITION_NAME_SOURCES:
        game = _probe_game(source.label)
        names = sorted(source.names(game))
        assert names, (
            f"{source.label} reserves nothing on its probe game, so its cells "
            f"would not exist — fix the probe recipe, not the sweep"
        )
        cells += [(source.label, name) for name in names]
    return cells


@pytest.mark.parametrize("label,name", _declared_site_cells())
def test_every_reserved_name_is_refused_as_a_declared_position_domain(
    label: str, name: str
) -> None:
    """The reconciliation sweep, derived from the SOURCE REGISTRY rather than
    from the guard's own set: every name every source reserves is refused where
    a position domain is declared, and the diagnostic names the source it came
    from.

    Naming the source is what makes the registry load-bearing at runtime and
    not only in this test. The message used to list three namespaces in prose
    while the union already held four — a stale enumeration reads exactly like
    a fresh one, and a designer told "a built-in domain, a zone type, or a
    declared type name" cannot tell which of them they hit.

    Name resolution answers positions BEFORE the other namespaces, so a shared
    spelling does not merely tie: the position wins and the other name becomes
    unreachable at that slot. `function f(x : R) = x.a` then fails with "cannot
    read field 'a' of Integer" — a message about a type the author never wrote.

    red under: return a fixed `"a built-in domain id"` from
    `_reserved_domain_source` instead of `source.label` — every other source's
    cells go red on the label (run: 27 failed, 4 passed).

    A DROPPED source cannot redden a cell here, and that is the point rather
    than a gap: the cells are derived from the registry, so a shrinking
    registry shrinks the grid. What refuses to shrink quietly is
    `_SOURCE_PROBES`' coverage assert above, which fails collection on the
    dropped row — the grid and its probe recipes are held to the registry from
    both sides.
    """
    probe = _SOURCE_PROBES[label]
    with pytest.raises(DiagnosticError, match="collides with") as ei:
        check_dsl(
            probe.source_text(
                positions=f"positions {{ {name} : 1..3 }}",
                zones=f"pile[{name}] : {probe.zone_type()}<{name}>",
            ),
            "t",
        )
    assert label in str(ei.value), (
        f"'{name}' was refused, but the diagnostic did not name {label!r}: "
        f"{ei.value}"
    )


@pytest.mark.parametrize("site", RESERVATION_SITES, ids=lambda s: s.replace(" ", "-"))
@pytest.mark.parametrize(
    "label", [s.label for s in POSITION_NAME_SOURCES], ids=lambda s: s.replace(" ", "-")
)
def test_every_reservation_site_asks_every_name_source(label: str, site: str) -> None:
    """source x site, over the guard itself.

    The matrix is FULL: every reservation site asks the whole registry, and a
    source that reserves only under some condition says so in its own `names`
    rather than by being consulted at some sites and not others. That is the
    property this grid holds the guard to — a per-site source list would be a
    second place for the axis to accumulate, which is the defect the registry
    exists to end, one level up.

    The board fixture is what makes the collection-noun row non-vacuous here:
    that source answers empty for a card game, so asking it with a board game
    is the only way its cells can fail.

    red under: give `_reserved_domain_source` a per-site source filter (any
    source it skips reddens that site's cells).
    """
    source = next(s for s in POSITION_NAME_SOURCES if s.label == label)
    board = parse_text(
        _board_game() + _SOURCE_PROBES[label].extra, "probe.cardlang"
    )
    names = sorted(source.names(board))
    assert names, (
        f"{label} reserves nothing even in a board game, so its cells here "
        f"cannot fail — give the probe a game where the source holds a name"
    )
    reported = resolve_mod._reserved_domain_source(board, names[0], site)
    assert reported == label, (
        f"{site} did not consult {label!r}: '{names[0]}' was reported as "
        f"{reported!r}"
    )


def _type_declaration_cells() -> list[tuple[str, str]]:
    """(source label, reserved name) for the `type` declaration site.

    Derived from the same source registry the declared-position sweep reads,
    minus the one source a `type` declaration IS: type-against-type is the
    self-pair, and `_check_duplicate_names` owns it — a second refusal there
    would co-report on one defect.

    A `type` head is `STRUCT_TYPE_NAME`, which excludes the clause keywords and
    nothing else, so a lower-case domain id is as spellable there as a Title
    Case type name and every remaining source can bind.
    """
    cells: list[tuple[str, str]] = []
    for source in POSITION_NAME_SOURCES:
        if source.label == "a declared type name":
            continue
        game = _probe_game(source.label)
        names = sorted(source.names(game))
        assert names, (
            f"{source.label} reserves nothing on its probe game, so its cells "
            f"would not exist — fix the probe recipe, not the sweep"
        )
        cells += [(source.label, name) for name in names]
    return cells


@pytest.mark.parametrize("label,name", _type_declaration_cells())
def test_every_reserved_name_is_refused_as_a_declared_type(
    label: str, name: str
) -> None:
    """The fourth site, swept from the same registry as the first three.

    A `type` declaration mints a name into the TYPE namespace, and every slot
    that reads one consults the built-ins first — so a struct sharing a
    reserved spelling is declarable and then unusable in every slot, which is
    accepted-but-ignored one step removed (issue #541).

    red under: drop the `type` site's `_reserved_domain_source` call.
    """
    probe = _SOURCE_PROBES[label]
    with pytest.raises(DiagnosticError, match="collides with") as ei:
        check_dsl(
            probe.source_text() + f"\ntype {name} = {{ x : Integer }}\n", "t"
        )
    assert label in str(ei.value), (
        f"'{name}' was refused, but the diagnostic did not name {label!r}: "
        f"{ei.value}"
    )


def test_every_reservation_site_passes_its_own_id() -> None:
    """The site axis is derived from the calls, not from this module's memory.

    `RESERVATION_SITES` says how many sites exist; this scrape says which
    call sites actually pass one. A fourth reservation site added without a
    row in `RESERVATION_SITES` — or a row nobody consults — is exactly the
    silent accumulation the source table was built to end, one axis over.

    red under: add a fourth `_reserved_domain_source(game, X, SOME_SITE)` call
    to `cardlang/resolve.py` without adding `SOME_SITE` to `RESERVATION_SITES`.
    """
    tree = ast.parse(Path(resolve_mod.__file__).read_text())
    passed: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "_reserved_domain_source"):
            continue
        assert len(node.args) == 3, (
            "a reservation call no longer passes its site — the matrix above "
            "cannot see it"
        )
        site_arg = node.args[2]
        assert isinstance(site_arg, ast.Name), (
            "a reservation call passes a computed site rather than one of the "
            "module's site constants, so the scrape cannot classify it"
        )
        passed.add(getattr(resolve_mod, site_arg.id))
    assert passed == set(RESERVATION_SITES), (
        f"the call sites pass {sorted(passed)} but the registry declares "
        f"{sorted(RESERVATION_SITES)}"
    )


def test_the_board_keeps_its_own_minted_spellings() -> None:
    """The exemption, end to end rather than only on the guard.

    A plain board game mints `cell` — a collection noun — and must still
    resolve, and FreeCell declares `positions { cell : 1..4 }` with no board at
    all. This is the negative control for the collection-noun source: read
    without its two narrowings (board games only, minus the board's own minted
    domain) the source refuses the kernel and the corpus their own names, which
    is a far louder failure than the gap it closes.

    Both narrowings are pinned here, one assertion each — the source is
    narrowed twice and a control that only exercises one of them leaves the
    other free to be widened in silence.

    red under: drop the `- {BOARD_DOMAIN}` narrowing (the board's own mint is
    refused), or drop the `game.board is not None` gating (FreeCell's shape and
    a boardless `line` are refused). Both run and observed, each reddening its
    own assertion.
    """
    check_dsl(_board_game(), "t")  # the kernel keeps its minted `cell`
    # FreeCell's shape: a boardless `cell` domain, which no collection form can
    # be written against.
    check_dsl(
        _game(
            positions="positions { cell : 1..4 }",
            zones="pile[cell] : Cascade<cell>",
        ),
        "t",
    )
    # ...and the same for `line`, the noun with no minted twin: boardless, it
    # means one thing, so the source must not claim it.
    check_dsl(
        _game(
            positions="positions { line : 1..3 }",
            zones="pile[line] : Cascade<line>",
        ),
        "t",
    )


def test_excluding_the_minted_domain_leaves_its_own_guard_standing() -> None:
    """The other half of that exemption: excluding `cell` from the
    collection-noun source must not remove a wall.

    A declared `positions { cell : ... }` beside a board is still refused — by
    `_resolve_board`, whose message names BOTH sites and tells the author which
    one to rename. That is the reason for the exclusion, so it is asserted
    rather than assumed: without this cell, narrowing the source reads as a way
    to make a corpus game pass rather than as a deferral to a better-placed
    guard.

    red under: delete the `BOARD_DOMAIN in declared_positions` (or
    `DIRECTION_DOMAIN in declared_positions`) arm from `resolve._resolve_board`.
    """
    for minted in ("cell", "dir"):
        with pytest.raises(DiagnosticError, match="rename the declared domain"):
            check_dsl(
                _board_game(
                    positions=f"positions {{ {minted} : 1..3 }}",
                    zones=f"strip[{minted}] : Cell<{minted}>",
                ),
                "t",
            )


@pytest.mark.parametrize(
    "source,message",
    [("lines(3)", "reads the board"), ("box", "iterates a collection of lines")],
)
def test_the_collection_quantifier_form_is_unwritable_without_a_board(
    source: str, message: str
) -> None:
    """Why the collection-noun source reserves in board games ONLY.

    The narrowing rests on a claim about REACH: in a boardless game the
    collection form cannot be written, so the noun carries one meaning and
    reserving it would take a name — FreeCell's `cell` — that nothing else can
    claim. The claim has two legs and both are run, because a source narrowed
    on an unchecked premise is the same defect as an axis listed by hand:
    `lines(k)` is board-only, and no other expression types as the collection
    of lines the form demands.

    red under: drop `lines` from `builtins.functions.BOARD_ONLY_CALL_FUNCS`, or
    give `typecheck._COLLECTION_BINDER_TYPES` an arm accepting a card
    collection.
    """
    with pytest.raises(DiagnosticError, match=message):
        check_dsl(
            _game(
                positions="positions { line : 1..3 }",
                zones="pile[line] : Cascade<line>  box : Deck",
                stmt=f"if any line in {source} where true {{ resigned := true }}",
            ),
            "t",
        )


@pytest.mark.parametrize("minted", ["cell", "dir"])
def test_a_declared_type_may_not_take_a_minted_domains_spelling(minted: str) -> None:
    """The two board sites, exercised through the source that can reach them.

    Only the per-game source can hold `cell` or `dir`: no built-in id, type
    name or zone type is spelled that way, so those cells of the matrix have no
    name to collide with and are recorded in the ledger rather than asserted
    here. A `type dir = { … }` beside a board would otherwise resolve clean
    while `along : dir` silently read the minted domain — direction lookup
    precedes struct lookup — which is one spelling meaning two things.

    red under: replace `minted_clash` (or `direction_clash`) in
    `resolve._resolve_board` with `None` — run, and each plant reddens its own
    cell alone (1 failed, 1 passed).
    """
    with pytest.raises(DiagnosticError, match="collides with a declared type name"):
        check_dsl(_board_game(extra=f"type {minted} = {{ a : Integer }}\n"), "t")


# --- enumeration agreement (runtime = static) --------------------------------


_PARAM_GAME = _game(
    vocab=", mv",
    moves=(
        "move_type mv(c : column, d : column) {\n"
        "  when: c is not d\n"
        "  effect { resigned := true }\n"
        "}\n"
    ),
)


def test_runtime_and_static_member_enumeration_agree() -> None:
    game = check_dsl(_PARAM_GAME, "t")
    static = enumerate_domain(
        "column",
        DomainSources(
            suits=(), ranks=(), players=(0,),
            positions={p.name: p.members for p in game.positions},
        ),
    )
    assert static == [1, 2, 3]

    seen: dict[str, list[object]] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        seen["candidates"] = list(candidates)
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(game, random.Random(0), chooser=chooser)
    # The guard-filtered cross-product, declaration order, c-major — and the
    # runtime enumerated the same 1..3 members the static space did.
    assert [c for c in seen["candidates"] if c != ("quit", None)] == [
        ("mv", (1, 2)), ("mv", (1, 3)),
        ("mv", (2, 1)), ("mv", (2, 3)),
        ("mv", (3, 1)), ("mv", (3, 2)),
    ]


def test_param_domain_reads_the_live_position_table() -> None:
    from cardlang.runtime.state import Ctx, RuntimeState

    game = check_dsl(_PARAM_GAME, "t")
    mv = next(m for m in game.move_types if m.name == "mv")

    captured: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(
        game, random.Random(0), chooser=chooser,
        on_first_decision=lambda rs: captured.__setitem__("rs", rs),
    )
    ctx = Ctx(rs=captured["rs"], chooser=chooser)
    assert param_domain(mv.params[0], 0, ctx) == [1, 2, 3]


# --- ownership: positions are unowned ----------------------------------------


def test_positions_are_unowned_for_every_observer() -> None:
    from cardlang.runtime.state import RuntimeState

    game = check_dsl(_game(), "t")
    captured: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(
        game, random.Random(0), chooser=chooser,
        on_first_decision=lambda rs: captured.__setitem__("rs", rs),
    )
    # No observer has a key of their own in a position domain, so ownership
    # never matches and every observer projects the zone type's `others`
    # column (runtime observe._is_owner and the proof oracle both read this
    # one function).
    assert zone_observer_key("column", captured["rs"], 0) is None


# --- the runtime Shadow Guard behind the bare-reference guard ---------------------


@pytest.mark.expects_shadow_guard
def test_bare_position_family_read_is_a_typed_runtime_error() -> None:
    """`resolve._check_position_family_refs` is the Owner Guard for the DSL
    spelling (rejection corpus); this Shadow Guard must fail typed — never a
    phantom-key KeyError — if a construction path ever bypasses it.

    Marked `expects_shadow_guard`: constructing one is the engine gap the
    suite-wide Pin catches, and this test does it deliberately.
    """
    from cardlang.ast import nodes as n
    from cardlang.runtime.evaluate import evaluate
    from cardlang.runtime.state import Ctx, RuntimeState

    game = check_dsl(_game(), "t")
    captured: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(
        game, random.Random(0), chooser=chooser,
        on_first_decision=lambda rs: captured.__setitem__("rs", rs),
    )
    ctx = Ctx(rs=captured["rs"], chooser=chooser).acting_as(0)
    ref = n.NameRef("pile", ref_kind="zone")
    with pytest.raises(ShadowGuardError, match="must be subscripted") as caught:
        evaluate(ref, ctx)
    assert caught.value.leaked == "resolve._check_position_family_refs"


# --- `to each` over a position family (the existing guard owns the class) -----


def test_to_each_position_family_is_rejected() -> None:
    with pytest.raises(DiagnosticError, match="deals one parcel per player"):
        check_dsl(
            _game(stmt="deal 1 card from deck to each pile"),
            "t",
        )


@pytest.mark.parametrize(
    "zones",
    [
        "pile[column] : Cascade<slot>",  # a different position domain
        "pile[column] : Cascade<player>",  # a role, not the index position
    ],
)
def test_position_family_owner_arg_must_match_its_index(zones: str) -> None:
    # The type-arg slot's MISUSE. A position family is keyed by its index
    # position, so an owner argument naming a different position — or a role —
    # is accepted-but-ignored. Distinct from the projection-uniformity guard
    # (a non-uniform type like Hand on a position index): here the type is
    # uniform (Cascade), only the argument's domain is wrong. The role-indexed
    # counterpart (`hand[player] : Cascade<column>`) and the general guard live
    # in tests/test_zone_index_roles.py and the rejection corpus.
    with pytest.raises(
        DiagnosticError, match="must name the same domain as the index"
    ):
        check_dsl(
            _game(zones=zones, positions="positions { column : 1..3  slot : 1..3 }"),
            "t",
        )


def test_role_indexed_family_may_not_take_a_position_owner_arg() -> None:
    # The fourth (role, position) direction: a role-indexed family with a
    # position type arg (`foo[player] : Cascade<column>`). Same guard — the
    # family keys by the player index and the `<column>` is ignored. (`pile`
    # keeps `column` a validly-used position so nothing else complains.)
    with pytest.raises(
        DiagnosticError, match="must name the same domain as the index"
    ):
        check_dsl(
            _game(zones="pile[column] : Cascade<column>  foo[player] : Cascade<column>"),
            "t",
        )


def test_position_move_param_types_as_integer_not_any() -> None:
    # A move parameter may be a position domain (`build(src : column)`); the
    # move-binder env must carry the game's positions so the param types as the
    # integer member it binds. Were that env a fresh TypeEnv() with no
    # positions, the param would type TAny and a wrong-domain use like `src is
    # hearts` would pass typecheck — accepted-but-ignored. The valid integer
    # uses (family subscript, integer comparison) still check.
    with pytest.raises(DiagnosticError, match="comparing Suit with Integer"):
        check_dsl(
            _game(
                vocab=", poke",
                moves="move_type poke(src : column) { when: src is hearts "
                "effect { resigned := true } }\n",
            ),
            "t",
        )
    check_dsl(
        _game(
            vocab=", poke",
            moves="move_type poke(src : column) { when: pile[src] is empty "
            "effect { resigned := true } }\n",
        ),
        "t",
    )


# --- IR ----------------------------------------------------------------------


def test_positions_appear_in_the_ir() -> None:
    game = check_dsl(_game(), "t")
    assert emit(game)["positions"] == [
        {"kind": "position", "name": "column", "lo": 1, "hi": 3}
    ]


# --- top_of / bottom_of: the sequence-orientation pin ------------------------


def test_top_is_the_sequence_end_and_bottom_the_front() -> None:
    """The orientation the positional movement semantics rest on
    (decisions.md, sequence orientation): arrivals append at the end, so
    `top_of` reads the last arrival and `bottom_of` the first; an empty
    collection and a non-card element each fail typed at the cause."""
    from cardlang.runtime.evaluate import native_call
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.values import Card, Seating

    game = check_dsl(_game(), "t")
    zones = ZoneStore(game.zones, (0,), positions={"column": (1, 2, 3)})
    rs = RuntimeState(Seating(1), zones, random.Random(0))
    rs.position_domains = {"column": (1, 2, 3)}
    pile = zones.instance("pile", 1)
    pile.add(Card("2", "spades"))
    pile.add(Card("A", "spades"))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: c[:k])

    assert native_call("top_of", [pile], ctx) == Card("A", "spades")
    assert native_call("bottom_of", [pile], ctx) == Card("2", "spades")
    with pytest.raises(OwnerGuardError, match="the collection is empty"):
        native_call("top_of", [zones.single("deck")], ctx)
    with pytest.raises(OwnerGuardError, match="expects a collection of cards"):
        native_call("top_of", [[1, 2]], ctx)
