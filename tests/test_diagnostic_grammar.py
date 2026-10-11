"""The main grammar accepts only the language; the teaching refusals live in
`cardlang/grammar/diagnostics.lark` and run only when a parse has failed.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   no alias of the compiled main grammar ends `_reject` and no
            terminal of it is named only by a refused rule; every twin the
            diagnostic grammar holds is exercised by a rejection golden and
            every golden's twin is one the diagnostic grammar holds; a
            corpus, library or stdlib file never reaches the diagnostic
            parser; a text neither grammar derives reports the main parser's
            own error; and `always`, the one twin that is a plain name once
            its keyword leaves the lexer, is refused by resolve in the
            builder's words where it stands as a whole predicate, accepted
            where a game declares it, and an ordinary unresolved name as an
            operand.
domain:     the compiled main grammar's rules and terminals (the first two
            pins); the `%extend` lines of `diagnostics.lark` crossed with the
            fixtures under `tests/rejections/` (the twin pin, derived in both
            directions); the corpus, library and stdlib globs (the
            never-reached pin); the holders of a predicate resolve's `always`
            table names (`resolve.ALWAYS_HOLDERS`), crossed with
            {declared, undeclared} x {whole predicate, operand} x {written in
            the game, written in a family library}.
registry:   `cardlang.parse._parser()` (main), `cardlang.parse._diagnostic_parser()`
            (composed), `cardlang.parse.DIAGNOSTIC_GRAMMAR` (the file),
            `tools.dead_surface.refusing_methods` over `cardlang.parse._Builder`,
            `cardlang.resolve.ALWAYS_HOLDERS`; the goldens by glob.
does not prove:  that a twin fires for a file holding a twin's slip AND a
            later genuine error -- the composed parse fails on the later
            error and the main error is reported, so the designer meets the
            slip only after fixing the other mistake. Nor that the messages
            themselves are right: `tests/test_rejections.py` pins each
            against its wrong sentence, byte for byte, and this module only
            proves every twin has one. Nor the terminal the file extends
            rather than aliases (`COMP_OP`'s `==` / `!=`): its refusal is
            the `compare` builder's, pinned by its own goldens and never
            a twin node.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

import pytest

from cardlang import parse as parse_module
from cardlang import resolve as resolve_module
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _Builder, _parser, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import ALWAYS_HOLDERS
from tools.dead_surface import default_sources, refusing_methods

ROOT = pathlib.Path(__file__).resolve().parent.parent
REJECTIONS = ROOT / "tests" / "rejections"


def test_the_main_grammar_carries_no_reject_alias() -> None:
    """Red under: one `-> x_reject` alternative left in cardlang.lark."""
    twins = sorted({str(r.alias) for r in _parser().rules if r.alias and str(r.alias).endswith("_reject")})
    assert twins == []


def test_the_main_grammar_has_no_terminal_only_a_refused_rule_names() -> None:
    """Every terminal is named by a rule the builder accepts, so no word exists
    in the lexer only to be refused. Red under: a twin-only terminal
    (`_CARD_VALUES_KW`, `STAKE_FLAG_COLON`) left in cardlang.lark."""
    refusing = refusing_methods(_Builder)
    homes: dict[str, set[bool]] = {}
    for rule in _parser().rules:
        node = str(rule.alias or rule.origin.name)
        refused = node.endswith("_reject") or node in refusing
        for symbol in rule.expansion:
            if symbol.is_term:
                homes.setdefault(str(symbol.name), set()).add(refused)
    assert sorted(t for t, kinds in homes.items() if kinds == {True}) == []


def _diagnostic_twins() -> set[str]:
    """Every node the diagnostic file's productions build."""
    text = parse_module.DIAGNOSTIC_GRAMMAR.read_text()
    return set(re.findall(r"->\s*([a-z_]+)\b", text))


def _twins_the_goldens_exercise() -> set[str]:
    twins = _diagnostic_twins()
    exercised: set[str] = set()
    for fixture in sorted(REJECTIONS.glob("*.cardlang")):
        start = "library" if fixture.read_text().lstrip().startswith("library") else "start"
        try:
            tree = parse_module._diagnostic_parser().parse(fixture.read_text(), start=start)
        except Exception:  # noqa: BLE001 -- a golden that fails both grammars is not a twin's
            continue
        exercised |= {str(sub.data) for sub in tree.iter_subtrees()} & twins
    return exercised


