"""The static deck-capacity check.

A too-large player count is a compile error, not a runtime crash on an exhausted
deck. The check is conservative — it bounds what it can and skips what it can't
(`all`, non-literal amounts, deals inside `repeat until`), so it must never reject
a valid corpus game. These tests pin both directions: over-capacity games fail,
all 13 corpus games pass, and the skip rules hold.
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
    # `deal all ... to each` takes only what remains; scoring it as capacity*players
    # would falsely overflow. It must be skipped.
    check_dsl(_game("5", "deal all cards from deck to each hand"), "all.cardlang")


def test_non_literal_amount_is_skipped() -> None:
    # `deal hand_size ...` (a state var) can't be bounded statically -> skipped,
    # even though 5 * 13 = 65 would overflow if it were scored.
    check_dsl(
        _game("5", "deal hand_size cards from deck to each hand", "  hand_size : Integer = 13"),
        "var.cardlang",
    )


def test_deal_inside_repeat_until_is_skipped() -> None:
    # The iteration count is a runtime value, so deals inside `repeat until` can't
    # be bounded -> skipped (55 per iteration would otherwise overflow).
    body = (
        "repeat until (number of players where n[player] > 0) >= 5 "
        "{ deal 11 cards from deck to each hand }"
    )
    check_dsl(_game("5", body), "repeat.cardlang")


# --- the corpus must all pass (no false positive) -----------------------------


@pytest.mark.parametrize("path", sorted(GAMES.glob("*.cardlang")), ids=lambda p: p.stem)
def test_corpus_game_fits_its_deck(path: Path) -> None:
    check_source(path)  # every shipped game must pass the capacity check


# --- the deck-size table must not drift from the runtime decks -----------------


@pytest.mark.parametrize("name", sorted(DECKS))
def test_deck_size_matches_runtime(name: str) -> None:
    assert deck_size(name) == len(build_deck(name))
