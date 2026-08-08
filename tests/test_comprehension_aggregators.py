"""Runtime semantics of every aggregation form (closed-domain completeness,
decisions.md): the domain is the English register's aggregation surface —
`sum of … over cards in …`, `highest/lowest … over cards in … or <default>`,
and the counting card query `number of cards in … [where …]` — each arm
exercised here, including the empty and filtered-to-empty cases (the order
aggregators' grammar makes the `or <default>` clause mandatory, so an empty
zone yields the declared value, never a crash).

The retired spellings (`sum/count/max/min over … as x: …`, `==`/`!=`) must
NOT parse — pinned at the bottom so retirement cannot silently regress.
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.openspiel.replay import RANK_DIR_TO_SIGN
from cardlang.parse import RANK_DIRECTIONS
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import RANK_DIR_TO_PICK
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

HEARTS_A = Card("A", "hearts")
HEARTS_2 = Card("2", "hearts")
CLUBS_K = Card("K", "clubs")


def _expr(expr_src: str) -> tuple[n.Game, n.Expr]:
    src = f"""
game Mini {{
  players: 1
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    let probe = {expr_src}
  }}
  winner: highest score
}}
"""
    game = check_dsl(src, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.LetStmt)
    return game, stmt.value


def _unused_chooser(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("aggregator evaluation makes no decision")


def _ctx(game: n.Game, pile_cards: list[Card]) -> Ctx:
    rs = RuntimeState(Seating(1), ZoneStore(game.zones, (0,)), random.Random(0))
    rs.zones.single("pile").add_all(pile_cards)
    return Ctx(rs=rs, chooser=_unused_chooser).acting_as(0)


# --- the RANK_DIR terminal is pinned against every consumer's mapping ---


def test_rank_dir_set_is_pinned() -> None:
    """The grammar's RANK_DIR terminal has three consumers that each collapse
    it to an order-fold over a closed token set: the `agg_order` builder
    (parse.RANK_DIRECTIONS, `highest`/`lowest … over cards in …`, which now
    stores the token verbatim rather than translating it), the
    driver's winner determination (runtime.driver.RANK_DIR_TO_PICK, `winner:
    highest/lowest <score>`), and the OpenSpiel adapter's return sign
    (openspiel.replay.RANK_DIR_TO_SIGN). All three key sets must agree with
    the grammar terminal — a new direction token arrives with its mapping in
    every place and arm tests, or not at all (closed-domain completeness,
    decisions.md)."""
    import re

    from cardlang.parse import _parser

    # Read the token set out of the compiled terminal rather than off the
    # grammar line: RANK_DIR carries whole-word anchoring like every other
    # keyword (tests/test_keyword_anchoring.py), so its source is one regex
    # rather than a `"a" | "b"` alternation of literals.
    (term,) = [t for t in _parser().terminals if t.name == "RANK_DIR"]
    regexp = term.pattern.to_regexp()
    match = re.match(r"\(\?:([a-z|]+)\)", regexp)
    assert match is not None, f"RANK_DIR is no longer a word alternation: {regexp}"
    in_grammar = set(match.group(1).split("|"))
    assert in_grammar == set(RANK_DIRECTIONS)
    assert in_grammar == set(RANK_DIR_TO_PICK)
    assert in_grammar == set(RANK_DIR_TO_SIGN)


def test_an_unrecognized_direction_word_is_a_syntax_error_not_a_silent_default() -> None:
    # RANK_DIR is a closed two-token set (`highest`/`lowest`); a plausible
    # third direction word must never reach the exhaustive mappings above by
    # silently misparsing as something else — it is rejected at the grammar
    # layer, the same layer that owns the RANK_DIR terminal, before any
    # builder or runtime code sees it.
    with pytest.raises(DiagnosticError, match="syntax error"):
        _expr("median 5 over cards in pile or -1")
    with pytest.raises(DiagnosticError, match="syntax error"):
        check_dsl(
            """
game MedianWinner {
  players: 1
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase p { }
  winner: median score
}
""",
            "median.cardlang",
        )


# --- sum ---


def test_sum_aggregates_the_body_over_every_card() -> None:
    game, e = _expr("sum of (if card.suit is hearts then 1 else 0) over cards in pile")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


def test_sum_with_a_where_filter_aggregates_the_matching_cards_only() -> None:
    game, e = _expr("sum of 1 over cards in pile where card.suit is hearts")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


def test_sum_over_an_empty_collection_is_zero() -> None:
    game, e = _expr("sum of 1 over cards in pile")
    assert evaluate(e, _ctx(game, [])) == 0


# --- counting (the card query) ---


def test_bare_count_is_the_zone_size() -> None:
    game, e = _expr("number of cards in pile")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 3
    assert evaluate(e, _ctx(game, [])) == 0


def test_filtered_count_counts_the_matches() -> None:
    game, e = _expr("number of cards in pile where card.suit is hearts")
    assert evaluate(e, _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2])) == 2


# --- highest / lowest ---


def test_highest_returns_the_largest_body_value() -> None:
    game, e = _expr(
        "highest (if card.suit is hearts then 9 else 1) over cards in pile or -1"
    )
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 9


def test_lowest_returns_the_smallest_body_value() -> None:
    game, e = _expr(
        "lowest (if card.suit is hearts then 9 else 1) over cards in pile or -1"
    )
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 1


def test_order_aggregators_respect_the_where_filter() -> None:
    game, e = _expr("highest 5 over cards in pile where card.suit is hearts or -1")
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 5


@pytest.mark.parametrize("agg", ["highest", "lowest"])
def test_order_aggregators_yield_the_default_on_an_empty_zone(agg: str) -> None:
    game, e = _expr(f"{agg} 5 over cards in pile or -1")
    assert evaluate(e, _ctx(game, [])) == -1


@pytest.mark.parametrize("agg", ["highest", "lowest"])
def test_order_aggregators_yield_the_default_when_the_filter_empties(agg: str) -> None:
    game, e = _expr(f"{agg} 5 over cards in pile where card.suit is spades or 42")
    assert evaluate(e, _ctx(game, [CLUBS_K, HEARTS_2])) == 42


# --- the retired spellings must not come back ---


@pytest.mark.parametrize(
    "src",
    [
        "sum over pile as c: 1",
        "count over pile as c: true",
        "max over pile as c: 1",
        "min over pile as c: 1",
        "any player p: score[p] >= 1",
    ],
)
def test_retired_aggregator_and_binder_spellings_do_not_parse(src: str) -> None:
    with pytest.raises(DiagnosticError, match="syntax error"):
        _expr(src)


def test_retired_equality_symbols_are_rejected_with_the_word_form() -> None:
    with pytest.raises(DiagnosticError, match="write `is`"):
        _expr("1 == 1")
    with pytest.raises(DiagnosticError, match="write `is not`"):
        _expr("1 != 1")
