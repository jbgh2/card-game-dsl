"""The Record Envelope says what the text output says, as data.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every rejection case's Record Envelope, read back through
                 the text renderer, prints its golden byte for byte; every
                 record carries a code, an author and `offered`
                 suggestions; a document of another schema or kind is
                 refused; every runtime refusal type becomes a told
                 diagnostic with the code and author its type names.
domain:          the rejection corpus, every case; the runtime refusal
                 types, derived as every exception class
                 `cardlang.runtime.errors` defines plus `IllegalMove`; a
                 Markdown game file's place, the one source whose offsets
                 count from somewhere other than its file.
registry:        the corpus -- tests/test_rejections.py::case_paths; the
                 refusal types -- `cardlang.records.RuntimeRefusal`; the
                 authors -- `cardlang.diagnostics.Author`.
held by:         Unrepresentable for the refusal types, whose match ends in
                 `assert_never`; Derived and Pinned for the round trip.
does not prove:  that a record's code is the right kind of fix for its
                 sentence; tests/test_diagnostic_codes.py holds a witness
                 per code, and the registry's naming review judges the rest.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import cardlang.runtime.errors as errors
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Author, Diagnostic, DiagnosticError, Note, Severity, Span
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl, check_markdown
from cardlang.records import (
    SCHEMA,
    Kind,
    RuntimeRefusal,
    UnreadableEnvelope,
    envelope,
    read_envelope,
    refusal_diagnostic,
)
from cardlang.runtime.state import IllegalMove
from tests.test_rejections import REJECTIONS_DIR, case_paths
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


def test_a_reader_refuses_what_it_cannot_read() -> None:
    assert read_envelope({"schema": SCHEMA, "kind": "diagnostics"}) is Kind.DIAGNOSTICS
    refused: tuple[object, ...] = (
        {"schema": SCHEMA + 1, "kind": "diagnostics"},
        {"kind": "diagnostics"},
        {"schema": SCHEMA, "kind": "game"},
        [],
    )
    for document in refused:
        with pytest.raises(UnreadableEnvelope):
            read_envelope(document)


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
    """Every exception class the runtime's failure channel defines, and the
    game's own `error(...)`."""
    defined = [
        cls for _, cls in inspect.getmembers(errors, inspect.isclass)
        if issubclass(cls, BaseException) and cls.__module__ == errors.__name__
    ]
    return sorted([*defined, IllegalMove], key=lambda c: c.__name__)


# The code and author each refusal type is told with: authored, never read
# off `refusal_diagnostic`.
EXPECTED: dict[str, tuple[Code, Author]] = {
    "GameDescriptionError": (Code.REFUSED_DURING_PLAY, Author.GAME),
    "OwnerGuardError": (Code.REFUSED_DURING_PLAY, Author.GAME),
    "ShadowGuardError": (Code.ENGINE_GAP, Author.ENGINE),
    "IllegalMove": (Code.GAME_ERROR_RAISED, Author.GAME),
    "InstallationError": (Code.INCOMPLETE_INSTALLATION, Author.INSTALLATION),
    "GameRegistrationError": (Code.UNREGISTRABLE_GAME, Author.REGISTRATION),
}


def _refusal(cls: type[BaseException]) -> RuntimeRefusal:
    exc = cls("the leaked guard", "a sentence") if cls is errors.ShadowGuardError else cls("a sentence")
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
    """red under: a new exception class defined in `cardlang/runtime/errors.py`."""
    assert sorted(EXPECTED) == [c.__name__ for c in _refusal_types()]


def test_a_retold_refusal_keeps_its_code() -> None:
    """A refusal raised in library text and told in the game's file keeps the
    code it was raised with. red under: `_retold` building with a fixed code."""
    from cardlang import attribution

    d = Diagnostic(Severity.ERROR, "x", None, code=Code.UNKNOWN_ZONE)
    assert attribution._retold(d, "y", None).code is Code.UNKNOWN_ZONE
