"""Surface-totality grid for a move type's stake row: `wager` / `concession`.

A move type may say, on its own line under its name, that playing it is a
**Wager** — the move stakes something the game settles later — or a
**Concession** — the move gives up what was at stake for certain. A move with
no row is plain. The fact is static game text: it enters no observation, mints
no action id, and changes nothing the runtime does. Its one reader is the
`ranked` Opponent, which declines a staked move wherever a plain one is on
offer (`cardlang.openspiel.ranked`).

Completeness ledger
-------------------
property:        every move type the grammar accepts carries its row, as
                 written, from the parse builder through resolve and the
                 library splice to the checked game and the IR; the row is
                 inert in the runtime, the encoding, and the rendered
                 information state; every plausible wrong sentence fails loud
                 in its owning layer's currency (a parse-layer DiagnosticError
                 naming the fix for the four reject-with-replacement shapes, a
                 syntax error for the rest, a resolve diagnostic for a row
                 nothing can read); and at every decision whose candidates mix
                 plain and staked move types, `ranked` answers a plain one.
domain:          definition site (`?top_item` and `?library_item`, the
                 productions naming `move_type_def`; a game body and the stdlib
                 rules fragment hold no move type) x row (absent, and each
                 member of `nodes.STAKES`) x `when:` (absent / present) x
                 parameter domain (nullary, each of `domains.PARAM_DOMAIN_ORDER`,
                 a declared position domain, the board-minted direction
                 domain, and `Card`) x the construct presenting it (each
                 `move_type`-namespace slot of `resolve._REFERENCE_SLOTS`, both
                 at once, an offer made from inside another move type's
                 effect, one made from a procedure, one made from inside a
                 move type nothing reaches, and none). A row on a
                 `Card`-parameterized move is refused: its action id is the
                 card's, so no seat can read the row. A row on a game move type
                 no reachable offering presents is refused: nothing can read
                 it, and an offer inside a move type or procedure nothing
                 reaches presents nothing. A library move type's row is the
                 library's statement for every game that imports it, so a game
                 that imports it and presents it nowhere is not refused. In a
                 game with a climbing round, a
                 move type spelled like one of the engine's own actions
                 (`primitives.climb_actions`) is refused whatever presents it.
                 The action space resolves an id by what minted it, never by
                 spelling, pinned on a space built by hand.
                 The dispositions: every non-empty subset of
                 {plain} + `nodes.STAKES` presented at one decision, in the name
                 block (a nullary `offer`) and the offering block (a
                 parameterized `offer`).
registry:        definition sites: the grammar's productions naming
                 `move_type_def` (scraped below); the row: `nodes.STAKES` and
                 the grammar's `move_stake` production (reconciled below);
                 parameter domains: `domains.PARAM_DOMAIN_ORDER`,
                 `board_domains.DIRECTION_DOMAIN`; presentation:
                 `resolve._REFERENCE_SLOTS`; blocks: `encoding.BLOCKS`;
                 games: `cardlang.openspiel.registry.GAMES`.
                 Keyword anchoring for `_WAGER_KW` / `_CONCESSION_KW`: the
                 derived grid in tests/test_keyword_anchoring.py. The designer
                 word for each new terminal:
                 tests/test_parse_diagnostics.py::test_every_terminal_has_a_designer_word.
does not prove:  that the row is marked on the right side. The checker cannot
                 read a stake off an effect, so a row on the wrong move type
                 passes every check here; execution is the witness, and the
                 Tichu line below reddens when the row moves from `call_tichu`
                 to `no_call`. Nor that `ranked` plays a staked decision well:
                 it declines every stake a plain move stands beside and draws
                 where none does, which is termination at Tichu and Pinochle,
                 not competence; a reason to take a stake is issue #768's.
"""

from __future__ import annotations

import hashlib
import itertools
import re
import typing
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

import pytest

from cardlang import ir
from cardlang.ast import nodes as n
from cardlang.board_domains import DIRECTION_DOMAIN
from cardlang.builtins.functions import PRIMITIVE_CLIMB_LEADS
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import PARAM_DOMAIN_ORDER
from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.infostate import SeatView, render_information_state
from cardlang.openspiel.ranked import DISPOSITIONS, RankedSeatPolicy
from cardlang.openspiel.registry import GAMES as REGISTERED
from cardlang.openspiel.replay import LiveLine, load
from cardlang.openspiel.seat_policy import SeatBinding, UniformSeatPolicy
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.resolve import _REFERENCE_SLOTS, _walk
from cardlang.runtime import primitives

