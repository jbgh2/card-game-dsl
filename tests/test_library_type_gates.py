"""A type-layer verdict on library text goes to the author who owns its fact.

A family library's text reaches the type checker spliced into the game, and
the splice marks it with its origin (the library, the definition holding it,
and the game's `uses` line). The type layer reads that mark wherever a
verdict reads a game clause:

- a seat or team number, or a rank or suit written as a string, is refused to
  the library's author in the library file, in every game -- a library names
  no seat, no team, no rank and no suit (decisions.md, "Family libraries");
- a card field the game's component set lacks is refused on the game's
  `uses` line, naming the library, the field and the game's content, like
  the card forms `resolve._CLAUSE_GATES` refuses there.

The same construct written by the game keeps the verdict it always had. A
numeric rank is spelled as a string wherever a rank is expected
(decisions.md, "Rank and suit values"), so a rank parameter -- the fix the
library refusal offers -- takes `"10"`, and the value it carries at play is
the card's own.

Completeness ledger
-------------------
property:        for every type-layer verdict that reads a game clause, library
                 text meets the verdict its owner is told: a library-alone
                 member is refused in the library file in every game and
                 never co-reported as the game's range or deck refusal; a
                 clause-decided member is refused on the `uses` line and
                 nowhere in the library file; game text keeps its own
                 verdict. Every remedy a refusal offers is applied and checks
                 clean, and the rank remedy plays.
domain:          the stamp's domain -- every definition kind of
                 `resolve._LIBRARY_DEF_KINDS` (a rule in each of its clause
                 slots, crossed with activation; a move type in its `when:`
                 and its effect) and a provided state default, plain and
                 indexed, plus a standard library rule a game activates --
                 crossed with each member: a seat number, a team number, a
                 rank string, a suit string, and a card field outside the
                 game's component set (a piece set, the piece sets sharing
                 one axis pair, and a deck); each crossed with {game-written,
                 library-reached} and {clause met, clause unmet}. Beside it,
                 every operand site of the choke point
                 (`typecheck._check_operand`, derived from its calls) placed
                 with each role it can carry -- seat, team, rank, suit -- or
                 held by the reason it carries none; each rank position
                 crossed with every spelling class over a short, a full and
                 the tarot deck, and the call position crossed with every
                 rank of every deck in `DECKS`; every numeric rank of every
                 deck passed as an argument and played. A rule no game
                 activates is checked against its library alone, which reads
                 names and not types, so its type-layer cells are clean in
                 every game: the cost PR #860 accepted, held for the standard
                 library by the pin that a corpus game activates each of its
                 rules. A seat or team number compared by `is` is issue
                 #803's, and one reaching a seat through an `if` branch, a
                 `let`, a function's result or arithmetic is issue #805's:
                 those cells are marked. Card-axis roles in a piece game are
                 issue #183's and a movement's noun is issue #170's; their
                 library cells are pinned in
                 tests/test_library_clause_gates.py.
registry:        stamp domain: `resolve._LIBRARY_DEF_KINDS`, `n.Library.state`;
                 the stamp: `n.LibraryOrigin`; clause fields and their
                 readers: `typecheck.TYPE_ENV_FIELD_SOURCES`,
                 `typecheck.CLAUSE_READS`, both pinned against an `ast` scan
                 of cardlang/typecheck.py; operand sites: the `_check_operand`
                 calls in cardlang/typecheck.py; decks: `runtime.values.DECKS`,
                 ranks `stdlib.enums.rank_names`; the uses-line clause gates
                 and their library cells:
                 tests/test_library_clause_gates.py::test_node_gate_cell; the
                 activation pin:
                 tests/test_play_source_grid.py::test_every_stdlib_rule_is_activated_by_some_corpus_game.
does not prove:  that a Primitive's rank argument plays as the card's own
                 value: its argument takes the same choke point as a user
                 function's, and the cell that executes is the user
                 function's. Nor that every operand site was crossed with
                 every deck: only the call position is, and the other sites
                 meet the decks only through the shared literal check.
"""

from __future__ import annotations

import ast
import random
from collections import Counter
from dataclasses import dataclass, fields
from pathlib import Path

import pytest

import cardlang.resolve as resolve_module
import cardlang.typecheck as typecheck_module
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.ast import nodes as n
from cardlang.runtime.values import COMPONENT_SETS, DECKS, build_deck
from cardlang.stdlib.enums import rank_names, suit_names

_LIB = "probe_lib"
_LIB_FILE = f"docs/libraries/{_LIB}.cardlang"
_GAME_FILE = "probe.cardlang"
_STDLIB_FILE = "cardlang/stdlib/rules.cardlang"
_TYPECHECK_PATH = Path(typecheck_module.__file__)
_TYPECHECK_SOURCE = _TYPECHECK_PATH.read_text()
_TYPECHECK_TREE = ast.parse(_TYPECHECK_SOURCE)

_EQUALITY = "issue #803: a seat or team number compared by `is` is not ranged"
_FORWARDED = (
    "issue #805: a seat or team number reaching its position through another "
    "expression's value is not ranged"
)

# A `ranking:` per deck a probe game uses, so a trick round can name its winner.
_RANKINGS = {"standard52": "aces high", "kuhn3": "K Q J"}


# --- the game a cell checks ----------------------------------------------------


@dataclass(frozen=True)
class Table:
    """The game clauses a cell toggles: the seat count, the number of teams
    (no `teams:` clause when 0) and the component set (a deck of `DECKS`, or
    a piece set)."""

    players: int = 4
    teams: int = 0
    deck: str = "standard52"

    @property
    def pieces(self) -> bool:
        return COMPONENT_SETS[self.deck].flavor == "piece"


def _teams_clause(table: Table) -> str:
    if not table.teams:
        return ""
    sides = [list(range(t, table.players, table.teams)) for t in range(table.teams)]
    return "teams: [" + ", ".join("[" + ", ".join(map(str, s)) + "]" for s in sides) + "]"


