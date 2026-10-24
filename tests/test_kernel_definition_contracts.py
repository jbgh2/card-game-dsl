"""Kernel Definition Contracts: the card facts a game answers by `function`.

The grid of issue #942, authored red before the implementation: a game
`function` named `is_trump`, `follow_class`, `card_strength` or `card_points`
answers the kernel's contract row, typed against it, and the
`card_points { }` table and each `trick_order { }` row lower to the function a
designer would write by hand (decisions.md "Trick Order", "Scoring has no
constructs of its own"; the rulings on issues #921 and #942).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a game answers each Kernel Definition Contract by name alone,
                 once, at the row's parameter and result, in either spelling;
                 the answer is a public fact of the card (hermetic by reach,
                 game-level state only, the Trick Order's reference order);
                 its absence is stated, never inferred; and no pass below the
                 parser can tell the two spellings apart.
domain:          the contract registry, iterated, crossed with: definition
                 state (answered, omitted, answered twice in each spelling
                 pair, answered by a library, mistyped name); signature
                 (parameter type, arity both ways, result type, the
                 permissive top, the parameter's own name); absence against
                 each consumer of the Trick Order and of card points;
                 hermeticity (each forbidden read, directly and through a
                 designer function); the reference order (every caller and
                 callee pair among the answers); the presence partition and
                 the unread law in the function spelling; the lowering (each
                 table and row form against its hand-written twin); the
                 library arms (a `requires` row, a library definition, a
                 `primitives { }` entry); a piece game; the run-time
                 witnesses (the census, a defaulted row called directly, the
                 spelling-neutral playout). The block spellings' own cells
                 stay in tests/test_trick_order.py and
                 tests/test_card_points.py.
registry:        contracts: `cardlang.kernel_contracts.KERNEL_DEFINITION_CONTRACTS`
                 and `TRICK_ORDER_CONTRACTS`; native registries:
                 `builtins.functions.BUILTIN_CALL_FUNCS`, `VALUE_NAMES`,
                 `PRIMITIVE_CALL_FUNCS`, `builtins.signatures.CALL_SIGS`,
                 `resolve._ROUND_QUERY_NAMES`; pronouns: `resolve._PRONOUNS`.
does not prove:  that every message earns its exact sentence: each cell reads
                 its refusal by needle, through one host game.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins import functions as F
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.kernel_contracts import (
    CONTRACTS,
    KERNEL_CONTRACT_NAMES,
    KERNEL_DEFINITION_CONTRACTS,
    TRICK_ORDER_CONTRACTS,
)
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _PRONOUNS, _ROUND_QUERY_NAMES
from cardlang.runtime.driver import play_game

_HOST = """game G {{
  players: 2
  max_length: 200
  cards: standard52
  {ranking}
  {clauses}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile  {zones}}}
  state {{ score[player] : Integer = 0  lead : Player = 0 {state}}}
  phase play {{
    {phase_state}
    shuffle deck
    deal 2 cards from deck to each hand
    {body}
    score[0] += 1
  }}
  winner: highest score
}}
{defs}
"""

_TRICK = (
    "round play_to_trick from lead over all players source hand into pile "
    "winner {winner}"
)
_BY_ORDER = _TRICK.format(winner="highest_by_trick_order")


def _source(
    *,
    clauses: str = "",
    body: str = "",
    defs: str = "",
    ranking: str = "ranking: aces high",
    zones: str = "",
    state: str = "",
    phase_state: str = "",
) -> str:
    return _HOST.format(
        clauses=clauses, body=body, defs=defs, ranking=ranking, zones=zones,
        state=state, phase_state=phase_state,
    )


def _diagnostics(source: str) -> list[str] | None:
    """Every error message, in bag order, or None for a clean check."""
    try:
        check_dsl(source, "contracts.cardlang")
    except DiagnosticError as exc:
        assert exc.diagnostic.span is not None, "a diagnostic without a span"
        notes = getattr(exc, "__notes__", []) or []
        return [exc.diagnostic.message, *notes]
    return None


@dataclass(frozen=True)
class Cell:
    id: str
    source: str
    needles: tuple[str, ...]  # empty = accept
    forbidden: tuple[str, ...] = ()
    count: int | None = None  # the whole bag's size, when the cell pins it


def _run(cell: Cell) -> None:
    found = _diagnostics(cell.source)
    if not cell.needles:
        assert found is None, "expected a clean check, got:\n" + "\n".join(found or [])
        return
    assert found is not None, "expected a diagnostic, the source checked clean"
    text = "\n".join(found)
    for needle in cell.needles:
        assert needle in text, f"expected {needle!r} in:\n{text}"
    for needle in cell.forbidden:
        assert needle not in text, f"did not expect {needle!r} in:\n{text}"
    if cell.count is not None:
        located = [m for m in found[1:] if ": error: " in m]
        assert max(1, len(located)) == cell.count, (
            f"expected {cell.count} diagnostic(s), got:\n{text}"
        )


# The cells green before the capability: the existing guards they keep.
# Every other cell is red until the capability lands.
_BORN_GREEN = frozenset({
    "is_trump-twice", "follow_class-twice", "card_strength-twice", "card_points-twice",
    "is_trump-mistyped-name-is-ordinary", "follow_class-mistyped-name-is-ordinary",
    "card_strength-mistyped-name-is-ordinary", "card_points-mistyped-name-is-ordinary",
    "cycle-through-card_points", "unread-ordinary-function-stays-clean",
    "unknown-rank-reports-once",
})
_RED = pytest.mark.xfail(strict=True, raises=AssertionError, reason="the capability (#942)")


def _params(cells: Iterable[Cell]) -> list[Any]:
    return [
        pytest.param(c, id=c.id, marks=() if c.id in _BORN_GREEN else (_RED,))
        for c in cells
    ]


# --- the host's reader of each contract --------------------------------------

_POINTS_READER = "score[1] := card_points(2 of spades)"
_CARD = "2 of spades"


def _consumer(name: str) -> str:
    """A body that reads contract `name` (with the Trick Order present where
    the name is one of its rows)."""
    if name == "card_points":
        return _POINTS_READER
    return _BY_ORDER


def _answer(name: str, body: str | None = None, param: str = "c : Card") -> str:
    """A well-formed answer to `name`, or one with the body given."""
    default = {
        "is_trump": "c.suit is hearts",
        "follow_class": "c.suit",
        "card_strength": "rank_value(c)",
        "card_points": "if c.rank is A then 11 else 0",
    }[name]
    return f"function {name}({param}) = {body if body is not None else default}"


def _defs(name: str, answer: str) -> str:
    """`answer`, plus `is_trump` when `name` is a Trick Order row that needs it."""
    if name in TRICK_ORDER_CONTRACTS and name != "is_trump":
        return _answer("is_trump") + "\n" + answer
    return answer


def _cell_source(name: str, answer: str, **kw: str) -> str:
    return _source(body=kw.pop("body", _consumer(name)), defs=_defs(name, answer), **kw)


NAMES = [c.name for c in KERNEL_DEFINITION_CONTRACTS]
ORDER_NAMES = list(TRICK_ORDER_CONTRACTS)


# =============================================================================
# 1. The registry: disjoint from every native namespace, iterated never listed
# =============================================================================


@_RED
def test_the_contract_registry_is_disjoint_from_every_native_namespace() -> None:
    """A Kernel Definition Contract is never the language's to define, and a
    Builtin never a game's: the two registries never meet.

    red under: adding `card_points` back to `BUILTIN_CALL_FUNCS`."""
    native = (
        F.BUILTIN_CALL_FUNCS
        | F.VALUE_NAMES
        | F.PRIMITIVE_CALL_FUNCS
        | frozenset(CALL_SIGS)
        | _ROUND_QUERY_NAMES
    )
    assert not (KERNEL_CONTRACT_NAMES & native), sorted(KERNEL_CONTRACT_NAMES & native)


def test_the_trick_order_rows_are_contracts_in_the_reference_order() -> None:
    """The Trick Order's rows are contract rows, and only `card_points` is
    outside the order. red under: dropping `follow_class` from
    `TRICK_ORDER_CONTRACTS`."""
    assert set(TRICK_ORDER_CONTRACTS) | {"card_points"} == set(KERNEL_CONTRACT_NAMES)
    assert TRICK_ORDER_CONTRACTS[0] == "is_trump"


def test_only_the_trick_order_rows_after_the_first_default() -> None:
    """Absence is stated for `is_trump` and `card_points`; the other two
    default. red under: giving `is_trump` a default."""
    assert {c.name for c in KERNEL_DEFINITION_CONTRACTS if c.defaulted} == set(
        TRICK_ORDER_CONTRACTS[1:]
    )


# =============================================================================
# 2. Definition state and signature, per contract
# =============================================================================


def _definition_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    for name in NAMES:
        row = CONTRACTS[name]
        add(Cell(f"{name}-answered", _cell_source(name, _answer(name)), ()))
        add(Cell(f"{name}-param-named-card",
                 _cell_source(name, _answer(name, body=_answer(name).split(" = ", 1)[1].replace("c.", "card.").replace("(c)", "(card)"), param="card : Card")),
                 ()))
        add(Cell(f"{name}-twice",
                 _cell_source(name, _answer(name) + "\n" + _answer(name)),
                 (f"duplicate function '{name}'",)))
        sig = f"answers the kernel's `{row.spelled}`, so it takes exactly one Card"
        add(Cell(f"{name}-param-player",
                 _cell_source(name, _answer(name, param="p : Player").replace("(c)", "(2 of spades)").replace("c.", "(2 of spades).")),
                 (sig,), forbidden=("shadows the native function",)))
        add(Cell(f"{name}-arity-zero",
                 _cell_source(name, f"function {name}() = " + {"is_trump": "true", "follow_class": "none", "card_strength": "1", "card_points": "1"}[name]),
                 (sig,), forbidden=("shadows the native function",)))
        add(Cell(f"{name}-arity-two",
                 _cell_source(name, _answer(name, param="c : Card, p : Player")),
                 (sig,), forbidden=("shadows the native function",)))
        wrong = {"is_trump": "c.rank", "follow_class": '"hearts"', "card_strength": "c.suit", "card_points": "c.rank"}[name]
        add(Cell(f"{name}-wrong-result",
                 _cell_source(name, _answer(name, body=wrong)),
                 (f"but the kernel reads `{row.spelled}`",)))
        top = "if c.rank is A then 1 else none" if name != "follow_class" else "if c.rank is A then 1 else c.suit"
        add(Cell(f"{name}-permissive-top",
                 _cell_source(name, _answer(name, body=top)),
                 ("types as `Any`",)))
        add(Cell(f"{name}-mistyped-name-is-ordinary",
                 _source(body=_POINTS_READER if name == "card_points" else "score[1] += 1",
                         clauses="card_points { A: 11 }" if name == "card_points" else "",
                         defs=_answer(name).replace(f"function {name}(", f"function {name}x(")),
                 ()))
    # Optional laundering on a strict row.
    add(Cell("is_trump-optional-result",
             _cell_source("is_trump", _answer("is_trump", body="if c.rank is A then true else none")),
             ("but the kernel reads `is_trump(card : Card) : Boolean`",)))
    return cells


@pytest.mark.parametrize("cell", _params(_definition_cells()))
def test_definition_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 3. Absence: stated, never inferred
# =============================================================================

_FALSE_FIX = "`function is_trump(c : Card) = false`"


def _absence_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    # `is_trump` omitted while a Trick Order consumer is written.
    add(Cell("no-is_trump-winner-slot", _source(body=_BY_ORDER), (_FALSE_FIX,)))
    add(Cell("no-is_trump-follows_lead",
             _source(body="score[1] := if follows_lead(2 of spades, pile) then 1 else 0"), (_FALSE_FIX,)))
    add(Cell("no-is_trump-winner-call",
             _source(body=f"{_BY_ORDER}\n    lead := highest_by_trick_order(pile)"), (_FALSE_FIX,)))
    for name in ORDER_NAMES:
        add(Cell(f"no-is_trump-{name}-call",
                 _source(body=f"score[1] := if {name}({_CARD}) is none then 1 else 0" if name == "follow_class"
                         else f"score[1] := if {name}({_CARD}) then 1 else 0" if name == "is_trump"
                         else f"score[1] := {name}({_CARD})"),
                 (_FALSE_FIX,)))
    # A Trick Order row answered with no `is_trump`: an orphan, whatever reads it.
    for name in ORDER_NAMES[1:]:
        add(Cell(f"orphan-{name}",
                 _source(body=_TRICK.format(winner="highest_of_led_suit"), defs=_answer(name)),
                 ("but the game declares no Trick Order", _FALSE_FIX)))
    # The defaults: a defaulted row is called directly in a Trick Order game.
    add(Cell("default-follow_class-called",
             _source(body=f"{_BY_ORDER}\n    score[1] := if follow_class({_CARD}) is spades then 1 else 0",
                     defs=_answer("is_trump")), ()))
    add(Cell("default-card_strength-called",
             _source(body=f"{_BY_ORDER}\n    score[1] := card_strength({_CARD})",
                     defs=_answer("is_trump")), ()))
    # T2: the defaulted strength with no `ranking:`.
    add(Cell("default-card_strength-without-ranking",
             _source(body=_BY_ORDER, defs=_answer("is_trump"), ranking=""),
             ("so strength defaults to `rank_value(card)`",)))
    add(Cell("answered-card_strength-without-ranking",
             _source(body=_BY_ORDER, defs=_answer("is_trump") + "\n" + _answer("card_strength", body="1"), ranking=""),
             ()))
    # Card points: a call with no answer.
    add(Cell("no-card_points-call", _source(body=_POINTS_READER),
             ("`card_points { }` table", "`function card_points(c : Card) = …`")))
    return cells


@pytest.mark.parametrize("cell", _params(_absence_cells()))
def test_absence_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 4. Hermeticity: each forbidden read, directly and through a function
# =============================================================================


def _forbidden_reads(name: str) -> list[tuple[str, str, str, str]]:
    """(id, body, needle, extra defs) per forbidden read, for an answer to
    `name` whose result is Integer or Boolean-shaped."""
    as_bool = name == "is_trump"
    def wrap(pred: str) -> str:
        if as_bool:
            return pred
        if name == "follow_class":
            return f"if {pred} then none else c.suit"
        return f"if {pred} then 1 else 0"
    reads = [
        ("zone-hand-0", wrap("any card in hand[0] where card.rank is A"), f"function `{name}` reads zone 'hand'", ""),
        ("zone-hand-bare", wrap("any card in hand where card.rank is A"), f"function `{name}` reads", ""),
        ("choose", wrap("(choose card from pile) is c"), f"function `{name}` makes a `choose`", ""),
        ("phase-state", wrap("late"), f"function `{name}` reads state variable 'late'", ""),
    ]
    for pronoun in sorted(_PRONOUNS):
        reads.append((f"pronoun-{pronoun}", wrap(f"{pronoun} is none"), f"function `{name}` reads the pronoun '{pronoun}'", ""))
    return reads


def _hermeticity_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    for name in NAMES:
        for rid, body, needle, _ in _forbidden_reads(name):
            phase_state = "state { late : Boolean = false }" if rid == "phase-state" else ""
            add(Cell(f"{name}-direct-{rid}",
                     _cell_source(name, _answer(name, body=body), phase_state=phase_state),
                     (needle,)))
            helper = f"function helper(c : Card) = {body}"
            via = {"is_trump": "helper(c)", "follow_class": "helper(c)", "card_strength": "helper(c)", "card_points": "helper(c)"}[name]
            add(Cell(f"{name}-through-{rid}",
                     _cell_source(name, helper + "\n" + _answer(name, body=via), phase_state=phase_state),
                     (needle.split(" reads")[0].split(" makes")[0], "through function `helper`")))
    # The control: a pure answer reading public state checks clean.
    add(Cell("is_trump-reads-public-state",
             _cell_source("is_trump", _answer("is_trump", body="c.suit is trump_suit"), state="  trump_suit : Suit = hearts"),
             ()))
    return cells


@pytest.mark.parametrize("cell", _params(_hermeticity_cells()))
def test_hermeticity_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 5. The reference order: every caller x callee among the answers
# =============================================================================


def _call(callee: str) -> str:
    return {
        "is_trump": "is_trump(c)",
        "follow_class": "follow_class(c) is none",
        "card_strength": "card_strength(c) > 3",
        "card_points": "card_points(c) > 3",
    }[callee]


def _reference_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    every = ORDER_NAMES + ["card_points"]
    for caller in every:
        for callee in every:
            if caller == callee:
                continue
            body = {
                "is_trump": _call(callee),
                "follow_class": f"if {_call(callee)} then none else c.suit",
                "card_strength": f"if {_call(callee)} then 1 else 0",
                "card_points": f"if {_call(callee)} then 1 else 0",
            }[caller]
            defs = [_answer(n_) for n_ in every if n_ not in (caller,)]
            defs.append(_answer(caller, body=body))
            source = _source(body=f"{_BY_ORDER}\n    {_POINTS_READER}", defs="\n".join(defs))
            later = (
                caller in ORDER_NAMES and callee in ORDER_NAMES
                and ORDER_NAMES.index(callee) > ORDER_NAMES.index(caller)
            )
            if later:
                add(Cell(f"{caller}-calls-{callee}", source, ("comes after it in the Trick Order",)))
            elif callee == "card_points" and caller != "card_points":
                # card_points' own answer calls nothing back: no cycle.
                add(Cell(f"{caller}-calls-{callee}", source, ()))
            elif caller == "card_points":
                add(Cell(f"{caller}-calls-{callee}", source, ()))
            else:
                add(Cell(f"{caller}-calls-{callee}", source, ()))
    # A cycle through card_points.
    cycle = "\n".join([
        _answer("is_trump"),
        _answer("card_strength", body="card_points(c)"),
        _answer("card_points", body="card_strength(c)"),
    ])
    add(Cell("cycle-through-card_points", _source(body=f"{_BY_ORDER}\n    {_POINTS_READER}", defs=cycle), ("recursive",)))
    return cells


@pytest.mark.parametrize("cell", _params(_reference_cells()))
def test_reference_order_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 6. The presence partition and the unread law, in the function spelling
# =============================================================================


def _partition_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    is_trump = _answer("is_trump", body="c.suit is spades")
    # h10: a round-configured winner beside an `is_trump` answer -- ONE refusal.
    add(Cell("standard-winner-beside-is_trump",
             _source(body=_TRICK.format(winner="highest_trump_or_led_suit"), defs=is_trump),
             ("beside function `is_trump`", "highest_by_trick_order"),
             forbidden=("none is stated",), count=1))
    add(Cell("game-trump-beside-is_trump",
             _source(clauses="trump: spades", body=_BY_ORDER, defs=is_trump),
             ("`trump: spades` beside function `is_trump`",)))
    add(Cell("round-trump-beside-is_trump",
             _source(body=_BY_ORDER + " trump spades", defs=is_trump),
             ("beside function `is_trump`",)))
    # The unread law: the Trick Order is ONE clause, its own answers never its
    # readers (h05), and follows_lead alone reads it (h06).
    add(Cell("unread-is_trump",
             _source(body="score[1] += 1", defs=is_trump),
             ("declares a Trick Order nothing reads",)))
    add(Cell("unread-self-read",
             _source(body="score[1] += 1",
                     defs=is_trump + "\n" + _answer("card_strength", body="if is_trump(c) then 100 else rank_value(c)")),
             ("declares a Trick Order nothing reads",)))
    add(Cell("read-only-by-follows_lead",
             _source(body="score[1] := if follows_lead(2 of spades, pile) then 1 else 0",
                     defs=is_trump + "\n" + _answer("card_strength", body="if is_trump(c) then 100 else rank_value(c)")),
             ()))
    add(Cell("unread-card_points",
             _source(body="score[1] += 1", defs=_answer("card_points")),
             ("function `card_points` is read by nothing",)))
    add(Cell("unread-ordinary-function-stays-clean",
             _source(body="score[1] += 1", defs="function pts(c : Card) = 1"),
             ()))
    return cells


@pytest.mark.parametrize("cell", _params(_partition_cells()))
def test_partition_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 7. Two spellings, one answer
# =============================================================================


def _both_spellings_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    add(Cell("card_points-table-and-function",
             _source(clauses="card_points { A: 11 }", body=_POINTS_READER, defs=_answer("card_points")),
             ("`card_points` is answered twice",)))
    for key, name in (("trump", "is_trump"), ("follow_class", "follow_class"), ("card_strength", "card_strength")):
        rows = "trump: card.suit is hearts" + (f"  {key}: " + {"follow_class": "card.suit", "card_strength": "rank_value(card)"}[key] if key != "trump" else "")
        add(Cell(f"{name}-row-and-function",
                 _source(clauses=f"trick_order {{ {rows} }}", body=_BY_ORDER, defs=_answer(name)),
                 (f"`{name}` is answered twice",)))
    # The double report: one unknown rank is one diagnostic.
    add(Cell("unknown-rank-reports-once",
             _source(clauses="card_points { Zed: 11 }", body=_POINTS_READER),
             ("card_points names unknown rank 'Zed'",), count=1))
    return cells


@pytest.mark.parametrize("cell", _params(_both_spellings_cells()))
def test_both_spellings_cell(cell: Cell) -> None:
    _run(cell)


def _stripped(node: Any) -> Any:
    """`node` with every span and the lowering stamp cleared, recursively."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        changes: dict[str, Any] = {}
        for f in dataclasses.fields(node):
            value = getattr(node, f.name)
            if f.name in ("span", "spelled_as"):
                changes[f.name] = None
            else:
                changes[f.name] = _stripped(value)
        return dataclasses.replace(node, **changes)
    if isinstance(node, tuple):
        return tuple(_stripped(v) for v in node)
    return node


