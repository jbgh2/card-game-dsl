"""A refusal standing in library text is told in the file one step decides.

`cardlang.attribution` decides, where the passes raise, which file every
refusal of spliced family-library text is told in: at the game's text a
crossing walk left by (its route), on the game's `uses` line when a game that
checks clean reaches the same definition (its certificate), and otherwise in
the library's file, with a note on the `uses` line when no game yet checks
clean with the library (decisions.md "Family libraries").

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        no refusal stands in a routed or certified library span; no
                 check but the step chooses a refusal's file, and every raise
                 after the splice runs the step; every crossing kind's fix,
                 applied, checks clean; every crossing walker reports its
                 crossing or says why it has none; every library has a clean
                 Library Witness among the games the glob finds; and who is
                 told never changes what is refused.
domain:          the crossing kinds of `attribution.CROSSING_KINDS`; the
                 members of the ledger's `crossing_walkers()`; every library
                 in `docs/libraries/`, against every game outside tests/
                 whose parse `uses` it; and for the relocation and twin pins,
                 every cell of tests/test_library_boundary_ledger.py's
                 game-to-library families, its choice, declared and unproven
                 cells, and every cell of tests/test_library_declaration_gates.py.
                 The raises are every `DiagnosticError` a pass after the
                 splice constructs; a library that does not parse is refused
                 at its parse, to its author alone, before any game is read.
registry:        crossing kinds: `attribution.CROSSING_KINDS`; walkers:
                 tests/test_library_boundary_ledger.py::crossing_walkers;
                 Library Witnesses: `attribution.witness_sources`; cells:
                 tests/test_library_boundary_ledger.py,
                 tests/test_library_declaration_gates.py; the notes and
                 warnings the step tells beside a refusal:
                 tests/test_library_notes.py.
does not prove:  that a certificate's reach is every way a definition runs: the
                 relocation pin's own reach is a name scan of each Library
                 Witness's text, which agrees with the step's only where both
                 follow names. Nor that a certified refusal's sentence carries
                 a fix the game can take where its check supplies none: the
                 step names the definition and the Library Witness, and the
                 check's own sentence follows.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

import pytest

import cardlang.attribution as attribution
import cardlang.resolve as R
from cardlang.deckcheck import check_capacity
from cardlang.diagnostics import DiagnosticBag, DiagnosticError, Route, Span
from cardlang.expand import expand
from cardlang.parse import parse_library, parse_text
from cardlang.typecheck import typecheck
import tests.test_library_boundary_ledger as L
import tests.test_library_declaration_gates as D

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE = _ROOT / "cardlang"


# --- the witness registry ---------------------------------------------------------

_LIBRARIES = sorted(p.stem for p in (_ROOT / "docs" / "libraries").glob("*.cardlang"))
_SKIPPED_DIRS = frozenset({".git", ".venv", "node_modules", "tests", "libraries"})


def _importers(name: str) -> set[str]:
    """Every `.cardlang` game outside tests/ whose parse `uses` `name`, read
    off the parsed tree rather than the glob's line match."""
    found: set[str] = set()
    for path in sorted(_ROOT.rglob("*.cardlang")):
        rel = path.relative_to(_ROOT)
        if _SKIPPED_DIRS & set(rel.parts[:-1]):
            continue
        text = path.read_text()
        if "uses" not in text:
            continue
        try:
            game = parse_text(text, rel.as_posix())
        except Exception:
            continue
        if any(use.name == name for use in game.uses):
            found.add(rel.as_posix())
    return found


@pytest.mark.parametrize("name", _LIBRARIES)
def test_the_witnesses_are_every_game_that_uses_the_library(name: str) -> None:
    """red under: drop `experiments` from `attribution._WITNESS_GLOBS`."""
    assert {at for at, _text in attribution.witness_sources(name)} == _importers(name)


