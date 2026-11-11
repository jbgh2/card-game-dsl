"""The Diagnostic Codes: every code is shipped, stable, and raised by a witness.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every member of `cardlang.diagnostic_codes.Code` is told by
                 an executed witness -- a rejection case, a game or library
                 text checked here, a command line run, or a runtime refusal
                 rendered; no code shipped is renamed, removed or given
                 another meaning: the blessed spellings and meanings and the
                 registry are one mapping; and every rejection case tells,
                 in order, the codes its `.codes` golden lists.
domain:          the registry crossed with one witness per member, the axis
                 derived from `Code` itself, so a member added without a
                 witness is a red cell rather than an unlisted one; and the
                 whole rejection corpus, every case with its code golden.
                 The witnesses reach the checker through `check_dsl`,
                 `parse_library` and `check_source`, the command line
                 through `cardlang.cli.main`, and the runtime through
                 `cardlang.records.refusal_diagnostic`.
registry:        the axis -- `Code`; the blessed spellings and meanings --
                 `SHIPPED`; the rejection corpus --
                 tests/test_rejections.py::case_paths.
held by:         Derived and Pinned. A code's spelling and meaning are
                 strings a tool keys on outside the type checker, so the
                 blessed mapping holds them; that every refusal carries a
                 code is held a rung higher, by `Diagnostic.code` being a
                 required field.
does not prove:  that a report site no rejection case reaches keeps its code:
                 such a site can move to another code with every pin here
                 green, unless it is its code's one witness. Measured
                 2026-11-11, by executing the corpus (`python -m
                 tests.test_diagnostic_codes`): 405 of 567 coded report sites. Nor that every
                 site sharing a code asks for the same kind of fix; the
                 naming review of the registry, read whole, judges that.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import random
import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import cardlang.resolve as resolve
from cardlang import cli, libraries, pipeline
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Diagnostic, DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl, check_markdown, check_source
from cardlang.records import RuntimeRefusal, refusal_diagnostic
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import (
    GameDescriptionError,
    GameRegistrationError,
    InstallationError,
    ShadowGuardError,
)
from cardlang.runtime.state import IllegalMove
from tests.test_rejections import REJECTIONS_DIR, case_paths
from tools.dead_surface import start_for
from tests.resolver_package import patch_resolver

_ROOT = Path(__file__).resolve().parent.parent

# Every code ever shipped, with its meaning. A code is never removed or
# renamed once it is here, and its meaning changes only by a deliberate
# edit of this mapping: a tool may key on either.
SHIPPED: dict[str, str] = {
    "syntax-error": "the text does not read as the language; fix it where the message points",
    "misspelled-keyword": "a word nearly spells a keyword the language expects there; write the keyword",
    "wrong-spelling": "the language spells this construct another way; write the spelling the message gives",
    "one-game-per-file": "a source holds exactly one `game { }` block; add it, or move the others to their own files",
    "one-fenced-block": "a Markdown game file holds its game in exactly one fenced block",
    "wrong-file-extension": "a game file's name ends in an extension the checker reads; rename the file",
    "unknown-command": "the first word names no command and no file; write a command or a path",
    "unreadable-file": "the file named cannot be read as text; name a readable game file",
    "unknown-name": "a name nothing in scope declares, refused where the checker cannot tell which sort of name was meant; read the suggestions, spell a declared name, or declare it",
    "unknown-zone": "a zone no `zones { }` entry declares; spell a declared zone, or declare it",
    "unknown-state-variable": "a state variable no `state { }` block declares; spell a declared one, or declare it",
    "unknown-function": "a function neither the game nor the language defines; spell a defined one, or define it",
    "unknown-procedure": "a procedure the game does not define; spell a defined one, or define it",
    "unknown-rule": "a rule no definition or library provides; spell a defined rule, or define it",
    "unknown-move-type": "a move type the game does not declare; spell a declared one, or declare it",
    "unknown-phase": "a phase that is not where the construct looks for it; name a phase that is",
    "unknown-mode": "a mode that is not a sibling of this phase's modes; name one that is",
    "unknown-outcome": "an outcome phase or case the game does not declare; name a declared one",
    "unknown-rank": "a rank the game's deck does not have; write one of its ranks",
    "unknown-suit": "a suit the game's deck does not have; write one of its suits",
    "unknown-deck": "a deck or piece set the language does not ship; name a shipped one",
    "unknown-library": "a family library that does not exist; name one in docs/libraries/",
    "unknown-type": "a type name the language does not have in that position; write one it has",
    "unknown-zone-type": "a zone type the language does not have; write one it has",
    "unknown-index-domain": "an index domain, owner or position domain nothing declares; name one that exists",
    "unknown-field": "a field the value does not have; read one of its fields, or read it another way",
    "unknown-turn-direction": "a turn direction the language does not have; write one it has",
    "unknown-round-function": "a round names a winner or predicate the language does not have; name one it has",
    "unknown-play-shape": "a play shape no row of the game's catalogue labels; write a row's label",
    "unknown-primitive": "a `primitives` entry nothing implements; name an implemented Primitive",
    "unknown-board": "a board the language does not have; write a board it has",
    "reserved-word": "the name is a word the language reserves; pick another name",
    "name-taken": "two things share one name, or one hides another; rename one",
    "written-twice": "one thing is written more than once; keep one",
    "wrong-sort-of-name": "the name is of another sort than the position takes; use a name of the right sort",
    "missing-declaration": "something reads a declaration the game does not make; add it",
    "unused-declaration": "a declaration nothing reaches; use it, or delete it",
    "has-no-effect": "something written changes nothing; drop it, or write what was meant",
    "conflicting-clauses": "two clauses cannot stand together; keep one of them",
    "out-of-place": "a clause or statement written where it cannot stand; move it where it belongs",
    "not-yet-supported": "the language cannot express this yet; write the game another way until it can",
    "out-of-range": "a number outside the values the position allows; write one inside them",
    "pieces-are-not-cards": "a card's rank, suit or points read in a game played with pieces",
    "deck-too-small": "the deck holds fewer cards than a hand deals from it",
    "board-shape": "a board declaration the board cannot be laid out from; fix the board's shape",
    "type-mismatch": "a value of another type than the position needs; write a value of that type",
    "untyped-value": "a value whose type the checker cannot know where an exact type is needed; make its type plain",
    "wrong-argument-count": "a call, a rule or a zone type is given more or fewer arguments than it takes",
    "wrong-argument": "an argument of a shape the position does not take; write the shape the message gives",
    "wrong-signature": "a definition's parameters or result differ from what its role requires",
    "wrong-subscript": "a zone or variable subscripted the wrong way, or not subscripted where it must be",
    "type-not-allowed-here": "a type the language allows only in another position; spell it there",
    "constant-condition": "a condition that is always true or always false; write the test that was meant",
    "needs-parentheses": "the text reads another way than it seems; add parentheses to say which",
    "out-of-scope": "something read where it does not exist; read it where it is declared, or pass it in",
    "no-player-acting": "the acting player is named, or a decision made, where no player is acting",
    "reads-beyond-parameters": "a function or procedure reads what its parameters do not pass it",
    "recursive-function": "a function calls itself, directly or through others",
    "answer-reads-beyond-the-card": "an answer the engine asks of a card reads more than the card and public state",
    "answer-calls-later-answer": "a Trick Order function calls one that comes after it in the Trick Order",
    "decides-on-hidden-cards": "a seat must check or pick from cards it cannot see; read cards it sees, or announce them",
    "wrong-zone-visibility": "a zone's type hides cards that the construct needs every seat, or its owner, to see",
    "hosted-poll-reads-unpublished-state": "a Hosted Poll reads Round State that is not yet published",
    "not-writable": "the target is not a state variable this text may write",
    "library-requirement-unmet": "the game lacks what a library it uses requires; add it to the game",
    "requirement-mismatch": "the game declares what a library requires, but not as the library requires it",
    "requirement-matches-several": "a library requirement matches several of the game's declarations; keep one",
    "outside-library-contract": "library text reads a name it neither defines nor requires; define it, or require it",
    "library-reaches-one-game": "library text names what belongs to one game; take it as a parameter or a requirement",
    "bad-requires-row": "a `requires` row the library cannot ask for in that form; write the row the message gives",
    "requires-what-is-provided": "a library requires what a library already provides or defines; drop one of the two",
    "library-not-yet-proven": "no game yet checks clean reaching this library text, so its refusal stands in the library's file",
    "rule-never-consulted": "a rule no decision ever asks; constrain a move type a trick round offers, or write the condition elsewhere",
    "needs-a-trick-round": "a construct only a trick round reads, in a game or phase with none",
    "mode-pairing": "modes whose transitions do not pair one condition with its far side",
    "climb-round-queries": "a climbing round's queries that do not belong together; name one engine's pair",
    "choose-integer-bounds": "a `choose integer` whose bounds offer no value, or no fixed ceiling",
    "teams-must-partition-seats": "`teams:` must put every seat on exactly one team",
    "use-winner-not-loser": "`loser:` cannot decide this game's result; rank a score with `winner:`",
    "unrankable-winner-target": "`winner:` ranks something that is not a score each player or team holds",
    "ranking-incomplete": "a ranking leaves out ranks or suits it must order; list them all",
    "catalogue-row-names-no-play": "a combination catalogue row no cards of the deck can make",
    "ambiguous-play-shape": "one play fits two rows of the catalogue; settle it in the rows",
    "card-play-parameters": "a card play's parameters or offering would make two plays look alike",
    "deal-distribution": "an even deal written with an amount or destination it cannot distribute",
    "wrong-zone-shape": "a single zone where a zone per player is needed, or the reverse",
    "wrong-primitive-type": "a `primitives` entry spells a type no Primitive implementation takes",
    "missing-outcome-arm": "a `produces:` block leaves an outcome case unhandled",
    "outcome-read-before-produced": "an outcome is consumed before the phase producing it has run",
    "refused-during-play": "a rule only a playout reaches refused the game",
    "game-error-raised": "the game's own `error(...)` refused a move no player was offered",
    "engine-gap": "the engine refused what an earlier check should have refused; the engine must change",
    "incomplete-installation": "the checkout is missing files the engine loads; reinstall it",
    "unregistrable-game": "a game file offered for registration cannot be registered by that name",
}


def test_the_blessed_list_is_the_registry() -> None:
    """red under: a member renamed, or its meaning rewritten, in
    `cardlang/diagnostic_codes.py`."""
    assert {code.slug: code.meaning for code in Code} == SHIPPED


def test_every_code_is_spelled_in_words() -> None:
    """A slug is lower-case words joined by hyphens, a meaning one ASCII
    line. red under: a member spelled `UNKNOWN_ZONE = ("UnknownZone", ...)`."""
    for code in Code:
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", code.slug), code
        assert code.meaning and code.meaning.isascii() and "\n" not in code.meaning, code
    assert len({code.slug for code in Code}) == len(Code)


# --- the witnesses ----------------------------------------------------------

Tells = Callable[[pytest.MonkeyPatch, Path], frozenset[Code]]


def _told(run: Callable[[], object]) -> frozenset[Code]:
    with pytest.raises(DiagnosticError) as excinfo:
        run()
    return frozenset(told.diagnostic.code for told in excinfo.value.told)


def _case(name: str) -> Tells:
    """A rejection case, checked as the corpus checks it."""
    path = REJECTIONS_DIR / f"{name}.cardlang"

    def tells(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
        return _told(lambda: check_dsl(path.read_text(), f"{name}.cardlang"))

    return tells


_LIBRARY = "probe_lib"
_HOST = """game Host {
  players: 2
  uses probe_lib
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase p { for each player q: score[q] := 0 }
  winner: highest score
}
"""


def _using(library_body: str, definitions: str = "") -> Tells:
    """A game using a family library no game proves, read from `library_body`."""

    def tells(mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
        library = parse_library(
            f"library {_LIBRARY} {{\n{library_body}\n}}\n", f"docs/libraries/{_LIBRARY}.cardlang"
        )
        patch_resolver(mp, "library_names", lambda: frozenset({_LIBRARY}))
        patch_resolver(mp, "load_library", lambda name: library)
        return _told(lambda: check_dsl(_HOST + definitions, "host.cardlang"))

    return tells


def _cli(argv: Callable[[Path], list[str]]) -> Tells:
    """A command line run with `--json`, read back from its Record Envelope."""

    def tells(_mp: pytest.MonkeyPatch, tmp: Path) -> frozenset[Code]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main([*argv(tmp), "--json"])
        return frozenset(
            next(c for c in Code if c.slug == r["code"])
            for r in json.loads(out.getvalue())["diagnostics"]
        )

    return tells


def _unknown_command(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
    refused = cli._normalize(["chek", "no-such-file.cardlang"])
    assert isinstance(refused, Diagnostic)
    return frozenset({refused.code})


def _wrong_extension(_mp: pytest.MonkeyPatch, tmp: Path) -> frozenset[Code]:
    path = tmp / "game.txt"
    path.write_text("game g { }\n")
    return _told(lambda: check_source(path))


def _no_fenced_block(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
    return _told(lambda: check_markdown("# A game\n\nNo block here.\n", "game.md"))


def _playout(fixture: str) -> Tells:
    """A fixture played out, its refusal told as the command line tells it."""

    def tells(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
        game = check_source(_ROOT / "tests" / "fixtures" / fixture)
        with pytest.raises((GameDescriptionError, IllegalMove)) as excinfo:
            play_game(game, random.Random(0))
        refused = excinfo.value
        assert isinstance(refused, (GameDescriptionError, IllegalMove))
        return frozenset({refusal_diagnostic(refused).diagnostic.code})

    return tells


def _broken_checkout(mp: pytest.MonkeyPatch, tmp: Path) -> frozenset[Code]:
    def missing() -> Path:
        raise InstallationError("the family library directory is not in this checkout")

    mp.setattr(libraries, "_libraries_dir", missing)
    libraries.library_names.cache_clear()
    pipeline._check.cache_clear()
    try:
        return _cli(lambda _tmp: ["check", str(_ROOT / "docs" / "games" / "kuhn-poker.cardlang")])(mp, tmp)
    finally:
        mp.undo()
        libraries.library_names.cache_clear()
        pipeline._check.cache_clear()


def _constructed(made: Callable[[], RuntimeRefusal]) -> Tells:
    """A refusal no clean run raises, told through the one converter: an
    engine gap is a leaked Owner Guard, and registration needs the OpenSpiel
    extra."""

    def tells(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
        return frozenset({refusal_diagnostic(made()).diagnostic.code})

    return tells


WITNESSES: dict[Code, Tells] = {
    Code.SYNTAX_ERROR: _case("legal_moves_in_mode_body"),
    Code.MISSPELLED_KEYWORD: _case("syntax_unknown_clause_keyword"),
    Code.WRONG_SPELLING: _case("card_points_colon"),
    Code.ONE_GAME_PER_FILE: _case("no_game_block"),
    Code.UNKNOWN_NAME: _case("direction_literal"),
    Code.UNKNOWN_ZONE: _case("code_unknown_zone"),
    Code.UNKNOWN_STATE_VARIABLE: _case("primitives_scoped_read_on_a_zone"),
    Code.UNKNOWN_FUNCTION: _case("call_evicted_trace_emitter_coup"),
    Code.UNKNOWN_PROCEDURE: _case("code_unknown_procedure"),
    Code.UNKNOWN_RULE: _case("active_rules_undefined_rule"),
    Code.UNKNOWN_MOVE_TYPE: _case("constrains_unknown_move_type"),
    Code.UNKNOWN_PHASE: _case("primitives_scoped_read_no_such_phase"),
    Code.UNKNOWN_MODE: _case("transition_to_non_sibling"),
    Code.UNKNOWN_OUTCOME: _case("code_unknown_outcome"),
    Code.UNKNOWN_RANK: _case("ranking_mixed_convention_and_ranks"),
    Code.UNKNOWN_SUIT: _case("round_trump_unknown_suit"),
    Code.UNKNOWN_DECK: _case("pieces_unknown_set"),
    Code.UNKNOWN_LIBRARY: _case("code_unknown_library"),
    Code.UNKNOWN_TYPE: _case("dir_parameter_on_morris9"),
    Code.UNKNOWN_ZONE_TYPE: _case("unknown_zone_type"),
    Code.UNKNOWN_INDEX_DOMAIN: _case("positions_for_each"),
    Code.UNKNOWN_FIELD: _case("code_unknown_field"),
    Code.UNKNOWN_TURN_DIRECTION: _case("unknown_direction"),
    Code.UNKNOWN_ROUND_FUNCTION: _case("code_unknown_round_function"),
    Code.UNKNOWN_PLAY_SHAPE: _case("code_unknown_play_shape"),
    Code.UNKNOWN_PRIMITIVE: _case("code_unknown_primitive"),
    Code.UNKNOWN_BOARD: _case("board_unknown_family"),
    Code.RESERVED_WORD: _case("reserved_word_zone"),
    Code.NAME_TAKEN: _case("binder_shadows_provided_state"),
    Code.WRITTEN_TWICE: _case("board_duplicate_clause"),
    Code.WRONG_SORT_OF_NAME: _case("primitives_round_slot_name"),
    Code.MISSING_DECLARATION: _case("board_with_cards"),
    Code.UNUSED_DECLARATION: _case("code_unknown_procedure"),
    Code.HAS_NO_EFFECT: _case("applies_when_always"),
    Code.CONFLICTING_CLAUSES: _case("morris_men_beside_cards"),
    Code.OUT_OF_PLACE: _case("move_stake_after_when"),
    Code.NOT_YET_SUPPORTED: _case("movement_visibility_override"),
    Code.OUT_OF_RANGE: _case("neighbors_past_the_end"),
    Code.PIECES_ARE_NOT_CARDS: _case("code_pieces_are_not_cards"),
    Code.DECK_TOO_SMALL: _case("deck_over_capacity"),
    Code.BOARD_SHAPE: _case("board_bad_args"),
    Code.TYPE_MISMATCH: _case("board_cell_state_var"),
    Code.UNTYPED_VALUE: _case("boolean_position_laundered_any"),
    Code.WRONG_ARGUMENT_COUNT: _case("arrival_winner_missing_trump"),
    Code.WRONG_ARGUMENT: _case("code_wrong_argument"),
    Code.WRONG_SIGNATURE: _case("primitives_signature_mismatch"),
    Code.WRONG_SUBSCRIPT: _case("positions_bare_family_reference"),
    Code.TYPE_NOT_ALLOWED_HERE: _case("collection_at_a_function_parameter"),
    Code.CONSTANT_CONDITION: _case("code_constant_condition"),
    Code.NEEDS_PARENTHESES: _case("code_needs_parentheses"),
    Code.OUT_OF_SCOPE: _case("primitives_scoped_read_called_outside"),
    Code.NO_PLAYER_ACTING: _case("code_no_player_acting"),
    Code.READS_BEYOND_PARAMETERS: _case("code_reads_beyond_parameters"),
    Code.RECURSIVE_FUNCTION: _case("code_recursive_function"),
    Code.ANSWER_READS_BEYOND_THE_CARD: _case("code_answer_reads_beyond_the_card"),
    Code.ANSWER_CALLS_LATER_ANSWER: _case("code_answer_calls_later_answer"),
    Code.DECIDES_ON_HIDDEN_CARDS: _case("hidden_read_blind_draw"),
    Code.WRONG_ZONE_VISIBILITY: _case("implicit_pool_hidden_from_owner"),
    Code.HOSTED_POLL_READS_UNPUBLISHED_STATE: _case("hosted_poll_card_movement"),
    Code.NOT_WRITABLE: _case("code_not_writable"),
    Code.REQUIREMENT_MISMATCH: _case("contract_result_mismatch"),
    Code.RULE_NEVER_CONSULTED: _case("constrains_game_move_type"),
    Code.NEEDS_A_TRICK_ROUND: _case("code_needs_a_trick_round"),
    Code.MODE_PAIRING: _case("code_mode_pairing"),
    Code.CLIMB_ROUND_QUERIES: _case("code_climb_round_queries"),
    Code.CHOOSE_INTEGER_BOUNDS: _case("choose_excluding_empties_range"),
    Code.TEAMS_MUST_PARTITION_SEATS: _case("code_teams_must_partition_seats"),
    Code.USE_WINNER_NOT_LOSER: _case("elimination_one_seat"),
    Code.UNRANKABLE_WINNER_TARGET: _case("stop_result_ranking_unindexed"),
    Code.RANKING_INCOMPLETE: _case("ranking_convention_non_french_deck"),
    Code.CATALOGUE_ROW_NAMES_NO_PLAY: _case("code_catalogue_row_names_no_play"),
    Code.AMBIGUOUS_PLAY_SHAPE: _case("code_ambiguous_play_shape"),
    Code.CARD_PLAY_PARAMETERS: _case("code_card_play_parameters"),
    Code.DEAL_DISTRIBUTION: _case("code_deal_distribution"),
    Code.WRONG_ZONE_SHAPE: _case("deal_to_each_subscripted"),
    Code.WRONG_PRIMITIVE_TYPE: _case("primitives_collection_bare_constructor"),
    Code.MISSING_OUTCOME_ARM: _case("code_missing_outcome_arm"),
    Code.OUTCOME_READ_BEFORE_PRODUCED: _case("code_outcome_read_before_produced"),
    Code.ONE_FENCED_BLOCK: _no_fenced_block,
    Code.WRONG_FILE_EXTENSION: _wrong_extension,
    Code.UNKNOWN_COMMAND: _unknown_command,
    Code.UNREADABLE_FILE: _cli(lambda tmp: ["check", str(tmp / "missing.cardlang")]),
    Code.LIBRARY_REQUIREMENT_UNMET: _using("requires { probe_s : Integer }\nfunction probe_fn() = probe_s"),
    Code.REQUIREMENT_MATCHES_SEVERAL: _using(
        "requires { probe_f(c : Card) : Boolean }",
        "function probe_f(c : Card) = true\nfunction probe_f(c : Card) = false\n",
    ),
    Code.OUTSIDE_LIBRARY_CONTRACT: _using("function probe_fn() = probe_undeclared"),
    Code.LIBRARY_REACHES_ONE_GAME: _using(
        "requires { hand[player] : Hand<player> }\nfunction probe_fn() = number of cards in hand[0]"
    ),
    Code.BAD_REQUIRES_ROW: _using("requires { probe_z : Integer<player> }"),
    Code.REQUIRES_WHAT_IS_PROVIDED: _using("state { claimed : Integer = 0 }\nrequires { claimed : Integer }"),
    # The library no game uses refuses in its own file, beside the warning.
    Code.LIBRARY_NOT_YET_PROVEN: _using("function probe_fn() = probe_undeclared"),
    Code.REFUSED_DURING_PLAY: _playout("empty_zone_choice.cardlang"),
    Code.GAME_ERROR_RAISED: _playout("rule_refuses_every_card.cardlang"),
    Code.ENGINE_GAP: _constructed(lambda: ShadowGuardError("resolve", "a leaked refusal")),
    Code.INCOMPLETE_INSTALLATION: _broken_checkout,
    Code.UNREGISTRABLE_GAME: _constructed(lambda: GameRegistrationError("two files claim one short name")),
}


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            c, marks=[pytest.mark.expects_shadow_guard] if c is Code.ENGINE_GAP else [], id=c.slug
        )
        for c in Code
    ],
)
def test_every_code_has_a_witness_that_tells_it(
    code: Code, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    witness = WITNESSES.get(code)
    assert witness is not None, f"`{code.slug}` has no witness"
    assert code in witness(monkeypatch, tmp_path)


# --- every rejection case's codes, a golden beside its text ------------------

# A deliberate, reviewed act, as the text goldens' bless is
# (tests/test_rejections.py): `CODES_BLESS=1 pytest -q tests/test_diagnostic_codes.py`.
_BLESS = os.environ.get("CODES_BLESS") == "1"


def _case_codes(path: Path) -> list[str]:
    """The codes a rejection case tells, in the order the text prints them."""
    name = path.relative_to(REJECTIONS_DIR).with_suffix("").as_posix()
    with pytest.raises(DiagnosticError) as excinfo:
        if start_for(path) == "library":
            parse_library(path.read_text(), f"{name}.cardlang")
        else:
            check_dsl(path.read_text(), f"{name}.cardlang")
    return [told.diagnostic.code.slug for told in excinfo.value.told]


@pytest.mark.parametrize(
    "path", case_paths(), ids=lambda p: p.relative_to(REJECTIONS_DIR).as_posix()
)
def test_a_case_tells_the_codes_its_golden_lists(path: Path) -> None:
    """red under: a site any rejection case reaches moved to another code."""
    golden = path.with_suffix(".codes")
    told = "".join(f"{slug}\n" for slug in _case_codes(path))
    if _BLESS:
        golden.write_text(told)
        return
    assert told == golden.read_text(), (
        f"{golden.relative_to(_ROOT)}: the case's codes moved -- inspect the change, "
        "then re-run with CODES_BLESS=1 if it is intended"
    )


def test_every_case_has_a_code_golden_and_every_golden_a_case() -> None:
    cases = {p.with_suffix("") for p in case_paths()}
    goldens = {
        p.with_suffix("")
        for p in [*REJECTIONS_DIR.glob("*.codes"), *(REJECTIONS_DIR / "libraries").glob("*.codes")]
    }
    assert cases == goldens


# --- the sites the corpus reaches, measured by running it -------------------


def _report_sites() -> list[tuple[str, int, int]]:
    """Every coded report site in `cardlang/` but the bag's own: file and lines."""
    sites: list[tuple[str, int, int]] = []
    for path in sorted((_ROOT / "cardlang").rglob("*.py")):
        rel = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and any(k.arg == "code" for k in node.keywords)
                and rel != "cardlang/diagnostics.py"
            ):
                sites.append((rel, node.lineno, node.end_lineno or node.lineno))
    return sites


