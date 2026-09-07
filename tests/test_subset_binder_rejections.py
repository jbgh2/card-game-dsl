"""Misuse probes for the subset binder: the sentences an author gets wrong.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   each of the most plausible wrong sentences meets a diagnostic in
            the layer that owns it, with a span, and none parses to a
            DIFFERENT working meaning.
domain:     the five misuse categories decisions.md "Surface totality" names,
            instantiated for this construct: an omitted mandatory clause whose
            boundary token an operand can absorb; a wrong-typed operand in each
            of the construct's three typed positions (the count, the predicate,
            the binder used as a card); the `in` spelling, which is a live form
            with a different meaning rather than a retired one; the binder
            referenced with no introducing construct; and the boundary slips --
            the singular/plural swap in both directions, the fused count, and
            the dropped size clause.
            One boundary, stated positively: the binder cannot reach a movement
            source, an epistemic target, or any other statement position,
            because the only fields it scopes to are the predicate and the
            aggregated body, and both are expressions. That pairwise cell is
            grammatically inexpressible, not merely unchecked.
registry:   the accepting side of every sentence here is the grid,
            tests/test_subset_binder_grid.py; the count guard's own wording is
            pinned there too.
does not prove:  that the diagnostics READ well to a designer. What is pinned
            is the layer, the span and the substring each names; whether the
            whole rendered message still says what it was written to say is
            the rejection corpus's job (tests/test_rejections.py), and only
            the guard with a case there has that.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _game(body: str) -> str:
    return (
        "game G {\n  players: 2\n  max_length: 100\n  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  table : Discard  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n  winner: highest score\n"
        "  phase p {\n"
        f"{body}\n  }}\n}}\n"
    )


# (label, the sentence, a substring the diagnostic must carry)
_PROBES: list[tuple[str, str, str]] = [
    # 1. Omitted mandatory clause, with an ABSORBING operand: the order
    #    aggregators' `or <default>` shares its token with a compound `where`,
    #    so the last disjunct is eaten and the sentence still parses. A
    #    truncated probe would only test the parser's error path.
    (
        "absorbed default",
        "    score[0] := highest 1 over subsets of 2 cards in table "
        "where 1 is 1 or 2 is 2",
        "absorbed by the",
    ),
    # 2. Wrong-typed operand, in each typed position the construct owns.
    (
        "collection where a Boolean is wanted",
        "    if any subset of 2 cards in table where subset { score[0] := 1 }",
        "must be Boolean, got Collection<Card>",
    ),
    (
        "a size that is not a count",
        '    score[0] := number of subsets of "two" cards in table where 1 is 1',
        "a subset size counts cards",
    ),
    (
        "the set handed to a card function",
        "    score[0] := number of subsets of 2 cards in table "
        "where rank_value(subset) is 1",
        "expects Card, got Collection<Card>",
    ),
    # 3. The `in` spelling. Not a retired spelling — a LIVE form with a
    #    different meaning, so the message must say which form was reached.
    (
        "the `in` spelling",
        "    if any subset in table where 1 is 1 { score[0] := 1 }",
        "subsets are spelled with `of`",
    ),
    # 4. The binder outside any introducing construct.
    (
        "binder out of scope",
        "    score[0] := number of cards in subset",
        "unresolved name 'subset'",
    ),
    # 5. Boundary slips: the noun's number in both directions, the fused
    #    count, and the size clause dropped altogether.
    ("plural noun under `any`", "    if any subsets of 2 cards in table where 1 is 1 "
     "{ score[0] := 1 }", "syntax error"),
    ("singular noun under `all`", "    if all subset of 2 cards in table where 1 is 1 "
     "{ score[0] := 1 }", "syntax error"),
    ("fused count", "    score[0] := number of subsets of 2ormore cards in table "
     "where 1 is 1", "syntax error"),
    ("no size clause", "    score[0] := number of subsets in table where 1 is 1",
     "syntax error"),
]


@pytest.mark.parametrize("label,body,carries", _PROBES, ids=[p[0] for p in _PROBES])
def test_a_plausible_wrong_sentence_is_refused_loudly(
    label: str, body: str, carries: str
) -> None:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(body), "misuse.cardlang")
    message = str(exc.value)
    assert carries in message, message
    # A diagnostic with no span cannot be pointed at, which is half of what
    # makes it a diagnostic rather than a crash.
    assert "misuse.cardlang:" in message, message


def test_the_size_clause_cannot_be_dropped_silently() -> None:
    """The size clause is mandatory, and the sentence that omits it must not
    reach a DIFFERENT working form. `number of subsets in table where ...`
    could plausibly have been absorbed by the collection quantifier's
    `number of <noun> where ...`, which would have counted something real and
    said nothing.

    red under: add `| _NUMBER_KW _OF_KW _SUBSETS_KW _IN_KW zone_expr
    _WHERE_KW expr` to `subset_query`."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("    score[0] := number of subsets in table where 1 is 1"),
                  "misuse.cardlang")
    assert "expected `of`" in str(exc.value), str(exc.value)


