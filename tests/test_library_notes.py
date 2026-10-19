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
                 library, one warning on the `uses` line says so; a refusal
                 of the game's text or its `uses` line naming library text
                 renders a note at each library line it names; a refusal's
                 notes are every distinct library line it stands on --
                 where it was raised, what its check handed the step, what
                 its sentences cite, and, at game text naming a library
                 definition or provided state (the innermost naming node at
                 the refusal, or one whose argument stands there) or at a
                 template argument substituted into one, that definition;
                 no check but the step spells a library's name or a
                 definition's library words into a string, and a citation
                 handed no line says why; every rendered line is an error, a
                 warning or a note; and who is told never changes what is
                 refused.
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
                 and the refusal carries no note. Library to game, one cell
                 per check that refuses the game's text or its `uses` line
                 naming library text (`NAMED`), two libraries where the check
                 compares two, a template argument the game wrote,
                 substituted into a library rule, at its clause and inside a
                 nested one, a game's read of provided state, and a game's
                 call and `run` of a library definition refused against its
                 signature, at the call and at an argument; each way of
                 standing on library text crossed with another
                 (`_UNION_CELLS`);
                 beside them, every refusal
                 naming a library that the boundary ledger's library-to-game
                 witnesses raise in the game's file. The scoped-read
                 containment's arms on a library move type, offered nowhere
                 and run outside the phase, are declaration-gate cells and
                 so ledger cells above. A sentence naming no library text --
                 a Hosted Poll binder shadowing "a function", a removal of a
                 rule this phase never added -- refuses the game's own text,
                 and its cell is the game's. The spelling census reads every
                 string of the package outside the step, f-string pieces and
                 the operands of an addition, its docstrings and the messages
                 of an installation's own errors excepted.
registry:        stages: `STAGES`, pinned against the raises after the splice
                 (`test_the_stages_are_the_raises`); tellings: `TELLINGS`;
                 rendered line kinds: `cardlang.diagnostics.LINE_KINDS`;
                 ledger cells: tests/test_library_attribution.py `_cells`;
                 library-to-game witnesses:
                 tests/test_library_boundary_ledger.py
                 `_library_to_game_witnesses`; the census's modules: the
                 `cardlang/` glob; rejection goldens: tests/test_rejections.py
                 `case_paths`.
does not prove:  that the library line a check names is the one its sentence
                 means: a check standing a refusal at the game's text hands
                 the step the library text it read, and the note is that
                 line. Nor that a sentence naming a library definition by its
                 bare name, with no library word, carries its line where it
                 stands at text other than the game's naming of it: the
                 census reads spellings, and such a sentence has none to
                 read, so its cell here is the check.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import cardlang.attribution as attribution
