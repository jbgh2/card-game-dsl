"""The static deck-capacity check.

A too-large player count is a compile error, not a runtime crash on an exhausted
deck. The check is conservative — it bounds what it can and skips what it can't
(`all`, non-literal amounts, deals inside `repeat until`), so it must never reject
a valid corpus game. These tests pin both directions: over-capacity games fail,
all 14 corpus games pass, and the skip rules hold.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.values import DECKS, build_deck
from cardlang.stdlib.values import deck_size

GAMES = Path(__file__).parent.parent / "docs" / "games"
STUD = GAMES / "seven-card-stud.cardlang"


def _game(players: str, body: str, extra_state: str = "") -> str:
    return f"""game G {{
  players: {players}
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ n[player] : Integer = 0 {extra_state} }}
  phase deal {{ {body} }}
  winner: highest n
}}"""


# --- over-capacity games are rejected -----------------------------------------


def test_eight_player_stud_overflows_the_deck() -> None:
    # The headline case: 7N+4 = 60 cards needed at 8 players, 52 available.
    src = STUD.read_text().replace("  players: 4", "  players: 8", 1)
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "stud8.cardlang")
    assert "60" in str(exc.value) and "52" in str(exc.value)


def test_four_player_stud_fits() -> None:
    check_source(STUD)  # 7*4+4 = 32 <= 52, must not raise


def test_deal_to_each_overflow_is_caught() -> None:
    # 5 * 11 = 55 > 52.
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("5", "deal 11 cards from deck to each hand"), "over.cardlang")
    assert "55" in str(exc.value)


def test_exact_capacity_passes_strict_greater_than() -> None:
    # 5 * 10 = 50 <= 52 — the boundary proves the comparison is strict `>`, not `>=`.
    check_dsl(_game("5", "deal 10 cards from deck to each hand"), "exact.cardlang")


def test_player_range_uses_the_high_end() -> None:
    # players 2..8: the high end (8 * 8 = 64 > 52) drives the overflow.
    with pytest.raises(DiagnosticError):
        check_dsl(_game("2 .. 8", "deal 8 cards from deck to each hand"), "range.cardlang")


# --- the conservative skip rules (never reject what can't be bounded) ----------


def test_deal_all_is_skipped() -> None:
    # An `all` round-robin deal takes only what remains; scoring it as
    # capacity*players would falsely overflow. It must be skipped. (The bare
    # `deal all ... to each` form is rejected by the combination checker —
    # see test_movement_combination_validity.py — so the round-robin form is
    # the one that reaches deckcheck.)
    check_dsl(
        _game("5", "deal all cards from deck as-equally-as-possible to each hand"),
        "all.cardlang",
    )


def test_non_literal_amount_is_skipped() -> None:
    # `deal hand_size ...` (a state var) can't be bounded statically -> skipped,
    # even though 5 * 13 = 65 would overflow if it were scored.
    check_dsl(
        _game("5", "deal hand_size cards from deck to each hand", "  hand_size : Integer = 13"),
        "var.cardlang",
    )


def test_deck_refill_resets_the_window() -> None:
    # Re-using the deck mid-hand is valid: `move all cards to deck` refills it, so
    # the two 52-card deals draw from separate fills and must not be summed to 104.
    body = (
        "deal 13 cards from deck to each hand  move all cards to deck  "
        "deal 13 cards from deck to each hand"
    )
    check_dsl(_game("4", body), "refill.cardlang")


def test_two_deals_without_a_refill_overflow() -> None:
    # The contrast: the same two deals with no refill between them draw 104 from one
    # fill -> overflow. Confirms the reset is the refill, not the statement boundary.
    body = "deal 13 cards from deck to each hand  deal 13 cards from deck to each hand"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("4", body), "norefill.cardlang")
    assert "104" in str(exc.value)


def test_deal_inside_repeat_until_is_skipped() -> None:
    # The iteration count is a runtime value, so deals inside `repeat until` can't
    # be bounded -> skipped (55 per iteration would otherwise overflow).
    body = (
        "repeat until (number of players where n[player] > 0) >= 5 "
        "{ deal 11 cards from deck to each hand }"
    )
    check_dsl(_game("5", body), "repeat.cardlang")


def _produces_game(arm_a: str, arm_b: str) -> str:
    """A game whose only deals sit inside `produces:` arm bodies — the statement
    position the gate's old silent default never saw."""
    return f"""game G {{
  players: 4
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ n[player] : Integer = 0 }}
  phase deal {{
    d produces:
      A {{ {arm_a} }}
      B {{ {arm_b} }}
  }}
  winner: highest n
}}
define d -> {{ A | B }} {{ produce A }}"""


def test_deal_inside_a_produces_arm_is_counted() -> None:
    # 4 * 14 = 56 > 52, written inside an arm body. Before `_stmt_usage` was
    # exhaustive, `Produces` fell to its silent default and this overflow sailed
    # through to a runtime ValueError on an exhausted deck.
    src = _produces_game("deal 14 cards from deck to each hand", "n[0] := 1")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "arm-over.cardlang")
    assert "56" in str(exc.value)


def test_produces_arms_bound_by_max_not_sum() -> None:
    # Exactly one arm runs, so two 52-card arms bound to 52, not 104. Summing
    # them would falsely reject this valid game — the arm treatment is max, the
    # same shape as if/else.
    src = _produces_game(
        "deal 13 cards from deck to each hand",
        "deal 13 cards from deck to each hand",
    )
    check_dsl(src, "arm-max.cardlang")


# --- the corpus must all pass (no false positive) -----------------------------


@pytest.mark.parametrize("path", sorted(GAMES.glob("*.cardlang")), ids=lambda p: p.stem)
def test_corpus_game_fits_its_deck(path: Path) -> None:
    check_source(path)  # every shipped game must pass the capacity check


# --- the deck-size table must not drift from the runtime decks -----------------


@pytest.mark.parametrize("name", sorted(DECKS))
def test_deck_size_matches_runtime(name: str) -> None:
    assert deck_size(name) == len(build_deck(name))
