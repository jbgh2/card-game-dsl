"""The game's Suit Ranking: the `suit ranking:` clause and its one reader,
`suit_value(s)`.

A game declares how its suits rank, strongest first, the way `ranking:`
declares its ranks: `suit ranking: spades hearts diamonds clubs`.
`suit_value(s)` reads it, the weakest listed suit 0. The list names every suit
the deck declares and may leave out the deck's special suits; reading a suit
the list leaves out is refused when the game runs. The clause reorders
nothing: the `Suit` move-parameter domain and `for each suit` keep the deck's
order.

Completeness ledger
-------------------
property:        every sentence written in the clause's position is accepted
                 with the declared values, or refused with a located message
                 that names the fix; `suit_value` reads the declared values
                 wherever the language admits a call, and is refused at the
                 call (or on the `uses` line, through a library) in a game
                 with no clause; a declared clause moves no Suit domain.
domain:          every deck in `DECKS`, crossed with the list forms (every
                 suit, the declared suits alone, each declared suit left
                 out, a repeat) and the wrong-name kinds (an unknown name,
                 `none`, a rank of the deck, a suit only another deck has, a
                 rank convention); every `n.Game` field as a reader position,
                 each a vehicle or a reason it holds no call, crossed with
                 the clause present or absent; the argument kinds a call can
                 pass; the clause-form misspellings; and the reverse-of-deck
                 twin over the Suit domain's three readers (the static action
                 space, the runtime Suit domain, `for each suit`). A clause
                 with no `suit_value` written anywhere in the game or its
                 libraries is refused; a reader written in a definition
                 nothing runs counts as a reader, the same domain the
                 no-clause refusal walks, so no game is refused both with
                 the clause and without it.
registry:        decks: `cardlang.runtime.values.DECKS` (declared suits:
                 `Deck.suits`; every suit: `deck_suits`); reader positions:
                 `cardlang.resolve._GAME_FIELD_ROLES`; the clause list:
                 `?game_item` in `cardlang/grammar/cardlang.lark`; the
                 `uses`-line gate row: tests/test_library_clause_gates.py;
                 the rank-name absorption pin:
                 tests/test_game_clause_guards.py::test_card_rank_excludes_every_clause_keyword.
does not prove:  that a refused misspelling outside the probed ones reads well:
                 the clause-form probes are the plausible wrong sentences, not
                 every string; any other string meets a located syntax error.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

import cardlang.resolve as resolve_module
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import emit
from cardlang.openspiel.encoding import ActionSpace
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import DECKS, deck_ranks, deck_suits

# --- the deck axis, derived ----------------------------------------------------


def _declared(deck: str) -> tuple[str, ...]:
    return tuple(DECKS[deck].suits)


def _specials(deck: str) -> tuple[str, ...]:
    return tuple(s for s in deck_suits(deck) if s not in DECKS[deck].suits)


def _strongest_first(deck: str, suits: tuple[str, ...]) -> tuple[str, ...]:
    """A list in the reverse of deck order, so no cell can pass by reading the
    deck's own order back."""
    return tuple(s for s in reversed(deck_suits(deck)) if s in suits)


def _a_rank_name(deck: str) -> str:
    return next(r for r in deck_ranks(deck) if r.isidentifier())


def _foreign_suit(deck: str) -> str:
    others = [s for d in DECKS for s in deck_suits(d) if s not in deck_suits(deck)]
    return others[0]


# --- the vehicle ---------------------------------------------------------------

_GAME = """game Probe {{
  players: 2
  max_length: 200
  cards: {deck}
{clauses}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0  pick : Suit? = none{state} }}
  phase play {{
{body}
  }}
{result}
}}
{tail}
"""


def _game(
    *,
    deck: str = "standard52",
    clause: str | None = "suit ranking: spades hearts diamonds clubs",
    clauses: str = "",
    state: str = "",
    body: str = "    score[0] := suit_value(spades)",
    result: str = "  winner: highest score",
    tail: str = "",
) -> str:
    lines = [f"  {clause}"] if clause is not None else []
    if clauses:
        lines.append(f"  {clauses}")
    return _GAME.format(
        deck=deck,
        clauses="\n".join(lines),
        state=state,
        body=body,
        result=result,
        tail=tail,
    )


