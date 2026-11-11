"""The Checker Query: every place a position can land, crossed with its three answers.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        At every position of a game file the checker accepts, the
                 Checker Query gives each of its three answers -- the names in
                 scope, the Type, what each seat sees -- or a told refusal
                 carrying its Diagnostic Code that names what can be answered
                 nearby; a position the file or its game does not hold is
                 refused whole; a file the checker refuses gets the checker's
                 refusal and no answer.
domain:          Two axes. The node axis is every member of the `Node` union,
                 crossed with the three answers and run over every instance
                 in the game text of every corpus game: each kind is answered
                 there, refused in the code its cell names, or placed in
                 `NOT_IN_CHECKED_TEXT` as a kind no checked game's text holds,
                 which that cell runs to show. The expected column is authored
                 from the language's own partitions: every node has a scope,
                 an expression has a Type and nothing else does, and a site
                 (`SITE_KINDS`) or an expression in a site's clause has an
                 answer for what each seat sees. The position axis is
                 `POSITION_CELLS`: the places in a file that are in no node or
                 in no game -- a comment, a blank line, past a line's end or
                 the file's, line or column 0, a Markdown file's prose and
                 fence -- and a keyword, a comment and a blank line inside a
                 node, which are answered as that node. Columns count
                 characters of the file's lines as `check` reports them, a tab
                 one column.
registry:        the node axis -- `get_args(n.Node)`, the expression and
                 statement axes `get_args(n.Expr)`, `get_args(n.Stmt)`; the
                 corpus -- `docs/games/*.cardlang`; the per-seat answer's
                 agreement with the adapter -- tests/test_query_seats.py.
held by:         Derived and Pinned: the node axis is the AST union, so a node
                 kind added to it arrives as uncovered cells; each answer is
                 read from its pass's record, so a cell here can only redden
                 when a record lacks an entry or the query reads the wrong one.
does not prove:  that an answer is the RIGHT one at a position no corpus game
                 holds. A kind is run at every instance the corpus writes, so
                 a slot no game uses is unrun for it. Nodes the parse builder
                 lowers from one row of text (a `card_points { }` row) share
                 that row's span, and the query answers at the innermost of
                 them, which is text nobody wrote.
"""

from __future__ import annotations

import contextlib
import io
import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, fields, is_dataclass
from functools import cache
from pathlib import Path
from typing import get_args

import pytest

from cardlang import cli, query
from cardlang.ast import nodes as n
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Span, Told
from cardlang.query import Answer, Checked, ask, ask_path, checked_text, render, scope_at, seats_at, type_at
from cardlang.records import Kind, UnreadableEnvelope, query_envelope, read_envelope
from cardlang.runtime.errors import GameRegistrationError

REPO = Path(__file__).resolve().parent.parent
GAMES = REPO / "docs" / "games"
HEARTS = GAMES / "hearts.cardlang"
CHEAT = GAMES / "cheat.cardlang"
TIC_TAC_TOE = GAMES / "tic-tac-toe.cardlang"
KUHN = GAMES / "kuhn-poker.cardlang"
SKELETON_MD = REPO / "tests" / "fixtures" / "skeleton.md"

NODE_KINDS: tuple[type, ...] = get_args(n.Node)
EXPR_KINDS: tuple[type, ...] = get_args(n.Expr)
STMT_KINDS: tuple[type, ...] = get_args(n.Stmt)

#: The parts of a game whose running moves a card or asks a seat.
SITE_KINDS: tuple[type, ...] = (
    n.Transfer,
    n.EachSimultaneous,
    n.EpistemicOp,
    n.Offer,
    n.Choose,
    n.TrickRound,
    n.ClimbRound,
)