import cardlang.resolve as R
from cardlang.ast import nodes as n
from cardlang.deckcheck import check_capacity
from cardlang.diagnostics import (
    LINE_KINDS,
    Diagnostic,
    DiagnosticBag,
    DiagnosticError,
    Route,
    Span,
    line_kind,
)
from cardlang.expand import expand
from cardlang.parse import parse_library, parse_text
from cardlang.stdlib.rules import stdlib_library
from cardlang.typecheck import typecheck
import tests.test_library_boundary_ledger as L
import tests.test_library_declaration_gates as D
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
        # Told at the game's `run` of `libp`, the refusal stands on `libp`
        # too; once expanded, the block the run became names nothing.
        runs = expected.primary == "game" and stage != "after-expand"
        libp = _line_of(_LIBRARY, "procedure libp")
        want = {(span.source_name, span.line)} | ({(L._LIB_FILE, libp)} if runs else set())
        assert {_location(nt) for nt in notes} == want, text
        refused = next(nt for nt in notes if _location(nt) == (span.source_name, span.line))
        assert _note_names(stage, lives, where) in refused, text
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
    procedure's body, is one refusal at the run, standing on both lines and
    on the procedure the run names."""
    game = _hidden_run("as leader { run libpr(high(dealer)) }")
    lines = L._bag(monkeypatch, _TWICE, game)
    text = "\n".join(lines)
    assert len(L._errors(lines)) == 1, text
    noted = {_location(ln) for ln in lines if line_kind(ln) == "note"}
    assert noted == {(L._LIB_FILE, 3), (L._LIB_FILE, 4), (L._LIB_FILE, 5)}, text


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
    libp = next(p.span for p in game.procedures if p.name == "libp")
    assert [note.span for note in bag.items[0].notes] == [span, libp, other]


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
    libp = next(p.span for p in game.procedures if p.name == "libp")
    assert [note.span for note in told.notes] == [span, libp]
    assert where in told.notes[0].message


# Every library line a refusal stands on, by each way it can stand on one:
# where it was raised, what its check handed the step, what its sentence or
# its game's sentence cites, and the definition the game text it is told at
# names. Each cell crosses two of them; its notes are their union.
def _union_cell(name: str, game: n.Game) -> tuple[DiagnosticBag, set[int]]:
    family, _ = _refused("family")
    outside, _ = _refused("outside")
    at = _game_text(game)
    libp = next(p for p in game.procedures if p.name == "libp")
    assert libp.span is not None
    route = Route("call", at, L._LIB, "libp")
    bag = DiagnosticBag()
    if name == "raised-and-handed":
        bag.error("the probe refuses this", family, route=route, stands_on=outside)
        return bag, {family.line, outside.line, libp.span.line}
    if name == "raised-and-cited-for-the-game":
        sentence = attribution.cite_library(L._LIB, outside) + " refuses this"
        bag.error("the probe refuses this", family, route=route, for_game=sentence)
        return bag, {family.line, outside.line, libp.span.line}
    if name == "named-and-handed-the-game's-text":
        bag.error("the probe refuses this", at, stands_on=at)
        return bag, {libp.span.line}
    assert name == "named-and-handed"
    bag.error("the probe refuses this", at, stands_on=outside)
    return bag, {libp.span.line, outside.line}


_UNION_CELLS = (
    "raised-and-handed", "raised-and-cited-for-the-game", "named-and-handed-the-game's-text",
    "named-and-handed",
)


@pytest.mark.parametrize("name", _UNION_CELLS)
def test_a_refusals_notes_are_every_library_line_it_stands_on(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    game = _spliced(monkeypatch, "after-splice", ())
    bag, want = _union_cell(name, game)
    attribution.tell(bag, game)
    (told,) = bag.items
    assert {note.span.line for note in told.notes} == want
    assert all(note.span.source_name == L._LIB_FILE for note in told.notes)


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


_TWO_DEFINITIONS = (
    "library boundarylib {\n"
    "  function high(c : Card) = rank_value(c) > 3\n"
    "  function low(c : Card) = rank_value(c) < 3\n"
    "}\n"
)


def test_a_gate_refusing_two_definitions_notes_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clause gate's one refusal naming two library definitions notes each
    one's line.

    red under: have `_check_library_clause_gates` hand the step only the
    first construct it refuses."""
    game = (
        "game Boundary {\n"
        "  players: 4\n"
        "  cards: standard52\n"
        "  max_length: 200\n"
        "  uses boundarylib\n"
        "  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase setup { shuffle deck  deal 5 cards from deck to each hand }\n"
        "  phase play { round play_to_trick from 0 over all players "
        "source hand into pile winner highest_of_led_suit }\n"
        "  winner: highest score\n"
        "}\n"
    )
    lines = L._bag(monkeypatch, _TWO_DEFINITIONS, game)
    text = "\n".join(lines)
    notes = [ln for ln in lines if line_kind(ln) == "note"]
    assert any("rank_value" in ln for ln in L._errors(lines)), text
    assert sorted(_location(ln)[1] for ln in notes) == [2, 3], text


def _noted_lines(lines: list[str]) -> list[int]:
    return sorted(_location(ln)[1] for ln in lines if line_kind(ln) == "note")


def _line_of(text: str, needle: str) -> int:
    return next(i for i, ln in enumerate(text.splitlines(), start=1) if needle in ln)


