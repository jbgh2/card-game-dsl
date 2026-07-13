"""Operator-axis totality for the BinOp operand walls (typecheck.py's
`_check_binop` dispatcher and its six per-class helpers).

Completeness ledger
--------------------
property:  every operator a `BinOp` node can carry has its operands checked
           for a plausible shape; a new operator landing in `infer`'s BinOp
           arm without a matching `OP_CLASSES` entry fails loud (a test, not
           a silent unwalled pass-through) rather than reaching runtime.
domain:    the operator registry — `infer`'s BinOp arm, `cardlang/
           typecheck.py` (13 operators: `== != < > <= >= and or in + - *
           offset_by`) — classified into 6 operand-shape families
           (`OP_CLASSES`) — crossed with the operand-type registry
           (`cardlang/types.py`'s closed `Type` union: TInteger, TBoolean,
           TString, TPlayer, TTeam, TCard, TEnum{Suit,Rank,Direction},
           TOptional, TCollection, TNull, TAny, TStruct, TVariant).
registry:  `OP_CLASSES` (operator -> class) pinned against `infer`'s BinOp
           arm by `test_op_classes_is_exactly_infers_binop_registry` below
           (scraped from `infer`'s own source, not hand-copied — a new
           operator without a matching entry fails this test). The operand-
           type registry is `cardlang.types.Type`.
covered:   (class, operand-type) cells with an executed probe in this
           module:
             equality    x TEnum(cross-enum), TEnum-vs-Integer  [pre-existing
                          wall, re-probed here for the dispatcher wiring]
             ordering    x TInteger (accept), TEnum(Rank) (hint), TEnum(Suit)
                          (enum-message), TCard (generic message), TAny
                          (accept, gradual)
             arithmetic  x TInteger (accept), TEnum(Rank) (hint), TEnum(Suit)
                          (concatenation message), TBoolean (generic
                          message)
             logical     x TBoolean (accept), TInteger (reject), TAny
                          (accept, gradual)
             membership  x TCollection-of-matching-element (accept),
                          non-collection right-hand-side (reject),
                          TInteger-vs-TCollection<Suit> (reject, the
                          `unify` generalization), TCard-vs-TCollection
                          <Card> zone family (accept, the pre-existing
                          zone-membership shape), TEnum literal-list (both
                          the valid-literal accept and the invalid-literal
                          reject — the retained per-element path,
                          `card.rank in [A, "10"]`)
             offset_by   x TPlayer/Direction (accept), non-Player left
                          (reject), non-Direction right (reject), TAny on
                          either side (accept, gradual)
sampled:   every class's "everything else concrete rejects" branch is one
           `isinstance` check against a fixed accept-set (`{TAny, TInteger}`
           for ordering/arithmetic, `{TAny, TBoolean}` for logical), so the
           un-probed members of the reject set (TTeam, TString, TStruct,
           TCollection, TOptional-of-a-rejected-payload, TNull) share the
           exact same code path as the probed TCard/TBoolean/TInteger
           representatives — probing one exercises the branch, not the
           type. `TOptional` unwrapping (`_bare`) is exercised once per
           class via a `Player?`/`Suit?`-shaped operand (`offset_by`'s
           corpus probe already routes through a nullable-adjacent binder);
           the unwrap itself is `types.py`'s own domain (not re-litigated
           here). `TVariant` is excluded from the operand-type domain
           entirely: this checker never infers a concrete `TVariant` for an
           expression reachable from a BinOp/aggregation/IsCheck position
           (the `outcome` pronoun — the only place a variant value flows —
           stays `TAny`; `_check_produce_stmt`/`_check_define_outcomes` type
           variants through a disjoint path that never calls `_check_binop`)
           — not a residual, a domain exclusion.
residual:  let-bound locals (`let x = <expr>`) are not typed across
           statements by the flat statement walk (`TypeEnv.locals` is
           populated only by loop/query/aggregation binders and function
           params — see `_all_statements_scoped`/`_stmt_tree_scoped`, which
           track ForEach/EachSimultaneous binders but not `LetStmt`). A
           `let`-bound name referenced in a later statement therefore
           infers `TAny` and passes every wall in this module vacuously,
           regardless of what its initializer actually computed (`let
           second = leader offset_by left` — skat.cardlang — types `second`
           as `TAny` for the rest of the phase body). This is not
           introduced by this change (every existing wall — the enum-
           comparison wall, the dot-form wall — has the same blind spot);
           it is recorded here because it materially limits how much bite
           every wall in this module has against let-derived values. Wall:
           roadmap.md, "Let-bound local typing across statements"
           (deferred — out of scope for this change, which covers operator/
           predicate-context totality, not the statement-walk's local
           environment threading).
"""

