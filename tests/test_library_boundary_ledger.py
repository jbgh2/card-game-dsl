"""Every refusal at the library boundary is told to the author who can act.

A game's text reaches a family library's text by a call, a `run`, an offer
or a Hosted Poll's closure; a library's text reaches the game's through its
`requires { }` contract and the game clauses and declarations it depends on.
A refusal there sits in one author's text for the other's cause unless it is
moved, so the ledger below enumerates every crossing and says where each is
told (decisions.md "Family libraries": a library is sound when some answer
meets its row, and a library definition is sound when some calling position
meets it; glossary/author.md).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a refusal whose cause is the game's text is reported in the
                 game's file -- at the game's last call into library text,
                 naming the library, or on its `uses` line when a game clause
                 or declaration decides it -- and a refusal whose cause is the
                 library's own text is reported in the library's file, in
                 every game; every crossing not yet told to its owner is a
                 strict xfail citing its issue; and who is told never changes
                 what is refused.
domain:          two directions. Game to library, the checks that follow a
                 call out of the text they started in (`crossing_walkers`,
                 each classified in `WALKERS`): a Trick Order row, at every
                 row of `TRICK_ORDER_ROWS`, with every arm of its refusal --
                 every pronoun of `resolve._PRONOUNS`, a `choose`, every zone
                 type of `LIBRARY_ZONE_TYPES`, a bare per-player family, every
                 Builtin of the row-call partition and every row's reader; a
                 decision no one can make, at every place of
                 `resolve._NO_ACTOR_WHERE`, for a `choose` and for `actor`; a
                 bare `hand` read through a function from every clause
                 `resolve._rule_clauses` reads; a Hosted Poll, along every
                 route and with every payload its own grid refuses; a game
                 decision, at every judged position of
                 `HIDDEN_READ_POSITIONS`, reading through a library function;
                 and a library procedure the game runs: every judged
                 position a procedure body holds (the seat-deciding rows of
                 `HIDDEN_READ_POSITIONS` whose node is a statement or an
                 expression), reading the cards of a parameter's seat, of a
                 contracted seat, of a zone no seat sees and of an index no
                 `as` names, each run where no one acts, as another seat and
                 as the seat it decides for; a decision reading nothing, where
                 no one acts; a run from a game move type's effect; the game's
                 own argument reading cards, through a function and through a
                 `let`; and the procedures no caller meets -- two seats, a seat the body
                 writes before it reads it, a `to each` movement, and a run
                 from a library move type's effect. Library to game: the
                 game's answer to a
                 Definition Contract at every judged position a library holds
                 and through a library function, in a `choose` and an `actor`
                 where no one acts, a bare `hand` under a library rule, an
                 Arrival Record, a call cycle, a call-site pronoun in a
                 function and in a procedure, and every contractable kind left
                 unanswered; every gate of the clause-gate grid; every member
                 of the type layer's clause reads; the game declarations the
                 framing check found that no contract row names; and the
                 library text a game activates or runs, judged once the game
                 is known (a rule activated, a library round). Beside them,
                 the library's own text: every check
                 `resolve.check_library_alone` runs, a call-site pronoun in a
                 library function, and a statement no procedure or move
                 type's effect may hold. The crossings held by an issue are
                 cells marked with it; the scoped-read containment arms on a
                 library move type (`_check_offered_containers`) have no
                 witness here, and issue #889 holds them. A library holds no
                 climbing round, whose slots name Primitives, so no Hosted
                 Poll and no poll binder starts in library text, and its
                 cell is the library's own refusal; it holds no `trick_order
                 { }` block, so no row is library text; it cannot contract a
                 position-indexed zone, and that row's cell is the library's
                 own refusal; and an `early` predicate is a Primitive, its
                 cell the same.
registry:        walkers: the passes' source, `crossing_walkers`; rows and the
                 row-call partition: `cardlang.builtins.functions`; pronouns:
                 `resolve._PRONOUNS`, `resolve._CALL_SITE_PRONOUNS`; zone
                 types: `stdlib.zones.LIBRARY_ZONE_TYPES`; places:
                 `resolve._NO_ACTOR_WHERE`; rule clauses:
                 `resolve._rule_clauses`; Hosted Poll routes and payloads:
                 tests/test_hosted_poll.py; judged positions:
                 tests/test_hidden_reads.py; Definition Contract crossings:
                 tests/test_contracted_hidden_reads.py and
                 tests/test_definition_contracts.py; clause gates:
                 tests/test_library_clause_gates.py; type-layer clause reads:
                 `typecheck.CLAUSE_READS`, tests/test_library_type_gates.py;
                 library-alone checks: `resolve.check_library_alone`;
                 positions a procedure holds: `_procedure_positions`.
does not prove:  that a check crossing into another definition by an idiom
                 other than the helpers and pool look-ups `crossing_walkers`
                 names is enumerated: such a check is outside the scan. Nor
                 that every arm of a library-to-game family is told to its
                 owner: one witness per arm runs here, and the owning grid
                 holds the cross. Nor that a sentence is whole: cells pin its
                 file, its line and the names it carries. Nor that the callers
                 `_HiddenReads._meeting_callers` tries are every caller: they
                 are the two ways `_names_acting_seat` proves library text's
                 index is the acting seat, a parameter and a State Variable,
                 and a proof added there goes untried, its refusals told to
                 the library. Nor that a library's own fault behind a decision
                 run where no one acts is told: the walk stops at the
                 decision, so a procedure no caller meets is told only that no
                 one acts.
"""

from __future__ import annotations

import ast
import sys
import re
import typing
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

import cardlang.resolve as R
from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    BUILTIN_CALL_FUNCS,
    TRICK_ORDER_READERS,
    TRICK_ORDER_ROW_CALLS,
    TRICK_ORDER_ROW_KEYS,
    TRICK_ORDER_ROW_UNCALLABLE,
    TRICK_ORDER_ROWS,
)
from cardlang.deckcheck import check_capacity
from cardlang.diagnostics import DiagnosticError
from cardlang.expand import expand
from cardlang.parse import parse_library, parse_text
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, identity_to_all
from cardlang.typecheck import typecheck
import tests.test_contracted_hidden_reads as CHR
import tests.test_definition_contracts as DC
import tests.test_hidden_reads as HR
import tests.test_hosted_poll as HP
import tests.test_library_clause_gates as CG
import tests.test_library_type_gates as TG
from tests.test_hidden_reads import _TYPES

_LIB = "boundarylib"
_LIB_FILE = f"docs/libraries/{_LIB}.cardlang"
_GAME_FILE = "boundary.cardlang"
_NAMED = f"library '{_LIB}'"


# --- the harness ---------------------------------------------------------------


def _rendered(exc: DiagnosticError) -> list[str]:
    notes = getattr(exc, "__notes__", [])
    return notes[0].splitlines() if notes else [str(exc)]


def _bag(monkeypatch: pytest.MonkeyPatch, library: str | None, game: str) -> list[str]:
    """Every diagnostic the library's own parse and then the game's pipeline
    raise, one rendered line each; [] when both accept. Unmemoized, since the
    library is patched per cell."""
    if library is not None:
        try:
            lib = parse_library(library, _LIB_FILE)
        except DiagnosticError as exc:
            return _rendered(exc)
        monkeypatch.setattr(R, "library_names", lambda: frozenset({_LIB}))
        monkeypatch.setattr(R, "load_library", lambda name: lib)
    try:
        check_capacity(expand(typecheck(R.resolve(parse_text(game, _GAME_FILE)))))
    except DiagnosticError as exc:
        return _rendered(exc)
    return []


def _line(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} is not in the game")


GAME = "game"
USES = "uses"
LIBRARY = "library"


@dataclass(frozen=True)
class Crossing:
    """One cell: the library, the game that makes the crossing, the owner the
    refusal is told to, and the game text the refusal stands at when the
    owner is the game (`anchor`). `twin` is the same game with the library's
    definitions written in the game itself, which a cell's verdict must
    match; None where the definition cannot move (it names the contract)."""

    library: str
    game: str
    owner: str | None
    anchor: str | None = None
    needles: tuple[str, ...] = ()
    twin: str | None = None
    names_library: bool = True


def _assert_told(cell: Crossing, bag: list[str]) -> None:
    if cell.owner is None:
        assert bag == [], "expected the cell to be accepted:\n" + "\n".join(bag)
        return
    assert bag, "expected a refusal, but the cell was accepted"
    text = "\n".join(bag)
    in_library = [line for line in bag if line.startswith(_LIB_FILE)]
    in_game = [line for line in bag if not line.startswith(_LIB_FILE)]
    if cell.owner == LIBRARY:
        assert in_game == [], text
    else:
        assert in_library == [], text
        needle = f"uses {_LIB}" if cell.owner == USES else cell.anchor
        assert needle is not None
        at = f"{_GAME_FILE}:{_line(cell.game, needle)}:"
        assert all(line.startswith(_GAME_FILE) for line in in_game), text
        assert any(line.startswith(at) for line in in_game), f"nothing at {at}\n{text}"
        if cell.names_library:
            assert all(_NAMED in line for line in in_game), text
    for needle in cell.needles:
        assert any(needle in line for line in bag), f"{needle!r} not said:\n{text}"


