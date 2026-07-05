"""Combination validity of the movement production (decisions.md, "Surface
totality"): every combination the grammar accepts is either implemented by the
executor or rejected at check time with a clear message. These pin the
rejections — each cell here used to parse and then be silently misread (a
dropped clause, a wrong-layer assert) at runtime.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _game(stmt: str) -> str:
    return f"""
game Mini {{
  players: 2
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    {stmt}
  }}
  winner: highest score
}}
"""


def _rejects(stmt: str, *needles: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(_game(stmt), "mini.cardlang")
    msg = str(ei.value)
    assert any(needle in msg for needle in needles), msg


# --- `as-equally-as-possible` composes only with an `all` deal `to each` ---


def test_rejects_distribution_with_a_single_destination() -> None:
    _rejects(
        "move all cards from deck as-equally-as-possible to pile",
        "no meaning with a single destination",
    )


def test_rejects_distribution_with_a_counted_amount() -> None:
    _rejects(
        "deal 2 cards from deck as-equally-as-possible to each hand",
        "the amount must be `all`",
    )


def test_rejects_distribution_with_chosen_selection() -> None:
    _rejects(
        "deal chosen all cards from deck as-equally-as-possible to each hand",
        "cannot combine with it",
    )


def test_rejects_distribution_with_random_selection() -> None:
    _rejects(
        "deal random all cards from deck as-equally-as-possible to each hand",
        "cannot combine with it",
    )


# --- `deal all ... to each` without a distribution is a trap (the first
# player would drain the whole source) ---


def test_rejects_all_to_each_without_distribution() -> None:
    _rejects(
        "deal all cards from deck to each hand",
        "use `as-equally-as-possible`",
    )


# --- a gather collects everything into one zone ---


def test_rejects_gather_with_a_counted_amount() -> None:
    _rejects("move 3 cards to pile", "collects every card")


def test_rejects_gather_to_each() -> None:
    _rejects("move all cards to each hand", "`to each` is not supported")


# --- deferred surface: the `in <zone>` form, visibility overrides, and
# resource nouns are rejected until built (roadmap.md) ---


def test_rejects_the_in_zone_form() -> None:
    _rejects("muck one cards in deck", "not yet supported")


def test_rejects_a_visibility_override() -> None:
    _rejects(
        "move one cards from deck to pile, visibility = 1",
        "not yet honored",
    )


def test_rejects_a_non_card_item_noun() -> None:
    _rejects("move 2 chips from deck to pile", "not a supported item noun")


# --- the accepted combinations stay accepted ---


@pytest.mark.parametrize(
    "stmt",
    [
        "deal all cards from deck as-equally-as-possible to each hand",  # Getaway
        "deal all cards from deck where c => c.suit == hearts as-equally-as-possible to each hand",
        "deal 13 cards from deck to each hand",  # the standard deal
        "move all cards to deck",  # the standard gather
        "move one card from deck to pile",  # singular noun (Cribbage's starter cut)
        "move chosen 2 cards from hand[0] to pile",
    ],
)
def test_accepts_the_implemented_combinations(stmt: str) -> None:
    check_dsl(_game(stmt), "mini.cardlang")  # raises on any rejection