def test_one_move_offered_by_two_library_lines_notes_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A game's Card move type over a `hand` hiding its cards, offered by two
    library procedures, is refused once at the game's move type and noted at
    each offer.

    red under: have `_check_implicit_pools` hand the step only the first
    library offer."""
    cell = D._card_pool_cell("procedures", "game", "hiding-Burn", False)
    library = cell.library.replace(
        "procedure lask(p : Player) { offer to p one of [gplay] }",
        "procedure lask(p : Player) { offer to p one of [gplay] }\n"
        "  procedure lask2(p : Player) { offer to p one of [gplay] }",
    )
    game = cell.game.replace("as 0 { run lask(0) }", "as 0 { run lask(0) }  as 1 { run lask2(1) }")
    lines = L._bag(monkeypatch, library, game)
    text = "\n".join(lines)
    assert any("does not show its owner the cards" in ln for ln in L._errors(lines)), text
    want = [_line_of(library, "procedure lask("), _line_of(library, "procedure lask2(")]
    assert _noted_lines(lines) == want, text


def test_one_offer_of_two_library_card_moves_notes_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A game's offer of two library Card move types is refused once at the
    offer and noted at each move type.

    red under: have `_check_card_offering` hand the step only the first
    library move type."""
    cell = D._two_card_moves_cell("game", "library-library")
    lines = L._bag(monkeypatch, cell.library, cell.game)
    text = "\n".join(lines)
    assert any("indistinguishable" in ln for ln in L._errors(lines)), text
    want = [_line_of(cell.library, "move_type lplay("), _line_of(cell.library, "move_type lplay2(")]
    assert _noted_lines(lines) == want, text


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
            assert (d.route, d.for_game, d.stands_on) == (None, None, ()), (stage, telling, lives)


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


# --- library to game: a refusal of the game's text naming library text ---------
#
# A check refusing the game's text or its `uses` line for library text the game
# meets names that text in its sentence, and the text's line is its note. One
# cell per check that names library text there; two libraries where the check
# compares two.

_OTHER = "otherlib"
_STDLIB_RULES = "cardlang/stdlib/rules.cardlang"


def _host(
    uses: tuple[str, ...] = (L._LIB,),
    zones: str = "",
    state: str = "score[player] : Integer = 0",
    body: str | None = None,
    rules: str = "",
    extra: str = "",
) -> str:
    play = body or (
        f"{rules}round play_to_trick from 0 over all players source hand into pile "
        "winner highest_of_led_suit"
    )
    return (
        "game Boundary {\n"
        "  players: 2\n"
        "  cards: standard52\n"
        "  max_length: 200\n"
        "  ranking: aces high\n"
        + "".join(f"  uses {u}\n" for u in uses)
        + f"  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile {zones} }}\n"
        f"  state {{ {state} }}\n"
        "  phase setup { shuffle deck  deal 5 cards from deck to each hand }\n"
        f"  phase play {{ {play} }}\n"
        "  winner: highest score\n"
        "}\n"
        f"{extra}"
    )


def _lib(name: str, body: str) -> str:
    return f"library {name} {{\n{body}\n}}\n"


_TRICK = "round play_to_trick from 0 over all players source hand into pile winner highest_of_led_suit"
_ROW_G = "  requires { g(c : Card) : Integer }\n  function h(c : Card) = g(c)"
_TEMPLATE = (
    "  rule lr(s : Suit) {\n"
    "    constrains: play_to_trick\n"
    "    demands: cards in hand where card.suit is s\n"
    "    if_impossible: hand\n"
    "  }"
)


@dataclass(frozen=True)
class Named:
    """A refusal of the game's text naming library text: the libraries by
    name, the game, the game text it is told at (`at`, a needle of the game's
    line), words its sentence carries (`says`), and the library lines its
    notes stand on, as (library, needle of the line)."""

    libraries: tuple[tuple[str, str], ...]
    game: str
    at: str
    says: str
    notes: tuple[tuple[str, str], ...]