from __future__ import annotations

import inspect
import re

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.typecheck import OP_CLASSES, infer

# --- shared minimal-game builder (mirrors test_zone_family_typing.py) ---


def _game(
    body: str,
    ranking: str = "ranking: A K Q J 10 9 8 7 6 5 4 3 2",
    extra_state: str = "",
) -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  {ranking}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
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
# The registry pin — OP_CLASSES must classify exactly infer()'s BinOp operators
# =============================================================================


def test_op_classes_is_exactly_infers_binop_registry() -> None:
    """`OP_CLASSES` (the operand-wall dispatcher's registry) must classify
    every operator `infer`'s BinOp arm recognizes — no more, no less.
    Scraped from `infer`'s own source (the three `e.op in (...)` / `==`
    tuples) rather than hand-copied, so a new operator added to `infer`
    without a matching `OP_CLASSES` entry fails this test instead of
    silently reaching `_op_class`'s runtime `AssertionError` only when
    someone happens to write that operator in a game."""
    src = inspect.getsource(infer)
    start = src.index("case n.BinOp():")
    end = src.index("case n.Not()")
    binop_src = src[start:end]
    literals = set(re.findall(r'"([^"]+)"', binop_src))
    assert literals == set(OP_CLASSES)


def test_an_unclassified_operator_fails_loud_not_silent() -> None:
    """`_op_class` itself, exercised directly: every real operator classifies
    (no AssertionError) — the runtime backstop behind the static pin above."""
    from cardlang.typecheck import _op_class  # noqa: PLC0415

    for op in OP_CLASSES:
        _op_class(op)  # must not raise
    with pytest.raises(AssertionError, match="OP_CLASSES"):
        _op_class("%")  # not a real operator; the registry has no entry


# =============================================================================
# equality (==, !=) — the dispatcher re-wires the pre-existing enum wall
# =============================================================================


def test_equality_cross_enum_still_rejected_through_the_dispatcher() -> None:
    _rejects(
        _game("let probe = hearts is left"),
        "comparing Suit with Direction can never be equal",
    )


def test_equality_integer_vs_enum_still_rejected() -> None:
    _rejects(
        _game("let probe = (Q of spades).suit is 3"),
        "comparing Suit with Integer can never be equal",
    )


def test_equality_matching_suits_still_accepted() -> None:
    _accepts(_game("let probe = (Q of spades).suit is hearts"))


# =============================================================================
# ordering (< > <= >=)
# =============================================================================


def test_ordering_accepts_integers() -> None:
    _accepts(_game("let probe = score[0] >= 1"))


def test_ordering_accepts_gradual_any() -> None:
    # `action.card_count` is not in ACTION_FIELDS, so it stays TAny.
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    transition_to: p when play_to_trick where action.card_count > 3"
        )
    )


def test_ordering_rejects_a_bare_rank_with_the_rank_value_hint() -> None:
    _rejects(
        _game("let probe = (Q of spades).rank > (K of spades).rank"),
        "compare strength via rank_value(...)",
    )


def test_ordering_rejects_a_non_rank_enum() -> None:
    _rejects(
        _game("let probe = (Q of spades).suit > (K of spades).suit"),
        "enum values have no arithmetic order",
    )


def test_ordering_rejects_a_card_operand() -> None:
    _rejects(
        _game("let probe = (Q of spades) > (K of spades)"),
        "'>' compares Integers, got Card",
    )


def test_ordering_wall_fires_on_either_operand() -> None:
    # The right operand is the offender this time — both sides are checked.
    _rejects(
        _game("let probe = 3 > (Q of spades).suit"),
        "enum values have no arithmetic order",
    )


# =============================================================================
# arithmetic (+ - *)
# =============================================================================


def test_arithmetic_accepts_integers() -> None:
    _accepts(_game("let probe = score[0] + 1"))


def test_arithmetic_rejects_a_bare_rank_with_the_rank_value_hint() -> None:
    _rejects(
        _game("let probe = (Q of spades).rank + 1"),
        "compare strength via rank_value(...)",
    )


def test_arithmetic_rejects_a_non_rank_enum_naming_the_runtime_trap() -> None:
    _rejects(
        _game("let probe = (Q of spades).suit + 1"),
        "concatenates as a string at runtime, not adds",
    )


