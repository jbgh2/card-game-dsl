"""A Hidden Read reached through a game's answer to a Definition Contract is
the game's (decisions.md "Family libraries", the Definition Contract
paragraph): a library is sound when some answer meets its row, so a read
only some answers make is the answer's, reported there.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a read a deciding seat cannot make, reached through a library
                 call of a contracted function, is refused once, in the
                 game's file, at the last text the game wrote on the way to
                 the read, naming the library, the row and the library's
                 decision position, with only remedies that pass; the same
                 read the library writes itself stays the library's; and the
                 refuse/accept outcome of every cell equals that of the same
                 read written inline in the library.
domain:          every judged position a library's text can hold (the
                 seat-deciding and chosen rows of `HIDDEN_READ_POSITIONS`
                 whose node kind a library reaches) crossed with every route
                 a read takes to it: written inline in the library; in the
                 game's answer; in a game helper the answer calls; in the
                 answer behind a library wrapper; in a library function the
                 answer calls with the game's seat and with the seat the
                 library passed; and in the answer, of the instance the
                 library's argument names -- each with a zone the deciding
                 seat cannot see and one every seat sees. Beside it: the
                 answer read at the game's own position through a library
                 wrapper; a contracted procedure and a contracted move type,
                 whose decisions are the game's own text; a decision each
                 receiving seat makes, and one Delegated Play routes; each
                 remedy a refusal offers, run; the other refusals reached
                 through an answer -- a `choose` and an `actor` where no
                 player is acting, a bare `hand` from a library rule, an
                 Arrival Record over a concealed pile; the library's own
                 indirections between its decision and its call (a rule
                 template the game turns on with an argument, a `let`, a
                 procedure argument); a computed seat the sentence cannot
                 quote; and the misuse probes (the library's own read handed
                 in as an argument, one answer asked at a game and a library
                 position, bare-family sugar in the answer). No library text
                 holds a position where no seat decides, so the no-seat rows
                 are outside by derivation; and a library holds no climbing
                 round, whose slots name Primitives (its own author is told
                 so), so no Hosted Poll's reach starts in library text.
registry:        positions: `cardlang.resolve.HIDDEN_READ_POSITIONS` restricted
                 by `tests.test_family_libraries._library_reachable_node_types`;
                 the inline verdict per position and zone type:
                 tests/test_hidden_reads.py; the host and the bag reader:
                 tests/test_definition_contracts.py.
does not prove:  that every position's sentence is whole: the move type's
                 `when:` and the two siblings are pinned exactly, the other
                 positions by location and needle.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass

import pytest

from cardlang import resolve as R
from cardlang.ast import nodes as n
from cardlang.parse import parse_library
from tests.test_definition_contracts import GAME, LIBRARY, _outcome
from tests.test_family_libraries import _library_reachable_node_types

_LIB_FILE = LIBRARY

# --- the positions, derived -------------------------------------------------


def library_positions() -> frozenset[tuple[type, str]]:
    """The judged positions a library's text can hold: every row of
    `HIDDEN_READ_POSITIONS` classed as a decision whose node kind some
    library field reaches."""
    reach = _library_reachable_node_types()
    judged = (R.READ_POSITION_NO_SEAT, R.READ_POSITION_SEAT, R.READ_POSITION_CHOSEN)
    return frozenset(
        key
        for key, (kind, _why) in R.HIDDEN_READ_POSITIONS.items()
        if kind in judged and key[0] in reach
    )


@dataclass(frozen=True)
class Position:
    """One position as a library writes it: the row kind its value takes, the
    place the expression `{e}` sits, the phrase a refusal names it by, and
    whether the host must activate the library's rule."""

    kind: str
    move_when: str = ""
    effect: str = ""
    rule: str = ""
    phrase: str = ""


_RULE = "rule watch {{ constrains: play_to_trick {clauses} }}"
_LED = "cards in hand where card.suit is state.led_suit"