def test_every_diagnostic_twin_is_a_node_the_builder_only_refuses() -> None:
    """A twin exists to refuse, so its builder method raises on every path;
    the composed parse can never hand back a tree the builder accepts. Red
    under: an alias in diagnostics.lark naming a builder method that returns."""
    twins = _diagnostic_twins()
    assert twins, "the diagnostic grammar holds no twin"
    assert twins <= refusing_methods(_Builder)


def test_every_diagnostic_twin_is_exercised_by_a_rejection_golden() -> None:
    """Derived both ways: the twins from the diagnostic file, the exercised set
    from parsing every golden under the composed grammar. Red under: a twin
    added to diagnostics.lark with no golden, or a golden deleted."""
    assert _diagnostic_twins() == _twins_the_goldens_exercise()


def test_the_corpus_never_reaches_the_diagnostic_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Red under: a twin left in the main grammar is harmless here; a corpus
    file written in a retired spelling is what reddens it."""
    def forbidden() -> object:
        raise AssertionError("a live file reached the diagnostic parser")

    monkeypatch.setattr(parse_module, "_diagnostic_parser", forbidden)
    for source in default_sources():
        if source.tier in ("corpus", "shared"):
            parse_module.parse_to_tree(source.text, source.name, start=source.start)


WRONG = (
    "game G {\n  players: 2 2\n  max_length: 10\n  cards: standard52\n"
    "  zones { deck : Deck }\n  phase p { shuffle deck }\n  winner: highest score\n}\n"
)


def test_a_text_neither_grammar_derives_reports_the_main_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The main parser's own error, byte for byte: computed before the second
    parse, so no expected-token list names a retired spelling. Red under:
    reporting the composed parser's error."""
    with pytest.raises(DiagnosticError) as composed:
        parse_text(WRONG, "wrong.cardlang")
    monkeypatch.setattr(parse_module, "_diagnostic_parser", _parser)
    with pytest.raises(DiagnosticError) as main_only:
        parse_text(WRONG + " ", "wrong.cardlang")
    assert composed.value.diagnostic.message == main_only.value.diagnostic.message
    assert composed.value.diagnostic.message.startswith("syntax error: unexpected")
    assert "card_values" not in composed.value.diagnostic.message


_ALWAYS_GAME = """\
game G {{
  players: 2
  max_length: 100
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ score[player] : Integer = 0{declared} }}
  phase play {{
    deal 3 cards from deck to each hand
    offer to 0 one of [pass]
  }}
  winner: highest score
}}
move_type pass {{
  when: {pred}
  effect {{ score[actor] += 1 }}
}}
"""


def test_a_declared_always_is_a_condition_like_any_other() -> None:
    """The one sentence this unit newly accepts: `always` is a name once its
    keyword leaves the lexer, so a game may declare it. Red under: a keyword
    terminal for `always` in the main grammar."""
    game = check_dsl(_ALWAYS_GAME.format(declared="  always : Boolean = true", pred="always"), "g.cardlang")
    assert game.move_types[0].when is not None