@pytest.mark.parametrize("name", _LIBRARIES)
def test_every_library_has_a_witness_that_checks_clean(name: str) -> None:
    """A library no game checks clean with has no certificate, and every
    routeless refusal in it stays in its file: this goes red when a library
    loses its last clean Library Witness.

    red under: delete the `uses stud` line of seven-card-stud.cardlang and of
    five-card-stud.cardlang."""
    from cardlang.pipeline import check_dsl

    clean = []
    for at, text in attribution.witness_sources(name):
        try:
            check_dsl(text, at)
        except Exception:
            continue
        clean.append(at)
    assert clean, f"no game that uses library '{name}' checks clean"


# --- the crossing kinds and their fixes -------------------------------------------


def _run_fixes(monkeypatch: pytest.MonkeyPatch, by_argument: bool) -> None:
    cells = [c for c in L._run_fix_cells() if ("argument" in c[0]) == by_argument]
    assert cells
    for _id, library, game, run in cells:
        L.test_the_fix_a_run_is_told_passes(monkeypatch, library, game, run)


def _call_fixes(monkeypatch: pytest.MonkeyPatch) -> None:
    L.test_the_no_one_acting_remedy_is_accepted(monkeypatch)
    L.test_the_rule_filter_remedy_is_accepted(monkeypatch)


def _activation_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    """"take 'librule' out of `active_rules:`": the game without the rule's
    activation, the library still used, checks clean."""
    library, game, _owner, anchor = L._JUDGED_ONCE_KNOWN["rule-activated-where-no-trick-round-asks-it"]
    assert anchor is not None
    fixed = game.replace(anchor, "active_rules: []")
    assert fixed != game
    assert L._bag(monkeypatch, library, fixed) == []


# kind -> the remedy its refusals offer, applied
_FIX_PROOFS: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    "row": L.test_the_row_remedy_is_accepted,
    "hosted_poll": L.test_the_hosted_poll_remedy_is_accepted,
    "run": lambda mp: _run_fixes(mp, by_argument=False),
    "run_argument": lambda mp: _run_fixes(mp, by_argument=True),
    "call": _call_fixes,
    "activation": _activation_fix,
}


def test_every_crossing_kind_has_its_fix_proven() -> None:
    """red under: add a kind to `attribution.CROSSING_KINDS`."""
    assert set(_FIX_PROOFS) == attribution.CROSSING_KINDS


def test_the_fix_table_is_keyed_by_every_crossing_kind() -> None:
    table = getattr(attribution, "FIX_TABLE")
    assert set(table) == attribution.CROSSING_KINDS


