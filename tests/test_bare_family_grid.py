"""A zone family named without its index is the acting player's own zone.

A bare `hand` means the acting player's hand: the engine keys the family by
the acting seat. That reading exists only for a family kept per player. A
family kept per team, per position or as one single zone has no instance a
seat can name by itself being the acting seat, so naming it where the engine
keys by seat is refused at check time, with the subscript the designer
writes instead.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   wherever the engine resolves a family name by the acting seat, the
            name must denote a family indexed by player; any other index role
            is a check-time diagnostic at the name's span, exactly one
            bare-family refusal per site (a concealed zone read at a decision
            position also draws the hidden-read refusal, and the bare-family
            refusal's spelling clears both), and with the static guard removed
            every such cell fails
            typed at play (a `ShadowGuardError`), never reading another
            team's or column's zone.
domain:     {index role} x {position the name is written at}. The roles are
            every zone-index role plus a declared position domain and a single
            zone. The positions are the expression positions a bare family
            name is resolved at (sampled), the string slots naming a zone (all
            of them), and the Builtins that read a family by name (all of
            them), in game text, a procedure body and a family library's body.
            Every corpus game declaring a family not kept per player (team,
            position, board cell) is swept with each subscript it writes on one
            removed in turn. Two whole-family
            positions keep their own guards and are crossed here for the
            one-diagnostic count only: `to each <family>` and a Trick Order
            row. A Primitive's `reads <family>` names the family whole, not
            the acting seat's instance, so it lies outside the domain.
registry:   roles: `cardlang.domains.ZONE_INDEX_ROLES`; string slots:
            `cardlang.resolve._REFERENCE_SLOTS` rows in the "zone" namespace;
            implicit reads: `cardlang.builtins.functions.BUILTIN_IMPLICIT_READS`;
            all derived in `tests/bare_family_axes.py`.
            corpus checks clean: `tests/test_typecheck_corpus.py::test_corpus_game_type_checks`.
does not prove:  that every expression position is walked. The guard is one
            walk over every name the resolver classifies as a zone; the grid
            samples the positions in `EXPR_ROWS`, and the corpus sweep
            covers every position the corpus writes such a family at.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest
from _pytest.mark.structures import ParameterSet

from cardlang import resolve as resolve_mod
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import Role, role_of
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import _check, check_dsl
from cardlang.resolve import _walk
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import ShadowGuardError
from tests.bare_family_axes import (
    ADMITTED_ROLE,
    CONCEALED_TEAM_DECL,
    EXPR_ROWS,
    IMPLICIT_READS,
    PLAY_SLOT_FIELD,
    POSITION_ROLE,
    ROLES,
    SINGLE,
    SOURCE_SLOT_FIELD,
    ZONE_SLOTS,
    ExprRow,
    role_decl,
)

REPO = Path(__file__).resolve().parent.parent
GAMES = REPO / "docs" / "games"

# The resolve function owning the refusal, named by the Shadow Guards.
OWNER = "resolve._check_bare_family_refs"

TEMPLATE = """game G {{
  players: 4
  teams: [[0, 1], [2, 3]]
  direction: clockwise
  max_length: 200
  cards: standard52
  ranking: aces high
  winner: highest score
  positions {{ column : 1..4 }}
  zones {{
    deck : Deck
    hand[player] : Hand<player>
    {decl}
  }}
  state {{ score[team] : Integer = 0 }}
  phase deal_out {{ shuffle deck  deal 2 cards from deck to each hand }}
  phase play {{ {body} }}
}}
{extra}
"""

# role -> what a bare `won` of that role is called in the refusal
_INDEX_WORD = {"team": "team", POSITION_ROLE: "column"}


def expr_source(row: ExprRow, decl: str, stmt: str | None = None) -> str:
    stmt = row.stmt if stmt is None else stmt
    if row.move_when:
        body = "for each player p: offer to p one of [m]"
        extra = f"move_type m {{ when: {stmt} effect {{ score[0] := 1 }} }}"
    elif row.function:
        body = "for each player p: as p { if f() { score[0] := 1 } }"
        extra = f"function f() = {stmt}"
    else:
        body = f"for each player p: as p {{ {stmt} }}"
        extra = ""
    return TEMPLATE.format(decl=decl, body=body, extra=extra)


def diagnostics(text: str) -> list[str]:
    """Every diagnostic `check_dsl` reports for `text`, one line each; empty
    when it checks. A stage reporting several attaches its whole bag as a
    note, the first diagnostic included."""
    try:
        check_dsl(text, "g")
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None) or []
        if not notes:
            return [exc.diagnostic.format()]
        return [line for note in notes for line in note.splitlines()]
    return []


def _static_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the check-time Owner Guards, leaving the runtime to answer."""
    monkeypatch.setattr(resolve_mod, "_check_bare_family_refs", lambda *a, **k: None)