# (block clause, the hand-written function it is)
_LOWERINGS: list[tuple[str, str, str]] = [
    ("table-named-key", "card_points { A: 11 }", "function card_points(card : Card) = if card.rank is A then 11 else 0"),
    ("table-numeric-key", 'card_points { 10: 10 }', 'function card_points(card : Card) = if card.rank is "10" then 10 else 0'),
    ("table-negative", "card_points { A: -25 }", "function card_points(card : Card) = if card.rank is A then -25 else 0"),
    ("table-else", "card_points { A: 11  else: 2 }", "function card_points(card : Card) = if card.rank is A then 11 else 2"),
    ("table-rows",
     'card_points { A: 11  10: 10  K: 4 }',
     'function card_points(card : Card) = if card.rank is A then 11 elif card.rank is "10" then 10 elif card.rank is K then 4 else 0'),
    ("row-trump", "trick_order { trump: card.suit is hearts }", "function is_trump(card : Card) = card.suit is hearts"),
    ("row-follow_class", "trick_order { trump: false  follow_class: card.suit }",
     "function is_trump(card : Card) = false\nfunction follow_class(card : Card) = card.suit"),
    ("row-card_strength", "trick_order { trump: false  card_strength: rank_value(card) }",
     "function is_trump(card : Card) = false\nfunction card_strength(card : Card) = rank_value(card)"),
]


