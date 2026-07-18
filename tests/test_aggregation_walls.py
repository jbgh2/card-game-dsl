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
           pred; Comprehension.source, Comprehension.filter, Comprehension.
           body, Comprehension.default (default only exists for `agg in
           {"max","min"}` — the grammar's `agg_order` production makes it
           mandatory there and absent for `agg_sum`).
registry:  the four AST node types (`cardlang/ast/nodes.py`) and the `agg`
           field's closed domain (`sum`/`max`/`min`, pinned elsewhere by
           `tests/test_comprehension_aggregators.py::
           test_rank_dir_set_is_pinned` against the grammar's `RANK_DIR`
           terminal plus the separate `agg_sum` production).
covered:   Quantifier.body (Boolean-checked, both roles reachable via
           `any`/`all` x `player`/`team`/`suit`/`rank` share one code path —
           `player` sampled); PlayerQuery.pred (Boolean-checked);
           CardQuery.source (the shared `_check_card_source` wall, probed
           on a wrong-element collection AND on a non-collection bare-Card
           source — the latter cell was a hole until the Codex review of
           PR #48: a card-typed non-collection unified with TCard and
           passed, then crashed at runtime iteration; reused by
           Comprehension);
           CardQuery.pred (Boolean-checked); Comprehension.source (shared
           wall, reused); Comprehension.filter (Boolean-checked);
           Comprehension.body (Integer-checked for all three `agg` values;
           the TEnum sub-case is checked separately for `sum` — a
           TypeError-at-runtime message — and `max`/`min` — a silent-
           lexicographic-compare message, since evaluate.py's two code
           paths diverge; verified empirically in this module's docstring
           development, not asserted from reading the source);
           Comprehension.default (the Boolean-misparse diagnostic — THE
           headline probe — and the generic body/default type-mismatch
           fallback when the default isn't Boolean). Note on the headline
           probe: the brief's exact sentence (`where card.suit is hearts or
           card.suit is spades`) is, as of this change, caught one layer
           earlier — resolve.py's concurrently-landed scoping fix evaluates
           `Comprehension.default` OUTSIDE the `card` binder's scope (the
           grammar's own reading: a default is a fallback value, not a
           per-card predicate), so a misparsed default that references
           `card` is now an "unresolved name" at resolve time, a stronger
           diagnosis of the identical bug. This typecheck-level wall's real,
           non-redundant domain is a misparsed default that does NOT
           reference the binder — any Boolean expression valid in the outer
           scope (a plain state var, a function call) — which resolves
           clean and reaches typecheck unchallenged; both are probed in
           `test_the_headline_misparse_is_rejected`.
sampled:   Quantifier's four roles (`player`/`team`/`suit`/`rank`) all route
           through the same `_role_type`-bound scoped environment and the
           same `_check_bool` call — `player` is the probed representative,
           the others share the branch, not re-derived per role. CardQuery's
           four kinds (`set`/`count`/`any`/`all`) all reach the same
           `_check_card_source`/pred-Boolean calls before the kind-specific
           runtime dispatch — `count` (no pred) and `set`/`any` (with pred)
           are both probed; `all` shares `any`'s code path unprobed.
residual:  same let-bound-locals residual as test_operator_walls.py (a
           `let`-derived aggregation source/body/filter/default stays
           `TAny` and passes every wall here vacuously) — not re-derived,
           see that module's ledger and roadmap.md, "Let-bound local typing
           across statements". No new residual is introduced by this
           module: the Boolean-default misparse wall is deliberately
           over-broad by design (a `where`-clause-adjacent Boolean default
           is flagged even in the vanishingly unlikely case that a
           Boolean-body aggregation genuinely intends a Boolean default —
           no corpus game does this, and the brief specifies exactly this
           trade-off: "almost always" the misparse, not "always"), so it is
           not tracked as a coverage gap.
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
    # THE PROBE named in the brief, exactly as given (`card.suit is hearts or
    # card.suit is spades`). Whether this exact sentence is caught by THIS
    # module's wall or by resolve.py's independently in-flight scoping fix
    # depends on the state of a file this module does not own (resolve.py,
    # under concurrent edit — see the module docstring): as of this change,
    # resolve.py evaluates `Comprehension.default` OUTSIDE the `card`
    # binder's scope (the grammar's own reading — a default is a fallback
    # value, not a per-card predicate), so `card` in the default is an
    # unresolved name one layer before typecheck runs at all. Either
    # outcome is a correct diagnosis of the identical bug, so the assertion
    # here is deliberately layer-agnostic (rejected, full stop) rather than
    # pinned to one message — pinning it to resolve's message would make
    # this test fail if that file's WIP is reverted or reshaped, for a
    # reason having nothing to do with this module's wall.
    with pytest.raises(DiagnosticError):
        check_dsl(
            _game(
                "let probe = highest rank_value(card) over cards in trick_pile "
                "where card.suit is hearts or card.suit is spades"
            ),
            "mini.cardlang",
        )
    # The typecheck-level wall THIS module adds is not redundant with that
    # resolve-level fix, and this is the case that proves it: a misparsed
    # default that does NOT reference `card` — any Boolean expression valid
    # in the outer scope, e.g. a plain state var — resolves cleanly
    # regardless of resolve.py's scoping and reaches typecheck unchallenged.
    # This probe is pinned to the wall's own message, since nothing outside
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
    # THE PROBE named in the brief (generalized: `cumulative_score`-shaped —
    # an indexed Integer state var, itself a `Collection<Integer>`).
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
    # A card-TYPED source is still not a collection: before this wall it
    # unified with TCard, passed, and `list(elements(card))` crashed at
    # runtime (Codex review, PR #48).
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
# Comprehension.filter — must be Boolean
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