def _refusal(text: str, source: str = "probe.cardlang") -> str:
    """Every rendered diagnostic `check_dsl` raises for `text`; fails the cell
    when the game is accepted."""
    try:
        check_dsl(text, source)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None)
        return "\n".join(notes) if notes else exc.diagnostic.format()
    raise AssertionError("the game was accepted")


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not in the probe game")


def _at(rendered: str, source: str, line: int, *needles: str) -> None:
    """Some diagnostic sits on `source:line` and carries every needle."""
    prefix = f"{source}:{line}:"
    hits = [
        row for row in rendered.splitlines()
        if row.startswith(prefix) and all(needle in row for needle in needles)
    ]
    assert hits, f"nothing at {prefix} naming {needles}:\n{rendered}"


def _clause_line(text: str) -> int:
    return _line_of(text, "suit ranking:")


# --- the list forms, per deck --------------------------------------------------


@dataclass(frozen=True)
class ListCell:
    deck: str
    form: str
    suits: tuple[str, ...]
    # The suit a "missing" cell leaves out; the extra word an unknown cell adds.
    word: str = ""

    @property
    def id(self) -> str:
        return f"{self.deck}-{self.form}" + (f"-{self.word}" if self.word else "")


def _list_cells() -> list[ListCell]:
    cells: list[ListCell] = []
    for deck in DECKS:
        every = _strongest_first(deck, deck_suits(deck))
        cells.append(ListCell(deck, "every_suit", every))
        cells.append(ListCell(deck, "declared_only", _strongest_first(deck, _declared(deck))))
        for left_out in _declared(deck):
            rest = tuple(s for s in every if s != left_out)
            if rest:  # else the empty clause, its own test below
                cells.append(ListCell(deck, "missing_declared", rest, left_out))
        for left_out in _specials(deck):
            cells.append(
                ListCell(deck, "missing_special", tuple(s for s in every if s != left_out), left_out)
            )
        cells.append(ListCell(deck, "repeated", every + (every[0],), every[0]))
        for kind, word in (
            ("unknown", "bogus"),
            ("none", "none"),
            ("rank", _a_rank_name(deck)),
            ("foreign_suit", _foreign_suit(deck)),
        ):
            cells.append(ListCell(deck, kind, every + (word,), word))
    return cells


def _value_body(suits: tuple[str, ...]) -> str:
    """One statement per listed suit, folding each `suit_value` into a decimal
    digit of seat 0's score, strongest first."""
    return "\n".join(f"    score[0] := score[0] * 10 + suit_value({s})" for s in suits)


@pytest.mark.parametrize("cell", _list_cells(), ids=lambda c: c.id)
def test_list_form(cell: ListCell) -> None:
    clause = "suit ranking: " + " ".join(cell.suits)
    accepted = cell.form in ("every_suit", "declared_only", "missing_special")
    if accepted:
        text = _game(deck=cell.deck, clause=clause, body=_value_body(cell.suits))
        game = check_dsl(text, "probe.cardlang")
        result = play_game(game, random.Random(0))
        want = int("".join(str(len(cell.suits) - 1 - i) for i in range(len(cell.suits))))
        assert result.scores[0] == want, (result.scores, cell.suits)
        return
    text = _game(deck=cell.deck, clause=clause, body="    score[0] := 1",
                 tail="function reader(s : Suit) = suit_value(s)")
    rendered = _refusal(text)
    line = _clause_line(text)
    match cell.form:
        case "missing_declared":
            _at(rendered, "probe.cardlang", line, f"leaves out {cell.word}",
                "strongest first")
        case "repeated":
            _at(rendered, "probe.cardlang", line, f"repeats suit '{cell.word}'")
        case "rank":
            _at(rendered, "probe.cardlang", line, f"'{cell.word}' is a rank", "`ranking:`")
        case "unknown" | "none" | "foreign_suit":
            _at(rendered, "probe.cardlang", line, f"'{cell.word}' is not a suit of deck")
        case _:
            raise AssertionError(f"unclassified list form {cell.form}")


