"""Misuse-probe rejection tests for the canasta108 registry extension.

The surface-totality audit's adversarial pass for adding Canasta: no new
grammar landed, so the probes target the registry seams the new deck and
primitives open — each proven loud in its layer's failure currency.

property:   canasta108 is served identically at every deck consumer, and
            every seam it opens fails loud: the ranking-convention path
            (non-French rank), the combo block (duplicate identical cards),
            and the primitive namespace (unknown name, wrong arity)
domain:     deck consumers keyed by deck name (size table, build_deck,
            deck_suits/deck_ranks/enum_values, card block, deckcheck) x the
            new entry; the convention x non-French-rank reconciliation; the
            duplicate-cards x joint-selection interaction; the three-table
            primitive namespace
registry:   DECKS (cardlang/runtime/values.py) / _DECK_SIZE
            (cardlang/stdlib/values.py); STDLIB_CALL_FUNCS / CALL_SIGS /
            the runtime dispatch; PRIMITIVE_READS
covered:    size pin: tests/test_deckcheck.py::test_deck_size_matches_runtime
            (parametrized over sorted(DECKS) — the new entry enters
            automatically); name/arity/annotation coherence:
            tests/test_signatures.py (set equality + dispatch-AST
            reconciliation, automatic); declared reads:
            tests/test_primitive_reads.py (two-sided row pin, automatic);
            adapter registration: the corpus glob <-> registry pin and the
            proof-module coverage pin (both two-sided, automatic); the
            probes below (convention wall, combo wall, unknown name, wrong
            arity); the 54-distinct-card block pin below
sampled:    deckcheck capacity at 108 — exercised by the corpus game's own
            deal plan (tests/test_playout_canasta.py)
residual:   joint selections on ANY duplicate-card deck (the combo block's
            frozenset canonicalization collapses copies) — walled loudly at
            ActionSpace.for_game (probed below) and recorded in
            roadmap.md, "Grammar surface deferred by the checker"
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _game(body: str, ranking: str = "A K Q J 10 9 8 7 6 5 4") -> str:
    return (
        "game G {\n"
        "  players: 4\n"
        "  partnerships: [[0, 2], [1, 3]]\n"
        "  direction: clockwise\n"
        "  max_length: 100\n"
        "  cards: canasta108\n"
        f"  ranking: {ranking}\n"
        "  zones { deck : Deck  hand[player] : Hand<player>  discard : Discard }\n"
        "  state { dealer : Player = 0  score[team] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"{body}"
        "}\n"
    )


def test_ranking_convention_rejected_on_canasta108() -> None:
    # A named convention orders only French ranks; canasta108 carries the
    # Joker, so `ranking: aces high` must be rejected naming the offender —
    # never silently filtered to a partial ranking.
    dsl = _game("  phase p { shuffle deck }\n", ranking="aces high")
    with pytest.raises(DiagnosticError, match="Joker"):
        check_dsl(dsl, "t.cardlang")


def test_joint_selection_walled_on_a_duplicate_card_deck() -> None:
    # canasta108 holds two copies of every standard card: the combo block's
    # frozenset canonicalization would collide {K♠,K♠} with {K♠}, so a
    # `where jointly` selection on such a deck is refused loudly at action-
    # space construction — the audit's residual, walled
    # (roadmap.md, "Grammar surface deferred by the checker").
    from cardlang.openspiel.encoding import ActionSpace

    dsl = _game(
        "  phase p { as dealer {\n"
        "    move chosen some cards from hand[dealer]\n"
        "         where jointly gin_valid_meld(cards) to discard\n"
        "  } }\n"
    )
    game = check_dsl(dsl, "t.cardlang")
    with pytest.raises(NotImplementedError, match="duplicate identical"):
        ActionSpace.for_game(game)


def test_unknown_canasta_primitive_is_a_resolve_error() -> None:
    dsl = _game("  phase p { if canasta_bogus(dealer) { shuffle deck } }\n")
    with pytest.raises(DiagnosticError, match="canasta_bogus"):
        check_dsl(dsl, "t.cardlang")


def test_wrong_arity_canasta_primitive_is_a_typecheck_error() -> None:
    # canasta_can_start takes (Player, Rank); calling it with one argument
    # must fail at check time, not crash the dispatch mid-playout.
    dsl = _game("  phase p { if canasta_can_start(dealer) { shuffle deck } }\n")
    with pytest.raises(DiagnosticError, match="canasta_can_start"):
        check_dsl(dsl, "t.cardlang")


def test_canasta108_card_block_dedups_copies() -> None:
    # 108 physical cards, 53 distinct (rank, suit) identities — the standard
    # 52 plus ONE joker identity (all four jokers are interchangeable). The
    # derived card block numbers each distinct card once — identical copies
    # share an action id — and the joker forces the per-game block (it sits
    # outside the standard 52 catalogue).
    from cardlang.openspiel.encoding import _derived_card_block
    from cardlang.runtime.values import build_deck

    deck = build_deck("canasta108")
    assert len(deck) == 108
    block = _derived_card_block("canasta108")
    assert block is not None and len(block) == 53
    assert len(set(block)) == 53 and set(deck) == set(block)