# --- the union source: the wrong spellings and the wrong members ------------
# Each of these is a sentence a designer would plausibly write for "these two
# zones together" without the brackets. The bare comma has the language's own
# precedent (`reads a, b`), `+` reads as addition, and `and` is the boolean
# operator three words later -- each meets a rejection that NAMES the bracket
# list, never a bare token error, on the `trick_order_comma_reject`
# precedent, in every form where a mandatory clause follows the source (the
# three query forms, the ordering fold). A member that is not a zone meets
# the shared source Owner Guard -- the message a lone source earns
# (`typecheck._check_card_source`), because the member check IS that guard
# applied per member, and a second wording would be a Shadow Guard. The rest
# are lists written where the language does not offer one, which stay syntax
# errors and must not silently parse as something else.
_UNION_PROBES: list[tuple[str, str, str]] = [
    ("comma", "    score[0] := number of subsets of 2 cards in table, hand[0] where 1 is 1",
     "[table, hand[p]]"),
    ("plus", "    score[0] := number of subsets of 2 cards in table + hand[0] where 1 is 1",
     "[table, hand[p]]"),
    ("and", "    score[0] := number of subsets of 2 cards in table and hand[0] where 1 is 1",
     "[table, hand[p]]"),
    ("plus, in the ordering fold",
     "    score[0] := highest 1 over subsets of 2 cards in table + hand[0] or 0",
     "[table, hand[p]]"),
    ("a state variable as a member",
     "    score[0] := number of subsets of 2 cards in [table, score] where 1 is 1",
     "expects a zone or collection of cards"),
    ("the list bound by let first",
     "    let both = [table, hand[0]]\n"
     "    score[0] := number of subsets of 2 cards in both where 1 is 1",
     "listed in the subset source itself"),
]

# Born green, and staying green: sentences that are syntax errors today and
# must REMAIN syntax errors after the union lands -- never a silent parse to
# some other meaning. Each names the edit that would redden it.
#   a number or player collection as a member:
#       red under: widen `subset_source`'s member from `zone_expr` to `expr`.
#   empty brackets:
#       red under: make the list's members optional, `"[" [zone_expr ("," zone_expr)*] "]"`.
#   a trailing comma:
#       red under: make the trailing member optional, `("," [zone_expr])*`.
#   an unclosed list:
#       red under: make the closing bracket optional, `["]"]`.
#   the list in a card query:
#       red under: give `cq_count`'s source the `subset_source` production.
#   a nested list:
#       red under: widen the list's member from `zone_expr` to `subset_source`.
#   a misjoin behind the `sum` fold's open end:
#       red under: give `agg_subset_sum` the guarded `subset_of_guarded` --
#       the edit `test_a_plus_behind_the_sum_fold_gets_no_wrong_fix` below
#       exists to refuse.
_UNION_STAYS_A_SYNTAX_ERROR: list[tuple[str, str]] = [
    ("empty brackets", "    score[0] := number of subsets of 2 cards in [] where 1 is 1"),
    ("a trailing comma", "    score[0] := number of subsets of 2 cards in [table,] where 1 is 1"),
    ("an unclosed list", "    score[0] := number of subsets of 2 cards in [table, hand[0] where 1 is 1"),
    ("a number as a member",
     "    score[0] := number of subsets of 2 cards in [table, 5] where 1 is 1"),
    ("a player collection as a member",
     "    score[0] := number of subsets of 2 cards in [table, all players] where 1 is 1"),
    ("the list in a card query",
     "    score[0] := number of cards in [table, hand[0]]"),
    ("a nested list",
     "    score[0] := number of subsets of 2 cards in [[table], hand[0]] where 1 is 1"),
    ("a misjoin behind the sum fold",
     "    score[0] := sum of 1 over subsets of 2 cards in table + hand[0] where 1 is 1"),
]


@pytest.mark.parametrize("label,body,carries", _UNION_PROBES, ids=[p[0] for p in _UNION_PROBES])
def test_a_wrong_union_is_refused_loudly(label: str, body: str, carries: str) -> None:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(body), "misuse.cardlang")
    message = str(exc.value)
    assert carries in message, message
    assert "misuse.cardlang:" in message, message


@pytest.mark.parametrize("label,body", _UNION_STAYS_A_SYNTAX_ERROR,
                         ids=[p[0] for p in _UNION_STAYS_A_SYNTAX_ERROR])
def test_a_malformed_union_stays_a_syntax_error(label: str, body: str) -> None:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(body), "misuse.cardlang")
    message = str(exc.value)
    assert "syntax error" in message, message
    assert "misuse.cardlang:" in message, message


def test_a_plus_behind_the_sum_fold_gets_no_wrong_fix() -> None:
    """`sum of 1 over subsets of 2 cards in table + score[1]` is a fold
    missing its parentheses (a fold is an `expr`, never an operand), and
    behind the sum fold's open end nothing says it was a source instead. It
    meets the parser's own refusal, never the twin's zone-list fix. Born
    green; red under: give `agg_subset_sum` the guarded `subset_of_guarded`
    in the grammar (the twin then claims the sentence and names the bracket
    list)."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("    score[0] := sum of 1 over subsets of 2 cards in table + score[1]"),
                  "misuse.cardlang")
    message = str(exc.value)
    assert "syntax error" in message, message
    assert "[table, hand[p]]" not in message, message
