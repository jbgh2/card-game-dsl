"""The subset binder's coverage grid: `subsets of <k> [or more] cards in <zone>`.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   every sentence the subset productions accept has the value the
            surface plainly says, and every sentence they do not accept meets a
            diagnostic in the layer that owns it -- never a silent parse to a
            different meaning, and never an unbounded enumeration.
domain:     the three closed value domains the construct declares, crossed:
            `SUBSET_QUERY_KINDS` x `SUBSET_SIZE_MODES` for the query register,
            `SUBSET_AGGREGATORS` x `SUBSET_SIZE_MODES` for the aggregation
            register, each over the source shapes `zone_expr` can actually
            produce (a zone name, a zone-family subscript, a `let`-bound
            collection -- `NameRef` and `Subscript` are the only two shapes the
            production admits), the filter axis where the grammar leaves it
            free, the count operand at its boundaries, and the source pool at
            the enumeration bound. Crossed separately, and deliberately: the
            value the binder produces against every operation that consumes a
            card collection, because a new value shape's defects live in its
            products with the constructs that already exist.
            Two boundaries, stated positively. The construct is card-flavored:
            a piece game meets `CardQuery`/`Comprehension`'s own refusal, which
            this inherits rather than restates. And the size clause is
            mandatory in both modes -- there is no unbounded-size spelling, so
            no cell asks what one would mean.
registry:   the axes are `cardlang.ast.nodes.SUBSET_QUERY_KINDS`,
            `SUBSET_AGGREGATORS` and `SUBSET_SIZE_MODES`, read here rather than
            spelled out; the source-shape axis is the `zone_expr` production
            (cardlang/grammar/cardlang.lark). The enumeration bound and its
            refusal are `cardlang.runtime.subsets`. The binder's presence in
            the lexical-scoping table is pinned at
            tests/test_binder_scoping.py::test_every_binding_node_kind_scopes_its_binder.
            The node's membership in the typed-position and state-default
            populations is pinned at tests/test_typed_positions.py and
            tests/test_state_default_scope.py, which derive their populations
            from the `Expr` union.
does not prove:  that the enumeration is fast enough for a pool at the bound.
            The bound is a non-termination backstop, not a performance budget:
            a 16-card pool admits 65,535 subsets, each a full `evaluate()`, and
            nothing here measures that. What is measured is that 17 refuses.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# --- the fixture: a four-card table of known content ------------------------
# The deal is filtered, so the table holds exactly the four 7s and hand[0] the
# four 6s. Every expected value below is arithmetic over those two facts.
_TABLE_SIZE = 4


def game(body: str, *, table_rank: str = "7", extra: str = "") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player>\n"
        "          spare : Discard }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        "  phase p {\n"
        "    move all cards to deck\n"
        f'    move all cards from deck where card.rank is "{table_rank}" to table\n'
        '    move all cards from deck where card.rank is "6" to hand[0]\n'
        f"{extra}"
        f"{body}\n"
        "  }\n"
        "}\n"
    )


def probe_value(body_expr: str, **kw: Any) -> int:
    """Run a one-phase game whose only job is to compute `body_expr` into
    the score slot, and return what it computed."""
    src = game(f"    score[0] := {body_expr}", **kw)
    result = play_game(check_dsl(src, "grid.cardlang"), rng=random.Random(0))
    return int(result.scores[0])


def probe_bool(body_expr: str, **kw: Any) -> bool:
    return probe_value(f"if {body_expr} then 1 else 0", **kw) == 1


# --- Grid A: the query register x size mode x source shape ------------------
# `number of cards in subset` is the body throughout: it reads the binder as a
# card collection, so each cell also exercises the pairwise interaction that
# makes the binder useful at all.

_SOURCES = {
    "zone": ("table", ""),
    "subscript": ("hand[0]", ""),
    "let": ("held", "    let held = cards in table where 1 is 1\n"),
}

# Expected values over a four-card source.
#   exact 2 -> C(4,2) = 6 subsets, every one of size 2
#   floor 2 -> 2^4 - 1 - 4 = 11 subsets, sizes 2..4
#
# Each cell carries its own predicate, chosen so the cell can DISCRIMINATE the
# axis it crosses. The counting cells take a tautology, because what separates
# the two size modes is the size of the domain itself (6 against 11) — a
# predicate that admits only size-2 subsets would answer 6 in both modes and
# the cell would be green without measuring the axis. The `any`/`all` cells
# take the opposite predicate, "this subset has exactly two cards", because
# what separates those two folds is a domain where some members satisfy and
# some do not.
_TAUTOLOGY = "1 is 1"
_IS_A_PAIR = "(number of cards in subset) is 2"

_QUERY_CELLS: list[tuple[str, str, str, str, int | bool]] = [
    (n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_EXACT, src, _TAUTOLOGY, 6) for src in _SOURCES
] + [
    (n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_FLOOR, src, _TAUTOLOGY, 11) for src in _SOURCES
] + [
    (n.SUBSET_KIND_ANY, n.SUBSET_SIZE_EXACT, "zone", _IS_A_PAIR, True),
    (n.SUBSET_KIND_ALL, n.SUBSET_SIZE_EXACT, "zone", _IS_A_PAIR, True),
    (n.SUBSET_KIND_ANY, n.SUBSET_SIZE_FLOOR, "zone", _IS_A_PAIR, True),
    (n.SUBSET_KIND_ALL, n.SUBSET_SIZE_FLOOR, "zone", _IS_A_PAIR, False),
]


def _size_clause(mode: str, k: int) -> str:
    return f"{k} or more cards" if mode == n.SUBSET_SIZE_FLOOR else f"{k} cards"


def _query_sentence(kind: str, mode: str, source: str, pred: str) -> str:
    size = _size_clause(mode, 2)
    if kind == n.SUBSET_KIND_ANY:
        return f"any subset of {size} in {source} where {pred}"
    if kind == n.SUBSET_KIND_ALL:
        return f"all subsets of {size} in {source} where {pred}"
    return f"number of subsets of {size} in {source} where {pred}"


@pytest.mark.parametrize("kind,mode,source,pred,expected", _QUERY_CELLS)
def test_query_register(
    kind: str, mode: str, source: str, pred: str, expected: int | bool
) -> None:
    name, extra = _SOURCES[source]
    sentence = _query_sentence(kind, mode, name, pred)
    if isinstance(expected, bool):
        assert probe_bool(sentence, extra=extra) is expected
    else:
        assert probe_value(sentence, extra=extra) == expected


def test_the_query_axis_is_the_whole_registry() -> None:
    """The grid's kind axis is the registry, not a list kept beside it."""
    assert {kind for kind, _, _, _, _ in _QUERY_CELLS} == n.SUBSET_QUERY_KINDS
    assert {mode for _, mode, _, _, _ in _QUERY_CELLS} == n.SUBSET_SIZE_MODES


