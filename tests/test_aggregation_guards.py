"""Aggregation-surface totality (typecheck.py's Comprehension/CardQuery/
PlayerQuery/Quantifier arms of `_check_expr`) — including the headline
misparse: a Boolean aggregation default absorbing the last disjunct of a
compound `where` predicate.

Completeness ledger
--------------------
property:  every predicate/body/default/source position an aggregation-
           shaped construct carries is checked at its real type — a filter
           or predicate must be Boolean, a `cards in`/`over cards in`
           source must be a zone or card collection, an order-aggregator
           body must be Integer (with a named fix for the enum-body
           mistake), and a Boolean default is flagged as the `where …or…`
           misparse rather than silently accepted with a different meaning
           than the surface reads.
domain:    the four binder-introducing expression forms `_check_expr`
           special-cases (`n.Quantifier`, `n.PlayerQuery`, `n.CardQuery`,
           `n.Comprehension`) crossed with every position each carries:
           Quantifier.body; PlayerQuery.pred; CardQuery.source, CardQuery.
           pred; Comprehension.source, Comprehension.where, Comprehension.
           body, Comprehension.default (default only exists for `agg in
           {"max","min"}` — the grammar's `agg_order` production makes it
           mandatory there and absent for `agg_sum`).
           The Comprehension.default position is narrower than the headline
           misparse it is named for, and the narrowing is not a gap: the
           misparse's own sentence (`where card.suit is hearts or card.suit
           is spades`) is caught one layer earlier, because resolve evaluates
           `Comprehension.default` OUTSIDE the `card` binder's scope (the
           grammar's own reading: a default is a fallback value, not a
           per-card predicate), so a misparsed default that references the
           binder surfaces as an "unresolved name" at resolve time, a
           stronger diagnosis of the identical bug. What this typecheck-level
           guard owns is a misparsed default that does NOT reference the
           binder — any Boolean expression valid in the outer scope, a plain
           state var or a function call — which resolves clean and reaches
           typecheck unchallenged.
registry:  the four AST node types (`cardlang/ast/nodes.py`) and the `agg`
           field's closed domain (`sum`/`max`/`min`, pinned elsewhere by
           `tests/test_comprehension_aggregators.py::
           test_rank_dir_set_is_pinned` against the grammar's `RANK_DIR`
           terminal plus the separate `agg_sum` production).
does not prove:  two things. That each binder role and each query kind is
           separately checked: Quantifier's four roles
           (`player`/`team`/`suit`/`rank`) route through the same
           `_role_type`-bound scoped environment and the same `_check_bool`
           call, with `player` as the probed representative, and CardQuery's
           four kinds (`set`/`count`/`any`/`all`) reach the same
           `_check_card_source` and pred-Boolean calls before the
           kind-specific runtime dispatch, with `all` sharing `any`'s code
           path unprobed — a role or kind that stopped sharing its branch
           would pass here. And nothing about an aggregation position
           reached through a `let` whose initializer types `TAny`: it
           carries `TAny` into the source, body, filter or default and
           passes every guard here vacuously, gradual typing's ordinary rule
           rather than a hole in the walk, with the class's ledger in
           tests/test_operator_guards.py.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

# --- shared minimal-game builder ---


def _game(body: str, extra_state: str = "") -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ score[player] : Integer = 0 {extra_state} }}
  phase p {{
    {body}
  }}
  winner: highest score
}}
"""


def _accepts(src: str) -> None:
    check_dsl(src, "mini.cardlang")


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


# =============================================================================
# THE headline misparse — a Boolean aggregation default
# =============================================================================


_FLAGS = "flag_a : Boolean = false  flag_b : Boolean = true"


def test_the_headline_misparse_is_rejected() -> None:
    # The headline probe (`card.suit is hearts or card.suit is spades`).
    # Two layers can each catch this sentence: THIS module's guard, or
    # resolve's binder scoping — resolve evaluates `Comprehension.default`
    # OUTSIDE the `card` binder's scope (the grammar's own reading: a default
    # is a fallback value, not a per-card predicate), so `card` in the default
    # is an unresolved name one layer before typecheck runs at all. Either
    # layer is a correct diagnosis of the identical bug, so the assertion is
    # deliberately layer-agnostic (rejected, full stop) rather than pinned to
    # one message: pinning it to resolve's message would make this test fail
    # whenever that scoping is reshaped, for a reason having nothing to do
    # with this module's guard.
    with pytest.raises(DiagnosticError):
        check_dsl(
            _game(
                "let probe = highest rank_value(card) over cards in trick_pile "
                "where card.suit is hearts or card.suit is spades"
            ),
            "mini.cardlang",
        )
    # The typecheck-level guard THIS module adds is not redundant with that
    # resolve-level fix, and this is the case that proves it: a misparsed
    # default that does NOT reference `card` — any Boolean expression valid
    # in the outer scope, e.g. a plain state var — resolves cleanly
    # regardless of resolve.py's scoping and reaches typecheck unchallenged.
    # This probe is pinned to the guard's own message, since nothing outside
    # this module can catch it.
    _rejects(
        _game(
            "let probe = highest rank_value(card) over cards in trick_pile "
            "where flag_a or flag_b",
            extra_state=_FLAGS,
        ),
        "parenthesize the whole `where` predicate, or supply a real default "
        "after `or`",
    )


def test_the_headline_misparse_fires_for_lowest_too() -> None:
    _rejects(
        _game(
            "let probe = lowest rank_value(card) over cards in trick_pile "
            "where flag_a or flag_b",
            extra_state=_FLAGS,
        ),
        "parenthesize the whole `where` predicate",
    )


