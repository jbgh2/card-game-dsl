"""A library construct the game's own declarations refuse is told in the game.

A family library's text can depend on a game declaration its `requires { }`
does not name: a `Card` parameter ranges over the acting seat's `hand`, a
Builtin reads a zone family no argument names, a move type takes a spelling
the game's climb engine owns, and a move type reaching a scoped Primitive
through the game's answer is judged by where the game's text offers it.
When the contract leaves the deciding declaration to the game, some game
meets the library and another does not, so the refusal is the game's: told
on its `uses` line, naming the library and its definition, with a fix the
game can take. When the contract names it, every game meeting the contract
is refused alike, and the refusal is the library's own, told where the
library wrote it. Who is told never changes what is refused.

Completeness ledger
-------------------
property:        every refusal of spliced library text that a game declaration
                 decides is told to the author who can act: on the game's
                 `uses` line, naming the library, when the library's contract
                 leaves the declaration to the game; where the library wrote
                 it when the contract names it; at the game's own text when
                 that text is the construct; every cell is refused exactly as
                 it is on the merge base; and every fix a `uses`-line refusal
                 offers checks clean.
domain:          four families. A `Card`-parameter move type in an offer: the
                 offering text (the game's phase, and every library
                 definition kind that holds statements) crossed with whose
                 move type it is (the library's, or the game's answer to a
                 `Move` row) and with the game's `hand` (none, a single zone,
                 one per team, and per player every zone type that does not
                 show its owner the cards), each declared `hand` crossed with
                 whether the library's contract names it; and two `Card`-
                 parameter move types in one offer, every pair of owners at
                 every offering text. Every Builtin reading a zone family no
                 argument names, called from every library definition kind,
                 over each `hand` that is not kept per player, crossed with
                 whether the contract names it. Every action of every climb
                 engine, spelled as a library move type in a corpus game
                 playing that engine, with a control a game of another
                 engine accepts. A move type reaching a scoped Primitive
                 through the game's answer to a `Procedure` row, at every
                 arm of the scoped-read containment check: offered nowhere,
                 offered from inside another move type, offered outside the
                 region, and run outside it from a library procedure, with
                 the move type the library's or the game's and the offering
                 text the game's or the library's. A `hand` absent from a game
                 a library's `player_holding` reads is accepted for game and
                 library alike (issue #869), so it is outside the grid.
registry:        zone types: `stdlib.zones.LIBRARY_ZONE_TYPES`, its owner
                 projection `stdlib.zones.reveals`; implicit reads:
                 `builtins.functions.BUILTIN_IMPLICIT_READS`; climb engines:
                 `builtins.functions.PRIMITIVE_CLIMB_LEADS` and
                 `runtime.primitives.climb_actions`; definition kinds:
                 `resolve._LIBRARY_DEF_KINDS`; the `Card` parameter's family:
                 `resolve.POOL_FROM_CARD_PARAMETERS`; the harness:
                 tests/test_library_boundary_ledger.py.
does not prove:  that a sentence is whole: cells pin its file, its line and
                 the library's name. Nor that a library procedure no game
                 runs, whose offer is judged all the same, is told the same in
                 a game that runs it elsewhere: the procedure cells run it
                 once, from the game's phase.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

import cardlang.resolve as R
from cardlang.builtins.functions import BUILTIN_IMPLICIT_READS, PRIMITIVE_CLIMB_LEADS
from cardlang.runtime import primitives
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, reveals
from tests.test_hidden_reads import _TYPES
from tests.test_library_boundary_ledger import (
    _LIB,
    GAME,
    LIBRARY,
    USES,
    Crossing,
    _assert_told,
    _bag,
)

_GAP = (
    "issue #889: a library construct the game's own declarations refuse is "
    "told in the library's file"
)

# --- the hosts --------------------------------------------------------------------

_HOST = """game Boundary {{
  players: 3
  cards: standard52
  max_length: 200
  ranking: aces high
  {teams}
  uses boundarylib
  zones {{ deck : Deck  stock[player] : Hand<player>  {zones}  pile : Discard }}
  state {{ score[player] : Integer = 0  who : Player = 0 }}
  phase setup {{ shuffle deck }}
  phase play {{ {body} }}
  winner: highest score
}}
{extra}"""

_FAMILY = re.findall(r"`(\w+)`", R.POOL_FROM_CARD_PARAMETERS)[0]
_TEAMS = "teams: [[0], [1, 2]]"


def _host(zones: str, body: str, extra: str = "") -> str:
    teams = _TEAMS if "[team]" in zones else ""
    return _HOST.format(teams=teams, zones=zones, body=body, extra=extra)


def _library(requires: tuple[str, ...], definitions: str) -> str:
    rows = "  ".join(requires)
    contract = f"requires {{ {rows} }}\n  " if rows else ""
    return f"library {_LIB} {{\n  {contract}{definitions}\n}}\n"


@dataclass(frozen=True)
class Cell:
    """One crossing: the library, the game, who is told, what the refusal
    says (`said`, a phrase of the check's own sentence, so a refusal for
    another reason is no verdict), and the game text a game-owned refusal
    stands at."""

    library: str
    game: str
    owner: str | None
    said: str = ""
    anchor: str | None = None
    names_library: bool = True
    gap: bool = False

    def crossing(self) -> Crossing:
        return Crossing(
            self.library, self.game, self.owner, anchor=self.anchor,
            needles=(self.said,) if self.said else (),
            names_library=self.names_library,
        )


# --- the `hand` a game declares -------------------------------------------------


def _hiding_types() -> list[str]:
    """Every zone type that does not show its owner the cards in it, which a
    family kept per player can be declared: an owned type takes the owner
    argument, an unowned one is indexed by player all the same. A position-
    indexed type is no seat's zone."""
    return sorted(
        t for t in LIBRARY_ZONE_TYPES
        if not reveals(t, "identity", True) and _TYPES[t][2] in ("player", "none")
    )


