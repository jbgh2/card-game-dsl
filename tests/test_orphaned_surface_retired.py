"""The orphaned surface issue #693 retires stays retired, and `always` teaches.

The operator's orphaned-surface ruling (direction review 2026-09-06: a
surface whose last consumer has left is deleted with its guards and proof
rows) retires the rows of direction-review verdict 7's dead-surface table
that issue #693 lists, the auction form of `round` that issue #819
rewrites as `turns` plus `offer`, and the `burn`, `muck` and `transfer`
synonyms of `move` that issue #835 cuts (the language is minimal: one word
per meaning). `always` is no keyword: a designer who writes it as a whole
predicate, undeclared, is told to leave the clause out (resolve's
`ALWAYS_HOLDERS`).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   no retired row is a rule or alias of the compiled grammar, no
            retired keyword is a keyword terminal, every retired sentence is
            refused at parse with a located diagnostic, and an undeclared
            `always` standing as the whole predicate of every clause
            resolve's table names is refused with a message naming the
            clause to leave out.
domain:     the retired set is the operator's rulings on issues #693, #819
            and #835, listed
            once below as `RETIRED_ROWS`, `RETIRED_KEYWORDS` and
            `RETIRED_SENTENCES`; the `always` positions are the compiled
            rules spelling a clause `cardlang.resolve.ALWAYS_HOLDERS` names
            (a keyword, a colon, one `expr`), read from the parser -- an
            existence check on the table's clauses, never a search for
            clauses the table lacks.
registry:   compiled grammar: `cardlang.parse._parser()` (its `rules` and
            `terminals`); the live report over the same grammar:
            `tools/dead_surface.py`.
does not prove:  that a designer reaching for a retired construct is told
            what to write instead. Outside `always`, a retired sentence
            meets the ordinary syntax error, which names the tokens the
            parser expected at that point and nothing about the retirement.
            Nor `always` declared: that it is then a condition like any
            other is tests/test_diagnostic_grammar.py's cell. Nor the
            optional predicate clauses the table does not name (a phase's
            `when`, a movement's or a `transition_to`'s `where`): an
            undeclared `always` there is an ordinary unresolved name.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _parser, parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import ALWAYS_HOLDERS


RETIRED_ROWS = (
    "type_def",
    "struct_field",
    "struct_lit",
    "field_init",
    "derived_block",
    "derived_field",
    "define_def",
    "actions_where",
    "move_in",
    "named_arg",
    "players_range",
    "require_optional",
    "always",
    # The auction form of `round` (issue #819): every bidding, betting and
    # polling ring is `turns` with an `offer` body.
    "auction_stmt",
    "auction_moves",
)

RETIRED_KEYWORDS = ("type", "derived", "define", "actions", "order", "offering")

_BASE = """\
game G {{
  players: {players}
  max_length: 100
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    deal 3 cards from deck to each hand
    {statement}
    round play_to_trick from 0 over all players source hand into trick_pile
          winner highest_of_led_suit
  }}
  winner: highest score
}}
{top}
"""


def _game(statement: str = "", top: str = "", players: str = "2") -> str:
    return _BASE.format(statement=statement, top=top, players=players)


RETIRED_SENTENCES: dict[str, str] = {
    "struct type": _game(top="type Bid = { level : Integer }"),
    "struct type with derived": _game(
        top="type R = { a : Integer } derived { b = a + 1 }"
    ),
    "struct literal": _game(statement="score[0] := Bid { level: 1 }"),
    "define": _game(top="define settle -> { made | set } { produce made }"),
    "demands actions where": _game(
        top=(
            "rule R {\n  constrains: play_to_trick\n"
            "  demands: actions where action.card_count > 0\n}"
        )
    ),
    "transfer in, no source": _game(statement="move 1 card in deck"),
    # The verb synonyms (issue #835): one terminal carried all three, so one
    # refusal covers them; a sentence per word is the record of each.
    "burn verb": _game(statement="burn 1 card from deck to trick_pile"),
    "muck verb": _game(statement="muck 1 card from deck to trick_pile"),
    "transfer verb": _game(statement="transfer 1 card from deck to trick_pile"),
    "named call argument": _game(statement="score[0] := max(a = 1, 2)"),
    "auction round": _game(
        statement=(
            "round offering [play_to_trick] from 0 over all players "
            "until score[0] > 0"
        )
    ),
    "player range": _game(players="2..4"),
    "auction order clause": _game(
        statement=(
            "round offering [pass] from 0 over all players order ring until true"
        ),
        top="move_type pass { effect { } }",
    ),
}

_OPTIONAL_REQUIRE = "library L {\n  requires { cap : Integer? }\n}"


def _compiled_rule_names() -> set[str]:
    names: set[str] = set()
    for rule in _parser().rules:
        names.add(rule.origin.name)
        if rule.alias:
            names.add(rule.alias)
    return names


def _keyword_words() -> set[str]:
    return {
        term.pattern.value
        for term in _parser().terminals
        if term.name.endswith("_KW") and term.pattern.type == "str"
    } | {
        term.pattern.value.split("(?!")[0]
        for term in _parser().terminals
        if term.name.endswith("_KW") and term.pattern.type == "re"
    }


@pytest.mark.parametrize("row", RETIRED_ROWS)
def test_retired_row_is_not_in_the_compiled_grammar(row: str) -> None:
    assert row not in _compiled_rule_names()


@pytest.mark.parametrize("word", RETIRED_KEYWORDS)
def test_retired_keyword_is_not_a_keyword_terminal(word: str) -> None:
    assert word not in _keyword_words()


@pytest.mark.parametrize("name", sorted(RETIRED_SENTENCES))
def test_retired_sentence_is_refused_at_parse(name: str) -> None:
    with pytest.raises(DiagnosticError) as exc:
        parse_text(RETIRED_SENTENCES[name], "retired.cardlang")
    assert exc.value.diagnostic.span is not None


def test_optional_required_variable_is_refused_at_parse() -> None:
    with pytest.raises(DiagnosticError) as exc:
        parse_library(_OPTIONAL_REQUIRE, "retired.cardlang")
    assert exc.value.diagnostic.span is not None


def _always_positions() -> set[str]:
    """The compiled rules spelling a clause resolve's `always` table names --
    a keyword, a colon, one `expr` -- so a table row whose clause leaves the
    grammar, or changes shape, reddens the sentence table below."""
    words = {clause[:-1] for clause in ALWAYS_HOLDERS}
    keyword_of = {
        term.name: term.pattern.value.split("(?!")[0]
        for term in _parser().terminals
        if term.name.endswith("_KW")
    }
    return {
        rule.origin.name
        for rule in _parser().rules
        if [s.name for s in rule.expansion[1:]] == ["COLON", "expr"]
        and keyword_of.get(rule.expansion[0].name) in words
    }


_ALWAYS_SENTENCES: dict[str, tuple[str, str]] = {
    "applies_when": (
        _game(
            top=(
                "rule R {\n  constrains: play_to_trick\n  applies_when: always\n"
                "  demands: cards in hand where card.suit is hearts\n"
                "  if_impossible: cards in hand\n}"
            )
        ),
        "applies_when:",
    ),
    "move_when": (
        _game(top="move_type pass {\n  when: always\n  effect { }\n}"),
        "when:",
    ),
}


def test_always_positions_are_exactly_the_sentences_below() -> None:
    """The derived position set equals the hand-written sentence table, so a
    clause added to resolve's table arrives here as a missing sentence.

    red under: add a third `<keyword> ":" expr` clause to cardlang.lark and
    its row to `ALWAYS_HOLDERS`."""
    assert _always_positions() == set(_ALWAYS_SENTENCES)


@pytest.mark.parametrize("position", sorted(_ALWAYS_SENTENCES))
def test_always_is_refused_naming_the_clause_to_leave_out(position: str) -> None:
    source, clause = _ALWAYS_SENTENCES[position]
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "always.cardlang")
    message = exc.value.diagnostic.message
    assert exc.value.diagnostic.span is not None
    assert "`always`" in message and f"`{clause}`" in message and "leave" in message
