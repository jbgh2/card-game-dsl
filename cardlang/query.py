"""The Checker Query: what the checker knows at one position of a game file.

`cardlang query FILE --at LINE:COL` answers three questions at a place in a
game file the checker accepts, without playing the game: which names a bare
name written there would resolve to, what Type the checker gives the
expression there, and what each seat sees when the movement or decision there
runs. One `Answer` value holds the facts; `render` spells them for a designer
and `cardlang.records.query_envelope` gives them to a tool, so the two cannot
say different things.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a file `check_source` accepts; a file it refuses is answered
              with the checker's own refusal and nothing else.
Establishes:  every answer is read from the pass that owns its fact, never
              worked out here: the names in scope from the resolver's Scope
              Record (`resolve(scopes=...)`, classified by the resolver's own
              classifier), the Type from the type checker's Type Record
              (`typecheck(types=...)`, every Type `infer` returned), and what
              each seat sees from the zone types through the projection the
              runtime's emitter reads (`stdlib.zones.zone_projection`), the
              emitter's own rule for an observer learning of a movement at all
              (`observe.movement_seen`), its rule for which zones have a
              holder (`observe.held`), and its table of who hears a pick
              (`observe.PICK_SHOWN`). Every position of the file gets an
              answer or a told refusal carrying its Diagnostic Code, addressed
              to whoever ran the query; a refusal says what can be answered
              nearby. The per-seat answer is the static one, and says so: the
              projection each kind of observer sees a site through, not the
              cards of a played line.
Now illegal:  a scope walk, a type inference or a visibility rule of this
              module's own; an answer about a file the checker refuses.
Held by:      Derived and Pinned: tests/test_query.py crosses every `Node`
              kind with the three answers over the corpus, and
              tests/test_query_seats.py holds the per-seat answer to the
              information states the OpenSpiel adapter derives and the pick
              table to what every registered game emits.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import assert_never, get_args

from cardlang.ast import nodes as n
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Author, Diagnostic, Severity, Span, Told
from cardlang.domains import role_of
from cardlang.extract import extract_single_block
from cardlang.parse import parse_block, parse_text
from cardlang.resolve import NamesInScope, resolve
from cardlang.runtime.delegation import CHOOSER_HELPER
from cardlang.runtime.observe import PICK_SHOWN, held, movement_seen
from cardlang.runtime.values import content_noun
from cardlang.stdlib.zones import zone_projection
from cardlang.typecheck import type_name, typecheck
from cardlang.types import TAny, Type

_EXPR_KINDS: tuple[type, ...] = get_args(n.Expr)
_STMT_KINDS: tuple[type, ...] = get_args(n.Stmt)


# --- the checked text ---------------------------------------------------------


@dataclass(frozen=True)
class Checked:
    """A game file the checker accepts, with what its passes recorded: the
    resolved tree the type checker read, the Scope Record and the Type
    Record, and where the game's text sits in the file."""

    path: str
    file_lines: tuple[str, ...]
    source_name: str
    program: str
    line_offset: int
    game: n.Game
    scopes: Mapping[n.NodeKey, NamesInScope]
    types: Mapping[n.NodeKey, Sequence[Type]]


def checked_text(text: str, source_name: str, markdown: bool) -> Checked:
    """The passes run again over text the checker has accepted, this time
    keeping their records. Not through the pipeline's memo, which would skip
    the passes on a repeat."""
    if markdown:
        block = extract_single_block(text, source_name)
        tree, program, offset = parse_block(block), block.text, block.start_line - 1
    else:
        tree, program, offset = parse_text(text, source_name), text, 0
    scopes: dict[n.NodeKey, NamesInScope] = {}
    types: dict[n.NodeKey, list[Type]] = {}
    game = resolve(tree, scopes=scopes)
    typecheck(game, types=types)
    return Checked(
        source_name, tuple(text.split("\n")), source_name, program, offset, game, scopes, types
    )


# --- the answer ---------------------------------------------------------------


@dataclass(frozen=True)
class Located:
    """The innermost part of the game the position falls in, and every part
    enclosing it, innermost last."""

    chain: tuple[object, ...]
    words: str
    text: str
    span: Span


@dataclass(frozen=True)
class InScope:
    """One name a bare name here resolves to, and what it is."""

    name: str
    sort: str  # the slug in `SORTS`