def unguarded_play_failure(text: str) -> BaseException | None:
    """Check `text` without the memo (a guard-off success must never be the
    cached answer for a guarded run), then play one seeded game; the exception
    play ends in, or None."""
    game = _check.__wrapped__(parse_text(text, "g"))
    try:
        play_game(game, random.Random(0))
    except Exception as exc:  # the cell's outcome IS the exception
        return exc
    return None


def _refusal_names(name: str, index: str) -> str:
    return f"`{name}` is one zone per {index}"


# --- each expression row places `won` where it says -------------------------


def sites(stmt: str) -> int:
    """How many times a row's sentence names `won` bare."""
    return len(re.findall(r"\bwon\b", stmt))


def _held(value: object) -> tuple[object, ...]:
    return value if isinstance(value, tuple) else (value,)


@pytest.mark.parametrize("row", EXPR_ROWS, ids=lambda r: r.key)
def test_each_expression_row_sits_where_it_says(row: ExprRow) -> None:
    """The sentence writes a bare `won` the resolver classifies as a zone,
    inside the (node, field) the row names."""
    game = check_dsl(expr_source(row, role_decl(ADMITTED_ROLE)), "g")
    subscripted = {id(x.obj) for x in _walk(game) if isinstance(x, n.Subscript)}
    inside = {
        id(x)
        for node in _walk(game)
        if isinstance(node, row.node)
        for held in _held(getattr(node, row.field))
        for x in _walk(held)
        if isinstance(x, n.NameRef) and x.name == "won" and x.ref_kind == "zone"
        and id(x) not in subscripted
    }
    assert inside, row


# --- axis E: index role x expression position --------------------------------


def _expr_cells() -> list[ParameterSet]:
    out = []
    for role in ROLES:
        for row in EXPR_ROWS:
            refused = role not in (ADMITTED_ROLE, SINGLE)
            out.append(pytest.param(role, row, refused, id=f"{role}-{row.key}"))
    return out


@pytest.mark.parametrize("role,row,refused", _expr_cells())
def test_expression_position(role: str, row: ExprRow, refused: bool) -> None:
    found = diagnostics(expr_source(row, role_decl(role)))
    if not refused:
        assert found == []
        return
    assert len(found) == sites(row.stmt), found
    for message in found:
        assert _refusal_names("won", _INDEX_WORD[role]) in message, message
        assert f"`won[<{_INDEX_WORD[role]}>]`" in message, message


# --- the hint is a claim: the spelling it names checks and plays -------------


# The refusal names a shape, `won[<team>]`, and how to name a player's team,
# `team_of(<player>)`; filled with the acting player and the first column, the
# spellings it names must check and play wherever the bare name stood.
_FILL = {"<player>": "actor", "<column>": "1"}


def applied_hint(message: str, name: str) -> str:
    """The subscripted spelling the refusal names, with its placeholders
    filled: `<team>` by the player's team the message also names."""
    shape = re.search(rf"`({re.escape(name)}\[<\w+>\])`", message)
    assert shape is not None, message
    spelling = shape.group(1)
    if "[<team>]" in spelling:
        team = re.search(r"`(team_of\(<player>\))`", message)
        assert team is not None, message
        spelling = spelling.replace("<team>", team.group(1))
    for placeholder, value in _FILL.items():
        spelling = spelling.replace(placeholder, value)
    return spelling


def _hint_cells() -> list[ParameterSet]:
    return [
        pytest.param(role, row, id=f"{role}-{row.key}")
        for role in ROLES
        if role not in (ADMITTED_ROLE, SINGLE)
        for row in EXPR_ROWS
    ]


