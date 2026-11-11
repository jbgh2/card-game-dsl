"""The Record Envelope: the checker's and the runtime's refusals as data.

A tool reading `cardlang check --json` reads one [[record-envelope]]: a JSON
document carrying its format's version (`schema`), what it holds (`kind`),
and, for a check, one Diagnostic Record per told diagnostic. A record holds
what `Diagnostic.format` prints, as fields: the [[diagnostic-code]], the
severity, the author who must act, the span, the message, the notes, and the
Near Misses as suggestions marked `offered`. The words are the diagnostic's
own; this module composes none and decides no author. The lines the command
line prints around a diagnostic -- a runtime refusal's phase and zone, the
hint that a mistyped path may have meant a command -- are not carried
(issue #1103). A `cardlang query --json` envelope holds one
[[checker-query]]'s answer, with any refusal as Diagnostic Records of the
same shape.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      every diagnostic it is handed is told (`Told`): its file
              decided by `cardlang.attribution` or by the raise that made
              it, and its author stamped there.
Establishes:  `envelope` (a check's) and `query_envelope` (a Checker
              Query's, from the one `query.Answer` its text is rendered from)
              are the producers of a Record Envelope, and
              `span_record` the one encoding of a place in it; a record's
              `message` is `Diagnostic.message`, and its suggestions are
              `Diagnostic.near_misses`, each `offered`; `refusal_diagnostic`
              is the one way a runtime refusal becomes a told diagnostic, by
              an exhaustive match over the refusal types the command line
              renders (`RUNTIME_REFUSALS`), and the one place outside the
              tests that reads a refusal's guard role, only to name its
              Author and code; `read_envelope` refuses a schema that is not
              this integer, a kind it does not know, and a payload of
              another shape than its kind's, rather than reading it
              best-effort.
Now illegal:  a second JSON spelling of a diagnostic or a place; a record
              whose words differ from the text a designer reads
              (tests/test_records.py, the round trip over the rejection
              corpus); a suggestion marked mechanically applicable.
Held by:      Derived and Pinned throughout. The match ends in
              `assert_never`, so the type checker holds its arms against
              `RuntimeRefusal`, but `RuntimeRefusal` is a hand-written union:
              a refusal class added to `cardlang.runtime.errors` and left out
              of it type-checks, and only tests/test_records.py, walking that
              module's classes, refuses it. The record's agreement with the
              text is held by the round trip over the rejection corpus.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import TypeVar, assert_never

from cardlang import query as q
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Author, Diagnostic, Severity, Span, Told
from cardlang.runtime.errors import (
    GameDescriptionError,
    GameRegistrationError,
    InstallationError,
    ShadowGuardError,
)
from cardlang.runtime.state import IllegalMove

#: The Record Envelope's format version. A change a reader could misread
#: moves it, and `read_envelope` refuses a version it does not know.
SCHEMA = 1

Record = dict[str, object]


class Kind(Enum):
    """What a Record Envelope holds."""

    DIAGNOSTICS = "diagnostics"
    QUERY = "query"


class Applicability(Enum):
    """How a suggestion may be applied: a Near Miss can name the wrong
    declared thing, so it is only ever offered."""

    OFFERED = "offered"


def span_record(span: Span | None) -> Record | None:
    """A place in a file: its name, line, column and length. The offsets a
    `Span` counts from are left out, since in a Markdown game file they count
    from the fenced block rather than from the file."""
    if span is None:
        return None
    return {
        "file": span.source_name,
        "line": span.line,
        "column": span.column,
        "length": span.end - span.start,
    }


def diagnostic_record(told: Told) -> Record:
    """One told diagnostic as a Diagnostic Record."""
    d = told.diagnostic
    return {
        "code": d.code.slug,
        "severity": d.severity.value,
        "author": told.author.value,
        "span": span_record(d.span),
        "message": d.message,
        "notes": [{"span": span_record(nt.span), "message": nt.message} for nt in d.notes],
        "suggestions": [
            {"text": name, "applicability": Applicability.OFFERED.value} for name in d.near_misses
        ],
    }


def envelope(told: Sequence[Told]) -> Record:
    """The Record Envelope of a check: every diagnostic it told, in the order
    the text output prints them; none for a game that checks clean."""
    return {
        "schema": SCHEMA,
        "kind": Kind.DIAGNOSTICS.value,
        "diagnostics": [diagnostic_record(t) for t in told],
    }


def query_envelope(answer: q.Answer) -> Record:
    """The Record Envelope of a Checker Query: where it was asked, any refusal
    of the whole question (the checker's, or the position's), and each of the
    three answers or the refusal standing in its place -- the facts the text a
    designer reads (`query.render`) is made from."""
    return {
        "schema": SCHEMA,
        "kind": Kind.QUERY.value,
        "at": {"file": answer.path, "line": answer.line, "column": answer.column},
        "diagnostics": [diagnostic_record(t) for t in answer.refused],
        "answer": None if answer.located is None else _answer_record(answer),
    }


def _answer_record(answer: q.Answer) -> Record:
    loc = answer.located
    assert loc is not None
    return {
        "part": {"what": loc.words, "span": span_record(loc.span), "text": loc.text},
        "scope": _or_refused(answer.scope, _scope_record),
        "type": _or_refused(answer.type, _type_record),
        "seats": _or_refused(answer.seats, _seats_record),
    }


_Answered = TypeVar("_Answered")


def _or_refused(
    value: _Answered | Told | None, record: Callable[[_Answered], Record]
) -> Record | None:
    if value is None:
        return None
    if isinstance(value, Told):
        return {"refused": diagnostic_record(value)}
    return record(value)


def _scope_record(scope: q.Scope) -> Record:
    return {
        "span": span_record(scope.span),
        "names": [{"name": s.name, "sort": s.sort} for s in scope.names],
        "at-a-name": scope.at_a_name,
    }


def _type_record(typed: q.Typed) -> Record:
    return {
        "span": span_record(typed.span),
        "text": typed.text,
        "types": list(typed.types),
        "open": typed.open,
    }


def _side_record(side: q.Side | None) -> Record | None:
    return None if side is None else {"zone": side.zone, "label": side.label}


def _seats_record(seats: q.Seats) -> Record:
    return {
        "form": "static",
        "span": span_record(seats.span),
        "site": seats.site,
        "construct": seats.construct,
        "decider": seats.decider,
        "pick": seats.pick,
        "source": _side_record(seats.source),
        "destination": _side_record(seats.destination),
        "observers": [
            {
                "who": o.who,
                "holds-source": o.holds_source,
                "holds-destination": o.holds_destination,
                "source": o.source,
                "destination": o.destination,
                "learns": o.learns,
            }
            for o in seats.observers
        ],
        "every-seat": seats.every_seat,
    }


class UnreadableEnvelope(ValueError):
    """A document this version of the format cannot read."""


# The fields of a Diagnostic Record, and of a place in one.
_RECORD_FIELDS = frozenset({"code", "severity", "author", "span", "message", "notes", "suggestions"})
_PLACE_FIELDS = frozenset({"file", "line", "column", "length"})


def _is_place(value: object) -> bool:
    return value is None or (
        isinstance(value, dict)
        and set(value) == _PLACE_FIELDS
        and isinstance(value["file"], str)
        and all(type(value[f]) is int for f in ("line", "column", "length"))
    )


def _is_record(value: object) -> bool:
    if not (isinstance(value, dict) and set(value) == _RECORD_FIELDS):
        return False
    notes, suggestions = value["notes"], value["suggestions"]
    return (
        all(isinstance(value[f], str) for f in ("code", "severity", "author", "message"))
        and _is_place(value["span"])
        and isinstance(notes, list)
        and all(
            isinstance(nt, dict) and set(nt) == {"span", "message"} and _is_place(nt["span"])
            for nt in notes
        )
        and isinstance(suggestions, list)
        and all(isinstance(sg, dict) and set(sg) == {"text", "applicability"} for sg in suggestions)
    )


def read_envelope(document: object) -> Kind:
    """What `document` holds, refusing a document that is no Record Envelope
    of this schema, or whose payload is not its kind's."""
    if not isinstance(document, dict):
        raise UnreadableEnvelope("a Record Envelope is a JSON object")
    schema = document.get("schema")
    if type(schema) is not int or schema != SCHEMA:
        raise UnreadableEnvelope(f"schema {schema!r} is not {SCHEMA}, the one this reader reads")
    kind = next((k for k in Kind if document.get("kind") == k.value), None)
    if kind is None:
        raise UnreadableEnvelope(f"kind {document.get('kind')!r} is no kind of Record Envelope")
    records = document.get("diagnostics")
    if not (isinstance(records, list) and all(_is_record(r) for r in records)):
        raise UnreadableEnvelope(f"a {kind.value} envelope holds a list of Diagnostic Records")
    match kind:
        case Kind.DIAGNOSTICS:
            if set(document) != {"schema", "kind", "diagnostics"}:
                raise UnreadableEnvelope("a diagnostics envelope holds a list of Diagnostic Records")
        case Kind.QUERY:
            if set(document) != {"schema", "kind", "at", "diagnostics", "answer"} or not (
                _is_query_place(document["at"]) and _is_query_answer(document["answer"])
            ):
                raise UnreadableEnvelope(
                    "a query envelope holds where it was asked, its refusals, and its answer"
                )
        case _:
            assert_never(kind)
    return kind


