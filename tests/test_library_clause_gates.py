"""A game missing a clause its library needs is told so on its own `uses` line.

PLACEHOLDER LEDGER
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import cardlang.resolve as resolve_module
from cardlang.builtins.functions import (
    BOARD_ONLY_CALL_FUNCS,
    BUILTIN_CALL_FUNCS,
    DECK_ONLY_CALL_FUNCS,
    PRIMITIVE_CLIMB_LEADS,
    TRICK_ORDER_EXCLUDED_FUNCS,
    TRICK_ORDER_EXCLUDED_WINNERS,
    TRICK_ORDER_GATED_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
)
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.typecheck import (
    RANKING_GATED_CLIMB_QUERIES,
    RANKING_GATED_FUNCS,
    RANKING_GATED_WINNERS,
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
    Gate("card_points", frozenset({"card_points"}), "card_points"),
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
    return replace(_CARD, trick_order=member in TRICK_ORDER_GATED_FUNCS)


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
                    cell = Cell(gate, member, met, through_library)
                    marks: list[pytest.MarkDecorator] = []
                    if through_library and not _probe(member).library_spellable:
                        marks.append(pytest.mark.skip(
                            reason="a family library declares no positions, so it "
                            "cannot spell this Builtin's cell or direction argument"
                        ))
                    elif through_library and not met:
                        marks.append(pytest.mark.xfail(
                            strict=True, raises=AssertionError,
                            reason="issue #847: refused inside the library file",
                        ))
                    params.append(pytest.param(cell, id=cell.id, marks=marks))
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

# The ranking-gated names a Trick Order replaces: beside a `trick_order { }`
# block each is refused in favour of the Trick Order winner, so naming that
# winner instead, under a block with a `card_strength:` row, also clears the
# ranking gate. For every other member, declaring `ranking:` is the one remedy.
_TRICK_ORDER_TWINS = (
    RANKING_GATED_FUNCS | RANKING_GATED_WINNERS | RANKING_GATED_CLIMB_QUERIES
) & (TRICK_ORDER_EXCLUDED_FUNCS | TRICK_ORDER_EXCLUDED_WINNERS)
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
    """A game naming `case.member` in its position. `twin` names the Trick
    Order winner in its place, under a block with a `card_strength:` row."""
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
        winner = _TRICK_ORDER_WINNER if twin else case.member
        return _game_text(
            clauses, uses=False, game_fn="", tag=tag, statement=_trick_round(winner)
        )
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
    [
        pytest.param(
            c, id=f"{c.position}-{c.member}",
            marks=(
                [] if c.member in _TRICK_ORDER_TWINS else
                [pytest.mark.xfail(
                    strict=True, raises=AssertionError,
                    reason="issue #484: offers a Trick Order remedy that cannot apply",
                )]
            ),
        )
        for c in _ranking_cases()
    ],
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
    refusal = _member_refusal(case, _rendered(_ranking_game(case, ranking=False)))
    assert _TRICK_ORDER_WINNER in refusal, refusal
    assert _rendered(_ranking_game(case, ranking=False, twin=True)) is None


# --- every definition kind a library holds reaches the gate the same way -----

_KIND_TEMPLATES: dict[str, str] = {
    "rules": (
        "rule probe_rule { constrains: play_to_trick "
        "demands: cards in hand where rank_value(card) > 0  if_impossible: hand }"
    ),
    "move_types": (
        "move_type probe_mv { when: (sum of rank_value(card) over cards in pile) > 0 "
        "effect { } }"
    ),
    "functions": "function probe_fn() = sum of rank_value(card) over cards in pile",
    "procedures": "procedure probe_pr() { let x = sum of rank_value(card) over cards in pile }",
}


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(field, marks=pytest.mark.xfail(
            strict=True, raises=AssertionError,
            reason="issue #847: refused inside the library file",
        ))
        for field, _ in resolve_module._LIBRARY_DEF_KINDS
    ],
)
def test_every_definition_kind_is_refused_on_the_uses_line(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = parse_library(
        f"library {_LIB} {{\n"
        "  requires { pile : TrickPile  hand[player] : Hand<player> }\n"
        f"  {_KIND_TEMPLATES[field]}\n}}\n",
        _LIB_FILE,
    )
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    text = _game_text(
        replace(_CARD, ranking=False), uses=True, game_fn="", tag=f"Kind{field.title()}"
    )
    rendered = _rendered(text)
    assert rendered is not None
    assert _LIB_FILE not in rendered, rendered
    where = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:"
    assert any(
        line.startswith(where) and "rank_value" in line and "ranking:" in line
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
    `resolve._library_slot_names` to `CALL_FUNCS`."""
    rendered = _library_alone_refusal(
        f"library {_LIB} {{ function probe_fn() = {member}() }}",
        _CARD,
        f"Prim{member.replace('_', '').title()}",
        monkeypatch,
    )
    assert any(
        line.startswith(_LIB_FILE) and f"'{member}'" in line
        and "nor a native function" in line
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
def test_a_library_cannot_name_a_clause_gated_round_slot(
    member: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gated winner or climbing query is named in a round, and a library
    holds a round only in a procedure, whose body may not hold one: the library
    is refused in its own file, whatever clauses the game declares.

    red under: deleting the procedure-body round refusal in
    `resolve._check_procedures`."""
    rendered = _library_alone_refusal(
        f"library {_LIB} {{\n"
        "  requires { pile : TrickPile  hand[player] : Hand<player> }\n"
        f"  procedure probe_pr() {{ {_SLOT_ROUNDS[member]} }}\n}}\n",
        replace(_CARD, ranking=False),
        f"Slot{member.replace('_', '').title()}",
        monkeypatch,
    )
    assert any(
        line.startswith(_LIB_FILE) and "contains a `round`" in line
        for line in rendered.splitlines()
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #847")
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #847")
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
