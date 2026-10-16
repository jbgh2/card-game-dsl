"""A game missing a clause its library needs is told so on its own `uses` line.

A construct a game clause decides -- a Builtin call, a move parameter's domain,
a range's role, a provided declaration's index, a card form in a piece game, a
position past a board region, a round's winner or climbing query -- is refused
against the same clauses whether the game writes it or a family library it
uses does. Written by the game, the refusal sits at the construct. Reached
through a library, it sits on the game's `uses` line and names the library,
the construct and the clause, and nothing is reported inside the library file,
whose author is someone else. Each gate's test has one home, which the `uses`
check and the gate both ask. Every remedy a refusal offers is applied here and
checked.

Completeness ledger
-------------------
property:        for every construct a game clause decides that a library can
                 write, the library-reached verdict equals the game-written
                 one, located on the `uses` line; each gate asks its row's
                 test rather than a copy; and every remedy a refusal offers
                 clears it.
domain:          the Builtin members of each clause gate, and the node members:
                 every iterable role and the board's `cell` in each range form
                 that names one, every role a declaration may be keyed by,
                 every fixed and card parameter domain on a move type, every
                 grammar alternative that reads a zone as cards plus `reveal
                 one card`, every trick-round winner, a round's own `trump`
                 clause and every climbing query in a round a move type's
                 effect holds (each against the content flavor too, since a
                 piece game declares none of the clauses that decide them),
                 and a literal position into every board region.
                 Each member is crossed with {clause met, clause unmet} and
                 {written in the game, reached through a library}; a
                 clause-free member is run met, as the control. A climbing
                 query is a Primitive, which no library may name, so its
                 library-reached cells, met and unmet, are its library-alone
                 refusal in the library file and its `uses`-line gate never
                 judges it (tests/test_library_round_slot_primitives.py).
                 Beside it:
                 every definition kind a library holds, for a Builtin and a
                 node member, and a library rule crossed with whether the game
                 activates it (one it does not activate is checked against its
                 library alone); every ranking-gated name in each position it
                 is named from, each remedy its refusal offers applied; the
                 `teams:` and `board:` remedies applied across seat counts and
                 flavors; every member of a gate on a clause a piece game
                 cannot declare, in a piece game; and every corpus game declaring `ranking:` that uses
                 a checked-in library reaching a ranking-gated Builtin, with
                 its `ranking:` line deleted. Members no library reaches are
                 each pinned by the refusal that bars them in the library's own
                 file: a gated Primitive call, a round in a procedure body, a
                 board verb taking a cell or a direction. Deck capacity is
                 judged at the phase that runs a library's deal, in the game's
                 own file. Members held elsewhere are refused in the library
                 file, each cell marked with its record: a card-axis role in a
                 piece game (issue #183) and a movement's noun and filter
                 (issue #170). A seat or team number, a card field and a rank
                 or suit string are type-layer gates, told through the
                 splice's origin stamp (tests/test_library_type_gates.py).
registry:        gate members: `typecheck.RANKING_GATED_FUNCS`,
                 `RANKING_GATED_WINNERS`, `RANKING_GATED_CLIMB_QUERIES`;
                 `builtins.functions.TRICK_ORDER_GATED_FUNCS`,
                 `TRICK_ORDER_EXCLUDED_FUNCS`, `BOARD_ONLY_CALL_FUNCS`,
                 `DECK_ONLY_CALL_FUNCS`, `TRICK_WINNER_NAMES`,
                 `TRICK_ORDER_GATED_WINNERS`, `TRICK_ORDER_EXCLUDED_WINNERS`,
                 `PRIMITIVE_CLIMB_LEADS`, `PRIMITIVE_CLIMB_FOLLOWS`; the Trick
                 Order twins: `typecheck.RANKING_TRICK_ORDER_TWINS`;
                 `resolve._TEAM_CALL_FUNCS`, `resolve._FRAME_CALL_FUNCS`,
                 `resolve._CARD_POINTS_CALLS`, `resolve._SUIT_RANKING_CALLS`,
                 `resolve._REGION_CALL_FUNCS`;
                 roles and domains: `domains.ITERABLE_ROLES`,
                 `ZONE_INDEX_ROLES`, `PARAM_DOMAINS`, `CARD_PARAM_DOMAINS`,
                 `CARD_AXIS_ROLES`, `board_domains.BOARD_DOMAIN`; card forms:
                 the `cq_`, `sq_` and `agg_` aliases of
                 cardlang/grammar/cardlang.lark. The table:
                 `resolve._CLAUSE_GATES`, its Builtin partition with
                 `resolve._CLAUSE_FREE_BUILTINS` over `BUILTIN_CALL_FUNCS`,
                 its node rows by name in `NODE_GATES`. Probe arguments:
                 `builtins.signatures.CALL_SIGS`. Definition kinds:
                 `resolve._LIBRARY_DEF_KINDS`.
does not prove:  that a member outside the Trick Order twin set has no Trick
                 Order remedy: the expected column reads the same set the
                 refusal is built from, so the two agree by construction, and
                 only the twins' remedy is executed. Nor that a game-written
                 refusal points at the construct's column: a cell matches the
                 definition's line. Nor that two node members in one game are
                 told in one refusal per gate: the cells hold one member each.
                 Nor that a gate reads its clause through its row: the one
                 home is the construct test, and a gate in the type layer, or
                 the Trick Order partition's two branches, reads the clause
                 itself, so the clause half of a row agrees with its gate only
                 as far as the cells run both channels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import cardlang.resolve as resolve_module
import cardlang.typecheck as typecheck_module
from cardlang.board_domains import BOARD_DOMAIN
from cardlang.builtins.functions import (
    BOARD_ONLY_CALL_FUNCS,
    BUILTIN_CALL_FUNCS,
    DECK_ONLY_CALL_FUNCS,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    TRICK_ORDER_EXCLUDED_FUNCS,
    TRICK_ORDER_EXCLUDED_WINNERS,
    TRICK_ORDER_GATED_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
    TRICK_WINNER_NAMES,
    TRUMP_READING_WINNERS,
)
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import (
    CARD_AXIS_ROLES,
    CARD_PARAM_DOMAINS,
    ITERABLE_ROLES,
    ZONE_INDEX_ROLES,
)
from cardlang.domains import PARAM_DOMAINS as _FIXED_PARAM_DOMAINS
from cardlang.libraries import library_names, load_library
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import walled_namespace_of
from cardlang.typecheck import (
    RANKING_GATED_CLIMB_QUERIES,
    RANKING_GATED_FUNCS,
    RANKING_GATED_WINNERS,
    RANKING_TRICK_ORDER_TWINS,
)
from cardlang.types import (
    TAny,
    TCard,
    TCell,
    TCollection,
    TDir,
    TEnum,
    TInteger,
    TOptional,
    TPlayer,
    TString,
    Type,
)

_LIB = "probe_lib"
_LIB_FILE = f"docs/libraries/{_LIB}.cardlang"
_GAME_FILE = "probe.cardlang"


# --- the game a cell checks ---------------------------------------------------


@dataclass(frozen=True)
class Clauses:
    """The game clauses the grid toggles. Every other line of the probe game is
    fixed, so a cell's outcome moves only with these."""

    pieces: bool = False  # `pieces:` rather than `cards:`
    board: bool = False
    board_size: int = 3  # a square grid; the probe asks for `lines(3)`
    players: int = 4
    teams: bool = True
    ranking: bool = True
    card_points: bool = True
    trick_order: bool = False
    # Off unless the probe reads it: a declared `suit ranking:` nothing reads is
    # refused in its own right.
    suit_ranking: bool = False


def _teams_clause(players: int) -> str:
    if players == 4:
        return "teams: [[0, 2], [1, 3]]"
    return "teams: [" + ", ".join(f"[{s}]" for s in range(players)) + "]"


def _game_text(
    clauses: Clauses, *, uses: bool, game_fn: str, tag: str, statement: str = ""
) -> str:
    c = clauses
    if c.pieces:
        content = "pieces: breakthrough_men"
        zones = "box : Deck  reserve[player] : PlayerPile<player>  pile : TrickPile"
    else:
        content = "cards: standard52"
        zones = "deck : Deck  hand[player] : Hand<player>  pile : TrickPile"
    if c.board:
        zones += "  square[cell] : Cell<cell>"
    lines = [
        f"game Probe{tag} {{",
        f"  players: {c.players}",
        _teams_clause(c.players) if c.teams else "",
        "  max_length: 1000",
        f"  {content}",
        f"  board: grid({c.board_size}, {c.board_size})" if c.board else "",
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2" if c.ranking else "",
        "  card_points { A: 1 else: 0 }" if c.card_points else "",
        "  suit ranking: spades hearts diamonds clubs" if c.suit_ranking else "",
        (
            "  trick_order { trump: card.suit is hearts  card_strength: 1 }"
            if c.trick_order
            else ""
        ),
        f"  uses {_LIB}" if uses else "",
        f"  zones {{ {zones} }}",
        "  state { score[player] : Integer = 0 }",
        "  phase p {",
        "    let w = highest_by_trick_order(pile)" if c.trick_order else "",
        "    for each player q: score[q] := 0",
        f"    {statement}",
        (
            "    turns t from 0 over all players until true "
            "{ offer to t one of [probe_fn] }"
            if game_fn.startswith("move_type")
            else ""
        ),
        "  }",
        "  winner: highest score",
        "}",
        game_fn,
    ]
    return "\n".join(lines) + "\n"


