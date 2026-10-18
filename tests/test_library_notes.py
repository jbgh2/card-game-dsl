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
                 text -- renders one `note:` at each library line it stands
                 on, once for a refusal raised at several and told once; a
                 refusal left in the library's file renders no
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
                 certified nowhere and its note names its library. A check
                 that hands the step a node with no span hands it no line,
                 and the refusal carries no note.
registry:        stages: `STAGES`, pinned against the raises after the splice
                 (`test_the_stages_are_the_raises`); tellings: `TELLINGS`;
                 rendered line kinds: `cardlang.diagnostics.LINE_KINDS`;
                 ledger cells: tests/test_library_attribution.py `_cells`;
                 rejection goldens: tests/test_rejections.py `case_paths`.
does not prove:  that the library line a check names is the one its sentence
                 means: a check standing a refusal at the game's text hands
                 the step the library text it read, and the note is that
                 line.

Class ledger (surface-totality-audit Step 2b)
---------------------------------------------
finding:    the boundary ledger's routed cell `game-to-library-0` renders as
            one line at the Trick Order row, naming `libf` and never its
            line (issue #894).
class:      every refusal told in the game's file that stands on library
            text, whichever way it got there, at every raise the step is
            handed, and every refusal standing in a spliced procedure body
            after `expand`.
members:    the grid's cells, crossed from `STAGES`, `TELLINGS` and `LIVES`;
            and every ledger cell `_cells` holds whose owner is the game's
            text or its `uses` line.
covered:    all of them.
residual:   none on the step. Beside it, the checks that refuse the game's
            text naming library text and hand the step nothing: issue #912;
            the deck capacity gate's phase refusal: issue #911. The standard
            library's own load is refused to the language's maintainers
            before any game, outside the step, and no step input it might
            carry is rendered.
why missed: the step's ledger and the destinations count both read "owned by
            the game's text" as "moved there by the step", and the step's
            pins asserted only where the primary line stands, never the
            whole rendered verdict against the library line. Measured
            2026-10-18 at 7e0f3852: of the 263 ledger cells owned by the
            game's text or the `uses` line, 198 were moved by the step and 65
            were stood at the game's text by five checks that name the
            library definition in their sentence and held no place to hand
            the step its span -- the hidden-read walk, the clause gates, the
            card-offering check, the implicit-pool check and the scoped-read
            offering check. Inside the step, both de-duplications -- the
            step's, keyed on the told sentence and place, and the hidden-read
            walk's, keyed on the crossing's game text -- kept the first
            refusal's library line and dropped the rest, and the raise before
            the splice was handed no library rule to name.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
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


# --- what the step keeps when it moves and merges refusals ----------------------

_TWICE = (
    "library boundarylib {\n"
    "  requires { secret[player] : HiddenPile<player>  hand[player] : Hand<player>  pile : Discard }\n"
    "  procedure libpr(k : Integer) {\n"
    "    move chosen k cards from hand to pile\n"
    "    move chosen k cards from hand to pile\n"
    "  }\n"
    "}\n"
)


def _hidden_run(body: str) -> str:
    return (
        "game Boundary {\n"
        "  players: 3\n"
        "  cards: standard52\n"
        "  max_length: 200\n"
        "  ranking: aces high\n"
        "  uses boundarylib\n"
        "  zones { deck : Deck  hand[player] : Hand<player>  pile : Discard  secret[player] : HiddenPile<player> }\n"
        "  state { score[player] : Integer = 0  leader : Player = 0  dealer : Player = 1 }\n"
        "  phase setup { shuffle deck  deal 5 cards from deck to each hand }\n"
        f"  phase play {{ {body} }}\n"
        "  winner: highest score\n"
        "}\n"
        "function high(p : Player) = number of cards in secret[p] where rank_value(card) > 3\n"
    )


def test_one_refusal_on_two_library_lines_names_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run whose argument reads hidden cards, for two decisions of the
    procedure's body, is one refusal at the run, standing on both lines."""
    game = _hidden_run("as leader { run libpr(high(dealer)) }")
    lines = L._bag(monkeypatch, _TWICE, game)
    text = "\n".join(lines)
    assert len(L._errors(lines)) == 1, text
    noted = {_location(ln) for ln in lines if line_kind(ln) == "note"}
    assert noted == {(L._LIB_FILE, 4), (L._LIB_FILE, 5)}, text


def test_merged_refusals_keep_every_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step tells two refusals with one sentence at one place once, with
    each library line either stood on, and one note for a line both stand
    on."""
    game = _spliced(monkeypatch, "after-splice", ())
    span, _where = _refused("family")
    same_line = replace(span, start=span.start + 1)
    other, _ = _refused("outside")
    at = _game_text(game)
    bag = DiagnosticBag()
    for library_at in (span, same_line, other):
        bag.error("the probe refuses this", library_at, route=Route("call", at, L._LIB, "libp"))
    attribution.tell(bag, game)
    assert len(bag.items) == 1
    assert [note.span for note in bag.items[0].notes] == [span, other]


def test_a_moved_refusal_standing_at_game_text_keeps_what_it_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A routed refusal whose own span is the game's text is noted at the
    library text its check reached."""
    game = _spliced(monkeypatch, "after-splice", ())
    span, where = _refused("family")
    at = _game_text(game)
    bag = DiagnosticBag()
    bag.error("the probe refuses this", at, route=Route("call", at, L._LIB, "libp"), stands_on=span)
    attribution.tell(bag, game)
    (told,) = bag.items
    assert [note.span for note in told.notes] == [span]
    assert where in told.notes[0].message


_RULE_LIBRARY = (
    "library boundarylib {\n"
    "  rule librule {\n"
    "    constrains: play_to_trick\n"
    "    demands: cards in hand where rank_value(card) > 3\n"
    "    if_impossible: hand\n"
    "  }\n"
    "}\n"
)


def test_a_refusal_before_the_splice_names_the_library_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clause gate refusing a library rule the game activates is told on
    the `uses` line before the rule is spliced, and its note names the
    rule."""
    game = (
        "game Boundary {\n"
        "  players: 4\n"
        "  cards: standard52\n"
        "  max_length: 200\n"
        "  uses boundarylib\n"
        "  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase setup { shuffle deck  deal 5 cards from deck to each hand }\n"
        "  phase play { active_rules: [librule] round play_to_trick from 0 over all players "
        "source hand into pile winner highest_of_led_suit }\n"
        "  winner: highest score\n"
        "}\n"
    )
    lines = L._bag(monkeypatch, _RULE_LIBRARY, game)
    text = "\n".join(lines)
    notes = [ln for ln in lines if line_kind(ln) == "note"]
    assert any("rank_value" in ln for ln in L._errors(lines)), text
    assert len(notes) == 1 and "rule `librule`" in notes[0], text


def test_no_refusal_leaves_the_step_with_its_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    """red under: have `attribution._bare` keep `stands_on`."""
    for stage, telling, lives in _cell_ids():
        with monkeypatch.context() as mp:
            game = _spliced(mp, stage, _WITNESSES[telling])
            span, _where = _refused(lives)
            bag = DiagnosticBag()
            bag.error("the probe refuses this", _game_text(game), stands_on=span)
            bag.error("the probe refuses this", span, route=Route("call", None, L._LIB, "libp"))
            bag.error("the probe refuses this too", span, for_game="the game's sentence")
            attribution.tell(bag, game)
        for d in bag.items:
            assert (d.route, d.for_game, d.stands_on) == (None, None, None), (stage, telling, lives)


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
            noted_lines = [_location(nt) for nt in library_notes]
            if cell.owner in (L.GAME, L.USES) and not library_notes:
                missing.append(f"{key}: no library note")
            if len(set(noted_lines)) != len(notes):
                missing.append(f"{key}: a note outside the library, or two on one line")
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
