"""A refusal of library text told in the game's file names the library's line.

The attribution step (`cardlang.attribution`) decides which file every refusal
of library text is told in; this module pins what it tells beside that
choice: the library line a refusal told in the game's file stands on, as a
`note:` under it, and the `uses`-line warning a refusal left in the
library's file carries (decisions.md "Family libraries").

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a refusal the step tells in the game's file -- at a
                 crossing's game text, on the `uses` line by a certificate,
                 or where a check stood it at the game's text on library
                 text -- renders exactly one `note:` at the library line it
                 stands on; a refusal left in the library's file renders no
                 note, and where its library is unproven, or its definition
                 is one no clean Library Witness reaches in a proven
                 library, one warning on the `uses` line says so; every
                 rendered line is an error, a warning or a note; and who is
                 told never changes what is refused.
domain:          the step's own domain, crossed: the game the step is handed
                 (`STAGES`: the spliced game before the splice's raise, the
                 resolved game, the expanded game), how the step tells the
                 refusal (`TELLINGS`), and where the refused definition lives
                 (`LIVES`: a family library's procedure, the standard
                 library's rule, a family library's text outside any
                 definition). Beside it, every cell the boundary ledger
                 and the declaration gates hold
                 (tests/test_library_attribution.py `_cells`), rendered
                 through the real pipeline, and every rejection golden of a
                 game that `uses` a library. The standard library has no
                 `uses` line, so its refusals are certified nowhere and warned
                 of nowhere: its certificate, unproven and unreached cells
                 stay in its file alone; its rules are spliced only once the
                 game activates them, so a note on one before the splice
                 names the standard library. Text outside any definition
                 has no definition a Library Witness can reach, so it is
                 certified nowhere and its note names its library.
registry:        stages: `STAGES`, pinned against the raises after the splice
                 (`test_the_stages_are_the_raises`); tellings: `TELLINGS`;
                 rendered line kinds: `cardlang.diagnostics.LINE_KINDS`;
                 ledger cells: tests/test_library_attribution.py `_cells`;
                 rejection goldens: tests/test_rejections.py `case_paths`.
does not prove:  that the library line a check names is the one its sentence
                 means: a check standing a refusal at the game's text hands
                 the step the library text it read, and the note is that
                 line. Nor that a refusal of the game's own phase the deck
                 capacity gate raises names the library deals it sums: the
                 refusal stands at the phase, the game's text.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

import cardlang.attribution as attribution
import cardlang.resolve as R
from cardlang.ast import nodes as n
from cardlang.diagnostics import LINE_KINDS, DiagnosticBag, DiagnosticError, Route, Span, line_kind
from cardlang.expand import expand
from cardlang.parse import parse_library, parse_text
from cardlang.stdlib.rules import stdlib_library
from cardlang.typecheck import typecheck
import tests.test_library_boundary_ledger as L
from tests.test_library_attribution import _cells
from tests.test_rejections import case_paths

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE = _ROOT / "cardlang"
_STDLIB_FILE = "cardlang/stdlib/rules.cardlang"

_LIBRARY = (
    "library boundarylib {\n"
    "  requires { score[player] : Integer }\n"
    "  procedure libp(p : Player) {\n"
    "    score[p] += 1\n"
    "  }\n"
    "}\n"
)


def _game(body: str) -> str:
    return (
        "game Notes {\n"
        "  players: 2\n"
        "  cards: standard52\n"
        "  max_length: 200\n"
        "  ranking: aces high\n"
        "  uses boundarylib\n"
        "  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase setup { shuffle deck  deal 5 cards from deck to each hand }\n"
        f"  phase play {{ {body} }}\n"
        "  winner: highest score\n"
        "}\n"
    )


_ROUND = (
    "active_rules: [MustFollowSuit] run libp(0) round play_to_trick from 0 over "
    "all players source hand into pile winner highest_of_led_suit"
)
_GAME = _game(_ROUND)
# A clean Library Witness that runs the procedure, and one that never does.
_REACHES = _GAME
_ELSEWHERE = _game(
    "round play_to_trick from 0 over all players source hand into pile "
    "winner highest_of_led_suit"
)


# --- the axes ------------------------------------------------------------------

# The game the step is handed: the spliced game, at the raise of the checks
# before the splice; the resolved game, at the raises after it; the expanded
# game, at the deck capacity gate's.
STAGES = ("before-splice", "after-splice", "after-expand")
# How the step tells a refusal: at the game text of its crossing; on the
# `uses` line by its certificate; in the library's file, unproven; in the
# library's file, a definition no clean Library Witness reaches; or where a
# check stood it, at the game's text, on library text.
TELLINGS = ("route", "certificate", "unproven", "unreached", "stands-on")
# Where the refused text lives: a family library's procedure, the standard
# library's rule, or a family library's text outside any definition (its
# contract).
LIVES = ("family", "stdlib", "outside")

# The raise each stage is handed its game at: (module, function).
_STAGE_RAISES = {
    "before-splice": ("resolve", "resolve"),
    "after-splice": ("typecheck", "typecheck"),
    "after-expand": ("deckcheck", "check_capacity"),
}


@dataclass(frozen=True)
class Told:
    """Where a cell's refusal is told -- `game` (the crossing's game text),
    `uses` (the `uses` line) or `library` (the library's file) -- whether a
    note names the library line, and the warning on the `uses` line, if
    any."""

    primary: str
    note: bool
    warning: str | None = None


_GAME_TOLD = Told("game", note=True)
_USES_TOLD = Told("uses", note=True)
_UNPROVEN_TOLD = Told("library", note=False, warning=attribution.UNPROVEN_PHRASE)
_UNREACHED_TOLD = Told("library", note=False, warning=attribution.UNREACHED_PHRASE)
_STAYS = Told("library", note=False)

# lives -> telling -> what the step tells, at every stage.
EXPECTED: dict[str, dict[str, Told]] = {
    "family": {
        "route": _GAME_TOLD,
        "certificate": _USES_TOLD,
        "unproven": _UNPROVEN_TOLD,
        "unreached": _UNREACHED_TOLD,
        "stands-on": _GAME_TOLD,
    },
    "stdlib": {
        "route": _GAME_TOLD,
        "certificate": _STAYS,
        "unproven": _STAYS,
        "unreached": _STAYS,
        "stands-on": _GAME_TOLD,
    },
    "outside": {
        "route": _GAME_TOLD,
        "certificate": _STAYS,
        "unproven": _UNPROVEN_TOLD,
        "unreached": _STAYS,
        "stands-on": _GAME_TOLD,
    },
}


def test_the_stages_are_the_raises() -> None:
    """Every raise of a pass that hands the step its game is a stage.

    red under: call `raise_if_errors` in `ir.emit`."""
    found: set[tuple[str, str]] = set()
    for module in ("resolve", "typecheck", "expand", "deckcheck", "ir"):
        tree = ast.parse((_PACKAGE / f"{module}.py").read_text())
        for top in tree.body:
            for nd in ast.walk(top):
                if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) and nd.func.id == "raise_if_errors":
                    found.add((module, getattr(top, "name", "<module>")))
    assert found == set(_STAGE_RAISES.values())


# --- the cell -------------------------------------------------------------------


def _spliced(monkeypatch: pytest.MonkeyPatch, stage: str, witnesses: tuple[str, ...]) -> n.Game:
    lib = parse_library(_LIBRARY, L._LIB_FILE)
    monkeypatch.setattr(R, "library_names", lambda: frozenset({L._LIB}))
    monkeypatch.setattr(R, "load_library", lambda name: lib)
    sources = tuple((f"witness-{at}.cardlang", text) for at, text in enumerate(witnesses))
    monkeypatch.setattr(attribution, "witness_sources", lambda name: sources)
    parsed = parse_text(_GAME, L._GAME_FILE)
    if stage == "before-splice":
        game, _rules = getattr(R, "_apply_uses")(parsed, DiagnosticBag())
        return game  # type: ignore[no-any-return]
    game = typecheck(R.resolve(parsed))
    return expand(game) if stage == "after-expand" else game


def _refused(lives: str) -> tuple[Span, str]:
    """The library text a cell refuses, and the definition holding it in the
    designer's words."""
    if lives == "family":
        proc = parse_library(_LIBRARY, L._LIB_FILE).procedures[0]
        span = proc.body[0].span
        where = "procedure `libp`"
    elif lives == "stdlib":
        rule = next(r for r in stdlib_library().rules if r.name == "MustFollowSuit")
        assert rule.applies_when is not None
        span = rule.applies_when.span
        where = "rule `MustFollowSuit`"
    else:
        span = parse_library(_LIBRARY, L._LIB_FILE).requires[0].span
        where = f"library '{L._LIB}'"
    assert span is not None
    return span, where


def _game_text(game: n.Game) -> Span:
    """The game text the cell's crossing leaves by: the `run` of the
    procedure, or the block it became."""
    for nd in R._walk(game):
        if isinstance(nd, (n.RunStmt, n.Block)) and nd.span is not None:
            return nd.span
    raise AssertionError("the game runs no procedure")


_WITNESSES = {
    "route": (), "certificate": (_REACHES,), "unproven": (), "unreached": (_ELSEWHERE,),
    "stands-on": (),
}


def _told(monkeypatch: pytest.MonkeyPatch, stage: str, telling: str, lives: str) -> list[str]:
    game = _spliced(monkeypatch, stage, _WITNESSES[telling])
    span, _where = _refused(lives)
    at = _game_text(game)
    bag = DiagnosticBag()
    if telling == "route":
        library = "stdlib" if lives == "stdlib" else L._LIB
        bag.error("the probe refuses this", span, route=Route("call", at, library, "libp"))
    elif telling == "stands-on":
        bag.error("the probe refuses this", at, stands_on=span)
    else:
        bag.error("the probe refuses this", span)
    uses = parse_text(_GAME, L._GAME_FILE).uses if stage == "before-splice" else ()
    with pytest.raises(DiagnosticError) as exc:
        attribution.raise_if_errors(bag, game, uses)
    return L._rendered(exc.value)


def _cell_ids() -> list[tuple[str, str, str]]:
    return [(s, t, v) for s in STAGES for t in TELLINGS for v in LIVES]


def _note_names(stage: str, lives: str, where: str) -> str:
    """What a cell's note names: the definition, or, for the standard
    library's rule before the splice brings it in, the standard library."""
    return "the standard library" if (stage, lives) == ("before-splice", "stdlib") else where


def _location(line: str) -> tuple[str, int]:
    path, line_no, _rest = line.split(":", 2)
    return path, int(line_no)


@pytest.mark.parametrize(("stage", "telling", "lives"), _cell_ids())
def test_a_refusal_is_told_with_its_library_line(
    monkeypatch: pytest.MonkeyPatch, stage: str, telling: str, lives: str
) -> None:
    expected = EXPECTED[lives][telling]
    span, where = _refused(lives)
    lines = _told(monkeypatch, stage, telling, lives)
    text = "\n".join(lines)
    errors = [ln for ln in lines if line_kind(ln) == "error"]
    notes = [ln for ln in lines if line_kind(ln) == "note"]
    warnings = [ln for ln in lines if line_kind(ln) == "warning"]
    assert len(errors) == 1, text
    uses_at = f"{L._GAME_FILE}:{L._line(_GAME, 'uses boundarylib')}:"
    primary = errors[0]
    if expected.primary == "library":
        assert _location(primary) == (span.source_name, span.line), text
    elif expected.primary == "uses":
        assert primary.startswith(uses_at), text
    else:
        assert primary.startswith(f"{L._GAME_FILE}:") and not primary.startswith(uses_at), text
    if expected.note:
        assert len(notes) == 1, text
        assert _location(notes[0]) == (span.source_name, span.line), text
        assert _note_names(stage, lives, where) in notes[0], text
    else:
        assert notes == [], text
    if expected.warning is None:
        assert warnings == [], text
    else:
        assert len(warnings) == 1 and warnings[0].startswith(uses_at), text
        assert expected.warning in warnings[0], text
        if expected.warning == attribution.UNREACHED_PHRASE:
            assert where in warnings[0], text


@pytest.mark.parametrize(("stage", "telling", "lives"), _cell_ids())
def test_who_is_told_never_changes_what_is_refused(
    monkeypatch: pytest.MonkeyPatch, stage: str, telling: str, lives: str
) -> None:
    """The step tells exactly the refusals it is handed, as the step that
    tells every refusal where it stands does: the warning and the note refuse
    nothing.

    red under: have `attribution.tell` drop a refusal it notes."""
    told = [ln for ln in _told(monkeypatch, stage, telling, lives) if line_kind(ln) == "error"]
    with monkeypatch.context() as mp:
        mp.setattr(attribution, "tell", attribution.keep_where_written)
        kept = [ln for ln in _told(mp, stage, telling, lives) if line_kind(ln) == "error"]
    assert len(told) == len(kept) == 1


# --- every rendered line is an error, a warning or a note -----------------------


def test_every_rendered_line_has_a_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """red under: render a note as `info:`."""
    assert LINE_KINDS == ("error", "warning", "note")
    for key, cell in _cells().items():
        for line in L._cell_bag(monkeypatch, cell):
            assert line_kind(line) in LINE_KINDS, (key, line)


# --- every ledger cell told in the game's file names the library's line ---------


def _grouped(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Each error or warning line with the note lines under it."""
    out: list[tuple[str, list[str]]] = []
    for line in lines:
        if line_kind(line) == "note" and out:
            out[-1][1].append(line)
        else:
            out.append((line, []))
    return out


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="the note is unbuilt")
def test_every_ledger_refusal_told_in_the_game_names_its_library_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read off the rendered verdict of every cell the step can touch.

    red under: have `attribution.tell` drop the note of a routed refusal."""
    missing: list[str] = []
    for key, cell in _cells().items():
        for line, notes in _grouped(L._cell_bag(monkeypatch, cell)):
            if line_kind(line) != "error":
                continue
            in_library = line.startswith((L._LIB_FILE, _STDLIB_FILE))
            library_notes = [nt for nt in notes if nt.startswith((L._LIB_FILE, _STDLIB_FILE))]
            if in_library and notes:
                missing.append(f"{key}: a note under a refusal in the library's file")
            if cell.owner in (L.GAME, L.USES) and len(library_notes) != 1:
                missing.append(f"{key}: {len(library_notes)} library notes")
    assert missing == []


# --- the rejection goldens ------------------------------------------------------


def test_no_golden_tells_a_library_refusal_in_the_librarys_file_unwarned() -> None:
    """A rejection golden of a game that `uses` a library names a library file
    as its refusal's location only beside the `uses`-line warning that says
    why.

    red under: rewrite a library-importing golden's first line to a
    `docs/libraries/` location."""
    for path in case_paths():
        if "libraries" in path.parts or "uses " not in path.read_text():
            continue
        lines = path.with_suffix(".expected").read_text().splitlines()
        primaries = [ln for ln in lines if line_kind(ln) == "error" and ln.startswith("docs/libraries/")]
        warned = any(
            line_kind(ln) == "warning"
            and (attribution.UNPROVEN_PHRASE in ln or attribution.UNREACHED_PHRASE in ln)
            for ln in lines
        )
        assert not primaries or warned, path.name


# --- the step alone makes a note ------------------------------------------------


def test_only_the_step_makes_a_note() -> None:
    """red under: construct a `Note` in resolve."""
    makers: set[str] = set()
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for nd in ast.walk(tree):
            if isinstance(nd, ast.Call) and isinstance(nd.func, (ast.Name, ast.Attribute)):
                name = nd.func.id if isinstance(nd.func, ast.Name) else nd.func.attr
                if name == "Note":
                    makers.add(path.relative_to(_PACKAGE).as_posix())
    assert makers <= {"attribution.py"}