_POSITIONS: dict[tuple[type, str], Position] = {
    (n.MoveTypeDef, "when"): Position("bool", move_when="when: {e}", phrase="move type `stay`'s `when:`"),
    (n.AppliesWhen, "pred"): Position(
        "bool",
        rule=_RULE.format(clauses=f"applies_when: {{e}} demands: {_LED} if_impossible: hand"),
        phrase="rule `watch`'s `applies_when:`",
    ),
    (n.Demands, "expr"): Position(
        "bool",
        rule=_RULE.format(clauses="demands: cards in hand where {e} if_impossible: hand"),
        phrase="rule `watch`'s `demands:`",
    ),
    (n.RuleDef, "if_impossible"): Position(
        "bool",
        rule=_RULE.format(clauses=f"demands: {_LED} if_impossible: cards in hand where {{e}}"),
        phrase="rule `watch`'s `if_impossible:`",
    ),
    (n.RuleDef, "exempts"): Position(
        "bool",
        rule=_RULE.format(
            clauses=f"demands: {_LED} if_impossible: hand exempts: cards in hand where {{e}}"
        ),
        phrase="rule `watch`'s `exempts:`",
    ),
    (n.Choose, "lo"): Position(
        "int", effect="pick[actor] := choose integer in ({e}) .. 3", phrase="a `choose`'s range"
    ),
    (n.Choose, "hi"): Position(
        "int", effect="pick[actor] := choose integer in 0 .. ({e}) up to 3", phrase="a `choose`'s range"
    ),
    (n.Choose, "excluding"): Position(
        "int",
        effect="pick[actor] := choose integer in 0 .. 3 excluding ({e})",
        phrase="a `choose`'s `excluding`",
    ),
    (n.Transfer, "amount"): Position(
        "int", effect="move chosen ({e}) cards from hand to pile", phrase="a chosen movement's amount"
    ),
    (n.Transfer, "source"): Position(
        "player", effect="move chosen 1 card from won[{e}] to pile", phrase="a chosen movement's source"
    ),
    (n.Transfer, "where"): Position(
        "bool", effect="move chosen 1 card from hand where {e} to pile", phrase="a chosen movement's `where`"
    ),
    (n.Transfer, "dest"): Position(
        "player", effect="move chosen 1 card from hand to won[{e}]", phrase="a chosen movement's destination"
    ),
}


def test_the_positions_are_every_judged_position_a_library_holds() -> None:
    """red under: move `(n.RuleDef, "exempts")` to `READ_POSITION_OUTSIDE`."""
    assert set(_POSITIONS) == library_positions()


def _label(key: tuple[type, str]) -> str:
    return f"{key[0].__name__}.{key[1]}"


_KEYS: list[tuple[type, str]] = sorted(_POSITIONS, key=_label)


# --- the row kinds: the row, the call, and a read of a zone as each type ------

_ROW = {
    "bool": ("ready", "ready(p : Player) : Boolean"),
    "int": ("count", "count(p : Player) : Integer"),
    "player": ("who", "who(p : Player) : Player"),
}


def _read(kind: str, zone: str, seat: str) -> str:
    """A read of the cards in `zone` as a value of `kind`; `seat` is the
    Player a `player` read returns."""
    if kind == "bool":
        return f"any card in {zone} where true"
    if kind == "int":
        return f"number of cards in {zone} where true"
    return f"if any card in {zone} where true then {seat} else {seat}"


def _announced(kind: str) -> str:
    """An answer from the game's state, which every seat sees."""
    return {"bool": "not acted[p]", "int": "pick[p]", "player": "p"}[kind]


# --- the routes -------------------------------------------------------------

ROUTES = (
    "inline",
    "answer",
    "game_helper",
    "library_wrapper",
    "library_function",
    "library_function_library_seat",
    "library_seat",
)


@dataclass(frozen=True)
class Built:
    """A cell's library text, game definitions, and the text in the game's
    definitions a refusal must point at (None: the library's own read)."""

    library: str
    defs: str
    anchor: str | None


