"""The main grammar accepts only the language; the reject-with-replacement
twins live in the Diagnostic Grammar (`cardlang/grammar/diagnostics.lark`)
and run only when a parse has failed.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   no alias of the compiled main grammar ends `_reject`, no
            terminal of it is named only by a refused rule, and no retired
            operator spelling lexes as its operator there; every twin the
            Diagnostic Grammar holds is a node the builder only refuses and
            is exercised by a rejection golden; a corpus, library or stdlib
            file never reaches the diagnostic parser; a text neither grammar
            derives reports the main parser's own error, or the composed
            parser's where that read past a twin's slip before failing,
            either in the main grammar's words; every golden a twin derives
            it derives once; and `always`, a plain name, is refused by
            resolve where it stands undeclared as the whole predicate of a
            clause the table names, accepted where a game or a library
            declares it as a value, and an ordinary unresolved name as an
            operand or where a definition that is no value bears the name.
domain:     the compiled main grammar's rules and terminals (the first two
            pins) and its lexer against the retired operator spellings of
            decisions.md "The expression register"; the aliases the composed
            parser's compiled rules carry beyond the main parser's, crossed
            with the fixtures under `tests/rejections/` (the twin pin); the
            live tiers of `tools.dead_surface` (the
            never-reached pin); the holders of a predicate resolve's `always`
            table names (`resolve.ALWAYS_HOLDERS`), crossed with
            {declared, undeclared} x {whole predicate, operand} x {written in
            the game, written in a family library}.
registry:   `cardlang.parse._parser()` (main), `cardlang.parse._diagnostic_parser()`
            (composed), `cardlang.parse.DIAGNOSTIC_GRAMMAR` (the file),
            `tools.dead_surface.refusing_methods` over `cardlang.parse._Builder`,
            `cardlang.resolve.ALWAYS_HOLDERS`; the goldens by glob.
does not prove:  that the later-mistake rule picks the right error for a
            file with two slips and a mistake between them -- the composed
            parse reads past the first slip, fails at the mistake, and the
            second slip waits behind both. Nor that the messages
            themselves are right: `tests/test_rejections.py` pins each
            against its wrong sentence, byte for byte, and this module only
            proves every twin has one. Nor that a golden exercises the
            `COMP_OP` extension through a twin node: that refusal is the
            `compare` builder's, pinned by the operator goldens and by the
            lexer pin here. Nor the optional predicate clauses the `always`
            table does not name (a phase's `when`, a movement's or a
            `transition_to`'s `where`), where an undeclared `always` is an
            ordinary unresolved name.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from lark import Lark
from lark.exceptions import UnexpectedCharacters, UnexpectedInput

from cardlang import parse as parse_module
from cardlang import resolve as resolve_module
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _Builder, _parser, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import ALWAYS_HOLDERS
from tests.test_rejections import case_paths
from tools.dead_surface import LIVE_TIERS, default_sources, refusing_methods, start_for



def test_the_main_grammar_carries_no_reject_alias() -> None:
    """Red under: one `-> x_reject` alternative left in cardlang.lark."""
    twins = sorted({str(r.alias) for r in _parser().rules if r.alias and str(r.alias).endswith("_reject")})
    assert twins == []


def test_the_main_grammar_has_no_terminal_only_a_refused_rule_names() -> None:
    """Every terminal is named by a rule the builder accepts, so no word exists
    in the lexer only to be refused. Red under: a twin's arm left in
    cardlang.lark with its terminal (`factor DIV_OP postfix -> div_symbol`
    and `DIV_OP`); a terminal no rule names lark drops, so it is nothing's."""
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
    """Every alias the composed parser's compiled rules carry beyond the main
    parser's: the nodes only a twin builds."""
    main = {str(r.alias) for r in _parser().rules if r.alias}
    return {str(r.alias) for r in parse_module._diagnostic_parser().rules if r.alias} - main


def _twins_the_goldens_exercise() -> set[str]:
    twins = _diagnostic_twins()
    exercised: set[str] = set()
    for fixture in case_paths():
        try:
            tree = parse_module._diagnostic_parser().parse(fixture.read_text(), start=start_for(fixture))
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


def test_every_refusing_builder_method_is_a_twin() -> None:
    """A builder method that raises on every path builds no node, so only a
    twin names it; one no grammar names is dead code. Red under: deleting a
    twin's `%extend` line and its golden but not its builder method."""
    main_nodes = {str(r.alias or r.origin.name) for r in _parser().rules}
    assert refusing_methods(_Builder) - _diagnostic_twins() - main_nodes == set()