#: What a name in scope is, by the resolver's classification: its slug in a
#: record, and its designer words.
SORTS: dict[str, str] = {
    "bound-here": "bound here (a parameter, a `let`, or the binder of a query, a quantifier or a loop)",
    "state-variable": "State Variable",
    "zone": "zone",
    "named-value": "named value (a suit, a rank, a seat direction, a shape label, ...)",
    "pronoun": "Pronoun",
    "play-source": "the Play Source (a rule's `hand`)",
}


def _sort(kind: n.RefKind) -> str | None:
    match kind:
        case "local":
            return "bound-here"
        case "state_var":
            return "state-variable"
        case "zone":
            return "zone"
        case "enum_value":
            return "named-value"
        case "pronoun":
            return "pronoun"
        case "play_source":
            return "play-source"
        case "bool" | "null":
            return None
        case _:
            assert_never(kind)


@dataclass(frozen=True)
class Scope:
    """The names a bare name written here resolves to, as the resolver
    classified them at `span`, the innermost node it judged."""

    span: Span
    names: tuple[InScope, ...]
    at_a_name: bool


@dataclass(frozen=True)
class Typed:
    """The Types the checker gave the expression at `span`: one, or one per
    place the check read it under a different scope."""

    span: Span
    text: str
    types: tuple[str, ...]
    open: bool


@dataclass(frozen=True)
class Side:
    """One side of a movement: the zone, and its instance as written."""

    zone: str
    label: str


@dataclass(frozen=True)
class Observer:
    """One kind of seat, and what it sees of a movement through each side's
    projection; `learns` is False where it sees nothing of either side."""

    who: str
    holds_source: bool
    holds_destination: bool
    source: str | None
    destination: str | None
    learns: bool


@dataclass(frozen=True)
class Seats:
    """What each seat sees when the site at `span` runs, from the zone types
    (the static form): who decides and what the others hear of the pick, and
    what each kind of seat sees of the movement it makes."""

    span: Span
    site: str
    construct: str | None
    decider: str | None
    pick: str | None
    source: Side | None
    destination: Side | None
    observers: tuple[Observer, ...]
    every_seat: str | None


@dataclass(frozen=True)
class Answer:
    """The Checker Query's whole answer at one position: refused outright
    (`refused`, the checker's refusal or the position's), or located, with
    each of the three answers or the refusal standing in its place."""

    path: str
    line: int
    column: int
    exit_code: int
    refused: tuple[Told, ...] = ()
    items: str = "cards"
    located: Located | None = None
    scope: Scope | Told | None = None
    type: Typed | Told | None = None
    seats: Seats | Told | None = None


def _told(message: str, span: Span | None, code: Code) -> Told:
    return Told(Diagnostic(Severity.ERROR, message, span, code=code), Author.INVOCATION)


EXIT_ANSWERED = 0
EXIT_GAME_AT_FAULT = 1
EXIT_CANNOT_PROCEED = 2


# --- locating -----------------------------------------------------------------


def _walk(node: object, chain: tuple[object, ...]) -> Iterator[tuple[object, tuple[object, ...]]]:
    if not is_dataclass(node) or isinstance(node, Span):
        return
    inner = (*chain, node)
    yield node, inner
    for f in fields(node):
        yield from _walk_value(getattr(node, f.name), inner)


def _walk_value(value: object, chain: tuple[object, ...]) -> Iterator[tuple[object, tuple[object, ...]]]:
    if is_dataclass(value) and not isinstance(value, Span):
        yield from _walk(value, chain)
    elif isinstance(value, tuple):
        for item in value:
            yield from _walk_value(item, chain)


def _span(node: object) -> Span | None:
    span = getattr(node, "span", None)
    return span if isinstance(span, Span) else None


def _offset(checked: Checked, line: int, column: int) -> int | None:
    """The offset into the game's text of a file position, None where the
    position is in the file but outside that text (a Markdown file's prose)."""
    program_lines = checked.program.split("\n")
    at = line - 1 - checked.line_offset
    if not 0 <= at < len(program_lines):
        return None
    return sum(len(text) + 1 for text in program_lines[:at]) + column - 1


