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
Establishes:  the names in scope are read from the resolver's Scope Record
              (`resolve(scopes=...)`, classified by the resolver's own
              classifier) and the Type from the type checker's Type Record
              (`typecheck(types=...)`, every Type `infer` returned); neither
              is worked out here. What each seat sees of a movement reads the
              projection the emitter reads (`stdlib.zones.zone_projection`),
              its rule for a seat learning of a movement at all
              (`observe.movement_seen`) and for which zones have a holder
              (`observe.held`), and what the others hear of a pick reads the
              pick table (`observe.PICK_SHOWN`), saying it is settled in play
              where the table holds no row. Every position of the file gets an
              answer or a told refusal carrying its Diagnostic Code, addressed
              to whoever ran the query; a refusal says what can be answered
              nearby, and a part of the game that runs sites standing
              elsewhere names where they stand. The per-seat answer is the
              static one, and says so; an end of a movement whose zone only
              play names, and the pick of a construct the table holds no row
              for, are said to be settled in play, never answered as nothing.
Restates:     what this module spells of the runtime rather than reads, each
              held by the oracle that plays every corpus game and compares
              each delivered event with the answer
              (tests/test_query_seats.py): the construct a movement's shape is
              asked by (`delegation.DECISION_POINTS`' sites); who decides each
              construct; that a reveal reaches every seat and a shuffle none
              (`execute._epistemic`); a round's routed decider and source
              (`delegation.decider_for`, `delegation.source_for`, for the forms
              `delegation.ROUTED_FORMS` names); the seats a climbing round asks
              out of turn (`primitives.climb_interrupt_decline`,
              `primitives.climb_announcements`, its Hosted Poll); the zones a
              source-less movement collects from (`execute._gather`); the zones
              an end can name (each branch of a conditional, the result of a
              function the game defines); and what a `run`, an offer or a round
              goes on to run (`expand`'s splice, a move type's effect).
Now illegal:  a scope walk or a type inference of this module's own; a
              projection rule of its own; an answer about a file the checker
              refuses.
Held by:      Derived and Pinned: tests/test_query.py crosses every `Node`
              kind with the three answers over the corpus, and
              tests/test_query_seats.py holds every per-seat answer a seeded
              line reaches to what play delivers.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import assert_never, get_args

from cardlang.ast import nodes as n
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Author, Diagnostic, Severity, Span, Told
from cardlang.domains import Role, role_of
from cardlang.extract import extract_single_block
from cardlang.parse import parse_block, parse_text
from cardlang.resolve import NamesInScope, resolve
from cardlang.runtime import primitives
from cardlang.runtime.delegation import CHOOSER_HELPER, HELPER_NAMES, ROUTED_FORMS, SOURCE_HELPER
from cardlang.runtime.mechanics import ClimbForm, TrickForm
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
    # The game's `uses` lines, which the resolver splices and drops, as the
    # parse wrote them.
    uses: tuple[n.UsesDecl, ...] = ()


def _file_lines(text: str) -> tuple[str, ...]:
    """The file's lines as `check` numbers them: a final newline ends the
    last line rather than starting another."""
    lines = text.split("\n")
    return tuple(lines[:-1] if len(lines) > 1 and lines[-1] == "" else lines)


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
        source_name, _file_lines(text), source_name, program, offset, game, scopes, types, tree.uses
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
    uses: n.UsesDecl | None = None


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
    """One end of a movement: the zone and its instance as written, or, where
    only play decides the zone (a `let`-bound zone, a parameter, a value
    worked out at play time), no zone and what decides it. `key` is the
    instance's index as written; `each` marks every instance of a family,
    one movement apiece (a gather)."""

    zone: str | None
    label: str
    key: str | None = None
    each: bool = False
    settled: str | None = None


@dataclass(frozen=True)
class Observer:
    """One kind of seat, and what it sees of a movement through each end's
    projection. An end whose zone only play decides has no projection here
    and no holding (None); `learns` is None where whether the seat learns of
    the movement at all is settled in play."""

    who: str
    holds_source: bool | None
    holds_destination: bool | None
    source: str | None
    destination: str | None
    learns: bool | None


@dataclass(frozen=True)
class TransferRoute:
    """One way a site can move content: its two ends, and every kind of
    seat's view of the move."""

    source: Side
    destination: Side
    observers: tuple[Observer, ...]


@dataclass(frozen=True)
class Seats:
    """What each seat sees when the site at `span` runs, from the zone types
    (the static form): who decides, who else is asked, what the others hear
    of the pick, each way the site can move content and what each kind of
    seat sees of it, and where the movements and decisions it runs next
    stand. `pick` is None where `observe.PICK_SHOWN` holds no row: what the
    others hear is then settled in play."""

    span: Span
    text: str
    site: str
    construct: str | None
    decider: str | None
    out_of_turn: tuple[str, ...]
    pick: str | None
    source_from: str | None
    moves: tuple[TransferRoute, ...]
    every_seat: str | None
    then: tuple[Span, ...]


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
    # A line's columns are its characters and its end, where a cursor stands
    # after the last of them (the only column an empty line has).
    width = len(checked.file_lines[line - 1])
    if not 1 <= column <= width + 1:
        return _told(
            f"line {line} of {checked.path} has columns 1 to {width + 1}, its last "
            f"at the line's end, so column {column} is outside it",
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
            if span.start <= offset < span.end and (best is None or len(chain) > len(best[1])):
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
    for uses in checked.uses:
        if uses.span is not None and offset is not None and uses.span.start <= offset < uses.span.end:
            return Located(chain, "a `uses` line", _excerpt(checked, uses.span), uses.span, uses)
    return Located(chain, _words(node), _excerpt(checked, span), span)


def _excerpt(checked: Checked, span: Span) -> str:
    text = checked.program[span.start : span.end].split("\n")[0].strip()
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
            f"{_words(inner)} (`{_excerpt(checked, span)}`) is not an expression "
            "and the checker gives it no Type; point at an expression inside it",
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
        f"the checker reads `{_excerpt(checked, span)}` without working out a Type "
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
        _excerpt(checked, span),
        tuple(type_name(t) for t in found),
        any(isinstance(t, TAny) for t in found),
    )


# What a projection shows, by its level, of the game's content (`{items}`:
# "cards", or "pieces"); one row per level of `PROJECTION_LEVELS`
# (tests/test_query.py pins the two together).
PROJECTION_WORDS: dict[str, str] = {
    "trivial": "nothing",
    "existence_only": "whether any {items}",
    "count_only": "how many {items}",
    "count_by_type": "how many {items} of each kind",
    "identity_set": "which {items}, not how many of each",
    "identity": "which {items}",
}

_PICK_WORDS: dict[str, str] = {
    "announced": "every seat hears the pick",
    "moved": "no other seat hears the pick; the others learn of it through the movement",
}
_PICK_SETTLED = "what the other seats hear of a pick is settled in play (issue #1111)"

ON_TURN = "the seat on turn"

# The round forms, by the node a `round` is (`mechanics.build_form`).
_FORMS: dict[type, type] = {n.TrickRound: TrickForm, n.ClimbRound: ClimbForm}


def _item(checked: Checked, *, plural: bool = False) -> str:
    return content_noun(checked.game.content_flavor, plural=plural)


def seats_at(checked: Checked, chain: tuple[object, ...]) -> Seats | Told:
    """What each seat sees when the innermost movement or decision enclosing
    the position runs, from the zone types: the site itself, or the one whose
    clause the position is in. Elsewhere, the part of the game holding the
    position is refused, with where the movements and decisions it runs
    stand when it runs any."""
    at = len(chain) - 1
    while at >= 0:
        node = chain[at]
        site = _site(checked, node, chain[:at])
        if site is not None:
            return site
        if isinstance(node, _STMT_KINDS) or not isinstance(node, _EXPR_KINDS):
            break
        at -= 1
    holder = chain[max(at, 0)]
    span = _span(holder)
    assert span is not None
    said = f"{_words(holder)} (`{_excerpt(checked, span)}`)"
    reached = _reached(checked, holder)
    if reached:
        return _told(
            f"{said} moves no {_item(checked)} itself and asks no seat; the movements "
            f"and decisions it runs stand at {_places(checked, reached, span)}; ask at each",
            span,
            Code.SEEN_AT_ITS_SITES,
        )
    written = ""
    if isinstance(holder, (n.AssignStmt, n.RotateStmt)):
        written = (
            "; what it writes is a State Variable, which every seat is shown at "
            "its next decision"
        )
    return _told(
        f"{said} moves no {_item(checked)} and asks no seat{written}",
        span,
        Code.NOTHING_SEEN_HERE,
    )


def _is_site(node: object) -> bool:
    return isinstance(
        node,
        (n.Transfer, n.EachSimultaneous, n.EpistemicOp, n.Offer, n.Choose, n.TrickRound, n.ClimbRound),
    )


def _reached(checked: Checked, root: object) -> tuple[Span, ...]:
    """Where every movement and decision `root` runs stands, `root` itself
    aside: those written inside it, inside each procedure it runs, and
    inside the effect of each move type it offers or plays, followed as the
    runtime follows them (a `run` splices its procedure's body; an offer or a
    round runs its move type's effect)."""
    procedures = {p.name: p for p in checked.game.procedures}
    move_types = {m.name: m for m in checked.game.move_types}
    found: dict[tuple[str, int, int], Span] = {}
    followed: set[str] = set()

    def follow(definition: object | None, name: str) -> None:
        if definition is not None and name not in followed:
            followed.add(name)
            visit(definition)

    def visit(start: object) -> None:
        for node, _chain in _walk(start, ()):
            span = _span(node)
            if node is not root and node is not start and _is_site(node) and span is not None:
                found.setdefault((span.source_name, span.start, span.end), span)
            match node:
                case n.RunStmt():
                    follow(procedures.get(node.name), f"procedure {node.name}")
                case n.Offer():
                    for name in node.offering:
                        follow(move_types.get(name), f"move {name}")
                case n.TrickRound() | n.ClimbRound():
                    follow(move_types.get(node.move_type), f"move {node.move_type}")
                case _:
                    pass

    visit(root)
    return tuple(sorted(found.values(), key=lambda s: (s.source_name != checked.source_name, s.source_name, s.start)))


def _places(checked: Checked, spans: Sequence[Span], beside: Span | None = None, most: int = 6) -> str:
    """Where some spans stand, as a designer reads them: a line of this file,
    with its column where it shares a line with `beside`, or a line of a
    family library's (asked about there as issue #1110)."""

    def place(s: Span) -> str:
        if s.source_name != checked.source_name:
            return f"line {s.line} of {s.source_name} (issue #1110)"
        if beside is not None and s.line == beside.line:
            return f"line {s.line}, column {s.column}"
        return f"line {s.line}"

    named = [place(s) for s in spans]
    named = list(dict.fromkeys(named))
    shown = ", ".join(named[:most])
    return shown if len(named) <= most else f"{shown} and {len(named) - most} more"


def _site(checked: Checked, node: object, enclosing: tuple[object, ...]) -> Seats | None:
    span = _span(node)
    if span is None:
        return None
    zones = {z.name: z for z in checked.game.zones}
    text = _excerpt(checked, span)
    match node:
        case n.Transfer():
            return _movement_site(checked, node, span, text, enclosing, zones)
        case n.EachSimultaneous():
            if isinstance(node.body, n.Transfer):
                return _movement_site(checked, node.body, span, text, (*enclosing, node), zones)
            return None
        case n.EpistemicOp():
            # What `execute._epistemic` emits: nothing for a shuffle; for a
            # reveal, the card to every seat, whatever the zone shows.
            ends = _ends(checked, node.zone, zones)
            label = " or ".join(e.label for e in ends)
            if node.op == "shuffle":
                every = "no seat learns anything: a shuffle shows no seat the new order"
            else:
                every = f"every seat sees the revealed {_item(checked)} in {label}, whatever {label} shows otherwise"
            return Seats(span, text, node.op, None, None, (), None, None, (), every, ())
        case n.Offer():
            return Seats(
                span, text, "offer", "offer", "the seat it is offered to", (),
                PICK_SHOWN["offer"], None, (), None, _reached(checked, node),
            )
        case n.Choose():
            return Seats(span, text, "choose", "choose", "the acting seat", (), PICK_SHOWN["choose"], None, (), None, ())
        case n.TrickRound() | n.ClimbRound():
            return _round_site(checked, node, span, text, zones)
        case _:
            return None


def _round_site(
    checked: Checked,
    node: n.TrickRound | n.ClimbRound,
    span: Span,
    text: str,
    zones: Mapping[str, n.ZoneDecl],
) -> Seats:
    """A round: its decider and source as the runtime routes them
    (`delegation.decider_for`, `delegation.source_for`, for a form in
    `delegation.ROUTED_FORMS` alone), and, for a climbing round, the seats a
    registered engine asks out of turn (`primitives.climb_interrupt_decline`,
    `primitives.climb_announcements`) and its Hosted Poll."""
    construct = "trick" if isinstance(node, n.TrickRound) else "climb"
    routed = _FORMS[type(node)].__name__ in ROUTED_FORMS
    helpers = {f.name: f for f in checked.game.functions if f.name in HELPER_NAMES}
    decider = ON_TURN
    if routed and CHOOSER_HELPER in helpers:
        decider = f"the seat `{CHOOSER_HELPER}` names for {ON_TURN}"
    source_from = None
    sources: tuple[Side, ...] = (Side(node.source_zone, f"{node.source_zone}[{ON_TURN}]", key=ON_TURN),)
    if routed and SOURCE_HELPER in helpers:
        helper = helpers[SOURCE_HELPER]
        sources = _ends(checked, helper.body, zones)
        param = helper.params[0].name if helper.params else "its argument"
        source_from = (
            f"the {_item(checked, plural=True)} come from the zone `{SOURCE_HELPER}` "
            f"names for {ON_TURN} ({param} below): {' or '.join(s.label for s in sources)}"
        )
    out_of_turn: list[str] = []
    if isinstance(node, n.ClimbRound):
        if isinstance(node.engine, n.RegisteredEngine):
            if primitives.climb_interrupt_decline(node.engine.lead) is not None:
                out_of_turn.append(
                    "after a play, the other seats are asked, out of turn, whether to "
                    "beat it (the engine's interrupt window)"
                )
            if primitives.climb_announcements(node.engine.lead):
                out_of_turn.append("a seat may be asked to make an announcement before it plays")
        if node.hosted is not None:
            out_of_turn.append(
                f"before each ask, the `before asking` statements run for the seat about "
                f"to be asked (line {node.hosted.span.line if node.hosted.span else span.line})"
            )
    dest = Side(node.play_zone, node.play_zone)
    moves = tuple(TransferRoute(s, dest, _observers(checked, zones, s, dest)) for s in sources)
    return Seats(
        span, text, construct, construct, decider, tuple(out_of_turn), PICK_SHOWN[construct],
        source_from, moves, None, _reached(checked, node),
    )


def _movement_site(
    checked: Checked,
    node: n.Transfer,
    span: Span,
    text: str,
    enclosing: tuple[object, ...],
    zones: Mapping[str, n.ZoneDecl],
) -> Seats:
    # The construct a chosen movement is asked by, as the decision points
    # its shapes reach name it (`delegation.DECISION_POINTS`).
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
    sources = _gathered(checked, node, zones) if node.source is None else _ends(checked, node.source, zones)
    if node.dest_each and isinstance(node.dest, n.NameRef):
        dests: tuple[Side, ...] = (Side(node.dest.name, f"{node.dest.name}[each seat]", key="each seat"),)
    else:
        dests = _ends(checked, node.dest, zones)
    moves = tuple(
        TransferRoute(s, d, _observers(checked, zones, s, d)) for s in sources for d in dests
    )
    every = None
    if node.source is None:
        every = (
            f"the {_item(checked, plural=True)} come from every other zone, one movement "
            "apiece, each seen as its own type shows it"
        )
    pick = None if construct is None else PICK_SHOWN[construct]
    return Seats(span, text, "movement", construct, decider, (), pick, None, moves, every, ())


def _gathered(checked: Checked, node: n.Transfer, zones: Mapping[str, n.ZoneDecl]) -> tuple[Side, ...]:
    """The zones a source-less movement collects from, as `execute._gather`
    reads them: every zone but the destination instance, a family's
    instances one movement apiece."""
    dests = _ends(checked, node.dest, zones)
    single_dests = {d.zone for d in dests if d.zone is not None and d.key is None}
    out: list[Side] = []
    for name in sorted(zones):
        decl = zones[name]
        if decl.index is None:
            if name not in single_dests:
                out.append(Side(name, name))
        else:
            out.append(Side(name, f"each {name}", each=True))
    return tuple(out)


def _ends(
    checked: Checked, expr: n.Expr, zones: Mapping[str, n.ZoneDecl], seen: frozenset[str] = frozenset()
) -> tuple[Side, ...]:
    """The zones an expression can name, each as written: a zone or a zone
    instance, every branch of a conditional, and the result of a function the
    game defines; anything else names its zone only when the game is
    played."""
    span = _span(expr)
    written = "the zone" if span is None else " ".join(checked.program[span.start : span.end].split())
    functions = {f.name: f for f in checked.game.functions}
    match expr:
        case n.NameRef() if expr.ref_kind == "zone" and expr.name in zones:
            return (Side(expr.name, expr.name),)
        case n.Subscript(obj=n.NameRef() as obj) if obj.ref_kind == "zone" and obj.name in zones:
            return (Side(obj.name, written, key=_key_text(checked, expr)),)
        case n.IfExpr():
            branches = (expr.then, *(value for _cond, value in expr.elifs), expr.otherwise)
            found = [side for b in branches for side in _ends(checked, b, zones, seen)]
            return tuple(dict.fromkeys(found))
        case n.Call() if expr.func in functions and expr.func not in seen:
            return _ends(checked, functions[expr.func].body, zones, seen | {expr.func})
        case _:
            return (Side(None, written, settled=f"`{written}` names its zone only when the game is played"),)


def _key_text(checked: Checked, expr: n.Expr) -> str | None:
    if isinstance(expr, n.Subscript) and (span := _span(expr.index)) is not None:
        return " ".join(checked.program[span.start : span.end].split())
    return None


def _holder(checked: Checked, zones: Mapping[str, n.ZoneDecl], side: Side) -> bool:
    if side.zone is None:
        return False
    positions = {p.name: p for p in checked.game.positions}
    return held(zones[side.zone].index, positions)


def _holder_words(zones: Mapping[str, n.ZoneDecl], side: Side) -> str:
    assert side.zone is not None
    index = zones[side.zone].index
    role = role_of(index) if index is not None else None
    team = role is Role.TEAM
    if side.each:
        return f"each seat of the team holding one {side.zone}" if team else f"the seat holding each {side.zone}"
    return f"each seat of the team holding {side.label}" if team else f"the seat holding {side.label}"


def _observers(
    checked: Checked, zones: Mapping[str, n.ZoneDecl], source: Side, dest: Side
) -> tuple[Observer, ...]:
    """Every kind of seat a movement can have, by which of its two zone
    instances the seat holds, and what each sees through the zone types; an
    end whose zone only play decides is no part of a seat's kind, and what a
    seat sees of it is settled in play."""
    holds_s = _holder(checked, zones, source)
    holds_d = _holder(checked, zones, dest)
    kinds: list[tuple[str, bool, bool]] = []
    if holds_s and holds_d:
        if source.key is not None and source.key == dest.key:
            kinds.append((f"{_holder_words(zones, source)} and {dest.label}", True, True))
        else:
            kinds.append((_holder_words(zones, source), True, False))
            kinds.append((_holder_words(zones, dest), False, True))
            kinds.append(("a seat holding both, where one seat does", True, True))
    elif holds_s:
        kinds.append((_holder_words(zones, source), True, False))
    elif holds_d:
        kinds.append((_holder_words(zones, dest), False, True))
    kinds.append(("every other seat" if kinds else "every seat", False, False))
    out: list[Observer] = []
    for who, on_s, on_d in kinds:
        sp = None if source.zone is None else zone_projection(zones[source.zone].type_ref.name, on_s)
        dp = None if dest.zone is None else zone_projection(zones[dest.zone].type_ref.name, on_d)
        learns: bool | None
        if sp is not None and dp is not None:
            learns = movement_seen(sp, dp)
        elif (sp or "trivial") != "trivial" or (dp or "trivial") != "trivial":
            learns = True
        else:
            learns = None
        out.append(
            Observer(
                who,
                None if source.zone is None else on_s,
                None if dest.zone is None else on_d,
                sp,
                dp,
                learns,
            )
        )
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
        seats=_uses_seats(checked, located) if located.uses is not None else seats_at(checked, located.chain),
    )