# --- the probe call, built from the member's signature ------------------------


def _arg(param: Type) -> tuple[str, str, bool]:
    """(declaration, argument, a library can spell it) for one parameter of a
    probe call. A family library declares no positions, so it has no spelling
    for a cell or a direction (`resolve._library_slot_names`)."""
    if isinstance(param, TCard):
        return "c : Card", "c", True
    if isinstance(param, TPlayer):
        return "p : Player", "p", True
    if isinstance(param, TInteger):
        return "", "3", True
    if isinstance(param, TString):
        return "", '"probe"', True
    if isinstance(param, TOptional) and isinstance(param.inner, TEnum):
        return "", "none", True
    if param == TEnum("Suit"):
        # A library names no suit, so it reaches a suit through a card.
        return "c : Card", "c.suit", True
    if isinstance(param, (TAny, TCollection)):
        return "", "pile", True
    if isinstance(param, TCell):
        return "x : cell", "x", False
    if isinstance(param, TDir):
        return "d : dir", "d", False
    raise AssertionError(f"no probe argument for parameter type {param!r}")


@dataclass(frozen=True)
class Probe:
    params: str
    call: str
    needs_pile: bool
    library_spellable: bool


def _probe(member: str) -> Probe:
    decls: list[str] = []
    args: list[str] = []
    spellable = True
    for param in CALL_SIGS[member].params:
        decl, arg, ok = _arg(param)
        spellable = spellable and ok
        if decl and decl not in decls:
            decls.append(decl)
        args.append(arg)
    return Probe(
        ", ".join(decls), f"{member}({', '.join(args)})", "pile" in args, spellable
    )


def _function(probe: Probe) -> str:
    """The definition holding the probe call. A direction is a move parameter's
    domain and no function's, so a call needing one is written in an offered
    move type instead, with the acting seat as its player."""
    if probe.library_spellable:
        return f"function probe_fn({probe.params}) = {probe.call}"
    params = ", ".join(p for p in probe.params.split(", ") if not p.startswith("p :"))
    call = probe.call.replace(", p)", ", actor)")
    return f"move_type probe_fn({params}) {{ effect {{ let y = {call} }} }}"


def _library_text(probe: Probe) -> str:
    requires = "requires { pile : TrickPile }" if probe.needs_pile else ""
    return f"library {_LIB} {{\n  {requires}\n  {_function(probe)}\n}}\n"


# --- the gates, derived from the registries that define them ------------------

_CARD = Clauses()
_BOARD = Clauses(
    pieces=True, board=True, players=2, teams=False, ranking=False, card_points=False
)
_PIECES = Clauses(pieces=True, ranking=False, card_points=False)


@dataclass(frozen=True)
class Gate:
    """One clause gate: the Builtins it governs, the clause a refusal must name,
    and the game that fails it, built from the member's home game."""

    name: str
    members: frozenset[str]
    clause: str


GATES: tuple[Gate, ...] = (
    Gate("ranking", RANKING_GATED_FUNCS, "ranking:"),
    Gate("trick_order_needed", TRICK_ORDER_GATED_FUNCS, "trick_order"),
    Gate("trick_order_refused", TRICK_ORDER_EXCLUDED_FUNCS, "trick_order"),
    Gate("card_points", resolve_module._CARD_POINTS_CALLS, "card_points"),
    Gate("suit_ranking", resolve_module._SUIT_RANKING_CALLS, "`suit ranking:`"),
    Gate("teams", resolve_module._TEAM_CALL_FUNCS, "teams:"),
    Gate("board", BOARD_ONLY_CALL_FUNCS, "board:"),
    Gate("two_seats", resolve_module._FRAME_CALL_FUNCS, "players"),
    # The one board verb whose ARGUMENT is judged against the board's size
    # (`resolve._check_board_call`): a literal `k` past the board's span.
    Gate("board_span", frozenset({"lines"}), "grid(2, 2)"),
    Gate("cards", DECK_ONLY_CALL_FUNCS, "piece"),
)


def _home(member: str) -> Clauses:
    """A game every gate on `member` is met in."""
    if member in BOARD_ONLY_CALL_FUNCS:
        return _BOARD
    return replace(
        _CARD,
        trick_order=member in TRICK_ORDER_GATED_FUNCS,
        suit_ranking=member in resolve_module._SUIT_RANKING_CALLS,
    )


def test_the_uses_check_holds_a_row_for_every_presence_gate() -> None:
    """The `uses`-line check's table holds exactly the gates this grid derives,
    so a gate it lacks is a red here even before a cell runs it. `board_span`
    is the argument-judged gate, held by its own leg.

    red under: emptying the members of the `teams:` row of
    `resolve._CLAUSE_GATES` (executed 2026-10-13)."""
    table = {row.members for row in resolve_module._CLAUSE_GATES if row.members}
    grid = {gate.members for gate in GATES if gate.name != "board_span"}
    assert table == grid


def test_every_builtin_is_clause_gated_or_clause_free() -> None:
    """Every Builtin either sits in a row of the `uses`-line check's table or is
    listed as gated by no clause, never both, so a Builtin registered with a
    new clause gate is a red here until its row exists.

    red under: adding `suit_value` to `BUILTIN_CALL_FUNCS` (executed
    2026-10-13)."""
    gated = frozenset[str]().union(
        *(row.members for row in resolve_module._CLAUSE_GATES)
    ) & BUILTIN_CALL_FUNCS
    free = resolve_module._CLAUSE_FREE_BUILTINS
    assert not gated & free, sorted(gated & free)
    assert gated | free == BUILTIN_CALL_FUNCS, sorted(BUILTIN_CALL_FUNCS - gated - free)


def _unmet(gate: Gate, member: str) -> Clauses:
    home = _home(member)
    match gate.name:
        case "ranking":
            return replace(home, ranking=False)
        case "trick_order_needed":
            return replace(home, trick_order=False)
        case "trick_order_refused":
            return replace(home, trick_order=True)
        case "card_points":
            return replace(home, card_points=False)
        case "suit_ranking":
            return replace(home, suit_ranking=False)
        case "teams":
            return replace(home, teams=False)
        case "board":
            return replace(home, board=False)
        case "board_span":
            return replace(home, board_size=2)
        case "two_seats":
            return replace(home, players=3)
        case "cards":
            return _PIECES
    raise AssertionError(f"no unmet game for gate {gate.name}")


# --- running a cell -----------------------------------------------------------


def _check(
    clauses: Clauses, probe: Probe, *, through_library: bool, tag: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str | None]:
    """Check one cell; return (game text, every rendered diagnostic or None)."""
    if through_library:
        library = parse_library(_library_text(probe), _LIB_FILE)
        monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
        monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
        text = _game_text(clauses, uses=True, game_fn="", tag=tag)
    else:
        text = _game_text(clauses, uses=False, game_fn=_function(probe), tag=tag)
    try:
        check_dsl(text, _GAME_FILE)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None)
        return text, "\n".join(notes) if notes else exc.diagnostic.format()
    return text, None


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not in the probe game")


# --- the grid -----------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    gate: Gate
    member: str
    met: bool
    through_library: bool

    @property
    def id(self) -> str:
        return (
            f"{self.gate.name}-{self.member}-{'met' if self.met else 'unmet'}-"
            f"{'library' if self.through_library else 'game'}"
        )


def _cells() -> list[object]:
    params: list[object] = []
    for gate in GATES:
        for member in sorted(gate.members & BUILTIN_CALL_FUNCS):
            for met in (True, False):
                for through_library in (False, True):
                    if through_library and not _probe(member).library_spellable:
                        continue  # `test_a_library_cannot_spell_a_cell_or_direction`
                    cell = Cell(gate, member, met, through_library)
                    params.append(pytest.param(cell, id=cell.id))
    return params


@pytest.mark.parametrize("cell", _cells())
def test_clause_gate_cell(cell: Cell, monkeypatch: pytest.MonkeyPatch) -> None:
    probe = _probe(cell.member)
    clauses = _home(cell.member) if cell.met else _unmet(cell.gate, cell.member)
    tag = "".join(ch for ch in cell.id.title() if ch.isalnum())
    text, rendered = _check(
        clauses, probe, through_library=cell.through_library, tag=tag,
        monkeypatch=monkeypatch,
    )
    if cell.met:
        assert rendered is None, rendered
        return
    assert rendered is not None, "accepted a game that does not meet the gate"
    if not cell.through_library:
        where = f"{_GAME_FILE}:{_line_of(text, ' probe_fn(')}:"
        hits = [
            line for line in rendered.splitlines()
            if line.startswith(where) and cell.member in line and cell.gate.clause in line
        ]
        assert hits, rendered
        return
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    hits = [
        line for line in rendered.splitlines()
        if line.startswith(where)
        and f"'{_LIB}'" in line
        and cell.member in line
        and cell.gate.clause in line
    ]
    assert hits, rendered