def locate(checked: Checked, line: int, column: int) -> Located | Told:
    """The innermost part of the game holding the position, or the refusal
    of a position the file or the game does not hold."""
    if not 1 <= line <= len(checked.file_lines):
        return _told(
            f"line {line} is outside {checked.path}, whose lines run from 1 to "
            f"{len(checked.file_lines)}",
            None,
            Code.POSITION_OUTSIDE_THE_FILE,
        )
    width = len(checked.file_lines[line - 1])
    if not 1 <= column <= width:
        where = "is empty" if width == 0 else f"has columns 1 to {width}"
        return _told(
            f"line {line} of {checked.path} {where}, so column {column} is outside it",
            None,
            Code.POSITION_OUTSIDE_THE_FILE,
        )
    offset = _offset(checked, line, column)
    best: tuple[object, tuple[object, ...]] | None = None
    if offset is not None:
        for node, chain in _walk(checked.game, ()):
            span = _span(node)
            if span is None or span.source_name != checked.source_name:
                continue
            start, end = _extent(checked, node, span)
            if start <= offset < end and (best is None or len(chain) > len(best[1])):
                best = (node, chain)
    if best is None:
        return _told(
            f"line {line} column {column} of {checked.path} is in no part of the "
            "game: a comment, a blank line or prose; point at a declaration, a "
            "phase, a statement or an expression",
            None,
            Code.POSITION_OUTSIDE_THE_GAME,
        )
    node, chain = best
    span = _span(node)
    assert span is not None
    return Located(chain, _words(node), _excerpt(checked, span, node), span)


def _extent(checked: Checked, node: object, span: Span) -> tuple[int, int]:
    """The text a node is written as. A name is its own spelling, where its
    span covers more (an assignment's target carries the assignment's span, a
    subscripted zone the subscript's: issue #1106)."""
    if isinstance(node, n.NameRef):
        end = span.start + len(node.name)
        if checked.program[span.start : end] == node.name:
            return span.start, end
    return span.start, span.end


def _excerpt(checked: Checked, span: Span, node: object | None = None) -> str:
    start, end = (span.start, span.end) if node is None else _extent(checked, node, span)
    text = checked.program[start:end].split("\n")[0].strip()
    return text if len(text) <= 60 else text[:57] + "..."


# What the part of a game a position lands on is, in a designer's words: a
# site by its own name, everything else by the part of the grammar it is.
_SITE_WORDS: dict[type, str] = {
    n.Transfer: "a movement",
    n.EpistemicOp: "a shuffle or a reveal",
    n.Offer: "an `offer`",
    n.Choose: "a `choose`",
    n.TrickRound: "a trick round",
    n.ClimbRound: "a climbing round",
    n.EachSimultaneous: "an `each ... simultaneously` decision",
    n.AssignStmt: "an assignment",
    n.RotateStmt: "a `rotate`",
    n.LetStmt: "a `let`",
    n.Phase: "a phase",
    n.Game: "the game",
    n.RuleDef: "a rule",
    n.MoveTypeDef: "a move type",
    n.FunctionDef: "a function",
    n.ProcedureDef: "a procedure",
    n.ZoneDecl: "a zone declaration",
    n.StateDecl: "a State Variable declaration",
    n.Parameter: "a parameter",
    n.NameRef: "a name",
}


def _words(node: object) -> str:
    words = _SITE_WORDS.get(type(node))
    if words is not None:
        return words
    if isinstance(node, _EXPR_KINDS):
        return "an expression"
    if isinstance(node, _STMT_KINDS):
        return "a statement"
    return "a declaration"


# --- the three answers --------------------------------------------------------


def scope_at(checked: Checked, chain: tuple[object, ...]) -> Scope | Told:
    """The names in scope at the innermost node of `chain` the resolver
    judged."""
    for node in reversed(chain):
        key = n.node_key(node)
        recorded = checked.scopes.get(key) if key is not None else None
        if recorded is not None:
            span = _span(node)
            assert span is not None
            named = tuple(
                InScope(name, sort)
                for name, kind in recorded.names
                if (sort := _sort(kind)) is not None
            )
            return Scope(span, named, recorded.at_a_name)
    # The Game node is always judged, and every chain starts at it.
    raise AssertionError("no node of the chain is in the Scope Record")


def type_at(checked: Checked, chain: tuple[object, ...]) -> Typed | Told:
    """The Type the checker gave the innermost expression of `chain`: of the
    expressions sharing its span (one written text read as two nodes), the
    innermost the checker typed."""
    inner = chain[-1]
    span = _span(inner)
    assert span is not None
    if not isinstance(inner, _EXPR_KINDS):
        return _told(
            f"{_words(inner)} (`{_excerpt(checked, span, inner)}`) is not an expression "
            "and has no Type; point at an expression inside it",
            span,
            Code.NOT_AN_EXPRESSION,
        )
    for node in reversed(chain):
        if _span(node) != span:
            break
        typed = _typed(checked, node)
        if typed is not None:
            return typed
    around = next(
        (t for node in reversed(chain[:-1]) if (t := _typed(checked, node)) is not None),
        None,
    )
    nearby = (
        ""
        if around is None
        else f"; the expression around it, `{around.text}`, is {' or '.join(around.types)}"
    )
    return _told(
        f"the checker reads `{_excerpt(checked, span, inner)}` without working out a Type "
        f"of its own{nearby}",
        span,
        Code.EXPRESSION_NOT_TYPED,
    )


