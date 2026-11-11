"""The Record Envelope: the checker's and the runtime's refusals as data.

A tool reading `cardlang check --json` reads one [[record-envelope]]: a JSON
document carrying its format's version (`schema`), what it holds (`kind`),
and, for a check, one Diagnostic Record per told diagnostic. A record holds
what the text output shows a designer, as fields: the [[diagnostic-code]],
the severity, the author who must act, the span, the message, the notes, and
the Near Misses as suggestions marked `offered`. The words are the
diagnostic's own; this module composes none and decides no author.

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
              renders; `read_envelope` refuses a schema or kind it does not
              know rather than reading it best-effort.
Now illegal:  a second JSON spelling of a diagnostic or a place; a record
              whose words differ from the text a designer reads
              (tests/test_records.py, the round trip over the rejection
              corpus); a suggestion marked mechanically applicable.
Held by:      Unrepresentable for the refusal types (the match ends in
              `assert_never`); Derived and Pinned for the record's agreement
              with the text, which the round trip runs.
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
    OwnerGuardError,
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


def read_envelope(document: object) -> Kind:
    """What `document` holds, refusing a document that is no Record Envelope
    of this schema."""
    if not isinstance(document, dict):
        raise UnreadableEnvelope("a Record Envelope is a JSON object")
    schema = document.get("schema")
    if schema != SCHEMA:
        raise UnreadableEnvelope(f"schema {schema!r} is not {SCHEMA}, the one this reader reads")
    kind = document.get("kind")
    for known in Kind:
        if kind == known.value:
            return known
    raise UnreadableEnvelope(f"kind {kind!r} is no kind of Record Envelope")


#: Every refusal the command line renders from a playout or a load: the
#: runtime's typed failure channel (`cardlang.runtime.errors`) and the game's
#: own `error(...)`.
RuntimeRefusal = GameDescriptionError | IllegalMove | InstallationError | GameRegistrationError


def refusal_diagnostic(exc: RuntimeRefusal) -> Told:
    """A runtime refusal as a told diagnostic: its sentence, the span it was
    stamped with, the code of its type, and the author its type names."""
    code: Code
    author: Author
    span: Span | None = None
    match exc:
        case ShadowGuardError():
            code, author, span = Code.ENGINE_GAP, Author.ENGINE, exc.span
        case OwnerGuardError():
            code, author, span = Code.REFUSED_DURING_PLAY, Author.GAME, exc.span
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
