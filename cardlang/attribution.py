"""Attribution: which file a refusal standing in family-library text is told in.

A game's text reaches a family library's text, and a check that follows it
can refuse library text for a cause the game's text supplies. Who is told is
decided here, once, for every check, where the passes raise (decisions.md
"Family libraries"): a library definition is sound when some game meets it,
so a failure only some games produce is the game's, and a fault in the
library's own text stays the library's.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      every diagnostic a pass collects carries the span of the text it
              refuses; a check that follows a crossing out of the game's text
              into library text attaches that crossing (`Route`) to every
              refusal it raises there that the crossing causes; a check that
              knows the sentence a game's author should read for a refusal of
              library text supplies it (`for_game`); a sentence names a
              library or its text only by a Library Citation made here
              (`cite_library`, `cite_definition`, `cite_origin`,
              `cite_where`), handed the span of the text it names, and the
              bag hands that span on as library text the refusal stands on;
              a check that refuses the game's text for library text it
              reached and does not name supplies that text (`stands_on`);
              every spliced definition carries its `n.LibraryOrigin`, and the
              block a library procedure's `run` becomes carries the
              procedure's (`expand`).
Establishes:  `raise_if_errors` is the only way a pass after the splice raises
              its diagnostics, `raise_where_written` the only way a library
              checked alone raises its own, and `tell` the one place a
              diagnostic's file is decided and its notes made. The words
              naming a library or its definitions in any sentence are made
              here. A refusal carrying a route is told
              at the route's game text, with its crossing kind's sentence
              (`FIX_TABLE`) or its `for_game` sentence. A refusal with no
              route, standing in a library definition some Library Witness
              reaches and checks clean with (its certificate), is told on the
              game's `uses` line, naming the definition and the Library
              Witness. Either keeps the library text it stood in as its note,
              naming the definition holding it. A refusal standing at the
              game's text with library text it names or reached keeps that
              text as its note; with none, one standing at game text naming
              a spliced library definition (resolve's naming slots) or at a
              template argument substituted into one keeps that definition's
              text (`_standing`). A refusal told in a library's file keeps no
              note. Any other refusal stays where it stands, with no
              note; where no Library Witness of its library checks clean, one
              warning on the `uses` line says so, and where one does but none
              reaches its definition, one warning names the definition. A
              library's Library Witnesses are the corpus and family games
              that `uses` it (`witness_sources`). A Library Witness reaches
              the definitions its own text names, followed through the
              reference namespaces, the rules it activates, the Delegated
              Play helpers where it plays a trick round, and the library's
              provided state.
Now illegal:  a diagnostic leaving a pass with a route, a `for_game` or a
              `stands_on`; a note made anywhere but here; a check spelling a
              library's name or a definition's library words into a sentence
              itself (tests/test_library_notes.py census), or a Library
              Citation spelled into a str (it raises); a warning that
              changes what is refused (each is told only beside a refusal); a
              check telling a refusal of library text on the `uses` line
              itself, outside the gates decisions.md names.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from cardlang.diagnostics import (
    Diagnostic,
    DiagnosticBag,
    DiagnosticError,
    LibraryCitation,
    Note,
    Severity,
    Span,
    line_kind,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from cardlang.ast import nodes as n

# Every kind of crossing a walk reports, by the game text it left by: a Trick
# Order row's call, a Hosted Poll's reach, a `run` of a library procedure (and
# a read its own arguments make), a decision position's call, and a rule's
# activation.
CROSSING_KINDS: frozenset[str] = frozenset(
    {"row", "hosted_poll", "run", "run_argument", "call", "activation"}
)

# The sentence a routed refusal adds, by its crossing kind: `{name}` the
# definition entered, `{library}` its library, `{fix}` the fix the walk
# computed. None where the walk's own sentence carries the fix.
FIX_TABLE: dict[str, str | None] = {
    "row": (
        "`{name}` is library '{library}''s, so write the fact in the row from the "
        "card and public state instead of calling it"
    ),
    "hosted_poll": "`{name}` is library '{library}''s, so take it out of the Hosted Poll's body",
    "run": "`{name}` is library '{library}''s procedure, so {fix}",
    "run_argument": (
        "`{name}` is library '{library}''s procedure, and the cards are read by "
        "the argument this `run` passes it"
    ),
    "call": None,
    "activation": None,
}

_ROOT = Path(__file__).resolve().parent.parent
# Where Library Witnesses live: the corpus, and the family-member
# directories under experiments/.
_WITNESS_GLOBS: tuple[tuple[str, str], ...] = (
    ("docs/games", "*.cardlang"),
    ("experiments", "**/*.cardlang"),
)


_USES_LINE = re.compile(r"^\s*uses\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.M)


def witness_sources(library: str) -> tuple[tuple[str, str], ...]:
    """Every game file that `uses` `library`, as (repo-relative path, text),
    in path order: the games whose verdicts can prove the library sound."""
    found: list[tuple[str, str]] = []
    for base, pattern in _WITNESS_GLOBS:
        for path in sorted((_ROOT / base).glob(pattern)):
            text = path.read_text()
            if library in _USES_LINE.findall(text):
                found.append((path.relative_to(_ROOT).as_posix(), text))
    return tuple(found)


# --- the raise ----------------------------------------------------------------


def raise_if_errors(
    bag: DiagnosticBag, game: n.Game, uses: tuple[n.UsesDecl, ...] = ()
) -> None:
    """Raise `bag`'s diagnostics, each told in the file `tell` decides, when
    it holds an error. `uses` are the game's `uses` lines where `game` no
    longer names them (a spliced game)."""
    if not bag.has_errors:
        return
    tell(bag, game, uses)
    _raise(bag)


def raise_where_written(bag: DiagnosticBag) -> None:
    """Raise `bag`'s diagnostics, each told where it stands, when it holds an
    error: a library checked alone, before any game is read."""
    if not bag.has_errors:
        return
    bag.items[:] = [_bare(d) for d in bag.items]
    _raise(bag)


def _raise(bag: DiagnosticBag) -> None:
    error = DiagnosticError(bag.items[0])
    if len(bag.items) > 1:
        error.add_note(bag.format())
    raise error


def keep_where_written(
    bag: DiagnosticBag, game: n.Game, uses: tuple[n.UsesDecl, ...] = ()
) -> None:
    """Every diagnostic told where it stands: what `tell` reduces to while a
    Library Witness is checked, since its verdict is all that is asked of
    it."""
    bag.items[:] = [_bare(d) for d in bag.items]


# Whether a Library Witness is being checked: its verdict only, nothing told.
_WITNESSING: ContextVar[bool] = ContextVar("_WITNESSING", default=False)


def tell(bag: DiagnosticBag, game: n.Game, uses: tuple[n.UsesDecl, ...] = ()) -> None:
    """Decide the file of every diagnostic in `bag`, in place."""
    if _WITNESSING.get():
        keep_where_written(bag, game, uses)
        return
    holders = _holders(game)
    lines = _uses_lines(game, uses, holders)
    standing = _standing(game, holders, lines)
    told: list[Diagnostic] = []
    seen: dict[tuple[str, Span | None], int] = {}
    unproven: dict[str, Span] = {}
    unreached: dict[tuple[str, str], Span] = {}
    for d in bag.items:
        moved = _routed(d) if d.route is not None else None
        if moved is None and d.route is None and d.severity is Severity.ERROR:
            origin = _holder(d.span, holders)
            library = origin.library if origin is not None else _library_of(d.span, lines)
            if library is not None and library in lines:
                certificate = _certificate(library)
                witness = (
                    certificate.reached.get(_key(origin)) if origin is not None else None
                )
                if witness is not None and origin is not None:
                    moved = Diagnostic(
                        d.severity,
                        d.for_game or _certified(d.message, origin, witness),
                        lines[library],
                    )
                elif not certificate.proven:
                    unproven.setdefault(library, lines[library])
                elif origin is not None:
                    unreached.setdefault((library, origin.where), lines[library])
        if moved is None:
            stands = d.stands_on + standing.get(_at(d.span), ())
            told.append(_bare(d, (), stands, holders, lines))
            continue
        stands = d.stands_on + standing.get(_at(moved.span), ())
        noted = _bare(moved, (d.span,), stands, holders, lines)
        key = (moved.message, moved.span)
        if key not in seen:
            seen[key] = len(told)
            told.append(noted)
            continue
        # One refusal told once, noted at every library line it was raised at.
        kept = told[seen[key]]
        lines_noted = {(nt.span.source_name, nt.span.line) for nt in kept.notes}
        extra = tuple(
            nt for nt in noted.notes if (nt.span.source_name, nt.span.line) not in lines_noted
        )
        told[seen[key]] = replace(kept, notes=kept.notes + extra)
    for library, at in unproven.items():
        told.append(Diagnostic(Severity.WARNING, unproven_warning(library), at))
    for (library, where), at in unreached.items():
        told.append(Diagnostic(Severity.WARNING, unreached_warning(library, where), at))
    bag.items[:] = told


# What the warning beside an unproven library's refusals begins with, and the
# warning beside a refusal of a proven library's definition no clean Library
# Witness reaches.
UNPROVEN_PHRASE = "no game yet checks clean with library"
UNREACHED_PHRASE = "no game yet checks clean reaching library"


def unproven_warning(library: str) -> str:
    return (
        f"{UNPROVEN_PHRASE} '{library}', so a refusal standing in its file is "
        f"told there"
    )


def unreached_warning(library: str, where: str) -> str:
    return (
        f"{UNREACHED_PHRASE} '{library}''s {where}, so its refusal is told in "
        f"the library's file"
    )


def is_library_warning(line: str) -> bool:
    """Whether a rendered line is the step's warning on a `uses` line."""
    return line_kind(line) == "warning" and (UNPROVEN_PHRASE in line or UNREACHED_PHRASE in line)


