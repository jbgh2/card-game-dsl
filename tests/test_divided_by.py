"""Surface-totality grid for rounded division: `divided by ... rounded up|down`.

The Merge Lane A pathfinder of issue #249 (epic #248). The operator ruling and
the per-PR counsel live on that issue; docs/decisions.md "The expression
register" carries the settled text this grid pins.

Completeness ledger
--------------------
property:  every sentence the rounded-division surface accepts computes the
           value its English states (floor toward negative infinity, ceiling
           toward positive infinity, direction mandatory), and every plausible
           wrong sentence fails loud in its owning layer's currency — parse
           and builder rejections as DiagnosticError, operand-shape rejections
           as bag-collected diagnostics naming the surface spelling, dynamic
           refusals (zero divisor, non-Integer operand reaching the evaluator
           through a gradual type) as OwnerGuardError.
domain:    direction x operand value class (sign quadrants, exactness, zero,
           dynamic none) x operand syntactic shape (literals, negative
           literals, names, calls, compounds per `factor` precedence) x host
           context (statement values, lvalue index, transfer amount, state
           default at setup time, choose bounds with the `up`/`up to`
           adjacency, aggregation body, function body, predicate contexts) x
           consuming layer (parse builder, resolve, typecheck, IR, evaluate)
           — plus the rejected-symbol surface `/`, `%` and the misuse
           sentences.
registry:  the direction axis derives from the grammar's term-level rule
           aliases (scraped from cardlang.lark by
           test_direction_axis_is_pinned_by_grammar_and_op_classes below) and
           from typecheck.OP_CLASSES; the operand-type axis and its
           accept-set are typecheck's ARITHMETIC class
           (tests/test_operator_guards.py owns that class's full operand
           grid; this module probes the class routing and the new ops'
           message spelling); host positions derive from the grammar's
           expression-reaching productions (the framing-check enumeration on
           issue #249).
covered:   the executed parametrizations and probes in this module —
           test_value_grid (16 hand-authored sign/exactness cells x both
           directions through a played game), the zero-divisor and
           dynamic-operand OwnerGuardError cells (literal, computed, at-setup,
           `Integer? = none`), the host cells (lvalue index, transfer amount
           bare and parenthesized, state default, choose pinned-range, choose
           adjacency both spellings, aggregation body, function body,
           predicate contexts), the typecheck rejection cells (collection /
           enum / rank / card / string operands, mixed offset_by chains both
           directions, TAny gradual accept), the resolve cells (unknown
           divisor name, choose upper bound with no static ceiling), the
           parse/builder cells (`/` and `%` reject-with-replacement, `//`
           comment-absorption characterization, missing clause and fused
           spellings, `x /= 2`, `a / / b`, and the bare-query dividend — a
           query form is an expr-level alternative, never a term, so
           `number of cards in z divided by ...` is refused unparenthesized),
           the IR emission cell, and the names-stay-names cells (`by`,
           `down`, `divided`, `rounded` as identifiers).
sampled:   (a) the long tail of expression host positions (round/turns
           clause slots, query kinds, if-expr branches, produce payloads,
           library/stdlib start symbols): one AST node, one op-string, one
           evaluator arm — every host funnels through the same _check_expr /
           evaluate walk probed here; the load-bearing distinct paths
           (statement registry, declaration tail, setup-time evaluation,
           binder scopes) each hold an executed cell above. (b) the reject
           branch of _check_arithmetic_operands for un-probed concrete types
           (TTeam, TStruct, TNull, TOptional-of-rejected): one isinstance
           check against {TAny, TInteger}, the same branch as the executed
           collection/string/card cells — the class grid is
           tests/test_operator_guards.py's. (c) rule_args: any non-suit-
           NameRef argument already rejects at resolve's isinstance filter
           (resolve.py, active-rules argument check) — the divided form is
           one more non-NameRef through the same branch. (d) `round` vs
           `rounded` prefix anchoring: the whole-word property is pinned
           mechanically by tests/test_keyword_anchoring.py over Lark's
           compiled terminal table.
residual:  (a) `//` cannot be rejected at any layer: it is the comment
           introducer, `a // b` parses as `a` with the line tail commented
           out (characterized below, spec'd in decisions.md "The expression
           register"); the closure options (comment-syntax change, a
           source-text lint pass) are new machinery needing an operator
           ruling — R2, recorded in the divided-by counsel comment on
           issue #249 pending that ruling. (b) a literal `0` divisor is
           caught at play time, not compile time: no const-fold pass exists,
           and minting one is unruled machinery — R3, same counsel record.
           (c) pre-existing classes this surface joins but does not own,
           each named in the framing-check enumeration on issue #249:
           named-arg call values are never type-walked (`f(x = expr)`),
           deckcheck's capacity gate skips non-IntLit transfer amounts, and
           the `+ - *` evaluator arms share the dynamic non-Integer operand
           hole the new arms guard against — all pre-date this surface,
           R3/R4, flagged for tracker filing in the PR record. (d)
           banker's/half-even rounding (tarot_per_opp) is not expressible
           with these two directions — a domain exclusion, not a gap
           (#250/#253/#255 own that surface).
"""