def reached_sites() -> tuple[int, int]:
    """How many report sites the rejection corpus executes, of how many."""
    from cardlang import diagnostics

    calls: set[tuple[str, int]] = set()

    def recording(fn: Callable[..., object]) -> Callable[..., object]:
        def inner(*args: object, **kwargs: object) -> object:
            frame = sys._getframe(1)
            calls.add((frame.f_code.co_filename, frame.f_lineno))
            return fn(*args, **kwargs)

        return inner

    originals = {
        name: getattr(diagnostics.DiagnosticBag, name) for name in ("error", "unknown")
    }
    original_init = diagnostics.Diagnostic.__init__
    try:
        for name, fn in originals.items():
            setattr(diagnostics.DiagnosticBag, name, recording(fn))
        setattr(diagnostics.Diagnostic, "__init__", recording(original_init))
        pipeline._check.cache_clear()
        for path in case_paths():
            try:
                _case_codes(path)
            except BaseException:  # noqa: BLE001 - a case that checks clean is not counted
                pass
    finally:
        for name, fn in originals.items():
            setattr(diagnostics.DiagnosticBag, name, fn)
        setattr(diagnostics.Diagnostic, "__init__", original_init)
    sites = _report_sites()
    reached = {
        site for site in sites for filename, line in calls
        if filename == str(_ROOT / site[0]) and site[1] <= line <= site[2]
    }
    return len(reached), len(sites)


if __name__ == "__main__":
    reached, total = reached_sites()
    print(f"{total - reached} of {total} report sites reached by no rejection case")
