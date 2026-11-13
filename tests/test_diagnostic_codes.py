"""The Diagnostic Codes: every code is shipped, stable, and raised by a witness.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every member of `cardlang.diagnostic_codes.Code` is told by
                 an executed witness -- a rejection case, a game or library
                 text checked here, a command line run, or a runtime refusal
                 rendered; no code shipped is renamed, removed or given
                 another meaning: the blessed spellings and meanings and the
                 registry are one mapping; every rejection case tells, in
                 order, the codes its `.codes` golden lists; every
                 `name-taken` and `written-twice` site tells the code of the
                 corrective act its sentence asks for; each misuse the board
                 registry refuses at check time, and each refusal of a family library's
                 `requires` rows `REQUIRES_ROWS` lists, tells the code of its
                 fix; and no code's
                 name uses a reserved word of the glossary outside an
                 approved compound of that word's own row, singular or
                 plural; the approved compounds are the ones each reserved
                 entry marks in `compounds:`, and a row approving its bare
                 word marks it.
domain:          the registry crossed with one witness per member, the axis
                 derived from `Code` itself, so a member added without a
                 witness is a red cell rather than an unlisted one; the whole
                 rejection corpus, every case with its code golden; every use
                 of `Code.NAME_TAKEN` and `Code.WRITTEN_TWICE` in `cardlang/`,
                 scraped, each matched to exactly one row of
                 `NAME_PAIR_SITES`; every `BoardMisuse`; the `requires`-row
                 refusals listed by hand in `REQUIRES_ROWS`, each reached
                 through a crafted family library a game uses, since the
                 library rejection corpus is refused by `parse_library`
                 alone, which runs no family-library check; and the registry
                 crossed with the reserved
                 entries of docs/glossary/. The witnesses reach the checker
                 through `check_dsl`, `parse_library`, `check_source` and the
                 standard library's own loader, the command line through
                 `cardlang.cli.main`, and the runtime through
                 `cardlang.records.refusal_diagnostic`.
registry:        the axis -- `Code`; the blessed spellings and meanings --
                 `SHIPPED`; the rejection corpus --
                 tests/test_rejections.py::case_paths; the board misuses --
                 `cardlang.stdlib.boards.BoardMisuse`; the reserved words and
                 their compounds -- docs/glossary/, read by
                 tools/glossary_index.py.
held by:         Derived and Pinned. A code's spelling and meaning are
                 strings a tool keys on outside the type checker, so the
                 blessed mapping holds them; that every refusal carries a
                 code is held a rung higher, by `Diagnostic.code` being a
                 required field, and so is a board misuse's code at check
                 time, by the check-time teller's exhaustive match over
                 `BoardMisuse` (a refusal raised at play takes the record
                 layer's code), and each misuse's raise site is tied to its
                 kind by `BOARD_MISUSE_RAISES`, derived from the enum, and a refusal
                 of library text's code by the library's sort, by the
                 exhaustive match of `attribution.library_text_codes`. Which
                 corrective act a sentence asks for is a reading of English,
                 so `NAME_PAIR_SITES` states it by hand over a scraped axis.
does not prove:  that a report site no rejection case reaches keeps its code:
                 such a site can move to another code with every pin here
                 green, unless it is its code's one witness or a row of the
                 grids above. Measured 2026-11-12, by executing the corpus
                 (`python -m tests.test_diagnostic_codes`): 407 of 581 coded
                 report sites. Nor that every site sharing a code asks for
                 the same kind of fix outside the `name-taken` and
                 `written-twice` sites; the naming review of the registry,
                 read whole, judges that. No designer input reaches the two
                 standard-library codes, nor `BoardMisuse.NO_LINES` through
                 `check_dsl`, which the board-need gate refuses first: their
                 rows here run the standard library's loader and the teller
                 directly. Nor does any game on disk reach
                 `table-cannot-number-a-decision`: its row plants the action
                 space's refusal where `play` loads the game. Nor that a
                 `requires`-row refusal `REQUIRES_ROWS`
                 does not list tells the code of its fix: the list is written
                 by hand, not scraped.
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
from typing import NoReturn

import pytest

import cardlang.resolve as resolve
from cardlang import cli, libraries, pipeline
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Diagnostic, DiagnosticBag, DiagnosticError
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
from cardlang.stdlib.boards import BoardMisuse, BoardRefusal, board_entry
from cardlang.stdlib.rules import STDLIB_NAME, STDLIB_SOURCE_NAME, load_stdlib
from tests.test_playout_records import _renamed_tichu
from tests.test_rejections import REJECTIONS_DIR, case_paths
from tools import glossary_index
from tools.dead_surface import start_for
from tests.resolver_package import patch_resolver

_ROOT = Path(__file__).resolve().parent.parent

# Every code the registry ships, with its meaning. A tool may key on either,
# so a spelling or a meaning changes only under an operator ruling recorded
# in docs/adr/, by a deliberate edit of this mapping.
SHIPPED: dict[str, str] = {
    "syntax-error": "the text does not read as the language; fix it where the message points",
    "misspelled-keyword": "a word nearly spells a keyword the language expects there; write the keyword",
    "wrong-spelling": "the language spells this construct another way; write the spelling the message gives",
    "one-game-per-file": "a source holds exactly one `game { }` block; add it, or move the others to their own files",
    "one-fenced-block": "a Markdown game file holds its game in exactly one fenced block",
    "wrong-file-extension": "a game file's name ends in an extension the checker reads; rename the file",
    "unknown-command": "the first word names no command and no file; write a command or a path",
    "unreadable-file": "the file named cannot be read as text; name a readable game file",
    "command-goes-first": "a command is written after the file; write it first",
    "unknown-command-line-option": "the command takes no command-line option of that name; write one it takes",
    "command-line-option-of-another-command": "the command-line option belongs to another command; name a command that takes every word of the line",
    "file-name-reads-as-command-line-option": "a file's name begins with a dash, so it reads as a command-line option; spell it as a path",
    "extra-word": "the command reads one game file and no other word; drop the word",
    "missing-game-file": "the command needs a game file and the line names none; name one",
    "command-line-usage": "the command line does not read as the command's; write what the message says it expects",
    "seat-view-of-a-playout-with-no-decision": "the engine takes a seat's view only from a playout that has made a decision, and this one made none; leave out --view and --info-state",
    "table-cannot-number-a-decision": "the game has a decision whose picks a table cannot number yet; watch it played with `cardlang demo`",
    "saved-game-not-resumable": "the file --resume names holds no game this game can go on with; name another file, or start a new game",
    "contradicts-saved-game": "a --seat, --seed or --vs names another than the saved game was played with; leave it out",
    "opponents-seated-wrongly": "the --vs items cannot seat the seats you do not take as written: a seat named twice, your own seat named, `all` beside another item, `rest` given twice or alone, or a --vs with no seat left to fill; write them as the message says",
    "unnamed-opponents": "a seat you do not take has no opponent; name one for it with --vs",
    "cannot-save-to-file": "the file --save or --resume names cannot take the saved game: it cannot be written, or it holds something saving would replace; name another file",
    "unwritable-output": "the command's own output cannot be written where the caller sent it: its reader has gone, or its encoding cannot spell what the command prints; read the output to its end, or give the stream an encoding that can",
    "unknown-name": "a name nothing in scope declares, refused where the checker cannot tell which sort of name was meant; read the suggestions, spell a declared name, or declare it",
    "unknown-zone": "a zone no `zones { }` entry declares; spell a declared zone, or declare it",
    "unknown-state-variable": "a state variable no `state { }` block declares; spell a declared one, or declare it",
    "unknown-function": "a function neither the game nor the language defines; spell a defined one, or define it",
    "unknown-procedure": "a procedure the game does not define; spell a defined one, or define it",
    "unknown-game-rule": "a game rule no definition or library provides; spell a defined game rule, or define it",
    "unknown-move-type": "a move type the game does not declare; spell a declared one, or declare it",
    "unknown-phase": "a phase that is not where the construct looks for it; name a phase that is",
    "unknown-mode": "a mode that is not a sibling of this phase's modes; name one that is",
    "unknown-outcome": "an outcome phase or case the game does not declare; name a declared one",
    "unknown-rank": "a rank the game's deck does not have; write one of its ranks",
    "unknown-suit": "a suit the game's deck does not have; write one of its suits",
    "unknown-deck": "a deck or piece set the language does not ship; name a shipped one",
    "unknown-family-library": "a family library that does not exist; name one in docs/libraries/",
    "unknown-checker-type": "a checker type name the language does not have in that position; write one it has",
    "unknown-zone-type": "a zone type the language does not have; write one it has",
    "unknown-zone-index": "a zone family's `[...]` index names nothing the game can key its zones by; name one the message lists",
    "unknown-zone-owner": "a zone type's `<...>` owner names nothing the game can own a zone by; name one the message lists",
    "unknown-quantifiable-domain": "a `for each` names nothing it can range over; name a quantifiable domain or position domain the message lists",
    "unknown-position-domain": "a query ranges over a position domain, or a collection noun, the game does not have; name one it has",
    "unknown-parameter-domain": "a move type's parameter names a parameter domain the language does not have; write one the message lists",
    "unknown-field": "a field the value does not have; read one of its fields, or read it another way",
    "unknown-turn-direction": "a turn direction the language does not have; write one it has",
    "unknown-trick-round-function": "a trick round names a winner function or an early-termination predicate the language does not have; name one it has",
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
    "checker-type-mismatch": "a value of another checker type than the position needs; write a value of that checker type",
    "checker-type-not-known-here": "a value whose checker type cannot be known where an exact checker type is needed; make its checker type plain",
    "wrong-argument-count": "a call, a game rule, a board, a zone type or a checker type is given more or fewer arguments than it takes",
    "wrong-argument": "an argument of a shape the position does not take; write the shape the message gives",
    "wrong-signature": "a definition's, or a `requires` row's, parameters or result differ from what its role requires",
    "wrong-subscript": "a zone or variable subscripted the wrong way, or not subscripted where it must be",
    "checker-type-not-allowed-here": "a checker type, or a word of a type slot, the language allows only in another position; spell it there, or write one this position takes",
    "constant-condition": "a condition that is always true or always false; write the test that was meant",
    "needs-parentheses": "the text reads another way than it seems; add parentheses to say which",
    "out-of-scope": "something read where it does not exist; read it where it is declared, or pass it in",
    "no-player-acting": "the acting player is named, or a decision made, where no player is acting",
    "reads-beyond-parameters": "a function or procedure reads what its parameters do not pass it",
    "recursive-function": "a function calls itself, directly or through others",
    "trick-order-function-reads-beyond-the-card": "a Trick Order function, or the game's `card_points` answer, reads more than the card and public state",
    "trick-order-function-calls-a-later-one": "a Trick Order function calls one that comes after it in the Trick Order",
    "decides-on-hidden-cards": "a seat must check or pick from cards it cannot see; read cards it sees, or announce them",
    "wrong-zone-visibility": "a zone's type hides cards that the construct needs every seat, or its owner, to see",
    "hosted-poll-reads-unpublished-round-state": "a Hosted Poll reads Round State that is not yet published",
    "not-writable": "the target is not a state variable this text may write",
    "family-library-requirement-unmet": "the game lacks what a family library it uses requires; add it to the game",
    "requirement-mismatch": "the game declares what a library requires, but not as the library requires it",
    "requirement-matches-several": "a library requirement matches several of the game's declarations; keep one",
    "outside-family-library-contract": "family library text reads a name it neither defines nor requires; define it, or require it",
    "standard-library-reads-undefined-name": "standard library text reads a name the standard library does not define; define it there",
    "family-library-reaches-one-game": "family library text names what belongs to one game; take it as a parameter or a requirement",
    "standard-library-reaches-one-game": "standard library text names what belongs to one game; keep the standard library to what every game shares",
    "family-library-cannot-require-a-game-rule": "a family library's `requires` row names a game rule, which only a game's `active_rules:` names; keep the definition that needs it in the game",
    "requires-what-is-provided": "a library requires what a library already provides or defines; drop one of the two",
    "family-library-not-yet-proven": "no game yet checks clean reaching this family library text, so its refusal stands in the family library's file",
    "game-rule-never-consulted": "a game rule no decision ever asks, so it would never apply; write the condition where a decision reads it, or delete the game rule",
    "modes-must-pair-up": "modes whose transitions do not pair one condition with its far side; give each condition its own pair of modes",
    "climb-round-lead-and-follows-mismatch": "a climbing round's lead and `follows` slots name no one engine; name a Registered Engine's lead query and its own follows query, or a Declared Engine's combination catalogue and the game's follows function",
    "choose-integer-needs-fixed-ceiling": "a `choose integer` has no upper bound known before play; give it a literal upper bound, or an `up to N` ceiling",
    "choice-offers-no-candidate": "a `choose integer` whose bounds or `excluding` leave no number to choose; widen what it offers",
    "teams-must-partition-seats": "`teams:` must put every seat on exactly one team",
    "use-winner-not-loser": "`loser:` cannot decide this game's result; rank a score with `winner:`",
    "unrankable-winner-target": "`winner:` ranks something that is not a score each player or team holds",
    "ranking-incomplete": "a ranking leaves out ranks or suits it must order; list them all",
    "catalogue-row-names-no-play": "a combination catalogue row no cards of the deck can make",
    "ambiguous-play-shape": "one play fits two rows of the catalogue; settle it in the rows",
    "card-plays-look-alike": "a card play's parameters or offering would make two plays look alike; fold them into one move type",
    "deal-all-to-each-needs-as-equally-as-possible": "`deal all ... to each` says no way to split the cards among the zones; write `as-equally-as-possible`",
    "wrong-zone-shape": "a single zone where a zone per player is needed, or the reverse",
    "wrong-primitive-checker-type": "a `primitives` entry spells a checker type no Primitive implementation takes",
    "missing-outcome-arm": "a `produces:` block leaves an outcome case unhandled",
    "outcome-read-before-produced": "an outcome is consumed before the phase producing it has run",
    "refused-during-play": "a rule only a playout reaches refused the game",
    "game-error-raised": "the game's own `error(...)` refused a move no player was offered",
    "primitive-reads-a-name-the-game-lacks": "a Primitive module the game uses reads, by its name, a state variable or zone the game no longer declares; declare it under that name",
    "random-play-reaches-length-stop": "uniform-random play met the game's Length Stop, its max_length reached without its rules ending it; raise the bound, end the loop that should have ended, or, if a table can lawfully play on without end, say so in the game's twin",
    "engine-gap": "the engine refused what an earlier check should have refused; the engine must change",
    "incomplete-installation": "the checkout is missing files the engine loads; reinstall it",
    "unregistrable-game": "a game file offered for registration cannot be registered by that name",
    "position-outside-the-file": "a line or column before the file's first, or past the end of its line or of the file; give a position inside the text",
    "position-outside-the-game": "a position in a comment, a blank line or prose that no part of the game holds; point inside the game's text",
    "not-an-expression": "the position is on a statement or a declaration, which has no value; point at an expression inside it",
    "expression-not-typed": "the checker reads this expression without working out its own type; ask about the expression around it",
    "nothing-seen-here": "nothing at this position moves a card or asks a seat; point at a movement or a decision",
    "seen-at-its-sites": "this moves no card itself but runs movements or decisions that stand elsewhere; ask at each of them",
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


def _standard_library(body: str) -> Tells:
    """Standard library text no shipped input holds, read by the standard
    library's own loader: no designer input reaches these codes."""

    def tells(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
        return _told(lambda: load_stdlib(f"library {STDLIB_NAME} {{\n{body}\n}}\n", STDLIB_SOURCE_NAME))

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


def _query(game: str, at: str) -> Tells:
    """A Checker Query run with `--json`: the codes of its refusals, of the
    whole question and of each answer."""

    def tells(_mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(["query", str(_ROOT / "docs" / "games" / game), "--at", at, "--json"])
        document = json.loads(out.getvalue())
        records = list(document["diagnostics"])
        for part in ("scope", "type", "seats"):
            answer = (document["answer"] or {}).get(part) or {}
            if "refused" in answer:
                records.append(answer["refused"])
        return frozenset(next(c for c in Code if c.slug == r["code"]) for r in records)

    return tells


def _refused_line(argv: Callable[[Path], list[str]]) -> Tells:
    """A command line refused before it is read, its refusal caught where the
    one renderer would print it."""

    def tells(mp: pytest.MonkeyPatch, tmp: Path) -> frozenset[Code]:
        told: list[Code] = []

        def caught(_parser: object, _line: object, refusal: Diagnostic) -> NoReturn:
            told.append(refusal.code)
            raise SystemExit(2)

        mp.setattr(cli, "_refuse", caught)
        mp.chdir(tmp)
        with pytest.raises(SystemExit):
            cli.main(argv(tmp))
        return frozenset(told)

    return tells


_HEARTS = str(_ROOT / "docs" / "games" / "hearts.cardlang")


def _dash_named(tmp: Path) -> list[str]:
    (tmp / "-g.cardlang").write_text("game g { }\n")
    return ["check", "-g.cardlang"]


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


_KUHN = str(_ROOT / "docs" / "games" / "kuhn-poker.cardlang")


def _saved_kuhn(tmp: Path) -> str:
    """A saved game of Kuhn poker, at seat 0 with seed 7 against `random`."""
    game = check_source(Path(_KUHN))
    saved = tmp / "saved.json"
    saved.write_text(
        json.dumps(
            {
                "cardlang_session": 2,
                "game": game.name,
                "identity": pipeline.game_identity(game),
                "seed": 7,
                "seat": 0,
                "opponents": {"1": "random"},
                "history": [],
            }
        )
    )
    return str(saved)


def _bounded(tmp: Path) -> str:
    """Tic-tac-toe at `max_length: 5`, which seed 0's uniform line reaches."""
    from tests.test_length_stop import bounded_tic_tac_toe

    path = tmp / "bounded.cardlang"
    path.write_text(bounded_tic_tac_toe())
    return str(path)


def _table_cannot_number(mp: pytest.MonkeyPatch, tmp: Path) -> frozenset[Code]:
    """No game the corpus holds has a decision a table cannot number, so the
    action space's refusal is raised where `play` loads the game."""

    def unnumbered(_path: str) -> NoReturn:
        raise NotImplementedError("no numbering for this decision")

    mp.setattr(cli, "load", unnumbered)
    return _cli(lambda _tmp: ["play", _KUHN, "--vs", "all=random"])(mp, tmp)


def _ascii_stdout(mp: pytest.MonkeyPatch, _tmp: Path) -> frozenset[Code]:
    """A playout printed to a stdout that cannot encode its em dashes, every
    refusal the run told read where its status is computed from them: under
    `--json` stdout holds only the envelope, which is ASCII, so the text form
    is the one that meets it."""
    told: list[Code] = []
    status = cli._Telling.status

    def recording(self: cli._Telling) -> int:
        told.extend(t.diagnostic.code for t in self.told)
        return status(self)

    mp.setattr(cli._Telling, "status", recording)
    mp.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="ascii"))
    cli.main(["demo", _KUHN, "--seed", "1"])
    return frozenset(told)


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
    Code.UNKNOWN_GAME_RULE: _case("active_rules_undefined_rule"),
    Code.UNKNOWN_MOVE_TYPE: _case("constrains_unknown_move_type"),
    Code.UNKNOWN_PHASE: _case("primitives_scoped_read_no_such_phase"),
    Code.UNKNOWN_MODE: _case("transition_to_non_sibling"),
    Code.UNKNOWN_OUTCOME: _case("code_unknown_outcome"),
    Code.UNKNOWN_RANK: _case("ranking_mixed_convention_and_ranks"),
    Code.UNKNOWN_SUIT: _case("round_trump_unknown_suit"),
    Code.UNKNOWN_DECK: _case("pieces_unknown_set"),
    Code.UNKNOWN_FAMILY_LIBRARY: _case("uses_unknown_family_library"),
    Code.UNKNOWN_CHECKER_TYPE: _case("unknown_type_function_param"),
    Code.UNKNOWN_PARAMETER_DOMAIN: _case("dir_parameter_on_morris9"),
    Code.UNKNOWN_ZONE_TYPE: _case("unknown_zone_type"),
    Code.UNKNOWN_ZONE_INDEX: _case("zone_index_unknown"),
    Code.UNKNOWN_ZONE_OWNER: _case("zone_owner_unknown"),
    Code.UNKNOWN_QUANTIFIABLE_DOMAIN: _case("positions_for_each"),
    Code.UNKNOWN_POSITION_DOMAIN: _case("any_over_unknown_position_domain"),
    Code.UNKNOWN_FIELD: _case("code_unknown_field"),
    Code.UNKNOWN_TURN_DIRECTION: _case("unknown_direction"),
    Code.UNKNOWN_TRICK_ROUND_FUNCTION: _case("trick_round_unknown_early_termination"),
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
    Code.CHECKER_TYPE_MISMATCH: _case("board_cell_state_var"),
    Code.CHECKER_TYPE_NOT_KNOWN_HERE: _case("boolean_position_laundered_any"),
    Code.WRONG_ARGUMENT_COUNT: _case("arrival_winner_missing_trump"),
    Code.WRONG_ARGUMENT: _case("code_wrong_argument"),
    Code.WRONG_SIGNATURE: _case("primitives_signature_mismatch"),
    Code.WRONG_SUBSCRIPT: _case("positions_bare_family_reference"),
    Code.CHECKER_TYPE_NOT_ALLOWED_HERE: _case("collection_at_a_function_parameter"),
    Code.CONSTANT_CONDITION: _case("code_constant_condition"),
    Code.NEEDS_PARENTHESES: _case("code_needs_parentheses"),
    Code.OUT_OF_SCOPE: _case("primitives_scoped_read_called_outside"),
    Code.NO_PLAYER_ACTING: _case("code_no_player_acting"),
    Code.READS_BEYOND_PARAMETERS: _case("code_reads_beyond_parameters"),
    Code.RECURSIVE_FUNCTION: _case("code_recursive_function"),
    Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD: _case("is_trump_reads_a_pronoun"),
    Code.TRICK_ORDER_FUNCTION_CALLS_A_LATER_ONE: _case("is_trump_calls_a_later_trick_order_function"),
    Code.DECIDES_ON_HIDDEN_CARDS: _case("hidden_read_blind_draw"),
    Code.WRONG_ZONE_VISIBILITY: _case("implicit_pool_hidden_from_owner"),
    Code.HOSTED_POLL_READS_UNPUBLISHED_ROUND_STATE: _case("hosted_poll_card_movement"),
    Code.NOT_WRITABLE: _case("code_not_writable"),
    Code.REQUIREMENT_MISMATCH: _case("contract_result_mismatch"),
    Code.GAME_RULE_NEVER_CONSULTED: _case("constrains_game_move_type"),
    Code.MODES_MUST_PAIR_UP: _case("mode_entered_and_transitioning"),
    Code.CLIMB_ROUND_LEAD_AND_FOLLOWS_MISMATCH: _case("climb_round_follows_with_another_engine"),
    Code.CHOOSE_INTEGER_NEEDS_FIXED_CEILING: _case("choose_without_static_ceiling"),
    Code.CHOICE_OFFERS_NO_CANDIDATE: _case("choose_excluding_empties_range"),
    Code.TEAMS_MUST_PARTITION_SEATS: _case("code_teams_must_partition_seats"),
    Code.USE_WINNER_NOT_LOSER: _case("elimination_one_seat"),
    Code.UNRANKABLE_WINNER_TARGET: _case("stop_result_ranking_unindexed"),
    Code.RANKING_INCOMPLETE: _case("ranking_convention_non_french_deck"),
    Code.CATALOGUE_ROW_NAMES_NO_PLAY: _case("code_catalogue_row_names_no_play"),
    Code.AMBIGUOUS_PLAY_SHAPE: _case("code_ambiguous_play_shape"),
    Code.CARD_PLAYS_LOOK_ALIKE: _case("offering_two_card_parameter_moves"),
    Code.DEAL_ALL_TO_EACH_NEEDS_AS_EQUALLY_AS_POSSIBLE: _case("deal_all_to_each_without_split"),
    Code.WRONG_ZONE_SHAPE: _case("deal_to_each_subscripted"),
    Code.WRONG_PRIMITIVE_CHECKER_TYPE: _case("primitives_collection_bare_constructor"),
    Code.MISSING_OUTCOME_ARM: _case("code_missing_outcome_arm"),
    Code.OUTCOME_READ_BEFORE_PRODUCED: _case("code_outcome_read_before_produced"),
    Code.ONE_FENCED_BLOCK: _no_fenced_block,
    Code.WRONG_FILE_EXTENSION: _wrong_extension,
    Code.UNKNOWN_COMMAND: _unknown_command,
    Code.COMMAND_GOES_FIRST: _refused_line(lambda _tmp: [_HEARTS, "demo"]),
    Code.UNKNOWN_COMMAND_LINE_OPTION: _refused_line(lambda _tmp: ["check", _HEARTS, "--emitir"]),
    Code.COMMAND_LINE_OPTION_OF_ANOTHER_COMMAND: _refused_line(lambda _tmp: ["check", _HEARTS, "--seed", "3"]),
    Code.FILE_NAME_READS_AS_COMMAND_LINE_OPTION: _refused_line(_dash_named),
    Code.EXTRA_WORD: _refused_line(lambda _tmp: ["check", _HEARTS, "extra"]),
    Code.MISSING_GAME_FILE: _refused_line(lambda _tmp: ["check"]),
    Code.COMMAND_LINE_USAGE: _refused_line(lambda _tmp: ["demo", _HEARTS, "--seed", "x"]),
    Code.UNREADABLE_FILE: _cli(lambda tmp: ["check", str(tmp / "missing.cardlang")]),
    Code.UNWRITABLE_OUTPUT: _ascii_stdout,
    Code.PRIMITIVE_READS_A_NAME_THE_GAME_LACKS: _cli(lambda tmp: ["demo", _renamed_tichu(tmp), "--seed", "1"]),
    Code.SEAT_VIEW_OF_A_PLAYOUT_WITH_NO_DECISION: _cli(
        lambda _tmp: ["demo", str(_ROOT / "tests" / "fixtures" / "skeleton.md"), "--seed", "5", "--view", "0"]
    ),
    Code.TABLE_CANNOT_NUMBER_A_DECISION: _table_cannot_number,
    Code.SAVED_GAME_NOT_RESUMABLE: _cli(lambda tmp: ["play", _KUHN, "--resume", str(tmp / "missing.json")]),
    Code.CONTRADICTS_SAVED_GAME: _cli(lambda tmp: ["play", _KUHN, "--resume", _saved_kuhn(tmp), "--seed", "9"]),
    Code.OPPONENTS_SEATED_WRONGLY: _cli(lambda _tmp: ["play", _KUHN, "--vs", "0=random"]),
    Code.UNNAMED_OPPONENTS: _cli(lambda _tmp: ["play", _KUHN]),
    Code.CANNOT_SAVE_TO_FILE: _cli(
        lambda tmp: ["play", _KUHN, "--vs", "all=random", "--save", str(tmp / "nodir" / "x.json")]
    ),
    Code.RANDOM_PLAY_REACHES_LENGTH_STOP: _cli(lambda tmp: ["demo", _bounded(tmp), "--seed", "0"]),
    Code.FAMILY_LIBRARY_REQUIREMENT_UNMET: _using("requires { probe_s : Integer }\nfunction probe_fn() = probe_s"),
    Code.REQUIREMENT_MATCHES_SEVERAL: _using(
        "requires { probe_f(c : Card) : Boolean }",
        "function probe_f(c : Card) = true\nfunction probe_f(c : Card) = false\n",
    ),
    Code.OUTSIDE_FAMILY_LIBRARY_CONTRACT: _using("function probe_fn() = probe_undeclared"),
    Code.FAMILY_LIBRARY_REACHES_ONE_GAME: _using(
        "requires { hand[player] : Hand<player> }\nfunction probe_fn() = number of cards in hand[0]"
    ),
    Code.FAMILY_LIBRARY_CANNOT_REQUIRE_A_GAME_RULE: _using("requires { probe_r : Rule }"),
    Code.STANDARD_LIBRARY_READS_UNDEFINED_NAME: _standard_library("function probe_fn() = probe_undeclared"),
    Code.STANDARD_LIBRARY_REACHES_ONE_GAME: _standard_library("function probe_fn(c : Card) = c is A of spades"),
    Code.REQUIRES_WHAT_IS_PROVIDED: _using("state { claimed : Integer = 0 }\nrequires { claimed : Integer }"),
    # The library no game uses refuses in its own file, beside the warning.
    Code.FAMILY_LIBRARY_NOT_YET_PROVEN: _using("function probe_fn() = probe_undeclared"),
    Code.REFUSED_DURING_PLAY: _playout("empty_zone_choice.cardlang"),
    Code.GAME_ERROR_RAISED: _playout("rule_refuses_every_card.cardlang"),
    Code.ENGINE_GAP: _constructed(lambda: ShadowGuardError("resolve", "a leaked refusal")),
    Code.INCOMPLETE_INSTALLATION: _broken_checkout,
    Code.UNREGISTRABLE_GAME: _constructed(lambda: GameRegistrationError("two files claim one short name")),
    Code.POSITION_OUTSIDE_THE_FILE: _query("hearts.cardlang", "999:1"),
    Code.POSITION_OUTSIDE_THE_GAME: _query("hearts.cardlang", "1:1"),
    Code.NOT_AN_EXPRESSION: _query("hearts.cardlang", "90:9"),
    Code.EXPRESSION_NOT_TYPED: _query("hearts.cardlang", "86:7"),
    Code.NOTHING_SEEN_HERE: _query("hearts.cardlang", "86:14"),
    Code.SEEN_AT_ITS_SITES: _query("coup.cardlang", "236:11"),
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