@pytest.mark.parametrize("kind", sorted(attribution.CROSSING_KINDS))
def test_a_crossing_kinds_fix_checks_clean(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    _FIX_PROOFS[kind](monkeypatch)


# --- every crossing walker reports its crossing ------------------------------------

# walker -> the crossing kinds it reports, and a cell of its family reporting each
_ROUTED: dict[str, dict[str, Callable[[], L.Crossing]]] = {
    "resolve._check_trick_order_rows": {
        "row": lambda: L._row_crossing("trump", L._row_arms("trump")["zone-HiddenPile"]),
    },
    "resolve._check_hosted_polls": {"hosted_poll": lambda: L._poll_crossing("run", "Transfer")},
    "resolve._HiddenReads._run": {
        "run": lambda: L._RUN_CASES["seat-the-run-acts-as"].crossing(),
        "run_argument": lambda: L._RUN_CASES["argument-calls-a-function"].crossing(),
    },
    "resolve._HiddenReads._refuse_unacting_decisions": {
        "call": lambda: L._unacting_crossing(R._NO_ACTOR_GATE, "choose"),
    },
    "resolve._check_play_source": {
        "call": lambda: L._play_source_crossing("demands"),
        "activation": lambda: L.Crossing(
            *L._JUDGED_ONCE_KNOWN["rule-activated-where-no-trick-round-asks-it"][:2], L.GAME
        ),
    },
}


# Why a walker reports no crossing: it refuses nothing; it reports at the
# game's own text (a position, a game definition, a contract answer's stamp);
# or what it refuses in library text is no crossing's doing, so the
# certificate tells it.
_NO_CROSSING_REASONS = frozenset({"refuses nothing", "game text", "certificate"})
_UNROUTED: dict[str, str] = {
    "resolve._row_routes": "refuses nothing",
    "resolve._HiddenReads._after": "refuses nothing",
    "expand._expansion": "refuses nothing",
    "resolve._HiddenReads.reads_of": "game text",
    "resolve._report_recursion": "game text",
    "resolve._check_unoffered_move_types": "game text",
    "typecheck._check_contracted_results": "game text",
    "resolve._check_functions": "certificate",
    "resolve._check_implicit_pools": "certificate",
    "typecheck._call_sig": "certificate",
    "typecheck._check_stmt_exprs": "certificate",
}


def test_every_crossing_walker_reports_its_crossing_or_says_why_not() -> None:
    """A walker that follows a crossing out of game text either reports the
    crossing with each refusal it raises in library text, or names why it
    reports none.

    red under: have `resolve._check_arrival_record_pile_args` call
    `_definition_closure`."""
    assert set(_ROUTED).isdisjoint(_UNROUTED)
    assert set(_ROUTED) | set(_UNROUTED) == L.crossing_walkers()
    assert set(_UNROUTED.values()) <= _NO_CROSSING_REASONS
    assert {k for kinds in _ROUTED.values() for k in kinds} == attribution.CROSSING_KINDS


def _emitted_routes(monkeypatch: pytest.MonkeyPatch, cell: L.Crossing) -> set[str]:
    kinds: set[str] = set()
    original = DiagnosticBag.error

    def spy(
        self: DiagnosticBag,
        message: str,
        span: Span | None = None,
        *,
        route: Route | None = None,
        for_game: str | None = None,
        stands_on: Span | None = None,
    ) -> None:
        if route is not None:
            kinds.add(route.kind)
        original(self, message, span, route=route, for_game=for_game, stands_on=stands_on)

    monkeypatch.setattr(DiagnosticBag, "error", spy)
    L._cell_bag(monkeypatch, cell)
    return kinds


@pytest.mark.parametrize(
    ("walker", "kind"),
    [
        pytest.param(
            w, k, id=f"{w}-{k}",
        )
        for w, kinds in sorted(_ROUTED.items())
        for k in sorted(kinds)
    ],
)
def test_a_walker_reports_its_crossing(
    monkeypatch: pytest.MonkeyPatch, walker: str, kind: str
) -> None:
    """red under: drop `route=` from the walker's report."""
    assert kind in _emitted_routes(monkeypatch, _ROUTED[walker][kind]())


# --- the cells the step can touch ------------------------------------------------


def _cells() -> dict[str, L.Crossing]:
    cells: dict[str, L.Crossing] = {}
    for at, cell in enumerate(L._game_to_library_cells()):
        cells[f"game-to-library-{at}"] = cell
    for case, (issue, library, game, _said) in sorted(L._held_choices().items()):
        if issue not in L._POLICY_HELD:
            cells[f"choice-{case}"] = L.Crossing(
                library, game, L.USES, witnesses=(L._unchosen()[case],)
            )
    for case, (library, game, witness) in sorted(L._declared_cases().items()):
        cells[f"declared-{case}"] = L.Crossing(library, game, L.USES, witnesses=(witness,))
    for case, (cell, _unproven) in sorted(L._unproven_cells().items()):
        cells[f"unproven-{case}"] = cell
    for key, grid_cell in sorted(D._cells().items()):
        cells[f"declaration-{key}"] = grid_cell.crossing()
    return cells


# --- no refusal stands in a routed or certified library span ----------------------

_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_HELPERS = ("chooser_for", "play_source_for")


def _certified_lines(monkeypatch: pytest.MonkeyPatch, cell: L.Crossing) -> set[int]:
    """The library lines some clean Library Witness of `cell` reaches, by a scan of
    names: every definition its own text names, every definition
    those name in turn, a Delegated Play helper where it plays a
    trick round, and the provided state."""
    try:
        library = parse_library(cell.library, L._LIB_FILE)
    except Exception:
        return set()
    lines = cell.library.splitlines(keepends=True)

    def text_of(span: Span | None) -> str:
        return "" if span is None else cell.library[span.start:span.end]

    defs: dict[str, Span | None] = {}
    for kind in ("functions", "procedures", "move_types", "rules"):
        for d in getattr(library, kind):
            defs[d.name] = d.span
    provided = [d.span for d in (library.state.decls if library.state else ())]
    reached: set[str] = set()
    for witness in cell.witnesses:
        if L._errors(L._bag(monkeypatch, cell.library, witness)):
            continue
        frontier = set(_IDENT.findall(witness)) & set(defs)
        if "round " in witness:
            frontier |= set(_HELPERS) & set(defs)
        while frontier:
            name = frontier.pop()
            if name not in reached:
                reached.add(name)
                frontier |= (set(_IDENT.findall(text_of(defs[name]))) & set(defs)) - reached
        reached.add("<provided>")
    spans = [defs[name] for name in reached if name in defs]
    if "<provided>" in reached:
        spans.extend(provided)
    out: set[int] = set()
    for span in spans:
        if span is not None:
            first = span.line
            last = first + cell.library[span.start:span.end].count("\n")
            out.update(range(first, last + 1))
    del lines
    return out


def _library_line(line: str) -> int:
    return int(line[len(L._LIB_FILE) + 1:].split(":", 1)[0])


def _routed_lines(monkeypatch: pytest.MonkeyPatch, cell: L.Crossing) -> set[int]:
    lines: set[int] = set()
    original = DiagnosticBag.error

    def spy(
        self: DiagnosticBag,
        message: str,
        span: Span | None = None,
        *,
        route: Route | None = None,
        for_game: str | None = None,
        stands_on: Span | None = None,
    ) -> None:
        if route is not None and span is not None and span.source_name == L._LIB_FILE:
            lines.add(span.line)
        original(self, message, span, route=route, for_game=for_game, stands_on=stands_on)

    with monkeypatch.context() as mp:
        mp.setattr(DiagnosticBag, "error", spy)
        L._cell_bag(mp, cell)
    return lines


def test_no_refusal_stands_in_a_routed_or_certified_library_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read off the rendered verdict and a name scan of the witnesses, never
    off the step.

    red under: have `attribution` leave a routed refusal where it stands."""
    standing: list[str] = []
    for key, cell in _cells().items():
        bag = L._errors(L._cell_bag(monkeypatch, cell))
        in_library = [_library_line(line) for line in bag if line.startswith(L._LIB_FILE)]
        if not in_library:
            continue
        held = _routed_lines(monkeypatch, cell) | _certified_lines(monkeypatch, cell)
        standing.extend(f"{key}: line {at}" for at in in_library if at in held)
    assert standing == []


# --- who is told never changes what is refused ----------------------------------


def test_the_step_never_changes_what_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every cell the step can touch is refused exactly when it is with the
    step telling every refusal where it stands.

    red under: have `attribution` drop a refusal it cannot place."""
    keep = getattr(attribution, "keep_where_written")
    for key, cell in _cells().items():
        told = bool(L._errors(L._cell_bag(monkeypatch, cell)))
        with monkeypatch.context() as mp:
            mp.setattr(attribution, "tell", keep)
            kept = bool(L._errors(L._cell_bag(mp, cell)))
        assert told == kept, key


def _alone(
    monkeypatch: pytest.MonkeyPatch, cell: L.Crossing, other: str, witnesses: tuple[str, ...]
) -> list[str]:
    """`cell`'s verdict with `other` registered beside its library, failing
    whenever it is loaded, and `witnesses` as its Library Witnesses."""
    lib = parse_library(cell.library, L._LIB_FILE)

    def load(name: str) -> object:
        if name != L._LIB:
            raise AssertionError(f"library '{name}' is loaded")
        return lib

    sources = tuple((f"witness-{at}.cardlang", text) for at, text in enumerate(witnesses))
    with monkeypatch.context() as mp:
        mp.setattr(R, "library_names", lambda: frozenset({L._LIB, other}))
        mp.setattr(R, "load_library", load)
        mp.setattr(attribution, "witness_sources", lambda name: sources)
        try:
            check_capacity(expand(typecheck(R.resolve(parse_text(cell.game, L._GAME_FILE)))))
        except DiagnosticError as exc:
            return L._rendered(exc)
    return []


def _parsed_cells() -> dict[str, L.Crossing]:
    found: dict[str, L.Crossing] = {}
    for key, cell in _cells().items():
        try:
            parse_library(cell.library, L._LIB_FILE)
        except Exception:
            continue
        found[key] = cell
    return found


def test_a_library_no_witness_uses_is_never_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registered library that neither the game nor any Library Witness uses
    never reaches this game's verdict.

    red under: key `attribution._certificate` on every registered library."""
    for key, cell in _parsed_cells().items():
        assert _alone(monkeypatch, cell, "unused", cell.witnesses) == L._cell_bag(monkeypatch, cell), key


def test_a_witness_whose_library_fails_fails_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Library Witness using a library that fails to load is not clean, and
    the other Library Witnesses certify as before.

    red under: have `attribution._fingerprint` let a load failure raise."""
    for key, cell in _parsed_cells().items():
        witnesses = (*cell.witnesses, "uses broken\n")
        assert _alone(monkeypatch, cell, "broken", witnesses) == L._cell_bag(monkeypatch, cell), key


# --- the library line a moved refusal stands on ---------------------------------


def test_a_routed_refusal_keeps_its_library_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """The witness: a Trick Order row calling a library function that reads a
    pronoun is told at the row, and the function's line follows as a note."""
    cell = _cells()["game-to-library-0"]
    bag = L._cell_bag(monkeypatch, cell)
    line = L._line(cell.library, "function libf")
    assert bag[0].startswith(f"{L._GAME_FILE}:"), "\n".join(bag)
    assert any(at.startswith(f"{L._LIB_FILE}:{line}:") and ": note: " in at for at in bag), "\n".join(bag)


# --- only the step chooses the file ----------------------------------------------

_PASSES = ("resolve", "typecheck", "expand", "deckcheck", "ir")
# The gates decisions.md names, which tell a game clause or a contract row on
# the `uses` line before any certificate: the type layer's clause reads and
# its contract-result check.
_USES_SPAN_READERS = frozenset({
    "attribution",
    "typecheck._check_contracted_results",
    "typecheck._library_field_gate",
})


def _qualified_reads(attr: str) -> set[str]:
    found: set[str] = set()
    for module in (*_PASSES, "attribution"):
        tree = ast.parse((_PACKAGE / f"{module}.py").read_text())
        for top in tree.body:
            for nd in ast.walk(top):
                if isinstance(nd, ast.Attribute) and nd.attr == attr and isinstance(nd.ctx, ast.Load):
                    name = getattr(top, "name", "<module>")
                    found.add(module if module == "attribution" else f"{module}.{name}")
    return found


def test_only_the_step_and_the_named_gates_read_the_uses_line() -> None:
    """red under: tell a refusal on `origin.uses_span` in a resolve check."""
    assert _qualified_reads("uses_span") <= _USES_SPAN_READERS


def test_no_check_moves_a_refusal_itself() -> None:
    """The per-check movers are gone: no sink class re-spans a refusal and no
    helper tells one on the `uses` line.

    red under: restore `_UsesLineTeller`."""
    tree = ast.parse((_PACKAGE / "resolve.py").read_text())
    names = {
        nd.name for nd in tree.body if isinstance(nd, (ast.ClassDef, ast.FunctionDef))
    }
    movers = {n for n in names if n.endswith("LibrarySink")} | (
        names & {"_UsesLineTeller", "_game_decides"}
    )
    assert movers == set()


def test_every_raise_after_the_splice_runs_the_step() -> None:
    """A pass raising its bag itself would raise refusals the step never
    placed.

    red under: construct `DiagnosticError(bag.items[0])` in typecheck."""
    raising = set()
    for module in _PASSES:
        tree = ast.parse((_PACKAGE / f"{module}.py").read_text())
        for nd in ast.walk(tree):
            if (
                isinstance(nd, ast.Call)
                and isinstance(nd.func, ast.Name)
                and nd.func.id == "DiagnosticError"
            ):
                raising.add(module)
    assert raising == set()
