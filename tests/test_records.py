"""The Record Envelope says what the text output says, as data.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every rejection case's Record Envelope, read back through
                 the text renderer, prints its golden byte for byte; every
                 record carries a code, an author and `offered`
                 suggestions; a document of another schema, a schema that is
                 no integer, another kind, or a payload of another shape is
                 refused; every runtime refusal type becomes a told
                 diagnostic with the code and author its type names; a
                 refusal survives pickling with every told diagnostic and
                 note it carries.
domain:          the rejection corpus, every case; the runtime refusal
                 types, derived as every exception class defined in
                 `cardlang/` that subclasses one of
                 `cardlang.records.RUNTIME_REFUSALS`; a
                 Markdown game file's place, the one source whose offsets
                 count from somewhere other than its file.
registry:        the corpus -- tests/test_rejections.py::case_paths; the
                 refusal types -- `cardlang.records.RuntimeRefusal`; the
                 authors -- `cardlang.diagnostics.Author`.
held by:         Derived and Pinned. The match ends in `assert_never`, but
                 over `RuntimeRefusal`, a hand-written union: a refusal class
                 added anywhere in `cardlang/` type-checks unlisted, and the
                 walk of the package's classes here is what refuses it.
does not prove:  that a record's code is the right kind of fix for its
                 sentence; tests/test_diagnostic_codes.py holds a witness
                 per code, and the registry's naming review judges the rest.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import get_args

import pytest

import cardlang.runtime.errors as errors
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Author, Diagnostic, DiagnosticError, Note, Severity, Span, Told
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl, check_markdown
from cardlang.records import (
    RUNTIME_REFUSALS,
    SCHEMA,
    Kind,
    RuntimeRefusal,
    UnreadableEnvelope,
    envelope,
    read_envelope,
    refusal_diagnostic,
)
from cardlang.runtime.state import IllegalMove
from cardlang.stdlib.boards import BoardMisuse, BoardRefusal
from tests.test_rejections import REJECTIONS_DIR, case_paths
from tests.test_runtime_refusal_location import engine_exception_classes
from tools.dead_surface import start_for


def _refused(path: Path) -> DiagnosticError:
    name = path.relative_to(REJECTIONS_DIR).with_suffix("").as_posix()
    with pytest.raises(DiagnosticError) as excinfo:
        if start_for(path) == "library":
            parse_library(path.read_text(), f"{name}.cardlang")
        else:
            check_dsl(path.read_text(), f"{name}.cardlang")
    return excinfo.value


def _place(record: object) -> Span | None:
    if record is None:
        return None
    assert isinstance(record, dict)
    return Span(record["file"], 0, record["length"], record["line"], record["column"])


def _diagnostic(record: dict[str, object]) -> Diagnostic:
    """A record read back into the diagnostic the text renderer prints."""
    notes = record["notes"]
    suggestions = record["suggestions"]
    assert isinstance(notes, list) and isinstance(suggestions, list)
    return Diagnostic(
        Severity(record["severity"]),
        str(record["message"]),
        _place(record["span"]),
        notes=tuple(Note(_place(nt["span"]), nt["message"]) for nt in notes),  # type: ignore[arg-type]
        near_misses=tuple(s["text"] for s in suggestions),
        code=next(c for c in Code if c.slug == record["code"]),
    )


@pytest.mark.parametrize(
    "path", case_paths(), ids=lambda p: p.relative_to(REJECTIONS_DIR).as_posix()
)
def test_a_case_s_records_print_its_golden(path: Path) -> None:
    """The envelope, through JSON and back through `Diagnostic.format`,
    prints what `cardlang check` prints: the first diagnostic, then every
    one as a note where there are several."""
    document = json.loads(json.dumps(envelope(_refused(path).told)))
    assert read_envelope(document) is Kind.DIAGNOSTICS
    told = [_diagnostic(r) for r in document["diagnostics"]]
    lines = [told[0].format()]
    if len(told) > 1:
        lines.append("\n".join(d.format() for d in told))
    assert "\n".join(lines) + "\n" == path.with_suffix(".expected").read_text()
    for record in document["diagnostics"]:
        assert record["author"] in {a.value for a in Author}
        assert all(s["applicability"] == "offered" for s in record["suggestions"])


_RECORD: dict[str, object] = {
    "code": "unknown-name",
    "severity": "error",
    "author": "game",
    "span": {"file": "g.cardlang", "line": 1, "column": 1, "length": 1},
    "message": "unresolved name 'x'",
    "notes": [],
    "suggestions": [{"text": "y", "applicability": "offered"}],
}


def _envelope(**fields: object) -> dict[str, object]:
    return {"schema": SCHEMA, "kind": "diagnostics", "diagnostics": [_RECORD], **fields}


@pytest.mark.parametrize(
    "document",
    [
        _envelope(schema=SCHEMA + 1),
        _envelope(schema=True),
        _envelope(schema=1.0),
        _envelope(schema="1"),
        {"kind": "diagnostics", "diagnostics": []},
        _envelope(kind="game"),
        _envelope(diagnostics="garbage"),
        {"schema": SCHEMA, "kind": "diagnostics"},
        _envelope(diagnostics=[{**_RECORD, "code": 3}]),
        _envelope(diagnostics=[{k: v for k, v in _RECORD.items() if k != "author"}]),
        _envelope(diagnostics=[{**_RECORD, "span": {"file": "g", "line": "1"}}]),
        _envelope(diagnostics=[{**_RECORD, "notes": [{"message": "m"}]}]),
        _envelope(diagnostics=[{**_RECORD, "suggestions": ["y"]}]),
        _envelope(extra=1),
        [],
    ],
)
def test_a_reader_refuses_what_it_cannot_read(document: object) -> None:
    with pytest.raises(UnreadableEnvelope):
        read_envelope(document)


def test_a_reader_reads_what_a_check_prints() -> None:
    assert read_envelope(_envelope()) is Kind.DIAGNOSTICS
    assert read_envelope(_envelope(diagnostics=[])) is Kind.DIAGNOSTICS


def test_a_refusal_survives_pickling() -> None:
    """red under: `DiagnosticError.__reduce__` deleted."""
    first = Told(Diagnostic(Severity.ERROR, "one", None, code=Code.UNKNOWN_ZONE), Author.GAME)
    second = Told(
        Diagnostic(Severity.WARNING, "two", None, code=Code.FAMILY_LIBRARY_NOT_YET_PROVEN), Author.GAME
    )
    exc = DiagnosticError(first, second)
    exc.add_note("a further note")
    back = pickle.loads(pickle.dumps(exc))
    assert back.told == exc.told
    assert back.diagnostic == exc.diagnostic
    assert back.__notes__ == exc.__notes__
    assert str(back) == str(exc)


def test_the_refusals_caught_are_the_refusal_types() -> None:
    """The classes `check --json` catches are the union the match covers."""
    assert set(RUNTIME_REFUSALS) == set(get_args(RuntimeRefusal))


def test_a_markdown_game_s_place_is_its_file_s() -> None:
    """In a `.md` game a span's offsets count from the fenced block; the
    record's line is the file's line, and it carries no offset."""
    markdown = "# A game\n\nSome rules.\n\n```cardlang\ngame g {\n  players: 2\n  zzz\n}\n```\n"
    with pytest.raises(DiagnosticError) as excinfo:
        check_markdown(markdown, "g.md")
    (record,) = json.loads(json.dumps(envelope(excinfo.value.told)))["diagnostics"]
    assert record["span"]["file"] == "g.md"
    assert record["span"]["line"] == markdown.splitlines().index("  zzz") + 1
    assert set(record["span"]) == {"file", "line", "column", "length"}


def _refusal_types() -> list[type[BaseException]]:
    """Every exception class defined anywhere in `cardlang/` that the record
    layer tells: a subclass of one of `RUNTIME_REFUSALS`."""
    return sorted(
        (c for c in engine_exception_classes().values() if issubclass(c, RUNTIME_REFUSALS)),
        key=lambda c: c.__name__,
    )


# The code and author each refusal type is told with: authored, never read
# off `refusal_diagnostic`.
EXPECTED: dict[str, tuple[Code, Author]] = {
    "GameDescriptionError": (Code.REFUSED_DURING_PLAY, Author.GAME),
    "OwnerGuardError": (Code.REFUSED_DURING_PLAY, Author.GAME),
    "BoardRefusal": (Code.REFUSED_DURING_PLAY, Author.GAME),
    "ShadowGuardError": (Code.ENGINE_GAP, Author.ENGINE),
    "IllegalMove": (Code.GAME_ERROR_RAISED, Author.GAME),
    "InstallationError": (Code.INCOMPLETE_INSTALLATION, Author.INSTALLATION),
    "GameRegistrationError": (Code.UNREGISTRABLE_GAME, Author.REGISTRATION),
}


def _refusal(cls: type[BaseException]) -> RuntimeRefusal:
    exc: BaseException
    if cls is errors.ShadowGuardError:
        exc = cls("the leaked guard", "a sentence")
    elif cls is BoardRefusal:
        exc = cls(BoardMisuse.NO_LINES, "a sentence")
    else:
        exc = cls("a sentence")
    assert isinstance(exc, (errors.GameDescriptionError, IllegalMove, errors.InstallationError, errors.GameRegistrationError))
    return exc


@pytest.mark.parametrize(
    "cls",
    [
        pytest.param(
            c,
            marks=[pytest.mark.expects_shadow_guard] if c is errors.ShadowGuardError else [],
            id=c.__name__,
        )
        for c in _refusal_types()
    ],
)
def test_every_runtime_refusal_is_told_by_its_type(cls: type[BaseException]) -> None:
    exc = _refusal(cls)
    span = Span("g.cardlang", 3, 7, 2, 4)
    if isinstance(exc, errors.Located):
        exc.locate(span=span)
    told = refusal_diagnostic(exc)
    assert (told.diagnostic.code, told.author) == EXPECTED[cls.__name__]
    assert told.diagnostic.message == str(exc)
    assert told.diagnostic.span == (span if isinstance(exc, errors.Located) else None)


def test_the_expected_column_names_every_refusal_type() -> None:
    """red under: a new subclass of `OwnerGuardError` defined anywhere in
    `cardlang/`."""
    assert sorted(EXPECTED) == [c.__name__ for c in _refusal_types()]


def test_a_retold_refusal_keeps_its_code() -> None:
    """A refusal raised in library text and told in the game's file keeps the
    code it was raised with. red under: `_retold` building with a fixed code."""
    from cardlang import attribution

    d = Diagnostic(Severity.ERROR, "x", None, code=Code.UNKNOWN_ZONE)
    assert attribution._retold(d, "y", None).code is Code.UNKNOWN_ZONE
