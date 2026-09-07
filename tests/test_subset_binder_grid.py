"""The subset binder's coverage grid: `subsets of <k> [or more] cards in <zone>`.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   every sentence the subset productions accept has the value the
            surface plainly says, and every sentence they do not accept meets a
            diagnostic in the layer that owns it -- never a silent parse to a
            different meaning, and never an unbounded enumeration.
domain:     the three closed value domains the construct declares. Fully
            crossed: `SUBSET_QUERY_KINDS` x `SUBSET_SIZE_MODES` x source shape,
            and `SUBSET_AGGREGATORS` x `SUBSET_SIZE_MODES` x source shape --
            the source shapes being the three a `zone_expr` can actually
            produce (a zone name, a zone-family subscript, a `let`-bound
            collection), since `NameRef` and `Subscript` are the only two the
            production admits and a computed collection reaches one only
            through a name -- in ONE OR MORE members, several listed in
            brackets (`[table, hand[0]]`). A multi-member source is a phrase
            on the node, never a value: it has no type, cannot be bound, and can reach no other
            slot, which is what keeps every zone-demanding position untouched.
            Its members are crossed over arity {1, 2, 3} and composition
            {zone, subscript, let, and their lists}; the list's semantics
            are pinned as cells -- a card in two members counts once per
            member (concatenation, the runtime's own multiset), the same zone
            twice is refused -- by spelling at check time, by identity at play
            time, where a computed index is first decidable -- one zone in
            brackets is refused as a second spelling of the bare zone, and
            the enumeration bound applies to the list's total. Order across a
            list is stated and not pinned: every fold the construct has is
            commutative, so it is unobservable through this construct. The
            list is the Subset Source's alone: at the six per-card source
            slots it is refused naming the one-zone boundary, and the bare
            joiners' reject twins ride only behind a mandatory clause, for the
            reasons the grammar states beside them -- both pinned in the
            rejections module, this grid's sibling.
            Swept at both values but NOT crossed with the above, each for a
            stated reason: the filter axis, which exists only in the
            aggregation register (the query forms' `where` is mandatory) and
            is swept across all three aggregators; the count operand at its
            boundaries, which is a property of the size clause and not of the
            fold above it; and the source pool either side of the enumeration
            bound, which is a property of the pool alone.
            Crossed separately, and deliberately: the value the binder
            produces against every operation that consumes a card collection,
            because a new value shape's defects live in its products with the
            constructs that already exist.
            The bound is stated over the pool rather than over the enumerated
            count, which is a designed constraint rather than a gap: it refuses
            a small domain drawn from a large zone, and a cell pins that as
            deliberate.
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
            The bound is a non-termination backstop, not a performance budget.
            A pool at the bound is walked here, so it is known to terminate --
            65,535 subsets, each a full `evaluate()` -- but no cell asserts a
            time, and none should: what a playout can afford is a property of
            the game, not of this construct.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.subsets import ENUMERATION_BOUND

# --- the fixture: a table of known content ---------------------------------
# The deals are filtered, so both zones hold exactly what they are asked for:
# one card per suit per named rank on the table, and — where the ranks do not
# overlap it — the four 6s in hand[0]. Every expected value below is arithmetic
# over that. The default is one rank, so a four-card table.
_TABLE_SIZE = 4


def game(body: str, *, table_ranks: tuple[str, ...] = ("7",), extra: str = "") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        "  phase p {\n"
        "    move all cards to deck\n"
        "    move all cards from deck where ("
        + " or ".join(f'card.rank is "{r}"' if r.isdigit() else f"card.rank is {r}"
                      for r in table_ranks)
        + ") to table\n"
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

# The listed members. `table` holds the four 7s and `hand[0]` the four 6s, so
# every two-member list below is eight cards and the three-member one adds
# the empty `hand[1]`, which contributes nothing -- an arity-3 cell whose
# expected values are the arity-2 ones is exactly what proves an empty member
# is inert rather than an error. The two orders of the same pair pin that no
# fold can see the order. The `let` member is the four table cards again, so
# `[held, table]` is the OVERLAP cell: eight cards, every one
# present twice, and concatenation counts each twice.
_LISTED_SOURCES = {
    "zone+subscript": ("[table, hand[0]]", "", 8),
    "subscript+zone": ("[hand[0], table]", "", 8),
    "let+subscript": ("[held, hand[0]]", "    let held = cards in table where 1 is 1\n", 8),
    "three": ("[table, hand[0], hand[1]]", "", 8),
    "overlap": ("[held, table]", "    let held = cards in table where 1 is 1\n", 8),
}


def _choose(n: int, k: int) -> int:
    from math import comb
    return comb(n, k)


# The authored arithmetic for a pool of N cards, size 2 in both modes, checked
# against the two hand-computed pools before any listed cell trusts it.
def _expected(size: int) -> dict[tuple[str, str], int | bool]:
    return {
        (n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_EXACT): _choose(size, 2),
        (n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_FLOOR): 2 ** size - 1 - size,
        (n.SUBSET_AGG_SUM, n.SUBSET_SIZE_EXACT): 2 * _choose(size, 2),
        (n.SUBSET_AGG_SUM, n.SUBSET_SIZE_FLOOR): size * 2 ** (size - 1) - size,
        (n.SUBSET_AGG_HIGHEST, n.SUBSET_SIZE_EXACT): 2,
        (n.SUBSET_AGG_HIGHEST, n.SUBSET_SIZE_FLOOR): size,
        (n.SUBSET_AGG_LOWEST, n.SUBSET_SIZE_EXACT): 2,
        (n.SUBSET_AGG_LOWEST, n.SUBSET_SIZE_FLOOR): 2,
    }


def test_the_listed_source_arithmetic_agrees_with_the_hand_computed_cells() -> None:
    """The formula is only as good as the two pools it was checked against:
    the four-card values every single-source cell below carries by hand, and
    the eight-card values computed by hand for the listed-source cells."""
    four = _expected(4)
    assert four[(n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_EXACT)] == 6
    assert four[(n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_FLOOR)] == 11
    assert four[(n.SUBSET_AGG_SUM, n.SUBSET_SIZE_FLOOR)] == 28
    eight = _expected(8)
    assert eight[(n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_EXACT)] == 28
    assert eight[(n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_FLOOR)] == 247
    assert eight[(n.SUBSET_AGG_SUM, n.SUBSET_SIZE_EXACT)] == 56
    assert eight[(n.SUBSET_AGG_SUM, n.SUBSET_SIZE_FLOOR)] == 1016

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
    (kind, mode, src, pred, expected)
    for src in _SOURCES
    for kind, mode, pred, expected in (
        (n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_EXACT, _TAUTOLOGY, 6),
        (n.SUBSET_KIND_COUNT, n.SUBSET_SIZE_FLOOR, _TAUTOLOGY, 11),
        (n.SUBSET_KIND_ANY, n.SUBSET_SIZE_EXACT, _IS_A_PAIR, True),
        (n.SUBSET_KIND_ALL, n.SUBSET_SIZE_EXACT, _IS_A_PAIR, True),
        (n.SUBSET_KIND_ANY, n.SUBSET_SIZE_FLOOR, _IS_A_PAIR, True),
        (n.SUBSET_KIND_ALL, n.SUBSET_SIZE_FLOOR, _IS_A_PAIR, False),
    )
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
    assert {src for _, _, src, _, _ in _QUERY_CELLS} == set(_SOURCES)


# --- Grid B: the aggregation register x size mode ---------------------------
# Body is `number of cards in subset` again, so the folds are over subset SIZES:
#   exact 2 -> six subsets of size 2      => sum 12, highest 2, lowest 2
#   floor 2 -> sizes 2 (x6), 3 (x4), 4 (x1) => sum 12+12+4 = 28, highest 4, lowest 2
_AGG_CELLS: list[tuple[str, str, str, int]] = [
    (agg, mode, src, expected)
    for src in _SOURCES
    for agg, mode, expected in (
        (n.SUBSET_AGG_SUM, n.SUBSET_SIZE_EXACT, 12),
        (n.SUBSET_AGG_SUM, n.SUBSET_SIZE_FLOOR, 28),
        (n.SUBSET_AGG_HIGHEST, n.SUBSET_SIZE_EXACT, 2),
        (n.SUBSET_AGG_HIGHEST, n.SUBSET_SIZE_FLOOR, 4),
        (n.SUBSET_AGG_LOWEST, n.SUBSET_SIZE_EXACT, 2),
        (n.SUBSET_AGG_LOWEST, n.SUBSET_SIZE_FLOOR, 2),
    )
]


def _agg_sentence(agg: str, mode: str, source: str, where: str | None) -> str:
    size = _size_clause(mode, 2)
    body = "number of cards in subset"
    filt = f" where {where}" if where else ""
    if agg == n.SUBSET_AGG_SUM:
        return f"sum of ({body}) over subsets of {size} in {source}{filt}"
    return f"{agg} ({body}) over subsets of {size} in {source}{filt} or 0"


@pytest.mark.parametrize("agg,mode,source,expected", _AGG_CELLS)
def test_aggregation_register(agg: str, mode: str, source: str, expected: int) -> None:
    name, extra = _SOURCES[source]
    assert probe_value(_agg_sentence(agg, mode, name, None), extra=extra) == expected


def test_the_aggregation_axis_is_the_whole_registry() -> None:
    assert {agg for agg, _, _, _ in _AGG_CELLS} == n.SUBSET_AGGREGATORS
    assert {mode for _, mode, _, _ in _AGG_CELLS} == n.SUBSET_SIZE_MODES
    assert {src for _, _, src, _ in _AGG_CELLS} == set(_SOURCES)


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
# The pool bound is the engine's, shared with the joint-selection movement: at
# the bound the enumeration runs, past it the refusal is loud. Both directions
# are measured, because a bound with only its accepting side tested is a bound
# that could have been anything.
def test_a_pool_within_the_bound_enumerates() -> None:
    """Four ranks is sixteen cards — the bound exactly — and its whole
    non-empty powerset is walked."""
    assert probe_value(
        "number of subsets of 1 or more cards in table where 1 is 1",
        table_ranks=("7", "6", "5", "4"),
    ) == 2 ** ENUMERATION_BOUND - 1


def test_a_pool_past_the_bound_is_refused_loudly() -> None:
    """One card past the bound the construct refuses rather than walking
    2^17 subsets. The refusal is the engine's own, from the home the joint
    movement enumerates through, so the two constructs cannot answer this
    differently.

    red under: raise `ENUMERATION_BOUND`, or drop the `check_pool` call from
    the evaluator's subset arm."""
    with pytest.raises(OwnerGuardError) as exc:
        probe_value(
            "number of subsets of 1 or more cards in table where 1 is 1",
            # Sixteen cards of four ranks, plus one more card: the smallest
            # pool the bound refuses.
            table_ranks=("7", "6", "5", "4"),
            extra='    move 1 card from deck where card.rank is A to table\n',
        )
    message = str(exc.value)
    assert "exceeds the enumeration bound" in message, message
    assert str(ENUMERATION_BOUND) in message, message