def _build(key: tuple[type, str], route: str, zone: str) -> Built:
    pos = _POSITIONS[key]
    fn, row = _ROW[pos.kind]
    rows = [row]
    lib_defs: list[str] = []
    seat = "actor" if route == "inline" else "p"
    if route == "inline":
        rows = []
        expr = _read(pos.kind, f"{zone}[1]", "actor")
    elif route == "library_wrapper":
        lib_defs.append(f"function gate(p : Player) = {fn}(p)")
        expr = "gate(actor)"
    elif route in ("library_function_library_seat", "library_seat"):
        expr = f"{fn}(1)"
    else:
        expr = f"{fn}(actor)"
    defs = ""
    anchor: str | None = f"{zone}["
    if route in ("answer", "library_wrapper"):
        defs = f"function {fn}(p : Player) = {_read(pos.kind, f'{zone}[1]', seat)}"
    elif route == "library_seat":
        defs = f"function {fn}(p : Player) = {_read(pos.kind, f'{zone}[p]', seat)}"
    elif route == "game_helper":
        defs = (
            f"function peek(q : Player) = {_read(pos.kind, f'{zone}[1]', 'q')}\n"
            f"function {fn}(p : Player) = peek(p)"
        )
    elif route in ("library_function", "library_function_library_seat"):
        lib_defs.append(f"function libpeek(q : Player) = {_read(pos.kind, f'{zone}[q]', 'q')}")
        passed = "1" if route == "library_function" else "p"
        defs = f"function {fn}(p : Player) = libpeek({passed})"
        anchor = "libpeek("
    if route == "inline":
        anchor = None
    library = _library_text(pos, expr, rows, lib_defs)
    return Built(library, defs, anchor)


def _library_text(pos: Position, expr: str, rows: list[str], lib_defs: list[str]) -> str:
    body = "\n  ".join(
        [
            pos.rule.replace("{e}", expr) if pos.rule else "",
            *lib_defs,
        ]
    )
    when = pos.move_when.replace("{e}", expr)
    effect = pos.effect.replace("{e}", expr)
    text = (
        "library contractlib {\n  requires {\n    acted[player] : Boolean\n    {rows}\n  }\n"
        "  procedure ask(first : Player) {\n"
        "    turns t from first over players where not acted[player]\n"
        "          until (number of players where not acted[player]) is 0 {\n"
        "      offer to t one of [stay]\n    }\n  }\n"
        "  move_type stay { {when} effect { {effect} acted[actor] := true } }\n"
        "  {body}\n}\n"
    )
    text = text.replace("{when}", when).replace("{effect}", effect).replace("{body}", body)
    used = [
        decl
        for marker, decl in (
            ("from hand", "hand[player] : Hand<player>"),
            ("to pile", "pile : TrickPile"),
            ("from pile", "pile : TrickPile"),
            ("won[", "won[player] : PlayerPile<player>"),
            ("each won", "won[player] : PlayerPile<player>"),
            ("secret[", "secret[player] : HiddenPile<player>"),
            ("pick[", "pick[player] : Integer"),
        )
        if marker in text
    ]
    return text.replace("{rows}", "\n    ".join(dict.fromkeys(rows + used)))


_HOST = """game Host {
  uses contractlib
  players: 2
  cards: standard52
  ranking: aces high
  max_length: 200
  zones {
    deck : Deck
    hand[player] : Hand<player>
    pile : TrickPile
    won[player] : PlayerPile<player>
    secret[player] : HiddenPile<player>
  }
  state { acted[player] : Boolean = false  pick[player] : Integer = 0 }
  phase play {
    {active}
    round play_to_trick from 0 over all players source hand into pile
      winner highest_of_led_suit
    run ask(0)
  }
  winner: highest pick
}
"""


def _game(defs: str, active: bool, extra_play: str = "") -> str:
    text = _HOST.replace("{active}", "active_rules: [watch]" if active else "")
    if extra_play:
        text = text.replace("    run ask(0)\n", f"    run ask(0)\n    {extra_play}\n")
    return text + defs + "\n"


def _where(text: str, defs: str, anchor: str) -> str:
    """The `file:line:column` prefix a refusal at the first `anchor` in the
    game's definitions carries."""
    at = text.index(defs) + defs.index(anchor)
    line = text.count("\n", 0, at) + 1
    column = at - (text.rfind("\n", 0, at) + 1) + 1
    return f"{GAME}:{line}:{column}:"


def _bag(monkeypatch: pytest.MonkeyPatch, library: str, game: str) -> list[str]:
    return _outcome(monkeypatch, lambda: (parse_library(library, _LIB_FILE),), game)


# --- the grid ---------------------------------------------------------------


def _cells() -> list[object]:
    cells: list[object] = []
    for key in _KEYS:
        for route in ROUTES:
            for zone in ("secret", "won"):
                cells.append(pytest.param(key, route, zone, id=f"{_label(key)}-{route}-{zone}"))
    return cells


