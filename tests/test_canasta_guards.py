"""Misuse-probe rejection tests for the canasta108 registry extension.

The surface-totality audit's adversarial pass for adding Canasta: no new
grammar landed, so the probes target the registry seams the new deck and
primitives open — each proven loud in its layer's failure channel.

property:   canasta108 is served identically at every deck consumer, and
            every seam it opens fails loud: the ranking-convention path
            (non-French rank), the combo block (duplicate identical cards),
            and the primitive namespace (unknown name, wrong arity)
domain:     deck consumers keyed by deck name (size table, build_deck,
            deck_suits/deck_ranks/enum_values, card block, deckcheck) x the
            new entry; the convention x non-French-rank reconciliation; the
            duplicate-cards x joint-selection interaction; the primitive
            namespace's registries and the game's own declaration
registry:   DECKS (cardlang/runtime/values.py) / _DECK_SIZE
            (cardlang/stdlib/enums.py); CALL_FUNCS / CALL_SIGS /
            DECLARED_ONLY_CALL_FUNCS; the `primitives { }` block
            canasta.cardlang declares, which is where its reads live
covered:    size pin: tests/test_deckcheck.py::test_deck_size_matches_runtime
            (parametrized over sorted(DECKS) — the new entry enters
            automatically); name/arity/annotation coherence:
            tests/test_signatures.py (set equality + dispatch-AST
            reconciliation, automatic); declared reads:
            tests/test_primitive_reads.py (two-sided pin, the game's block
            against the module's own accessor literals, automatic) — at
            MODULE grain, its scan comparing the module-wide union; ENTRY
            grain, whether one entry's own clause suffices for the code that
            entry reaches, is answered at playout, where a narrowed clause
            checks clean and the bundle refuses in the typed
            PrimitiveReadError channel naming the entry and the clause to
            extend (that module's `sampled:` row states the same limit for
            per-call-site attribution);
            adapter registration: the corpus glob <-> registry pin and the
            proof-module coverage pin (both two-sided, automatic); a
            declared-only name called from a game with no block:
            tests/test_primitives_block.py's regime product, whose
            declared-only axis is `DECLARED_ONLY_CALL_FUNCS` itself, so these
            six enter it automatically and it Owns that refusal; the
            probes below (convention guard, combo guard, unknown name, wrong
            arity); the 54-distinct-card block pin below
sampled:    deckcheck capacity at 108 — exercised by the corpus game's own
            deal plan (tests/test_playout_canasta.py)
residual:   joint selections on ANY duplicate-card deck (the combo block's
            frozenset canonicalization collapses copies) — guarded loudly at
            ActionSpace.for_game (probed below) and recorded in
            roadmap.md, "Grammar surface deferred by the checker"
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from tests.test_primitives_block import _entry_and_body


def _game(
    body: str, ranking: str = "A K Q J 10 9 8 7 6 5 4", block: str = ""
) -> str:
    """A canasta108 probe game. `block` is its `primitives { }` entries,
    written only by the cell whose subject is a declared Primitive's CALL:
    Canasta's Primitives are reached by declaration alone
    (`DECLARED_ONLY_CALL_FUNCS`), so a game with no block is refused at the
    name and the call is never typed at all."""
    return (
        "game G {\n"
        "  players: 4\n"
        "  teams: [[0, 2], [1, 3]]\n"
        "  direction: clockwise\n"
        "  max_length: 100\n"
        "  cards: canasta108\n"
        f"  ranking: {ranking}\n"
        f"{block}"
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
    # space construction — the audit's residual, guarded
    # (roadmap.md, "Grammar surface deferred by the checker").
    from cardlang.openspiel.encoding import ActionSpace

    dsl = _game(
        "  phase p { as dealer {\n"
        "    move chosen some cards from hand[dealer]\n"
        "         where jointly gin_valid_meld(cards) to discard\n"
        "  } }\n",
        block="  primitives { gin_valid_meld(cards : Collection<Card>) : Boolean }\n",
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
    # must fail at check time, not crash the dispatch mid-playout. The game
    # declares the entry, so the call reaches the ARITY check — and the match
    # pins that message rather than the name, which a refusal at any earlier
    # layer would also carry.
    dsl = _game(
        "  phase p { if canasta_can_start(dealer) { shuffle deck } }\n",
        block="  primitives { " + _entry_and_body("canasta_can_start")[0] + " }\n",
    )
    with pytest.raises(DiagnosticError, match=r"canasta_can_start\(\) expects 2 argument"):
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
