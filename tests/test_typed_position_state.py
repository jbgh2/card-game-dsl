"""A state variable typed by the board's named-member position domain.

A designer remembers a square -- the piece mid-capture, the square a shuttle
left -- as `chain_from : cell? = none`, writes it with `chain_from := dest`
and reads it with `chain_from is none` or `from is chain_from`, as a
`Player?` variable is read and written. Three seams carry it, each dark until
the one before it opens: resolve admits the type name
(`resolve._declared_type_universe`, read by the `StateDecl` arm of
`_validate_refs`); the type checker types the variable from the game's
position domains (`typecheck.type_from_name`, whose domain parameters every
caller passes); and the runtime stores whatever the variable is assigned.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a `state` variable's declared type names a value type or one
                 of the game's named-member position domains, scalar or
                 indexed by seat or team, and nothing else; a named-member
                 one types `cell` (`cell?` with `?`), never the permissive
                 top, so every type Owner Guard reads it; every refusal this
                 module pins names a declaration or a test that, taken as
                 written, checks or plays in the game it is told in; and a
                 `none` square is refused in designer words where a square
                 must be named at play.
domain:          GRID D, the declaration: the state type -- every value type
                 in `KNOWN_TYPE_NAMES` as the control, the board's
                 named-member domain, an integer position domain, the
                 direction domain, `Combination`, an unknown name. The
                 named-member domain is crossed with index (scalar,
                 `[player]`, `[team]`), optional, default and declaring site
                 (game-level and phase-local `state { }`); each refused class
                 has one row per kind of game that tells it differently (a
                 board minting directions, `morris9` minting none, a
                 boardless card game, a boardless piece game, a boardless
                 game declaring an integer domain spelled `cell`), and each
                 such row has a FIX_TAKEN row. GRID R, the reads and writes:
                 every statement and expression position a `Player?`
                 variable is consumed at, on a scalar `cell?` and on a
                 per-seat store, the `winner:` target among them. GRID P,
                 play: the scalar anchor and the per-seat store end to end,
                 and a `none` square reaching each route that needs a
                 square -- a zone subscript, a move's destination, a user
                 function's `cell` parameter, a per-seat key, a Builtin, a
                 collection form's source -- each with its named fix played. A library's `state { }`
                 and `requires` rows are a different domain: a library
                 declares no board, its type slot admits the value types
                 (`resolve._library_slot_names`), and a `requires` row
                 cannot spell `?`. What the variable's value shows each seat
                 is the proof module's of the first game that writes it
                 (issue #983).
registry:        value types: typecheck.KNOWN_TYPE_NAMES; position domains:
                 `game.positions` partitioned by `PositionDecl.members_named`;
                 index roles: domains.ZONE_INDEX_ROLES; direction domain:
                 board_domains.DIRECTION_DOMAIN, minted per game by
                 `resolve._minted_directions`; content: types.Flavor; the
                 sibling grid over every declaring position:
                 tests/test_type_name_positions.py::test_the_board_names_grid;
                 a `none` at a Builtin slot: tests/test_direction_lift.py.
held by:         the state admit-set is Derived and Pinned. It has one
                 defining site, `resolve._declared_type_universe`, which the
                 `StateDecl` arm of `resolve._validate_refs` reads as it is
                 and `resolve._check_declared_type_names` extends, so the two
                 checks cannot spell the state set twice. The named-member
                 partition it is built from is spelled again wherever
                 `git grep -n "members_named is" -- cardlang` finds it:
                 resolve's `_declared_type_universe`, `_state_type_refusal`,
                 `_resolve_positions`, `_resolve_board`, `_minted_directions`
                 and `_validate_refs`, typecheck's `_position_types` and
                 `_ambient_env`, and ir's `_position`;
                 GRID D's admit rows and the sibling grid pin what those
                 sites say together. The typing is Derived and Pinned:
                 `type_from_name` takes the game's domains as required
                 parameters, so a caller that omits them does not
                 type-check, but an empty mapping does, and the plants below
                 pin that each state-typing site passes the game's own. The
                 refusal classes are Derived and Pinned: a declared type name
                 reaches resolve as source text, so no union classifies it
                 before resolve does; GRID D pins each class's message and
                 FIX_TAKEN its fix. The `none` key is Derived and Pinned at
                 the key's Owner Guard, `state.ZoneStore.instance`:
                 `types.coercible` admits an optional where its base is
                 wanted, and the flow narrowing that would make the case
                 unwritable is issue #990.
does not prove:  that a caller hands `type_from_name` the game's OWN domains
                 beyond the two state-typing sites the plants exercise: an
                 empty mapping type-checks as well as the right one.
red under:       GRID D's admit and default cells, GRID R and GRID P are born
                 red, and the `StateDecl` arm reading `KNOWN_TYPE_NAMES` in
                 place of the helper reddens all of them, the indexed rows
                 included. Passing `{}` for the positions of
                 `typecheck._check_state_default_type` reddens the `none`,
                 Integer and String default cells at every index and site;
                 passing `{}` for the positions of `typecheck._ambient_env`'s
                 state typing reddens GRID R's type refusals, scalar and
                 per-seat, and its `membership` row. In
                 `resolve._state_type_refusal`, dropping the minted-`dir`
                 branch reddens `board-dir?`, dropping the unminted one
                 reddens `morris9-dir?` and `boardless-dir?`, and telling
                 every boardless game the card game's fix reddens
                 `boardless-pieces-cell?`. Dropping the `None` branch of
                 `state.ZoneStore.instance` reddens GRID P's four zone rows,
                 and `evaluate._subscript` passing no `optional_key` reddens
                 the `zone-subscript` and `move-destination` rows. The
                 value-type controls are born green and redden if the helper
                 drops `KNOWN_TYPE_NAMES`; the indexed-store refusal is born
                 green and reddens if the index arm admits the named-member
                 domains; the `a1` rows are born green and redden if resolve
                 reads a board member's name as a value;
                 `test_every_owned_refusal_has_its_fix_taken` reddens if a
                 FIX_TAKEN row is dropped.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import EndedBy, GameResult, play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.typecheck import KNOWN_TYPE_NAMES


class CellMismatch(AssertionError):
    """A grid cell's outcome differed from its authored expectation; a
    designed-to-flip mark constrained to it cannot be met by a harness
    failure."""


BOARD_GAME = """game G {
  players: 2
  direction: clockwise
  max_length: 40
%(teams)s  board: %(family)s
  pieces: xo_marks
%(positions)s
  zones {
    box             : Deck
    square[cell]    : Cell<cell>
    reserve[player] : PlayerPile<player>
  }
  state {
    result[player] : Integer = 0
    done           : Boolean = false
    n              : Integer = 0
%(state)s
  }
  phase setup {
    move all pieces from box where piece.side is x to reserve[0]
    move all pieces from box to reserve[1]
%(setup)s
  }
  phase play {
%(phase_state)s
    turns t from 0 over all players until done {
      offer to t one of [place, stop]
    }
  }
  winner: %(winner)s
}
%(functions)s
move_type place(at : cell) {
  when: %(when)s
  effect {
    move one piece from reserve[actor] to square[at]
%(effect)s
  }
}
move_type stop {
  when: %(stop_when)s
  effect {
%(stop_effect)s
    done := true
  }
}
"""

BOARDLESS_GAME = """game G {
  players: 2
  max_length: 40
  cards: standard52
%(positions)s
  zones { deck : Deck  hand[player] : Hand<player> }
  state {
    result[player] : Integer = 0
    done           : Boolean = false
%(state)s
  }
  phase play {
    turns t from 0 over all players until done {
      offer to t one of [stop]
    }
  }
  winner: highest result
}
move_type stop { effect { done := true } }
"""

TEAMS = "  teams: [[0], [1]]\n"


def board(**slots: str) -> str:
    filled = {
        "teams": "", "family": "grid(3, 3)", "positions": "", "state": "",
        "setup": "", "phase_state": "", "functions": "",
        "when": "square[at] is empty", "effect": "", "stop_when": "true",
        "stop_effect": "", "winner": "highest result",
    }
    filled.update(slots)
    return BOARD_GAME % filled


def boardless(**slots: str) -> str:
    filled = {"positions": "", "state": ""}
    filled.update(slots)
    return BOARDLESS_GAME % filled


def boardless_pieces(state: str) -> str:
    """A boardless game whose content is pieces rather than cards."""
    return (
        boardless(state=state)
        .replace("  cards: standard52\n", "  pieces: xo_marks\n")
        .replace("deck : Deck  hand[player] : Hand<player>", "box : Deck")
    )


def _verdict(source: str) -> str | None:
    """None for a program that checks; the first diagnostic's message for one
    that does not."""
    try:
        check_dsl(source, "typed_position_state.cardlang")
    except DiagnosticError as exc:
        return exc.diagnostic.message
    return None


ACCEPT = None
Expected = str | tuple[str, ...] | None

# The cells a change designs to flip, carried as strict xfails so the grid can
# be pushed red; empty between changes.
RED: frozenset[str] = frozenset()


def _param(cid: str, *values: object) -> object:
    marks = [pytest.mark.xfail(strict=True, raises=CellMismatch)] if cid in RED else []
    return pytest.param(*values, id=cid, marks=marks)


def _expect(source: str, expected: Expected) -> None:
    got = _verdict(source)
    if expected is None:
        if got is not None:
            raise CellMismatch(f"expected the program to check, got: {got}")
        return
    needles = (expected,) if isinstance(expected, str) else expected
    if got is None:
        raise CellMismatch(f"expected a refusal naming {needles}, the program checked")
    missing = [s for s in needles if s not in got]
    if missing:
        raise CellMismatch(f"the refusal lacks {missing}: {got}")


# The refusal each refused class owns, in the words its fix needs.
INTEGER_DOMAIN = ("is typed `column`", "a position domain of numbers", "as an `Integer`")
DIRECTION = (
    "is typed `dir`",
    "a move or function parameter takes a direction (`along : dir`)",
    "a state variable cannot hold one",
)
UNMINTED_DIRECTION = ("is typed `dir`", "board family 'morris9' mints no directions", "as a `cell?`")
NO_BOARD_DIRECTION = ("is typed `dir`", "declares no `board:`", "as a `SeatDirection`")
NO_BOARD_CARDS = ("is typed `cell`", "declares no `board:`", "`pieces:` in place of `cards:`, and a `board:`")
NO_BOARD_PIECES = ("is typed `cell`", "declares no `board:`", "declare the `board:` its pieces stand on")
INTEGER_CELL = ("is typed `cell`", "a position domain of numbers", "as an `Integer`")
OWNED_REFUSALS = (
    INTEGER_DOMAIN, INTEGER_CELL, DIRECTION, UNMINTED_DIRECTION, NO_BOARD_DIRECTION, NO_BOARD_CARDS,
    NO_BOARD_PIECES,
)


# --- GRID D: the declaration ---------------------------------------------------

DECL_CELLS: list[tuple[str, str, Expected]] = []

# The value types: the control, admitted before and after.
for _t in sorted(KNOWN_TYPE_NAMES):
    DECL_CELLS.append((f"value-{_t}?", board(state=f"    v : {_t}? = none"), ACCEPT))

# The named-member domain, crossed with index, optional, default and site. A
# `[team]` store is declared in a game with teams.
_PRIOR = "    prior : cell? = none\n"
for _index in ("", "[player]", "[team]"):
    for _site in ("game", "phase"):
        def _at(decl: str, site: str = _site, index: str = _index) -> str:
            decl = decl.replace("v :", f"v{index} :", 1)
            teams = TEAMS if index == "[team]" else ""
            if site == "game":
                return board(teams=teams, state=_PRIOR + f"    {decl}")
            return board(teams=teams, state=_PRIOR, phase_state=f"    state {{ {decl} }}")

        _row = f"{_site}{_index}"
        DECL_CELLS += [
            (f"{_row}-cell?-none", _at("v : cell? = none"), ACCEPT),
            (f"{_row}-cell-none", _at("v : cell = none"), "declared Cell, but its default has type none"),
            (f"{_row}-cell?-3", _at("v : cell? = 3"), "declared Cell?, but its default has type Integer"),
            (f"{_row}-cell-3", _at("v : cell = 3"), "declared Cell, but its default has type Integer"),
            (f"{_row}-cell?-string", _at('v : cell? = "a1"'), "declared Cell?, but its default has type String"),
            (f"{_row}-cell?-a1", _at("v : cell? = a1"), "unresolved name 'a1'"),
            (f"{_row}-cell-a1", _at("v : cell = a1"), "unresolved name 'a1'"),
            (f"{_row}-cell?-prior", _at("v : cell? = prior"), ACCEPT),
            # A `Player?` reads as a `Player` (types.coercible; flow narrowing
            # is issue #990), and a `cell?` as a `cell` alike.
            (f"{_row}-cell-prior", _at("v : cell = prior"), ACCEPT),
        ]

DECL_CELLS += [
    # A boardless game mints no `cell`, and the refusal's fix follows its
    # content; one that declares an integer domain spelled `cell` holds
    # numbers, the integer class.
    ("boardless-cell?", boardless(state="    v : cell? = none"), NO_BOARD_CARDS),
    ("boardless-cell", boardless(state="    v : cell = none"), NO_BOARD_CARDS),
    ("boardless-pieces-cell?", boardless_pieces("    v : cell? = none"), NO_BOARD_PIECES),
    (
        "boardless-integer-cell?",
        boardless(positions="  positions { cell : 1..3 }", state="    v : cell? = none"),
        INTEGER_CELL,
    ),
    # The refused classes, one row each, in every game where the class exists.
    (
        "board-column?",
        board(positions="  positions { column : 1..3 }", state="    v : column? = none"),
        INTEGER_DOMAIN,
    ),
    (
        "boardless-column",
        boardless(positions="  positions { column : 1..3 }", state="    v : column = 1"),
        INTEGER_DOMAIN,
    ),
    ("board-dir?", board(state="    v : dir? = none"), DIRECTION),
    ("morris9-dir?", board(family="morris9", state="    v : dir? = none"), UNMINTED_DIRECTION),
    ("boardless-dir?", boardless(state="    v : dir? = none"), NO_BOARD_DIRECTION),
    ("board-unknown?", board(state="    v : Square? = none"), "unknown type 'Square' in declaration of 'v'"),
    (
        "board-Combination?",
        board(state="    v : Combination? = none"),
        "`Combination` is a function parameter's type only",
    ),
    (
        "board-indexed-by-cell",
        board(state="    seen[cell] : Integer = 0"),
        "is indexed by 'cell', which is not an indexable role",
    ),
]

# Each refusal's named fix, taken exactly as the refusal names it, checks. A
# row's id is the refusal row it answers.
FIX_TAKEN: list[tuple[str, str]] = [
    (
        "boardless-cell?",
        boardless(state="    v : cell? = none").replace(
            "  cards: standard52\n", "  pieces: xo_marks\n  board: grid(3, 3)\n"
        ),
    ),
    (
        "boardless-cell",
        boardless(state="    prior : cell? = none\n    v : cell = prior").replace(
            "  cards: standard52\n", "  pieces: xo_marks\n  board: grid(3, 3)\n"
        ),
    ),
    (
        "boardless-pieces-cell?",
        boardless_pieces("    v : cell? = none").replace(
            "  pieces: xo_marks\n", "  board: grid(3, 3)\n  pieces: xo_marks\n"
        ),
    ),
    (
        "boardless-integer-cell?",
        boardless(positions="  positions { cell : 1..3 }", state="    v : Integer? = none"),
    ),
    ("board-column?", board(positions="  positions { column : 1..3 }", state="    v : Integer? = none")),
    ("boardless-column", boardless(positions="  positions { column : 1..3 }", state="    v : Integer = 1")),
    ("board-dir?", board(functions="function f(along : dir) = is_diagonal(along)\n")),
    ("morris9-dir?", board(family="morris9", state="    v : cell? = none")),
    ("boardless-dir?", boardless(state="    v : SeatDirection? = none")),
]


@pytest.mark.parametrize(
    ("source", "expected"),
    [_param(cid, src, want) for cid, src, want in DECL_CELLS],
)
def test_the_declaration_grid(source: str, expected: Expected) -> None:
    _expect(source, expected)


@pytest.mark.parametrize("source", [_param(f"{cid}-fix-taken", src) for cid, src in FIX_TAKEN])
def test_a_refusal_s_named_fix_checks(source: str) -> None:
    _expect(source, ACCEPT)


def test_every_owned_refusal_has_its_fix_taken() -> None:
    """The refusal rows carrying one of this module's own refusal sentences
    are exactly the rows a FIX_TAKEN row answers.

    red under: delete any FIX_TAKEN row."""
    refused = {cid for cid, _src, want in DECL_CELLS if want in OWNED_REFUSALS}
    assert refused == {cid for cid, _src in FIX_TAKEN}


# --- GRID R: reads and writes of a `cell?` variable ------------------------------

_ANCHOR = "    last_at : cell? = none"
_PER_SEAT = "    lastp[player] : cell? = none"
_MINE = "function mine(c : cell) = square[c] is empty\n"
_BESIDE = "any dir where has_step(last_at, dir, actor) and (neighbor(last_at, dir, actor) is at)"

USE_CELLS: list[tuple[str, str, dict[str, str], Expected]] = [
    ("assign-from-parameter", _ANCHOR, {"effect": "    last_at := at"}, ACCEPT),
    ("assign-from-let", _ANCHOR, {"effect": "    let c = at\n    last_at := c"}, ACCEPT),
    ("assign-none", _ANCHOR, {"effect": "    last_at := none"}, ACCEPT),
    ("is-none", _ANCHOR, {"stop_when": "last_at is none"}, ACCEPT),
    ("is-not-none", _ANCHOR, {"stop_when": "last_at is not none"}, ACCEPT),
    ("is-parameter", _ANCHOR, {"when": "(square[at] is empty) and (at is not last_at)"}, ACCEPT),
    (
        "chain-guard",
        _ANCHOR,
        {"when": f"(square[at] is empty) and ((last_at is none) or ({_BESIDE}))"},
        ACCEPT,
    ),
    ("function-argument", _ANCHOR, {"functions": _MINE, "stop_when": "mine(last_at)"}, ACCEPT),
    ("zone-subscript-key", _ANCHOR, {"stop_when": "square[last_at] is empty"}, ACCEPT),
    ("builtin-argument", _ANCHOR, {"stop_when": "any dir where has_step(last_at, dir, actor)"}, ACCEPT),
    ("membership", _ANCHOR, {"stop_when": "last_at in far_row(0)"}, ACCEPT),
    # Each refusal's only `cell` operand is the variable, so the refusal reads
    # the variable's type.
    ("is-integer", _ANCHOR, {"stop_when": "last_at is 3"}, "comparing Cell with Integer can never be equal"),
    ("ordering", _ANCHOR, {"stop_when": "last_at < 3"}, "'<' compares Integers, got Cell"),
    ("arithmetic", _ANCHOR, {"stop_effect": "    n := last_at + 1"}, "'+' expects Integer operands, got Cell"),
    ("assign-integer", _ANCHOR, {"effect": "    last_at := 3"}, "cannot assign Integer to 'last_at' (Cell?)"),
    ("assign-string", _ANCHOR, {"effect": '    last_at := "a1"'}, "cannot assign String to 'last_at' (Cell?)"),
    ("assign-to-integer", _ANCHOR, {"stop_effect": "    n := last_at"}, "cannot assign Cell? to 'n' (Integer)"),
    ("field", _ANCHOR, {"stop_when": "last_at.side is x"}, "cannot read field 'side' of Cell?"),
    # A per-seat store, read and written through its seat.
    ("per-seat-assign", _PER_SEAT, {"effect": "    lastp[actor] := at"}, ACCEPT),
    ("per-seat-is-not-none", _PER_SEAT, {"stop_when": "lastp[actor] is not none"}, ACCEPT),
    ("per-seat-zone-key", _PER_SEAT, {"stop_when": "square[lastp[actor]] is empty"}, ACCEPT),
    ("per-seat-ordering", _PER_SEAT, {"stop_when": "lastp[actor] < 3"}, "'<' compares Integers, got Cell"),
    (
        "per-seat-arithmetic",
        _PER_SEAT,
        {"stop_effect": "    n := lastp[actor] + 1"},
        "'+' expects Integer operands, got Cell",
    ),
    (
        "per-seat-assign-integer",
        _PER_SEAT,
        {"effect": "    lastp[actor] := 3"},
        "cannot assign Integer to 'lastp' (Cell?)",
    ),
    ("per-seat-winner", _PER_SEAT, {"winner": "highest lastp"}, "an optional score may be `none`"),
    (
        "per-seat-winner-plain",
        "    prior : cell? = none\n    lastp[player] : cell = prior",
        {"winner": "highest lastp"},
        "a game is ranked by a score, so the target must be Boolean, Integer",
    ),
]


@pytest.mark.parametrize(
    ("state", "slots", "expected"),
    [_param(cid, state, slots, want) for cid, state, slots, want in USE_CELLS],
)
def test_the_read_and_write_grid(state: str, slots: dict[str, str], expected: Expected) -> None:
    _expect(board(state=state, **slots), expected)


# --- GRID P: play ------------------------------------------------------------------

# The chain anchor on grid(3, 3): each mark after the first lands beside the
# last one placed, and `stop`, offered once a mark is down, scores the stopper
# exactly when the remembered square holds a mark.
WITNESS = board(
    state=_ANCHOR,
    when=f"(square[at] is empty) and ((last_at is none) or ({_BESIDE}))",
    effect="    last_at := at",
    stop_when="last_at is not none",
    stop_effect="    if square[last_at] is not empty { result[actor] := 1 }",
)

# Each seat remembers the square it last marked, the shuttle's per-seat store.
PER_SEAT_WITNESS = board(
    state=_PER_SEAT,
    effect="    lastp[actor] := at",
    stop_when="lastp[actor] is not none",
    stop_effect="    if square[lastp[actor]] is not empty { result[actor] := 1 }",
)


def _play(source: str, seed: int) -> GameResult:
    if (refused := _verdict(source)) is not None:
        raise CellMismatch(f"the program does not check: {refused}")
    return play_game(check_dsl(source, "typed_position_state.cardlang"), random.Random(seed))


@pytest.mark.parametrize("source", [_param("anchor", WITNESS), _param("per-seat", PER_SEAT_WITNESS)])
@pytest.mark.parametrize("seed", range(12))
def test_the_witness_remembers_the_square_it_wrote(source: str, seed: int) -> None:
    result = _play(source, seed)
    assert result.ended_by is EndedBy.RULES
    assert sorted(result.seat_scores) == [0, 1]


_NAMED_KEY = (
    "zone family 'square'",
    "its key `last_at` is none here",
    "test `last_at is not none` before naming `square[last_at]`",
)
_UNNAMED_KEY = (
    "zone family 'square'",
    "its key is none here",
    "test it with `is not none` where it is read, before it names `square[...]` "
    "or is passed to a function that does",
)

# A `none` square reaching each route that needs a square, and the same route
# with the refusal's named fix taken.
NONE_AT_PLAY: list[tuple[str, str, str, tuple[str, ...], str]] = [
    (
        "zone-subscript",
        _ANCHOR,
        "    if square[last_at] is empty { n := 1 }",
        _NAMED_KEY,
        "    if last_at is not none { if square[last_at] is empty { n := 1 } }",
    ),
    (
        "move-destination",
        _ANCHOR,
        "    move one piece from reserve[0] to square[last_at]",
        _NAMED_KEY,
        "    if last_at is not none { move one piece from reserve[0] to square[last_at] }",
    ),
    (
        "function-parameter",
        _ANCHOR,
        "    if mine(last_at) { n := 1 }",
        _UNNAMED_KEY,
        "    if (last_at is not none) and mine(last_at) { n := 1 }",
    ),
    (
        "per-seat-key",
        _PER_SEAT,
        "    if square[lastp[0]] is empty { n := 1 }",
        _UNNAMED_KEY,
        "    if (lastp[0] is not none) and (square[lastp[0]] is empty) { n := 1 }",
    ),
    (
        "builtin",
        _ANCHOR,
        "    if any dir where has_step(last_at, dir, 0) { n := 1 }",
        ("`has_step` was given none where it needs a `cell`", "test it with `is none` before passing it"),
        "    if last_at is not none { if any dir where has_step(last_at, dir, 0) { n := 1 } }",
    ),
    (
        "collection-form-source",
        _ANCHOR,
        "    if any cell in [last_at] where true { n := 1 }",
        ("`any cell in …` ranges over `cell`'s members, but its source holds none",
         "test it with `is not none` before putting it in the source"),
        "    if last_at is not none { if any cell in [last_at] where true { n := 1 } }",
    ),
]


@pytest.mark.parametrize(
    ("state", "setup", "needles"),
    [_param(cid, state, setup, needles) for cid, state, setup, needles, _fix in NONE_AT_PLAY],
)
def test_a_none_square_is_refused_where_a_square_is_needed(
    state: str, setup: str, needles: tuple[str, ...]
) -> None:
    source = board(state=state, functions=_MINE, setup=setup)
    with pytest.raises(OwnerGuardError) as exc:
        _play(source, 0)
    missing = [s for s in needles if s not in str(exc.value)]
    if missing:
        raise CellMismatch(f"the refusal lacks {missing}: {exc.value}")


@pytest.mark.parametrize(
    ("state", "setup"),
    [_param(f"{cid}-fix-taken", state, fix) for cid, state, _setup, _needles, fix in NONE_AT_PLAY],
)
def test_a_none_square_s_named_fix_plays(state: str, setup: str) -> None:
    result = _play(board(state=state, functions=_MINE, setup=setup), 0)
    assert result.ended_by is EndedBy.RULES