# --- game to library: a Trick Order row calling a library function --------------
#
# The row's arms are `resolve._check_trick_order_rows`' refusals, each read
# off its registry: every pronoun, a `choose`, every zone type, a bare family,
# every Builtin a row may or may not call, and every row's reader.

_TRICK_HOST = """game Boundary {{
  players: 4
  max_length: 2000
  cards: standard52
  ranking: aces high
  {clauses}
  uses boundarylib
  trick_order {{ {rows} }}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile  {zones} }}
  state {{ score[player] : Integer = 0  who : Player = 0 }}
  phase play {{
    let w = highest_by_trick_order(pile)
    score[w] += 1
  }}
  winner: highest score
}}
"""

# How each row asks a Boolean `libf(card)`, typed as the row's own value.
_ROW_ASKS = {
    "trump": "libf(card)",
    "follow_class": "if libf(card) then card.suit else card.suit",
    "card_strength": "if libf(card) then 1 else 2",
}
# Each row's own body where the cell does not probe it.
_ROW_DEFAULT = {
    "trump": "card.suit is hearts",
    "follow_class": "card.suit",
    "card_strength": "rank_value(card)",
}


def _rows(probed: str) -> str:
    return "  ".join(
        f"{key}: {_ROW_ASKS[key] if key == probed else _ROW_DEFAULT[key]}"
        for key in TRICK_ORDER_ROW_KEYS
    )


@dataclass(frozen=True)
class RowArm:
    """A Boolean library body `function libf(c : Card) = ...`, the contract
    rows and game zones it needs, the game clauses it needs, and who owns its
    refusal from a row: the game (a library function is sound wherever it is
    called but from a row), the library (refused in every game), the `uses`
    line (a game clause the library needs), or None (a row may call it)."""

    body: str
    owner: str | None
    requires: str = ""
    zones: str = ""
    clauses: str = ""


def _pronoun_arms() -> dict[str, RowArm]:
    spelling = {
        "state": "c.suit is state.led_suit",
        "active_rules": "active_rules is active_rules",
        "actor": "actor is who",
        "action": "action.card is c",
        "winner": "winner is who",
    }
    assert set(spelling) == R._PRONOUNS
    return {
        f"pronoun-{p}": RowArm(
            body,
            # A call-site pronoun in a function body is refused to the
            # function's author in every game (`_check_functions`).
            LIBRARY if p in R._CALL_SITE_PRONOUNS else GAME,
        )
        for p, body in spelling.items()
    }


def _zone_arms() -> dict[str, RowArm]:
    arms: dict[str, RowArm] = {}
    for ztype in sorted(LIBRARY_ZONE_TYPES):
        kind = _TYPES[ztype][2]
        if kind == "position":
            # A library declares no `positions { }`, so it cannot contract a
            # position-indexed family: its own refusal, in every game.
            decl = f"probe[column] : {ztype}<column>"
            arms[f"zone-{ztype}"] = RowArm("true", LIBRARY, requires=decl, zones=decl)
            continue
        if kind == "none":
            decl, ref = f"probe : {ztype}", "probe"
        elif kind == "team":
            decl, ref = f"probe[team] : {ztype}<team>", "probe[team_of(who)]"
        else:
            decl, ref = f"probe[player] : {ztype}<player>", "probe[who]"
        arms[f"zone-{ztype}"] = RowArm(
            f"any card in {ref} where true",
            None if identity_to_all(ztype) else GAME,
            requires=decl,
            zones=decl,
            clauses="teams: [[0, 2], [1, 3]]" if kind == "team" else "",
        )
    return arms


# Each Builtin as a library writes it: the card a parameter, any seat the
# required `who`, the pile the contracted `pile`.
_CALL_SPELLINGS: dict[str, tuple[str, str]] = {
    "rank_value": ("rank_value(c) > 3", ""),
    "card_points": ("card_points(c) > 3", "card_points { A: 1 }"),
    "suit_of": ("suit_of(c) is c.suit", ""),
    "suit_value": ("suit_value(c.suit) > 0", "suit ranking: spades hearts diamonds clubs"),
    "team_of": ("team_of(who) is team_of(who)", "teams: [[0, 2], [1, 3]]"),
    "top_of": ("top_of(pile) is c", ""),
    "bottom_of": ("bottom_of(pile) is c", ""),
    "player_holding": ("player_holding(c) is who", ""),
    "error": ('if c.suit is c.suit then true else error("no")', ""),
    "lines": ("lines(3) is empty", ""),
    "neighbor": ("neighbor(who, who, who) is who", ""),
    "has_step": ("has_step(who, who, who)", ""),
    "is_diagonal": ("is_diagonal(who)", ""),
    "home": ("home(who) is empty", ""),
    "far_row": ("far_row(who) is who", ""),
    "highest_trump_or_led_suit": ("highest_trump_or_led_suit(pile, c.suit) is who", ""),
    "highest_by_trick_order": ("highest_by_trick_order(pile) is who", ""),
    "follows_lead": ("follows_lead(c, pile)", ""),
}


def _call_arms() -> dict[str, RowArm]:
    assert set(_CALL_SPELLINGS) == TRICK_ORDER_ROW_CALLS | TRICK_ORDER_ROW_UNCALLABLE
    from cardlang.builtins.functions import BOARD_ONLY_CALL_FUNCS, TRICK_ORDER_EXCLUDED_FUNCS

    arms: dict[str, RowArm] = {}
    for name, (body, clauses) in sorted(_CALL_SPELLINGS.items()):
        if name in TRICK_ORDER_ROW_CALLS:
            owner: str | None = None
        elif name in BOARD_ONLY_CALL_FUNCS or name in TRICK_ORDER_EXCLUDED_FUNCS:
            # A game clause the library's call needs, or one it is refused
            # beside: the `uses` line's clause gate speaks first.
            owner = USES
        else:
            owner = GAME
        arms[f"call-{name}"] = RowArm(body, owner, clauses=clauses)
    return arms


def _reader_arms(row: str) -> dict[str, RowArm]:
    order = {key: at for at, (key, _) in enumerate(TRICK_ORDER_ROWS)}
    spelled = {
        "is_trump": "is_trump(c)",
        "follow_class": "follow_class(c) is c.suit",
        "card_strength": "card_strength(c) > 0",
    }
    assert set(spelled) == set(TRICK_ORDER_READERS)
    arms: dict[str, RowArm] = {}
    for key, reader in TRICK_ORDER_ROWS:
        earlier = order[key] < order[row]
        arms[f"reader-{reader}"] = RowArm(spelled[reader], None if earlier else GAME)
    return arms


def _row_arms(row: str) -> dict[str, RowArm]:
    return {
        **_pronoun_arms(),
        "choose": RowArm("(choose integer in 0 .. 3) > 1", GAME),
        "bare-family": RowArm(
            "any card in shown where true",
            GAME,
            requires="shown[player] : PublicHand<player>",
            zones="shown[player] : PublicHand<player>",
        ),
        **_zone_arms(),
        **_call_arms(),
        **_reader_arms(row),
    }


def _row_crossing(row: str, arm: RowArm) -> Crossing:
    requires = "  ".join(
        r for r in ("who : Player", "pile : TrickPile", arm.requires) if r
    )
    library = (
        f"library {_LIB} {{\n  requires {{ {requires} }}\n"
        f"  function libf(c : Card) = {arm.body}\n}}\n"
    )
    host = _TRICK_HOST.format(clauses=arm.clauses, rows=_rows(row), zones=arm.zones)
    twin = host.replace(f"  uses {_LIB}\n", "") + f"function libf(c : Card) = {arm.body}\n"
    return Crossing(
        library, host, arm.owner,
        anchor=f"{row}: {_ROW_ASKS[row]}",
        needles=("`libf`",) if arm.owner == GAME else (),
        twin=twin,
    )


def _row_cells() -> list[object]:
    return [
        pytest.param(row, arm, id=f"{row}-{arm}")
        for row in TRICK_ORDER_ROW_KEYS
        for arm in _row_arms(row)
    ]


@pytest.mark.parametrize("row,arm", _row_cells())
def test_a_row_reaching_a_library_function(
    monkeypatch: pytest.MonkeyPatch, row: str, arm: str
) -> None:
    cell = _row_crossing(row, _row_arms(row)[arm])
    _assert_told(cell, _bag(monkeypatch, cell.library, cell.game))


# --- game to library: a decision where no one acts, made in a library function --
#
# `_HiddenReads`' walk for decisions no seat can make, from each place a game
# reads with no player acting (`resolve._NO_ACTOR_WHERE`).

_UNACTING_HOST = """game Boundary {{
  players: 2
  max_length: 50
  cards: standard52
  ranking: aces high
  uses boundarylib
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard }}
  state {{ score[player] : Integer = 0  bid : Integer = 0  done : Boolean = false  who : Player = 0 }}
  {phase}
  {result}
}}
"""
_DEAL = "shuffle deck\n    deal 1 card from deck to each hand"
_TRICK = (
    "round play_to_trick from 0 over all players source hand into pile "
    "winner highest_trump_or_led_suit"
)