from __future__ import annotations

import json
import random
import re
from importlib import resources

import pytest

from cardlang import ir
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.typecheck import OP_CLASSES, OpClass

# --- the shared minimal game shell (mirrors tests/test_operator_guards.py) ---


def _game(body: str, extra_state: str = "", top: str = "") -> str:
    return f"""
{top}
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ s[player] : Integer = 0 {extra_state} }}
  phase p {{
    {body}
  }}
  winner: highest s
}}
"""


def _accepts(src: str) -> n.Game:
    return check_dsl(src, "mini.cardlang")


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


def _scores(src: str) -> dict[int, int]:
    return play_game(check_dsl(src, "mini.cardlang"), random.Random(0)).scores


def _play_rejects(src: str, needle: str) -> None:
    game = check_dsl(src, "mini.cardlang")
    with pytest.raises(OwnerGuardError) as ei:
        play_game(game, random.Random(0))
    assert needle in str(ei.value), str(ei.value)


# =============================================================================
# The direction-axis pin — the grammar and OP_CLASSES must agree on the axis
# =============================================================================


def test_direction_axis_is_pinned_by_grammar_and_op_classes() -> None:
    """The direction axis derives from the grammar's term-level aliases; the
    literal `up`/`down` parametrizations below are reconciled here so a
    direction added or renamed in one registry cannot drift past the other."""
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    scraped = set(re.findall(r"->\s*divided_by_rounded_(\w+)", grammar))
    assert scraped == {"up", "down"}
    classified = {op for op in OP_CLASSES if op.startswith("divided_by_rounded_")}
    assert classified == {"divided_by_rounded_up", "divided_by_rounded_down"}
    assert all(OP_CLASSES[op] is OpClass.ARITHMETIC for op in classified)


# =============================================================================
# The value grid — hand-authored sign/exactness cells, both directions,
# computed through a played game (the evaluator, not a unit shim)
# =============================================================================

# (direction, dividend, divisor, expected). Expected values are design
# decisions authored before the implementation existed: floor toward negative
# infinity, ceiling toward positive infinity, per decisions.md.
VALUE_CELLS: list[tuple[str, int, int, int]] = [
    # exact multiple / remainder / |dividend| < |divisor| / zero dividend
    ("down", 6, 2, 3),
    ("down", 7, 2, 3),
    ("down", 1, 3, 0),
    ("down", 0, 2, 0),
    ("down", -7, 2, -4),
    ("down", -6, 2, -3),
    ("down", 7, -2, -4),
    ("down", -7, -2, 3),
    ("up", 6, 2, 3),
    ("up", 7, 2, 4),
    ("up", 1, 3, 1),
    ("up", 0, 2, 0),
    ("up", -7, 2, -3),
    ("up", -6, 2, -3),
    ("up", 7, -2, -3),
    ("up", -7, -2, 4),
]