@pytest.mark.parametrize(
    "deck", [d for d in DECKS if len(deck_suits(d)) == 1], ids=lambda d: d
)
def test_leaving_out_the_only_suit_is_the_empty_clause(deck: str) -> None:
    """A deck with one suit has nothing left once its suit is left out: the
    list is empty, which the grammar refuses."""
    text = _game(deck=deck, clause="suit ranking:", body="    score[0] := 1",
                 tail="function reader(s : Suit) = suit_value(s)")
    _at(_refusal(text), "probe.cardlang", _clause_line(text) + 1)


@pytest.mark.parametrize("deck", [d for d in DECKS if _specials(d)], ids=lambda d: d)
def test_a_special_suit_the_list_leaves_out_is_refused_when_read(deck: str) -> None:
    """The declared suits alone check clean; a card of a special suit reaching
    `suit_value` is refused in the runtime's channel, naming the reader, the
    suit and the declared list. Every card of the deck is read, so the special
    suit is always reached."""
    listed = _strongest_first(deck, _declared(deck))
    text = _game(
        deck=deck,
        clause="suit ranking: " + " ".join(listed),
        body="    score[0] := sum of suit_value(card.suit) over cards in deck",
    )
    game = check_dsl(text, "probe.cardlang")
    with pytest.raises(OwnerGuardError) as exc:
        play_game(game, random.Random(0))
    message = str(exc.value)
    assert "suit_value" in message
    assert any(f"'{s}'" in message for s in _specials(deck)), message
    assert ", ".join(listed) in message, message


@pytest.mark.parametrize("deck", list(DECKS), ids=lambda d: d)
def test_every_card_of_the_deck_reads_under_a_full_list(deck: str) -> None:
    every = _strongest_first(deck, deck_suits(deck))
    text = _game(
        deck=deck,
        clause="suit ranking: " + " ".join(every),
        body="    score[0] := sum of suit_value(card.suit) over cards in deck",
    )
    play_game(check_dsl(text, "probe.cardlang"), random.Random(0))


