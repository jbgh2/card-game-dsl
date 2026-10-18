"""Span-precise source locations and diagnostics.

Every compile stage of the [[pipeline]] reports problems as :class:`Diagnostic`
values carrying a :class:`Span` back into the original DSL source — this is the
compile half of the [[failure-channel]], the runtime half being
`runtime/errors.py`. The quality of these messages is the tool's value
(docs/building.md, "CI gates"), so the span is threaded through from the very
first stage rather than bolted on later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True, slots=True)
class Span:
    """A half-open range into a single DSL source string.

    ``line`` and ``column`` are 1-based and point at the start, matching the
    convention Lark uses, so positions can be lifted straight from parse
    tokens. ``source_name`` identifies the origin (e.g. a game file path) for
    multi-file harness runs.
    """

    source_name: str
    start: int
    end: int
    line: int
    column: int

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"span end {self.end} precedes start {self.start}")


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Route:
    """The crossing by which a check left a game's text for a family
    library's: its kind (`attribution.CROSSING_KINDS`), the game text the walk
    left by (`at`), the library definition it entered, and the fix the walk
    computed for the game's author where the kind's sentence takes one."""

    kind: str
    at: Span | None
    library: str
    name: str
    fix: str | None = None


@dataclass(frozen=True, slots=True)
class Note:
    """A second location a diagnostic is told with: the library line a
    refusal told in the game's file stands on. Made only by
    `cardlang.attribution`."""

    span: Span
    message: str


# The kind every rendered line leads with: a diagnostic's severity, or a note
# under it.
NOTE = "note"
LINE_KINDS: tuple[str, ...] = (*(s.value for s in Severity), NOTE)


def _located(span: Span | None, kind: str, message: str) -> str:
    where = "" if span is None else f"{span.source_name}:{span.line}:{span.column}: "
    return f"{where}{kind}: {message}"


_LINE = re.compile(rf"^(?:.+?:\d+:\d+: )?({'|'.join(LINE_KINDS)}): ")


def line_kind(line: str) -> str | None:
    """The kind a rendered line leads with (`LINE_KINDS`), None for a line no
    diagnostic renders."""
    found = _LINE.match(line)
    return None if found is None else found.group(1)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A single problem found by any stage, located in the source, with the
    notes it is told with.

    `route`, `for_game` and `stands_on` are read only by
    `cardlang.attribution`, which decides which file a refusal of
    family-library text is told in: the crossing a walk followed into that
    text, the sentence the game's author reads when the refusal is told to
    them, and the library text a refusal standing at the game's text was
    reached through. No diagnostic leaves a pass carrying any of them."""

    severity: Severity
    message: str
    span: Span | None = None
    route: Route | None = None
    for_game: str | None = None
    notes: tuple[Note, ...] = ()
    stands_on: tuple[Span, ...] = ()

    def format(self) -> str:
        lines = [_located(self.span, self.severity.value, self.message)]
        lines.extend(_located(note.span, NOTE, note.message) for note in self.notes)
        return "\n".join(lines)


class DiagnosticError(Exception):
    """Raised when a stage cannot continue past a diagnostic.

    Carries the structured :class:`Diagnostic` so the CLI and harness can
    render it consistently rather than parsing exception strings.
    """

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.format())
        self.diagnostic = diagnostic


@dataclass(slots=True)
class DiagnosticBag:
    """Accumulates diagnostics across a stage so several problems surface at once."""

    items: list[Diagnostic] = field(default_factory=list)

    def error(
        self,
        message: str,
        span: Span | None = None,
        *,
        route: Route | None = None,
        for_game: str | None = None,
        stands_on: Span | tuple[Span, ...] | None = None,
    ) -> None:
        on = (stands_on,) if isinstance(stands_on, Span) else stands_on or ()
        self.items.append(Diagnostic(Severity.ERROR, message, span, route, for_game, stands_on=on))

    def warning(self, message: str, span: Span | None = None) -> None:
        self.items.append(Diagnostic(Severity.WARNING, message, span))

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.items)

    def format(self) -> str:
        return "\n".join(d.format() for d in self.items)