@pytest.mark.parametrize(
    ("direction", "dividend", "divisor", "expected"),
    VALUE_CELLS,
    ids=[f"{a}_by_{b}_{d}" for d, a, b, _ in VALUE_CELLS],
)
def test_value_grid(direction: str, dividend: int, divisor: int, expected: int) -> None:
    src = _game(f"s[0] := {dividend} divided by {divisor} rounded {direction}")
    assert _scores(src)[0] == expected


def test_left_associative_chain() -> None:
    # ((13 down 2) = 6, then 6 up 4) = 2 — a chain is left-associative.
    src = _game("s[0] := 13 divided by 2 rounded down divided by 4 rounded up")
    assert _scores(src)[0] == 2


def test_mul_binds_tighter_on_both_sides() -> None:
    # decisions.md: `2 * bid divided by base rounded up` divides the product.
    src = _game("s[0] := 2 * 5 divided by 4 rounded up  s[1] := 10 divided by 2 * 2 rounded down")
    scores = _scores(src)
    assert scores[0] == 3  # (2*5)/4 up = 3, not 2*(5/4 up)=4
    assert scores[1] == 2  # 10/(2*2) down = 2, not (10/2)*2=10


def test_sum_binds_looser_than_division() -> None:
    # 2 + 9/3 down: the term-level reading gives 2+3=5; a sum-absorbed
    # dividend would give 11/3 down = 3 — the readings separate.
    src = _game("s[0] := 2 + 9 divided by 3 rounded down")
    assert _scores(src)[0] == 5


# =============================================================================
# Zero divisor and dynamic operands — OwnerGuardError, the game-author channel
# =============================================================================


@pytest.mark.parametrize("direction", ["up", "down"])
def test_zero_divisor_literal_is_a_typed_runtime_error(direction: str) -> None:
    _play_rejects(
        _game(f"s[0] := 7 divided by 0 rounded {direction}"),
        "nonzero divisor",
    )


def test_zero_divisor_computed_is_the_same_error() -> None:
    _play_rejects(
        _game("s[0] := 7 divided by z rounded up", extra_state="z : Integer = 0"),
        "nonzero divisor",
    )


def test_zero_divisor_in_a_state_default_fires_at_setup() -> None:
    # Declaration-site expressions evaluate at driver bring-up; the guard's
    # channel does not depend on a phase being live.
    _play_rejects(
        _game("s[0] := q", extra_state="q : Integer = 1 divided by 0 rounded down"),
        "nonzero divisor",
    )


def test_none_divisor_through_an_optional_is_a_typed_runtime_error() -> None:
    # `Integer?` unwraps for the static check (the class rule), so a live
    # `none` reaches the evaluator: the arm refuses it in the same channel as
    # the zero divisor, never as a bare Python TypeError.
    _play_rejects(
        _game("s[0] := 6 divided by m rounded up", extra_state="m : Integer? = none"),
        "Integer",
    )


# =============================================================================
# Host contexts — the load-bearing distinct consuming paths, each executed
# =============================================================================


def test_lvalue_index_host() -> None:
    src = _game("s[3 divided by 2 rounded down] := 9")
    assert _scores(src)[1] == 9


def test_transfer_amount_host_bare() -> None:
    # The amount slot abuts a bare item noun (`... rounded down cards ...`) —
    # the absorption-prone position; the noun must not be eaten.
    src = _game(
        "deal 4 divided by 2 rounded down cards from deck to hand[0]\n"
        "    s[0] := number of cards in hand[0]"
    )
    assert _scores(src)[0] == 2