GAMES = Path(__file__).parent.parent / "docs" / "games"
GRAMMAR = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()

# ---------------------------------------------------------------------------
# The axes, derived.
# ---------------------------------------------------------------------------


def _productions_naming(symbol: str) -> list[str]:
    """The heads of the grammar's productions whose body names `symbol`."""
    heads: list[str] = []
    head = None
    for line in GRAMMAR.splitlines():
        stripped = line.split("//", 1)[0]
        m = re.match(r"^(\??[a-z_]+)\s*:", stripped)
        if m:
            head = m.group(1)
        if head is not None and re.search(rf"\b{symbol}\b", stripped) and not stripped.startswith(symbol):
            heads.append(head.lstrip("?"))
    return sorted(set(heads))


SITES = _productions_naming("move_type_def")
ROWS: tuple[str | None, ...] = (None, *n.STAKES)
PARAMS: tuple[str | None, ...] = (None, *PARAM_DOMAIN_ORDER, "slot", DIRECTION_DOMAIN, "Card")
PRESENTERS = tuple(
    sorted(f"{node.__name__}.{field}" for (node, field), ns in _REFERENCE_SLOTS.items() if ns == "move_type")
)


def test_the_axes_are_pinned_by_the_grammar_and_the_registries() -> None:
    """The definition sites are the productions naming `move_type_def`; the row
    words are exactly `nodes.STAKES`, each an anchored keyword of the
    `move_stake` production; the presenters are the `move_type` slots."""
    assert SITES == ["library_item", "top_item"]
    production = GRAMMAR[GRAMMAR.index("\nmove_stake:") :].split("\nSTAKE_FLAG_COLON", 1)[0]
    keywords = set(re.findall(r"_([A-Z]+)_KW", production))
    assert keywords == {stake.upper() for stake in n.STAKES}, "the row words are exactly the registry's"
    assert typing.get_args(n.Stake) == n.STAKES
    words = re.findall(r'"([a-z_]+)"\s*/\(\?!\[A-Za-z0-9_\]\)/', GRAMMAR)
    for stake in n.STAKES:
        assert stake in words
    assert "[move_stake] [move_when] move_effect" in GRAMMAR
    assert PRESENTERS == ("Offer.offering",)


# ---------------------------------------------------------------------------
# The shells.
# ---------------------------------------------------------------------------

_HEADER = """
  players: 2
  direction: clockwise
  max_length: 200
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  positions { slot : 1..2 }
  zones { deck : Deck  hand[player] : Hand<player> }
  state { tally[player] : Integer = 0  done : Integer = 0 }
"""

_BOARD_HEADER = """
  players: 2
  direction: clockwise
  max_length: 200
  board: grid(3, 3)
  pieces: xo_marks
  zones { box : Deck  square[cell] : Cell<cell> }
  state { tally[player] : Integer = 0  done : Integer = 0 }
"""


def _move(row: str | None, when: bool, param: str | None, name: str = "m") -> str:
    head = f"move_type {name}" + (f"(x : {param})" if param else "")
    body = (f"{row}\n  " if row else "") + ("when: done < 50\n  " if when else "")
    return f"{head} {{\n  {body}effect {{ tally[actor] += 1  done += 1 }}\n}}"


def _game(site: str, move: str, presenter: str, board: bool = False) -> str:
    """A two-seat game whose one phase presents `m` beside the plain `stay`."""
    present = {
        "Offer.offering": "for each player p: offer to p one of [m, stay]",
        "both": "for each player p: offer to p one of [m, stay]\n"
        "    turns t from 0 over all players until done >= 4 { offer to t one of [m, stay] }",
        "effect": "for each player p: offer to p one of [opener]",
        "procedure": "run present_m()",
        "none": "for each player p: offer to p one of [stay]",
        "unreached": "for each player p: offer to p one of [stay]",
    }[presenter]
    setup = "" if board else "shuffle deck\n    deal 2 cards from deck to each hand\n    "
    tail = move if site == "top_item" else ""
    uses = f"uses {_library_name(move)}\n" if site == "library_item" else ""
    header = _BOARD_HEADER if board else _HEADER
    extra = {
        "effect": "move_type opener { effect { offer to actor one of [m, stay] } }",
        "unreached": "move_type opener { effect { offer to actor one of [m, stay] } }",
        "procedure": "procedure present_m() { for each player p: offer to p one of [m, stay] }",
    }
    return f"""
game Mini {{
  {uses}{header}
  phase p {{
    {setup}{present}
  }}
  winner: highest tally
}}
move_type stay {{ effect {{ done += 1 }} }}
{extra.get(presenter, "")}
{tail}
"""