#: Node kinds with a span that no checked game's text holds, and why.
NOT_IN_CHECKED_TEXT: dict[type, str] = {
    n.Library: "a family library's whole text; a game file holds none",
    n.UsesDecl: "the resolver splices the library it names and drops the line",
    n.RequireDecl: "written only in a family library",
    n.MoveContract: "written only in a family library",
    n.FunctionContract: "written only in a family library",
    n.ProcedureContract: "written only in a family library",
    n.Block: "made by procedure expansion, after the passes the query reads",
}

#: The slots whose expression the type checker reads without inferring a
#: Type, so the Type Record holds none there (issue #1107).
UNTYPED_SLOTS: frozenset[tuple[type, str]] = frozenset(
    {
        (n.AssignStmt, "target"),
        (n.RotateStmt, "target"),
        (n.Subscript, "obj"),
        (n.Demands, "expr"),
        (n.RuleDef, "exempts"),
        (n.RuleDef, "if_impossible"),
    }
)

ANSWERS = ("scope", "type", "seats")
ANSWERED = "answered"


def _kind_id(kind: object) -> str:
    return kind.__name__ if isinstance(kind, type) else str(kind)


def _slot_id(slot: object) -> str:
    assert isinstance(slot, tuple)
    return f"{_kind_id(slot[0])}.{slot[1]}"


def _has_span_field(kind: type) -> bool:
    return any(f.name == "span" for f in fields(kind))


# --- the corpus, checked once, with every node's place ------------------------


@dataclass(frozen=True)
class Placed:
    """One node of a checked game's text, the nodes enclosing it, and the
    slot it fills in its parent."""

    node: object
    chain: tuple[object, ...]
    slot: tuple[type, str] | None


def _placed(node: object, chain: tuple[object, ...], slot: tuple[type, str] | None) -> Iterator[Placed]:
    if not is_dataclass(node) or isinstance(node, Span):
        return
    inner = (*chain, node)
    yield Placed(node, inner, slot)
    for f in fields(node):
        value = getattr(node, f.name)
        for child in value if isinstance(value, tuple) else (value,):
            yield from _placed(child, inner, (type(node), f.name))


@cache
def _corpus() -> tuple[tuple[Checked, tuple[Placed, ...]], ...]:
    out = []
    for path in sorted(GAMES.glob("*.cardlang")):
        checked = checked_text(path.read_text(), str(path), markdown=False)
        placed = tuple(
            p
            for p in _placed(checked.game, (), None)
            if isinstance(span := getattr(p.node, "span", None), Span)
            and span.source_name == checked.source_name
        )
        out.append((checked, placed))
    return tuple(out)


def _outcome(answer: object) -> str:
    return answer.diagnostic.code.slug if isinstance(answer, Told) else ANSWERED


def _expected_seats(placed: Placed) -> str:
    """A site, or an expression in a site's clause: the innermost node, then
    its expression-only enclosers, up to the first that is not an
    expression."""
    for node in reversed(placed.chain):
        if isinstance(node, SITE_KINDS):
            return ANSWERED
        if isinstance(node, n.EachSimultaneous):
            return ANSWERED
        if not isinstance(node, EXPR_KINDS):
            return Code.NOTHING_SEEN_HERE.slug
    return Code.NOTHING_SEEN_HERE.slug


def _expected(placed: Placed, answer: str) -> str:
    if answer == "scope":
        return ANSWERED
    if answer == "type":
        return ANSWERED if isinstance(placed.node, EXPR_KINDS) else Code.NOT_AN_EXPRESSION.slug
    return _expected_seats(placed)


_ASK = {"scope": scope_at, "type": type_at, "seats": seats_at}


@cache
def _mismatches() -> dict[tuple[str, str], list[str]]:
    """Every instance whose answer differs from the expected column, by
    (kind, answer), less the slots `UNTYPED_SLOTS` holds."""
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for checked, placed in _corpus():
        for p in placed:
            for answer in ANSWERS:
                if answer == "type" and p.slot in UNTYPED_SLOTS:
                    continue
                got = _outcome(_ASK[answer](checked, p.chain))
                want = _expected(p, answer)
                if got != want:
                    span = getattr(p.node, "span")
                    out[(type(p.node).__name__, answer)].append(
                        f"{span.source_name}:{span.line}:{span.column} got {got}, want {want}"
                    )
    return out