def _bare(
    d: Diagnostic,
    raised_at: tuple[Span | None, ...] = (),
    stands_on: tuple[Span, ...] = (),
    holders: list[_Holder] | None = None,
    lines: dict[str, Span] | None = None,
) -> Diagnostic:
    """`d` told as it stands, with no step input left on it, and the library
    text it stands on as its notes: each distinct library line of where it
    was raised and of `stands_on`, in that order, outside the file `d` is
    told in; none where `d` is told in a library's file."""
    in_library = d.span is not None and (
        _holder(d.span, holders or []) is not None or _library_of(d.span, lines or {}) is not None
    )

    def noted(spans: tuple[Span | None, ...]) -> tuple[Note, ...]:
        found: dict[tuple[str, int], Note] = {}
        for at in () if in_library else spans:
            nt = _note(at, d.span, holders or [], lines or {})
            if nt is not None:
                found.setdefault((nt.span.source_name, nt.span.line), nt)
        return tuple(found.values())

    notes = noted(raised_at + stands_on)
    if d.route is None and d.for_game is None and not d.stands_on and not notes:
        return d
    return Diagnostic(d.severity, d.message, d.span, notes=notes)


def _note(
    at: Span | None, told_at: Span | None, holders: list[_Holder], lines: dict[str, Span]
) -> Note | None:
    """The note naming the library text at `at`, for a refusal told at
    `told_at`; None where `at` is no library's text or the refusal is told in
    its file."""
    if at is None or (told_at is not None and told_at.source_name == at.source_name):
        return None
    origin = _holder(at, holders)
    if origin is not None:
        return Note(at, f"in {_library_words(origin.library)}'s {_where(origin)}")
    library = _library_of(at, lines)
    return None if library is None else Note(at, f"in {_library_words(library)}")