# place -> (phase, result, the game text a refusal stands at)
_UNACTING_PLACES: dict[str, tuple[str, str, str]] = {
    R._NO_ACTOR_STATEMENT: (
        f"phase play {{\n    {_DEAL}\n    bid := libpick()\n  }}",
        "winner: highest score",
        "bid := libpick()",
    ),
    R._NO_ACTOR_GATE: (
        f"phase play when libpick() is 1 {{\n    {_DEAL}\n  }}",
        "winner: highest score",
        "when libpick() is 1",
    ),
    R._NO_ACTOR_RESULT: (
        f"phase play {{\n    {_DEAL}\n  }}",
        "loser: libpick()",
        "loser: libpick()",
    ),
    R._NO_ACTOR_ROUND: (
        f"phase play {{\n    {_DEAL}\n    mode open {{ transition_to: closed when play_to_trick "
        f"where libpick() is 1 }}\n    mode closed {{ }}\n    {_TRICK}\n  }}",
        "winner: highest score",
        "where libpick() is 1",
    ),
}

# need -> (the library function's body, its owner)
_UNACTING_NEEDS: dict[str, tuple[str, str]] = {
    "choose": ("choose integer in 0 .. 1", GAME),
    # `actor` in a function body is refused to its author in every game
    # (`_check_functions`), and told once.
    "actor": ("if actor is who then 0 else 1", LIBRARY),
}


def test_the_unacting_places_are_every_place_no_one_acts() -> None:
    """red under: add a place to `resolve._NO_ACTOR_WHERE`."""
    assert set(_UNACTING_PLACES) == set(R._NO_ACTOR_WHERE)


def _unacting_crossing(place: str, need: str) -> Crossing:
    phase, result, anchor = _UNACTING_PLACES[place]
    body, owner = _UNACTING_NEEDS[need]
    definition = f"function libpick() = {body}"
    library = f"library {_LIB} {{\n  requires {{ who : Player }}\n  {definition}\n}}\n"
    host = _UNACTING_HOST.format(phase=phase, result=result)
    twin = host.replace(f"  uses {_LIB}\n", "") + definition + "\n"
    return Crossing(
        library, host, owner, anchor=anchor,
        needles=("no player is acting", "`libpick`") if owner == GAME else (),
        twin=twin,
    )


@pytest.mark.parametrize(
    "place,need",
    [
        pytest.param(place, need, id=f"{place}-{need}")
        for place in sorted(_UNACTING_PLACES)
        for need in sorted(_UNACTING_NEEDS)
    ],
)
def test_a_decision_no_one_can_make_in_a_library_function(
    monkeypatch: pytest.MonkeyPatch, place: str, need: str
) -> None:
    cell = _unacting_crossing(place, need)
    bag = _bag(monkeypatch, cell.library, cell.game)
    _assert_told(cell, bag)
    assert len(bag) == 1, "\n".join(bag)


# --- game to library: a rule's clause calling a library function that reads `hand`
#
# `_check_play_source`, from every clause slot `resolve._rule_clauses` reads.


def _rule_clause_slots() -> tuple[str, ...]:
    """The `RuleDef` fields `_rule_clauses` reads, in its order."""
    tree = ast.parse(Path(R.__file__).read_text())
    fn = next(
        nd for nd in ast.walk(tree)
        if isinstance(nd, ast.FunctionDef) and nd.name == "_rule_clauses"
    )
    return tuple(
        dict.fromkeys(
            nd.attr for nd in ast.walk(fn)
            if isinstance(nd, ast.Attribute)
            and isinstance(nd.value, ast.Name) and nd.value.id == "rule"
        )
    )


_LED = "cards in hand where card.suit is hearts"
_RULE_SLOTS: dict[str, str] = {
    "applies_when": f"applies_when: {{e}} demands: {_LED} if_impossible: hand",
    "demands": "demands: cards in hand where {e} if_impossible: hand",
    "if_impossible": f"demands: {_LED} if_impossible: cards in hand where {{e}}",
    "exempts": f"demands: {_LED} if_impossible: hand exempts: cards in hand where {{e}}",
}


def test_the_rule_slots_are_every_clause_a_rule_reads() -> None:
    """red under: add a clause to `resolve._rule_clauses`."""
    assert set(_RULE_SLOTS) == set(_rule_clause_slots())


_RULE_HOST = """game Boundary {
  players: 3
  cards: standard52
  max_length: 200
  ranking: aces high
  uses boundarylib
  zones { deck : Deck  hand[player] : Hand<player>  pile : Discard }
  state { score[player] : Integer = 0 }
  phase setup { shuffle deck  deal 5 cards from deck to each hand }
  phase play { active_rules: [Probed] ROUND }
  winner: highest score
}
""".replace("ROUND", _TRICK)


def _play_source_crossing(slot: str) -> Crossing:
    definition = "function libbare() = any card in hand where true"
    library = (
        f"library {_LIB} {{\n  requires {{ hand[player] : Hand<player> }}\n"
        f"  {definition}\n}}\n"
    )
    rule = (
        "rule Probed { constrains: play_to_trick "
        + _RULE_SLOTS[slot].format(e="libbare()") + " }\n"
    )
    game = _RULE_HOST + rule
    twin = game.replace(f"  uses {_LIB}\n", "") + definition + "\n"
    return Crossing(
        library, game, GAME, anchor="libbare()",
        needles=("rule 'Probed'", "`libbare`"),
        twin=twin,
    )


@pytest.mark.parametrize(
    "slot", sorted(_RULE_SLOTS)
)
def test_a_rule_calling_a_library_function_that_reads_hand(
    monkeypatch: pytest.MonkeyPatch, slot: str
) -> None:
    cell = _play_source_crossing(slot)
    _assert_told(cell, _bag(monkeypatch, cell.library, cell.game))


# --- lifting a game's definitions into a library --------------------------------


def _requires_rows(game: str, definitions: str) -> list[str]:
    """The contract rows a library holding `definitions` needs from `game`:
    each zone and state variable the game declares that the definitions name,
    spelled as the game declares it, and each of the game's move types they
    offer."""
    tree = parse_text(game, "lift.cardlang")
    named = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", definitions))
    defined = set(re.findall(r"(?:function|procedure|move_type)\s+([A-Za-z_][A-Za-z_0-9]*)", definitions))
    rows: list[str] = []
    for z in tree.zones:
        if z.name in named and z.span is not None:
            rows.append(game[z.span.start:z.span.end])
    decls = [nd for nd in R._walk(tree) if isinstance(nd, n.StateDecl)]
    for d in decls:
        if d.name in named and d.span is not None:
            rows.append(game[d.span.start:d.span.end].split("=")[0].strip())
    for mt in tree.move_types:
        if mt.name in named and mt.name not in defined:
            rows.append(f"{mt.name} : Move")
    return rows


def _lift(game: str, definitions: str) -> tuple[str, str]:
    """`game` using a library that holds `definitions`, and that library."""
    rows = _requires_rows(game, definitions)
    requires = f"  requires {{ {'  '.join(rows)} }}\n" if rows else ""
    library = f"library {_LIB} {{\n{requires}{definitions}\n}}\n"
    lifted = re.sub(r"^(game \w+ \{)$", rf"\1\n  uses {_LIB}", game, count=1, flags=re.M)
    assert lifted != game, "no `game` header to add a `uses` line under"
    return lifted, library


# --- game to library: a Hosted Poll reaching library text -----------------------
#
# `_check_hosted_polls`, along every route its own grid derives
# (tests/test_hosted_poll.py, `ROUTES` from `resolve.HOSTED_REACH_POOLS`), with
# every payload that grid refuses.


_POLL_ROUTES = sorted(r for r in HP.ROUTES if r != "direct")
_POLL_PAYLOADS = sorted({*HP.EXPR_PAYLOADS, *HP.STMT_PAYLOADS})


def _poll_cells() -> list[object]:
    return [
        pytest.param(route, payload, id=f"{route}-{payload}")
        for route in _POLL_ROUTES
        for payload in _POLL_PAYLOADS
        if payload in HP.EXPR_PAYLOADS or HP.ROUTES[route][2]
    ]


def _alone_refused(library: str) -> bool:
    """Whether the library is refused against itself alone, before any game is
    consulted (`resolve.check_library_alone`): its own author's fault, in
    every game."""
    from cardlang.diagnostics import DiagnosticBag

    bag = DiagnosticBag()
    R.check_library_alone(parse_library(library, _LIB_FILE), bag)
    return bag.has_errors


def _poll_owner(route: str, payload: str, library: str) -> str:
    if _alone_refused(library):
        # A Primitive or a phase the library names: refused to its author.
        return LIBRARY
    if route == "run" and payload in HP.PROC_OWN_REFUSALS:
        # A procedure body may not hold it in any game (`_check_procedures`).
        return LIBRARY
    if route != "run" and payload in _MOVE_EFFECT_NEVER:
        # Nor may a move type's effect (the type layer's phase-only refusals).
        return LIBRARY
    return GAME