def test_the_bound_is_the_pool_even_where_the_domain_would_be_small() -> None:
    """A designed constraint, recorded where a reader meets it: the bound is on
    the SOURCE POOL, so `subsets of 2 cards in <a 17-card zone>` is refused even
    though it names only 136 subsets. The alternative — bounding the enumerated
    count — would admit it, and was weighed and not taken: a pool is a zone the
    designer can see on the page, an enumerated count is arithmetic they never
    wrote, and one number a designer can hold beats two.

    This cell exists because the constraint is invisible from the accepting
    side. Nothing here argues it is right; it pins that it is deliberate, so a
    future reader meets a decision rather than a bug.

    red under: bound the enumerated candidate count instead of the pool."""
    with pytest.raises(OwnerGuardError, match="exceeds the enumeration bound"):
        probe_value(
            "number of subsets of 2 cards in table where 1 is 1",
            table_ranks=("7", "6", "5", "4"),
            extra='    move 1 card from deck where card.rank is A to table\n',
        )


def test_the_bound_refusal_names_the_zone_it_is_about() -> None:
    """A subset query is legal inside a movement's `where` filter, and a
    movement locates its own refusals at its own source zone. First writer of
    each field wins, so without a stamp here the designer would be sent to the
    zone the MOVEMENT drew from rather than the one the query ranged over —
    two different zones, and only one of them too big.

    red under: drop the `locate` call from `evaluate._subset_query`'s
    bound arm."""
    src = game(
        "    move all cards from hand[0]\n"
        "         where any subset of 2 or more cards in table where 1 is 1 to pile",
        # Five ranks is twenty cards, past the bound. The ranks avoid the 6s
        # so hand[0] still holds four — an empty movement source would never
        # evaluate the filter, and the cell would pass without raising.
        table_ranks=("7", "5", "4", "3", "2"),
    ).replace(
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player> }",
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player>\n"
        "          pile : Discard }",
    )
    with pytest.raises(OwnerGuardError) as exc:
        play_game(check_dsl(src, "grid.cardlang"), rng=random.Random(0))
    assert exc.value.zone == "table", exc.value.zone