def _game(
    table: Table,
    *,
    tag: str,
    uses: bool,
    state: str = "",
    statement: str = "",
    definitions: str = "",
) -> str:
    if table.pieces:
        content = f"pieces: {table.deck}"
        zones = "box : Deck  reserve[player] : PlayerPile<player>  pile : TrickPile"
        ranking = ""
    else:
        content = f"cards: {table.deck}"
        zones = "deck : Deck  hand[player] : Hand<player>  pile : TrickPile"
        ranking = f"ranking: {_RANKINGS[table.deck]}" if table.deck in _RANKINGS else ""
    lines = [
        f"game Probe{tag} {{",
        f"  players: {table.players}",
        f"  {_teams_clause(table)}",
        "  max_length: 1000",
        f"  {content}",
        f"  {ranking}",
        f"  uses {_LIB}" if uses else "",
        f"  zones {{ {zones} }}",
        f"  state {{ score[player] : Integer = 0  {state} }}",
        "  phase p {",
        "    for each player q: score[q] := 0",
        f"    {statement}",
        f"    {'' if uses else _used(definitions)}",
        "  }",
        "  winner: highest score",
        "}",
        definitions,
    ]
    return "\n".join(lines) + "\n"


def _used(definitions: str) -> str:
    """The statements a game needs so its own probe definitions are used: a
    game's move type must be offered and its procedure run, or the game is
    refused for the dead definition rather than for the construct."""
    used = []
    if "move_type probe_mv" in definitions:
        used.append("offer to 0 one of [probe_mv]")
    if "procedure probe_pr()" in definitions:
        used.append("run probe_pr()")
    return "\n    ".join(used)


def _rendered(text: str) -> str | None:
    try:
        check_dsl(text, _GAME_FILE)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None)
        return "\n".join(notes) if notes else exc.diagnostic.format()
    return None


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not in the probe game")


def _with_library(monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    library = parse_library(f"library {_LIB} {{\n{body}\n}}\n", _LIB_FILE)
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: library)


def _tag(*parts: object) -> str:
    return "".join(
        "".join(ch for ch in str(p).title() if ch.isalnum()) for p in parts
    )


# --- the verdicts, in the words each owner is told ---------------------------


@dataclass(frozen=True)
class Verdict:
    """What a cell expects: refused in the library file with every phrase of
    `library`, refused on the `uses` line with every phrase of `uses_line`,
    refused in the game file with every phrase of `game`, or clean (all three
    empty). Nothing else is reported in a file the verdict does not name."""

    library: tuple[str, ...] = ()
    uses_line: tuple[str, ...] = ()
    game: tuple[str, ...] = ()


_CLEAN = Verdict()


def _assert_verdict(text: str, rendered: str | None, verdict: Verdict) -> None:
    if verdict == _CLEAN:
        assert rendered is None, rendered
        return
    assert rendered is not None, "accepted"
    # The refusals, without the warning an unproven library's adds.
    lines = [ln for ln in rendered.splitlines() if ": warning: " not in ln]
    uses = f"{_GAME_FILE}:{_line_of(text, f'uses {_LIB}')}:" if f"uses {_LIB}" in text else None
    in_library = [ln for ln in lines if ln.startswith(_LIB_FILE) or ln.startswith(_STDLIB_FILE)]
    on_uses = [ln for ln in lines if uses is not None and ln.startswith(uses)]
    in_game = [
        ln for ln in lines
        if ln.startswith(_GAME_FILE) and (uses is None or not ln.startswith(uses))
    ]
    for phrases, found, where in (
        (verdict.library, in_library, "the library file"),
        (verdict.uses_line, on_uses, "the `uses` line"),
        (verdict.game, in_game, "the game file"),
    ):
        if phrases:
            assert any(all(p in ln for p in phrases) for ln in found), (
                f"expected {phrases} in {where}:\n{rendered}"
            )
        else:
            assert not found, f"nothing expected in {where}:\n{rendered}"


def _seat_refusal(value: int, provided: str | None = None) -> tuple[str, ...]:
    head = (f"library '{_LIB}' names seat {value}", "a library names no seat")
    if provided is not None:
        return head + (f"declare `{provided}` in `requires {{ }}` instead of `state {{ }}`",)
    return head + ("add `dealer : Player` to `requires { }`",)


def _team_refusal(value: int, provided: str | None = None) -> tuple[str, ...]:
    head = (f"library '{_LIB}' names team {value}", "a library names no team")
    if provided is not None:
        return head + (f"declare `{provided}` in `requires {{ }}` instead of `state {{ }}`",)
    return head + ("add `side : Team` to `requires { }`",)


def _enum_refusal(enum: str, value: str, provided: str | None = None) -> tuple[str, ...]:
    noun = enum.lower()
    head = (f'library \'{_LIB}\' names the {noun} "{value}"', f"a library names no {noun}")
    if provided is not None:
        return head + (f"declare `{provided}` in `requires {{ }}` instead of `state {{ }}`",)
    return head + (f"take the {noun} as a parameter",)


def _field_refusal(field: str, table: Table) -> tuple[str, ...]:
    if table.pieces:
        return (f"library '{_LIB}' reads the field `{field}`", "this game is played with pieces")
    return (f"library '{_LIB}' reads the field `{field}`", "this game's cards have the fields")


# --- the members, and the definition kinds that hold them --------------------


@dataclass(frozen=True)
class Member:
    """One construct a type-layer gate decides by a game clause.

    `pred` is a Boolean predicate holding it, for the definition kinds (`card`
    is bound where a rule's clause binds it, and `c` where `params` declares
    it); `default` a state declaration holding it, `{x}` its variable; `state`
    the state it reads, provided by the library or declared by the game;
    `requires` the contract rows the library form needs (the game declares
    them in its own zones). `met` and `unmet` are the games that pass and fail
    the gate's clause (`met` None: no game passes it). `kinds` names the
    definition kinds that cannot hold the construct, each with the reason."""

    name: str
    pred: str
    params: str
    default: str | None
    state: str
    requires: str
    met: Table | None
    unmet: Table
    library_verdict: str  # "library" | "uses_line"
    game_refusal: tuple[str, ...]
    library_words: tuple[str, ...]
    provided_words: tuple[str, ...]
    unheld: dict[str, str]