def _typed(checked: Checked, node: object) -> Typed | None:
    if not isinstance(node, _EXPR_KINDS):
        return None
    key = n.node_key(node)
    found = checked.types.get(key) if key is not None else None
    if not found:
        return None
    span = _span(node)
    assert span is not None
    return Typed(
        span,
        _excerpt(checked, span, node),
        tuple(type_name(t) for t in found),
        any(isinstance(t, TAny) for t in found),
    )


# What a projection shows, by its level, of the game's content (`{items}`:
# "cards", or "pieces").
_PROJECTION_WORDS: dict[str, str] = {
    "identity": "which {items}",
    "count_only": "how many {items}",
    "trivial": "nothing",
}

_PICK_WORDS: dict[str, str] = {
    "announced": "every seat hears the pick",
    "moved": "no other seat hears the pick; the others learn of it through the movement",
    "pass announced": "every seat hears a pass; a play is seen through the movement",
}

ON_TURN = "the seat on turn"


def _item(checked: Checked, *, plural: bool = False) -> str:
    return content_noun(checked.game.content_flavor, plural=plural)


def seats_at(checked: Checked, chain: tuple[object, ...]) -> Seats | Told:
    """What each seat sees when the innermost movement or decision enclosing
    the position runs, from the zone types: the site itself, or the one whose
    clause the position is in."""
    for at in range(len(chain) - 1, -1, -1):
        node = chain[at]
        site = _site(checked, node, chain[:at])
        if site is not None:
            return site
        if isinstance(node, _STMT_KINDS) or not isinstance(node, _EXPR_KINDS):
            break
    inner = chain[-1]
    span = _span(inner)
    assert span is not None
    written = ""
    if isinstance(inner, (n.AssignStmt, n.RotateStmt)):
        written = (
            "; what it writes is a State Variable, which every seat is shown at "
            "its next decision"
        )
    inside = _first_site_inside(checked, inner)
    nearby = "" if inside is None else f"; the first inside it is on line {inside.line}"
    return _told(
        f"{_words(inner)} (`{_excerpt(checked, span, inner)}`) moves no "
        f"{_item(checked)} and asks no seat{written}{nearby}",
        span,
        Code.NOTHING_SEEN_HERE,
    )


def _first_site_inside(checked: Checked, node: object) -> Span | None:
    for inner, chain in _walk(node, ()):
        span = _span(inner)
        if inner is node or span is None or span.source_name != checked.source_name:
            continue
        if _site(checked, inner, chain[:-1]) is not None:
            return span
    return None


def _site(checked: Checked, node: object, enclosing: tuple[object, ...]) -> Seats | None:
    span = _span(node)
    if span is None:
        return None
    zones = {z.name: z for z in checked.game.zones}
    match node:
        case n.Transfer():
            return _movement_site(checked, node, span, enclosing, zones)
        case n.EachSimultaneous():
            if isinstance(node.body, n.Transfer):
                return _movement_site(checked, node.body, span, (*enclosing, node), zones)
            return None
        case n.EpistemicOp():
            side = _side(checked, node.zone, zones)
            label = side.label if side is not None else "the zone"
            if node.op == "shuffle":
                return Seats(span, "shuffle", None, None, None, side, None, (),
                             "no seat learns anything: a shuffle shows no seat the new order")
            return Seats(span, "reveal", None, None, None, side, None, (),
                         f"every seat sees the revealed {_item(checked)} in {label}, whatever {label} shows otherwise")
        case n.Offer():
            return _decision(span, "offer", "the seat it is offered to")
        case n.Choose():
            return _decision(span, "choose", "the acting seat")
        case n.TrickRound() | n.ClimbRound():
            construct = "trick" if isinstance(node, n.TrickRound) else "climb"
            decider = ON_TURN
            if construct == "trick" and any(f.name == CHOOSER_HELPER for f in checked.game.functions):
                decider = f"the seat `{CHOOSER_HELPER}` names for {ON_TURN}"
            source = Side(node.source_zone, f"{node.source_zone}[{ON_TURN}]")
            dest = Side(node.play_zone, node.play_zone)
            observers = _observers(checked, zones, source, ON_TURN, dest, None)
            return Seats(span, construct, construct, decider, PICK_SHOWN[construct], source, dest, observers, None)
        case _:
            return None