# The statements a move type's effect may hold in no game: phase control flow.
_MOVE_EFFECT_NEVER = frozenset({"Produce", "ContinueTo", "SkipToNextHand"})


def _poll_crossing(route: str, payload: str) -> Crossing:
    if payload in HP.EXPR_PAYLOADS:
        text, _words = HP.EXPR_PAYLOADS[payload]
        kw = HP._route_source(route, text, is_stmt=False)
    else:
        text, _words = HP.STMT_PAYLOADS[payload]
        kw = HP._route_source(route, text, is_stmt=True)
    needs = HP.SNIPPETS.get(payload, ("", {}))[1]
    # A library names no seat: the grid's filler statement, rewritten seat-free.
    definitions = kw.pop("extra").replace("score[0] += 0", "runs += 0")
    host = HP.source(**kw, **needs)
    game, library = _lift(host, definitions)
    owner = _poll_owner(route, payload, library)
    first = HP.ROUTES[route][0].splitlines()[-1].strip()
    anchor = re.split(r"[({]", first)[0].strip() if owner == GAME else None
    return Crossing(
        library, game, owner, anchor=anchor,
        needles=("the Hosted Poll",) if owner == GAME else (),
        twin=HP.source(**kw, **needs, extra=definitions),
    )


@pytest.mark.parametrize("route,payload", _poll_cells())
def test_a_hosted_poll_reaching_library_text(
    monkeypatch: pytest.MonkeyPatch, route: str, payload: str
) -> None:
    cell = _poll_crossing(route, payload)
    _assert_told(cell, _bag(monkeypatch, cell.library, cell.game))


# --- game to library: a decision a game position reaches through a library function
#
# `_HiddenReads.reads_of`, from every judged position of `HIDDEN_READ_POSITIONS`
# (tests/test_hidden_reads.py's builders), reading a zone through a library
# function that returns it.



def _judged_keys() -> list[str]:
    return sorted(HR._POSITIONS)


def _parses(text: str) -> bool:
    try:
        parse_text(text, "lift.cardlang")
    except DiagnosticError:
        return False
    return True


def _hidden_read_crossing(label: str) -> Crossing:
    """The position's identity read of a concealed zone, the zone returned by
    a library function; where the position's grammar holds a zone reference
    and no call (a chosen movement's source, a `cards in` query), the library
    function returns the seat whose zone is read instead."""
    _key, needs, build = HR._POSITIONS[label]
    need = "identity" if "identity" in needs else needs[0]
    zone = "secret[player] : HiddenPile<player>"
    body, defs = build(need, "libz()")
    definition, anchor = "function libz() = secret[leader]", "libz()"
    if not _parses(HR._game(body, defs, zone=zone)):
        body, defs = build(need, "secret[libseat()]")
        definition, anchor = "function libseat() = leader", "secret[libseat()]"
    host = HR._game(body, defs, zone=zone)
    game, library = _lift(host, definition)
    return Crossing(
        library, game, GAME, anchor=anchor, twin=host + definition + "\n",
        names_library=False,
    )


@pytest.mark.parametrize("label", _judged_keys())
def test_a_game_decision_reading_through_a_library_function(
    monkeypatch: pytest.MonkeyPatch, label: str
) -> None:
    """The position is the game's own text, so the refusal stands there and
    names the library's function on the route.

    red under: report a refused read at `read.span` in `_HiddenReads._judge`."""
    cell = _hidden_read_crossing(label)
    _assert_told(cell, _bag(monkeypatch, cell.library, cell.game))


# --- game to library: a library procedure the game runs ------------------------
#
# `_HiddenReads._run_body` judges a procedure's statements in the run site's
# acting context, so a library procedure's decision is decided by where the
# game runs it. The procedure is sound when some caller meets it: then every
# refusal its run makes is the game's, told at the `run`; when no caller can,
# it is the library's, told where the library wrote it.

_RUN_REQUIRES = (
    "requires { secret[player] : HiddenPile<player>  leader : Player  dealer : Player  "
    "hand[player] : Hand<player>  pile : Discard  bid : Integer  stock : Deck }"
)
_RUN_HOST = """game Boundary {{
  players: 3
  cards: standard52
  max_length: 200
  ranking: aces high
  uses boundarylib
  zones {{ deck : Deck  stock : Deck  hand[player] : Hand<player>  pile : Discard  secret[player] : HiddenPile<player> }}
  state {{ score[player] : Integer = 0  leader : Player = 0  dealer : Player = 1  bid : Integer = 0 }}
  phase setup {{ shuffle deck  deal 5 cards from deck to each hand }}
  phase play {{ {body} }}
  winner: highest score
}}
"""


# What a refusal of a procedure's decision says: its seat cannot see what
# it reads, or no one is there to decide.
_RUN_REFUSALS = ("cannot see", "no one can make the decision")


def _assert_run_told(cell: Crossing, bag: list[str]) -> None:
    """`_assert_told`, and a refusal told to the library offers no run of
    the procedure as its fix."""
    _assert_told(cell, bag)
    if cell.owner == LIBRARY:
        text = "\n".join(bag)
        assert any(why in text for why in _RUN_REFUSALS), text
        assert not any(_REMEDY.search(line) for line in bag), text


def _run_library(definitions: str) -> str:
    return f"library {_LIB} {{\n  {_RUN_REQUIRES}\n  {definitions}\n}}\n"


def _run_twin(definitions: str, body: str) -> str:
    """The same game with the library's definitions written in it."""
    return _run_game(body).replace(f"  uses {_LIB}\n", "") + definitions + "\n"


# The judged positions a procedure body can hold: the rows of
# `HIDDEN_READ_POSITIONS` a seat decides whose node is a statement or an
# expression, so it can be written inside a procedure.
def _procedure_positions() -> frozenset[tuple[type, str]]:
    held = {*typing.get_args(n.Stmt), *typing.get_args(n.Expr)}
    return frozenset(
        key
        for key, (kind, _) in R.HIDDEN_READ_POSITIONS.items()
        if kind in (R.READ_POSITION_SEAT, R.READ_POSITION_CHOSEN) and key[0] in held
    )


# position -> the procedure statement reading zone reference `z` there.
_RUN_POSITIONS: dict[tuple[type, str], Callable[[str], str]] = {
    (n.Choose, "lo"): lambda z: (
        f"bid := choose integer in (number of cards in {z} where rank_value(card) > 3) .. 13"
    ),
    (n.Choose, "hi"): lambda z: (
        f"bid := choose integer in 0 .. (number of cards in {z} where rank_value(card) > 3) up to 13"
    ),
    (n.Choose, "excluding"): lambda z: (
        f"bid := choose integer in 0 .. 13 excluding (number of cards in {z} where rank_value(card) > 3)"
    ),
    (n.Transfer, "amount"): lambda z: (
        f"move chosen (number of cards in {z} where rank_value(card) > 3) cards from hand to pile"
    ),
    (n.Transfer, "source"): lambda z: f"move chosen 1 card from {z} to pile",
    (n.Transfer, "where"): lambda z: f"move chosen 1 card from hand where any card in {z} where rank_value(card) > 3 to pile",
    (n.Transfer, "dest"): lambda z: (
        f"move chosen 1 card from hand to secret[if any card in {z} where rank_value(card) > 3 then leader else leader]"
    ),
}

# How the procedure names the zone it reads, and whether some caller meets
# it: by its parameter `p` and by a contracted seat it can be run as, or by
# a zone no seat sees and an index no `as` names, which no caller can.
_RUN_READERS: dict[str, tuple[str, bool]] = {
    "parameter": ("secret[p]", True),
    "state-variable": ("secret[leader]", True),
    "unseen-zone": ("stock", False),
    "unnamed-seat": ("secret[leader + 0]", False),
}

# Where the game runs it: no seat acting, the wrong seat, and the seat the
# procedure decides for.
_RUN_SITES: dict[str, str] = {
    "no-one-acts": "run libpr(leader)",
    "wrong-seat": "as dealer { run libpr(leader) }",
    "meeting-seat": "as leader { run libpr(leader) }",
}


def _position_label(key: tuple[type, str]) -> str:
    return f"{key[0].__name__}.{key[1]}"


def _run_position_crossing(position: tuple[type, str], reader: str, site: str) -> Crossing:
    zone, meetable = _RUN_READERS[reader]
    procedure = f"procedure libpr(p : Player) {{ {_RUN_POSITIONS[position](zone)} }}"
    run = _RUN_SITES[site]
    if not meetable:
        owner: str | None = LIBRARY
    else:
        owner = None if site == "meeting-seat" else GAME
    return Crossing(
        _run_library(procedure),
        _run_game(run),
        owner,
        anchor=run,
        twin=_run_twin(procedure, run),
    )


def _run_position_cells() -> list[object]:
    cells: list[object] = []
    for position in sorted(_procedure_positions(), key=_position_label):
        for reader in _RUN_READERS:
            for site in _RUN_SITES:
                cells.append(
                    pytest.param(
                        position, reader, site, id=f"{_position_label(position)}-{reader}-{site}"
                    )
                )
    return cells


