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
                 answer for what each seat sees; at every position of each
                 kind in `STATE_POSITION_KINDS` the scope's State Variables
                 are those a name written there reads, off the declarations
                 (`_expected_state`), a State Variable read is listed around
                 the read, and at one position of each kind in Hearts a read
                 of each State Variable written there checks clean exactly
                 when it is listed (`_ORACLE_CELLS`); a definition
                 body's scope lists no Pronoun its body may not read, and a
                 `state { }` default's lists no `actor` and the State
                 Variables declared before it and around it
                 (`_body_and_default_scopes`); at a position that is no name
                 inside a Hosted Poll's body and inside a kernel answer's, a
                 read of each State Variable, Pronoun and zone checks clean
                 exactly when it is listed (`_REACH_ORACLE_CELLS`). The
                 position axis is
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
                 them for the whole row. The seats column's rule
                 for which enclosing part answers (a site, or an expression in
                 a site's clause) is the one `cardlang.query.seats_at` reads by, so a
                 wrong rule passes here; that each answer is what the engine
                 shows a seat is tests/test_query_seats.py's claim. The
                 State Variables listed in a callable body are held only by
                 the read-is-listed half: no scope rule judges a callable body
                 (issue #242). The scope does not apply the rule of who is
                 acting (issue #1089): it lists `actor` and a bare zone
                 family where no player acts, each refused when written
                 there. At a node that is no name it lists a zone family of
                 any index, which the bare-family rule refuses written bare
                 there: that rule judges a name alone. The Hosted Poll
                 rule and the kernel-answer rule are
                 run by apply-the-read at one position each, never over the
                 corpus; the rule of a function a rule's clauses reach is
                 run by no cell here, since the one answer cell's answer
                 rule refuses the same names first, and it is held by
                 tests/test_near_miss_positions.py alone. A zone family's
                 name answers with the Type
                 the checker gives it, one zone's content: the checker holds
                 a family's content (`TypeEnv.zones`) and the Type of its key
                 (`TypeEnv.zone_families`) apart, and no Type of the family
                 keyed by its index, which a keyed State Variable has.
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

from cardlang import cli, query, resolve
from cardlang.ast import nodes as n
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import DiagnosticError, Span, Told
from cardlang.query import (
    PROJECTION_WORDS,
    Checked,
    ask,
    ask_path,
    checked_text,
    render,
    scope_at,
    seats_at,
    type_at,
)
from cardlang.stdlib.zones import PROJECTION_LEVELS
from cardlang.pipeline import check_dsl
from cardlang.records import Kind, UnreadableEnvelope, query_envelope, read_envelope
from cardlang.runtime.errors import GameRegistrationError

REPO = Path(__file__).resolve().parent.parent
GAMES = REPO / "docs" / "games"
HEARTS = GAMES / "hearts.cardlang"
CHEAT = GAMES / "cheat.cardlang"
TIC_TAC_TOE = GAMES / "tic-tac-toe.cardlang"
KUHN = GAMES / "kuhn-poker.cardlang"
BIG_TWO = GAMES / "big-two.cardlang"
BELOTE = GAMES / "belote.cardlang"
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

#: The slots no value read of the checker reaches -- a write target, a zone
#: family's name, a rule clause's whole expression -- which the check types
#: where it reads them.
UNREAD_SLOTS: frozenset[tuple[type, str]] = frozenset(
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


# A part of the game that is no site, and no expression in a site's clause,
# is refused one of these ways: it runs nothing, or it runs sites standing
# elsewhere. Which of them, and whether it is true, is the oracle's
# (tests/test_query_seats.py).
_NO_SITE: frozenset[str] = frozenset({Code.NOTHING_SEEN_HERE.slug, Code.SEEN_AT_ITS_SITES.slug})


def _expected_seats(placed: Placed) -> frozenset[str]:
    """A site, or an expression in a site's clause: the innermost node, then
    its expression-only enclosers, up to the first that is not an
    expression."""
    for node in reversed(placed.chain):
        if isinstance(node, SITE_KINDS):
            return frozenset({ANSWERED})
        if not isinstance(node, EXPR_KINDS):
            return _NO_SITE
    return _NO_SITE


def _expected(placed: Placed, answer: str) -> frozenset[str]:
    if answer == "scope":
        return frozenset({ANSWERED})
    if answer == "type":
        return frozenset({ANSWERED if isinstance(placed.node, EXPR_KINDS) else Code.NOT_AN_EXPRESSION.slug})
    return _expected_seats(placed)


_ASK = {"scope": scope_at, "type": type_at, "seats": seats_at}


@cache
def _mismatches() -> dict[tuple[str, str], list[str]]:
    """Every instance whose answer differs from the expected column, by
    (kind, answer)."""
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for checked, placed in _corpus():
        for p in placed:
            for answer in ANSWERS:
                got = _outcome(_ASK[answer](checked, p.chain))
                want = _expected(p, answer)
                if got not in want:
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


#: One position of each slot of `UNREAD_SLOTS` in a corpus game, and the
#: Type the declarations give it there: the variable's declared Type for a
#: write target, the zone's content for a family's name, a card set for a
#: rule's card clauses, and the permissive top for an `error(...)` fallback.
UNREAD_SLOT_TYPES: dict[tuple[type, str], tuple[Path, int, int, str]] = {
    (n.AssignStmt, "target"): (HEARTS, 86, 7, "Player?"),  # `leader : Player? = none`
    (n.RotateStmt, "target"): (HEARTS, 54, 14, "SeatDirection"),  # `pass_direction : SeatDirection`
    (n.Subscript, "obj"): (HEARTS, 66, 16, "Collection<Card>"),  # `hand[player] : Hand<player>`
    (n.Demands, "expr"): (HEARTS, 124, 12, "Collection<Card>"),
    (n.RuleDef, "exempts"): (GAMES / "french-tarot.cardlang", 286, 12, "Collection<Card>"),
    (n.RuleDef, "if_impossible"): (GAMES / "getaway.cardlang", 86, 18, "Any"),
}


def test_every_unread_slot_has_its_named_position() -> None:
    """red under: add `(n.BinOp, "left")` to `UNREAD_SLOTS`."""
    assert set(UNREAD_SLOTS) == set(UNREAD_SLOT_TYPES)


@pytest.mark.parametrize("slot", sorted(UNREAD_SLOTS, key=_slot_id), ids=_slot_id)
def test_an_expression_in_an_unread_slot_has_a_type(slot: tuple[type, str]) -> None:
    """The expression in a slot no value read reaches has the Type the check
    gave it there, at every instance of the slot the corpus writes, and at
    the slot's named position the Type its declarations give it. red under:
    revert `_check_rotate`'s target to `env.state_vars.get(name)`."""
    instances = [
        (checked, p)
        for checked, placed in _corpus()
        for p in placed
        if p.slot == slot and isinstance(p.node, EXPR_KINDS)
    ]
    assert instances, f"no corpus game writes {_slot_id(slot)}"
    untyped = [
        f"{getattr(p.node, 'span').source_name}:{getattr(p.node, 'span').line}"
        for checked, p in instances
        if isinstance(type_at(checked, p.chain), Told)
    ]
    assert not untyped, untyped[:5]
    path, line, column, expected = UNREAD_SLOT_TYPES[slot]
    checked = checked_text(path.read_text(), str(path), markdown=False)
    located = query.locate(checked, line, column)
    assert not isinstance(located, Told)
    kind, field = slot
    holder, node = located.chain[-2], located.chain[-1]
    assert isinstance(holder, kind) and getattr(holder, field) is node
    typed = type_at(checked, located.chain)
    assert not isinstance(typed, Told)
    assert typed.types == (expected,)


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
    "the line a final newline would start": PositionCell(HEARTS, 149, 1, Code.POSITION_OUTSIDE_THE_FILE.slug),
    "the file's last line, a comment": PositionCell(HEARTS, 148, 1, Code.POSITION_OUTSIDE_THE_GAME.slug),
    "indentation inside the game": PositionCell(HEARTS, 24, 1, ANSWERED, "the game"),
    "a comment inside a block": PositionCell(HEARTS, 39, 9, ANSWERED, "a declaration"),
    "a keyword of a statement": PositionCell(HEARTS, 65, 10, ANSWERED, "a movement"),
    "an operator between operands": PositionCell(HEARTS, 67, 28, ANSWERED, "an expression"),
    "a name": PositionCell(HEARTS, 66, 16, ANSWERED, "a name"),
    "an assignment's operator": PositionCell(HEARTS, 86, 14, ANSWERED, "an assignment"),
    "a rule after the game block": PositionCell(HEARTS, 122, 3, ANSWERED, "a rule"),
    "a `uses` line": PositionCell(KUHN, 33, 3, ANSWERED, "a `uses` line"),
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


def test_scope_lists_only_live_state_at_a_statement() -> None:
    """Hearts' `passing` phase cannot read `play`'s `leader`."""
    answer = ask_path(HEARTS, 65, 9)
    assert answer.scope is not None and not isinstance(answer.scope, Told)
    assert "leader" not in {s.name for s in answer.scope.names}


def _declared_state(block: n.StateBlock | None) -> frozenset[str]:
    return frozenset(d.name for d in block.decls) if block is not None else frozenset()


_NO_STATE_RULE = (n.FunctionDef, n.ProcedureDef, n.MoveTypeDef, n.RuleDef)


def _phase_state(phase: n.Phase) -> frozenset[str]:
    return _declared_state(next((i for i in phase.items if isinstance(i, n.StateBlock)), None))


def _expected_state(game: n.Game, chain: tuple[object, ...]) -> tuple[str, frozenset[str]]:
    """The kind of position `chain` ends at, and the State Variables a name
    written there reads, off the declarations alone: in a `state { }` block,
    those of every enclosing block and those declared before its declaration;
    elsewhere, the game's and those of each phase enclosing it."""
    game_state = _declared_state(game.state)
    phases = [x for x in chain if isinstance(x, n.Phase)]
    for i, holder in enumerate(chain):
        if isinstance(holder, n.StateBlock):
            owners = [x for x in chain[:i] if isinstance(x, n.Phase)]
            enclosing = (
                frozenset()
                if holder is game.state
                else game_state.union(*(_phase_state(ph) for ph in owners[:-1]))
            )
            if i + 1 == len(chain):
                return "a `state { }` block", enclosing
            decl = chain[i + 1]
            assert isinstance(decl, n.StateDecl)
            earlier = frozenset(d.name for d in holder.decls[: holder.decls.index(decl)])
            return "a state declaration", enclosing | earlier
    live = game_state.union(*(_phase_state(ph) for ph in phases))
    if len(chain) == 1:
        return "the game", live
    return ("a phase" if phases else "a game-level clause"), live


#: The kinds of position the State Variable grid covers.
STATE_POSITION_KINDS = ("the game", "a game-level clause", "a phase", "a `state { }` block", "a state declaration")


@cache
def _state_scope_mismatches() -> tuple[list[str], dict[str, int]]:
    """Every position, a name or not, outside a callable or rule body (whose
    state no scope rule judges, issue #242) whose listed State Variables are
    not what `_expected_state` reads off the declarations; every State
    Variable a corpus game reads that is not listed at the part of the game
    holding the read; and how many positions of each kind were judged."""
    out: list[str] = []
    judged: dict[str, int] = dict.fromkeys(STATE_POSITION_KINDS, 0)
    for checked, placed in _corpus():
        for p in placed:
            scope = scope_at(checked, p.chain)
            assert not isinstance(scope, Told)
            listed = {s.name for s in scope.names if s.sort == "state-variable"}
            span = getattr(p.node, "span")
            where = f"{span.source_name}:{span.line}:{span.column} {type(p.node).__name__}"
            slot_takes_state = not isinstance(p.node, n.NameRef) or "state-variable" in {
                s.sort for s in scope.names
            }
            if slot_takes_state and not any(isinstance(x, _NO_STATE_RULE) for x in p.chain):
                kind, live = _expected_state(checked.game, p.chain)
                judged[kind] += 1
                if listed != live:
                    out.append(f"{where} ({kind}): lists {sorted(listed ^ live)} wrongly")
            if isinstance(p.node, n.NameRef) and p.node.ref_kind == "state_var" and len(p.chain) > 1:
                around = scope_at(checked, p.chain[:-1])
                assert not isinstance(around, Told)
                if p.node.name not in {s.name for s in around.names}:
                    out.append(f"{where}: reads {p.node.name}, unlisted around it")
    return out, judged


@cache
def _body_and_default_scopes() -> tuple[list[str], list[str], int, int]:
    """At every position that is no name in a game definition's body, the
    Pronouns it may not read (`_refused_call_site_pronouns`) are not listed;
    at every one in a `state { }` default, `actor` is not listed and the State
    Variables listed are those declared before it in its block and those of
    every enclosing block, read off the declarations. With how many positions
    of each kind the corpus holds."""
    bodies: list[str] = []
    defaults: list[str] = []
    in_bodies = in_defaults = 0
    for checked, placed in _corpus():
        game_state = _declared_state(checked.game.state)
        for p in placed:
            if isinstance(p.node, n.NameRef):
                continue
            scope = scope_at(checked, p.chain)
            assert not isinstance(scope, Told)
            pronouns = {s.name for s in scope.names if s.sort == "pronoun"}
            listed = {s.name for s in scope.names if s.sort == "state-variable"}
            span = getattr(p.node, "span")
            where = f"{span.source_name}:{span.line}:{span.column} {type(p.node).__name__}"
            for i, holder in enumerate(p.chain[:-1]):
                if isinstance(holder, (n.FunctionDef, n.ProcedureDef)):
                    body = holder.body if isinstance(holder.body, tuple) else (holder.body,)
                    if any(part is p.chain[i + 1] for part in body):
                        in_bodies += 1
                        refused = resolve._refused_call_site_pronouns(holder)
                        if pronouns & refused:
                            bodies.append(f"{where}: lists {sorted(pronouns & refused)}")
                if isinstance(holder, n.StateBlock) and i + 2 < len(p.chain):
                    decl = p.chain[i + 1]
                    assert isinstance(decl, n.StateDecl)
                    if p.chain[i + 2] is not decl.default:
                        continue
                    in_defaults += 1
                    earlier = frozenset(d.name for d in holder.decls[: holder.decls.index(decl)])
                    phases = [x for x in p.chain[:i] if isinstance(x, n.Phase)]
                    enclosing = frozenset() if holder is checked.game.state else game_state.union(
                        *(_declared_state(next((it for it in ph.items if isinstance(it, n.StateBlock)), None)) for ph in phases[:-1])
                    )
                    if "actor" in pronouns or listed != earlier | enclosing:
                        defaults.append(f"{where}: lists {sorted(listed ^ (earlier | enclosing))}, actor {'actor' in pronouns}")
    return bodies, defaults, in_bodies, in_defaults


def test_scope_in_a_definition_body_lists_no_refused_pronoun() -> None:
    """red under: record `_ScopeFacts.refused_pronouns` at `NameRef` nodes
    alone in `classification._scope_facts`."""
    bodies, _defaults, in_bodies, _ = _body_and_default_scopes()
    assert in_bodies, "no corpus game defines a function or procedure"
    assert not bodies, "\n".join(bodies[:8])


def test_scope_in_a_state_default_is_what_a_default_reads() -> None:
    """red under: record a default's live state at `NameRef` nodes alone in
    `classification._scope_facts`."""
    _bodies, defaults, _, in_defaults = _body_and_default_scopes()
    assert in_defaults, "no corpus game writes a `state { }` default"
    assert not defaults, "\n".join(defaults[:8])


@pytest.mark.parametrize("kind", STATE_POSITION_KINDS)
def test_scope_lists_the_state_a_name_there_reads(kind: str) -> None:
    """At every position of the kind, the State Variables listed are those a
    name written there reads, off the declarations; and a State Variable the
    game reads is listed around the read. red under: record `_ScopeFacts` at
    `NameRef` nodes alone in `classification._scope_facts`; for a game-level
    clause, yield only `NameRef` nodes from `_phase_scoped_nodes`'
    game-level loop."""
    wrong, judged = _state_scope_mismatches()
    assert judged[kind], f"the corpus holds no position of {kind}"
    mine = [w for w in wrong if f"({kind})" in w or "unlisted around it" in w]
    assert not mine, "\n".join(mine[:8])


def _state_read(decl: n.StateDecl) -> str:
    """A read of the variable `decl` declares that types whatever its Type."""
    read = f"{decl.name}[0]" if decl.index is not None else decl.name
    return f"if {read} is {read} then 0 else 0"


#: Positions of each kind of `STATE_POSITION_KINDS` in Hearts, and the text
#: that writes a read there: a line inserted before the given line.
_ORACLE_CELLS: dict[str, tuple[int, int, int, str]] = {
    "the game": (27, 1, 27, "  loser: READ"),
    "a game-level clause": (116, 3, 116, "  loser: READ"),
    "a phase": (65, 9, 64, "      let probe_read = READ"),
    "a `state { }` block": (44, 5, 47, "      probe_read : Integer = READ"),
    "a state declaration": (47, 22, 47, "      probe_read : Integer = READ"),
}


def _refusal_codes(text: str) -> list[str]:
    try:
        check_dsl(text, "probe.cardlang")
    except DiagnosticError as refused:
        return [told.diagnostic.code.slug for told in refused.told]
    return []


@pytest.mark.parametrize("kind", STATE_POSITION_KINDS)
def test_a_listed_state_variable_reads_there_and_an_unlisted_one_is_refused(kind: str) -> None:
    """Written at the position, a read of each State Variable the scope
    lists checks clean, and a read of each it does not list is refused as out
    of scope. red under: drop the `yield game, top` from
    `scope._phase_scoped_nodes`."""
    line, column, before, writes = _ORACLE_CELLS[kind]
    answer = ask_path(HEARTS, line, column)
    assert answer.scope is not None and not isinstance(answer.scope, Told)
    listed = {s.name for s in answer.scope.names if s.sort == "state-variable"}
    lines = HEARTS.read_text().split("\n")
    checked = checked_text(HEARTS.read_text(), str(HEARTS), markdown=False)
    decls = [d for b in resolve._walk(checked.game) if isinstance(b, n.StateBlock) for d in b.decls]
    assert listed and set(listed) < {d.name for d in decls}
    wrong = []
    for decl in decls:
        text = "\n".join([*lines[: before - 1], writes.replace("READ", _state_read(decl)), *lines[before - 1 :]])
        codes = _refusal_codes(text)
        if decl.name in listed and codes:
            wrong.append(f"{decl.name} is listed and refused {codes}")
        if decl.name not in listed and Code.OUT_OF_SCOPE.slug not in codes:
            wrong.append(f"{decl.name} is unlisted and refused {codes}, not out of scope")
    assert not wrong, wrong


#: Positions that are no name, inside a body a reach rule judges, and the line
#: that writes a read there: the file, the position, the line written at, and
#: whether the written line replaces that line or stands before it.
_REACH_ORACLE_CELLS: dict[str, tuple[Path, int, int, int, bool, str]] = {
    "a Hosted Poll's body": (BIG_TWO, 110, 27, 110, False, "                let probe_read = READ"),
    "a kernel answer's body": (
        BELOTE, 345, 44, 345, True, "function is_trump(card : Card) = card.suit is trump_suit and ((READ) is (READ))"
    ),
}

#: The rules the scope does not apply at a node that is no name, by the code
#: each refuses in: who is acting (issue #1089), and a zone family named bare,
#: which the bare-family rule judges at a name alone.
_UNAPPLIED_AT_A_NODE = frozenset({Code.NO_PLAYER_ACTING.slug, Code.WRONG_SUBSCRIPT.slug})


@pytest.mark.parametrize("where", sorted(_REACH_ORACLE_CELLS))
def test_a_listed_name_reads_inside_a_reach_and_an_unlisted_one_is_refused(where: str) -> None:
    """Written at a position that is no name inside the body, a read of each
    State Variable, Pronoun and zone the scope lists checks clean, and a read
    of each it does not list is refused. `actor` and a zone family listed
    there may be refused only by a rule in `_UNAPPLIED_AT_A_NODE`. red under:
    drop the Hosted Poll disjunct, or the answer disjunct, from
    `classifier._scope_refuses`; or record `_ScopeFacts.hosted`, or
    `answer_through`, at `NameRef` nodes alone in
    `classification._scope_facts`."""
    path, line, column, at, replaces, writes = _REACH_ORACLE_CELLS[where]
    answer = ask_path(path, line, column)
    assert answer.scope is not None and not isinstance(answer.scope, Told)
    assert not answer.scope.at_a_name
    listed = {s.name for s in answer.scope.names if s.sort in ("state-variable", "pronoun", "zone")}
    text = path.read_text()
    lines = text.split("\n")
    game = checked_text(text, str(path), markdown=False).game
    families = {z.name for z in game.zones if z.index is not None}
    candidates = {
        *(d.name for b in resolve._walk(game) if isinstance(b, n.StateBlock) for d in b.decls),
        *(z.name for z in game.zones),
        *resolve._PRONOUNS,
    }
    assert listed and listed <= candidates
    wrong = []
    for name in sorted(candidates):
        probe = "\n".join([*lines[: at - 1], writes.replace("READ", name), *lines[at - 1 + replaces :]])
        codes = _refusal_codes(probe)
        unapplied = name == "actor" or name in families
        if name in listed and codes and not (unapplied and set(codes) <= _UNAPPLIED_AT_A_NODE):
            wrong.append(f"{name} is listed and refused {codes}")
        if name not in listed and not codes:
            wrong.append(f"{name} is unlisted and reads clean")
    assert not wrong, wrong


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
    assert "the checker's Type: `choose integer" in count and "is Integer" in count
    assert "every seat hears the pick" in count
    play = render(ask_path(CHEAT, 137, 5))
    assert "the seat holding hand[actor]: sees which cards leave hand[actor], and how many cards arrive at played" in play
    assert "every other seat: sees how many cards leave hand[actor], and how many cards arrive at played" in play


def test_board_game_piece_onto_a_square() -> None:
    """A square is held by no seat: every seat sees the piece land."""
    text = render(ask_path(TIC_TAC_TOE, 55, 5))
    assert "every other seat: sees which pieces leave reserve[actor], and which pieces arrive at square[at]" in text


# Positions whose answers carry every kind of per-seat fact between them: a
# routed source, a gather, an announced and a moved pick, out-of-turn asks, a
# site answering a position inside it, an offer running its moves' effects.
_ONE_VALUE_CELLS: tuple[tuple[Path, int, int], ...] = (
    (HEARTS, 65, 9),
    (HEARTS, 51, 7),
    (GAMES / "bridge.cardlang", 143, 9),
    (GAMES / "tichu.cardlang", 223, 9),
    (GAMES / "coup.cardlang", 135, 61),
    (CHEAT, 135, 20),
    (TIC_TAC_TOE, 55, 5),
)


@pytest.mark.parametrize(("path", "line", "column"), _ONE_VALUE_CELLS, ids=lambda v: str(getattr(v, "name", v)))
def test_text_and_json_are_one_answer(path: Path, line: int, column: int) -> None:
    """Every fact the record holds of what each seat sees is in the text, in
    the order the record lists it: the answering site where it is not the
    position asked, the construct, who decides, who else is asked, what the
    others hear, where the content comes from, each movement and each kind of
    seat's view, and what it runs next. red under: drop the `asked as:` line
    from `query._render_seats`."""
    answer = ask_path(path, line, column)
    record = query_envelope(answer)
    seats = record["answer"]["seats"]  # type: ignore[index]
    text = render(answer)
    assert record["answer"]["items"] in text  # type: ignore[index]
    if "refused" in seats:
        assert seats["refused"]["message"] in text
        return
    expected: list[str] = []
    if (seats["span"]["line"], seats["span"]["column"]) != (line, column):
        expected.append(f"line {seats['span']['line']}: {seats['text']}")
    if seats["construct"] is not None:
        expected.append(f"asked as: {seats['construct']}")
    if seats["decider"] is not None:
        expected.append(seats["decider"])
    expected.extend(seats["out-of-turn"])
    if seats["source-from"] is not None:
        expected.append(seats["source-from"])
    if seats["every-seat"] is not None:
        expected.append(seats["every-seat"])
    for move in seats["moves"]:
        if len(seats["moves"]) > 1:
            expected.append(f"when it moves from {move['source']['label']} to {move['destination']['label']}:")
        expected.extend(f"{o['who']}: {o['sees']}" for o in move["observers"])
    for place in seats["then"]:
        expected.append(f"line {place['line']}")
    at = 0
    for fact in expected:
        found = text.find(fact, at)
        assert found >= 0, (fact, text)
        at = found


def test_the_projection_words_name_every_level() -> None:
    """Every level a zone type can project has its words, so no answer meets
    a level it cannot say. red under: delete the `"existence_only"` row of
    `query.PROJECTION_WORDS`."""
    assert set(PROJECTION_WORDS) == set(PROJECTION_LEVELS)


def test_an_open_type_says_where_it_is_refused() -> None:
    """The checker's Permissive Top passes where any value may stand and is
    refused where an exact Type is needed, as `winner and true` is."""
    text = render(ask_path(GAMES / "bridge.cardlang", 147, 19))
    assert "is Any" in text and "refuses it" in text and "any value passes" not in text


@pytest.mark.parametrize(
    ("path", "line", "column", "facts"),
    [
        (GAMES / "bridge.cardlang", 143, 9, ("dummy_hand[p]", "`play_source_for`")),
        (HEARTS, 51, 7, ("when it moves from each hand to deck:", "the seat holding each hand: sees which cards leave each hand")),
        (GAMES / "tichu.cardlang", 223, 9, ("out of turn", "settled in play (issue #1111)")),
    ],
    ids=["routed trick source", "gather", "climbing round"],
)
def test_a_site_the_review_found_answered_wrong(path: Path, line: int, column: int, facts: tuple[str, ...]) -> None:
    text = render(ask_path(path, line, column))
    for fact in facts:
        assert fact in text, (fact, text)


@pytest.mark.parametrize(
    ("path", "line", "column"),
    [(GAMES / "coup.cardlang", 236, 11), (GAMES / "five-card-stud.cardlang", 211, 9)],
    ids=["run of a game procedure", "run of a library-calling procedure"],
)
def test_a_run_names_where_its_sites_stand(path: Path, line: int, column: int) -> None:
    answer = ask_path(path, line, column)
    assert isinstance(answer.seats, Told)
    assert answer.seats.diagnostic.code is Code.SEEN_AT_ITS_SITES
    assert "stand at line" in answer.seats.diagnostic.message


def test_a_uses_line_names_its_library() -> None:
    answer = ask_path(KUHN, 33, 3)
    assert answer.located is not None and answer.located.words == "a `uses` line"
    assert isinstance(answer.seats, Told) and "poker_betting" in answer.seats.diagnostic.message


@pytest.mark.parametrize(
    "probe",
    ["let z = discard\n    move one card from deck to z", "let h = hand[0]\n    move one card from h to deck"],
    ids=["a let-bound destination", "a let-bound source"],
)
def test_an_end_only_play_names_is_settled_in_play(probe: str, tmp_path: Path) -> None:
    """An end the query cannot name is never `learns nothing`."""
    game = tmp_path / "probe.cardlang"
    game.write_text(_LET_PROBE.replace("PROBE", probe.replace("\\n", "\n")))
    statement_line = 1 + _LET_PROBE.split("PROBE")[0].count("\n") + 1
    answer = ask_path(game, statement_line, 5)
    assert answer.seats is not None and not isinstance(answer.seats, Told), render(answer)
    assert "settled in play" in render(answer)
    assert all(o.learns is not False for m in answer.seats.moves for o in m.observers)


_LET_PROBE = """game Probe {
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  zones {
    deck : Deck
    discard : Discard
    hand[player] : Hand<player>
  }
  state { score[player] : Integer = 0 }
  phase p {
    PROBE
    for each player q: score[q] := 1
  }
  winner: highest score
}
"""


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
def test_an_engine_failure_prints_its_envelope_and_exits_3(
    where: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """As `check --json` records one, in either of the two runs of the passes
    a query makes: the engine's record, its traceback on stderr, exit 3."""

    def crashed(*_args: object) -> None:
        raise AssertionError("an engine invariant")

    if where == "the check":
        monkeypatch.setattr(cli, "check_source", crashed)
    else:
        monkeypatch.setattr(query, "ask_path", crashed)
    code = cli.main(["query", str(HEARTS), "--at", "90:9", "--json"])
    out, err = capsys.readouterr()
    document = json.loads(out)
    assert read_envelope(document) is Kind.QUERY and document["answer"] is None
    (record,) = document["diagnostics"]
    assert (record["code"], record["author"], record["message"]) == (
        "engine-gap", "engine", "an engine invariant"
    )
    assert code == 3
    assert "Traceback (most recent call last)" in err


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