# --- reader positions ------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """A place `suit_value` can be written, as game text: the body, extra
    clauses, tail and result lines of the vehicle, and the needle marking the
    line holding the call."""

    clauses: str = ""
    body: str = "    score[0] := 1"
    tail: str = ""
    result: str = "  winner: highest score"
    state: str = ""
    library: str = ""
    needle: str = "suit_value("


_LIBRARY_FN = "library probe_lib {\n  function reader(c : Card) = suit_value(c.suit)\n}\n"

# Every `n.Game` field, as `_GAME_FIELD_ROLES` lists them: the vehicle writing
# `suit_value` there, or why the field holds no call of its own.
POSITIONS: dict[str, Position | str] = {
    "phases": Position(body="    score[0] := suit_value(spades)"),
    "move_types": Position(
        body="    offer to 0 one of [bump]",
        tail="move_type bump { effect { score[actor] := suit_value(spades) } }",
    ),
    "procedures": Position(
        body="    run bump()",
        tail="procedure bump() { score[0] := suit_value(spades) }",
    ),
    "functions": Position(
        body="    score[0] := reader(spades)",
        tail="function reader(s : Suit) = suit_value(s)",
    ),
    "rules": Position(
        clauses="ranking: aces high",
        body=(
            "    deal 2 cards from deck to each hand\n"
            "    active_rules: [Spades]\n"
            "    round play_to_trick from 0 over all players source hand into pile "
            "winner highest_of_led_suit"
        ),
        tail=(
            "rule Spades {\n  constrains: play_to_trick\n"
            "  applies_when: suit_value(spades) > 0\n"
            "  demands: cards in hand where card.suit is spades\n  if_impossible: hand\n}"
        ),
    ),
    "trick_order": Position(
        clauses="trick_order { trump: card.suit is spades  card_strength: suit_value(card.suit) }",
        body=(
            "    deal 2 cards from deck to each hand\n"
            "    round play_to_trick from 0 over all players source hand into pile "
            "winner highest_by_trick_order"
        ),
    ),
    "loser": Position(
        result="  loser: if suit_value(spades) > 0 then 0 else 1",
    ),
    "uses": Position(
        clauses="uses probe_lib",
        library=_LIBRARY_FN,
        needle="uses probe_lib",
    ),
    "state": Position(state="  base : Integer = suit_value(spades)"),
    "winner": "names a state variable, never an expression",
    "primitives": "declares Python signatures; a body is Python, never a call",
    "card_points": "a table of integer literals",
    "board": "a board family and integer arguments",
    "zones": "zone declarations",
    "positions": "integer ranges",
    "players": "a seat count",
    "teams": "seat lists",
    "name": "a name",
    "deck": "a component set's name",
    "content_flavor": "stamped by the parser",
    "direction": "a turn direction",
    "ranking": "rank names",
    "ranking_convention": "a convention keyword",
    "suit_ranking": "suit names: the clause itself",
    "trump": "a suit name",
    "max_length": "an integer",
    "span": "a source location",
}


def test_every_game_field_is_a_reader_position_or_holds_no_call() -> None:
    """The position axis is the game's field list, as resolve's own field
    registry spells it; a field added to `n.Game` is a red here until it is
    given a vehicle or a reason.

    red under: deleting the `rules` row of `POSITIONS`."""
    assert set(POSITIONS) == set(resolve_module._GAME_FIELD_ROLES)


def _position_text(position: Position, clause: str | None) -> str:
    return _game(
        clause=clause,
        clauses=position.clauses,
        state=position.state,
        body=position.body,
        result=position.result,
        tail=position.tail,
    )


def _check_position(
    position: Position, clause: str | None, monkeypatch: pytest.MonkeyPatch
) -> str:
    if position.library:
        library = parse_library(position.library, "docs/libraries/probe_lib.cardlang")
        monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({"probe_lib"}))
        monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    return _position_text(position, clause)


_CALLABLE_POSITIONS = sorted(
    name for name, p in POSITIONS.items() if isinstance(p, Position) and name != "state"
)


@pytest.mark.parametrize("field", _CALLABLE_POSITIONS)
def test_a_reader_with_the_clause_checks_and_plays(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    position = POSITIONS[field]
    assert isinstance(position, Position)
    text = _check_position(position, "suit ranking: spades hearts diamonds clubs", monkeypatch)
    play_game(check_dsl(text, "probe.cardlang"), random.Random(0))


@pytest.mark.parametrize("field", _CALLABLE_POSITIONS)
def test_a_reader_without_the_clause_is_refused_where_the_designer_wrote(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Written in the game, the refusal sits on the call's line; reached through
    a library, on the game's `uses` line, naming the library."""
    position = POSITIONS[field]
    assert isinstance(position, Position)
    text = _check_position(position, None, monkeypatch)
    rendered = _refusal(text)
    needles = ["suit_value", "`suit ranking:`"]
    if position.library:
        needles.append("'probe_lib'")
        assert "docs/libraries/probe_lib.cardlang" not in rendered, rendered
    _at(rendered, "probe.cardlang", _line_of(text, position.needle), *needles)


def test_a_state_default_refuses_the_call_for_its_own_reason() -> None:
    """A game-level default is evaluated before any phase and may call nothing;
    with the clause declared the call is still refused there, by that rule."""
    position = POSITIONS["state"]
    assert isinstance(position, Position)
    text = _position_text(position, "suit ranking: spades hearts diamonds clubs")
    _at(_refusal(text), "probe.cardlang", _line_of(text, "base : Integer"))


# --- the unread clause -----------------------------------------------------------


def test_a_clause_nothing_reads_is_refused() -> None:
    text = _game(body="    score[0] := 1")
    _at(_refusal(text), "probe.cardlang", _clause_line(text), "read by nothing",
        "suit_value")


def test_a_reader_in_a_definition_nothing_runs_still_reads_the_clause() -> None:
    """The unread check walks the text the no-clause refusal walks, so a game
    whose only `suit_value` sits in a function nothing calls is accepted with the
    clause and refused without it, never refused both ways."""
    tail = "function unused(s : Suit) = suit_value(s)"
    check_dsl(_game(body="    score[0] := 1", tail=tail), "probe.cardlang")
    _refusal(_game(clause=None, body="    score[0] := 1", tail=tail))