def test_the_run_positions_are_the_judged_rows_a_procedure_holds() -> None:
    """Every judged position a procedure body can hold has a statement here.

    red under: move `(n.Transfer, "where")` to `READ_POSITION_OUTSIDE`."""
    assert set(_RUN_POSITIONS) == _procedure_positions()


@pytest.mark.parametrize(("position", "reader", "site"), _run_position_cells())
def test_a_library_procedure_run_reading_at_a_judged_position(
    monkeypatch: pytest.MonkeyPatch, position: tuple[type, str], reader: str, site: str
) -> None:
    """A read some caller can make is the game's to make where it runs the
    procedure; a read no caller can make is the library's, in every game.

    red under (the library cells): make `_HiddenReads._run_sink` give an
    empty `_meeting_callers` the any-player caller, so every refusal is told
    at the `run`."""
    cell = _run_position_crossing(position, reader, site)
    _assert_run_told(cell, _bag(monkeypatch, cell.library, cell.game))


@dataclass(frozen=True)
class RunCase:
    """The library's definitions, the phase body that runs them, who is told
    and, where the run stands outside the phase body, the game's own
    definitions holding it (`defs`) and the run itself (`at`)."""

    definitions: str
    body: str
    owner: str
    defs: str = ""
    at: str | None = None
    needles: tuple[str, ...] = ()

    @property
    def anchor(self) -> str:
        return self.at or self.body

    def game(self, body: str | None = None) -> str:
        return _run_game(body if body is not None else self.body) + self.defs

    def crossing(self) -> Crossing:
        return Crossing(
            _run_library(self.definitions), self.game(), self.owner, anchor=self.anchor,
            needles=self.needles,
            twin=self.game().replace(f"  uses {_LIB}\n", "") + self.definitions + "\n",
        )


# What a refusal of a read the game's own argument makes adds.
_BY_ARGUMENT = "the cards are read by the argument this `run` passes it"
# What a refusal adds where no run of the procedure as one seat passes with
# the arguments this `run` passes it.
_NO_RUN_FIX = "pass it only arguments that seat can see"

_RUN_CASES: dict[str, RunCase] = {
    "no-one-acts-choose": RunCase(
        "procedure libpr() { bid := choose integer in 0 .. 1 }", "run libpr()", GAME,
    ),
    "no-one-acts-chosen-movement": RunCase(
        "procedure libpr() { move chosen 1 card from hand to pile }", "run libpr()", GAME,
    ),
    "seat-passed-by-value": RunCase(
        "procedure libpr(p : Player) { move chosen 1 card from secret[p] to pile }",
        "as 0 { run libpr(1) }",
        GAME,
    ),
    "seat-the-run-acts-as": RunCase(
        "procedure libpr() { move chosen 1 card from secret[leader] to pile }",
        "as 0 { run libpr() }",
        GAME,
    ),
    # A game move type's effect runs it, for whichever seat is offered it.
    "run-by-a-game-move-type": RunCase(
        "procedure libpr() { move chosen 1 card from secret[leader] to pile }",
        "offer to leader one of [gmt]",
        GAME,
        defs="move_type gmt { effect { run libpr() } }\n",
        at="run libpr()",
    ),
    # The game's own argument reads the cards: the read is the game's text.
    "argument-calls-a-function": RunCase(
        "procedure libpr(k : Integer) { move chosen k cards from hand to pile }",
        "as leader { run libpr(high_cards(dealer)) }",
        GAME,
        needles=(_BY_ARGUMENT,),
    ),
    "argument-bound-by-a-let": RunCase(
        "procedure libpr(k : Integer) { move chosen k cards from hand to pile }",
        "as leader { let n = high_cards(dealer)  run libpr(n) }",
        GAME,
        at="run libpr(n)",
        needles=(_BY_ARGUMENT,),
    ),
    # The argument reads the seat the run acts as, and the body another: no
    # run as one seat passes with this argument.
    "argument-and-body-read-two-seats": RunCase(
        "procedure libpr(k : Integer) { move chosen k cards from secret[leader] to pile }",
        "as dealer { run libpr(high_cards(dealer)) }",
        GAME,
        needles=(_NO_RUN_FIX,),
    ),
    # No one seat sees both pools, so no caller meets the procedure, though
    # each statement alone is met by some caller.
    "two-seats": RunCase(
        "procedure libpr() { move chosen 1 card from secret[leader] to pile  "
        "move chosen 1 card from secret[dealer] to pile }",
        "as leader { run libpr() }",
        LIBRARY,
    ),
    # The procedure moves the seat it reads before reading it.
    "seat-written-before-it-is-read": RunCase(
        "procedure libpr() { leader := dealer  move chosen 1 card from secret[leader] to pile }",
        "as leader { run libpr() }",
        LIBRARY,
    ),
    # Each receiving seat decides, whoever runs it.
    "to-each-receiver": RunCase(
        "procedure libpr() { move chosen 1 card from secret[leader] to each hand }",
        "as leader { run libpr() }",
        LIBRARY,
    ),
    # A library move type runs it: library text throughout.
    "run-by-a-library-move-type": RunCase(
        "procedure libpr() { move chosen 1 card from secret[leader] to pile }  "
        "move_type libmt { effect { run libpr() } }",
        "offer to leader one of [libmt]",
        LIBRARY,
    ),
}
# The game's own definitions every run's game holds.
_RUN_GAME_DEFS = (
    "function high_cards(p : Player) = number of cards in secret[p] where rank_value(card) > 3\n"
)


def _run_game(run: str) -> str:
    return _RUN_HOST.format(body=run) + _RUN_GAME_DEFS


@pytest.mark.parametrize("case", sorted(_RUN_CASES))
def test_a_library_procedure_run_where_it_cannot_decide(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """red under (the library cells): make `_HiddenReads._run_sink` give
    an empty `_meeting_callers` the any-player caller, or push
    `False` for a library move type's effect in `_walk_game`; (the argument
    cells): drop the `run_args` arm of `_HiddenReads._tell`."""
    cell = _RUN_CASES[case].crossing()
    _assert_run_told(cell, _bag(monkeypatch, cell.library, cell.game))


def test_a_library_procedure_run_as_the_seat_it_reads_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control for the run family: the same procedure, run as the seat
    whose cards it reads, checks clean, so the library is sound for some
    caller."""
    case = _RUN_CASES["seat-the-run-acts-as"]
    library = _run_library(case.definitions)
    assert _bag(monkeypatch, library, case.game("as leader { run libpr() }")) == []


_REMEDY = re.compile(r"so run it [^:]*: `(as [^`]*)`")


def _run_fix_cells() -> list[tuple[str, str, str, str]]:
    """Every game-owned run cell: (id, library, the game, the run a fix
    replaces)."""
    cells = [
        (key, _run_library(case.definitions), case.game(), case.anchor)
        for key, case in sorted(_RUN_CASES.items())
        if case.owner == GAME
    ]
    for position in sorted(_procedure_positions(), key=_position_label):
        for reader in _RUN_READERS:
            for site in _RUN_SITES:
                cell = _run_position_crossing(position, reader, site)
                if cell.owner == GAME:
                    cells.append(
                        (
                            f"{_position_label(position)}-{reader}-{site}",
                            cell.library, cell.game, _RUN_SITES[site],
                        )
                    )
    return cells


@pytest.mark.parametrize(
    ("library", "game", "run"),
    [
        pytest.param(library, game, run, id=cell_id)
        for cell_id, library, game, run in _run_fix_cells()
    ],
)
def test_the_fix_a_run_is_told_passes(
    monkeypatch: pytest.MonkeyPatch, library: str, game: str, run: str
) -> None:
    """A run's refusals offer at most one run of the procedure, and that run,
    written in place of the game's own (a `<player>` in it spelled as seat
    0), checks clean; where they offer none, each says why.

    red under: in `_HiddenReads._run_sink`, offer the first of
    `_meeting_callers` without asking `_passing_fix`."""
    bag = _bag(monkeypatch, library, game)
    text = "\n".join(bag)
    fixes = {m.group(1) for line in bag for m in _REMEDY.finditer(line)}
    assert len(fixes) <= 1, text
    if not fixes:
        assert bag and all(_BY_ARGUMENT in line or _NO_RUN_FIX in line for line in bag), text
        return
    fix = fixes.pop().replace("<player>", "0")
    assert game.count(run) == 1, run
    assert _bag(monkeypatch, library, game.replace(run, fix)) == [], fix


# --- library to game: a game declaration the library's text depends on ----------
#
# Refusals decided by what the game declares, which no `requires` row names
# and no `resolve._CLAUSE_GATES` row routes to the `uses` line.

_DECLARED_GAP = (
    "issue #889: a library construct the game's own declarations refuse is "
    "told in the library's file"
)
_DECLARED_HOST = """game Boundary {{
  players: 3
  cards: standard52
  max_length: 200
  ranking: aces high
  uses boundarylib
  zones {{ deck : Deck  {zones}  pile : Discard }}
  state {{ score[player] : Integer = 0  who : Player = 0 }}
  phase setup {{ shuffle deck }}
  phase play {{ {body} }}
  winner: highest score
}}
"""
_LPLAY = "move_type lplay(c : Card) { effect { score[actor] += 1 } }"


def _declared_cases() -> dict[str, tuple[str, str]]:
    from cardlang.runtime import primitives

    action = sorted(primitives.climb_actions("tichu_lead_options"))[0]
    climb = HP.source().replace("game HostedMini {", f"game HostedMini {{\n  uses {_LIB}")
    return {
        "card-parameter-offered-by-the-library-with-no-hand": (
            f"library {_LIB} {{ requires {{ score[player] : Integer }} {_LPLAY}\n"
            "  procedure lask(p : Player) { offer to p one of [lplay] } }",
            _DECLARED_HOST.format(zones="stock[player] : Hand<player>", body="as 0 { run lask(0) }"),
        ),
        "card-parameter-over-a-hand-its-owner-cannot-see": (
            f"library {_LIB} {{ requires {{ score[player] : Integer }} {_LPLAY} }}",
            _DECLARED_HOST.format(
                zones="hand[player] : ChipStack<player>", body="as 0 { offer to 0 one of [lplay] }"
            ),
        ),
        "move-type-spelled-like-the-games-climb-engine-action": (
            f"library {_LIB} {{ move_type {action} {{ effect {{ }} }} }}",
            climb,
        ),
        "player-holding-over-a-single-hand": (
            f"library {_LIB} {{ requires {{ who : Player }} "
            "function lph(c : Card) = player_holding(c) is who }",
            _DECLARED_HOST.format(zones="hand : Discard", body="as 0 { score[0] := 1 }"),
        ),
    }


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            c, id=c,
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=_DECLARED_GAP),
        )
        for c in sorted(_declared_cases())
    ],
)
def test_a_library_construct_the_games_declarations_refuse(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    library, game = _declared_cases()[case]
    cell = Crossing(library, game, USES)
    _assert_told(cell, _bag(monkeypatch, cell.library, cell.game))


def test_each_game_declaration_case_is_refused_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """The #889 cells are red for the location alone: each is refused, in the
    library's file, so a fix moves the report and never the verdict."""
    for case, (library, game) in _declared_cases().items():
        bag = _bag(monkeypatch, library, game)
        assert bag and all(line.startswith(_LIB_FILE) for line in bag), (case, bag)


