"""A refusal names a definition only through a citation carrying its line.

Every function, procedure, move type, rule, rule template and provided state
variable a refusal's sentence names -- the game's or a library's -- is named
by a citation (`attribution.cite_named` and its siblings), which carries the
definition's span: the attribution step words it and, for library text,
makes its Library Note (decisions.md "Family libraries"). A citation of the
game's own text renders the same words and makes no note.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        no refusal any refusal-raising cell below raises names a
                 definition of its game or libraries in plain text: every
                 such name in a sentence, its own sentence and the game's
                 alike, is inside a citation; and no source string outside
                 the step interpolates a slot that only ever names a
                 definition.
domain:          the executed census: every refusal raised while every
                 rejection golden (tests/test_rejections.py `case_paths`),
                 every ledger cell (tests/test_library_attribution.py
                 `_cells`), every library-to-game witness
                 (tests/test_library_boundary_ledger.py
                 `_library_to_game_witnesses`) and every `NAMED` cell of
                 tests/test_library_notes.py runs, against the definitions
                 of the game and libraries the cell checks -- functions,
                 procedures, move types, rules and templates, the standard
                 library's rules, and the libraries' provided state, less the
                 language's own words (the Play Source, the reserved values),
                 which a sentence quotes as the language's. A name
                 is named where it is a quoted token of the sentence's plain
                 text, or an identifier inside a backquoted snippet. The
                 static arm: the reference-slot fields every row of which
                 names a definition namespace (`_DEFINITION_FIELDS`,
                 derived from `resolve._REFERENCE_SLOTS` and
                 `resolve._CONTEXTUAL_SLOTS`), interpolated into a string
                 anywhere in `cardlang/` outside the step.
registry:        definition namespaces: `_DEFINITION_NAMESPACES`; reference
                 slots: `resolve._REFERENCE_SLOTS`, `resolve._CONTEXTUAL_SLOTS`;
                 cells: the four families above.
does not prove:  that a refusal no cell raises cites what it names: the
                 executed census reads only sentences a cell raises, and the
                 static arm only the slots that always name a definition --
                 a `.name` is shared with zones, phases and parameters, so a
                 source scan cannot tell a definition's name from theirs.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

import pytest

import cardlang.diagnostics as D
import cardlang.resolve as R
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError, LibraryCitation, Sentence, Span
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.stdlib.rules import stdlib_rules
import tests.test_library_boundary_ledger as L
import tests.test_library_notes as LN
from tests.test_library_attribution import _cells
from tests.test_rejections import REJECTIONS_DIR, case_paths

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE = _ROOT / "cardlang"
_THE_STEP = frozenset({"attribution.py", "diagnostics.py"})

# The namespaces whose names are always definitions a refusal cites. The
# `function` namespace also holds the Builtins and the Primitives, so a slot
# drawing from it names no definition for sure.
_DEFINITION_NAMESPACES = frozenset({"procedure", "move_type", "rule"})


def _definitions(game: n.Game | None, libraries: tuple[n.Library, ...]) -> frozenset[str]:
    names: set[str] = set(stdlib_rules())
    for holder in (*libraries, *(() if game is None else (game,))):
        for field in ("functions", "procedures", "move_types", "rules"):
            names.update(d.name for d in getattr(holder, field))
    for library in libraries:
        if library.state is not None:
            names.update(d.name for d in library.state.decls)
    # The language's own words: a sentence quoting the Play Source or a
    # reserved value speaks of the language, whatever a definition shares it.
    return frozenset(names - _LANGUAGE_WORDS)


_LANGUAGE_WORDS = frozenset({R.PLAY_SOURCE_NAME}) | R.RESERVED_VALUE_NAMES


_QUOTED = re.compile(r"'([^'\s]+)'|`([^`]+)`")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _named_in(text: str, definitions: frozenset[str]) -> set[str]:
    found: set[str] = set()
    for single, snippet in _QUOTED.findall(text):
        if single and single in definitions:
            found.add(single)
        for word in _IDENT.findall(snippet):
            if word in definitions:
                found.add(word)
    return found


def _plain(message: object) -> list[str]:
    if isinstance(message, str):
        return [message]
    if isinstance(message, LibraryCitation):
        return []
    assert isinstance(message, Sentence)
    return [p for p in message.parts if isinstance(p, str)]


# The frames between a check and the bag, which name no check.
_PASSING_FRAMES = frozenset({"error", "_emit", "_tell", "recording"})


def _site(frame: FrameType | None) -> str:
    while frame is not None and (
        frame.f_code.co_name in _PASSING_FRAMES
        or not frame.f_code.co_filename.startswith(str(_PACKAGE))
    ):
        frame = frame.f_back
    if frame is None:
        return "<outside cardlang>"
    path = Path(frame.f_code.co_filename).relative_to(_PACKAGE).as_posix()
    return f"{path}::{frame.f_code.co_name}"


@dataclass
class _Census:
    definitions: frozenset[str] = frozenset()
    found: dict[str, str] | None = None
    # Refusals read against a known set of definitions.
    read: int = 0

    def record(self, message: object, for_game: object) -> None:
        assert self.found is not None
        if self.definitions:
            self.read += 1
        named: set[str] = set()
        for said in (message, for_game):
            if said is None:
                continue
            for text in _plain(said):
                named |= _named_in(text, self.definitions)
        if named:
            self.found.setdefault(_site(sys._getframe(2)), ", ".join(sorted(named)))


def _instrumented(monkeypatch: pytest.MonkeyPatch, census: _Census) -> None:
    real = D.DiagnosticBag.error
    real_uses = getattr(R, "_apply_uses")

    def applying(game: n.Game, bag: D.DiagnosticBag) -> tuple[n.Game, dict[str, n.RuleDef]]:
        libraries = tuple(
            getattr(R, "load_library")(u.name) for u in game.uses if u.name in getattr(R, "library_names")()
        )
        census.definitions = census.definitions | _definitions(game, libraries)
        return real_uses(game, bag)  # type: ignore[no-any-return]

    monkeypatch.setattr(R, "_apply_uses", applying)

    def error(self: D.DiagnosticBag, message: D.Said, span: Span | None = None, **kw: object) -> None:
        census.record(message, kw.get("for_game"))
        real(self, message, span, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(D.DiagnosticBag, "error", error)


def _library_texts(text: str) -> tuple[n.Library, ...]:
    out: list[n.Library] = []
    for name in re.findall(r"^\s*uses\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M):
        try:
            out.append(getattr(R, "load_library")(name))
        except Exception:
            continue
    return tuple(out)


def _parsed(text: str, label: str) -> n.Game | None:
    try:
        return parse_text(text, label)
    except DiagnosticError:
        return None


# --- the cells the census reads ---------------------------------------------------


Cell = Callable[[pytest.MonkeyPatch, _Census], None]


def _rejection_cells() -> dict[str, Cell]:
    def cell(path: Path) -> Cell:
        def run(mp: pytest.MonkeyPatch, census: _Census) -> None:
            text = path.read_text()
            label = path.relative_to(REJECTIONS_DIR).as_posix()
            if "libraries" in path.parts:
                try:
                    library = parse_library(text, label)
                except DiagnosticError:
                    return
                census.definitions = _definitions(None, (library,))
                return
            census.definitions = _definitions(_parsed(text, label), _library_texts(text))
            try:
                check_dsl(text, label)
            except DiagnosticError:
                pass
        return run

    return {f"rejection:{p.stem}": cell(p) for p in case_paths()}


def _crossing_cell(crossing: L.Crossing) -> Cell:
    def run(mp: pytest.MonkeyPatch, census: _Census) -> None:
        libraries: tuple[n.Library, ...] = ()
        if crossing.library is not None:
            try:
                libraries = (parse_library(crossing.library, L._LIB_FILE),)
            except DiagnosticError:
                return
        census.definitions = _definitions(_parsed(crossing.game, L._GAME_FILE), libraries)
        L._cell_bag(mp, crossing)
    return run


def _ledger_cells() -> dict[str, Cell]:
    return {f"ledger:{k}": _crossing_cell(c) for k, c in _cells().items()}


def _named_cells() -> dict[str, Cell]:
    def cell(named: LN.Named) -> Cell:
        def run(mp: pytest.MonkeyPatch, census: _Census) -> None:
            libraries = tuple(
                parse_library(t, f"docs/libraries/{k}.cardlang") for k, t in named.libraries
            )
            census.definitions = _definitions(_parsed(named.game, L._GAME_FILE), libraries)
            LN._named_bag(mp, named)
        return run
    return {f"named:{k}": cell(c) for k, c in LN.NAMED.items()}


def _witness_cells() -> dict[str, Cell]:
    def cell(witness: L.Witness) -> Cell:
        def run(mp: pytest.MonkeyPatch, census: _Census) -> None:
            witness(mp)
        return run
    return {f"witness:{k}": cell(w) for k, w in L._library_to_game_witnesses().items()}


_FAMILIES: dict[str, Callable[[], dict[str, Cell]]] = {
    "rejections": _rejection_cells,
    "ledger": _ledger_cells,
    "named": _named_cells,
    "witnesses": _witness_cells,
}


def _uncited(monkeypatch: pytest.MonkeyPatch, family: str) -> dict[str, str]:
    """Each check that named a definition in plain text, by its site, to the
    first cell and names it was caught at."""
    found: dict[str, str] = {}
    read = 0
    for key, cell in sorted(_FAMILIES[family]().items()):
        census = _Census(found={})
        with monkeypatch.context() as mp:
            _instrumented(mp, census)
            cell(mp, census)
        read += census.read
        for site, names in (census.found or {}).items():
            found.setdefault(site, f"{key}: {names}")
    assert read > 0, f"{family}: no refusal was read against its definitions"
    return found


@pytest.mark.parametrize("family", sorted(_FAMILIES))
def test_no_refusal_names_a_definition_in_plain_text(
    monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    """red under: write `f"function '{fn.name}' is recursive"` back in
    `resolve._report_recursion`."""
    assert _uncited(monkeypatch, family) == {}


def test_the_census_sees_a_plain_definition_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """A known positive: a refusal naming a definition in plain text is
    caught, at its site, and one citing it is not.

    red under: return no names from `_named_in`."""
    census = _Census(definitions=frozenset({"libp"}), found={})
    with monkeypatch.context() as mp:
        _instrumented(mp, census)
        D.DiagnosticBag().error("procedure 'libp' is never run", None)
        D.DiagnosticBag().error(LibraryCitation("procedure 'libp'", None) + " is never run", None)
        D.DiagnosticBag().error("run `libp(0)` here", None)
    assert census.found == {"<outside cardlang>": "libp"}


# --- the static arm ----------------------------------------------------------------


def _definition_fields() -> frozenset[str]:
    """The reference-slot fields every row of which names a definition."""
    by_field: dict[str, set[str]] = {}
    for (_cls, field), namespace in R._REFERENCE_SLOTS.items():
        by_field.setdefault(field, set()).add(namespace)
    for (_cls, field), slot in R._CONTEXTUAL_SLOTS.items():
        by_field.setdefault(field, set()).update(slot.namespaces)
    return frozenset(f for f, spaces in by_field.items() if spaces <= _DEFINITION_NAMESPACES)


_DEFINITION_FIELDS = _definition_fields()


def _interpolations(source: str) -> Iterator[str]:
    tree = ast.parse(source)
    for nd in ast.walk(tree):
        operands: list[ast.expr] = []
        if isinstance(nd, ast.JoinedStr):
            operands = [v.value for v in nd.values if isinstance(v, ast.FormattedValue)]
        elif isinstance(nd, ast.BinOp) and isinstance(nd.op, ast.Add):
            operands = [nd.left, nd.right]
        for operand in operands:
            if isinstance(operand, ast.Attribute) and operand.attr in _DEFINITION_FIELDS:
                yield f"{getattr(nd, 'lineno', 0)}: {ast.unparse(operand)}"


def test_the_definition_fields_are_derived() -> None:
    """red under: give `Offer.offering` a second namespace in the
    registry."""
    assert "offering" in _DEFINITION_FIELDS
    assert not {"name", "func"} & _DEFINITION_FIELDS


def test_no_source_interpolates_a_definition_slot() -> None:
    """red under: write `f"offering {nd.offering}"` into a resolve
    sentence."""
    found = [
        f"{path.relative_to(_ROOT).as_posix()}:{at}"
        for path in sorted(_PACKAGE.rglob("*.py"))
        if path.relative_to(_PACKAGE).as_posix() not in _THE_STEP
        for at in _interpolations(path.read_text())
    ]
    assert found == []