def test_the_repair_parenthesizing_the_whole_predicate_is_accepted() -> None:
    # The fix the message names: wrap the compound predicate and supply a
    # real (Integer) default.
    _accepts(
        _game(
            "let probe = highest rank_value(card) over cards in trick_pile "
            "where (card.suit is hearts or card.suit is spades) or -1"
        )
    )


def test_a_boolean_default_with_no_filter_is_a_plain_mismatch_not_the_misparse() -> None:
    # No `where` clause at all: no `or` to have been split from, so this is
    # an ordinary body/default type mismatch, not the parenthesize message.
    _rejects(
        _game("let probe = highest rank_value(card) over cards in trick_pile or true"),
        "aggregation default type mismatch: the body is Integer, the "
        "default is Boolean",
    )


def test_pinochle_shape_stays_accepted() -> None:
    # pinochle.cardlang's real shape: `where <boolean> or <integer default>`
    # — the filter is Boolean, the default is Integer, no misparse.
    _accepts(
        _game(
            "let probe = highest rank_value(card) over cards in trick_pile "
            "where card.suit is hearts or -1"
        )
    )


# =============================================================================
# Comprehension.source / CardQuery.source — the shared `_check_card_source`
# =============================================================================


def test_aggregation_source_rejects_a_non_card_collection() -> None:
    # The headline probe, generalized: `cumulative_score`-shaped — an
    # indexed Integer state var, itself a `Collection<Integer>`.
    _rejects(
        _game("let probe = sum of 1 over cards in score"),
        "'cards in ...' expects a zone or collection of cards, got "
        "Collection<Integer>",
    )


def test_card_query_source_rejects_a_non_card_collection() -> None:
    _rejects(
        _game("let probe = number of cards in score"),
        "'cards in ...' expects a zone or collection of cards, got "
        "Collection<Integer>",
    )


def test_card_query_source_rejects_a_bare_card() -> None:
    # A card-TYPED source is still not a collection: without this guard it
    # would unify with TCard, pass, and `list(elements(card))` would crash at
    # runtime.
    _rejects(
        _game(
            "let probe = number of cards in lead",
            extra_state=" lead : Card? = none",
        ),
        "a single Card is not a collection of cards",
    )


def test_aggregation_source_rejects_a_bare_card() -> None:
    _rejects(
        _game(
            "let probe = sum of 1 over cards in lead",
            extra_state=" lead : Card? = none",
        ),
        "a single Card is not a collection of cards",
    )


def test_aggregation_source_accepts_a_real_zone() -> None:
    _accepts(_game("let probe = sum of rank_value(card) over cards in hand[0]"))


def test_card_query_source_accepts_a_real_zone() -> None:
    _accepts(_game("let probe = number of cards in hand[0]"))


# =============================================================================
# Comprehension.where — must be Boolean
# =============================================================================


def test_aggregation_filter_must_be_boolean() -> None:
    _rejects(
        _game("let probe = sum of rank_value(card) over cards in hand[0] where card.rank"),
        "aggregation `where` filter must be Boolean, got Rank",
    )


def test_aggregation_filter_boolean_is_accepted() -> None:
    _accepts(
        _game(
            "let probe = sum of rank_value(card) over cards in hand[0] "
            "where card.suit is hearts"
        )
    )


# =============================================================================
# Comprehension.body — sum/max/min all fold Integers
# =============================================================================


def test_sum_body_rejects_a_boolean() -> None:
    _rejects(
        _game("let probe = sum of true over cards in hand[0]"),
        "'sum' expects an Integer body, got Boolean",
    )


def test_sum_body_rejects_an_enum_naming_the_type_error() -> None:
    _rejects(
        _game("let probe = sum of card.suit over cards in hand[0]"),
        "summing enum values type-errors at runtime",
    )


def test_max_body_rejects_an_enum_naming_the_silent_string_compare() -> None:
    _rejects(
        _game(
            "let probe = highest card.suit over cards in hand[0] or hearts"
        ),
        "comparing enum values folds the underlying strings lexicographically",
    )


def test_min_body_enum_also_gets_the_rank_value_hint() -> None:
    _rejects(
        _game("let probe = lowest card.rank over cards in hand[0] or A"),
        "rank_value(card)",
    )


def test_sum_body_integer_is_accepted() -> None:
    _accepts(_game("let probe = sum of rank_value(card) over cards in hand[0]"))


def test_max_body_integer_is_accepted() -> None:
    _accepts(
        _game("let probe = highest rank_value(card) over cards in hand[0] or 0")
    )


# =============================================================================
# CardQuery.pred / PlayerQuery.pred / Quantifier.body — must be Boolean
# =============================================================================


def test_card_query_predicate_must_be_boolean() -> None:
    _rejects(
        _game("let probe = cards in hand[0] where card.rank"),
        "card-query predicate must be Boolean, got Rank",
    )


def test_player_query_predicate_must_be_boolean() -> None:
    _rejects(
        _game("let probe = players where score[player]"),
        "player-query predicate must be Boolean, got Integer",
    )


def test_quantifier_body_must_be_boolean() -> None:
    _rejects(
        _game("let probe = any player where score[player]"),
        "quantifier body must be Boolean, got Integer",
    )


def test_card_query_predicate_boolean_is_accepted() -> None:
    _accepts(_game("let probe = cards in hand[0] where card.suit is hearts"))


def test_player_query_predicate_boolean_is_accepted() -> None:
    _accepts(_game("let probe = players where score[player] > 0"))


def test_quantifier_body_boolean_is_accepted() -> None:
    _accepts(_game("let probe = any player where score[player] > 0"))