@cache
def _kinds_present() -> frozenset[type]:
    return frozenset(type(p.node) for _checked, placed in _corpus() for p in placed)


# --- the node axis -----------------------------------------------------------


def test_every_node_kind_is_placed() -> None:
    """A node kind with a span is in some corpus game's checked text, or is
    named in `NOT_IN_CHECKED_TEXT`; a kind with no span field is located only
    through the node holding it."""
    unplaced = [
        kind.__name__
        for kind in NODE_KINDS
        if _has_span_field(kind) and kind not in _kinds_present() and kind not in NOT_IN_CHECKED_TEXT
    ]
    assert not unplaced, f"node kinds no corpus game's checked text holds: {unplaced}"


@pytest.mark.parametrize("kind", sorted(NOT_IN_CHECKED_TEXT, key=_kind_id), ids=_kind_id)
def test_a_kind_named_absent_is_absent(kind: type) -> None:
    assert kind not in _kinds_present(), NOT_IN_CHECKED_TEXT[kind]


@pytest.mark.parametrize("answer", ANSWERS)
@pytest.mark.parametrize(
    "kind",
    [k for k in NODE_KINDS if _has_span_field(k) and k not in NOT_IN_CHECKED_TEXT],
    ids=_kind_id,
)
def test_node_kind_answer(kind: type, answer: str) -> None:
    """Every instance of the kind in the corpus's checked text answers as
    the expected column says."""
    if kind not in _kinds_present():
        pytest.fail(f"{kind.__name__} has no instance; `test_every_node_kind_is_placed` names it")
    wrong = _mismatches().get((kind.__name__, answer), [])
    assert not wrong, "\n".join(wrong[:5])


@pytest.mark.parametrize("slot", sorted(UNTYPED_SLOTS, key=_slot_id), ids=_slot_id)
@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1107")
def test_an_expression_in_an_untyped_slot_has_a_type(slot: tuple[type, str]) -> None:
    untyped = [
        f"{getattr(p.node, 'span').line}"
        for checked, placed in _corpus()
        for p in placed
        if p.slot == slot and isinstance(p.node, EXPR_KINDS)
        and isinstance(type_at(checked, p.chain), Told)
    ]
    assert not untyped


def test_every_untyped_slot_is_a_real_slot() -> None:
    """Each slot `UNTYPED_SLOTS` excuses holds an untyped expression in the
    corpus, so the list shrinks with the fix rather than going stale.
    red under: add `(n.BinOp, "left")` to `UNTYPED_SLOTS`."""
    for slot in UNTYPED_SLOTS:
        assert any(
            p.slot == slot and isinstance(type_at(checked, p.chain), Told)
            for checked, placed in _corpus()
            for p in placed
        ), slot


# --- the position axis ---------------------------------------------------------


@dataclass(frozen=True)
class PositionCell:
    path: Path
    line: int
    column: int
    outcome: str
    words: str | None = None