_FOUR = Table()
_TWO = Table(players=2)
_SIX_IN_THREE = Table(players=6, teams=3)
_FOUR_IN_TWO = Table(players=4, teams=2)
_KUHN = Table(players=2, deck="kuhn3")
_BREAKTHROUGH = Table(players=2, deck="breakthrough_men")

_PARAM_FREE = "the construct reads a card parameter, and this kind declares none"
_NO_CARD_DEFAULT = "a state default holds no card to read a field of"
_PIECE_CARD_FORM = (
    "a card form in a piece game is refused on the `uses` line first "
    "(`resolve._CLAUSE_GATES`, tests/test_library_clause_gates.py::test_node_gate_cell)"
)

_MEMBERS: tuple[Member, ...] = (
    Member(
        "seat", "(number of cards in hand[3]) > 0", "", "{x} : Player = 3", "",
        "hand[player] : Hand<player>", _FOUR, _TWO, "library",
        ("seat 3 is out of range",), _seat_refusal(3), _seat_refusal(3, "{x}"), {},
    ),
    Member(
        "team", "tally[2] > 0", "", "{x} : Team = 2", "tally[team] : Integer = 0", "",
        _SIX_IN_THREE, _FOUR_IN_TWO, "library",
        ("team 2 is out of range",), _team_refusal(2), _team_refusal(2, "{x}"), {},
    ),
    Member(
        "rank_string", 'any card in pile where card.rank is "10"', "",
        '{x} : Rank? = "10"', "", "pile : TrickPile", _FOUR, _KUHN, "library",
        ('"10" is not a Rank value of this deck',), _enum_refusal("Rank", "10"),
        _enum_refusal("Rank", "10", "{x}"), {},
    ),
    Member(
        "suit_string", 'any card in pile where card.suit is "hearts"', "",
        '{x} : Suit? = "hearts"', "", "pile : TrickPile", None, _FOUR, "library",
        ("write the Suit value bare",), _enum_refusal("Suit", "hearts"),
        _enum_refusal("Suit", "hearts", "{x}"), {},
    ),
    Member(
        "card_field_pieces", "c.suit is c.suit", "(c : Card)", None, "", "",
        _FOUR, _BREAKTHROUGH, "uses_line",
        ("Piece has no field 'suit'",), _field_refusal("suit", _BREAKTHROUGH), (),
        {
            "move_types": "a `Card` parameter on a move type in a piece game is "
            "refused on the `uses` line first (`resolve._CLAUSE_GATES`)",
            "procedures": "a procedure's parameters are seats (resolve refuses "
            "any other domain)",
            "rules": _PIECE_CARD_FORM,
            "state": _NO_CARD_DEFAULT,
        },
    ),
    Member(
        "card_field_deck", "any card in pile where card.color is card.color", "", None, "",
        "pile : TrickPile", None, _FOUR, "uses_line",
        ("Card has no field 'color'",), _field_refusal("color", _FOUR), (),
        {"state": _NO_CARD_DEFAULT},
    ),
)

# A definition kind's slot: (kind, slot, the text holding `{pred}` and `{params}`).
# `rules` is a rule's clause slots; a move type is crossed in its guard and its
# effect; `state` is a provided declaration, plain and indexed.
_RULE_SLOTS: dict[str, str] = {
    "applies_when": (
        "rule probe_rule {{ constrains: play_to_trick  applies_when: {pred}  "
        "demands: cards in hand where true  if_impossible: hand }}"
    ),
    "demands": (
        "rule probe_rule {{ constrains: play_to_trick  "
        "demands: cards in hand where {pred}  if_impossible: hand }}"
    ),
    "if_impossible": (
        "rule probe_rule {{ constrains: play_to_trick  demands: cards in hand where true  "
        "if_impossible: cards in hand where {pred} }}"
    ),
    "exempts": (
        "rule probe_rule {{ constrains: play_to_trick  demands: cards in hand where true  "
        "if_impossible: hand  exempts: cards in hand where {pred} }}"
    ),
}
_KIND_SLOTS: dict[str, dict[str, str]] = {
    "rules": _RULE_SLOTS,
    "move_types": {
        "when": "move_type probe_mv{params} {{ when: {pred}  effect {{ }} }}",
        "effect": "move_type probe_mv{params} {{ effect {{ let x = {pred} }} }}",
    },
    "functions": {"body": "function probe_fn{params} = {pred}"},
    "procedures": {"body": "procedure probe_pr() {{ let x = {pred} }}"},
    "state": {"plain": "", "indexed": ""},
}
_ROUND = (
    "round play_to_trick from 0 over all players source hand into pile "
    "winner highest_of_led_suit"
)


def test_the_kind_axis_is_the_stamp_domain() -> None:
    """Every definition kind a library holds is a row, plus its provided state."""
    kinds = {field for field, _ in resolve_module._LIBRARY_DEF_KINDS}
    assert set(_KIND_SLOTS) == kinds | {"state"}
    assert "state" in {f.name for f in fields(n.Library)}


@dataclass(frozen=True)
class KindCell:
    member: Member
    kind: str
    slot: str
    met: bool
    through_library: bool
    activated: bool = True

    @property
    def id(self) -> str:
        return "-".join(
            [
                self.member.name, self.kind, self.slot,
                "met" if self.met else "unmet",
                "library" if self.through_library else "game",
            ]
            + ([] if self.activated else ["not_activated"])
        )


def _definition(cell: KindCell) -> str:
    member = cell.member
    params = member.params if cell.kind in ("functions", "move_types") else ""
    if cell.kind == "functions" and not params:
        params = "()"
    if cell.kind == "rules" and member.params:
        raise AssertionError("a rule holds no parameter")
    return _KIND_SLOTS[cell.kind][cell.slot].format(pred=member.pred, params=params)


def _kind_cells() -> list[object]:
    params: list[object] = []
    for member in _MEMBERS:
        for kind, slots in _KIND_SLOTS.items():
            if kind in member.unheld:
                continue
            if kind == "state" and member.default is None:
                raise AssertionError(f"{member.name}: no default and no reason")
            for slot in slots:
                for met in (True, False):
                    if met and member.met is None:
                        continue
                    for through_library in (False, True):
                        for activated in (True, False) if kind == "rules" else (True,):
                            cell = KindCell(member, kind, slot, met, through_library, activated)
                            params.append(pytest.param(cell, id=cell.id))
    return params