@pytest.mark.parametrize("key,route,zone", _cells())
def test_a_read_through_an_answer_is_told_to_its_author(
    monkeypatch: pytest.MonkeyPatch, key: tuple[type, str], route: str, zone: str
) -> None:
    """Each library position, each route, a concealed zone and a public one.
    The public zone is accepted on every route; the concealed one is refused
    once, to the library where the library wrote the read and to the game
    otherwise, at the game's last text on the way to it."""
    pos = _POSITIONS[key]
    built = _build(key, route, zone)
    game = _game(built.defs, bool(pos.rule))
    bag = _bag(monkeypatch, built.library, game)
    if zone == "won":
        assert bag == [], "\n".join(bag)
        return
    assert len(bag) == 1, "\n".join(bag)
    (line,) = bag
    if built.anchor is None:
        assert line.startswith(LIBRARY), line
        return
    assert line.startswith(_where(game, built.defs, built.anchor)), line
    fn, row = _ROW[pos.kind]
    for needle in ("library 'contractlib'", f"`{row}`", pos.phrase):
        assert needle in line, (needle, line)
    library_seat = route in ("library_seat", "library_function_library_seat")
    if library_seat:
        # The instance read is the one the library's argument names: the
        # sentence spells the game's own text and names what the library passes.
        assert f"`{zone}[p]`" in line and "passes `1` as `p`" in line, line
        assert "the seat the library passes" not in line, line
    else:
        assert f"`{zone}[1]`" in line, line
    if route == "game_helper":
        assert "through function `peek`" in line, line
    if route == "library_function":
        assert "through function `libpeek`" in line, line


def test_the_grid_commands_both_outcomes() -> None:
    """red under: make `_cells` emit only the `won` zone."""
    zones = {typing.cast(typing.Any, cell).values[2] for cell in _cells()}
    assert zones == {"secret", "won"}


# --- the verdict does not move ----------------------------------------------


def _refused(monkeypatch: pytest.MonkeyPatch, built: Built, rule: bool) -> bool:
    return bool(_bag(monkeypatch, built.library, _game(built.defs, rule)))


@pytest.mark.parametrize("key", _KEYS, ids=_label)
def test_every_route_is_refused_exactly_when_the_inline_read_is(
    monkeypatch: pytest.MonkeyPatch, key: tuple[type, str]
) -> None:
    """Who is told never changes what is refused: per position, every route's
    outcome on either zone equals the library's own inline read of it.

    red under: have `_HiddenReads._judge` skip a read that crossed a contract."""
    rule = bool(_POSITIONS[key].rule)
    for zone in ("secret", "won"):
        inline = _refused(monkeypatch, _build(key, "inline", zone), rule)
        for route in ROUTES:
            assert _refused(monkeypatch, _build(key, route, zone), rule) == inline, (route, zone)


# --- every remedy a refusal offers passes ------------------------------------


@pytest.mark.parametrize("key", _KEYS, ids=_label)
@pytest.mark.parametrize("remedy", ["every_seat_sees", "the_passed_seat", "announced"])
def test_each_offered_remedy_is_accepted(
    monkeypatch: pytest.MonkeyPatch, key: tuple[type, str], remedy: str
) -> None:
    """The fixes the refusal names, each taken in the game's answer: read a
    zone every seat sees; read the instance of the seat the library passes,
    where it passes the deciding seat; answer from the game's state."""
    pos = _POSITIONS[key]
    fn, _row = _ROW[pos.kind]
    built = _build(key, "answer", "secret")
    if remedy == "every_seat_sees":
        defs = f"function {fn}(p : Player) = {_read(pos.kind, 'won[1]', 'p')}"
    elif remedy == "the_passed_seat":
        defs = f"function {fn}(p : Player) = {_read(pos.kind, 'secret[p]', 'p')}"
    else:
        defs = f"function {fn}(p : Player) = {_announced(pos.kind)}"
    bag = _bag(monkeypatch, built.library, _game(defs, bool(pos.rule)))
    assert bag == [], "\n".join(bag)


