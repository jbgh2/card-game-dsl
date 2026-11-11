"""Span-precise source locations and diagnostics.

Every compile stage of the [[pipeline]] reports problems as :class:`Diagnostic`
values carrying a :class:`Span` back into the original DSL source — this is the
compile half of the [[failure-channel]], the runtime half being
`runtime/errors.py`. The quality of these messages is the tool's value
(docs/building.md, "CI gates"), so the span is threaded through from the very
first stage rather than bolted on later.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a check refusing a designer-written spelling because the set it
              looked the spelling up in lacks it holds that set at the
              refusal.
Establishes:  `resemblance` is the one measure of how alike two spellings
              are, and `near_misses` the one ranking of a set's [[near-miss]]es
              by it; `DiagnosticBag.unknown` is the one way a check refuses
              a spelling absent from a set it holds, and the refusal carries
              that set's Near Misses as data (`Diagnostic.near_misses`), as a
              parse refusal of a misspelled keyword carries the keywords the
              grammar accepts in its place (`cardlang.parse`);
              `Diagnostic.format` is the one place the `did you mean` clause
              is worded.
Now illegal:  a check composing an unknown-name refusal with
              `DiagnosticBag.error` (tests/test_near_misses.py census), a
              second resemblance measure, and a Near Miss applied to a
              designer's text for them: it can name the wrong declared
              thing, so it is only ever offered.
Held by:      Derived and Pinned -- a refusal's sentence is a `str`, which no
              union tells apart, so the census holds the routing.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
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
    fix: Said | None = None


_UNSPELLED = (
    "a Library Citation is never spelled into a str; compose the sentence with `+` "
    "or `Sentence.join` and hand it to the bag"
)


@dataclass(frozen=True, slots=True)
class LibraryCitation:
    """Library text a sentence names: the designer words naming it, and the
    span of that text, None where no library text stands behind the name.
    Made only by `cardlang.attribution`; the bag renders the words and hands
    the span to the step as library text the refusal stands on."""

    words: str
    span: Span | None

    def __str__(self) -> str:
        raise TypeError(_UNSPELLED)

    def __format__(self, spec: str) -> str:
        raise TypeError(_UNSPELLED)

    def __add__(self, other: Said) -> Sentence:
        return Sentence((self,)) + other

    def __radd__(self, other: str) -> Sentence:
        return Sentence((other, self))


@dataclass(frozen=True, slots=True)
class Sentence:
    """A sentence naming library text: plain text and Library Citations, in
    order."""

    parts: tuple[str | LibraryCitation, ...]

    def __str__(self) -> str:
        raise TypeError(_UNSPELLED)

    def __format__(self, spec: str) -> str:
        raise TypeError(_UNSPELLED)

    def __add__(self, other: Said) -> Sentence:
        tail = other.parts if isinstance(other, Sentence) else (other,)
        return Sentence(self.parts + tail)

    def __radd__(self, other: str) -> Sentence:
        return Sentence((other, *self.parts))

    @staticmethod
    def join(separator: str, items: Iterable[Said]) -> Said:
        """`separator.join(items)`, for items that may name library text."""
        out: Said = ""
        for at, item in enumerate(items):
            out = item if at == 0 else out + separator + item
        return out


# What a sentence may be: plain text, or text naming library text.
Said = str | LibraryCitation | Sentence


#: The fewest Near Misses a refusal is worth reading past, and the least
#: resemblance a declared name needs to be one. The cutoff is difflib's own
#: `get_close_matches` default: a one-letter slip, a transposition or a
#: dropped letter in a name of four letters or more clears it, and a name
#: sharing no run of letters with the spelling does not.
NEAR_MISS_LIMIT = 3
NEAR_MISS_CUTOFF = 0.6


def resemblance(typed: str, declared: str) -> float:
    """How alike two spellings are, from 0 to 1, ignoring case."""
    return SequenceMatcher(None, typed.casefold(), declared.casefold()).ratio()


def near_misses(spelled: str, among: Iterable[str]) -> tuple[str, ...]:
    """The declared names in `among` that `spelled` nearly spells: at most
    `NEAR_MISS_LIMIT`, most alike first and alphabetical among equals, each
    at least `NEAR_MISS_CUTOFF` alike, and never `spelled` itself."""
    scored = sorted(
        (-resemblance(spelled, name), name) for name in set(among) if name != spelled
    )
    return tuple(name for score, name in scored if -score >= NEAR_MISS_CUTOFF)[:NEAR_MISS_LIMIT]


def listed(words: Sequence[str], conjunction: str = "or") -> str:
    """`words` as a sentence lists them: `a`, `a or b`, `a, b or c`."""
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + f" {conjunction} " + words[-1]


def _or_list(names: tuple[str, ...]) -> str:
    return listed([f"`{name}`" for name in names])


def rendered(message: Said) -> tuple[str, tuple[Span, ...]]:
    """`message`'s words, and the span of each library text it names."""
    if isinstance(message, str):
        return message, ()
    parts = message.parts if isinstance(message, Sentence) else (message,)
    words = "".join(p if isinstance(p, str) else p.words for p in parts)
    spans = tuple(p.span for p in parts if isinstance(p, LibraryCitation) and p.span is not None)
    return words, spans


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
    reached through. No diagnostic leaves a pass carrying any of them.

    `near_misses` are the declared names a refused spelling nearly spells
    (`near_misses`), offered by `format` and carried through every retelling;
    never mechanically applicable."""

    severity: Severity
    message: str
    span: Span | None = None
    route: Route | None = None
    for_game: str | None = None
    notes: tuple[Note, ...] = ()
    stands_on: tuple[Span, ...] = ()
    near_misses: tuple[str, ...] = ()

    def format(self) -> str:
        message = self.message
        if self.near_misses:
            message += f"; did you mean {_or_list(self.near_misses)}?"
        lines = [_located(self.span, self.severity.value, message)]
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
        message: Said,
        span: Span | None = None,
        *,
        route: Route | None = None,
        for_game: Said | None = None,
        stands_on: Span | tuple[Span, ...] | None = None,
    ) -> None:
        """`stands_on` is library text the refusal reached that its sentences
        do not name; the library text they name, in `message` and in
        `for_game`, stands on their citations."""
        on = (stands_on,) if isinstance(stands_on, Span) else stands_on or ()
        words, cited = rendered(message)
        game_words: str | None = None
        if for_game is not None:
            game_words, game_cited = rendered(for_game)
            cited += game_cited
        self.items.append(
            Diagnostic(Severity.ERROR, words, span, route, game_words, stands_on=on + cited)
        )

    def unknown(
        self,
        message: Said,
        spelled: str,
        among: Iterable[str],
        span: Span | None = None,
        *,
        route: Route | None = None,
        for_game: Said | None = None,
        stands_on: Span | tuple[Span, ...] | None = None,
        written: Callable[[str], str] | None = None,
    ) -> None:
        """Refuse `spelled`, absent from `among`, the set it was looked up in:
        `error`, with the set's Near Misses carried as data, each as `written`
        spells it where the refusal stands (a numeric rank in a string
        position is written quoted)."""
        self.error(message, span, route=route, for_game=for_game, stands_on=stands_on)
        near = near_misses(spelled, among)
        if written is not None:
            near = tuple(written(name) for name in near)
        self.items[-1] = replace(self.items[-1], near_misses=near)

    def warning(self, message: str, span: Span | None = None) -> None:
        self.items.append(Diagnostic(Severity.WARNING, message, span))

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.items)

    def format(self) -> str:
        return "\n".join(d.format() for d in self.items)
