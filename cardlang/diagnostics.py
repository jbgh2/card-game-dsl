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
              is worded. A refusal of a bare name carries the whole ranking
              too (`Diagnostic.ranked_near_misses`, `unknown(in_place=True)`),
              the data `cardlang.pipeline._judged` narrows `near_misses` by:
              it writes each Near Miss into a copy of the designer's text and
              checks that copy, which is never told and never kept. Every diagnostic carries its Diagnostic Code
              (`cardlang.diagnostic_codes.Code`), which `format` never shows;
              a `DiagnosticError` carries every diagnostic it tells as a
              Told Diagnostic (`Told`), each with its Author, and renders the
              text a designer reads from them.
              `DiagnosticBag.settle` is the one decision of which refusals a
              refused spelling's consequences leave untold: a refusal that
              marks what clears it (`Unless`) is withheld when one assignment
              of fixes, a member of each cause's set (`Refused`), clears every
              marked refusal those causes reach, and told otherwise; a refusal
              no member of a cause's set clears is told, and so is every cause
              no other cause clears. `cardlang.attribution` settles a bag
              before it tells it, so no told diagnostic carries a mark.
Now illegal:  a check composing an unknown-name refusal with
              `DiagnosticBag.error` (tests/test_near_misses.py census), a
              second resemblance measure, and a Near Miss applied to a
              designer's text for them: it can name the wrong declared
              thing, so it is only ever offered; a diagnostic made without a
              code, and a `DiagnosticError` raised without an author; a check
              withholding a refusal of its own because another refusal
              exists, rather than marking what clears it.
Held by:      Derived and Pinned for the routing -- a refusal's sentence is a
              `str`, which no union tells apart, so the census holds it;
              Unrepresentable for the code and the author, required fields.
              The settling has one owner (`settle`); which fixes clear a
              marked refusal is a fact of the marking check's body, held by
              its member's row, which executes the fix
              (tests/test_refusal_consequences.py).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from enum import Enum

from cardlang.diagnostic_codes import Code


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


class Author(Enum):
    """Whose artifact must change for a refusal to clear: the [[author]] a
    told diagnostic addresses."""

    GAME = "game"
    LIBRARY = "library"
    ENGINE = "engine"
    INSTALLATION = "installation"
    REGISTRATION = "registration"
    INVOCATION = "invocation"


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


def near_misses(
    spelled: str, among: Iterable[str], limit: int | None = NEAR_MISS_LIMIT
) -> tuple[str, ...]:
    """The declared names in `among` that `spelled` nearly spells: at most
    `limit`, most alike first and alphabetical among equals, each at least
    `NEAR_MISS_CUTOFF` alike, and never `spelled` itself."""
    scored = sorted(
        (-resemblance(spelled, name), name) for name in set(among) if name != spelled
    )
    return tuple(name for score, name in scored if -score >= NEAR_MISS_CUTOFF)[:limit]


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


class SlotKind(Enum):
    """What a refused spelling stands in: the kind of declaration or
    reference its fix names."""

    DECK = "deck"
    CONTENT_KIND = "content kind"
    BOARD = "board"
    ZONE_INDEX = "zone index"
    PROCEDURE = "procedure"
    MOVE_TYPE = "move type"
    RULE = "rule"
    FUNCTION = "function"
    MODE = "mode"
    SIMULTANEOUS_ROLE = "simultaneous role"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class Slot:
    """One place a refused spelling stands: its kind, and which one of that
    kind (a zone's name, a phase's, or the spelling's own text)."""

    kind: SlotKind
    name: str


@dataclass(frozen=True, slots=True)
class Refused:
    """A cause: the slot a refused spelling stands in, and the set it was
    looked up in, any member of which is a fix."""

    slot: Slot
    fixes: frozenset[str]


@dataclass(frozen=True, slots=True)
class Unless:
    """What clears a consequence: a fix in `clears` of a refused spelling of
    `kind`, in a slot `names` holds, or in any slot of the kind when `names`
    is None."""

    kind: SlotKind
    clears: frozenset[str]
    names: frozenset[str] | None = None

    def reaches(self, cause: Refused) -> bool:
        return (
            cause.slot.kind is self.kind
            and (self.names is None or cause.slot.name in self.names)
            and not self.clears.isdisjoint(cause.fixes)
        )


def text_slot(span: Span) -> Slot:
    """The slot of a bare spelling: its own text."""
    return Slot(SlotKind.TEXT, f"{span.source_name}:{span.start}:{span.end}")