def _where(origin: n.LibraryOrigin) -> str:
    """The definition `origin` records, in the designer's words, after its
    library's name: a provided declaration by the variable it declares."""
    return origin.where if origin.provided is None else f"provided state `{origin.provided}`"


def _library_words(library: str) -> str:
    from cardlang.stdlib.rules import STDLIB_NAME

    return "the standard library" if library == STDLIB_NAME else f"library '{library}'"


# --- the words a sentence names library text by -----------------------------------


def cite_library(library: str, at: Span | None) -> LibraryCitation:
    """`library` named alone, standing on the library text at `at`: the text
    the sentence is about, None where it names no text of the library."""
    return LibraryCitation(_library_words(library), at)


def cite_definition(library: str, where: str, at: Span | None) -> LibraryCitation:
    """`where`, a definition of `library` in the designer's words, standing on
    the library text at `at`."""
    return LibraryCitation(f"{_library_words(library)}'s {where}", at)


def cite_origin(origin: n.LibraryOrigin, at: Span | None) -> LibraryCitation:
    """The definition `origin` records, standing on the library text at
    `at`."""
    return cite_definition(origin.library, _where(origin), at)


def cite_where(where: str, at: Span | None) -> LibraryCitation:
    """`where`, a definition in the designer's words, in a sentence that has
    named its library already, standing on the library text at `at`."""
    return LibraryCitation(where, at)


def _routed(d: Diagnostic) -> Diagnostic:
    route = d.route
    assert route is not None
    if d.for_game is not None:
        return Diagnostic(d.severity, d.for_game, route.at)
    sentence = FIX_TABLE[route.kind]
    message = d.message
    if sentence is not None:
        message += ". " + sentence.format(name=route.name, library=route.library, fix=route.fix)
    return Diagnostic(d.severity, message, route.at)