def test_a_zone_may_be_named_for_the_binder_and_the_binder_still_wins() -> None:
    """`subset` is not reserved against a game's own names — no more than `card`
    or `player` are, both of which a game may also use — so a zone called
    `subset` is legal and the binder shadows it inside the query by the ordinary
    lexical rule.

    The cell exists because the alternative is silent: if the zone won, the
    predicate would read the zone's whole contents for every candidate and the
    query would answer about something the sentence never mentions. The two
    readings are told apart by the count — the zone below holds four cards, so
    `is 2` is false for every candidate under the zone reading (0) and true for
    every candidate under the binder reading (6).

    red under: remove `n.SubsetQuery` from `_BINDER_SCOPE_FIELDS`, which stops
    the binder entering scope and lets the zone answer."""
    src = game(
        "    move all cards from deck where card.rank is A to subset\n"
        "    score[0] := number of subsets of 2 cards in table "
        "where (number of cards in subset) is 2",
    ).replace(
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player> }",
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player>\n"
        "          subset : Discard }",
    )
    result = play_game(check_dsl(src, "grid.cardlang"), rng=random.Random(0))
    assert int(result.scores[0]) == 6, "the zone answered, not the binder"


# --- Grid F: the listed source -----------------------------------------------
_LISTED_QUERY_CELLS = [
    (kind, mode, src)
    for src in _LISTED_SOURCES
    for kind in sorted(n.SUBSET_QUERY_KINDS)
    for mode in sorted(n.SUBSET_SIZE_MODES)
]
_LISTED_AGG_CELLS = [
    (agg, mode, src)
    for src in _LISTED_SOURCES
    for agg in sorted(n.SUBSET_AGGREGATORS)
    for mode in sorted(n.SUBSET_SIZE_MODES)
]