def test_the_piece_sets_share_one_axis_pair() -> None:
    """The piece-set axis of the card-field member is one cell because every
    piece set in the registry names the same two fields; a set naming others
    is a new member. red under: registering `xo_marks` with the axes `side`
    and `mark` (executed 2026-10-15)."""
    axes = {cs.axes for cs in COMPONENT_SETS.values() if cs.flavor == "piece"}
    assert axes == {("side", "kind")}


def test_every_member_is_held_by_every_kind_or_names_why() -> None:
    for member in _MEMBERS:
        assert set(member.unheld) <= set(_KIND_SLOTS), member.name
        for reason in member.unheld.values():
            assert reason


def _kind_expected(cell: KindCell) -> Verdict:
    member = cell.member
    table = member.met if cell.met else member.unmet
    assert table is not None
    if not cell.through_library:
        # A game's own rule is checked whether or not it is activated.
        return _CLEAN if cell.met else Verdict(game=member.game_refusal)
    if cell.kind == "rules" and not cell.activated:
        return _CLEAN  # checked against its library alone, which reads names
    if member.library_verdict == "library":
        words = member.provided_words if cell.kind == "state" else member.library_words
        return Verdict(library=tuple(w.replace("{x}", "probe_x") for w in words))
    return _CLEAN if cell.met else Verdict(uses_line=member.library_words)


@pytest.mark.parametrize("cell", _kind_cells())
def test_kind_cell(cell: KindCell, monkeypatch: pytest.MonkeyPatch) -> None:
    member = cell.member
    table = member.met if cell.met else member.unmet
    assert table is not None
    tag = _tag("Kind", cell.id)
    state = member.state
    if cell.kind == "state":
        assert member.default is not None
        default = member.default.replace("{x}", "probe_x")
        if cell.slot == "indexed":
            default = default.replace("probe_x :", "probe_x[player] :")
        state = f"{state}  {default}"
        definition = ""
    else:
        definition = _definition(cell)
    statement = ""
    if cell.kind == "rules":
        activate = "active_rules: [probe_rule]\n    " if cell.activated else ""
        statement = f"{activate}{_ROUND}"
    if cell.through_library:
        provided = f"state {{ {state} }}" if state.strip() else ""
        requires = f"requires {{ {member.requires} }}" if member.requires else ""
        _with_library(monkeypatch, f"{requires}\n{provided}\n{definition}")
        text = _game(table, tag=tag, uses=True, statement=statement)
    else:
        text = _game(table, tag=tag, uses=False, state=state, statement=statement, definitions=definition)
    _assert_verdict(text, _rendered(text), _kind_expected(cell))


# --- the operand sites, and the roles each carries ---------------------------


def _enclosing_functions() -> dict[ast.AST, str]:
    owner: dict[ast.AST, str] = {}
    for top in ast.walk(_TYPECHECK_TREE):
        if isinstance(top, ast.FunctionDef):
            for node in ast.walk(top):
                owner.setdefault(node, top.name)
    return owner