# --- library text a game activates or runs, judged once the game is known -------
#
# A library rule is judged when a game activates it, and a library procedure's
# rounds when a game runs it; each refusal names who owns it.

_ACTIVATING_HOST = """game Boundary {
  players: 3
  cards: standard52
  max_length: 200
  ranking: aces high
  uses boundarylib
  zones { deck : Deck  hand[player] : Hand<player>  pile : Discard }
  state { score[player] : Integer = 0 }
  phase setup { shuffle deck  deal 5 cards from deck to each hand }
  phase play { BODY }
  winner: highest score
}
"""
_PIECE_HOST = """game Boundary {
  players: 2
  pieces: breakthrough_men
  max_length: 200
  uses boundarylib
  zones { box : Deck  reserve[player] : PlayerPile<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase play { active_rules: [libr(hearts)] score[0] := 1 }
  winner: highest score
}
"""
_LEADS = "demands: cards in hand where card.suit is state.led_suit if_impossible: hand"
_ROUND_REQUIRES = "requires { hand[player] : Hand<player>  pile : Discard }"

# case -> (library, game, owner, the game text a game-owned refusal stands at)
_JUDGED_ONCE_KNOWN: dict[str, tuple[str, str, str, str | None]] = {
    "rule-activated-where-no-trick-round-asks-it": (
        f"library {_LIB} {{ rule librule {{ constrains: play_to_trick {_LEADS} }} }}",
        _ACTIVATING_HOST.replace("BODY", "active_rules: [librule] score[0] := 1"),
        GAME, "active_rules: [librule]",
    ),
    "rule-constraining-an-unknown-move-type": (
        f"library {_LIB} {{ rule librule {{ constrains: nosuch demands: hand if_impossible: hand }} }}",
        _ACTIVATING_HOST.replace("BODY", f"active_rules: [librule] {_TRICK}"),
        LIBRARY, None,
    ),
    "rule-enforcing-nothing": (
        f"library {_LIB} {{ rule librule {{ constrains: play_to_trick if_impossible: hand }} }}",
        _ACTIVATING_HOST.replace("BODY", f"active_rules: [librule] {_TRICK}"),
        LIBRARY, None,
    ),
    "rule-template-in-a-piece-game": (
        f"library {_LIB} {{ rule libr(piece : Suit) {{ constrains: play_to_trick "
        "demands: cards in hand where true if_impossible: hand } }",
        _PIECE_HOST, USES, None,
    ),
    "round-early-predicate": (
        f"library {_LIB} {{ {_ROUND_REQUIRES} procedure lr(p : Player) {{ round play_to_trick "
        "from p over all players source hand into pile winner highest_of_led_suit "
        "early on_play_off_led_suit } }",
        _ACTIVATING_HOST.replace("BODY", "run lr(0)"),
        LIBRARY, None,
    ),
    "climbing-round-and-its-hosted-poll": (
        f"library {_LIB} {{ {_ROUND_REQUIRES} procedure lc(p : Player) {{ round climb "
        "play_combination from p over all players source hand into pile combinations "
        "tichu_lead_options follows tichu_follows until true } }",
        _ACTIVATING_HOST.replace("BODY", "run lc(0)"),
        LIBRARY, None,
    ),
    "row-reaching-a-primitive": (
        f"library {_LIB} {{ function lp(c : Card) = skat_next_bid(0) > 3 }}",
        _TRICK_HOST.format(clauses="", rows=_rows("trump").replace("libf(card)", "lp(card)"), zones=""),
        LIBRARY, None,
    ),
}


@pytest.mark.parametrize("case", sorted(_JUDGED_ONCE_KNOWN))
def test_library_text_judged_once_the_game_is_known(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    library, game, owner, anchor = _JUDGED_ONCE_KNOWN[case]
    cell = Crossing(library, game, owner, anchor=anchor, names_library=owner == USES)
    _assert_told(cell, _bag(monkeypatch, cell.library, cell.game))


# --- library to game: the crossings an owning grid holds -------------------------
#
# Each family's whole cross lives in its own grid; one witness per arm runs
# here, by calling that grid's own cell, so the ledger reads the verdict the
# grid pins rather than restating it.


Witness = Callable[[pytest.MonkeyPatch], None]


def _bind(check: Callable[..., None], *args: object) -> Witness:
    """An owning grid's cell `check(monkeypatch, *args)`, as one witness."""

    def witness(monkeypatch: pytest.MonkeyPatch) -> None:
        check(monkeypatch, *args)

    return witness


def _cell(check: Callable[[typing.Any, pytest.MonkeyPatch], None], cell: object) -> Witness:
    """An owning grid's cell `check(cell, monkeypatch)`, as one witness."""

    def witness(monkeypatch: pytest.MonkeyPatch) -> None:
        check(cell, monkeypatch)

    return witness


def _answered_witnesses() -> dict[str, Witness]:
    """A library's text reaching the game's answer to its Definition Contract."""
    out: dict[str, Witness] = {}
    for key in CHR._KEYS:
        for route in ("answer", "library_function"):
            out[f"hidden-read-{CHR._label(key)}-{route}"] = _bind(
                CHR.test_a_read_through_an_answer_is_told_to_its_author, key, route, "secret"
            )
    out["no-one-acts-choose"] = CHR.test_a_choose_in_an_answer_read_where_no_one_acts_is_the_games
    out["no-one-acts-actor"] = CHR.test_actor_in_an_answer_read_where_no_one_acts_is_told_once
    out["play-source"] = (
        CHR.test_a_bare_hand_in_an_answer_a_library_rule_calls_is_told_a_fix_the_game_can_take
    )
    out["arrival-record"] = CHR.test_an_arrival_record_over_a_concealed_pile_in_an_answer_is_the_games
    out["call-cycle"] = DC.test_a_call_cycle_through_the_contract_is_the_games_to_break
    for answer, needle, label in (
        (
            "procedure settle(p : Player) { acted[actor] := true }",
            "procedure 'settle' reads the call-site pronoun 'actor'",
            "procedure",
        ),
        (
            "function ready(p : Player) = not acted[actor]",
            "function 'ready' reads the call-site pronoun 'actor'",
            "function",
        ),
    ):
        out[f"call-site-pronoun-{label}"] = _bind(
            DC.test_a_contracted_definition_reading_a_pronoun_is_told_a_fix_it_can_take,
            answer, needle,
        )
    for field, _noun in DC.contractable_kinds():
        out[f"contract-row-unanswered-{field}"] = _bind(
            DC.test_who_answers_a_definition_row, field, "absent"
        )
    return out


def _spellable(gate: CG.Gate) -> list[str]:
    return [
        m for m in sorted(gate.members & BUILTIN_CALL_FUNCS) if CG._probe(m).library_spellable
    ]


def _clause_witnesses() -> dict[str, Witness]:
    """A library's text needing a game clause: one unmet member per gate of
    `resolve._CLAUSE_GATES` (tests/test_library_clause_gates.py), and one
    library-reached member per member of the type layer's clause reads
    (tests/test_library_type_gates.py)."""
    out: dict[str, Witness] = {}
    for gate in CG.GATES:
        members = _spellable(gate)
        if members:
            out[f"clause-gate-{gate.name}"] = _cell(
                CG.test_clause_gate_cell, CG.Cell(gate, members[0], False, True)
            )
    by_gate: dict[str, CG.NodeMember] = {}
    for node_member in CG._node_members():
        by_gate.setdefault(node_member.gate, node_member)
    for name in CG.NODE_GATES:
        out[f"clause-gate-{name}"] = _cell(
            CG.test_node_gate_cell, CG.NodeCell(by_gate[name], False, True)
        )
    for type_member in TG._MEMBERS:
        out[f"type-gate-{type_member.name}"] = _cell(
            TG.test_kind_cell, TG.KindCell(type_member, "functions", "body", False, True)
        )
    return out


def _library_to_game_witnesses() -> dict[str, Witness]:
    return {**_answered_witnesses(), **_clause_witnesses()}


@pytest.mark.parametrize("witness", sorted(_library_to_game_witnesses()))
def test_a_library_reaching_the_games_text(monkeypatch: pytest.MonkeyPatch, witness: str) -> None:
    _library_to_game_witnesses()[witness](monkeypatch)


def test_every_clause_gate_has_a_witness() -> None:
    """Every gate the clause-gate grid runs has a library-reached witness here.

    red under: add a Builtin gate to `test_library_clause_gates.GATES` whose
    members no library can spell."""
    names = {
        k.removeprefix("clause-gate-") for k in _clause_witnesses() if k.startswith("clause-gate-")
    }
    assert names == {g.name for g in CG.GATES} | set(CG.NODE_GATES)


def test_every_clause_read_of_the_type_layer_names_its_owner() -> None:
    """Each type-layer read of a game clause is told to one owner, or holds an
    issue: `held` reads cite theirs.

    red under: register a `held` clause read whose reason cites no issue."""
    from cardlang.typecheck import CLAUSE_READS

    for key, read in CLAUSE_READS.items():
        assert read.verdict in {"library", "uses_line", "shadowed", "typing", "game_text", "held"}, key
        if read.verdict == "held":
            assert re.search(r"issue #\d+", read.reason), key


# --- the members held by a cited issue -----------------------------------------


def _held_cells() -> list[object]:
    cells: list[object] = []
    for param in CG._node_cells():
        p = typing.cast(typing.Any, param)
        for mark in p.marks:
            if mark.name == "xfail":
                reason = mark.kwargs["reason"]
                cells.append(pytest.param(
                    ("node", p.values[0]), id=f"clause-{p.id}",
                    marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason),
                ))
    for held in CG._HELD:
        cells.append(pytest.param(
            ("held", held), id=f"held-{held.name}",
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=held.reason),
        ))
    for form, (_body, reason) in sorted(TG._UNREACHED.items()):
        cells.append(pytest.param(
            ("seat", form), id=f"seat-{form}",
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason),
        ))
    cells.append(pytest.param(
        ("primitive-spelling", None), id="procedure-spelled-like-the-games-primitive",
        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #872"),
    ))
    return cells