def _decision(span: Span, construct: str, decider: str) -> Seats:
    return Seats(span, construct, construct, decider, PICK_SHOWN[construct], None, None, (), None)


def _movement_site(
    checked: Checked,
    node: n.Transfer,
    span: Span,
    enclosing: tuple[object, ...],
    zones: Mapping[str, n.ZoneDecl],
) -> Seats:
    construct: str | None = None
    decider: str | None = None
    if node.selection_mode == "chosen":
        if enclosing and isinstance(enclosing[-1], n.EachSimultaneous):
            construct, decider = "simultaneous", "each seat, for its own pick"
        elif node.joint:
            construct, decider = "joint", "the acting seat"
        elif node.dest_each:
            construct, decider = "transfer", "each receiving seat, for the cards it receives"
        else:
            construct, decider = "transfer", "the acting seat"
    source = None if node.source is None else _side(checked, node.source, zones)
    if node.dest_each and isinstance(node.dest, n.NameRef):
        dest: Side | None = Side(node.dest.name, f"{node.dest.name}[each seat]")
        dest_key: str | None = "each seat"
    else:
        dest = _side(checked, node.dest, zones)
        dest_key = None if dest is None else _key_text(checked, node.dest)
    source_key = None if node.source is None else _key_text(checked, node.source)
    observers = _observers(checked, zones, source, source_key, dest, dest_key)
    every = None
    if node.source is None:
        every = f"the {_item(checked, plural=True)} come from every zone, each seen as its own type shows it"
    pick = None if construct is None else PICK_SHOWN[construct]
    return Seats(span, "movement", construct, decider, pick, source, dest, observers, every)


def _side(checked: Checked, expr: n.Expr, zones: Mapping[str, n.ZoneDecl]) -> Side | None:
    """The zone an expression names, as written; None for a zone the
    expression decides only when it runs."""
    name = expr.obj if isinstance(expr, n.Subscript) else expr
    if not isinstance(name, n.NameRef) or name.ref_kind != "zone" or name.name not in zones:
        return None
    span = _span(expr)
    label = name.name if span is None else checked.program[span.start : span.end]
    return Side(name.name, " ".join(label.split()))


def _key_text(checked: Checked, expr: n.Expr) -> str | None:
    if isinstance(expr, n.Subscript) and (span := _span(expr.index)) is not None:
        return " ".join(checked.program[span.start : span.end].split())
    return None


def _holder(checked: Checked, zones: Mapping[str, n.ZoneDecl], side: Side | None) -> bool:
    if side is None:
        return False
    decl = zones[side.zone]
    positions = {p.name: p for p in checked.game.positions}
    return held(decl.index, positions)


def _holder_words(zones: Mapping[str, n.ZoneDecl], side: Side) -> str:
    index = zones[side.zone].index
    role = role_of(index) if index is not None else None
    if role is not None and role.value == "team":
        return f"each seat of the team holding {side.label}"
    return f"the seat holding {side.label}"


def _observers(
    checked: Checked,
    zones: Mapping[str, n.ZoneDecl],
    source: Side | None,
    source_key: str | None,
    dest: Side | None,
    dest_key: str | None,
) -> tuple[Observer, ...]:
    """Every kind of seat a movement can have, by which of its two zone
    instances the seat holds, and what each sees through the zone types."""
    holds_s = _holder(checked, zones, source)
    holds_d = _holder(checked, zones, dest)
    kinds: list[tuple[str, bool, bool]] = []
    if holds_s and holds_d and source is not None and dest is not None:
        if source_key is not None and source_key == dest_key:
            kinds.append((f"{_holder_words(zones, source)} and {dest.label}", True, True))
        else:
            kinds.append((_holder_words(zones, source), True, False))
            kinds.append((_holder_words(zones, dest), False, True))
            kinds.append(("a seat holding both, where one seat does", True, True))
    elif holds_s and source is not None:
        kinds.append((_holder_words(zones, source), True, False))
    elif holds_d and dest is not None:
        kinds.append((_holder_words(zones, dest), False, True))
    kinds.append(("every other seat" if kinds else "every seat", False, False))
    out: list[Observer] = []
    for who, on_s, on_d in kinds:
        sp = None if source is None else zone_projection(zones[source.zone].type_ref.name, on_s)
        dp = None if dest is None else zone_projection(zones[dest.zone].type_ref.name, on_d)
        learns = movement_seen(sp or "trivial", dp or "trivial") if sp or dp else False
        out.append(Observer(who, on_s, on_d, sp, dp, learns))
    return tuple(out)