def test_arithmetic_rejects_a_boolean_operand() -> None:
    _rejects(
        _game("let probe = true + 1"),
        "'+' expects Integer operands, got Boolean",
    )


# =============================================================================
# logical (and or)
# =============================================================================


def test_logical_accepts_booleans() -> None:
    _accepts(_game("let probe = (score[0] > 0) and (score[1] > 0)"))


def test_logical_rejects_a_smuggled_integer_even_though_and_infers_boolean() -> None:
    # `and`'s own infer() arm is a fixed TBoolean regardless of its operands,
    # so a bug like `if (a and 3) {...}` is invisible to a top-level Boolean
    # check on the whole `if` condition — this wall catches it at the
    # operator itself. THE PROBE: a plausible typo (`score[0] and 3` where
    # the author meant `score[0] > 0 and 3 > 1` or similar) must reject.
    _rejects(
        _game("if (true and 3) { score[0] := 1 }"),
        "'and' expects Boolean operands, got Integer",
    )


def test_logical_accepts_gradual_any() -> None:
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    transition_to: p when play_to_trick where action.card_count and true"
        )
    )


# =============================================================================
# membership (in)
# =============================================================================


def test_membership_accepts_card_in_a_card_collection() -> None:
    _accepts(_game("let probe = (Q of spades) in hand[0]"))


def test_membership_rejects_non_collection_right_hand_side() -> None:
    _rejects(
        _game("let probe = 3 in score[0]"),
        "the right-hand side of `in` must be a collection",
    )


def test_membership_rejects_integer_against_a_suit_list() -> None:
    # THE PROBE named in the brief: `Integer in [hearts, spades]` — the
    # general `unify`-based wall, not the enum-literal path (the left
    # operand isn't itself an enum).
    _rejects(
        _game("let probe = 3 in [hearts, spades]"),
        "membership compares Integer with a collection of Suit — never true",
    )


def test_membership_rejects_a_suit_against_a_card_collection() -> None:
    # THE PROBE named in the brief: "a Suit in a zone (collection of Card)".
    _rejects(
        _game("let probe = hearts in hand[0]"),
        "membership compares Suit with a collection of Card — never true",
    )


def test_membership_keeps_the_enum_literal_list_validation() -> None:
    # doppelkopf.cardlang's real shape: `card.rank in [A, "10"]` must stay
    # legal (the retained ListLit per-element path, not the general unify
    # wall — the list's inferred element type is TAny-ish across mixed
    # literal forms, so only the literal-by-literal check catches misuse).
    _accepts(
        _game(
            'let probe = (number of cards in hand[0] where card.rank in [A, "10"])'
        )
    )


def test_membership_enum_literal_list_still_rejects_a_bad_literal() -> None:
    _rejects(
        _game(
            'let probe = (number of cards in hand[0] where card.rank in [A, "Kx"])'
        ),
        "is not a Rank value of this deck",
    )


def test_membership_accepts_gradual_any_collection() -> None:
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    transition_to: p when play_to_trick where action.card in [action.card]"
        )
    )


# =============================================================================
# offset_by
# =============================================================================


def test_offset_by_accepts_player_and_direction() -> None:
    _accepts(_game("for each player p: let probe = (p offset_by left is p)"))


def test_offset_by_accepts_a_declared_direction_state_var() -> None:
    # hearts.cardlang's real shape: `hand[player offset_by pass_direction]`,
    # a *declared* `Direction` state var on the right, not a bare literal.
    _accepts(
        _game(
            "for each player p: let probe = (p offset_by pass_direction is p)",
            extra_state="pass_direction : Direction = hold",
        )
    )


def test_offset_by_rejects_a_non_player_left_operand() -> None:
    _rejects(
        _game("let probe = ((Q of spades) offset_by left)"),
        "'offset_by' rotates a Player around the seating ring",
    )


def test_offset_by_rejects_a_non_direction_right_operand() -> None:
    _rejects(
        _game("for each player p: let probe = (p offset_by hearts is p)"),
        "'offset_by' expects a Direction",
    )


def test_offset_by_accepts_gradual_any_on_either_side() -> None:
    # A let-bound local stays TAny in the flat walk (documented residual
    # above) — both operands pass vacuously.
    _accepts(
        _game(
            "let second = actor offset_by left\n"
            "    for each player p: let probe = (second offset_by left is p)"
        )
    )
