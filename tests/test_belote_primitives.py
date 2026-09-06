"""Known-value tests and misuse probes for Belote's Primitives
(cardlang/runtime/belote.py) and their registry wiring — the change's
surface-totality artifacts (the audit's rejection tests and ledger).

Completeness ledger (surface-totality-audit)
--------------------------------------------
property:   every Belote primitive computes its documented value over the
            32-card pack, and every plausible misuse of its native names
            fails loud in the owning layer's channel
domain:     every `belote_*` row of CALL_FUNCS (the registry is the axis;
            no count is written here) x {name, arity, param types,
            declaration site} + the primitives' own value domains (the
            decomposition's combination classes over 32 ranks x 4 suits, the
            guard's class argument). Belote holds no
            PRIMITIVE_TRICK_WINNERS row: the trick order is the game's
            `trick_order { }` block (issue #250 PR 4), so the winner, the
            within-trump strength and the live-trick team gate are the
            language's and are covered by tests/test_trick_order.py's grid
            and tests/test_trick_order_migration.py's pin.
            The game declares its Primitives, so a name reaches Python
            through its own `primitives { }` entry and there is no dispatch
            arm or authored reads row to misuse — the declaration site
            replaces both in this domain, and each of its two ends is a
            probe below.
registry:   cardlang/builtins/functions.py / signatures.py (names + types;
            reconciled against the dispatch by tests/test_signatures.py),
            the game's own `primitives { }` block (the declared reads,
            pinned against the implementation's source by
            tests/test_primitive_reads.py and against `implementation_sig`
            by typecheck), the openspiel registry (glob-pinned by
            tests/test_typecheck_corpus.py)
covered:    name/arity/type misuse at resolve/typecheck (the probes
            below, each a DiagnosticError with a span), at BOTH ends of the
            declaration — a typo at a call site and a typo in the entry
            itself answer in different channels; the trick/auction
            outcome-namespace crossings both ways; the runtime guard
            (non-class guard argument) as a typed error; decomposition
            known-values for every combination class, the natural
            (non-play) sequence order, the carre-first overlap rule, the
            top-five quinte cut, and the non-declarable 8/7 carres
does not prove: that a call to an implemented Primitive this block OMITS is
            refused — that cell belongs to the regime product over
            `PRIMITIVE_CALL_FUNCS`
            (tests/test_primitives_block.py), which covers it for every
            Primitive including these, and restating it per game
            would be the same fact on a lower rung
sampled:    the ctx-reading accessors (belote_decl_* / royal_player) are
            exercised end-to-end by the playout oracle
            (tests/test_playout_belote.py recomputes every announcement,
            window, and settlement from the table's own record, and pins
            the window's aim against the first trump royal played) and the
            proof module's pinned lines
            (tests/openspiel_ready/test_belote.py) rather than by synthetic
            RuntimeState fixtures here
residual:   the premature-call guard (`belote_royal_player` outside any
            round) is a loud typed RuntimeError by construction (the
            `_round_state` guard) but reachable only from a game file no
            corpus game resembles; it carries its guard in the primitive
            itself and needs no roadmap record (the guard exists; only a
            synthetic-fixture probe is deferred)
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime import narrowing, reads
from cardlang.runtime.belote import belote_best_is, decomposition
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import Card

BELOTE = Path(__file__).parent.parent / "docs" / "games" / "belote.cardlang"


def _c(spec: str) -> Card:
    rank = spec[:-1]
    suit = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[spec[-1]]
    return Card(rank, suit)


def _h(*specs: str) -> list[Card]:
    return [_c(s) for s in specs]


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


# --- the runtime guards (typed, at the cause) ---


def test_best_is_rejects_a_non_class_argument() -> None:
    # The class guard fires before any bundle read, so no runtime state is
    # needed to probe it (the argument is a literal in the game file).
    with pytest.raises(OwnerGuardError, match="not a declaration class"):
        belote_best_is(
            cast(narrowing.EngineFacts, None), cast(reads.GameReads, None), 0, 7, "A", False
        )


# --- misuse probes: the new native names, in the owning layer's channel ---


def _expect_rejected(text: str, fragment: str) -> None:
    with pytest.raises(DiagnosticError, match=fragment):
        check_dsl(text, "probe.cardlang")


def test_probe_unknown_primitive_name_is_a_resolve_error() -> None:
    """A typo at the CALL site alone: the block still declares the real name,
    so the misspelling is a name this game's namespace does not hold."""
    src = BELOTE.read_text()
    text = src.replace("let bp = belote_royal_player()", "let bp = belote_royal_playr()")
    assert text != src
    _expect_rejected(text, "unknown function 'belote_royal_playr'")


def test_probe_unknown_primitive_name_in_the_entry_is_a_resolve_error() -> None:
    """The declaration's other end, and a different channel: a typo in the
    ENTRY names Python nothing implements, so the refusal points at the
    implementation index rather than at this game's namespace. Both ends
    matter — the two halves of the coupling are authored independently, which
    is what makes reconciling them the check."""
    src = BELOTE.read_text()
    text = src.replace("belote_royal_player() : Player?", "belote_royal_playr() : Player?")
    assert text != src
    _expect_rejected(text, "nothing implements the Primitive `belote_royal_playr`")


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


def test_probe_trick_winner_fn_on_an_auction_round_is_rejected() -> None:
    src = BELOTE.read_text()
    anchor = "until (number of players where not decl_acted[player]) is 0"
    text = src.replace(
        anchor, anchor + "\n                outcome highest_by_trick_order", 1
    )
    assert text != src
    _expect_rejected(
        text,
        "auction round outcome 'highest_by_trick_order' is not an auction outcome",
    )


def test_probe_auction_outcome_on_the_trick_round_is_rejected() -> None:
    src = BELOTE.read_text()
    text = src.replace(
        "winner highest_by_trick_order", "winner tarot_auction_outcome"
    )
    assert text != src
    _expect_rejected(
        text, "trick round winner 'tarot_auction_outcome' is not a trick winner function"
    )