def test_every_diagnostic_twin_is_exercised_by_a_rejection_golden() -> None:
    """The twins from the compiled rules, the exercised set from parsing every
    golden under the composed grammar; a golden's node is the grammar's by
    construction, so the pin is that every twin is exercised. Red under: a
    twin added to diagnostics.lark with no golden, or a golden deleted."""
    assert _diagnostic_twins() == _twins_the_goldens_exercise()


_RETIRED_OPERATORS = ("==", "!=", "/", "%")


def test_the_main_lexer_knows_no_retired_operator() -> None:
    """The retired operator spellings (decisions.md "The expression register")
    lex as an operator only under the composed grammar; the main grammar's
    tokens never spell one. Red under: restoring `"==" | "!="` to `COMP_OP`
    in cardlang.lark."""
    composed = Lark(
        parse_module._grammar_text() + "\n" + parse_module.DIAGNOSTIC_GRAMMAR.read_text(),
        parser=None,
        lexer="basic",
        start=list(_parser().options.start),
    )
    for op in _RETIRED_OPERATORS:
        assert {t.type for t in composed.lex(f"a {op} b") if t.value == op} <= {"COMP_OP", "DIV_OP"}
        assert any(t.value == op for t in composed.lex(f"a {op} b"))
        try:
            assert all(t.value != op for t in parse_module._lexer().lex(f"a {op} b"))
        except UnexpectedCharacters:
            pass