def _uses_seats(checked: Checked, located: Located) -> Told:
    """A `uses` line runs nothing itself: the definitions it splices stand in
    the library's file, where the query cannot answer yet."""
    assert located.uses is not None
    library = located.uses.name
    spliced = [
        s for node, _chain in _walk(checked.game, ())
        if _is_site(node) and (s := _span(node)) is not None and s.source_name != checked.source_name
        and library in s.source_name
    ]
    where = _places(checked, spliced) if spliced else "no line of it"
    return _told(
        f"a `uses` line moves no {_item(checked)} itself and asks no seat; it brings in "
        f"`{library}`, whose movements and decisions that this game holds stand at {where}",
        located.span,
        Code.SEEN_AT_ITS_SITES,
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
    lines.extend(_render_seats(answer.seats, answer.items, loc.span))
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
            "  (which of these a name may be also depends on the slot it is written "
            "in; point at a name to see)"
        )
    return out


def _render_type(typed: Typed | Told | None) -> list[str]:
    if typed is None:
        return []
    if isinstance(typed, Told):
        return _refusal_line("the checker's Type", typed)
    open_words = (
        " (the checker works out nothing narrower: it passes where any value may "
        "stand, and a position needing an exact Type, such as an `and` operand or "
        "a condition, refuses it)"
        if typed.open
        else ""
    )
    return [f"the checker's Type: `{typed.text}` is {' or '.join(typed.types)}{open_words}"]