@pytest.mark.parametrize("kind,mode,source", _LISTED_QUERY_CELLS)
def test_query_register_over_a_listed_source(kind: str, mode: str, source: str) -> None:
    name, extra, size = _LISTED_SOURCES[source]
    if kind == n.SUBSET_KIND_COUNT:
        sentence = _query_sentence(kind, mode, name, _TAUTOLOGY)
        assert probe_value(sentence, extra=extra) == _expected(size)[(kind, mode)]
    else:
        sentence = _query_sentence(kind, mode, name, _IS_A_PAIR)
        # every exact-2 subset is a pair; a floor-2 domain also holds larger ones
        expected = True if kind == n.SUBSET_KIND_ANY else mode == n.SUBSET_SIZE_EXACT
        assert probe_bool(sentence, extra=extra) is expected


@pytest.mark.parametrize("agg,mode,source", _LISTED_AGG_CELLS)
def test_aggregation_register_over_a_listed_source(agg: str, mode: str, source: str) -> None:
    name, extra, size = _LISTED_SOURCES[source]
    assert probe_value(_agg_sentence(agg, mode, name, None), extra=extra) == _expected(size)[(agg, mode)]


def test_the_listed_source_axes_are_the_whole_registries() -> None:
    assert {k for k, _, _ in _LISTED_QUERY_CELLS} == n.SUBSET_QUERY_KINDS
    assert {a for a, _, _ in _LISTED_AGG_CELLS} == n.SUBSET_AGGREGATORS
    assert {m for _, m, _ in _LISTED_QUERY_CELLS} == n.SUBSET_SIZE_MODES
    assert {s for _, _, s in _LISTED_QUERY_CELLS} == set(_LISTED_SOURCES)