# One sentence per holder clause, in the game and in a family library the game
# uses; `{pred}` is the predicate, `{declared}` a state row declaring `always`.
# A rule is consulted at the trick round's card decision alone, so the rule
# holder's game and host carry one; the trick-free move-type holder stays on
# `_ALWAYS_GAME`.
_TRICK_GAME = """\
game G {{
  players: 2
  max_length: 100
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ score[player] : Integer = 0{declared} }}
  phase play {{
    deal 3 cards from deck to each hand
    round play_to_trick from 0 over all players source hand into trick_pile
          winner highest_of_led_suit
  }}
  winner: highest score
}}
"""
_GAME_HOLDERS: dict[str, str] = {
    "when:": _ALWAYS_GAME,
    "applies_when:": _TRICK_GAME + (
        "rule R {{\n  constrains: play_to_trick\n  applies_when: {pred}\n"
        "  demands: cards in hand where card.suit is hearts\n  if_impossible: hand\n}}\n"
    ),
}
_LIBRARY_HOST = _TRICK_GAME.format(declared="  declared_thing : Integer = 0").replace(
    "game G {\n", "game H {\n  uses leaky\n"
)
_LIBRARY_HOLDERS: dict[str, str] = {
    "when:": "library leaky {{ requires {{ declared_thing : Integer }} state {{{declared} }}\n"
             "  move_type m {{ when: {pred}  effect {{ declared_thing := 1 }} }} }}",
    "applies_when:": "library leaky {{ requires {{ declared_thing : Integer  hand[player] : Hand<player> }}"
                     " state {{{declared} }}\n"
                     "  rule R {{ constrains: play_to_trick  applies_when: {pred}"
                     "  demands: cards in hand where declared_thing is 0  if_impossible: hand }} }}",
}


def _check_with_library(library_text: str, monkeypatch: pytest.MonkeyPatch) -> object:
    library = parse_module.parse_library(library_text, "docs/libraries/leaky.cardlang")
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({"leaky"}))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: library)
    return check_dsl(_LIBRARY_HOST, "h.cardlang")


def test_every_holder_has_a_game_and_a_library_sentence() -> None:
    assert set(_GAME_HOLDERS) == set(ALWAYS_HOLDERS) == set(_LIBRARY_HOLDERS)


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
def test_an_undeclared_always_standing_alone_is_told_to_leave_the_clause_out(clause: str) -> None:
    """Resolve's refusal, in the builder's words, for every holder the table
    names. Red under: dropping the `always` arm from resolve."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_GAME_HOLDERS[clause].format(declared="", pred="always"), "g.cardlang")
    assert exc.value.diagnostic.message == (
        f"`always` is not a condition — {ALWAYS_HOLDERS[clause]} has no `{clause}` line; leave it out"
    )


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
def test_an_undeclared_always_in_a_library_clause_is_refused_to_the_library_author(
    clause: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same words, located in the library file: the library walk reads the
    refusal off the classified tree instead of reporting a read past the
    contract. Red under: dropping `always_refused` from `_library_reach`."""
    with pytest.raises(DiagnosticError) as exc:
        _check_with_library(_LIBRARY_HOLDERS[clause].format(declared="", pred="always"), monkeypatch)
    diagnostic = exc.value.diagnostic
    assert diagnostic.message == (
        f"`always` is not a condition — {ALWAYS_HOLDERS[clause]} has no `{clause}` line; leave it out"
    )
    assert diagnostic.span is not None and diagnostic.span.source_name == "docs/libraries/leaky.cardlang"
    assert "requires" not in str(exc.value)


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
def test_a_library_declaring_always_reads_it_as_a_condition(
    clause: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red under: the library walk refusing every bare `always` rather than
    the unclassified one."""
    _check_with_library(
        _LIBRARY_HOLDERS[clause].format(declared=" always : Boolean = true", pred="always"), monkeypatch
    )


def test_an_undeclared_always_as_an_operand_is_an_ordinary_unresolved_name() -> None:
    """Red under: the `always` arm firing on any `NameRef` named `always`
    rather than on the whole predicate."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_ALWAYS_GAME.format(declared="", pred="always and score[actor] is 0"), "g.cardlang")
    assert "unresolved name 'always'" in exc.value.diagnostic.message


def test_every_always_holder_in_the_table_has_a_teaching_sentence() -> None:
    """The holders resolve names are exactly the clauses the orphaned-surface
    pin drives (`tests/test_orphaned_surface_retired.py`, `_ALWAYS_SENTENCES`),
    and each site's field is a field of its node."""
    from tests.test_orphaned_surface_retired import _ALWAYS_SENTENCES

    assert set(ALWAYS_HOLDERS) == {clause for _, clause in _ALWAYS_SENTENCES.values()}
    for node_type, site in resolve_module._ALWAYS_SITES.items():
        assert site.field in {f.name for f in dataclasses.fields(node_type)}