def _operand_sites() -> list[tuple[str, str, int]]:
    """(enclosing function, `expected` argument as written, its ordinal among
    the same pair) for every `_check_operand(...)` call in typecheck.py, in
    source order."""
    owner = _enclosing_functions()
    calls = sorted(
        (
            node for node in ast.walk(_TYPECHECK_TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_check_operand"
        ),
        key=lambda c: (c.lineno, c.col_offset),
    )
    seen: Counter[tuple[str, str]] = Counter()
    sites: list[tuple[str, str, int]] = []
    for call in calls:
        expected = ast.get_source_segment(_TYPECHECK_SOURCE, call.args[2]) or "?"
        key = (owner.get(call, "<module>"), expected)
        sites.append((key[0], key[1], seen[key]))
        seen[key] += 1
    return sites


@dataclass(frozen=True)
class Placement:
    """A sentence putting `{v}` at one operand site, for one role. `state` is
    what the sentence reads or writes (the library provides it, the game
    declares it); `requires` the rows the library form needs. `forms` the
    definitions holding it, in library or game text alike."""

    role: str  # "Player" | "Team" | "Rank" | "Suit"
    forms: str
    state: str = ""
    requires: str = ""
    # A trick round names a winner that reads `ranking:`, which only a deck of
    # `_RANKINGS` declares here (tarot78 cannot: no `ranking:` serves it).
    needs_ranking: bool = False


_HAND = "hand[player] : Hand<player>"
_PILE = "pile : TrickPile"
_HAND_PILE = f"{_HAND}  {_PILE}"

# Every operand site of the choke point: the placements of the roles it can
# carry, or the reason it carries none of them.
_SITES: dict[tuple[str, str, int], tuple[Placement, ...] | str] = {
    ("_check_card_source", "_UNKEYED_COLLECTION", 0): "expects a card collection",
    ("_check_subset_query", "TInteger()", 0): "expects an Integer",
    ("_domain_query_binder_type", "want", 0): "expects a line or a collection of lines",
    ("_check_round_actors", "TPlayer()", 0): (
        Placement(
            "Player",
            "move_type probe_mv { effect { round play_to_trick from {v} over all "
            "players source hand into pile winner highest_of_led_suit } }",
            requires=_HAND_PILE,
        ),
    ),
    ("_check_round_trump", 'TOptional(TEnum("Suit"))', 0): (
        Placement(
            "Suit",
            "move_type probe_mv { effect { round play_to_trick from actor over all "
            "players source hand into pile winner highest_trump_or_led_suit trump {v} } }",
            requires=_HAND_PILE, needs_ranking=True,
        ),
    ),
    ("_check_if_impossible", "_UNKEYED_COLLECTION", 0): "expects a card collection",
    ("_check_state_default_type", "declared", 0): (
        Placement("Player", "", state="probe_x : Player = {v}"),
        Placement("Team", "", state="probe_x : Team = {v}"),
        Placement("Rank", "", state="probe_x : Rank? = {v}"),
        Placement("Suit", "", state="probe_x : Suit? = {v}"),
    ),
    ("_check_is_check", "_UNKEYED_COLLECTION", 0): "expects a collection",
    ("_check_participants", "TCollection(TPlayer())", 0): (
        "expects a collection of seats; a seat number in it is the element site"
    ),
    ("_check_assign", "target.key", 0): (
        Placement(
            "Player", "procedure probe_pr() { probe_t[{v}] := 1 }",
            state="probe_t[player] : Integer = 0",
        ),
        Placement(
            "Team", "procedure probe_pr() { probe_t[{v}] := 1 }",
            state="probe_t[team] : Integer = 0",
        ),
    ),
    ("_check_assign", "TInteger()", 0): "`+=` and `-=` expect an Integer",
    ("_check_assign", "target", 0): (
        Placement("Player", "procedure probe_pr() { probe_x := {v} }", state="probe_x : Player? = none"),
        Placement("Team", "procedure probe_pr() { probe_x := {v} }", state="probe_x : Team? = none"),
        Placement("Rank", "procedure probe_pr() { probe_x := {v} }", state="probe_x : Rank? = none"),
        Placement("Suit", "procedure probe_pr() { probe_x := {v} }", state="probe_x : Suit? = none"),
    ),
    ("_check_transfer", "TInteger()", 0): "expects an Integer count",
    ("_check_produce_stmt", "expected", 0): (
        "a `produce` stands only in an outcome phase's body, which a library cannot hold"
    ),
    ("typecheck", "TPlayer()", 0): "the `loser:` clause, which a library cannot hold",
    ("_check_trick_order", "expected", 0): (
        "a `trick_order { }` row, which a library cannot hold"
    ),
    ("_check_participants", "TPlayer()", 0): (
        Placement(
            "Player",
            "move_type probe_mv { effect { round play_to_trick from actor over "
            "[{v}, actor] source hand into pile winner highest_of_led_suit } }",
            requires=_HAND_PILE,
        ),
    ),
    ("_check_expr", "TPlayer()", 0): (
        Placement("Player", "function probe_fn() = the first player from {v} where true"),
    ),
    ("_check_stmt_semantics", "TPlayer()", 0): (
        Placement(
            "Player",
            "move_type probe_mv { effect { as {v} { probe_t[actor] := 1 } } }",
            state="probe_t[player] : Integer = 0",
        ),
    ),
    ("_check_stmt_semantics", "TPlayer()", 1): (
        Placement(
            "Player",
            "move_type probe_ok { effect { } } procedure probe_pr() { turns t from {v} "
            "over all players until true { offer to t one of [probe_ok] } }",
        ),
    ),
    ("_check_stmt_semantics", "TPlayer()", 2): (
        Placement(
            "Player",
            "move_type probe_ok { effect { } } procedure probe_pr() { offer to {v} one of [probe_ok] }",
        ),
    ),
    ("_check_stmt_exprs", "param", 0): (
        Placement(
            "Player",
            "procedure probe_pr(p : Player) { probe_t[p] := 1 } "
            "move_type probe_mv { effect { run probe_pr({v}) } }",
            state="probe_t[player] : Integer = 0",
        ),
    ),
    ("_check_expr", "param", 0): (
        Placement("Player", "function probe_f(p : Player) = 1  function probe_fn() = probe_f({v})"),
        Placement("Team", "function probe_f(t : Team) = 1  function probe_fn() = probe_f({v})"),
        Placement("Rank", "function probe_f(r : Rank) = 1  function probe_fn() = probe_f({v})"),
        Placement("Suit", "function probe_f(s : Suit) = 1  function probe_fn() = probe_f({v})"),
    ),
    ("_check_expr", "family", 0): (
        Placement("Player", "function probe_fn() = number of cards in hand[{v}]", requires=_HAND),
    ),
    ("_check_expr", "obj.key", 0): (
        Placement("Player", "function probe_fn() = probe_t[{v}]", state="probe_t[player] : Integer = 0"),
        Placement("Team", "function probe_fn() = probe_t[{v}]", state="probe_t[team] : Integer = 0"),
    ),
    ("_check_expr", "TInteger()", 0): "expects an Integer",
}


def test_every_operand_site_is_placed_or_names_why() -> None:
    """red under: adding a `_check_operand(...)` call anywhere in
    cardlang/typecheck.py, which this table then lacks (executed 2026-10-15)."""
    assert set(_SITES) == set(_operand_sites())


def _placements() -> list[tuple[tuple[str, str, int], Placement]]:
    return [
        (site, placement)
        for site, held in sorted(_SITES.items())
        if not isinstance(held, str)
        for placement in held
    ]


def _site_id(site: tuple[str, str, int]) -> str:
    function, expected, ordinal = site
    return f"{function.strip('_')}:{expected}:{ordinal}"


def _place(
    placement: Placement, value: str, table: Table, *, through_library: bool, tag: str,
    monkeypatch: pytest.MonkeyPatch, extra_state: str = "", statement: str = "",
) -> str:
    forms = placement.forms.replace("{v}", value)
    state = placement.state.replace("{v}", value)
    if through_library:
        provided = f"state {{ {state} }}" if state else ""
        requires = f"requires {{ {placement.requires} }}" if placement.requires else ""
        _with_library(monkeypatch, f"{requires}\n{provided}\n{forms}")
        return _game(table, tag=tag, uses=True, state=extra_state, statement=statement)
    return _game(
        table, tag=tag, uses=False, state=f"{state}  {extra_state}",
        definitions=forms, statement=statement,
    )


# --- seats and teams at every operand site -----------------------------------

# (the number, the game where it is a real seat or team, the game where it is not)
_ROLE_TABLES: dict[str, tuple[int, Table, Table]] = {
    "Player": (3, _FOUR, _TWO),
    "Team": (2, _SIX_IN_THREE, _FOUR_IN_TWO),
}


def _role_cells() -> list[object]:
    params: list[object] = []
    for site, placement in _placements():
        if placement.role not in _ROLE_TABLES:
            continue
        for met in (True, False):
            for through_library in (False, True):
                cell_id = (
                    f"{_site_id(site)}-{placement.role}-{'met' if met else 'unmet'}-"
                    f"{'library' if through_library else 'game'}"
                )
                params.append(pytest.param(site, placement, met, through_library, id=cell_id))
    return params


@pytest.mark.parametrize(("site", "placement", "met", "through_library"), _role_cells())
def test_role_number_cell(
    site: tuple[str, str, int], placement: Placement, met: bool, through_library: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, met_table, unmet_table = _ROLE_TABLES[placement.role]
    table = met_table if met else unmet_table
    text = _place(
        placement, str(value), table, through_library=through_library,
        tag=_tag("Role", _site_id(site), placement.role, met, through_library),
        monkeypatch=monkeypatch,
    )
    provided = "probe_x" if site[0] == "_check_state_default_type" else None
    if through_library:
        words = (
            _seat_refusal(value, provided) if placement.role == "Player"
            else _team_refusal(value, provided)
        )
        expected = Verdict(library=words)
    elif met:
        expected = _CLEAN
    else:
        noun = "seat" if placement.role == "Player" else "team"
        expected = Verdict(game=(f"{noun} {value} is out of range",))
    _assert_verdict(text, _rendered(text), expected)


def test_seat_zero_is_a_seat_a_library_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first seat is a seat: a library names none of them."""
    _with_library(monkeypatch, f"requires {{ {_HAND} }}\nfunction probe_fn() = number of cards in hand[0]")
    text = _game(_FOUR, tag="SeatZero", uses=True)
    _assert_verdict(text, _rendered(text), Verdict(library=_seat_refusal(0)))


def test_an_integer_that_is_not_a_seat_stays_legal(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_library(
        monkeypatch,
        f"requires {{ {_HAND} }}\n"
        "state { probe_t[player] : Integer = 0 }\n"
        "function probe_fn(p : Player) = (number of cards in hand[p]) + 1\n"
        "procedure probe_pr(p : Player) { probe_t[p] += 2 }",
    )
    text = _game(_FOUR, tag="PlainInteger", uses=True)
    assert _rendered(text) is None


# The positions the choke point does not reach, which issues #803 and #805 hold
# for games and libraries alike.
_UNREACHED: dict[str, tuple[str, str]] = {
    "equality": ("move_type probe_mv { when: actor is 3  effect { } }", _EQUALITY),
    "if_branch": (
        "state { probe_x : Player? = none }\n"
        "procedure probe_pr() { probe_x := if true then 3 else none }",
        _FORWARDED,
    ),
    "let": (
        f"requires {{ {_HAND} }}\n"
        "move_type probe_mv { effect { let s = 3\n let n = number of cards in hand[s] } }",
        _FORWARDED,
    ),
    "function_result": (
        f"requires {{ {_HAND} }}\n"
        "function probe_s() = 3  function probe_fn() = number of cards in hand[probe_s()]",
        _FORWARDED,
    ),
    "arithmetic": (
        f"requires {{ {_HAND} }}\nfunction probe_fn() = number of cards in hand[1 + 2]",
        _FORWARDED,
    ),
}


@pytest.mark.parametrize(
    "form",
    [
        pytest.param(
            name, id=name,
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason),
        )
        for name, (_, reason) in sorted(_UNREACHED.items())
    ],
)
def test_an_unreached_seat_position_is_refused(form: str, monkeypatch: pytest.MonkeyPatch) -> None:
    body, _ = _UNREACHED[form]
    _with_library(monkeypatch, body)
    text = _game(_FOUR, tag=_tag("Unreached", form), uses=True)
    rendered = _rendered(text)
    assert rendered is not None and "a library names no seat" in rendered, rendered


# --- ranks and suits at every operand site, every spelling -------------------


@dataclass(frozen=True)
class Spelling:
    """One way to write a value where a rank or suit is expected: `text`, and
    the deck values it names (`value`; None when it names none)."""

    name: str
    text: str
    value: str | None
    string: bool


def _spellings(enum: str, deck: str) -> list[Spelling]:
    if enum == "Rank":
        out = [
            Spelling("numeric_string", '"10"', "10", True),
            Spelling("numeric_bare", "10", None, False),
            Spelling("name_string", '"Q"', "Q", True),
            Spelling("name_bare", "Q", "Q", False),
            Spelling("absent_string", '"11"', "11", True),
        ]
        if deck == "tarot78":
            out += [
                Spelling("atout_string", '"21"', "21", True),
                Spelling("atout_bare", "21", None, False),
            ]
        return out
    return [
        Spelling("suit_string", '"spades"', "spades", True),
        Spelling("suit_bare", "spades", "spades", False),
    ]


def _deck_values(enum: str, deck: str) -> frozenset[str]:
    return rank_names(deck) if enum == "Rank" else suit_names(deck)


_ENUM_DECKS = ("standard52", "kuhn3", "tarot78")


def _enum_expected(
    enum: str, spelling: Spelling, deck: str, *, through_library: bool, provided: bool,
) -> Verdict:
    """The verdict a rank or suit spelling meets, from the spelling rule alone:
    a numeric value the deck holds is written as a string; a name-form value
    is written bare; a value the deck lacks is no value; a bare number is an
    Integer. A library writes none of them as a string, and none bare, since
    a bare name is a deck value it cannot read."""
    values = _deck_values(enum, deck)
    if through_library:
        if spelling.string:
            assert spelling.value is not None
            return Verdict(library=_enum_refusal(enum, spelling.value, "probe_x" if provided else None))
        if spelling.value is not None:
            return Verdict(library=(f"reads '{spelling.value}'",))  # the deck-agnostic name sweep
        return Verdict(library=("a library names no rank; take the rank as a parameter",))
    if spelling.string:
        assert spelling.value is not None
        if spelling.value not in values:
            return Verdict(game=(f'"{spelling.value}" is not a {enum} value of this deck',))
        if not spelling.value.isdigit():
            return Verdict(game=(f"write the {enum} value bare",))
        return _CLEAN
    if spelling.value is None:
        return Verdict(game=("numeric ranks are written as strings",))
    if spelling.value not in values:
        return Verdict(game=(f"'{spelling.value}'",))
    return _CLEAN


def _enum_cells() -> list[object]:
    params: list[object] = []
    for site, placement in _placements():
        if placement.role not in ("Rank", "Suit"):
            continue
        for deck in _ENUM_DECKS:
            if placement.needs_ranking and deck not in _RANKINGS:
                continue
            for spelling in _spellings(placement.role, deck):
                for through_library in (False, True):
                    cell_id = (
                        f"{_site_id(site)}-{placement.role}-{deck}-{spelling.name}-"
                        f"{'library' if through_library else 'game'}"
                    )
                    params.append(pytest.param(
                        site, placement, deck, spelling, through_library, id=cell_id,
                    ))
    return params


@pytest.mark.parametrize(
    ("site", "placement", "deck", "spelling", "through_library"), _enum_cells()
)
def test_enum_spelling_cell(
    site: tuple[str, str, int], placement: Placement, deck: str, spelling: Spelling,
    through_library: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    players = 2 if deck == "kuhn3" else 4
    table = Table(players=players, deck=deck)
    text = _place(
        placement, spelling.text, table, through_library=through_library,
        tag=_tag("Enum", _site_id(site), placement.role, deck, spelling.name, through_library),
        monkeypatch=monkeypatch,
    )
    provided = site[0] == "_check_state_default_type"
    expected = _enum_expected(
        placement.role, spelling, deck, through_library=through_library, provided=provided,
    )
    _assert_verdict(text, _rendered(text), expected)


def _rank_cells() -> list[object]:
    params: list[object] = []
    for deck in sorted(DECKS):
        for rank in sorted(rank_names(deck)):
            for string in (True, False):
                if not string and not rank.isdigit() and not rank.isidentifier():
                    continue
                params.append(pytest.param(
                    deck, rank, string, id=f"{deck}-{rank}-{'string' if string else 'bare'}",
                ))
    return params


@pytest.mark.parametrize(("deck", "rank", "string"), _rank_cells())
def test_every_rank_of_every_deck_as_an_argument(deck: str, rank: str, string: bool) -> None:
    """A game passes each rank of its deck to its own `Rank` parameter: a
    numeric rank as a string, a name-form rank bare."""
    players = 2 if len(build_deck(deck)) < 8 else 4
    spelled = f'"{rank}"' if string else rank
    text = _game(
        Table(players=players, deck=deck), tag=_tag("EveryRank", deck, rank, string), uses=False,
        definitions=f"function probe_f(r : Rank) = 1  function probe_fn() = probe_f({spelled})",
    )
    rendered = _rendered(text)
    if string == rank.isdigit():
        assert rendered is None, rendered
    elif string:
        assert rendered is not None and "write the Rank value bare" in rendered, rendered
    else:
        assert rendered is not None and "numeric ranks are written as strings" in rendered, rendered


# --- the rank argument at play ------------------------------------------------


def _numeric_ranks() -> list[object]:
    return [
        pytest.param(deck, rank, id=f"{deck}-{rank}")
        for deck in sorted(DECKS)
        for rank in sorted(rank_names(deck), key=lambda r: (len(r), r))
        if rank.isdigit()
    ]


def _counting_game(deck: str, spelled: str, *, through_library: bool, tag: str) -> str:
    players = 2 if len(build_deck(deck)) < 8 else 4
    count = f"score[0] := number of cards in deck where probe_is(card, {spelled})"
    function = "function probe_is(c : Card, r : Rank) = c.rank is r"
    return _game(
        Table(players=players, deck=deck), tag=tag, uses=through_library, statement=count,
        definitions="" if through_library else function,
    )


@pytest.mark.parametrize(("deck", "rank"), _numeric_ranks())
def test_a_numeric_rank_argument_plays_as_the_cards_own(deck: str, rank: str) -> None:
    """The oracle is the deck registry: the cards of that rank in a fresh deck."""
    text = _counting_game(deck, f'"{rank}"', through_library=False, tag=_tag("Plays", deck, rank))
    result = play_game(check_dsl(text, _GAME_FILE), random.Random(0))
    assert result.scores[0] == sum(1 for c in build_deck(deck) if c.rank == rank)


def test_the_library_rank_remedy_checks_and_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal's fix, applied: the library takes the rank as a parameter
    and the game passes rank 10."""
    _with_library(monkeypatch, "function probe_is(c : Card, r : Rank) = c.rank is r")
    text = _counting_game("standard52", '"10"', through_library=True, tag="RankRemedy")
    result = play_game(check_dsl(text, _GAME_FILE), random.Random(0))
    assert result.scores[0] == 4


# --- the remedies each library refusal offers, applied ------------------------


def test_the_seat_remedy_checks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_library(
        monkeypatch,
        f"requires {{ {_HAND}  dealer : Player }}\n"
        "function probe_fn() = number of cards in hand[dealer]",
    )
    text = _game(_TWO, tag="SeatRemedy", uses=True, state="dealer : Player = 0")
    assert _rendered(text) is None


def test_the_team_remedy_checks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_library(
        monkeypatch,
        "requires { side : Team }\nstate { probe_t[team] : Integer = 0 }\n"
        "function probe_fn() = probe_t[side]",
    )
    text = _game(_FOUR_IN_TWO, tag="TeamRemedy", uses=True, state="side : Team = 0")
    assert _rendered(text) is None


def test_the_provided_default_remedy_checks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """`merchant : Player = 1` moved to the contract: the game declares it."""
    _with_library(monkeypatch, "requires { merchant : Player }\nfunction probe_fn() = merchant")
    text = _game(_TWO, tag="DefaultRemedy", uses=True, state="merchant : Player = 1")
    assert _rendered(text) is None


def test_the_suit_remedy_checks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_library(monkeypatch, "function probe_is(c : Card, s : Suit) = c.suit is s")
    text = _game(
        _FOUR, tag="SuitRemedy", uses=True,
        statement="score[0] := number of cards in deck where probe_is(card, spades)",
    )
    assert _rendered(text) is None


def test_the_card_field_remedy_is_leaving_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """A game played with pieces cannot use a library reading a card's suit:
    the same game without the `uses` line checks clean."""
    _with_library(monkeypatch, "function probe_fn(c : Card) = c.suit is c.suit")
    assert _rendered(_game(_BREAKTHROUGH, tag="FieldRemedy", uses=False)) is None


# --- who the stamp names, and who it does not ---------------------------------


def test_two_libraries_are_each_told_on_their_own_line(monkeypatch: pytest.MonkeyPatch) -> None:
    clean = parse_library("library probe_other { function probe_g() = 1 }", "docs/libraries/probe_other.cardlang")
    reading = parse_library(
        f"library {_LIB} {{ function probe_fn(c : Card) = c.suit is c.suit }}", _LIB_FILE
    )
    libraries = {"probe_other": clean, _LIB: reading}
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset(libraries))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: libraries[name])
    text = _game(_BREAKTHROUGH, tag="TwoLibraries", uses=True).replace(
        f"  uses {_LIB}", f"  uses probe_other\n  uses {_LIB}"
    )
    _assert_verdict(text, _rendered(text), Verdict(uses_line=_field_refusal("suit", _BREAKTHROUGH)))