NAMED: dict[str, Named] = {
    "definition-collision": Named(
        ((L._LIB, _lib(L._LIB, "  function f(c : Card) = rank_value(c)")),),
        _host(extra="function f(c : Card) = rank_value(c)\n"),
        "function f(c : Card)", "is defined by this game and also by",
        ((L._LIB, "function f("),),
    ),
    "two-libraries-define": Named(
        (
            (L._LIB, _lib(L._LIB, "  function f(c : Card) = rank_value(c)")),
            (_OTHER, _lib(_OTHER, "  function f(c : Card) = rank_value(c)")),
        ),
        _host(uses=(L._LIB, _OTHER)),
        f"uses {_OTHER}", "is defined by both",
        ((L._LIB, "function f("), (_OTHER, "function f(")),
    ),
    "brought-in-over-game-name": Named(
        ((L._LIB, _lib(L._LIB, "  function seen(c : Card) = rank_value(c)")),),
        _host(zones="seen : Discard"),
        "seen : Discard", "brings in function 'seen'",
        ((L._LIB, "function seen("),),
    ),
    "brought-in-over-another-contract": Named(
        (
            (L._LIB, _lib(L._LIB, "  requires { score[player] : Integer }\n  procedure g() { score[0] += 1 }")),
            (_OTHER, _lib(_OTHER, _ROW_G)),
        ),
        _host(uses=(L._LIB, _OTHER), extra="function g(c : Card) = rank_value(c)\n"),
        f"uses {L._LIB}", "has this game define 'g'",
        ((L._LIB, "procedure g("), (_OTHER, "requires { g(")),
    ),
    "two-libraries-provide": Named(
        (
            (L._LIB, _lib(L._LIB, "  state { tally : Integer = 0 }")),
            (_OTHER, _lib(_OTHER, "  state { tally : Integer = 0 }")),
        ),
        _host(uses=(L._LIB, _OTHER)),
        f"uses {_OTHER}", "is provided by both",
        ((L._LIB, "tally"), (_OTHER, "tally")),
    ),
    "game-declares-provided": Named(
        ((L._LIB, _lib(L._LIB, "  state { tally : Integer = 0 }")),),
        _host(state="score[player] : Integer = 0  tally : Integer = 0"),
        "tally : Integer = 0", "is declared by this game and also provided",
        ((L._LIB, "tally"),),
    ),
    "requires-what-another-provides": Named(
        (
            (L._LIB, _lib(L._LIB, "  state { tally : Integer = 0 }")),
            (_OTHER, _lib(_OTHER, "  requires { tally : Integer }\n  procedure bump() { tally += 1 }")),
        ),
        _host(uses=(L._LIB, _OTHER)),
        f"uses {_OTHER}", "which library 'boundarylib' provides",
        ((_OTHER, "requires { tally"), (L._LIB, "tally")),
    ),
    "write-of-provided-state": Named(
        ((L._LIB, _lib(L._LIB, "  state { tally : Integer = 0 }")),),
        _host(body=f"tally := 1  {_TRICK}"),
        "tally := 1", "cannot write 'tally'",
        ((L._LIB, "tally"),),
    ),
    "chosen-binder-over-provided-state": Named(
        ((L._LIB, _lib(L._LIB, "  state { tally : Integer = 0 }")),),
        _host(body=f"let tally = 1  {_TRICK}"),
        "let tally = 1", "binder 'tally' is spelled like state",
        ((L._LIB, "tally"),),
    ),
    "unchosen-binder-over-provided-state": Named(
        ((L._LIB, _lib(L._LIB, "  state { card : Integer = 0 }")),),
        _host(body=f"score[0] := number of cards in hand where rank_value(card) > 3  {_TRICK}"),
        "score[0] := number", "and this form binds 'card'",
        ((L._LIB, "card : Integer"),),
    ),
    "requires-zone-undeclared": Named(
        ((L._LIB, _lib(L._LIB, "  requires { stock : Discard }")),),
        _host(),
        f"uses {L._LIB}", "requires zone `stock : Discard`",
        ((L._LIB, "requires {"),),
    ),
    "requires-state-undeclared": Named(
        ((L._LIB, _lib(L._LIB, "  requires { tally : Integer }")),),
        _host(),
        f"uses {L._LIB}", "requires state `tally : Integer`",
        ((L._LIB, "requires {"),),
    ),
    "requires-state-of-another-type": Named(
        ((L._LIB, _lib(L._LIB, "  requires { score[player] : Boolean }")),),
        _host(),
        f"uses {L._LIB}", "but game 'Boundary' declares it as `Integer`",
        ((L._LIB, "requires {"),),
    ),
    "requires-function-undefined": Named(
        ((L._LIB, _lib(L._LIB, _ROW_G)),),
        _host(),
        f"uses {L._LIB}", "which game 'Boundary' does not define",
        ((L._LIB, "requires {"),),
    ),
    "contract-result-type": Named(
        ((L._LIB, _lib(L._LIB, "  requires { g(c : Card) : Integer }\n  function h(c : Card) = g(c) > 2")),),
        _host(extra="function g(c : Card) = c.suit is hearts\n"),
        f"uses {L._LIB}", "returning Boolean",
        ((L._LIB, "requires {"),),
    ),
    "card-field-the-deck-lacks": Named(
        ((L._LIB, _lib(L._LIB, "  function h(c : Card) = c.colour")),),
        _host(),
        f"uses {L._LIB}", "reads the field `colour`",
        ((L._LIB, "c.colour"),),
    ),
    "answer-reads-a-call-site-pronoun": Named(
        ((L._LIB, _lib(L._LIB, _ROW_G)),),
        _host(extra="function g(c : Card) = score[actor]\n"),
        "function g(c : Card)", "calls it under its contract",
        ((L._LIB, "requires {"),),
    ),
    "answer-reads-the-play-source": Named(
        ((L._LIB, _lib(L._LIB, (
            "  requires { g(c : Card) : Integer }\n"
            "  rule lr {\n    constrains: play_to_trick\n"
            "    demands: cards in hand where g(card) > 0\n    if_impossible: hand\n  }"
        ))),),
        _host(rules="active_rules: [lr] ", extra="function g(c : Card) = number of cards in hand\n"),
        "function g(c : Card)", "calls it under its contract",
        ((L._LIB, "requires {"), (L._LIB, "rule lr {")),
    ),
    "recursion-through-library-text": Named(
        ((L._LIB, _lib(L._LIB, _ROW_G)),),
        _host(extra="function g(c : Card) = h(c)\n"),
        "function g(c : Card)", "is recursive through",
        ((L._LIB, "function h("),),
    ),
    "template-without-arguments": Named(
        ((L._LIB, _lib(L._LIB, _TEMPLATE)),),
        _host(rules="active_rules: [lr] "),
        "active_rules: [lr]", "is parameterized",
        ((L._LIB, "rule lr("),),
    ),
    "template-of-another-arity": Named(
        ((L._LIB, _lib(L._LIB, _TEMPLATE)),),
        _host(rules="active_rules: [lr(hearts, spades)] "),
        "active_rules: [lr(", "argument(s), got 2",
        ((L._LIB, "rule lr("),),
    ),
    "template-argument-not-a-suit": Named(
        ((L._LIB, _lib(L._LIB, _TEMPLATE)),),
        _host(rules="active_rules: [lr(score)] "),
        "active_rules: [lr(", "must be a suit literal",
        ((L._LIB, "rule lr("),),
    ),
    "rule-taking-no-arguments": Named(
        ((L._LIB, _lib(L._LIB, (
            "  rule lr {\n    constrains: play_to_trick\n"
            "    demands: cards in hand where rank_value(card) > 3\n    if_impossible: hand\n  }"
        ))),),
        _host(rules="active_rules: [lr(hearts)] "),
        "active_rules: [lr(", "takes no parameters",
        ((L._LIB, "rule lr {"),),
    ),
    "substituted-template-argument": Named(
        ((L._LIB, _lib(L._LIB, _TEMPLATE.replace("card.suit is s", "rank_value(card) > s"))),),
        _host(rules="active_rules: [lr(hearts)] "),
        "active_rules: [lr(", "Suit enum values have no arithmetic order",
        ((L._LIB, "rank_value(card) > s"), (L._LIB, "rule lr(")),
    ),
    "call-of-another-arity": Named(
        ((L._LIB, _lib(L._LIB, "  function h(c : Card) = rank_value(c)")),),
        _host(body=f"score[0] := h()  {_TRICK}"),
        "score[0] := h()", "h() expects 1 argument(s), got 0",
        ((L._LIB, "function h("),),
    ),
    "call-argument-of-another-type": Named(
        ((L._LIB, _lib(L._LIB, "  function h(c : Card) = rank_value(c)")),),
        _host(body=f"score[0] := h(3)  {_TRICK}"),
        "score[0] := h(3)", "h() expects Card, got Integer",
        ((L._LIB, "function h("),),
    ),
    "run-of-another-arity": Named(
        ((L._LIB, _lib(L._LIB, "  requires { score[player] : Integer }\n  procedure p(x : Player) { score[x] += 1 }")),),
        _host(body=f"run p()  {_TRICK}"),
        "run p()", "procedure 'p' expects 1 argument(s), got 0",
        ((L._LIB, "procedure p("),),
    ),
    "run-argument-of-another-type": Named(
        ((L._LIB, _lib(L._LIB, "  requires { score[player] : Integer }\n  procedure p(x : Player) { score[x] += 1 }")),),
        _host(body=f"run p(true)  {_TRICK}"),
        "run p(true)", "procedure 'p' expects Player, got Boolean",
        ((L._LIB, "procedure p("),),
    ),
    "read-of-provided-state": Named(
        ((L._LIB, _lib(L._LIB, "  state { tally : Integer = 0 }")),),
        _host(body=f"score[0] := number of cards in hand where tally  {_TRICK}"),
        "score[0] := number", "card-query predicate must be Boolean, got Integer",
        ((L._LIB, "tally"),),
    ),
    "template-argument-in-a-nested-clause": Named(
        ((L._LIB, _lib(L._LIB, _TEMPLATE.replace(
            "card.suit is s",
            "(if rank_value(card) > 9 then true elif rank_value(card) > s then true else false)",
        ))),),
        _host(rules="active_rules: [lr(hearts)] "),
        "active_rules: [lr(", "Suit enum values have no arithmetic order",
        ((L._LIB, "rank_value(card) > s"), (L._LIB, "rule lr(")),
    ),
    "game-rule-over-a-standard-library-rule": Named(
        ((L._LIB, _lib(L._LIB, "  function z(c : Card) = rank_value(c)")),),
        _host(extra=(
            "rule MustFollowSuit {\n  constrains: play_to_trick\n"
            "  demands: cards in hand where rank_value(card) > 3\n  if_impossible: hand\n}\n"
        )),
        "rule MustFollowSuit {", "shadows the standard",
        (("stdlib", "rule MustFollowSuit"),),
    ),
}