def test_transfer_amount_host_parenthesized() -> None:
    src = _game(
        "deal (4 divided by 2 rounded up) cards from deck to hand[0]\n"
        "    s[0] := number of cards in hand[0]"
    )
    assert _scores(src)[0] == 2


def test_state_default_host_evaluates_at_setup() -> None:
    src = _game("s[0] := q", extra_state="q : Integer = 7 divided by 2 rounded up")
    assert _scores(src)[0] == 4


def test_choose_bound_host_pinned_range() -> None:
    # lo == hi forces the drawn value; a computed hi requires `up to`. The
    # for-each gives the choose its acting-player context (the choose
    # harness's own shape, tests/test_choose_ceiling.py).
    src = _game(
        "for each player q: s[q] := choose integer in "
        "(6 divided by 3 rounded down) .. (6 divided by 3 rounded down) up to 5"
    )
    scores = _scores(src)
    assert scores[0] == 2 and scores[1] == 2


def test_choose_adjacency_up_up_to_parses_to_one_reading() -> None:
    # The doubled `up`: the first closes the division, the second opens the
    # ceiling. The Choose node must carry the division as `hi` and 10 as the
    # ceiling — one derivation, no silent re-bracketing.
    game = _accepts(
        _game(
            "for each player q: s[q] := choose integer in 1 .. z divided by 2 rounded up up to 10",
            extra_state="z : Integer = 4",
        )
    )

    def walk(node: object) -> list[n.Choose]:
        found: list[n.Choose] = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if isinstance(cur, n.Choose):
                found.append(cur)
            if hasattr(cur, "__dataclass_fields__"):
                for f in cur.__dataclass_fields__:
                    stack.append(getattr(cur, f))
            elif isinstance(cur, tuple):
                stack.extend(cur)
        return found

    chooses = walk(game)
    assert len(chooses) == 1
    assert chooses[0].ceiling == 10
    hi = chooses[0].hi
    assert isinstance(hi, n.BinOp) and hi.op == "divided_by_rounded_up"


def test_choose_adjacency_single_up_to_is_a_loud_syntax_error() -> None:
    # `... rounded up to 10`: the direction consumes `up`, bare `to` matches
    # nothing — a syntax error, never a silent floor-with-ceiling reading.
    _rejects(
        _game("for each player q: s[q] := choose integer in 1 .. 4 divided by 2 rounded up to 10"),
        "syntax error",
    )


def test_choose_computed_hi_still_demands_a_static_ceiling() -> None:
    # A divided-by hi is never a literal, so the existing resolve guard must
    # demand `up to N` — the new form cannot slip past the action-space rule.
    _rejects(
        _game(
            "for each player q: s[q] := choose integer in 1 .. z divided by 2 rounded up",
            extra_state="z : Integer = 4",
        ),
        "statically known upper bound",
    )


def test_aggregation_body_host() -> None:
    # Binder-scoped host: the aggregated expression divides per card; the
    # mandatory empty-set default sits outside the division (below `or`).
    src = _game(
        "deal 2 cards from deck to hand[0]\n"
        "    s[0] := highest card_value(card) divided by 2 rounded up "
        "over cards in hand[0] or 0"
    )
    game = check_dsl(src, "mini.cardlang")
    assert play_game(game, random.Random(0)).scores[0] >= 0


def test_function_body_host() -> None:
    src = _game(
        "s[0] := half_up(7)",
        top="function half_up(x : Integer) = x divided by 2 rounded up",
    )
    assert _scores(src)[0] == 4


def test_predicate_context_hosts_accept() -> None:
    # The same expression inside an if-statement condition and a card-query
    # `where` — the two representative predicate scopes. The query dividends
    # are parenthesized: the query forms sit at the top of the expression
    # grammar (their `where` extends maximally right), so a bare query can
    # never be an operator operand — the corpus convention (skat's summed
    # card points), pinned by the probe below.
    src = _game(
        "deal 4 cards from deck to hand[0]\n"
        "    if (number of cards in hand[0]) divided by 2 rounded down >= 2 { s[0] := 1 }\n"
        "    if any card in hand[0] where (number of cards in hand[0]) divided by 4 rounded up >= 1 { s[1] := 1 }"
    )
    scores = _scores(src)
    assert scores[0] == 1 and scores[1] == 1


