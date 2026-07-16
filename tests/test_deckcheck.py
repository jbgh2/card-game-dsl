"""The static deck-capacity check.

A too-large player count is a compile error, not a runtime crash on an exhausted
deck. The check is conservative — it bounds what it can and skips what it can't
(`all`, non-literal amounts, deals inside `repeat until`), so it must never reject
a valid corpus game. These tests pin both directions: over-capacity games fail,
all corpus games pass, and the skip rules hold.

property:   every statement kind states its deck behaviour in `_stmt_usage`
            (count / branch / skip / inert), and the gate never rejects a
            valid game
domain:     the `Stmt` union (statement kinds) × deck effect {draw, refill,
            branch, repeat, inert}
registry:   `cardlang.ast.nodes.Stmt` — the walk is an exhaustive match
            (mypy-enforced), so a new statement kind cannot fall to a silent
            "draws nothing" default (that default is how deals inside a
            `Block`, and then inside a `produces:` arm, were invisible)
covered:    Movement (count / full refill / literal partial return — all
            pinned; a partial return SUBTRACTS rather than resetting,
            since modeling one returned card as a full refill accepted a
            genuinely overflowing game), IfStmt (taken-branch
            counting AND max-not-sum, both pinned below), ForEach (per-role
            iteration counts from the domain table — overflow and exact-fit
            pinned below), Block (unconditional sequence — both failure
            directions pinned in test_procedures' capacity-parity test),
            Produces (max over arms, both directions pinned below),
            RepeatUntil (skip — sound because the runtime checks the
            condition first, so the zero-iteration path is always possible)
sampled:    the inert group (let/assign/rotate/offer/round/produce/jumps) is
            asserted inert by the match arms' own comments; no per-kind probe,
            since inertness is "no Movement reachable", a structural fact
residual:   draws inside MOVE effects (via `offer`/rounds) are outside the
            gate's domain — not statically boundable; recorded in roadmap.md
            ("The deck-capacity gate does not see move-driven draws")
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


def test_a_partial_return_is_not_a_refill() -> None:
    # Deal 40, put ONE card back, deal 16 more: 40 - 1 + 16 = 55 > 52. The old
    # model treated any movement into the deck as a full refill (carry -> 0),
    # so this was accepted and died mid-deal at runtime on the exhausted-deck
    # error the gate exists to prevent.
    body = (
        "deal 10 cards from deck to each hand  "
        "move 1 cards from hand[0] to deck  "
        "deal 4 cards from deck to each hand"
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("4", body), "partial.cardlang")
    assert "55" in str(exc.value)


def test_a_literal_return_subtracts_exactly() -> None:
    # The passing contrast: return 10, then a deal that fits the freed space.
    # 40 - 10 + 20 = 50 <= 52.
    body = (
        "deal 10 cards from deck to each hand  "
        "move 10 cards from hand[0] to deck  "
        "deal 5 cards from deck to each hand"
    )
    check_dsl(_game("4", body), "partial-fit.cardlang")


def test_two_deals_without_a_refill_overflow() -> None:
    # The contrast: the same two deals with no refill between them draw 104 from one
    # fill -> overflow. Confirms the reset is the refill, not the statement boundary.
    body = "deal 13 cards from deck to each hand  deal 13 cards from deck to each hand"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("4", body), "norefill.cardlang")
    assert "104" in str(exc.value)


def test_a_guarded_deal_counts_as_taken() -> None:
    # 40 unconditional + 52 inside the if-branch: a guarded deal is TAKEN for
    # bounding purposes, so the window peaks at 92 > 52. Without this pin, an
    # IfStmt arm quietly returning (carry, carry) keeps the whole suite green
    # while the gate goes blind to every guarded deal.
    body = (
        "deal 10 cards from deck to each hand  "
        "if n[0] is 0 { deal 13 cards from deck to each hand }"
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("4", body), "guarded.cardlang")
    assert "92" in str(exc.value)


def test_if_branches_bound_by_max_not_sum() -> None:
    # 24 unconditional + max(28, 28) = 52 exactly: one branch runs, so summing
    # them (80) would falsely reject this valid game.
    body = (
        "deal 6 cards from deck to each hand  "
        "if n[0] is 0 { deal 7 cards from deck to each hand } "
        "else { deal 7 cards from deck to each hand }"
    )
    check_dsl(_game("4", body), "branch-max.cardlang")


def test_for_each_over_a_value_domain_multiplies_iterations() -> None:
    # The module docstring's own cautionary example: `for each suit` runs its
    # body once per SUIT (4), not once — 4 x 15 = 60 > 52. The old rule was
    # "players, or once", which counted this as one iteration and let it
    # through to a mid-deal ValueError.
    body = "for each suit s: move 15 cards from deck to hand[0]"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("4", body), "suits.cardlang")
    assert "60" in str(exc.value)


def test_for_each_iterations_thread_the_carry() -> None:
    # The passing contrast at the exact boundary: 4 suits x 13 = 52.
    body = "for each suit s: move 13 cards from deck to hand[0]"
    check_dsl(_game("4", body), "suits-fit.cardlang")


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