#: The most assignments `DiagnosticBag.settle` tries for one group of
#: causes; past it the group's consequences are told.
SETTLE_LIMIT = 100_000


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
    never mechanically applicable. `ranked_near_misses` is every Near Miss of
    a refused bare name, ranked, where each is a name written in place of
    that name at `span`: what `cardlang.pipeline` re-checks to narrow
    `near_misses`. A retelling moves the span and drops it.

    `code` is the kind of fix the refusal asks for (`Code`), required where
    the diagnostic is made and kept by every retelling; `format` never
    shows it.

    `refuses` marks a cause, the refused spelling's slot and its fixes, and
    `unless` a consequence, what clears it: read only by
    `DiagnosticBag.settle`, which leaves no told diagnostic carrying either."""

    severity: Severity
    message: str
    span: Span | None = None
    route: Route | None = None
    for_game: str | None = None
    notes: tuple[Note, ...] = ()
    stands_on: tuple[Span, ...] = ()
    near_misses: tuple[str, ...] = ()
    ranked_near_misses: tuple[str, ...] = ()
    refuses: Refused | None = None
    unless: tuple[Unless, ...] = ()
    code: Code = field(kw_only=True)

    def format(self) -> str:
        message = self.message
        if self.near_misses:
            message += f"; did you mean {_or_list(self.near_misses)}?"
        lines = [_located(self.span, self.severity.value, message)]
        lines.extend(_located(note.span, NOTE, note.message) for note in self.notes)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Told:
    """A diagnostic as told: in the file the attribution step decided, to
    the author who must act on it. Made only where a refusal is told --
    `cardlang.attribution`, the parser's and the extract step's own raises,
    the command line, and `cardlang.records.refusal_diagnostic`."""

    diagnostic: Diagnostic
    author: Author


class DiagnosticError(Exception):
    """Raised when a stage cannot continue past a diagnostic.

    Carries every told diagnostic as data (`told`), the first also as
    `diagnostic`, so the CLI and harness can render them consistently rather
    than parsing exception strings. Where it tells more than one, the rendering
    of them all is attached as a note, the text a designer reads.
    """

    def __init__(self, first: Told, *rest: Told) -> None:
        super().__init__(first.diagnostic.format())
        self.diagnostic = first.diagnostic
        self.told: tuple[Told, ...] = (first, *rest)
        if rest:
            self.add_note("\n".join(t.diagnostic.format() for t in self.told))

    def __reduce__(self) -> tuple[object, ...]:
        # Rebuilt from its told diagnostics, every note it carries kept.
        return (_told_again, self.told, self.__dict__)


def _told_again(first: Told, *rest: Told) -> DiagnosticError:
    """A `DiagnosticError` unpickled: made again from what it told."""
    error = DiagnosticError(first, *rest)
    error.__dict__.pop("__notes__", None)
    return error


@dataclass(slots=True)
class DiagnosticBag:
    """Accumulates diagnostics across a stage so several problems surface at once."""

    items: list[Diagnostic] = field(default_factory=list)

    def error(
        self,
        message: Said,
        span: Span | None = None,
        *,
        code: Code,
        route: Route | None = None,
        for_game: Said | None = None,
        stands_on: Span | tuple[Span, ...] | None = None,
        refuses: Refused | None = None,
        unless: Unless | tuple[Unless, ...] = (),
    ) -> None:
        """`code` is the kind of fix the refusal asks for. `stands_on` is
        library text the refusal reached that its sentences do not name; the library text they name, in `message` and in
        `for_game`, stands on their citations. `refuses` marks the refusal a
        cause, `unless` a consequence (`settle`)."""
        on = (stands_on,) if isinstance(stands_on, Span) else stands_on or ()
        words, cited = rendered(message)
        game_words: str | None = None
        if for_game is not None:
            game_words, game_cited = rendered(for_game)
            cited += game_cited
        self.items.append(
            Diagnostic(
                Severity.ERROR,
                words,
                span,
                route,
                game_words,
                stands_on=on + cited,
                refuses=refuses,
                unless=(unless,) if isinstance(unless, Unless) else unless,
                code=code,
            )
        )

    def unknown(
        self,
        message: Said,
        spelled: str,
        among: Iterable[str],
        span: Span | None = None,
        *,
        code: Code,
        route: Route | None = None,
        for_game: Said | None = None,
        stands_on: Span | tuple[Span, ...] | None = None,
        written: Callable[[str], str] | None = None,
        in_place: bool = False,
        slot: Slot | None = None,
        unless: Unless | tuple[Unless, ...] = (),
    ) -> None:
        """Refuse `spelled`, absent from `among`, the set it was looked up in:
        `error`, with the set's Near Misses carried as data, each as `written`
        spells it where the refusal stands (a numeric rank in a string
        position is written quoted). `in_place` says `spelled` is a bare name
        at `span`, each Near Miss a name written in its place, and carries
        the whole ranking (`Diagnostic.ranked_near_misses`). `slot` is where
        `spelled` stands, and marks the refusal a cause whose fixes are
        `among`; `unless` is as for `error`."""
        fixes = frozenset(among)
        self.error(
            message,
            span,
            code=code,
            route=route,
            for_game=for_game,
            stands_on=stands_on,
            refuses=None if slot is None else Refused(slot, fixes),
            unless=unless,
        )
        ranked = near_misses(spelled, fixes, limit=None)
        near = ranked[:NEAR_MISS_LIMIT]
        if written is not None:
            near = tuple(written(name) for name in near)
        self.items[-1] = replace(
            self.items[-1], near_misses=near, ranked_near_misses=ranked if in_place else ()
        )

    def settle(self) -> None:
        """Withhold the refusals a refused spelling's fix would clear, and
        strip every mark. A cause marking no consequence is told, and so is
        a cause that no such cause reaches. The rest are grouped by the
        causes that reach them; a group is withheld when one fix of each
        cause clears all of it (`_assignable`), and told otherwise."""
        items = self.items
        if not any(d.unless for d in items):
            if any(d.refuses is not None for d in items):
                items[:] = [replace(d, refuses=None) for d in items]
            return
        roots = [i for i, d in enumerate(items) if d.refuses is not None and not d.unless]
        marked = [c for c, d in enumerate(items) if d.unless]
        # A cause that is itself a consequence is cleared only by a root, and
        # one no root reaches is told; every other consequence is cleared by
        # a cause that is told.
        doubles = {c for c in marked if items[c].refuses is not None and _reaching(items, c, roots)}
        causes = roots + [c for c in marked if items[c].refuses is not None and c not in doubles]
        clearers = {
            c: _reaching(items, c, roots if c in doubles else causes)
            for c in marked
            if items[c].refuses is None or c in doubles
        }
        group_of: dict[int, int] = {}
        groups: dict[int, tuple[set[int], set[int]]] = {}
        for c, by in clearers.items():
            if not by:
                continue
            consequences, reaching = {c}, set(by)
            for g in {group_of[i] for i in by if i in group_of}:
                more, also = groups.pop(g)
                consequences |= more
                reaching |= also
            for i in reaching:
                group_of[i] = c
            groups[c] = (consequences, reaching)
        withheld: set[int] = set()
        for consequences, reaching in groups.values():
            if _assignable(items, sorted(consequences), sorted(reaching), clearers):
                withheld |= consequences
        items[:] = [
            replace(d, refuses=None, unless=()) for i, d in enumerate(items) if i not in withheld
        ]

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.items)

    def format(self) -> str:
        return "\n".join(d.format() for d in self.items)


def _reaching(items: list[Diagnostic], c: int, causes: Iterable[int]) -> list[int]:
    """The causes among `causes`, other than `c`, that a fix of could clear
    the consequence `items[c]`."""
    found: list[int] = []
    for i in causes:
        refused = items[i].refuses
        if i != c and refused is not None and any(u.reaches(refused) for u in items[c].unless):
            found.append(i)
    return found


def _assignable(
    items: list[Diagnostic], consequences: list[int], causes: list[int], clearers: dict[int, list[int]]
) -> bool:
    """Whether one fix of each cause, a member of its set or none, clears
    every consequence: some `Unless` of each reaching a cause whose fix is in
    its `clears`. Searched depth first, giving up past `SETTLE_LIMIT` tries."""

    def refused(i: int) -> Refused:
        cause = items[i].refuses
        assert cause is not None
        return cause

    domains: dict[int, list[str | None]] = {}
    for i in causes:
        values = {
            value
            for c in consequences
            if i in clearers[c]
            for u in items[c].unless
            if u.reaches(refused(i))
            for value in u.clears & refused(i).fixes
        }
        domains[i] = [*sorted(values), None]
    tries = 0

    def cleared(c: int, chosen: dict[int, str | None]) -> bool | None:
        """True when the fixes chosen clear `c`, False when no fix left to
        choose can, None while one still might."""
        open_cause = False
        for i in clearers[c]:
            if i not in chosen:
                open_cause = True
                continue
            value = chosen[i]
            if value is not None and any(u.reaches(refused(i)) and value in u.clears for u in items[c].unless):
                return True
        return None if open_cause else False

    def search(at: int, chosen: dict[int, str | None]) -> bool:
        nonlocal tries
        tries += 1
        if tries > SETTLE_LIMIT or any(cleared(c, chosen) is False for c in consequences):
            return False
        if at == len(causes):
            return True
        for value in domains[causes[at]]:
            chosen[causes[at]] = value
            if search(at + 1, chosen):
                return True
            del chosen[causes[at]]
        return False

    return search(0, {})