# --- asking -------------------------------------------------------------------


def ask(checked: Checked, line: int, column: int) -> Answer:
    """The Checker Query's answer at a position of a checked file."""
    located = locate(checked, line, column)
    if isinstance(located, Told):
        return Answer(checked.path, line, column, EXIT_CANNOT_PROCEED, refused=(located,))
    return Answer(
        checked.path,
        line,
        column,
        EXIT_ANSWERED,
        located=located,
        items=_item(checked, plural=True),
        scope=scope_at(checked, located.chain),
        type=type_at(checked, located.chain),
        seats=seats_at(checked, located.chain),
    )


def refused(path: str, line: int, column: int, told: tuple[Told, ...], exit_code: int) -> Answer:
    """The answer for a file the checker refuses, or cannot read: its
    refusal, and nothing else."""
    return Answer(path, line, column, exit_code, refused=told)


def ask_path(path: Path, line: int, column: int) -> Answer:
    """`ask`, for a game file on disk the checker has accepted."""
    return ask(checked_text(path.read_text(), str(path), path.suffix == ".md"), line, column)


# --- the text a designer reads ------------------------------------------------


def render(answer: Answer) -> str:
    """The answer as a designer reads it, from the same value the record is
    made from."""
    if answer.located is None:
        return "\n".join(t.diagnostic.format() for t in answer.refused)
    loc = answer.located
    lines = [f"{answer.path}:{loc.span.line}:{loc.span.column}: {loc.words}: {loc.text}"]
    lines.extend(_render_scope(answer.scope))
    lines.extend(_render_type(answer.type))
    lines.extend(_render_seats(answer.seats, answer.items))
    return "\n".join(lines)


def _refusal_line(heading: str, told: Told) -> list[str]:
    return [f"{heading}: none here -- {told.diagnostic.message}"]


def _render_scope(scope: Scope | Told | None) -> list[str]:
    if scope is None:
        return []
    if isinstance(scope, Told):
        return _refusal_line("names in scope", scope)
    out = ["names in scope:"]
    for sort, words in SORTS.items():
        names = [s.name for s in scope.names if s.sort == sort]
        if names:
            out.append(f"  {words}: {', '.join(names)}")
    if not scope.at_a_name:
        out.append(
            "  (every State Variable is listed; which are live here is judged at a "
            "name, so point at one to see)"
        )
    return out


def _render_type(typed: Typed | Told | None) -> list[str]:
    if typed is None:
        return []
    if isinstance(typed, Told):
        return _refusal_line("Type", typed)
    open_words = " (the checker leaves it open: any value passes)" if typed.open else ""
    return [f"Type: `{typed.text}` is {' or '.join(typed.types)}{open_words}"]


def _render_seats(seats: Seats | Told | None, items: str) -> list[str]:
    if seats is None:
        return []
    if isinstance(seats, Told):
        return _refusal_line("what each seat sees", seats)
    out = [
        f"what each seat sees (static, from the zone types; which {items}, and which "
        "seat holds a zone, are settled when the game is played):"
    ]
    if seats.decider is not None:
        out.append(f"  who decides: {seats.decider}, asked and remembering each pick")
    if seats.pick is not None:
        out.append(f"  {_PICK_WORDS[seats.pick]}")
    if seats.every_seat is not None:
        out.append(f"  {seats.every_seat}")
    for obs in seats.observers:
        out.append(f"  {obs.who}: {_sees(obs, seats.source, seats.destination, items)}")
    return out


def _sees(obs: Observer, source: Side | None, dest: Side | None, items: str) -> str:
    if not obs.learns:
        return "learns nothing of it"
    parts: list[str] = []
    if source is not None and obs.source is not None and obs.source != "trivial":
        parts.append(f"{_PROJECTION_WORDS[obs.source].format(items=items)} leave {source.label}")
    if dest is not None and obs.destination is not None and obs.destination != "trivial":
        parts.append(f"{_PROJECTION_WORDS[obs.destination].format(items=items)} arrive at {dest.label}")
    return "sees " + ", and ".join(parts)