POSITION_CELLS: dict[str, PositionCell] = {
    "header comment": PositionCell(HEARTS, 1, 1, Code.POSITION_OUTSIDE_THE_GAME.slug),
    "blank line between top-level items": PositionCell(HEARTS, 118, 1, Code.POSITION_OUTSIDE_THE_GAME.slug),
    "comment between top-level items": PositionCell(HEARTS, 119, 4, Code.POSITION_OUTSIDE_THE_GAME.slug),
    "line 0": PositionCell(HEARTS, 0, 1, Code.POSITION_OUTSIDE_THE_FILE.slug),
    "column 0": PositionCell(HEARTS, 24, 0, Code.POSITION_OUTSIDE_THE_FILE.slug),
    "past the end of a line": PositionCell(HEARTS, 24, 40, Code.POSITION_OUTSIDE_THE_FILE.slug),
    "past the end of an empty line": PositionCell(HEARTS, 37, 2, Code.POSITION_OUTSIDE_THE_FILE.slug),
    "an empty line inside the game": PositionCell(HEARTS, 37, 1, ANSWERED, "the game"),
    "the end of a line": PositionCell(HEARTS, 24, 13, ANSWERED, "the game"),
    "past the end of the file": PositionCell(HEARTS, 10_000, 1, Code.POSITION_OUTSIDE_THE_FILE.slug),
    "indentation inside the game": PositionCell(HEARTS, 24, 1, ANSWERED, "the game"),
    "a comment inside a block": PositionCell(HEARTS, 39, 9, ANSWERED, "a declaration"),
    "a keyword of a statement": PositionCell(HEARTS, 65, 10, ANSWERED, "a movement"),
    "an operator between operands": PositionCell(HEARTS, 67, 28, ANSWERED, "an expression"),
    "a name": PositionCell(HEARTS, 66, 16, ANSWERED, "a name"),
    "an assignment's operator": PositionCell(HEARTS, 86, 14, ANSWERED, "an assignment"),
    "a rule after the game block": PositionCell(HEARTS, 122, 3, ANSWERED, "a rule"),
    "a `uses` line": PositionCell(KUHN, 33, 3, ANSWERED, "the game"),
    "Markdown prose": PositionCell(SKELETON_MD, 3, 1, Code.POSITION_OUTSIDE_THE_GAME.slug),
    "Markdown fence": PositionCell(SKELETON_MD, 8, 1, Code.POSITION_OUTSIDE_THE_GAME.slug),
    "Markdown game text": PositionCell(SKELETON_MD, 15, 5, ANSWERED, "a zone declaration"),
}


@pytest.mark.parametrize("name", sorted(POSITION_CELLS))
def test_position_cell(name: str) -> None:
    cell = POSITION_CELLS[name]
    answer = ask_path(cell.path, cell.line, cell.column)
    if cell.outcome == ANSWERED:
        assert answer.located is not None, render(answer)
        assert answer.exit_code == 0
        assert answer.located.words == cell.words, answer.located
        assert answer.scope is not None and answer.type is not None and answer.seats is not None
    else:
        assert answer.located is None
        assert [t.diagnostic.code.slug for t in answer.refused] == [cell.outcome]
        assert answer.exit_code == 2


def test_a_markdown_answer_counts_the_file_s_lines() -> None:
    """A position in a Markdown game is the file's line, and the answer's
    place is too, never the fenced block's."""
    answer = ask_path(SKELETON_MD, 15, 5)
    assert answer.located is not None
    assert (answer.located.span.line, answer.located.span.column) == (15, 5)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1108")
def test_scope_lists_only_live_state_at_a_statement() -> None:
    """Hearts' `passing` phase cannot read `play`'s `leader`."""
    answer = ask_path(HEARTS, 65, 9)
    assert answer.scope is not None and not isinstance(answer.scope, Told)
    assert "leader" not in {s.name for s in answer.scope.names}


def test_scope_at_a_name_lists_only_what_may_stand_there() -> None:
    """At a movement's source, only what the slot takes: no State Variable."""
    answer = ask_path(HEARTS, 66, 16)
    assert answer.scope is not None and not isinstance(answer.scope, Told)
    sorts = {s.sort for s in answer.scope.names}
    assert "state-variable" not in sorts and "zone" in sorts


# --- the witnesses -----------------------------------------------------------


def _cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def _seat_lines(answer: Answer) -> list[str]:
    return [line for line in render(answer).split("\n") if line.startswith("  ")]