def test_the_same_zone_twice_is_refused_by_name() -> None:
    """`[table, table]` names one zone twice. Refused at resolve, in
    the designer's words, naming the zone -- not folded into a domain where
    every card appears twice and nothing says so."""
    try:
        probe_value("number of subsets of 2 cards in [table, table] where 1 is 1")
    except Exception as exc:
        assert "table" in str(exc) and "twice" in str(exc), str(exc)
    else:
        raise AssertionError("a zone named twice was accepted")


def test_the_bound_applies_to_the_listed_sources_total() -> None:
    """Twelve cards on the table and four in hand is sixteen -- the bound
    exactly -- and the whole non-empty powerset is walked; one more rank on
    the table makes twenty, and the list is refused as a whole."""
    assert probe_value(
        "number of subsets of 1 or more cards in [table, hand[0]] where 1 is 1",
        table_ranks=("7", "5", "4"),
    ) == 2 ** ENUMERATION_BOUND - 1
    with pytest.raises(OwnerGuardError) as exc:
        probe_value(
            "number of subsets of 1 or more cards in [table, hand[0]] where 1 is 1",
            table_ranks=("7", "5", "4", "3"),
        )
    assert "20 cards" in str(exc.value), str(exc.value)


def test_a_computed_index_lists_a_zone_once() -> None:
    """`[table, hand[p]]` with `p` bound at play time is the pool
    `[table, hand[0]]` is, so the listed cells' arithmetic applies to it."""
    assert probe_value(
        "number of subsets of 2 cards in [table, hand[p]] where 1 is 1",
        extra="    let p = the player where player is 0\n",
    ) == _choose(8, 2)


def test_two_members_that_are_one_zone_at_play_time_are_refused() -> None:
    """`[hand[p], hand[q]]` with p = q. Resolve refuses the same SPELLING
    twice; a computed index is decided here, by identity, so the pool never
    holds one zone's cards twice. The refusal names both members and the zone
    they turned out to be, and is located at the whole list."""
    with pytest.raises(OwnerGuardError) as exc:
        probe_value(
            "number of subsets of 2 cards in [hand[p], hand[q]] where 1 is 1",
            extra=("    let p = the player where player is 0\n"
                   "    let q = the player where player is 0\n"),
        )
    message = str(exc.value)
    assert "`hand[q]`" in message and "`hand[p]`" in message and "hand[0]" in message, message
    assert exc.value.zone == "[hand[p], hand[q]]", exc.value.zone


def test_the_bound_refusal_names_the_whole_list() -> None:
    """The refusal is located at the list the designer wrote, not at its
    first member and not at nothing."""
    with pytest.raises(OwnerGuardError) as exc:
        probe_value(
            "number of subsets of 1 or more cards in [table, hand[0]] where 1 is 1",
            table_ranks=("7", "5", "4", "3"),
        )
    assert exc.value.zone == "[table, hand[0]]", exc.value.zone