# --- Grid B: the aggregation register x size mode ---------------------------
# Body is `number of cards in subset` again, so the folds are over subset SIZES:
#   exact 2 -> six subsets of size 2      => sum 12, highest 2, lowest 2
#   floor 2 -> sizes 2 (x6), 3 (x4), 4 (x1) => sum 12+12+4 = 28, highest 4, lowest 2
_AGG_CELLS: list[tuple[str, str, int]] = [
    (n.SUBSET_AGG_SUM, n.SUBSET_SIZE_EXACT, 12),
    (n.SUBSET_AGG_SUM, n.SUBSET_SIZE_FLOOR, 28),
    (n.SUBSET_AGG_HIGHEST, n.SUBSET_SIZE_EXACT, 2),
    (n.SUBSET_AGG_HIGHEST, n.SUBSET_SIZE_FLOOR, 4),
    (n.SUBSET_AGG_LOWEST, n.SUBSET_SIZE_EXACT, 2),
    (n.SUBSET_AGG_LOWEST, n.SUBSET_SIZE_FLOOR, 2),
]


def _agg_sentence(agg: str, mode: str, source: str, where: str | None) -> str:
    size = _size_clause(mode, 2)
    body = "number of cards in subset"
    filt = f" where {where}" if where else ""
    if agg == n.SUBSET_AGG_SUM:
        return f"sum of ({body}) over subsets of {size} in {source}{filt}"
    return f"{agg} ({body}) over subsets of {size} in {source}{filt} or 0"