def _per_player(ztype: str) -> str:
    owner = "<player>" if _TYPES[ztype][2] == "player" else ""
    return f"{_FAMILY}[player] : {ztype}{owner}"


# hand -> its declaration in the game ("" when the game declares none)
_NOT_PER_PLAYER: dict[str, str] = {
    "single": f"{_FAMILY} : Discard",
    "team": f"{_FAMILY}[team] : TeamPile<team>",
}


def _hands() -> dict[str, str]:
    return {
        "none": "",
        **_NOT_PER_PLAYER,
        **{f"hiding-{t}": _per_player(t) for t in _hiding_types()},
    }


# --- family 1: a `Card`-parameter move type in an offer --------------------------

# offering text -> (the library definition holding the offer of `{m}`, the
# game statement putting it in play). The game's phase offers it itself.
_OFFERERS: dict[str, tuple[str, str]] = {
    "game": ("", "as 0 {{ offer to 0 one of [{m}] }}"),
    "procedures": (
        "procedure lask(p : Player) {{ offer to p one of [{m}] }}",
        "as 0 {{ run lask(0) }}",
    ),
    "move_types": (
        "move_type lrelay {{ effect {{ offer to actor one of [{m}] }} }}",
        "as 0 {{ offer to 0 one of [lrelay] }}",
    ),
}


def test_the_offering_texts_are_every_library_kind_that_holds_statements() -> None:
    """A function's body is an expression and a rule holds clauses, so neither
    holds an `offer`; every other kind a library defines does.

    red under: add a statement-holding kind to `resolve._LIBRARY_DEF_KINDS`."""
    kinds = {field for field, _ in R._LIBRARY_DEF_KINDS} - {"functions", "rules"}
    assert set(_OFFERERS) - {"game"} == kinds


_LPLAY = "move_type lplay(c : Card) { effect { score[actor] += 1 } }"
_GPLAY = "move_type gplay(c : Card) { effect { score[actor] += 1 } }\n"
_GPLAY2 = "move_type gplay2(c : Card) { effect { score[actor] += 2 } }\n"
_LPLAY2 = "move_type lplay2(c : Card) { effect { score[actor] += 2 } }"