# --- the board registry's refusals, each by the misuse it carries ------------

# Each misuse, the code the one teller gives it, and the rejection case that
# reaches it through `check_dsl`: None where the board-need gate
# (`resolve.references._BOARD_NEED_GATES`) refuses the verb first.
BOARD_MISUSES: dict[BoardMisuse, tuple[Code, str | None]] = {
    BoardMisuse.UNKNOWN_FAMILY: (Code.UNKNOWN_BOARD, "board_unknown_family"),
    BoardMisuse.WRONG_ARGUMENT_COUNT: (Code.WRONG_ARGUMENT_COUNT, "board_grid_without_arguments"),
    BoardMisuse.ARGUMENT_OUT_OF_RANGE: (Code.OUT_OF_RANGE, "board_bad_args"),
    BoardMisuse.UNDECLARED_LINE_LENGTH: (Code.OUT_OF_RANGE, "lines2_on_morris9"),
    BoardMisuse.NO_LINES: (Code.MISSING_DECLARATION, None),
}


@pytest.mark.parametrize("misuse", list(BoardMisuse), ids=lambda m: m.name.lower())
def test_a_board_misuse_tells_its_code(
    misuse: BoardMisuse, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """red under: `_tell_board_refusal`'s `ARGUMENT_OUT_OF_RANGE` arm coded
    `Code.WRONG_ARGUMENT_COUNT`."""
    code, case = BOARD_MISUSES[misuse]
    bag = DiagnosticBag()
    resolve._tell_board_refusal(BoardRefusal(misuse, "a probe refusal"), "probe", None, bag)
    assert [d.code for d in bag.items] == [code]
    if case is not None:
        assert _case(case)(monkeypatch, tmp_path) == {code}


# Each misuse, and the registry call that raises it.
BOARD_MISUSE_RAISES: dict[BoardMisuse, Callable[[], object]] = {
    BoardMisuse.UNKNOWN_FAMILY: lambda: board_entry("no_such_board", ()),
    BoardMisuse.WRONG_ARGUMENT_COUNT: lambda: board_entry("grid", (3,)),
    BoardMisuse.ARGUMENT_OUT_OF_RANGE: lambda: board_entry("grid", (0, 3)),
    BoardMisuse.NO_LINES: lambda: board_entry("hex_rhombus", (3,)).lines(3),
    BoardMisuse.UNDECLARED_LINE_LENGTH: lambda: board_entry("morris9", ()).lines(2),
}


@pytest.mark.parametrize("misuse", list(BoardMisuse), ids=lambda m: m.name.lower())
def test_the_registry_raises_each_misuse_as_itself(misuse: BoardMisuse) -> None:
    """red under: `BoardEntry.lines` raising its no-lines refusal as
    `BoardMisuse.UNDECLARED_LINE_LENGTH`."""
    raising = BOARD_MISUSE_RAISES.get(misuse)
    assert raising is not None, f"`{misuse.name}` has no raise site here"
    with pytest.raises(BoardRefusal) as excinfo:
        raising()
    assert excinfo.value.misuse is misuse


# --- a family library's `requires` rows, each refusal by the fix it asks ------

# One row per refusal of the `requires`-row checks, keyed by a phrase of its
# sentence: the library text that reaches it, and the code of the fix it asks.
REQUIRES_ROWS: dict[str, tuple[str, Code]] = {
    "is a state type and takes no type argument": ("probe_z : Integer<player>", Code.WRONG_ARGUMENT_COUNT),
    "names the kind, not the row's type word": ("probe_m : move_type", Code.WRONG_SPELLING),
    "a move type has no index": ("probe_m[player] : Move", Code.WRONG_SUBSCRIPT),
    "a move type contract takes no type argument": ("probe_m : Move<player>", Code.WRONG_ARGUMENT_COUNT),
    "a function the game defines is contracted by its signature": ("probe_f : function", Code.WRONG_SPELLING),
    "a procedure the game defines is contracted by its signature": ("probe_p : procedure", Code.WRONG_SPELLING),
    "a rule cannot be contracted": ("probe_r : rule", Code.FAMILY_LIBRARY_CANNOT_REQUIRE_A_GAME_RULE),
    "the kernel's contract is": ("is_trump(c : Card) : Integer", Code.WRONG_SIGNATURE),
    "no function could declare": ("probe_f(z : Hand) : Boolean", Code.CHECKER_TYPE_NOT_ALLOWED_HERE),
    "no procedure could declare": ("probe_p(z : Boolean) : Procedure", Code.CHECKER_TYPE_NOT_ALLOWED_HERE),
    "a procedure returns no value, so its row carries no": ("probe_f() : Procedure?", Code.WRONG_SPELLING),
    "a move type is offered by name and passed no arguments": ("probe_f() : Move", Code.WRONG_SPELLING),
    "names a kind of definition, not the type the function returns": ("probe_f() : function", Code.CHECKER_TYPE_NOT_ALLOWED_HERE),
    "a function returns a value, and a zone the game declares": ("probe_f() : Hand", Code.CHECKER_TYPE_NOT_ALLOWED_HERE),
    "is a procedure parameter's domain": ("probe_f() : Positive", Code.CHECKER_TYPE_NOT_ALLOWED_HERE),
}


@pytest.mark.parametrize("phrase", sorted(REQUIRES_ROWS))
def test_a_requires_row_refusal_tells_the_code_of_its_fix(
    phrase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    row, code = REQUIRES_ROWS[phrase]
    library = parse_library(
        f"library {_LIBRARY} {{\n  requires {{ {row} }}\n}}\n", f"docs/libraries/{_LIBRARY}.cardlang"
    )
    patch_resolver(monkeypatch, "library_names", lambda: frozenset({_LIBRARY}))
    patch_resolver(monkeypatch, "load_library", lambda name: library)
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(_HOST, "host.cardlang")
    told = {(str(t.diagnostic.message), t.diagnostic.code) for t in excinfo.value.told}
    reached = [c for message, c in told if phrase in message]
    assert reached, f"`{row}` does not reach the refusal saying {phrase!r}: {told}"
    assert reached == [code]


# --- `name-taken` against `written-twice` -------------------------------------

# The corrective act each site's own sentence asks for. A site that asks the
# author to rename one of two things, or that could be read either way, is
# `name-taken`; a site that asks the author to delete or merge a repeat is
# `written-twice`.
_ACT_CODE: dict[str, Code] = {
    "rename one": Code.NAME_TAKEN,
    "either": Code.NAME_TAKEN,
    "drop the repeat": Code.WRITTEN_TWICE,
}

# Every report site of the two codes, keyed by its file and a phrase of its
# sentence, with the act the sentence asks for.
NAME_PAIR_SITES: dict[tuple[str, str], str] = {
    ("cardlang/catalogue_pass.py", "labels two rows of"): "rename one",
    ("cardlang/catalogue_pass.py", "a row's label names its shape"): "rename one",
    ("cardlang/catalogue_pass.py", "names `"): "drop the repeat",
    ("cardlang/catalogue_pass.py", "is said twice in"): "drop the repeat",
    ("cardlang/parse.py", "a game declares one"): "drop the repeat",
    ("cardlang/parse.py", "a library declares one `requires` block"): "drop the repeat",
    ("cardlang/parse.py", "a library declares one `state` block"): "drop the repeat",
    ("cardlang/resolve/classified_checks.py", "names the same go-again flag"): "rename one",
    ("cardlang/resolve/classified_checks.py", "shadows the native function of the same name"): "rename one",
    ("cardlang/resolve/classified_checks.py", "declares more than one parameter named"): "either",
    ("cardlang/resolve/classified_checks.py", "that slot always runs"): "rename one",
    ("cardlang/resolve/classified_checks.py", "shadowing its own parameter"): "rename one",
    ("cardlang/resolve/classifier.py", "the Hosted Poll's binder"): "rename one",
    ("cardlang/resolve/declarations.py", "is spelled like the climb engine"): "rename one",
    ("cardlang/resolve/declarations.py", "ranking: repeats rank"): "drop the repeat",
    ("cardlang/resolve/declarations.py", "card_points repeats rank"): "drop the repeat",
    ("cardlang/resolve/declarations.py", "suit ranking: repeats suit"): "drop the repeat",
    ("cardlang/resolve/declarations.py", "is answered twice"): "drop the repeat",
    ("cardlang/resolve/declarations.py", "the later declaration would silently shadow the earlier one"): "either",
    ("cardlang/resolve/library_alone.py", "which names more than one parameter named"): "rename one",
    ("cardlang/resolve/library_alone.py", "a contract names each thing once"): "drop the repeat",
    ("cardlang/resolve/library_alone.py", "and also holds a"): "rename one",
    ("cardlang/resolve/library_alone.py", "is the language's own callback"): "rename one",
    ("cardlang/resolve/positions.py", "'{BOARD_DOMAIN}', which collides with the declared `positions"): "rename one",
    ("cardlang/resolve/positions.py", "which collides with {minted_clash}"): "rename one",
    ("cardlang/resolve/positions.py", "'{DIRECTION_DOMAIN}', which collides with the declared `positions"): "rename one",
    ("cardlang/resolve/positions.py", "which collides with {direction_clash}"): "rename one",
    ("cardlang/resolve/positions.py", "pick another name"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "declares one `"): "drop the repeat",
    ("cardlang/resolve/primitive_declarations.py", "is a Builtin the language ships"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "answers in the language"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "is already defined in this game"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "the innermost frame wins"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "each parameter is named once"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "a `reads` clause names each spelling at most once"): "drop the repeat",
    ("cardlang/resolve/primitive_declarations.py", "as BOTH a state variable and a zone"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "the game-level variable is then unreadable"): "rename one",
    ("cardlang/resolve/primitive_declarations.py", "while this game declares it as a zone"): "rename one",
    ("cardlang/resolve/references.py", "binds parameters by name"): "rename one",
    ("cardlang/resolve/rule_instantiation.py", "declares more than one parameter named"): "either",
    ("cardlang/resolve/rule_instantiation.py", "shadowing its own parameter"): "rename one",
    ("cardlang/resolve/rule_instantiation.py", "delete the local definition"): "either",
    ("cardlang/resolve/rule_instantiation.py", "declares more than one `state { }` block"): "drop the repeat",
    ("cardlang/resolve/rule_instantiation.py", "appears twice in one subset source"): "drop the repeat",
    ("cardlang/resolve/splice.py", "the repeat imports nothing further"): "drop the repeat",
    ("cardlang/resolve/splice.py", "a `uses` import adds names without overriding"): "rename one",
    ("cardlang/resolve/splice.py", "nothing in this file says the spelling was taken"): "rename one",
    ("cardlang/resolve/splice.py", "there is nothing here to rename"): "rename one",
    ("cardlang/resolve/splice.py", "resolves it from the stdlib"): "either",
    ("cardlang/resolve/splice.py", "but run this one instead"): "rename one",
    ("cardlang/resolve/splice.py", "the two libraries cannot both be used"): "either",
    ("cardlang/resolve/splice.py", "rename the game's {noun}"): "either",
    ("cardlang/resolve/splice.py", "is provided by both"): "either",
    ("cardlang/resolve/splice.py", "is defined by both"): "either",
    ("cardlang/resolve/splice.py", "that slot runs the"): "rename one",
    ("cardlang/resolve/splice.py", "delete the game's declaration"): "either",
    ("cardlang/typecheck.py", "duplicate outcome phase name"): "either",
    ("cardlang/typecheck.py", "in produces"): "drop the repeat",
    ("cardlang/typecheck.py", "is consumed by more than one"): "drop the repeat",
}


def _sentence(call: ast.Call) -> str:
    """The literal text of a report call's sentence: every string constant
    and f-string part among its positional arguments, joined."""
    parts: list[str] = []
    for arg in call.args:
        for node in ast.walk(arg):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                parts.append(node.value)
            elif isinstance(node, ast.FormattedValue):
                parts.append("{" + ast.unparse(node.value) + "}")
    return "".join(parts)


def _name_pair_sites() -> list[tuple[str, int, Code, str]]:
    """Every use of `Code.NAME_TAKEN` or `Code.WRITTEN_TWICE` in `cardlang/`:
    file, line, code and the sentence of the report call it is the `code=` of."""
    sites: list[tuple[str, int, Code, str]] = []
    for path in sorted((_ROOT / "cardlang").rglob("*.py")):
        rel = path.relative_to(_ROOT).as_posix()
        if rel == "cardlang/diagnostic_codes.py":
            continue
        tree = ast.parse(path.read_text())
        coded = {
            id(k.value): node
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            for k in node.keywords if k.arg == "code"
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name) and node.value.id == "Code"
                and node.attr in (Code.NAME_TAKEN.name, Code.WRITTEN_TWICE.name)
            ):
                call = coded.get(id(node))
                assert call is not None, f"{rel}:{node.lineno}: `Code.{node.attr}` outside a report call's `code=`"
                sites.append((rel, node.lineno, Code[node.attr], _sentence(call)))
    return sites


def test_every_name_pair_site_is_classified_once() -> None:
    """The site axis is scraped from the source, so a new site of either code
    with no row, or a row naming no site, reddens here."""
    sites = _name_pair_sites()
    rows: dict[tuple[str, str], int] = {key: 0 for key in NAME_PAIR_SITES}
    for rel, line, _code, sentence in sites:
        matched = [key for key in NAME_PAIR_SITES if key[0] == rel and key[1] in sentence]
        assert len(matched) == 1, f"{rel}:{line}: {len(matched)} rows match {sentence!r}"
        rows[matched[0]] += 1
    assert {key for key, hits in rows.items() if hits != 1} == set()


def test_a_name_pair_site_tells_the_code_of_the_act_it_asks() -> None:
    """red under: `catalogue_pass.py`'s "labels two rows of" site coded
    `Code.WRITTEN_TWICE`."""
    wrong = [
        f"{rel}:{line}: {code.slug}, asks {act!r}"
        for rel, line, code, sentence in _name_pair_sites()
        for (file, phrase), act in NAME_PAIR_SITES.items()
        if file == rel and phrase in sentence and _ACT_CODE[act] is not code
    ]
    assert wrong == []


# --- code names and the glossary's reserved words ----------------------------

Reserved = dict[str, tuple[tuple[str, ...], ...]]


def _reserved_words(entries: list[dict[str, str]] | None = None) -> Reserved:
    """Each reserved word of the glossary (docs/glossary/ by default), with
    the compounds its own entry marks in `compounds:`, each as its words. A
    row that approves its bare word marks it (the Outcome row)."""
    entries = glossary_index.load() if entries is None else entries
    return {
        glossary_index.words(e["term"])[0]: tuple(
            glossary_index.words(c) for c in glossary_index.compounds(e)
        )
        for e in entries
        if e["reserved"] == "true"
    }


def _reserved_word(token: str, reserved: Reserved) -> str | None:
    """The reserved word `token` spells, singular or plural."""
    return next((w for w in reserved if token in (w, w + "s", w + "es")), None)


def _stands_in(tokens: list[str], i: int, compound: tuple[str, ...], word: str) -> bool:
    """Whether the reserved word at `tokens[i]` stands inside `compound`."""
    for j, w in enumerate(compound):
        start = i - j
        if w != word or start < 0 or start + len(compound) > len(tokens):
            continue
        window = tokens[start : start + len(compound)]
        if all(k == j or t == c for k, (t, c) in enumerate(zip(window, compound))):
            return True
    return False


def _bare_reserved_words(slug: str, reserved: Reserved) -> list[str]:
    """The reserved words `slug` uses outside every compound of their own row."""
    tokens = slug.split("-")
    bare: list[str] = []
    for i, token in enumerate(tokens):
        word = _reserved_word(token, reserved)
        if word is not None and not any(_stands_in(tokens, i, c, word) for c in reserved[word]):
            bare.append(token)
    return bare


def test_the_reserved_word_reading_tells_a_compound_from_a_bare_word() -> None:
    """The reading of the glossary, against spellings whose answer is known.
    red under: `checker type` dropped from docs/glossary/type.md's
    `compounds:`."""
    reserved = _reserved_words()
    assert _bare_reserved_words("unknown-house-rule", reserved) == ["rule"]
    assert _bare_reserved_words("unknown-game-rule", reserved) == []
    assert _bare_reserved_words("one-fenced-block", reserved) == []
    assert _bare_reserved_words("unknown-turn-direction", reserved) == []
    assert _bare_reserved_words("trick-order-function-calls-a-later-one", reserved) == []
    assert _bare_reserved_words("unknown-checker-type", reserved) == []
    assert _bare_reserved_words("hosted-poll-reads-unpublished-round-state", reserved) == []
    assert _bare_reserved_words("checker-of-the-value", reserved) == ["value"]


@pytest.mark.parametrize(
    "slug, bare",
    [
        ("conflicting-rules", ["rules"]),
        ("unknown-types", ["types"]),
        ("a-rule-hand-unknown", ["rule", "hand"]),
        ("unknown-state-block", ["block"]),
    ],
)
def test_a_plural_a_neighbour_rows_compound_or_prose_approves_nothing(slug: str, bare: list[str]) -> None:
    """A reserved word counts singular or plural, and only a compound its own
    row marks approves it: `state block` is the `state` row's, not the
    `block` row's, and a row's prose marks nothing."""
    assert _bare_reserved_words(slug, _reserved_words()) == bare


def test_only_a_compound_of_a_words_own_row_approves_it() -> None:
    """red under: `_bare_reserved_words` reading every row's compounds, or a
    row's marked bare word approving nothing."""
    entries = [
        {"term": "probe", "reserved": "true", "compounds": "[probe, probe gadget]", "_slug": "probe"},
        {"term": "gadget", "reserved": "true", "compounds": "[gadget kit]", "_slug": "gadget"},
    ]
    reserved = _reserved_words(entries)
    assert _bare_reserved_words("unknown-probe", reserved) == []
    assert _bare_reserved_words("unknown-gadget-kit", reserved) == []
    assert _bare_reserved_words("unknown-gadgets", reserved) == ["gadgets"]
    assert _bare_reserved_words("unknown-probe-gadget", reserved) == ["gadget"]


@pytest.mark.parametrize("code", list(Code), ids=lambda c: c.slug)
def test_a_code_name_uses_a_reserved_word_only_in_an_approved_compound(code: Code) -> None:
    """red under: a member spelled `UNKNOWN_HOUSE_RULE = ("unknown-house-rule", ...)`."""
    assert _bare_reserved_words(code.slug, _reserved_words()) == []


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