def test_bare_query_dividend_is_a_loud_syntax_error() -> None:
    # `number of cards in <zone> divided by ...` without parens: the query is
    # a complete expr-level alternative, never a term — the sentence is
    # refused, not silently re-bracketed.
    _rejects(
        _game("s[0] := number of cards in hand[0] divided by 2 rounded down"),
        "syntax error",
    )


# =============================================================================
# Typecheck — the ARITHMETIC class routing and the surface-spelled messages
# =============================================================================


def test_collection_dividend_rejects() -> None:
    _rejects(
        _game("let probe = hand[0] divided by 2 rounded up"),
        "expects Integer operands",
    )


def test_suit_divisor_rejects_with_the_surface_spelling() -> None:
    # The diagnostic must speak the surface phrase, never the internal op
    # string, and must not claim the `+` concatenation hazard for a division.
    src = _game("let probe = 6 divided by hearts rounded down")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "divided by ... rounded down" in message
    assert "divided_by_rounded_down" not in message
    assert "concatenates" not in message


def test_rank_operand_rejects_with_the_rank_hint() -> None:
    _rejects(
        _game("let probe = (A of spades).rank divided by 2 rounded up"),
        "rank_value",
    )


def test_card_divisor_rejects() -> None:
    _rejects(
        _game("let probe = 6 divided by (A of spades) rounded up"),
        "expects Integer operands",
    )


def test_string_divisor_rejects() -> None:
    _rejects(
        _game('let probe = 6 divided by "3" rounded up'),
        "expects Integer operands",
    )


def test_player_dividend_via_offset_by_rejects() -> None:
    # `p offset_by left divided by 2 rounded up`: the dividend types Player.
    # Player/Integer coerce for equality, but arithmetic stays Integer-only.
    _rejects(
        _game("for each player q: let probe = q offset_by left divided by 2 rounded up"),
        "expects Integer operands",
    )


def test_division_result_into_offset_by_rejects() -> None:
    # The mirror chain: `(4 divided by 2 rounded up) offset_by left` — the
    # offset_by left-operand guard demands a Player and Integer is refused.
    _rejects(
        _game("let probe = 4 divided by 2 rounded up offset_by left"),
        "offset_by",
    )


def test_gradual_any_operand_is_accepted() -> None:
    # An unregistered `action.<field>` stays TAny — the gradual pass-through,
    # same accept-set as `+ - *` (tests/test_operator_guards.py owns the class).
    _accepts(
        _game(
            "for each player q: s[q] := 1\n"
            "    mode m { transition_to: p when play_to_trick "
            "where action.card_count divided by 2 rounded up > 3 }\n"
            "    mode p { }"
        )
    )


def test_optional_integer_operand_is_accepted_statically() -> None:
    # `Integer?` unwraps for the operand check (the optional-wrapper class
    # rule); the live-none case is the runtime cell above.
    _accepts(
        _game("s[0] := 6 divided by m rounded up", extra_state="m : Integer? = 3")
    )


# =============================================================================
# Resolve — operands get the full reference sweep
# =============================================================================


def test_unknown_divisor_name_is_a_resolve_diagnostic() -> None:
    _rejects(_game("s[0] := 6 divided by nosuch rounded up"), "nosuch")


# =============================================================================
# The rejected symbols — `/` and `%` teach the word form; `//` is a comment
# =============================================================================


def test_slash_rejects_with_the_replacement_spelling() -> None:
    src = _game("s[0] := 7 / 2")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "not an operator" in message
    assert "rounded down" in message and "rounded up" in message