def test_the_passed_seat_is_offered_only_where_it_is_the_deciders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library passes the deciding seat: the refusal offers its instance.
    It passes another seat: reading that seat's instance is what fails, so
    the refusal does not offer it. A zone its owner cannot see: no instance
    would do, so it is not offered either."""
    key = (n.MoveTypeDef, "when")
    offered = _bag(monkeypatch, _build(key, "answer", "secret").library, _game(
        _build(key, "answer", "secret").defs, False))
    assert any("the seat the library passes as `p`" in line for line in offered), offered
    seat = _build(key, "library_seat", "secret")
    withheld = _bag(monkeypatch, seat.library, _game(seat.defs, False))
    assert withheld and not any("the seat the library passes" in line for line in withheld)
    deck = _bag(
        monkeypatch,
        _build(key, "answer", "secret").library,
        _game("function ready(p : Player) = any card in deck where true", False),
    )
    assert deck and all(line.startswith(GAME) for line in deck), deck
    assert not any("the seat the library passes" in line for line in deck), deck


# --- the game's own position, through a library wrapper ----------------------


def test_a_game_position_reaching_its_answer_through_a_library_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The game's own move type calls the library's `gate`, which calls the
    game's answer: every text on the route but the wrapper is the game's, and
    the refusal is at the read, naming the library that calls the answer."""
    library = _library_text(
        Position("bool"),
        "true",
        ["ready(p : Player) : Boolean"],
        ["function gate(p : Player) = ready(p)"],
    )
    defs = (
        "function ready(p : Player) = any card in secret[1] where true\n"
        "move_type mine { when: gate(actor) effect { acted[actor] := true } }"
    )
    game = _game(defs, False, "offer to 0 one of [mine]")
    bag = _bag(monkeypatch, library, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(_where(game, defs, "secret[")), bag
    assert "move type `mine`'s `when:`" in bag[0] and "library 'contractlib'" in bag[0], bag


# --- the other refusals reached through an answer ----------------------------

_NO_ACTOR_LIBRARY = """library contractlib {
  requires {
    acted[player] : Boolean
    count(p : Player) : Integer
    pick[player] : Integer
  }
  procedure ask(first : Player) {
    pick[first] := count(first)
    turns t from first over players where not acted[player]
          until (number of players where not acted[player]) is 0 {
      offer to t one of [stay]
    }
  }
  move_type stay { effect { acted[actor] := true } }
}
"""


def test_a_choose_in_an_answer_read_where_no_one_acts_is_the_games(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library reads the answer where no player is acting; the answer
    makes a `choose`. Only the game can change that, so the game is told a fix
    it can take, never to wrap library text in `as`."""
    defs = "function count(p : Player) = choose integer in 0 .. 3"
    game = _game(defs, False)
    bag = _bag(monkeypatch, _NO_ACTOR_LIBRARY, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(_where(game, defs, "choose")), bag
    assert "library 'contractlib'" in bag[0] and "`count(p : Player) : Integer`" in bag[0], bag
    assert "Name who decides" not in bag[0], bag


def test_the_answer_to_a_no_one_acting_read_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fix the refusal above names: compute the answer from the
    parameter the row passes or from the game's state."""
    bag = _bag(monkeypatch, _NO_ACTOR_LIBRARY, _game("function count(p : Player) = pick[p]", False))
    assert bag == [], bag


def test_actor_in_an_answer_read_where_no_one_acts_is_told_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`actor` in an answer is the call-site pronoun refusal's, which sends the
    game to the parameter the row passes; nothing tells the game to wrap the
    library's text in `as`."""
    bag = _bag(monkeypatch, _NO_ACTOR_LIBRARY, _game("function count(p : Player) = actor", False))
    assert len(bag) == 1, bag
    assert bag[0].startswith(GAME) and "call-site pronoun 'actor'" in bag[0], bag


_RULE_LIBRARY = """library contractlib {
  requires {
    acted[player] : Boolean
    ok(c : Card) : Boolean
  }
  procedure ask(first : Player) {
    turns t from first over players where not acted[player]
          until (number of players where not acted[player]) is 0 {
      offer to t one of [stay]
    }
  }
  move_type stay { effect { acted[actor] := true } }
  rule watch { constrains: play_to_trick demands: cards in hand where ok(card) if_impossible: hand }
}
"""


def test_a_bare_hand_in_an_answer_a_library_rule_calls_is_told_a_fix_the_game_can_take(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library's rule calls the game's answer from its clauses; the
    answer reads bare `hand`. The filter is in library text, so the game is
    sent to the card the row passes, never told to move the filter."""
    defs = "function ok(c : Card) = c in hand"
    game = _game(defs, True)
    bag = _bag(monkeypatch, _RULE_LIBRARY, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(_where(game, defs, "hand")), bag
    assert "library 'contractlib'" in bag[0] and "`ok(c : Card) : Boolean`" in bag[0], bag
    assert "keep the filter in the rule" not in bag[0], bag


def test_the_answer_reading_the_passed_card_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fix the refusal above names: read the card the row passes."""
    bag = _bag(monkeypatch, _RULE_LIBRARY, _game("function ok(c : Card) = c.suit is hearts", True))
    assert bag == [], bag


def test_an_arrival_record_over_a_concealed_pile_in_an_answer_is_the_games(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Arrival Record's Owner Guard judges the call where it is written,
    whatever position reaches it: in an answer, that is the game's text.

    red under: report `_check_arrival_record_pile_args`' type refusal at
    `game.span`."""
    library = _RULE_LIBRARY
    defs = "function ok(c : Card) = follows_lead(c, secret[0])"
    game = _game(defs, True)
    bag = _bag(monkeypatch, library, game)
    assert bag and all(line.startswith(GAME) for line in bag), bag
    at = _where(game, defs, "follows_lead(")
    assert any(line.startswith(at) and "fully public pile" in line for line in bag), bag


# --- the other two contracted kinds: the decision is the game's own text -----

_KIND_LIBRARY = """library contractlib {
  requires {
    acted[player] : Boolean
    pick[player] : Integer
    {row}
  }
  procedure ask(first : Player) {
    turns t from first over players where not acted[player]
          until (number of players where not acted[player]) is 0 {
      offer to t one of [{offering}]
    }
  }
  move_type stay { effect { {use} acted[actor] := true } }
}
"""

_CONTRACTED_KIND: dict[str, tuple[str, str, str, str]] = {
    # row, the library's offering, the library's use, the game's answer
    "procedure": (
        "settle(p : Player) : Procedure",
        "stay",
        "run settle(actor)",
        "procedure settle(p : Player) {\n"
        "  pick[p] := choose integer in 0 .. (number of cards in secret[1] where true) up to 3\n}",
    ),
    "move_type": (
        "fold : Move",
        "stay, fold",
        "",
        "move_type fold { when: any card in secret[1] where true effect { acted[actor] := true } }",
    ),
}


@pytest.mark.parametrize("kind", sorted(_CONTRACTED_KIND))
def test_a_contracted_procedure_or_move_type_decides_in_the_games_text(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """A procedure row and a move row hand the library's decision to a
    definition whose positions are the game's own text, so the refusal is
    there already, at the game's position.

    red under: have `_HiddenReads._judge` report an uncrossed refusal with no
    span."""
    row, offering, use, answer = _CONTRACTED_KIND[kind]
    library = (
        _KIND_LIBRARY.replace("{row}", row).replace("{offering}", offering).replace("{use}", use)
    )
    game = _game(answer, False)
    bag = _bag(monkeypatch, library, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(GAME) and "`secret[1]`" in bag[0], bag


def test_a_read_every_receiving_seat_decides_is_told_without_the_passed_seat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chosen movement `to each` is decided by each receiving seat: the
    answer is told so, and no single seat's instance is offered as the fix."""
    pos = Position("int", effect="move chosen ({e}) cards from pile to each won")
    library = _library_text(pos, "count(actor)", ["count(p : Player) : Integer"], [])
    defs = "function count(p : Player) = number of cards in secret[1] where true"
    game = _game(defs, False)
    bag = _bag(monkeypatch, library, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(_where(game, defs, "secret[")), bag
    assert "not every receiving seat can see" in bag[0], bag
    assert "the seat the library passes" not in bag[0], bag


# --- misuse probes ----------------------------------------------------------


def test_a_read_in_the_librarys_own_argument_stays_the_librarys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library hands the answer a value its own text reads from a zone the
    deciding seat cannot see: the answer reads only its parameter, so the read
    is the library's, at the library's text."""
    library = _library_text(
        Position("bool"),
        "true",
        ["ready(b : Boolean) : Boolean", "secret[player] : HiddenPile<player>"],
        [],
    ).replace("move_type stay { ", "move_type stay { when: ready(any card in secret[1] where true) ")
    bag = _bag(monkeypatch, library, _game("function ready(b : Boolean) = b", False))
    assert len(bag) == 1, bag
    assert bag[0].startswith(LIBRARY) and "`secret[1]`" in bag[0], bag


def test_one_answer_read_at_a_game_position_and_a_library_position_is_told_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The game's own move type and the library's both ask the answer: two
    sentences at the one read, each naming its own position."""
    built = _build((n.MoveTypeDef, "when"), "answer", "secret")
    defs = built.defs + "\nmove_type mine { when: ready(actor) effect { acted[actor] := true } }"
    game = _game(defs, False, "offer to 0 one of [mine]")
    bag = _bag(monkeypatch, built.library, game)
    assert len(bag) == 2, bag
    assert all(line.startswith(GAME) for line in bag), bag
    assert any("library 'contractlib'" in line for line in bag), bag
    assert any("move type `mine`'s `when:`" in line for line in bag), bag


def test_an_answer_reading_bare_family_sugar_reads_the_deciders_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A designer writes the family bare in the answer, meaning the deciding
    seat's own: the body inherits the acting seat, so it is accepted."""
    built = _build((n.MoveTypeDef, "when"), "answer", "secret")
    bag = _bag(
        monkeypatch, built.library, _game("function ready(p : Player) = any card in secret where true", False)
    )
    assert bag == [], bag


def test_a_read_through_an_answer_under_delegated_play_names_the_routed_decider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under Delegated Play a rule's clauses are decided by
    `chooser_for(actor)`: the answer's refusal names that decider, still in
    the game's file."""
    key = (n.AppliesWhen, "pred")
    built = _build(key, "answer", "secret")
    defs = built.defs + "\nfunction chooser_for(p : Player) = if p is 1 then 0 else p"
    game = _game(defs, True)
    bag = _bag(monkeypatch, built.library, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(_where(game, defs, "secret[")), bag
    assert "`chooser_for(actor)`" in bag[0] and "library 'contractlib'" in bag[0], bag


# --- the library's own indirections before the call --------------------------

_COUNT_HIDDEN = "function count(p : Player) = number of cards in secret[1] where true"

_INDIRECTIONS: dict[str, tuple[Position, list[str], bool]] = {
    # The library's own text between its decision and its call of the answer.
    "rule_template": (
        Position(
            "bool",
            rule=(
                "rule watch(s : Suit) { constrains: play_to_trick applies_when: ready(actor) "
                "demands: cards in hand where card.suit is s if_impossible: hand }"
            ),
        ),
        [],
        True,
    ),
    "let": (
        Position("int", effect="let k = count(actor)\n pick[actor] := choose integer in 0 .. (k) up to 3"),
        [],
        False,
    ),
    "run_argument": (
        Position("int", effect="run chooser(actor, count(actor))"),
        ["procedure chooser(who : Player, k : Integer) { pick[who] := choose integer in 0 .. (k) up to 3 }"],
        False,
    ),
}


@pytest.mark.parametrize("via", sorted(_INDIRECTIONS))
def test_an_answer_reached_through_the_librarys_own_indirection_is_the_games(
    monkeypatch: pytest.MonkeyPatch, via: str
) -> None:
    """A rule template the game turns on with an argument, a `let` and a
    procedure argument in the library's text: the answer's read is told to
    the game at the read, whatever library text carries its value."""
    pos, lib_defs, rule = _INDIRECTIONS[via]
    fn, row = _ROW[pos.kind]
    library = _library_text(pos, "", [row], lib_defs)
    defs = _COUNT_HIDDEN if pos.kind == "int" else (
        "function ready(p : Player) = any card in secret[1] where true"
    )
    game = _game(defs, rule)
    if via == "rule_template":
        game = game.replace("active_rules: [watch]", "active_rules: [watch(hearts)]")
    bag = _bag(monkeypatch, library, game)
    assert len(bag) == 1, bag
    assert bag[0].startswith(_where(game, defs, "secret[")), bag
    assert "library 'contractlib'" in bag[0] and f"`{row}`" in bag[0], bag


def test_a_library_argument_no_index_spelling_reaches_is_named_by_what_it_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library passes a computed seat the sentence cannot quote: it says
    the seat is not shown to be the decider, never a placeholder."""
    built = _build((n.MoveTypeDef, "when"), "library_seat", "secret")
    library = built.library.replace("ready(1)", "ready(if acted[actor] then 1 else 0)")
    bag = _bag(monkeypatch, library, _game(built.defs, False))
    assert len(bag) == 1, bag
    assert "passes a seat it does not show to be the acting seat as `p`" in bag[0], bag
    assert "..." not in bag[0], bag


def test_the_passed_seat_remedy_through_a_library_function_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fix a read in a library function the answer calls is offered: hand
    the library function the seat the library passes."""
    for key in _KEYS:
        pos = _POSITIONS[key]
        fn, _row = _ROW[pos.kind]
        built = _build(key, "library_function", "secret")
        bag = _bag(
            monkeypatch,
            built.library,
            _game(f"function {fn}(p : Player) = libpeek(p)", bool(pos.rule)),
        )
        assert bag == [], (key, bag)


# --- the sentences, whole ----------------------------------------------------

_SENTENCES: dict[str, str] = {
    "answer": (
        "function `ready` reads the cards in `secret[1]`, which the acting seat "
        "cannot see, but library 'contractlib' calls it under its contract "
        "`ready(p : Player) : Boolean` in move type `stay`'s `when:`, which the "
        "acting seat decides, so the acting seat must be able to check it. Read "
        "cards every seat can see, or the cards of the seat the library passes as "
        "`p`, or have the holder announce or reveal the fact first"
    ),
    "library_seat": (
        "function `ready` reads the cards in `secret[p]`, and library 'contractlib' "
        "passes `1` as `p` when it calls it under its contract "
        "`ready(p : Player) : Boolean` in move type `stay`'s `when:`, which the "
        "acting seat decides, so the acting seat must be able to check it, but the "
        "acting seat cannot see them. Read cards every seat can see, or have the "
        "holder announce or reveal the fact first"
    ),
    "library_function": (
        "function `ready` reads the cards in `secret[1]` (through function "
        "`libpeek`), which the acting seat cannot see, but library 'contractlib' "
        "calls it under its contract `ready(p : Player) : Boolean` in move type "
        "`stay`'s `when:`, which the acting seat decides, so the acting seat must be "
        "able to check it. Read cards every seat can see, or the cards of the seat "
        "the library passes as `p`, or have the holder announce or reveal the fact "
        "first"
    ),
}


@pytest.mark.parametrize("route", sorted(_SENTENCES))
def test_the_sentence_a_game_author_reads(monkeypatch: pytest.MonkeyPatch, route: str) -> None:
    built = _build((n.MoveTypeDef, "when"), route, "secret")
    game = _game(built.defs, False)
    bag = _bag(monkeypatch, built.library, game)
    assert built.anchor is not None
    assert bag == [f"{_where(game, built.defs, built.anchor)} error: {_SENTENCES[route]}"], bag


def test_the_sentences_of_the_two_sibling_refusals(monkeypatch: pytest.MonkeyPatch) -> None:
    choose = _bag(
        monkeypatch, _NO_ACTOR_LIBRARY, _game("function count(p : Player) = choose integer in 0 .. 3", False)
    )
    assert [line.split(" error: ", 1)[1] for line in choose] == [
        "function `count` makes a `choose`, but library 'contractlib' calls it under "
        "its contract `count(p : Player) : Integer` where no player is acting "
        "(outside any `as <player>`, `for each player`, `turns` or offered move, "
        "nobody is taking a turn), so no one can make the decision. Compute the "
        "answer from the parameters the row passes, or from the game's own state"
    ], choose
    hand = _bag(monkeypatch, _RULE_LIBRARY, _game("function ok(c : Card) = c in hand", True))
    assert [line.split(" error: ", 1)[1] for line in hand] == [
        "function 'ok' reads `hand`, and rule 'watch' calls it from its clauses: "
        "inside a rule, `hand` is the cards the player on turn plays from, and a "
        "function cannot see which cards those are — library 'contractlib' calls it "
        "under its contract `ok(c : Card) : Boolean`, from text this game cannot "
        "edit, so the filter cannot move into the rule: read the card the row "
        "passes, or the game's own state"
    ], hand
