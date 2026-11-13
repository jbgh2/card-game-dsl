"""Facts the resolver reads off the game's declarations.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  the deck, the board, the minted directions and the declared
              types as every step reads them, each derived once here; the
              slot each of the game's component set, content kind, board and
              zone indexes stands in, and what clears a refusal resting on
              each (`DECK_SLOT`, `sets_naming`, `content_kind_unless`,
              `board_mints`, `kept_per_player`), stated once for every step
              that marks one; and the arguments a `run` binds to a
              `Positive` parameter (`positive_arguments`), read by its guard
              and by the position record.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import assert_never
from dataclasses import replace
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN, DIRECTION_DOMAIN, board_directions, directions_of
from cardlang.diagnostics import DiagnosticBag, Refused, Slot, SlotKind, Span, Unless
from cardlang.domains import SIMULTANEOUS_ROLES, Role, role_names, role_of
from cardlang.stdlib.boards import BOARD_FAMILIES, BoardEntry, BoardMisuse, BoardRefusal, board_entry
from cardlang.stdlib.enums import enum_values, rank_names, suit_names
from cardlang.stdlib.rules import STDLIB_NAME, stdlib_rules
from cardlang.typecheck import COMBINATION_TYPE_NAME, KNOWN_TYPE_NAMES, POSITIVE_PARAM_DOMAIN
from cardlang.resolve.walk import _traverse
# The zone family a move type's `Card` parameter takes its card from: the
# acting seat's own instance (`DECISION_POOLS`' Card-parameter row).
CARD_PARAMETER_FAMILY = "hand"


# Every statement that WRITES persistent state, as (node class, the field holding
# the written name). `runtime/state.py`'s `Store.set` is the one door onto
# persistent state, and `runtime/execute.py` reaches it from exactly these three
# handlers — which is the direction the pin runs in:
# `tests/test_family_libraries.py::test_write_sites_cover_every_state_writing_node`
# scrapes the runtime and compares, so this tuple answers to the executor rather
# than being a list maintained alongside it.
#
# `:=`/`+=`/`-=` and `rotate` carry a classified `NameRef`; `again` is a bare
# string the runtime clears at each turn boundary, which is why it is a write
# site at all and why a hand-written axis would have missed it.
_STATE_WRITE_SITES: tuple[tuple[type[n.Stmt], str], ...] = (
    (n.AssignStmt, "target"),
    (n.RotateStmt, "target"),
    (n.Turns, "again"),
)


def _written_state_name(node: object) -> str | None:
    """The state name this node writes, or None if it writes no state."""
    for cls, field_name in _STATE_WRITE_SITES:
        if isinstance(node, cls):
            written = getattr(node, field_name)
            if isinstance(written, n.NameRef):
                return written.name
            return written if isinstance(written, str) else None
    return None


def _declared_board(game: n.Game) -> BoardEntry | None:
    """The entry the game's `board:` clause builds, or None for a boardless
    game or a `board:` the registry refuses (that refusal is the clause's own,
    by `_resolve_board`)."""
    if game.board is None:
        return None
    try:
        return board_entry(game.board.family, game.board.args)
    except BoardRefusal:
        return None


def _stamped_stdlib_rules() -> dict[str, n.RuleDef]:
    """The standard library's rules, each stamped with its origin as the
    splice stamps the rules a game activates."""
    return {
        name: replace(rule, origin=n.LibraryOrigin(STDLIB_NAME, f"rule `{name}`"))
        for name, rule in stdlib_rules().items()
    }

def _map_climb_rounds(node: object, step: Callable[[n.ClimbRound], n.ClimbRound]) -> object:
    """`node` with `step` applied to every climbing round in it, rebuilding
    only the nodes on the path to one (`_traverse` keeps every untouched
    subtree's identity)."""
    if isinstance(node, tuple):
        mapped = tuple(_map_climb_rounds(x, step) for x in node)
        return node if all(a is b for a, b in zip(mapped, node, strict=True)) else mapped
    if isinstance(node, n.ClimbRound):
        node = step(node)
    return _traverse(node, lambda _field, value: _map_climb_rounds(value, step))


def _tell_board_refusal(
    refused: BoardRefusal, family: str, span: Span | None, bag: DiagnosticBag
) -> None:
    """Tell the board registry's refusal by the misuse it carries: a family it
    does not register is a name refused against `BOARD_FAMILIES`."""
    match refused.misuse:
        case BoardMisuse.UNKNOWN_FAMILY:
            bag.unknown(str(refused), family, BOARD_FAMILIES, span, code=Code.UNKNOWN_BOARD, slot=BOARD_SLOT)
        case BoardMisuse.WRONG_ARGUMENT_COUNT:
            bag.error(str(refused), span, code=Code.WRONG_ARGUMENT_COUNT)
        case BoardMisuse.ARGUMENT_OUT_OF_RANGE | BoardMisuse.UNDECLARED_LINE_LENGTH:
            bag.error(str(refused), span, code=Code.OUT_OF_RANGE)
        case BoardMisuse.NO_LINES:
            bag.error(str(refused), span, code=Code.MISSING_DECLARATION)
        case _:
            assert_never(refused.misuse)


def _family_shape(index: str | None) -> str:
    return "a single zone" if index is None else f"one zone per {index}"


# The slot of the game's `cards:`/`pieces:` set, and of its content kind.
DECK_SLOT = Slot(SlotKind.DECK, "")
CONTENT_KIND_SLOT = Slot(SlotKind.CONTENT_KIND, "")


BOARD_SLOT = Slot(SlotKind.BOARD, "")


def board_mints(name: str) -> Unless:
    """What clears a refusal of a position name a board mints: the game's
    refused `board:` fixed to a family that mints it, `cell` by every family
    and `dir` by every family with a movement frame."""
    if name == BOARD_DOMAIN:
        families = frozenset(BOARD_FAMILIES)
    elif name == DIRECTION_DOMAIN:
        families = frozenset(
            f for f, family in BOARD_FAMILIES.items()
            if family.build(tuple(p.lo for p in family.params)).frame is not None
        )
    else:
        families = frozenset()
    return Unless(SlotKind.BOARD, families)


def index_slot(zone: str) -> Slot:
    """The slot of a zone's index role."""
    return Slot(SlotKind.ZONE_INDEX, zone)


def kept_per_player(zone: str) -> Unless:
    """What clears a refusal of a zone not kept per player: its refused
    index fixed to `player`."""
    return Unless(SlotKind.ZONE_INDEX, frozenset(role_names(frozenset({Role.PLAYER}))), frozenset({zone}))


def content_kind_refused(flavor: str) -> Refused:
    """A component set declared with the other content kind's keyword: the
    cause, whose one fix is that kind."""
    return Refused(CONTENT_KIND_SLOT, frozenset({flavor}))


def content_kind_unless(game: n.Game) -> Unless:
    """What clears a refusal of a game's card content in a piece game: its
    set declared as cards."""
    return Unless(SlotKind.CONTENT_KIND, frozenset({"card"}) - {game.content_flavor})


def sets_naming(name: str) -> frozenset[str]:
    """The component sets in which `name` is a bare enum value: what clears
    its refusal under a refused set."""
    from cardlang.runtime.values import COMPONENT_SETS

    return frozenset(s for s in COMPONENT_SETS if name in enum_values(s))


def sets_holding(rank: str, suit: str) -> frozenset[str]:
    """The component sets whose cards include `rank of suit`."""
    from cardlang.runtime.values import COMPONENT_SETS

    return frozenset(s for s in COMPONENT_SETS if rank in rank_names(s) and suit in suit_names(s))


def positive_arguments(proc: n.ProcedureDef, run: n.RunStmt) -> Iterator[tuple[n.Parameter, n.Expr]]:
    """Each argument `run` binds to a `Positive` parameter of `proc`, which
    takes a written number and no name."""
    for param, arg in zip(proc.params, run.args):
        if param.type_name == POSITIVE_PARAM_DOMAIN:
            yield param, arg


def _deck_known(deck: str) -> bool:
    """True iff `deck` names a known CARD deck — the gate on the card-specific
    resolve paths that read a rank/suit ORDER (`ranking:` membership and
    convention expansion). Deliberately False for a piece set, not only an
    unknown name: those clauses are rejected outright for a piece game by
    `_reject_card_content_clauses` before these paths run, so the gate need only
    admit real card decks."""
    from cardlang.runtime.values import DECKS

    return deck in DECKS


def _component_known(deck: str) -> bool:
    """True iff `deck` names a known component set of EITHER flavor — the gate
    on the flavor-agnostic namespaces (a game's suits, ranks, and bare enum
    values), which a piece set populates from its own axes exactly as a card
    deck does. `component_set` is the registry; an unknown name yields empty
    namespaces (its own diagnostic is `_resolve_component_set`'s)."""
    from cardlang.runtime.values import component_set

    return component_set(deck) is not None


def _declared_suits_phrase(deck: str) -> str:
    """The suits a `suit ranking:` must list, in the designer's words: the deck's
    declared suits, and the special suits it may leave out."""
    from cardlang.runtime.values import DECKS, deck_suits

    if deck not in DECKS:
        return "the deck's suits"
    declared = DECKS[deck].suits
    specials = [s for s in deck_suits(deck) if s not in declared]
    phrase = f"the deck's suits ({', '.join(declared)})"
    if specials:
        phrase += f", optionally with its special suits ({', '.join(specials)}),"
    return phrase


def simultaneous_role_slot(nd: n.EachSimultaneous) -> Slot:
    """The slot of a simultaneous block's role."""
    return Slot(SlotKind.SIMULTANEOUS_ROLE, f"{nd.span}")


def _simultaneous_role_refused(nd: n.EachSimultaneous) -> bool:
    """Whether a simultaneous block's role is no seat domain: the registry's
    `simultaneous` column, since a value domain has no actor to move."""
    return role_of(nd.role) not in SIMULTANEOUS_ROLES


def _combination_outside_a_parameter(type_name: str, where: str) -> str | None:
    """The refusal of `Combination` declared anywhere but a function's
    parameter, or None for any other type name. A climbing play exists while
    a round asks its follows function about it, so only that function and
    the helpers it passes one to may name its type."""
    if type_name.removesuffix("?") != COMBINATION_TYPE_NAME:
        return None
    return (
        f"`{COMBINATION_TYPE_NAME}` is a function parameter's type only (`{type_name}` "
        f"here) — a climbing play exists while a round's follows function reads it, so {where} cannot "
        f"hold one"
    )


def _declared_type_universe(game: n.Game) -> frozenset[str]:
    """The type names a `state` variable may declare: the value types and the
    game's named-member position domains (a board's `cell`). A function
    parameter and an outcome payload admit these and the domains a parameter
    alone takes (`_check_declared_type_names`), so the state set is the
    narrower of the two by construction."""
    return KNOWN_TYPE_NAMES | frozenset(
        p.name for p in game.positions if p.members_named is not None
    )


def _minted_directions(game: n.Game) -> frozenset[str]:
    """The board direction domains the game's board minted: `{dir}` once a
    board with a movement frame validated, `{}` for a boardless game, a board
    with no frame, or a board that failed (decisions.md "Boards and cells").

    The one gate every position admitting `dir` reads -- a move parameter, a
    bare quantifier noun, a function parameter's and an outcome payload's
    type -- so no two of them can disagree on whether a board minted it. It
    asks whether the board minted `cell` (a named-member position domain):
    `_resolve_board` mints nothing for a board that failed validation, and
    `directions_of` re-derives from the board entry, which raises on such a
    board, so `dir` never stands without `cell`; it falls alone where the
    validated board has no movement frame (`directions_of` is empty)."""
    board_minted = any(
        p.name == BOARD_DOMAIN and p.members_named is not None for p in game.positions
    )
    return frozenset(directions_of(game)) if board_minted else frozenset()


def _unminted_direction(game: n.Game, name: str) -> str | None:
    """What a game lacks for `name` to be the direction domain, where `name`
    is that domain's spelling and the game neither mints nor declares it: no
    `board:` at all, or a board whose family has no movement frame (and so
    mints no `dir`, `board_domains.directions_of`). None for every other name,
    and for a board the registry refuses, whose refusal is the clause's own.
    The one test every position admitting `dir` asks before calling the name
    unknown."""
    if name != DIRECTION_DOMAIN or any(p.name == name for p in game.positions):
        return None
    if game.board is None:
        return "the game declares no `board:`"
    entry = _declared_board(game)
    if entry is None or board_directions(entry):
        return None
    destination = "a move on this board names the cell it acts on (`at : cell`)"
    if entry.answers("edges"):
        destination += ", and `neighbors(c)` gives the cells the board joins to a cell"
    return f"board family '{entry.family}' mints no directions; {destination}"


def _direction_refusal(game: n.Game, name: str) -> str | None:
    """How a declared type's refusal of an unminted `dir` ends: what `dir` is,
    and what the game lacks (`_unminted_direction`)."""
    lack = _unminted_direction(game, name)
    if lack is None:
        return None
    return "the board direction domain a `board:` mints, but " + lack