def _certified(message: str, origin: n.LibraryOrigin, witness: str) -> str:
    return (
        f"library '{origin.library}''s {_where(origin)} is refused in this game, "
        f"though {witness} checks clean with library '{origin.library}': {message}"
    )


# --- where a diagnostic stands ----------------------------------------------------


@dataclass(frozen=True)
class _Holder:
    source: str
    start: int
    end: int
    origin: n.LibraryOrigin


def _holders(game: n.Game) -> list[_Holder]:
    """Every spliced definition and provided declaration, by the span of the
    library text it holds, and every block a library procedure's `run`
    became, by its definition's span."""
    from cardlang.ast import nodes as n
    from cardlang.resolve import _walk

    found: list[_Holder] = []
    defs: list[object] = [*game.functions, *game.procedures, *game.move_types, *game.rules]
    if game.state is not None:
        defs.extend(game.state.decls)
    for d in defs:
        origin = getattr(d, "origin", None)
        span = getattr(d, "span", None)
        if origin is not None and span is not None:
            found.append(_Holder(span.source_name, span.start, span.end, origin))
    for nd in _walk(game):
        if isinstance(nd, n.Block) and nd.origin is not None and nd.definition is not None:
            at = nd.definition
            found.append(_Holder(at.source_name, at.start, at.end, nd.origin))
    return found


_Place = tuple[str, int, int]


def _at(span: Span | None) -> _Place | None:
    return None if span is None else (span.source_name, span.start, span.end)


def _standing(
    game: n.Game, holders: list[_Holder], lines: dict[str, Span]
) -> dict[_Place | None, tuple[Span, ...]]:
    """The game text that stands on library text, by its place, to that
    library text: a template argument the game wrote, substituted into a
    library definition, stands on the library text holding it; and game text
    naming a spliced library definition -- by `resolve`'s naming slots, a
    call, a `run`, an offer, an activation -- stands on that definition. A
    refusal standing at such game text stands on that library text."""
    from cardlang import resolve

    found: dict[_Place | None, tuple[Span, ...]] = {}

    def visit(node: object, holding: Span) -> None:
        span = getattr(node, "span", None)
        if isinstance(span, Span) and span.source_name != holding.source_name:
            found.setdefault(_at(span), (holding,))
            return
        inner = span if isinstance(span, Span) else holding
        for child in _children(node):
            visit(child, inner)

    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)}
        for ns, field in (*resolve.HOSTED_REACH_POOLS.items(), ("rule", "rules"))
    }
    for pool in pools.values():
        for d in pool.values():
            span = getattr(d, "span", None)
            if getattr(d, "origin", None) is not None and isinstance(span, Span):
                visit(d, span)
    naming = getattr(resolve, "_NAMING_SLOTS_BY_TYPE")
    for node in resolve._walk(game):
        span = getattr(node, "span", None)
        if not isinstance(span, Span) or _holder(span, holders) or _library_of(span, lines):
            continue
        for field_name in naming.get(type(node), ()):
            pool = pools.get(resolve.slot_namespace(node, field_name) or "", {})
            named = [pool.get(name) for name in resolve.slot_strings(node, field_name)]
            at = tuple(
                defined for d in named
                if getattr(d, "origin", None) is not None
                and isinstance(defined := getattr(d, "span", None), Span)
            )
            if at:
                found[_at(span)] = found.get(_at(span), ()) + at
    return found


def _children(node: object) -> Iterator[object]:
    """The nodes one level under `node`, the stamps the splice leaves aside."""
    if not is_dataclass(node) or isinstance(node, type):
        return
    for f in fields(node):
        if f.name in ("origin", "contract", "contracts"):
            continue
        value = getattr(node, f.name)
        for item in value if isinstance(value, tuple) else (value,):
            if is_dataclass(item) and not isinstance(item, (Span, type)):
                yield item


def _holder(span: Span | None, holders: list[_Holder]) -> n.LibraryOrigin | None:
    if span is None:
        return None
    inside = [
        h for h in holders
        if h.source == span.source_name and h.start <= span.start and span.end <= h.end
    ]
    return min(inside, key=lambda h: h.end - h.start).origin if inside else None


