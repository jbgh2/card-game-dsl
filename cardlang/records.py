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
(issue #1103).

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      every diagnostic it is handed is told (`Told`): its file
              decided by `cardlang.attribution` or by the raise that made
              it, and its author stamped there.
Establishes:  `envelope` is the one producer of a Record Envelope and
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

from collections.abc import Sequence
from enum import Enum
from typing import assert_never

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
    if set(document) != {"schema", "kind", "diagnostics"} or not (
        isinstance(records, list) and all(_is_record(r) for r in records)
    ):
        raise UnreadableEnvelope("a diagnostics envelope holds a list of Diagnostic Records")
    return kind


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