_SEAT_HOST = """game Boundary {
  players: 3
  cards: standard52
  max_length: 200
  uses boundarylib
  zones { deck : Deck }
  state { score[player] : Integer = 0 }
  phase play { score[0] := 1 }
  winner: highest score
}
"""


@pytest.mark.parametrize("cell", _held_cells())
def test_a_crossing_an_issue_holds(monkeypatch: pytest.MonkeyPatch, cell: tuple[str, object]) -> None:
    kind, value = cell
    if kind == "node":
        CG.test_node_gate_cell(typing.cast(typing.Any, value), monkeypatch)
    elif kind == "held":
        CG.test_a_held_member_is_refused_on_the_uses_line(typing.cast(typing.Any, value), monkeypatch)
    elif kind == "seat":
        TG.test_an_unreached_seat_position_is_refused(str(value), monkeypatch)
    else:
        game = (Path(__file__).resolve().parent.parent / "docs" / "games" / "five-hundred.cardlang").read_text()
        lifted = re.sub(r"^(game \w+ \{)$", rf"\1\n  uses {_LIB}", game, count=1, flags=re.M)
        library = f"library {_LIB} {{ procedure five_hundred_bid_value() {{ }} }}"
        bag = _bag(monkeypatch, library, lifted)
        _assert_told(Crossing(library, lifted, USES), bag)


# --- the library's own text ------------------------------------------------------
#
# A library refused against itself alone is its author's fault in every game:
# one witness per check `resolve.check_library_alone` runs.

_ALONE_WITNESSES: dict[str, str] = {
    "_check_library_encapsulation": "function libf() = undeclared_name",
    "_check_contract_shapes": "requires { x : Rule }",
    "_check_require_indexes": "requires { seen[rank] : Integer }",
    "_refuse_play_source_params": (
        "rule librule(hand : Suit) { constrains: play_to_trick "
        "demands: cards in hand where card.suit is hand if_impossible: hand }"
    ),
}


def _library_alone_checks() -> set[str]:
    tree = ast.parse(Path(R.__file__).read_text())
    fn = next(
        nd for nd in ast.walk(tree)
        if isinstance(nd, ast.FunctionDef) and nd.name == "check_library_alone"
    )
    return {
        nd.func.id for nd in ast.walk(fn)
        if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
    }


def test_every_library_alone_check_has_a_witness() -> None:
    """red under: add a check to `resolve.check_library_alone`."""
    assert set(_ALONE_WITNESSES) == _library_alone_checks()


@pytest.mark.parametrize("check", sorted(_ALONE_WITNESSES))
def test_a_library_refused_against_itself(monkeypatch: pytest.MonkeyPatch, check: str) -> None:
    library = f"library {_LIB} {{ {_ALONE_WITNESSES[check]} }}"
    assert _alone_refused(library), check
    bag = _bag(monkeypatch, library, _SEAT_HOST)
    _assert_told(Crossing(library, _SEAT_HOST, LIBRARY), bag)


# --- the sentences a game's author reads ----------------------------------------

_SENTENCES: dict[str, str] = {
    "row": (
        "`trump:` reads zone 'probe' (HiddenPile) through library 'boundarylib''s "
        "function `libf`, which does not project identity to every observer — a "
        "Trick Order is public by construction and may read only fully public "
        "zones. `libf` is library 'boundarylib''s, so write the fact in the row "
        "from the card and public state instead of calling it"
    ),
    "row-bare-family": (
        "`trump:` reads `shown` bare (the acting player's instance) through "
        "library 'boundarylib''s function `libf` — a Trick Order row has no acting "
        "player. `libf` is library 'boundarylib''s, so write the fact in the row "
        "from the card and public state instead of calling it"
    ),
    "rule": (
        "rule 'Probed' calls library 'boundarylib''s function `libbare` from its "
        "clauses, which reads `hand`: inside a rule, `hand` is the cards the "
        "player on turn plays from, and a function cannot see which cards those "
        "are — `libbare` is library 'boundarylib''s, so write the filter in the "
        "rule's own clause (`cards in hand where ...`) instead of calling it"
    ),
    "no-one-acts": (
        "a `choose` (through library 'boundarylib''s function `libpick`) is written "
        "where no player is acting (a phase's `when` or `repeat until` is read "
        "between turns), so no one can make the decision. Make the decision "
        "before the gate is read -- in an earlier phase, or for `repeat until` in "
        "the phase's own body -- into a state variable (`as <player> { pick := "
        "choose ... }`), and read that variable here"
    ),
    "hosted-poll": (
        "the Hosted Poll (`before asking p`) may not hold a card movement, "
        "reached through library 'boundarylib''s procedure 'via' (run): it runs "
        "between two asks of a live climbing trick, where only decisions and "
        "state writes may happen. `via` is library 'boundarylib''s, so take it "
        "out of the Hosted Poll's body"
    ),
}


def _sentence_cell(name: str) -> Crossing:
    return {
        "row": lambda: _row_crossing("trump", _row_arms("trump")["zone-HiddenPile"]),
        "row-bare-family": lambda: _row_crossing("trump", _row_arms("trump")["bare-family"]),
        "rule": lambda: _play_source_crossing("demands"),
        "no-one-acts": lambda: _unacting_crossing(R._NO_ACTOR_GATE, "choose"),
        "hosted-poll": lambda: _poll_crossing("run", "Transfer"),
    }[name]()