def _card_pool_cell(offerer: str, mover: str, hand: str, contracted: bool) -> Cell:
    holding, statement = _OFFERERS[offerer]
    name = "lplay" if mover == "library" else "gplay"
    requires = ["score[player] : Integer"]
    definitions = [_LPLAY] if mover == "library" else []
    if mover == "game":
        requires.append("gplay : Move")
    if holding:
        definitions.append(holding.format(m=name))
    zone = _hands()[hand]
    if contracted:
        requires.append(zone)
    library = _library(tuple(requires), "\n  ".join(definitions))
    body = statement.format(m=name)
    game = _host(zone, body, _GPLAY if mover == "game" else "")
    no_hand = hand in ("none", *_NOT_PER_PLAYER)
    said = f"`{_FAMILY}[player]`" if no_hand else "does not show its owner the cards"
    if mover == "game" and not no_hand:
        # The game's own move type over its own `hand`: the game's text.
        return Cell(
            library, game, GAME, said, anchor="gplay(c : Card)", names_library=False
        )
    if contracted and mover == "library":
        # No game meeting the contract can offer the move type.
        return Cell(library, game, LIBRARY, said, gap=offerer == "game" and no_hand)
    if offerer == "game" and no_hand:
        # The game's own offer names the move type: the game's text.
        return Cell(library, game, GAME, said, anchor=body, names_library=False)
    return Cell(library, game, USES, said, gap=True)


def _card_pool_cells() -> dict[str, Cell]:
    cells: dict[str, Cell] = {}
    for offerer in _OFFERERS:
        for mover in ("library", "game"):
            if offerer == "game" and mover == "game":
                continue  # no library text on the route
            for hand in _hands():
                for contracted in (False, True) if hand != "none" else (False,):
                    key = f"{offerer}-offers-{mover}-move-hand-{hand}" + (
                        "-contracted" if contracted else ""
                    )
                    cells[key] = _card_pool_cell(offerer, mover, hand, contracted)
    return cells


# Two `Card`-parameter move types in one offer: whose each is.
_PAIRS: dict[str, tuple[str, str]] = {
    "library-library": ("lplay", "lplay2"),
    "library-game": ("lplay", "gplay"),
    "game-game": ("gplay", "gplay2"),
}


def _two_card_moves_cell(offerer: str, pair: str) -> Cell:
    holding, statement = _OFFERERS[offerer]
    names = ", ".join(_PAIRS[pair])
    requires = ["score[player] : Integer"]
    definitions: list[str] = []
    extra = ""
    for name in _PAIRS[pair]:
        if name.startswith("l"):
            definitions.append(_LPLAY if name == "lplay" else _LPLAY2)
        else:
            if holding:
                requires.append(f"{name} : Move")
            extra += _GPLAY if name == "gplay" else _GPLAY2
    if holding:
        definitions.append(holding.format(m=names))
    library = _library(tuple(requires), "\n  ".join(definitions))
    body = statement.format(m=names)
    game = _host(f"{_FAMILY}[player] : Hand<player>", body, extra)
    said = "indistinguishable"
    if offerer == "game":
        return Cell(library, game, GAME, said, anchor=body, names_library=False)
    if pair == "library-library":
        return Cell(library, game, LIBRARY, said)
    # The game's answer to a `Move` row is what puts a second card play beside
    # the first: some answer meets the library.
    return Cell(library, game, USES, said, gap=True)


def _two_card_moves_cells() -> dict[str, Cell]:
    return {
        f"{offerer}-offers-two-card-moves-{pair}": _two_card_moves_cell(offerer, pair)
        for offerer in _OFFERERS
        for pair in _PAIRS
        if not (offerer == "game" and pair == "game-game")
    }


# --- family 2: a Builtin reading a zone family no argument names ------------------

# Builtin -> a Boolean reading of it, `c` a card and `who` a seat.
_IMPLICIT_SPELLINGS: dict[str, str] = {"player_holding": "player_holding({c}) is who"}


def test_every_implicit_read_has_a_spelling() -> None:
    """red under: add a Builtin to `BUILTIN_IMPLICIT_READS`."""
    assert set(_IMPLICIT_SPELLINGS) == set(BUILTIN_IMPLICIT_READS)


# definition kind -> (the library definition asking `{e}`, the game statement
# reaching it). A rule is no holder: a game asking a rule that declares `hand`
# as anything but a zone kept per player is refused for the name at its zone,
# since a rule's bare `hand` is the cards the player on turn plays from.
_IMPLICIT_HOLDERS: dict[str, tuple[str, str]] = {
    "functions": ("function lask(c : Card) = {e}", "as 0 {{ score[0] := 1 }}"),
    "procedures": (
        "procedure lask(p : Player) {{ if any card in stock[p] where {e} {{ who := p }} }}",
        "as 0 {{ run lask(0) }}",
    ),
    "move_types": (
        "move_type lask {{ when: any card in stock[actor] where {e} effect {{ }} }}",
        "as 0 {{ offer to 0 one of [lask] }}",
    ),
}


