"""Surface-totality grid for the `excluding` clause of an integer `choose`:
`choose integer in <lo> .. <hi> [up to <N>] [excluding <e>]`.

Merge Lane A (issue #509). The counsel lives on the pull request;
docs/decisions.md "The integer `choose` domain" carries the settled text this
grid pins.

Completeness ledger
--------------------
property:  every sentence the clause accepts offers the chooser exactly the
           live range less the one value the exclusion names, and the value
           drawn is the value announced; every exclusion that can never act
           or always empties the choice, every non-Integer operand of a
           `choose` (`lo`, `hi`, `excluding` alike), and every plausible
           wrong spelling fails loud in its owning layer's currency — parse
           rejections as DiagnosticError naming a syntax error, resolve and
           typecheck rejections as bag-collected diagnostics naming the
           construct, dynamic refusals (an exclusion that empties the live
           range, a non-Integer operand reaching the evaluator through the
           permissive top) as OwnerGuardError.
domain:    the three operand positions of a `choose` (`lo`, `hi`,
           `excluding`) x each position's static decidability (literal,
           runtime; `hi` with and without `up to`) x the exclusion's
           relation to the static offerable interval (absent, below, at the
           low end, inside, at the high end, above, emptying a singleton) x
           the operand's syntactic shape (literals, negative literals,
           names, compounds, a nested `choose`, a parenthesized `if`, a
           user-function call) x consuming layer (parse builder, resolve,
           typecheck, IR, evaluate, the adapter's encoded legal set) — plus
           the misuse sentences, the names-stay-names cells, the explicit-
           ambiguity cells, and the corpus witness. `choose` is an
           expression-level form: its trailing operand extends as far right
           as possible, and a choose used as an operator's operand is
           parenthesized (the bare spelling is a syntax error). A fully
           literal in-range exclusion is accepted with one action id legal
           in no state, by design (the clause is the game's rule, not a
           sizing declaration; decisions.md). The node-level bans on where a
           `choose` may sit (a state default, a Trick Order row) are
           unchanged by the clause and pinned by their own modules.
registry:  clause order and operand positions derive from the grammar's
           `choose_expr` production (scraped by
           test_production_is_pinned); the static expected column is
           `_expected_static`, authored from decisions.md; the
           operand-type accept set is typecheck's Integer-or-TAny rule
           (the arithmetic class's full operand grid:
           tests/test_operator_guards.py); keyword anchoring:
           tests/test_keyword_anchoring.py; the node-level bans:
           tests/test_state_default_scope.py, tests/test_trick_order.py;
           the per-observer legal-action agreement over the witness:
           tests/openspiel_ready/test_oh_hell.py; the IR key:
           tests/test_ir_schema_version.py.
does not prove: that an exclusion reads only state its chooser can see. The
           grid's exclusions read public state; the instrument for that
           property is the per-game proof harness, which runs over the
           corpus witness alone, so a designer's exclusion over a hidden
           zone is refused by nothing this module executes.
naming:    `excluding` mints no glossary entry: the clause is one English
           word with one meaning on one construct, the sibling clause
           `up to` carries none, the word appears in neither the glossary's
           reserved-words table nor the grammar's NAME exclusions, and it
           stays a legal identifier (the names-stay-names cells below).
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, fields, is_dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from lark import Lark, Tree

from cardlang import ir
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.observe import render

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
OH_HELL = GAMES / "oh-hell.cardlang"

# The runtime values the shell's state variables hold. `m` is a runtime lower
# bound, `n` a runtime upper bound, `k` a runtime exclusion inside the
# interval, `k5` a runtime exclusion at its high end (the value that empties
# the singleton `5 .. 5`).
STATE = "x[player] : Integer = 0  m : Integer = 0  n : Integer = 5  k : Integer = 3  k5 : Integer = 5"
VALUES = {"m": 0, "n": 5, "k": 3, "k5": 5}


def _game(choose: str, state: str = STATE, top: str = "", extra: str = "") -> str:
    return f"""
{top}
game G {{
  players: 2
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ {state} }}
  phase play {{
    for each player p: x[p] := {choose}
    {extra}
  }}
  winner: highest x
}}
"""


def _walk(node: object) -> Iterator[object]:
    if is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


def _chooses(game: n.Game) -> list[n.Choose]:
    return [nd for nd in _walk(game) if isinstance(nd, n.Choose)]


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "t")
    assert needle in str(ei.value), str(ei.value)


@dataclass
class Played:
    """One playout seen from the chooser seam and the observation stream."""

    candidates: list[list[int]]
    picks: list[int]
    announces: list[tuple[int, Any]]


def _play(game: n.Game, seed: int) -> Played:
    rng = random.Random(seed)
    played = Played([], [], [])

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        assert k == 1, "an integer choose draws one value"
        if candidates and isinstance(candidates[0], int) and not isinstance(candidates[0], bool):
            played.candidates.append(list(candidates))
            pick = rng.choice(candidates)
            played.picks.append(pick)
            return [pick]
        return rng.sample(candidates, k)

    def observer(player: int, event: tuple[Any, ...]) -> None:
        if event[0] == "announce":
            played.announces.append((player, event[2]))

    play_game(game, rng, chooser=chooser, observer=observer)
    return played


# =============================================================================
# The production pin — the clause order and the keyword's anchoring
# =============================================================================


def _grammar() -> str:
    return resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()


def test_production_is_pinned() -> None:
    """The exclusion is the last optional clause, after `up to`, and takes one
    `sum`; the keyword is anchored like every other. The clause order is the
    axis the misuse probes below assume."""
    grammar = _grammar()
    production = re.search(r"^choose_expr:.*$", grammar, re.MULTILINE)
    assert production is not None
    assert production.group(0) == (
        'choose_expr: _CHOOSE_KW _INTEGER_KW _IN_KW sum ".." sum '
        "[_UP_KW _TO_KW INT] [_EXCLUDING_KW sum]  -> choose_integer"
    )
    assert '_EXCLUDING_KW: "excluding" /(?![A-Za-z0-9_])/' in grammar


# =============================================================================
# The static grid — lo x hi x excluding, expected column authored from the law
# =============================================================================


@dataclass(frozen=True)
class Operand:
    label: str
    text: str
    literal: int | None  # the static value, or None for a runtime expression
    runtime: int | None  # the value the expression takes at playout


LO: tuple[Operand, ...] = (
    Operand("lo0", "0", 0, 0),
    Operand("lo5", "5", 5, 5),
    Operand("loRT", "m", None, 0),
)

# (label, text, static ceiling or None when the resolver must refuse it)
HI: tuple[tuple[str, str, int | None], ...] = (
    ("hi5", "5", 5),
    ("hiRT", "n up to 5", 5),
    ("hiNoCeiling", "n", None),
)

EX: tuple[Operand | None, ...] = (
    None,
    Operand("exNeg", "-1", -1, -1),
    Operand("ex0", "0", 0, 0),
    Operand("ex3", "3", 3, 3),
    Operand("ex5", "5", 5, 5),
    Operand("ex6", "6", 6, 6),
    Operand("exRT", "k", None, 3),
    Operand("exRTsum", "k + 1", None, 4),
    Operand("exRTif", "(if m is 0 then k else 9)", None, 3),
    Operand("exRThigh", "k5", None, 5),
    Operand("exNested", "(choose integer in 0 .. 1)", None, None),
)


def _expected_static(lo: Operand, hi: tuple[str, str, int | None], ex: Operand | None) -> str | None:
    """The law's verdict on one cell: None to accept, else the diagnostic's
    needle. decisions.md "The integer `choose` domain": a runtime `hi` needs
    `up to`; a literal `lo` outside the reserved block is refused; a literal
    exclusion outside the static offerable interval — literal `lo` (or 0)
    up to the ceiling — can never act; a literal exclusion equal to a
    singleton interval always empties it."""
    ceiling = hi[2]
    if ceiling is None:
        return "statically known upper bound"
    low = lo.literal if lo.literal is not None else 0
    if lo.literal is not None and lo.literal > ceiling:
        return "exceeds its ceiling"
    if ex is not None and ex.literal is not None:
        if not low <= ex.literal <= ceiling:
            return "can never act"
        if low == ceiling:
            return "would always empty"
    return None


def _static_cells() -> list[tuple[Operand, tuple[str, str, int | None], Operand | None]]:
    return [(lo, hi, ex) for lo in LO for hi in HI for ex in EX]


def _cell_id(cell: tuple[Operand, tuple[str, str, int | None], Operand | None]) -> str:
    lo, hi, ex = cell
    return f"{lo.label}-{hi[0]}-{ex.label if ex else 'noEx'}"


@pytest.mark.parametrize("cell", _static_cells(), ids=_cell_id)
def test_static_grid(cell: tuple[Operand, tuple[str, str, int | None], Operand | None]) -> None:
    """Every cell either rejects with the law's needle or is accepted AND
    played: the chooser sees the live range less the exclusion's value, and
    the announced value is the drawn one."""
    lo, hi, ex = cell
    src = _game(f"choose integer in {lo.text} .. {hi[1]}" + (f" excluding {ex.text}" if ex else ""))
    needle = _expected_static(lo, hi, ex)
    if needle is not None:
        _rejects(src, needle)
        return
    game = check_dsl(src, "t")
    (choose,) = [c for c in _chooses(game) if ex is None or ex.label != "exNested" or c.excluding is not None]
    assert (choose.excluding is None) == (ex is None)
    live = list(range(lo.runtime or 0, VALUES["n"] + 1))
    for seed in range(12):
        excluded_live = ex.runtime if ex is not None else None
        if ex is not None and ex.label != "exNested" and not [v for v in live if v != excluded_live]:
            with pytest.raises(OwnerGuardError, match=f"excluding {excluded_live}"):
                play_game(game, random.Random(seed))
            continue
        played = _play(game, seed)
        if ex is not None and ex.label == "exNested":
            # Two decisions per player: the inner choose (0 .. 1) draws first,
            # its value excluded from the outer draw.
            assert len(played.picks) == 4
            inner, outer = played.picks[0], played.picks[1]
            assert played.candidates[0] == [0, 1]
            assert played.candidates[1] == [v for v in live if v != inner]
            assert outer != inner
        else:
            excluded = ex.runtime if ex is not None else None
            expected = [v for v in live if v != excluded]
            assert played.candidates == [expected, expected], played.candidates
            assert all(p in expected for p in played.picks)
        # The announcement carries the drawn value — nothing corrects it after.
        assert [a[1] for a in played.announces[0::2]] == [render(p) for p in played.picks]


def test_runtime_emptied_range_is_refused_naming_the_exclusion() -> None:
    # `5 .. 5 excluding k5` with `k5` = 5: not statically decidable (a runtime
    # exclusion), so it passes resolve and must refuse at play time in the
    # game author's channel, naming the value that emptied the choice.
    game = check_dsl(_game("choose integer in 5 .. 5 excluding k5"), "t")
    with pytest.raises(OwnerGuardError, match="excluding 5"):
        play_game(game, random.Random(0))


def test_runtime_lo_below_the_block_is_still_the_range_guard() -> None:
    # A runtime `lo` that goes negative escapes the reserved block; the
    # existing range guard owns that, clause or no clause.
    game = check_dsl(
        _game("choose integer in m .. 5 excluding 2", state=STATE.replace("m : Integer = 0", "m : Integer = -1")),
        "t",
    )
    with pytest.raises(OwnerGuardError, match="escaped its declared domain"):
        play_game(game, random.Random(0))


@pytest.mark.parametrize("hi", ["5", "n up to 5"])
def test_negative_literal_lo_is_rejected_at_resolve(hi: str) -> None:
    # The literal-bounds class, swept: a literal `lo` above the ceiling was
    # refused statically while a literal `lo` below the block was left to the
    # runtime guard. Both ends of the reserved block are decided at resolve.
    _rejects(_game(f"choose integer in -1 .. {hi}"), "below the reserved block")


# =============================================================================
# The pre-existing rejections re-run with the clause present
# =============================================================================

EXISTING_REJECTIONS: tuple[tuple[str, str], ...] = (
    ("0 .. n", "statically known upper bound"),
    ("0 .. 13 up to 10", "already its static ceiling"),
    ("0 .. 5 up to 10", "already its static ceiling"),
    ("5 .. 3", "exceeds its ceiling"),
    ("11 .. n up to 10", "exceeds its ceiling"),
    ("0 .. (13 - 1)", "statically known upper bound"),
)


@pytest.mark.parametrize("clause", ["", " excluding 2", " excluding k"])
@pytest.mark.parametrize(("rng_text", "needle"), EXISTING_REJECTIONS, ids=[r[0] for r in EXISTING_REJECTIONS])
def test_existing_rejections_hold_with_the_clause(rng_text: str, needle: str, clause: str) -> None:
    _rejects(_game(f"choose integer in {rng_text}{clause}"), needle)


# =============================================================================
# The operand-type class — every Integer position of a choose, one Owner Guard
# =============================================================================

BAD_OPERANDS: tuple[tuple[str, str], ...] = (
    ("suit", "hearts"),
    ("string", '"3"'),
    ("card", "(A of spades)"),
    ("list", "[3, 5]"),
    ("zone", "hand[p]"),
    ("boolean", "true"),
)


def _with_operand(position: str, text: str) -> str:
    if position == "lo":
        return f"choose integer in {text} .. 5"
    if position == "hi":
        return f"choose integer in 0 .. {text} up to 5"
    return f"choose integer in 0 .. 5 excluding {text}"


@pytest.mark.parametrize("position", ["lo", "hi", "excluding"])
@pytest.mark.parametrize(("kind", "text"), BAD_OPERANDS, ids=[b[0] for b in BAD_OPERANDS])
def test_non_integer_operand_is_rejected_at_typecheck(position: str, kind: str, text: str) -> None:
    _rejects(_game(_with_operand(position, text)), "expects an Integer")


@pytest.mark.parametrize("position", ["lo", "hi", "excluding"])
def test_optional_integer_operand_is_accepted_statically(position: str) -> None:
    # `Integer?` unwraps for the operand check (the class rule); a live `none`
    # is the evaluator's to refuse (next cell).
    game = check_dsl(_game(_with_operand(position, "o"), state=STATE + "  o : Integer? = 3"), "t")
    assert len(_chooses(game)) == 1


@pytest.mark.parametrize("position", ["lo", "hi", "excluding"])
def test_none_operand_is_a_typed_runtime_error(position: str) -> None:
    game = check_dsl(_game(_with_operand(position, "o"), state=STATE + "  o : Integer? = none"), "t")
    with pytest.raises(OwnerGuardError, match="Integer"):
        play_game(game, random.Random(0))


@pytest.mark.parametrize("position", ["lo", "hi", "excluding"])
@pytest.mark.parametrize("literal", ["true", "false"])
def test_boolean_through_the_permissive_top_is_refused_not_coerced(position: str, literal: str) -> None:
    # An `if` whose branches disagree types TAny, so the static guard passes
    # it; the evaluator must refuse the Boolean (bool subclasses int in the
    # host language, so a bare int check would draw `true` as 1).
    shape = f"(if m is 0 then {literal} else 1)"
    game = check_dsl(_game(_with_operand(position, shape)), "t")
    with pytest.raises(OwnerGuardError, match="Integer"):
        play_game(game, random.Random(0))


def test_user_function_call_in_the_exclusion_is_typed_and_evaluated() -> None:
    game = check_dsl(
        _game("choose integer in 0 .. 5 excluding f(2)", top="function f(v : Integer) = v + 1"),
        "t",
    )
    played = _play(game, 0)
    assert played.candidates == [[0, 1, 2, 4, 5], [0, 1, 2, 4, 5]]


def test_unknown_name_in_the_exclusion_is_rejected_at_resolve() -> None:
    _rejects(_game("choose integer in 0 .. 5 excluding nobody"), "nobody")


# =============================================================================
# Parse — the misuse probes, each a loud syntax error
# =============================================================================

MISUSE: tuple[tuple[str, str], ...] = (
    ("swapped-order", "choose integer in 0 .. n excluding 3 up to 5"),
    ("doubled-clause", "choose integer in 0 .. 5 excluding 3 excluding 4"),
    ("comma-list", "choose integer in 0 .. 5 excluding 3, 4"),
    ("missing-operand", "choose integer in 0 .. 5 excluding"),
    ("before-range", "choose integer excluding 3 in 0 .. 5"),
    ("except-spelling", "choose integer in 0 .. 5 except 3"),
    ("but-not-spelling", "choose integer in 0 .. 5 but not 3"),
    ("without-spelling", "choose integer in 0 .. 5 without 3"),
    ("fused-keyword", "choose integer in 0 .. 5 excluding3"),
)


@pytest.mark.parametrize(("case", "choose"), MISUSE, ids=[m[0] for m in MISUSE])
def test_misuse_sentence_is_a_syntax_error(case: str, choose: str) -> None:
    _rejects(_game(choose), "syntax error")


def test_excluding_outside_a_choose_is_a_syntax_error() -> None:
    _rejects(
        _game("0", extra="deal 2 cards from deck to hand[0] excluding 1"),
        "syntax error",
    )


def test_exclusion_extends_as_far_right_as_possible() -> None:
    """`excluding k - 1` is one operand — the exclusion, not a subtraction from
    the choose — and the statement on the next line is untouched.

    red under: re-admit `choose_expr` to `?primary` — the sentence then has
    a second derivation, `(choose ... excluding k) - 1`. Which derivation
    this cell sees is the parser's pick; the explicit-ambiguity cell
    `compound-then-statement` is what reddens, and it is the pin."""
    game = check_dsl(
        _game("choose integer in 0 .. n up to 5 excluding k - 1", extra="x[0] := x[0] + 10"),
        "t",
    )
    (choose,) = _chooses(game)
    assert isinstance(choose.excluding, n.BinOp) and choose.excluding.op == "-"
    assert choose.ceiling == 5
    played = _play(game, 0)
    assert played.candidates[0] == [0, 1, 3, 4, 5]


def test_choose_as_a_bare_operand_is_a_syntax_error() -> None:
    """A choose is an expression-level form, like a query: as an operator's
    operand it is parenthesized, never bare — the bare spelling is refused
    rather than read with the operator inside the choose's last clause.

    red under: re-admit `choose_expr` to `?primary` — both sentences then
    parse."""
    _rejects(_game("1 + choose integer in 0 .. 5"), "syntax error")
    # The mirror: a trailing operator belongs to the choose's last clause —
    # here the range's `hi` becomes the compound `5 * 2`, which is no literal.
    _rejects(_game("choose integer in 0 .. 5 * 2"), "statically known upper bound")


def test_parenthesized_choose_is_an_operand() -> None:
    game = check_dsl(_game("(choose integer in 0 .. 5 excluding 2) + 10"), "t")
    played = _play(game, 0)
    assert played.candidates == [[0, 1, 3, 4, 5], [0, 1, 3, 4, 5]]
    scores = play_game(game, random.Random(0)).scores
    assert all(10 <= v <= 15 and v != 12 for v in scores.values())


# =============================================================================
# Names stay names — `excluding` remains a legal identifier
# =============================================================================


def test_excluding_is_a_legal_name_and_the_exclusion_operand() -> None:
    """A state variable named `excluding` reads as a name in every expression
    position, the exclusion slot included.

    red under: add `excluding` to the grammar's NAME exclusion list — the
    declaration then fails to parse."""
    game = check_dsl(
        _game(
            "choose integer in 0 .. 5 excluding excluding",
            state=STATE + "  excluding : Integer = 2",
            extra="x[0] := x[0] + excluding",
        ),
        "t",
    )
    played = _play(game, 0)
    assert played.candidates[0] == [0, 1, 3, 4, 5]


# =============================================================================
# Explicit ambiguity — the trailing optional clause mints no `_ambig`
# =============================================================================

AMBIGUITY_SOURCES: tuple[tuple[str, str], ...] = (
    ("compound-then-statement", _game("choose integer in 0 .. n up to 5 excluding k - 1", extra="x[0] := 1")),
    ("both-clauses", _game("choose integer in 0 .. n up to 5 excluding k")),
    ("name-named-excluding", _game("choose integer in 0 .. 5 excluding excluding", state=STATE + "  excluding : Integer = 2")),
    ("nested-choose", _game("choose integer in 0 .. 5 excluding (choose integer in 0 .. 1)")),
)


@pytest.mark.parametrize(("case", "src"), AMBIGUITY_SOURCES, ids=[a[0] for a in AMBIGUITY_SOURCES])
def test_clause_parses_with_zero_ambiguity(case: str, src: str) -> None:
    explicit = Lark(
        _grammar(),
        parser="earley",
        ambiguity="explicit",
        propagate_positions=True,
        maybe_placeholders=True,
    )
    tree = explicit.parse(src)
    assert isinstance(tree, Tree)
    assert sum(1 for t in tree.iter_subtrees() if t.data == "_ambig") == 0


# =============================================================================
# IR — the key is present exactly when the clause is
# =============================================================================


def _choose_ir(game: n.Game) -> dict[str, Any]:
    emitted = ir.emit(game)

    def find(node: Any) -> Iterator[dict[str, Any]]:
        if isinstance(node, dict):
            if node.get("kind") == "choose":
                yield node
            for v in node.values():
                yield from find(v)
        elif isinstance(node, list):
            for v in node:
                yield from find(v)

    (choose,) = list(find(emitted))
    return choose


def test_ir_carries_the_exclusion_only_when_written() -> None:
    with_clause = _choose_ir(check_dsl(_game("choose integer in 0 .. 5 excluding k"), "t"))
    assert with_clause["excluding"] == {"kind": "name", "name": "k"} | {
        k: v for k, v in with_clause["excluding"].items() if k not in ("kind", "name")
    }
    assert with_clause["ceiling"] == 5
    without = _choose_ir(check_dsl(_game("choose integer in 0 .. 5"), "t"))
    assert "excluding" not in without


# =============================================================================
# The adapter — the excluded id leaves the legal set, the block does not move
# =============================================================================


def test_action_block_is_unchanged_and_the_excluded_id_is_absent() -> None:
    game = check_dsl(_game("choose integer in 0 .. 5 excluding k"), "t")
    space = ActionSpace.for_game(game)
    assert space._int_ceiling == 5
    played = _play(game, 0)
    legal = sorted(space.encode(c) for c in played.candidates[0])
    assert legal == [space.encode(v) for v in (0, 1, 2, 4, 5)]
    assert space.encode(3) not in legal


# =============================================================================
# The node-level bans are unchanged by the clause
# =============================================================================


def test_state_default_still_cannot_choose_with_the_clause() -> None:
    _rejects(
        _game("0", state=STATE + "  d : Integer = choose integer in 0 .. 5 excluding 2"),
        "cannot `choose`",
    )


# =============================================================================
# The corpus witness — Oh Hell's dealer hook, at the seam and on the wire
# =============================================================================


def test_oh_hell_dealer_is_offered_every_bid_but_the_forbidden_one() -> None:
    """Per hand: the three non-dealer seats are offered the whole range, the
    dealer is offered the range less `hand_size - total_bid` (nothing less
    when that number is out of range), and the announced bids never total
    the hand size."""
    game = check_source(OH_HELL)
    dealer_constrained = dealer_free = 0
    for seed in range(6):
        played = _play(game, seed)
        assert len(played.candidates) == 19 * 4
        for hand in range(19):
            cands = played.candidates[hand * 4 : hand * 4 + 4]
            picks = played.picks[hand * 4 : hand * 4 + 4]
            hand_size = cands[0][-1]
            full = list(range(hand_size + 1))
            assert cands[0] == cands[1] == cands[2] == full
            forbidden = hand_size - sum(picks[:3])
            if 0 <= forbidden <= hand_size:
                dealer_constrained += 1
                assert cands[3] == [v for v in full if v != forbidden]
            else:
                dealer_free += 1
                assert cands[3] == full
            assert sum(picks) != hand_size
    assert dealer_constrained and dealer_free


def test_oh_hell_announces_the_bid_it_scores() -> None:
    game = check_source(OH_HELL)
    played = _play(game, 0)
    # Every bid draw is announced to all four seats, in draw order, as drawn.
    announced = [
        a[1] for a in played.announces if isinstance(a[1], int) and not isinstance(a[1], bool)
    ]
    assert announced, "the bid draws are announced"
    assert announced == [render(p) for p in played.picks for _ in range(4)]


def test_oh_hell_carries_two_chooses_under_one_ceiling() -> None:
    game = check_source(OH_HELL)
    chooses = _chooses(game)
    assert [c.excluding is not None for c in chooses] == [True, False]
    assert {n.static_ceiling(c) for c in chooses} == {10}
    assert ActionSpace.for_game(game)._int_ceiling == 10