@pytest.mark.parametrize("name", sorted(_SENTENCES))
def test_the_sentence_a_game_author_reads(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    cell = _sentence_cell(name)
    (line,) = _bag(monkeypatch, cell.library, cell.game)
    assert line.split(": error: ", 1)[1] == _SENTENCES[name]


# --- every remedy a crossing's refusal offers passes ----------------------------


def test_the_row_remedy_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """"write the fact in the row from the card and public state instead of
    calling it": the row written that way, the library still used, checks
    clean, for every row and every arm the game owns."""
    for row in TRICK_ORDER_ROW_KEYS:
        for name, arm in _row_arms(row).items():
            if arm.owner != GAME:
                continue
            cell = _row_crossing(row, arm)
            fixed = cell.game.replace(f"{row}: {_ROW_ASKS[row]}", f"{row}: {_ROW_DEFAULT[row]}")
            assert fixed != cell.game
            assert _bag(monkeypatch, cell.library, fixed) == [], (row, name)


def test_the_rule_filter_remedy_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """"write the filter in the rule's own clause (`cards in hand where
    ...`)": the library function's read written in the clause itself checks
    clean, from every clause slot."""
    for slot in _RULE_SLOTS:
        cell = _play_source_crossing(slot)
        fixed = cell.game.replace("libbare()", "any card in hand where true")
        assert _bag(monkeypatch, cell.library, fixed) == [], slot


def test_the_no_one_acting_remedy_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The decision made earlier into a state variable, and the variable read
    where the library function was called, checks clean at every place."""
    for place in _UNACTING_PLACES:
        cell = _unacting_crossing(place, "choose")
        fixed = cell.game.replace("libpick()", "bid")
        assert _bag(monkeypatch, cell.library, fixed) == [], place


def test_the_hosted_poll_remedy_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """"take it out of the Hosted Poll's body": the poll holding only its own
    statements, the library still used, checks clean on every route the game
    owns."""
    for route in _POLL_ROUTES:
        for payload in _POLL_PAYLOADS:
            if not (payload in HP.EXPR_PAYLOADS or HP.ROUTES[route][2]):
                continue
            cell = _poll_crossing(route, payload)
            if cell.owner != GAME:
                continue
            body = HP.ROUTES[route][0].format(x="", e="")
            fixed = cell.game.replace(HP.indent(body), HP.COUNTING)
            assert fixed != cell.game, (route, payload)
            if "nop" in body:
                # The game's own helper the poll offered, which nothing offers now.
                fixed = fixed.replace(HP.NOP, "")
            assert _bag(monkeypatch, cell.library, fixed) == [], (route, payload)


# --- the walkers, derived -------------------------------------------------------
#
# A refusal can sit in one author's text for the other's cause only where a
# check follows a call, a `run`, an offer or a closure out of the text it
# started in. Those checks are the functions that call the call-crossing
# helpers below, read off the passes' source.

_CROSSING_HELPERS = frozenset({
    "_definition_closure", "_reaches", "_reachable_definitions", "_reachable_nodes",
    "_call_reads", "_actor_needs_in", "_writes",
})
_DEFINITION_POOLS = frozenset({"functions", "procedures", "move_types", "fns", "procs", "pool"})
_PASSES = ("resolve", "typecheck", "expand")


def crossing_walkers() -> frozenset[str]:
    """Every `module.function` in the passes that calls a call-crossing helper
    or looks a definition up in a pool by name."""
    found: set[str] = set()
    for module in _PASSES:
        path = Path(R.__file__).with_name(f"{module}.py")
        tree = ast.parse(path.read_text())
        for top in tree.body:
            for fn in ast.walk(top):
                if not isinstance(fn, ast.FunctionDef):
                    continue
                owner = f"{top.name}." if isinstance(top, ast.ClassDef) else ""
                for nd in ast.walk(fn):
                    name: str | None = None
                    if isinstance(nd, ast.Call):
                        func = nd.func
                        if isinstance(func, ast.Name) and func.id in _CROSSING_HELPERS:
                            name = func.id
                        elif isinstance(func, ast.Attribute) and func.attr in _CROSSING_HELPERS:
                            name = func.attr
                        elif (
                            isinstance(func, ast.Attribute) and func.attr == "get"
                            and _pool_name(func.value) in _DEFINITION_POOLS
                        ):
                            name = "get"
                    elif isinstance(nd, ast.Subscript) and _pool_name(nd.value) in _DEFINITION_POOLS:
                        name = "subscript"
                    if name is not None and fn.name not in _CROSSING_HELPERS:
                        found.add(f"{module}.{owner}{fn.name}")
    return frozenset(found)


def _pool_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


# walker -> where its crossings are held
WALKERS: dict[str, str] = {
    "resolve._check_trick_order_rows": "test_a_row_reaching_a_library_function",
    "resolve._row_routes": "the routes `_check_trick_order_rows` locates its refusals by",
    "resolve._check_play_source": (
        "test_a_rule_calling_a_library_function_that_reads_hand; the answer's: "
        "test_a_library_reaching_the_games_text[play-source]"
    ),
    "resolve._check_hosted_polls": "test_a_hosted_poll_reaching_library_text",
    "resolve._HiddenReads.reads_of": (
        "test_a_game_decision_reading_through_a_library_function; the answer's: "
        "test_a_library_reaching_the_games_text[hidden-read-*]"
    ),
    "resolve._HiddenReads._refuse_unacting_decisions": (
        "test_a_decision_no_one_can_make_in_a_library_function; the answer's: "
        "test_a_library_reaching_the_games_text[no-one-acts-*]"
    ),
    "resolve._HiddenReads._run": (
        "test_a_library_procedure_run_reading_at_a_judged_position, "
        "test_a_library_procedure_run_where_it_cannot_decide"
    ),
    "resolve._HiddenReads._after": "liveness of an `as` state variable: refuses nothing itself",
    "resolve._check_functions": "test_a_library_reaching_the_games_text[call-cycle, call-site-pronoun-*]",
    "resolve._report_recursion": "test_a_library_reaching_the_games_text[call-cycle]",
    "resolve._check_unoffered_move_types": "reports the game's own move type, at its declaration",
    "resolve._check_implicit_pools": (
        "test_a_library_construct_the_games_declarations_refuse (issue #889)"
    ),
    "resolve._consumption_reachable_nodes": "a consumption question: reports the declaration asked about",
    "resolve._resolve_trump": "a consumption question: reports the game's `trump:`",
    "typecheck._call_sig": "types a call at its own site",
    "typecheck._check_contracted_results": "test_a_library_reaching_the_games_text[contract-row-*]",
    "typecheck._check_stmt_exprs": "types a `run`'s arguments at the run site",
    "expand._expansion": "splices a procedure body: refuses nothing",
}


def test_every_crossing_walker_is_classified() -> None:
    """A check that follows a call out of the text it started in either has
    its crossings held by a family here, or says why it has none. A new
    walker is red here until it is classified.

    red under: have `resolve._check_arrival_record_pile_args` call
    `_definition_closure`."""
    assert set(WALKERS) == crossing_walkers()


# --- the verdict does not move --------------------------------------------------


def _game_to_library_cells() -> list[Crossing]:
    cells: list[Crossing] = []
    for row in TRICK_ORDER_ROW_KEYS:
        cells.extend(_row_crossing(row, arm) for arm in _row_arms(row).values())
    cells.extend(
        _unacting_crossing(place, need) for place in _UNACTING_PLACES for need in _UNACTING_NEEDS
    )
    cells.extend(_play_source_crossing(slot) for slot in _RULE_SLOTS)
    cells.extend(_hidden_read_crossing(label) for label in _judged_keys())
    cells.extend(
        _poll_crossing(route, payload)
        for route in _POLL_ROUTES
        for payload in _POLL_PAYLOADS
        if payload in HP.EXPR_PAYLOADS or HP.ROUTES[route][2]
    )
    cells.extend(
        _run_position_crossing(position, reader, site)
        for position in sorted(_procedure_positions(), key=_position_label)
        for reader in _RUN_READERS
        for site in _RUN_SITES
    )
    cells.extend(case.crossing() for case in _RUN_CASES.values())
    return cells


def test_who_is_told_never_changes_what_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every game-to-library cell the game or no one owns is refused exactly
    when the same definitions, written in the game itself, are.

    red under: have `_check_trick_order_rows` skip a node reached through a
    library function."""
    for cell in _game_to_library_cells():
        if cell.owner not in (GAME, None) or cell.twin is None:
            continue
        crossed = bool(_bag(monkeypatch, cell.library, cell.game))
        inline = bool(_bag(monkeypatch, None, cell.twin))
        assert crossed == inline, (cell.owner, cell.game, cell.library)


# --- the finish line --------------------------------------------------------------


def _marked_cells() -> list[tuple[str, str, str]]:
    """Every (test, cell id, xfail reason) this module parametrizes with an
    xfail mark."""
    out: list[tuple[str, str, str]] = []
    module = sys.modules[__name__]
    for name, fn in vars(module).items():
        if not name.startswith("test_"):
            continue
        for mark in getattr(fn, "pytestmark", []):
            if mark.name != "parametrize":
                continue
            for param in mark.args[1]:
                for sub in getattr(param, "marks", ()):
                    if sub.name == "xfail":
                        out.append((name, str(param.id), str(sub.kwargs.get("reason", ""))))
    return out


def test_every_crossing_not_told_to_its_owner_cites_its_issue() -> None:
    """The epic's finish line, as a pin: every cell this ledger marks as not
    yet told to its owner names the issue that holds it, so the ledger has no
    unaddressed and uncited crossing.

    red under: drop the issue number from `_DECLARED_GAP`."""
    marked = _marked_cells()
    assert marked
    uncited = [(t, c) for t, c, reason in marked if not re.search(r"issue #\d+", reason)]
    assert uncited == []