def test_hearts_pass() -> None:
    """The pass: each seat decides; the holder of each hand sees the cards,
    every other seat a count."""
    answer = ask_path(HEARTS, 65, 9)
    text = render(answer)
    assert "who decides: each seat, for its own pick" in text
    assert "no other seat hears the pick" in text
    assert "the seat holding hand[player]: sees which cards leave hand[player], and how many cards arrive at hand[player offset_by pass_direction]" in text
    assert "every other seat: sees how many cards leave hand[player], and how many cards arrive" in text
    record = query_envelope(answer)
    assert read_envelope(record) is Kind.QUERY
    seats = record["answer"]["seats"]  # type: ignore[index]
    assert seats["construct"] == "simultaneous" and seats["form"] == "static"


def test_hearts_trick_and_hidden_hand() -> None:
    answer = ask_path(HEARTS, 90, 9)
    text = render(answer)
    assert "the seat holding hand[the seat on turn]: sees which cards leave hand[the seat on turn], and which cards arrive at trick_pile" in text
    assert "every other seat: sees how many cards leave hand[the seat on turn], and which cards arrive at trick_pile" in text


def test_cheat_face_down_play_and_announced_count() -> None:
    """Cheat's claim count is announced; the cards go face down."""
    count = render(ask_path(CHEAT, 135, 20))
    assert "Type: `choose integer" in count and "is Integer" in count
    assert "every seat hears the pick" in count
    play = render(ask_path(CHEAT, 137, 5))
    assert "the seat holding hand[actor]: sees which cards leave hand[actor], and how many cards arrive at played" in play
    assert "every other seat: sees how many cards leave hand[actor], and how many cards arrive at played" in play


def test_board_game_piece_onto_a_square() -> None:
    """A square is held by no seat: every seat sees the piece land."""
    text = render(ask_path(TIC_TAC_TOE, 55, 5))
    assert "every other seat: sees which pieces leave reserve[actor], and which pieces arrive at square[at]" in text


def test_text_and_json_are_one_answer() -> None:
    """Every observer line the text prints is a record in the JSON, in order."""
    answer = ask_path(HEARTS, 65, 9)
    record = query_envelope(answer)
    observers = record["answer"]["seats"]["observers"]  # type: ignore[index]
    printed = [line.split(":")[0].strip() for line in _seat_lines(answer) if ": sees" in line or "learns nothing" in line]
    assert printed == [o["who"] for o in observers]


def test_query_command_answers_on_stdout() -> None:
    code, out, err = _cli("query", str(HEARTS), "--at", "90:9")
    assert code == 0 and not err
    assert out.startswith(f"{HEARTS}:90:9: a trick round: ")


def test_query_command_json() -> None:
    code, out, _err = _cli("query", str(HEARTS), "--at", "90:9", "--json")
    assert code == 0
    document = json.loads(out)
    assert read_envelope(document) is Kind.QUERY
    assert document["diagnostics"] == [] and document["answer"]["part"]["what"] == "a trick round"


def test_a_position_outside_the_file_is_refused_to_whoever_asked() -> None:
    code, out, err = _cli("query", str(HEARTS), "--at", "999:1")
    assert code == 2 and not out and "outside" in err
    code, out, _err = _cli("query", str(HEARTS), "--at", "999:1", "--json")
    document = json.loads(out)
    assert code == 2 and document["answer"] is None
    assert [d["code"] for d in document["diagnostics"]] == ["position-outside-the-file"]
    assert document["diagnostics"][0]["author"] == "invocation"


def test_a_refused_file_gets_the_checker_s_refusal_and_no_answer(tmp_path: Path) -> None:
    broken = tmp_path / "hearts.cardlang"
    broken.write_text(HEARTS.read_text().replace("from hand[player]", "from hnad[player]"))
    check_code, _out, check_err = _cli("check", str(broken))
    code, out, err = _cli("query", str(broken), "--at", "66:16")
    assert (code, out, err) == (check_code, "", check_err) and code == 1
    _code, check_json, _err = _cli("check", str(broken), "--json")
    code, out, _err = _cli("query", str(broken), "--at", "66:16", "--json")
    document = json.loads(out)
    assert code == 1 and document["answer"] is None
    assert document["diagnostics"] == json.loads(check_json)["diagnostics"]