def _library_name(move: str) -> str:
    """One library name per move text: `check_dsl` is memoized on the game's
    text and resolve caches per library name, so two cells sharing a name
    would read each other's answers."""
    return "probe_" + hashlib.sha256(move.encode()).hexdigest()[:12]


def _checked(site: str, move: str, presenter: str, monkeypatch: pytest.MonkeyPatch, board: bool = False) -> n.Game:
    if site == "library_item":
        name = _library_name(move)
        library = parse_library(
            f"library {name} {{\nrequires {{ tally[player] : Integer  done : Integer }}\n{move}\n}}",
            f"{name}.cardlang",
        )
        monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({name}))
        monkeypatch.setattr("cardlang.resolve.load_library", lambda name: library)
    return check_dsl(_game(site, move, presenter, board), "mini.cardlang")


def _m(game: n.Game) -> n.MoveTypeDef:
    return next(mt for mt in game.move_types if mt.name == "m")


# ---------------------------------------------------------------------------
# The declaration grid: site x row x when x parameter domain.
# ---------------------------------------------------------------------------

DECLARATION_CELLS = list(itertools.product(SITES, ROWS, (False, True), PARAMS))


@pytest.mark.parametrize(
    ("site", "row", "when", "param"),
    DECLARATION_CELLS,
    ids=[f"{s}-{r or 'plain'}-{'when' if w else 'bare'}-{p or 'nullary'}" for s, r, w, p in DECLARATION_CELLS],
)
def test_the_row_reaches_the_checked_game_or_is_refused(
    site: str, row: str | None, when: bool, param: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    move = _move(row, when, param)
    board = param == DIRECTION_DOMAIN
    if site == "library_item" and param in ("slot", DIRECTION_DOMAIN):
        # A library names no position domain of its own, so the including
        # game's would be what it meant: refused whatever the row.
        with pytest.raises(DiagnosticError) as ei:
            _checked(site, move, "Offer.offering", monkeypatch, board)
        assert "which the library does not have" in str(ei.value)
        return
    if param == "Card" and row is not None:
        with pytest.raises(DiagnosticError) as ei:
            _checked(site, move, "Offer.offering", monkeypatch, board)
        assert f"`{row}` on move type `m`" in str(ei.value)
        assert "action id is the card" in str(ei.value)
        return
    game = _checked(site, move, "Offer.offering", monkeypatch, board)
    assert _m(game).stake == row
    assert (_m(game).when is not None) is when


# ---------------------------------------------------------------------------
# The presentation grid: row x the construct presenting the move.
# ---------------------------------------------------------------------------

PRESENTATION_CELLS = list(
    itertools.product(SITES, ROWS, (*PRESENTERS, "both", "effect", "procedure", "none", "unreached"))
)


@pytest.mark.parametrize(
    ("site", "row", "presenter"),
    PRESENTATION_CELLS,
    ids=[f"{s}-{r or 'plain'}-{p}" for s, r, p in PRESENTATION_CELLS],
)
def test_a_row_nothing_can_read_is_refused(
    site: str, row: str | None, presenter: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    move = _move(row, False, None)
    if presenter in ("none", "unreached") and site == "top_item":
        with pytest.raises(DiagnosticError) as ei:
            _checked(site, move, presenter, monkeypatch)
        # Under "unreached" the game's own `opener` is never offered either,
        # and is reported beside `m`; the pass's whole report is the evidence.
        report = "\n".join([str(ei.value), *(getattr(ei.value, "__notes__", []) or [])])
        if row is not None:
            assert f"`{row}` on move type `m`, which no reachable `offer` presents" in report
        else:
            assert "move type `m` is never offered" in report
        if presenter == "unreached":
            assert "move type `opener` is never offered" in report
        return
    if presenter == "unreached":
        # The library's `m` is the library's vocabulary; the game's own
        # `opener`, which nothing offers, is what the game wrote and nobody plays.
        with pytest.raises(DiagnosticError, match="move type `opener` is never offered"):
            _checked(site, move, presenter, monkeypatch)
        return
    assert _m(_checked(site, move, presenter, monkeypatch)).stake == row


# ---------------------------------------------------------------------------
# The misuse probes: the sentences a designer would plausibly get wrong.
# ---------------------------------------------------------------------------

# (body, the fix the refusal names, the line the refusal points at). Every
# refusal lands on the word to move or delete, never on the `move_type` line.
_REJECT_WITH_FIX = {
    "row-after-when": ("when: done < 50\n  wager\n  effect { done += 1 }", "before `when:`", "  wager"),
    "flag-true": ("wager: true\n  effect { done += 1 }", "write `wager` alone", "  wager: true"),
    "flag-false": ("wager: false\n  effect { done += 1 }", "leaving the row out", "  wager: false"),
    "flag-empty": ("wager:\n  effect { done += 1 }", "write `wager` alone", "  wager:"),
    "flag-empty-before-when": ("wager:\n  when: done < 50\n  effect { done += 1 }", "write `wager` alone", "  wager:"),
    "concession-flag": ("concession: true\n  effect { done += 1 }", "write `concession` alone", "  concession: true"),
    "flag-after-when": (
        "when: done < 50\n  concession: true\n  effect { done += 1 }",
        "a row, not a flag, and it stands with the move's name, before `when:`",
        "  concession: true",
    ),
    "second-row-after-when": (
        "wager\n  when: done < 50\n  concession\n  effect { done += 1 }",
        "one Stake row — `wager` stands under its name, so delete the `concession`",
        "  concession",
    ),
}

# (body, the word the parser refuses). Each is a syntax error AT that word, so
# a grammar that came to accept the shape would redden the cell.
_SYNTAX_ERRORS = {
    "doubled": ("wager\n  wager\n  effect { done += 1 }", "wager"),
    "both-words": ("wager\n  concession\n  effect { done += 1 }", "concession"),
    "row-after-effect": ("effect { done += 1 }\n  wager", "wager"),
    "comma": ("wager,\n  effect { done += 1 }", ","),
    "capitalised": ("Wager\n  effect { done += 1 }", "Wager"),
    "plural": ("wagers\n  effect { done += 1 }", "wagers"),
    "verb": ("concede\n  effect { done += 1 }", "concede"),
    "cautious": ("cautious\n  effect { done += 1 }", "cautious"),
    "optional": ("optional\n  effect { done += 1 }", "optional"),
    "fused": ("wagerwhen: done < 50\n  effect { done += 1 }", "wagerwhen"),
    "equals": ("wager = true\n  effect { done += 1 }", "="),
}


@pytest.mark.parametrize("probe", sorted(_REJECT_WITH_FIX))
def test_a_misplaced_or_flagged_row_is_refused_naming_the_fix(probe: str) -> None:
    body, needle, at = _REJECT_WITH_FIX[probe]
    src = _game("top_item", f"move_type m {{\n  {body}\n}}", "Offer.offering")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)
    lines = src.splitlines()
    head = next(i for i, line in enumerate(lines) if line.startswith("move_type m {"))
    expected = next(i for i in range(head, len(lines)) if lines[i] == at) + 1
    span = ei.value.diagnostic.span
    assert span is not None and span.line == expected, (span, expected)


@pytest.mark.parametrize("probe", sorted(_SYNTAX_ERRORS))
def test_other_words_in_the_slot_are_syntax_errors(probe: str) -> None:
    body, word = _SYNTAX_ERRORS[probe]
    src = _game("top_item", f"move_type m {{\n  {body}\n}}", "Offer.offering")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert f"syntax error: unexpected `{word}`" in str(ei.value), str(ei.value)
    assert ei.value.diagnostic.span is not None
    # The flag's colon is spelled only by the two refusals, so no hint offers it.
    assert "`:`" not in str(ei.value), str(ei.value)


@pytest.mark.parametrize(
    "holder",
    [
        "function f(x : Integer) = wager x",
        "procedure q() { wager done += 1 }",
        "rule R { wager constrains: play_to_trick demands: true }",
    ],
    ids=["function", "procedure", "rule"],
)
def test_the_row_belongs_to_move_types_alone(holder: str) -> None:
    """A syntax error on the holder's own line: a grammar that came to accept
    the row there would leave only the holder's unrelated refusals (a rule
    with no `if_impossible`, a procedure nothing runs), which are no syntax
    error."""
    src = _game("top_item", _move(None, False, None), "Offer.offering") + "\n" + holder
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert "syntax error" in str(ei.value), str(ei.value)
    span = ei.value.diagnostic.span
    assert span is not None and span.line == len(src.splitlines())


@pytest.mark.parametrize("stake", n.STAKES)
@pytest.mark.parametrize(
    ("declaration", "edit"),
    [
        ("state variable", ("done : Integer = 0", "done : Integer = 0  {w} : Integer = 0")),
        ("zone", ("deck : Deck", "deck : Deck  {w} : Deck")),
        ("function", ("move_type stay", "function {w}(x : Integer) = x\nmove_type stay")),
    ],
)
def test_the_row_words_are_reserved_as_declared_names(stake: str, declaration: str, edit: tuple[str, str]) -> None:
    """The words are clause keywords, so a declaration spelled like one would
    read, at every bare use, as a reference to something the row is not."""
    old, new = edit
    src = _game("top_item", _move(None, False, None), "Offer.offering").replace(old, new.format(w=stake), 1)
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert f"'{stake}' is a reserved word" in str(ei.value), str(ei.value)


@pytest.mark.parametrize("stake", n.STAKES)
def test_a_move_type_may_be_named_like_its_row(stake: str) -> None:
    """A move type's name is never a bare value, so it keeps the freedom
    `move_type outcome` has."""
    src = _game("top_item", _move(None, False, None), "Offer.offering").replace("[m, stay]", f"[m, stay, {stake}]")
    src += f"\nmove_type {stake} {{\n  {stake}\n  effect {{ done += 1 }}\n}}"
    game = check_dsl(src, "mini.cardlang")
    assert {mt.name: mt.stake for mt in game.move_types}[stake] == stake


def _climb_actions_by_game() -> list[tuple[str, str]]:
    """Every own action of every climb engine a registered game plays, beside
    that game's file: the engines from the games, the actions from the
    registry (`primitives.climb_actions`)."""
    cells: list[tuple[str, str]] = []
    for file_name in sorted(REGISTERED.values()):
        game = check_dsl((GAMES / file_name).read_text(), file_name)
        engines = sorted({nd.combos_fn for nd in _walk(game) if isinstance(nd, n.ClimbRound)})
        cells += [(file_name, action) for engine in engines for action in primitives.climb_actions(engine)]
    return cells


CLIMB_ACTION_CELLS = _climb_actions_by_game()


@pytest.mark.parametrize("engine", sorted(PRIMITIVE_CLIMB_LEADS))
def test_every_climb_engine_spells_its_own_actions_apart(engine: str) -> None:
    """Every registered climb engine's own actions are distinct words, so no
    two of its decisions share a rendering or an action id — the Owner the
    registry's own refusal in `primitives.climb_actions` shadows.

    red under: make any engine's `climb_interrupt_decline` answer "pass"."""
    decline = primitives.climb_interrupt_decline(engine)
    rows = (primitives.CLIMB_PASS, *primitives.climb_announcements(engine), *([decline] if decline else []))
    assert len(set(rows)) == len(rows), rows
    assert primitives.climb_actions(engine) == rows


@pytest.mark.parametrize(("file_name", "action"), CLIMB_ACTION_CELLS, ids=[f"{f}-{a}" for f, a in CLIMB_ACTION_CELLS])
def test_every_climb_action_is_a_name_no_move_type_takes(file_name: str, action: str) -> None:
    """A move type spelled like any of the engine's own actions is refused by
    name, located at the move type, whether or not anything presents it.

    red under: drop the `_check_climb_action_names` call from `resolve`."""
    text = (GAMES / file_name).read_text() + f"\nmove_type {action} {{\n  effect {{ }}\n}}\n"
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(text, f"{file_name}-{action}")
    assert f"move type `{action}` is spelled like the climb engine" in str(ei.value), str(ei.value)
    span = ei.value.diagnostic.span
    assert span is not None and span.line == len(text.splitlines()) - 2


_TOKEN_PRESENTERS = (
    "offer",
    "offer-parameterized",
    "offer-nullable",
    "ring",
    "ring-nullable",
    "library, unpresented",
)
_TOKEN_PARAMS = {"offer-parameterized": "(s : Suit)", "offer-nullable": "(s : Suit?)", "ring-nullable": "(s : Suit?)"}
TOKEN_CELLS = list(itertools.product(("pass",), _TOKEN_PRESENTERS, ROWS))


@pytest.mark.parametrize(
    ("token", "presenter", "row"),
    TOKEN_CELLS,
    ids=[f"{t}-{p}-{r or 'plain'}" for t, p, r in TOKEN_CELLS],
)
def test_a_move_type_spelled_like_a_climb_token_is_refused(
    token: str, presenter: str, row: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a game with a climbing round, a move type spelled like one of the
    engine's own actions is refused by the checker, located, whatever presents
    it and whatever its row: a seat would see the two alike, and a nullary
    `offer` of it would share the action's id.

    red under: drop the `_check_climb_action_names` call from `resolve`."""
    text = (GAMES / "tichu.cardlang").read_text()
    param = _TOKEN_PARAMS.get(presenter, "")
    move = f"move_type {token}{param} {{\n  {row or ''}\n  effect {{ quiet += 0 }}\n}}\n"
    dragon = "offer to winner one of [dragon_to_left, dragon_to_right]"
    assert dragon in text and "game Tichu {" in text, "the witness's anchors moved"
    if presenter.startswith("offer"):
        text = text.replace(dragon, f"offer to winner one of [dragon_to_left, dragon_to_right, {token}]") + move
    elif presenter.startswith("ring"):
        text = text.replace(
            dragon,
            f"turns w from winner over players where player is winner "
            f"until trick_pile is empty {{ offer to w one of [dragon_to_left, dragon_to_right, {token}] }}",
        ) + move
    else:
        name = _library_name(move + token)
        library = parse_library(f"library {name} {{\n{move.replace('quiet += 0', '')}}}", f"{name}.cardlang")
        monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({name}))
        monkeypatch.setattr("cardlang.resolve.load_library", lambda _: library)
        text = text.replace("game Tichu {", f"game Tichu {{\n  uses {name}", 1)
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(text, f"tichu-{token}-{presenter}-{row}.cardlang")
    assert f"move type `{token}` is spelled like the climb engine" in str(ei.value), str(ei.value)
    assert ei.value.diagnostic.span is not None


# A space built by hand: the checker refuses a move type spelled like a climb
# action, so no game reaches this. The action space still resolves by what
# minted an id, never by spelling, and these cells pin that it does.
_BY_HAND = ActionSpace(
    None,
    ["bid", "pass"],
    [("pass", None), ("pass", "hearts"), ("raise", None)],
    None,
    [],
    engine_names=frozenset({"pass"}),
)
_OFFERING_IDS = [aid for aid in range(_BY_HAND.num_distinct_actions) if _BY_HAND.block_of(aid) == "offering"]


@pytest.mark.parametrize("aid", _OFFERING_IDS, ids=[str(_BY_HAND.decode(a)) for a in _OFFERING_IDS])
def test_an_offering_id_resolves_by_what_minted_it(aid: int) -> None:
    """A move type's candidate encodes to its own id, stands for its move type,
    and is never matched by an engine action spelled like it.

    red under: drop `name not in self._engine_names` from `ActionSpace.encode`,
    or `move_named` from `ActionSpace.match`."""
    candidate = _BY_HAND.decode(aid)
    assert _BY_HAND.encode(candidate) == aid
    assert _BY_HAND.move_type_of(aid) == candidate[0]
    assert _BY_HAND.match(aid, [candidate]) == candidate
    engine_pass = _BY_HAND.encode("pass")
    assert _BY_HAND.move_type_of(engine_pass) is None
    if candidate[0] == "pass":
        with pytest.raises(ValueError):
            _BY_HAND.match(engine_pass, [candidate])


def test_a_nullary_offer_keeps_its_bare_name_id() -> None:
    """The runtime writes a nullary `offer` move as `(name, None)`, and the
    space numbers it by its bare name, which stands for the move type."""
    bid = _BY_HAND.encode("bid")
    assert _BY_HAND.encode(("bid", None)) == bid
    assert _BY_HAND.move_type_of(bid) == "bid"
    assert _BY_HAND.match(bid, [("bid", None)]) == ("bid", None)


def _ids_before_combinations(space: ActionSpace) -> range:
    stop = 0
    while stop < space.num_distinct_actions and space.block_of(stop) != "combination":
        stop += 1
    return range(stop)


@pytest.mark.parametrize("short_name", sorted(REGISTERED))
def test_move_type_of_names_exactly_the_ids_a_move_type_minted(short_name: str) -> None:
    """An offering id stands for its move type; a bare-name id for the offered
    move type it is, or for none where a climb engine minted it; a card or
    integer id for none. The combination block is a codec's arithmetic and
    stands for none (`encoding.verb_of` names it `COMBO_VERB`).

    red under: answer `move_type_of` from `verb_of` (every climb game's `pass`
    then stands for a move type)."""
    game, space = load(str(GAMES / REGISTERED[short_name]))
    move_types = {mt.name for mt in game.move_types}
    engines = {nd.combos_fn for nd in _walk(game) if isinstance(nd, n.ClimbRound)}
    tokens = {action for engine in engines for action in primitives.climb_actions(engine)}
    for aid in _ids_before_combinations(space):
        block = space.block_of(aid)
        named = space.move_type_of(aid)
        if block == "offering":
            assert named == space.verb_of(aid) and named in move_types
        elif block == "name":
            verb = space.verb_of(aid)
            assert named == (None if verb in tokens else verb)
            assert named is None or named in move_types
        else:
            assert named is None


# ---------------------------------------------------------------------------
# Consumers: the IR carries it; the runtime, encoding and views do not.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row", ROWS)
def test_the_ir_carries_the_row_only_where_it_is_written(row: str | None) -> None:
    game = check_dsl(_game("top_item", _move(row, False, None), "Offer.offering"), "mini.cardlang")
    move_types = ir.emit(game)["move_types"]
    assert isinstance(move_types, list)
    emitted = next(m for m in move_types if isinstance(m, dict) and m["name"] == "m")
    assert isinstance(emitted, dict)
    assert emitted.get("stake") == row
    assert ("stake" in emitted) is (row is not None)


_STAKE_LINE = re.compile(r"^\s*(?:" + "|".join(n.STAKES) + r")\s*$", re.MULTILINE)


def _unmarked(game_file: str, tmp_path: Path) -> str:
    """The witness game with its stake rows deleted, and nothing else."""
    text = (GAMES / game_file).read_text()
    assert _STAKE_LINE.search(text), f"{game_file} carries no stake row"
    out = tmp_path / game_file
    out.write_text(_STAKE_LINE.sub("", text))
    return str(out)


@pytest.mark.parametrize("game_file", ["tichu.cardlang", "pinochle.cardlang"])
def test_the_row_mints_no_action_id(game_file: str, tmp_path: Path) -> None:
    """red under: mint each staked move type's candidates twice, once per
    Stake, in `ActionSpace.for_game`'s offering block."""
    marked, _ = load(str(GAMES / game_file))
    bare, _ = load(_unmarked(game_file, tmp_path))
    a, b = ActionSpace.for_game(marked), ActionSpace.for_game(bare)
    assert a.num_distinct_actions == b.num_distinct_actions
    assert a.verbs() == b.verbs()
    # Every id before the combination block, which is a codec's arithmetic and
    # reads no move type (Tichu's is hundreds of millions of ids wide).
    stop = 0
    while stop < a.num_distinct_actions and a.block_of(stop) != "combination":
        stop += 1
    assert [a.to_string(i) for i in range(stop)] == [b.to_string(i) for i in range(stop)]


class _Enough(Exception):
    """Ends a line on a seat's behalf once the prefix compared is played."""


_PREFIX = 400


def test_the_row_enters_no_information_state(tmp_path: Path) -> None:
    """The first decisions of one line of Pinochle, played by the uniform draw
    at every seat, are the same with and without its rows, seen from every
    seat. A prefix, because no uniform Pinochle line reaches the end of the
    game (`tests/playout_policy.py`, its reference-policy row).

    red under: emit a move type's `stake` in the event `runtime/observe`
    announces for its play."""
    marked = str(GAMES / "pinochle.cardlang")
    bare = _unmarked("pinochle.cardlang", tmp_path)
    seen: dict[str, list[str]] = {marked: [], bare: []}

    def recording(path: str, seat: int) -> object:
        draw = UniformSeatPolicy(3)

        def pick(view: SeatView, legal: Sequence[int]) -> int:
            if len(seen[path]) >= _PREFIX:
                raise _Enough
            seen[path].append(f"{seat}\n{render_information_state(view)}")
            return draw(view, legal)

        return pick

    for path in (marked, bare):
        with pytest.raises(_Enough):
            LiveLine(path, 3).play({seat: recording(path, seat) for seat in range(4)})  # type: ignore[misc]
    assert seen[marked] == seen[bare]
    assert len(seen[marked]) == _PREFIX


# ---------------------------------------------------------------------------
# The reader: `ranked` declines a stake a plain move stands beside.
# ---------------------------------------------------------------------------

_KINDS: tuple[str | None, ...] = (None, *n.STAKES)
COMPOSITIONS = [c for k in range(1, len(_KINDS) + 1) for c in itertools.combinations(_KINDS, k)]
_BLOCK_SITES = {
    "name": "for each player p: offer to p one of [{moves}]",
    "ring": "turns t from 0 over all players until done >= 6 {{ offer to t one of [{moves}] }}",
    "offering-parameterized": "for each player p: offer to p one of [{moves}]",
}


def _composition_game(kinds: tuple[str | None, ...], site: str) -> str:
    param = "(s : Suit)" if site == "offering-parameterized" else ""
    names = [f"k_{kind or 'plain'}" for kind in kinds]
    moves = "\n".join(
        f"move_type {name}{param} {{ {kind or ''}\n effect {{ tally[actor] += 1  done += 1 }} }}"
        for name, kind in zip(names, kinds)
    )
    present = _BLOCK_SITES[site].format(moves=", ".join(names))
    return f"""
game Mini {{
  {_HEADER}
  phase p repeat until done >= 6 {{
    {present}
  }}
  winner: highest tally
}}
{moves}
"""


@pytest.mark.parametrize(
    ("kinds", "site"),
    list(itertools.product(COMPOSITIONS, _BLOCK_SITES)),
    ids=[f"{'+'.join(k or 'plain' for k in c)}-{s}" for c, s in itertools.product(COMPOSITIONS, _BLOCK_SITES)],
)
def test_ranked_answers_a_plain_move_wherever_one_is_offered(
    kinds: tuple[str | None, ...], site: str, tmp_path: Path
) -> None:
    path = tmp_path / "mini.cardlang"
    path.write_text(_composition_game(kinds, site))
    game, space = load(str(path))
    asked = 0

    def seat(s: int) -> object:
        ranked = RankedSeatPolicy(SeatBinding(game, space, s, 7))
        draw = UniformSeatPolicy(7)

        def pick(view: SeatView, legal: Sequence[int]) -> int:
            nonlocal asked
            picked = ranked(view, legal)
            verbs = {space.verb_of(aid) for aid in legal}
            if None in kinds:
                assert space.verb_of(picked) == "k_plain", f"{space.verb_of(picked)} over k_plain"
            else:
                assert picked == draw(view, legal), "a decision with nothing plain is drawn"
            assert verbs
            asked += 1
            return picked

        return pick

    LiveLine(str(path), 7).play({s: seat(s) for s in range(2)})  # type: ignore[misc]
    assert asked, "no decision was reached"


_SITE_BLOCK = {"name": "name", "ring": "name", "offering-parameterized": "offering"}


def test_the_blocks_that_name_a_move_type_are_the_blocks_that_decline_stakes() -> None:
    """The blocks whose ids stand for a move type, derived over every
    registered game through `move_type_of`, are exactly the blocks `ranked`
    declines stakes in and exactly the blocks the disposition grid presents.

    red under: set `ranked.DISPOSITIONS["offering"]` to "ranked"."""
    naming: set[str] = set()
    for file_name in REGISTERED.values():
        _, space = load(str(GAMES / file_name))
        naming |= {space.block_of(aid) for aid in _ids_before_combinations(space) if space.move_type_of(aid) is not None}
    assert naming == {block for block, disposition in DISPOSITIONS.items() if disposition == "declines stakes"}
    assert naming == set(_SITE_BLOCK.values()) and set(_SITE_BLOCK) == set(_BLOCK_SITES)


# ---------------------------------------------------------------------------
# The witnesses, played by `ranked` at every seat.
# ---------------------------------------------------------------------------


def _ranked_table(path: str, seed: int) -> list[str]:
    game, space = load(path)
    picked: list[str] = []

    def seat(s: int) -> object:
        ranked = RankedSeatPolicy(SeatBinding(game, space, s, seed))

        def pick(view: SeatView, legal: Sequence[int]) -> int:
            aid = ranked(view, legal)
            picked.append(space.verb_of(aid))
            return aid

        return pick

    LiveLine(path, seed).play({s: seat(s) for s in range(game.players.count)})  # type: ignore[misc]
    return picked


def test_a_ranked_tichu_table_plays_to_the_end_and_never_calls() -> None:
    """Termination by declining, not competence: no seat calls.

    red under: move the `wager` row from `call_tichu` to `no_call` in
    docs/games/tichu.cardlang (the table then calls at every poll it may and
    runs to its declared length)."""
    picked = _ranked_table(str(GAMES / "tichu.cardlang"), 0)
    assert "call_tichu" not in picked and "call_grand_tichu" not in picked
    assert "no_call" in picked and "decline_grand" in picked


@pytest.mark.parametrize("seed", range(3))
def test_a_ranked_pinochle_table_plays_to_the_end_and_never_concedes(seed: int) -> None:
    """red under: move the `concession` row from `throw_in` to `play_on` in
    docs/games/pinochle.cardlang."""
    picked = _ranked_table(str(GAMES / "pinochle.cardlang"), seed)
    assert "throw_in" not in picked and "submit_bid" not in picked
    assert "play_on" in picked