# The fields of a Checker Query's answer, and of each of its three answers
# where it is given rather than refused.
_ANSWER_FIELDS = frozenset({"part", "scope", "type", "seats"})
_ANSWERED_FIELDS: dict[str, frozenset[str]] = {
    "scope": frozenset({"span", "names", "at-a-name"}),
    "type": frozenset({"span", "text", "types", "open"}),
    "seats": frozenset(
        {"form", "span", "site", "construct", "decider", "pick", "source", "destination",
         "observers", "every-seat"}
    ),
}


def _is_query_place(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"file", "line", "column"}
        and isinstance(value["file"], str)
        and all(type(value[f]) is int for f in ("line", "column"))
    )


def _is_query_answer(value: object) -> bool:
    if value is None:
        return True
    if not (isinstance(value, dict) and set(value) == _ANSWER_FIELDS):
        return False
    part = value["part"]
    if not (isinstance(part, dict) and set(part) == {"what", "span", "text"} and _is_place(part["span"])):
        return False
    for name, fields in _ANSWERED_FIELDS.items():
        answer = value[name]
        if isinstance(answer, dict) and set(answer) == {"refused"}:
            if not _is_record(answer["refused"]):
                return False
        elif not (isinstance(answer, dict) and set(answer) == fields and _is_place(answer["span"])):
            return False
    return True