# --- argument kinds --------------------------------------------------------------

_ARGUMENTS: dict[str, tuple[str, str, str]] = {
    # name: (state declaration, the call's argument, expected: "plays" |
    # "runtime" | a needle the check-time refusal carries)
    "suit_literal": ("", "hearts", "plays"),
    "suit_state": ("  trumps : Suit = hearts", "trumps", "plays"),
    "card_suit": ("", "top_of(deck).suit", "plays"),
    "optional_holding_a_suit": ("  maybe : Suit? = hearts", "maybe", "plays"),
    "optional_holding_none": ("", "pick", "runtime"),
    "none_literal": ("", "none", "expects Suit"),
    "card": ("", "top_of(deck)", "`.suit`"),
    "card_binder": ("", "c", "`suit_value(c.suit)`"),
    "rank": ("", "top_of(deck).rank", "expects Suit"),
    "integer": ("", "3", "expects Suit"),
}


@pytest.mark.parametrize("kind", sorted(_ARGUMENTS))
def test_argument_kind(kind: str) -> None:
    state, arg, expect = _ARGUMENTS[kind]
    if arg == "c":
        body = "    score[0] := reader(top_of(deck))"
        tail = "function reader(c : Card) = suit_value(c)"
    else:
        body = f"    score[0] := suit_value({arg})"
        tail = ""
    text = _game(state=state, body=body, tail=tail)
    if expect == "plays":
        play_game(check_dsl(text, "probe.cardlang"), random.Random(0))
        return
    if expect == "runtime":
        game = check_dsl(text, "probe.cardlang")
        with pytest.raises(OwnerGuardError) as exc:
            play_game(game, random.Random(0))
        assert "suit_value" in str(exc.value) and "none" in str(exc.value)
        return
    _at(_refusal(text), "probe.cardlang", _line_of(text, "suit_value("), expect)


def test_the_card_hint_names_a_fix_that_checks() -> None:
    """The fix the Card refusal names is checked as written."""
    text = _game(body="    score[0] := reader(top_of(deck))",
                 tail="function reader(c : Card) = suit_value(c.suit)")
    check_dsl(text, "probe.cardlang")


# --- misspelled clauses ----------------------------------------------------------

_MISUSE: dict[str, tuple[str, str]] = {
    # name: (the clause line, a needle the refusal carries)
    "comparison_symbols": ("suit ranking: clubs < diamonds < hearts < spades", ""),
    "commas": ("suit ranking: spades, hearts, diamonds, clubs",
               "`suit ranking: spades hearts diamonds clubs`"),
    "no_colon": ("suit ranking spades hearts diamonds clubs", ""),
    "plural": ("suits ranking: spades hearts diamonds clubs", ""),
    "number_in_slot": ("suit ranking: 1 2 3 4", ""),
    "string_in_slot": ('suit ranking: "spades" "hearts" "diamonds" "clubs"', ""),
    "rank_convention": ("suit ranking: aces high", "`ranking: aces high`"),
    "ranks_in_slot": ("suit ranking: A K Q", "`ranking:`"),
    "suits_in_ranking": ("ranking: spades hearts diamonds clubs", "`suit ranking:`"),
    "ranking_suit_order": ("ranking: suit spades hearts diamonds clubs",
                           "`suit ranking: spades hearts diamonds clubs`"),
}


@pytest.mark.parametrize("name", sorted(_MISUSE))
def test_a_misspelled_clause_is_refused_on_its_line(name: str) -> None:
    clause, needle = _MISUSE[name]
    text = _game(clause=clause, tail="function reader(s : Suit) = suit_value(s)")
    rendered = _refusal(text)
    if clause.startswith("ranking:") and name != "ranking_suit_order":
        # A `ranking:` refusal sits on the game's opening line, as every
        # `ranking:` refusal does (issue #863).
        line = _line_of(text, "game Probe")
    else:
        line = _line_of(text, " ".join(clause.split()[:2]))
    rows = [r for r in rendered.splitlines() if r.startswith(f"probe.cardlang:{line}:")]
    assert rows, rendered
    if needle:
        assert any(needle in r for r in rows), rendered