@pytest.mark.parametrize("agg,mode,expected", _AGG_CELLS)
def test_aggregation_register(agg: str, mode: str, expected: int) -> None:
    assert probe_value(_agg_sentence(agg, mode, "table", None)) == expected


def test_the_aggregation_axis_is_the_whole_registry() -> None:
    assert {agg for agg, _, _ in _AGG_CELLS} == n.SUBSET_AGGREGATORS
    assert {mode for _, mode, _ in _AGG_CELLS} == n.SUBSET_SIZE_MODES


# --- Grid C: the filter axis, free only where the grammar leaves it free ----
# The query forms REQUIRE `where` (their whole result is the fold of a
# predicate); the aggregation forms leave it optional, exactly as their
# card-by-card siblings do. Filtering to subsets whose first-listed size is 2
# leaves the floor form with only its six size-2 subsets.
@pytest.mark.parametrize("agg,expected", [
    (n.SUBSET_AGG_SUM, 12), (n.SUBSET_AGG_HIGHEST, 2), (n.SUBSET_AGG_LOWEST, 2),
])
def test_aggregation_filter_narrows_the_domain(agg: str, expected: int) -> None:
    sentence = _agg_sentence(
        agg, n.SUBSET_SIZE_FLOOR, "table", "(number of cards in subset) is 2"
    )
    assert probe_value(sentence) == expected


# --- Grid D: the count operand at its boundaries ----------------------------
# A size the source cannot supply is not an error: it yields no subsets, and
# the fold's own empty answer applies -- the same reading a `where` that empties
# a zone already has. A size below one IS an error: the empty set is not a
# subset the language enumerates, and a zero-card "subset" is not a thing a
# rulebook names.
_K_ACCEPTED: list[tuple[int, str, int]] = [
    (1, n.SUBSET_SIZE_EXACT, 4),                 # four singletons
    (1, n.SUBSET_SIZE_FLOOR, 15),                # 2^4 - 1
    (_TABLE_SIZE, n.SUBSET_SIZE_EXACT, 1),       # the whole table, once
    (_TABLE_SIZE, n.SUBSET_SIZE_FLOOR, 1),
    (_TABLE_SIZE + 1, n.SUBSET_SIZE_EXACT, 0),   # no subset that large
    (_TABLE_SIZE + 1, n.SUBSET_SIZE_FLOOR, 0),
]

# A size below one is refused, not empty: the empty set is not a subset the
# language enumerates, and no rulebook names a zero-card group. The refusal
# must say that in the designer's words, which is what these cells assert --
# so before the guard exists they fail on the ASSERTION (the syntax error's
# message is not the guard's), and that is the red each mark names.
_K_REFUSED: list[tuple[str, str]] = [
    ("0 cards", "at least one card"),
    ("0 or more cards", "at least one card"),
    ("(0 - 1) cards", "at least one card"),
]


@pytest.mark.parametrize("k,mode,expected", _K_ACCEPTED)
def test_a_count_the_source_cannot_supply_is_empty_not_an_error(
    k: int, mode: str, expected: int
) -> None:
    sentence = f"number of subsets of {_size_clause(mode, k)} in table where 1 is 1"
    assert probe_value(sentence) == expected


@pytest.mark.parametrize("size,wording", _K_REFUSED)
def test_a_count_below_one_is_refused_in_the_designers_words(
    size: str, wording: str
) -> None:
    sentence = f"number of subsets of {size} in table where 1 is 1"
    try:
        probe_value(sentence)
    except Exception as exc:  # the guard's channel is what the wording pins
        assert wording in str(exc), str(exc)
    else:
        raise AssertionError(f"`{size}` was accepted")


# --- Grid E: the enumeration bound ------------------------------------------
# The pool bound is the engine's, shared with the joint-selection movement:
# at the bound the enumeration runs, one card past it the refusal is loud.
@pytest.mark.parametrize("rank,pool,accepted", [("7", 4, True)])
def test_a_pool_within_the_bound_enumerates(rank: str, pool: int, accepted: bool) -> None:
    assert probe_value("number of subsets of 1 or more cards in table where 1 is 1",
                       table_rank=rank) == 2 ** pool - 1