def test_the_corpus_never_reaches_the_diagnostic_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Red under: a twin left in the main grammar is harmless here; a corpus
    file written in a retired spelling is what reddens it."""
    def forbidden() -> object:
        raise AssertionError("a live file reached the diagnostic parser")

    monkeypatch.setattr(parse_module, "_diagnostic_parser", forbidden)
    for source in default_sources():
        if source.tier in LIVE_TIERS:
            parse_module.parse_to_tree(source.text, source.name, start=source.start)


# A state row's `:` where `=` belongs: both parsers stop there, and only the
# composed one would offer the `<` a twin accepts after a type name.
WRONG = (
    "game G {\n  players: 2\n  max_length: 10\n  cards: standard52\n"
    "  zones { deck : Deck }\n  state { score[player] : Integer : 0 }\n"
    "  phase p { shuffle deck }\n  winner: highest score\n}\n"
)


# A golden is a game, checked through `check_dsl`, or a library under
# `tests/rejections/libraries/`, parsed through `parse_library`
# (`tests/test_rejections.py`); its start symbol is its directory's
# (`tools.dead_surface.start_for`).


def test_every_golden_a_twin_derives_has_one_derivation() -> None:
    """Under the composed grammar with ambiguity explicit, no golden the main
    grammar refuses parses to an `_ambig` node: the twin that speaks is the
    grammar's choice, never lark's. Red under: a second twin deriving a
    golden's slip (plant `%extend trump: _TRUMP_KW ":" INT -> planted_reject`
    in diagnostics.lark)."""
    explicit = Lark(
        parse_module._grammar_text() + "\n" + parse_module.DIAGNOSTIC_GRAMMAR.read_text(),
        parser="earley",
        ambiguity="explicit",
        propagate_positions=True,
        maybe_placeholders=True,
        start=list(_parser().options.start),
    )
    ambiguous: list[str] = []
    derived = 0
    for fixture in case_paths():
        text = fixture.read_text()
        start = start_for(fixture)
        try:
            _parser().parse(text, start=start)
            continue
        except UnexpectedInput:
            pass
        try:
            tree = explicit.parse(text, start=start)
        except UnexpectedInput:
            continue
        derived += 1
        if any(str(sub.data) == "_ambig" for sub in tree.iter_subtrees()):
            ambiguous.append(fixture.name)
    assert derived and ambiguous == []


def test_a_slip_before_a_later_mistake_reports_the_later_mistake_first() -> None:
    """The composed grammar reads past the slip, so the failure it meets is a
    second mistake, reported in the main grammar's words; the slip's own
    teaching comes once that is fixed. Red under: reporting the main error
    whenever the composed parse fails."""
    slip_game = _ALWAYS_GAME.format(declared="", pred="score[actor] == 1")
    with pytest.raises(DiagnosticError) as later:
        parse_text(slip_game + "}\n", "slip.cardlang")
    message = later.value.diagnostic.message
    assert message.startswith("syntax error: unexpected") and "==" not in message
    assert later.value.diagnostic.span is not None
    assert later.value.diagnostic.span.line == slip_game.count("\n") + 1
    with pytest.raises(DiagnosticError) as slip:
        parse_text(slip_game, "slip.cardlang")
    assert slip.value.diagnostic.message.startswith("`==` is not an operator")


def test_a_text_neither_grammar_derives_reports_the_main_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Where both parsers stop at the same offset, the main parser's own error,
    byte for byte, so the expected-token list offers nothing only a twin
    accepts. Red under: reporting the composed parser's error on a tie -- it
    offers the `<` of the collection twin after a type name."""
    with pytest.raises(DiagnosticError) as composed:
        parse_text(WRONG, "wrong.cardlang")
    monkeypatch.setattr(parse_module, "_diagnostic_parser", _parser)
    with pytest.raises(DiagnosticError) as main_only:
        parse_text(WRONG + " ", "wrong.cardlang")
    message = composed.value.diagnostic.message
    assert message == main_only.value.diagnostic.message
    assert message.startswith("syntax error: unexpected `:`") and message.endswith("expected `=` or `?`")


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


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
def test_a_declared_always_is_a_condition_like_any_other(clause: str) -> None:
    """`always` is a name, so a game may declare it and read it as the whole
    predicate of any holder. Red under: a keyword terminal for `always` in the
    main grammar."""
    check_dsl(_GAME_HOLDERS[clause].format(declared="  always : Boolean = true", pred="always"), "g.cardlang")


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
    """Resolve's refusal, naming the clause to leave out, for every holder the
    table names. Red under: dropping the `always` arm from resolve."""
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
def test_a_library_defining_always_is_not_told_to_leave_the_clause_out(
    clause: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library function named `always`, read without its call, is no omission
    there either: the library walk keeps the refusal `_rewrite` recorded and
    never reconstructs one from an unclassified predicate. Red under: reading
    the refusal off the classified tree instead of the walk's bag."""
    library = _LIBRARY_HOLDERS[clause].format(declared="", pred="always").replace(
        "library leaky {", "library leaky { function always() = true ", 1
    )
    with pytest.raises(DiagnosticError) as exc:
        _check_with_library(library, monkeypatch)
    assert "leave it out" not in str(exc.value)
    assert "reads 'always'" in str(exc.value)


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
def test_a_library_declaring_always_reads_it_as_a_condition(
    clause: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red under: the library walk refusing every bare `always` rather than
    the unclassified one."""
    _check_with_library(
        _LIBRARY_HOLDERS[clause].format(declared=" always : Boolean = true", pred="always"), monkeypatch
    )


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
def test_an_undeclared_always_as_an_operand_is_an_ordinary_unresolved_name(clause: str) -> None:
    """Red under: the `always` arm firing on any `NameRef` named `always`
    rather than on the whole predicate."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_GAME_HOLDERS[clause].format(declared="", pred="always and score[0] is 0"), "g.cardlang")
    assert "unresolved name 'always'" in exc.value.diagnostic.message


@pytest.mark.parametrize("clause", sorted(ALWAYS_HOLDERS))
@pytest.mark.parametrize("definition", ["function always() = true", "move_type always {{ effect {{ }} }}"])
def test_an_always_naming_a_definition_is_an_ordinary_unresolved_name(clause: str, definition: str) -> None:
    """A function named `always`, read without its call, is no condition and
    no omission: the teaching sentence would advise deleting a clause the
    designer meant to keep. Red under: gating the refusal on the value
    namespaces alone."""
    source = _GAME_HOLDERS[clause].format(declared="", pred="always") + definition.format() + "\n"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "g.cardlang")
    assert "unresolved name 'always'" in str(exc.value)
    assert "leave it out" not in str(exc.value)


def test_every_always_holder_in_the_table_has_a_teaching_sentence() -> None:
    """The holders resolve names are exactly the clauses the orphaned-surface
    pin drives (`tests/test_orphaned_surface_retired.py`, `_ALWAYS_SENTENCES`),
    and each site's field is a field of its node."""
    from tests.test_orphaned_surface_retired import _ALWAYS_SENTENCES

    assert set(ALWAYS_HOLDERS) == {clause for _, clause in _ALWAYS_SENTENCES.values()}
    for node_type, site in resolve_module._ALWAYS_SITES.items():
        assert site.field in {f.name for f in dataclasses.fields(node_type)}