def _render_seats(seats: Seats | Told | None, items: str, asked: Span | None) -> list[str]:
    if seats is None:
        return []
    if isinstance(seats, Told):
        return _refusal_line("what each seat sees", seats)
    out = [
        f"what each seat sees (static, from the zone types; which {items}, and which "
        "seat holds a zone, are settled when the game is played):"
    ]
    if asked is None or (seats.span.line, seats.span.column) != (asked.line, asked.column):
        out.append(f"  answered at the {seats.site} on line {seats.span.line}: {seats.text}")
    if seats.construct is not None:
        out.append(f"  asked as: {seats.construct}")
    if seats.decider is not None:
        out.append(f"  who decides: {seats.decider}, asked and remembering each pick")
    out.extend(f"  also asked: {words}" for words in seats.out_of_turn)
    if seats.construct is not None:
        out.append(f"  {_PICK_SETTLED if seats.pick is None else _PICK_WORDS[seats.pick]}")
    if seats.source_from is not None:
        out.append(f"  {seats.source_from}")
    if seats.every_seat is not None:
        out.append(f"  {seats.every_seat}")
    for move in seats.moves:
        indent = "  "
        if len(seats.moves) > 1:
            out.append(f"  when it moves from {move.source.label} to {move.destination.label}:")
            indent = "    "
        out.extend(
            f"{indent}{obs.who}: {sees(obs, move, items)}" for obs in move.observers
        )
    if seats.then:
        out.append(f"  then it runs the movements and decisions at {', '.join(_then_places(seats))}")
    return out


def _then_places(seats: Seats) -> list[str]:
    file = seats.span.source_name
    return list(
        dict.fromkeys(
            f"line {s.line}" if s.source_name == file else f"line {s.line} of {s.source_name} (issue #1110)"
            for s in seats.then
        )
    )


def sees(obs: Observer, move: TransferRoute, items: str) -> str:
    """What one kind of seat sees of one movement, in a designer's words."""
    if obs.learns is False:
        return "learns nothing of it"
    parts: list[str] = []
    unsettled: list[str] = []
    for side, projection, verb in (
        (move.source, obs.source, "leave"),
        (move.destination, obs.destination, "arrive at"),
    ):
        if side.zone is None:
            unsettled.append(side.label)
        elif projection is not None and projection != "trivial":
            parts.append(f"{PROJECTION_WORDS[projection].format(items=items)} {verb} {side.label}")
    said = "sees " + ", and ".join(parts) if parts else ""
    if unsettled:
        later = f"what it sees of {' and '.join(unsettled)} is settled in play, which names the zone"
        said = f"{said}; {later}" if said else later
    return said