def test_the_clause_is_inexpressible_in_a_library() -> None:
    """A library declares no game clause; the clause written in one is a
    located syntax error in the library's own file."""
    with pytest.raises(DiagnosticError) as exc:
        parse_library(
            "library probe_lib {\n  suit ranking: spades hearts\n}\n",
            "docs/libraries/probe_lib.cardlang",
        )
    assert exc.value.diagnostic.span is not None
    assert exc.value.diagnostic.span.line == 2


def test_a_second_clause_is_refused() -> None:
    clause = "suit ranking: spades hearts diamonds clubs"
    text = _game(clauses=clause)
    _at(_refusal(text), "probe.cardlang", _line_of(text, clause) + 1,
        "declares one `suit ranking:`")


def test_the_clause_is_refused_in_a_game_played_with_pieces() -> None:
    text = """game Probe {
  players: 2
  max_length: 10
  pieces: xo_marks
  suit ranking: spades hearts
  zones { box : Deck  reserve[player] : PlayerPile<player> }
  state { score[player] : Integer = 0 }
  phase play { score[0] := 1 }
  winner: highest score
}
"""
    rendered = _refusal(text)
    assert "`suit ranking:`" in rendered and "piece" in rendered, rendered


def test_a_game_function_named_suit_value_is_refused() -> None:
    text = _game(body="    score[0] := 1", tail="function suit_value(s : Suit) = 1")
    assert "suit_value" in _refusal(text)


# --- the clause reorders nothing ------------------------------------------------

_DOMAIN_GAME = """game Probe {{
  players: 2
  max_length: 50
  cards: standard52
{clause}
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0  seen : Integer = 0 }}
  phase play {{
    for each suit s: seen := seen * 10 + (if s is clubs then 1 elif s is diamonds then 2 elif s is hearts then 3 else 4)
    score[0] := seen
{reader}
    offer to 0 one of [name_suit]
  }}
  winner: highest score
}}
move_type name_suit(s : Suit?) {{ effect {{ score[1] := 1 }} }}
"""


def _domain_game(clause: str | None) -> n.Game:
    text = _DOMAIN_GAME.format(
        clause=f"  {clause}" if clause else "",
        reader="    score[1] := suit_value(spades)" if clause else "",
    )
    return check_dsl(text, "domain.cardlang")


def test_a_reverse_of_deck_clause_moves_no_suit_domain() -> None:
    """The twin declaring the reverse of deck order and the twin declaring no
    clause share the static action space, the runtime Suit domain and the
    `for each suit` order.

    red under: building `rs.suits` from the clause in `driver.play_game`."""
    reverse = "suit ranking: " + " ".join(reversed(deck_suits("standard52")))
    ranked, plain = _domain_game(reverse), _domain_game(None)
    ranked_space, plain_space = ActionSpace.for_game(ranked), ActionSpace.for_game(plain)
    assert ranked_space.num_distinct_actions == plain_space.num_distinct_actions
    for suit in (*deck_suits("standard52"), None):
        assert ranked_space.encode(("name_suit", suit)) == plain_space.encode(("name_suit", suit))
    domains: list[tuple[str, ...]] = []

    def hook(rs: RuntimeState) -> None:
        domains.append(rs.suits)

    ranked_result = play_game(ranked, random.Random(0), on_first_decision=hook)
    plain_result = play_game(plain, random.Random(0), on_first_decision=hook)
    assert domains[0] == domains[1] == deck_suits("standard52")
    assert ranked_result.scores[0] == plain_result.scores[0] == 1234


# --- the IR ---------------------------------------------------------------------


def test_the_ir_carries_the_clause_only_when_declared() -> None:
    declared = emit(check_dsl(_game(), "probe.cardlang"))
    assert declared["suit_ranking"] == ["spades", "hearts", "diamonds", "clubs"]
    plain = emit(check_dsl(_game(clause=None, body="    score[0] := 1"), "probe.cardlang"))
    assert "suit_ranking" not in plain
