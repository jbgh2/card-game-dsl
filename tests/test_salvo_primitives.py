"""Salvo's combo table: the grid for the declared Primitive `salvo_combos`.

Salvo (`experiments/salvo/`) scores an army's own structure on top of the
per-card proximity and affinity its game file computes in the DSL. The table is
`experiments/salvo/DESIGN.md`, "Rules (full game)" — the authority every
expected value below is read from — and `cardlang/runtime/salvo.py` is the
Python the game declares in its own `primitives { }` block.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   an army's combo bonus is DESIGN.md's table: three independent
            families (of-a-kind, run, flush), each scoring at most once and on
            its LARGEST instance only, summed; one card may serve several
            families; a joker serves none, and the exclusion happens before
            every family so no joker can pair by rank or extend a run or a
            flush. The wrapper maps its Integer argument onto exactly the
            three army families the declaration reads, and refuses any other.
domain:     family x size, crossed with the exclusion axis. FAMILY is the
            closed set the table names (of-a-kind, run, flush); SIZE is each
            family's own closed ladder (of-a-kind 1..4, run <3 / 3 / 4 / >=5,
            flush <3 / 3 / 4 / >=5), taken at the rung and at both its
            boundaries; EXCLUSION is {no joker, joker present} over the shape
            each family would otherwise score. Adjacency carries its own
            sub-axis, because the run family is the one whose scale is a
            declared fact rather than a card fact: the low boundary (A-2-3),
            the high non-boundary (Q-K-A, refused — the scale is linear), the
            interior gap, the duplicate-rank collapse, and the joker's SLOT on
            that scale — Salvo's own ranking puts it where the two readings
            coincide, so the cell that separates them carries its own scale.
            Composition is the crossing of the three families on one army,
            sampled at DESIGN.md's own worked example and at the empty army.
registry:   the ladders are DESIGN.md's table, transcribed here rather than
            derived — deriving them from `cardlang.runtime.salvo` would
            measure the implementation against itself. The rank scale is the
            game's declared `ranking:`, read through `check_source` on
            `experiments/salvo/salvo.cardlang` so the fixture cannot drift
            into a private copy of the order; the family names the wrapper
            maps onto are the `reads` clause of that same file's block.
covered:    every cell below, parametrized. The declaration's agreement with
            the implementation — existence, contract, and signature shape —
            is tests/test_primitives_block.py's reconciliation pin, whose
            domain is every game that declares a block, this one among them;
            that the game as a whole plays with the Primitive in it is the
            arena rig's mirror pin
            (`experiments/salvo/triage.py`), which restates the table
            independently and compares on every playout. That the rigs' table
            IS a second authoring — never an import of the module it mirrors,
            which would make the comparison one statement against itself — is
            a property of their source rather than of this domain, and carries
            its own ledger at the pin that scrapes them.
sampled:    the of-a-kind ladder's top rung is `>= 4` rather than exactly 4:
            standard54 holds four cards of a natural rank, so five is
            unreachable from any deal and the rung is written as a floor.
does not prove: nothing here says the VALUES are right. They are DESIGN.md's
            starting values, declared there as "expected to move at the
            simulation step"; this grid pins that the code computes the table
            the design states, and the arena's combo-incidence instrumentation
            is what will move it. And the "five or longer" rungs of the run
            and flush ladders are unreachable in play — a location holds at
            most four of one player's cards — so they are proven on synthetic
            five-card inputs only, which is the designed table rather than the
            reachable one (the game does not bend to the harness).

Red under the stub, replayed 2026-08-29 at this module's current width: the
bare run while `cardlang/runtime/salvo.py` holds its five functions as
`NotImplementedError` signatures and nothing else — `45 failed, 3 passed`.
Every combo cell fails on its own call rather than on one collection error, so
each names the behaviour it wants; the three that pass are the rig-mirror pins
at the foot of this module, which read the rigs' own source and never the
module the stub replaces.

red under: one mutation of `cardlang/runtime/salvo.py` per family, each run
    rather than argued — pair 4 -> 5 (13 failed); the run scale keeping the
    joker rank (1 failed, and only the joker-slot cell, which is why that cell
    exists); flush of three 5 -> 6 (10 failed); `naturals()` returning its
    argument (6 failed); the wrapper taking `loc % 3` instead of refusing
    (3 failed); of-a-kind scoring every instance rather than the largest
    (2 failed).
"""

from __future__ import annotations

import ast
import pathlib
import random

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime import narrowing, reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.salvo import (
    combo_score,
    flush_bonus,
    of_a_kind_bonus,
    run_bonus,
    salvo_combos,
)
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

GAME = "experiments/salvo/salvo.cardlang"