@_RED
@pytest.mark.parametrize(("label", "block", "written"), _LOWERINGS, ids=[x[0] for x in _LOWERINGS])
def test_the_lowering_is_the_hand_written_function(label: str, block: str, written: str) -> None:
    """Each block form parses to the `FunctionDef` a designer would write,
    node for node, modulo spans and the stamp that names the spelling."""
    lowered = parse_text(_source(clauses=block), "a.cardlang")
    hand = parse_text(_source(defs=written), "b.cardlang")
    def answers(g: n.Game) -> list[Any]:
        return sorted(
            (_stripped(f) for f in g.functions if f.name in KERNEL_CONTRACT_NAMES),
            key=lambda f: f.name,
        )
    got = answers(lowered)
    assert got, "the block lowered to no answer"
    assert got == answers(hand)
    assert all(
        getattr(f, "spelled_as", None) is not None
        for f in lowered.functions if f.name in KERNEL_CONTRACT_NAMES
    )


# =============================================================================
# 8. Libraries and Primitive entries
# =============================================================================

_LIB_HOST = """game G {{
  uses contractlib
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  {clauses}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    score[1] := lib_points(2 of spades)
    score[0] := 1
  }}
  winner: highest score
}}
{defs}
"""

_LIB = """library contractlib {{
  requires {{
    {rows}
  }}
  function lib_points(c : Card) = {call}
  {extra}
}}
"""