def test_the_implicit_holders_are_every_library_definition_kind_but_a_rule() -> None:
    """red under: add a kind to `resolve._LIBRARY_DEF_KINDS`."""
    kinds = {field for field, _ in R._LIBRARY_DEF_KINDS}
    assert set(_IMPLICIT_HOLDERS) == kinds - {"rules"}


def _implicit_cell(builtin: str, holder: str, hand: str, contracted: bool) -> Cell:
    family = BUILTIN_IMPLICIT_READS[builtin][0]
    assert family == _FAMILY, family
    definition, statement = _IMPLICIT_HOLDERS[holder]
    asked = _IMPLICIT_SPELLINGS[builtin].format(c="c" if holder == "functions" else "card")
    zone = _NOT_PER_PLAYER[hand]
    requires = ["who : Player", "stock[player] : Hand<player>"]
    if contracted:
        requires.append(zone)
    library = _library(tuple(requires), definition.format(e=asked))
    game = _host(zone, statement.format())
    return Cell(
        library, game, LIBRARY if contracted else USES,
        "finds the player holding a card", gap=not contracted,
    )


def _implicit_cells() -> dict[str, Cell]:
    return {
        f"{builtin}-in-{holder}-over-{hand}-hand" + ("-contracted" if contracted else ""):
            _implicit_cell(builtin, holder, hand, contracted)
        for builtin in sorted(BUILTIN_IMPLICIT_READS)
        for holder in _IMPLICIT_HOLDERS
        for hand in _NOT_PER_PLAYER
        for contracted in (False, True)
    }


# --- family 3: a library move type spelled like the game's climb engine's action --

_GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _engine_games() -> dict[str, str]:
    """Each climb engine to the corpus game whose climbing round plays it."""
    found: dict[str, str] = {}
    for path in sorted(_GAMES.glob("*.cardlang")):
        text = path.read_text()
        for engine in sorted(PRIMITIVE_CLIMB_LEADS):
            if re.search(rf"\bcombinations\s+{engine}\b", text):
                found.setdefault(engine, path.name)
    return found


def test_every_climb_engine_has_a_corpus_game() -> None:
    """red under: register a climb engine no corpus game plays."""
    assert set(_engine_games()) == set(PRIMITIVE_CLIMB_LEADS)


def _with_uses(file_name: str) -> str:
    text = (_GAMES / file_name).read_text()
    lifted = re.sub(r"^(game \w+ \{)$", rf"\1\n  uses {_LIB}", text, count=1, flags=re.M)
    assert lifted != text
    return lifted


def _climb_cells() -> dict[str, Cell]:
    cells: dict[str, Cell] = {}
    games = _engine_games()
    for engine in sorted(PRIMITIVE_CLIMB_LEADS):
        game = _with_uses(games[engine])
        for action in primitives.climb_actions(engine):
            library = _library((), f"move_type {action} {{ effect {{ }} }}")
            cells[f"{engine}-{action}"] = Cell(
                library, game, USES, "spelled like the climb engine", gap=True
            )
    # The control: an action of one engine, in a game playing another that
    # owns no such action.
    owned = {e: set(primitives.climb_actions(e)) for e in PRIMITIVE_CLIMB_LEADS}
    for engine in sorted(PRIMITIVE_CLIMB_LEADS):
        for other in sorted(PRIMITIVE_CLIMB_LEADS):
            spare = sorted(owned[other] - owned[engine])
            if spare and f"control-{engine}" not in cells:
                library = _library((), f"move_type {spare[0]} {{ effect {{ }} }}")
                cells[f"control-{engine}"] = Cell(library, _with_uses(games[engine]), None)
    return cells


# --- family 4: a library move type's scoped-read containment ----------------------

_SCOPED_HOST = """game Boundary {{
  players: 2
  max_length: 100
  cards: pinochle48
  ranking: A 10 K Q J 9
  uses boundarylib
  primitives {{
    pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit in outer
  }}
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ meld[player] : Integer = 0 }}
  phase outer {{
    state {{ trump_suit : Suit? = spades }}
    shuffle deck
    deal 12 cards from deck to each hand
    {inside}
  }}
  phase after {{
    {outside}
  }}
  winner: highest meld
}}
{extra}"""
_SETTLE = """procedure settle() {
  for each player p: meld[p] := pinochle_meld_value(p)
}
"""
_IDLE = "meld[0] := 0"
_LNOTE = "move_type lnote { effect { run settle() } }"
_GNOTE = "move_type gnote {\n  when: pinochle_meld_value(actor) >= 0\n  effect { meld[0] := meld[0] }\n}\n"
_LRELAY = "move_type lrelay {{ effect {{ offer to actor one of [{m}] }} }}"
_GRELAY = "move_type grelay {{\n  effect {{ offer to actor one of [{m}] }}\n}}\n"
_LSHOW = "procedure lshow(p : Player) {{ offer to p one of [{m}] }}"