def _rank_index() -> dict[str, int]:
    """The driver's `rank_index` for Salvo's declared `ranking:` — read from
    the game file through the checker, the same order the runtime builds."""
    order = check_source(GAME).ranking
    return {r: len(order) - 1 - i for i, r in enumerate(order)}


RIDX = _rank_index()


def _cards(*spec: str) -> list[Card]:
    """`"7s"` -> the seven of spades; `"Jk"` -> a joker."""
    suits = {"c": "clubs", "d": "diamonds", "h": "hearts", "s": "spades"}
    out: list[Card] = []
    for item in spec:
        if item == "Jk":
            out.append(Card("Joker", "joker"))
        else:
            out.append(Card(item[:-1], suits[item[-1]]))
    return out


# --- of-a-kind: pair 4, three 12, four 20; the largest instance only --------
#
# Every input isolates the family: no three cards share a suit and no three
# ranks are consecutive, so a nonzero answer can only come from of-a-kind.

_OF_A_KIND: dict[str, tuple[tuple[str, ...], int]] = {
    "none": (("7s", "9h", "Jd"), 0),
    "pair": (("7s", "7h"), 4),
    "trips": (("7s", "7h", "7d"), 12),
    "quads": (("7s", "7h", "7d", "7c"), 20),
    "two-pairs-score-once": (("7s", "7h", "9s", "9h"), 4),
    "trips-do-not-also-score-their-pair": (("7s", "7h", "7d", "9c"), 12),
}


@pytest.mark.parametrize("case", sorted(_OF_A_KIND))
def test_of_a_kind_ladder(case: str) -> None:
    spec, expected = _OF_A_KIND[case]
    assert of_a_kind_bonus(_cards(*spec)) == expected


@pytest.mark.parametrize("case", sorted(_OF_A_KIND))
def test_of_a_kind_cells_isolate_their_family(case: str) -> None:
    """The isolation the ladder above depends on, asserted rather than
    assumed: each of-a-kind input scores nothing in the other two families, so
    `combo_score` returns the ladder's own value."""
    spec, expected = _OF_A_KIND[case]
    cards = _cards(*spec)
    assert run_bonus(cards, RIDX) == 0 and flush_bonus(cards) == 0
    assert combo_score(cards, RIDX) == expected


# --- runs: three 6, four 10, five or longer 15; the longest run only --------

_RUNS: dict[str, tuple[tuple[str, ...], int]] = {
    "none": (("7s", "9h", "Jd"), 0),
    "gap": (("7s", "8h", "10d"), 0),
    "three": (("7s", "8h", "9d"), 6),
    "four": (("7s", "8h", "9d", "10c"), 10),
    # Five cards exceed a location's capacity of four: the rung is designed,
    # not reachable, and is proven on the synthetic input.
    "five": (("6s", "7h", "8d", "9c", "10s"), 15),
    "duplicate-rank-collapses": (("7s", "7h", "8d", "9c"), 6),
    "ace-low-boundary": (("As", "2h", "3d"), 6),
    "no-wraparound-at-the-top": (("Qs", "Kh", "Ad"), 0),
}


@pytest.mark.parametrize("case", sorted(_RUNS))
def test_run_ladder(case: str) -> None:
    spec, expected = _RUNS[case]
    assert run_bonus(_cards(*spec), RIDX) == expected


def test_adjacency_ignores_where_the_ranking_puts_the_joker() -> None:
    """The scale a run reads is the natural ranks, whatever slot the declared
    `ranking:` gives the joker.

    Salvo's own ranking puts it at the head, where dropping it shifts every
    natural rank uniformly and adjacency is unchanged either way — so this
    cell states the property on a scale where the two readings DIFFER,
    without which the exclusion in `run_bonus` could not be observed to
    matter at all."""
    order = ("K", "Q", "J", "10", "9", "8", "Joker", "7", "6", "5", "4", "3", "2", "A")
    joker_in_the_middle = {r: len(order) - 1 - i for i, r in enumerate(order)}
    assert run_bonus(_cards("7s", "8h", "9d"), joker_in_the_middle) == 6


# --- flushes: three 5, four 9, five or longer 14; the longest flush only ----

_FLUSHES: dict[str, tuple[tuple[str, ...], int]] = {
    "none": (("7s", "9h", "Jd"), 0),
    "two-is-not-a-flush": (("7s", "9s", "Jd"), 0),
    "three": (("7s", "9s", "Js"), 5),
    "four": (("7s", "9s", "Js", "Ks"), 9),
    # As with the run ladder's fifth rung: designed, not reachable in play.
    "five": (("5s", "7s", "9s", "Js", "Ks"), 14),
}