def _library_bag(monkeypatch: pytest.MonkeyPatch, library: str, host: str) -> list[str] | None:
    built = parse_library(library, "docs/libraries/contractlib.cardlang")
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({"contractlib"}))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: built)
    return _diagnostics(host)


def _library_cells() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """(id, library text, host text, needles) -- empty needles = accept."""
    out: list[tuple[str, str, str, tuple[str, ...]]] = []
    for row in KERNEL_DEFINITION_CONTRACTS:
        name = row.name
        call = f"if {name}(c) then 1 else 0" if name == "is_trump" else (
            f"if {name}(c) is none then 1 else 0" if name == "follow_class" else f"{name}(c)")
        answer = _answer(name)
        if name in ORDER_NAMES[1:]:
            answer = _answer("is_trump") + "\n" + answer
        out.append((f"requires-{name}-answered",
                    _LIB.format(rows=row.spelled, call=call, extra=""),
                    _LIB_HOST.format(clauses="", defs=answer), ()))
        out.append((f"requires-{name}-unanswered",
                    _LIB.format(rows=row.spelled, call=call, extra=""),
                    _LIB_HOST.format(clauses="", defs=""),
                    (f"function {name}(", )))
        wrong = row.spelled.replace(row.result_spelling, "Player")
        out.append((f"requires-{name}-wrong-signature",
                    _LIB.format(rows=wrong, call="1", extra=""),
                    _LIB_HOST.format(clauses="", defs=answer),
                    ("but the kernel's contract is",)))
        out.append((f"library-defines-{name}",
                    _LIB.format(rows="", call="1", extra=_answer(name)),
                    _LIB_HOST.format(clauses="", defs=""),
                    ("only a game answers it",)))
    out.append(("requires-card_points-answered-by-the-table",
                _LIB.format(rows=CONTRACTS["card_points"].spelled, call="card_points(c)", extra=""),
                _LIB_HOST.format(clauses="card_points { A: 11 }", defs=""), ()))
    out.append(("requires-card_points-unanswered-names-the-table",
                _LIB.format(rows=CONTRACTS["card_points"].spelled, call="card_points(c)", extra=""),
                _LIB_HOST.format(clauses="", defs=""), ("card_points { ",)))
    return out


