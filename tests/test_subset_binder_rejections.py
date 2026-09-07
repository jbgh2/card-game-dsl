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