def _uses_lines(
    game: n.Game, uses: tuple[n.UsesDecl, ...], holders: list[_Holder]
) -> dict[str, Span]:
    """Each used library's `uses` line, by library name."""
    lines: dict[str, Span] = {}
    for use in (*game.uses, *uses):
        if use.span is not None:
            lines.setdefault(use.name, use.span)
    for holder in holders:
        if holder.origin.uses_span is not None:
            lines.setdefault(holder.origin.library, holder.origin.uses_span)
    return lines


def _library_of(span: Span | None, lines: dict[str, Span]) -> str | None:
    """The library whose file `span` stands in: a used library, or the
    standard library."""
    from cardlang.libraries import library_source_name
    from cardlang.stdlib.rules import STDLIB_NAME, STDLIB_SOURCE_NAME

    if span is None:
        return None
    if span.source_name == STDLIB_SOURCE_NAME:
        return STDLIB_NAME
    return next((lib for lib in lines if library_source_name(lib) == span.source_name), None)


# --- the certificate ----------------------------------------------------------------

_Key = tuple[str, str, str | None]


def _key(origin: n.LibraryOrigin | None) -> _Key:
    assert origin is not None
    return (origin.library, origin.where, origin.provided)


@dataclass(frozen=True)
class _Certificate:
    """What a library's Library Witnesses prove: whether any checks clean, and each
    definition some clean Library Witness reaches, to the first such one."""

    proven: bool
    reached: dict[_Key, str]


_CERTIFICATES: dict[object, _Certificate] = {}


def _certificate(library: str) -> _Certificate:
    from cardlang import resolve

    load = getattr(resolve, "load_library")
    sources = witness_sources(library)
    # The text of every library a Library Witness uses, never one none uses.
    used = {library} | {m for _label, text in sources for m in _USES_LINE.findall(text)}
    names = sorted(used & getattr(resolve, "library_names")())
    key = (library, tuple(_fingerprint(load, name) for name in names), sources)
    found = _CERTIFICATES.get(key)
    if found is None:
        proven = False
        reached: dict[_Key, str] = {}
        for label, source in sources:
            keys = _witness_reach(label, source)
            if keys is None:
                continue
            proven = True
            for k in keys:
                reached.setdefault(k, label)
        found = _Certificate(proven, reached)
        _CERTIFICATES[key] = found
    return found


def _fingerprint(load: Callable[[str], object], name: str) -> str:
    """A library's text for the cache key. A library that fails to load fails
    only the Library Witnesses that use it, where each is checked."""
    try:
        return repr(load(name))
    except Exception as exc:
        return f"unloadable: {exc!r}"


@contextmanager
def _witnessing() -> Iterator[None]:
    token = _WITNESSING.set(True)
    try:
        yield
    finally:
        _WITNESSING.reset(token)


def _witness_reach(label: str, source: str) -> frozenset[_Key] | None:
    """The library definitions `source` reaches, when it checks clean; None
    when it does not."""
    from cardlang import resolve
    from cardlang.deckcheck import check_capacity
    from cardlang.expand import expand
    from cardlang.parse import parse_text
    from cardlang.typecheck import typecheck

    with _witnessing():
        try:
            game = resolve.resolve(parse_text(source, label))
            check_capacity(expand(typecheck(game)))
        except Exception:
            # Not clean, whatever the failure: a Library Witness's own crash is
            # told where that game is checked, never in the game asking here.
            return None
    return _reach(game)


def _reach(game: n.Game) -> frozenset[_Key]:
    """Every spliced definition `game` runs: what the text it runs names --
    its phases, rows, rules and results, never a definition nothing runs --
    followed through the reference namespaces, every rule it activates (a
    library rule is spliced only where it is activated), the Delegated Play
    helpers where it plays a trick round, and the provided state."""
    from cardlang import resolve
    from cardlang.ast import nodes as n
    from cardlang.runtime.delegation import HELPER_NAMES

    trick = any(isinstance(nd, n.TrickRound) for nd in resolve._walk(game))
    engine_called = HELPER_NAMES if trick else frozenset()
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)}
        for ns, field in resolve.HOSTED_REACH_POOLS.items()
    }
    helpers = tuple(f for f in game.functions if f.name in engine_called)
    runs = replace(game, functions=helpers, procedures=(), move_types=())
    run: list[object] = [t for t, _via in resolve._definition_closure([runs], pools).values()]
    run.extend(helpers)
    run.extend(game.rules)
    if game.state is not None:
        run.extend(game.state.decls)
    return frozenset(
        _key(origin) for d in run if (origin := getattr(d, "origin", None)) is not None
    )