def test_a_game_argument_to_a_library_rule_is_the_games(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rule template's arguments are game text: a suit the game passes is
    not a suit the library names."""
    _with_library(
        monkeypatch,
        "rule probe_rule(s: Suit) { constrains: play_to_trick  "
        "demands: cards in hand where card.suit is not s  if_impossible: hand }",
    )
    text = _game(
        _FOUR, tag="RuleArgument", uses=True,
        statement=f"active_rules: [probe_rule(hearts)]\n    {_ROUND}",
    )
    assert _rendered(text) is None


def test_a_standard_library_rule_is_held_to_the_same_law(monkeypatch: pytest.MonkeyPatch) -> None:
    library = parse_library(
        "library stdlib { rule ProbeRule { constrains: play_to_trick  "
        'demands: cards in hand where card.rank is "10"  if_impossible: hand } }',
        _STDLIB_FILE,
    )
    monkeypatch.setattr(resolve_module, "stdlib_rules", lambda: {r.name: r for r in library.rules})
    text = _game(_FOUR, tag="StdlibRule", uses=False, statement=f"active_rules: [ProbeRule]\n    {_ROUND}")
    rendered = _rendered(text)
    assert rendered is not None
    assert any(
        ln.startswith(_STDLIB_FILE) and "library 'stdlib' names the rank \"10\"" in ln
        for ln in rendered.splitlines()
    ), rendered


def test_game_text_is_never_stamped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same rank string, written by the game beside a library it uses,
    keeps the game's verdict."""
    _with_library(monkeypatch, "function probe_g() = 1")
    text = _game(
        _KUHN, tag="GameBesideLibrary", uses=True,
        definitions='function probe_fn(c : Card) = c.rank is "10"',
    )
    _assert_verdict(text, _rendered(text), Verdict(game=('"10" is not a Rank value of this deck',)))


# --- the clause-reading type gates: one registry, every read in it -------------


_ENV_RECEIVER_SUFFIX = "env"


def _clause_reads() -> set[tuple[str, str]]:
    """(enclosing function, field) for every read of a clause field of a
    `TypeEnv` in typecheck.py."""
    sources = typecheck_module.TYPE_ENV_FIELD_SOURCES
    clause = {f for f, kind in sources.items() if kind == "clause"}
    owner = _enclosing_functions()
    reads: set[tuple[str, str]] = set()
    for node in ast.walk(_TYPECHECK_TREE):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in clause
            and isinstance(node.value, ast.Name)
            and node.value.id.endswith(_ENV_RECEIVER_SUFFIX)
        ):
            reads.add((owner.get(node, "<module>"), node.attr))
    return reads


