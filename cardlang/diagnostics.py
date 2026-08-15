"""Span-precise source locations and diagnostics.

Every compile stage of the [[pipeline]] reports problems as :class:`Diagnostic`
values carrying a :class:`Span` back into the original DSL source — this is the
compile half of the [[failure-channel]], the runtime half being
`runtime/errors.py`. The quality of these messages is the tool's value
(docs/building.md, "CI gates"), so the span is threaded through from the very
first stage rather than bolted on later.
"""

from __future__ import annotations

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
class Diagnostic:
    """A single problem found by any stage, located in the source."""

    severity: Severity
    message: str
    span: Span | None = None

    def format(self) -> str:
        where = ""
        if self.span is not None:
            where = f"{self.span.source_name}:{self.span.line}:{self.span.column}: "
        return f"{where}{self.severity.value}: {self.message}"


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

    def error(self, message: str, span: Span | None = None) -> None:
        self.items.append(Diagnostic(Severity.ERROR, message, span))

    def warning(self, message: str, span: Span | None = None) -> None:
        self.items.append(Diagnostic(Severity.WARNING, message, span))

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.items)

    def format(self) -> str:
        return "\n".join(d.format() for d in self.items)