# --- the ranking gate offers only remedies that remedy (issue #484) -----------
#
# Every name the ranking gate covers, in each position it can be named from,
# written by the game itself in a game with no `ranking:`. The refusal's
# remedies are claims, so each one it offers is applied and the game checked.

_REPO = Path(__file__).resolve().parent.parent

_TRICK_ORDER_TWINS = RANKING_TRICK_ORDER_TWINS
_TRICK_ORDER_WINNER = min(TRICK_ORDER_GATED_WINNERS)


def _trick_round(winner: str) -> str:
    return f"round play_to_trick from 0 over all players source hand into pile winner {winner}"


def _climb_round(lead: str, follows: str) -> str:
    return (
        "round climb play_combination from 0 over all players source hand into pile "
        f"combinations {lead} follows {follows} "
        "until (number of players where hand[player] is not empty) <= 1"
    )


def _corpus_witness(member: str) -> str:
    """The text of a checked-in game that declares and calls the Primitive
    `member`: a Primitive is reached only by declaration, so its witness is the
    game that declares it."""
    paths = sorted((_REPO / "docs" / "games").glob("*.cardlang")) + sorted(
        (_REPO / "experiments").glob("*/*.cardlang")
    )
    for path in paths:
        text = path.read_text()
        if "primitives {" in text and f"{member}(" in text:
            return text
    raise AssertionError(f"no checked-in game declares the Primitive {member}")


@dataclass(frozen=True)
class RankingCase:
    member: str
    position: str  # "call", "winner", "climb"


def _ranking_cases() -> list[RankingCase]:
    cases = [RankingCase(m, "call") for m in sorted(RANKING_GATED_FUNCS)]
    cases += [RankingCase(m, "winner") for m in sorted(RANKING_GATED_WINNERS)]
    cases += [RankingCase(m, "climb") for m in sorted(RANKING_GATED_CLIMB_QUERIES)]
    return cases


def _ranking_game(case: RankingCase, *, ranking: bool, twin: bool = False) -> str:
    """A game naming `case.member` in its position, with the round's own `trump`
    clause where the member reads one. `twin` applies the Trick Order remedy
    as the refusal words it: a block with `trump:` and `card_strength:` rows
    in place of the `trump` clause, and the Trick Order winner named or called
    in the member's place."""
    tag = f"{case.position}{case.member}{ranking}{twin}".replace("_", "").title()
    clauses = replace(_CARD, ranking=ranking, trick_order=twin)
    if case.position == "call":
        if case.member not in BUILTIN_CALL_FUNCS:
            text = _corpus_witness(case.member)
            if ranking:
                return text
            return "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith("ranking:")
            )
        probe = _probe(case.member)
        if twin:
            probe = _probe(_TRICK_ORDER_WINNER)
        return _game_text(clauses, uses=False, game_fn=_function(probe), tag=tag)
    if case.position == "winner":
        round_text = _trick_round(_TRICK_ORDER_WINNER if twin else case.member)
        if not twin and case.member in TRUMP_READING_WINNERS:
            round_text += " trump hearts"
        return _game_text(clauses, uses=False, game_fn="", tag=tag, statement=round_text)
    lead, follows = (
        (case.member, "bigtwo_follows")
        if case.member in PRIMITIVE_CLIMB_LEADS
        else ("bigtwo_lead_options", case.member)
    )
    return _game_text(
        clauses, uses=False, game_fn="", tag=tag, statement=_climb_round(lead, follows)
    )


def _rendered(text: str) -> str | None:
    try:
        check_dsl(text, _GAME_FILE)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None)
        return "\n".join(notes) if notes else exc.diagnostic.format()
    return None


def _member_refusal(case: RankingCase, rendered: str | None) -> str:
    assert rendered is not None, f"{case.member} accepted with no `ranking:`"
    hits = [
        line for line in rendered.splitlines()
        if case.member in line and "rank strength" in line
    ]
    assert len(hits) >= 1, rendered
    return hits[0]


@pytest.mark.parametrize(
    "case",
    [pytest.param(c, id=f"{c.position}-{c.member}") for c in _ranking_cases()],
)
def test_the_ranking_refusal_offers_the_trick_order_only_where_it_applies(
    case: RankingCase,
) -> None:
    refusal = _member_refusal(case, _rendered(_ranking_game(case, ranking=False)))
    offers_trick_order = "trick_order" in refusal
    assert offers_trick_order == (case.member in _TRICK_ORDER_TWINS), refusal


@pytest.mark.parametrize(
    "case", [pytest.param(c, id=f"{c.position}-{c.member}") for c in _ranking_cases()]
)
def test_declaring_a_ranking_clears_the_refusal(case: RankingCase) -> None:
    rendered = _rendered(_ranking_game(case, ranking=True))
    assert rendered is None or case.member not in rendered, rendered


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(c, id=f"{c.position}-{c.member}")
        for c in _ranking_cases()
        if c.member in _TRICK_ORDER_TWINS
    ],
)
def test_the_trick_order_remedy_clears_the_refusal(case: RankingCase) -> None:
    """The remedy as the refusal words it is the remedy `twin` applies: each
    piece of it is read off the message before the remedied game is checked."""
    refusal = _member_refusal(case, _rendered(_ranking_game(case, ranking=False)))
    assert "`trick_order { }` block with `trump:` and `card_strength:` rows" in refusal
    assert "in place of any `trump` clause" in refusal, refusal
    if case.position == "call":
        assert f"call `{_TRICK_ORDER_WINNER}(pile)` instead" in refusal, refusal
    else:
        assert f"name {_TRICK_ORDER_WINNER} as the winner" in refusal, refusal
    assert _rendered(_ranking_game(case, ranking=False, twin=True)) is None


# --- every definition kind a library holds reaches the gate the same way -----
#
# A Builtin call and a node construct, each in every definition kind. A rule
# reaches the game only where `active_rules:` switches it on; one no game
# activates is checked against its library alone (decisions.md "Family
# libraries"), so it is crossed with activation.

_KIND_TEMPLATES: dict[str, str] = {
    "rules": (
        "rule probe_rule {{ constrains: play_to_trick "
        "demands: cards in hand where {pred}  if_impossible: hand }}"
    ),
    "move_types": "move_type probe_mv {{ when: {pred} effect {{ }} }}",
    "functions": "function probe_fn() = {pred}",
    "procedures": "procedure probe_pr() {{ let x = {pred} }}",
}

# (the predicate a definition holds, the game that fails its gate, the words
# its refusal names)
_KIND_PROBES: dict[str, tuple[str, Clauses, tuple[str, str]]] = {
    "builtin": (
        "(sum of rank_value(card) over cards in pile) > 0",
        replace(_CARD, ranking=False, trick_order=True),
        ("rank_value", "ranking:"),
    ),
    "node": (
        "any team where true",
        replace(_CARD, teams=False, trick_order=True),
        ("`any team where`", "teams:"),
    ),
}


def _kind_cases() -> list[object]:
    cases: list[object] = []
    for field, _ in resolve_module._LIBRARY_DEF_KINDS:
        for probe in sorted(_KIND_PROBES):
            for activated in (True, False) if field == "rules" else (True,):
                case_id = f"{field}-{probe}" + ("" if activated else "-not_activated")
                cases.append(pytest.param(field, probe, activated, id=case_id))
    return cases