def _source_file(library: str) -> str:
    return _STDLIB_RULES if library == "stdlib" else f"docs/libraries/{library}.cardlang"


def _source_text(cell: Named, library: str) -> str:
    if library == "stdlib":
        return (_ROOT / _STDLIB_RULES).read_text()
    return dict(cell.libraries)[library]


def _named_bag(monkeypatch: pytest.MonkeyPatch, cell: Named) -> list[str]:
    libraries = {
        name: parse_library(text, f"docs/libraries/{name}.cardlang") for name, text in cell.libraries
    }
    monkeypatch.setattr(R, "library_names", lambda: frozenset(libraries))
    monkeypatch.setattr(R, "load_library", lambda name: libraries[name])
    monkeypatch.setattr(attribution, "witness_sources", lambda name: ())
    try:
        check_capacity(expand(typecheck(R.resolve(parse_text(cell.game, L._GAME_FILE)))))
    except DiagnosticError as exc:
        return L._rendered(exc)
    return []


def _named_refusal(lines: list[str], cell: Named) -> tuple[str, list[str]]:
    found = [(line, notes) for line, notes in _grouped(lines) if cell.says in line]
    assert len(found) == 1, "\n".join(lines)
    return found[0]


@pytest.mark.parametrize("name", sorted(NAMED))
def test_a_refusal_naming_library_text_notes_its_line(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    cell = NAMED[name]
    lines = _named_bag(monkeypatch, cell)
    text = "\n".join(lines)
    line, notes = _named_refusal(lines, cell)
    assert line_kind(line) == "error", text
    assert _location(line) == (L._GAME_FILE, _line_of(cell.game, cell.at)), text
    want = {
        (_source_file(lib), _line_of(_source_text(cell, lib), needle)) for lib, needle in cell.notes
    }
    assert {_location(nt) for nt in notes} == want, text
    for nt in notes:
        assert "library '" in nt or "the standard library" in nt, text


@pytest.mark.parametrize("name", sorted(NAMED))
def test_who_is_told_a_library_named_refusal_never_changes_what_is_refused(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """red under: have `attribution.tell` drop a refusal it notes."""
    cell = NAMED[name]
    told = L._errors(_named_bag(monkeypatch, cell))
    with monkeypatch.context() as mp:
        mp.setattr(attribution, "tell", attribution.keep_where_written)
        kept = L._errors(_named_bag(mp, cell))
    assert told == kept and told


# --- no check spells library text into a sentence itself -------------------------

# The words that name a library or its text in a sentence, and the attributes
# holding a library's name or a definition's words.
_LIBRARY_WORDS = re.compile(r"\blibrary '|\bthe standard library\b|\bstandard-library\b", re.I)
_LIBRARY_WORD_BEFORE_VALUE = re.compile(r"\blibrary\s*'?$", re.I)
_LIBRARY_ATTRS = frozenset({"where", "through", "library"})
# The attributes holding a library's name or a definition's words as a str;
# an entry's `through` is a Library Citation, which a sentence adds.
_SPELLED_ATTRS = frozenset({"where", "library"})


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for nd in ast.walk(tree):
        if isinstance(nd, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = nd.body[0] if nd.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def _installation_messages(tree: ast.AST) -> set[int]:
    """The strings inside a `raise` of an exception that is no refusal: an
    installation's own fault, told to whoever installed it."""
    found: set[int] = set()
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Raise) and isinstance(nd.exc, ast.Call):
            func = nd.exc.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "DiagnosticError":
                found.update(id(sub) for sub in ast.walk(nd.exc))
    return found


def _spellings(source: str) -> list[str]:
    """Each line where `source` spells a library's name or a definition's
    library words into a string itself."""
    tree = ast.parse(source)
    skipped = _docstrings(tree) | _installation_messages(tree)
    skipped |= {
        id(piece)
        for nd in ast.walk(tree) if isinstance(nd, ast.JoinedStr)
        for piece in nd.values
    }
    found: list[str] = []
    for nd in ast.walk(tree):
        if id(nd) in skipped:
            continue
        if isinstance(nd, ast.JoinedStr):
            pieces = nd.values
            for at, piece in enumerate(pieces):
                if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                    following = pieces[at + 1] if at + 1 < len(pieces) else None
                    if _LIBRARY_WORDS.search(piece.value) or (
                        isinstance(following, ast.FormattedValue)
                        and _LIBRARY_WORD_BEFORE_VALUE.search(piece.value)
                    ):
                        found.append(f"{nd.lineno}: {piece.value!r}")
                elif (
                    isinstance(piece, ast.FormattedValue)
                    and isinstance(piece.value, ast.Attribute)
                    and piece.value.attr in _LIBRARY_ATTRS
                ):
                    found.append(f"{nd.lineno}: {{{ast.unparse(piece.value)}}}")
        elif isinstance(nd, ast.Constant) and isinstance(nd.value, str) and _LIBRARY_WORDS.search(nd.value):
            found.append(f"{nd.lineno}: {nd.value!r}")
        elif isinstance(nd, ast.BinOp) and isinstance(nd.op, ast.Add):
            for operand in (nd.left, nd.right):
                if isinstance(operand, ast.Attribute) and operand.attr in _SPELLED_ATTRS:
                    found.append(f"{nd.lineno}: + {ast.unparse(operand)}")
            left = nd.left
            if (
                isinstance(left, ast.Constant) and isinstance(left.value, str)
                and _LIBRARY_WORD_BEFORE_VALUE.search(left.value)
            ):
                found.append(f"{nd.lineno}: {left.value!r} +")
    return found


_THE_STEP = frozenset({"attribution.py", "diagnostics.py"})


def test_no_check_spells_library_text_into_a_sentence() -> None:
    """The words naming a library or its text are made by the attribution
    step alone, from a value carrying the text's span.

    red under: write `f"library {name!r}"` into a sentence in resolve."""
    spelled = [
        f"{path.relative_to(_ROOT).as_posix()}:{at}"
        for path in sorted(_PACKAGE.rglob("*.py"))
        if path.relative_to(_PACKAGE).as_posix() not in _THE_STEP
        for at in _spellings(path.read_text())
    ]
    assert spelled == []


def test_the_spelling_census_reads_every_spelling() -> None:
    """Each arm of `_spellings` finds its spelling, so the census cannot pass
    by reading nothing.

    red under: drop the `_LIBRARY_WORD_BEFORE_VALUE` arm from `_spellings`."""
    sources = {
        "word": "x = f\"library '{name}' requires\"\n",
        "value": "x = f\"library {name!r} requires\"\n",
        "standard": "x = 'the standard library holds'\n",
        "where": "x = f\"in {origin.where}\"\n",
        "added-name": "x = \"library \" + origin.library\n",
        "added-where": "x = origin.where + \" reads\"\n",
        "docstring": "def f():\n    \"\"\"library 'x' is quiet here.\"\"\"\n",
        "installation": "raise ValueError(f\"library '{name}' is broken\")\n",
    }
    found = {key: len(_spellings(source)) for key, source in sources.items()}
    assert found == {
        "word": 1, "value": 1, "standard": 1, "where": 1, "added-name": 2, "added-where": 1,
        "docstring": 0, "installation": 0,
    }


# Each check citing library text with no span, and why its sentence stands on
# no line there: no library text stands behind the name, or another citation
# in the same sentence carries the line.
_UNSPANNED_CITATIONS: dict[tuple[str, str], str] = {
    ("resolve.py", "_apply_uses"): "a repeated or unknown `uses` line, or the standard "
    "library's: no library text is in question",
    ("resolve.py", "_check_library_clause_gates"): "the subject; each definition the "
    "gate lists is cited at its refused text",
    ("resolve.py", "_check_library_lines_span"): "the subject; the definition holding "
    "the call is cited at it",
    ("typecheck.py", "_library_field_gate"): "the subject; the definition holding the "
    "read is cited at it",
}
_CITES = frozenset({"cite_library", "cite_definition", "cite_origin", "cite_where"})


def test_a_citation_handed_no_span_says_why() -> None:
    """red under: cite `library.name` with `None` in `_check_state_claims`."""
    found: set[tuple[str, str]] = set()
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for top in ast.walk(tree):
            if not isinstance(top, ast.FunctionDef):
                continue
            for nd in ast.walk(top):
                if (
                    isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
                    and nd.func.id in _CITES and nd.args
                    and isinstance(nd.args[-1], ast.Constant) and nd.args[-1].value is None
                ):
                    found.add((path.relative_to(_PACKAGE).as_posix(), top.name))
    assert found == set(_UNSPANNED_CITATIONS)


def test_a_library_checked_alone_raises_with_no_step_input() -> None:
    """The standard library's own check raises through the step, which keeps
    no input on what it raises.

    red under: have `attribution.raise_where_written` raise the bag as it
    stands."""
    bag = DiagnosticBag()
    span = Span(_STDLIB_RULES, 0, 1, 1, 1)
    bag.error(attribution.cite_library("stdlib", span) + " refuses this", span)
    with pytest.raises(DiagnosticError) as exc:
        attribution.raise_where_written(bag)
    told = exc.value.diagnostic
    assert (told.message, told.route, told.for_game, told.stands_on) == (
        "the standard library refuses this", None, None, (),
    )


def test_only_the_step_raises_a_bag_after_parse() -> None:
    """A bag a check fills reaches a raise only through the step; the
    parser's bag never holds a Library Citation.

    red under: raise `DiagnosticError(bag.items[0])` in `stdlib/rules.py`."""
    raisers: set[str] = set()
    for path in sorted(_PACKAGE.rglob("*.py")):
        for nd in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
                and nd.func.id == "DiagnosticError" and nd.args
                and isinstance(nd.args[0], ast.Subscript)
                and isinstance(nd.args[0].value, ast.Attribute)
                and nd.args[0].value.attr == "items"
            ):
                raisers.add(path.relative_to(_PACKAGE).as_posix())
    assert raisers == {"attribution.py", "parse.py"}


def test_a_library_citation_is_never_spelled_into_a_str() -> None:
    """red under: give `LibraryCitation` a `__format__` that returns its
    words."""
    cited = attribution.cite_library(L._LIB, None)
    with pytest.raises(TypeError):
        f"{cited}"
    with pytest.raises(TypeError):
        str(cited + " reads")


# --- every library-to-game refusal told in the game names its library line -------


def _told_in_the_game(monkeypatch: pytest.MonkeyPatch, witness: L.Witness) -> list[Diagnostic]:
    """Every error the step tells outside a library's file while `witness`
    runs a game that uses a library."""
    told: list[Diagnostic] = []
    real = attribution.tell

    def recording(bag: DiagnosticBag, game: n.Game, uses: tuple[n.UsesDecl, ...] = ()) -> None:
        real(bag, game, uses)
        if attribution._WITNESSING.get() or not attribution._holders(game) and not uses:
            return
        told.extend(
            d for d in bag.items
            if d.severity.value == "error"
            and d.span is not None
            and not d.span.source_name.startswith(("docs/libraries/", _STDLIB_RULES))
        )

    monkeypatch.setattr(attribution, "tell", recording)
    witness(monkeypatch)
    return told


def test_every_library_to_game_refusal_told_in_the_game_names_its_library_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read off every refusal the step tells in the game's file, naming a
    library, while each witness of the ledger's library-to-game families
    runs; a sentence naming no library refuses the game's own text.

    red under: have `attribution._bare` drop every note."""
    missing: list[str] = []
    read = 0
    for key, witness in sorted(L._library_to_game_witnesses().items()):
        with monkeypatch.context() as mp:
            for d in _told_in_the_game(mp, witness):
                if not _LIBRARY_WORDS.search(d.message):
                    continue
                read += 1
                if not d.notes:
                    missing.append(f"{key}: {d.format()}")
    assert read > 0
    assert missing == []


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