@pytest.mark.parametrize("case", sorted(_FLUSHES))
def test_flush_ladder(case: str) -> None:
    spec, expected = _FLUSHES[case]
    assert flush_bonus(_cards(*spec)) == expected


# --- the joker exclusion, through `combo_score` -----------------------------
#
# The exclusion is an ORDERING property of the whole core, not of any one
# family: the filter must run before every family, so each cell is a shape
# that WOULD score if the joker counted.

_JOKERS: dict[str, tuple[tuple[str, ...], int]] = {
    # Both jokers carry the rank "Joker", so an unfiltered pair scores 4.
    "two-jokers-are-not-a-pair": (("Jk", "Jk"), 0),
    # Joker sits at the head of the declared ranking, adjacent to K: an
    # unfiltered run scan reads K-Q-Joker as a run of three.
    "a-joker-does-not-extend-a-run-at-the-scale-head": (("Jk", "Ks", "Qh"), 0),
    "a-joker-does-not-complete-a-run": (("Jk", "7s", "8h"), 0),
    "a-joker-does-not-extend-a-flush": (("Jk", "7s", "9s"), 0),
    "a-joker-does-not-join-a-pair": (("Jk", "7s", "7h"), 4),
    # The exclusion removes the joker and nothing else.
    "a-joker-beside-a-scoring-army": (("Jk", "7s", "8s", "9s"), 11),
}


@pytest.mark.parametrize("case", sorted(_JOKERS))
def test_joker_exclusion(case: str) -> None:
    spec, expected = _JOKERS[case]
    assert combo_score(_cards(*spec), RIDX) == expected


# --- composition: one card serves several families -------------------------

_COMPOSED: dict[str, tuple[tuple[str, ...], int]] = {
    # DESIGN.md's own worked example: pair 4 + run of three 6 + flush of
    # three 5 = 15.
    "the-design-note-example": (("7s", "7h", "8s", "9s"), 15),
    "empty-army": ((), 0),
    "one-card": (("7s",), 0),
}


@pytest.mark.parametrize("case", sorted(_COMPOSED))
def test_composition(case: str) -> None:
    spec, expected = _COMPOSED[case]
    assert combo_score(_cards(*spec), RIDX) == expected


def test_the_worked_example_is_the_sum_of_its_three_families() -> None:
    """The composition rule stated as the decomposition DESIGN.md gives: the
    example's 15 is 4 + 6 + 5, not one family's 15."""
    cards = _cards("7s", "7h", "8s", "9s")
    assert (of_a_kind_bonus(cards), run_bonus(cards, RIDX), flush_bonus(cards)) == (4, 6, 5)


# --- the wrapper: the Integer argument's domain is the three armies ---------


def _zone_decls() -> tuple[n.ZoneDecl, ...]:
    return tuple(
        n.ZoneDecl(name=f"army_{loc}", index="player", type_ref=n.TypeRef(name="PlayerPile"))
        for loc in ("a", "b", "c")
    )


def _row() -> reads.PrimitiveReads:
    """The row the game's `reads army_a[p], army_b[p], army_c[p]` declares —
    read from the block itself, so the fixture cannot declare reads the game
    does not."""
    game = check_source(GAME)
    assert game.primitives is not None
    decl = next(d for d in game.primitives.decls if d.name == "salvo_combos")
    return reads.PrimitiveReads(
        module="cardlang/runtime/salvo.py",
        game_file="salvo.cardlang",
        zone_families=frozenset(r.name for r in decl.reads),
    )


def _bundles(
    armies: dict[str, dict[int, list[Card]]], p: int
) -> tuple[narrowing.EngineFacts, reads.GameReads]:
    rs = RuntimeState(Seating(2), ZoneStore(_zone_decls(), (0, 1)), random.Random(0))
    rs.rank_index = RIDX
    for family, per_player in armies.items():
        for player, cards in per_player.items():
            rs.zones.instance(family, player).add_all(cards)
    # The declared clause is indexed by `p`, so the call materializes the one
    # instance it names — the same keying the dispatch performs.
    return narrowing.bind(rs, None, _row(), {name: p for name in ("army_a", "army_b", "army_c")})


_LOC_FAMILY: dict[int, str] = {0: "army_a", 1: "army_b", 2: "army_c"}


@pytest.mark.parametrize("loc", sorted(_LOC_FAMILY))
def test_wrapper_reads_the_army_its_argument_names(loc: int) -> None:
    """Each location's Integer reads that location's army and no other: the
    named family holds the worked example (15), the other two a lone card."""
    armies: dict[str, dict[int, list[Card]]] = {
        family: {0: _cards("7s") if family != _LOC_FAMILY[loc] else _cards("7s", "7h", "8s", "9s")}
        for family in _LOC_FAMILY.values()
    }
    assert salvo_combos(*_bundles(armies, 0), 0, loc) == 15