@_RED
@pytest.mark.parametrize(
    ("label", "library", "host", "needles"), _library_cells(), ids=[c[0] for c in _library_cells()]
)
def test_library_cell(
    monkeypatch: pytest.MonkeyPatch, label: str, library: str, host: str, needles: tuple[str, ...]
) -> None:
    found = _library_bag(monkeypatch, library, host)
    if not needles:
        assert found is None, "expected a clean check, got:\n" + "\n".join(found or [])
        return
    assert found is not None, "expected a diagnostic, the source checked clean"
    text = "\n".join(found)
    for needle in needles:
        assert needle in text, f"expected {needle!r} in:\n{text}"


@_RED
@pytest.mark.parametrize("name", NAMES)
def test_a_primitive_entry_may_not_take_a_contract_name(name: str) -> None:
    source = _source(clauses=f"primitives {{ {name}(c : Card) : Integer }}", body="score[1] += 1")
    found = _diagnostics(source)
    assert found is not None, "expected a diagnostic, the source checked clean"
    assert f"answers the kernel's `{CONTRACTS[name].spelled}`" in "\n".join(found), "\n".join(found)


@_RED
@pytest.mark.parametrize("name", NAMES)
def test_a_piece_game_answers_no_card_contract(name: str) -> None:
    source = (
        "game P {\n  players: 2\n  pieces: xo_marks\n  max_length: 60\n"
        "  zones { box : Deck  reserve[player] : PlayerPile<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase play {\n    move all pieces from box where piece.side is x to reserve[0]\n"
        "    score[0] += 1\n  }\n  winner: highest score\n}\n"
        f"{_answer(name)}\n"
    )
    found = _diagnostics(source)
    assert found is not None, "expected a diagnostic, the source checked clean"
    assert "played with pieces" in "\n".join(found), "\n".join(found)