def test_every_type_env_field_names_its_source() -> None:
    """red under: adding a field to `TypeEnv` the table lacks (executed
    2026-10-15)."""
    env_fields = {f.name for f in fields(typecheck_module.TypeEnv)}
    assert set(typecheck_module.TYPE_ENV_FIELD_SOURCES) == env_fields


def test_every_clause_read_is_registered() -> None:
    """red under: a new function reading `env.max_players`, which
    `CLAUSE_READS` lacks (executed 2026-10-15)."""
    assert set(typecheck_module.CLAUSE_READS) == _clause_reads()


def test_every_clause_read_has_an_env_receiver() -> None:
    """A clause field read through a receiver the scan does not name would
    escape the registry: every read of such a field is on an `env` or on the
    game itself. red under: `e2 = env` then `e2.max_players` in a new
    function (executed 2026-10-15)."""
    sources = typecheck_module.TYPE_ENV_FIELD_SOURCES
    clause = {f for f, kind in sources.items() if kind == "clause"}
    escapes = [
        node.lineno
        for node in ast.walk(_TYPECHECK_TREE)
        if isinstance(node, ast.Attribute)
        and node.attr in clause
        and not (
            isinstance(node.value, ast.Name)
            and (node.value.id.endswith(_ENV_RECEIVER_SUFFIX) or node.value.id in ("game", "self"))
        )
    ]
    assert not escapes, escapes