@pytest.mark.parametrize(("field", "probe", "activated"), _kind_cases())
def test_every_definition_kind_is_refused_on_the_uses_line(
    field: str, probe: str, activated: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    pred, clauses, (word, clause) = _KIND_PROBES[probe]
    library = parse_library(
        f"library {_LIB} {{\n"
        "  requires { pile : TrickPile  hand[player] : Hand<player> }\n"
        f"  {_KIND_TEMPLATES[field].format(pred=pred)}\n}}\n",
        _LIB_FILE,
    )
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    rounds = (
        "active_rules: [probe_rule]\n    "
        "round play_to_trick from 0 over all players source hand into pile "
        "winner highest_by_trick_order"
    )
    text = _game_text(
        clauses, uses=True, game_fn="",
        tag=f"Kind{field.title()}{probe.title()}{activated}",
        statement=rounds if field == "rules" and activated else "",
    )
    rendered = _rendered(text)
    if not activated:
        assert rendered is None, rendered
        return
    assert rendered is not None
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert any(
        line.startswith(where) and word in line and clause in line
        for line in rendered.splitlines()
    ), rendered


# --- the cells a library cannot reach, each pinned by the refusal that bars it


def _library_alone_refusal(
    library_text: str, clauses: Clauses, tag: str, monkeypatch: pytest.MonkeyPatch
) -> str:
    library = parse_library(library_text, _LIB_FILE)
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    rendered = _rendered(_game_text(clauses, uses=True, game_fn="", tag=tag))
    assert rendered is not None
    return rendered


_GATED_PRIMITIVES = sorted(
    frozenset[str]().union(*(gate.members for gate in GATES)) - BUILTIN_CALL_FUNCS
)


@pytest.mark.parametrize("member", _GATED_PRIMITIVES)
def test_a_library_cannot_call_a_clause_gated_primitive(
    member: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library calls Builtins only, so a gated Primitive never reaches a game
    through one: the library is refused in its own file, to its own author.

    red under: widening the `function` namespace of
    `resolve._library_slot_names` to `CALL_FUNCS` (executed 2026-10-13)."""
    rendered = _library_alone_refusal(
        f"library {_LIB} {{ function probe_fn() = {member}() }}",
        _CARD,
        f"Prim{member.replace('_', '').title()}",
        monkeypatch,
    )
    assert any(
        line.startswith(_LIB_FILE) and f"'{member}'" in line
        and "which is a Primitive" in line
        for line in rendered.splitlines()
    ), rendered


_UNSPELLABLE = sorted(
    m
    for gate in GATES
    for m in gate.members & BUILTIN_CALL_FUNCS
    if not _probe(m).library_spellable
)


@pytest.mark.parametrize("member", sorted(set(_UNSPELLABLE)))
def test_a_library_cannot_spell_a_cell_or_direction(
    member: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A board verb taking a cell or a direction never reaches a game through a
    library: a library declares no positions, so the parameter's type is
    refused in its own file, to its own author.

    red under: adding the position names `cell` and `dir` to the `type`
    namespace of `resolve._library_slot_names` (executed 2026-10-13)."""
    probe = _probe(member)
    rendered = _library_alone_refusal(
        f"library {_LIB} {{ function probe_fn({probe.params}) = {probe.call} }}",
        _BOARD,
        f"Pos{member.replace('_', '').title()}",
        monkeypatch,
    )
    assert any(
        line.startswith(_LIB_FILE)
        and ("type 'cell'" in line or "type 'dir'" in line)
        and "the library does not have" in line
        for line in rendered.splitlines()
    ), rendered


_SLOT_ROUNDS: dict[str, str] = {
    **{w: _trick_round(w) for w in sorted(RANKING_GATED_WINNERS | TRICK_ORDER_GATED_WINNERS)},
    **{
        q: (
            _climb_round(q, "bigtwo_follows")
            if q in PRIMITIVE_CLIMB_LEADS
            else _climb_round("bigtwo_lead_options", q)
        )
        for q in sorted(RANKING_GATED_CLIMB_QUERIES)
    },
}


@pytest.mark.parametrize("member", sorted(_SLOT_ROUNDS))
def test_a_library_procedure_cannot_hold_a_round(
    member: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A procedure body may not hold a round, and a climbing query is a
    Primitive, which no library names (tests/test_library_round_slot_primitives.py),
    so a library naming a gated winner or climbing query there is refused in
    its own file, in a game whose clauses meet the gate. A library reaches a
    game with a round through a move type's effect, which the node cells run.

    red under: disabling the `_WINNER_BINDING_STMTS` arm of
    `resolve._check_procedures` (the winners, executed 2026-10-13), or
    `resolve._round_slot_primitives` (the climbing queries, executed
    2026-10-14)."""
    rendered = _library_alone_refusal(
        f"library {_LIB} {{\n"
        "  requires { pile : TrickPile  hand[player] : Hand<player> }\n"
        f"  procedure probe_pr() {{ {_SLOT_ROUNDS[member]} }}\n}}\n",
        replace(_CARD, trick_order=member in TRICK_ORDER_GATED_WINNERS),
        f"Slot{member.replace('_', '').title()}",
        monkeypatch,
    )
    refusal = (
        f"names '{member}', which is a Primitive"
        if walled_namespace_of(member) is not None
        else "contains a `round`"
    )
    assert any(
        line.startswith(_LIB_FILE) and refusal in line for line in rendered.splitlines()
    ), rendered


# --- misuse probes: the sentences a designer plausibly gets wrong -------------


def _with_libraries(
    monkeypatch: pytest.MonkeyPatch, libraries: dict[str, str]
) -> None:
    parsed = {
        name: parse_library(text, f"docs/libraries/{name}.cardlang")
        for name, text in libraries.items()
    }
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset(parsed))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: parsed[name])


_RANK_LIB = "library probe_lib { function probe_fn(c : Card) = rank_value(c) }"


def _corpus_ranking_witnesses() -> list[tuple[str, str]]:
    """(corpus game file, library it uses) for every corpus game that declares
    a `ranking:` and uses a checked-in library whose definitions call a
    ranking-gated Builtin."""
    found: list[tuple[str, str]] = []
    for path in sorted((_REPO / "docs" / "games").glob("*.cardlang")):
        lines = path.read_text().splitlines()
        if not any(line.lstrip().startswith("ranking:") for line in lines):
            continue
        for line in lines:
            words = line.split()
            if len(words) == 2 and words[0] == "uses" and words[1] in library_names():
                game = parse_text("\n".join(lines), path.name)
                calls = resolve_module._library_calls(load_library(words[1]), game)
                if any(call.func in RANKING_GATED_FUNCS for call, _ in calls):
                    found.append((path.name, words[1]))
    return found


def test_the_corpus_holds_a_ranking_witness() -> None:
    """The corpus cells below are not vacuous: some checked-in library reaches
    a ranking-gated Builtin, and some corpus game uses it."""
    assert _corpus_ranking_witnesses()


@pytest.mark.parametrize(
    ("game_file", "library"),
    [pytest.param(g, lib, id=f"{g}-{lib}") for g, lib in _corpus_ranking_witnesses()],
)
def test_a_corpus_game_without_its_ranking_is_told_on_its_uses_line(
    game_file: str, library: str
) -> None:
    """A real game and a real library: the game stays valid as written, and with
    its `ranking:` line deleted the refusal names the library on the game's own
    `uses` line and nothing inside the library file."""
    path = _REPO / "docs" / "games" / game_file
    text = path.read_text()
    assert _rendered(text.replace("game ", "game Witness", 1)) is None
    stripped = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("ranking:")
    )
    rendered = _rendered(stripped.replace("game ", "game Unranked", 1))
    assert rendered is not None
    assert f"docs/libraries/{library}.cardlang" not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(stripped, f'uses {library}')}:"
    assert any(
        line.startswith(where) and f"'{library}'" in line and "ranking:" in line
        and any(member in line for member in RANKING_GATED_FUNCS)
        for line in rendered.splitlines()
    ), rendered


def test_a_ranking_convention_meets_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ranking: aces high` is a `ranking:` the checker expands later, so a
    library reading rank strength is accepted beside it."""
    _with_libraries(monkeypatch, {_LIB: _RANK_LIB})
    text = _game_text(replace(_CARD, ranking=False), uses=True, game_fn="", tag="Conv")
    text = text.replace("  max_length: 1000", "  max_length: 1000\n  ranking: aces high")
    assert _rendered(text) is None


def test_a_convention_on_a_misspelled_deck_names_the_deck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The game wrote a `ranking:`; what is wrong is the deck it names, and the
    refusal says that rather than asking for a clause the game already has."""
    _with_libraries(monkeypatch, {_LIB: _RANK_LIB})
    text = _game_text(replace(_CARD, ranking=False), uses=True, game_fn="", tag="Deck")
    text = text.replace("cards: standard52", "cards: standrd52\n  ranking: aces high")
    rendered = _rendered(text)
    assert rendered is not None and "standrd52" in rendered, rendered
    assert "declares no `ranking:`" not in rendered, rendered
    assert _LIB_FILE not in rendered, rendered


def test_a_malformed_teams_clause_is_refused_at_the_clause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `teams:` that does not partition the seats is declared, so the library
    is not blamed: the refusal is the clause's own."""
    _with_libraries(
        monkeypatch, {_LIB: "library probe_lib { function probe_fn(p : Player) = team_of(p) }"}
    )
    text = _game_text(_CARD, uses=True, game_fn="", tag="BadTeams")
    text = text.replace("teams: [[0, 2], [1, 3]]", "teams: [[0, 2], [1]]")
    rendered = _rendered(text)
    assert rendered is not None
    assert "seat 3" in rendered, rendered
    assert _LIB_FILE not in rendered and "probe_lib" not in rendered, rendered


def test_two_libraries_are_each_refused_on_their_own_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _with_libraries(
        monkeypatch,
        {
            "ranks": "library ranks { function by_rank(c : Card) = rank_value(c) }",
            "points": "library points { function by_points(c : Card) = card_points(c) }",
        },
    )
    text = _game_text(
        replace(_CARD, ranking=False, card_points=False), uses=False, game_fn="", tag="Two"
    )
    text = text.replace("  max_length: 1000", "  max_length: 1000\n  uses ranks\n  uses points")
    rendered = _rendered(text)
    assert rendered is not None
    assert "docs/libraries/" not in rendered, rendered
    for library, member, clause in (
        ("ranks", "rank_value", "ranking:"), ("points", "card_points", "card_points")
    ):
        where = f"{_GAME_FILE}:{_line_of(text, f'uses {library}')}:"
        assert any(
            line.startswith(where) and f"'{library}'" in line
            and member in line and clause in line
            for line in rendered.splitlines()
        ), rendered


def test_one_library_missing_two_clauses_is_told_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _with_libraries(
        monkeypatch,
        {
            _LIB: "library probe_lib { function probe_fn(c : Card) = "
            "rank_value(c) + card_points(c) }"
        },
    )
    text = _game_text(
        replace(_CARD, ranking=False, card_points=False), uses=True, game_fn="", tag="Both"
    )
    rendered = _rendered(text)
    assert rendered is not None
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    lines = [line for line in rendered.splitlines() if line.startswith(where)]
    assert any("rank_value" in line and "ranking:" in line for line in lines), rendered
    assert any("card_points(" in line or "`card_points`" in line for line in lines), rendered


# --- the gates on constructs that are not Builtin calls -----------------------
#
# The same law for every construct a game clause decides that a library can
# write: a move parameter's domain, a range's role, a provided declaration's
# index, a card form in a piece game, a position past a board region, a round's
# winner or climbing query. Each member is written once, as a definition, and
# checked written by the game and reached through a library, in a game that
# meets its gate and in one that fails it.


@dataclass(frozen=True)
class NodeGame:
    """The probe game a node member is checked in: its clauses, plus the
    game-level `trump:` a trump-reading winner reads."""

    clauses: Clauses
    trump: bool = False


@dataclass(frozen=True)
class NodeMember:
    """One construct a node gate decides: the definition holding it (named
    `probe_fn`), what the library contracts for or provides, the words a
    refusal must name, and the games that meet and fail the gate."""

    gate: str
    construct: str
    definition: str
    word: str
    clause: str
    met: NodeGame
    unmet: NodeGame
    requires: str = ""
    provided: str = ""
    # What the game-written refusal names, where it is not the clause.
    game_word: str = ""

    @property
    def id(self) -> str:
        return f"{self.gate}-{self.construct}"


def _node_game_text(
    member: NodeMember, game: NodeGame, *, through_library: bool, tag: str
) -> str:
    c = game.clauses
    if c.pieces:
        content = "pieces: breakthrough_men"
        zones = "box : Deck  reserve[player] : PlayerPile<player>  pile : TrickPile"
    else:
        content = "cards: standard52"
        zones = "deck : Deck  hand[player] : Hand<player>  pile : TrickPile"
    if c.board:
        zones += "  square[cell] : Cell<cell>"
    state = "score[player] : Integer = 0"
    if member.provided and not through_library:
        state += f"  {member.provided}"
    definition = member.definition
    statement = ""
    if definition.startswith("procedure"):
        statement = "run probe_fn()"
    elif definition.startswith("move_type"):
        statement = "turns t from 0 over all players until true { offer to t one of [probe_fn] }"
    written = not through_library and definition != "state"
    lines = [
        f"game Probe{tag} {{",
        f"  players: {c.players}",
        f"  {_teams_clause(c.players)}" if c.teams else "",
        "  max_length: 1000",
        f"  {content}",
        f"  board: grid({c.board_size}, {c.board_size})" if c.board else "",
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2" if c.ranking else "",
        "  trump: hearts" if game.trump else "",
        (
            "  trick_order { trump: card.suit is hearts  card_strength: 1 }"
            if c.trick_order
            else ""
        ),
        f"  uses {_LIB}" if through_library else "",
        f"  zones {{ {zones} }}",
        f"  state {{ {state} }}",
        "  phase p {",
        "    let w = highest_by_trick_order(pile)" if c.trick_order else "",
        "    for each player q: score[q] := 0",
        f"    {statement}",
        "  }",
        "  winner: highest score",
        "}",
        definition if written else "",
    ]
    return "\n".join(lines) + "\n"


def _node_library_text(member: NodeMember) -> str:
    requires = f"requires {{ {member.requires} }}" if member.requires else ""
    provided = f"state {{ {member.provided} }}" if member.provided else ""
    definition = "" if member.definition == "state" else member.definition
    return f"library {_LIB} {{\n  {requires}\n  {provided}\n  {definition}\n}}\n"


# --- the axes, each derived from the registry that defines it ----------------

_CARD_AXIS_ROLE_NAMES = frozenset(role.value for role in CARD_AXIS_ROLES)


def _role_members() -> list[NodeMember]:
    """Every iterable role crossed with every range form that names one: `for
    each`, and the `any`/`all` quantifiers. A board's `cell` is ranged by `for
    each` alone: its quantifier is the position query, which names a declared
    position domain, and a library declares none."""
    members: list[NodeMember] = []
    roles = sorted(role.value for role in ITERABLE_ROLES) + [BOARD_DOMAIN]
    for role in roles:
        forms = [("for_each", f"procedure probe_fn() {{ for each {role} x: let y = 1 }}")]
        if role != BOARD_DOMAIN:
            forms += [
                ("any", f"function probe_fn() = any {role} where true"),
                ("all", f"function probe_fn() = all {role}s where true"),
            ]
        for form, definition in forms:
            if role == "team":
                gate, word, clause = "team_range", "team", "teams:"
                met, unmet = NodeGame(_CARD), NodeGame(replace(_CARD, teams=False))
            elif role == BOARD_DOMAIN:
                gate, word, clause = "cell_range", "for each cell", "board:"
                met, unmet = NodeGame(_BOARD), NodeGame(replace(_BOARD, board=False))
            elif role in _CARD_AXIS_ROLE_NAMES:
                gate, word, clause = "card_axis_role", role, "pieces"
                met, unmet = NodeGame(_CARD), NodeGame(_PIECES)
            else:
                gate, word, clause = "clause_free", role, ""
                met, unmet = NodeGame(_CARD), NodeGame(_CARD)
            members.append(
                NodeMember(gate, f"{form}_{role}", definition, word, clause, met, unmet)
            )
    return members


def _state_index_members() -> list[NodeMember]:
    """Provided state keyed by every role a declaration may be keyed by."""
    members: list[NodeMember] = []
    for role in sorted(r.value for r in ZONE_INDEX_ROLES):
        decl = f"won[{role}] : Integer = 0"
        if role == "team":
            members.append(
                NodeMember(
                    "team_state", "team", "state", "won[team]", "teams:",
                    NodeGame(_CARD), NodeGame(replace(_CARD, teams=False)), provided=decl,
                )
            )
        else:
            members.append(
                NodeMember(
                    "clause_free", f"state_{role}", "state", role, "",
                    NodeGame(_CARD), NodeGame(_CARD), provided=decl,
                )
            )
    return members


def _move_parameter_members() -> list[NodeMember]:
    """A move type taking each parameter domain fixed by the language or by
    the deck. `Rank` is gated twice: by the content flavor and by `ranking:`."""
    members: list[NodeMember] = []
    for domain in sorted(_FIXED_PARAM_DOMAINS | CARD_PARAM_DOMAINS):
        definition = f"move_type probe_fn(x : {domain}) {{ effect {{ }} }}"
        tag = domain.replace("?", "_opt")
        if domain in CARD_PARAM_DOMAINS:
            members.append(
                NodeMember(
                    "card_content", f"param_{tag}", definition, f"`{domain}`", "pieces",
                    NodeGame(_CARD), NodeGame(_PIECES),
                )
            )
        else:
            members.append(
                NodeMember(
                    "clause_free", f"param_{tag}", definition, domain, "",
                    NodeGame(_CARD), NodeGame(_CARD),
                )
            )
        if domain == "Rank":
            members.append(
                NodeMember(
                    "rank_parameter", "param_Rank", definition, "`Rank`", "ranking:",
                    NodeGame(_CARD), NodeGame(replace(_CARD, ranking=False)),
                )
            )
    return members


# Every grammar alternative that reads a zone as cards, keyed by its
# alternative name, written as a function body over the contracted `pile`.
_CARD_FORM_PROBES: dict[str, str] = {
    "cq_set": "cards in pile where true",
    "cq_count": "number of cards in pile",
    "cq_any": "any card in pile where true",
    "cq_all": "all cards in pile where true",
    "sq_any": "any subset of 2 cards in pile where true",
    "sq_all": "all subsets of 2 cards in pile where true",
    "sq_count": "number of subsets of 2 cards in pile where true",
    "agg_sum": "sum of 1 over cards in pile",
    "agg_order": "highest 1 over cards in pile or 0",
    "agg_subset_sum": "sum of 1 over subsets of 2 cards in pile",
    "agg_subset_order": "highest 1 over subsets of 2 cards in pile or 0",
}


def _card_form_alternatives() -> frozenset[str]:
    """The grammar's card-reading alternatives: the aliases of the
    `card_query`, `subset_query` and `agg_query` productions."""
    grammar = (_REPO / "cardlang" / "grammar" / "cardlang.lark").read_text()
    return frozenset(re.findall(r"->\s*((?:cq|sq|agg)_\w+)", grammar))


def test_the_card_form_probes_are_the_grammar_alternatives() -> None:
    """A card-reading form added to the grammar is a red here until it has a
    probe, so the card-content cells cannot quietly miss it.

    red under: adding an alternative `-> cq_none` to `card_query` in
    cardlang/grammar/cardlang.lark (executed 2026-10-14)."""
    assert _card_form_alternatives() == frozenset(_CARD_FORM_PROBES)


def _card_form_members() -> list[NodeMember]:
    members = [
        NodeMember(
            "card_content", alias, f"function probe_fn() = {text}", "", "pieces",
            NodeGame(_CARD), NodeGame(_PIECES), requires="pile : TrickPile",
        )
        for alias, text in sorted(_CARD_FORM_PROBES.items())
    ]
    members.append(
        NodeMember(
            "card_content", "reveal", "procedure probe_fn() { reveal one card from pile }",
            "reveal one card", "pieces", NodeGame(_CARD), NodeGame(_PIECES),
            requires="pile : TrickPile",
        )
    )
    return members


_ROUND_ZONES = "hand[player] : Hand<player>  pile : TrickPile"


def _round_definition(round_text: str, params: str = "") -> str:
    head = f"move_type probe_fn({params})" if params else "move_type probe_fn"
    return f"{head} {{ effect {{ {round_text} }} }}"


def _round_members() -> list[NodeMember]:
    """Every trick-round winner, a round's own `trump` clause, and every
    climbing query, in a round a move type's effect holds, against each
    clause that decides it."""
    members: list[NodeMember] = []
    no_order = replace(_CARD, trick_order=False)
    with_order = replace(_CARD, trick_order=True)
    for winner in sorted(TRICK_WINNER_NAMES):
        definition = _round_definition(_trick_round(winner))
        trump = winner in TRUMP_READING_WINNERS
        members.append(
            NodeMember(
                "card_content", f"winner_{winner}", definition, winner, "pieces",
                NodeGame(with_order if winner in TRICK_ORDER_GATED_WINNERS else no_order, trump),
                NodeGame(_PIECES), requires=_ROUND_ZONES,
            )
        )
        if winner in TRICK_ORDER_GATED_WINNERS:
            members.append(
                NodeMember(
                    "trick_order_reading", f"winner_{winner}", definition, winner,
                    "trick_order", NodeGame(with_order), NodeGame(no_order),
                    requires=_ROUND_ZONES,
                )
            )
        if winner in TRICK_ORDER_EXCLUDED_WINNERS:
            members.append(
                NodeMember(
                    "trick_order_replaced", f"winner_{winner}", definition, winner,
                    "trick_order", NodeGame(no_order, trump), NodeGame(with_order),
                    requires=_ROUND_ZONES,
                )
            )
        if winner in RANKING_GATED_WINNERS:
            members.append(
                NodeMember(
                    "ranking_slot", f"winner_{winner}", definition, winner, "ranking:",
                    NodeGame(no_order, trump), NodeGame(replace(_CARD, ranking=False), trump),
                    requires=_ROUND_ZONES,
                )
            )
    members.append(
        NodeMember(
            "trick_order_replaced", "round_trump_clause",
            _round_definition(_trick_round("highest_trump_or_led_suit") + " trump s", "s : Suit"),
            "`trump` clause", "trick_order", NodeGame(no_order), NodeGame(with_order),
            requires=_ROUND_ZONES,
        )
    )
    for query in sorted(PRIMITIVE_CLIMB_LEADS | PRIMITIVE_CLIMB_FOLLOWS):
        family = query.split("_")[0]
        definition = _round_definition(
            _climb_round(f"{family}_lead_options", f"{family}_follows")
        )
        members.append(
            NodeMember(
                "card_content", f"climb_{query}", definition, query, "pieces",
                NodeGame(no_order), NodeGame(_PIECES), requires=_ROUND_ZONES,
            )
        )
        members.append(
            NodeMember(
                "trick_order_replaced", f"climb_{query}", definition, query, "trick_order",
                NodeGame(no_order), NodeGame(with_order), requires=_ROUND_ZONES,
            )
        )
        if query in RANKING_GATED_CLIMB_QUERIES:
            members.append(
                NodeMember(
                    "ranking_slot", f"climb_{query}", definition, query, "ranking:",
                    NodeGame(no_order), NodeGame(replace(_CARD, ranking=False)),
                    requires=_ROUND_ZONES,
                )
            )
    return members


# Past every region of the smallest board probed, inside every region of the
# largest.
_PAST = 9


def _region_members() -> list[NodeMember]:
    """A literal position into each board region, on a board large enough and
    on one too small."""
    members: list[NodeMember] = []
    for region in sorted(resolve_module._REGION_CALL_FUNCS):
        seat = isinstance(CALL_SIGS[region].params[0], TPlayer)
        members.append(
            NodeMember(
                "board_position", region,
                f"function probe_fn({'p : Player' if seat else ''}) = "
                f"{region}({'p' if seat else '3'})[{_PAST}]",
                f"{region}(...)[{_PAST}]", "board: grid(3, 3)",
                NodeGame(replace(_BOARD, board_size=10)), NodeGame(_BOARD),
                game_word="past the end",
            )
        )
    return members


def _node_members() -> list[NodeMember]:
    return (
        _role_members()
        + _state_index_members()
        + _move_parameter_members()
        + _card_form_members()
        + _round_members()
        + _region_members()
    )


# The node rows of `resolve._CLAUSE_GATES`, by the name the grid gives them.
# Named rather than imported, so the cell table derives on a tree without them.
NODE_GATES: dict[str, str] = {
    "card_content": "_CARD_CONTENT_GATE",
    "trick_order_reading": "_TRICK_ORDER_READING_GATE",
    "trick_order_replaced": "_TRICK_ORDER_REPLACED_GATE",
    "team_range": "_TEAM_RANGE_GATE",
    "team_state": "_TEAM_STATE_GATE",
    "cell_range": "_CELL_RANGE_GATE",
    "board_position": "_BOARD_POSITION_GATE",
    "rank_parameter": "_RANK_PARAMETER_GATE",
    "ranking_slot": "_RANKING_SLOT_GATE",
}

# Members the `uses` check does not hold, each with its record.
_HELD_ELSEWHERE: dict[str, str] = {
    "card_axis_role": (
        "a card-axis role in a piece game is refused in the library file; "
        "issue #183 decides whether a library may name one at all"
    ),
}


def test_the_uses_check_holds_a_row_for_every_node_gate() -> None:
    """The rows of the `uses`-line check's table that are not keyed on a
    Builtin are exactly the node gates this grid runs, so a node gate the
    table lacks, or one the grid never runs, is a red here.

    red under: deleting `_CELL_RANGE_GATE` from `resolve._CLAUSE_GATES`
    (executed 2026-10-14)."""
    rows = [getattr(resolve_module, name) for name in NODE_GATES.values()]
    table = [row for row in resolve_module._CLAUSE_GATES if not row.members]
    assert len(table) == len(rows) and all(row in table for row in rows)
    gates = {m.gate for m in _node_members()} - {"clause_free"} - set(_HELD_ELSEWHERE)
    assert gates == set(NODE_GATES)


@dataclass(frozen=True)
class NodeCell:
    member: NodeMember
    met: bool
    through_library: bool

    @property
    def id(self) -> str:
        return (
            f"{self.member.id}-{'met' if self.met else 'unmet'}-"
            f"{'library' if self.through_library else 'game'}"
        )


def _node_cells() -> list[object]:
    params: list[object] = []
    for member in _node_members():
        for met in (True, False):
            if member.gate == "clause_free" and not met:
                continue
            for through_library in (False, True):
                cell = NodeCell(member, met, through_library)
                marks = []
                if member.gate in _HELD_ELSEWHERE and through_library and not met:
                    marks.append(
                        pytest.mark.xfail(
                            strict=True, raises=AssertionError,
                            reason=_HELD_ELSEWHERE[member.gate],
                        )
                    )
                params.append(pytest.param(cell, id=cell.id, marks=marks))
    return params


def _check_node(
    member: NodeMember, game: NodeGame, *, through_library: bool, tag: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str | None]:
    if through_library:
        library = parse_library(_node_library_text(member), _LIB_FILE)
        monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
        monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    text = _node_game_text(member, game, through_library=through_library, tag=tag)
    return text, _rendered(text)


def _construct_line(text: str, member: NodeMember) -> int:
    if member.provided:
        return _line_of(text, member.provided)
    kind = member.definition.split(" ")[0]
    return _line_of(text, f"{kind} probe_fn")


def _node_tag(cell_id: str) -> str:
    return "".join(ch for ch in cell_id.title() if ch.isalnum())


def _library_alone(member: NodeMember) -> bool:
    """A member no library may write: a climbing query is a Primitive, so a
    library round naming one is refused in the library file whatever the
    game's clauses (tests/test_library_round_slot_primitives.py), and its
    `uses`-line gate never judges it."""
    return walled_namespace_of(member.word) is not None


def _assert_library_alone_refusal(member: NodeMember, text: str, rendered: str | None) -> None:
    """The member's library-alone refusal, in the library file, and no
    clause-gate refusal of it on the game's `uses` line. A piece game also
    meets the contract's unmet `hand` zone there, which is not the member's."""
    assert rendered is not None, "accepted a library naming a Primitive"
    lines = rendered.splitlines()
    assert any(
        line.startswith(_LIB_FILE) and f"names '{member.word}', which is a Primitive" in line
        for line in lines
    ), rendered
    uses_line = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert not any(line.startswith(uses_line) and member.word in line for line in lines), rendered


@pytest.mark.parametrize("cell", _node_cells())
def test_node_gate_cell(cell: NodeCell, monkeypatch: pytest.MonkeyPatch) -> None:
    member = cell.member
    game = member.met if cell.met else member.unmet
    text, rendered = _check_node(
        member, game, through_library=cell.through_library, tag=_node_tag(cell.id),
        monkeypatch=monkeypatch,
    )
    if cell.through_library and _library_alone(member):
        _assert_library_alone_refusal(member, text, rendered)
        return
    if cell.met:
        assert rendered is None, rendered
        return
    assert rendered is not None, "accepted a game that does not meet the gate"
    clause = member.clause.rstrip(":")
    if not cell.through_library:
        where = f"{_GAME_FILE}:{_construct_line(text, member)}:"
        word = member.game_word or clause
        assert any(
            line.startswith(where) and word in line for line in rendered.splitlines()
        ), rendered
        return
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert any(
        line.startswith(where) and f"'{_LIB}'" in line and member.word in line
        and clause in line
        for line in rendered.splitlines()
    ), rendered


# --- each node gate asks its row's test, not a copy of it --------------------
#
# Each gate's test has one home. Emptying that home must clear the refusal of
# every member the game writes, so a downstream gate restating the test inline
# would still refuse here, and be red.


def _no_needs(row_name: str) -> tuple[object, str, object]:
    row = getattr(resolve_module, row_name)
    return resolve_module, row_name, replace(row, needs=lambda nd, g: ())


def _homes(gate: str) -> list[tuple[object, str, object]]:
    """Where `gate`'s test lives, as (module, attribute, emptied value)."""
    match gate:
        case "card_content":
            return [
                _no_needs("_CARD_CONTENT_GATE"),
                (typecheck_module, "card_content_forms", lambda nd: ()),
            ]
        case "trick_order_reading":
            return [(resolve_module, "_trick_order_reading_slots", lambda nd, g: ())]
        case "trick_order_replaced":
            return [
                (resolve_module, name, lambda nd, g: ())
                for name in (
                    "_round_trump_clauses", "_trick_order_excluded_winners", "_climb_queries"
                )
            ]
        case "board_position":
            return [(resolve_module, "_position_past_end", lambda nd, g: None)]
        case "ranking_slot":
            return [(typecheck_module, "ranking_gated_slots", lambda nd: ())]
    return [_no_needs(NODE_GATES[gate])]


# What each gate's own refusal says, for a member the game writes.
_GATE_REFUSALS: dict[str, str] = {
    "card_content": "this game declares pieces",
    "trick_order_reading": "reads the game's `trick_order { }` block, but this game declares none",
    "trick_order_replaced": "beside a `trick_order { }` block",
    "team_range": "ranges over teams",
    "team_state": "is indexed by 'team'",
    "cell_range": "ranges over the board's cells",
    "board_position": "is past the end",
    "rank_parameter": "has a Rank parameter",
    "ranking_slot": "reads a card's rank strength",
}


@pytest.mark.parametrize(
    "member",
    [pytest.param(m, id=m.id) for m in _node_members() if m.gate in NODE_GATES],
)
def test_each_node_gate_asks_its_rows_test(
    member: NodeMember, monkeypatch: pytest.MonkeyPatch
) -> None:
    """red under: restating the team range test inline in the `ForEach` /
    `Quantifier` team arm of `resolve._validate_refs` (`role_of(nd.role) is
    Role.TEAM and not game.teams`) (executed 2026-10-14)."""
    text = _node_game_text(
        member, member.unmet, through_library=False, tag=f"Home{_node_tag(member.id)}"
    )
    refused = _rendered(text)
    assert refused is not None and _GATE_REFUSALS[member.gate] in refused, refused
    for module, name, value in _homes(member.gate):
        monkeypatch.setattr(module, name, value)
    emptied = _rendered(text.replace("game Home", "game Emptied", 1))
    assert emptied is None or _GATE_REFUSALS[member.gate] not in emptied, emptied


# --- the members a node test cannot reach, each with its record --------------
#
# A construct whose flavor question issue #170 holds is refused in the library
# file, and its cell names what fixing it means. A gate that needs an operand's
# type is told through the splice's origin stamp instead
# (tests/test_library_type_gates.py).

@dataclass(frozen=True)
class HeldMember:
    name: str
    library: str
    game: str
    word: str
    clause: str
    reason: str
    # What the gate that refuses it today says, in the library file.
    refusal: str


_HELD: tuple[HeldMember, ...] = (
    HeldMember(
        "movement_filter",
        "requires { box : Deck  pile : TrickPile } procedure probe_fn() "
        "{ move all cards from box where card.rank is card.rank to pile }",
        "pieces", "card", "pieces",
        "issue #170: a movement's item noun and its filter's binder follow the "
        "game's content flavor, and that issue decides who owns the question",
        "unresolved name 'card'",
    ),
)


def _held_game(held: HeldMember) -> str:
    clauses = {"pieces": _PIECES}[held.game]
    return _game_text(clauses, uses=True, game_fn="", tag=f"Held{held.name.title()}")


@pytest.mark.parametrize(
    "held",
    [
        pytest.param(
            h, id=h.name,
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=h.reason),
        )
        for h in _HELD
    ],
)
def test_a_held_member_is_refused_on_the_uses_line(
    held: HeldMember, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_libraries(monkeypatch, {_LIB: f"library {_LIB} {{ {held.library} }}"})
    text = _held_game(held)
    rendered = _rendered(text)
    assert rendered is not None
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert any(
        line.startswith(where) and held.word in line and held.clause in line
        for line in rendered.splitlines()
    ), rendered


@pytest.mark.parametrize("held", [pytest.param(h, id=h.name) for h in _HELD])
def test_a_held_member_is_refused_in_the_library_file(
    held: HeldMember, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard that stands until the held cells move: loud, in the library's
    file."""
    _with_libraries(monkeypatch, {_LIB: f"library {_LIB} {{ {held.library} }}"})
    rendered = _rendered(_held_game(held))
    assert rendered is not None
    assert any(
        line.startswith(_LIB_FILE) and held.refusal in line for line in rendered.splitlines()
    ), rendered


# --- deck capacity is judged where the game runs the deal ---------------------


@pytest.mark.parametrize("count", [13, 14])
def test_a_library_deal_is_judged_at_the_phase_that_runs_it(
    count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deck capacity is counted after the procedure is spliced into the phase
    that runs it, so a library's deal the deck cannot hold is refused at that
    phase, in the game's own file, and never in the library's."""
    _with_libraries(
        monkeypatch,
        {
            _LIB: f"library {_LIB} {{ requires {{ deck : Deck  hand[player] : Hand<player> }} "
            f"procedure deal_all() {{ deal {count} cards from deck to each hand }} }}"
        },
    )
    text = _game_text(
        _CARD, uses=True, game_fn="", tag=f"Deal{count}", statement="run deal_all()"
    )
    rendered = _rendered(text)
    if count * 4 <= 52:
        assert rendered is None, rendered
        return
    assert rendered is not None
    assert _LIB_FILE not in rendered, rendered
    assert rendered.startswith(f"{_GAME_FILE}:{_line_of(text, 'phase p')}:"), rendered
    assert "deals up to" in rendered, rendered


# --- misuse probes and remedies for the node gates ----------------------------


def _uses_line_refusal(text: str, rendered: str | None) -> str:
    assert rendered is not None
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    hits = [line for line in rendered.splitlines() if line.startswith(where)]
    assert hits, rendered
    return hits[0]


@pytest.mark.parametrize("players", [2, 3, 4, 5, 6])
def test_the_offered_teams_clause_partitions_the_seats(
    players: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `teams:` a team refusal offers is written for this game's seats, and
    pasted in as written it clears the refusal."""
    _with_libraries(
        monkeypatch, {_LIB: f"library {_LIB} {{ function probe_fn() = any team where true }}"}
    )
    clauses = replace(_CARD, players=players, teams=False)
    text = _game_text(clauses, uses=True, game_fn="", tag=f"Seats{players}")
    refusal = _uses_line_refusal(text, _rendered(text))
    offered = re.search(r"`(teams: \[.*\])`", refusal)
    assert offered is not None, refusal
    remedied = text.replace("  max_length: 1000", f"  {offered.group(1)}\n  max_length: 1000")
    assert _rendered(remedied.replace("game Seats", "game Remedied", 1)) is None


@pytest.mark.parametrize("pieces", [True, False])
def test_the_board_refusal_offers_a_board_only_where_one_is_legal(
    pieces: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `board:` is legal only beside `pieces:`. A piece game is offered one,
    and declaring it clears the refusal; a card game is told it cannot use the
    library, for a cell range and for a board-reading Builtin alike.

    red under: returning "declare one" for every flavor from
    `resolve._board_fix` (executed 2026-10-14)."""
    library = (
        f"library {_LIB} {{ procedure probe_fn() {{ for each cell c: let y = 1 }} "
        f"function probe_lines() = lines(3) }}"
    )
    _with_libraries(monkeypatch, {_LIB: library})
    clauses = replace(_BOARD, board=False) if pieces else _CARD
    text = _game_text(
        clauses, uses=True, game_fn="", tag=f"Cells{pieces}", statement="run probe_fn()"
    )
    rendered = _rendered(text)
    assert rendered is not None
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    refusals = [line for line in rendered.splitlines() if line.startswith(where)]
    assert len(refusals) == 2, rendered
    for refusal in refusals:
        assert ("declare one" in refusal) == pieces, refusal
        assert ("a card game cannot use this library" in refusal) == (not pieces), refusal
    if pieces:
        remedied = text.replace("  max_length: 1000", "  board: grid(3, 3)\n  max_length: 1000")
        assert _rendered(remedied.replace("game Cells", "game Remedied", 1)) is None


_RANK_PARAM_LIB = (
    f"library {_LIB} {{ move_type probe_fn(r : Rank) {{ effect {{ }} }} }}"
)


def test_a_ranking_convention_meets_the_rank_parameter_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _with_libraries(monkeypatch, {_LIB: _RANK_PARAM_LIB})
    text = _game_text(replace(_CARD, ranking=False), uses=True, game_fn="", tag="ConvParam")
    text = text.replace("  max_length: 1000", "  max_length: 1000\n  ranking: aces high")
    assert _rendered(text) is None


def test_a_convention_on_a_misspelled_deck_does_not_ask_for_a_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _with_libraries(monkeypatch, {_LIB: _RANK_PARAM_LIB})
    text = _game_text(replace(_CARD, ranking=False), uses=True, game_fn="", tag="DeckParam")
    text = text.replace("cards: standard52", "cards: standrd52\n  ranking: aces high")
    rendered = _rendered(text)
    assert rendered is not None and "standrd52" in rendered, rendered
    assert "declares no `ranking:`" not in rendered, rendered
    assert _LIB_FILE not in rendered, rendered


def test_a_piece_game_is_told_its_flavor_before_its_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A piece game cannot declare `ranking:`, so a library `Rank` parameter is
    refused for the flavor, and nothing asks for a ranking."""
    _with_libraries(monkeypatch, {_LIB: _RANK_PARAM_LIB})
    text = _game_text(_PIECES, uses=True, game_fn="", tag="PieceParam")
    refusal = _uses_line_refusal(text, _rendered(text))
    assert "pieces" in refusal and "`Rank`" in refusal, refusal
    assert "ranking:" not in (_rendered(text) or ""), _rendered(text)


def test_a_malformed_teams_clause_is_refused_at_the_clause_not_the_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _with_libraries(
        monkeypatch, {_LIB: f"library {_LIB} {{ function probe_fn() = any team where true }}"}
    )
    text = _game_text(_CARD, uses=True, game_fn="", tag="BadTeamsRange")
    text = text.replace("teams: [[0, 2], [1, 3]]", "teams: [[0, 2], [1]]")
    rendered = _rendered(text)
    assert rendered is not None and "seat 3" in rendered, rendered
    assert _LIB_FILE not in rendered and "probe_lib" not in rendered, rendered


def test_a_board_that_mints_no_cells_is_refused_at_the_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared board that fails is the `board:` clause's refusal; the
    library's `for each cell` is not blamed for the cells it never got."""
    _with_libraries(
        monkeypatch,
        {_LIB: f"library {_LIB} {{ procedure probe_fn() {{ for each cell c: let y = 1 }} }}"},
    )
    text = _game_text(
        replace(_BOARD, board_size=0), uses=True, game_fn="", tag="NoCells",
        statement="run probe_fn()",
    )
    rendered = _rendered(text)
    assert rendered is not None and "board family 'grid'" in rendered, rendered
    assert _LIB_FILE not in rendered and "probe_lib" not in rendered, rendered


# --- a piece game is never asked for a clause it cannot declare ---------------
#
# A piece game is refused `ranking:`, `trump:`, `card_points` and a Trick
# Order, so a refusal asking it for one offers a fix that cannot be applied.
# Every member of a gate on those clauses reaches a piece game's refusal
# through the content-flavor gate, which runs first.

_CARD_ONLY_CLAUSE_GATES = (
    "rank_parameter", "ranking_slot", "trick_order_reading", "trick_order_replaced"
)


def test_every_card_clause_builtin_is_deck_only() -> None:
    """The Builtin rows on a clause a piece game cannot declare are pre-empted
    in a piece game by the deck-only row, which runs first.

    red under: removing `card_points` from `DECK_ONLY_CALL_FUNCS` (executed
    2026-10-14)."""
    card_clause_builtins = (
        (RANKING_GATED_FUNCS & BUILTIN_CALL_FUNCS)
        | TRICK_ORDER_GATED_FUNCS
        | TRICK_ORDER_EXCLUDED_FUNCS
        | resolve_module._CARD_POINTS_CALLS
    )
    assert card_clause_builtins <= DECK_ONLY_CALL_FUNCS, sorted(
        card_clause_builtins - DECK_ONLY_CALL_FUNCS
    )


@pytest.mark.parametrize(
    "member",
    [pytest.param(m, id=m.id) for m in _node_members() if m.gate in _CARD_ONLY_CLAUSE_GATES],
)
def test_a_piece_game_is_told_its_flavor_not_a_card_clause(
    member: NodeMember, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A climbing query reaches no piece game through a library: the library
    is refused for the Primitive first and alone, and the game-written cells
    of `test_node_gate_cell` carry the flavor refusal for it.

    red under: deleting the `TrickRound` and `ClimbRound` arms of
    `typecheck.card_content_forms` (executed 2026-10-15: the winner members)."""
    text, rendered = _check_node(
        member, NodeGame(_PIECES), through_library=True,
        tag=f"Flavor{_node_tag(member.id)}", monkeypatch=monkeypatch,
    )
    if _library_alone(member):
        _assert_library_alone_refusal(member, text, rendered)
        return
    assert rendered is not None
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert any(
        line.startswith(where) and f"'{_LIB}'" in line and "played with pieces" in line
        for line in rendered.splitlines()
    ), rendered
    for clause in ("`ranking:`", "`trick_order { }`"):
        assert clause not in rendered, rendered


# --- every occurrence is named, however often a member recurs -----------------
#
# A gate's refusal names every definition that holds one of its members. A
# member written twice, in two definitions, is named in both, for a Builtin row
# and for a node row alike.


def _twice(definition: str) -> str:
    return definition + "\n  " + definition.replace("probe_fn", "probe_fn2", 1)


def _repeat_cases() -> list[object]:
    cases: list[object] = []
    for gate in GATES:
        if gate.name == "board_span":
            continue
        member = next(
            (m for m in sorted(gate.members & BUILTIN_CALL_FUNCS) if _probe(m).library_spellable),
            None,
        )
        if member is None:
            continue
        probe = _probe(member)
        requires = "requires { pile : TrickPile }" if probe.needs_pile else ""
        cases.append(
            pytest.param(
                f"library {_LIB} {{\n  {requires}\n  {_twice(_function(probe))}\n}}\n",
                _unmet(gate, member), None, member,
                id=f"builtin-{gate.name}-{member}",
            )
        )
    seen: set[str] = set()
    for node in _node_members():
        if node.gate not in NODE_GATES or node.gate in seen or node.definition == "state":
            continue
        seen.add(node.gate)
        requires = f"requires {{ {node.requires} }}" if node.requires else ""
        cases.append(
            pytest.param(
                f"library {_LIB} {{\n  {requires}\n  {_twice(node.definition)}\n}}\n",
                node.unmet.clauses, node.unmet, node.word,
                id=f"node-{node.id}",
            )
        )
    return cases


@pytest.mark.parametrize(("library", "clauses", "node_game", "word"), _repeat_cases())
def test_a_member_written_twice_is_named_in_both_definitions(
    library: str, clauses: Clauses, node_game: NodeGame | None, word: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """red under: claiming each member as the gate reaches it, rather than
    after the gate has collected every occurrence, in
    `resolve._check_library_clause_gates` (the Builtin cells); and claiming a
    node row's members by what the refusal calls them rather than by the
    node itself (the node cells) (both executed 2026-10-14)."""
    _with_libraries(monkeypatch, {_LIB: library})
    text = _game_text(clauses, uses=True, game_fn="", tag="Twice")
    if node_game is not None and node_game.trump:
        text = text.replace("  max_length: 1000", "  trump: hearts\n  max_length: 1000")
    rendered = _rendered(text)
    assert rendered is not None
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert any(
        line.startswith(where) and word in line
        and "`probe_fn`" in line and "`probe_fn2`" in line
        for line in rendered.splitlines()
    ), rendered