# =============================================================================
# 9. Witnesses: the planted faults and the run-time cells
# =============================================================================


def test_hearts_value_name_probe_is_still_refused() -> None:
    """#145's arm stands beside the contracts: a game function named like a
    value Builtin its own slot names is refused."""
    source = _source(body=_TRICK.format(winner="highest_of_led_suit"),
                     defs="function highest_of_led_suit(p : Player) = 1")
    found = _diagnostics(source)
    assert found is not None
    assert "that slot always runs the language's `highest_of_led_suit`" in "\n".join(found)


@_RED
def test_a_wrong_parameter_is_the_contracts_refusal_alone() -> None:
    """P7': `function is_trump(p : Player) = true` on a host whose winner reads
    the Trick Order meets only the contract's parameter check."""
    found = _diagnostics(_source(body=_BY_ORDER, defs="function is_trump(p : Player) = true"))
    assert found is not None
    text = "\n".join(found)
    assert "answers the kernel's `is_trump(card : Card) : Boolean`, so it takes exactly one Card" in text
    assert "shadows the native function" not in text
    assert "declares none" not in text


def _trace(source: str, seed: int) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    play_game(
        check_dsl(source, "contracts.cardlang"),
        random.Random(seed),
        tracer=lambda kind, data: events.append((kind, data)),
    )
    return events