def test_a_family_library_file_is_refused_by_the_checker() -> None:
    """A library's own file holds no game (asking at a line of library text
    in the game using it is issue #1110)."""
    library = REPO / "docs" / "libraries" / "poker_betting.cardlang"
    code, _out, err = _cli("query", str(library), "--at", "1:1")
    assert code == 1 and "error" in err


def test_an_unreadable_file_is_refused_to_whoever_asked(tmp_path: Path) -> None:
    code, out, err = _cli("query", str(tmp_path / "absent.cardlang"), "--at", "1:1")
    assert code == 2 and "no such file" in err
    code, out, _err = _cli("query", str(tmp_path / "absent.cardlang"), "--at", "1:1", "--json")
    assert code == 2 and [d["code"] for d in json.loads(out)["diagnostics"]] == ["unreadable-file"]


@pytest.mark.parametrize("json_too", [False, True])
@pytest.mark.parametrize("written", [None, "66", "66:", ":16", "a:b", "66-16", "1"])
def test_a_query_naming_no_position_is_refused_as_text(written: str | None, json_too: bool) -> None:
    """Refused after the line is parsed, as `demo`'s `--at` without a seat
    is, and as text under `--json` too, as a command line that cannot be
    read is under `check --json`: exit 2, nothing on stdout."""
    argv = ["query", str(HEARTS), *([] if written is None else ["--at", written])]
    code, out, err = _cli(*argv, *(["--json"] if json_too else []))
    assert (code, out) == (2, "")
    assert err.startswith("cardlang: ") and "LINE:COL" in err


def test_ask_answers_every_position_of_a_game() -> None:
    """Total over one whole file: every line and column of Hearts is answered
    or refused, never left to a traceback."""
    checked = checked_text(HEARTS.read_text(), str(HEARTS), markdown=False)
    for line, text in enumerate(checked.file_lines, start=1):
        for column in range(0, len(text) + 2):
            answer = ask(checked, line, column)
            assert answer.located is not None or answer.refused


def test_a_registration_refusal_is_a_record_and_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """As `check --json` records one."""

    def refused(_path: object) -> None:
        raise GameRegistrationError("two files claim one short name")

    monkeypatch.setattr(cli, "check_source", refused)
    code, out, err = _cli("query", str(HEARTS), "--at", "90:9", "--json")
    document = json.loads(out)
    (record,) = document["diagnostics"]
    assert (code, err, document["answer"]) == (2, "", None)
    assert (record["code"], record["author"]) == ("unregistrable-game", "registration")


@pytest.mark.parametrize("where", ["the check", "the query's own run of the passes"])
def test_an_engine_failure_prints_its_envelope_and_keeps_its_traceback(
    where: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As `check --json` records one (issue #1104), in either of the two runs
    of the passes a query makes."""

    def crashed(*_args: object) -> None:
        raise AssertionError("an engine invariant")

    if where == "the check":
        monkeypatch.setattr(cli, "check_source", crashed)
    else:
        monkeypatch.setattr(query, "ask_path", crashed)
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(AssertionError):
        cli.main(["query", str(HEARTS), "--at", "90:9", "--json"])
    document = json.loads(out.getvalue())
    assert read_envelope(document) is Kind.QUERY and document["answer"] is None
    (record,) = document["diagnostics"]
    assert (record["code"], record["author"], record["message"]) == (
        "engine-gap", "engine", "an engine invariant"
    )


def test_a_query_envelope_of_another_shape_is_refused() -> None:
    """The reader holds a query envelope to its kind's payload."""
    document = query_envelope(ask_path(HEARTS, 90, 9))
    assert read_envelope(document) is Kind.QUERY
    for broken in (
        {**document, "extra": 1},
        {**document, "answer": {"part": None}},
        {k: v for k, v in document.items() if k != "at"},
    ):
        with pytest.raises(UnreadableEnvelope):
            read_envelope(broken)
