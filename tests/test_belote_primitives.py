"""Known-value tests and misuse probes for Belote's stdlib primitives
(cardlang/runtime/belote.py) and their registry wiring — the change's
surface-totality artifacts (the audit's rejection tests and ledger).

Completeness ledger (surface-totality-audit)
--------------------------------------------
property:   every Belote primitive computes its documented value over the
            32-card pack, and every plausible misuse of the new stdlib
            names fails loud in the owning layer's currency
domain:     Belote's 10 STDLIB_CALL_FUNCS rows + 1 STDLIB_TRICK_OUTCOMES
            row x {name, arity, param types, dispatch arm,
            reads row} + the primitives' own value domains (32 ranks x
            4 suits, the decomposition's combination classes, the guard's
            class argument)
registry:   cardlang/stdlib/functions.py / signatures.py (names + types;
            reconciled against the dispatch by tests/test_signatures.py),
            cardlang/runtime/reads.py (the declared-reads row, pinned both
            ways by tests/test_primitive_reads.py), the openspiel registry
            (glob-pinned by tests/test_typecheck_corpus.py)
covered:    name/arity/type misuse at resolve/typecheck (the five probes
            below, each a DiagnosticError with a span); the trick/auction
            outcome-namespace crossings both ways; the runtime walls
            (non-pack rank, non-class guard argument) as typed errors;
            decomposition known-values for every combination class, the
            natural (non-play) sequence order, the carre-first overlap
            rule, the top-five quinte cut, and the non-declarable 8/7
            carres; trick-winner known-values for the J-9 trump reorder
            and the ace-ten plain order
sampled:    the ctx-reading accessors (belote_decl_* / opp_winning /
            royal_player) are exercised end-to-end by the playout oracle
            (tests/test_playout_belote.py recomputes every announcement,
            window, and settlement from traces) and the proof module's
            pinned lines (tests/openspiel_ready/test_belote.py) rather
            than by synthetic RuntimeState fixtures here
residual:   the premature-call walls (`belote_opp_winning` /
            `belote_royal_player` outside any round; opp_winning with no
            actor) are loud typed RuntimeErrors by construction (the
            `_round_state` / actor guards) but reachable only from a game
            file no corpus game resembles; they carry their wall in the
            primitive itself and need no roadmap record (the wall exists;
            only a synthetic-fixture probe is deferred)
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.belote import (
    belote_best_is,
    belote_trick_winner,
    belote_trump_height,
    decomposition,
)
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card

BELOTE = Path(__file__).parent.parent / "docs" / "games" / "belote.cardlang"

# The game's ace-ten rank_index (plain-suit play order), as the runtime
# builds it from `ranking: ace-ten` on skat32: A > 10 > K > Q > J > 9 > 8 > 7.
_ACE_TEN = {"7": 0, "8": 1, "9": 2, "J": 3, "Q": 4, "K": 5, "10": 6, "A": 7}


def _c(spec: str) -> Card:
    rank = spec[:-1]
    suit = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[spec[-1]]
    return Card(rank, suit)


def _h(*specs: str) -> list[Card]:
    return [_c(s) for s in specs]


# --- known values: the trump reorder and the trick winner ---


def test_trump_heights_are_the_j9_reorder() -> None:
    order = ["J", "9", "A", "10", "K", "Q", "8", "7"]
    heights = [belote_trump_height(Card(r, "hearts")) for r in order]
    assert heights == sorted(heights, reverse=True) == [8, 7, 6, 5, 4, 3, 2, 1]


def test_trick_winner_trump_beats_plain_and_j_beats_9() -> None:
    # Hearts trump: the 9H beats the AH; any trump beats a plain-suit ace.
    played = [(0, _c("AS")), (1, _c("9H")), (2, _c("AH")), (3, _c("KS"))]
    assert belote_trick_winner(played, "spades", "hearts", _ACE_TEN) == 1
    played = [(0, _c("9H")), (1, _c("JH")), (2, _c("AH")), (3, _c("10H"))]
    assert belote_trick_winner(played, "hearts", "hearts", _ACE_TEN) == 1


def test_trick_winner_plain_suit_is_ace_ten() -> None:
    # No trump played: the 10 of the led suit beats the K (ace-ten order),
    # and an off-suit ace never wins.
    played = [(0, _c("KS")), (1, _c("10S")), (2, _c("AD")), (3, _c("7S"))]
    assert belote_trick_winner(played, "spades", "hearts", _ACE_TEN) == 1


# --- known values: the canonical decomposition ---


def _kinds(cards: list[Card], trump: str) -> list[tuple[int, int, bool, int]]:
    return [(cls, h, tr, pts) for cls, h, tr, pts, _ in decomposition(cards, trump)]


def test_sequences_use_the_natural_order_not_the_play_orders() -> None:
    # K-Q-J is a tierce (natural adjacency) even though the PLAY orders
    # (ace-ten; the trump reorder) both scatter those ranks.
    assert _kinds(_h("KS", "QS", "JS"), "hearts") == [(1, 7, False, 20)]
    # A-10 is NOT adjacent (the 10 sits in its natural place): no tierce.
    assert _kinds(_h("AS", "10S", "9S"), "hearts") == []
    # J-10-9 is a tierce headed by the J.
    assert _kinds(_h("JS", "10S", "9S"), "hearts") == [(1, 5, False, 20)]


def test_sequence_lengths_and_the_top_five_quinte_cut() -> None:
    assert _kinds(_h("AS", "KS", "QS", "JS"), "hearts") == [(2, 8, False, 50)]
    assert _kinds(_h("AS", "KS", "QS", "JS", "10S"), "hearts") == [(3, 8, False, 100)]
    # A seven-card run declares ONE quinte from its top; the leftover pair
    # below it is too short to declare.
    assert _kinds(
        _h("AS", "KS", "QS", "JS", "10S", "9S", "8S"), "hearts"
    ) == [(3, 8, False, 100)]


def test_trump_flag_marks_trump_suit_sequences() -> None:
    assert _kinds(_h("AH", "KH", "QH"), "hearts") == [(1, 8, True, 20)]
    assert _kinds(_h("AH", "KH", "QH"), "spades") == [(1, 8, False, 20)]


def test_carres_rank_and_score_j_9_then_100s() -> None:
    assert _kinds(_h("JC", "JD", "JH", "JS"), "hearts") == [(4, 6, False, 200)]
    assert _kinds(_h("9C", "9D", "9H", "9S"), "hearts") == [(4, 5, False, 150)]
    assert _kinds(_h("QC", "QD", "QH", "QS"), "hearts") == [(4, 1, False, 100)]
    # 8s and 7s are not declarable carres.
    assert _kinds(_h("8C", "8D", "8H", "8S"), "hearts") == []


def test_carre_extracts_first_and_no_card_counts_twice() -> None:
    # The four jacks form the carre; the J of spades is then NOT available
    # to the spade run, which continues as A-K-Q only.
    combos = _kinds(_h("JC", "JD", "JH", "JS", "AS", "KS", "QS"), "hearts")
    assert combos == [(4, 6, False, 200), (1, 8, False, 20)]


def test_best_combination_ordering_class_then_height_then_trump() -> None:
    # A plain quarte outranks a trump tierce (class first) …
    combos = _kinds(_h("AS", "KS", "QS", "JS", "AH", "KH", "QH"), "hearts")
    assert combos[0] == (2, 8, False, 50)
    # … and between equal tierces the trump one leads.
    combos = _kinds(_h("AS", "KS", "QS", "AH", "KH", "QH"), "hearts")
    assert combos[0] == (1, 8, True, 20)


# --- the runtime walls (typed, at the cause) ---


def test_trump_height_rejects_a_non_pack_rank() -> None:
    with pytest.raises(RuntimeError, match="not a skat32 rank"):
        belote_trump_height(Card("2", "hearts"))


def test_best_is_rejects_a_non_class_argument() -> None:
    # The class wall fires before any state read, so no runtime state is
    # needed to probe it (the argument is a literal in the game file).
    with pytest.raises(RuntimeError, match="not a declaration class"):
        belote_best_is(cast(Ctx, None), 0, 7, "A", False)


# --- misuse probes: the new stdlib names, in the owning layer's currency ---


def _expect_rejected(text: str, fragment: str) -> None:
    with pytest.raises(DiagnosticError, match=fragment):
        check_dsl(text, "probe.cardlang")


def test_probe_unknown_primitive_name_is_a_resolve_error() -> None:
    src = BELOTE.read_text()
    text = src.replace("belote_royal_player()", "belote_royal_playr()")
    assert text != src
    _expect_rejected(text, "unknown function 'belote_royal_playr'")


def test_probe_wrong_arity_is_a_typecheck_error() -> None:
    src = BELOTE.read_text()
    text = src.replace(
        "belote_best_is(actor, 1, h, false)", "belote_best_is(actor, 1, h)", 1
    )
    assert text != src
    _expect_rejected(text, r"belote_best_is\(\) expects 4 argument\(s\), got 3")


def test_probe_wrong_param_type_is_a_typecheck_error() -> None:
    src = BELOTE.read_text()
    text = src.replace("belote_decl_size(p)", "belote_decl_size(trump_suit)")
    assert text != src
    _expect_rejected(text, r"belote_decl_size\(\) expects Player, got Suit\?")


def test_probe_trick_outcome_on_an_auction_round_is_rejected() -> None:
    src = BELOTE.read_text()
    anchor = "until (number of players where not decl_acted[player]) is 0"
    text = src.replace(
        anchor, anchor + "\n                outcome belote_trick_winner", 1
    )
    assert text != src
    _expect_rejected(
        text, "auction round outcome 'belote_trick_winner' is not an auction outcome"
    )


def test_probe_auction_outcome_on_the_trick_round_is_rejected() -> None:
    src = BELOTE.read_text()
    text = src.replace(
        "outcome belote_trick_winner trump trump_suit",
        "outcome tarot_auction_outcome trump trump_suit",
    )
    assert text != src
    _expect_rejected(
        text, "trick round outcome 'tarot_auction_outcome' is not a trick outcome"
    )
