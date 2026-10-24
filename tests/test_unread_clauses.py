"""A game clause nothing reads is refused at the clause.

property:   a clause some `_CLAUSE_GATES` row reads is refused, at the
            clause, when nothing the game writes meets one of its reader
            rows' tests; and for every reader position a game is refused
            with the clause or without it, never both. A clause its own
            Owner Guard refused draws that refusal alone.
domain:     reader clause x reader position x clause present/absent. The
            clause axis is every `clause` of a `role == "reader"` row of
            `resolve._CLAUSE_GATES`; the position axis is no reader, a phase
            statement, an offered move type's effect and a function nothing
            calls, the written text the gates themselves refuse in. A round
            is a statement, so the trump clause's reader stands in the phase
            and the move type only. The library positions are
            tests/test_suit_ranking.py's (an activated and a dormant library
            rule) and tests/test_library_clause_gates.py's (every library
            definition kind, on the `uses` line).
registry:   rows: `cardlang.resolve._CLAUSE_GATES` (`clause`, `role`);
            sentences: `cardlang.resolve._UNREAD_SENTENCES`; clause fields:
            `cardlang.ast.nodes.Game`; the trump clause's dead-container
            cells: tests/test_trump_slot_class.py::test_dead_clause_counts_written_rounds;
            the Trick Order's cells: tests/test_trick_order.py::test_partition_cell.
does not prove:  that a reader runs. A reader in a definition nothing runs
            reads the clause here (issue #932).
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from cardlang import resolve as R
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

_HOST = """game G {{
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  {clause}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    {body}
    score[0] := 1
  }}
  winner: highest score
}}
{defs}
"""

READER_CLAUSES = sorted({row.clause for row in R._CLAUSE_GATES if row.role == "reader"})

# clause -> (the clause as written, its reader: an expression, or a statement
# for the trump clause, whose reader is a round)
_VEHICLES: dict[str, tuple[str, str]] = {
    "card_points": ("card_points { A: 1 }", "card_points(2 of spades)"),
    "suit_ranking": ("suit ranking: spades hearts diamonds clubs", "suit_value(spades)"),
    "trick_order": (
        "trick_order { trump: card.suit is hearts }",
        "if is_trump(2 of spades) then 1 else 0",
    ),
    "trump": (
        "trump: spades",
        "round play_to_trick from 0 over all players source hand into pile "
        "winner highest_trump_or_led_suit",
    ),
}
_STATEMENT_READERS = frozenset({"trump"})

POSITIONS = ("none", "phase", "move-type", "uncalled-function")


def _source(clause: str, position: str, declared: bool) -> str:
    text, reader = _VEHICLES[clause]
    body, defs = "", ""
    statement = reader if clause in _STATEMENT_READERS else f"score[0] := {reader}"
    if position == "phase":
        body = statement
    elif position == "move-type":
        body = "offer to 0 one of [m]"
        defs = f"move_type m {{ effect {{ {statement.replace('score[0]', 'score[actor]')} }} }}"
    elif position == "uncalled-function":
        defs = f"function r() = {reader}"
    return _HOST.format(clause=text if declared else "", body=body, defs=defs)


def _errors(src: str) -> list[str]:
    try:
        check_dsl(src, "g.cardlang")
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", [])
        lines = "\n".join(notes).splitlines() if notes else [str(exc)]
        return [line for line in lines if ": error: " in line]
    return []


def test_every_row_names_a_game_field() -> None:
    """Every row's clause is an `n.Game` field or a clause the game states by
    answering Kernel Definition Contracts (`resolve._DEFINITION_CLAUSES`),
    and no clause is both. red under: give a `_CLAUSE_GATES` row a `clause`
    neither spells."""
    names = {f.name for f in fields(n.Game)}
    assert not (names & set(R._DEFINITION_CLAUSES))
    assert {row.clause for row in R._CLAUSE_GATES} <= names | set(R._DEFINITION_CLAUSES)


def test_every_reader_clause_has_a_sentence_and_a_vehicle() -> None:
    """red under: add a `role="reader"` row on a clause `_UNREAD_SENTENCES`
    does not key."""
    assert set(R._UNREAD_SENTENCES) == set(READER_CLAUSES)
    assert set(_VEHICLES) == set(READER_CLAUSES)


@pytest.mark.parametrize("clause", READER_CLAUSES)
def test_every_reader_row_gates_on_its_clause(clause: str) -> None:
    """Each reader row refuses its construct exactly when its clause is
    absent, so "the clause is present" is the converse of the row's own gate.

    red under: file the `_SUIT_RANKING_CALLS` row under `clause="ranking"`."""
    with_clause = parse_text(_source(clause, "phase", True), "g.cardlang")
    without = parse_text(_source(clause, "phase", False), "g.cardlang")
    for row in R._CLAUSE_GATES:
        if row.role == "reader" and row.clause == clause:
            assert row.unmet(without) and not row.unmet(with_clause), row


CELLS = [
    pytest.param(clause, position, id=f"{clause}-{position}")
    for clause in READER_CLAUSES
    for position in POSITIONS
    if not (clause in _STATEMENT_READERS and position == "uncalled-function")
]


@pytest.mark.parametrize(("clause", "position"), CELLS)
def test_a_game_is_refused_with_the_clause_or_without_it_never_both(
    clause: str, position: str
) -> None:
    """With no reader, the clause is refused as read by nothing and the game
    without it is clean; with a reader anywhere written, the clause is read
    and the game without it is refused by the reader's own gate.

    red under: drop a reader row's `role="reader"` (its clause's no-reader
    cell checks clean with the clause)."""
    present = _errors(_source(clause, position, True))
    absent = _errors(_source(clause, position, False))
    if position == "none":
        assert len(present) == 1 and "is read by" in present[0], present
        assert absent == [], absent
    else:
        assert present == [], present
        assert absent and not any("is read by" in e for e in absent), absent


@pytest.mark.parametrize(
    ("clause", "malformed"),
    [
        pytest.param("suit_ranking", "suit ranking: spades spades hearts diamonds clubs", id="suit-ranking-repeat"),
        pytest.param("card_points", "card_points { ace: 1 }", id="card-points-unknown-rank"),
        pytest.param("trump", "trump: bogus", id="trump-unknown-suit"),
    ],
)
def test_a_clause_its_own_guard_refused_draws_that_refusal_alone(
    clause: str, malformed: str
) -> None:
    """The clause's Owner Guard hands its verdict over, so a malformed clause
    with no reader is told one thing.

    red under: drop the handover (`refused.add(...)`) in the clause's guard."""
    errors = _errors(_HOST.format(clause=malformed, body="", defs=""))
    assert len(errors) == 1 and "is read by" not in errors[0], errors


def test_go_fish_with_an_unread_table_is_refused() -> None:
    """The planted-fault witness: Go Fish, which reads no card points, with a
    `card_points { }` table added.

    red under: drop the `_CARD_POINTS_CALLS` row's `role="reader"`."""
    path = Path("docs/games/go-fish.cardlang")
    text = path.read_text()
    anchor = "  cards: standard52\n"
    assert text.count(anchor) == 1
    errors = _errors(text.replace(anchor, anchor + "  card_points { A: 1 }\n"))
    assert len(errors) == 1 and "card_points { } is read by nothing" in errors[0], errors
