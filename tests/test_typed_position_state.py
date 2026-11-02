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
                 of the game's named-member position domains, and nothing
                 else; a named-member one types `cell` (`cell?` with `?`),
                 never the permissive top, so every type Owner Guard reads it;
                 a `none` it holds is refused, in designer words, where a
                 square must be named at play.
domain:          GRID D, the declaration: the state type -- every value type
                 in `KNOWN_TYPE_NAMES` as the control, the board's
                 named-member domain, an integer position domain, the
                 direction domain, `Combination`, an unknown name -- crossed
                 with optional, default, declaring site (game-level and
                 phase-local `state { }`) and game (a board; no board; no
                 board with an integer domain spelled `cell`), the type-side
                 product taken on the named-member domain and the refusal
                 rows one per refused class. GRID R, the reads and writes:
                 every statement and expression position a `Player?`
                 variable is consumed at, on a `cell?` variable in a board
                 game. GRID P, play: the witness fixture end to end, and a
                 `none` reaching each site that needs a square -- a zone
                 subscript, a user function's `cell` parameter, a Builtin.
                 A library's `state { }` and `requires` rows are a different
                 domain: a library declares no board, its type slot admits
                 the value types (`resolve._library_slot_names`), and a
                 `requires` row cannot spell `?`. What the variable's value
                 shows each seat is the proof module's of the first game that
                 writes it (issue #983).
registry:        value types: typecheck.KNOWN_TYPE_NAMES; position domains:
                 `game.positions` partitioned by `PositionDecl.members_named`;
                 direction domain: board_domains.DIRECTION_DOMAIN; the
                 sibling grid over every declaring position:
                 tests/test_type_name_positions.py::test_the_board_names_grid;
                 a `none` at a Builtin slot:
                 tests/test_direction_lift.py.
held by:         the state admit-set is Unrepresentable as a second spelling:
                 one helper, `resolve._declared_type_universe`, is the state
                 set, and the function-parameter set is that helper plus the
                 domains a parameter alone takes. The typing is
                 Unrepresentable as an omission: `type_from_name` takes the
                 game's domains as required parameters, so a caller that
                 omits them does not type-check. The refusal classes are
                 Derived and Pinned: a declared type name reaches resolve as
                 source text, so no union classifies it before resolve does,
                 and GRID D pins each class's message. The `none` key at a
                 zone subscript is Derived and Pinned at the key's Owner
                 Guard, `state.ZoneStore.instance`: `types.coercible` admits
                 an optional where its base is wanted, a designed constraint
                 (the language has no flow narrowing), so the case is
                 reachable at play.
does not prove:  that a caller hands `type_from_name` the game's OWN domains:
                 an empty mapping type-checks as well as the right one, and
                 only the cells typing a `cell` read (GRID R's refusals, GRID
                 D's default cells) witness the threading.
red under:       GRID D's admit cells, GRID R and GRID P are born red, and
                 reverting the admit-set reddens them; passing `{}` for the
                 positions of `typecheck._check_state_default` reddens
                 `default-cell?-3`. The value-type controls are born green and
                 redden if the helper drops `KNOWN_TYPE_NAMES`; the
                 indexed-store refusal is born green and reddens if the index
                 arm admits the named-member domains; the unresolved-cell
                 rows are born green and redden if resolve reads a board
                 member's name as a value.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import EndedBy, play_game
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
  board: grid(3, 3)
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
  winner: highest result
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


def board(**slots: str) -> str:
    filled = {
        "positions": "", "state": "", "setup": "", "phase_state": "",
        "functions": "", "when": "square[at] is empty", "effect": "",
        "stop_when": "true", "stop_effect": "",
    }
    filled.update(slots)
    return BOARD_GAME % filled


def boardless(**slots: str) -> str:
    filled = {"positions": "", "state": ""}
    filled.update(slots)
    return BOARDLESS_GAME % filled


def _verdict(source: str) -> str | None:
    """None for a program that checks; the first diagnostic's message for one
    that does not."""
    try:
        check_dsl(source, "typed_position_state.cardlang")
    except DiagnosticError as exc:
        return exc.diagnostic.message
    return None


ACCEPT = None


def _expect(source: str, expected: str | tuple[str, ...] | None) -> None:
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


def _flip(cell_id: str, red: frozenset[str]) -> list[pytest.MarkDecorator]:
    return [pytest.mark.xfail(strict=True, raises=CellMismatch)] if cell_id in red else []


# The refusal each refused class owns, in the words its fix needs.
INTEGER_DOMAIN = ("is typed `column`", "a position domain of numbers", "as an `Integer`")
DIRECTION = ("is typed `dir`", "a move or function parameter takes", "a state variable cannot hold one")
NO_BOARD = ("is typed `cell`", "declares no `board:`")


# --- GRID D: the declaration ---------------------------------------------------

DECL_CELLS: list[tuple[str, str, str | tuple[str, ...] | None]] = []

# The value types: the control, admitted before and after.
for _t in sorted(KNOWN_TYPE_NAMES):
    DECL_CELLS.append((f"value-{_t}?", board(state=f"    v : {_t}? = none"), ACCEPT))

# The named-member domain, crossed with optional, default and site.
_PRIOR = "    prior : cell? = none\n"
for _site in ("game", "phase"):
    def _at(decl: str, site: str = _site) -> str:
        if site == "game":
            return board(state=_PRIOR + f"    {decl}")
        return board(state=_PRIOR, phase_state=f"    state {{ {decl} }}")

    DECL_CELLS += [
        (f"{_site}-cell?-none", _at("v : cell? = none"), ACCEPT),
        (f"{_site}-cell-none", _at("v : cell = none"), "declared Cell, but its default has type none"),
        (f"{_site}-cell?-3", _at("v : cell? = 3"), "declared Cell?, but its default has type Integer"),
        (f"{_site}-cell-3", _at("v : cell = 3"), "declared Cell, but its default has type Integer"),
        (f"{_site}-cell?-string", _at('v : cell? = "a1"'), "declared Cell?, but its default has type String"),
        (f"{_site}-cell?-a1", _at("v : cell? = a1"), "unresolved name 'a1'"),
        (f"{_site}-cell-a1", _at("v : cell = a1"), "unresolved name 'a1'"),
        (f"{_site}-cell?-prior", _at("v : cell? = prior"), ACCEPT),
        # A `Player?` reads as a `Player` (types.coercible: no flow narrowing),
        # and a `cell?` as a `cell` alike.
        (f"{_site}-cell-prior", _at("v : cell = prior"), ACCEPT),
    ]

DECL_CELLS += [
    # A boardless game mints no `cell`; one that declares an integer domain
    # spelled `cell` holds numbers, the integer class.
    ("boardless-cell?", boardless(state="    v : cell? = none"), NO_BOARD),
    ("boardless-cell", boardless(state="    v : cell = none"), NO_BOARD),
    (
        "boardless-integer-cell?",
        boardless(positions="  positions { cell : 1..3 }", state="    v : cell? = none"),
        ("is typed `cell`", "a position domain of numbers", "as an `Integer`"),
    ),
    # The refused classes, one row each, in both games where the class exists.
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
    ("boardless-dir?", boardless(state="    v : dir? = none"), DIRECTION),
    ("board-unknown?", board(state="    v : Square? = none"), "unknown type 'Square' in declaration of 'v'"),
    (
        "board-Combination?",
        board(state="    v : Combination? = none"),
        "a state variable cannot hold one",
    ),
    (
        "board-indexed-by-cell",
        board(state="    seen[cell] : Integer = 0"),
        "is indexed by 'cell', which is not an indexable role",
    ),
]

# The cells this change designs to flip.
DECL_RED = frozenset(
    cid
    for cid, _src, want in DECL_CELLS
    if not cid.startswith("value-")
    and not cid.endswith("-a1")
    and cid not in ("board-unknown?", "board-Combination?", "board-indexed-by-cell")
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [pytest.param(src, want, id=cid, marks=_flip(cid, DECL_RED)) for cid, src, want in DECL_CELLS],
)
def test_the_declaration_grid(source: str, expected: str | tuple[str, ...] | None) -> None:
    _expect(source, expected)


# --- GRID R: reads and writes of a `cell?` variable ------------------------------

_ANCHOR = "    last_at : cell? = none"
_MINE = "function mine(c : cell) = square[c] is empty\n"

USE_CELLS: list[tuple[str, dict[str, str], str | tuple[str, ...] | None]] = [
    ("assign-from-parameter", {"effect": "    last_at := at"}, ACCEPT),
    ("assign-from-let", {"effect": "    let c = at\n    last_at := c"}, ACCEPT),
    ("assign-none", {"effect": "    last_at := none"}, ACCEPT),
    ("is-none", {"stop_when": "last_at is none"}, ACCEPT),
    ("is-not-none", {"stop_when": "last_at is not none"}, ACCEPT),
    ("is-parameter", {"when": "(square[at] is empty) and (at is not last_at)"}, ACCEPT),
    (
        "chain-guard",
        {"when": "(square[at] is empty) and ((last_at is none) or (at in neighbors(last_at)))"},
        ACCEPT,
    ),
    ("function-argument", {"functions": _MINE, "stop_when": "mine(last_at)"}, ACCEPT),
    ("zone-subscript-key", {"stop_when": "square[last_at] is empty"}, ACCEPT),
    ("builtin-argument", {"stop_when": "number of cells in neighbors(last_at) where true > 1"}, ACCEPT),
    ("membership", {"stop_when": "last_at in far_row(0)"}, ACCEPT),
    ("is-integer", {"stop_when": "last_at is 3"}, "comparing Cell? with Integer can never be equal"),
    ("ordering", {"when": "(square[at] is empty) and (last_at < at)"}, "'<' compares Integers, got Cell?"),
    ("arithmetic", {"stop_effect": "    n := last_at + 1"}, "'+' expects Integer operands, got Cell?"),
    ("assign-integer", {"effect": "    last_at := 3"}, "cannot assign Integer to 'last_at' (Cell?)"),
    ("assign-string", {"effect": '    last_at := "a1"'}, "cannot assign String to 'last_at' (Cell?)"),
    ("assign-to-integer", {"stop_effect": "    n := last_at"}, "cannot assign Cell? to 'n' (Integer)"),
    ("field", {"stop_when": "last_at.side is x"}, "cannot read field 'side' of Cell?"),
]


@pytest.mark.parametrize(
    ("slots", "expected"),
    [
        pytest.param(slots, want, id=cid, marks=[pytest.mark.xfail(strict=True, raises=CellMismatch)])
        for cid, slots, want in USE_CELLS
    ],
)
def test_the_read_and_write_grid(slots: dict[str, str], expected: str | tuple[str, ...] | None) -> None:
    _expect(board(state=_ANCHOR, **slots), expected)


# --- GRID P: play ------------------------------------------------------------------

# The chain anchor on grid(3, 3): each mark after the first lands beside the
# last one placed, and `stop`, offered once a mark is down, scores the stopper
# exactly when the remembered square holds a mark.
WITNESS = board(
    state=_ANCHOR,
    when="(square[at] is empty) and ((last_at is none) or (at in neighbors(last_at)))",
    effect="    last_at := at",
    stop_when="last_at is not none",
    stop_effect="    if square[last_at] is not empty { result[actor] := 1 }",
)


def _play(source: str, seed: int) -> object:
    if (refused := _verdict(source)) is not None:
        raise CellMismatch(f"the program does not check: {refused}")
    return play_game(check_dsl(source, "typed_position_state.cardlang"), random.Random(seed))


@pytest.mark.xfail(strict=True, raises=CellMismatch)
@pytest.mark.parametrize("seed", range(12))
def test_the_witness_remembers_the_square_it_wrote(seed: int) -> None:
    result = _play(WITNESS, seed)
    assert result.ended_by is EndedBy.RULES  # type: ignore[attr-defined]
    assert sorted(result.seat_scores) == [0, 1]  # type: ignore[attr-defined]


NONE_AT_PLAY: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "zone-subscript",
        board(state=_ANCHOR, setup="    if square[last_at] is empty { n := 1 }"),
        ("zone family 'square'", "its key is none here", "test it with `is none`"),
    ),
    (
        "function-parameter",
        board(state=_ANCHOR, functions=_MINE, setup="    if mine(last_at) { n := 1 }"),
        ("zone family 'square'", "its key is none here", "test it with `is none`"),
    ),
    (
        "builtin",
        board(state=_ANCHOR, setup="    if number of cells in neighbors(last_at) where true > 1 { n := 1 }"),
        ("`neighbors` was given none where it needs a `cell`",),
    ),
]


@pytest.mark.xfail(strict=True, raises=CellMismatch)
@pytest.mark.parametrize(
    ("source", "needles"),
    [pytest.param(src, needles, id=cid) for cid, src, needles in NONE_AT_PLAY],
)
def test_a_none_square_is_refused_where_a_square_is_needed(source: str, needles: tuple[str, ...]) -> None:
    with pytest.raises(OwnerGuardError) as exc:
        _play(source, 0)
    missing = [s for s in needles if s not in str(exc.value)]
    if missing:
        raise CellMismatch(f"the refusal lacks {missing}: {exc.value}")