@pytest.mark.parametrize("loc", sorted(_LOC_FAMILY))
def test_wrapper_reads_the_player_it_is_asked_about(loc: int) -> None:
    """The seat is the call's argument, not the acting player: player 1's
    army scores and player 0's does not."""
    armies = {
        family: {0: _cards("7s"), 1: _cards("7s", "7h", "8s", "9s")}
        for family in _LOC_FAMILY.values()
    }
    assert salvo_combos(*_bundles(armies, 1), 1, loc) == 15


@pytest.mark.parametrize("loc", [-1, 3, 99])
def test_wrapper_refuses_a_location_outside_the_three(loc: int) -> None:
    """The Integer type admits every integer; the three locations are the
    domain, and one outside it is refused by name rather than answered from
    whichever family a modulus would land on.

    In the game author's channel: a designer writing `salvo_combos(p, 3)`
    typechecks — nothing statically bounds an Integer — so this guard is the
    one statement of which three mean something, and it addresses the person
    who can fix it."""
    armies = {family: {0: _cards("7s")} for family in _LOC_FAMILY.values()}
    with pytest.raises(OwnerGuardError) as exc:
        salvo_combos(*_bundles(armies, 0), 0, loc)
    assert "salvo_combos" in str(exc.value) and "0..2" in str(exc.value)


# --- the rig mirrors are a second authoring, not a second reference ---------

_SALVO_DIR = pathlib.Path(GAME).resolve().parent
_MIRRORS = ("triage.py", "probe_liveness.py")
_RUNTIME_MODULE = "cardlang.runtime.salvo"


def _imported_modules(path: pathlib.Path) -> frozenset[str]:
    """Every module one rig imports, as `ast` reads it: the dotted name of an
    `import x.y`, the module of a `from x.y import z`, and that module joined
    to each imported name so `from cardlang.runtime import salvo` is seen for
    what it is.

    Parsed, never searched. `triage.py`'s own docstring names
    `cardlang/runtime/salvo.py` — it is the file saying it must not import it —
    so a substring scrape would report the prose it exists to protect."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return frozenset(names)


@pytest.mark.parametrize("rig", _MIRRORS)
def test_a_rig_mirror_imports_no_salvo_runtime(rig: str) -> None:
    """The rigs' combo scorer is a SECOND authoring of DESIGN.md's table, and
    the arena's mirror-drift assertions compare it against the DSL's settle
    math on every playout. An import of `cardlang/runtime/salvo.py` would make
    those two statements one statement compared with itself — every playout
    still green, and the differential gone.

    property:   neither rig imports the module the game declares, by any
                spelling `ast` can see.
    domain:     the two rig modules under `experiments/salvo/` that run the
                game; the sibling test below is what keeps their own
                cross-imports inside that domain.
    registry:   the file names above. They are the whole rig surface, so the
                domain is listed rather than globbed — a third rig is a new
                row here, and the glob in the sibling test is what makes that
                omission fail rather than pass.
    does not prove: only that the import is absent from these two files. A
                module they import from OUTSIDE their own directory could
                still reach the runtime module; the LLM rigs reach for `grimp`
                where that matters, and here the two files are short enough to
                read.

    red under: add `from cardlang.runtime.salvo import combo_score` to either
    rig."""
    imports = _imported_modules(_SALVO_DIR / rig)
    assert any(m.startswith("cardlang.") for m in imports), (
        f"{rig}: the scrape found no `cardlang` import at all — it would not "
        f"see {_RUNTIME_MODULE} either"
    )
    assert _RUNTIME_MODULE not in imports, (
        f"{rig} imports {_RUNTIME_MODULE}: the mirror and the engine would be "
        f"one authoring, and the arena's drift assertions would compare it "
        f"with itself"
    )


def test_the_mirror_scrape_covers_every_rig_module_the_rigs_reach() -> None:
    """The pin above is per-FILE, and `probe_liveness.py` reaches the game
    through `triage`. This is what makes that hop part of the scrape rather
    than an assumption about it: every module a rig imports from its own
    directory is itself a scraped rig, so no third file can become the route.

    red under: add `import tune_sighted` to either rig."""
    scraped = {pathlib.Path(m).stem for m in _MIRRORS}
    local = {p.stem for p in _SALVO_DIR.glob("*.py")}
    assert local - scraped, "every rig module is scraped; the glob proves nothing"
    for rig in _MIRRORS:
        reached = {m for m in _imported_modules(_SALVO_DIR / rig) if m in local}
        assert reached <= scraped, (
            f"{rig} imports the unscraped rig module(s) {sorted(reached - scraped)} "
            f"— add them to `_MIRRORS` or the hop leaves the domain"
        )