@pytest.mark.parametrize("role,row", _hint_cells())
def test_hint_spelling_checks_and_plays(role: str, row: ExprRow) -> None:
    """red under: the position refusal naming `won[<position>]` instead of
    `won[<column>]` (resolve's bare-family Owner Guard)."""
    found = diagnostics(expr_source(row, role_decl(role)))
    assert len(found) == sites(row.stmt), found
    hint = applied_hint(found[0], "won")
    if row.function:  # a function is hermetic: it names a seat, not `actor`
        hint = hint.replace("actor", "0")
    fixed = re.sub(r"\bwon\b", hint, row.stmt)
    try:
        game = check_dsl(expr_source(row, role_decl(role), fixed), "g")
        play_game(game, random.Random(0))
    except Exception as exc:
        raise AssertionError(f"the hint's spelling {fixed!r} fails: {exc!r}") from exc


# --- static guard off: every refused expression cell fails typed at play -----


def _unguarded_expr_cells() -> list[ParameterSet]:
    return [
        pytest.param(role, row, id=f"{role}-{row.key}")
        for role in ROLES
        if role not in (ADMITTED_ROLE, SINGLE)
        for row in EXPR_ROWS
    ]


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize("role,row", _unguarded_expr_cells())
def test_unguarded_expression_cell_fails_typed(
    role: str, row: ExprRow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _static_off(monkeypatch)
    failure = unguarded_play_failure(expr_source(row, role_decl(role)))
    assert isinstance(failure, ShadowGuardError), repr(failure)
    assert failure.leaked == OWNER


# --- information sets: a concealed team zone named bare is not "own" ---------


def test_concealed_team_zone_read_bare_is_not_credited_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the bare-family guard removed, the hidden-read checker still
    refuses a decision that reads a concealed team zone named bare: the seat
    deciding owns no instance the bare name can be proven to reach."""
    _static_off(monkeypatch)
    row = next(r for r in EXPR_ROWS if r.move_when)
    text = expr_source(row, CONCEALED_TEAM_DECL, "any card in won where card.suit is hearts")
    try:
        _check.__wrapped__(parse_text(text, "g"))
    except DiagnosticError as exc:
        assert "cannot see" in str(exc), str(exc)
        return
    raise AssertionError("a bare concealed team zone was credited as the decider's own")


# --- axis S: index role x string slot naming a zone --------------------------


def _slot_source(slot: tuple[type, str], role: str) -> str:
    node, field = slot
    path = GAMES / ("big-two.cardlang" if node.__name__ == "ClimbRound" else "spades.cardlang")
    text = path.read_text()
    decl = role_decl(role).replace("won", "slotzone")
    text = text.replace("  zones {\n", "  positions { column : 1..4 }\n  zones {\n" f"    {decl}\n", 1)
    if "teams:" not in text:
        text = text.replace("  players: 4\n", "  players: 4\n  teams: [[0, 2], [1, 3]]\n", 1)
    old = "source hand" if field == SOURCE_SLOT_FIELD else "into trick_pile"
    new = "source slotzone" if field == SOURCE_SLOT_FIELD else "into slotzone"
    assert old in text, (path, old)
    return text.replace(old, new)


def _slot_admitted(field: str) -> str:
    return ADMITTED_ROLE if field == SOURCE_SLOT_FIELD else SINGLE


def _slot_cells() -> list[ParameterSet]:
    return [
        pytest.param(
            slot, role, id=f"{slot[0].__name__}.{slot[1]}-{role}",
        )
        for slot in ZONE_SLOTS
        for role in ROLES
    ]


@pytest.mark.parametrize("slot,role", _slot_cells())
def test_zone_slot(slot: tuple[type, str], role: str) -> None:
    found = diagnostics(_slot_source(slot, role))
    if role == _slot_admitted(slot[1]):
        assert found == []
        return
    assert len(found) == 1, found
    if slot[1] == SOURCE_SLOT_FIELD:
        assert "must be a zone kept per player" in found[0], found[0]
    else:
        assert "must be a single zone" in found[0], found[0]
    # The expression hint names a subscript, which a slot cannot hold.
    assert "team_of" not in found[0] and "[<" not in found[0], found[0]


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize(
    "slot,role",
    [
        pytest.param(s, r, id=f"{s[0].__name__}.{s[1]}-{r}")
        for s in ZONE_SLOTS
        for r in ROLES
        if r != _slot_admitted(s[1])
    ],
)
def test_unguarded_zone_slot_fails_typed(
    slot: tuple[type, str], role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _static_off(monkeypatch)
    failure = unguarded_play_failure(_slot_source(slot, role))
    assert isinstance(failure, ShadowGuardError), repr(failure)
    assert failure.leaked == OWNER


# --- axis I: index role x Builtin reading a family by name -------------------

_IMPLICIT_TEMPLATE = """game G {{
  players: 4
  teams: [[0, 1], [2, 3]]
  direction: clockwise
  max_length: 200
  cards: standard52
  ranking: aces high
  winner: highest score
  positions {{ column : 1..4 }}
  zones {{
    deck : Deck
    {decl}
  }}
  state {{ score[player] : Integer = 0  lead : Player = 0 }}
  phase play {{ move all cards from deck to {target}  lead := {call}(2 of clubs)  score[lead] := 1 }}
}}
"""


def _implicit_source(fn: str, family: str, role: str) -> str:
    decl = role_decl(role).replace("won", family).replace("PlayerPile", "Hand").replace(
        "TeamPile", "Hand"
    )
    # Key 1: a team id or a column read back as seat 1 is the silent wrong answer.
    target = family if role == SINGLE else f"{family}[1]"
    return _IMPLICIT_TEMPLATE.format(decl=decl, target=target, call=fn)


def _implicit_cells() -> list[ParameterSet]:
    return [
        pytest.param(
            fn, fam, role, id=f"{fn}-{role}",
        )
        for fn, fam in IMPLICIT_READS
        for role in ROLES
    ]


@pytest.mark.parametrize("fn,family,role", _implicit_cells())
def test_implicit_read(fn: str, family: str, role: str) -> None:
    found = diagnostics(_implicit_source(fn, family, role))
    if role == ADMITTED_ROLE:
        assert found == []
        return
    assert len(found) == 1, found
    assert f"`{family}[player]`" in found[0], found[0]


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize(
    "fn,family,role",
    [
        pytest.param(fn, fam, r, id=f"{fn}-{r}")
        for fn, fam in IMPLICIT_READS
        for r in ROLES
        if r != ADMITTED_ROLE
    ],
)
def test_unguarded_implicit_read_fails_typed(
    fn: str, family: str, role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _static_off(monkeypatch)
    failure = unguarded_play_failure(_implicit_source(fn, family, role))
    assert isinstance(failure, ShadowGuardError), repr(failure)
    assert failure.leaked == OWNER


# --- whole-family positions with their own guards: one diagnostic each -------


def test_to_each_team_family_reports_once() -> None:
    row = EXPR_ROWS[0]
    found = diagnostics(
        expr_source(row, role_decl("team"), "deal 1 card from deck to each won")
    )
    assert len(found) == 1, found
    assert "per player" in found[0], found[0]


def _belote_row_reading(read: str) -> str:
    text = (GAMES / "belote.cardlang").read_text()
    old = "trump:         card.suit is trump_suit\n"
    assert old in text
    return text.replace(old, f"trump:         card.suit is trump_suit and {read}\n", 1)


def test_trick_order_row_team_family_reports_once() -> None:
    """A row has no acting player, so the hint's shape is filled with a team
    literal there; the hint names no pronoun that a row could not read."""
    found = diagnostics(_belote_row_reading("captured is empty"))
    assert len(found) == 1, found
    assert _refusal_names("captured", "team") in found[0], found[0]
    assert "actor" not in found[0], found[0]
    shape = re.search(r"`(captured\[<team>\])`", found[0])
    assert shape is not None, found[0]
    filled = shape.group(1).replace("<team>", "0")
    assert diagnostics(_belote_row_reading(f"{filled} is empty")) == []


# --- corpus sweep: each subscript on a family not kept per player, removed ---


def _swept_families(game: n.Game) -> dict[str, str]:
    """The game's families whose index is not the player role, by index."""
    return {
        z.name: z.index
        for z in game.zones
        if z.index is not None and role_of(z.index) is not Role.PLAYER
    }


def _subscripts_on(name: str) -> list[tuple[int, int, str]]:
    """(start, end, index) of the bracketed index of every subscript the game
    writes on a family `_swept_families` names, read off the checked tree."""
    game = check_dsl((GAMES / name).read_text(), name)
    swept = _swept_families(game)
    return sorted(
        {
            (nd.obj.span.start + len(nd.obj.name), nd.span.end, swept[nd.obj.name])
            for nd in _walk(game)
            if isinstance(nd, n.Subscript)
            and isinstance(nd.obj, n.NameRef)
            and nd.obj.ref_kind == "zone"
            and nd.obj.name in swept
            and nd.span is not None
            and nd.obj.span is not None
            and nd.span.source_name == name
        }
    )


def _sweeps(path: Path) -> bool:
    return bool(_swept_families(check_dsl(path.read_text(), path.name)))


def _corpus_cells() -> list[ParameterSet]:
    out = []
    for path in sorted(GAMES.glob("*.cardlang")):
        if not _sweeps(path):
            continue
        text = path.read_text()
        for start, end, index in _subscripts_on(path.name):
            line = text.count("\n", 0, start) + 1
            out.append(pytest.param(
                path.name, start, end, line, index, id=f"{path.stem}:{line}:{start}"
            ))
    return out


_CORPUS = _corpus_cells()


def test_corpus_sweep_reaches_every_game_it_should() -> None:
    swept = {p.values[0] for p in _CORPUS}
    declaring = {p.name for p in GAMES.glob("*.cardlang") if _sweeps(p)}
    assert swept == declaring and swept, (swept, declaring)


@pytest.mark.parametrize("name,start,end,line,index", _CORPUS)
def test_corpus_subscript_removed_is_refused(
    name: str, start: int, end: int, line: int, index: str
) -> None:
    text = (GAMES / name).read_text()
    found = diagnostics(text[:start] + text[end:])
    hits = [d for d in found if f"is one zone per {index}," in d and f":{line}:" in d]
    assert len(hits) == 1, found


# --- bodies spliced in before the check: a procedure, a family library ------


_STASH = "procedure stash() { move all cards from hand to won }"
_TEAM_LIBRARY = """library teamlib {
  requires {
    hand[player] : Hand<player>
    won[team] : TeamPile<team>
  }
  %s
}
""" % _STASH


def test_procedure_body_bare_team_family_is_refused() -> None:
    found = diagnostics(TEMPLATE.format(
        decl=role_decl("team"), body="for each player p: as p { run stash() }", extra=_STASH
    ))
    assert len(found) == 1 and _refusal_names("won", "team") in found[0], found


def test_library_body_bare_team_family_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal locates the library's own line: the library's author wrote it."""
    library = parse_library(_TEAM_LIBRARY, "teamlib")
    monkeypatch.setattr(resolve_mod, "library_names", lambda: frozenset({"teamlib"}))
    monkeypatch.setattr(resolve_mod, "load_library", lambda name: library)
    text = TEMPLATE.format(
        decl=role_decl("team"), body="for each player p: as p { run stash() }", extra=""
    ).replace("  positions {", "  uses teamlib\n  positions {", 1)
    found = diagnostics(text)
    assert len(found) == 1 and found[0].startswith("teamlib:"), found
    assert _refusal_names("won", "team") in found[0], found


def test_concealed_team_zone_named_bare_is_refused_and_its_fix_clears() -> None:
    """A concealed team zone read bare at a decision position draws the
    bare-family refusal once, and the hidden-read refusal beside it: no seat
    owns what a bare team name reads. The refusal's spelling clears both."""
    row = next(r for r in EXPR_ROWS if r.move_when)
    read = "any card in won where card.suit is hearts"
    found = diagnostics(expr_source(row, CONCEALED_TEAM_DECL, read))
    (refusal,) = [d for d in found if _refusal_names("won", "team") in d]
    fixed = read.replace("won", applied_hint(refusal, "won"))
    assert diagnostics(expr_source(row, CONCEALED_TEAM_DECL, fixed)) == []


# --- misuse probes: what a designer writes for "my side's pile" --------------

_PROBES: dict[str, tuple[str, str]] = {
    "seat_as_team": (
        "for each player p: as p { move all cards from hand to won[actor] }",
        "keyed by Team",
    ),
    "binder_as_team": (
        "for each player p: as p { move all cards from hand to won[p] }",
        "keyed by Team",
    ),
    "bare_in_for_each_team": (
        "for each team t: move all cards from won to deck",
        _refusal_names("won", "team"),
    ),
    "bare_where_nobody_acts": (
        "move all cards from won to deck",
        _refusal_names("won", "team"),
    ),
}


@pytest.mark.parametrize("body,expected", list(_PROBES.values()), ids=list(_PROBES))
def test_misuse_probe_is_refused_once(body: str, expected: str) -> None:
    found = diagnostics(TEMPLATE.format(decl=role_decl("team"), body=body, extra=""))
    assert len(found) == 1 and expected in found[0], found