@pytest.mark.xfail(strict=True, raises=DiagnosticError, reason="the capability (#942)")
def test_the_table_and_the_function_play_the_same_game() -> None:
    """P2: a point table and the function it lowers to play byte-identically,
    the end-of-game census's `total_value` included."""
    reader = f"{_BY_ORDER}\n    score[1] += card_points(top_of(pile))"
    table = _source(clauses="card_points { A: 11  K: 4 }", body=reader, defs=_answer("is_trump"))
    function = _source(body=reader, defs=_answer("is_trump") + "\n"
                       + "function card_points(c : Card) = if c.rank is A then 11 elif c.rank is K then 4 else 0")
    for seed in (1, 2, 3, 5, 11, 42):
        a, b = _trace(table, seed), _trace(function, seed)
        assert a == b, f"seed {seed}: the two spellings diverge"
        ends = [d for k, d in a if k == "game_end"]
        assert ends and "total_value" in ends[0]


@pytest.mark.xfail(strict=True, raises=DiagnosticError, reason="the capability (#942)")
def test_the_census_reads_a_hand_written_card_points() -> None:
    """The census sums the game's answer, whichever spelling wrote it: a
    function counting every ace 11 totals 44 over the full deck."""
    source = _source(body=_POINTS_READER,
                     defs="function card_points(c : Card) = if c.rank is A then 11 else 0")
    events = _trace(source, 1)
    ends = [d for k, d in events if k == "game_end"]
    assert ends and ends[0]["total_value"] == 44, ends