#: Every refusal the command line renders from a playout or a load: the
#: runtime's typed failure channel (`cardlang.runtime.errors`) and the game's
#: own `error(...)`, as a type and as the classes a caller catches.
RuntimeRefusal = GameDescriptionError | IllegalMove | InstallationError | GameRegistrationError
RUNTIME_REFUSALS: tuple[type[Exception], ...] = (
    GameDescriptionError,
    IllegalMove,
    InstallationError,
    GameRegistrationError,
)


def refusal_diagnostic(exc: RuntimeRefusal) -> Told:
    """A runtime refusal as a told diagnostic: its sentence, the span it was
    stamped with, the code of its type, and the author its type names."""
    code: Code
    author: Author
    span: Span | None = None
    match exc:
        case ShadowGuardError():
            code, author, span = Code.ENGINE_GAP, Author.ENGINE, exc.span
        case GameDescriptionError():
            code, author, span = Code.REFUSED_DURING_PLAY, Author.GAME, exc.span
        case IllegalMove():
            code, author, span = Code.GAME_ERROR_RAISED, Author.GAME, exc.span
        case InstallationError():
            code, author = Code.INCOMPLETE_INSTALLATION, Author.INSTALLATION
        case GameRegistrationError():
            code, author = Code.UNREGISTRABLE_GAME, Author.REGISTRATION
        case _:
            assert_never(exc)
    return Told(Diagnostic(Severity.ERROR, str(exc), span, code=code), author)