def _references(function: str, name: str) -> bool:
    for node in ast.walk(_TYPECHECK_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            return any(
                isinstance(sub, ast.Attribute) and sub.attr == name for sub in ast.walk(node)
            )
    raise AssertionError(f"{function} not in typecheck.py")


def test_every_refusing_clause_read_asks_the_stamp() -> None:
    """A row whose verdict is told to its owner reads the stamp in the gate it
    names. red under: replacing the `env.origins` lookup in
    `_check_role_literal` with `origin = None` (executed 2026-10-15)."""
    for (function, field), row in typecheck_module.CLAUSE_READS.items():
        if row.verdict in ("library", "uses_line"):
            assert row.gate is not None, (function, field)
            assert _references(row.gate, "origins"), (function, field, row.gate)
        else:
            assert row.reason, (function, field)


def test_a_string_valued_name_is_never_a_rank() -> None:
    """The string spelling belongs to the literal: a `let` holding `"10"` is a
    String, refused where a rank is wanted, as `card.rank is r` refuses it."""
    text = _game(
        _FOUR, tag="LetString", uses=False,
        definitions=(
            "function probe_f(r : Rank) = 1\n"
            'move_type probe_mv { effect { let r = "10"\n let n = probe_f(r) } }'
        ),
    )
    _assert_verdict(text, _rendered(text), Verdict(game=("probe_f() expects Rank, got String",)))