def _scoped_cell(arm: str, mover: str, site: str) -> Cell:
    """`arm` of `resolve._check_offered_containers` for a move type (`mover`'s)
    reaching the scoped Primitive, its offer written by `site`."""
    m = "lnote" if mover == "library" else "gnote"
    requires = ["settle() : Procedure"] if mover == "library" else [f"{m} : Move"]
    definitions = [_LNOTE] if mover == "library" else []
    extra = _GNOTE if mover == "game" else _SETTLE
    inside, outside = _IDLE, _IDLE
    anchor: str | None = None
    if arm == "unoffered":
        pass
    elif arm == "walled":
        if site == "library":
            definitions.append(_LRELAY.format(m=m))
            inside = "as 0 { offer to 0 one of [lrelay] }"
        else:
            extra += _GRELAY.format(m=m)
            inside = "as 0 { offer to 0 one of [grelay] }"
            anchor = f"effect {{ offer to actor one of [{m}] }}"
    elif arm == "offered-outside":
        outside = f"as 0 {{ offer to 0 one of [{m}] }}"
        anchor = outside
    else:  # run-outside
        definitions.append(_LSHOW.format(m=m))
        outside = "as 0 { run lshow(0) }"
        anchor = outside
    library = _library(tuple(requires), "\n  ".join(definitions))
    game = _SCOPED_HOST.format(inside=inside, outside=outside, extra=extra)
    said = "reads state declared in phase"
    if anchor is not None:
        return Cell(library, game, GAME, said, anchor=anchor, names_library=False)
    return Cell(library, game, USES, said, gap=True)


# arm -> the offering texts it can be written by: none, for a move type
# nothing offers; the game's phase or move type; a library's move type or
# procedure.
_SCOPED_ARMS: dict[str, tuple[str, ...]] = {
    "unoffered": ("none",),
    "walled": ("library", "game"),
    "offered-outside": ("game",),
    "run-outside": ("library",),
}


def _scoped_cells() -> dict[str, Cell]:
    """Every arm, at every text that can write it, for a move type the
    library or the game defines; a cell with no library text on the route
    is the game's alone, and no crossing."""
    return {
        f"{arm}-{mover}-move-type" + (f"-by-{site}" if site != "none" else ""):
            _scoped_cell(arm, mover, site)
        for arm, sites in _SCOPED_ARMS.items()
        for mover in ("library", "game")
        for site in sites
        if mover == "library" or site == "library"
    }


# --- the grid -----------------------------------------------------------------

_FAMILIES: dict[str, Callable[[], dict[str, Cell]]] = {
    "card-pool": _card_pool_cells,
    "two-card-moves": _two_card_moves_cells,
    "implicit-read": _implicit_cells,
    "climb-action": _climb_cells,
    "scoped-read": _scoped_cells,
}


def _cells() -> dict[str, Cell]:
    return {
        f"{family}:{key}": cell
        for family, build in _FAMILIES.items()
        for key, cell in build().items()
    }


def _params() -> list[object]:
    return [
        pytest.param(
            key, id=key,
            marks=(
                [pytest.mark.xfail(strict=True, raises=AssertionError, reason=_GAP)]
                if cell.gap else []
            ),
        )
        for key, cell in _cells().items()
    ]


def test_every_refused_cell_names_what_it_is_refused_for() -> None:
    """A cell refused for another reason (a syntax error, a contract unmet)
    passes for the wrong reason unless it pins the check's own phrase.

    red under: drop `said` from a `_climb_cells` cell."""
    assert [k for k, c in _cells().items() if c.owner is not None and not c.said] == []


@pytest.mark.parametrize("key", _params())
def test_a_library_construct_a_game_declaration_decides(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    cell = _cells()[key]
    _assert_told(cell.crossing(), _bag(monkeypatch, cell.library, cell.game))
