"""The Diagnostic Codes: every code is shipped, stable, and raised by a witness.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every member of `cardlang.diagnostic_codes.Code` is told by
                 an executed witness -- a rejection case, a game or library
                 text checked here, a command line run, or a runtime refusal
                 rendered -- and no code shipped is renamed or removed: the
                 blessed list and the registry are one set.
domain:          the registry crossed with one witness per member, the axis
                 derived from `Code` itself, so a member added without a
                 witness is a red cell rather than an unlisted one. The
                 witnesses reach the checker through `check_dsl`,
                 `parse_library` and `check_source`, the command line
                 through `cardlang.cli.main`, and the runtime through
                 `cardlang.records.refusal_diagnostic`.
registry:        the axis -- `Code`; the blessed spellings -- `SHIPPED`;
                 the rejection corpus -- tests/test_rejections.py::case_paths.
held by:         Derived and Pinned. A code's spelling is a string a tool
                 keys on outside the type checker, so the blessed list holds
                 it; that every refusal carries a code is held a rung higher,
                 by `Diagnostic.code` being a required field.
does not prove:  that every report site sharing a code asks for the same
                 kind of fix. One witness per code shows the code is told;
                 the naming review of the registry, read whole, is what
                 judges a site's code.
"""

from __future__ import annotations

import contextlib
import io
import json
import random
import re
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
from tests.test_rejections import REJECTIONS_DIR
from tests.resolver_package import patch_resolver

_ROOT = Path(__file__).resolve().parent.parent

# Every code ever shipped. A code is never removed or renamed once it is
# here: a tool may key on it.
SHIPPED: tuple[str, ...] = (
    "syntax-error",
    "misspelled-keyword",
    "wrong-spelling",
    "one-game-per-file",
    "one-fenced-block",
    "wrong-file-extension",
    "unknown-command",
    "unreadable-file",
    "unknown-name",
    "unknown-zone",
    "unknown-state-variable",
    "unknown-function",
    "unknown-procedure",
    "unknown-rule",
    "unknown-move-type",
    "unknown-phase",
    "unknown-mode",
    "unknown-outcome",
    "unknown-rank",
    "unknown-suit",
    "unknown-deck",
    "unknown-library",
    "unknown-type",
    "unknown-zone-type",
    "unknown-index-domain",
    "unknown-field",
    "unknown-turn-direction",
    "unknown-round-function",
    "unknown-play-shape",
    "unknown-primitive",
    "unknown-board",
    "reserved-word",
    "name-taken",
    "written-twice",
    "wrong-sort-of-name",
    "missing-declaration",
    "unused-declaration",
    "has-no-effect",
    "conflicting-clauses",
    "out-of-place",
    "not-yet-supported",
    "out-of-range",
    "pieces-are-not-cards",
    "deck-too-small",
    "board-shape",
    "type-mismatch",
    "untyped-value",
    "wrong-argument-count",
    "wrong-argument",
    "wrong-signature",
    "wrong-subscript",
    "type-not-allowed-here",
    "constant-condition",
    "needs-parentheses",
    "out-of-scope",
    "no-player-acting",
    "reads-beyond-parameters",
    "recursive-function",
    "answer-reads-beyond-the-card",
    "answer-calls-later-answer",
    "decides-on-hidden-cards",
    "wrong-zone-visibility",
    "hosted-poll-reads-unpublished-state",
    "not-writable",
    "library-requirement-unmet",
    "requirement-mismatch",
    "requirement-matches-several",
    "outside-library-contract",
    "library-reaches-one-game",
    "bad-requires-row",
    "requires-what-is-provided",
    "library-not-yet-proven",
    "rule-never-consulted",
    "needs-a-trick-round",
    "mode-pairing",
    "climb-round-queries",
    "choose-integer-bounds",
    "teams-must-partition-seats",
    "use-winner-not-loser",
    "unrankable-winner-target",
    "ranking-incomplete",
    "catalogue-row-names-no-play",
    "ambiguous-play-shape",
    "card-play-parameters",
    "deal-distribution",
    "wrong-zone-shape",
    "wrong-primitive-type",
    "missing-outcome-arm",
    "outcome-read-before-produced",
    "refused-during-play",
    "game-error-raised",
    "engine-gap",
    "incomplete-installation",
    "unregistrable-game",
)


def test_the_blessed_list_is_the_registry() -> None:
    """red under: a member renamed in `cardlang/diagnostic_codes.py`."""
    assert {code.slug for code in Code} == set(SHIPPED)
    assert len(SHIPPED) == len(set(SHIPPED))


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
    Code.PIECES_ARE_NOT_CARDS: _case("cards_names_a_piece_set"),
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