def test_percent_rejects_naming_the_expansion() -> None:
    src = _game("s[0] := 7 % 2")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "not an operator" in message
    assert "remainder" in message


def test_slash_rejection_fires_before_a_trailing_comment() -> None:
    _rejects(_game("s[0] := 7 / 2 // halve the pot"), "not an operator")


def test_double_slash_is_a_comment_the_characterization() -> None:
    """CHARACTERIZATION, not sanction: `a // b` parses as `a` with the line
    tail commented out — `//` is the comment introducer and cannot be claimed
    by an operator rejection at any layer (executed evidence in the divided-by
    counsel on issue #249: an un-prioritized terminal never wins the resolve,
    a prioritized one steals genuine comments). This pin makes any change to
    the trap loud; the residual is recorded in the module ledger."""
    game = parse_text(_game("let x = s[0] // 2"), "mini.cardlang")

    def find_lets(node: object) -> list[n.LetStmt]:
        found: list[n.LetStmt] = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if isinstance(cur, n.LetStmt):
                found.append(cur)
            if hasattr(cur, "__dataclass_fields__"):
                for f in cur.__dataclass_fields__:
                    stack.append(getattr(cur, f))
            elif isinstance(cur, tuple):
                stack.extend(cur)
        return found

    lets = find_lets(game)
    assert len(lets) == 1
    assert isinstance(lets[0].value, n.Subscript)  # `s[0]`, nothing more


# =============================================================================
# Misuse probes — the plausible wrong sentences, each loud
# =============================================================================


@pytest.mark.parametrize(
    ("body", "case_id"),
    [
        ("s[0] := 7 divided by 2", "missing-rounding-clause"),
        ("s[0] := 7 divided by 2 rounded", "missing-direction"),
        ("s[0] := 7 divided by 2 up", "missing-rounded"),
        ("s[0] := 7 divided 2 rounded up", "missing-by"),
        ("s[0] := 7 divided by 2 rounded sideways", "unknown-direction"),
        ("s[0] := 7 divided by 2 rounded up down", "doubled-direction"),
        ("s[0] := 7 dividedby 2 rounded up", "fused-dividedby"),
        ("s[0] := 7 divided by 2 roundedup", "fused-roundedup"),
        ("s[0] := 7 rounded up", "rounded-without-divided"),
        ("s[0] := 7 divided by 2 rounded up * 3", "term-mul-needs-parens"),
        ("s[0] /= 2", "no-slash-assign"),
        ("s[0] := 7 / / 2", "doubled-slash-with-space"),
    ],
)
def test_misuse_is_a_loud_syntax_error(body: str, case_id: str) -> None:
    _rejects(_game(body), "syntax error")


# =============================================================================
# Names stay names — anchoring only, no NAME exclusion
# =============================================================================


def test_the_new_words_remain_legal_identifiers() -> None:
    src = _game(
        "let by = 3\n"
        "    let down = 6\n"
        "    let divided = 12\n"
        "    let rounded = 2\n"
        "    s[0] := divided divided by down rounded down\n"
        "    s[1] := down divided by by rounded up",
        extra_state="",
    )
    scores = _scores(src)
    assert scores[0] == 2  # 12 / 6 floor
    assert scores[1] == 2  # 6 / 3 ceil


def test_down_as_a_state_variable_name() -> None:
    src = _game("s[0] := down divided by 2 rounded down", extra_state="down : Integer = 9")
    assert _scores(src)[0] == 4


# =============================================================================
# IR — the op strings are a wire-format commitment
# =============================================================================


def test_ir_emits_both_op_strings() -> None:
    game = _accepts(
        _game(
            "s[0] := 7 divided by 2 rounded up\n"
            "    s[1] := 7 divided by 2 rounded down"
        )
    )
    blob = json.dumps(ir.emit(game))
    assert '"divided_by_rounded_up"' in blob
    assert '"divided_by_rounded_down"' in blob
